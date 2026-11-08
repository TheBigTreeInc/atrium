import test from 'node:test';
import assert from 'node:assert/strict';
import {parseTavixMarketplace,fetchTavixMarketplace} from '../src/tavix_marketplace.mjs';
const game={id:'org.example.klondike',version:'0.1.1',name:'Klondike',publisher:'example',summary:'Solo cards',description:'Card solitaire',categories:['cards'],platforms:['web','windows'],featured:false,collections:[]};
const snapshot={schema:'atrium.tavix-games/v1',sourceIndexSha256:'a'.repeat(64),games:[game]};
test('read only TaviX marketplace offers no executable/install location',()=>{
 const result=parseTavixMarketplace(snapshot);
 assert.equal(result.games[0].name,'Klondike');
 assert.ok(Object.isFrozen(result.games[0]));
 assert.ok(!Object.hasOwn(result.games[0],'entrypoint'));
});
test('empty bundled marketplace is healthy, unpinned content is not',()=>{
 assert.equal(parseTavixMarketplace({schema:snapshot.schema,sourceIndexSha256:null,games:[]}).games.length,0);
 assert.throws(()=>parseTavixMarketplace({...snapshot,sourceIndexSha256:null}),/Invalid TaviX/);
});
test('rejects identity spoofing, install URLs, duplicate IDs and output schema drift',()=>{
 for(const patch of [{entrypoint:'https://evil.example'},{publisher:'fake/script'},{id:'../evil'},{categories:['cards','cards']},{platforms:['linux']},{featured:'yes'},{description:'x\x00'}]){
  assert.throws(()=>parseTavixMarketplace({...snapshot,games:[{...game,...patch}]}));
 }
 assert.throws(()=>parseTavixMarketplace({...snapshot,games:[game,game]}));
});
test('fetch only same-origin relative static projection without credentials or redirects',async()=>{
 let called;
 const value=await fetchTavixMarketplace(async (url,settings)=>{called=[url,settings];return {ok:true,json:async()=>snapshot};});
 assert.deepEqual(called,['./tavix-games.json',{cache:'no-store',credentials:'omit',redirect:'error'}]);
 assert.equal(value.games.length,1);
 await assert.rejects(fetchTavixMarketplace(async()=>({ok:false})),/unavailable/);
 await assert.rejects(fetchTavixMarketplace(async()=>({ok:true}), 'https://evil.example/index.json'),/same-origin/);
});
