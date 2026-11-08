import {mountHostedLife} from '../src/hosted_cards.mjs';
import {mountMultiplayerPreview} from '../src/multiplayer_preview_ui.mjs';
import {loadIsolatedApp} from '../src/apphost.mjs';
import {fetchPublicCatalog, loadCatalogEndpoint, isStillPublished} from '../src/catalog_client.mjs';
import {fetchTavixMarketplace} from '../src/tavix_marketplace.mjs';

const area=document.querySelector('#apps');
const stage=document.querySelector('#stage');
const gameTools=document.querySelector('#gameTools');
const closeGame=document.querySelector('#closeGame');
const catalogStatus=document.querySelector('#catalogStatus');
const libraryMirror=document.querySelector('#libraryMirror');
const categoryChips=document.querySelector('.chips');
let refreshInFlight=false,activeApp=null,generation=0,endpoint=null,activeFilter="all",installedSnapshot={available:false,games:[]},installedError=null;

function showView(name){
 document.querySelectorAll('[data-view-panel]').forEach(panel=>{panel.hidden=panel.dataset.viewPanel!==name;});
 document.querySelectorAll('[data-view]').forEach(button=>{
  const current=button.dataset.view===name;button.classList.toggle('active',current);
  if(current)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
 });
 if(name!=='discover'&&activeApp) revokeOpenApp('');
 window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));
document.querySelectorAll('[data-view-target]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.viewTarget)));
// The Tavi extension is a player library first; standalone Atrium still opens Discover.
if(document.body.classList.contains('tavix-extension'))showView('library');
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

/** Configuration not supplied in an offline developer preview is NOT a network error.
 * Genuine transport and schema errors remain visible without repeating tall cards.
 */
function catalogIssue(kind, error){
 const embedded=document.body.classList.contains('tavix-extension');
 const title=kind==='hosted'?'Hosted game catalog unavailable':kind==='tavix'?'TaviX game catalog unavailable':'Reviewed game catalog unavailable';
 return {
  title:embedded?'Online games could not be refreshed':title,
  detail:embedded?'Check your connection or try again.':String(error?.message||'The catalog could not be loaded.'),
  source:kind
 };
}
function emptyState(title, detail){
 const box=document.createElement('div');box.className='emptyState';
 const symbol=document.createElement('span');symbol.className='state-icon';symbol.setAttribute('aria-hidden','true');symbol.textContent='◇';
 const heading=document.createElement('h3');heading.textContent=title;
 const para=document.createElement('p');para.textContent=detail;
 box.append(symbol,heading,para);return box;
}
function issuePanel(issue){
 const node=document.createElement('div');node.className='source-notice';
 node.dataset.catalogIssue='true';node.setAttribute('role','status');
 const message=document.createElement('span');message.textContent=issue.title;
 const retry=document.createElement('button');retry.type='button';retry.className='source-retry';
 retry.textContent='Retry';retry.addEventListener('click',()=>void refreshCatalog());
 node.append(message,retry);
 // Keep detailed source diagnostics inspectable, not duplicated in a huge panel.
 if(!document.body.classList.contains('tavix-extension')){
  const details=document.createElement('small');details.textContent=issue.detail;node.append(details);
 }
 return node;
}
function libraryNotice(title,detail,actionLabel){
 const node=document.createElement('div');node.className='library-notice';node.setAttribute('role','status');
 const copy=document.createElement('span');
 const strong=document.createElement('strong');strong.textContent=title;copy.append(strong);
 if(detail){const description=document.createElement('span');description.className='library-notice-detail';description.textContent=detail;copy.append(description);}
 node.append(copy);
 if(actionLabel){const button=document.createElement('button');button.type='button';button.className='source-retry';button.textContent=actionLabel;button.addEventListener('click',()=>showView('discover'));node.append(button);}
 return node;
}
/** Filters are based only on actual publication sources, not invented genres. */
function applyCategoryFilter(){
 const cards=[...area.querySelectorAll('.game-card')];
 let shown=0;
 for(const card of cards){
  card.hidden=activeFilter!=='all'&&card.dataset.source!==activeFilter;
  if(!card.hidden)shown++;
 }
 area.querySelector('[data-filter-empty]')?.remove();
 if(cards.length&&!shown){
  const node=emptyState('No games from this source','Try All games to browse the other trusted catalog.');
  node.dataset.filterEmpty='true';area.append(node);
 }
}
document.querySelectorAll('.chip[data-filter]').forEach(chip=>chip.addEventListener('click',()=>{
 activeFilter=chip.dataset.filter;
 document.querySelectorAll('.chip[data-filter]').forEach(button=>{
  const selected=button===chip;button.classList.toggle('active',selected);
  button.setAttribute('aria-pressed',String(selected));
 });
 applyCategoryFilter();
}));
function makeInstalledCard(game){
 const card=document.createElement('article');card.className='game-card';card.dataset.gameId=game.id;card.dataset.source='installed';
 const cover=document.createElement('div');cover.className='cover';
 const symbol=document.createElement('span');symbol.className='symbol';symbol.textContent='♠';
 const live=document.createElement('span');live.className='live';live.textContent='INSTALLED';cover.append(symbol,live);
 const body=document.createElement('div');body.className='card-body';
 const meta=document.createElement('div');meta.className='meta';
 const tag=document.createElement('span');tag.className='pill';tag.textContent='Offline-capable package';
 const version=document.createElement('span');version.className='pill muted';version.textContent=game.version;
 meta.append(tag,version);
 const heading=document.createElement('h3');heading.textContent=game.name;
 const details=document.createElement('p');details.textContent=game.classification.categories.join(' · ')||'Installed TaviX game';
 const actions=document.createElement('div');actions.className='card-actions';
 const play=document.createElement('button');play.className='btn primary';play.type='button';play.textContent='Play';
 const status=document.createElement('span');status.setAttribute('role','status');status.className='status';
 play.addEventListener('click',async()=>{
  play.disabled=true;status.textContent='Asking Tavi to open…';
  try{
   // Re-fetch before launch to avoid a stale/removed package. The host also
   // rechecks its trusted registry and the expected version independently.
   const fresh=await window.__atriumInstalledGames.list();
   if(!fresh.available)throw Error('Tavi installed-game support is unavailable');
   await window.__atriumInstalledGames.open(game,fresh);
   status.textContent='Opening in Tavi…';
  }catch(error){status.textContent='Cannot open: '+String(error?.message||'Host rejected launch');}
  finally{play.disabled=false;}
 });
 actions.append(play,status);body.append(meta,heading,details,actions);card.append(cover,body);return card;
}
/** TaviX catalog entries are DISPLAY metadata, not an installation source.
 * Only Tavi's verified installed-games API can launch a package. */
function makeTavixMarketplaceCard(game){
 const card=document.createElement('article');card.className='game-card';card.dataset.gameId=game.id;card.dataset.source='tavix';
 const cover=document.createElement('div');cover.className='cover';
 const symbol=document.createElement('span');symbol.className='symbol';symbol.textContent='🎮';
 const marker=document.createElement('span');marker.className='live';marker.textContent='TaviX';cover.append(symbol,marker);
 const body=document.createElement('div');body.className='card-body';
 const meta=document.createElement('div');meta.className='meta';
 const publisher=document.createElement('span');publisher.className='pill';publisher.textContent=game.publisher;
 const version=document.createElement('span');version.className='pill muted';version.textContent=game.version;meta.append(publisher,version);
 const heading=document.createElement('h3');heading.textContent=game.name;
 const detail=document.createElement('p');detail.textContent=game.description;
 const actions=document.createElement('div');actions.className='card-actions';
 const status=document.createElement('span');status.className='status';status.setAttribute('role','status');
 const installed=installedSnapshot.available&&installedSnapshot.games.find(g=>g.id===game.id&&g.version===game.version);
 if(installed){
  const play=document.createElement('button');play.className='btn primary';play.type='button';play.textContent='Play';
  play.addEventListener('click',async()=>{
   play.disabled=true;status.textContent='Checking installed game…';
   try{const fresh=await window.__atriumInstalledGames.list();await window.__atriumInstalledGames.open(installed,fresh);status.textContent='Opening in Tavi…';}
   catch(error){status.textContent='Tavi declined: '+String(error?.message||'unavailable');}
   finally{play.disabled=false;}
  });actions.append(play);
 }else status.textContent='Install through Tavi Apps';
 actions.append(status);body.append(meta,heading,detail,actions);card.append(cover,body);return card;
}
async function refreshInstalledGames(){
 installedError=null;
 if(typeof window.__atriumInstalledGames?.list!=='function'){
  installedSnapshot={available:false,games:[]};return;
 }
 try{installedSnapshot=await window.__atriumInstalledGames.list();}
 catch(error){installedSnapshot={available:false,games:[]};installedError=String(error?.message||'Host request failed');}
}
function appendDiscoverAction(box, label='Find games'){
 const action=document.createElement('button');action.type='button';action.className='btn tonal';
 action.textContent=label;action.addEventListener('click',()=>showView('discover'));
 box.append(action);return box;
}
function syncLibraryMirror(issues=[]){
 libraryMirror.replaceChildren();
 const cards=[...area.querySelectorAll('.game-card')];
 if(installedSnapshot.available){for(const game of installedSnapshot.games)libraryMirror.append(makeInstalledCard(game));}
 else libraryMirror.append(libraryNotice('Installed games in Tavi',installedError?'Tavi could not provide the approved game list.':'Games appear here when Tavi authorizes the official Atrium integration.','Discover'));
 // Standalone diagnostics may include catalog failures; inside Tavi each
 // online source warning appears only in Discover, never twice.
 if(!document.body.classList.contains('tavix-extension'))for(const issue of issues)libraryMirror.append(issuePanel(issue));
 if(!cards.length){
  if(!issues.length&&installedSnapshot.available&&!installedSnapshot.games.length)libraryMirror.append(libraryNotice('No games installed yet','Installed games will appear here when Tavi reports them.','Discover'));
  return;
 }
 for(const card of cards){
  const clone=card.cloneNode(true);clone.hidden=false;
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
  await refreshInstalledGames();
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
  // An unconfigured hosted gateway resolves to the bundled, validated
  // hosted-games.json snapshot. A valid empty list is NOT a service outage.
  // Genuine HTTP, trust and schema errors are still handled below.
  try{count+=await mountHostedLife({area});}
  catch(error){issues.push(catalogIssue('hosted',error));}
  if(catalog){for(const app of catalog.apps){area.append(makeReviewedCard(app));count++;}}
  // The bundled snapshot is healthy/empty until an independently approved
  // TaviX index is projected at build time. Missing online services do not
  // prevent a cached/local TaviX catalog from being shown.
  try{const marketplace=await fetchTavixMarketplace(fetch);
   for(const game of marketplace.games){area.append(makeTavixMarketplaceCard(game));count++;}
  }catch(error){issues.push(catalogIssue('tavix',error));}
  if(issues.length){
   catalogStatus.textContent=count?`${count} available · Some online games could not be refreshed`:'Online catalog unavailable';
   catalogStatus.dataset.state='disconnected';
   // One small notice per failing source; never a huge repeated error card.
   for(const issue of issues)area.prepend(issuePanel(issue));
  }else{
   catalogStatus.textContent=count?`${count} ${count===1?'game':'games'}`:'0 games';
   catalogStatus.dataset.state=count?'ready':'empty';
   if(!count){
    const node=libraryNotice('No games published yet','Games will appear here when they are added to the catalog.');
    const button=document.createElement('button');button.type='button';button.className='source-retry';button.textContent='Refresh';button.addEventListener('click',()=>void refreshCatalog());node.append(button);
    area.append(node);
   }
  }
  if(categoryChips)categoryChips.hidden=count===0;
  applyCategoryFilter();
  syncLibraryMirror(issues);
 }finally{refreshInFlight=false;}
}

mountMultiplayerPreview(document.querySelector('#multiplayerLab'));
await refreshCatalog();
// A game launch can temporarily replace the Tavi extension surface without
// unloading it. Refresh trusted inventory on return; never cache a previous
// authorization as proof a game is still installed/enabled. Fresh loads also
// follow the initial refreshCatalog() path above.
const refreshOnReturn=()=>{if(!document.hidden)void refreshCatalog();};
document.addEventListener('visibilitychange',refreshOnReturn);
window.addEventListener('focus',refreshOnReturn);
window.addEventListener('pageshow',refreshOnReturn);
setInterval(refreshOnReturn,60000);
