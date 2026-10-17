import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePublicCatalog, fetchPublicCatalog} from '../src/catalog_client.mjs';
const digest = 'a'.repeat(64);
const manifest = {id:'classic.checkers', title:'Checkers', status:'published', sha256:digest,
  entry:`https://assets.example.org/assets/${digest}/index.html`};
const base = {schema:'atrium.catalog-snapshot/v1', allowedOrigins:['https://assets.example.org'], apps:[manifest]};
test('public snapshot accepted with no API secrets', () => {
  assert.equal(parsePublicCatalog(base).apps.length, 1);
  assert.equal(parsePublicCatalog({...base, apps:[]}).apps.length, 0);
});
test('reject malformed snapshot and unsafe app entries', () => {
  for (const candidate of [
    {...base, schema:'atrium.catalog/v1'},
    {...base, apps:[{...manifest, status:'pending'}]},
    {...base, apps:[{...manifest, entry:'https://evil.example/app'}]},
    {...base, apps:[manifest,manifest]},
    {...base, allowedOrigins:['http://assets.example.org']}
  ]) assert.throws(() => parsePublicCatalog(candidate));
});
test('fetch only sends anonymous no-store request', async () => {
  const result = await fetchPublicCatalog(async (url, opts) => {
    assert.equal(url, './catalog.json');
    assert.equal(opts.credentials, 'omit');
    assert.equal(opts.cache, 'no-store');
    assert.equal(opts.redirect, 'error');
    assert.equal(opts.headers, undefined);
    return {ok:true, json:async()=>base};
  });
  assert.equal(result.apps[0].id, manifest.id);
});
