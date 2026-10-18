/** Clearly labelled opt-in simulation. No production token, remote API or registration. */
import {GameLobbyClient} from './multiplayer_lobby.mjs';
import {MockLifeAPI} from './mock_life_api.mjs';

const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function button(label,action,{disabled=false,cls=''}={}){
  const b=make('button',label,cls);b.type='button';b.disabled=disabled;b.addEventListener('click',()=>void action());return b;
}
const statusLabel=m=>m.status==='waiting'?'Waiting for opponent':m.status==='complete'?'Finished':m.status==='overdue'?'Overdue':m.yourTurn?'Your turn':'Waiting for opponent';
export function mountMultiplayerPreview(root,{backend=new MockLifeAPI()}={}) {
  if(!root)throw Error('Missing multiplayer preview host');
  const state={backend,viewer:'alice',opened:false,selected:null,busy:false,invite:''};
  const client=new GameLobbyClient((...args)=>backend.request(...args));
  const update=async (message='')=>{
    root.replaceChildren();
    const heading=make('div',undefined,'lobbyTop');
    const left=make('div');left.append(make('span','SANDBOX • NOT A REAL MATCH','lobbyFlag'),make('h3','Life multiplayer lobby preview'));
    heading.append(left,button(state.opened?'Close preview':'Explore mock lobby',async()=>{state.opened=!state.opened;await update();}));root.append(heading);
    root.append(make('p','Try a sample private match, swap between two simulated players and preview the join/continue flow. No game state or account is created on Looprd.', 'lobbyDescription'));
    if(!state.opened)return;
    const controls=make('div',undefined,'lobbyControls');
    const who=make('label','Simulated account: ','lobbyLabel');const select=make('select');select.setAttribute('aria-label','Simulated account');
    for(const person of [{id:'alice',name:'Alice · creator'},{id:'bob',name:'Bob · invited player'}]){const opt=make('option',person.name);opt.value=person.id;select.append(opt);}
    select.value=state.viewer;
    select.addEventListener('change',async()=>{backend.useViewer(select.value);state.viewer=select.value;state.selected=null;await update();});
    who.append(select);controls.append(who);
    controls.append(button('Create mock match (60h)',async()=>{await run(async()=>{state.selected=await client.create({mode:'private-async',deadlineHours:60});},'Mock match created');},{disabled:state.viewer!=='alice'||state.busy}));
    controls.append(button('Create without deadline',async()=>{await run(async()=>{state.selected=await client.create({mode:'private-async',deadlineHours:null});},'Mock unlimited match created');},{disabled:state.viewer!=='alice'||state.busy}));
    root.append(controls);
    if(message)root.append(make('p',message,'lobbyMessage'));
    let matches=[];
    try {if(!client.info) await client.discover();matches=await client.listMatches();}
    catch(error){root.append(make('p','Lobby simulation failed: '+error.message,'lobbyMessage'));return;}
    const wrap=make('div',undefined,'lobbyMatches');
    if(!matches.length)wrap.append(make('p','No matches for this simulated account. Create as Alice, invite Bob, then join as Bob.','lobbyEmpty'));
    for(const match of matches){
      const card=make('article',undefined,'lobbyMatch');
      const meta=make('div');meta.append(make('strong',`Life • ${match.matchId}`),make('span',statusLabel(match),'matchState'));
      card.append(meta,make('p',match.deadline?`Turn deadline (UTC): ${match.deadline}`:'No turn deadline','muted smallprint'));
      const actions=make('div',undefined,'lobbyActions');
      actions.append(button('Continue preview',async()=>{await run(async()=>{state.selected=await client.resume(match.matchId);},'Match restored from the mock game');},{disabled:state.busy}));
      if(match.status==='waiting'&&state.viewer==='alice') actions.append(button('Generate mock invitation',async()=>{await run(async()=>{state.invite=await client.invite(match.matchId);},'Mock invitation generated — not a real secret');},{disabled:state.busy}));
      card.append(actions);wrap.append(card);
    }
    root.append(wrap);
    const inviteArea=make('div',undefined,'lobbyJoin');inviteArea.append(make('h4','Join a mock invitation'));
    const joinInput=make('input');joinInput.type='text';joinInput.placeholder='DEMO_INVITE_demo_101';joinInput.maxLength=128;joinInput.autocomplete='off';joinInput.setAttribute('aria-label','Mock invitation code');joinInput.value=state.invite;
    joinInput.addEventListener('input',()=>{state.invite=joinInput.value.trim();});
    inviteArea.append(joinInput,button('Join as Bob',async()=>{await run(async()=>{state.selected=await client.join(state.invite);state.invite='';},'Joined simulated match');},{disabled:state.viewer!=='bob'||state.busy}));
    if(state.invite && state.viewer==='alice')inviteArea.append(make('p',`Test invitation: ${state.invite} — switch to Bob, paste into the field, then join.`, 'muted smallprint'));
    root.append(inviteArea);
    if(state.selected){
      const panel=make('div',undefined,'lobbySelected');panel.append(make('h4','Current mock session'),make('p',`${state.selected.matchId} · ${statusLabel(state.selected)} · revision ${state.selected.revision}`));
      panel.append(button('Simulate end turn',async()=>{await run(async()=>{state.selected=await client.simulateEndTurn(state.selected.matchId,state.selected.revision);},'Turn advanced in memory; no Social notification was sent');},{disabled:!state.selected.yourTurn||state.busy}));
      panel.append(make('p','This does not run Life rules or send Tavi notifications. In production, only Life validates actions and changes seats.', 'muted smallprint'));
      root.append(panel);
    }
  };
  const run=async(operation,notice)=>{
    if(state.busy)return;state.busy=true;
    let message=notice;
    try {await operation();}catch(e){message='Preview action rejected: '+e.message;}
    finally{state.busy=false;await update(message);}
  };
  void update();return {backend,client};
}
