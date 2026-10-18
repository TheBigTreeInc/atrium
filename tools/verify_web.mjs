import {readFile, stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dist=path.join(root,'dist');
for (const name of ['index.html','main.mjs','catalog.json','catalog-config.json','src/apphost.mjs','src/catalog_client.mjs','.nojekyll']) {
 const file=path.join(dist,name);
 const info=await stat(file);
 assert(info.isFile() && (info.size>0 || name==='.nojekyll'),`missing build asset: ${name}`);
}
const main=await readFile(path.join(dist,'main.mjs'),'utf8');
assert(main.includes("'./src/apphost.mjs'"),'built entrypoint must use relative module import');
assert(!main.includes("'../src/apphost.mjs'"),'built entrypoint escapes dist');
assert(main.includes("'./src/catalog_client.mjs'"),'catalog module path must be build-local');
const catalog=JSON.parse(await readFile(path.join(dist,'catalog.json'),'utf8'));
assert(catalog && (Array.isArray(catalog) || typeof catalog==='object'));
const index=await readFile(path.join(dist,'index.html'),'utf8');
assert(index.includes('src="./main.mjs"'),'Pages must use subpath-safe relative JS');
assert(!index.includes('src="/main.mjs"'),'Pages must not use origin-root assets');
const config=JSON.parse(await readFile(path.join(dist,'catalog-config.json'),'utf8'));
const {parseCatalogSource}=await import('../src/catalog_client.mjs');
assert(typeof parseCatalogSource(config)==='string','validated public catalog source');
assert(!main.includes('Authorization') && !main.includes('apiKey'),'No operator credential in public client');
assert(!index.includes('Tavi login') && !index.includes('Sign in to play'),'Do not simulate missing shared-auth system');
console.log('Verified Pages-safe static portal assets (publication is operator-triggered)');
