import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createTaviXSDK} from '../extensions/tavi/tavix-sdk.mjs';
import {installedGamesClient,openInstalledGame} from '../extensions/tavi/installed-games.mjs';

// Contract simulator, NOT a claim to run Tavi 0.3.141 source. The host is the
// only party that can authorize a caller and attest installed/approved games.
const id='org.example.klondike';
const atrium='inc.thebigtree.tavi.atrium';
const feature='tavix.installed-games/v1';
function hostSimulation({approved=true,extensionId=atrium}={}){
 const state={approved,extensionId,game:{id,version:'0.1.0',name:'Klondike Solitaire',classification:{type:'game',categories:['cards','solitaire']},installed:true,enabled:true},opened:null,route:'atrium',messages:[]};
 const target={postMessage(message){
  state.messages.push(message);
  queueMicrotask(()=>{
   const verified=state.approved && state.extensionId===atrium;
   const game=state.game;
   const active=game.installed && game.enabled;
   let ok=true,result=null,error='Game unavailable';
   if(message.method==='host.info')result={standard:'tavix/1.0',channel:'tavi.extension/v1',api:'1.0.0',extensionId:state.extensionId,mode:'embedded',navigation:'host',features:verified?[feature]:[]};
   else if(message.method==='games.installed.list'){
    if(!verified){ok=false;error='Permission denied';}
    else result={schema:'tavix.installed-games.inventory/v1',games:active?[{id:game.id,version:game.version,name:game.name,classification:game.classification}]:[]};
   }else if(message.method==='games.installed.open'){
    const p=message.params;
    if(!verified||!active||!p||p.id!==game.id||p.expectedVersion!==game.version){ok=false;error='Game unavailable';}
    else {result={accepted:true,id:game.id,version:game.version};state.opened=game.version;state.route='klondike';}
   }else if(message.method==='navigation.close'){state.route='atrium';}
   else throw Error('Unexpected method '+message.method);
   for(const fn of listeners)fn({source:target,data:{channel:'tavi.extension/v1',direction:'response',id:message.id,ok,result,error}});
  });
 }};
 const listeners=new Set();
 const source={addEventListener(event,fn){assert.equal(event,'message');listeners.add(fn);},removeEventListener(event,fn){listeners.delete(fn);}};
 return {state,sdk:createTaviXSDK(target,source)};
}

test('approved host lists classified Klondike, launches by id/version only, returns and refreshes inventory',async()=>{
 const {state,sdk}=hostSimulation();
 try{
  const first=await installedGamesClient(sdk);
  assert.equal(first.available,true);assert.equal(first.games.length,1);
  assert(Object.isFrozen(first.games));assert(Object.isFrozen(first.games[0]));
  const accepted=await openInstalledGame(sdk,first.games[0],first);
  assert.deepEqual(accepted,{accepted:true,id,version:'0.1.0'});
  assert.equal(state.route,'klondike');
  const open=state.messages.find(message=>message.method==='games.installed.open');
  assert.deepEqual(open.params,{id,expectedVersion:'0.1.0'});
  assert.equal(Object.hasOwn(open,'url'),false);
  await sdk.navigation.close();assert.equal(state.route,'atrium');
  const resumed=await installedGamesClient(sdk);
  assert.deepEqual(resumed.games.map(g=>g.id),[id]);
 }finally{sdk.dispose();}
});

test('Tavi rejects stale game version even after a valid initial inventory',async()=>{
 const {state,sdk}=hostSimulation();
 try{
  const first=await installedGamesClient(sdk);
  state.game.version='0.2.0';
  await assert.rejects(openInstalledGame(sdk,first.games[0],first),/Game unavailable/);
  const second=await installedGamesClient(sdk);assert.equal(second.games[0].version,'0.2.0');
  await assert.rejects(openInstalledGame(sdk,first.games[0],second),/verified installed inventory/);
 }finally{sdk.dispose();}
});

for(const condition of ['disabled','uninstalled']){
 test(`Tavi rejects a ${condition} game and omits it from subsequent inventory`,async()=>{
  const {state,sdk}=hostSimulation();
  try{
   const first=await installedGamesClient(sdk);
   state.game[condition==='disabled'?'enabled':'installed']=false;
   await assert.rejects(openInstalledGame(sdk,first.games[0],first),/Game unavailable/);
   const second=await installedGamesClient(sdk);assert.deepEqual(second.games,[]);
  }finally{sdk.dispose();}
 });
}

test('revoked official host grant is re-negotiated before any launch request',async()=>{
 const {state,sdk}=hostSimulation();
 try{
  const previous=await installedGamesClient(sdk);
  state.approved=false;
  await assert.rejects(openInstalledGame(sdk,previous.games[0],previous),/no longer authorizes/);
  assert.equal(state.messages.filter(m=>m.method==='games.installed.open').length,0);
  assert.deepEqual(await installedGamesClient(sdk),{available:false,games:[]});
 }finally{sdk.dispose();}
});

test('unapproved developer shadow and wrong extension identity never request another extension inventory',async()=>{
 for(const opts of [{approved:false},{approved:true,extensionId:'org.example.other'}]){
  const {state,sdk}=hostSimulation(opts);
  try{
   assert.deepEqual(await installedGamesClient(sdk),{available:false,games:[]});
   assert.deepEqual(state.messages.map(m=>m.method),['host.info']);
  }finally{sdk.dispose();}
 }
});

test('a retained Atrium screen refreshes after a game returns, not only on initial load',async()=>{
 const source=await readFile(new URL('../web/main.mjs',import.meta.url),'utf8');
 assert.match(source,/window\.addEventListener\('focus',refreshOnReturn\)/);
 assert.match(source,/window\.addEventListener\('pageshow',refreshOnReturn\)/);
 assert.match(source,/document\.addEventListener\('visibilitychange',refreshOnReturn\)/);
 assert.match(source,/const fresh=await window\.__atriumInstalledGames\.list\(\)/);
});
