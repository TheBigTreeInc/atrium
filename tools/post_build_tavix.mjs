/** ZipRunner post-build: compile the Atrium extension and stage it in TaviX.
 *
 * The earlier ZipRunner recipe already runs `npm run build` and `npm run verify`.
 * On Windows this process applies the same effective environment as:
 *   $env:TAVIX_REPOSITORY_DIR = "C:\\Users\\dorbi\\source\\tavix"
 *   $env:TAVIX_STAGE_REQUIRED = "1"
 * when Atrium is checked out at C:\\Users\\dorbi\\source\\atrium.
 *
 * All Git publication/approval stays in the separate tavix ZipRunner project.
 */
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {tavixPostBuildEnvironment} from './tavix_post_build_config.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const env = tavixPostBuildEnvironment(root);
console.log(`[atrium-post-build] TAVIX_REPOSITORY_DIR=${env.TAVIX_REPOSITORY_DIR}`);
console.log(`[atrium-post-build] TAVIX_STAGE_REQUIRED=${env.TAVIX_STAGE_REQUIRED}`);
for (const script of ['build_tavi_extension.mjs', 'stage_tavix.mjs']) {
 console.log(`[atrium-post-build] node tools/${script}`);
 const result = spawnSync(process.execPath, [path.join(root, 'tools', script)], {
  cwd: root, env, stdio: 'inherit', windowsHide: true,
 });
 if (result.error) throw result.error;
 if (result.status !== 0) {
  console.error(`[atrium-post-build] FAILED: tools/${script} (exit ${result.status ?? 'unknown'})`);
  process.exit(result.status || 1);
 }
}
console.log('[atrium-post-build] Extension build/staging completed. Review and push the TaviX project separately.');
