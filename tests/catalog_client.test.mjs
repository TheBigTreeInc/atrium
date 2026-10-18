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

import {parseCatalogSource, loadCatalogEndpoint, samePublishedRelease, isStillPublished} from '../src/catalog_client.mjs';
test('configured live HTTPS catalog source is public and fail closed', () => {
  const schema = 'atrium.catalog-source/v1';
  assert.equal(parseCatalogSource({schema, gatewayUrl:''}), './catalog.json');
  assert.equal(parseCatalogSource({schema, gatewayUrl:'https://catalog.example.org/catalog.json'}), 'https://catalog.example.org/catalog.json');
  for (const bad of [
    'http://catalog.example.org/catalog.json',
    'https://secret@catalog.example.org/catalog.json',
    'https://catalog.example.org/catalog.json?apikey=x',
    'https://catalog.example.org/catalog.json#x',
    'https://localhost/catalog.json',
    'https://127.0.0.1/catalog.json',
    'https://catalog.internal/catalog.json',
    'https://catalog.example.org/registry/catalog',
    'https://catalog.example.org:8443/catalog.json',
  ]) assert.throws(() => parseCatalogSource({schema, gatewayUrl:bad}));
  assert.throws(() => parseCatalogSource({schema, gatewayUrl:'', apiKey:'no'}));
});
test('source config fetched anonymously and an unavailable config never silently falls back', async () => {
  assert.equal(await loadCatalogEndpoint(async (_, options) => {
    assert.equal(options.credentials,'omit');
    assert.equal(options.redirect,'error');
    assert.equal(options.cache,'no-store');
    return {ok:true,json:async()=>({schema:'atrium.catalog-source/v1',gatewayUrl:'https://catalog.example.org/catalog.json'})};
  }), 'https://catalog.example.org/catalog.json');
  await assert.rejects(() => loadCatalogEndpoint(async () => ({ok:false})), /unavailable/);
});
test('revocation detects missing or replaced release identities', () => {
  const installed = {...manifest, version:'1.0.0'};
  assert.equal(isStillPublished({...base,apps:[installed]}, installed), true);
  for (const changed of [
    {...installed,sha256:'b'.repeat(64)},
    {...installed,entry:'https://assets.example.org/assets/'+ 'b'.repeat(64) + '/index.html'},
    {...installed,version:'2.0.0'},
    {...installed,status:'disabled'}
  ]) assert.equal(samePublishedRelease(installed,changed),false);
  assert.equal(isStillPublished({...base,apps:[]},installed),false);
});
