import test from 'node:test';
import assert from 'node:assert/strict';
import {validateEntry} from '../src/apphost.mjs';
const base={entry:'https://api.example.org/assets/a/index.html',sha256:'a'.repeat(64)};
test('accept approved immutable origin',()=>assert.equal(validateEntry(base,['https://api.example.org']).host,'api.example.org'));
test('deny unknown origin',()=>assert.throws(()=>validateEntry({...base,entry:'https://attacker.test/run'},['https://api.example.org'])));
test('deny URL query and fragments',()=>{
 for(const suffix of ['?token=abc','#next'])assert.throws(()=>validateEntry({...base,entry:base.entry+suffix},['https://api.example.org']));
});
test('deny HTTP except explicit localhost mode',()=>{
 assert.throws(()=>validateEntry({...base,entry:'http://localhost:8080/index'},['http://localhost:8080']));
 assert.equal(validateEntry({...base,entry:'http://localhost:8080/index'},['http://localhost:8080'],true).hostname,'localhost');
});
test('requires SHA256 integrity metadata',()=>assert.throws(()=>validateEntry({...base,sha256:''},['https://api.example.org'])));
test('pre-mount approval guard prevents any iframe from rendering on revocation', async () => {
  const {loadIsolatedApp} = await import('../src/apphost.mjs');
  const {createHash} = await import('node:crypto');
  const bytes = new TextEncoder().encode('<!doctype html><title>Example</title>');
  const hex = createHash('sha256').update(bytes).digest('hex');
  let mounts = 0;
  const parent = {replaceChildren: () => {mounts++;}};
  const prev = globalThis.document;
  globalThis.document = {createElement: () => ({setAttribute(){},set srcdoc(value){this.html=value;}})};
  try {
    const entry = `https://assets.example.org/assets/${hex}/index.html`;
    const app = {id:'first.party',title:'Game',sha256:hex,entry};
    await assert.rejects(() => loadIsolatedApp(app,parent,['https://assets.example.org'],async () => ({ok:true,arrayBuffer:async()=>bytes.buffer}),
      {subtle:{digest:async (_alg,buf)=>createHash('sha256').update(new Uint8Array(buf)).digest()}},
      async()=>{throw Error('approval revoked while loading');}),/approval revoked/);
    assert.equal(mounts,0);
  } finally {globalThis.document=prev;}
});
