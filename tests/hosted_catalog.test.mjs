import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateHostedCatalog,fetchHostedCatalog} from '../src/hosted_catalog.mjs';
const base={schema:'atrium.hosted-games/v1',games:[]};
const game={gameId:'life.loop',title:'Life',publisherId:'thebigtreeinc',deploymentId:'prod-life',component:'the-life-loop',launchUrl:'https://thebigtreeinc.github.io/life/',apiBaseUrl:'https://api.example.org/looprd/the-life-loop/v1',sourceRevision:'a'.repeat(40),approved:true,status:'published',embedAllowed:false};
test('default source publishes NO games',()=>assert.deepEqual(validateHostedCatalog(base).games,[]));
test('only explicit reviewed and bound Life record can appear',()=>{assert.equal(validateHostedCatalog({...base,games:[game]}).games[0].gameId,'life.loop');for(const change of [{approved:false},{status:'candidate'},{sourceRevision:'main'},{launchUrl:'http://example.org'},{launchUrl:'https://bad.example.org/?token=x'},{apiBaseUrl:'https://evil.example.org/admin'},{component:'evil'}, {embedAllowed:'yes'}])assert.throws(()=>validateHostedCatalog({...base,games:[{...game,...change}]}));});
test('reject duplicate deployments, extra fields and cred-containing redirects',()=>{assert.throws(()=>validateHostedCatalog({...base,games:[game,game]}));assert.throws(()=>validateHostedCatalog({...base,games:[{...game,credential:'secret'}]}));});
test('public retrieval has no bearer/cookies and errors fail closed',async()=>{const calls=[];await fetchHostedCatalog(async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>base};});assert.equal(calls[0].options.credentials,'omit');assert.equal(calls[0].options.redirect,'error');await assert.rejects(()=>fetchHostedCatalog(async()=>({ok:false})));});
