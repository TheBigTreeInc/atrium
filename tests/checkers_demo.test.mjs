import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {initialBoard,legalMoves,applyMove,staffMove} from '../src/checkers_demo_engine.mjs';
import {bundleCheckers,stageCheckers} from '../tools/stage_checkers.mjs';
import {parsePublicCatalog} from '../src/catalog_client.mjs';
const blank = pieces=>{
  const rows=Array.from({length:8},()=>Array(8).fill('.'));
  for(const [r,c,p] of pieces)rows[r][c]=p;
  return rows.map(row=>row.join(''));
};
test('initial board and deterministic Staff match baseline American checkers',()=>{
  const b=initialBoard();
  assert.equal(b.length,8);
  assert.equal(b.join('').match(/r/g).length,12);
  assert.equal(b.join('').match(/b/g).length,12);
  const legal=legalMoves(b,'r');
  assert.equal(legal.length,7);
  assert.deepEqual(staffMove(b,'r'),legal[0]);
  const result=applyMove(b,'r',legal[0]);
  assert.equal(result.turn,'b');
  assert.equal(legalMoves(result.board,'b').length>0,true);
});
test('captures mandatory, complete chain required, and legal jump applied',()=>{
  const b=blank([[2,1,'r'],[3,2,'b'],[5,4,'b']]);
  const jumps=legalMoves(b,'r');
  assert.deepEqual(jumps,[[[2,1],[4,3],[6,5]]]);
  assert.throws(()=>applyMove(b,'r',[[2,1],[4,3]]),/illegal/);
  const state=applyMove(b,'r',jumps[0]);
  assert.equal(state.board[6][5],'r');
  assert.equal(state.winner,'r');
});
test('crown stops capture chain and upper-case king can move backwards',()=>{
  const b=blank([[5,0,'r'],[6,1,'b'],[6,3,'b']]);
  const legal=legalMoves(b,'r');
  assert.deepEqual(legal,[[[5,0],[7,2]]]);
  const next=applyMove(b,'r',legal[0]);
  assert.equal(next.board[7][2],'R');
  const king=blank([[4,3,'R']]);
  assert(legalMoves(king,'r').some(p=>p[1][0]===3));
});
test('invalid board rejected and no privileged runtime bridge is in preview UI',async()=>{
  assert.throws(()=>legalMoves(['invalid'],'r'),/board/);
  const ui=await readFile(new URL('../src/checkers_demo_ui.mjs',import.meta.url),'utf8');
  for(const forbidden of ['localStorage','sessionStorage','parent.postMessage','fetch(', 'XMLHttpRequest','WebSocket','eval('])
    assert.equal(ui.includes(forbidden),false,forbidden);
});
test('staging is explicitly scoped to static Pages, content hashed, repeatable and verifiable',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'atrium-preview-'));
  try{
    const config={schema:'atrium.catalog-source/v1',gatewayUrl:''};
    const empty={schema:'atrium.catalog-snapshot/v1',allowedOrigins:[],apps:[]};
    await writeFile(join(dir,'catalog-config.json'),JSON.stringify(config));
    await writeFile(join(dir,'catalog.json'),JSON.stringify(empty));
    const {entry,digest,bytes}=await stageCheckers({output:dir});
    const html=await readFile(join(dir,'games','checkers',digest,'index.html'));
    const catalog=JSON.parse(await readFile(join(dir,'catalog.json'),'utf8'));
    assert.equal(createHash('sha256').update(html).digest('hex'),digest);
    assert.equal(html.length,bytes);
    assert(html.toString().includes('Checkers'));
    assert(!html.toString().includes('__ATRIUM_CHECKERS_'));
    assert.equal(parsePublicCatalog(catalog).apps[0].entry,entry);
    assert.equal(catalog.apps[0].status,'published');
    assert.equal(catalog.apps[0].id,'atrium.checkers.preview');
    await assert.rejects(()=>stageCheckers({output:dir}),/empty preview/);
    await writeFile(join(dir,'catalog.json'),JSON.stringify(empty));
    await writeFile(join(dir,'catalog-config.json'),JSON.stringify({...config,gatewayUrl:'https://catalog.example.org/catalog.json'}));
    await assert.rejects(()=>stageCheckers({output:dir}),/live gateway/);
  }finally{await rm(dir,{recursive:true,force:true});}
});
test('bundler requires known source placeholders',()=>{
  assert.throws(()=>bundleCheckers('<html></html>','export const initialBoard = 1;',''),/placeholders/);
});
