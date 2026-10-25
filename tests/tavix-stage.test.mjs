import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
test('Atrium stages via immutable TaviX Git checkout only after verify',async()=>{
 const src=await readFile(path.join(root,'tools/stage_tavix.mjs'),'utf8');
 assert.match(src,/repository\.py/);
 assert.match(src,/TAVIX_STAGE_READY/);
 assert.doesNotMatch(src,/\b(?:git push|git commit|gh repo|token=)\b/i);
 const recipe=JSON.parse(await readFile(path.join(root,'project.zr')));
 assert(recipe.build.indexOf('node tools/stage_tavix.mjs') > recipe.build.indexOf('npm run verify'));
 assert(recipe.build.indexOf('node tools/stage_tavix.mjs') > recipe.build.indexOf('node tools/build_tavi_extension.mjs'));
 const second=JSON.parse(await readFile(path.join(root,'atrium.zr')));
 assert.deepEqual(second.build,recipe.build);
 const manifest=JSON.parse(await readFile(path.join(root,'extensions/tavi/manifest.json')));
 assert.equal(manifest.version,'1.0.4');
});
