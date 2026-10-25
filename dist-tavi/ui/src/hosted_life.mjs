/** Atrium launch-only integration for an operator-approved Life instance.
 * No game rules, seat assignment, Social bearer token or challenge->match side effect.
 */
import {GameLobbyClient, matchRef} from './multiplayer_lobby.mjs';
const ID = /^[a-z][a-z0-9.-]{2,119}$/;
function requireThat(condition, message) {if (!condition) throw Error('Hosted Life: '+message);}
function publicURL(value) {
  requireThat(typeof value==='string' && value.length<=2048,'missing URL');
  const url=new URL(value);
  requireThat(url.protocol==='https:' && !url.username && !url.password && !url.hash && !url.search && !url.port && url.hostname.includes('.') && !url.hostname.endsWith('.local') && !url.hostname.endsWith('.internal') && !url.hostname.endsWith('.localhost') && !/^\d+\.\d+\.\d+\.\d+$/.test(url.hostname) && !url.hostname.includes(':'),'unsafe public HTTPS URL');
  return url;
}
/** Projection MUST come from the operator-approved runtime and reviewed catalog, not from arbitrary sidecar URLs. */
export function approvedLifeTarget({catalogEntry, discoveryInstance}) {
  requireThat(catalogEntry?.status==='published' && catalogEntry.gameId==='life.loop' && catalogEntry.approved===true,'game has not been explicitly published');
  requireThat(discoveryInstance?.gameId==='life.loop' && discoveryInstance.component==='the-life-loop' && discoveryInstance.status==='reviewed' && discoveryInstance.available===true && discoveryInstance.launchAvailable===true,'Life instance unavailable or unreviewed');
  requireThat(ID.test(discoveryInstance.gameId) && typeof discoveryInstance.deploymentId==='string' && /^[a-z][a-z0-9-]{2,95}$/.test(discoveryInstance.deploymentId),'invalid discovery identity');
  requireThat(catalogEntry.publisherId===discoveryInstance.publisherId && catalogEntry.deploymentId===discoveryInstance.deploymentId,'catalog and discovered deployment mismatch');
  const launch=publicURL(discoveryInstance.launchUrl);
  const api=publicURL(discoveryInstance.apiBaseUrl);
  requireThat(discoveryInstance.apiBaseUrl.startsWith(api.origin+'/looprd/the-life-loop/v'),'API route must originate from the activated LoopRD component');
  requireThat(catalogEntry.launchUrl===launch.href && catalogEntry.apiBaseUrl===api.href,'unapproved route or changed launch target');
  return Object.freeze({gameId:'life.loop',component:'the-life-loop',deploymentId:discoveryInstance.deploymentId,apiBaseUrl:api.href,launchUrl:launch.href,embedAllowed:catalogEntry.embedAllowed===true});
}
export function publicLifeTransport(target, {request, identityProvider}) {
  requireThat(target?.gameId==='life.loop' && typeof request==='function' && typeof identityProvider==='function','missing approved transport or identity provider');
  return async (method,path,body) => {
    requireThat((method==='GET' && path==='/play/info') || (method==='POST' && path==='/play'),'unknown Life operation');
    // A trusted caller supplies a *game-scoped* credential through its own client flow.
    // Atrium never receives a raw Social bearer, and never adds one to URL/iframe.
    let authorization;
    if(method==='POST') {
      const identity=await identityProvider(target);
      requireThat(identity?.audience==='life.loop' && typeof identity.authorization==='string' && identity.authorization.startsWith('Bearer ') && identity.authorization.length<4096,'no authorized Life game credential');
      authorization=identity.authorization;
    }
    const response=await request({url:target.apiBaseUrl+path,method,body,authorization,credentials:'omit',redirect:'error'});
    // LoopRD's Starlette HTTPException wraps a Life error under `detail`.
    if(response?.ok===false || (Number.isInteger(response?.status) && response.status>=400)) {
      const status=response.status;
      const detail=response.detail ?? response.error ?? response.body?.detail;
      const err=new Error('Life request rejected'+(Number.isInteger(status)?' ('+status+')':''));
      err.status=status;err.gameError=detail;
      throw err;
    }
    return response;
  };
}
export async function authorizedLifeLobby(target, options) {
  const client=new GameLobbyClient(publicLifeTransport(target,options));
  const info=await client.discover(); // Only the actual deployed Life /play/info envelope unlocks live mode.
  requireThat(['create','invite','join','list_matches','resume'].every(op=>info.operations.includes(op)),'Life public lobby operations not advertised');
  client.requireCreateId=true;
  return client;
}
/** Opaque match id only; server verifies seat again on every GET/act/resume. */
export function launchLife(target, matchId, {openExternal,embed,allowEmbed=false}) {
  const id=matchRef(matchId);
  requireThat(target?.gameId==='life.loop' && typeof openExternal==='function','invalid launch');
  const base=publicURL(target.launchUrl);
  // Never place invitation, Social token, seat proof or authorization in URL.
  // An opaque identifier is not authorization; Life must verify the session itself.
  const uri=new URL(base.href);
  uri.searchParams.set('match',id);
  const launch=Object.freeze({schema:'atrium.life-launch/v1',gameId:'life.loop',matchId:id,url:uri.href,context:{matchId:id,gameId:'life.loop'}});
  if(allowEmbed && target.embedAllowed===true && typeof embed==='function') embed(launch);
  else openExternal(launch.url);
  return launch;
}
/** Tavi receives only a reviewed target and opaque context, never Social bearer credentials. */
export function taviLaunchHandoff(launch) {
  requireThat(launch?.schema==='atrium.life-launch/v1' && launch.gameId==='life.loop','invalid Life launch handoff');
  matchRef(launch.matchId);
  const url=publicURL(launch.url.split('?')[0]);
  requireThat(new URL(launch.url).searchParams.size===1 && new URL(launch.url).searchParams.get('match')===launch.matchId,'unexpected launch parameters');
  return Object.freeze({schema:'atrium.tavi-launch/v1',gameId:'life.loop',target:url.href,matchContext:{matchId:launch.matchId}});
}
