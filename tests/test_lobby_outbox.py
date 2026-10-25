"""Transactional, idempotent, server-side lobby event records (not Life turn events)."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from src.hostless_lobby import HostlessLobbyStore, LobbyError


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.db=Path(self.tmp.name)/'persistent.sqlite'
        self.a='social_player_AAA11111'
        self.b='social_player_BBB22222'
        self.store=HostlessLobbyStore(self.db,clock=lambda:1730000000)

    def tearDown(self):
        self.tmp.cleanup()

    def test_outbox_survives_retries_restarts_and_manual_ack(self):
        created=self.store.create(self.a,'request_12345678',game_id='life.loop',
                   deployment_id='life-deployment',publisher_id='life.publisher')
        lid=created['lobbyId']
        self.store.create(self.a,'request_12345678',game_id='life.loop',
                   deployment_id='life-deployment',publisher_id='life.publisher')
        self.assertEqual([r['type'] for r in self.store.pending_events()],['lobby.created'])
        self.store.bind_match(self.a,lid,'life_match_123456',confirm_match=lambda *args:True)
        self.store.bind_match(self.a,lid,'life_match_123456',confirm_match=lambda *args:True)
        code=self.store.invite(self.a,lid)
        self.store.join(self.b,code,confirm_seat=lambda *args:True)
        self.store.join(self.b,code,confirm_seat=lambda *args:True)
        new=HostlessLobbyStore(self.db,clock=lambda:1730000100)
        types=[x['type'] for x in new.pending_events()]
        self.assertEqual(sorted(types),sorted(['lobby.created','lobby.ready','lobby.joined']))
        self.assertTrue(new.acknowledge_event(new.pending_events()[0]['eventId']))
        self.assertEqual(len(new.pending_events()),2)
        # Ack of already-delivered event is idempotent; no raw invites stored.
        self.assertNotIn(code,str(new.pending_events()))
        with self.assertRaisesRegex(LobbyError,'invalid_outbox_id'):
            new.acknowledge_event('bad')
        self.store.leave(self.a,lid)
        self.assertIn('lobby.left',[x['type'] for x in new.pending_events()])
        new.finish(self.b,lid,confirm_finished=lambda *args:True)
        self.assertIn('lobby.finished',[x['type'] for x in new.pending_events()])
        with self.assertRaisesRegex(LobbyError,'invalid_outbox_limit'):
            new.pending_events(limit=0)

    def test_failures_do_not_emit_committed_events(self):
        created=self.store.create(self.a,'request_12345678',game_id='life.loop',
                   deployment_id='life-deployment',publisher_id='life.publisher')
        with self.assertRaisesRegex(LobbyError,'life_match_unverified'):
            self.store.bind_match(self.a,created['lobbyId'],'life_match_123456',confirm_match=lambda *args:False)
        self.assertEqual([x['type'] for x in self.store.pending_events()],['lobby.created'])


if __name__ == '__main__': unittest.main()
