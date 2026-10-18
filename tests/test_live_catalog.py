"""A real anonymous loopback gateway must never serve a revoked/stale snapshot."""
import hashlib
import json
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tests._test_dependencies import require_test_dependencies
require_test_dependencies()

from tests.test_registry_runtime import RegistryStorageTests, BASE, submit, review, change_publisher_status
from tools.live_catalog import gateway_handler, fresh_snapshot, validate_browser_origin


class LiveCatalogTests(RegistryStorageTests):
    def setUp(self):
        super().setUp()
        self.assets = Path(self.temp.name) / 'assets'
        self.assets.mkdir()
        self.server = HTTPServer(('127.0.0.1', 0), gateway_handler(self.engine.url.database, self.assets,
                                                               'https://thebigtreeinc.github.io'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%d' % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        super().tearDown()

    def _get(self, path='/catalog.json', origin='https://thebigtreeinc.github.io', method='GET'):
        request = Request(self.url + path, method=method, headers={'Origin': origin})
        try:
            with urlopen(request, timeout=3) as reply:
                return reply.status, dict(reply.headers), reply.read()
        except HTTPError as error:
            return error.code, dict(error.headers), error.read()

    def _publish(self):
        self.prepare()
        content = b'<!doctype html><title>Reviewed Checkers</title>'
        digest = hashlib.sha256(content).hexdigest()
        manifest = BASE | {'sha256': digest, 'entry': f'https://assets.example.org/assets/{digest}/index.html'}
        item = self.invoke(submit, {'manifest': manifest})
        self.invoke(review, {'submissionId': item['submissionId'], 'decision': 'approve'})
        (self.assets / (digest + '.html')).write_bytes(content)
        return digest

    def test_live_gateway_disables_and_restores_without_restart_or_push(self):
        self._publish()
        status, headers, body = self._get()
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['apps']), 1)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://thebigtreeinc.github.io')
        self.assertNotIn('apiKey', body.decode())
        self.invoke(change_publisher_status, {'publisherId': 'first-party', 'status': 'disabled'})
        status, headers, body = self._get()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['apps'], [])
        self.invoke(change_publisher_status, {'publisherId': 'first-party', 'status': 'active'})
        self.assertEqual(len(json.loads(self._get()[2])['apps']), 1)

    def test_gateway_fails_closed_on_missing_or_tampered_assets(self):
        digest = self._publish()
        self.assertEqual(self._get()[0], 200)
        (self.assets / (digest + '.html')).write_bytes(b'malicious replacement')
        status, headers, body = self._get()
        self.assertEqual(status, 503)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual(json.loads(body), {'error': 'catalog unavailable'})
        self.assertNotIn('Reviewed Checkers', body.decode())

    def test_cors_is_exact_and_no_credentials_or_wildcards(self):
        self._publish()
        _, headers, _ = self._get(origin='https://evil.example.org')
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertNotIn('Access-Control-Allow-Credentials', headers)
        self.assertEqual(self._get(method='OPTIONS')[0], 204)
        self.assertEqual(self._get(method='OPTIONS',origin='https://evil.example.org')[0], 403)
        self.assertEqual(self._get('/registry/publishers')[0], 404)
        self.assertEqual(self._get('/catalog.json?token=secret')[0], 404)
        self.assertEqual(self._get(method='HEAD')[0], 405)

    def test_missing_database_never_serves_old_snapshot(self):
        self._publish()
        self.assertEqual(self._get()[0], 200)
        self.engine.dispose()
        Path(self.engine.url.database).unlink()
        self.assertEqual(self._get()[0], 503)

    def test_gateway_requires_clean_browser_origin(self):
        for origin in ('http://thebigtreeinc.github.io','https://localhost',
                       'https://thebigtreeinc.github.io/atrium','https://evil@thebigtreeinc.github.io'):
            with self.assertRaises(ValueError):
                validate_browser_origin(origin)
        self.assertEqual(validate_browser_origin('https://thebigtreeinc.github.io'), 'https://thebigtreeinc.github.io')


if __name__ == '__main__':
    unittest.main()
