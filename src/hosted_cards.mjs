import {fetchConfiguredHostedCatalog} from './hosted_catalog.mjs';

const symbolFor = id => id === 'life.loop' ? '⌂' : id === 'market.grove' ? '↗' : '✦';
const descriptionFor = game => game.gameId === 'life.loop'
 ? 'Create a life of your own, or return to an existing match.'
 : 'A game from your trusted LoopRD library.';
const MATCH = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

/** Public launcher: trusted LoopRD deployment is the publication authority.
 * Never open a browser automatically when an embedded Tavi host lacks its
 * surface capability; the player must choose that fallback explicitly.
 */
export async function mountHostedLife({area,fetcher=fetch,openExternal=url=>window.open(url,'_blank','noopener,noreferrer')}){
 const catalog=await fetchConfiguredHostedCatalog(fetcher);
 for(const game of catalog.games){
  const card=document.createElement('article');card.className='game-card';card.dataset.gameId=game.gameId;card.dataset.source='looprd';
  const cover=document.createElement('div');cover.className='cover';
  const symbol=document.createElement('span');symbol.className='symbol';symbol.textContent=symbolFor(game.gameId);
  const live=document.createElement('span');live.className='live';live.textContent='AVAILABLE';cover.append(symbol,live);
  const body=document.createElement('div');body.className='card-body';
  const meta=document.createElement('div');meta.className='meta';
  const badge=document.createElement('span');badge.className='pill';badge.textContent='Trusted LoopRD';
  const platform=document.createElement('span');platform.className='pill muted';platform.textContent='Web · Phone';meta.append(badge,platform);
  const heading=document.createElement('h3');heading.textContent=game.title;
  const blurb=document.createElement('p');blurb.textContent=descriptionFor(game);
  const actions=document.createElement('div');actions.className='card-actions';
  const status=document.createElement('p');status.className='launch-status';status.hidden=true;status.setAttribute('role','status');
  const matchInput=document.createElement('input');matchInput.type='text';matchInput.placeholder='Existing match ID';matchInput.setAttribute('aria-label','Life match ID for resume');matchInput.maxLength=128;matchInput.hidden=true;
  const browser=document.createElement('button');browser.className='btn outline';browser.textContent='Open in browser';browser.hidden=true;
  let pendingBrowserMatch='';
  async function reviewedGame(){
   const current=(await fetchConfiguredHostedCatalog(fetcher)).games.find(g=>g.gameId===game.gameId&&g.deploymentId===game.deploymentId);
   if(!current||JSON.stringify(current)!==JSON.stringify(game))throw Error('Game publication changed');
   return current;
  }
  function message(text){status.textContent=text;status.hidden=!text;}
  async function openGame(matchId='',legacyOnly=false){
   browser.hidden=true;pendingBrowserMatch='';message('');
   let verified=false;
   if(matchId&&!MATCH.test(matchId)){message('Enter a valid match ID to resume.');return;}
   try{
    const current=await reviewedGame();verified=true;
    const surfaceLaunch=window.__atriumTaviOpenGame;
    const oldLifeLaunch=window.__atriumTaviLaunch;
    if(typeof surfaceLaunch==='function'){
     const opened=legacyOnly&&typeof oldLifeLaunch==='function'
      ? await oldLifeLaunch(game.deploymentId,current.launchUrl,matchId)
      : await surfaceLaunch(game.gameId,game.deploymentId,current.launchUrl,matchId);
     if(opened){message(legacyOnly?'Older Tavi launch requested. It may open externally.':'Opening in Tavi…');return;}
     message('This Tavi host cannot embed games. You may choose to open the game in your browser.');
     pendingBrowserMatch=matchId;browser.hidden=false;
    }else{
     // Standalone Atrium: the user explicitly selected Play/Resume.
     const url=new URL(current.launchUrl);
     if(matchId)url.searchParams.set('match',matchId);
     openExternal(url.href);
    }
   }catch(error){
    message(error.message);
    // A capability error is a presentation limitation, not publication approval.
    // Still revalidate the catalog on the separate user-initiated browser action.
    if(verified && typeof window.__atriumTaviOpenGame==='function'){
     pendingBrowserMatch=matchId;browser.hidden=false;
     if(game.gameId==='life.loop'&&matchId&&/older Tavi host/.test(error.message)&&typeof window.__atriumTaviLaunch==='function')legacy.hidden=false;
    }
   }
  }
  const play=document.createElement('button');play.className='btn primary';play.textContent=game.gameId==='life.loop'?'Play solo':'Play';play.addEventListener('click',()=>void openGame());
  actions.append(play);
  const legacy=document.createElement('button');legacy.className='btn tonal';legacy.textContent='Use older Tavi launch';legacy.hidden=true;
  legacy.addEventListener('click',()=>{legacy.hidden=true;void openGame(matchInput.value.trim(),true);});
  if(game.gameId==='life.loop'){
   const resumeShow=document.createElement('button');resumeShow.className='btn outline';resumeShow.textContent='Resume match';
   resumeShow.addEventListener('click',()=>{matchInput.hidden=false;resume.hidden=false;matchInput.focus();});
   const resume=document.createElement('button');resume.className='btn tonal';resume.textContent='Continue';resume.hidden=true;
   resume.addEventListener('click',()=>void openGame(matchInput.value.trim()));
   actions.append(resumeShow,resume);
  }
  browser.addEventListener('click',async()=>{
   browser.disabled=true;
   try{const current=await reviewedGame();const url=new URL(current.launchUrl);if(pendingBrowserMatch)url.searchParams.set('match',pendingBrowserMatch);openExternal(url.href);message('Opened in browser. Your Tavi chat stays here.');browser.hidden=true;}
   catch(error){message(error.message);}finally{browser.disabled=false;}
  });
  body.append(meta,heading,blurb,matchInput,actions,legacy,browser,status);card.append(cover,body);area.append(card);
 }
 return catalog.games.length;
}
