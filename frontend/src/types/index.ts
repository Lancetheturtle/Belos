export type Position = [number, number];
export type Vehicle = {
  route?: Position[];
  routeIndex?: number;
  movementPath?: Position[];
  movementTimes?: number[];
  unloadingUntil?: number;
  id: string;
  crew: string;
  dispatchUnavailable?: boolean;
  reportedStatus?: string;
  statusReportedAt?: string;
  position: Position;
  outOfService: boolean;
  holdUntil: number;
  holdReason: string;
  tripId?: string;
};
export type Trip = {
  requestKey?: string;
  etaMinute?: number | null;
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
export type Snapshot = {
  simulationSpeed?: number;
  dispatch?: {
    status: string;
    message: string;
    routingSource: string;
    algorithm?: string;
    lastPlannedMinute?: number;
  };
  assignmentHistory?: AssignmentChange[];
  optimizationResults?: OptimizationComparison;
  minute: number;
  traffic: boolean;
  vehicles: Vehicle[];
  trips: Trip[];
  events: string[];
};
export type Action =
  | {
      type: 'create-call';
      requestKey: string;
      pickupName: string;
      destinationName: string;
      pickup: Position;
      destination: Position;
      pickupInMinutes: number;
    }
  | {
      type: 'report-status';
      vehicleId: string;
      status: 'available' | 'unavailable' | 'out_of_service';
      observedAt: string;
    }
  | { type: 'set-speed'; speed: number }
  | { type: 'reoptimize' }
  | { type: 'advance'; minutes: number }
  | { type: 'traffic'; enabled: boolean }
  | { type: 'delay' | 'emergency' | 'outage' | 'restore'; vehicleId: string }
  | { type: 'assign'; tripId: string; vehicleId: string };

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
