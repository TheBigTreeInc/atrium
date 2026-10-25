import {fetchConfiguredHostedCatalog} from './hosted_catalog.mjs';

const symbolFor = id => id === 'life.loop' ? '⌂' : id === 'market.grove' ? '↗' : '✦';
const descriptionFor = game => game.gameId === 'life.loop'
 ? 'Build a life, share a match and return when your next turn is ready.'
 : 'A LoopRD-hosted game discovered from this deployment.';

/** Public launcher. Trusted LoopRD publication is authoritative; a match id is never seat proof. */
export async function mountHostedLife({area,fetcher=fetch,openExternal=url=>window.open(url,'_blank','noopener,noreferrer')}){
 const catalog=await fetchConfiguredHostedCatalog(fetcher);
 for(const game of catalog.games){
  const card=document.createElement('article');card.className='game-card';card.dataset.gameId=game.gameId;card.dataset.source='looprd';
  const cover=document.createElement('div');cover.className='cover';
  const symbol=document.createElement('span');symbol.className='symbol';symbol.textContent=symbolFor(game.gameId);
  const live=document.createElement('span');live.className='live';live.textContent='PLAYABLE';cover.append(symbol,live);
  const body=document.createElement('div');body.className='card-body';
  const meta=document.createElement('div');meta.className='meta';
  const badge=document.createElement('span');badge.className='pill';badge.textContent='LoopRD verified';
  const platform=document.createElement('span');platform.className='pill muted';platform.textContent='Web · Phone';meta.append(badge,platform);
  const heading=document.createElement('h3');heading.textContent=game.title;
  const blurb=document.createElement('p');blurb.textContent=descriptionFor(game);
  const actions=document.createElement('div');actions.className='card-actions';
  const matchInput=document.createElement('input');matchInput.type='text';matchInput.placeholder='Existing match ID';matchInput.setAttribute('aria-label','Life match ID for resume');matchInput.maxLength=160;
  const button=document.createElement('button');button.className='btn primary';button.textContent=game.gameId==='life.loop'?'Play Life':'Play';
  button.addEventListener('click',async()=>{
   try{const current=(await fetchConfiguredHostedCatalog(fetcher)).games.find(g=>g.gameId===game.gameId&&g.deploymentId===game.deploymentId);
    if(!current||JSON.stringify(current)!==JSON.stringify(game))throw Error('Game publication changed');
    const matchId=game.gameId==='life.loop'?matchInput.value.trim():'';
    if(matchId&&!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(matchId))throw Error('Invalid Life match ID');
    const surfaceLaunch=window.__atriumTaviOpenGame;
    const oldLifeLaunch=window.__atriumTaviLaunch;
    if(typeof surfaceLaunch==='function'){
     const opened=await surfaceLaunch(game.gameId,current.launchUrl,matchId);
     if(!opened)openExternal(current.launchUrl); // host lacks optional surface capability
    }else if(game.gameId==='life.loop'&&matchId&&typeof oldLifeLaunch==='function')await oldLifeLaunch(current.launchUrl,matchId);
    else openExternal(current.launchUrl);
   }catch(e){button.textContent='Unavailable';button.disabled=true;button.title=e.message;}
  });
  actions.append(button);
  if((typeof window.__atriumTaviOpenGame==='function'||typeof window.__atriumTaviLaunch==='function')&&game.gameId==='life.loop'){
   const resume=document.createElement('button');resume.className='btn outline';resume.textContent='Resume match';resume.addEventListener('click',()=>{matchInput.hidden=false;matchInput.focus();});actions.append(resume);matchInput.hidden=true;
  }
  body.append(meta,heading,blurb,matchInput,actions);card.append(cover,body);area.append(card);
 }
 return catalog.games.length;
}
