import { createTransportClient, type ConnectionState } from './transportClient';
import type { Action, Snapshot, TransportDirectory } from '../types';

const emptyDirectory: TransportDirectory = { ambulances: [], transport_requests: [] };
export const getDirectory = (s: Snapshot) => s.directory ?? emptyDirectory;
export const canAct = (s: Snapshot, action: Action['type']) =>
  Boolean(s.supportedActions?.includes(action));

type Status = { state: ConnectionState; error?: string };
let connection: Status = { state: 'connecting' };
const listeners = new Set<() => void>();
export const subscribeConnection = (listener: () => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};
export const getConnection = () => connection;
export const client = createTransportClient(
  import.meta.env?.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  (...args) => fetch(...args),
  (state, error) => {
    connection = { state, error };
    listeners.forEach((fn) => fn());
  },
);
