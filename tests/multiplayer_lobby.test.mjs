import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {GameLobbyClient, validateInfo, inspectInternalLifeCapabilities, projectMatch, GAME_PLAY_SCHEMA} from '../src/multiplayer_lobby.mjs';
import {MockLifeAPI} from '../src/mock_life_api.mjs';

const INFO=JSON.parse(readFileSync(new URL('../examples/life.game-play-info.proposed.json',import.meta.url)));
const INTERNAL={schema:GAME_PLAY_SCHEMA,gameId:'life.loop',component:'the-life-loop',operations:['create','invite','join','list_matches','resume'],agentPlaySupported:false,publicPlayApiAvailable:false};

test('strict Atrium contract rejects invented live capabilities and malformed envelopes',()=>{
  assert.equal(validateInfo(INFO).gameId,'life.loop');
  assert.throws(()=>validateInfo({...INFO,url:'https://evil.example'}),/unexpected game info/);
  assert.throws(()=>validateInfo({...INFO,component:'attacker'}),/identity/);
  assert.throws(()=>validateInfo({...INFO,engine:{version:'v1',digest:'not-hash'}}),/engine lock/);
  assert.throws(()=>validateInfo({...INFO,capabilities:{asyncTurns:true,agentPlaySupported:true},operations:INFO.operations.filter(x=>x!=='legal_actions')}),/capability/);
  assert.throws(()=>validateInfo({...INFO,capabilities:{asyncTurns:'yes',agentPlaySupported:false}}),/capabilities/);
  assert.throws(()=>validateInfo({...INFO,operations:[...INFO.operations,'malicious']}),/operations/);
  assert.throws(()=>validateInfo(INTERNAL),/unexpected/);
  assert.deepEqual(inspectInternalLifeCapabilities(INTERNAL),{
    gameId:'life.loop',source:'life-internal-only',liveAvailable:false,agentPlaySupported:false,
    operations:['create','invite','join','list_matches','resume'],reason:'Life has no deployed authenticated /play/info or /play endpoint'
  });
});

test('match projection discards game-injected URLs/hidden secrets and rejects invalid deadlines',()=>{
  const value=projectMatch({matchId:'opaque_123',revision:3,status:'active',yourTurn:true,deadline:'2026-10-18T18:00:00Z',privateData:{token:'stolen'},url:'https://evil.test/'});
  assert.deepEqual(value,{matchId:'opaque_123',revision:3,status:'active',yourTurn:true,deadline:'2026-10-18T18:00:00Z'});
  for (const id of ['../admin','https://example.com/','foo?ticket=x','x y',''])assert.throws(()=>projectMatch({matchId:id,revision:0,status:'waiting',yourTurn:false,deadline:null}),/match ID/);
  for (const d of ['2026-10-18T10:00:00+02:00','2026-02-30T10:00:00Z','not-date',42])assert.throws(()=>projectMatch({matchId:'m1',revision:0,status:'waiting',yourTurn:false,deadline:d}),/deadline/);
  assert.throws(()=>projectMatch({matchId:'m1',revision:0,status:'waiting',yourTurn:true,deadline:null}),/non-active/);
});

test('mock Life allows create / invite / one-use join / resume without browsers or Social',async()=>{
  let now=Date.parse('2026-10-18T16:00:00Z');
  const server=new MockLifeAPI({now:()=>now,seedExample:false});
  const client=new GameLobbyClient((...args)=>server.request(...args));
  assert.deepEqual(await client.listMatches().then(()=>null,e=>e.message).then(x=>x), 'Game lobby contract: discover before performing operations');
  const info=await client.discover();
  assert.equal(info.capabilities.agentPlaySupported,false);
  assert.equal(info.capabilities.asyncTurns,false); // a mock isn't a real game-rule API.
  assert.deepEqual(await client.listMatches(),[]);
  const waiting=await client.create({mode:'private-async',deadlineHours:60});
  assert.equal(waiting.status,'waiting');
  assert.equal(waiting.yourTurn,false);
  const invite=await client.invite(waiting.matchId);
  assert.equal(typeof invite,'string');
  assert.equal((await client.listMatches()).length,1);
  server.useViewer('bob');
  assert.deepEqual(await client.listMatches(),[]); // member filtering is server-owned
  assert.equal((await client.join(invite)).status,'active');
  await assert.rejects(()=>client.join(invite),/invitation unavailable/);
  const bob=await client.resume(waiting.matchId);
  assert.equal(bob.yourTurn,false);
  server.useViewer('alice');
  const alice=await client.resume(waiting.matchId);
  assert.equal(alice.yourTurn,true);
  assert.equal((await client.simulateEndTurn(waiting.matchId,alice.revision)).yourTurn,false);
  await assert.rejects(()=>client.simulateEndTurn(waiting.matchId,alice.revision),/not your turn/);
  server.useViewer('bob');
  const bobTurn=await client.resume(waiting.matchId);
  assert.equal(bobTurn.yourTurn,true);
  now += 60*60*1000;
  assert.equal((await client.simulateEndTurn(waiting.matchId,bobTurn.revision)).deadline,'2026-10-21T05:00:00.000Z');
});

test('preview has a 60h policy and a no-deadline alternative, never a 48h room TTL',async()=>{
  const server=new MockLifeAPI({now:()=>Date.parse('2026-10-18T12:00:00Z'),seedExample:false});
  const client=new GameLobbyClient((...args)=>server.request(...args)); await client.discover();
  const unlimited=await client.create({mode:'private-async',deadlineHours:null});
  assert.equal(unlimited.deadline,null);
  const timed=await client.create({mode:'private-async',deadlineHours:60});
  assert.equal(timed.deadline,'2026-10-21T00:00:00.000Z');
  await assert.rejects(()=>client.create({mode:'private-async',deadlineHours:48}),/unsupported preview settings/);
  await assert.rejects(()=>client.call('resume',{token:'social-session'}),/unsafe operation fields/);
  await assert.rejects(()=>client.call('resume',{url:'https://bad.example'}),/unsafe operation fields/);
  await assert.rejects(()=>client.call('unknown'),/operation not advertised/);
});

test('mock is locally isolated and source includes no credential forwarding or network calls',()=>{
  const source=readFileSync(new URL('../src/mock_life_api.mjs',import.meta.url),'utf8');
  const preview=readFileSync(new URL('../src/multiplayer_preview_ui.mjs',import.meta.url),'utf8');
  const index=readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
  assert.doesNotMatch(source,/\bfetch\s*\(|\bWebSocket\s*\(|localStorage|sessionStorage/);
  assert.doesNotMatch(preview,/\bfetch\s*\(|localStorage|sessionStorage|Bearer |apiKey/);
  assert.match(index,/SANDBOX|Multiplayer lab/i);
  assert.match(index,/No live game sessions/);
});
