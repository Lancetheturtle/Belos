# Proposed medical transport API

Replaces the earlier scenario/dispatch incident contract. Coordinate with the backend developer before enabling API mode.

- POST /transport/reset with {} returns the initial shift Snapshot.
- POST /transport/action accepts an Action and returns the complete updated Snapshot.

Canonical types: frontend/src/types/index.ts. Snapshot: minute (minutes since 09:00), traffic (boolean), vehicles, trips, events (newest first). Positions are [latitude, longitude]. Scheduled times, holds, and actual timestamps are minutes relative to 09:00.

Actions:

```json
{"type":"advance","minutes":5}
{"type":"traffic","enabled":true}
{"type":"delay","vehicleId":"AMB-01"}
{"type":"emergency","vehicleId":"AMB-01"}
{"type":"outage","vehicleId":"AMB-01"}
{"type":"restore","vehicleId":"AMB-01"}
{"type":"assign","tripId":"TR-101","vehicleId":"AMB-04"}
```

Crew delay adds 10 minutes, emergency interruption adds 15; holds stack. Outages stop movement and unlink the assignment. Before pickup, the trip returns to waiting; onboard, preserve the patient's position in transferLocation and set transfer status. An explicit available-unit assignment is required. Restore never silently reclaims a reassigned trip. Preserve actualPickup across a transfer. Completion releases the unit.

Frontend currently derives demo ETA from distance, holdUntil, and global traffic. Replace these display helpers with authoritative backend ETA fields when integrating road routing. Backend owns state; UI requests advances and renders returned snapshots. Add session IDs for multi-user support and configure CORS for the frontend origin. Do not implement these demo assumptions as live transport protocols.

## Road simulation geometry

Vehicles may include route ([lat,lng][]), routeIndex (current segment start index), movementPath (the polyline traversed during the latest state tick), and unloadingUntil (simulation minutes). Trips may include transportRoute for pickup-to-destination geometry. The demo uses OSRM driving routes from OpenStreetMap, with bundled initial route fixtures. New replacement approaches request OSRM with a timeout; routing failures surface as errors instead of substituting direct lines. API implementations should return route geometry and movementPath to support the same rendering.

The demo clock runs continuously at 15x with pause/resume. Road travel is modeled at 30 km/h (15 with slowdown), with scheduled-pickup waiting, two-minute loading, and two-minute unloading. Route geometry represents ordinary driving roads; travel speed and wait durations are simulation assumptions, not live traffic estimates. Routing docs: https://project-osrm.org/docs/v5.24.0/api/#route-service .
## Current frontend integration (five-feature update)

This section supersedes the earlier initial-load behavior. GET /transport/state returns a complete Snapshot without resetting it. POST /transport/reset with {} explicitly resets the shift. POST /transport/action retains its existing action shapes. API mode polls state approximately once per second while running; the backend owns simulation time. Pause only stops the viewer polling in API mode. Demo mode still runs locally at 15x. Opening the page or pressing connection Retry never resets state.

Connection status follows actual requests: connecting, connected after a validated snapshot, disconnected after HTTP/network/schema failure, and retry. Local demo mode is labeled as local data. Missing route geometry is accepted for location-only snapshots and generates a visible warning; the map does not invent a driving-route highlight.

Optional Snapshot.assignmentHistory:
```json
[{"tripId":"TR-101","fromVehicleId":"AMB-01","toVehicleId":"AMB-04","reason":"Backend reoptimization after vehicle outage","minute":12}]
```
Omit fromVehicleId/toVehicleId for unassigned. History is authoritative when supplied; otherwise the UI records observed assignment changes during the current browser session. Store durable history in SQL. A poll can miss intermediate changes, so backend history is preferred.

Optional Snapshot.optimizationResults:
```json
{
  "scenarioId":"same-inputs-paired-run-001",
  "tripsTotal":20,
  "baseline":{"onTimePickups":14,"averageDelayMinutes":8,"distanceKm":145,"tripsCompleted":18},
  "optimized":{"onTimePickups":17,"averageDelayMinutes":5,"distanceKm":132,"tripsCompleted":19}
}
```
The payload above illustrates the schema, not measured results. Use identical demand, fleet, initial conditions, and horizon for paired runs. onTimePickups and tripsCompleted are counts; averageDelayMinutes is average nonnegative pickup lateness over picked-up trips (include on-time pickups as zero). distanceKm is total driven fleet distance over the run. Report tripsTotal as the same requested population for both policies. The frontend displays clearly labeled example values if this optional payload is absent; it computes no claimed savings.

Demo scenarios are local-only presets. Fleet-wide automatic reoptimization remains backend work. A breakdown preset starts a new shift with AMB-01 out of service and TR-101 requiring replacement. Crew-delay preset starts AMB-01 with a ten-minute hold. Running either replaces the current local demo state.

Static schedule overlay: source is frontend/src/data/transportDataset.json. Purple dots are CSV pickup coordinates, with selected destination highlighted in blue. They remain independent from moving simulation vehicles. Clicking a patient record enables the overlay and fits pickup/destination bounds. A future backend directory response should preserve the CSV identifiers and schema described in dataset-directory.md.