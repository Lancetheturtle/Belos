# Frontend / Tiger Data API contract

The source tables are `ambulances` (15 existing records at verification) and `transport_requests` (60 existing records). The API reads them directly and preserves their IDs. The original backend ORM tables and legacy services are retained. Five additive `belos_transport_*` tables persist the shared clock, plans/geometry, holds, events and position history.

## Reads

`GET /transport/state` returns a `Snapshot` as defined in `src/types/index.ts`. `/transport/snapshot` aliases it. Required fields: finite `minute`, boolean `traffic`, `vehicles`, `trips`, string-array `events`. Reads do not mutate or advance the simulation. Empty arrays are valid. Positions and geometry use `[latitude, longitude]`; OSRM conversion happens in Python.

A vehicle includes `id`, `crew`, `position`, `outOfService`, `holdUntil`, `holdReason`, optional `tripId`, `route`, `routeIndex`. Trips include `id`, `from`, `to`, `pickup`, `destination`, `scheduled`, `status`, optional `vehicleId`, `eta`, `actualPickup`, `completedAt`, `transferLocation`, `transportRoute`, `plannedVehicleId`, `plannedSequence`. Active references must agree on both sides. Completed requests may retain their historical unit ID. Queued assignments appear as waiting trips with `plannedVehicleId` until the worker activates them.

`minute`, `scheduled`, holds, actual pickup/completion and ETA use minutes relative to `integration.referenceAt`: 09:00 America/New_York on the earliest dataset date. The recorded clock is initialized from existing ambulance location-update timestamps. The worker advances it independently; API reads never do. Raw directory timestamps remain timezone-aware ISO strings, with dates retained across midnight.

Directory request statuses map to dispatch statuses: scheduled -> waiting; assigned/en_route_to_pickup/at_pickup -> pickup; transporting -> onboard; completed -> complete; cancelled -> cancelled; transfer -> transfer. The source directory preserves its native status names. A transfer keeps the patient at the stopped vehicle location until explicitly assigned a replacement.

`directory` contains full `ambulances` and `transport_requests` projections using the explicit `DirectoryAmbulance` and `DirectoryRequest` types. Null/empty ambulance IDs mean unassigned. IDs are unique, and referenced units must exist. No pagination, renumbering, invented patient records, or replacement demo data is used.

Optional `assignmentHistory` is authoritative backend history. `optimizationResults` is reserved for measured paired-run comparisons; no example numbers are substituted. `integration` includes `source`, `schemaReady`, `running`, `workerConnected`, `simulationSpeed`, `referenceAt` and `routing` description. `supportedActions` lists available commands and is empty before extension initialization.

## Writes

The frontend uses `POST /transport/commands`, not the preserved legacy `/transport/action`. Payloads:

```json
{"type":"assign","tripId":"<database request id>","vehicleId":"<database ambulance id>"}
{"type":"routes"}
{"type":"optimize"}
{"type":"delay","vehicleId":"<id>","minutes":10}
{"type":"outage","vehicleId":"<id>"}
{"type":"restore","vehicleId":"<id>"}
{"type":"traffic","enabled":true}
{"type":"simulation","running":true,"speed":15}
```

Each successful write returns the complete updated snapshot. Invalid commands/records return 422; missing records 404; conflicts 409; routing failures 502; unavailable database or missing extension initialization 503. The browser performs no optimistic dispatch mutation. Simulation running/speed flags affect the separate Python worker, not the browser clock.

`GET /transport/routes/{vehicle_id}/{trip_id}` previews a real-directory vehicle-to-pickup road route without saving or assigning it. Geometry is persisted when preparing active routes, assigning or replanning; normal polling makes no OSRM requests. `GET /transport/diagnostics` exposes source counts and worker readiness; `GET /transport/positions/{vehicle_id}` exposes bounded persisted position history.

See [backend/README.md](../backend/README.md) for commands, implementation boundaries and verified limitations.
