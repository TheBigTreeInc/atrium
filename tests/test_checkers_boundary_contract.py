"""Non-production structural contract: game rules stay with the game module.

Does NOT prove live Social identity, an installed Tavi client, or deployed LoopRD.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CheckersOwnershipBoundaryTests(unittest.TestCase):
    def test_generic_lobby_and_catalog_do_not_import_checkers_authority(self):
        generic = ('src/hostless_lobby.py', 'src/lobby_runtime.py', 'src/catalog.py',
                   'src/hosted_catalog_looprd.py', 'src/discovery_runtime.py')
        for relative in generic:
            with self.subTest(source=relative):
                source = (ROOT / relative).read_text(encoding='utf-8')
                tree = ast.parse(source)
                imports = [node.module for node in ast.walk(tree)
                           if isinstance(node, ast.ImportFrom) and node.module]
                imports += [alias.name for node in ast.walk(tree)
                            if isinstance(node, ast.Import) for alias in node.names]
                self.assertFalse(any(name.startswith(('src.checkers', 'checkers'))
                                     for name in imports))

    def test_tavix_and_browser_do_not_own_server_match_or_game_rules(self):
        for relative in ('extensions/tavi/extension-bridge.mjs',
                         'extensions/tavi/tavix-sdk.mjs',
                         'src/checkers_remote_entry.mjs',
                         'src/checkers_remote_view.mjs'):
            with self.subTest(source=relative):
                source = (ROOT / relative).read_text(encoding='utf-8')
                self.assertNotIn('checkers_match_authority', source)
                self.assertNotIn('checkers_adapter', source)
                self.assertNotIn('checkers_demo_engine', source)
                self.assertNotIn('function applyMove(', source)
        # The game rules oracle is not a mutable public match host.
        spec = (ROOT / 'modules/games/checkers/looprd.yaml').read_text(encoding='utf-8')
        self.assertIn('persistentMatchesEnabled: false', spec)
        self.assertNotIn('checkers_trusted_routes', spec)

if __name__ == '__main__':
    unittest.main()
