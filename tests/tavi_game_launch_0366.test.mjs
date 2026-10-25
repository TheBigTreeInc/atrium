import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const bridge=fs.readFileSync('extensions/tavi/extension-bridge.mjs','utf8');
const cards=fs.readFileSync('src/hosted_cards.mjs','utf8');
test('TaviX advertised surface first, Life-only opt-in legacy fallback',()=>{
 assert.match(bridge,/tavix.surface\/v1/);assert.match(bridge,/assertTaviXHostInfo/);
 assert.match(bridge,/atrium.tavi-launch\/v1/);assert.match(bridge,/ui.requestGameLaunch/);
 assert.match(bridge,/awaitingApproval/);assert.match(bridge,/tavi.info\(/);
});
test('hosted game refreshes publication before Tavi surface or browser',()=>{
 assert.match(cards,/fetchConfiguredHostedCatalog\(fetcher\)/);
 assert.match(cards,/JSON.stringify\(current\)!==JSON.stringify\(game\)/);
 assert.match(cards,/surfaceLaunch\(game.gameId,game.deploymentId,current.launchUrl,matchId\)/);
 assert.match(cards,/browser.addEventListener\('click'/);
 assert.doesNotMatch(cards,/if\(!opened\)openExternal/);
});
test('no bearer tokens or popup privilege in TaviX bridge',()=>{
 assert.doesNotMatch(bridge,/window.open|location.assign|Bearer\s|localStorage|sessionStorage|allow-popups/);
});
