// Bundled into a sandboxed srcdoc frame. No network, storage, parent messages or privileged APIs.
(() => {
  const boardNode=document.querySelector('#board');
  const statusNode=document.querySelector('#status');
  const hintNode=document.querySelector('#hint');
  const logNode=document.querySelector('#moveLog');
  const modeButton=document.querySelector('#mode');
  let board=initialBoard(),turn='r',winner=null,selected=[],staff=false,busy=false,history=[];
  let round=0;
  const same=(a,b)=>a[0]===b[0]&&a[1]===b[1];
  const prefix=(path,part)=>part.every((item,i)=>same(item,path[i]||[-1,-1]));
  function status() {
    const moves=winner?[]:legalMoves(board,turn);
    statusNode.textContent=winner?`${winner==='r'?'Red':'Black'} wins!`:
      busy?'Staff is thinking…':`${turn==='r'?'Red':'Black'} to move`;
    hintNode.textContent=winner?'Start another game to play again.':
      selected.length?`Choose a highlighted destination${selected.length>1?' to finish the capture chain':''}.`:
      moves.some(m=>m.length>2||Math.abs(m[1][0]-m[0][0])===2)?'Capture required.':'Select a piece to see legal moves.';
  }
  function paint(){
    status();boardNode.replaceChildren();
    const options=winner?[]:legalMoves(board,turn);
    const targets=selected.length?options.filter(move=>prefix(move,selected)&&move.length>selected.length)
      .map(move=>move[selected.length]):[];
    for(let r=0;r<8;r++)for(let c=0;c<8;c++){
      const cell=document.createElement('button');cell.type='button';cell.className='cell'+((r+c)%2?' dark':'');
      const piece=board[r][c];const here=[r,c];
      if(targets.some(p=>same(p,here))) cell.classList.add('choice');
      if(selected.length&&same(selected[selected.length-1],here)) cell.classList.add('selected');
      cell.setAttribute('aria-label',`Row ${r+1}, column ${c+1}${piece!=='.'?', '+(piece.toLowerCase()==='r'?'red':'black')+(piece!==piece.toLowerCase()?' king':''):' empty'}`);
      if(piece!=='.'){
        const disc=document.createElement('span');disc.className='piece '+(piece.toLowerCase()==='r'?'red':'black')+(piece!==piece.toLowerCase()?' king':'');
        disc.setAttribute('aria-hidden','true');cell.append(disc);
      }
      cell.addEventListener('click',()=>select(here));boardNode.append(cell);
    }
    logNode.replaceChildren();for(const item of history.slice(-8).reverse()){
      const li=document.createElement('li');li.textContent=item;logNode.append(li);
    }
  }
  function complete(path) {
    const actor=turn;const next=applyMove(board,turn,path);board=next.board;turn=next.turn;winner=next.winner;selected=[];
    history.push(`${actor==='r'?'Red':'Black'}: ${path.map(([r,c])=>`${String.fromCharCode(97+c)}${8-r}`).join(' → ')}`);
    paint();
    if(!winner&&turn==='b'&&staff){
      busy=true;paint();const expected=round;
      setTimeout(()=>{
        if(expected!==round||!busy)return;
        const reply=staffMove(board,'b');busy=false;
        if(reply)complete(reply);else paint();
      },260);
    }
  }
  function select(here){
    if(winner||busy||(staff&&turn==='b'))return;
    const options=legalMoves(board,turn);
    if(options.some(p=>same(p[0],here)) && (!selected.length || same(selected[0],here))) {
      selected=[here];paint();return;
    }
    if(selected.length){
      const next=[...selected,here];const possible=options.filter(p=>prefix(p,next));
      if(possible.length){
        const finished=possible.find(p=>p.length===next.length);
        if(finished) complete(finished);else{selected=next;paint();}
        return;
      }
    }
    selected=options.some(p=>same(p[0],here))?[here]:[];paint();
  }
  function reset(){round++;board=initialBoard();turn='r';winner=null;selected=[];history=[];busy=false;paint();}
  document.querySelector('#restart').addEventListener('click',reset);
  modeButton.addEventListener('click',()=>{staff=!staff;modeButton.textContent=staff?'Play two-player':'Play vs Staff';reset();});
  paint();
})();
