/** Anonymous, fail-closed public catalog transport: no DAPI operator credentials. */
export function parsePublicCatalog(data) {
  if (!data || data.schema !== 'atrium.catalog-snapshot/v1' ||
      !Array.isArray(data.apps) || !Array.isArray(data.allowedOrigins) ||
      data.apps.length > 10000 || data.allowedOrigins.length > 10000) throw Error('invalid catalog format');
  const origins = new Set();
  for (const origin of data.allowedOrigins) {
    if (typeof origin !== 'string' || origins.has(origin)) throw Error('invalid catalog origin');
    const url = new URL(origin);
    if (url.origin !== origin || url.protocol !== 'https:' || url.username || url.password) throw Error('invalid catalog origin');
    origins.add(origin);
  }
  const ids = new Set();
  for (const app of data.apps) {
    if (!app || typeof app.id !== 'string' || ids.has(app.id) ||
        app.status !== 'published' || typeof app.title !== 'string' ||
        !/^[a-f0-9]{64}$/.test(app.sha256 || '') || typeof app.entry !== 'string') {
      throw Error('invalid published application');
    }
    const url = new URL(app.entry);
    if (url.protocol !== 'https:' || !origins.has(url.origin) || url.username || url.password || url.search || url.hash ||
        !url.pathname.split('/').includes(app.sha256)) throw Error('unsafe published application');
    ids.add(app.id);
  }
  return data;
}

/** The deployed Pages config is public and does not carry credentials. */
export function parseCatalogSource(config) {
  if (!config || config.schema !== 'atrium.catalog-source/v1' ||
      Object.keys(config).some(key => !['schema','gatewayUrl'].includes(key)) ||
      typeof config.gatewayUrl !== 'string') throw Error('invalid catalog source configuration');
  if (!config.gatewayUrl) return './catalog.json'; // Explicit no-gateway preview mode.
  const raw = config.gatewayUrl;
  const url = new URL(raw);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
      url.pathname !== '/catalog.json' || url.port || url.origin === 'null' ||
      url.hostname === 'localhost' || url.hostname.endsWith('.localhost') ||
      url.hostname.endsWith('.local') || url.hostname.endsWith('.internal') ||
      /^[0-9.]+$/.test(url.hostname) || url.hostname.startsWith('[') ||
      !url.hostname.includes('.') || raw !== url.href) throw Error('invalid HTTPS catalog gateway URL');
  return raw;
}

export async function loadCatalogEndpoint(fetcher = fetch, configUrl = './catalog-config.json') {
  const response = await fetcher(configUrl, {cache:'no-store', credentials:'omit', redirect:'error'});
  if (!response.ok) throw Error('catalog source configuration unavailable');
  return parseCatalogSource(await response.json());
}

export function samePublishedRelease(app, candidate) {
  return !!app && !!candidate && app.id === candidate.id && app.status === 'published' &&
    candidate.status === 'published' && app.entry === candidate.entry &&
    app.sha256 === candidate.sha256 && app.version === candidate.version;
}

export function isStillPublished(catalog, app) {
  return catalog.apps.some(candidate => samePublishedRelease(app, candidate));
}

export async function fetchPublicCatalog(fetcher = fetch, url = './catalog.json') {
  const response = await fetcher(url, {cache: 'no-store', credentials: 'omit', redirect: 'error'});
  if (!response.ok) throw Error('public catalog unavailable');
  return parsePublicCatalog(await response.json());
}
