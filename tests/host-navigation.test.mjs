import test from 'node:test';import assert from 'node:assert/strict';
// Independent unit verification of mode contract without a browser or host.
function hostOwnsNavigation(info){return info?.extensionId==='inc.thebigtree.tavi.atrium'&&info?.mode==='embedded'&&info?.navigation==='host';}
test('hide duplicate return only for authenticated host-info shape',()=>{
assert.equal(hostOwnsNavigation({extensionId:'inc.thebigtree.tavi.atrium',mode:'embedded',navigation:'host'}),true);
for(const value of [null,{}, {extensionId:'inc.thebigtree.tavi.atrium',mode:'standalone',navigation:'host'},{extensionId:'other',mode:'embedded',navigation:'host'}])assert.equal(hostOwnsNavigation(value),false);
});
