/** Read a display-only, same-origin TaviX game projection. Never install or
 * launch from a catalog URL: the approved Tavi installed-games host owns Play.
 */
const ID=/^[a-z][a-z0-9]*(?:[.-][a-z0-9]+){2,}$/;
const VERSION=/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const CATEG=/^[a-z][a-z0-9-]{0,39}$/;
const SHA=/^[a-f0-9]{64}$/;
const PLATFORMS=new Set(['web','windows','android']);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const keys=(value,allowed)=>Object.keys(value).every(k=>allowed.includes(k));
const text=(v,len)=>typeof v==='string'&&!!v.trim()&&v.length<=len&&!/[\x00-\x1f]/.test(v);
const tags=(values,max)=>Array.isArray(values)&&values.length<=max&&new Set(values).size===values.length&&values.every(x=>typeof x==='string'&&CATEG.test(x));
export function parseTavixMarketplace(value){
 if(!object(value)||!keys(value,['schema','sourceIndexSha256','games'])||value.schema!=='atrium.tavix-games/v1'||
    !(value.sourceIndexSha256===null||typeof value.sourceIndexSha256==='string'&&SHA.test(value.sourceIndexSha256))||
    !Array.isArray(value.games)||value.games.length>150||(!value.sourceIndexSha256&&value.games.length))throw Error('Invalid TaviX marketplace catalog');
 const seen=new Set();
 return Object.freeze({schema:value.schema,sourceIndexSha256:value.sourceIndexSha256,games:Object.freeze(value.games.map(g=>{
  if(!object(g)||!keys(g,['id','version','name','publisher','summary','categories','platforms','description','featured','collections'])||
     Object.keys(g).length!==10||!text(g.id,120)||!ID.test(g.id)||seen.has(g.id)||!VERSION.test(g.version)||
     !text(g.name,60)||!text(g.publisher,64)||!/^[a-z0-9-]{2,64}$/.test(g.publisher)||!text(g.summary,240)||
     !text(g.description,300)||typeof g.featured!=='boolean'||!tags(g.categories,8)||!tags(g.collections,8)||
     !Array.isArray(g.platforms)||g.platforms.length===0||new Set(g.platforms).size!==g.platforms.length||
     g.platforms.some(x=>!PLATFORMS.has(x)))throw Error('Invalid TaviX marketplace game');
  seen.add(g.id);return Object.freeze({...g,categories:Object.freeze([...g.categories]),platforms:Object.freeze([...g.platforms]),collections:Object.freeze([...g.collections])});
 }))});
}
export async function fetchTavixMarketplace(fetcher=fetch,url='./tavix-games.json'){
 if(url!=='./tavix-games.json')throw Error('TaviX marketplace must use the bundled same-origin snapshot');
 const response=await fetcher(url,{cache:'no-store',credentials:'omit',redirect:'error'});
 if(!response.ok)throw Error('TaviX marketplace snapshot unavailable');
 return parseTavixMarketplace(await response.json());
}
