import {cp,readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseHostedCatalogSource} from '../src/hosted_catalog.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const web=path.join(root,'dist');
const dest=path.join(root,'dist-tavi','ui');
// The previously published 1.0.4 payload is immutable. Recompiling it from
// evolving shared UI sources would change bytes and fail a real TaviX checkout.
const configured=JSON.parse(await readFile(path.join(web,'hosted-config.json'),'utf8'));
const configuredEndpoint=parseHostedCatalogSource(configured);
// Opt-in *build only*: this is an unapproved candidate for TaviX repository
// review, not a developer shadow and not an implicit source-trust grant.
const reviewCandidate=process.env.ATRIUM_TAVIX_REVIEW_CANDIDATE==='1';
if(reviewCandidate && process.env.ATRIUM_TAVIX_DEV_PREVIEW==='1')throw Error('Review candidate and developer preview are mutually exclusive');
if(reviewCandidate && configuredEndpoint!=='./hosted-games.json')throw Error('Offline installed-games candidate requires the healthy empty catalog; use the separately reviewed hosted release path for live endpoints');
if(configuredEndpoint==='./hosted-games.json' && process.env.ATRIUM_TAVIX_DEV_PREVIEW!=='1' && !reviewCandidate){
 const frozen=path.join(root,'extensions','tavi','immutable-1.0.4');
 const lock=JSON.parse(await readFile(path.join(root,'extensions','tavi','immutable-1.0.4.lock.json'),'utf8'));
 if(lock.schema!=='atrium.tavix.immutable-lock/v1'||lock.version!=='1.0.4')throw Error('Invalid historical TaviX lock');
 const {createHash}=await import('node:crypto');
 const {readdir}=await import('node:fs/promises');
 const relative=[];
 async function walk(dir,prefix=''){
  for(const entry of await readdir(dir,{withFileTypes:true})){
   const sub=prefix?prefix+'/'+entry.name:entry.name;
   if(entry.isDirectory())await walk(path.join(dir,entry.name),sub);
   else if(entry.isFile())relative.push(sub);
   else throw Error('Unexpected immutable release entry');
  }
 }
 await walk(frozen);
 if(relative.length!==Object.keys(lock.files).length)throw Error('Frozen TaviX file count changed');
 for(const file of relative){
  const expected=lock.files[file];
  if(!/^[a-f0-9]{64}$/.test(expected||''))throw Error('Unpinned frozen TaviX file');
  if(createHash('sha256').update(await readFile(path.join(frozen,...file.split('/')))).digest('hex')!==expected)
   throw Error('Frozen TaviX file checksum changed: '+file);
 }
 await rm(path.join(root,'dist-tavi'),{recursive:true,force:true});
 await cp(frozen,path.join(root,'dist-tavi'),{recursive:true});
 console.log('Atrium TaviX 1.0.4: copied pinned immutable offline release; no shared UI rebuild');
}else{
await rm(path.join(root,'dist-tavi'),{recursive:true,force:true});
await mkdir(dest,{recursive:true});
for (const name of ['index.html','material-theme.css','main.mjs','catalog.json','catalog-config.json','tavix-games.json','hosted-games.json','hosted-config.json']) await cp(path.join(web,name),path.join(dest,name));
await cp(path.join(web,'src'),path.join(dest,'src'),{recursive:true});
const html=await readFile(path.join(dest,'index.html'),'utf8');
const insert=`<button id="returnTavi" type="button" class="tavi-return" hidden>← Return to Tavi</button>`;
// Ensure a single shared UI source; the extension adds only host navigation glue.
// Register Tavi host broker before the shared UI builds Life launch cards.
const result=html.replace('<body>','<body class="tavix-extension">'+insert).replace('<script type="module" src="./main.mjs"></script>', '<script type="module" src="./extension-bridge.mjs"></script><script type="module" src="./main.mjs"></script>');
if(result===html||!result.includes('returnTavi')) throw Error('Unable to inject Tavi host control');

// Extension-specific compact presentation. The standalone Atrium Pages UI is
// untouched; Tavi owns its own header and navigation when embedded.
// Only in a new configured hosted TaviX extension: place Atrium sections
// under Tavi's own header instead of stacking two bottom navigation bars.
// This module is never injected into the immutable offline 1.0.4 release.
await writeFile(path.join(dest,'atrium-tavi-layout.mjs'), `const nav=document.querySelector('.bottom-nav');
const layout=document.querySelector('.layout');
if(nav&&layout){layout.before(nav);nav.classList.add('tavix-inline-tabs');
 nav.setAttribute('aria-label','Atrium sections');}
`);
await writeFile(path.join(dest,'index.html'),result.replace('</head>',
 '<script type="module" src="./atrium-tavi-layout.mjs"></script></head>'));
// This bridge contains only behavior not already defined by shared Material theme.
// An existing Tavi host owns header/footer and navigation-close; no extra app bar.
const compactCSS=`<style id="atrium-tavix-compact">
.tavix-extension.tavix-host-navigation .topbar{display:none}
.tavix-extension #mockLobbySection{display:none}
.tavix-extension .tavi-return:not([hidden]){display:inline-flex;align-items:center;position:fixed;right:12px;top:9px;z-index:999;min-height:42px;padding:0 16px;border:1px solid var(--md-outline-variant);border-radius:999px;background:var(--md-secondary-container);color:var(--md-on-secondary-container);font-weight:700}
</style>`;
await writeFile(path.join(dest,'index.html'),(await readFile(path.join(dest,'index.html'),'utf8')).replace('</head>',compactCSS+'</head>'));

const bridge=await readFile(path.join(root,'extensions/tavi/extension-bridge.mjs'),'utf8');
if(!bridge.includes("../../src/hosted_catalog.mjs"))throw Error('Trusted catalog source import missing in TaviX bridge');
await writeFile(path.join(dest,'extension-bridge.mjs'),bridge.replace("../../src/hosted_catalog.mjs","./src/hosted_catalog.mjs"));
await cp(path.join(root,'extensions/tavi/tavix-sdk.mjs'),path.join(dest,'tavix-sdk.mjs'));
await cp(path.join(root,'extensions/tavi/installed-games.mjs'),path.join(dest,'installed-games.mjs'));
for(const file of ['atrium-assets.mjs','tavi-assets-client-0.1.11.mjs'])await cp(path.join(root,'extensions/tavi',file),path.join(dest,file));
// A live public catalog is a different immutable TaviX release. Preserve the
// existing 1.0.4 bytes when the operator has not configured an approved URL.
// Version for a future live release is explicit source-controlled metadata, not
// chosen by runtime state, browser input, or a generic LoopRD manifest.
const endpoint=configuredEndpoint;
const baseManifest=JSON.parse(await readFile(path.join(root,'extensions/tavi/manifest.json'),'utf8'));
let extensionManifest=baseManifest;
if(endpoint!=='./hosted-games.json' || process.env.ATRIUM_TAVIX_DEV_PREVIEW==='1' || reviewCandidate){
 const release=reviewCandidate
  ? JSON.parse(await readFile(path.join(root,'extensions/tavi/installed-games-candidate.json'),'utf8'))
  : process.env.ATRIUM_TAVIX_DEV_PREVIEW==='1' ? {schema:'atrium.tavix.hosted-release/v1',version:'1.0.10'}
  : JSON.parse(await readFile(path.join(root,'extensions/tavi/hosted-release.json'),'utf8'));
 const expectedSchema=reviewCandidate?'atrium.tavix.review-candidate/v1':'atrium.tavix.hosted-release/v1';
 if(release.schema!==expectedSchema ||
    Object.keys(release).some(key=>!['schema','version'].includes(key)) ||
    !/^\d+\.\d+\.\d+$/.test(release.version) ||
    !/^\d+\.\d+\.\d+$/.test(baseManifest.version)){
  throw Error('Invalid dedicated hosted TaviX release metadata');
 }
 const current=baseManifest.version.split('.').map(Number);
 const next=release.version.split('.').map(Number);
 const differing=next.findIndex((n,i)=>n!==current[i]);
 if(differing===-1 || next[differing]<current[differing]){
  throw Error('Hosted TaviX version must increase monotonically');
 }
 extensionManifest={...baseManifest,version:release.version};
}
await writeFile(path.join(root,'dist-tavi','manifest.json'),JSON.stringify(extensionManifest,null,2)+'\n');
console.log(`Atrium TaviX ${extensionManifest.version}: ${reviewCandidate?'unapproved offline installed-games review candidate (NOT staged or trusted)':process.env.ATRIUM_TAVIX_DEV_PREVIEW==='1'?'explicit developer preview':'operator-configured hosted extension'}`);
console.log('Tavi extension built from shared Atrium static UI');

}
