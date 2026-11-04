"""Source-only trusted route contract exercised through disposable real HTTP.

These are *fixture sessions*, not Tavi/Social authentication, and no public
LoopRD route is activated. The verified-host integration remains unimplemented.
"""
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.checkers import initial_board
from src.checkers_match_authority import CheckersMatchAuthority
from src.checkers_trusted_host import ApprovedLobby, CheckersTrustedHost, VerifiedAccount
from src.checkers_trusted_routes import CheckersTrustedRoutes
from tests.support.checkers_trusted_http import trusted_disposable_server


class Client:
    def __init__(self, base, token):
        self.base, self.token = base, token

    def request(self, method, path, body=None, headers=None):
        content = json.dumps(body).encode('utf-8') if body is not None else None
        h = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'}
        if headers:
            h.update(headers)
        req = Request(self.base + path, method=method, data=content, headers=h)
        try:
            with urlopen(req, timeout=5) as result:
                return result.status, json.loads(result.read())
        except HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())

    def create(self, ref='approved-lobby'):
        return self.request('POST', '/games/checkers/matches', {'lobbyRef': ref})

    def get(self):
        return self.request('GET', '/games/checkers/matches/secure-match')

    def join(self):
        return self.request('POST', '/games/checkers/matches/secure-match/join')

    def legal(self):
        return self.request('GET', '/games/checkers/matches/secure-match/legal-actions')

    def move(self, revision, path, request_id):
        return self.request('POST', '/games/checkers/matches/secure-match/moves',
                            {'revision': revision, 'requestId': request_id, 'path': path})


class TrustedRouteNetworkQA(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atrium-checkers-route-')
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'authority.sqlite'
        self.authority = CheckersMatchAuthority(self.database)
        self.red_ctx, self.black_ctx, self.other_ctx = object(), object(), object()
        red = VerifiedAccount('tavi.social', 'user-red', 'atrium.checkers/v1')
        black = VerifiedAccount('tavi.social', 'user-black', 'atrium.checkers/v1')
        other = VerifiedAccount('tavi.social', 'user-other', 'atrium.checkers/v1')
        self.accounts = {self.red_ctx: red, self.black_ctx: black, self.other_ctx: other}
        self.lobbies = {'approved-lobby': ApprovedLobby('secure-match', 'checkers', 'accepted', red, black)}
        self.host = CheckersTrustedHost(self.authority,
                                        resolve_account=self.accounts.__getitem__,
                                        approve_lobby=lambda context, ref: self.lobbies[ref],
                                        issuer='tavi.social')
        self.router = CheckersTrustedRoutes(self.host)
        self.sessions = {'fixture-session-red': self.red_ctx,
                         'fixture-session-black': self.black_ctx,
                         'fixture-session-other': self.other_ctx}
        self.listener = trusted_disposable_server(self.router, self.sessions)
        self.base = self.listener.__enter__()
        self.red = Client(self.base, 'fixture-session-red')
        self.black = Client(self.base, 'fixture-session-black')
        self.other = Client(self.base, 'fixture-session-other')

    def tearDown(self):
        self.listener.__exit__(None, None, None)
        self.authority.close()

    def test_create_join_inspect_and_server_owned_actions_over_two_sessions(self):
        code, match = self.red.create()
        self.assertEqual(code, 201)
        self.assertEqual(match['state']['board'], initial_board())
        self.assertEqual(self.black.join()[1]['seat'], 'black')
        self.assertEqual(self.red.join()[1]['seat'], 'red')
        self.assertEqual(self.black.get(), (200, match))
        self.assertTrue(self.red.legal()[1]['actions'])
        self.assertEqual(self.black.legal()[1]['actions'], [])
        self.assertNotIn('user-red', json.dumps(match))
        self.assertNotIn('user-black', json.dumps(match))
        first = self.red.legal()[1]['actions'][0]
        code, after = self.red.move(0, first, 'one')
        self.assertEqual(code, 200)
        self.assertEqual(after['revision'], 1)
        self.assertEqual(self.black.get()[1], after)
        self.assertTrue(self.black.legal()[1]['actions'])

    def test_injected_client_claims_and_fake_session_cannot_grant_a_seat(self):
        self.assertEqual(Client(self.base, 'forged').create()[0], 401)
        self.assertEqual(self.other.create()[1]['error'], 'lobby_not_approved')
        self.assertEqual(self.red.request('POST', '/games/checkers/matches',
                           {'lobbyRef': 'approved-lobby', 'subject': 'user-black'})[1]['error'],
                         'invalid_envelope')
        self.assertEqual(self.red.create()[0], 201)
        self.assertEqual(self.other.get()[0], 403)
        self.assertEqual(self.other.join()[0], 403)
        self.assertEqual(self.other.legal()[0], 403)
        path = self.red.legal()[1]['actions'][0]
        self.assertEqual(self.other.move(0, path, 'forged-move')[0], 403)
        self.assertEqual(self.black.request('POST', '/games/checkers/matches/secure-match/moves',
                           {'revision': 0, 'requestId': 'a', 'path': path, 'seat': 'red'})[1]['error'],
                         'invalid_envelope')
        self.assertEqual(self.red.get()[1]['revision'], 0)

    def test_lobby_must_be_accepted_and_routes_reject_unexpected_paths(self):
        self.lobbies['declined'] = ApprovedLobby('bad-match', 'checkers', 'declined',
                                                self.accounts[self.red_ctx], self.accounts[self.black_ctx])
        self.assertEqual(self.red.create('declined'), (403, {'error': 'lobby_not_approved'}))
        self.assertEqual(self.red.create('../hijack')[0], 422)
        self.assertEqual(self.red.request('GET', '/games/checkers/matches/abc/../../admin')[0], 404)
        self.assertEqual(self.red.request('GET', '/games/checkers/matches/secure-match?seat=red')[0], 404)
        self.assertEqual(self.red.request('GET', '/games/checkers/matches/secure-match/moves')[0], 404)
        self.assertEqual(self.red.request('POST', '/games/checkers/matches/secure-match/join',
                                          {'subject': 'user-red'})[0], 404)
        self.assertEqual(self.red.create()[0], 201)
        self.assertEqual(self.black.create()[0], 409)

    def test_replay_revision_conflict_and_recovery_after_server_restart(self):
        self.assertEqual(self.red.create()[0], 201)
        path = self.red.legal()[1]['actions'][0]
        accepted = self.red.move(0, path, 'request-once')
        self.assertEqual(accepted[0], 200)
        self.assertEqual(self.red.move(0, path, 'request-once'), accepted)
        self.assertEqual(self.red.move(0, path, 'request-twice')[1]['error'], 'stale_revision')
        self.listener.__exit__(None, None, None)
        self.authority.close()
        self.authority = CheckersMatchAuthority(self.database)
        self.host = CheckersTrustedHost(self.authority,
                                        resolve_account=self.accounts.__getitem__,
                                        approve_lobby=lambda context, ref: self.lobbies[ref],
                                        issuer='tavi.social')
        self.router = CheckersTrustedRoutes(self.host)
        self.listener = trusted_disposable_server(self.router, self.sessions)
        self.base = self.listener.__enter__()
        self.red = Client(self.base, 'fixture-session-red')
        self.black = Client(self.base, 'fixture-session-black')
        self.assertEqual(self.red.join()[1]['match'], accepted[1])
        self.assertEqual(self.black.get(), accepted)
        self.assertEqual(self.red.move(0, path, 'request-once'), accepted)
        self.assertTrue(self.black.legal()[1]['actions'])

    def test_complete_match_over_host_bound_transport_with_deterministic_result(self):
        self.assertEqual(self.red.create()[0], 201)
        random_choices = random.Random(0)
        transcript = []
        for index in range(1, 201):
            match = self.red.get()[1]
            if match['status'] == 'finished':
                break
            active = self.red if match['state']['turn'] == 'r' else self.black
            inactive = self.black if active is self.red else self.red
            legal = active.legal()[1]
            self.assertEqual(legal['revision'], match['revision'])
            self.assertEqual(inactive.legal()[1]['actions'], [])
            choice = random_choices.choice(legal['actions'])
            transcript.append(choice)
            status, changed = active.move(match['revision'], choice, 'bound-%03d' % index)
            self.assertEqual(status, 200)
            self.assertEqual(changed['revision'], index)
            self.assertEqual(inactive.get()[1], changed)
        self.assertEqual(index, 54)
        self.assertEqual(match['state']['winner'], 'r')
        self.assertEqual(match['revision'], 53)
        digest = hashlib.sha256(json.dumps(transcript, sort_keys=True, separators=(',', ':'))
                                .encode('utf-8')).hexdigest()
        self.assertEqual(digest, '4bde7e4ec0a0f5737e6439ddeae2a2bd4a795a0aff75e1ab05048289bf4b3ab7')
        self.assertEqual(self.red.join()[1]['match'], self.black.join()[1]['match'])

    def test_route_contract_does_not_register_public_looprd_or_embed_credentials(self):
        root = Path(__file__).resolve().parents[1]
        src = (root/'src/checkers_trusted_routes.py').read_text(encoding='utf-8')
        spec = (root/'modules/games/checkers/looprd.yaml').read_text(encoding='utf-8')
        tavi = (root/'src/apphost.mjs').read_text(encoding='utf-8')
        self.assertNotIn('fixture-session-red', src)
        self.assertNotIn('Authorization', src)
        self.assertNotIn('ThreadingHTTPServer', src)
        self.assertNotIn('checkers_trusted_routes', spec)
        self.assertNotIn('checkers_trusted_routes', tavi)
        self.assertIn('persistentMatchesEnabled: false', spec)
        self.assertEqual(self.router.dispatch({'subject': 'user-red'}, 'GET',
                         '/games/checkers/matches/secure-match'),
                         (503, {'error': 'trusted_identity_unavailable'}))


if __name__ == '__main__':
    unittest.main()
