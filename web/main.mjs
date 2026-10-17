import {validateEntry,loadIsolatedApp} from '../src/apphost.mjs';
const area=document.querySelector('#apps');
const stage=document.querySelector('#stage');
async function init(){
 try {
   const response=await fetch('./catalog.json',{cache:'no-store'});
   if(!response.ok)throw Error('catalog not published');
   const data=await response.json();
   if(!Array.isArray(data.apps)||!Array.isArray(data.allowedOrigins))throw Error('invalid catalog');
   const published=data.apps.filter(x=>x.status==='published');
   if(!published.length)return;
   area.replaceChildren();
   for (const item of published) {
     const card=document.createElement('article');card.className='tile';
     const name=document.createElement('h2');name.textContent=item.title;
     const desc=document.createElement('p');desc.textContent=item.description || item.id;
     const launch=document.createElement('button');launch.textContent='Open';
     launch.addEventListener('click',async()=>{
       stage.textContent='Opening verified app…';
       try{await loadIsolatedApp(item,stage,data.allowedOrigins);}catch(e){stage.textContent='Cannot open app: '+e.message;}
     });card.append(name,desc,launch);area.append(card);
   }
 }catch(err){stage.textContent='Catalog unavailable: '+err.message;}
}
init();
