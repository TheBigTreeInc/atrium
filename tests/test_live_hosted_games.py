"""Durable, private operator approval cannot be replaced by a DAPI discovery ack."""
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
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'registry.db'
        self.approval=Path(self.temp.name)/'review.json'
        self.review={'schema':'atrium.hosted-life-approval/v1','gameId':'life.loop',
          'publisherId':'thebigtreeinc','deploymentId':'prod-life','component':'the-life-loop',
          'sourceRevision':SHA,'pagesWorkflowRunId':123456789,'launchUrl':URL,'apiBaseUrl':API,
          'approvedBy':'operator-review','approvedAt':'2026-10-20T00:00:00Z','embedAllowed':False}
        self.approval.write_text(json.dumps(self.review), encoding='utf-8')
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

    def test_reviewed_live_instance_publication(self):
        result=public_snapshot(self.db,self.approval)
        self.assertEqual(result['games'][0]['launchUrl'],URL)
        self.assertEqual(result['games'][0]['sourceRevision'],SHA)
        self.assertEqual(result['games'][0]['approved'],True)
        self.assertNotIn('pagesWorkflowRunId',result['games'][0])

    def test_discovery_alone_not_a_publication(self):
        self.approval.unlink()
        with self.assertRaises(FileNotFoundError):public_snapshot(self.db,self.approval)

    def test_revision_drift_withdrawn_and_url_change_fail_closed(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "sourceProvenance"=?',
                       (json.dumps({'kind':'git','revision':'e'*40}),))
        self.assertEqual(public_snapshot(self.db,self.approval)['games'],[])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "sourceProvenance"=?,"state"=?',
                       (json.dumps({'kind':'git','revision':SHA}),'withdrawn'))
        self.assertEqual(public_snapshot(self.db,self.approval)['games'],[])
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE "AtriumTrustedInstance" SET "state"=?',('active',))
            db.execute('UPDATE "AtriumTrustedDeployment" SET "launchOrigins"=?',
                       (json.dumps({'game-web':'https://life.example.org/'}),))
        self.assertEqual(public_snapshot(self.db,self.approval)['games'],[])

    def test_public_snapshot_closes_sqlite_read_connection(self):
        """Windows can remove temp SQLite files only after the handle is closed."""
        real_connect = sqlite3.connect
        opened = []

        def track_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            opened.append(connection)
            return connection

        with patch('tools.live_hosted_games.sqlite3.connect', side_effect=track_connect):
            self.assertEqual(len(public_snapshot(self.db, self.approval)['games']), 1)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute('SELECT 1')

    def test_malformed_approval_refused(self):
        self.review['sourceRevision']='main'
        self.approval.write_text(json.dumps(self.review), encoding='utf-8')
        with self.assertRaises(ValueError):public_snapshot(self.db,self.approval)

if __name__=='__main__':unittest.main()
