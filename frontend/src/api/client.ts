import type { Conditions, Policy, SimulationAction, Snapshot } from '../types';
import { addIncident, advance, createScenario, dispatch } from '../mocks/simulation';

export const isDemo = import.meta.env.VITE_DATA_MODE !== 'api';
const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/,'');
async function request(path:string, body?:unknown):Promise<Snapshot> {
  const response=await fetch(`${base}${path}`, {method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(10000)});
  if(!response.ok) throw new Error(`Backend request failed (${response.status}). Check the API service and contract.`);
  const data=await response.json();
  if(!Array.isArray(data.vehicles)||!Array.isArray(data.incidents)||!Array.isArray(data.events)||typeof data.elapsedSeconds!=='number'||!('comparison' in data)) throw new Error('Backend response does not match the Snapshot contract.');
  return data;
}
export const client = {
  load: async (scenario:Snapshot['scenario']):Promise<Snapshot> => isDemo ? createScenario(scenario) : request(`/scenario?name=${scenario}`),
  dispatch: async (snapshot:Snapshot,policy:Policy,conditions:Conditions):Promise<Snapshot> => isDemo ? dispatch(snapshot,policy,conditions) : request('/dispatch',{policy,conditions}),
  simulate: async (snapshot:Snapshot,action:SimulationAction):Promise<Snapshot> => isDemo ? action.action==='advance'?advance(snapshot,action.seconds):addIncident(snapshot,action.priority) : request('/simulate',action),
};
