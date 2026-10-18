"""Characterization of external publisher origin proof, including SSRF/replay failures."""
import asyncio
import ipaddress
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests._test_dependencies import require_test_dependencies
require_test_dependencies()

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException
from tools.check_specs import compose, ROOT

spec = compose(ROOT/'looprd.yaml')
source = next(h['source'] for h in spec['handlers']
              if h['path'] == '/registry/publishers/proofs' and h['method'] == 'POST')
ns = {}
exec(compile(source, '<proof-handler>', 'exec'), ns)


class PublisherOriginProofTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.engine = sa.create_engine('sqlite:///' + str(Path(temp.name)/'registry.sqlite'))
        self.addCleanup(self.engine.dispose)
        metadata = sa.MetaData()
        sa.Table('App', metadata, sa.Column('id', sa.Integer, primary_key=True),
                 sa.Column('appId', sa.String(120)), sa.Column('title', sa.String(160)),
                 sa.Column('publisher', sa.String(120)), sa.Column('category', sa.String(48)),
                 sa.Column('version', sa.String(48)), sa.Column('status', sa.String(32)),
                 sa.Column('manifest', sa.JSON))
        metadata.create_all(self.engine)
        with self.engine.begin() as db:
            for migration in spec['database']['migrations']:
                for stmt in migration['statements']:
                    db.exec_driver_sql(stmt)
        self.Session = sessionmaker(self.engine)
        self.invoke(ns['register_publisher'], {'id':'studio-x','name':'Studio X',
                                               'origins':['https://studio.example.org']})

    def invoke(self, fn, payload=None, query=None):
        ctx = SimpleNamespace(body=payload, session_factory=self.Session,
                              transaction=self.Session.begin,
                              emit=None, request=SimpleNamespace(query_params=query or {}))
        return asyncio.run(fn(ctx))

    def issue(self):
        return self.invoke(ns['issue_publisher_proof'], {'publisherId':'studio-x',
                              'origin':'https://studio.example.org'})

    def verify(self, issue):
        return self.invoke(ns['verify_publisher_proof'], {'publisherId':'studio-x',
                           'origin':'https://studio.example.org','challengeId':issue['challengeId']})

    def test_roundtrip_and_no_auto_publication(self):
        issued = self.issue()
        self.assertEqual(issued['status'], 'pending')
        self.assertIn(issued['challengeId'] + '.txt', issued['proofUrl'])
        self.assertIn('publisher=studio-x\norigin=https://studio.example.org', issued['proofContent'])
        with patch.dict(ns, {'_read_public_https': lambda *a: issued['proofContent'].encode()}):
            verified = self.verify(issued)
        self.assertEqual(verified['status'], 'verified')
        self.assertFalse(verified['publisherIdentityVerified'])
        with self.assertRaises(HTTPException) as repeated:
            self.verify(issued)
        self.assertEqual(repeated.exception.status_code, 409)
        status = self.invoke(ns['list_publisher_proofs'], query={'publisherId':'studio-x'})
        self.assertEqual(status['proofs'][0]['status'], 'verified')
        self.assertNotIn('tokenDigest', status['proofs'][0])
        with self.Session() as db:
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AppRelease"')).scalar_one(), 0)
            self.assertEqual(db.execute(sa.text('SELECT "status" FROM "Publisher"')).scalar_one(), 'active')

    def test_reissue_invalidates_prior_nonce(self):
        first = self.issue(); second = self.issue()
        self.assertNotEqual(first['challengeId'], second['challengeId'])
        with self.assertRaises(HTTPException) as old:
            self.verify(first)
        self.assertEqual(old.exception.status_code, 409)
        with patch.dict(ns, {'_read_public_https': lambda *a: second['proofContent'].encode()}):
            self.assertEqual(self.verify(second)['status'], 'verified')

    def test_invalid_content_fails_without_consuming(self):
        issued = self.issue()
        with patch.dict(ns, {'_read_public_https': lambda *a: b'unrelated'}):
            with self.assertRaises(HTTPException) as wrong:
                self.verify(issued)
        self.assertEqual(wrong.exception.status_code, 422)
        with patch.dict(ns, {'_read_public_https': lambda *a: issued['proofContent'].encode()}):
            self.assertEqual(self.verify(issued)['status'], 'verified')

    def test_expired_challenge_rejected_before_network(self):
        issued = self.issue()
        with self.Session.begin() as db:
            db.execute(sa.text('UPDATE "PublisherOriginProof" SET "expiresAt"=:expiry'),
                       {'expiry':'2000-01-01T00:00:00+00:00'})
        with patch.dict(ns, {'_read_public_https': lambda *a: self.fail('network should not be touched')}):
            with self.assertRaises(HTTPException) as expired:
                self.verify(issued)
        self.assertEqual(expired.exception.status_code, 409)

    def test_fail_closed_on_network_error(self):
        issued = self.issue()
        def bad(*a):
            raise ValueError('unsafe DNS')
        with patch.dict(ns, {'_read_public_https': bad}):
            with self.assertRaises(HTTPException) as failed:
                self.verify(issued)
        self.assertEqual(failed.exception.status_code, 502)
        self.assertEqual(self.invoke(ns['list_publisher_proofs'],
                         query={'publisherId':'studio-x'})['proofs'][0]['status'], 'pending')

    def test_unapproved_origin_and_publisher_disabled(self):
        with self.assertRaises(HTTPException) as unapproved:
            self.invoke(ns['issue_publisher_proof'], {'publisherId':'studio-x',
                                                       'origin':'https://elsewhere.example.org'})
        self.assertEqual(unapproved.exception.status_code, 403)
        self.invoke(ns['change_publisher_status'], {'publisherId':'studio-x','status':'disabled'})
        with self.assertRaises(HTTPException) as disabled:
            self.issue()
        self.assertEqual(disabled.exception.status_code, 403)

    def test_reject_extra_keys_and_malformed_ids(self):
        for bad in ({'publisherId':'studio-x','origin':'https://studio.example.org','ignore':True},
                    {'publisherId':'studio-x','origin':'https://127.0.0.1'},
                    {'publisherId':'studio-x','origin':'https://studio.example.org:8080'}):
            with self.subTest(bad=bad), self.assertRaises(HTTPException):
                self.invoke(ns['issue_publisher_proof'], bad)
        issued = self.issue()
        with self.assertRaises(HTTPException):
            self.invoke(ns['verify_publisher_proof'], {'publisherId':'studio-x',
                        'origin':'https://studio.example.org', 'challengeId':'a'*31})

    def test_private_dns_answers_fail_closed(self):
        for value in ('127.0.0.1','10.1.2.3','172.16.0.1','192.168.1.2',
                      '169.254.169.254','::1','fc00::1234','2001:db8::1','ff02::1'):
            with self.subTest(value=value), patch.object(ns['socket'], 'getaddrinfo',
                    return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', (value,443))]):
                with self.assertRaises(ValueError):
                    ns['_public_addresses']('studio.example.org')

    def test_mixed_dns_answers_fail_closed(self):
        answers=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1',443)),
                 (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1',443))]
        with patch.object(ns['socket'], 'getaddrinfo', return_value=answers):
            with self.assertRaises(ValueError):
                ns['_public_addresses']('studio.example.org')

    def test_public_dns_is_pinned(self):
        answers=[(socket.AF_INET, socket.SOCK_STREAM,6,'',('1.1.1.1',443))]
        with patch.object(ns['socket'],'getaddrinfo',return_value=answers):
            self.assertEqual(ns['_public_addresses']('studio.example.org'),('1.1.1.1',))

    def test_redirect_and_oversize_network_response_rejected(self):
        class FakeSocket:
            def settimeout(self, n): pass
            def sendall(self, payload):
                self.request=payload
            def close(self): pass
        class FakeContext:
            def wrap_socket(self, sock, server_hostname):
                self.assert_host=server_hostname
                return FakeSocket()
        class FakeResponse:
            def __init__(self, sock): pass
            def begin(self): pass
            def getheader(self, name, default=None): return default
            def read(self, length): return b'x'*1500
            def close(self): pass
        with patch.dict(ns, {'_public_addresses': lambda host: ('1.1.1.1',)}), \
             patch.object(ns['socket'], 'create_connection',return_value=FakeSocket()), \
             patch.object(ns['ssl'], 'create_default_context',return_value=FakeContext()), \
             patch.object(ns['http'].client, 'HTTPResponse',FakeResponse):
            FakeResponse.status=302
            with self.assertRaisesRegex(ValueError, 'redirects disallowed'):
                ns['_read_public_https']('https://studio.example.org','a'*32)
            FakeResponse.status=200
            with self.assertRaisesRegex(ValueError, 'too large'):
                ns['_read_public_https']('https://studio.example.org','a'*32)

    def test_only_operator_routes(self):
        routes = [x for x in spec['handlers'] if x['path'].startswith('/registry/publishers/proofs')]
        self.assertEqual(len(routes),3)
        self.assertTrue(all(x['scopes']==['apps:approve'] for x in routes))
        self.assertEqual(spec['database']['schemaVersion'],5)

    def test_second_registered_publisher_cannot_claim_same_origin(self):
        self.invoke(ns['register_publisher'], {'id': 'studio-y', 'name': 'Other studio',
                       'origins': ['https://studio.example.org']})
        self.issue()
        with self.assertRaises(HTTPException) as conflict:
            self.invoke(ns['issue_publisher_proof'], {'publisherId': 'studio-y',
                            'origin': 'https://studio.example.org'})
        self.assertEqual(conflict.exception.status_code, 409)

    def test_migration_preserves_preexisting_publisher(self):
        # This checks the actual v4 SQL against a v3 schema, without dropping tables.
        with self.Session.begin() as db:
            db.execute(sa.text('INSERT INTO "App" ("appId","title","publisher","category",'
                               '"version","status","manifest") VALUES '
                               '(:a,:b,:c,:d,:e,:f,:g)'),
                       dict(a='survivor.game',b='Survivor',c='studio-x',d='game',e='1.0.0',
                            f='disabled',g='{}'))
        with self.Session() as db:
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "App"')).scalar_one(),1)
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "Publisher"')).scalar_one(),1)
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "PublisherOriginProof"')).scalar_one(),0)

    def test_second_publisher_cannot_claim_origin_implicitly(self):
        with self.assertRaises(HTTPException):
            self.invoke(ns['issue_publisher_proof'], {'publisherId':'different-studio',
                              'origin':'https://studio.example.org'})


if __name__ == '__main__': unittest.main()
