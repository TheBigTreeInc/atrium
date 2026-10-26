import {mountHostedLife} from '../src/hosted_cards.mjs';
import {mountMultiplayerPreview} from '../src/multiplayer_preview_ui.mjs';
import {loadIsolatedApp} from '../src/apphost.mjs';
import {fetchPublicCatalog, loadCatalogEndpoint, isStillPublished} from '../src/catalog_client.mjs';

const area=document.querySelector('#apps');
const stage=document.querySelector('#stage');
const gameTools=document.querySelector('#gameTools');
const closeGame=document.querySelector('#closeGame');
const catalogStatus=document.querySelector('#catalogStatus');
const libraryMirror=document.querySelector('#libraryMirror');
let refreshInFlight=false,activeApp=null,generation=0,endpoint=null;

function showView(name){
 document.querySelectorAll('[data-view-panel]').forEach(panel=>{panel.hidden=panel.dataset.viewPanel!==name;});
 document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===name));
 if(name!=='discover'&&activeApp) revokeOpenApp('');
 window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));
document.querySelectorAll('[data-view-target]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.viewTarget)));
document.querySelectorAll('[data-jump-library]').forEach(button=>button.addEventListener('click',()=>{showView('discover');area.scrollIntoView({behavior:'smooth',block:'start'});}));

function revokeOpenApp(reason='This game is no longer available in the trusted game library.'){
 generation++;activeApp=null;stage.replaceChildren();gameTools.hidden=true;if(reason)stage.textContent=reason;
}
closeGame.addEventListener('click',()=>{revokeOpenApp('');stage.replaceChildren();area.scrollIntoView({block:'start'});});

async function freshCatalog(){
 const configured=await loadCatalogEndpoint();
 if(endpoint!==null&&configured!==endpoint)revokeOpenApp('Game catalog changed; the open game was closed.');
 endpoint=configured;return fetchPublicCatalog(fetch,endpoint);
}

function makeReviewedCard(app){
 const card=document.createElement('article');card.className='game-card';card.dataset.gameId=app.id;card.dataset.source='release';
 const cover=document.createElement('div');cover.className='cover';
 const symbol=document.createElement('span');symbol.className='symbol';symbol.textContent=app.id==='atrium.checkers.preview'?'♟':'✦';
 const live=document.createElement('span');live.className='live';live.textContent='PLAYABLE';cover.append(symbol,live);
 const body=document.createElement('div');body.className='card-body';
 const meta=document.createElement('div');meta.className='meta';
 const tag=document.createElement('span');tag.className='pill';tag.textContent=app.id==='atrium.checkers.preview'?'Local game':'Reviewed release';
 const platform=document.createElement('span');platform.className='pill muted';platform.textContent='Web';meta.append(tag,platform);
 const heading=document.createElement('h3');heading.textContent=app.title;
 const details=document.createElement('p');details.textContent=app.id==='atrium.checkers.preview'?'Classic checkers against a friend or Staff.':'Verified browser game in the Atrium library.';
 const actions=document.createElement('div');actions.className='card-actions';
 const button=document.createElement('button');button.className='btn primary';button.textContent='Play';
 button.addEventListener('click',async()=>{
  const requestId=++generation;stage.replaceChildren();stage.textContent='Checking game availability…';
  try{const latest=await freshCatalog();if(!isStillPublished(latest,app))throw Error('game was removed or changed');
   await loadIsolatedApp(app,stage,latest.allowedOrigins,fetch,crypto,async()=>{const atMount=await freshCatalog();if(requestId!==generation||!isStillPublished(atMount,app))throw Error('game changed while opening');});
   activeApp=app;gameTools.hidden=false;stage.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(error){if(requestId===generation)revokeOpenApp('Cannot open game: '+error.message);}
 });
 actions.append(button);body.append(meta,heading,details,actions);card.append(cover,body);return card;
}

/** Neither a failed transport nor an unconfigured gateway is an empty registry. */
function catalogIssue(kind, error){
 const msg=String(error?.message||'');
 if(kind==='hosted' && msg.includes('ATRIUM_HOSTED_NOT_CONFIGURED')){
  return {title:'Hosted games not connected',detail:'Atrium does not have a configured public LoopRD game catalog. This is a connection/setup issue, not a statement that no games are registered.'};
 }
 return kind==='hosted'
  ? {title:'Hosted game catalog unavailable',detail:'Atrium could not load the trusted LoopRD game catalog. Check the public catalog URL and HTTPS connection; registered games cannot be shown until it recovers.'}
  : {title:'Reviewed game catalog unavailable',detail:'Atrium could not load its reviewed app catalog. Check the configured source; availability is currently unknown.'};
}
function emptyState(title, detail){
 const box=document.createElement('div');box.className='emptyState';
 const heading=document.createElement('h3');heading.textContent=title;
 const para=document.createElement('p');para.textContent=detail;
 box.append(heading,para);return box;
}
function issuePanel(issue){
 const node=emptyState(issue.title,issue.detail);
 node.dataset.catalogIssue='true';node.setAttribute('role','status');return node;
}
function syncLibraryMirror(issues=[]){
 libraryMirror.replaceChildren();
 const cards=[...area.querySelectorAll('.game-card')];
 // Show problems alongside any available games. The mirror must never silently
 // represent a network error as a legitimate zero-game library.
 for(const issue of issues)libraryMirror.append(issuePanel(issue));
 if(!cards.length){
  if(!issues.length)libraryMirror.append(emptyState('No games yet','The connected catalogs returned no published games.'));
  return;
 }
 for(const card of cards){
  const clone=card.cloneNode(true);
  clone.querySelectorAll('button,input').forEach(el=>el.remove());
  const actions=document.createElement('div');actions.className='card-actions';
  const open=document.createElement('button');open.className='btn tonal';open.textContent='Open in Discover';open.addEventListener('click',()=>{showView('discover');const original=area.querySelector(`[data-game-id="${CSS.escape(card.dataset.gameId)}"]`);original?.scrollIntoView({behavior:'smooth',block:'center'});});
  clone.querySelector('.card-body')?.append(actions);actions.append(open);libraryMirror.append(clone);
 }
}

async function refreshCatalog(){
 if(refreshInFlight)return;refreshInFlight=true;
 try{
  const issues=[];
  let count=0, catalog=null;
  try{
   catalog=await freshCatalog();
   if(activeApp&&!isStillPublished(catalog,activeApp))revokeOpenApp();
  }catch(error){
   issues.push(catalogIssue('reviewed',error));
   // A failed catalog cannot authorize a still-open app.
   revokeOpenApp('Game library unavailable.');
  }
  area.replaceChildren();
  try{count+=await mountHostedLife({area});}
  catch(error){issues.push(catalogIssue('hosted',error));}
  if(catalog){for(const app of catalog.apps){area.append(makeReviewedCard(app));count++;}}
  if(issues.length){
   catalogStatus.textContent=count?`${count} available · Catalog connection problem`:'Catalog not connected';
   // Keep the issue visible even if another source has cards.
   for(const issue of issues)area.prepend(issuePanel(issue));
  }else{
   catalogStatus.textContent=`${count} ${count===1?'game':'games'} available`;
   if(!count)area.append(emptyState('No published games','Both connected catalog sources responded successfully, but no games are currently published.'));
  }
  syncLibraryMirror(issues);
 }finally{refreshInFlight=false;}
}

mountMultiplayerPreview(document.querySelector('#multiplayerLab'));
await refreshCatalog();
document.addEventListener('visibilitychange',()=>{if(!document.hidden)void refreshCatalog();});
setInterval(()=>{if(!document.hidden)void refreshCatalog();},60000);
