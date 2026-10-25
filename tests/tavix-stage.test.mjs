import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {tavixPostBuildEnvironment} from '../tools/tavix_post_build_config.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');

test('Atrium builds once and stages only after the verified build',async()=>{
 const stage=await readFile(path.join(root,'tools/stage_tavix.mjs'),'utf8');
 assert.match(stage,/repository\.py/);
 assert.match(stage,/TAVIX_STAGE_READY/);
 assert.doesNotMatch(stage,/\b(?:git push|git commit|gh repo|token=)\b/i);
 const launcher=await readFile(path.join(root,'tools/post_build_tavix.mjs'),'utf8');
 assert.match(launcher,/build_tavi_extension\.mjs/);
 assert.match(launcher,/stage_tavix\.mjs/);
 assert.match(launcher,/spawnSync\(/);
 assert.match(launcher,/result\.status !== 0/);
 assert.doesNotMatch(launcher,/\b(?:git push|git commit|gh repo)\b/i);
 const recipe=JSON.parse(await readFile(path.join(root,'project.zr')));
 assert.deepEqual(recipe.build.slice(-3),['npm run build','npm run verify','node tools/post_build_tavix.mjs']);
 assert(!recipe.build.includes('node tools/stage_tavix.mjs'),'staging would run twice');
 assert(!recipe.build.includes('node tools/build_tavi_extension.mjs'),'Tavi build would run twice');
 const second=JSON.parse(await readFile(path.join(root,'atrium.zr')));
 assert.deepEqual(second.build,recipe.build);
 const manifest=JSON.parse(await readFile(path.join(root,'extensions/tavi/manifest.json')));
 assert.equal(manifest.version,'1.0.4');
});

test('Windows ZipRunner checkout requires the adjacent TaviX Git repository',()=>{
 const env=tavixPostBuildEnvironment('C:\\Users\\dorbi\\source\\atrium', {platform:'win32',env:{}});
 assert.equal(env.TAVIX_REPOSITORY_DIR,'C:\\Users\\dorbi\\source\\tavix');
 assert.equal(env.TAVIX_STAGE_REQUIRED,'1');
 const unableToSkip=tavixPostBuildEnvironment('C:\\Users\\dorbi\\source\\atrium', {platform:'win32',env:{TAVIX_STAGE_REQUIRED:'0'}});
 assert.equal(unableToSkip.TAVIX_STAGE_REQUIRED,'1','Windows must fail rather than skip TaviX staging');
});

test('Explicit TaviX path override honored without allowing Windows skip',()=>{
 const env=tavixPostBuildEnvironment('C:\\work\\atrium',{platform:'win32',env:{TAVIX_REPOSITORY_DIR:'D:\\apps\\tavix',TAVIX_STAGE_REQUIRED:'1',SOURCE_ONLY:'preserved'}});
 assert.equal(env.TAVIX_REPOSITORY_DIR,'D:\\apps\\tavix');
 assert.equal(env.TAVIX_STAGE_REQUIRED,'1');
 assert.equal(env.SOURCE_ONLY,'preserved');
});

test('Standalone Linux CI may skip, but explicit required flag remains binding',()=>{
 const standalone=tavixPostBuildEnvironment('/srv/atrium',{platform:'linux',env:{}});
 assert.equal(standalone.TAVIX_REPOSITORY_DIR,'/srv/tavix');
 assert.equal(standalone.TAVIX_STAGE_REQUIRED,'0');
 const enforced=tavixPostBuildEnvironment('/srv/atrium',{platform:'linux',env:{TAVIX_STAGE_REQUIRED:'1'}});
 assert.equal(enforced.TAVIX_STAGE_REQUIRED,'1');
});
