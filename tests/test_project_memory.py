"""Project-owned durable knowledge and agent source guards (no provider claims)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ProjectMemoryTests(unittest.TestCase):
    def test_project_record_is_scoped_and_nonauthorizing(self):
        record = json.loads((ROOT/'registry/project-memory.json').read_text(encoding='utf-8'))
        package = json.loads((ROOT/'package.json').read_text(encoding='utf-8'))
        self.assertEqual(record['schema'], 'ziprunner.project-memory/v1')
        self.assertEqual(record['project_key'], 'atrium')
        self.assertEqual(record['owner_project'], 'atrium')
        self.assertEqual(record['version'], package['version'])
        self.assertIsNone(record['canonical_project_id'])
        self.assertEqual(record['publication_status'], 'proposed')
        self.assertEqual(record['source']['source_path'], 'registry/project-memory.json')
        self.assertTrue(record['facts'])
        ids = [f['id'] for f in record['facts']]
        self.assertEqual(len(ids), len(set(ids)))
        for fact in record['facts']:
            self.assertEqual(set(('id','topic','statement','source','observed_at','review_after','status')) - set(fact), set())
            self.assertIn(fact['status'], ('verified','observed','unverified','superseded'))
            self.assertLessEqual(len(fact['statement']),1000)
        blob=(ROOT/'registry/project-memory.json').read_text(encoding='utf-8')
        self.assertNotIn('C:\\Users',blob)
        self.assertNotIn('BEGIN PRIVATE KEY',blob)
    def test_agent_profile_preserves_ownership_and_approval(self):
        root=(ROOT/'AGENTS.md').read_text(encoding='utf-8')
        scoped=(ROOT/'.ziprunner/PROJECT_AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('INSTRUCT.md',root)
        self.assertIn('DESIGN.adoc',root)
        self.assertIn('Manager/QA',root)
        self.assertIn('TaviX',scoped)
        self.assertIn('operator',scoped)
        self.assertIn('`atrium`',scoped)
        self.assertIn('Canonical UUID: **unverified**',scoped)

if __name__ == '__main__': unittest.main()
