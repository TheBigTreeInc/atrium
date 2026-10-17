"""Read-only export must never publish unreviewed, disabled, or tampered apps."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests._test_dependencies import require_test_dependencies
require_test_dependencies()

import sqlalchemy as sa

from tools.export_catalog import build_catalog, export
from tests.test_registry_runtime import RegistryStorageTests, BASE, DIGEST, register_publisher, submit, review, change_publisher_status


class PublicExportTests(RegistryStorageTests):
    def setUp(self):
        super().setUp()
        self.assets = Path(self.temp.name) / 'verified-assets'
        self.assets.mkdir()
        self.output = Path(self.temp.name) / 'catalog.json'

    def _publish(self, body):
        item = self.invoke(submit, {'manifest': body})
        self.invoke(review, {'submissionId': item['submissionId'], 'decision': 'approve'})

    def test_operator_export_and_disable(self):
        self.prepare()
        content = b'<!doctype html><title>Checkers</title>'
        digest = hashlib.sha256(content).hexdigest()
        manifest = BASE | {'sha256': digest,
                          'entry': f'https://assets.example.org/assets/{digest}/index.html'}
        self._publish(manifest)
        with self.assertRaises(ValueError):
            export(self.engine.url.database, self.assets, self.output)
        (self.assets / (digest + '.html')).write_bytes(content)
        receipt = export(self.engine.url.database, self.assets, self.output)
        self.assertEqual(receipt['count'], 1)
        snapshot = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(snapshot['apps'][0]['id'], BASE['id'])
        self.assertEqual(snapshot['allowedOrigins'], ['https://assets.example.org'])
        self.assertNotIn('apiKey', self.output.read_text(encoding='utf-8'))
        self.assertEqual(self.invoke(change_publisher_status, {'publisherId': 'first-party', 'status': 'disabled'})['affectedApps'], 1)
        self.assertEqual(build_catalog(self.engine.url.database, self.assets)['apps'], [])
        self.assertEqual(export(self.engine.url.database, self.assets, self.output)['count'], 0)
        self.assertEqual(self.invoke(change_publisher_status, {'publisherId': 'first-party', 'status': 'active'})['status'], 'active')
        self.assertEqual(build_catalog(self.engine.url.database, self.assets)['apps'][0]['id'], BASE['id'])

    def test_fail_closed_on_tampering_preserves_previous_snapshot(self):
        self.prepare()
        content = b'<!doctype html><title>OK</title>'
        digest = hashlib.sha256(content).hexdigest()
        manifest = BASE | {'sha256': digest,
                          'entry': f'https://assets.example.org/assets/{digest}/index.html'}
        self._publish(manifest)
        asset = self.assets / (digest + '.html')
        asset.write_bytes(content)
        export(self.engine.url.database, self.assets, self.output)
        before = self.output.read_bytes()
        asset.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            export(self.engine.url.database, self.assets, self.output)
        self.assertEqual(self.output.read_bytes(), before)
        asset.write_bytes(content)
        with self.Session.begin() as s:
            s.execute(sa.text('UPDATE "App" SET "manifest"=:val'), {'val': json.dumps(manifest | {'title': 'Tampered'})})
        with self.assertRaisesRegex(ValueError, 'tampered'):
            export(self.engine.url.database, self.assets, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_empty_catalog_requires_no_assets_and_has_no_origins(self):
        self.assertEqual(build_catalog(self.engine.url.database, self.assets),
                         {'schema': 'atrium.catalog-snapshot/v1', 'allowedOrigins': [], 'apps': []})


if __name__ == '__main__':
    unittest.main()
