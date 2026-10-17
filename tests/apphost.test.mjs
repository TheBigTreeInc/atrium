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
