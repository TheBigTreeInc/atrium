// Tavi 0.3.66 official Atrium extension: exact, opt-in launch broker.
// No Social credentials, Life proofs, iframe popups or ambient navigation.
const CHANNEL = 'tavi.extension/v1';
let sequence = 0;
const pending = new Map();
function hostCall(method, extra = {}) {
 const id = ++sequence;
 return new Promise((resolve, reject) => {
  const timer = setTimeout(() => { pending.delete(id); reject(Error('Tavi host did not respond')); }, 10000);
  pending.set(id,{resolve,reject,timer});
  window.parent.postMessage({channel:CHANNEL,direction:'request',id,method,...extra},'*');
 });
}
window.addEventListener('message', event => {
 if(event.source !== window.parent || event.data?.channel !== CHANNEL || event.data.direction !== 'response')return;
 const entry = pending.get(event.data.id);if(!entry)return;
 pending.delete(event.data.id);clearTimeout(entry.timer);
 if(event.data.ok)entry.resolve(event.data.result);else entry.reject(Error(event.data.error || 'Tavi host rejected request'));
});
const MATCH=/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const TARGET= /^https:\/\//;
export function exactLifeHandoff(target, matchId) {
 if(typeof target!=='string'||!TARGET.test(target)||typeof matchId!=='string'||!MATCH.test(matchId))throw Error('Invalid Life launch context');
 const url=new URL(target);
 if(url.href!==target||url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.port||!url.hostname.includes('.')||url.hostname.endsWith('.localhost')||url.hostname.endsWith('.local')||url.hostname.endsWith('.internal')||/^\d+(?:\.\d+){3}$/.test(url.hostname)||url.hostname.includes(':'))throw Error('Unapproved Life target');
 return {schema:'atrium.tavi-launch/v1',gameId:'life.loop',target,matchContext:{matchId}};
}
export async function requestLifeLaunch(target, matchId) {
 const handoff=exactLifeHandoff(target,matchId);
 const info=await hostCall('host.info');
 if(!info?.features?.includes('atrium.tavi-launch/v1'))throw Error('Tavi does not support reviewed Life launch');
 const result=await hostCall('ui.requestGameLaunch',{handoff});
 if(result?.awaitingApproval!==true)throw Error('Tavi did not queue Life launch');
 return result;
}
// Loaded only in the official Tavi iframe build. Standalone web never uses it.
window.__atriumTaviLaunch = requestLifeLaunch;
document.getElementById('returnTavi')?.addEventListener('click',async event=>{
 const button=event.currentTarget;button.disabled=true;
 try{await hostCall('ui.close');}catch{button.disabled=false;}
});
