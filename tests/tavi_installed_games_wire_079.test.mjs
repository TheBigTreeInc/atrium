import test from 'node:test';
import assert from 'node:assert/strict';
import {createTaviXSDK} from '../extensions/tavi/tavix-sdk.mjs';
import {installedGamesClient,openInstalledGame} from '../extensions/tavi/installed-games.mjs';

const game={id:'org.example.klondike',version:'0.1.0',name:'Klondike Solitaire',classification:{type:'game',categories:['cards','solitaire']}};
const inventory={schema:'tavix.installed-games.inventory/v1',games:[game]};
function harness({features=['tavix.installed-games/v1'],openResult={accepted:true,id:game.id,version:game.version},denied=false}={}){
 const sent=[],listeners=new Set();
 const source={addEventListener(name,fn){assert.equal(name,'message');listeners.add(fn);},removeEventListener(name,fn){listeners.delete(fn);}};
 const target={postMessage(message,origin){
  assert.equal(origin,'*');sent.push(message);
  queueMicrotask(()=>{
   let result;
   if(message.method==='host.info')result={standard:'tavix/1.0',channel:'tavi.extension/v1',api:'1.0.0',extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host',features};
   else if(message.method==='games.installed.list')result=inventory;
   else if(message.method==='games.installed.open')result=openResult;
   else if(message.method==='storage.get')result=null;
   else if(message.method==='storage.set')result=null;
   else if(message.method==='navigation.close')result=null;
   else throw Error('Unexpected method '+message.method);
   for(const listener of listeners)listener({source:target,data:{channel:'tavi.extension/v1',direction:'response',id:message.id,ok:!denied,error:'Permission denied',result}});
  });
 }};
 return {sent,sdk:createTaviXSDK(target,source)};
}

test('installed-game open uses Social 0.3.141 params envelope and no executable URL',async()=>{
 const {sent,sdk}=harness();
 try{
  const current=await installedGamesClient(sdk);
  const accepted=await openInstalledGame(sdk,current.games[0],current);
  assert.equal(accepted.accepted,true);
  const list=sent.find(x=>x.method==='games.installed.list');
  assert.deepEqual(Object.keys(list).sort(),['channel','direction','id','method'].sort());
  const open=sent.find(x=>x.method==='games.installed.open');
  assert.deepEqual(open.params,{id:game.id,expectedVersion:game.version});
  assert.deepEqual(Object.keys(open).sort(),['channel','direction','id','method','params'].sort());
  assert(!JSON.stringify(open).includes('url'));
 }finally{sdk.dispose();}
});

test('other Tavi host calls retain their existing top-level storage/navigation wire format',async()=>{
 const {sent,sdk}=harness();
 try{
  await sdk.storage.get('save');await sdk.storage.set('save','value');await sdk.navigation.close();
  assert.deepEqual(sent.find(x=>x.method==='storage.get').key,'save');
  assert.deepEqual(sent.find(x=>x.method==='storage.set').value,'value');
  for(const message of sent)assert.equal(Object.hasOwn(message,'params'),false);
 }finally{sdk.dispose();}
});

test('without the approved feature no installed inventory or launch calls are sent',async()=>{
 const {sent,sdk}=harness({features:[]});
 try{
  const unavailable=await installedGamesClient(sdk);assert.deepEqual(unavailable,{available:false,games:[]});
  await assert.rejects(openInstalledGame(sdk,game,unavailable),/verified installed inventory/);
  assert.deepEqual(sent.map(x=>x.method),['host.info']);
 }finally{sdk.dispose();}
});

test('host denied/revoked authorization and stale version are never reported as successful launches',async()=>{
 const {sdk,sent}=harness({openResult:{accepted:false}});
 try{
  const current=await installedGamesClient(sdk);
  await assert.rejects(openInstalledGame(sdk,game,current),/did not accept/);
  const prior=sent.length;
  await assert.rejects(openInstalledGame(sdk,{...game,version:'0.2.0'},current),/verified installed inventory/);
  assert.equal(sent.length,prior);
 }finally{sdk.dispose();}
 const denied=harness({denied:true});
 try{await assert.rejects(installedGamesClient(denied.sdk),/Permission denied/);}finally{denied.sdk.dispose();}
});
