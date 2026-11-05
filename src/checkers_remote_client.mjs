/** Shared, rules-free client for a Social-authenticated Atrium Checkers match.
 *
 * The host supplies `transport({method,path,body}) -> {status,body}` and owns
 * login, session/CSRF material, TLS origin, and accepted-lobby authorization.
 * No bearer, subject, seat, or other authorization claim is accepted here.
 * This module is NOT a login implementation and is not a published game.
 */
const ID = /^[A-Za-z0-9_-]{1,64}$/;
const API = '/games/checkers/matches';
const ROUTE = /^\/games\/checkers\/matches(?:\/[A-Za-z0-9_-]{1,64}(?:\/(?:join|legal-actions|moves))?)?$/;
const requireId = (value, kind) => {
  if (typeof value !== 'string' || !ID.test(value)) throw new TypeError(`invalid_${kind}`);
  return value;
};

export class CheckersRemoteError extends Error {
  constructor(code, status = 0) {
    super(code);
    this.name = 'CheckersRemoteError';
    this.code = code;
    this.status = status;
  }
}

const copy = x => structuredClone(x);
const validateSnapshot = (document, matchId) => {
  if (!document || typeof document !== 'object' || Array.isArray(document) ||
      document.matchId !== matchId || !Number.isSafeInteger(document.revision) ||
      document.revision < 0 || !document.state ||
      !Array.isArray(document.state.board) || document.state.board.length !== 8 ||
      !document.state.board.every(row => typeof row === 'string' && row.length === 8) ||
      ![null,'r','b'].includes(document.state.turn) ||
      ![null,'r','b'].includes(document.state.winner)) {
    throw new CheckersRemoteError('invalid_match_response');
  }
  return copy(document);
};
const validateActions = (document, matchId, revision) => {
  if (!document || document.protocol !== 'atrium.checkers.actions/v1' ||
      document.matchId !== matchId || document.revision !== revision ||
      !['red','black'].includes(document.seat) || !Array.isArray(document.actions) ||
      document.actions.length > 100 || !document.actions.every(path =>
        Array.isArray(path) && path.length >= 2 && path.length <= 13 &&
        path.every(coord => Array.isArray(coord) && coord.length === 2 &&
          coord.every(n => Number.isInteger(n) && n >= 0 && n <= 7)))) {
    throw new CheckersRemoteError('invalid_actions_response');
  }
  return copy(document);
};

/** Explicitly same-origin fetch adapter; other host transports are injected.
 * This adapter intentionally does not know how to obtain Social credentials.
 */
export function sameOriginMatchTransport(fetchFn = globalThis.fetch) {
  if (typeof fetchFn !== 'function') throw new TypeError('fetch_required');
  return async ({method, path, body}) => {
    if (!['GET','POST'].includes(method) || typeof path !== 'string' ||
        !ROUTE.test(path)) {
      throw new TypeError('invalid_match_path');
    }
    const options = {
      method, credentials:'same-origin', redirect:'error', cache:'no-store',
      referrerPolicy:'no-referrer', headers: {'Accept':'application/json'}
    };
    if (method === 'POST' && body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    const response = await fetchFn(path, options);
    if (!response || !Number.isInteger(response.status) || typeof response.json !== 'function') {
      throw new CheckersRemoteError('invalid_http_response');
    }
    const contentType = response.headers?.get?.('content-type') || '';
    if (!/^application\/json(?:\s*;|\s*$)/i.test(contentType)) {
      throw new CheckersRemoteError('invalid_content_type', response.status);
    }
    return {status: response.status, body: await response.json()};
  };
}

export class CheckersRemoteClient {
  constructor({transport, matchId, requestIdFactory = () => globalThis.crypto.randomUUID()}) {
    if (typeof transport !== 'function' || typeof requestIdFactory !== 'function') {
      throw new TypeError('trusted_transport_required');
    }
    this.matchId = requireId(matchId,'match_id');
    this.transport = transport;
    this.requestIdFactory = requestIdFactory;
    this.current = null;
    this.seat = null;
    this.pending = null;
  }
  get route() { return `${API}/${this.matchId}`; }
  get snapshot() { return this.current === null ? null : copy(this.current); }

  async _call(method, path, body) {
    const result = await this.transport({method,path,body: body === undefined ? undefined : copy(body)});
    if (!result || !Number.isInteger(result.status) || !result.body ||
        typeof result.body !== 'object' || Array.isArray(result.body)) {
      throw new CheckersRemoteError('invalid_transport_response');
    }
    if (result.status < 200 || result.status >= 300) {
      const code = typeof result.body.error === 'string' && /^[a-z][a-z0-9_]{0,80}$/.test(result.body.error)
        ? result.body.error : 'request_rejected';
      throw new CheckersRemoteError(code,result.status);
    }
    return result.body;
  }

  async join() {
    const result = await this._call('POST',`${this.route}/join`);
    if (!['red','black'].includes(result.seat)) throw new CheckersRemoteError('invalid_seat_response');
    const snapshot = validateSnapshot(result.match,this.matchId);
    this.seat = result.seat;
    this.current = snapshot;
    return {seat:this.seat,match:copy(snapshot)};
  }
  async refresh() {
    const snapshot = validateSnapshot(await this._call('GET',this.route),this.matchId);
    // An older poll must never roll back a newer locally observed revision.
    if (this.current === null || snapshot.revision >= this.current.revision) this.current = snapshot;
    return this.snapshot;
  }
  async legalActions() {
    if (this.current === null) await this.refresh();
    const result = await this._call('GET',`${this.route}/legal-actions`);
    if (result.revision !== this.current.revision) {
      await this.refresh();
      throw new CheckersRemoteError('state_changed',409);
    }
    return validateActions(result,this.matchId,this.current.revision);
  }
  async move(path) {
    if (this.pending) throw new CheckersRemoteError('unresolved_move');
    if (!this.current) throw new CheckersRemoteError('join_required');
    const requestId = requireId(this.requestIdFactory(),'request_id');
    this.pending = {revision:this.current.revision,requestId,path:copy(path)};
    return this.retryPending();
  }
  async retryPending() {
    if (!this.pending) throw new CheckersRemoteError('no_pending_move');
    const payload = copy(this.pending);
    try {
      const result = validateSnapshot(await this._call('POST',`${this.route}/moves`,payload),this.matchId);
      if (result.revision < payload.revision + 1) throw new CheckersRemoteError('invalid_move_response');
      if (this.current === null || result.revision >= this.current.revision) this.current = result;
      this.pending = null;
      return this.snapshot;
    } catch (error) {
      // If the server rejected the request definitively, it cannot be safely
      // replayed. If network delivery is uncertain, preserve the exact ID/body.
      if (error instanceof CheckersRemoteError && error.status >= 400) this.pending = null;
      throw error;
    }
  }
}
