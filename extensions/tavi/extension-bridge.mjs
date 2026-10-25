// Atrium TaviX 1.0 browser integration. Tavi is messenger-first; game surfaces
// are optional and must be explicitly advertised by the Tavi host.
// SDK 1.0.0 supplied with the Atrium 0.5.39 source. No bearer, Social token,
// LoopRD operator key or player proof is forwarded into the launched surface.
import {createTaviXSDK, assertTaviXHostInfo} from './tavix-sdk.mjs';

const tavi=createTaviXSDK();
const MATCH=/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const GAME=/^[a-z][a-z0-9.-]{2,118}$/;

function validatedTarget(target){
 if(typeof target!=='string'||!target.startsWith('https://'))throw Error('Invalid game launch target');
 const url=new URL(target);
 if(url.href!==target||url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.port||!url.hostname.includes('.')||
    ['.localhost','.local','.internal','.test'].some(x=>url.hostname.endsWith(x))||
    /^\d+(?:\.\d+){3}$/.test(url.hostname)||url.hostname.includes(':'))throw Error('Unapproved game target');
 return target;
}

export function exactLifeHandoff(target,matchId){
 validatedTarget(target);
 if(typeof matchId!=='string'||!MATCH.test(matchId))throw Error('Invalid Life match context');
 return {schema:'atrium.tavi-launch/v1',gameId:'life.loop',target,matchContext:{matchId}};
}

export function hostOwnsNavigation(info){
 return info?.extensionId==='inc.thebigtree.tavi.atrium' &&
        info?.mode==='embedded' && info?.navigation==='host';
}

export async function requestLifeLaunch(target,matchId,info){
 const handoff=exactLifeHandoff(target,matchId);
 const host=info||await tavi.info();
 if(!host?.features?.includes('atrium.tavi-launch/v1'))throw Error('Tavi does not support reviewed Life launch');
 const result=await tavi.ui.requestGameLaunch(handoff); // compatibility: ui.requestGameLaunch
 if(result?.awaitingApproval!==true)throw Error('Tavi did not queue Life launch');
 return result;
}

/** Returns false only when a capability is absent, allowing a normal browser launch. */
export async function requestGameSurface(gameId,target,matchId=''){
 if(typeof gameId!=='string'||!GAME.test(gameId))throw Error('Invalid game identity');
 validatedTarget(target);
 if(matchId&&(!MATCH.test(matchId)||gameId!=='life.loop'))throw Error('Invalid game match context');
 let info;
 try{info=await tavi.info();}catch{return false;}
 if(info?.features?.includes('tavix.surface/v1')){
  // New games only use a conforming, capability-advertising TaviX host.
  assertTaviXHostInfo(info);
  await tavi.surfaces.requestOpen({
   schema:'tavix.surface/v1',id:gameId,kind:'game',target,
   context:matchId?{matchId}:{},presentation:'auto'
  });
  return true;
 }
 if(gameId==='life.loop'&&matchId&&info?.features?.includes('atrium.tavi-launch/v1')){
  await requestLifeLaunch(target,matchId,info);
  return true;
 }
 return false;
}

// These bindings exist only in the TaviX extension build, not public Pages.
window.__atriumTaviOpenGame=requestGameSurface;
window.__atriumTaviLaunch=(target,matchId)=>requestLifeLaunch(target,matchId);

const returnButton=document.getElementById('returnTavi');
returnButton?.addEventListener('click',async()=>{
 returnButton.disabled=true;
 try{
  const info=await tavi.info();
  if(info?.standard==='tavix/1.0'){
   assertTaviXHostInfo(info);
   await tavi.navigation.close();
  }else await tavi.ui.close(); // old Tavi host fallback
 }catch{returnButton.disabled=false;}
});
void tavi.info().then(info=>{
 if(hostOwnsNavigation(info))returnButton?.remove();
}).catch(()=>{});
