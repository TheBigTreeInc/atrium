import {cp,readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const web=path.join(root,'dist');
const dest=path.join(root,'dist-tavi','ui');
await rm(path.join(root,'dist-tavi'),{recursive:true,force:true});
await mkdir(dest,{recursive:true});
for (const name of ['index.html','main.mjs','catalog.json','catalog-config.json','hosted-games.json','hosted-config.json','.nojekyll']) await cp(path.join(web,name),path.join(dest,name));
await cp(path.join(web,'src'),path.join(dest,'src'),{recursive:true});
const html=await readFile(path.join(dest,'index.html'),'utf8');
const insert=`<button id="returnTavi" type="button" style="position:fixed;right:10px;top:9px;z-index:999;background:#267c69;color:white;border:2px solid #b1ded1;border-radius:8px;min-height:42px">← Return to Tavi</button>`;
// Ensure a single shared UI source; the extension adds only host navigation glue.
// Register Tavi host broker before the shared UI builds Life launch cards.
const result=html.replace('<body>','<body>'+insert).replace('<script type="module" src="./main.mjs"></script>', '<script type="module" src="./extension-bridge.mjs"></script><script type="module" src="./main.mjs"></script>');
if(result===html||!result.includes('returnTavi')) throw Error('Unable to inject Tavi host control');
await writeFile(path.join(dest,'index.html'),result);
await cp(path.join(root,'extensions/tavi/extension-bridge.mjs'),path.join(dest,'extension-bridge.mjs'));
await cp(path.join(root,'extensions/tavi/manifest.json'),path.join(root,'dist-tavi','manifest.json'));
console.log('Tavi extension built from shared Atrium static UI');
