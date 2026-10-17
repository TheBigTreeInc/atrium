import {readFile, stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dist=path.join(root,'dist');
for (const name of ['index.html','main.mjs','catalog.json','src/apphost.mjs']) {
 const file=path.join(dist,name);
 const info=await stat(file);
 assert(info.isFile() && info.size>0,`missing build asset: ${name}`);
}
const main=await readFile(path.join(dist,'main.mjs'),'utf8');
assert(main.includes("'./src/apphost.mjs'"),'built entrypoint must use relative module import');
assert(!main.includes("'../src/apphost.mjs'"),'built entrypoint escapes dist');
const catalog=JSON.parse(await readFile(path.join(dist,'catalog.json'),'utf8'));
assert(catalog && (Array.isArray(catalog) || typeof catalog==='object'));
console.log('Verified standalone static portal artifacts (no deployment implied)');
