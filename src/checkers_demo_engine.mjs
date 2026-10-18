/** Standalone American checkers rules for operator-approved first-party preview.
 * Mirrors src/checkers.py: red downward; forced full capture chains;
 * men stop on promotion; deterministic baseline Staff opponent.
 * This preview stores no matches and never claims Looprd multiplayer authority.
 */
export const initialBoard = () => Array.from({length:8}, (_, r) => Array.from({length:8}, (_,c) =>
  (r+c)%2 ? (r<3 ? 'r' : (r>4 ? 'b' : '.')) : '.').join(''));
const inRange = (r,c) => r>=0 && r<8 && c>=0 && c<8;
const dirs = p => p === p.toUpperCase() ? [[1,1],[1,-1],[-1,1],[-1,-1]] :
  p==='r' ? [[1,1],[1,-1]] : [[-1,1],[-1,-1]];
const own = (p,player) => p!=='.' && p.toLowerCase()===player;
const enemy = (a,b) => b!=='.' && a.toLowerCase()!==b.toLowerCase();
const crown = (p,row) => (p==='r' && row===7) || (p==='b' && row===0);
function validate(board,player) {
  if (!Array.isArray(board) || board.length!==8 || !board.every(row=>typeof row==='string' && row.length===8)) throw Error('invalid board');
  if (!['r','b'].includes(player)) throw Error('invalid player');
  for(let r=0;r<8;r++) for(let c=0;c<8;c++) {
    const p=board[r][c];
    if (!'.rbRB'.includes(p) || (p!=='.' && (r+c)%2===0)) throw Error('invalid square');
  }
}
function captures(matrix,r,c,path) {
  const piece=matrix[r][c], result=[];
  for(const [dr,dc] of dirs(piece)) {
    const mr=r+dr,mc=c+dc,nr=r+2*dr,nc=c+2*dc;
    if(!inRange(nr,nc) || !enemy(piece,matrix[mr][mc]) || matrix[nr][nc]!=='.') continue;
    const copy=matrix.map(row=>row.slice());
    copy[r][c]='.';copy[mr][mc]='.';
    const crowned=crown(piece,nr);
    copy[nr][nc]=crowned?piece.toUpperCase():piece;
    const next=[...path,[nr,nc]];
    if(crowned) result.push(next);
    else {const again=captures(copy,nr,nc,next);result.push(...(again.length?again:[next]));}
  }
  return result;
}
const comparePath=(a,b) => {
  for(let i=0;i<Math.min(a.length,b.length);i++) for(let k=0;k<2;k++)
    if(a[i][k]!==b[i][k]) return a[i][k]-b[i][k];
  return a.length-b.length;
};
export function legalMoves(board,player) {
  validate(board,player);
  const matrix=board.map(row=>[...row]), jumps=[], walks=[];
  for(let r=0;r<8;r++) for(let c=0;c<8;c++) {
    const p=matrix[r][c]; if(!own(p,player)) continue;
    jumps.push(...captures(matrix,r,c,[[r,c]]));
    for(const [dr,dc] of dirs(p)) {
      const nr=r+dr,nc=c+dc;
      if(inRange(nr,nc) && matrix[nr][nc]==='.') walks.push([[r,c],[nr,nc]]);
    }
  }
  return (jumps.length?jumps:walks).sort(comparePath);
}
export function applyMove(board,player,path) {
  const legal=legalMoves(board,player);
  if (!legal.some(m=>JSON.stringify(m)===JSON.stringify(path))) throw Error('illegal or incomplete move');
  const matrix=board.map(row=>[...row]);
  let [r,c]=path[0], p=matrix[r][c]; matrix[r][c]='.';
  for(const [nr,nc] of path.slice(1)) {
    if(Math.abs(nr-r)===2) matrix[(r+nr)/2][(c+nc)/2]='.';
    r=nr;c=nc;
  }
  if(crown(p,r)) p=p.toUpperCase();
  matrix[r][c]=p;
  const nextBoard=matrix.map(row=>row.join(''));
  const opponent=player==='r'?'b':'r';
  const winner=legalMoves(nextBoard,opponent).length?null:player;
  return {board:nextBoard,turn:winner?null:opponent,winner};
}
export function staffMove(board,player) { return legalMoves(board,player)[0]??null; }
