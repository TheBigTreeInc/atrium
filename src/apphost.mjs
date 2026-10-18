/** Minimal untrusted app host: isolated HTML iframe, no privileged capabilities. */
export function validateEntry(manifest, allowedOrigins, allowLocal = false) {
  if (!manifest || typeof manifest !== 'object' || typeof manifest.entry !== 'string' || !/^[a-f0-9]{64}$/.test(manifest.sha256 || '')) throw Error('invalid manifest');
  const u = new URL(manifest.entry);
  if (u.username || u.password || u.search || u.hash) throw Error('mutable or credentialed entry');
  if (u.protocol !== 'https:' && !(allowLocal && u.protocol === 'http:' && ['localhost','127.0.0.1'].includes(u.hostname))) throw Error('HTTPS required');
  if (!allowedOrigins.includes(u.origin)) throw Error('unapproved origin');
  return u;
}
export async function loadIsolatedApp(manifest, parent, approvedOrigins, fetcher = fetch, cryptoAPI = crypto, beforeMount = async () => {}) {
  const url = validateEntry(manifest, approvedOrigins);
  const response = await fetcher(url.href, {mode:'cors', credentials:'omit', redirect:'error', cache:'no-store'});
  if (!response.ok) throw Error('asset unavailable');
  const buffer = await response.arrayBuffer();
  if (buffer.byteLength > 1024 * 1024) throw Error('app asset exceeds 1MiB');
  const digest = await cryptoAPI.subtle.digest('SHA-256', buffer);
  const actual = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2,'0')).join('');
  if (actual !== manifest.sha256) throw Error('app asset digest mismatch');
  const frame = document.createElement('iframe');
  frame.setAttribute('sandbox','allow-scripts');
  frame.setAttribute('referrerpolicy','no-referrer');
  frame.setAttribute('title', String(manifest.title || manifest.id || 'App'));
  // No allow-same-origin / top-navigation / popups; no privileged parent message bridge.
  const html = new TextDecoder().decode(buffer);
  frame.srcdoc = html;
  await beforeMount();
  parent.replaceChildren(frame);
  return frame;
}
