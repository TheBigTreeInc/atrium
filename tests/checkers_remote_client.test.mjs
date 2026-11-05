import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {CheckersRemoteClient,CheckersRemoteError,sameOriginMatchTransport} from '../src/checkers_remote_client.mjs';

const initial = ['.r.r.r.r','r.r.r.r.','.r.r.r.r','........','........','b.b.b.b.','.b.b.b.b','b.b.b.b.'];
const snapshot = revision => ({matchId:'match-one',revision,state:{board:initial,turn:revision%2?'b':'r',winner:null},status:'active'});
const actions = revision => ({protocol:'atrium.checkers.actions/v1',matchId:'match-one',revision,seat:'red',turn:'r',actions:[[[2,1],[3,0]]]});
const client = (transport,requestIdFactory=()=> 'req-one')=>new CheckersRemoteClient({transport,matchId:'match-one',requestIdFactory});

const gateway = () => {
  let revision=0, calls=[];
  const replies = new Map();
  const transport = async request => {
    calls.push(structuredClone(request));
    if (request.path.endsWith('/join')) return {status:200,body:{seat:'red',match:snapshot(revision)}};
    if (request.path.endsWith('/legal-actions')) return {status:200,body:actions(revision)};
    if (request.method==='GET') return {status:200,body:snapshot(revision)};
    if (request.path.endsWith('/moves')) {
      const {revision:r,requestId,path} = request.body;
      if (replies.has(requestId)) return {status:200,body:replies.get(requestId)};
      if (r!==revision) return {status:409,body:{error:'stale_revision'}};
      if (JSON.stringify(path)!==JSON.stringify([[2,1],[3,0]]))return {status:422,body:{error:'illegal_move'}};
      revision++;
      replies.set(requestId,snapshot(revision));
      return {status:200,body:snapshot(revision)};
    }
    return {status:404,body:{error:'not_found'}};
  };
  return {transport,calls,advance(){revision++}};
};

test('two separate thin clients observe authoritative revisions; no local move evaluation',async()=>{
  const server=gateway();
  const red=client(server.transport,()=> 'request-red');
  const black=client(server.transport,()=> 'request-black');
  assert.deepEqual((await red.join()).match,snapshot(0));
  assert.deepEqual((await black.join()).match,snapshot(0));
  const legal=await red.legalActions();
  assert.equal(legal.actions.length,1);
  legal.actions[0][0][0]=7;
  const moved=await red.move([[2,1],[3,0]]);
  assert.equal(moved.revision,1);
  assert.equal((await black.refresh()).revision,1);
  assert.equal(server.calls.at(-1).path,'/games/checkers/matches/match-one');
  assert.deepEqual(Object.keys(server.calls.find(c=>c.path.endsWith('/moves')).body).sort(),['path','requestId','revision']);
  assert.ok(!server.calls.some(c=>JSON.stringify(c).includes('user-red')));
});

test('after uncertain network delivery, retry uses identical request ID and payload',async()=>{
  const server=gateway();let missed=false;
  const transport=async req=>{
    const result=await server.transport(req);
    if (req.path.endsWith('/moves') && !missed){missed=true;throw new Error('lost TCP response');}
    return result;
  };
  const red=client(transport);await red.join();
  await assert.rejects(red.move([[2,1],[3,0]]),/lost TCP response/);
  assert.equal(red.pending.requestId,'req-one');
  assert.equal((await red.retryPending()).revision,1);
  assert.equal(red.pending,null);
  const attempts=server.calls.filter(x=>x.path.endsWith('/moves'));
  assert.equal(attempts.length,2);assert.deepEqual(attempts[0].body,attempts[1].body);
});

test('stale conflict clears pending, preserves last good state and permits resync',async()=>{
  const server=gateway();const red=client(server.transport);await red.join();server.advance();
  await assert.rejects(red.move([[2,1],[3,0]]),e=>e.code==='stale_revision'&&e.status===409);
  assert.equal(red.pending,null);assert.equal(red.snapshot.revision,0);
  assert.equal((await red.refresh()).revision,1);
});

test('IDs and response structure fail closed; stale legal-actions requires refresh',async()=>{
  assert.throws(()=>new CheckersRemoteClient({transport:()=>{},matchId:'../admin'}),/invalid_match_id/);
  const broken=client(async()=>({status:200,body:{matchId:'match-one',revision:0,state:{}}}));
  await assert.rejects(broken.join(),e=>e.code==='invalid_seat_response');
  const server=gateway();const red=client(server.transport);await red.join();server.advance();
  await assert.rejects(red.legalActions(),e=>e.code==='state_changed'&&e.status===409);
  assert.equal(red.snapshot.revision,1);
});

test('same-origin adapter sends only relative path, no identity, and no redirects',async()=>{
  const requests=[];
  const fetchFn=async(path,opt)=>{
    requests.push({path,opt});
    return {status:200,headers:{get:()=> 'application/json; charset=utf-8'},json:async()=>snapshot(0)};
  };
  const transport=sameOriginMatchTransport(fetchFn);
  const red=client(transport);
  assert.equal((await red.refresh()).revision,0);
  assert.equal(requests[0].path,'/games/checkers/matches/match-one');
  assert.equal(requests[0].opt.credentials,'same-origin');
  assert.equal(requests[0].opt.redirect,'error');
  assert.equal(requests[0].opt.cache,'no-store');
  assert.equal(Object.keys(requests[0].opt.headers).join(','),'Accept');
  await assert.rejects(transport({method:'GET',path:'/games/checkers/matches/../admin'}),/invalid_match_path/);
});

test('browser match client contains no rules engine, Tavi session token, or local persistent authority',()=>{
  const src=readFileSync(new URL('../src/checkers_remote_client.mjs', import.meta.url),'utf8');
  assert.doesNotMatch(src,/\b(legalMoves|applyMove|initialBoard|localStorage|sessionStorage|Authorization|Bearer)\b/);
  assert.match(src,/trusted_transport_required/);
});
