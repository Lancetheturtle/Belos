export type Position = [number, number];
export type Vehicle = {
  route?: Position[];
  routeIndex?: number;
  movementPath?: Position[];
  unloadingUntil?: number;
  id: string;
  crew: string;
  position: Position;
  outOfService: boolean;
  holdUntil: number;
  holdReason: string;
  tripId?: string;
};
export type Trip = {
  eta?: number; // Authoritative arrival minute from the API.
  transportRoute?: Position[];
  id: string;
  from: string;
  to: string;
  pickup: Position;
  destination: Position;
  scheduled: number;
  status: 'waiting' | 'pickup' | 'onboard' | 'transfer' | 'complete';
  vehicleId?: string;
  actualPickup?: number;
  completedAt?: number;
  transferLocation?: Position;
};
export type TransportDirectory = {
  ambulances: DirectoryAmbulance[];
  transport_requests: DirectoryRequest[];
};
export type DirectoryAmbulance = {
  ambulance_id: string;
  unit_name: string;
  current_location: string;
  current_lat: number;
  current_lng: number;
  status: string;
  crew_count: number;
  stretcher_capacity: number;
  service_level: string;
  last_location_update_at: string;
  shift_end_at: string;
};
export type DirectoryRequest = {
  request_id: string;
  patient_id: string;
  pickup_location: string;
  pickup_address: string;
  pickup_lat: number;
  pickup_lng: number;
  pickup_time: string;
  status: string;
  dropoff_location: string;
  dropoff_address: string;
  dropoff_lat: number;
  dropoff_lng: number;
  ambulance_id: string | null;
  transport_type: string;
  mobility: string;
  planned_duration_minutes: number;
  booking_type: string;
  service_level: string;
};
export type Snapshot = {
  directory?: TransportDirectory;
  supportedActions?: Action['type'][];
  assignmentHistory?: AssignmentChange[];
  optimizationResults?: OptimizationComparison;
  minute: number;
  traffic: boolean;
  vehicles: Vehicle[];
  trips: Trip[];
  events: string[];
};
export type Action = { type: 'assign'; tripId: string; vehicleId: string };

export type AssignmentChange = {
  tripId: string;
  fromVehicleId?: string;
  toVehicleId?: string;
  reason: string;
  minute: number;
};
export type OptimizationMetrics = {
  onTimePickups: number;
  averageDelayMinutes: number;
  distanceKm: number;
  tripsCompleted: number;
};
export type OptimizationComparison = {
  scenarioId: string;
  tripsTotal: number;
  baseline: OptimizationMetrics;
  optimized: OptimizationMetrics;
};
