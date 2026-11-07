import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const file=relative=>readFileSync(new URL('../'+relative,import.meta.url),'utf8');
const html=file('web/index.html');
const css=file('web/material-theme.css');
const main=file('web/main.mjs');
const tavi=file('tools/build_tavi_extension.mjs');

test('Material 3 tonal surface, shape and state tokens support light and dark without remote assets',()=>{
 for(const token of ['--md-primary','--md-secondary-container','--md-surface-container-high','--md-on-surface','--md-outline-variant','--md-error-container'])assert(css.includes(token),token);
 assert.match(css,/@media\(prefers-color-scheme:dark\)/);
 assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
 assert.match(html,/href="\.\/material-theme\.css"/);
 assert.doesNotMatch(css,/@import|https?:\/\/|@font-face/);
});
test('phone navigation uses local vectors, Material active indicators and separate Tavi top tabs',()=>{
 for(const view of ['discover','library','lobbies','activity']){
  assert.equal((html.match(new RegExp(`data-view="${view}"`, 'g'))||[]).length,2);
 }
 assert.equal((html.match(/class="nav-icon"/g)||[]).length,8);
 assert.equal((html.match(/<svg viewBox="0 0 24 24" aria-hidden="true">/g)||[]).length,8);
 assert.match(css,/\.bottom-nav \.nav-btn\.active \.nav-icon/);
 assert.match(css,/\.bottom-nav\.tavix-inline-tabs/);
 assert.match(css,/\.tavix-inline-tabs \.nav-btn\.active:after/);
 assert.match(tavi,/layout\.before\(nav\)/);
 assert.match(tavi,/tavix-host-navigation \.topbar\{display:none\}/);
 assert.match(tavi,/copied pinned immutable offline release/);
});
test('real source filters, accessible nav state and connection retry are wired',()=>{
 for(const key of ['all','looprd','release'])assert(html.includes(`data-filter="${key}"`));
 assert.match(main,/card\.dataset\.source!==activeFilter/);
 assert.match(main,/button\.setAttribute\('aria-pressed',String\(selected\)\)/);
 assert.match(main,/button\.setAttribute\('aria-current','page'\)/);
 assert.match(main,/retry\.addEventListener\('click',\(\)=>void refreshCatalog\(\)\)/);
 assert.match(main,/catalogStatus\.dataset\.state='disconnected'/);
 assert.match(main,/if\(categoryChips\)categoryChips\.hidden=count===0/);
 assert.doesNotMatch(html,/For you<\/button>|Multiplayer<\/button>|Strategy<\/button>|Casual<\/button>/);
});
test('static and hosted Tavi builds include shared Material CSS but do not rewrite immutable release',()=>{
 for(const path of ['tools/build.mjs','tools/verify_web.mjs','tools/build_tavi_extension.mjs'])assert.match(file(path),/material-theme\.css/);
 assert.match(tavi,/if\(configuredEndpoint==='\.\/hosted-games\.json' && process\.env\.ATRIUM_TAVIX_DEV_PREVIEW!=='1'\)/);
 assert.match(tavi,/immutable-1\.0\.4\.lock\.json/);
 assert.match(css,/\.chips\[hidden\]\{display:none!important\}/);
});
