import {loadIsolatedApp} from '../src/apphost.mjs';
import {fetchPublicCatalog, loadCatalogEndpoint, isStillPublished} from '../src/catalog_client.mjs';
const area = document.querySelector('#apps');
const stage = document.querySelector('#stage');
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
    if (!catalog.apps.length) {
      const empty = document.createElement('p');
      empty.textContent = 'No approved applications are currently published.';
      area.append(empty);
    }
    for (const app of catalog.apps) {
      const card = document.createElement('article'); card.className = 'tile';
      const heading = document.createElement('h2'); heading.textContent = app.title;
      const details = document.createElement('p'); details.textContent = app.id;
      const button = document.createElement('button'); button.textContent = 'Open';
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
        } catch (error) {
          if (requestId === generation) revokeOpenApp('Cannot open game: ' + error.message);
        }
      });
      card.append(heading, details, button); area.append(card);
    }
  } catch (error) {
    // Never leave revoked games visible or running if the gateway is unavailable.
    area.replaceChildren();
    revokeOpenApp('Public catalog unavailable; running game closed: ' + error.message);
  } finally {
    refreshInFlight = false;
  }
}
await refreshCatalog();
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) void refreshCatalog();
});
setInterval(() => { if (!document.hidden) void refreshCatalog(); }, 60000);
