/** Operator-controlled Pages source URL, no credentials embedded. */
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseHostedCatalogSource,validateHostedCatalog} from '../src/hosted_catalog.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const file=path.join(root,'dist','hosted-config.json');
const gateway=process.env.ATRIUM_PUBLIC_HOSTED_CATALOG_URL??'';
if(process.env.ATRIUM_REQUIRE_PUBLIC_HOSTED_CATALOG==='1' && !gateway) {
 throw Error('ATRIUM_PUBLIC_HOSTED_CATALOG_URL is required for hosted-game activation; refusing to stage an empty catalog');
}
const data={schema:'atrium.hosted-source/v1',gatewayUrl:gateway};
parseHostedCatalogSource(data);
if(gateway && parseHostedCatalogSource(data)!==gateway)throw Error('Unapproved hosted catalog URL');
if(gateway){
 // No mutable or fake hosted extension is allowed to enter an immutable TaviX
 // release. Preflight reads the real anonymous public projection before staging.
 // It does not submit a management request or send credentials.
 let response;
 try{
  response=await fetch(gateway,{
   method:'GET',redirect:'error',credentials:'omit',cache:'no-store',
   signal:AbortSignal.timeout(8000),headers:{Accept:'application/json'}
  });
 }catch(error){
  throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: public gateway is unreachable ('+(error?.name==='TimeoutError'?'timeout':'connection error')+')');
 }
 if(!response.ok)throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: public gateway HTTP '+response.status);
 if(!/application\/json/i.test(response.headers.get('content-type')||''))throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: public gateway must serve JSON');
 if(!/no-store/i.test(response.headers.get('cache-control')||''))throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: public gateway must disable caching');
 if(response.headers.get('access-control-allow-origin')!=='*')throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: anonymous game catalog requires public cross-origin access');
 let snapshot;
 try {snapshot=validateHostedCatalog(await response.json());}
 catch{throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: invalid trusted game projection');}
 if(snapshot.games.length===0)throw Error('ATRIUM_HOSTED_PREFLIGHT_FAILED: no active trusted game with a resolved launch mapping');
 console.log('Verified live anonymous hosted catalog (game count: '+snapshot.games.length+')');
}
const before=JSON.parse(await readFile(file,'utf8'));
if(before.schema!==data.schema)throw Error('Invalid source hosted config');
await writeFile(file,JSON.stringify(data,null,2)+'\n');
console.log(data.gatewayUrl?'Configured approved hosted catalog gateway':'Hosted-game catalog disabled (reviewed-only preview)');
