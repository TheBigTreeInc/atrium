/** Rules-free Checkers board surface shared by an authenticated browser and Tavi.
 * A host binds an existing CheckersRemoteClient; this view never authenticates,
 * decides whether a move is legal, or stores/creates a match.
 */
const same = (a,b) => a[0] === b[0] && a[1] === b[1];
const startsWith = (path,selection) => selection.every((point,i) => same(path[i]||[-1,-1],point));

/** Follow paths advertised by the server, NEVER compute them from the board. */
export function selectServerPath(actions, selected, square) {
  const choices = Array.isArray(actions) ? actions : [];
  const next = [...selected, square];
  const possible = choices.filter(path => startsWith(path,next));
  if (possible.length) {
    const complete = possible.find(path => path.length === next.length);
    return {selected:complete ? [] : next, complete:complete || null};
  }
  return {selected: choices.some(path => same(path[0],square)) ? [square] : [], complete:null};
}

export async function mountRemoteCheckers(root, client) {
  if (!root || typeof root.replaceChildren !== 'function' || !client ||
      typeof client.join !== 'function' || typeof client.legalActions !== 'function') {
    throw new TypeError('remote_board_binding_required');
  }
  const doc=root.ownerDocument;
  let selected=[], actions=[], busy=false, message='';
  const el=(tag,text) => {
    const n=doc.createElement(tag);
    if (text !== undefined) n.textContent=text;
    return n;
  };
  const toolbar=el('div');toolbar.className='checkers-remote-toolbar';
  const heading=el('p'); heading.setAttribute('role','status');
  const detail=el('p');detail.setAttribute('aria-live','polite');
  const board=el('div');board.className='checkers-remote-board';board.setAttribute('role','group');
  board.setAttribute('aria-label','Checkers match board');
  const reload=el('button','Refresh match');reload.type='button';
  const retry=el('button','Retry last move');retry.type='button';
  toolbar.append(heading,reload,retry);root.replaceChildren(toolbar,board,detail);

  function paint(){
    const snap=client.snapshot;
    board.replaceChildren();
    heading.textContent=snap ? (snap.state.winner ?
      `${snap.state.winner==='r'?'Red':'Black'} wins` :
      `Revision ${snap.revision} · ${snap.state.turn==='r'?'Red':'Black'} to move`):'Joining match';
    detail.textContent=message || (client.seat ? `Your seat: ${client.seat}`:'Waiting for seat');
    reload.disabled=busy;retry.disabled=busy||!client.pending;
    if (!snap) return;
    for (let r=0;r<8;r++) for (let c=0;c<8;c++) {
      const square=[r,c], piece=snap.state.board[r][c], button=el('button');
      button.type='button';button.className='checkers-remote-square'+((r+c)%2?' dark':'');
      const selectable=actions.some(path=>startsWith(path,[...selected,square]) ||
        (!selected.length && same(path[0],square)));
      button.disabled=busy||!selectable||snap.state.winner!==null;
      if (selected.some(point=>same(point,square)))button.classList.add('selected');
      button.setAttribute('aria-label',`Row ${r+1}, column ${c+1}: `+
        (piece==='.'?'empty':`${piece.toLowerCase()==='r'?'red':'black'}${piece!==piece.toLowerCase()?' king':''}`));
      if(piece!=='.'){
        const chip=el('span');chip.className='checkers-remote-piece '+
          (piece.toLowerCase()==='r'?'red':'black')+(piece!==piece.toLowerCase()?' king':'');
        chip.setAttribute('aria-hidden','true');button.append(chip);
      }
      button.addEventListener('click',()=>clickSquare(square));board.append(button);
    }
  }
  async function synchronize({join=false}={}){
    busy=true;paint();
    try {
      if(join)await client.join();else await client.refresh();
      actions=(await client.legalActions()).actions;
      selected=[];message='';
    }catch(error){
      actions=[];selected=[];message=`Match unavailable: ${error.code||'network_error'}`;
    }finally{busy=false;paint();}
  }
  async function clickSquare(square){
    if(busy)return;
    const chosen=selectServerPath(actions,selected,square);
    selected=chosen.selected;
    if(!chosen.complete){paint();return;}
    busy=true;paint();
    try{
      await client.move(chosen.complete);
      actions=(await client.legalActions()).actions;
      message='';
    }catch(error){
      message=`Move not completed: ${error.code||'network_error'}`;
      if(!client.pending){
        try { await client.refresh();actions=(await client.legalActions()).actions; }
        catch {actions=[];}
      }
    }finally {busy=false;paint();}
  }
  retry.addEventListener('click',async()=>{
    if (busy||!client.pending)return;
    busy=true;paint();
    try {await client.retryPending();actions=(await client.legalActions()).actions;message='';}
    catch(error){message=`Retry not completed: ${error.code||'network_error'}`;}
    finally{busy=false;paint();}
  });
  reload.addEventListener('click',()=>synchronize());
  await synchronize({join:true});
  return {refresh:()=>synchronize(), destroy:()=>root.replaceChildren()};
}
