import {cp,readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const web=path.join(root,'dist');
const dest=path.join(root,'dist-tavi','ui');
await rm(path.join(root,'dist-tavi'),{recursive:true,force:true});
await mkdir(dest,{recursive:true});
for (const name of ['index.html','main.mjs','catalog.json','catalog-config.json','hosted-games.json','hosted-config.json']) await cp(path.join(web,name),path.join(dest,name));
await cp(path.join(web,'src'),path.join(dest,'src'),{recursive:true});
const html=await readFile(path.join(dest,'index.html'),'utf8');
const insert=`<button id="returnTavi" type="button" style="position:fixed;right:10px;top:9px;z-index:999;background:#267c69;color:white;border:2px solid #b1ded1;border-radius:8px;min-height:42px">← Return to Tavi</button>`;
// Ensure a single shared UI source; the extension adds only host navigation glue.
// Register Tavi host broker before the shared UI builds Life launch cards.
const result=html.replace('<body>','<body class="tavix-extension">'+insert).replace('<script type="module" src="./main.mjs"></script>', '<script type="module" src="./extension-bridge.mjs"></script><script type="module" src="./main.mjs"></script>');
if(result===html||!result.includes('returnTavi')) throw Error('Unable to inject Tavi host control');

// Extension-specific compact presentation. The standalone Atrium Pages UI is
// untouched; Tavi owns its own header and navigation when embedded.
const compactCSS=`<style id="atrium-tavix-compact">
.tavix-extension .hero{display:none}
.tavix-extension #mockLobbySection{display:none}
.tavix-extension .layout{max-width:none;margin:0;padding:10px}
.tavix-extension .content{padding-bottom:calc(82px + env(safe-area-inset-bottom))}
.tavix-extension .section{margin-top:12px}
.tavix-extension .section-head{margin:0 0 8px}
.tavix-extension .grid{gap:10px}
.tavix-extension .game-card{border-radius:18px}
.tavix-extension .cover{height:100px}
.tavix-extension .card-actions{flex-wrap:wrap}
.tavix-extension .game-card input{min-width:0;max-width:100%;min-height:44px}
.tavix-extension .launch-status{font-size:13px;color:#c5e8d4;line-height:1.4;margin:8px 0}
.tavix-extension.tavix-host-navigation .topbar{display:none}
@media(max-width:650px){.tavix-extension .layout{padding:6px max(8px,env(safe-area-inset-right)) calc(76px + env(safe-area-inset-bottom)) max(8px,env(safe-area-inset-left))}.tavix-extension .cover{height:80px}.tavix-extension .card-body{padding:12px}.tavix-extension .bottom-nav{left:5px;right:5px;bottom:max(5px,env(safe-area-inset-bottom))}.tavix-extension #stage iframe{height:calc(100dvh - 120px);min-height:320px}}
</style>`;
await writeFile(path.join(dest,'index.html'),result.replace('</head>',compactCSS+'</head>'));

const bridge=await readFile(path.join(root,'extensions/tavi/extension-bridge.mjs'),'utf8');
if(!bridge.includes("../../src/hosted_catalog.mjs"))throw Error('Trusted catalog source import missing in TaviX bridge');
await writeFile(path.join(dest,'extension-bridge.mjs'),bridge.replace("../../src/hosted_catalog.mjs","./src/hosted_catalog.mjs"));
await cp(path.join(root,'extensions/tavi/tavix-sdk.mjs'),path.join(dest,'tavix-sdk.mjs'));
await cp(path.join(root,'extensions/tavi/manifest.json'),path.join(root,'dist-tavi','manifest.json'));
console.log('Tavi extension built from shared Atrium static UI');
