import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../web/main.mjs',import.meta.url),'utf8');
test('catalog transport failures stay visible on Discover and My Games',()=>{
 assert.match(source,/function catalogIssue\(/);
 assert.match(source,/ATRIUM_HOSTED_NOT_CONFIGURED/);
 assert.match(source,/syncLibraryMirror\(issues\)/);
 assert.match(source,/area\.prepend\(issuePanel\(issue\)\)/);
 assert.match(source,/libraryMirror\.append\(issuePanel\(issue\)\)/);
 assert.doesNotMatch(source,/if\(!count\)\s*\{?\s*area\.innerHTML=/);
 assert.match(source,/if\(!issues\.length\)/);
});
