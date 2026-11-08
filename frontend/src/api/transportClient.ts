import type { Action, Snapshot } from '../types';
export type ConnectionState = 'connecting' | 'connected' | 'disconnected';
const point = (p: unknown) =>
  Array.isArray(p) &&
  p.length === 2 &&
  p.every((n) => typeof n === 'number' && Number.isFinite(n)) &&
  Math.abs(p[0]) <= 90 &&
  Math.abs(p[1]) <= 180;
export function validateSnapshot(data: any): Snapshot {
  if (
    !data ||
    !Number.isFinite(data.minute) ||
    typeof data.traffic !== 'boolean' ||
    !Array.isArray(data.vehicles) ||
    !Array.isArray(data.trips) ||
    !Array.isArray(data.events) ||
    !data.events.every((x: unknown) => typeof x === 'string')
  )
    throw new Error('Invalid transport snapshot.');
  const ids = new Set<string>();
  for (const v of data.vehicles) {
    if (
      typeof v.id !== 'string' ||
      ids.has(v.id) ||
      !point(v.position) ||
      typeof v.crew !== 'string' ||
      typeof v.outOfService !== 'boolean' ||
      !Number.isFinite(v.holdUntil) ||
      typeof v.holdReason !== 'string'
    )
      throw new Error('Invalid vehicle in backend response.');
    ids.add(v.id);
    if (
      v.route !== undefined &&
      (!Array.isArray(v.route) || !v.route.every(point))
    )
      throw new Error('Invalid road route.');
  }
  for (const t of data.trips)
    if (
      typeof t.id !== 'string' ||
      typeof t.from !== 'string' ||
      typeof t.to !== 'string' ||
      !point(t.pickup) ||
      !point(t.destination) ||
      !Number.isFinite(t.scheduled) ||
      !['waiting', 'pickup', 'onboard', 'transfer', 'complete'].includes(
        t.status,
      )
    )
      throw new Error('Invalid trip in backend response.');
  if (data.optimizationResults) {
    const result = data.optimizationResults;
    if (
      typeof result.scenarioId !== 'string' ||
      !Number.isFinite(result.tripsTotal) ||
      result.tripsTotal <= 0
    )
      throw new Error('Invalid optimization comparison.');
    for (const group of [result.baseline, result.optimized])
      if (
        !group ||
        ![
          'onTimePickups',
          'averageDelayMinutes',
          'distanceKm',
          'tripsCompleted',
        ].every((k) => Number.isFinite(group[k]) && group[k] >= 0) ||
        group.onTimePickups > result.tripsTotal ||
        group.tripsCompleted > result.tripsTotal
      )
        throw new Error('Invalid optimization metrics.');
  }
  if (
    data.assignmentHistory !== undefined &&
    (!Array.isArray(data.assignmentHistory) ||
      !data.assignmentHistory.every(
        (h: any) =>
          typeof h.tripId === 'string' &&
          Number.isFinite(h.minute) &&
          typeof h.reason === 'string' &&
          (h.fromVehicleId === undefined ||
            typeof h.fromVehicleId === 'string') &&
          (h.toVehicleId === undefined || typeof h.toVehicleId === 'string'),
      ))
  )
    throw new Error('Invalid assignment history.');
  return data;
}
export function createTransportClient(
  base: string,
  fetcher: typeof fetch,
  status: (state: ConnectionState, error?: string) => void,
) {
  async function request(path: string, body?: Action | {}) {
    status('connecting');
    try {
      const response = await fetcher(`${base.replace(/\/$/, '')}${path}`, {
        method: body ? 'POST' : 'GET',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok)
        throw new Error(`Backend request failed (${response.status}).`);
      const snapshot = validateSnapshot(await response.json());
      status('connected');
      return snapshot;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Backend unavailable';
      status('disconnected', message);
      throw e;
    }
  }
  return {
    load: () => request('/transport/state'),
    reset: () => request('/transport/reset', {}),
    act: (_s: Snapshot, a: Action) => request('/transport/action', a),
  };
}
