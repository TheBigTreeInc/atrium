import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const read=(name)=>readFile(new URL('../'+name,import.meta.url),'utf8');

test('review-only TaviX candidate does not require an online gateway or optional Assets permissions',async()=>{
 const candidate=JSON.parse(await read('extensions/tavi/installed-games-candidate.json'));
 const manifest=JSON.parse(await read('extensions/tavi/manifest.json'));
 assert.equal(candidate.schema,'atrium.tavix.review-candidate/v1');
 assert.equal(candidate.version,'1.0.11');
 assert.equal(manifest.version,'1.0.4'); // pinned historical release stays unchanged
 assert.deepEqual(manifest.permissions,['ui.panel']);
 assert.equal(Object.hasOwn(manifest,'assetDependencies'),false);
 assert(!manifest.permissions.some(p=>p.startsWith('assets.')));
});

test('unapproved review candidate must be explicitly requested and cannot auto-stage to official TaviX',async()=>{
 const builder=await read('tools/build_tavi_extension.mjs');
 const postBuild=await read('tools/post_build_tavix.mjs');
 assert.match(builder,/ATRIUM_TAVIX_REVIEW_CANDIDATE/);
 assert.match(builder,/reviewCandidate && configuredEndpoint!=='\.\/hosted-games\.json'/);
 assert.match(builder,/installed-games-candidate\.json/);
 assert.match(builder,/review-candidate\/v1/);
 assert.match(builder,/reviewCandidate && process\.env\.ATRIUM_TAVIX_DEV_PREVIEW==='1'/);
 assert.match(postBuild,/if\(process\.env\.ATRIUM_TAVIX_REVIEW_CANDIDATE==='1'\)throw Error/);
 assert(!builder.includes('git push'));
});
