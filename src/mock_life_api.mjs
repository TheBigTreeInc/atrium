/** Memory-only simulated Life API. Never makes a fetch, writes a database, or signs a Social principal. */
import {GAME_PLAY_SCHEMA, matchRef} from './multiplayer_lobby.mjs';
const INFO=Object.freeze({protocol:GAME_PLAY_SCHEMA,gameId:'life.loop',component:'the-life-loop',engine:{version:'mock-rules-preview-1',digest:'a'.repeat(64)},operations:['create','invite','join','list_matches','end_turn','resume'],capabilities:{asyncTurns:false,agentPlaySupported:false}});
function deny(reason) {throw new Error(`Mock Life: ${reason}`);}
export class MockLifeAPI {
  constructor({now=()=>Date.now(),seedExample=true}={}) {
    this.now=now;this.viewer='alice';this.matches=new Map();this.invites=new Map();this.serial=0;
    if(seedExample){
      const match=this._new('demo-100',60,'active');match.seats.add('bob');match.active='alice';
    }
  }
  useViewer(viewer){if(!['alice','bob'].includes(viewer))deny('unknown simulated player');this.viewer=viewer;}
  _new(id,hours,status='waiting') {
    const match={id,revision:0,status,active:'alice',seats:new Set(['alice']),hours,deadline:hours===null?null:new Date(this.now()+hours*3600000).toISOString()};
    this.matches.set(id,match);return match;
  }
  _owned(id){const m=this.matches.get(matchRef(id));if(!m || !m.seats.has(this.viewer)) deny('match membership required');return m;}
  _project(m){return {matchId:m.id,revision:m.revision,status:m.status,yourTurn:m.status==='active'&&m.active===this.viewer,deadline:m.deadline};}
  async request(method,path,body){
    // Intentionally no live URL or credentials; URL fields are never accepted.
    if(method==='GET'&&path==='/play/info'&&body===null) return structuredClone(INFO);
    if(method!=='POST'||path!=='/play'||!body||body.schema!==GAME_PLAY_SCHEMA||typeof body.op!=='string')deny('unsupported request');
    switch(body.op){
      case 'list_matches':return {ok:true,matches:[...this.matches.values()].filter(m=>m.seats.has(this.viewer)).map(m=>this._project(m))};
      case 'create':{
        if(!body.settings||body.settings.mode!=='private-async'||![null,60].includes(body.settings.deadlineHours))deny('unsupported settings');
        if(this.viewer!=='alice')deny('mock match creation is Alice-only');
        const m=this._new(`demo-${++this.serial+100}`,body.settings.deadlineHours);return {ok:true,match:this._project(m)};
      }
      case 'invite':{
        const m=this._owned(body.matchId);if(this.viewer!=='alice'||m.status!=='waiting')deny('only creator may invite to waiting match');
        const code=`DEMO_INVITE_${m.id.replaceAll('-','_')}`;this.invites.set(code,m.id);return {ok:true,invitation:code};
      }
      case 'join':{
        const id=this.invites.get(body.invitation);if(!id||this.viewer!=='bob')deny('invitation unavailable to this mock guest');
        const m=this.matches.get(id);if(!m||m.status!=='waiting'||m.seats.has('bob'))deny('seat unavailable');
        m.seats.add('bob');m.status='active';m.revision++;this.invites.delete(body.invitation);return {ok:true,match:this._project(m)};
      }
      case 'resume':return {ok:true,match:this._project(this._owned(body.matchId))};
      case 'end_turn':{
        const m=this._owned(body.matchId);
        if(m.status!=='active'||m.active!==this.viewer)deny('not your turn');
        if(body.expectedRevision!==m.revision)deny('stale expected revision');
        m.active=this.viewer==='alice'?'bob':'alice';m.revision++;
        m.deadline=m.hours===null?null:new Date(this.now()+m.hours*3600000).toISOString();
        return {ok:true,match:this._project(m)};
      }
      default:deny('no mock handler for operation');
    }
  }
}
