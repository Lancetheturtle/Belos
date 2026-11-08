import { clock } from '../utils/time';
import type { Action, Position, Snapshot, Trip, Vehicle } from '../types';
export function distance(a: Position, b: Position): number {
  const r = Math.PI / 180,
    dLat = (b[0] - a[0]) * r,
    dLng = (b[1] - a[1]) * r;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}
export const free = (v: Vehicle, s: Snapshot) =>
  !v.outOfService &&
  !v.dispatchUnavailable &&
  !v.tripId &&
  v.holdUntil <= s.minute;
export function target(t: Trip): Position {
  return t.status === 'onboard'
    ? t.destination
    : (t.transferLocation ?? t.pickup);
}
export function eta(s: Snapshot, t: Trip): number | null {
  if (t.etaMinute !== undefined) return t.etaMinute;
  if (t.status === 'complete') return t.completedAt ?? s.minute;
  const v = s.vehicles.find((v) => v.id === t.vehicleId);
  if (!v || v.outOfService) return null;
  const km = v.route ? remainingDistance(v) : distance(v.position, target(t));
  return (
    Math.max(s.minute, v.holdUntil, v.unloadingUntil ?? 0) +
    km / (s.traffic ? 0.25 : 0.5)
  );
}
export function late(s: Snapshot, t: Trip): number {
  if (t.actualPickup !== undefined)
    return Math.max(0, Math.ceil(t.actualPickup - t.scheduled - 1e-7));
  return Math.max(0, Math.ceil((eta(s, t) ?? s.minute) - t.scheduled - 1e-7));
}
export function remainingDistance(v: Vehicle): number {
  if (!v.route) return 0;
  let km = 0,
    from = v.position;
  for (let i = (v.routeIndex ?? 0) + 1; i < v.route.length; i++) {
    km += distance(from, v.route[i]);
    from = v.route[i];
  }
  return km;
}
function moveOnRoad(v: Vehicle, km: number): boolean {
  const route = v.route!;
  let i = v.routeIndex ?? 0;
  while (i < route.length - 1) {
    const next = route[i + 1],
      segment = distance(v.position, next);
    if (segment <= km + 1e-9) {
      km -= segment;
      v.position = [...next];
      i++;
      v.movementPath!.push([...v.position]);
    } else {
      const p = km / segment;
      v.position = [
        v.position[0] + (next[0] - v.position[0]) * p,
        v.position[1] + (next[1] - v.position[1]) * p,
      ];
      v.movementPath!.push([...v.position]);
      break;
    }
  }
  v.routeIndex = i;
  return i >= route.length - 1;
}
function event(s: Snapshot, message: string) {
  s.events = [`${clock(s.minute)} · ${message}`, ...s.events].slice(0, 8);
}
export function createScenario(): Snapshot {
  return {
    minute: 0,
    traffic: false,
    events: ['09:00 · Transport shift started. Three pickups assigned.'],
    vehicles: [
      {
        id: 'AMB-01',
        crew: 'Crew A',
        position: [42.72, -73.687],
        outOfService: false,
        holdUntil: 0,
        holdReason: '',
        tripId: 'TR-101',
      },
      {
        id: 'AMB-02',
        crew: 'Crew B',
        position: [42.743, -73.677],
        outOfService: false,
        holdUntil: 0,
        holdReason: '',
        tripId: 'TR-102',
      },
      {
        id: 'AMB-03',
        crew: 'Crew C',
        position: [42.727, -73.66],
        outOfService: false,
        holdUntil: 0,
        holdReason: '',
        tripId: 'TR-103',
      },
      {
        id: 'AMB-04',
        crew: 'Crew D',
        position: [42.736, -73.681],
        outOfService: false,
        holdUntil: 0,
        holdReason: '',
      },
    ],
    trips: [
      {
        id: 'TR-101',
        from: 'Riverside care home',
        to: 'Troy medical center',
        pickup: [42.731, -73.688],
        destination: [42.743, -73.671],
        scheduled: 5,
        status: 'pickup',
        vehicleId: 'AMB-01',
      },
      {
        id: 'TR-102',
        from: 'Northside residence',
        to: 'Dialysis clinic',
        pickup: [42.75, -73.679],
        destination: [42.725, -73.68],
        scheduled: 10,
        status: 'pickup',
        vehicleId: 'AMB-02',
      },
      {
        id: 'TR-103',
        from: 'Eastside rehab',
        to: 'Outpatient clinic',
        pickup: [42.73, -73.654],
        destination: [42.72, -73.675],
        scheduled: 10,
        status: 'pickup',
        vehicleId: 'AMB-03',
      },
      {
        id: 'TR-104',
        from: 'Troy medical center',
        to: 'Riverside care home',
        pickup: [42.743, -73.671],
        destination: [42.731, -73.688],
        scheduled: 15,
        status: 'waiting',
      },
      {
        id: 'TR-105',
        from: 'South Troy residence',
        to: 'Dialysis clinic',
        pickup: [42.71, -73.68],
        destination: [42.725, -73.68],
        scheduled: 20,
        status: 'waiting',
      },
      {
        id: 'TR-106',
        from: 'Outpatient clinic',
        to: 'Eastside rehab',
        pickup: [42.72, -73.675],
        destination: [42.73, -73.654],
        scheduled: 25,
        status: 'waiting',
      },
    ],
  };
}
export function applyAction(state: Snapshot, action: Action): Snapshot {
  const s = structuredClone(state);
  if (action.type === 'create-call' || action.type === 'report-status')
    throw new Error('Call entry and status reports require backend mode.');
  if (action.type === 'set-speed') {
    if (
      !Number.isInteger(action.speed) ||
      action.speed < 1 ||
      action.speed > 60
    )
      throw new Error('Speed must be between 1 and 60.');
    s.simulationSpeed = action.speed;
    return s;
  }
  if (action.type === 'reoptimize')
    throw new Error('Automatic dispatch requires backend mode.');
  if (action.type === 'traffic') {
    s.traffic = action.enabled;
    event(
      s,
      action.enabled
        ? 'Road slowdown active. Travel speed reduced by half.'
        : 'Road slowdown cleared.',
    );
    return s;
  }
  if (action.type === 'advance') {
    if (
      !Number.isFinite(action.minutes) ||
      action.minutes <= 0 ||
      action.minutes > 60
    )
      throw new Error('Advance must be between 0 and 60 minutes.');
    // Step at one-second resolution so travel, holds, and pickup times remain consistent.
    const end = s.minute + action.minutes;
    for (const v of s.vehicles) v.movementPath = [[...v.position]];
    while (s.minute < end - 1e-8) {
      const dt = Math.min(1 / 60, end - s.minute);
      s.minute += dt;
      for (const v of s.vehicles) {
        if (v.outOfService || v.holdUntil > s.minute + 1e-8 || !v.tripId)
          continue;
        const t = s.trips.find((t) => t.id === v.tripId)!;
        if (v.unloadingUntil !== undefined) {
          if (s.minute >= v.unloadingUntil) {
            t.status = 'complete';
            t.completedAt = s.minute;
            delete v.tripId;
            delete v.unloadingUntil;
            delete v.route;
            delete v.routeIndex;
            event(s, `${t.id} delivered. ${v.id} available.`);
          }
          continue;
        }
        const dest = target(t),
          km = distance(v.position, dest);
        const fraction =
          km > 0 ? Math.min(1, ((s.traffic ? 0.25 : 0.5) * dt) / km) : 1;
        const arrived = v.route
          ? moveOnRoad(v, (s.traffic ? 0.25 : 0.5) * dt)
          : fraction === 1;
        if (!v.route)
          v.position = [
            v.position[0] + (dest[0] - v.position[0]) * fraction,
            v.position[1] + (dest[1] - v.position[1]) * fraction,
          ];
        if (arrived) {
          if (t.status === 'pickup') {
            if (s.minute + 1e-8 < t.scheduled) {
              if (v.route) {
                v.holdUntil = t.scheduled;
                v.holdReason = 'Waiting at pickup';
              }
              continue;
            } // Wait for scheduled pickup.
            if (t.actualPickup === undefined) t.actualPickup = s.minute;
            t.status = 'onboard';
            delete t.transferLocation;
            if (t.transportRoute) {
              v.route = structuredClone(t.transportRoute);
              v.routeIndex = 0;
              v.position = [...v.route[0]];
              v.holdUntil = s.minute + 2;
              v.holdReason = 'Loading at pickup';
            }
            event(s, `${v.id} picked up ${t.id}. Heading to ${t.to}.`);
          } else if (t.status === 'onboard') {
            if (v.route) {
              v.unloadingUntil = s.minute + 2;
              v.holdUntil = s.minute + 2;
              v.holdReason = 'Unloading at destination';
              event(s, `${v.id} arrived at ${t.to}. Waiting to unload.`);
              continue;
            }
            t.status = 'complete';
            t.completedAt = s.minute;
            delete v.tripId;
            event(s, `${t.id} delivered to ${t.to}. ${v.id} is available.`);
          }
        }
      }
    }
    s.minute = Math.round(end * 1000) / 1000;
    return s;
  }
  const v = s.vehicles.find((v) => v.id === action.vehicleId);
  if (!v) throw new Error('Vehicle not found.');
  if (action.type === 'assign') {
    const t = s.trips.find((t) => t.id === action.tripId);
    if (!t || !['waiting', 'transfer'].includes(t.status))
      throw new Error('This transport cannot be assigned.');
    if (!free(v, s)) throw new Error('Choose an available ambulance.');
    t.status = 'pickup';
    t.vehicleId = v.id;
    v.tripId = t.id;
    delete v.route;
    delete v.routeIndex;
    delete v.unloadingUntil;
    event(
      s,
      `${t.id} assigned to ${v.id}${t.transferLocation ? ' for a simulated transfer' : ''}.`,
    );
    return s;
  }
  if (action.type === 'outage') {
    if (v.outOfService) return s;
    const t = s.trips.find((t) => t.id === v.tripId);
    if (t) {
      const onboard = t.status === 'onboard';
      t.status = onboard || t.transferLocation ? 'transfer' : 'waiting';
      if (onboard) t.transferLocation = [...v.position];
      delete t.vehicleId;
      event(
        s,
        `${t.id} ${t.status === 'transfer' ? 'needs a transfer at the stopped vehicle' : 'needs reassignment'}.`,
      );
    }
    delete v.tripId;
    delete v.route;
    delete v.routeIndex;
    delete v.unloadingUntil;
    v.outOfService = true;
    v.holdUntil = s.minute;
    v.holdReason = '';
    event(s, `${v.id} is out of service.`);
    return s;
  }
  if (action.type === 'restore') {
    v.outOfService = false;
    event(s, `${v.id} returned to service. Assign a transport when ready.`);
    return s;
  }
  if (v.outOfService)
    throw new Error('Return this ambulance to service first.');
  const minutes = action.type === 'delay' ? 10 : 15;
  v.holdUntil = Math.max(s.minute, v.holdUntil) + minutes;
  v.holdReason = action.type === 'delay' ? 'Crew delay' : 'Emergency hold';
  event(s, `${v.id}: ${v.holdReason.toLowerCase()}, +${minutes} minutes.`);
  return s;
}
