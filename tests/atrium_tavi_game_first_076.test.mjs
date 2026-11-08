import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');
const html=read('web/index.html');
const css=read('web/material-theme.css');
const main=read('web/main.mjs');
const builder=read('tools/build_tavi_extension.mjs');

test('embedded Atrium starts with My games, keeping standalone Discover',()=>{
 assert.match(main,/if\(document\.body\.classList\.contains\('tavix-extension'\)\)showView\('library'\)/);
 assert.match(html,/data-view-panel="discover"/);
 assert.match(html,/data-view-panel="library" hidden/);
 assert.match(html,/class="bottom-nav"/);
});
test('Tavi uses a compact two-tab secondary navigation rather than duplicate footers',()=>{
 assert.match(css,/body\.tavix-extension \.bottom-nav\.tavix-inline-tabs\{\s*grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
 assert.match(css,/body\.tavix-extension \.tavix-inline-tabs \.nav-btn\[data-view="activity"\]\{display:none\}/);
 assert.match(css,/body\.tavix-extension \.topbar\{display:none\}/);
 assert.match(css,/body\.tavix-extension \.rail\{display:none\}/);
});
test('embedded appearance does not accidentally inherit OS dark mode when host chrome is light',()=>{
 assert.match(css,/body\.tavix-extension\{\s*color-scheme:light/);
 assert.match(css,/--md-surface:#f7fbf6/);
 assert.match(css,/html:has\(> body\.tavix-extension\)\{color-scheme:light/);
});
test('empty activity and lobbies tell the truth and let players browse',()=>{
 assert.match(html,/Game activity is coming/);
 assert.match(html,/check Tavi for notifications/);
 assert.match(html,/Lobbies are on their way/);
 assert.equal((html.match(/data-view-target="discover"/g)||[]).length,2);
 assert.doesNotMatch(html,/Nothing needs your attention/);
 assert.match(html,/class="footnote trust-notes"/);
 assert.match(html,/<summary>How games are protected<\/summary>/);
 assert.match(main,/function appendDiscoverAction\(/);
 assert.match(main,/Installed games in Tavi/);
});
test('new local preview is versioned without mutating frozen 1.0.4 or reviewed hosted 1.0.6',()=>{
 assert.match(builder,/version:'1\.0\.10'/);
 assert.match(builder,/immutable-1\.0\.4\.lock\.json/);
 assert.equal(JSON.parse(read('extensions/tavi/hosted-release.json')).version,'1.0.6');
});
