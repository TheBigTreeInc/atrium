import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
const manifest=JSON.parse(fs.readFileSync('extensions/tavi/manifest.json','utf8'));
test('current Tavi API v1 permissions only',()=>{assert.equal(manifest.schema,'tavi.extension/v1');assert.deepEqual(manifest.permissions,['ui.panel']);assert.equal(manifest.hostApi.min,'1.0.0');});
test('extension only closes its panel, not Social',()=>{const bridge=fs.readFileSync('extensions/tavi/extension-bridge.mjs','utf8');assert.match(bridge,/hostCall\('ui.close'\)/);assert.doesNotMatch(bridge,/Bearer\s|localStorage|sessionStorage|Authorization:/);});
test('one shared Atrium web source',()=>{const builder=fs.readFileSync('tools/build_tavi_extension.mjs','utf8');assert.match(builder,/cp\(path.join\(web,'src'\),path.join\(dest,'src'\)/);assert.doesNotMatch(builder,/mock_life_api.*writeFile/);});
