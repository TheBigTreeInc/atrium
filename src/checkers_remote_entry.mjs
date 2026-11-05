/** Host-neutral Checkers player entry for a Social-authenticated same-origin host.
 *
 * A match ID selects an existing game; it is never proof of account or seat.
 * The host must verify the Social session and accepted lobby before exposing
 * /games/checkers/matches/*. No login, challenge grant, or authoritative game
 * engine is included in the browser or Tavi-facing surface.
 */
import {CheckersRemoteClient, sameOriginMatchTransport} from './checkers_remote_client.mjs';
import {mountRemoteCheckers} from './checkers_remote_view.mjs';

const ID = /^[A-Za-z0-9_-]{1,64}$/;

export function createHostedCheckersPlayer(root, {
  fetchFn = globalThis.fetch,
  requestIdFactory,
  pollMs = 4000,
  setIntervalFn = globalThis.setInterval,
  clearIntervalFn = globalThis.clearInterval
} = {}) {
  if (!root || typeof root.replaceChildren !== 'function' || !root.ownerDocument ||
      typeof fetchFn !== 'function' || !Number.isSafeInteger(pollMs) || pollMs < 1000 ||
      pollMs > 60000 || typeof setIntervalFn !== 'function' ||
      typeof clearIntervalFn !== 'function') throw new TypeError('checkers_hosted_player_binding_required');
  if (requestIdFactory !== undefined && typeof requestIdFactory !== 'function') {
    throw new TypeError('invalid_request_id_factory');
  }
  const doc = root.ownerDocument;
  const form=doc.createElement('form');form.className='checkers-hosted-launch';
  const label=doc.createElement('label');label.textContent='Match ID';
  const field=doc.createElement('input');field.type='text';field.required=true;
  field.maxLength=64;field.autocomplete='off';field.setAttribute('aria-label','Checkers match ID');
  label.append(field);
  const submit=doc.createElement('button');submit.type='submit';submit.textContent='Join match';
  const intro=doc.createElement('p');intro.textContent='Requires a verified Social session on this host. The match ID grants no access.';
  const status=doc.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const stage=doc.createElement('section');stage.className='checkers-hosted-stage';
  stage.setAttribute('aria-label','Live Checkers match');
  form.append(label,submit);root.replaceChildren(intro,form,status,stage);
  const transport=sameOriginMatchTransport(fetchFn);
  let active=null,timer=null,busy=false,disposed=false;

  function stop(){
    if(timer!==null){clearIntervalFn(timer);timer=null;}
    if(active){active.destroy();active=null;}
    stage.replaceChildren();
  }
  async function launch(matchId){
    if(disposed)throw new Error('player_disposed');
    if(typeof matchId!=='string'||!ID.test(matchId)){
      status.textContent='Invalid match ID';
      return false;
    }
    if(busy)return false;
    busy=true;submit.disabled=true;stop();status.textContent='Joining the authenticated match…';
    try {
      const params={transport,matchId};
      if(requestIdFactory!==undefined)params.requestIdFactory=requestIdFactory;
      const client=new CheckersRemoteClient(params);
      const view=await mountRemoteCheckers(stage,client);
      if(disposed){view.destroy();return false;}
      // mountRemoteCheckers deliberately renders server failures instead of
      // inventing an offline or guest identity. Never start polling on failure.
      if(!client.seat){view.destroy();status.textContent='Match unavailable or access denied';return false;}
      active=view;status.textContent='Connected. Moves are verified by the match server.';
      timer=setIntervalFn(()=>{
        if(!disposed && active && !doc.hidden) void active.refresh();
      },pollMs);
      return true;
    }catch(error){
      stage.replaceChildren();
      status.textContent='Match unavailable or access denied';
      return false;
    }finally{busy=false;submit.disabled=false;}
  }
  form.addEventListener('submit',event=>{
    event.preventDefault();
    void launch(field.value);
  });
  return {launch,destroy(){disposed=true;stop();root.replaceChildren();}};
}
