"""Social 0.3.145 real route and envelope regression; fake host, NOT live QA."""
import tempfile
import unittest
from pathlib import Path

from src.hostless_lobby import HostlessLobbyStore, LobbyError
from src.lobby_runtime import TrustedGame, VerifiedActor
from src.social_0145_binding import (
    SOCIAL_CHALLENGE_ROUTE, SOCIAL_CONTACT_ROUTE, Social0145ServiceRoutes,
    bind_social0145_multiplayer,
)

ISSUER = 'social-production-issuer'
GAME = TrustedGame('life.loop', 'life-deployment-1', 'thebigtreeinc', 'active')


class FakeSocial0145:
    """Fixtures copied from Social 0.3.145 server contract, not client inbox data."""
    def __init__(self):
        self.status = 'pending'
        self.friends = True
        self.online = True
        self.calls = []
        self.override = None

    def __call__(self, route, body):
        self.calls.append((route, body))
        if not self.online:
            raise ConnectionError('private Social backend')
        if self.override is not None:
            return self.override
        if route == SOCIAL_CHALLENGE_ROUTE:
            assert body == {'schema':'atrium.social-challenge-status/v1','challengeId':123}
            return {'schema':'atrium.social-challenge-status/v1',
                    'challengeId':123, 'issuer':ISSUER, 'sender':'acct_1',
                    'recipient':'acct_2','gameId':'life','status':self.status,
                    'original':True}
        if route == SOCIAL_CONTACT_ROUTE:
            assert body == {'schema':'atrium.social-contact-status/v1','issuer':ISSUER,
                            'sender':'acct_1','recipient':'acct_2'}
            return {'schema':'atrium.social-contact-status/v1',
                    'issuer':ISSUER,'sender':'acct_1','recipient':'acct_2',
                    'accepted':self.friends}
        raise AssertionError('unknown Social route')


class FakeLifeService:
    """Fake of Life's PROPOSED server API, not a deployed Life backend."""
    def __init__(self):
        self.match = 'life_match_000123'
        self.seats = {'acct_1'}
        self.join_allowed = True
        self.finished = False
        self.calls = []

    def __call__(self, operation, body, grant, game):
        self.calls.append((operation, dict(body)))
        assert game == GAME
        assert grant['audience'] == 'life.loop'
        subject = grant['subject']
        if operation == 'create':
            assert subject == 'acct_1'
            return {'schema':'looprd.game-play/v1','ok':True,
                    'result':{'matchId':self.match,'gameId':GAME.game_id,
                              'requestId':body['requestId'],'creator':subject,'confirmed':True}}
        if operation == 'match.attest':
            return {'schema':'atrium.life-match-attestation/v1','gameId':GAME.game_id,
                    'matchId':self.match,'creator':'acct_1',
                    'requestId':body['requestId'],'confirmed':True}
        if operation == 'join':
            if self.join_allowed and subject == 'acct_2' and body['socialChallengeId'] == 123:
                self.seats.add(subject)
                allowed = True
            else:
                allowed = False
            return {'schema':'looprd.game-play/v1','gameId':GAME.game_id,
                    'matchId':self.match,'subject':subject,'joined':allowed}
        if operation in ('seat.verify','resume'):
            allowed = subject in self.seats
            return {'schema':'looprd.game-play/v1','gameId':GAME.game_id,
                    'matchId':self.match,'subject':subject,'authorized':allowed,
                    'seat':(0 if subject == 'acct_1' else 1) if allowed else None}
        if operation == 'status':
            return {'schema':'looprd.game-play/v1','gameId':GAME.game_id,
                    'matchId':self.match,'subject':subject,
                    'status':'completed' if self.finished else 'active'}
        raise AssertionError('unreviewed Life op')


class Social0145IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'atrium-lobbies.sqlite'
        self.social = FakeSocial0145()
        self.life = FakeLifeService()
        self.active = True
        self._bind()

    def _bind(self):
        def auth(context):
            if context in ('a','b'):
                return VerifiedActor('acct_1' if context == 'a' else 'acct_2',
                                     ISSUER, 'atrium.lobby')
            return None
        self.runtime, self.bridge = bind_social0145_multiplayer(
            HostlessLobbyStore(self.db, clock=lambda:1730000000),
            authenticate=auth,
            resolve_game=lambda game_id, deployment: GAME if self.active else None,
            issue_life_grant=lambda actor, game: {'subject':actor.subject,'audience':'life.loop'},
            social_service_call=self.social, life_exchange=self.life,
            social_issuer=ISSUER, catalog_game_id='life')

    def _create(self):
        return self.runtime.dispatch('a','new_game',
            {'requestId':'life_create_000001','gameId':'life.loop',
             'deploymentId':'life-deployment-1'})

    def _attach(self):
        room = self._create()
        self.bridge.attach('a', lobby_id=room['lobbyId'],challenge_id=123)
        return room

    def test_exact_social_0145_paths_and_two_subject_restart_resume(self):
        room=self._attach()
        self.assertEqual(room['state'],'ready')
        self.assertEqual(self.social.calls[-1][0], SOCIAL_CONTACT_ROUTE)
        self.social.status='accepted'
        joined=self.bridge.accept('b',challenge_id=123)
        self.assertEqual(joined['matchId'],room['matchId'])
        self.assertEqual(len([x for x in self.life.calls if x[0]=='join']),1)
        self._bind()  # real SQLite persisted across new runtime/bridge instances
        self.assertEqual(self.runtime.dispatch('b','resume',{'lobbyId':room['lobbyId']})['state'],'ready')
        self.assertEqual(self.bridge.status('b',challenge_id=123)['canResume'],True)
        self.assertEqual(self.bridge.accept('b',challenge_id=123)['matchId'],room['matchId'])
        self.assertEqual({r for r, _ in self.social.calls},
                         {SOCIAL_CHALLENGE_ROUTE,SOCIAL_CONTACT_ROUTE})
        # Replay is idempotent; Life's authority still decides the game seat.
        self.assertEqual(self.runtime.dispatch('a','leave',{'lobbyId':room['lobbyId']})['matchUnchanged'],True)
        self.assertEqual(self.runtime.dispatch('b','resume',{'lobbyId':room['lobbyId']})['state'],'ready')

    def test_denials_do_not_grant_unauthorized_life_seat(self):
        room=self._attach()
        self.social.status='declined'
        with self.assertRaisesRegex(LobbyError,'social_challenge_not_accepted'):
            self.bridge.accept('b',challenge_id=123)
        self.social.status='accepted'
        self.social.friends=False
        with self.assertRaisesRegex(LobbyError,'not_accepted_tavi_friends'):
            self.bridge.accept('b',challenge_id=123)
        self.social.friends=True
        self.life.join_allowed=False
        with self.assertRaisesRegex(LobbyError,'life_seat_admission_denied'):
            self.bridge.accept('b',challenge_id=123)
        self.assertNotIn('acct_2',self.life.seats)
        self.life.join_allowed=True
        self.active=False
        with self.assertRaisesRegex(LobbyError,'game_not_published'):
            self.bridge.accept('b',challenge_id=123)
        self.active=True
        with self.assertRaisesRegex(LobbyError,'not_challenge_recipient'):
            self.bridge.accept('a',challenge_id=123)
        self.assertEqual(room['state'],'ready')

    def test_fail_closed_on_spoofed_social_mismatch_denial_and_outage(self):
        room=self._attach()
        self.social.status='accepted'
        for patch in ({'original':False}, {'gameId':'checkers'}, {'issuer':'wrong'},
                      {'recipient':'acct_3'}, {'accepted':True},
                      {'ok':False,'reason':'caller_not_approved'}):
            valid = FakeSocial0145()(SOCIAL_CHALLENGE_ROUTE,
                {'schema':'atrium.social-challenge-status/v1','challengeId':123})
            valid.update(patch)
            self.social.override=valid
            with self.subTest(patch=patch),self.assertRaises(LobbyError):
                self.bridge.accept('b',challenge_id=123)
        self.social.override=None
        self.social.online=False
        with self.assertRaises(LobbyError):
            self.bridge.accept('b',challenge_id=123)
        self.assertNotIn('acct_2',self.life.seats)
        self.social.online=True
        self.assertEqual(self.bridge.accept('b',challenge_id=123)['matchId'],room['matchId'])

    def test_adapter_rejects_client_chosen_method_or_extra_authority(self):
        adapter=Social0145ServiceRoutes(self.social)
        for method, payload in [
            ('DELETE',{}),
            ('challenge.status',{'schema':'atrium.social-challenge-status/v1','challengeId':123,'token':'x'}),
            ('challenge.status',{'schema':'atrium.social-challenge-status/v1','challengeId':True}),
            ('contact.status',{'schema':'atrium.social-contact-status/v1','issuer':ISSUER,
                               'sender':'acct_1','recipient':'acct_2','url':'attacker'}),
        ]:
            with self.subTest(method=method),self.assertRaises(LobbyError):
                adapter(method,payload)
        with self.assertRaises(LobbyError):
            Social0145ServiceRoutes(None)


if __name__ == '__main__':
    unittest.main()
