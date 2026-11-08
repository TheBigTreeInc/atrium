"""No live TaviX access, package approval or installing in these source tests."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.tavix_marketplace_projection import project_tavix_games

ROOT = Path(__file__).resolve().parents[1]


def repo():
    return {'schema':'tavi.repository/v1','name':'Operator-approved local fixture','extensions':[
      {'manifest':{'schema':'tavi.extension/v1','kind':'app','id':'org.example.klondike',
        'version':'0.1.1','name':'Klondike','summary':'Solo card game',
        'publisher':'example','classification':{'type':'game','categories':['cards','solitaire']},
        'platforms':['windows','android']},'entrypoint':'https://test.example/klondike'},
      {'manifest':{'schema':'tavi.extension/v1','kind':'app','id':'org.example.notepad',
        'version':'1.0.0','name':'Notepad','summary':'App','publisher':'example',
        'platforms':['web'],'classification':{'type':'app'}},'entrypoint':'https://test.example/notepad'}]}


def source(data):
    raw = json.dumps(data, separators=(',', ':'), sort_keys=True).encode()
    return raw, hashlib.sha256(raw).hexdigest()


class TavixMarketplaceProjectionTests(unittest.TestCase):
    def test_only_classified_games_no_executable_package_urls(self):
        raw, pin = source(repo())
        result = project_tavix_games(raw, pin)
        self.assertEqual(result['sourceIndexSha256'],pin)
        self.assertEqual(result['schema'],'atrium.tavix-games/v1')
        self.assertEqual(len(result['games']),1)
        game = result['games'][0]
        self.assertEqual(game['id'],'org.example.klondike')
        self.assertEqual(game['categories'],['cards','solitaire'])
        self.assertTrue({'name','publisher','version','platforms','summary'} <= set(game))
        self.assertFalse({'entrypoint','download','source','approved','sha256','permissions'} & set(game))

    def test_presentation_cannot_mutate_trust_or_permissions(self):
        raw, pin = source(repo())
        metadata={'schema':'atrium.tavix-presentation/v1','games':{'org.example.klondike':{
            'description':'An offline solitaire classic','collections':['family'], 'featured':True}}}
        game=project_tavix_games(raw,pin,metadata)['games'][0]
        self.assertEqual((game['description'],game['collections'],game['featured']),
                         ('An offline solitaire classic',['family'],True))
        for forbidden in ['downloadUrl','approved','version','permissions','id']:
            patch={'schema':metadata['schema'],'games':{'org.example.klondike':{forbidden:True}}}
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                project_tavix_games(raw,pin,patch)
        with self.assertRaisesRegex(ValueError,'absent or unclassified'):
            project_tavix_games(raw,pin,{'schema':metadata['schema'],'games':{'org.example.notepad':{}}})

    def test_pin_rejects_changed_index_and_potentially_unsafe_games(self):
        raw, pin=source(repo())
        with self.assertRaisesRegex(ValueError,'pin mismatch'):
            project_tavix_games(raw+b' ',pin)
        with self.assertRaisesRegex(ValueError,'approved'):
            project_tavix_games(raw,'')
        for edit in ['duplicate','unclassified','badcategories','badplatforms']:
            r=repo()
            if edit=='duplicate':r['extensions'].append(r['extensions'][0])
            if edit=='unclassified':r['extensions'][0]['manifest']['classification']={'type':'app'}
            if edit=='badcategories':r['extensions'][0]['manifest']['classification']['categories']=['cards','cards']
            if edit=='badplatforms':r['extensions'][0]['manifest']['platforms']=['linux']
            changed, changedpin=source(r)
            if edit=='unclassified':
                self.assertEqual(project_tavix_games(changed,changedpin)['games'],[])
            else:
                with self.subTest(edit=edit),self.assertRaises(ValueError):
                    project_tavix_games(changed,changedpin)

    def test_cli_does_not_replace_existing_catalog_on_failed_pin(self):
        raw,pin=source(repo())
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'index.json';src.write_bytes(raw)
            output=root/'catalog.json';output.write_text('previous review\n', encoding='utf-8')
            cmd=[sys.executable,str(ROOT/'tools/project_tavix_marketplace.py'),'--index',str(src),
                 '--approved-sha256','0'*64,'--output',str(output)]
            invalid=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(invalid.returncode,0)
            self.assertEqual(output.read_text(encoding='utf-8'),'previous review\n')
            cmd[cmd.index('0'*64)]=pin
            good=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['games'][0]['id'],'org.example.klondike')


if __name__=='__main__':unittest.main()
