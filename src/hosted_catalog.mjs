/** Separate, explicitly reviewed hosted-game launch projection; never a substitute for Life auth. */
const HTTPS = value => {
 if(typeof value!=='string'||value.length>2048)throw Error('Invalid URL');
 const u=new URL(value);
 if(u.protocol!=='https:'||u.username||u.password||u.hash||u.search||u.port||!u.hostname.includes('.')||u.hostname.endsWith('.local')||u.hostname.endsWith('.localhost')||u.hostname.endsWith('.internal')||/^\d+(\.\d+){3}$/.test(u.hostname)||u.hostname.includes(':'))throw Error('Unsafe HTTPS URL');
 return u.href;
};
const ID=/^[a-z][a-z0-9.-]{2,119}$/;
export function validateHostedCatalog(data){
 if(!data||data.schema!=='atrium.hosted-games/v1'||!Array.isArray(data.games)||Object.keys(data).some(k=>!['schema','games'].includes(k))||data.games.length>100)throw Error('Invalid hosted catalog');
 const seen=new Set();
 for(const g of data.games){
  if(!g||Object.keys(g).some(k=>!['gameId','title','publisherId','deploymentId','component','launchUrl','apiBaseUrl','sourceRevision','approved','status','embedAllowed'].includes(k))||g.approved!==true||g.status!=='published'||g.gameId!=='life.loop'||g.component!=='the-life-loop'||!ID.test(g.gameId)||!ID.test(g.publisherId)||!/^[a-z][a-z0-9-]{2,95}$/.test(g.deploymentId)||typeof g.title!=='string'||!g.title.trim()||g.title.length>80||!/^[0-9a-f]{40}$/.test(g.sourceRevision)||typeof g.embedAllowed!=='boolean')throw Error('Unreviewed or invalid hosted game');
  HTTPS(g.launchUrl);HTTPS(g.apiBaseUrl);
  if(!g.apiBaseUrl.startsWith(new URL(g.apiBaseUrl).origin+'/looprd/the-life-loop/v'))throw Error('Unexpected LoopRD route');
  if(seen.has(g.gameId+':'+g.deploymentId))throw Error('Duplicate hosted game');seen.add(g.gameId+':'+g.deploymentId);
 }
 return data;
}
export async function fetchHostedCatalog(fetcher=fetch,url='./hosted-games.json'){
 const r=await fetcher(url,{credentials:'omit',cache:'no-store',redirect:'error'});
 if(!r.ok)throw Error('Hosted game approvals unavailable');
 return validateHostedCatalog(await r.json());
}
