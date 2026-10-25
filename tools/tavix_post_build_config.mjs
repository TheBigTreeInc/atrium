/** Resolve Atrium's post-build TaviX policy without hardcoding operator machine paths.
 * On Windows, ZipRunner MUST stage the compiled release into the adjacent TaviX
 * Git checkout. CI and independent non-Windows checkouts may build without it.
 */
import path from 'node:path';

export function tavixPostBuildEnvironment(projectRoot, {platform = process.platform, env = process.env} = {}) {
 if (typeof projectRoot !== 'string' || !projectRoot) throw Error('Atrium source root is required');
 const paths = platform === 'win32' ? path.win32 : path.posix;
 const requested = typeof env.TAVIX_REPOSITORY_DIR === 'string' ? env.TAVIX_REPOSITORY_DIR.trim() : '';
 const repository = requested
  ? paths.resolve(projectRoot, requested)
  : paths.resolve(projectRoot, '..', 'tavix');
 const required = platform === 'win32' || env.TAVIX_STAGE_REQUIRED === '1';
 return {
  ...env,
  TAVIX_REPOSITORY_DIR: repository,
  TAVIX_STAGE_REQUIRED: required ? '1' : '0',
 };
}
