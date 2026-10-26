import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateHostedCatalog,fetchHostedCatalog,parseHostedCatalogSource,fetchConfiguredHostedCatalog} from '../src/hosted_catalog.mjs';
const base={schema:'atrium.hosted-games/v1',games:[]};
const game={gameId:'life.loop',title:'Life',publisherId:'thebigtreeinc',deploymentId:'prod-life',component:'the-life-loop',launchUrl:'https://thebigtreeinc.github.io/life/',apiBaseUrl:'https://api.example.org/looprd/the-life-loop/v1',sourceRevision:'a'.repeat(40),approved:true,status:'published',embedAllowed:false};
test('default source publishes NO games',()=>assert.deepEqual(validateHostedCatalog(base).games,[]));
test('only explicit reviewed and bound Life record can appear',()=>{assert.equal(validateHostedCatalog({...base,games:[game]}).games[0].gameId,'life.loop');for(const change of [{approved:false},{status:'candidate'},{sourceRevision:'main'},{launchUrl:'http://example.org'},{launchUrl:'https://bad.example.org/?token=x'},{apiBaseUrl:'https://evil.example.org/admin'},{component:'evil'}, {embedAllowed:'yes'}])assert.throws(()=>validateHostedCatalog({...base,games:[{...game,...change}]}));});
test('reject duplicate deployments, extra fields and cred-containing redirects',()=>{assert.throws(()=>validateHostedCatalog({...base,games:[game,game]}));assert.throws(()=>validateHostedCatalog({...base,games:[{...game,credential:'secret'}]}));});
test('public retrieval has no bearer/cookies and errors fail closed',async()=>{const calls=[];await fetchHostedCatalog(async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>base};});assert.equal(calls[0].options.credentials,'omit');assert.equal(calls[0].options.redirect,'error');await assert.rejects(()=>fetchHostedCatalog(async()=>({ok:false})));});

test('operator HTTPS hosted catalog source must be reviewed and never accept credentials',()=>{
 assert.equal(parseHostedCatalogSource({schema:'atrium.hosted-source/v1',gatewayUrl:''}),'./hosted-games.json');
 const approved='https://catalog.operator-games.net/hosted-games.json';
 assert.equal(parseHostedCatalogSource({schema:'atrium.hosted-source/v1',gatewayUrl:approved}),approved);
 const looprd='https://api.operator-games.net/looprd/atrium/v1/catalog/hosted-games';
 assert.equal(parseHostedCatalogSource({schema:'atrium.hosted-source/v1',gatewayUrl:looprd}),looprd);
 for(const url of ['https://atrium.example.org/hosted-games.json','https://example.org/hosted-games.json','https://host.test/hosted-games.json','http://atrium.example.org/hosted-games.json','https://u:p@atrium.example.org/hosted-games.json','https://atrium.example.org/catalog.json','https://catalog.operator-games.net/hosted-games.json?token=x','https://api.operator-games.net/looprd/atrium/v1/registry/discovery/v2/catalog','https://api.operator-games.net/looprd/atrium/v1/catalog/hosted-games?token=x','https://localhost/hosted-games.json'])assert.throws(()=>parseHostedCatalogSource({schema:'atrium.hosted-source/v1',gatewayUrl:url}));
 assert.throws(()=>parseHostedCatalogSource({schema:'atrium.hosted-source/v1',gatewayUrl:'',authorization:'secret'}));
});
test('configured hosted catalogue loads public source and review without bearer',async()=>{
 const urls=[];
 const data=await fetchConfiguredHostedCatalog(async(url,opt)=>{
  urls.push({url,opt});
  return {ok:true,json:async()=>url==='./hosted-config.json'?{schema:'atrium.hosted-source/v1',gatewayUrl:'https://catalog.operator-games.net/hosted-games.json'}:base};
 });
 assert.deepEqual(data.games,[]);
 assert.deepEqual(urls.map(x=>x.url),['./hosted-config.json','https://catalog.operator-games.net/hosted-games.json']);
 assert(urls.every(x=>x.opt.credentials==='omit'&&x.opt.redirect==='error'));
});
test('operator-approved second hosted game can be listed without Life hardcoding',()=>{
 const other={...game,gameId:'example.chess',component:'chess-server',title:'Chess',
    apiBaseUrl:'https://api.example.org/looprd/chess-server/v1',
    launchUrl:'https://games.example.org/chess/index.html'};
 assert.deepEqual(validateHostedCatalog({...base,games:[game,other]}).games.map(g=>g.gameId),['life.loop','example.chess']);
 assert.throws(()=>validateHostedCatalog({...base,games:[{...other,apiBaseUrl:game.apiBaseUrl}]}));
});

test('offline preview configuration explicitly says not connected rather than zero published games',async()=>{
 await assert.rejects(()=>fetchConfiguredHostedCatalog(async()=>({ok:true,json:async()=>({schema:'atrium.hosted-source/v1',gatewayUrl:''})})),/ATRIUM_HOSTED_NOT_CONFIGURED/);
});
