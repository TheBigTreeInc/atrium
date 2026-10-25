"""Source contract regression for a player-independent Atrium lobby store."""
import tempfile
from pathlib import Path
import unittest
from src.hostless_lobby import HostlessLobbyStore, LobbyError


class DurableLobbyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'lobby.sqlite'
        self.now=10_000
        self.store=HostlessLobbyStore(self.path,clock=lambda:self.now)
        self.a='user_alpha_1234'
        self.b='user_beta_5678'
        self.c='user_gamma_123'
        self.refs=dict(game_id='life.loop',deployment_id='life-prod-1',publisher_id='thebigtreeinc')

    def create_ready(self):
        pending=self.store.create(self.a,'request_12345678',**self.refs)
        self.assertEqual(pending['state'],'pending')
        with self.assertRaisesRegex(LobbyError,'game_match_not_confirmed'):
            self.store.inspect(self.a,pending['lobbyId'],require_ready=True)
        seen=[]
        ready=self.store.bind_match(self.a,pending['lobbyId'],'life_match_123456',confirm_match=lambda *args:(seen.append(args) or True))
        self.assertEqual(seen[0],('life.loop','life-prod-1','life_match_123456',self.a,'request_12345678'))
        return ready

    def test_two_clients_reopen_store_without_creator_online(self):
        ready=self.create_ready()
        code=self.store.invite(self.a,ready['lobbyId'])
        self.assertEqual(self.store.join(self.b,code,confirm_seat=lambda *args:True)['matchId'],'life_match_123456')
        # Full client and Atrium process restart: no browser/client in this store.
        again=HostlessLobbyStore(self.path,clock=lambda:self.now)
        self.assertEqual(again.list_for(self.b)[0]['matchId'],'life_match_123456')
        self.assertEqual(again.inspect(self.b,ready['lobbyId'],require_ready=True)['state'],'ready')
        self.assertEqual(again.inspect(self.a,ready['lobbyId'])['state'],'ready')

    def test_create_retries_are_idempotent_and_conflicts_rejected(self):
        a=self.store.create(self.a,'request_12345678',**self.refs)
        self.assertEqual(a['lobbyId'],self.store.create(self.a,'request_12345678',**self.refs)['lobbyId'])
        with self.assertRaisesRegex(LobbyError,'idempotency_conflict'):
            self.store.create(self.a,'request_12345678',**{**self.refs,'game_id':'market.grove'})

    def test_invite_claim_is_single_principal_and_survives_failed_seat_verification(self):
        ready=self.create_ready()
        code=self.store.invite(self.a,ready['lobbyId'])
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.store.join(self.b,code,confirm_seat=lambda *args:False)
        with self.assertRaisesRegex(LobbyError,'invitation_already_claimed'):
            self.store.join(self.c,code,confirm_seat=lambda *args:True)
        new=HostlessLobbyStore(self.path,clock=lambda:self.now)
        self.assertEqual(new.join(self.b,code,confirm_seat=lambda *args:True)['state'],'ready')
        self.assertEqual(new.join(self.b,code,confirm_seat=lambda *args:True)['lobbyId'],ready['lobbyId'])
        with self.assertRaisesRegex(LobbyError,'not_lobby_member'):
            new.inspect(self.c,ready['lobbyId'])

    def test_expiry_and_leaving_are_distinct_from_match_deletion(self):
        ready=self.create_ready()
        code=self.store.invite(self.a,ready['lobbyId'],seconds=60)
        self.now+=61
        with self.assertRaisesRegex(LobbyError,'invitation_expired_or_missing'):
            self.store.join(self.b,code,confirm_seat=lambda *args:True)
        fresh=self.store.invite(self.a,ready['lobbyId'])
        self.store.join(self.b,fresh,confirm_seat=lambda *args:True)
        self.store.leave(self.a,ready['lobbyId'])
        self.assertEqual(self.store.inspect(self.b,ready['lobbyId'])['matchId'],'life_match_123456')
        with self.assertRaisesRegex(LobbyError,'not_lobby_member'):
            self.store.inspect(self.a,ready['lobbyId'])

    def test_life_must_confirm_bind_and_finish_and_id_is_not_authorization(self):
        pending=self.store.create(self.a,'request_12345678',**self.refs)
        with self.assertRaisesRegex(LobbyError,'life_match_unverified'):
            self.store.bind_match(self.a,pending['lobbyId'],'life_match_123456',confirm_match=lambda *args:False)
        with self.assertRaisesRegex(LobbyError,'not_lobby_member'):
            self.store.bind_match(self.c,pending['lobbyId'],'life_match_123456',confirm_match=lambda *args:True)
        ready=self.store.bind_match(self.a,pending['lobbyId'],'life_match_123456',confirm_match=lambda *args:True)
        with self.assertRaisesRegex(LobbyError,'life_game_not_finished'):
            self.store.finish(self.a,ready['lobbyId'],confirm_finished=lambda *args:False)
        self.assertEqual(self.store.finish(self.a,ready['lobbyId'],confirm_finished=lambda *args:True)['state'],'finished')

    def test_pending_join_cannot_view_lobby(self):
        ready=self.create_ready()
        code=self.store.invite(self.a,ready['lobbyId'])
        with self.assertRaisesRegex(LobbyError,'life_seat_unverified'):
            self.store.join(self.b,code,confirm_seat=lambda *args:False)
        with self.assertRaisesRegex(LobbyError,'not_lobby_member'):
            self.store.inspect(self.b,ready['lobbyId'])

if __name__=='__main__': unittest.main()
