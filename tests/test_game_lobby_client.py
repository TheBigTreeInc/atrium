import json
import unittest
from pathlib import Path
from src.game_lobby_client import GameLobbyClient, LobbyProtocolError

ROOT = Path(__file__).resolve().parents[1]
INFO = json.loads((ROOT/'examples/life.game-play-info.proposed.json').read_text(encoding='utf-8'))

class LobbyClientTests(unittest.TestCase):
    def client(self, response):
        calls=[]
        def transport(method, path, body):
            calls.append((method,path,body))
            return INFO if path == '/play/info' else response
        c=GameLobbyClient(transport, game_id='life.loop', component='the-life-loop')
        c.discover()
        return c,calls

    def test_lobby_projection_and_request(self):
        c,calls=self.client({'ok':True,'matches':[{'matchId':'opaque-1','revision':3,'status':'active','yourTurn':True,'deadline':None,'secret':'do-not-leak','url':'https://evil.test'}]})
        self.assertEqual(c.list_matches(),[{'matchId':'opaque-1','revision':3,'status':'active','yourTurn':True,'deadline':None}])
        self.assertEqual(calls[-1],('POST','/play',{'schema':'looprd.game-play/v1','op':'list_matches'}))

    def test_rejects_duplicate(self):
        m={'matchId':'m','revision':0,'status':'waiting','yourTurn':False,'deadline':None}
        c,_=self.client({'ok':True,'matches':[m,m]})
        with self.assertRaises(LobbyProtocolError): c.list_matches()

    def test_rejects_invalid_deadline(self):
        c,_=self.client({'ok':True,'matches':[{'matchId':'m','revision':1,'status':'active','yourTurn':True,'deadline':'2026-10-18T01:00:00+02:00'}]})
        with self.assertRaises(LobbyProtocolError): c.list_matches()

    def test_rejects_failed_response(self):
        c,_=self.client({'ok':False,'matches':[]})
        with self.assertRaises(LobbyProtocolError): c.list_matches()

    def test_discover_required(self):
        c=GameLobbyClient(lambda *_: None,game_id='life.loop',component='the-life-loop')
        with self.assertRaises(LobbyProtocolError): c.list_matches()

    def test_rejects_unbounded_listing(self):
        c,_=self.client({'ok':True,'matches':[{}]*101})
        with self.assertRaises(LobbyProtocolError): c.list_matches()
