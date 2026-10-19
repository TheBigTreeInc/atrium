import {fetchHostedCatalog} from './hosted_catalog.mjs';
/** Safe public launcher: an opaque match reference is never proof of seat ownership. */
export async function mountHostedLife({area,fetcher=fetch,openExternal=url=>window.open(url,'_blank','noopener,noreferrer')}){
 const catalog=await fetchHostedCatalog(fetcher);
 for(const game of catalog.games){
  if(game.gameId!=='life.loop')continue;
  const card=document.createElement('article');card.className='tile';
  const body=document.createElement('div');body.className='body';
  const badge=document.createElement('span');badge.className='pill';badge.textContent='Approved hosted game';
  const heading=document.createElement('h3');heading.textContent=game.title;
  const blurb=document.createElement('p');blurb.textContent='Play or resume through Life. Your game account and seat are verified by Life.';
  const matchInput=document.createElement('input');matchInput.type='text';matchInput.placeholder='Existing match ID';matchInput.setAttribute('aria-label','Life match ID for resume');matchInput.maxLength=160;
  const button=document.createElement('button');button.textContent=typeof window.__atriumTaviLaunch==='function'?'Resume Life':'Open Life';
  button.addEventListener('click',async()=>{
   // Refresh review before launching; no remote URL from user input or Tavi message.
   try{const current=(await fetchHostedCatalog(fetcher)).games.find(g=>g.gameId===game.gameId&&g.deploymentId===game.deploymentId);
    if(!current||JSON.stringify(current)!==JSON.stringify(game))throw Error('Life approval changed');
    const launchThroughTavi=window.__atriumTaviLaunch;
    if(typeof launchThroughTavi==='function'){
     const matchId=matchInput.value.trim();
     if(!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(matchId))throw Error('An existing Life match ID is required for Tavi resume');
     await launchThroughTavi(current.launchUrl,matchId);
     button.textContent='Approve Open Life in Tavi';
    }else openExternal(current.launchUrl);
   }catch(e){button.textContent='Launch unavailable';button.disabled=true;}
  });
  if(typeof window.__atriumTaviLaunch==='function')body.append(matchInput);
  body.append(badge,heading,blurb,button);card.append(body);area.append(card);
 }
 return catalog.games.length;
}
