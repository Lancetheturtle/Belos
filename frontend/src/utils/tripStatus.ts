import type { Trip } from '../types';
export const statusLabel = (t: Trip) =>
  ({
    waiting: 'Needs ambulance',
    pickup: t.transferLocation ? 'Heading to transfer' : 'Heading to pickup',
    onboard: 'Patient on board',
    transfer: 'Needs transfer',
    complete: 'Completed',
    cancelled: 'Cancelled',
  })[t.status];
