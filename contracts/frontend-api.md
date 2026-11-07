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