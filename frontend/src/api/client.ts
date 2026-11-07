import type { Action, Snapshot } from '../types';
import { applyAction, createScenario } from '../mocks/simulation';
export const isDemo=false;
const base=(import.meta.env.VITE_API_BASE_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
async function request(path:string,action?:Action):Promise<Snapshot>{
 const response=await fetch(`${base}${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(action??{}),signal:AbortSignal.timeout(10000)});
 if(!response.ok)throw new Error(`Backend request failed (${response.status}).`);
 const data=await response.json();if(!Array.isArray(data.trips)||!Array.isArray(data.vehicles)||!Array.isArray(data.events)||typeof data.minute!=='number')throw new Error('Backend must implement the transport Snapshot contract.');
 return data;
}
export const client={load:async():Promise<Snapshot>=>isDemo?createScenario():request('/transport/reset'),act:async(s:Snapshot,a:Action):Promise<Snapshot>=>isDemo?applyAction(s,a):request('/transport/action',a)};
