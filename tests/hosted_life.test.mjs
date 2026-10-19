import {test} from 'node:test';
import assert from 'node:assert/strict';
import {approvedLifeTarget, publicLifeTransport, authorizedLifeLobby, launchLife, taviLaunchHandoff} from '../src/hosted_life.mjs';
const catalogEntry={gameId:'life.loop',status:'published',approved:true,publisherId:'thebigtreeinc',deploymentId:'test-cluster',launchUrl:'https://life.example.org/game',apiBaseUrl:'https://api.example.org/looprd/the-life-loop/v1',embedAllowed:false};
const discoveryInstance={gameId:'life.loop',component:'the-life-loop',status:'reviewed',available:true,launchAvailable:true,publisherId:'thebigtreeinc',deploymentId:'test-cluster',launchUrl:catalogEntry.launchUrl,apiBaseUrl:catalogEntry.apiBaseUrl};
test('exact approved deployment and route required',()=>{
 assert.equal(approvedLifeTarget({catalogEntry,discoveryInstance}).gameId,'life.loop');
 for(const update of [{status:'withdrawn'},{launchUrl:'https://evil.example.org/game'},{apiBaseUrl:'https://api.example.org/admin'},{publisherId:'someoneelse'},{launchAvailable:false}]) assert.throws(()=>approvedLifeTarget({catalogEntry,discoveryInstance:{...discoveryInstance,...update}}));
 assert.throws(()=>approvedLifeTarget({catalogEntry:{...catalogEntry,approved:false},discoveryInstance}));
});
test('Life transport requires audience-bound token and never navigates via it',async()=>{
 const target=approvedLifeTarget({catalogEntry,discoveryInstance});const requests=[];
 const transport=publicLifeTransport(target,{identityProvider:async()=>({audience:'life.loop',authorization:'Bearer game-scoped-test-token'}),request:async r=>{requests.push(r);return {ok:true};}});
 await transport('GET','/play/info',null);
 assert.equal(requests[0].url,'https://api.example.org/looprd/the-life-loop/v1/play/info');
 assert.equal(requests[0].credentials,'omit');assert.equal(requests[0].redirect,'error');
 assert.ok(!requests[0].url.includes('token'));
 await assert.rejects(()=>publicLifeTransport(target,{identityProvider:async()=>({audience:'tavi-social',authorization:'Bearer social-token'}),request:async()=>({})})('POST','/play',{schema:'looprd.game-play/v1',op:'resume',matchId:'m_1'}));
 await assert.rejects(()=>transport('POST','/matches/seat',{seat:'other'}));
});
test('internal-only Life capabilities cannot authorize live lobby',async()=>{
 const target=approvedLifeTarget({catalogEntry,discoveryInstance});
 await assert.rejects(()=>authorizedLifeLobby(target,{identityProvider:async()=>({audience:'life.loop',authorization:'Bearer game'}),request:async()=>({schema:'looprd.game-play/v1',gameId:'life.loop',component:'the-life-loop',publicPlayApiAvailable:false,agentPlaySupported:false,operations:['resume']})}));
});
test('resume launch is opaque and external by default; no challenge-created match',()=>{
 const target=approvedLifeTarget({catalogEntry,discoveryInstance});const opened=[];
 const launch=launchLife(target,'match_123',{openExternal:u=>opened.push(u),embed:()=>assert.fail('iframe should not be used'),allowEmbed:true});
 assert.deepEqual(opened,[launch.url]);assert.deepEqual(taviLaunchHandoff(launch),{schema:'atrium.tavi-launch/v1',gameId:'life.loop',target:'https://life.example.org/game',matchContext:{matchId:'match_123'}});
 assert.ok(!JSON.stringify(launch).includes('authorization'));
 assert.throws(()=>launchLife(target,'../../steal',{openExternal:()=>{}}));
});
test('Life 0.5.95 public info is reachable without a game bearer; POST requires it',async()=>{
 const target=approvedLifeTarget({catalogEntry,discoveryInstance});const records=[];
 const info={protocol:'looprd.game-play/v1',gameId:'life.loop',component:'the-life-loop',engine:{version:'0.5.95',digest:'a'.repeat(64)},operations:['create','invite','join','list_matches','resume','get','legal_actions','act','end_turn'],capabilities:{asyncTurns:true,agentPlaySupported:false}};
 const client=await authorizedLifeLobby(target,{identityProvider:async()=>({audience:'life.loop',authorization:'Bearer game-scoped'}),request:async req=>{records.push(req);if(req.method==='GET')return info;return {ok:true,schema:'looprd.game-play/v1',result:{matchId:'life_123'},match:{matchId:'life_123',revision:0,status:'active',yourTurn:true,deadline:null}}}});
 assert.equal(records[0].authorization,undefined);
 await assert.rejects(()=>client.create({mode:'private-async',deadlineHours:60,ruleset:'classic'}),/stable requestId/);
 const match=await client.create({mode:'private-async',deadlineHours:60,ruleset:'classic'},'challenge_abc_create');
 assert.equal(match.matchId,'life_123');assert.equal(records[1].body.requestId,'challenge_abc_create');
 assert.equal(records[1].authorization,'Bearer game-scoped');
});
test('Life gateway errors are never treated as valid lobby replies',async()=>{
 const target=approvedLifeTarget({catalogEntry,discoveryInstance});
 const transport=publicLifeTransport(target,{identityProvider:async()=>({audience:'life.loop',authorization:'Bearer game'}),request:async()=>({status:403,detail:{code:'wrong_seat'}})});
 await assert.rejects(()=>transport('POST','/play',{op:'resume'}),e=>e.status===403 && e.gameError.code==='wrong_seat');
});
