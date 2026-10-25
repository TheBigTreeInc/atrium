/** Stage only Atrium's compiled TaviX output into a sibling TaviX Git checkout.
 * Runs after a successful verified build. No git commands or network writes.
 * A missing *optional* sibling checkout never breaks standalone Atrium.
 */
import {existsSync} from 'node:fs';
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
 console.log('TAVIX_STAGE_READY: review/push changes through the separate tavix ZipRunner Git project');
}
