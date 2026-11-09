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
export function needsPickupBeacon(trip: Trip, minute: number, vehicle?: Vehicle): boolean {
  if (trip.status === 'transfer') return true;
  if (!['waiting', 'pickup'].includes(trip.status) || vehicle?.activity === 'Loading patient') return false;
  // Stranded patients need immediate recovery, regardless of the original schedule.
  if (trip.transferLocation) return true;
  if (trip.actualPickup !== undefined) return false;
  return trip.scheduled - minute <= 60;
}
