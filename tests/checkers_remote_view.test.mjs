import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {selectServerPath} from '../src/checkers_remote_view.mjs';

const serverPaths=[[[2,1],[4,3],[6,5]],[[2,1],[4,3],[6,1]],[[2,5],[3,4]]];
test('board follows only server-provided full capture paths',()=>{
  assert.deepEqual(selectServerPath(serverPaths,[],[2,1]),{selected:[[2,1]],complete:null});
  assert.deepEqual(selectServerPath(serverPaths,[[2,1]],[4,3]),{selected:[[2,1],[4,3]],complete:null});
  assert.deepEqual(selectServerPath(serverPaths,[[2,1],[4,3]],[6,5]),
    {selected:[],complete:serverPaths[0]});
  assert.deepEqual(selectServerPath(serverPaths,[[2,1],[4,3]],[5,5]),
    {selected:[],complete:null});
  assert.deepEqual(selectServerPath(serverPaths,[],[0,0]),{selected:[],complete:null});
});

test('remote board surface cannot calculate or persist authoritative moves',()=>{
  const src=readFileSync(new URL('../src/checkers_remote_view.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(src,/\b(applyMove|legalMoves|initialBoard|localStorage|sessionStorage|Authorization|Bearer)\b/);
  assert.match(src,/client\.legalActions\(\)/);
  assert.match(src,/client\.move\(chosen\.complete\)/);
});

class Element {
  constructor(doc,tag){
    this.ownerDocument=doc;this.tagName=tag;this.children=[];this.handlers={};this.attrs={};
    this.classList={add:()=>{}};this.textContent='';this.disabled=false;
  }
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  addEventListener(name,fn){this.handlers[name]=fn;}
  setAttribute(name,value){this.attrs[name]=value;}
}

test('reusable board view renders 64 cells and submits only a server-advertised full path',async()=>{
  const {mountRemoteCheckers}=await import('../src/checkers_remote_view.mjs');
  const doc={createElement(tag){return new Element(doc,tag);}};
  const root=new Element(doc,'section');
  const original=['.r.r.r.r','r.r.r.r.','.r.r.r.r','........','........','b.b.b.b.','.b.b.b.b','b.b.b.b.'];
  const current={matchId:'match-one',revision:0,state:{board:original,turn:'r',winner:null}};
  const sent=[];
  const thin={snapshot:current,seat:null,pending:null,
    async join(){this.seat='red';return {seat:'red',match:this.snapshot};},
    async refresh(){return this.snapshot;},
    async legalActions(){return {actions:this.snapshot.revision===0?[[[2,1],[3,0]]]:[]};},
    async move(path){sent.push(path);this.snapshot={...this.snapshot,revision:1,state:{...this.snapshot.state,turn:'b'}};}
  };
  const mounted=await mountRemoteCheckers(root,thin);
  assert.equal(root.children[1].children.length,64);
  assert.equal(root.children[1].children[0].disabled,true);
  await root.children[1].children[17].handlers.click();
  await root.children[1].children[24].handlers.click();
  assert.deepEqual(sent,[[[2,1],[3,0]]]);
  assert.match(root.children[0].children[0].textContent,/Revision 1/);
  mounted.destroy();assert.equal(root.children.length,0);
});
