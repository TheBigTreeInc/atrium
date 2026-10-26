import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,mkdir,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {tavixPostBuildEnvironment} from '../tools/tavix_post_build_config.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');


/** A test-only sibling TaviX repository: NEVER stage to the operator checkout. */
async function fakeTavixRepository(base) {
 const repo=path.join(base,'tavix');
 await mkdir(path.join(repo,'tools'),{recursive:true});
 await writeFile(path.join(repo,'project.zr'),'{}\n');
 // Intentionally a JS fixture invoked via TAVIX_PYTHON=node; never publish
 // or validate a real TaviX archive with this implementation.
 await writeFile(path.join(repo,'tools','repository.py'),`const fs=require('node:fs');const path=require('node:path');
  const args=process.argv.slice(2);const get=k=>args[args.indexOf(k)+1];
  const repo=get('--repository'),input=get('--input');
  const src=JSON.parse(fs.readFileSync(path.join(input,'manifest.json'),'utf8'));
  const rel=path.join(repo,'extensions',src.id,src.version);fs.mkdirSync(rel,{recursive:true});
  const manifestPath=path.join(rel,'manifest.json');
  if(fs.existsSync(manifestPath)) {
   if(JSON.stringify(JSON.parse(fs.readFileSync(manifestPath,'utf8')))!==JSON.stringify(src)) {
    console.error('IMMUTABLE_RELEASE_CONFLICT');process.exit(2);
   }
  } else {fs.writeFileSync(manifestPath,JSON.stringify(src));}
  const archive=path.join(rel,src.id+'-'+src.version+'.tavix');
  if(!fs.existsSync(archive))fs.writeFileSync(archive,'immutable fixture archive: '+src.version);
  const indexPath=path.join(repo,'tavi.repository.json');
  const old=fs.existsSync(indexPath)?JSON.parse(fs.readFileSync(indexPath,'utf8')):null;
  const older=old?.extensions?.find(e=>e.manifest?.id===src.id);
  const compare=(a,b)=>{const x=a.split('.').map(Number),y=b.split('.').map(Number);for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]-y[i];return 0};
  if(!older||compare(src.version,older.manifest.version)>0){
   const entry={manifest:src,entrypoint:'https://example.test/extensions/'+src.id+'/'+src.version+'/ui/index.html'};
   fs.writeFileSync(indexPath,JSON.stringify({schema:'tavi.repository/v1',extensions:[entry]}));
  }
  process.stdout.write(JSON.stringify({id:src.id,version:src.version,status:older?'unchanged':'added'})+'\\n');
  `);
 return repo;
}
function digest(bytes){return createHash('sha256').update(bytes).digest('hex');}

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
  await fakeTavixRepository(base);
  const r=spawnSync(cmd,['run','build'],{cwd:root,encoding:'utf8',
   shell:process.platform==='win32',
   env:{...process.env,TAVIX_REPOSITORY_DIR:repo,TAVIX_STAGE_REQUIRED:'1',TAVIX_PYTHON:process.execPath},timeout:30000});
  assert.equal(r.status,0,`build failed: ${r.stderr}\n${r.stdout}`);
  assert.match(r.stdout,/TAVIX_STAGE_READY/);
  assert.match(r.stdout,/1\.0\.4/);
 }finally{await rm(base,{recursive:true,force:true});}
});

test('configuration is ordered before compilation and version selection is source controlled',async()=>{
 const launcher=await readFile(path.join(root,'tools/post_build_tavix.mjs'),'utf8');
 const configureAt=launcher.indexOf("'configure_hosted_catalog.mjs'");
 const compileAt=launcher.indexOf("'build_tavi_extension.mjs'");
 const stageAt=launcher.indexOf("'stage_tavix.mjs'");
 assert(configureAt>=0 && configureAt<compileAt && compileAt<stageAt);
 const release=JSON.parse(await readFile(path.join(root,'extensions/tavi/hosted-release.json'),'utf8'));
 assert.equal(release.schema,'atrium.tavix.hosted-release/v1');
 assert.equal(release.version,'1.0.6');
 const builder=await readFile(path.join(root,'tools/build_tavi_extension.mjs'),'utf8');
 assert.match(builder,/hosted-release\.json/);
 assert.match(builder,/parseHostedCatalogSource/);
 assert.match(builder,/extensionManifest=\{\.\.\.baseManifest,version:release.version\}/);
});

test('approved HTTPS hosted gateway creates separate 1.0.6, never mutates offline 1.0.4',async()=>{
 const base=await mkdtemp(path.join(tmpdir(),'atrium-hosted-stage-'));
 const repo=await fakeTavixRepository(base);
 const cmd=process.platform==='win32'?'npm.cmd':'npm';
 const url='https://catalog.operator-games.net/hosted-games.json';
 const preload=path.join(base,'public-preflight.cjs');
 await writeFile(preload,`globalThis.fetch=async(url,options)=>{
  if(url!==${JSON.stringify(url)})throw Error('unexpected preflight URL');
  if(options.credentials!=='omit'||options.redirect!=='error'||options.cache!=='no-store')throw Error('unsafe preflight');
  return {ok:true,status:200,headers:{get(name){return {'content-type':'application/json','cache-control':'no-store','access-control-allow-origin':'*'}[name]||null;}},json:async()=>({schema:'atrium.hosted-games/v1',games:[{
   gameId:'life.loop',title:'Life',publisherId:'thebigtreeinc',deploymentId:'verified-life',component:'the-life-loop',
   launchUrl:'https://thebigtreeinc.github.io/life/',apiBaseUrl:'https://api.trusted-games.net/looprd/the-life-loop/v1',sourceRevision:'${'a'.repeat(40)}',approved:true,status:'published',embedAllowed:false
  }]})};
 };`);
 const opts={cwd:root,encoding:'utf8',shell:process.platform==='win32',timeout:40000};
 // On Windows the required flag cannot be disabled. Every command here stages
 // solely in the temporary TaviX fixture. Tests never change C:\...\tavix.
 const env={...process.env,TAVIX_REPOSITORY_DIR:repo,TAVIX_PYTHON:process.execPath,TAVIX_STAGE_REQUIRED:'1'};
 const testEnv={...env,NODE_OPTIONS:[env.NODE_OPTIONS||'',`--require=${preload}`].filter(Boolean).join(' ')};
 try {
  const missing=spawnSync(cmd,['run','build'],{...opts,env:{...env,ATRIUM_PUBLIC_HOSTED_CATALOG_URL:'',ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG:'1'}});
  assert.notEqual(missing.status,0,'must not stage an empty 1.0.6 release');
  assert.match(missing.stdout+missing.stderr,/ATRIUM_PUBLIC_HOSTED_CATALOG_URL is required/);
  const unsafe=spawnSync(cmd,['run','build'],{...opts,env:{...env,ATRIUM_PUBLIC_HOSTED_CATALOG_URL:'https://example.org/hosted-games.json?token=unsafe',ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG:'1'}});
  assert.notEqual(unsafe.status,0,'must reject credential-bearing gateway URL');
  const good=spawnSync(cmd,['run','build'],{...opts,env:{...testEnv,ATRIUM_PUBLIC_HOSTED_CATALOG_URL:url,ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG:'1'}});
  assert.equal(good.status,0,`approved hosted build failed: ${good.stderr}\n${good.stdout}`);
  assert.match(good.stdout,/Verified live anonymous hosted catalog/);
  const reserved=spawnSync(cmd,['run','build'],{...opts,env:{...testEnv,ATRIUM_PUBLIC_HOSTED_CATALOG_URL:'https://atrium.example.org/hosted-games.json',ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG:'1'}});
  assert.notEqual(reserved.status,0,'reserved documentation hostname cannot stage');
  assert.match(reserved.stdout+reserved.stderr,/Unapproved hosted catalog gateway URL/);
  const cfg=JSON.parse(await readFile(path.join(root,'dist-tavi/ui/hosted-config.json'),'utf8'));
  const live=JSON.parse(await readFile(path.join(root,'dist-tavi/manifest.json'),'utf8'));
  assert.equal(cfg.gatewayUrl,url);
  assert.equal(live.version,'1.0.6');
  assert.match(good.stdout,/TaviX 1\.0\.6/);
  assert.match(good.stdout,/TAVIX_STAGE_READY/);
  const archived105=path.join(repo,'extensions',live.id,'1.0.6',`${live.id}-1.0.6.tavix`);
  const before=digest(await readFile(archived105));
  const normal=spawnSync(cmd,['run','build'],{...opts,env:{...env,ATRIUM_PUBLIC_HOSTED_CATALOG_URL:'',ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG:'0'}});
  assert.equal(normal.status,0,`default build failed: ${normal.stderr}\n${normal.stdout}`);
  const normalCfg=JSON.parse(await readFile(path.join(root,'dist-tavi/ui/hosted-config.json'),'utf8'));
  const original=JSON.parse(await readFile(path.join(root,'dist-tavi/manifest.json'),'utf8'));
  assert.equal(normalCfg.gatewayUrl,'');
  assert.equal(original.version,'1.0.4');
  assert.match(normal.stdout,/TAVIX_STAGE_ARCHIVED/, 'older immutable release is not the catalog current version');
  const current=JSON.parse(await readFile(path.join(repo,'tavi.repository.json'),'utf8'));
  assert.equal(current.extensions[0].manifest.version,'1.0.6','offline rebuild must not downgrade the hosted catalog');
  assert.equal(digest(await readFile(archived105)),before,'hosted 1.0.6 archive must remain immutable');
 } finally { await rm(base,{recursive:true,force:true}); }
});

// Even if a repository process exits zero, its catalog may not be stale or
// missing. A future (higher) staged release must be indexed precisely.
test('stage verification rejects an index older than the requested release',async()=>{
 const base=await mkdtemp(path.join(tmpdir(),'atrium-tavix-stale-'));
 const repo=await fakeTavixRepository(base);
 const tempRoot=path.join(base,'atrium');
 const tempTool=path.join(tempRoot,'tools','stage_tavix.mjs');
 try {
  // Use an isolated project directory so this test cannot change the normal
  // dist or dist-tavi output, nor any operator's TaviX Git checkout.
  await mkdir(path.dirname(tempTool),{recursive:true});
  await writeFile(tempTool,await readFile(path.join(root,'tools','stage_tavix.mjs')));
  const src={...JSON.parse(await readFile(path.join(root,'extensions/tavi/manifest.json'),'utf8')),version:'1.0.6'};
  const dist=path.join(tempRoot,'dist-tavi');await mkdir(dist,{recursive:true});
  await writeFile(path.join(dist,'manifest.json'),JSON.stringify(src));
  // Simulate a repository implementation falsely exiting success without
  // updating its index. The staged 1.0.6 archive exists but 1.0.4 is current.
  const dir=path.join(repo,'extensions',src.id,src.version);await mkdir(dir,{recursive:true});
  await writeFile(path.join(dir,'manifest.json'),JSON.stringify(src));
  await writeFile(path.join(dir,src.id+'-'+src.version+'.tavix'),'fixture');
  const old={...src,version:'1.0.4'};
  await writeFile(path.join(repo,'tavi.repository.json'),JSON.stringify({extensions:[{manifest:old,entrypoint:'https://example.test/extensions/'+src.id+'/1.0.4/ui/index.html'}]}));
  await writeFile(path.join(repo,'tools','repository.py'),"process.stdout.write('noop fixture\\n');\n");
  const stage=spawnSync(process.execPath,[tempTool],{cwd:tempRoot,encoding:'utf8',env:{...process.env,TAVIX_REPOSITORY_DIR:repo,TAVIX_STAGE_REQUIRED:'1',TAVIX_PYTHON:process.execPath}});
  assert.notEqual(stage.status,0,'stale TaviX catalog must fail closed');
  assert.match(stage.stdout+stage.stderr,/index points to an older release/);
 }finally{await rm(base,{recursive:true,force:true});}
});

test('offline 1.0.4 assets are checksum-pinned and never regenerated from changing shared UI',async()=>{
 const lock=JSON.parse(await readFile(path.join(root,'extensions/tavi/immutable-1.0.4.lock.json'),'utf8'));
 assert.equal(lock.version,'1.0.4');
 assert.equal(Object.keys(lock.files).length,17);
 for(const [name,hash] of Object.entries(lock.files)){
  assert.equal(digest(await readFile(path.join(root,'extensions/tavi/immutable-1.0.4',name))),hash);
 }
 const script=await readFile(path.join(root,'tools/build_tavi_extension.mjs'),'utf8');
 assert.match(script,/copied pinned immutable offline release/);
 assert.match(script,/Frozen TaviX file checksum changed/);
});
