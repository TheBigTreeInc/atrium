/** Operator-only staging of a first-party Checkers *preview* into Pages.
 * Does not approve registry releases and refuses to mix this opt-in preview with
 * a live catalog gateway. Never runs automatically on source pushes.
 */
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {parsePublicCatalog,parseCatalogSource} from '../src/catalog_client.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const dist=path.join(root,'dist');
export function bundleCheckers(template,engine,ui) {
  if (!template.includes('/*__ATRIUM_CHECKERS_ENGINE__*/') || !template.includes('/*__ATRIUM_CHECKERS_UI__*/')) throw Error('missing game bundle placeholders');
  if (!engine.includes('export function legalMoves') || !engine.includes('export const initialBoard')) throw Error('unexpected Checkers engine');
  if (/^\s*import /m.test(engine) || /^\s*import /m.test(ui)) throw Error('remote modules forbidden in iframe preview');
  return template.replace('/*__ATRIUM_CHECKERS_ENGINE__*/',engine.replace(/^export /gm,''))
    .replace('/*__ATRIUM_CHECKERS_UI__*/',ui);
}
export async function stageCheckers({baseUrl='https://thebigtreeinc.github.io/atrium/',output=dist}={}) {
  const origin=new URL(baseUrl);
  if(origin.protocol!=='https:'||origin.search||origin.hash||origin.username||origin.password||origin.port||!baseUrl.endsWith('/')||!origin.pathname.endsWith('/atrium/')) throw Error('invalid Pages base URL');
  const config=JSON.parse(await readFile(path.join(output,'catalog-config.json'),'utf8'));
  if(parseCatalogSource(config)!=='./catalog.json')throw Error('never stage static preview while live gateway configured');
  const current=JSON.parse(await readFile(path.join(output,'catalog.json'),'utf8'));
  parsePublicCatalog(current);
  if(current.apps.length||current.allowedOrigins.length)throw Error('staging requires an empty preview catalog');
  const html=bundleCheckers(...await Promise.all([
    'web/games/checkers.template.html','src/checkers_demo_engine.mjs','src/checkers_demo_ui.mjs'
  ].map(name=>readFile(path.join(root,name),'utf8'))));
  const bytes=Buffer.from(html,'utf8');
  if(bytes.length>1024*1024)throw Error('preview exceeds apphost 1 MiB bound');
  const digest=createHash('sha256').update(bytes).digest('hex');
  const entry=new URL(`games/checkers/${digest}/index.html`,baseUrl).href;
  const snapshot={schema:'atrium.catalog-snapshot/v1',allowedOrigins:[origin.origin],apps:[{
    id:'atrium.checkers.preview',title:'Checkers · Local Preview',status:'published',version:'0.1.0-preview',entry,sha256:digest
  }]};
  parsePublicCatalog(snapshot);
  const target=path.join(output,'games','checkers',digest);
  await mkdir(target,{recursive:true});
  await writeFile(path.join(target,'index.html'),bytes);
  await writeFile(path.join(output,'catalog.json'),JSON.stringify(snapshot,null,2)+'\n');
  return {entry,digest,bytes:bytes.length};
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===path.resolve(process.argv[1])){
  if(process.env.ATRIUM_PUBLISH_CHECKERS_DEMO!=='true')throw Error('explicit operator opt-in ATRIUM_PUBLISH_CHECKERS_DEMO=true required');
  const info=await stageCheckers({baseUrl:process.env.ATRIUM_PAGES_BASE_URL||'https://thebigtreeinc.github.io/atrium/'});
  console.log('Staged explicitly approved standalone Checkers Pages preview:',info.digest);
}
