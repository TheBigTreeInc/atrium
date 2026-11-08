/** Atrium consumer of the proposed TaviX installed-games/v1 host feature.
 * No local registry reads or cross-extension URL construction are permitted.
 */
import {assertTaviXHostInfo} from './tavix-sdk.mjs';

export const INSTALLED_GAMES_FEATURE='tavix.installed-games/v1';
const ID=/^[a-z][a-z0-9]*(?:[.-][a-z0-9]+){2,}$/;
const VERSION=/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const CATEGORY=/^[a-z][a-z0-9-]{0,39}$/;
const ATRIUM_ID='inc.thebigtree.tavi.atrium';
function featureAuthorized(info){
 assertTaviXHostInfo(info);
 return info.extensionId===ATRIUM_ID && info.features.includes(INSTALLED_GAMES_FEATURE);
}
const own=(v,k)=>Object.prototype.hasOwnProperty.call(v,k);
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
export function validateInstalledInventory(value){
 if(!object(value)||Object.keys(value).some(k=>!['schema','games'].includes(k))||value.schema!=='tavix.installed-games.inventory/v1'||!Array.isArray(value.games)||value.games.length>150)throw Error('Invalid installed games inventory');
 const ids=new Set();
 return Object.freeze(value.games.map(g=>{
  if(!object(g)||Object.keys(g).some(k=>!['id','version','name','classification'].includes(k))||typeof g.id!=='string'||g.id.length>120||!ID.test(g.id)||!VERSION.test(g.version)||typeof g.name!=='string'||!g.name.trim()||g.name.length>60||ids.has(g.id))throw Error('Invalid installed game descriptor');
  const c=g.classification;
  if(!object(c)||c.type!=='game'||!Array.isArray(c.categories)||c.categories.length>12||new Set(c.categories).size!==c.categories.length||c.categories.some(x=>typeof x!=='string'||!CATEGORY.test(x)))throw Error('Invalid installed game classification');
  ids.add(g.id);
  return Object.freeze({id:g.id,version:g.version,name:g.name,classification:Object.freeze({type:'game',categories:Object.freeze([...c.categories])})});
 }));
}
export async function installedGamesClient(sdk){
 const info=await sdk.info();
 if(!featureAuthorized(info))return {available:false,games:[]};
 const games=validateInstalledInventory(await sdk.games.installed.list());
 return {available:true,games};
}
export async function openInstalledGame(sdk,game,inventory){
 if(!object(game)||!inventory?.available||!inventory.games?.some(g=>g.id===game.id&&g.version===game.version))throw Error('Game is not in the verified installed inventory');
 // A trust grant may be revoked between initial listing and a user pressing
 // Play. Re-negotiate before the launch request; Tavi must also recheck.
 if(!featureAuthorized(await sdk.info()))throw Error('Tavi no longer authorizes installed-game launching');
 // Never take a URL or source path from a game descriptor.
 const result=await sdk.games.installed.open({id:game.id,expectedVersion:game.version});
 if(!object(result)||result.accepted!==true||result.id!==game.id||result.version!==game.version)throw Error('Tavi did not accept this game launch');
 return result;
}
