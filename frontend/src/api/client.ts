import { prepareRoads } from './roadRouting';
import { createTransportClient, type ConnectionState } from './transportClient';
import type { Action, Snapshot } from '../types';
import { applyAction, createScenario } from '../mocks/simulation';
export const isDemo = import.meta.env.VITE_DATA_MODE !== 'api';
type Status = { state: ConnectionState | 'demo'; error?: string };
let connection: Status = { state: isDemo ? 'demo' : 'connecting' };
const listeners = new Set<() => void>();
export const subscribeConnection = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export const getConnection = () => connection;
const backend = createTransportClient(
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  (...args) => fetch(...args),
  (state, error) => {
    connection = { state, error };
    listeners.forEach((fn) => fn());
  },
);
export type ScenarioName = 'normal' | 'breakdown' | 'crew-delay';
export async function demoScenario(name: ScenarioName): Promise<Snapshot> {
  if (!isDemo)
    throw new Error('Preset scenarios are available in demo mode only.');
  let s = createScenario();
  if (name !== 'normal')
    s = applyAction(s, {
      type: name === 'breakdown' ? 'outage' : 'delay',
      vehicleId: 'AMB-01',
    });
  return prepareRoads(s);
}
export const client = {
  load: async (): Promise<Snapshot> =>
    isDemo ? prepareRoads(createScenario()) : backend.load(),
  reset: async (): Promise<Snapshot> =>
    isDemo ? prepareRoads(createScenario()) : backend.reset(),
  act: async (s: Snapshot, a: Action): Promise<Snapshot> =>
    isDemo ? prepareRoads(applyAction(s, a)) : backend.act(s, a),
};
