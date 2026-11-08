import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fetchConfiguredHostedCatalog,loadHostedEndpoint} from '../src/hosted_catalog.mjs';
import {loadCatalogEndpoint,fetchPublicCatalog} from '../src/catalog_client.mjs';

const root=new URL('../',import.meta.url);
const main=readFileSync(new URL('web/main.mjs',root),'utf8');
const config=JSON.parse(readFileSync(new URL('web/hosted-config.json',root),'utf8'));
const catalog=JSON.parse(readFileSync(new URL('web/hosted-games.json',root),'utf8'));
const reviewedConfig=JSON.parse(readFileSync(new URL('web/catalog-config.json',root),'utf8'));
const reviewed=JSON.parse(readFileSync(new URL('web/catalog.json',root),'utf8'));

test('empty bundled catalogs are valid published-game inventories, not outages',async()=>{
 assert.deepEqual(catalog.games,[]);
 assert.deepEqual(reviewed.apps,[]);
 const visits=[];
 const byUrl={'./hosted-config.json':config,'./hosted-games.json':catalog,'./catalog-config.json':reviewedConfig,'./catalog.json':reviewed};
 const local=async(url,opts)=>{visits.push({url,opts});assert.ok(url in byUrl,'unexpected external source: '+url);return {ok:true,json:async()=>byUrl[url]};};
 assert.equal(await loadHostedEndpoint(local),'./hosted-games.json');
 assert.deepEqual((await fetchConfiguredHostedCatalog(local)).games,[]);
 assert.deepEqual((await fetchPublicCatalog(local,await loadCatalogEndpoint(local))).apps,[]);
 assert.deepEqual(visits.map(x=>x.url),['./hosted-config.json','./hosted-config.json','./hosted-games.json','./catalog-config.json','./catalog.json']);
 assert.ok(visits.every(x=>x.opts?.credentials==='omit'));
});

test('configured unavailable HTTPS catalog still fails closed; never show a fabricated empty inventory',async()=>{
 const endpoint='https://catalog.operator-games.net/hosted-games.json';
 let calls=0;
 const fetcher=async(url)=>{calls++;return {ok:true,json:async()=>({schema:'atrium.hosted-source/v1',gatewayUrl:endpoint}),status:200,...(url===endpoint?{ok:false,status:503}:{})};};
 await assert.rejects(fetchConfiguredHostedCatalog(fetcher),/HTTP 503/);
 assert.equal(calls,2);
});

test('healthy zero inventory renders compact empty state rather than unavailable',()=>{
 assert.match(main,/No games published yet/);
 assert.match(main,/:'0 games'/);
 assert.match(main,/await mountHostedLife\(\{area\}\)/);
 assert.doesNotMatch(main,/hostedDisabled/);
 assert.doesNotMatch(main,/ATRIUM_HOSTED_NOT_CONFIGURED/);
 assert.match(main,/issues\.push\(catalogIssue\('hosted',error\)\)/);
});
