import unittest
from src.checkers import initial_board,legal_moves,apply_move,staff_move

def b(*entries):
 rows=[list('........') for _ in range(8)]
 for (r,c,p) in entries:rows[r][c]=p
 return [''.join(row) for row in rows]
class CheckersTest(unittest.TestCase):
 def test_start_has_seven_moves(self):
  self.assertEqual(len(legal_moves(initial_board(),'r')),7)
 def test_legal_move_updates_state(self):
  board=initial_board();state=apply_move(board,'r',legal_moves(board,'r')[0]);self.assertEqual(state['turn'],'b')
 def test_capture_forced(self):
  board=b((2,1,'r'),(3,2,'b'),(5,6,'b'))
  self.assertEqual(legal_moves(board,'r'),[[[2,1],[4,3]]])
  with self.assertRaises(ValueError):apply_move(board,'r',[[2,1],[3,0]])
 def test_chain_jump_mandatory(self):
  board=b((1,0,'r'),(2,1,'b'),(4,3,'b'),(7,6,'b'))
  moves=legal_moves(board,'r');self.assertEqual(moves,[[[1,0],[3,2],[5,4]]])
  with self.assertRaises(ValueError):apply_move(board,'r',[[1,0],[3,2]])
 def test_crown_ends_turn(self):
  board=b((5,0,'r'),(6,1,'b'),(6,3,'b'))
  state=apply_move(board,'r',[[5,0],[7,2]])
  self.assertEqual(state['board'][7][2],'R')
 def test_staff_is_deterministic(self):
  board=initial_board();self.assertEqual(staff_move(board,'r'),staff_move(board,'r'))
 def test_invalid_board_rejected(self):
  with self.assertRaises(ValueError):legal_moves(['xxx'],'r')
 def test_stale_spec_guard(self):
  import subprocess,sys
  r=subprocess.run([sys.executable,'tools/build_spec.py','--check'],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main()
