/** Stage only Atrium's compiled TaviX output into a sibling TaviX Git checkout.
 * Runs after a successful verified build. No git commands or network writes.
 * A missing *optional* sibling checkout never breaks standalone Atrium.
 */
import {existsSync, readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const repo=path.resolve(process.env.TAVIX_REPOSITORY_DIR || path.join(root,'..','tavix'));
const tool=path.join(repo,'tools','repository.py');
const required=process.env.TAVIX_STAGE_REQUIRED==='1';
if(!existsSync(tool)||!existsSync(path.join(repo,'project.zr'))){
 if(required)throw Error(`TAVIX_STAGE_REQUIRED: TaviX checkout unavailable at ${repo}`);
 console.log('TAVIX_STAGE_SKIPPED: optional TaviX repository checkout not found; standalone Atrium build remains valid');
}else{
 const args=[tool,'stage','--repository',repo,'--input',path.join(root,'dist-tavi'),'--source-url','https://github.com/TheBigTreeInc/atrium','--license','NOASSERTION'];
 const proc=spawnSync(process.env.TAVIX_PYTHON || (process.platform==='win32'?'python':'python3'),args,{cwd:root,stdio:'inherit',windowsHide:true});
 if(proc.error)throw proc.error;
 if(proc.status!==0)throw Error(`TaviX post-build stage failed (${proc.status}); source build is valid but no reviewed repository release was staged`);
 // Report success only when the release AND index are in the requested checkout.
 // A successful child exit is not sufficient evidence: a wrong --repository
 // directory or an unexpectedly no-op staging tool must fail the build.
 const sourceManifest=JSON.parse(readFileSync(path.join(root,'dist-tavi','manifest.json'),'utf8'));
 const releasePath=path.join(repo,'extensions',sourceManifest.id,sourceManifest.version);
 const releaseManifestPath=path.join(releasePath,'manifest.json');
 const archivePath=path.join(releasePath,`${sourceManifest.id}-${sourceManifest.version}.tavix`);
 const indexPath=path.join(repo,'tavi.repository.json');
 if (![releaseManifestPath,archivePath,indexPath].every(existsSync)) {
  throw Error(`TAVIX_STAGE_INCOMPLETE: missing release or repository index in ${releasePath}`);
 }
 const releaseManifest=JSON.parse(readFileSync(releaseManifestPath,'utf8'));
 const index=JSON.parse(readFileSync(indexPath,'utf8'));
 // The repository advertises its CURRENT version, not every immutable archive.
 // A repeated offline 1.0.4 build may therefore legitimately return
 // `unchanged` after a reviewed, newer 1.0.5 has become the current entry.
 // Preserve the old archive without downgrading the index or claiming it is
 // currently offered to users. A newer request must still be indexed exactly.
 if (releaseManifest.id!==sourceManifest.id || releaseManifest.version!==sourceManifest.version ||
     !Array.isArray(index.extensions)) {
  throw Error('TAVIX_STAGE_INCOMPLETE: staged manifest or repository catalog invalid');
 }
 const matches=index.extensions.filter(ext=>ext?.manifest?.id===sourceManifest.id);
 if (matches.length!==1) {
  throw Error('TAVIX_STAGE_INCOMPLETE: exactly one catalog entry required for staged extension');
 }
 const published=matches[0];
 const publishedVersion=published.manifest?.version;
 const compare=(left,right)=>{
  if(!/^\d+\.\d+\.\d+$/.test(left)||!/^\d+\.\d+\.\d+$/.test(right)){
   throw Error('TAVIX_STAGE_INCOMPLETE: invalid semantic version in repository index');
  }
  const a=left.split('.').map(Number),b=right.split('.').map(Number);
  for(let i=0;i<3;i++)if(a[i]!==b[i])return Math.sign(a[i]-b[i]);
  return 0;
 };
 const relation=compare(publishedVersion,sourceManifest.version);
 if (typeof published.entrypoint!=='string' ||
     !published.entrypoint.includes(`/extensions/${sourceManifest.id}/${publishedVersion}/`)) {
  throw Error('TAVIX_STAGE_INCOMPLETE: indexed extension entrypoint does not match its version');
 }
 if (relation<0) {
  throw Error('TAVIX_STAGE_INCOMPLETE: index points to an older release than the staged version');
 }
 if (relation>0) {
  // Correct historical behavior: never reinterpret an already-archived
  // unchanged release as an active index promotion.
  console.log(`TAVIX_STAGE_ARCHIVED: ${releasePath} remains immutable; catalog currently advertises ${publishedVersion} (Git review/push required)`);
 } else {
  console.log(`TAVIX_STAGE_READY: ${releasePath} (Git review/push required)`);
 }
}
