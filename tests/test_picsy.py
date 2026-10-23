import math
import unittest
from app.picsy import contribution, demo_three_person, natural_recovery, transaction, virtual_bank


class TestPicsy(unittest.TestCase):
    def setUp(self):
        self.e = [[.8,.2,0],[0,.7,.3],[.2,0,.8]]

    def test_virtual_bank(self):
        p=virtual_bank(self.e)
        self.assertTrue(all(abs(sum(row)-1)<1e-10 for row in p))
        self.assertTrue(all(p[i][i]==0 for i in range(3)))

    def test_contribution(self):
        p=virtual_bank(self.e);c=contribution(self.e)
        self.assertAlmostEqual(sum(c),3.0)
        for j in range(3):self.assertAlmostEqual(sum(c[i]*p[i][j] for i in range(3)),c[j],places=8)

    def test_budget_conservation(self):
        b=transaction(self.e,2,1,.15)
        self.assertAlmostEqual(b[2][2],.65)
        self.assertAlmostEqual(b[2][1],.15)
        self.assertTrue(all(abs(sum(row)-1)<1e-10 for row in b))

    def test_recovery(self):
        r=natural_recovery(self.e,.1)
        self.assertAlmostEqual(r[0][0],.82)
        self.assertAlmostEqual(r[0][1],.18)
        self.assertEqual(len(contribution(r)),3)

    def test_reject_invalid(self):
        with self.assertRaises(ValueError):transaction(self.e,0,1,.9)
        with self.assertRaises(ValueError):virtual_bank([[1,1],[0,1]])
        with self.assertRaises(ValueError):natural_recovery(self.e,2)
        with self.assertRaises(ValueError):virtual_bank([[float("nan"), .5],[.5,.5]])
        with self.assertRaises(ValueError):transaction(self.e,0,1,float("nan"))

    def test_example_changes(self):
        d=demo_three_person()
        self.assertTrue(any(abs(a-b)>1e-7 for a,b in zip(d['before']['c'],d['after']['c'])))


if __name__=='__main__': unittest.main()
