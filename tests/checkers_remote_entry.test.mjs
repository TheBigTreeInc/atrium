import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHostedCheckersPlayer} from '../src/checkers_remote_entry.mjs';

class Element {
  constructor(doc,tag){this.ownerDocument=doc;this.tagName=tag;this.children=[];this.handlers={};this.attributes={};this.textContent='';this.disabled=false;this.value='';this.classList={add:()=>{}};}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  addEventListener(name,fn){this.handlers[name]=fn;}
  setAttribute(name,val){this.attributes[name]=val;}
}
function setup({fetchFn,requestIdFactory}={}) {
  const doc={hidden:false,createElement(tag){return new Element(doc,tag);}};
  const root=new Element(doc,'main');
  let poll=null,stopped=[];
  const app=createHostedCheckersPlayer(root,{fetchFn,requestIdFactory,setIntervalFn(fn,ms){poll={fn,ms};return 1;},clearIntervalFn(token){stopped.push(token);poll=null;}});
  return {root,doc,app,get poll(){return poll;},stopped};
}
const board=['.r.r.r.r','r.r.r.r.','.r.r.r.r','........','........','b.b.b.b.','.b.b.b.b','b.b.b.b.'];
function sampleFetch({deny=false}={}){
  const history=[];let revision=0;
  const respond=(status,body)=>({status,headers:{get:()=> 'application/json'},json:async()=>body});
  const fn=async(path,options)=>{
    history.push({path,options});
    if(deny)return respond(401,{error:'unauthorized'});
    const base='/games/checkers/matches/match-123';
    if(path===base+'/join'&&options.method==='POST')return respond(200,{seat:'red',match:{matchId:'match-123',revision,state:{board,turn:'r',winner:null},status:'active'}});
    if(path===base+'/legal-actions')return respond(200,{protocol:'atrium.checkers.actions/v1',matchId:'match-123',revision,seat:'red',actions:revision===0?[[[2,1],[3,0]]]:[]});
    if(path===base&&options.method==='GET')return respond(200,{matchId:'match-123',revision,state:{board,turn:revision?'b':'r',winner:null},status:'active'});
    if(path===base+'/moves'&&options.method==='POST'){
      const payload=JSON.parse(options.body);
      if(payload.revision!==revision)return respond(409,{error:'stale_revision'});
      revision++;
      return respond(200,{matchId:'match-123',revision,state:{board,turn:'b',winner:null},status:'active'});
    }
    return respond(404,{error:'not_found'});
  };
  return {fn,history};
}

test('hosted board joins a verified same-origin match and sends server-authorized moves', async()=>{
  const server=sampleFetch();const demo=setup({fetchFn:server.fn,requestIdFactory:()=> 'move-123'});
  assert.equal(await demo.app.launch('match-123'),true);
  assert.equal(demo.root.children[3].children[1].children.length,64);
  assert.equal(demo.poll.ms,4000);
  assert.deepEqual(server.history.map(x=>x.path),[
    '/games/checkers/matches/match-123/join','/games/checkers/matches/match-123/legal-actions']);
  const squares=demo.root.children[3].children[1].children;
  await squares[17].handlers.click();await squares[24].handlers.click();
  const move=server.history.find(x=>x.path.endsWith('/moves'));
  assert.deepEqual(JSON.parse(move.options.body),{revision:0,requestId:'move-123',path:[[2,1],[3,0]]});
  assert.equal(move.options.credentials,'same-origin');
  assert.equal(demo.root.children[3].children[0].children[0].textContent,'Revision 1 · Black to move');
  demo.app.destroy();assert.equal(demo.root.children.length,0);assert.deepEqual(demo.stopped,[1]);
});

test('match ID is a selector, not a grant; rejects malformed IDs before network calls',async()=>{
  const server=sampleFetch();const demo=setup({fetchFn:server.fn});
  for(const value of ['../admin','a/b','', 'x'.repeat(65)])assert.equal(await demo.app.launch(value),false);
  assert.equal(server.history.length,0);
  assert.match(demo.root.children[2].textContent,/Invalid match ID/);
  demo.app.destroy();
});

test('failed Social-hosted session does not mount a guest board or start polling',async()=>{
  const server=sampleFetch({deny:true});const demo=setup({fetchFn:server.fn});
  assert.equal(await demo.app.launch('match-123'),false);
  assert.equal(demo.root.children[3].children.length,0);
  assert.equal(demo.poll,null);
  assert.match(demo.root.children[2].textContent,/access denied/);
  demo.app.destroy();
});

test('polling refreshes server state only when active and visible, and stops on destroy',async()=>{
  const server=sampleFetch();const demo=setup({fetchFn:server.fn});
  assert.equal(await demo.app.launch('match-123'),true);
  demo.doc.hidden=true;
  demo.poll.fn();
  await Promise.resolve();
  assert.equal(server.history.filter(x=>x.options.method==='GET').length,1);
  demo.doc.hidden=false;
  demo.poll.fn();
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(server.history.filter(x=>x.options.method==='GET').length>=2);
  demo.app.destroy();assert.equal(demo.poll,null);
});

test('built player is isolated from local Checkers engine and is not advertised as a reviewed release',()=>{
  const src=readFileSync(new URL('../src/checkers_remote_entry.mjs',import.meta.url),'utf8');
  const page=readFileSync(new URL('../web/games/checkers-remote.html',import.meta.url),'utf8');
  const build=readFileSync(new URL('../tools/build.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(src,/(applyMove|legalMoves|initialBoard|localStorage|sessionStorage|Bearer|Authorization)/);
  assert.match(src,/sameOriginMatchTransport/);
  assert.doesNotMatch(page,/(demo_engine|Bearer|Authorization|apiKey)/);
  assert.match(build,/Source-only hosted multiplayer player/);
  assert.match(page,/Social and LoopRD game host/);
});
