import type { Trip, Vehicle } from '../types';
export const statusLabel = (t: Trip) =>
  ({
    waiting: 'Needs ambulance',
    pickup: t.transferLocation ? 'Heading to transfer' : 'Heading to pickup',
    onboard: 'Patient on board',
    transfer: 'Needs transfer',
    complete: 'Completed',
    cancelled: 'Cancelled',
  })[t.status];

// Only show a pickup beacon while this patient still needs to be collected.
// Transfers retain the original actualPickup timestamp, so check the current unit too.
export function needsPickupBeacon(trip: Trip, vehicle?: Vehicle): boolean {
  if (trip.status === 'waiting' || trip.status === 'transfer') return true;
  if (trip.status !== 'pickup' || vehicle?.activity === 'Loading patient') return false;
  return Boolean(trip.transferLocation) || trip.actualPickup === undefined;
}
