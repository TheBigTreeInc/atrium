import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const bridge=fs.readFileSync('extensions/tavi/extension-bridge.mjs','utf8');
const cards=fs.readFileSync('src/hosted_cards.mjs','utf8');
test('Tavi 0.3.66 launch requires feature negotiation and user approval',()=>{assert.match(bridge,/atrium.tavi-launch\/v1/);assert.match(bridge,/ui.requestGameLaunch/);assert.match(bridge,/awaitingApproval/);assert.match(bridge,/host.info/);});
test('hosted card refreshes approval before Tavi request',()=>{assert.match(cards,/fetchConfiguredHostedCatalog\(fetcher\)/);assert.match(cards,/JSON.stringify\(current\)!==JSON.stringify\(game\)/);assert.match(cards,/launchThroughTavi\(current.launchUrl,matchId\)/);});
test('no tokens or popup privilege in Tavi bridge',()=>{assert.doesNotMatch(bridge,/window.open|location.assign|Bearer\s|localStorage|sessionStorage|allow-popups/);});
