"""Ensure the approved architecture survives future source passes."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PlatformArchitectureTests(unittest.TestCase):
    def test_same_social_account_and_tavi_chat_only(self):
        s = (ROOT / 'docs/PLATFORM_ACCESS_AND_INSTALLATION.adoc').read_text(encoding='utf-8')
        for phrase in ('one authority for user registration', 'does not need Tavi open',
                       'Tavi* is principally the Social chat/messenger client',
                       'issuer+subject', 'single-use', 'no reusable Social bearer'):
            self.assertIn(phrase, s)

    def test_github_pages_backend_is_looprd_and_installer_is_platform_aware(self):
        s = (ROOT / 'docs/PLATFORM_ACCESS_AND_INSTALLATION.adoc').read_text(encoding='utf-8')
        for phrase in ('GitHub Pages static hosting', 'static host, not a backend',
                       'Only compatible platform is offered', 'mobile',
                       'loopback-only', 'PWA'):
            self.assertIn(phrase, s)

    def test_design_sources_link_canonical_architecture(self):
        for name in ('DESIGN.adoc', 'PROJECT_PLAN.adoc', 'docs/ARCHITECTURE.adoc', 'docs/ROADMAP.adoc'):
            self.assertIn('docs/PLATFORM_ACCESS_AND_INSTALLATION.adoc', (ROOT/name).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
