"""Manifest and documentation contracts must remain aligned with the canonical validator."""
import json
import unittest
from pathlib import Path
import yaml
from src.catalog import VERSION, APP_ID, PUBLISHER_ID, FIELDS, PERMISSIONS, ALLOWED_KINDS
from tools.check_specs import ROOT


class RegistryContractTests(unittest.TestCase):
    def test_manifest_json_schema_matches_runtime(self):
        contract = json.loads((ROOT/'schemas/atrium-app-v1.schema.json').read_text(encoding='utf-8'))
        assert contract['additionalProperties'] is False
        assert set(contract['properties']) == FIELDS
        assert set(contract['required']) == FIELDS - {'permissions'}
        assert set(contract['properties']['kind']['enum']) == ALLOWED_KINDS
        assert set(contract['properties']['permissions']['items']['enum']) == PERMISSIONS
        assert contract['properties']['version']['pattern'] == VERSION.pattern
        assert contract['properties']['id']['pattern'] == APP_ID.pattern
        assert contract['properties']['publisher']['pattern'] == PUBLISHER_ID.pattern

    def test_openapi_matches_reviewed_routes(self):
        documented = yaml.safe_load((ROOT/'openapi.yaml').read_text(encoding='utf-8'))
        composed = yaml.safe_load((ROOT/'modules/registry/looprd.yaml').read_text(encoding='utf-8'))
        routes = {(h['path'], h.get('method','GET').lower()) for h in composed['handlers']}
        for path, methods in documented['paths'].items():
            for method in methods:
                assert (path, method) in routes, (path, method)

    def test_generated_registry_source_does_not_import_local_modules(self):
        composed = yaml.safe_load((ROOT/'modules/registry/looprd.yaml').read_text(encoding='utf-8'))
        for handler in composed['handlers']:
            if handler.get('kind') == 'python':
                assert 'from src.' not in handler['source']
                assert 'from .catalog' not in handler['source']
                compile(handler['source'], '<generated-registry>', 'exec')


if __name__ == '__main__':
    unittest.main()
