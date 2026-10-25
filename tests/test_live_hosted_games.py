"""Operator-trusted LoopRD deployments are first-class Atrium publication authority."""
import json
from contextlib import closing
from unittest.mock import patch
import sqlite3
from pathlib import Path
import tempfile
import unittest
from tools.live_hosted_games import public_snapshot

SHA='c'*40
URL='https://thebigtreeinc.github.io/life/index.html'
API='https://api.example.org/looprd/the-life-loop/v1'

class HostedGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'registry.db'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript('''CREATE TABLE "AtriumTrustedDeployment" ("deploymentId" TEXT,"status" TEXT,"launchOrigins" TEXT,"apiOrigin" TEXT);
            CREATE TABLE "AtriumTrustedInstance" ("deploymentId" TEXT,"component" TEXT,"gameId" TEXT,"publisherId" TEXT,"state" TEXT,"sidecar" TEXT,"sourceProvenance" TEXT,"apiBaseUrl" TEXT);''')
            db.execute('INSERT INTO "AtriumTrustedDeployment" VALUES (?,?,?,?)',
                       ('prod-life','active',json.dumps({'game-web':'https://thebigtreeinc.github.io/life/'}),'https://api.example.org'))
            self.sidecar={'game':{'id':'life.loop','publisher':'thebigtreeinc','title':'The Life Loop',
              'launch':{'mode':'hosted-web','originRef':'game-web','entrypoint':'index.html'}}}
            db.execute('INSERT INTO "AtriumTrustedInstance" VALUES (?,?,?,?,?,?,?,?)',
                       ('prod-life','the-life-loop','life.loop','thebigtreeinc','active',
                        json.dumps(self.sidecar),json.dumps({'kind':'git','revision':SHA}),API))

    def test_trusted_looprd_instance_auto_publishes(self):
        result=public_snapshot(self.db)
        self.assertEqual(result['games'][0]['launchUrl'],URL)
        self.assertEqual(result['games'][0]['sourceRevision'],SHA)
        self.assertEqual(result['games'][0]['approved'],True)
        self.assertEqual(result['games'][0]['status'],'published')

    def test_no_second_approval_document_is_required(self):
        self.assertEqual([x['gameId'] for x in public_snapshot(self.db)['games']],['life.loop'])

    def test_withdrawn_or_disabled_is_removed_automatically(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "state"=?',('withdrawn',))
        self.assertEqual(public_snapshot(self.db)['games'],[])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "state"=?',('active',))
            db.execute('UPDATE "AtriumTrustedDeployment" SET "status"=?',('disabled',))
        self.assertEqual(public_snapshot(self.db)['games'],[])

    def test_new_trusted_game_is_generic_not_life_hardcoded(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            side={'game':{'id':'market.grove','publisher':'thebigtreeinc','title':'Market Grove',
                  'launch':{'mode':'hosted-web','originRef':'atrium-web','entrypoint':'games/market-grove/index.html'}}}
            db.execute('UPDATE "AtriumTrustedDeployment" SET "launchOrigins"=?',
                       (json.dumps({'game-web':'https://thebigtreeinc.github.io/life/','atrium-web':'https://thebigtreeinc.github.io/atrium/'}),))
            db.execute('INSERT INTO "AtriumTrustedInstance" VALUES (?,?,?,?,?,?,?,?)',
                       ('prod-life','market-grove','market.grove','thebigtreeinc','active',json.dumps(side),
                        json.dumps({'kind':'git','revision':'d'*40}),'https://api.example.org/looprd/atrium/market-grove/v1'))
        result=public_snapshot(self.db)
        self.assertEqual([g['gameId'] for g in result['games']],['life.loop','market.grove'])

    def test_non_git_or_unsafe_public_binding_fails_closed(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "sourceProvenance"=?',
                       (json.dumps({'kind':'local','revision':None}),))
        self.assertEqual(public_snapshot(self.db)['games'],[])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "sourceProvenance"=?,"apiBaseUrl"=?',
                       (json.dumps({'kind':'git','revision':SHA}),'https://evil.example.org/looprd/the-life-loop/v1'))
        with self.assertRaises(ValueError): public_snapshot(self.db)

    def test_public_snapshot_closes_sqlite_read_connection(self):
        real_connect = sqlite3.connect; opened=[]
        def track_connect(*args, **kwargs):
            connection=real_connect(*args, **kwargs); opened.append(connection); return connection
        with patch('tools.live_hosted_games.sqlite3.connect', side_effect=track_connect):
            self.assertEqual(len(public_snapshot(self.db)['games']),1)
        with self.assertRaises(sqlite3.ProgrammingError): opened[0].execute('SELECT 1')

if __name__=='__main__': unittest.main()
