/** Adapter to canonical Tavi Assets 0.1.11 read-only/consent-bound consumer SDK.
 * This module does not grant entitlement, publish packs or implement an engine.
 * Tavi host is the only source of per-session pack/capability grants.
 */
import {createTaviAssetsClient,AssetsUnavailableError} from './tavi-assets-client-0.1.11.mjs';

export function createAtriumAssets(tavi){
 if(!tavi||typeof tavi.info!=='function'||typeof tavi.assetRequest!=='function')throw TypeError('Authenticated TaviX host SDK required');
 const client=createTaviAssetsClient({info:()=>tavi.info(),request:(method,params)=>tavi.assetRequest(method,params)});
 return Object.freeze({
  async connect(){
   try{return {available:true,host:await client.connect(),client};}
   catch(error){if(error instanceof AssetsUnavailableError)return {available:false,client:null};throw error;}
  },
 });
}
