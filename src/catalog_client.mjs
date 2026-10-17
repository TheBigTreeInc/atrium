/** Browser-only snapshot reader: never authenticates to the DAPI operator registry. */
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

export async function fetchPublicCatalog(fetcher = fetch, url = './catalog.json') {
  const response = await fetcher(url, {cache: 'no-store', credentials: 'omit', redirect: 'error'});
  if (!response.ok) throw Error('public catalog unavailable');
  return parsePublicCatalog(await response.json());
}
