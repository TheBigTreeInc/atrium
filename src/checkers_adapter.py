"""Checkers implementation of reusable pure engine contract, kept out of DAPI globals."""
from copy import deepcopy
from src import checkers


class CheckersEngine:
    game_id = 'checkers'
    ruleset = 'american-checkers/v1'

    def initial_state(self):
        return {'board': checkers.initial_board(), 'turn': 'r', 'winner': None}

    def deserialize(self, document):
        if not isinstance(document, dict) or set(document) != {'board', 'turn', 'winner'}:
            raise ValueError('invalid checkers state envelope')
        board = document['board']
        checkers.validate_board(board)
        if document['turn'] not in ('r', 'b', None):
            raise ValueError('invalid turn')
        if document['winner'] not in ('r', 'b', None):
            raise ValueError('invalid winner')
        if (document['winner'] is None) == (document['turn'] is None):
            raise ValueError('game must have either an active turn or a winner')
        return deepcopy(document)

    def serialize(self, state):
        return self.deserialize(state)

    def legal_actions(self, state):
        state = self.deserialize(state)
        return [] if state['winner'] else checkers.legal_moves(state['board'], state['turn'])

    def staff_action(self, state):
        state = self.deserialize(state)
        return None if state['winner'] else checkers.staff_move(state['board'], state['turn'])

    def transition(self, state, action):
        state = self.deserialize(state)
        if state['winner']:
            raise ValueError('match already completed')
        return checkers.apply_move(state['board'], state['turn'], action)

    def outcome(self, state):
        state = self.deserialize(state)
        return {'finished': state['winner'] is not None, 'winner': state['winner']}
