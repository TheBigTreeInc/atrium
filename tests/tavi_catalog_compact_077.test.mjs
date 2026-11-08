import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {loadHostedEndpoint,isUnconfiguredHostedCatalog,parseHostedCatalogSource} from '../src/hosted_catalog.mjs';
const main=readFileSync(new URL('../web/main.mjs',import.meta.url),'utf8');
const css=readFileSync(new URL('../web/material-theme.css',import.meta.url),'utf8');
const html=readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const builder=readFileSync(new URL('../tools/build.mjs',import.meta.url),'utf8');

test('empty hosted gateway is a deliberate preview state, not a failed network request',async()=>{
 const fetcher=async()=>({ok:true,json:async()=>({schema:'atrium.hosted-source/v1',gatewayUrl:''})});
 await assert.rejects(loadHostedEndpoint(fetcher),error=>isUnconfiguredHostedCatalog(error));
 assert.equal(isUnconfiguredHostedCatalog(new Error('ATRIUM_HOSTED_UNAVAILABLE: HTTP 502')),false);
 assert.equal(isUnconfiguredHostedCatalog(new Error('invalid hosted catalog')),false);
 assert.equal(parseHostedCatalogSource({schema:'atrium.hosted-source/v1',gatewayUrl:''}),'./hosted-games.json');
});
test('genuine hosted source failures remain errors rather than empty inventory',async()=>{
 const badFetch=async()=>({ok:false,status:503});
 await assert.rejects(loadHostedEndpoint(badFetch),error=>!isUnconfiguredHostedCatalog(error));
 assert.match(main,/issues\.push\(catalogIssue\('hosted',error\)\)/);
 assert.match(main,/issues\.push\(catalogIssue\('reviewed',error\)\)/);
});
test('embedded Tavi has one compact status per context and does not duplicate source errors',()=>{
 assert.match(main,/if\(isUnconfiguredHostedCatalog\(error\)\)hostedDisabled=true/);
 assert.match(main,/if\(!hostedDisabled&&!issues\.some/);
 assert.match(main,/if\(!document\.body\.classList\.contains\('tavix-extension'\)\)for\(const issue of issues\)/);
 assert.match(main,/No online games published yet/);
 assert.match(main,/Installed games not connected/);
 assert.doesNotMatch(main,/Catalog not connected/);
 assert.doesNotMatch(main,/Retry connection/);
 assert.match(css,/body\.tavix-extension \.emptyState \.state-icon\{display:none/);
 assert.match(css,/\.source-notice,\.library-notice\{/);
 assert.match(html,/Discover games/);
 assert.match(builder,/from '.\/src\/hosted_catalog\.mjs'/);
});
