import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const html=readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const main=readFileSync(new URL('../web/main.mjs',import.meta.url),'utf8');
const builder=readFileSync(new URL('../tools/build_tavi_extension.mjs',import.meta.url),'utf8');
test('mobile layout wraps categories and presents a light/dark palette',()=>{
 assert.match(html,/\.chips\{overflow:visible;flex-wrap:wrap/);
 assert.match(html,/prefers-color-scheme:dark/);
 assert.match(html,/\.chips\[hidden\]\{display:none!important\}/);
});
test('empty hosted catalog is a normal zero-game library, while real errors remain visible',()=>{
 assert.doesNotMatch(main,/isUnconfiguredHostedCatalog\(error\)/);
 assert.match(main,/categoryChips\.hidden=count===0/);
 assert.doesNotMatch(main,/hostedDisabled/);
 assert.match(main,/No games published yet/);
 assert.match(main,/issues\.push\(catalogIssue\('hosted',error\)\)/);
});
test('future TaviX shell has no second bottom bar; pinned offline version remains immutable',()=>{
 assert.match(builder,/tavix-inline-tabs/);
 assert.match(builder,/layout\.before\(nav\)/);
 assert.match(builder,/if\(configuredEndpoint==='\.\/hosted-games\.json' && process\.env\.ATRIUM_TAVIX_DEV_PREVIEW!=='1' && !reviewCandidate\)/);
 assert.match(builder,/copied pinned immutable offline release/);
});
