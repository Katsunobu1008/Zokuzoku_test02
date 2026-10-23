import os
import tempfile
import unittest
from app.store import DomainError, Store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(os.path.join(self.tmp.name,'test.sqlite'))

    def tearDown(self):self.tmp.cleanup()

    def test_seed_and_persistence(self):
        d=self.store.list_ideas('a')
        self.assertEqual(len(d['ideas']),100)
        self.assertEqual(len(self.store.list_ideas('b')['ideas']),100)
        self.assertEqual(len(Store(os.path.join(self.tmp.name,'test.sqlite')).list_ideas()['ideas']),100)

    def test_create_lineage_and_like(self):
        idea=self.store.create_idea('a',{'title':'青いライト','prompt':'海のように光るオリジナルのインテリア','parent_id':'seed-000','rights':'original'})
        self.assertEqual(idea['generation'],1)
        self.assertEqual(len(self.store.list_ideas()['ideas']),101)
        self.assertTrue(self.store.like('b',idea['id'])['liked'])
        self.assertFalse(self.store.like('b',idea['id'])['liked'])

    def test_support_is_intent_not_money(self):
        result=self.store.pledge('a','seed-001',50)
        self.assertFalse(result['charged'])
        self.assertEqual(result['status'],'intent_recorded')
        self.store.pledge('a','seed-001',100)
        row=next(i for i in self.store.list_ideas('a')['ideas'] if i['id']=='seed-001')
        self.assertEqual(row['support_points'],100)
        with self.assertRaises(DomainError):self.store.pledge('a','seed-001',-50)

    def test_rights_and_invalid_parent(self):
        data={'title':'作品A','prompt':'個人的なオリジナル作品の発想です','rights':'licensed'}
        with self.assertRaises(DomainError):self.store.create_idea('a',data)
        data['rights']='original';data['parent_id']='missing'
        with self.assertRaises(DomainError):self.store.create_idea('a',data)

    def test_comments(self):
        self.store.comment('a','seed-010','すてきなアイデア')
        self.assertEqual(self.store.comments('seed-010')[0]['body'],'すてきなアイデア')

if __name__=='__main__':unittest.main()
