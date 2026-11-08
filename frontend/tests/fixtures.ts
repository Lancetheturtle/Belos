// Static HTTP response fixtures for automated tests only. Never imported by the app.
import type { Snapshot, TransportDirectory } from '../src/types';
export const createSnapshot = (): Snapshot => ({
  minute: 0,
  traffic: false,
  vehicles: [
    { id: 'AMB-01', crew: 'Test crew A', position: [42.7, -73.7], outOfService: false, holdUntil: 0, holdReason: '', tripId: 'TR-101' },
    { id: 'AMB-04', crew: 'Test crew D', position: [42.72, -73.72], outOfService: false, holdUntil: 0, holdReason: '' },
  ],
  trips: [
    { id: 'TR-101', from: 'Test pickup', to: 'Test destination', pickup: [42.71, -73.71], destination: [42.73, -73.73], scheduled: 5, status: 'pickup', vehicleId: 'AMB-01' },
    { id: 'TR-104', from: 'Test pickup B', to: 'Test destination B', pickup: [42.71, -73.71], destination: [42.73, -73.73], scheduled: 10, status: 'waiting' },
  ],
  events: [],
});
export const directory: TransportDirectory = {
  ambulances: [{
    ambulance_id: 'AMB-01', unit_name: 'Test unit', current_location: 'Test facility',
    current_lat: 42.7, current_lng: -73.7, status: 'available', crew_count: 2,
    stretcher_capacity: 1, service_level: 'BLS_non_emergency',
    last_location_update_at: '2026-11-07T10:00:00-05:00', shift_end_at: '2026-11-07T18:00:00-05:00',
  }],
  transport_requests: [{
    request_id: 'TEST-REQUEST', patient_id: 'TEST-PATIENT', pickup_location: 'Test pickup',
    pickup_address: 'Test pickup address', pickup_lat: 42.71, pickup_lng: -73.71,
    pickup_time: '2026-11-07T10:05:00-05:00', status: 'scheduled',
    dropoff_location: 'Test destination', dropoff_address: 'Test destination address',
    dropoff_lat: 42.73, dropoff_lng: -73.73, ambulance_id: 'AMB-01',
    transport_type: 'scheduled_transfer', mobility: 'stretcher', planned_duration_minutes: 20,
    booking_type: 'preplanned', service_level: 'BLS_non_emergency',
  }],
};
