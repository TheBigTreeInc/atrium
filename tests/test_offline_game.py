"""No bundled Solitaire or runtime assumptions; only external candidate ingestion."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from tools.offline_game import pack_folder, verify_archive

META = {'id':'org.example.solitaire','publisher':'example','title':'Solitaire','version':'1.0.0'}

class OfflineGameContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='atrium-external-game-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.game = self.path/'external'
        self.game.mkdir()
        (self.game/'index.html').write_text('<html><script src="game.js"></script></html>', encoding='utf-8')
        (self.game/'game.js').write_text('const game = {offline:true};', encoding='utf-8')
        self.bundle = self.path/'game.zip'
    def build(self):
        return pack_folder(self.game,self.bundle,META)
    def test_independent_bundle_is_verified_without_tavi_or_looprd(self):
        r=self.build()
        self.assertEqual(r['status'],'candidate_verified_not_installed')
        self.assertEqual(r['assets'],2)
        self.assertEqual(verify_archive(self.bundle),r)
    def test_deterministic_archive(self):
        a=self.build()['sha256']
        self.assertEqual(a,self.build()['sha256'])
    def test_remote_assets_rejected(self):
        (self.game/'game.js').write_text("import 'https://cdn.example/game.js';",encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'External resource'):
            self.build()
    def test_missing_entry_and_invalid_id_rejected(self):
        (self.game/'index.html').unlink()
        with self.assertRaisesRegex(ValueError,'Missing'):
            self.build()
        (self.game/'index.html').write_text('offline',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'game ID'):
            pack_folder(self.game,self.bundle,{**META,'id':'INVALID'})
    def test_symlinks_and_traversal_rejected(self):
        with ZipFile(self.bundle,'w',ZIP_DEFLATED) as z:
            z.writestr('../outside.html','BAD')
            z.writestr('atrium-game.json','{}')
        with self.assertRaisesRegex(ValueError,'Unsafe asset'):
            verify_archive(self.bundle)
        link = self.game/'link.js'
        try:
            link.symlink_to(self.game/'game.js')
        except OSError as exc:
            # Non-developer Windows accounts lack SeCreateSymbolicLinkPrivilege.
            # Still test the *rejection* without needing OS link privileges.
            if sys.platform != 'win32' or getattr(exc, 'winerror', None) != 1314:
                raise
            self.assertSymlinkRejectedViaMock()
        else:
            with self.assertRaisesRegex(ValueError,'Symlink'):
                self.build()

    def assertSymlinkRejectedViaMock(self):
        # Exercise pack_folder's real is_symlink guard deterministically even
        # when the operating system cannot create a symlink at all.
        target = self.game/'game.js'
        # Patching Path alone does not reliably intercept WindowsPath methods.
        # Patch the concrete class returned by the running platform.
        concrete_path = type(target)
        with patch.object(concrete_path, 'is_symlink', autospec=True,
                          side_effect=lambda path: path.name == 'game.js') as guard:
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                self.build()
            self.assertTrue(guard.called, 'pack_folder must check actual asset paths')

    def test_symlink_guard_does_not_require_windows_privilege(self):
        self.assertSymlinkRejectedViaMock()
    def test_changed_asset_after_manifest_is_rejected(self):
        self.build()
        with ZipFile(self.bundle) as z:
            entries={i.filename:z.read(i.filename) for i in z.infolist()}
        entries['game.js']=b'changed'
        with ZipFile(self.bundle,'w',ZIP_DEFLATED) as z:
            for k,v in entries.items():z.writestr(k,v)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            verify_archive(self.bundle)
    def test_unlisted_asset_is_rejected(self):
        self.build()
        with ZipFile(self.bundle,'a') as z:z.writestr('unlisted.js','hello')
        with self.assertRaisesRegex(ValueError,'Unlisted'):
            verify_archive(self.bundle)
    def test_source_only_contract_has_no_install_side_effect(self):
        self.build()
        self.assertFalse((self.path/'installed').exists())
        from tools import offline_game
        import inspect
        self.assertNotIn('subprocess',inspect.getsource(offline_game))
        self.assertNotIn('requests.',inspect.getsource(offline_game))

if __name__=='__main__':unittest.main()
