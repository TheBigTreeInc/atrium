"""Contract characterization for the UNMOUNTED Atrium lobby runtime adapter."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.hostless_lobby import HostlessLobbyStore, LobbyError
from src.lobby_runtime import HostlessLobbyRuntime, VerifiedActor, TrustedGame


class MockLife:
    def __init__(self):
        self.seats = {'social_player_AAA11111'}
        self.match_ok = False
        self.fail = False
        self.calls = []

    def verify_match(self, game, grant, match, subject, key):
        self.calls.append(('match', subject, key))
        if self.fail: raise ConnectionError('Life unavailable')
        return self.match_ok and subject == grant['subject'] and match == 'life_match_123456'

    def verify_seat(self, game, grant, match, subject, lobby):
        self.calls.append(('seat', subject, lobby))
        if self.fail: raise ConnectionError('Life unavailable')
        if grant['subject'] != subject or match != 'life_match_123456': return False
        self.seats.add(subject)
        return True

    def verify_finished(self, game, grant, match, subject):
        return False

    def can_resume(self, game, grant, match, subject):
        if self.fail: raise ConnectionError('Life unavailable')
        return (subject in self.seats and grant['subject'] == subject
                and match == 'life_match_123456')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / 'lobby.sqlite'
        self.store = HostlessLobbyStore(self.path, clock=lambda: 1730000000)
        self.actor_a = VerifiedActor('social_player_AAA11111', 'social', 'atrium.lobby')
        self.actor_b = VerifiedActor('social_player_BBB22222', 'social', 'atrium.lobby')
        self.life = MockLife()
        self.game = TrustedGame('life.loop', 'life-deployment', 'life.publisher', 'active')
        self.active = True
        self.auth_calls = 0
        def auth(context):
            self.auth_calls += 1
            return {'a': self.actor_a, 'b': self.actor_b}.get(context)
        def game(gid, did):
            return self.game if self.active else None
        def grant(actor, trusted):
            return {'audience': 'life.loop', 'subject': actor.subject, 'ephemeral': 'private-grant'}
        self.runtime = HostlessLobbyRuntime(self.store, authenticate=auth,
                 resolve_game=game, issue_life_grant=grant, life=self.life, social_issuer='social')

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, actor, operation, **payload):
        return self.runtime.dispatch(actor, operation, payload)

    def ready(self):
        v = self.invoke('a','create',requestId='request_12345678',gameId='life.loop',deploymentId='life-deployment')
        self.life.match_ok=True
        return self.invoke('a', 'bind_match', lobbyId=v['lobbyId'], matchId='life_match_123456')

    def test_hostless_flow_restart_and_no_client_host(self):
        v = self.invoke('a','create',requestId='request_12345678',gameId='life.loop',deploymentId='life-deployment')
        self.assertEqual(v['state'],'pending')
        self.assertIsNone(v['matchId'])
        with self.assertRaisesRegex(LobbyError,'life_match_unverified'):
            self.invoke('a','bind_match',lobbyId=v['lobbyId'],matchId='life_match_123456')
        self.life.match_ok=True
        ready=self.invoke('a','bind_match',lobbyId=v['lobbyId'],matchId='life_match_123456')
        invite=self.invoke('a','invite',lobbyId=v['lobbyId'],ttlSeconds=86400)
        self.assertNotIn('private-grant',json.dumps([v,ready,invite]))
        joined=self.invoke('b','join',invitation=invite['invitation'])
        self.assertEqual(joined['matchId'], 'life_match_123456')
        # Host-owned database survives process and both client exits.
        new_store=HostlessLobbyStore(self.path,clock=lambda: 1730000000)
        new_runtime=HostlessLobbyRuntime(new_store,authenticate=self.runtime.authenticate,
            resolve_game=self.runtime.resolve,issue_life_grant=self.runtime.grant,life=self.life, social_issuer='social')
        self.assertEqual(new_runtime.dispatch('b','resume',{'lobbyId':ready['lobbyId']})['state'],'ready')
        left=self.invoke('a','leave',lobbyId=ready['lobbyId'])
        self.assertTrue(left['matchUnchanged'])
        self.assertEqual(self.invoke('b','resume',lobbyId=ready['lobbyId'])['matchId'],'life_match_123456')

    def test_fail_closed_principal_payload_grant_and_seat(self):
        for operation,payload in [('create',{'requestId':'request_12345678','gameId':'life.loop','deploymentId':'life-deployment','principal':self.actor_a.subject}),
                                   ('list', {'token':'X'}),('join',{'invitation':'x'*43,'url':'https://example.com'})]:
            with self.subTest(operation=operation),self.assertRaisesRegex(LobbyError,'invalid_lobby_request'):
                self.runtime.dispatch('a',operation,payload)
        with self.assertRaisesRegex(LobbyError,'social_authentication_required'):
            self.runtime.dispatch('unknown','list',{})
        with self.assertRaisesRegex(LobbyError,'not_lobby_member'):
            self.invoke('b','inspect',lobbyId=self.ready()['lobbyId'])
        self.life.seats.clear()
        lobby_id=self.store.list_for(self.actor_a.subject)[0]['lobbyId']
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.invoke('a','resume',lobbyId=lobby_id)
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.invoke('a','invite',lobbyId=lobby_id,ttlSeconds=3600)

    def test_publisher_swap_disable_and_life_outage(self):
        ready=self.ready()
        self.active=False
        self.assertEqual(self.invoke('a','list'),{'lobbies':[]})
        with self.assertRaisesRegex(LobbyError,'game_not_published'):
            self.invoke('a','resume',lobbyId=ready['lobbyId'])
        self.active=True
        self.game = TrustedGame('life.loop','life-deployment','foreign.publisher','active')
        with self.assertRaisesRegex(LobbyError,'game_not_published'):
            self.invoke('a','resume',lobbyId=ready['lobbyId'])
        self.game = TrustedGame('life.loop','life-deployment','life.publisher','active')
        self.life.fail=True
        with self.assertRaisesRegex(LobbyError,'life_authority_unavailable'):
            self.invoke('a','resume',lobbyId=ready['lobbyId'])
        self.life.fail=False
        self.assertEqual(self.invoke('a','resume',lobbyId=ready['lobbyId'])['state'],'ready')

    def test_expired_invite_untrusted_provider_and_no_reissue(self):
        ready=self.ready()
        code=self.invoke('a','invite',lobbyId=ready['lobbyId'],ttlSeconds=60)['invitation']
        self.assertEqual(self.store.invitation_target(code)['gameId'],'life.loop')
        self.store.clock=lambda:1730000061
        with self.assertRaisesRegex(LobbyError,'invitation_expired_or_missing'):
            self.invoke('b','join',invitation=code)
        with self.assertRaisesRegex(LobbyError,'life_authority_required'):
            HostlessLobbyRuntime(self.store, authenticate=lambda ctx:self.actor_a,
                resolve_game=lambda *args:self.game,issue_life_grant=lambda *args:True,life=object(),social_issuer='social')

    def test_callback_authority_result_must_be_true(self):
        ready=self.ready()
        self.life.can_resume=lambda *args:'yes'  # truthy but not authorized
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.invoke('a','resume',lobbyId=ready['lobbyId'])
        with self.assertRaisesRegex(LobbyError,'invalid_lobby_request'):
            self.runtime.dispatch('a','finish',{'lobbyId':ready['lobbyId'],'matchId':'forged'})


if __name__ == '__main__': unittest.main()
