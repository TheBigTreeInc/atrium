/** Operator controls the public LoopRD intake URL once per Atrium Pages deployment. */
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const file=path.join(root,'dist','registration-config.json');
const data={schema:'atrium.registration-source/v1',endpointUrl:process.env.ATRIUM_PUBLIC_REGISTRATION_ENDPOINT??''};
const current=JSON.parse(await readFile(file,'utf8'));
if(current.schema!==data.schema)throw Error('Unexpected registration config schema');
if(data.endpointUrl){
 const u=new URL(data.endpointUrl);
 if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||u.port||u.pathname!=='/looprd/atrium-registration/v1/registrations'||u.hostname.endsWith('.local')||u.hostname.endsWith('.localhost')||u.hostname.endsWith('.internal')||/^[0-9.]+$/.test(u.hostname)||!u.hostname.includes('.')||!data.endpointUrl.startsWith('https://'))throw Error('Registration endpoint must be a public clean HTTPS LoopRD route');
}
await writeFile(file,JSON.stringify(data,null,2)+'\n');
console.log(data.endpointUrl?'Registration endpoint configured':'No public registration endpoint configured');
