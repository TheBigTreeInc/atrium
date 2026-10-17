import copy
import json
import unittest
from pathlib import Path
from src.game_play_contract import GameContractError, validate_game_info

ROOT = Path(__file__).resolve().parents[1]
class GamePlayContractTests(unittest.TestCase):
    def setUp(self):
        self.info = json.loads((ROOT/'examples/life.game-play-info.proposed.json').read_text(encoding='utf-8'))
    def test_valid_proposed_fixture(self):
        self.assertEqual(validate_game_info(self.info, expected_game_id='life.loop', expected_component='the-life-loop'), self.info)
    def test_reject_wrong_component(self):
        with self.assertRaises(GameContractError): validate_game_info(self.info, expected_component='other')
    def test_reject_unverified_protocol(self):
        self.info['protocol'] = 'looprd.game-play/v2'
        with self.assertRaises(GameContractError): validate_game_info(self.info)
    def test_agent_requires_headless_operations(self):
        self.info['capabilities']['agentPlaySupported'] = True
        self.info['operations'].remove('legal_actions')
        with self.assertRaises(GameContractError): validate_game_info(self.info)
    def test_no_extra_untrusted_fields(self):
        self.info['url'] = 'https://bad.example'
        with self.assertRaises(GameContractError): validate_game_info(self.info)
    def test_engine_lock_is_required(self):
        self.info['engine']['digest'] = 'unverified'
        with self.assertRaises(GameContractError): validate_game_info(self.info)
    def test_capabilities_must_be_bools(self):
        self.info['capabilities']['asyncTurns'] = 'true'
        with self.assertRaises(GameContractError): validate_game_info(self.info)
