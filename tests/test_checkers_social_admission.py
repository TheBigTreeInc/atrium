"""Disposable verified-Social projection; does not assert real Social credentials."""
from dataclasses import replace
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import tempfile
from pathlib import Path
import unittest

from src.checkers_match_authority import CheckersMatchAuthority, MatchFailure
from src.checkers_social_admission import CheckersSocialAdmission
from src.checkers_trusted_host import VerifiedAccount
from src.checkers_trusted_routes import CheckersTrustedRoutes
from src.social_challenge_bridge import VerifiedSocialChallenge
from tests.support.checkers_trusted_http import trusted_disposable_server


class SocialAdmissionQA(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='checkers-social-admission-')
        self.addCleanup(self.scratch.cleanup)
        self.authority = CheckersMatchAuthority(Path(self.scratch.name) / 'match.sqlite')
        # Resolve the *current* connection at teardown: restart tests replace self.authority.
        # A captured bound .close() leaves match.sqlite locked on Windows.
        self.addCleanup(lambda: self.authority.close())
        self.red, self.black, self.outsider = object(), object(), object()
        self.accounts = {
            self.red: VerifiedAccount('tavi.social', 'acct_11', 'atrium.checkers/v1'),
            self.black: VerifiedAccount('tavi.social', 'acct_12', 'atrium.checkers/v1'),
            self.outsider: VerifiedAccount('tavi.social', 'acct_13', 'atrium.checkers/v1'),
        }
        self.challenges = {713: VerifiedSocialChallenge(
            challenge_id=713, issuer='tavi.social', sender='acct_11',
            recipient='acct_12', catalog_game_id='checkers', status='accepted')}
        self.friends = True
        self.admission = CheckersSocialAdmission(
            issuer='tavi.social', resolve_session=self.accounts.__getitem__,
            lookup_original_challenge=self.challenges.__getitem__,
            accepted_contact=lambda issuer, sender, recipient: self.friends,
        )
        self.host = self.admission.bind(self.authority)
        self.routes = CheckersTrustedRoutes(self.host)

    def error(self, expected, fn):
        with self.assertRaises(MatchFailure) as found:
            fn()
        self.assertEqual(found.exception.code, expected)

    def test_accepted_original_challenge_creates_private_shared_match(self):
        first = self.host.create_from_accepted_lobby(self.red, 'social_713')
        self.assertEqual(first['revision'], 0)
        match = first['matchId']
        self.assertRegex(match, r'^sc_[0-9a-f]{40}$')
        self.assertNotIn('713', match)
        self.assertEqual(self.host.join(self.black, match)['seat'], 'black')
        self.assertEqual(self.host.join(self.red, match)['seat'], 'red')
        self.assertEqual(self.host.inspect(self.black, match), first)
        self.error('not_a_participant', lambda: self.host.inspect(self.outsider, match))
        self.error('match_already_exists', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))

    def test_wrong_actor_and_raw_browser_claims_rejected(self):
        self.error('lobby_not_approved', lambda: self.host.create_from_accepted_lobby(self.outsider, 'social_713'))
        self.error('trusted_identity_unavailable', lambda: self.host.create_from_accepted_lobby(
            {'subject': 'acct_11', 'seat': 'red'}, 'social_713'))
        self.accounts[self.red] = {'issuer':'tavi.social','subject':'acct_11','audience':'atrium.checkers/v1'}
        self.error('trusted_identity_invalid', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))

    def test_only_accepted_original_checkers_challenge_is_approved(self):
        original = self.challenges[713]
        variants = (
            {'status':'pending'}, {'status':'declined'}, {'status':'cancelled'},
            {'catalog_game_id':'life'}, {'issuer':'not-tavi.social'},
            {'sender':'acct_12', 'recipient':'acct_12'},
            {'recipient':'malformed'}, {'challenge_id':714},
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.challenges[713] = replace(original, **variant)
                self.error('lobby_not_approved', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))
        self.challenges[713] = original
        self.challenges[713] = {'status':'accepted', 'sender':'acct_11', 'recipient':'acct_12'}
        self.error('lobby_not_approved', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))

    def test_invalid_lobby_reference_never_triggers_lookup(self):
        for value in ('713', 'social_0', 'social_0713', 'social_9223372036854775808',
                      'social_713/other', '../social_713', 'social_1?token=private', None, 713):
            with self.subTest(reference=value):
                self.error('invalid_lobby_reference', lambda: self.host.create_from_accepted_lobby(self.red,value))

    def test_contact_and_service_failures_fail_closed(self):
        self.friends = False
        self.error('lobby_not_approved', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))
        self.friends = 1  # literal True, not truthy values
        self.error('lobby_not_approved', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))
        del self.challenges[713]
        self.error('trusted_lobby_unavailable', lambda: self.host.create_from_accepted_lobby(self.red, 'social_713'))

    def test_two_session_route_join_legal_move_and_restart(self):
        status, match = self.routes.dispatch(self.red, 'POST', '/games/checkers/matches', {'lobbyRef':'social_713'})
        self.assertEqual(status, 201)
        match_id = match['matchId']
        prefix = '/games/checkers/matches/' + match_id
        self.assertEqual(self.routes.dispatch(self.black, 'POST',prefix+'/join')[1]['seat'],'black')
        red_moves = self.routes.dispatch(self.red, 'GET',prefix+'/legal-actions')[1]
        self.assertTrue(red_moves['actions'])
        self.assertEqual(self.routes.dispatch(self.black, 'GET',prefix+'/legal-actions')[1]['actions'],[])
        payload = {'revision':0, 'requestId':'social-move-1','path': red_moves['actions'][0]}
        code, moved = self.routes.dispatch(self.red, 'POST',prefix+'/moves',payload)
        self.assertEqual(code,200)
        self.assertEqual(moved['revision'],1)
        self.assertEqual(self.routes.dispatch(self.red, 'POST',prefix+'/moves',payload),(200,moved))
        self.assertEqual(self.routes.dispatch(self.outsider, 'GET',prefix)[0],403)
        self.assertEqual(self.routes.dispatch(self.black, 'GET',prefix)[1],moved)
        self.assertTrue(self.routes.dispatch(self.black, 'GET',prefix+'/legal-actions')[1]['actions'])
        self.authority.close()
        self.authority = CheckersMatchAuthority(Path(self.scratch.name) / 'match.sqlite')
        self.host = self.admission.bind(self.authority)
        self.routes = CheckersTrustedRoutes(self.host)
        self.assertEqual(self.routes.dispatch(self.black, 'GET',prefix)[1],moved)
        self.assertEqual(self.routes.dispatch(self.red, 'POST',prefix+'/moves',payload),(200,moved))

    def test_two_independent_http_clients_use_server_verified_social_projection(self):
        # Fixture bearer aliases remain test-only: not a Social token verifier.
        sessions = {'fixture-red':self.red, 'fixture-black':self.black,
                    'fixture-outsider':self.outsider}
        with trusted_disposable_server(self.routes, sessions) as base:
            def send(token, method, path, body=None):
                payload = json.dumps(body).encode('utf-8') if body is not None else None
                request = Request(base + path, data=payload, method=method,
                                  headers={'Authorization':'Bearer '+token,
                                           'Content-Type':'application/json'})
                try:
                    with urlopen(request, timeout=5) as response:
                        return response.status, json.loads(response.read())
                except HTTPError as error:
                    with error:
                        return error.code, json.loads(error.read())
            self.assertEqual(send('fixture-red','POST','/games/checkers/matches',
                                  {'lobbyRef':'social_713','subject':'acct_11'})[0],422)
            code, match = send('fixture-red','POST','/games/checkers/matches',{'lobbyRef':'social_713'})
            self.assertEqual(code,201)
            route = '/games/checkers/matches/' + match['matchId']
            self.assertEqual(send('fixture-black','POST',route+'/join')[1]['seat'],'black')
            self.assertEqual(send('fixture-outsider','GET',route)[0],403)
            self.assertEqual(send('missing','GET',route)[0],401)
            actions = send('fixture-red','GET',route+'/legal-actions')[1]['actions']
            self.assertTrue(actions)
            code, state = send('fixture-red','POST',route+'/moves',
                               {'revision':0,'requestId':'social-http-1','path':actions[0]})
            self.assertEqual(code,200)
            self.assertEqual(state['revision'],1)
            self.assertEqual(send('fixture-black','GET',route)[1],state)
            self.assertTrue(send('fixture-black','GET',route+'/legal-actions')[1]['actions'])

    def test_cleanup_closes_reopened_sqlite_on_windows(self):
        # The registered teardown callback must close the newest SQLite connection.
        # Windows cannot unlink an open match.sqlite, unlike POSIX.
        self.authority.close()
        self.authority = CheckersMatchAuthority(Path(self.scratch.name) / 'match.sqlite')
        reopened = self.authority
        # Run cleanup in the same LIFO order that unittest uses, before exiting.
        self.doCleanups()
        import sqlite3
        with self.assertRaises(sqlite3.ProgrammingError):
            reopened.sql.execute('SELECT 1')
        self.assertFalse(Path(self.scratch.name).exists())

    def test_service_absent_cannot_install_or_bind(self):
        for kwargs in (
            {'issuer':'bad issuer'}, {'resolve_session':None},
            {'lookup_original_challenge':None}, {'accepted_contact':None},
        ):
            with self.subTest(kwargs=kwargs):
                values=dict(issuer='tavi.social', resolve_session=self.accounts.__getitem__,
                    lookup_original_challenge=self.challenges.__getitem__, accepted_contact=lambda *args: True)
                values.update(kwargs)
                with self.assertRaises(ValueError):
                    CheckersSocialAdmission(**values)

if __name__ == '__main__':
    unittest.main()
