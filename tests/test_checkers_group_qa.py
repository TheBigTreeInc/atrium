"""Real loopback network requests against the exact source-package Checkers adapter.

The fixture is test-only: no claim of Social-issued tokens, a live LoopRD route,
Tavi integration or a production hostless service follows from this suite.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.checkers_adapter import CheckersEngine
from src.checkers_match_authority import CheckersMatchAuthority, MatchFailure
from src.checkers import initial_board, legal_moves
from tests.support.checkers_disposable import DisposableCheckersAuthority, disposable_server


class SimulatedClient:
    """Independent HTTP client, no imported game rules or DB connection."""
    def __init__(self, base, bearer):
        self.base, self.bearer = base, bearer

    def call(self, match='match1', *, method='GET', payload=None, action='moves'):
        endpoint = self.base + '/matches/' + match + ('/' + action if method == 'POST' else '')
        content = None if payload is None else json.dumps(payload).encode('utf-8')
        request = Request(endpoint, data=content, method=method,
                          headers={'Authorization': 'Bearer ' + self.bearer,
                                   'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())

    def join(self, match='match1'):
        return self.call(match, method='POST', action='join')

    def move(self, revision, path, request_id, match='match1'):
        return self.call(match, method='POST',
                         payload={'revision': revision, 'path': path, 'requestId': request_id})


def board_with(*pieces):
    board = [list('........') for _ in range(8)]
    for r, c, piece in pieces:
        board[r][c] = piece
    return [''.join(row) for row in board]


class CheckersNetworkGroupQA(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atrium-checkers-qa-')
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'fixture.sqlite'
        self.authority = DisposableCheckersAuthority(self.database)
        self.authority.seed('match1', 'actor-red', 'actor-black')
        # Tokens are deliberately fixed, test-only, not Social bearer credentials.
        self.identities = {'fixture-red-only': 'actor-red',
                           'fixture-black-only': 'actor-black',
                           'fixture-other-only': 'actor-outsider'}
        self._context = disposable_server(self.authority, self.identities)
        self.base = self._context.__enter__()
        self.red = SimulatedClient(self.base, 'fixture-red-only')
        self.black = SimulatedClient(self.base, 'fixture-black-only')
        self.outsider = SimulatedClient(self.base, 'fixture-other-only')

    def tearDown(self):
        self._context.__exit__(None, None, None)
        self.authority.close()

    def test_distinct_clients_sequential_moves_and_no_client_authority(self):
        initial = self.red.call()[1]
        self.assertEqual(initial['state']['board'], initial_board())
        self.assertEqual(initial['revision'], 0)
        self.assertNotIn('red_subject', json.dumps(initial))
        self.assertEqual(self.black.call()[1], initial)
        red_action = legal_moves(initial['state']['board'], 'r')[0]
        code, after_red = self.red.move(0, red_action, 'red-0001')
        self.assertEqual(code, 200)
        self.assertEqual(after_red['revision'], 1)
        self.assertEqual(after_red['state']['turn'], 'b')
        black_action = legal_moves(after_red['state']['board'], 'b')[0]
        code, after_black = self.black.move(1, black_action, 'black-0001')
        self.assertEqual(code, 200)
        self.assertEqual(after_black['revision'], 2)
        self.assertEqual(after_black['state']['turn'], 'r')
        self.assertEqual(self.red.call()[1], after_black)

    def test_unauthorized_wrong_identity_and_wrong_turn(self):
        self.assertEqual(SimulatedClient(self.base, 'unknown').call()[0], 401)
        self.assertEqual(self.outsider.call()[0], 403)
        move = legal_moves(initial_board(), 'r')[0]
        self.assertEqual(self.outsider.move(0, move, 'outsider')[0], 403)
        self.assertEqual(self.black.move(0, move, 'wrong-seat')[1]['error'], 'not_your_turn')
        self.assertEqual(self.red.call()[1]['revision'], 0)

    def test_stale_revision_idempotent_retry_and_changed_duplicate(self):
        move = legal_moves(initial_board(), 'r')[0]
        first_status, first = self.red.move(0, move, 'operation-alpha')
        self.assertEqual(first_status, 200)
        self.assertEqual(self.red.move(0, move, 'operation-alpha'), (200, first))
        self.assertEqual(self.red.move(0, move, 'operation-other')[1]['error'], 'stale_revision')
        altered = move[::-1]
        self.assertEqual(self.red.move(0, altered, 'operation-alpha')[1]['error'], 'duplicate_request_changed')
        self.assertEqual(self.black.call()[1]['revision'], 1)

    def test_illegal_move_and_mandatory_multi_capture(self):
        board = board_with((1, 0, 'r'), (2, 1, 'b'), (4, 3, 'b'), (7, 6, 'b'))
        self.authority.seed('capture', 'actor-red', 'actor-black',
                            state={'board': board, 'turn': 'r', 'winner': None})
        self.assertEqual(self.red.move(0, [[1, 0], [3, 2]], 'partial', 'capture')[1]['error'], 'illegal_move')
        result = self.red.move(0, [[1, 0], [3, 2], [5, 4]], 'complete', 'capture')
        self.assertEqual(result[0], 200)
        self.assertEqual(result[1]['state']['board'][5][4], 'r')
        self.assertEqual(result[1]['state']['turn'], 'b')

    def test_network_victory_and_terminal_state(self):
        board = board_with((5, 0, 'r'), (6, 1, 'b'))
        self.authority.seed('victory', 'actor-red', 'actor-black',
                            state={'board': board, 'turn': 'r', 'winner': None})
        code, state = self.red.move(0, [[5, 0], [7, 2]], 'win', 'victory')
        self.assertEqual(code, 200)
        self.assertEqual(state['state']['winner'], 'r')
        self.assertIsNone(state['state']['turn'])
        self.assertEqual(state['status'], 'finished')
        self.assertEqual(self.black.move(1, [[6, 1], [5, 0]], 'after-win', 'victory')[1]['error'], 'match_finished')

    def test_disconnect_server_restart_and_persisted_replay(self):
        move = legal_moves(initial_board(), 'r')[0]
        status, accepted = self.red.move(0, move, 'survive-restart')
        self.assertEqual(status, 200)
        # Drop both HTTP clients and the listening authority, not only in-memory state.
        self._context.__exit__(None, None, None)
        self.authority.close()
        self.authority = DisposableCheckersAuthority(self.database)
        self._context = disposable_server(self.authority, self.identities)
        self.base = self._context.__enter__()
        # Fresh client objects simulate reconnecting independent identities.
        self.red = SimulatedClient(self.base, 'fixture-red-only')
        self.black = SimulatedClient(self.base, 'fixture-black-only')
        self.assertEqual(self.red.call()[1], accepted)
        self.assertEqual(self.black.call()[1], accepted)
        self.assertEqual(self.red.move(0, move, 'survive-restart'), (200, accepted))
        next_move = legal_moves(accepted['state']['board'], 'b')[0]
        self.assertEqual(self.black.move(1, next_move, 'after-restart')[1]['revision'], 2)

    def test_join_requires_correct_authenticated_identity_and_returns_seat(self):
        status, joined = self.red.join()
        self.assertEqual(status, 200)
        self.assertEqual(joined['seat'], 'red')
        self.assertEqual(joined['match'], self.red.call()[1])
        self.assertEqual(self.black.join()[1]['seat'], 'black')
        self.assertEqual(self.red.join(), (status, joined))  # hostless resume is idempotent
        self.assertEqual(self.outsider.join(), (403, {'error': 'not_a_participant'}))
        self.assertEqual(SimulatedClient(self.base, 'untrusted').join()[0], 401)
        self.assertEqual(self.outsider.join('nonexistent')[0], 404)
        self.assertEqual(self.red.call()[1]['revision'], 0)

    def test_network_crowning_and_king_backward_capture(self):
        # American men crown and stop on reaching the last row during a jump.
        board = board_with((5, 0, 'r'), (6, 1, 'b'), (6, 3, 'b'), (1, 2, 'b'))
        self.authority.seed('crown', 'actor-red', 'actor-black',
                            state={'board': board, 'turn': 'r', 'winner': None})
        code, promoted = self.red.move(0, [[5, 0], [7, 2]], 'crown-1', 'crown')
        self.assertEqual(code, 200)
        self.assertEqual(promoted['state']['board'][7][2], 'R')
        self.assertEqual(promoted['state']['turn'], 'b')
        # Kings can capture backwards on a later turn; no forced backward man capture.
        king = board_with((5, 4, 'R'), (4, 3, 'b'), (0, 1, 'b'))
        self.authority.seed('king', 'actor-red', 'actor-black',
                            state={'board': king, 'turn': 'r', 'winner': None})
        code, moved = self.red.move(0, [[5, 4], [3, 2]], 'king-back', 'king')
        self.assertEqual(code, 200)
        self.assertEqual(moved['state']['board'][3][2], 'R')
        self.assertEqual(moved['state']['board'][4][3], '.')

    def test_network_validates_malformed_envelopes_and_does_not_mutate_state(self):
        invalid = (
            {'revision': True, 'requestId': 'a', 'path': [[2, 1], [3, 0]]},
            {'revision': 0, 'requestId': 'a', 'path': [[2, 1], [9, 0]]},
            {'revision': 0, 'requestId': 'a', 'path': [[2, 1]]},
            {'revision': 0, 'requestId': 'a', 'path': [[2, 1], [3, 0]], 'seat': 'red'},
            {'revision': -1, 'requestId': 'a', 'path': [[2, 1], [3, 0]]},
        )
        for case in invalid:
            with self.subTest(case=case):
                self.assertEqual(self.red.call(method='POST', payload=case)[0], 422)
                self.assertEqual(self.red.call()[1]['revision'], 0)

    def test_production_authority_creation_requires_distinct_host_confirmed_seats(self):
        # Core API carries no browser bearer, token map or HTTP listener.
        with tempfile.TemporaryDirectory() as folder:
            store = CheckersMatchAuthority(Path(folder) / 'production-core-test.sqlite')
            try:
                with self.assertRaises(ValueError):
                    store.create_match('bad', 'red', 'red')
                created = store.create_match('trusted-game', 'signed-red', 'signed-black')
                self.assertEqual(created['state'], CheckersEngine().initial_state())
                self.assertEqual(store.join('trusted-game', 'signed-black')['seat'], 'black')
                with self.assertRaises(MatchFailure) as cm:
                    store.inspect('trusted-game', 'not-a-seat')
                self.assertEqual(cm.exception.http_status, 403)
            finally:
                store.close()

    def test_cross_connection_atomic_revision_and_retry(self):
        # Two independent source-authority connections share the same SQLite file.
        # Exactly one different request at revision 0 may succeed.
        other = CheckersMatchAuthority(self.database)
        try:
            path = legal_moves(initial_board(), 'r')[0]
            gate = __import__('threading').Barrier(2)
            def race(authority, req_id):
                gate.wait(timeout=4)
                try:
                    return 200, authority.move('match1', 'actor-red',
                                               {'revision': 0, 'requestId': req_id, 'path': path})
                except MatchFailure as exc:
                    return exc.http_status, exc.code
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(race, self.authority, 'race-a')
                b = pool.submit(race, other, 'race-b')
                results = [a.result(timeout=8), b.result(timeout=8)]
            self.assertEqual(sorted(code for code, _ in results), [200, 409])
            self.assertEqual(self.black.call()[1]['revision'], 1)
            self.assertEqual([payload for code, payload in results if code == 409],
                             ['stale_revision'])
        finally:
            other.close()

    def test_source_boundaries_and_deterministic_fixture_digest(self):
        root = Path(__file__).resolve().parents[1]
        module_text = (root / 'src/checkers_match_authority.py').read_text(encoding='utf-8')
        fixture_text = (root / 'tests/support/checkers_disposable.py').read_text(encoding='utf-8')
        looprd_text = (root / 'looprd.yaml').read_text(encoding='utf-8')
        tavi_text = (root / 'src/apphost.mjs').read_text(encoding='utf-8')
        self.assertIn('from src.checkers_adapter import CheckersEngine', module_text)
        self.assertIn('from src.checkers_match_authority import CheckersMatchAuthority', fixture_text)
        self.assertNotIn('ThreadingHTTPServer', module_text)
        self.assertNotIn('Bearer', module_text)
        self.assertNotIn('from src.checkers import', looprd_text)
        self.assertNotIn('from src.checkers import', tavi_text)
        self.assertNotIn('tests/support/checkers_disposable', looprd_text)
        self.assertNotIn('tests/support/checkers_disposable', tavi_text)
        self.assertNotIn('fixture-red-only', looprd_text)
        self.assertNotIn('fixture-red-only', tavi_text)
        state = CheckersEngine().initial_state()
        encoded = json.dumps(state, sort_keys=True, separators=(',', ':')).encode('utf-8')
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         '7d67ce7f27975374930d7d42f5c39c251af86b22e05c582c7308ce983726b61f')
        self.assertEqual(state['board'], initial_board())


if __name__ == '__main__':
    unittest.main()
