import unittest
from src.game_contract import GameEngine, replay
from src.checkers_adapter import CheckersEngine


class GameContractTests(unittest.TestCase):
    def setUp(self):
        self.engine = CheckersEngine()

    def test_adapter_implements_shared_interface(self):
        self.assertIsInstance(self.engine, GameEngine)
        self.assertEqual(self.engine.game_id, 'checkers')

    def test_legal_actions_and_replay_are_deterministic(self):
        state = self.engine.initial_state()
        actions = self.engine.legal_actions(state)
        self.assertTrue(actions)
        after = self.engine.transition(state, actions[0])
        self.assertEqual(after, replay(self.engine, [actions[0]]))
        self.assertEqual(self.engine.deserialize(self.engine.serialize(after)), after)

    def test_staff_action_is_legal(self):
        state = self.engine.initial_state()
        self.assertIn(self.engine.staff_action(state), self.engine.legal_actions(state))

    def test_invalid_state_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.deserialize({'board': [], 'turn': 'r', 'winner': None})

if __name__ == '__main__':
    unittest.main()
