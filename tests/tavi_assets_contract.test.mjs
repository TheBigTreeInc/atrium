import test from 'node:test';
import assert from 'node:assert/strict';
import {createAtriumAssets} from '../extensions/tavi/atrium-assets.mjs';
import {createTaviAssetsClient,AssetsUnavailableError} from '../extensions/tavi/tavi-assets-client-0.1.11.mjs';
const feature='tavi.assets/v1';
test('canonical Assets client fails closed when Social has not activated a grant',async()=>{
 const tavi={info:async()=>({features:[]}),assetRequest:async()=>{throw Error('must not be called');}};
 const session=createAtriumAssets(tavi);
 assert.deepEqual(await session.connect(),{available:false,client:null});
 await assert.rejects(createTaviAssetsClient({info:tavi.info,request:tavi.assetRequest}).connect(),AssetsUnavailableError);
});
test('Tavi-granted Asset service remains the sole owner of package discovery and customization',async()=>{
 const calls=[];
 const tavi={info:async()=>({features:[feature],api:'1.0.0'}),assetRequest:async(method,params)=>{
   calls.push([method,params]);return {schema:'tavi.assets.pack-list/v1',items:[]};
 }};
 const {available,client}=await createAtriumAssets(tavi).connect();
 assert.equal(available,true);
 await client.listPacks({type:'playing-cards',limit:5});
 assert.deepEqual(calls,[['assets.packs.list',{type:'playing-cards',limit:5}]]);
 assert.throws(()=>client.describe('../escape'),/Invalid packId/);
});
