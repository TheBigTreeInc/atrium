"""Cross-language match envelope expectations: adapter is mocked, NOT a DAPI activation."""
import copy
import json
import unittest
from pathlib import Path
from src.game_lobby_client import GameLobbyClient, LobbyProtocolError
from src.game_play_contract import validate_game_info, GameContractError

ROOT = Path(__file__).resolve().parents[1]
INFO = json.loads((ROOT / 'examples/life.game-play-info.proposed.json').read_text(encoding='utf8'))
INFO['operations'].insert(1,'invite')

class MultiplayerAdapterTests(unittest.TestCase):
    def test_read_create_invite_join_resume_use_explicit_transport_and_private_projection(self):
        calls=[]
        response={
            'list_matches': {'ok':True,'matches':[{'matchId':'demo_101','revision':0,'status':'active','yourTurn':True,'deadline':None,'secret':'never-pass','url':'https://evil.test'}]},
            'create': {'ok':True,'match':{'matchId':'demo_102','revision':0,'status':'waiting','yourTurn':False,'deadline':None}},
            'invite': {'ok':True,'invitation':'DEMO_INVITE_102'},
            'join': {'ok':True,'match':{'matchId':'demo_102','revision':1,'status':'active','yourTurn':False,'deadline':None}},
            'resume': {'ok':True,'match':{'matchId':'demo_101','revision':0,'status':'active','yourTurn':True,'deadline':None}},
        }
        def transport(method,path,body):
            calls.append((method,path,body))
            if method=='GET':return INFO
            return response[body['op']]
        client=GameLobbyClient(transport,game_id='life.loop',component='the-life-loop')
        client.discover()
        self.assertEqual(client.list_matches()[0]['matchId'],'demo_101')
        self.assertNotIn('secret',client.list_matches()[0]);self.assertNotIn('url',client.list_matches()[0])
        self.assertEqual(client.create()['status'],'waiting')
        self.assertEqual(client.invite('demo_102'),'DEMO_INVITE_102')
        self.assertEqual(client.join('DEMO_INVITE_102')['revision'],1)
        self.assertTrue(client.resume('demo_101')['yourTurn'])
        self.assertIn(('POST','/play',{'schema':'looprd.game-play/v1','op':'create','settings':{'mode':'private-async','deadlineHours':60}}),calls)
        self.assertIn(('POST','/play',{'schema':'looprd.game-play/v1','op':'invite','matchId':'demo_102'}),calls)
    def test_reject_unsafe_refs_and_invented_public_info(self):
        client=GameLobbyClient(lambda *_: INFO,game_id='life.loop',component='the-life-loop');client.discover()
        for match in ('../steal','https://evil.test','id?secret=1'):
            with self.assertRaises(LobbyProtocolError):client.invite(match)
        with self.assertRaises(LobbyProtocolError):client.join('bad')
        with self.assertRaises(LobbyProtocolError):client.create(deadline_hours=48)
        proposed=copy.deepcopy(INFO)
        proposed['url']='https://evil.test'
        with self.assertRaises(GameContractError):validate_game_info(proposed)
        self.assertIn('invite',validate_game_info(INFO)['operations'])
    def test_internal_life_handoff_is_not_deployed_play_contract(self):
        internal={'schema':'looprd.game-play/v1','gameId':'life.loop','component':'the-life-loop','operations':['create','invite','join','list_matches','resume'],'modes':['private-async'],'actionExecution':'server-evaluated','agentPlaySupported':False,'publicPlayApiAvailable':False,'identityRequired':True}
        with self.assertRaises(GameContractError): validate_game_info(internal)

if __name__=='__main__':unittest.main()
