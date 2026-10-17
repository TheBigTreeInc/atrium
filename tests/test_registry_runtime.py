"""Storage and security characterization tests for operator-managed registry endpoints."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests._test_dependencies import require_test_dependencies
require_test_dependencies()

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException

from tools.check_specs import compose, ROOT

# Execute precisely the canonical code embedded into the generated DAPI handler.
_spec = compose(ROOT / 'looprd.yaml')
_source = next(h['source'] for h in _spec['handlers'] if h['path'] == '/registry/reviews')
_namespace = {}
exec(compile(_source, '<dapi-registry-test>', 'exec'), _namespace)
register_publisher = _namespace['register_publisher']
submit = _namespace['submit']
review = _namespace['review']
catalog = _namespace['catalog']
disable = _namespace['disable']
submissions = _namespace['submissions']
change_publisher_status = _namespace['change_publisher_status']

DIGEST = 'a' * 64
BASE = {
    'id': 'classic.checkers', 'title': 'Checkers', 'version': '1.0.0',
    'publisher': 'first-party', 'kind': 'game',
    'entry': f'https://assets.example.org/assets/{DIGEST}/index.html',
    'sha256': DIGEST, 'permissions': ['game:join'],
}


class RegistryStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = sa.create_engine(f'sqlite:///{self.temp.name}/registry.db')
        self.addCleanup(self.engine.dispose)
        metadata = sa.MetaData()
        sa.Table('App', metadata,
                 sa.Column('id', sa.Integer, primary_key=True),
                 sa.Column('appId', sa.String(120), unique=True, nullable=False),
                 sa.Column('title', sa.String(160), nullable=False),
                 sa.Column('publisher', sa.String(120), nullable=False),
                 sa.Column('category', sa.String(48), nullable=False),
                 sa.Column('version', sa.String(48), nullable=False),
                 sa.Column('status', sa.String(32), nullable=False),
                 sa.Column('manifest', sa.JSON, nullable=False))
        metadata.create_all(self.engine)
        # Exercise the actual declared additive migration statements, not a fake table.
        migration = compose(ROOT / 'looprd.yaml')['database']['migrations'][0]
        with self.engine.begin() as connection:
            for statement in migration['statements']:
                connection.exec_driver_sql(statement)
        self.Session = sessionmaker(self.engine)
        self.events = []

    def invoke(self, action, body=None):
        ctx = SimpleNamespace(body=body, session_factory=self.Session,
                              transaction=self.Session.begin,
                              emit=lambda s, event: self.events.append(event))
        return asyncio.run(action(ctx))

    def prepare(self):
        self.invoke(register_publisher, {'id': 'first-party', 'name': 'First party',
                                         'origins': ['https://assets.example.org']})

    def test_submit_approve_discover_disable_is_persistent(self):
        self.prepare()
        self.assertEqual(self.invoke(catalog)['apps'], [])
        response = self.invoke(submit, {'manifest': BASE})
        self.assertEqual(self.invoke(catalog)['apps'], [])
        self.assertEqual(self.invoke(review, {'submissionId': response['submissionId'],
                                             'decision': 'approve'})['status'], 'approved')
        self.assertEqual(self.invoke(catalog)['apps'][0]['id'], BASE['id'])
        self.assertEqual(self.events[0]['resource'], 'apps')
        self.assertEqual(self.invoke(disable, {'appId': BASE['id']})['status'], 'disabled')
        self.assertEqual(self.invoke(catalog)['apps'], [])
        # A new database session must see the previous committed version and status.
        with self.Session() as session:
            assert session.execute(sa.text('SELECT COUNT(*) FROM "AppRelease"')).scalar_one() == 1
            assert session.execute(sa.text('SELECT status FROM "App"')).scalar_one() == 'disabled'

    def test_reject_before_publication(self):
        self.prepare()
        for bad in (BASE | {'publisher': 'other-party'},
                    BASE | {'entry': 'https://localhost/assets/' + DIGEST},
                    BASE | {'permissions': ['admin:all']},
                    BASE | {'extraSecret': 'bad'}):
            with self.subTest(bad=bad), self.assertRaises(HTTPException):
                self.invoke(submit, {'manifest': bad})
        self.assertEqual(self.invoke(submissions)['submissions'], [])

    def test_review_immutable_and_no_downgrade(self):
        self.prepare()
        first = self.invoke(submit, {'manifest': BASE})
        self.invoke(review, {'submissionId': first['submissionId'], 'decision': 'approve'})
        with self.assertRaises(HTTPException):
            self.invoke(review, {'submissionId': first['submissionId'], 'decision': 'approve'})
        with self.assertRaises(HTTPException):
            self.invoke(submit, {'manifest': BASE})
        second = self.invoke(submit, {'manifest': BASE | {'version': '0.9.0'}})
        with self.assertRaises(HTTPException) as error:
            self.invoke(review, {'submissionId': second['submissionId'], 'decision': 'approve'})
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.invoke(catalog)['apps'][0]['version'], '1.0.0')

    def test_review_rejection_does_not_publish(self):
        self.prepare()
        submission = self.invoke(submit, {'manifest': BASE})
        self.invoke(review, {'submissionId': submission['submissionId'], 'decision': 'reject'})
        self.assertEqual(self.invoke(catalog)['apps'], [])
        self.assertEqual(self.invoke(submissions)['submissions'][0]['status'], 'rejected')

    def test_separate_publishers_cannot_take_an_existing_app(self):
        self.prepare()
        first = self.invoke(submit, {'manifest': BASE})
        self.invoke(review, {'submissionId': first['submissionId'], 'decision': 'approve'})
        self.invoke(register_publisher, {'id': 'another-publisher', 'name': 'Other',
                                         'origins': ['https://assets.example.org']})
        forged = BASE | {'publisher': 'another-publisher', 'version': '2.0.0'}
        with self.assertRaises(HTTPException) as error:
            self.invoke(submit, {'manifest': forged})
        self.assertEqual(error.exception.status_code, 409)

    def test_legacy_unreviewed_app_is_not_discoverable(self):
        self.prepare()
        with self.Session.begin() as session:
            session.execute(sa.text('INSERT INTO "App" ("appId","title","publisher","category",'
                                    '"version","status","manifest") VALUES '
                                    '(:app,:title,:publisher,:kind,:version,:status,:manifest)'),
                            {'app':BASE['id'], 'title':BASE['title'], 'publisher':BASE['publisher'],
                             'kind':BASE['kind'], 'version':BASE['version'], 'status':'published',
                             'manifest':json.dumps(BASE)})
        self.assertEqual(self.invoke(catalog)['apps'], [])

    def test_tampered_active_app_is_not_discoverable(self):
        self.prepare()
        submission = self.invoke(submit, {'manifest': BASE})
        self.invoke(review, {'submissionId': submission['submissionId'], 'decision': 'approve'})
        with self.Session.begin() as session:
            session.execute(sa.text('UPDATE "App" SET "manifest"=:bad WHERE "appId"=:app'),
                            {'bad': json.dumps(BASE | {'entry':'https://evil.example/index.html'}),
                             'app': BASE['id']})
        self.assertEqual(self.invoke(catalog)['apps'], [])

    def test_catalog_pages_only_reviewed_entries(self):
        self.prepare()
        second = BASE | {'id': 'classic.chess', 'title': 'Chess'}
        for manifest in (BASE, second):
            self.invoke(review, {'submissionId': self.invoke(submit, {'manifest':manifest})['submissionId'],
                                 'decision':'approve'})
        from types import SimpleNamespace
        def page(query):
            ctx = SimpleNamespace(body=None, session_factory=self.Session,
                                  request=SimpleNamespace(query_params=query))
            return asyncio.run(catalog(ctx))
        first = page({'limit':'1'})
        self.assertTrue(first['hasMore'])
        self.assertEqual(first['count'], 1)
        later = page({'limit':'1', 'after':first['next']})
        self.assertFalse(later['hasMore'])
        self.assertNotEqual(first['apps'][0]['id'], later['apps'][0]['id'])
        for query in ({'limit':'0'}, {'limit':'101'}, {'after':'../secrets'}):
            with self.assertRaises(HTTPException):
                page(query)

    def test_publisher_suspend_revoke_and_restore_catalog(self):
        self.prepare()
        submission = self.invoke(submit, {'manifest':BASE})
        self.invoke(review, {'submissionId':submission['submissionId'], 'decision':'approve'})
        self.assertEqual(len(self.invoke(catalog)['apps']), 1)
        changed = self.invoke(change_publisher_status,
                              {'publisherId':'first-party', 'status':'disabled'})
        self.assertEqual(changed['affectedApps'], 1)
        self.assertEqual(self.invoke(catalog)['apps'], [])
        with self.assertRaises(HTTPException):
            self.invoke(submit, {'manifest': BASE | {'version':'2.0.0'}})
        self.assertEqual(self.invoke(change_publisher_status,
                                    {'publisherId':'first-party', 'status':'active'})['status'], 'active')
        self.assertEqual(len(self.invoke(catalog)['apps']), 1)
        self.assertGreaterEqual(len(self.events), 3)

    def test_generic_registry_resources_are_read_only(self):
        spec = compose(ROOT / 'looprd.yaml')
        self.assertEqual(spec['resources']['apps']['operations'], ['list', 'get'])
        self.assertEqual(spec['resources']['endpoints']['operations'], ['list', 'get'])
        for path in ('/registry/submissions', '/registry/reviews', '/registry/disable'):
            handler = next(h for h in spec['handlers'] if h['path'] == path and h.get('method') == 'POST')
            self.assertEqual(handler['scopes'], ['apps:approve'])
        read = next(h for h in spec['handlers'] if h['path'] == '/registry/catalog')
        self.assertEqual(read['scopes'], ['apps:read'])
        self.assertEqual(spec['auth']['mode'], 'database')


if __name__ == '__main__':
    unittest.main()
