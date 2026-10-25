"""Source-only Tavi 0.3.113 challenge -> Atrium lobby -> Life seat handshake.

These tests use fake trusted service callbacks, never a browser/credential payload.
They do not claim a real Social service-side challenge lookup exists today.
"""
import tempfile
from dataclasses import replace
from pathlib import Path
import unittest

from src.hostless_lobby import HostlessLobbyStore, LobbyError
from src.lobby_runtime import HostlessLobbyRuntime, VerifiedActor, TrustedGame
from src.social_challenge_bridge import SocialChallengeBridge, VerifiedSocialChallenge


class LifeAuthority:
    def __init__(self):
        self.seats = {'acct_1'}
        self.available = True
        self.calls = []
        self.created = {}

    def create_match(self, game, grant, principal, request):
        self.calls.append(('create_match',principal,request))
        if not self.available: raise ConnectionError('Life service offline')
        key=(principal,request)
        if key not in self.created:
            self.created[key]='life_match_012345'
        return self.created[key]

    def verify_match(self, game, grant, match, principal, request):
        self.calls.append(('match', principal, match))
        return self.available and principal == 'acct_1' and match == 'life_match_012345'

    def verify_seat(self, game, grant, match, principal, lobby):
        self.calls.append(('seat', principal, match))
        return self.available and principal in self.seats and grant['subject'] == principal

    def can_resume(self, game, grant, match, principal):
        self.calls.append(('resume', principal, match))
        return self.available and principal in self.seats and grant['subject'] == principal

    def verify_finished(self, *args):
        return False


class SocialLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'hosted-lobbies.sqlite'
        self.store = HostlessLobbyStore(self.path, clock=lambda: 1720000000)
        self.social_issuer = 'social-instance-test-1'
        self.accounts = {'a': 'acct_1', 'b': 'acct_2', 'c': 'acct_3'}
        self.life = LifeAuthority()
        self.game = TrustedGame('life.loop', 'life-host-1', 'thebigtreeinc', 'active')
        self.challenge = VerifiedSocialChallenge(123, self.social_issuer, 'acct_1', 'acct_2', 'life', 'pending')
        self.friend = True
        self.social_available = True
        self.runtime = self.make_runtime(self.store)
        self.bridge = self.make_bridge(self.runtime)

    def make_runtime(self, store):
        def auth(context):
            if context not in self.accounts:
                return None
            return VerifiedActor(self.accounts[context], self.social_issuer, 'atrium.lobby')
        return HostlessLobbyRuntime(store, authenticate=auth,
            resolve_game=lambda game_id, dep: self.game,
            issue_life_grant=lambda actor,game:{'audience':'life.loop', 'subject':actor.subject},
            life=self.life, social_issuer=self.social_issuer)

    def make_bridge(self, runtime):
        def lookup(challenge_id):
            if not self.social_available:
                raise ConnectionError('Social service down')
            return self.challenge
        return SocialChallengeBridge(runtime, get_challenge=lookup,
            accepted_contact=lambda issuer,a,b: self.friend,
            catalog_game_id='life')

    def ready(self, request='request_challenge_1234'):
        pending = self.runtime.dispatch('a', 'create', {'requestId':request, 'gameId':'life.loop', 'deploymentId':'life-host-1'})
        assert pending['state']=='pending'
        return self.runtime.dispatch('a', 'bind_match', {'lobbyId':pending['lobbyId'], 'matchId':'life_match_012345'})

    def linked(self):
        lobby = self.ready()
        attached=self.bridge.attach('a', lobby_id=lobby['lobbyId'], challenge_id=123)
        self.assertEqual(attached['status'],'awaiting_friend')
        return lobby

    def test_new_game_creates_real_life_match_once_and_retries_after_outage(self):
        payload={'requestId':'request_new_game_001','gameId':'life.loop','deploymentId':'life-host-1'}
        self.life.available=False
        with self.assertRaisesRegex(LobbyError,'life_match_creation_unavailable'):
            self.runtime.dispatch('a','new_game',payload)
        pending=self.store.list_for('acct_1')[0]
        self.assertEqual(pending['state'],'pending')
        self.life.available=True
        ready=self.runtime.dispatch('a','new_game',payload)
        self.assertEqual(ready['lobbyId'],pending['lobbyId'])
        self.assertEqual(ready['matchId'],'life_match_012345')
        self.assertEqual(self.runtime.dispatch('a','new_game',payload)['lobbyId'],ready['lobbyId'])
        self.assertEqual([x[0] for x in self.life.calls].count('create_match'),2) # offline + successful
        with self.assertRaisesRegex(LobbyError,'game_not_published'):
            self.runtime.dispatch('a','new_game',{**payload,'gameId':'other.game'})

    def test_two_accounts_recovery_and_idempotent_accept(self):
        lobby = self.linked()
        self.assertEqual(self.bridge.status('b', challenge_id=123)['canResume'], False)
        with self.assertRaisesRegex(LobbyError,'social_challenge_not_accepted'):
            self.bridge.accept('b', challenge_id=123)
        self.challenge=replace(self.challenge,status='accepted')
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.bridge.accept('b', challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'), [])
        # Life, not Social nor Atrium, independently provisions the recipient seat.
        self.life.seats.add('acct_2')
        result=self.bridge.accept('b', challenge_id=123)
        self.assertEqual(result['matchId'], 'life_match_012345')
        self.assertEqual(result['lobbyId'], lobby['lobbyId'])
        self.assertEqual(self.bridge.status('a', challenge_id=123)['recipientJoined'], True)
        self.bridge.accept('b',challenge_id=123)
        events=[x for x in self.store.pending_events() if x['type']=='lobby.joined']
        self.assertEqual(len(events), 1)
        # Both Tavi clients exit: independent server process can rehydrate.
        restarted_store = HostlessLobbyStore(self.path, clock=lambda: 1720000000)
        restarted_bridge = self.make_bridge(self.make_runtime(restarted_store))
        self.assertEqual(restarted_bridge.accept('b', challenge_id=123)['lobbyId'],lobby['lobbyId'])
        self.assertEqual(restarted_bridge.status('b', challenge_id=123)['status'],'accepted')
        self.assertEqual(self.store.inspect('acct_1',lobby['lobbyId'])['state'],'ready')

    def test_optional_life_authority_seat_admission_after_social_acceptance(self):
        lobby=self.linked()
        calls=[]
        def admit(game, grant, match_id, recipient, challenge_id):
            calls.append((recipient,match_id,challenge_id))
            self.life.seats.add(recipient)  # Life fixture applies authoritative admission
            return True
        producer=SocialChallengeBridge(self.runtime,
            get_challenge=lambda challenge_id:self.challenge,
            accepted_contact=lambda issuer,a,b:self.friend,
            catalog_game_id='life', admit_life_seat=admit)
        with self.assertRaisesRegex(LobbyError,'social_challenge_not_accepted'):
            producer.accept('b',challenge_id=123)
        self.assertEqual(calls,[])
        self.challenge=replace(self.challenge,status='accepted')
        self.assertEqual(producer.accept('b',challenge_id=123)['lobbyId'],lobby['lobbyId'])
        self.assertEqual(calls,[('acct_2','life_match_012345',123)])
        producer.accept('b',challenge_id=123)  # Life's admit must remain idempotent
        self.assertEqual(self.store.list_for('acct_2')[0]['lobbyId'],lobby['lobbyId'])

    def test_life_authority_seat_admission_fails_closed(self):
        self.linked()
        self.challenge=replace(self.challenge,status='accepted')
        bad=SocialChallengeBridge(self.runtime,
            get_challenge=lambda challenge_id:self.challenge,
            accepted_contact=lambda issuer,a,b:True,
            catalog_game_id='life', admit_life_seat=lambda *args:'yes')
        with self.assertRaisesRegex(LobbyError,'life_seat_admission_denied'):
            bad.accept('b',challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'),[])

    def test_attach_must_be_creator_ready_and_trusted_social(self):
        pending=self.runtime.dispatch('a','create',{'requestId':'request_12345678','gameId':'life.loop','deploymentId':'life-host-1'})
        with self.assertRaises(LobbyError):
            self.bridge.attach('a',lobby_id=pending['lobbyId'],challenge_id=123)
        lobby=self.runtime.dispatch('a','bind_match',{'lobbyId':pending['lobbyId'],'matchId':'life_match_012345'})
        with self.assertRaisesRegex(LobbyError,'not_lobby_member'):
            self.bridge.attach('c',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.bridge.attach('a',lobby_id=lobby['lobbyId'],challenge_id=123)
        with self.assertRaisesRegex(LobbyError,'not_challenge_recipient'):
            self.bridge.accept('a',challenge_id=123)
        with self.assertRaisesRegex(LobbyError,'unlinked_social_challenge'):
            self.bridge.accept('c',challenge_id=456)
        with self.assertRaisesRegex(LobbyError,'invalid_social_challenge_id'):
            self.bridge.attach('a',lobby_id=lobby['lobbyId'],challenge_id=True)

    def test_link_duplicate_is_stable_and_cannot_move(self):
        first=self.linked()
        self.assertEqual(self.bridge.attach('a',lobby_id=first['lobbyId'],challenge_id=123)['lobbyId'],first['lobbyId'])
        second=self.ready('request_challenge_5678')
        with self.assertRaisesRegex(LobbyError,'social_challenge_already_linked'):
            self.bridge.attach('a',lobby_id=second['lobbyId'],challenge_id=123)

    def test_wrong_game_subject_issuer_status_contact_and_provider_fail_closed(self):
        lobby=self.ready()
        base=self.challenge
        for changed in [replace(base,issuer='foreign-server'),replace(base,sender='acct_3'),
                        replace(base,recipient='acct_1'),replace(base,catalog_game_id='life.loop'),
                        replace(base,challenge_id=456)]:
            with self.subTest(changed=changed),self.assertRaises(LobbyError):
                self.challenge=changed
                self.bridge.attach('a',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.challenge=base
        self.friend=False
        with self.assertRaisesRegex(LobbyError,'not_accepted_tavi_friends'):
            self.bridge.attach('a',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.friend=True
        self.social_available=False
        with self.assertRaisesRegex(LobbyError,'social_challenge_unavailable'):
            self.bridge.attach('a',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.social_available=True
        self.bridge.attach('a',lobby_id=lobby['lobbyId'],challenge_id=123)
        self.challenge=replace(base,status='declined')
        with self.assertRaisesRegex(LobbyError,'social_challenge_not_accepted'):
            self.bridge.accept('b',challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'),[])

    def test_challenge_accepts_before_link_and_life_join_still_required(self):
        ready=self.ready()
        self.challenge=replace(self.challenge,status='accepted')
        self.assertEqual(self.bridge.attach('a',lobby_id=ready['lobbyId'],challenge_id=123)['status'],'accepted')
        self.assertFalse(self.bridge.status('b',challenge_id=123)['canResume'])
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.bridge.accept('b',challenge_id=123)
        self.life.seats.add('acct_2')
        self.assertTrue(self.bridge.accept('b',challenge_id=123)['matchId'])

    def test_deployment_revocation_seat_removal_and_status_privacy(self):
        lobby=self.linked()
        self.challenge=replace(self.challenge,status='accepted')
        self.life.seats.add('acct_2')
        self.game=TrustedGame('life.loop','life-host-1','malicious.publisher','active')
        with self.assertRaisesRegex(LobbyError,'game_not_published'):
            self.bridge.accept('b',challenge_id=123)
        self.game=TrustedGame('life.loop','life-host-1','thebigtreeinc','active')
        self.life.seats.remove('acct_2')
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.bridge.accept('b',challenge_id=123)
        with self.assertRaisesRegex(LobbyError,'unlinked_social_challenge'):
            self.bridge.status('c',challenge_id=123)
        self.assertEqual(self.store.list_for('acct_2'),[])
        self.assertEqual(self.store.inspect('acct_1',lobby['lobbyId'])['state'],'ready')

    def test_creator_leaving_does_not_delete_a_match(self):
        lobby=self.linked()
        self.challenge=replace(self.challenge,status='accepted')
        self.life.seats.add('acct_2')
        self.bridge.accept('b',challenge_id=123)
        self.store.leave('acct_1',lobby['lobbyId'])
        self.assertEqual(self.runtime.dispatch('b','resume',{'lobbyId':lobby['lobbyId']})['state'],'ready')


if __name__=='__main__':
    unittest.main()
