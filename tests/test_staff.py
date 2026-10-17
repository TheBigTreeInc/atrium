import unittest
from src.staff import Table,StaffPolicy,plan_staff,staff_public_profile
class StaffTests(unittest.TestCase):
 def test_only_selected_tables(self):
  ts=[Table('a',2,1,allow_staff=True),Table('b',2,0,allow_staff=True),Table('c',2,1,allow_staff=False),Table('d',2,1,allow_staff=True,ranked=True)]
  self.assertEqual(plan_staff(ts,StaffPolicy('when_human_waiting',max_staff_tables=1)),{'a':1})
 def test_demonstration_occupies_bounded_subset(self):
  ts=[Table('a',2,0,allow_staff=True),Table('b',2,0,allow_staff=True),Table('c',2,0,allow_staff=True)]
  self.assertEqual(plan_staff(ts,StaffPolicy('demonstration',max_staff_tables=1)),{'a':1})
 def test_empty_is_default(self):
  self.assertEqual(plan_staff([Table('a',2,1,allow_staff=True)],StaffPolicy()),{})
 def test_no_fake_social_or_administration(self):
  p=staff_public_profile('staff:checkers-001','Willow')
  self.assertEqual(p['label'],'Staff');self.assertTrue(p['computerControlled'])
  self.assertFalse(p['canFriend']);self.assertFalse(p['canMessage']);self.assertFalse(p['isModerator'])
 def test_no_staff_in_ranked_even_demonstration(self):
  self.assertEqual(plan_staff([Table('a',2,1,allow_staff=True,ranked=True)],StaffPolicy('demonstration')),{})
 def test_invalid_occupancy_rejected(self):
  with self.assertRaises(ValueError):plan_staff([Table('a',2,5,allow_staff=True)],StaffPolicy('demonstration'))
if __name__=='__main__':unittest.main()
