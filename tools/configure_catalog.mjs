/** Operator-only build-time public Pages configuration. Never embeds secrets. */
import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {parseCatalogSource} from '../src/catalog_client.mjs';
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const file = path.join(root,'dist','catalog-config.json');
const gatewayUrl = process.env.ATRIUM_PUBLIC_CATALOG_URL ?? '';
const data = {schema:'atrium.catalog-source/v1', gatewayUrl};
parseCatalogSource(data); // Reject unknown protocols, auth-bearing links and non-HTTPS origins.
const prior = JSON.parse(await readFile(file,'utf8'));
if (prior.schema !== data.schema) throw Error('invalid base Pages catalog configuration');
await writeFile(file, JSON.stringify(data, null, 2) + '\n');
console.log(gatewayUrl ? 'Configured public HTTPS gateway URL for Pages (no credentials)' : 'Using operator-staged preview snapshot (no live gateway configured)');
