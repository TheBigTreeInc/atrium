import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,mkdir,rm} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
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
 assert.deepEqual(recipe.build.slice(-2),['npm run build','npm run verify']);
 assert(!recipe.build.includes('node tools/post_build_tavix.mjs'),'staging would run twice');
 assert(!recipe.build.includes('node tools/stage_tavix.mjs'),'staging would run twice');
 assert(!recipe.build.includes('node tools/build_tavi_extension.mjs'),'Tavi build would run twice');
 const second=JSON.parse(await readFile(path.join(root,'atrium.zr')));
 assert.deepEqual(second.build,recipe.build);
 const manifest=JSON.parse(await readFile(path.join(root,'extensions/tavi/manifest.json')));
 const pkg=JSON.parse(await readFile(path.join(root,'package.json'),'utf8'));
 assert.match(pkg.scripts.build,/node tools\/post_build_tavix\.mjs/,'build must stage even if ZipRunner keeps an older recipe');
 assert.match(pkg.scripts.build,/node tools\/verify_web\.mjs.*node tools\/post_build_tavix\.mjs/,'verify before staging');
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

test('GitHub-hosted Windows CI may skip while operator Windows stays mandatory',()=>{
 const ci=tavixPostBuildEnvironment('D:\\a\\atrium',{platform:'win32',env:{GITHUB_ACTIONS:'true'}});
 assert.equal(ci.TAVIX_STAGE_REQUIRED,'0');
 const force=tavixPostBuildEnvironment('D:\\a\\atrium',{platform:'win32',env:{GITHUB_ACTIONS:'true',TAVIX_STAGE_REQUIRED:'1'}});
 assert.equal(force.TAVIX_STAGE_REQUIRED,'1');
 const local=tavixPostBuildEnvironment('D:\\a\\atrium',{platform:'win32',env:{CI:'true'}});
 assert.equal(local.TAVIX_STAGE_REQUIRED,'1');
});

test('Standalone Linux CI may skip, but explicit required flag remains binding',()=>{
 const standalone=tavixPostBuildEnvironment('/srv/atrium',{platform:'linux',env:{}});
 assert.equal(standalone.TAVIX_REPOSITORY_DIR,'/srv/tavix');
 assert.equal(standalone.TAVIX_STAGE_REQUIRED,'0');
 const enforced=tavixPostBuildEnvironment('/srv/atrium',{platform:'linux',env:{TAVIX_STAGE_REQUIRED:'1'}});
 assert.equal(enforced.TAVIX_STAGE_REQUIRED,'1');
});


test('npm run build cannot report success when required TaviX staging is absent',async()=>{
 const absent=path.join(tmpdir(),'atrium-no-such-tavix-checkout-045');
 const cmd=process.platform==='win32'?'npm.cmd':'npm';
 const result=spawnSync(cmd,['run','build'],{cwd:root,encoding:'utf8',
  shell:process.platform==='win32',
  env:{...process.env,TAVIX_REPOSITORY_DIR:absent,TAVIX_STAGE_REQUIRED:'1'},timeout:30000});
 assert.notEqual(result.status,0,`build incorrectly succeeded: ${result.stdout}`);
 assert.match(result.stdout+result.stderr,/TAVIX_STAGE_REQUIRED/);
});

test('npm run build invokes staging and verifies the output release and index',async()=>{
 const base=await mkdtemp(path.join(tmpdir(),'atrium-tavix-stage-'));
 const repo=path.join(base,'tavix');
 const cmd=process.platform==='win32'?'npm.cmd':'npm';
 try{
  await mkdir(path.join(repo,'tools'),{recursive:true});
  await writeFile(path.join(repo,'project.zr'),'{}\n');
  // Fixture models only repository.py's output shape, not its immutable signing policy.
  // Running it with the Node executable avoids a Python dependency in Node tests.
  await writeFile(path.join(repo,'tools','repository.py'),`const fs=require('node:fs');const path=require('node:path');
  const args=process.argv.slice(2);const get=k=>args[args.indexOf(k)+1];
  const repo=get('--repository'),input=get('--input');
  const src=JSON.parse(fs.readFileSync(path.join(input,'manifest.json'),'utf8'));
  const rel=path.join(repo,'extensions',src.id,src.version);fs.mkdirSync(rel,{recursive:true});
  fs.writeFileSync(path.join(rel,'manifest.json'),JSON.stringify(src));
  fs.writeFileSync(path.join(rel,src.id+'-'+src.version+'.tavix'),'fixture only');
  fs.writeFileSync(path.join(repo,'tavi.repository.json'),JSON.stringify({extensions:[{manifest:src,entrypoint:'https://example.test/extensions/'+src.id+'/'+src.version+'/ui/index.html'}]}));
  `);
  const r=spawnSync(cmd,['run','build'],{cwd:root,encoding:'utf8',
   shell:process.platform==='win32',
   env:{...process.env,TAVIX_REPOSITORY_DIR:repo,TAVIX_STAGE_REQUIRED:'1',TAVIX_PYTHON:process.execPath},timeout:30000});
  assert.equal(r.status,0,`build failed: ${r.stderr}\n${r.stdout}`);
  assert.match(r.stdout,/TAVIX_STAGE_READY/);
  assert.match(r.stdout,/1\.0\.4/);
 }finally{await rm(base,{recursive:true,force:true});}
});
