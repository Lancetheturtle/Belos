export type Position = [number, number];
export type Vehicle = { route?: Position[]; routeIndex?: number; movementPath?: Position[]; unloadingUntil?: number; id: string; crew: string; position: Position; outOfService: boolean; holdUntil: number; holdReason: string; tripId?: string };
export type Trip = { transportRoute?: Position[]; id: string; from: string; to: string; pickup: Position; destination: Position; scheduled: number; status: 'waiting' | 'pickup' | 'onboard' | 'transfer' | 'complete'; vehicleId?: string; actualPickup?: number; completedAt?: number; transferLocation?: Position };
export type Snapshot = { minute: number; traffic: boolean; vehicles: Vehicle[]; trips: Trip[]; events: string[] };
export type Action = { type: 'advance'; minutes: number } | { type: 'traffic'; enabled: boolean } | { type: 'delay' | 'emergency' | 'outage' | 'restore'; vehicleId: string } | { type: 'assign'; tripId: string; vehicleId: string };
