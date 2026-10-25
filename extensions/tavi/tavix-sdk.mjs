/** TaviX 1.0 browser SDK.
 *
 * The stable wire channel remains `tavi.extension/v1` for compatibility with
 * existing Tavi applications. TaviX standardizes that deployed protocol; it
 * does not expose Social credentials or native privileges to the iframe.
 */
export const TAVIX_STANDARD='tavix/1.0';
export const TAVIX_CHANNEL='tavi.extension/v1';
export const TAVIX_HOST_API='1.0.0';

export function assertTaviXHostInfo(info){
 if(!info||typeof info!=='object'||info.standard!==TAVIX_STANDARD||info.channel!==TAVIX_CHANNEL||typeof info.api!=='string'||!/^1\.\d+\.\d+$/.test(info.api)||typeof info.extensionId!=='string'||info.mode!=='embedded'||info.navigation!=='host'||!Array.isArray(info.features))throw Error('Host is not TaviX 1.0 compatible');
 return info;
}

export function createTaviXSDK(target=window.parent,source=window){
 let nextId=0;
 const pending=new Map(),listeners=new Map();
 const receiver=e=>{
  if(e.source!==target||e.data?.channel!==TAVIX_CHANNEL)return;
  if(e.data.direction==='event'){
   const handlers=listeners.get(e.data.event);if(handlers)for(const fn of [...handlers]){try{fn(e.data.payload);}catch{}}
   return;
  }
  if(e.data.direction!=='response')return;
  const item=pending.get(e.data.id);if(!item)return;pending.delete(e.data.id);clearTimeout(item.timer);
  if(e.data.ok)item.resolve(e.data.result);else item.reject(Error(e.data.error||'TaviX request failed'));
 };
 source.addEventListener('message',receiver);
 const request=(method,args={})=>{
  const id=++nextId;
  return new Promise((resolve,reject)=>{
   if(pending.size>=20)return reject(Error('Too many TaviX requests'));
   const timer=setTimeout(()=>{pending.delete(id);reject(Error('TaviX host did not respond'));},10000);
   pending.set(id,{resolve,reject,timer});
   target.postMessage({channel:TAVIX_CHANNEL,direction:'request',id,method,...args},'*');
  });
 };
 const call=(method,params={})=>request(method,{params});
 const on=(event,handler)=>{
  if(typeof event!=='string'||!event||typeof handler!=='function')throw Error('Invalid TaviX event listener');
  const set=listeners.get(event)||new Set();set.add(handler);listeners.set(event,set);
  return ()=>{set.delete(handler);if(!set.size)listeners.delete(event);};
 };
 return {
  info:()=>request('host.info'),
  conformance:async()=>assertTaviXHostInfo(await request('host.info')),
  capabilities:()=>request('host.capabilities'),
  navigation:{back:()=>request('navigation.back'),close:()=>request('navigation.close')},
  storage:{get:key=>request('storage.get',{key}),set:(key,value)=>request('storage.set',{key,value})},
  ui:{toast:message=>request('ui.toast',{message}),close:()=>request('ui.close'),
    // Compatibility only. New integrations should negotiate tavix.surface/v1.
    requestGameLaunch:handoff=>request('ui.requestGameLaunch',{handoff})},
  // TaviX optional module. Tavi 0.3.108 deliberately fails closed until the
  // generic nested surface broker is implemented and advertised by host.info.
  surfaces:{requestOpen:surface=>request('surface.requestOpen',{surface})},
  on,
  wallet:{balance:()=>call('wallet.balance'),transactions:params=>call('wallet.transactions',params),
    claim:params=>call('wallet.claim',params),convert:params=>call('wallet.convert',params),
    purchase:params=>call('wallet.purchase',params),orderStatus:params=>call('wallet.orderStatus',params),
    transfer:params=>call('wallet.transfer',params)},
  pets:{list:params=>call('pets.list',params),get:params=>call('pets.get',params),command:params=>call('pets.command',params)},
  contacts:{list:params=>call('contacts.list',params)},
  messages:{list:params=>call('messages.list',params),send:params=>call('messages.send',params)},
  events:{list:params=>call('events.list',params)},
  services:{list:()=>call('services.list')},
  dispose:()=>{source.removeEventListener('message',receiver);for(const item of pending.values()){clearTimeout(item.timer);item.reject(Error('TaviX disconnected'));}pending.clear();listeners.clear();}
 };
}

// Deployed-source compatibility name. Existing apps do not need a rewrite.
export const createTaviExtensionSDK=createTaviXSDK;
