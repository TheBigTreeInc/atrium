import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const html=readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const main=readFileSync(new URL('../web/main.mjs',import.meta.url),'utf8');
test('Atrium is a phone-first game store and lobby',()=>{
 for(const view of ['discover','library','lobbies','activity'])assert.match(html,new RegExp(`data-view="${view}"`));
 assert.match(html,/bottom-nav/);assert.match(html,/safe-area-inset-bottom/);assert.match(html,/Featured games/);assert.match(html,/Game lobbies/);
 assert.doesNotMatch(html,/Awaiting publication/);assert.doesNotMatch(html,/Integration planned/);
});
test('trusted LoopRD catalog is the hosted-game source',()=>{
 assert.match(html,/operator-trusted LoopRD/i);assert.match(main,/mountHostedLife/);assert.match(main,/trusted LoopRD game/i);
});
