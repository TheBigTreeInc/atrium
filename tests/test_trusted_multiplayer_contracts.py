"""Social/Life interop candidate source tests; no real external service is claimed."""
import tempfile
import unittest
from pathlib import Path

from src.hostless_lobby import HostlessLobbyStore, LobbyError
from src.lobby_runtime import VerifiedActor, TrustedGame
from src.trusted_multiplayer_contracts import (TrustedSocialStatus, TrustedLifeAuthority,
    bind_trusted_multiplayer, SOCIAL_LOOKUP, SOCIAL_CONTACT, LIFE_PLAY, LIFE_ATTEST)

ISSUER='reviewed-social-installation-42'
GAME=TrustedGame('life.loop','life-runtime-1','thebigtreeinc','active')
MATCH='life_match_abcdefgh123456'


class StubServices:
    def __init__(self):
        self.available=True
        self.challenge_status='pending'
        self.friend=True
        self.seats={'acct_1':0}
        self.calls=[]
        self.created={}
        self.bad_reply=None
        self.game=GAME

    def authenticate(self, context):
        return VerifiedActor(context,ISSUER,'atrium.lobby')

    def resolve(self, game_id, deployment_id):
        return self.game

    def grant(self, actor, game):
        return ('life-trusted-bound-identity',actor.subject,game.game_id)

    def social(self, operation, payload):
        self.calls.append(('social',operation,payload))
        if not self.available: raise OSError('secret internal service error: do-not-log')
        if operation=='challenge.status':
            if payload!={'schema':SOCIAL_LOOKUP,'challengeId':123}: raise ValueError('unknown')
            result=dict(schema=SOCIAL_LOOKUP,challengeId=123,issuer=ISSUER,sender='acct_1',
                        recipient='acct_2',gameId='life',status=self.challenge_status,original=True)
        elif operation=='contact.status':
            result=dict(schema=SOCIAL_CONTACT,issuer=ISSUER,sender='acct_1',recipient='acct_2',accepted=self.friend)
        else: raise ValueError('unknown')
        if self.bad_reply and self.bad_reply[0]=='social':result[self.bad_reply[1]]=self.bad_reply[2]
        return result

    def life(self, op, payload, grant, game):
        self.calls.append(('life',op,payload))
        if not self.available:raise OSError('secret internal service error: do-not-log')
        assert game==self.game
        assert grant[0]=='life-trusted-bound-identity' and grant[2]=='life.loop'
        subject=grant[1]
        if op=='create':
            assert payload['schema']==LIFE_PLAY
            self.seats.setdefault(subject,0)
            self.created.setdefault((subject,payload['requestId']), MATCH)
            result={'schema':LIFE_PLAY,'ok':True,'result':{'gameId':game.game_id,
              'matchId':self.created[(subject,payload['requestId'])],
              'requestId':payload['requestId'],'creator':subject,'confirmed':True}}
        elif op=='match.attest':
            assert payload['schema']==LIFE_ATTEST
            result={'schema':LIFE_ATTEST,'matchId':payload['matchId'],'gameId':game.game_id,
              'creator':subject,'requestId':payload['requestId'],
              'confirmed':self.created.get((subject,payload['requestId']))==payload['matchId']}
        elif op=='join':
            assert payload['schema']==LIFE_PLAY and payload['socialChallengeId']==123
            if subject=='acct_2' and self.challenge_status=='accepted' and self.friend:self.seats[subject]=1
            result={'schema':LIFE_PLAY,'gameId':game.game_id,'matchId':payload['matchId'],
                    'subject':subject,'joined':subject in self.seats}
        elif op in ('seat.verify','resume'):
            assert payload['schema']==LIFE_PLAY
            seat=self.seats.get(subject)
            result={'schema':LIFE_PLAY,'gameId':game.game_id,'matchId':payload['matchId'],
                    'subject':subject,'authorized':seat is not None,'seat':seat}
        elif op=='status':
            result={'schema':LIFE_PLAY,'gameId':game.game_id,'matchId':payload['matchId'],
                    'subject':subject,'status':'active'}
        else:raise ValueError('unknown op')
        if self.bad_reply and self.bad_reply[0]=='life':result[self.bad_reply[1]]=self.bad_reply[2]
        return result


class MultiplayerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'hostless.db'
        self.services=StubServices()
        self.store=HostlessLobbyStore(self.db)
        self.runtime,self.bridge=self.bound()

    def tearDown(self):self.tmp.cleanup()

    def bound(self):
        s=self.services
        return bind_trusted_multiplayer(self.store,authenticate=s.authenticate,
          resolve_game=s.resolve,issue_life_grant=s.grant,
          social_exchange=s.social,life_exchange=s.life,
          social_issuer=ISSUER,catalog_game_id='life')

    def new_lobby(self):
        p={'requestId':'stable_request_12345678','gameId':'life.loop','deploymentId':'life-runtime-1'}
        return self.runtime.dispatch('acct_1','new_game',p)

    def test_create_attach_accept_join_resume_survives_clients_and_server_restart(self):
        lobby=self.new_lobby()
        self.assertEqual(lobby['state'],'ready')
        self.assertEqual(lobby['matchId'], MATCH)
        self.assertEqual(self.bridge.attach('acct_1',lobby_id=lobby['lobbyId'],challenge_id=123)['status'],'awaiting_friend')
        with self.assertRaisesRegex(LobbyError,'social_challenge_not_accepted'):
            self.bridge.accept('acct_2',challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'), [])
        self.services.challenge_status='accepted'
        friend=self.bridge.accept('acct_2',challenge_id=123)
        self.assertEqual(friend['matchId'],MATCH)
        self.assertEqual(self.bridge.status('acct_2',challenge_id=123)['canResume'],True)
        self.assertEqual(self.new_lobby()['lobbyId'],lobby['lobbyId'])
        self.store=HostlessLobbyStore(self.db)
        self.runtime,self.bridge=self.bound()
        self.assertEqual(self.bridge.accept('acct_2',challenge_id=123)['lobbyId'],lobby['lobbyId'])
        self.assertEqual(self.runtime.dispatch('acct_2','resume',{'lobbyId':lobby['lobbyId']})['matchId'],MATCH)
        self.assertEqual(len([x for x in self.store.pending_events() if x['type']=='lobby.joined']),1)

    def test_wrong_actor_or_inactive_deployment_never_grants_membership(self):
        lobby=self.new_lobby()
        self.bridge.attach('acct_1',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.services.challenge_status='accepted'
        with self.assertRaisesRegex(LobbyError,'not_challenge_recipient'):
            self.bridge.accept('acct_3',challenge_id=123)
        self.services.game=TrustedGame(GAME.game_id,GAME.deployment_id,'different.publisher','active')
        with self.assertRaisesRegex(LobbyError,'game_not_published'):
            self.bridge.accept('acct_2',challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'),[])

    def test_social_response_cannot_be_sender_notification_or_wrong_pair(self):
        lobby=self.new_lobby()
        for field,value in [('original',False),('challengeId',124),('issuer','foreign'),
                           ('gameId','life.loop'),('sender','acct_3'),('status','forged')]:
            with self.subTest(field=field),self.assertRaisesRegex(LobbyError,'social'):
                self.services.bad_reply=('social',field,value)
                self.bridge.attach('acct_1',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.services.bad_reply=None
        self.services.friend=False
        with self.assertRaisesRegex(LobbyError,'not_accepted_tavi_friends'):
            self.bridge.attach('acct_1',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'),[])

    def test_forged_life_seat_or_creator_confirmation_never_binds(self):
        self.services.bad_reply=('life','ok',1)
        with self.assertRaisesRegex(LobbyError,'life_match_creation_unavailable'):
            self.new_lobby()
        self.assertEqual(self.store.list_for('acct_1')[0]['state'],'pending')
        self.services.bad_reply=('life','creator','acct_3')
        with self.assertRaisesRegex(LobbyError,'life_match_creation_unavailable'):
            self.new_lobby()
        self.services.bad_reply=None
        lobby=self.new_lobby()
        self.bridge.attach('acct_1',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.services.challenge_status='accepted'
        self.services.bad_reply=('life','seat',True)
        with self.assertRaisesRegex(LobbyError,'life_seat_admission_unavailable|life_seat_unverified'):
            self.bridge.accept('acct_2',challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'),[])

    def test_outage_retains_lobby_and_retries_without_secrets(self):
        lobby=self.new_lobby()
        self.bridge.attach('acct_1',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.services.challenge_status='accepted'
        self.services.available=False
        with self.assertRaises(LobbyError) as ctx:
            self.bridge.accept('acct_2',challenge_id=123)
        self.assertNotIn('do-not-log',str(ctx.exception))
        self.assertEqual(self.store.list_for('acct_2'),[])
        self.services.available=True
        self.assertEqual(self.bridge.accept('acct_2',challenge_id=123)['matchId'],MATCH)

    def test_transport_fails_closed_if_missing_bound_host_services(self):
        with self.assertRaisesRegex(LobbyError,'social_service_binding_required'):
            TrustedSocialStatus(None,issuer=ISSUER,catalog_game_id='life')
        with self.assertRaisesRegex(LobbyError,'life_service_binding_required'):
            TrustedLifeAuthority(None)
        with self.assertRaisesRegex(LobbyError,'social_service_binding_required'):
            bind_trusted_multiplayer(self.store,authenticate=self.services.authenticate,
              resolve_game=self.services.resolve,issue_life_grant=self.services.grant,
              social_exchange=self.services.social,life_exchange=self.services.life,
              social_issuer='',catalog_game_id='life')

if __name__=='__main__':unittest.main()
