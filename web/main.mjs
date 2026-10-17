import {loadIsolatedApp} from '../src/apphost.mjs';
import {fetchPublicCatalog} from '../src/catalog_client.mjs';
const area = document.querySelector('#apps');
const stage = document.querySelector('#stage');
let refreshInFlight = false;

async function refreshCatalog() {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    const catalog = await fetchPublicCatalog();
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
        stage.textContent = 'Opening verified app…';
        try { await loadIsolatedApp(app, stage, catalog.allowedOrigins); }
        catch (error) { stage.textContent = 'Cannot open app: ' + error.message; }
      });
      card.append(heading, details, button); area.append(card);
    }
  } catch (error) {
    stage.textContent = 'Catalog unavailable: ' + error.message;
  } finally {
    refreshInFlight = false;
  }
}
await refreshCatalog();
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) void refreshCatalog();
});
// Poll only while foregrounded; public snapshots are published separately.
setInterval(() => { if (!document.hidden) void refreshCatalog(); }, 60000);
