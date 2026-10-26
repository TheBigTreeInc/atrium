/** Operator-controlled Pages source URL, no credentials embedded. */
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseHostedCatalogSource} from '../src/hosted_catalog.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const file=path.join(root,'dist','hosted-config.json');
const gateway=process.env.ATRIUM_PUBLIC_HOSTED_CATALOG_URL??'';
if(process.env.ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG==='1' && !gateway) {
 throw Error('ATRIUM_PUBLIC_HOSTED_CATALOG_URL is required for hosted-game activation; refusing to stage an empty catalog');
}
const data={schema:'atrium.hosted-source/v1',gatewayUrl:gateway};
parseHostedCatalogSource(data);
if(gateway && parseHostedCatalogSource(data)!==gateway)throw Error('Unapproved hosted catalog URL');
const before=JSON.parse(await readFile(file,'utf8'));
if(before.schema!==data.schema)throw Error('Invalid source hosted config');
await writeFile(file,JSON.stringify(data,null,2)+'\n');
console.log(data.gatewayUrl?'Configured approved hosted catalog gateway':'Hosted-game catalog disabled (reviewed-only preview)');
