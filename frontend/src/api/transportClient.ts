import type { Action, Snapshot, TransportDirectory } from '../types';
export type ConnectionState = 'connecting' | 'connected' | 'disconnected';
const point = (p: unknown) =>
  Array.isArray(p) &&
  p.length === 2 &&
  p.every((n) => typeof n === 'number' && Number.isFinite(n)) &&
  Math.abs(p[0]) <= 90 &&
  Math.abs(p[1]) <= 180;
const object = (value: any) => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown) => typeof value === 'string' && value.trim().length > 0;
const date = (value: unknown) => text(value) && /(?:Z|[+-]\d{2}:\d{2})$/.test(value as string) && Number.isFinite(Date.parse(value as string));
const count = (value: unknown) => Number.isInteger(value) && (value as number) >= 0;
const actionTypes = ['assign','optimize','routes','outage','restore','delay','traffic','simulation','reset'];
export function validateDirectory(data: any): TransportDirectory {
  if (!object(data) || !Array.isArray(data.ambulances) || !Array.isArray(data.transport_requests))
    throw new Error('Invalid transport directory.');
  const units = new Set<string>();
  for (const v of data.ambulances) {
    if (!object(v) || !['ambulance_id', 'unit_name', 'current_location', 'service_level'].every(k => text(v[k])) ||
      !['available', 'assigned', 'en_route_to_pickup', 'at_pickup', 'transporting', 'out_of_service'].includes(v.status) ||
      units.has(v.ambulance_id) || !point([v.current_lat, v.current_lng]) ||
      !count(v.crew_count) || !count(v.stretcher_capacity) || !date(v.last_location_update_at) || !date(v.shift_end_at))
      throw new Error('Invalid ambulance in transport directory.');
    units.add(v.ambulance_id);
  }
  const requests = new Set<string>();
  for (const t of data.transport_requests) {
    if (!object(t) || !['request_id', 'patient_id', 'pickup_location', 'pickup_address', 'dropoff_location', 'dropoff_address', 'transport_type', 'mobility', 'booking_type', 'service_level'].every(k => text(t[k])) ||
      !['scheduled', 'assigned', 'en_route_to_pickup', 'at_pickup', 'transporting', 'completed', 'cancelled', 'transfer'].includes(t.status) ||
      requests.has(t.request_id) || !point([t.pickup_lat, t.pickup_lng]) || !point([t.dropoff_lat, t.dropoff_lng]) ||
      !date(t.pickup_time) || !Number.isFinite(t.planned_duration_minutes) || t.planned_duration_minutes < 0 ||
      (t.ambulance_id !== null && t.ambulance_id !== '' && (!text(t.ambulance_id) || !units.has(t.ambulance_id))))
      throw new Error('Invalid request in transport directory.');
    requests.add(t.request_id);
  }
  return data;
}
export function validateSnapshot(data: any): Snapshot {
  if (
    !object(data) ||
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
      !object(v) ||
      !text(v.id) ||
      ids.has(v.id) ||
      !point(v.position) ||
      typeof v.crew !== 'string' ||
      typeof v.outOfService !== 'boolean' ||
      !Number.isFinite(v.holdUntil) ||
      typeof v.holdReason !== 'string'
    )
      throw new Error('Invalid vehicle in backend response.');
    ids.add(v.id);
    if (v.routePhase !== undefined && !['pickup','dropoff','stopped'].includes(v.routePhase))
      throw new Error('Invalid route phase.');
    if ((v.tripId !== undefined && !text(v.tripId)) ||
        (v.routeIndex !== undefined && (!count(v.routeIndex) || !v.route || v.routeIndex >= v.route.length)) ||
        (v.movementPath !== undefined && (!Array.isArray(v.movementPath) || !v.movementPath.every(point))) ||
        (v.unloadingUntil !== undefined && !Number.isFinite(v.unloadingUntil)))
      throw new Error('Invalid vehicle movement in backend response.');
    if (
      v.route !== undefined &&
      (!Array.isArray(v.route) || !v.route.every(point))
    )
      throw new Error('Invalid road route.');
  }
  const tripIds = new Set<string>();
  for (const t of data.trips) {
    if (
      !object(t) ||
      !text(t.id) || tripIds.has(t.id) ||
      typeof t.from !== 'string' ||
      typeof t.to !== 'string' ||
      !point(t.pickup) ||
      !point(t.destination) ||
      !Number.isFinite(t.scheduled) ||
      !['waiting', 'pickup', 'onboard', 'transfer', 'complete', 'cancelled'].includes(
        t.status,
      )
    )
      throw new Error('Invalid trip in backend response.');
    tripIds.add(t.id);
    if ((t.plannedVehicleId !== undefined && !ids.has(t.plannedVehicleId)) ||
        (t.plannedSequence !== undefined && !count(t.plannedSequence)) ||
        (t.vehicleId !== undefined && !ids.has(t.vehicleId)) ||
        ['eta', 'actualPickup', 'completedAt'].some(k => t[k] !== undefined && !Number.isFinite(t[k])) ||
        (t.transferLocation !== undefined && !point(t.transferLocation)) ||
        (t.transportRoute !== undefined && (!Array.isArray(t.transportRoute) || !t.transportRoute.every(point))))
      throw new Error('Invalid trip details in backend response.');
  }
  for (const v of data.vehicles) {
    if (v.tripId !== undefined && !data.trips.some((t: any) => t.id === v.tripId && t.vehicleId === v.id))
      throw new Error('Inconsistent vehicle assignment.');
  }
  for (const t of data.trips) {
    if (t.vehicleId !== undefined && !['complete','cancelled'].includes(t.status) && !data.vehicles.some((v: any) => v.id === t.vehicleId && v.tripId === t.id))
      throw new Error('Inconsistent trip assignment.');
  }
  if (data.integration !== undefined && (!object(data.integration) ||
      typeof data.integration.source !== 'string' ||
      !['schemaReady','running','workerConnected'].every(k => typeof data.integration[k] === 'boolean') ||
      !Number.isFinite(data.integration.simulationSpeed) || data.integration.simulationSpeed <= 0 ||
      !date(data.integration.referenceAt) || typeof data.integration.routing !== 'string'))
    throw new Error('Invalid server simulation metadata.');
  if (data.directory !== undefined) validateDirectory(data.directory);
  if (data.supportedActions !== undefined && (!Array.isArray(data.supportedActions) || !data.supportedActions.every((a: unknown) => actionTypes.includes(a as string))))
    throw new Error('Invalid supported actions.');
  if (data.optimizationResults !== undefined) {
    const result = data.optimizationResults;
    if (
      !object(result) ||
      typeof result.scenarioId !== 'string' ||
      !Number.isFinite(result.tripsTotal) ||
      !count(result.tripsTotal)
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
          object(h) && typeof h.tripId === 'string' &&
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
  let connected = false;
  async function request(path: string, body?: Action) {
    // Refreshing a healthy connection is not a reconnect.
    if (!connected) status('connecting');
    try {
      const response = await fetcher(`${base.replace(/\/$/, '')}${path}`, {
        method: body ? 'POST' : 'GET',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        cache: 'no-store',
        credentials: 'same-origin',
        signal: AbortSignal.timeout(body ? 120000 : 10000),
      });
      if (!response.ok)
        throw new Error(`Transport API request failed (${response.status}) at ${path}.`);
      const snapshot = validateSnapshot(await response.json());
      connected = true;
      status('connected');
      return snapshot;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Backend unavailable';
      connected = false;
      status('disconnected', message);
      throw e;
    }
  }
  return {
    load: () => request('/transport/state'),
    act: (s: Snapshot, a: Action) => {
      if (!s.supportedActions?.includes(a.type)) return Promise.reject(new Error('This action is not supported by the server.'));
      return request('/transport/commands', a);
    },
  };
}
