import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
const manifest=JSON.parse(fs.readFileSync('extensions/tavi/manifest.json','utf8'));
test('TaviX extension uses immutable 1.0.4 and only panel permission',()=>{
 assert.equal(manifest.schema,'tavi.extension/v1');assert.equal(manifest.version,'1.0.4');
 assert.deepEqual(manifest.permissions,['ui.panel']);assert.equal(manifest.hostApi.min,'1.0.0');
});
test('TaviX SDK is used for scoped navigation, not a private host broker',()=>{
 const bridge=fs.readFileSync('extensions/tavi/extension-bridge.mjs','utf8');
 const sdk=fs.readFileSync('extensions/tavi/tavix-sdk.mjs','utf8');
 assert.match(bridge,/createTaviXSDK/);assert.match(bridge,/tavi\.navigation\.close\(\)/);
 assert.match(bridge,/tavix\.surface\/v1/);assert.match(bridge,/requestGameLaunch/);
 assert.match(sdk,/TAVIX_STANDARD='tavix\/1.0'/);
 assert.doesNotMatch(bridge,/window\.parent\.postMessage|Bearer\s|localStorage|sessionStorage|Authorization:/);
});
test('one shared Atrium web source, with SDK packaged as extension-only asset',()=>{
 const builder=fs.readFileSync('tools/build_tavi_extension.mjs','utf8');
 assert.match(builder,/cp\(path.join\(web,'src'\),path.join\(dest,'src'\)/);
 assert.match(builder,/tavix-sdk\.mjs/);
 assert.doesNotMatch(builder,/mock_life_api.*writeFile/);
});
