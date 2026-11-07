"""Source-backed C4 architecture baseline checks (NOT a Structurizr DSL parser)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DSL = ROOT / 'architecture' / 'c4' / 'workspace.dsl'
DOC = ROOT / 'architecture' / 'c4' / 'README.adoc'


class C4ArchitectureTests(unittest.TestCase):
    def test_package_includes_source_of_truth_at_requested_root(self):
        from tools.package_zip import source_files
        source = {p.relative_to(ROOT).as_posix() for p in source_files()}
        self.assertIn('architecture/c4/workspace.dsl', source)
        self.assertIn('architecture/c4/README.adoc', source)

    def test_explicit_level_3_and_minimal_context_views(self):
        text = DSL.read_text(encoding='utf-8')
        expected = {
            'atrium_context': 'systemContext atrium',
            'atrium_containers': 'container atrium',
            'atrium_runtime_components': 'component api',
            'atrium_portal_components': 'component portal',
            'atrium_tavix_components': 'component tavix',
            'atrium_discovery_flow': 'dynamic api',
            'atrium_checkers_source_flow': 'dynamic api',
        }
        for key, prefix in expected.items():
            with self.subTest(key=key):
                self.assertIn(prefix + ' ' + key, text)
        for component in ('registry', 'discovery', 'arcade', 'hostedProjection',
                          'socialAdmission', 'checkersRoutes', 'checkersHost',
                          'checkersAuthority', 'portalShell', 'hostedGameClient',
                          'checkersPlayer', 'taviBridge', 'taviSdk'):
            self.assertRegex(text, rf'(?m)^\s*{component}\s*=\s*component\b')

    def test_identifiers_and_relationship_endpoints_are_unique_and_defined(self):
        text = DSL.read_text(encoding='utf-8')
        declarations = re.findall(r'^\s*([A-Za-z][A-Za-z0-9]*)\s*=\s*(?:person|softwareSystem|container|component)\b',text,re.M)
        self.assertEqual(len(declarations),len(set(declarations)), 'C4 element identifiers must be stable/unique')
        known=set(declarations)
        edges=re.findall(r'^\s*([A-Za-z][A-Za-z0-9]*)\s*->\s*([A-Za-z][A-Za-z0-9]*)\s+"',text,re.M)
        self.assertGreater(len(edges),25)
        self.assertFalse({ref for edge in edges for ref in edge}-known)
        views=re.findall(r'^\s*(?:systemContext|container|component|dynamic)\s+\w+\s+(atrium_[a-z_]+)\b',text,re.M)
        self.assertEqual(len(views),len(set(views)))
        self.assertEqual(len(views),8)
        self.assertIn("atrium_offline_candidate_components", views)
        # Strip quoted strings/comments to sanity-check block nesting; this does NOT validate DSL grammar.
        without_strings=re.sub(r'"(?:[^"\\]|\\.)*"','""',text)
        self.assertEqual(without_strings.count('{'),without_strings.count('}'))

    def test_source_only_boundaries_are_not_misrepresented_as_live(self):
        text=DSL.read_text(encoding='utf-8')
        doc=DOC.read_text(encoding='utf-8')
        for source in ('src/checkers_trusted_routes.py','src/checkers_social_admission.py',
                       'src/checkers_match_authority.py','src/hosted_catalog_looprd.py',
                       'src/discovery_v2.py','extensions/tavi/extension-bridge.mjs',
                       'games/market-grove/looprd.yaml','web/main.mjs'):
            with self.subTest(source=source):
                self.assertTrue((ROOT/source).is_file())
                self.assertIn(source, doc)
        self.assertIn('SourceOnly',text)
        self.assertIn('portal -> hostedProjection \"Request hosted catalog through configured LoopRD endpoint\"',text)
        self.assertIn('Not registered as public LoopRD routes',doc)
        self.assertIn('No Atrium ODPS artifact',doc)
        self.assertNotIn('deployment atrium ',text)
        self.assertIn('not equivalent',doc)

    def test_documented_evidence_paths_are_files(self):
        doc=DOC.read_text(encoding='utf-8')
        refs = set(re.findall(r'`((?:src|web|modules|games|tools|extensions|examples)/[A-Za-z0-9._/-]+)`',doc))
        self.assertGreater(len(refs),25)
        missing=sorted(ref for ref in refs if not (ROOT/ref).exists())
        self.assertEqual(missing,[])


if __name__=='__main__':
    unittest.main()
