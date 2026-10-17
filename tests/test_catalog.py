import unittest
from src.catalog import validate_manifest,canonical_hash
BASE={'id':'classic.checkers','title':'Checkers','version':'0.1.0','publisher':'first-party','kind':'game','entry':'https://api.example.org/assets/sha256/'+('a'*64)+'/index.html','sha256':'a'*64,'permissions':['game:join']}
class CatalogTests(unittest.TestCase):
    def test_approved_immutable_entry(self):
        x=validate_manifest(BASE,approved_origins={'https://api.example.org'})
        self.assertEqual(x['id'],'classic.checkers')
        self.assertEqual(canonical_hash(x),canonical_hash(dict(x)))
    def test_unapproved_endpoint(self):
        x=BASE|{'entry':'https://evil.example/index.html'}
        with self.assertRaises(ValueError):validate_manifest(x,approved_origins={'https://api.example.org'})
    def test_rejects_query_credentials_and_fragment(self):
        for path in ['https://api.example.org/x?a=1','https://api.example.org/x#frag','https://user:pw@api.example.org/x','http://api.example.org/x']:
            with self.subTest(path=path),self.assertRaises(ValueError):validate_manifest(BASE|{'entry':path},approved_origins={'https://api.example.org'})
    def test_rejects_ip_private_and_malformed_dns_origins(self):
        from src.catalog import validate_origin
        for origin in ('https://127.0.0.1', 'https://localhost',
                       'https://game.internal', 'https://10.0.0.1',
                       'https://-invalid.example.com', 'https://bad..example.com'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_origin(origin)

    def test_invalid_capability(self):
        with self.assertRaises(ValueError):validate_manifest(BASE|{'permissions':['admin:write']},approved_origins={'https://api.example.org'})
    def test_rejects_untrusted_metadata(self):
        with self.assertRaises(ValueError):
            validate_manifest(BASE|{'secret':'bad'},approved_origins={'https://api.example.org'})
if __name__=='__main__':unittest.main()
