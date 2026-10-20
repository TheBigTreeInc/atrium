import {mountHostedLife} from '../src/hosted_cards.mjs';
import {mountMultiplayerPreview} from '../src/multiplayer_preview_ui.mjs';
import {loadIsolatedApp} from '../src/apphost.mjs';
import {fetchPublicCatalog, loadCatalogEndpoint, isStillPublished} from '../src/catalog_client.mjs';
const area = document.querySelector('#apps');
const stage = document.querySelector('#stage');
const catalogStatus = document.querySelector('#catalogStatus');
let refreshInFlight = false;
let activeApp = null;
let generation = 0;
let endpoint = null;

function revokeOpenApp(reason = 'This game is no longer available in the approved catalog.') {
  generation++;
  activeApp = null;
  stage.replaceChildren();
  stage.textContent = reason;
}

async function freshCatalog() {
  const configured = await loadCatalogEndpoint();
  if (endpoint !== null && configured !== endpoint) {
    revokeOpenApp('Public catalog gateway changed; existing game closed.');
  }
  endpoint = configured;
  return fetchPublicCatalog(fetch, endpoint);
}

async function refreshCatalog() {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    const catalog = await freshCatalog();
    if (activeApp && !isStillPublished(catalog, activeApp)) revokeOpenApp();
    area.replaceChildren();
    catalogStatus.textContent = `${catalog.apps.length} approved ${catalog.apps.length === 1 ? 'entry' : 'entries'}`;
    document.querySelector('#checkers-coming-soon').hidden = catalog.apps.some(app => app.id === 'atrium.checkers.preview');
    if (!catalog.apps.length) {
      const empty = document.createElement('div');
      empty.className = 'emptyState';
      empty.innerHTML = '<h3>The first game is being prepared</h3><p>The storefront is online, but no playable releases have been approved for publication yet. Checkers will appear here once its reviewed preview is explicitly published.</p>';
      area.append(empty);
    }
    try {
      const hostedCount = await mountHostedLife({area});
      const lifePlaceholder = document.querySelector('#life-coming-soon');
      if(lifePlaceholder) lifePlaceholder.hidden = hostedCount > 0;
      if(hostedCount) area.querySelector('.emptyState')?.remove();
      if(hostedCount) catalogStatus.textContent = `${catalog.apps.length + hostedCount} approved ${catalog.apps.length + hostedCount === 1 ? 'entry' : 'entries'}`;
    } catch (error) {
      // This is a publication/configuration fault, not an empty catalog.
      const status = document.createElement('p');
      status.className = 'lobbyMessage';
      status.textContent = `Hosted-game catalog unavailable: ${error.message}`;
      area.append(status);
    }
    for (const app of catalog.apps) {
      const card = document.createElement('article'); card.className = 'tile';
      const art=document.createElement('div');art.className='art';
      art.textContent=app.id==='atrium.checkers.preview'?'♟':'✧';art.style.fontSize='58px';
      const body=document.createElement('div');body.className='body';
      const tag=document.createElement('span');tag.className='pill';
      tag.textContent=app.id==='atrium.checkers.preview'?'Local playable preview':'Reviewed release';
      const heading = document.createElement('h3'); heading.textContent = app.title;
      const details = document.createElement('p');
      details.textContent=app.id==='atrium.checkers.preview'?'American checkers · 2 players or Staff opponent · No login needed':'Verified browser game';
      const button = document.createElement('button'); button.textContent = 'Play game';
      button.addEventListener('click', async () => {
        const requestId = ++generation;
        stage.replaceChildren();
        stage.textContent = 'Checking current publication…';
        try {
          const latest = await freshCatalog();
          if (!isStillPublished(latest, app)) throw Error('game was removed or changed');
          // A second freshness check immediately before the iframe is mounted
          // catches a revocation that occurred during the asset fetch/hash.
          await loadIsolatedApp(app, stage, latest.allowedOrigins, fetch, crypto, async () => {
            const atMount = await freshCatalog();
            if (requestId !== generation || !isStillPublished(atMount, app)) {
              throw Error('game approval changed while opening');
            }
          });
          activeApp = app;
          stage.scrollIntoView({behavior:'smooth',block:'start'});
        } catch (error) {
          if (requestId === generation) revokeOpenApp('Cannot open game: ' + error.message);
        }
      });
      body.append(tag,heading,details,button);card.append(art,body);area.append(card);
    }
  } catch (error) {
    // Never leave revoked games visible or running if the gateway is unavailable.
    area.replaceChildren();
    catalogStatus.textContent='Catalog unavailable';
    revokeOpenApp('Public catalog unavailable; running game closed: ' + error.message);
  } finally {
    refreshInFlight = false;
  }
}
mountMultiplayerPreview(document.querySelector('#multiplayerLab'));
await refreshCatalog();
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) void refreshCatalog();
});
setInterval(() => { if (!document.hidden) void refreshCatalog(); }, 60000);
