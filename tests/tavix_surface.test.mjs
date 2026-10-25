import test from 'node:test';
import assert from 'node:assert/strict';

const requests=[];
const listeners=new Map();
let info={standard:'tavix/1.0',channel:'tavi.extension/v1',api:'1.0.0',extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host',features:['tavix.surface/v1']};
const button={disabled:false,handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},remove(){}};
const parent={postMessage(message){
 requests.push(message);
 queueMicrotask(()=>{
  let result={};
  if(message.method==='host.info')result=info;
  if(message.method==='ui.requestGameLaunch')result={awaitingApproval:true};
  const event={source:parent,data:{channel:'tavi.extension/v1',direction:'response',id:message.id,ok:true,result}};
  for(const fn of listeners.get('message')||[])fn(event);
 });
}};
const windowMock={parent,addEventListener(name,fn){const a=listeners.get(name)||[];a.push(fn);listeners.set(name,a);},removeEventListener(){}};
globalThis.window=windowMock;
globalThis.document={getElementById(id){return id==='returnTavi'?button:null;}};
const {requestGameSurface,requestReviewedGameSurface,exactLifeHandoff}=await import('../extensions/tavi/extension-bridge.mjs');
const target='https://thebigtreeinc.github.io/life/';

test('feature-advertised TaviX host opens generic surface without player credentials',async()=>{
 requests.length=0;
 const opened=await requestGameSurface('life.loop',target);
 assert.equal(opened,true);
 const r=requests.find(x=>x.method==='surface.requestOpen');
 assert.deepEqual(r.surface,{schema:'tavix.surface/v1',id:'life.loop',kind:'game',target,context:{},presentation:'auto'});
 assert(!JSON.stringify(r).includes('Authorization'));
});
test('TaviX accepts optional existing match context without passing identity',async()=>{
 requests.length=0;
 assert.equal(await requestGameSurface('life.loop',target,'abc-9'),true);
 const r=requests.find(x=>x.method==='surface.requestOpen');
 assert.deepEqual(r.surface.context,{matchId:'abc-9'});
});
test('older Tavi supports negotiated Life resume only',async()=>{
 info={extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host',features:['atrium.tavi-launch/v1']};
 requests.length=0;
 await assert.rejects(()=>requestGameSurface('life.loop',target,'resume_1'),/older Tavi host/);
 assert(!requests.some(x=>x.method==='ui.requestGameLaunch'));
 assert.equal(await requestGameSurface('life.loop',target,'resume_1',{allowLegacy:true}),true);
 assert(requests.some(x=>x.method==='ui.requestGameLaunch'&&x.handoff.matchContext.matchId==='resume_1'));
 await assert.rejects(()=>requestGameSurface('market.grove','https://thebigtreeinc.github.io/atrium/'),/cannot open an embedded game/);
 assert(!requests.some(x=>x.method==='surface.requestOpen'));
});
test('host without capability requires explicit browser choice rather than fake success',async()=>{
 info={extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host',features:[]};
 await assert.rejects(()=>requestGameSurface('life.loop',target),/explicit Open in browser/);
});
test('reject bad surface targets and match IDs before any host request',async()=>{
 requests.length=0;
 await assert.rejects(()=>requestGameSurface('life.loop','http://bad.example/'),/Invalid game launch target/);
 await assert.rejects(()=>requestGameSurface('life.loop','https://127.0.0.1/'),/Unapproved game target/);
 await assert.rejects(()=>requestGameSurface('life.loop',target,'bad id'),/Invalid game match context/);
 assert.throws(()=>exactLifeHandoff(target,'bad id'),/Invalid Life match context/);
 assert.equal(requests.length,0);
});
test('Return to Tavi uses TaviX navigation.close when host advertises the standard',async()=>{
 info={standard:'tavix/1.0',channel:'tavi.extension/v1',api:'1.0.0',extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host',features:['tavix.surface/v1']};
 requests.length=0;
 await button.handlers.click();
 assert(requests.some(x=>x.method==='navigation.close'));
});


test('reviewed surface revalidates the exact currently published deployment and launch target',async()=>{
 info={standard:'tavix/1.0',channel:'tavi.extension/v1',api:'1.0.0',extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host',features:['tavix.surface/v1']};
 const game={gameId:'life.loop',component:'the-life-loop',publisherId:'thebigtreeinc',deploymentId:'test-life-1',title:'Life',
   launchUrl:target,apiBaseUrl:'https://api.example.org/looprd/the-life-loop/v1',sourceRevision:'a'.repeat(40),approved:true,status:'published',embedAllowed:true};
 let games=[game];
 const fetcher=async url=>({ok:true,json:async()=>url.includes('hosted-config')?{schema:'atrium.hosted-source/v1',gatewayUrl:''}:{schema:'atrium.hosted-games/v1',games}});
 requests.length=0;
 assert.equal(await requestReviewedGameSurface('life.loop','test-life-1',target,'',{fetcher}),true);
 assert(requests.some(x=>x.method==='surface.requestOpen'));
 requests.length=0;
 await assert.rejects(()=>requestReviewedGameSurface('life.loop','test-life-2',target,'',{fetcher}),/not published/);
 await assert.rejects(()=>requestReviewedGameSurface('life.loop','test-life-1','https://not-approved.example/game','',{fetcher}),/not published/);
 games=[];
 await assert.rejects(()=>requestReviewedGameSurface('life.loop','test-life-1',target,'',{fetcher}),/not published/);
 assert.equal(requests.length,0);
});

test('TaviX requested match selector contains no credential or browser query',async()=>{
 requests.length=0;
 const context='resume_123';
 await requestGameSurface('life.loop',target,context);
 const surface=requests.find(x=>x.method==='surface.requestOpen').surface;
 assert.deepEqual(surface.context,{matchId:context});
 assert.equal(new URL(surface.target).search,'');
 assert(!JSON.stringify(surface).match(/bearer|token|seat|authorization|invite/i));
});
