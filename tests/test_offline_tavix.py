"""External game -> TaviX preview interchange; no game, Tavi installation or approval."""
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
from tools.offline_game import pack_folder, verify_archive
from tools.offline_tavix import build_tavix, verify_tavix

META = dict(id='klondike.solitaire',publisher='example-publisher',title='Klondike Solitaire',version='0.1.0')
APP_ID = 'org.example.klondike'

class OfflineTavixBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='atrium-independent-tavix-')
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'independent-game';self.folder.mkdir()
        (self.folder/'index.html').write_text('<html><head><link rel="stylesheet" href="styles/app.css"></head><body><script src="js/main.js"></script></body></html>',encoding='utf-8')
        (self.folder/'js').mkdir();(self.folder/'js/main.js').write_text('const standaloneGame = true;',encoding='utf-8')
        (self.folder/'styles').mkdir();(self.folder/'styles/app.css').write_text('body { background: green; }',encoding='utf-8')
        (self.folder/'assets').mkdir();(self.folder/'assets/icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>',encoding='utf-8')
        (self.folder/'MANIFEST.sha256').write_text('a'*64+'  index.html\n',encoding='utf-8')
        self.candidate=Path(self.tmp.name)/'candidate.zip'
        self.tavix=Path(self.tmp.name)/'dev.tavix'

    def build(self):
        pack_folder(self.folder,self.candidate,META)
        return build_tavix(self.candidate,self.tavix,APP_ID)

    def test_external_game_with_svg_namespace_and_integrity_manifest_accepted(self):
        r=pack_folder(self.folder,self.candidate,META)
        self.assertEqual(r['assets'],5)
        self.assertEqual(verify_archive(self.candidate),r)

    def test_candidate_to_tavix_preserves_original_game_files(self):
        r=self.build()
        self.assertEqual(r['status'],'developer_preview_only_not_installed')
        with ZipFile(self.tavix) as z:
            manifest=json.loads(z.read('manifest.json'))
            self.assertEqual(manifest['kind'],'app')
            self.assertEqual(manifest['id'],APP_ID)
            self.assertEqual(manifest['permissions'],['ui.panel'])
            self.assertEqual(manifest['icon'],'ui/assets/icon.svg')
            self.assertEqual(z.read('ui/js/main.js'),(self.folder/'js/main.js').read_bytes())
            self.assertNotIn('ui/MANIFEST.sha256',z.namelist())
            src=json.loads(z.read('ui/atrium-game.json'))
            self.assertEqual(src['gameId'],META['id'])
            self.assertEqual(src['sourceCandidateSha256'],verify_archive(self.candidate)['sha256'])
            self.assertEqual({x.compress_type for x in z.infolist()},{ZIP_STORED})

    def test_tavix_repeated_build_is_reproducible(self):
        first=self.build()['sha256']
        self.assertEqual(self.build()['sha256'],first)
        self.assertEqual(verify_tavix(self.tavix)['sha256'],first)

    def test_corrupted_tavix_asset_fails(self):
        self.build()
        with ZipFile(self.tavix) as z:items={i.filename:z.read(i.filename) for i in z.infolist()}
        items['ui/js/main.js']=b'malicious replaced bytecode'
        with ZipFile(self.tavix,'w',ZIP_STORED) as z:
            for name,body in items.items():z.writestr(name,body)
        with self.assertRaisesRegex(ValueError,'integrity'):
            verify_tavix(self.tavix)

    def test_corrupted_candidate_fails_before_conversion(self):
        pack_folder(self.folder,self.candidate,META)
        with ZipFile(self.candidate) as z:items={i.filename:z.read(i.filename) for i in z.infolist()}
        items['js/main.js']=b'evil'
        with ZipFile(self.candidate,'w',ZIP_DEFLATED) as z:
            for name,body in items.items():z.writestr(name,body)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            build_tavix(self.candidate,self.tavix,APP_ID)
        self.assertFalse(self.tavix.exists())

    def test_unsupported_webassembly_target_fails_until_tavi_supports_it(self):
        (self.folder/'engine.wasm').write_bytes(b'\x00asm\x01\x00\x00\x00')
        pack_folder(self.folder,self.candidate,META)
        with self.assertRaisesRegex(ValueError,'Unsupported or unsafe TaviX asset path'):
            build_tavix(self.candidate,self.tavix,APP_ID)

    def test_does_not_impersonate_official_app_or_claim_install(self):
        pack_folder(self.folder,self.candidate,META)
        with self.assertRaisesRegex(ValueError,'TaviX ID'):
            build_tavix(self.candidate,self.tavix,'klondike.solitaire')
        self.assertFalse(self.tavix.exists())
        r=build_tavix(self.candidate,self.tavix,APP_ID)
        self.assertNotIn('installed',r['status'].replace('not_installed',''))
        with ZipFile(self.tavix) as z:
            manifest=json.loads(z.read('manifest.json'))
            self.assertFalse(any(p!='ui.panel' for p in manifest['permissions']))
            self.assertNotEqual(manifest['id'],'inc.thebigtree.tavi.atrium')

    def test_remote_url_still_rejected_in_asset(self):
        (self.folder/'js/main.js').write_text("fetch('https://external.example/game')",encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'External resource'):
            pack_folder(self.folder,self.candidate,META)

if __name__=='__main__':unittest.main()
