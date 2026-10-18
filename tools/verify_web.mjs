import {readFile, stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dist=path.join(root,'dist');
for (const name of ['index.html','main.mjs','catalog.json','catalog-config.json','src/apphost.mjs','src/catalog_client.mjs','src/multiplayer_lobby.mjs','src/mock_life_api.mjs','src/multiplayer_preview_ui.mjs','src/hosted_life.mjs','.nojekyll']) {
 const file=path.join(dist,name);
 const info=await stat(file);
 assert(info.isFile() && (info.size>0 || name==='.nojekyll'),`missing build asset: ${name}`);
}
const main=await readFile(path.join(dist,'main.mjs'),'utf8');
assert(main.includes("'./src/apphost.mjs'"),'built entrypoint must use relative module import');
assert(!main.includes("'../src/apphost.mjs'"),'built entrypoint escapes dist');
assert(main.includes("'./src/catalog_client.mjs'"),'catalog module path must be build-local');
assert(main.includes("'./src/multiplayer_preview_ui.mjs'"),'multiplayer mock entry must be build-local');
assert(!main.includes("'../src/multiplayer_preview_ui.mjs'"),'multiplayer entry escapes dist');
const mockSource=await readFile(path.join(dist,'src','mock_life_api.mjs'),'utf8');
assert(!/\bfetch\s*\(/.test(mockSource),'mock must not make live network requests');
const catalog=JSON.parse(await readFile(path.join(dist,'catalog.json'),'utf8'));
const {parsePublicCatalog}=await import('../src/catalog_client.mjs');
parsePublicCatalog(catalog);
if (catalog.apps.length) {
  // Static first-party preview is independently verified at build time. Production
  // live catalogs are consumed at request time, never merged into static assets.
  assert.equal(catalog.apps.length,1,'only explicit first-party preview may be staged');
  const app=catalog.apps[0];
  assert.equal(app.id,'atrium.checkers.preview');
  assert.equal(app.entry,`https://thebigtreeinc.github.io/atrium/games/checkers/${app.sha256}/index.html`);
  const asset=await readFile(path.join(dist,'games','checkers',app.sha256,'index.html'));
  assert.equal(createHash('sha256').update(asset).digest('hex'),app.sha256,'staged HTML must match catalog digest');
}

const index=await readFile(path.join(dist,'index.html'),'utf8');
assert(index.includes('src="./main.mjs"'),'Pages must use subpath-safe relative JS');
assert(index.includes('id="multiplayerLab"'),'UI preview must remain reachable with an empty catalog');
assert(index.includes('No live game sessions'),'sandbox cannot masquerade as real multiplayer');
assert(!index.includes('src="/main.mjs"'),'Pages must not use origin-root assets');
const config=JSON.parse(await readFile(path.join(dist,'catalog-config.json'),'utf8'));
const {parseCatalogSource}=await import('../src/catalog_client.mjs');
assert(typeof parseCatalogSource(config)==='string','validated public catalog source');
assert(!main.includes('Authorization') && !main.includes('apiKey'),'No operator credential in public client');
assert(!index.includes('Tavi login') && !index.includes('Sign in to play'),'Do not simulate missing shared-auth system');
console.log('Verified Pages-safe static portal assets (publication is operator-triggered)');
