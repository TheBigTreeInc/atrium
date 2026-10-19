/** Pure, transport-injected game lobby client for an explicitly proposed Life API.
 * No HTTP, credentials, identity issuer, storage or trusted endpoint selection here.
 * The proposed envelope is NOT the currently deployed Life /play API.
 */
export const GAME_PLAY_SCHEMA = 'looprd.game-play/v1';
const OPERATIONS = new Set(['create','invite','join','list_matches','get','legal_actions','act','end_turn','history','resume']);
const MATCH_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const GAME_ID = /^[a-z][a-z0-9.-]{2,119}$/;
const COMPONENT = /^[a-z][a-z0-9-]{0,47}$/;
const SHA = /^[a-f0-9]{64}$/;
const STATUS = new Set(['waiting','active','overdue','complete']);
const keys = (object, expected) => Object.keys(object).sort().join('|') === [...expected].sort().join('|');
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value) && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
function fail(message) { throw new TypeError(`Game lobby contract: ${message}`); }
export function matchRef(value) {
  if (typeof value !== 'string' || !MATCH_ID.test(value)) fail('invalid opaque match ID');
  return value;
}
export function deadlineUTC(value) {
  if (value === null) return null;
  if (typeof value !== 'string' || value.length > 40 || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0,19)!==value.slice(0,19)) fail('invalid UTC deadline');
  return value;
}
export function validateInfo(info, {gameId='life.loop', component='the-life-loop'}={}) {
  if (!plain(info) || !keys(info,['protocol','gameId','component','engine','operations','capabilities'])) fail('unexpected game info fields');
  if (info.protocol !== GAME_PLAY_SCHEMA || typeof info.gameId !== 'string' || !GAME_ID.test(info.gameId) || info.gameId !== gameId || typeof info.component !== 'string' || !COMPONENT.test(info.component) || info.component !== component) fail('game identity or protocol mismatch');
  if (!plain(info.engine) || !keys(info.engine,['version','digest']) || typeof info.engine.version !== 'string' || info.engine.version.length < 1 || info.engine.version.length > 80 || typeof info.engine.digest !== 'string' || !SHA.test(info.engine.digest)) fail('missing versioned engine lock');
  if (!Array.isArray(info.operations) || info.operations.length < 1 || new Set(info.operations).size !== info.operations.length || !info.operations.every(x=>typeof x==='string' && OPERATIONS.has(x))) fail('invalid operations');
  if (!plain(info.capabilities) || !keys(info.capabilities,['asyncTurns','agentPlaySupported']) || typeof info.capabilities.asyncTurns !== 'boolean' || typeof info.capabilities.agentPlaySupported !== 'boolean') fail('unverified capabilities');
  const required = info.capabilities.asyncTurns ? ['get','act','end_turn','resume'] : [];
  if (info.capabilities.agentPlaySupported) required.push('legal_actions','act','end_turn','resume');
  if (!required.every(x=>info.operations.includes(x))) fail('capability not supported by operations');
  return Object.freeze({gameId:info.gameId,component:info.component,operations:Object.freeze([...info.operations]),capabilities:Object.freeze({...info.capabilities}),engine:Object.freeze({...info.engine})});
}
export function projectMatch(item) {
  if (!plain(item)) fail('match must be an object');
  const matchId=matchRef(item.matchId);
  if (!Number.isSafeInteger(item.revision) || item.revision < 0 || !STATUS.has(item.status) || typeof item.yourTurn !== 'boolean') fail('invalid match state');
  if (item.status !== 'active' && item.yourTurn) fail('non-active match cannot be your turn');
  return Object.freeze({matchId,revision:item.revision,status:item.status,yourTurn:item.yourTurn,deadline:deadlineUTC(item.deadline)});
}
function envelope(response) {
  if (!plain(response) || response.ok !== true) fail('game did not return success');
  return response;
}
function invitation(value) {
  // A private invitation is returned only to its authorized caller; never log, URL-encode or persist it here.
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{8,128}$/.test(value)) fail('invalid invitation');
  return value;
}
export class GameLobbyClient {
  constructor(transport,{gameId='life.loop',component='the-life-loop'}={}) {
    if (typeof transport !== 'function') fail('authenticated transport must be injected');
    this.transport=transport;this.gameId=gameId;this.component=component;this.info=null;this.requireCreateId=false;
  }
  async discover() {
    this.info=validateInfo(await this.transport('GET','/play/info',null),{gameId:this.gameId,component:this.component});
    if (!this.info.operations.includes('list_matches')) fail('game cannot list matches');
    return this.info;
  }
  async call(op,fields={}) {
    if (!this.info) fail('discover before performing operations');
    if (!this.info.operations.includes(op)) fail('operation not advertised');
    if (!plain(fields) || Object.keys(fields).some(x=>['schema','op','token','url','authorization'].includes(x))) fail('unsafe operation fields');
    return envelope(await this.transport('POST','/play',{schema:GAME_PLAY_SCHEMA,op,...fields}));
  }
  async listMatches() {
    const result=await this.call('list_matches');
    if (!Array.isArray(result.matches) || result.matches.length > 100) fail('unbounded match list');
    const matches=result.matches.map(projectMatch);
    if (new Set(matches.map(x=>x.matchId)).size !== matches.length) fail('duplicate match');
    return matches;
  }
  async create(options={}, requestId) {
    const live=this.requireCreateId===true;
    if (!plain(options) || (live ? !keys(options,['mode','deadlineHours','ruleset']) : !keys(options,['mode','deadlineHours'])) || options.mode !== 'private-async' || ![null,60].includes(options.deadlineHours) || (live && options.ruleset!=='classic')) fail('unsupported preview settings');
    if (live && (typeof requestId!=='string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$/.test(requestId))) fail('stable requestId required for live Life creation');
    const fields={settings:options};
    if(live) fields.requestId=requestId;
    return projectMatch((await this.call('create',fields)).match);
  }
  async invite(matchId) {
    return invitation((await this.call('invite',{matchId:matchRef(matchId)})).invitation);
  }
  async join(code) {
    return projectMatch((await this.call('join',{invitation:invitation(code)})).match);
  }
  async resume(matchId) {
    return projectMatch((await this.call('resume',{matchId:matchRef(matchId)})).match);
  }
  async simulateEndTurn(matchId,revision) {
    if (!Number.isSafeInteger(revision) || revision<0) fail('invalid expected revision');
    return projectMatch((await this.call('end_turn',{matchId:matchRef(matchId),expectedRevision:revision})).match);
  }
}
/** Atrium does not elevate Life's INTERNAL launch capabilities to a public live API.
 * This bridge deliberately reports a blocked state until /play/info is actually deployed.
 */
export function inspectInternalLifeCapabilities(internal) {
  if (!plain(internal) || internal.schema!==GAME_PLAY_SCHEMA || internal.gameId!=='life.loop' || internal.component!=='the-life-loop' || internal.publicPlayApiAvailable!==false || internal.agentPlaySupported!==false || !Array.isArray(internal.operations)) fail('unrecognized internal Life handoff');
  return Object.freeze({gameId:internal.gameId,source:'life-internal-only',liveAvailable:false,agentPlaySupported:false,operations:Object.freeze(internal.operations.filter(x=>OPERATIONS.has(x))),reason:'Life has no deployed authenticated /play/info or /play endpoint'});
}
