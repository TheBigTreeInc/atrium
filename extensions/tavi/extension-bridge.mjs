// Atrium TaviX 1.0 browser integration. Tavi is messenger-first; game surfaces
// are optional and must be explicitly advertised by the Tavi host.
// SDK 1.0.0 supplied with the Atrium 0.5.39 source. No bearer, Social token,
// LoopRD operator key or player proof is forwarded into the launched surface.
import {createTaviXSDK, assertTaviXHostInfo} from './tavix-sdk.mjs';
import {fetchConfiguredHostedCatalog} from '../../src/hosted_catalog.mjs';

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
export async function requestGameSurface(gameId,target,matchId='',{allowLegacy=false}={}){
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
  if(!allowLegacy)throw Error('An older Tavi host can only hand Life off externally. Select the separate legacy launch action to continue.');
  await requestLifeLaunch(target,matchId,info);
  return true;
 }
 throw Error('This Tavi host cannot open an embedded game yet. Use the explicit Open in browser action or update Tavi.');
}

/** Tavi-facing game entry point. A caller cannot supply an arbitrary URL: the
 * validated public, no-credential LoopRD catalog must contain the same deployed
 * game and exact target at the moment we ask the host to open a surface.
 * This is defense in depth; Tavi must independently enforce its own grants.
 */
export async function requestReviewedGameSurface(gameId,deploymentId,target,matchId='',options={}) {
 const catalog=await fetchConfiguredHostedCatalog(options.fetcher || fetch);
 const approved=catalog.games.find(game=>game.gameId===gameId && game.deploymentId===deploymentId && game.launchUrl===target);
 if(!approved)throw Error('This game is not published by the trusted LoopRD catalog');
 if(options.legacyOnly){
  if(gameId!=='life.loop'||!matchId)throw Error('Legacy launch requires an existing Life match');
  return requestGameSurface(gameId,approved.launchUrl,matchId,{allowLegacy:true});
 }
 return requestGameSurface(gameId,approved.launchUrl,matchId);
}
// Only the reviewed public catalog can supply a launch target to Tavi.
window.__atriumTaviOpenGame=(gameId,deploymentId,target,matchId)=>requestReviewedGameSurface(gameId,deploymentId,target,matchId);
window.__atriumTaviLaunch=(deploymentId,target,matchId)=>requestReviewedGameSurface('life.loop',deploymentId,target,matchId,{legacyOnly:true});

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
 if(hostOwnsNavigation(info)){document.body?.classList?.add('tavix-host-navigation');returnButton?.remove();}
}).catch(()=>{});
