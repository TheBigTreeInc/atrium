/**
 * Tavi Assets consumer reference SDK v1 (transport-injected).
 * No direct postMessage, origin assumptions, files, download, wallet or ownership API.
 * An approved TaviX host SDK must supply a session-bound {info, request} transport.
 * Tavi has NOT implemented these proposed assets.* methods yet.
 */
const FEATURE = 'tavi.assets/v1';
const DEPENDENCIES_FEATURE = 'tavi.assets.dependencies/v1';

export class AssetsUnavailableError extends Error {
  constructor(message = 'Tavi Assets host feature unavailable') {
    super(message);
    this.name = 'AssetsUnavailableError';
  }
}

export function createTaviAssetsClient(transport) {
  if (!transport || typeof transport.info !== 'function' || typeof transport.request !== 'function') {
    throw new TypeError('Session-bound host transport with info() and request() required');
  }
  let ready = false;
  let supportsDependencies = false;
  async function connect() {
    const info = await transport.info();
    if (!info || !Array.isArray(info.features) || !info.features.includes(FEATURE)) {
      ready = false;
      supportsDependencies = false;
      throw new AssetsUnavailableError();
    }
    ready = true;
    supportsDependencies = info.features.includes(DEPENDENCIES_FEATURE);
    return {feature: FEATURE, api: info.api ?? null};
  }
  async function invoke(method, params) {
    if (!ready) throw new AssetsUnavailableError('Call connect() and negotiate host support first');
    const result = await transport.request(method, params);
    if (!result || typeof result !== 'object') throw new Error('Invalid host assets response');
    return result;
  }
  const id = packId => {
    if (typeof packId !== 'string' || !/^[a-z0-9][a-z0-9._-]{0,126}$/.test(packId)) {
      throw new TypeError('Invalid packId');
    }
    return packId;
  };
  return Object.freeze({
    connect,
    dependencyStatus: () => {
      if (!supportsDependencies) throw new AssetsUnavailableError('Dependency status feature unavailable');
      return invoke('assets.dependencies.status', {});
    },
    describe: packId => invoke('assets.describe', {packId: id(packId)}),
    listObjects: (packId, filters = {}) => invoke('assets.objects.list', {...filters, packId: id(packId)}),
    // Queries only the installed packs the trusted host grants to this session.
    listPacks: (filters = {}) => invoke('assets.packs.list', filters),
    discoverObjects: (filters = {}) => invoke('assets.objects.discover', filters),
    // Resolves independent customization slots; artwork composition is game-owned.
    resolveComposition: components => invoke('assets.composition.resolve', {components}),
    getObject: (packId, objectId) => invoke('assets.objects.get', {packId: id(packId), objectId}),
    listCollections: (packId, filters = {}) => invoke('assets.collections.list', {...filters, packId: id(packId)}),
    getCollection: (packId, collectionId) => invoke('assets.collections.get', {packId: id(packId), collectionId}),
    preferences: packId => invoke('assets.preferences.get', {packId: id(packId)}),
    select: (packId, capability, variant) => invoke('assets.preferences.set', {packId: id(packId), capability, variant}),
    resolve: (packId, capability) => invoke('assets.resolve', {packId: id(packId), capability})
  });
}
