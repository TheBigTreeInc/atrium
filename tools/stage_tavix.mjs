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
 if (releaseManifest.id!==sourceManifest.id || releaseManifest.version!==sourceManifest.version ||
     !Array.isArray(index.extensions) ||
     !index.extensions.some(ext=>ext.manifest?.id===sourceManifest.id &&
       ext.manifest?.version===sourceManifest.version &&
       typeof ext.entrypoint==='string' &&
       ext.entrypoint.includes(`/extensions/${sourceManifest.id}/${sourceManifest.version}/`))) {
  throw Error('TAVIX_STAGE_INCOMPLETE: staged manifest or catalog does not match requested extension version');
 }
 console.log(`TAVIX_STAGE_READY: ${releasePath} (Git review/push required)`);
}
