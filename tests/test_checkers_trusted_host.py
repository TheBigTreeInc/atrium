"""Tests of the host-resolved Checkers port, not real Social integration."""
import json
from pathlib import Path
import tempfile
import unittest

from src.checkers_match_authority import CheckersMatchAuthority, MatchFailure
from src.checkers_trusted_host import ApprovedLobby, CheckersTrustedHost, VerifiedAccount


class TrustedHostBoundaryQA(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atrium-trusted-checkers-')
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'match.sqlite'
        self.store = CheckersMatchAuthority(self.db)
        self.addCleanup(self.store.close)
        self.red_ctx, self.black_ctx, self.out_ctx = object(), object(), object()
        self.accounts = {
            self.red_ctx: VerifiedAccount('tavi.social', 'uuid-red', 'atrium.checkers/v1'),
            self.black_ctx: VerifiedAccount('tavi.social', 'uuid-black', 'atrium.checkers/v1'),
            self.out_ctx: VerifiedAccount('tavi.social', 'uuid-outsider', 'atrium.checkers/v1'),
        }
        self.approval = ApprovedLobby('server-match', 'checkers', 'accepted',
                                     self.accounts[self.red_ctx], self.accounts[self.black_ctx])
        self.lobbies = {'lobby-one': self.approval}
        self.host = CheckersTrustedHost(self.store, resolve_account=self.accounts.__getitem__,
                                       approve_lobby=lambda ctx, ref: self.lobbies[ref],
                                       issuer='tavi.social')

    def assert_error(self, code, callback):
        with self.assertRaises(MatchFailure) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_host_attested_lobby_creates_namespaced_private_seats(self):
        initial = self.host.create_from_accepted_lobby(self.red_ctx, 'lobby-one')
        self.assertEqual(initial['revision'], 0)
        self.assertEqual(initial['matchId'], 'server-match')
        self.assertEqual(self.host.join(self.black_ctx, 'server-match')['seat'], 'black')
        self.assertEqual(self.host.join(self.red_ctx, 'server-match')['seat'], 'red')
        self.assertEqual(self.host.inspect(self.black_ctx, 'server-match'), initial)
        self.assertNotIn('uuid-red', json.dumps(initial))
        self.assertNotIn('uuid-black', json.dumps(initial))
        self.assert_error('not_a_participant', lambda: self.host.inspect(self.out_ctx, 'server-match'))
        self.assert_error('match_already_exists',
                          lambda: self.host.create_from_accepted_lobby(self.red_ctx, 'lobby-one'))

    def test_imposter_context_cannot_set_subject_or_create_a_match(self):
        forged = {'subject': 'uuid-red', 'issuer': 'tavi.social', 'seat': 'red'}
        self.assert_error('trusted_identity_unavailable',
                          lambda: self.host.create_from_accepted_lobby(forged, 'lobby-one'))
        self.assert_error('trusted_identity_unavailable',
                          lambda: self.host.legal_actions(forged, 'server-match'))
        self.assert_error('lobby_not_approved',
                          lambda: self.host.create_from_accepted_lobby(self.out_ctx, 'lobby-one'))
        self.assert_error('trusted_lobby_unavailable',
                          lambda: self.host.create_from_accepted_lobby(self.red_ctx, 'not-accepted'))
        self.assert_error('invalid_lobby_reference',
                          lambda: self.host.create_from_accepted_lobby(self.red_ctx, '../wrong'))

    def test_declined_cross_game_wrong_audience_and_issuer_rejected(self):
        for variant in (
            ApprovedLobby('m1', 'checkers', 'pending', self.approval.red, self.approval.black),
            ApprovedLobby('m1', 'life', 'accepted', self.approval.red, self.approval.black),
            ApprovedLobby('m1', 'checkers', 'accepted', self.approval.red,
                          VerifiedAccount('other.social', 'uuid-black', 'atrium.checkers/v1')),
            ApprovedLobby('m1', 'checkers', 'accepted', self.approval.red,
                          VerifiedAccount('tavi.social', 'uuid-black', 'not-checkers')),
            ApprovedLobby('m1', 'checkers', 'accepted', self.approval.red, self.approval.red),
        ):
            self.lobbies['lobby-one'] = variant
            self.assert_error('lobby_not_approved',
                              lambda: self.host.create_from_accepted_lobby(self.red_ctx, 'lobby-one'))
        self.assert_error('not_found', lambda: self.host.inspect(self.red_ctx, 'm1'))
        self.accounts[self.red_ctx] = {'subject': 'uuid-red'}  # raw claims not accepted
        self.assert_error('trusted_identity_invalid',
                          lambda: self.host.join(self.red_ctx, 'server-match'))

    def test_server_owned_move_and_reconnect_without_identity_in_payload(self):
        self.host.create_from_accepted_lobby(self.red_ctx, 'lobby-one')
        initial = self.host.legal_actions(self.red_ctx, 'server-match')
        self.assertTrue(initial['actions'])
        self.assertEqual(self.host.legal_actions(self.black_ctx, 'server-match')['actions'], [])
        payload = {'revision': 0, 'requestId': 'host-001', 'path': initial['actions'][0]}
        moved = self.host.move(self.red_ctx, 'server-match', payload)
        self.assertEqual(moved['revision'], 1)
        self.assertEqual(self.host.move(self.red_ctx, 'server-match', payload), moved)
        self.assert_error('not_a_participant',
                          lambda: self.host.move(self.out_ctx, 'server-match', payload))
        self.assert_error('invalid_envelope',
                          lambda: self.host.move(self.black_ctx, 'server-match', dict(payload, subject='uuid-black')))
        self.assertEqual(self.host.join(self.black_ctx, 'server-match')['match'], moved)
        self.assertEqual(self.host.legal_actions(self.red_ctx, 'server-match')['actions'], [])
        self.assertTrue(self.host.legal_actions(self.black_ctx, 'server-match')['actions'])


if __name__ == '__main__':
    unittest.main()
