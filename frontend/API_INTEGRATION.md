# Frontend API contract for Tiger Data

This is a frontend handoff, not a backend implementation. All changes for this preparation are inside `frontend/`.

## Current backend gaps (read-only inspection)

The checked-in `backend/main.py` has no `GET /transport/state`, reassigns `app = FastAPI()` after defining transport routes, and accepts an action shape different from the frontend contract. Its action handler currently advances time rather than implementing manual assignment. `backend/simulation.py` returns vehicle `lat/lng/status/trip_id` and trip coordinate objects, missing required schedule, label, crew, traffic and hold fields. Those responses are intentionally not coerced into invented dispatch information. The directory/table records are not currently exposed through the expected state response.

Therefore the frontend is prepared for integration, but cannot be described as connected to Tiger Data yet. No database connection or backend startup was attempted. The backend owner must expose the read contract below (or adapt the HTTP boundary once a final API contract is agreed).

## Read and refresh

`GET {VITE_API_BASE_URL}/transport/state` returns one complete `Snapshot` (see `src/types/index.ts`). Reads must not mutate, seed, reset or advance database state. The frontend has no reset or advance-time request. Polling reads state; the backend must advance its simulation independently. All POST action responses must use the same snapshot schema.

Required fields:

- `minute`: finite minutes relative to the shift's 09:00 reference, as used by the existing UI.
- `traffic`: boolean.
- `vehicles`: array of unique `id`, `crew`, `position: [latitude, longitude]`, `outOfService`, `holdUntil`, `holdReason`, optional `tripId`.
- `trips`: array of unique `id`, `from`, `to`, `pickup` and `destination` coordinate tuples, `scheduled` minute, `status` (`waiting`, `pickup`, `onboard`, `transfer`, `complete`), optional `vehicleId`, `actualPickup`, `completedAt`, `transferLocation`, `eta`.
- `events`: array of strings, newest first.

Empty arrays are valid. Vehicle and active trip assignment references must agree. Optional `eta` is the server's arrival minute (pickup/transfer for pickup trips, dropoff for onboard trips). The browser does not calculate live travel estimates. All numeric values must be JSON numbers, including PostgreSQL numeric columns serialized by the HTTP service.

Optional route fields: vehicle `route`, `routeIndex`, `movementPath`, `unloadingUntil`; trip `transportRoute`. All geometry is `[latitude, longitude]`, not GeoJSON longitude-first order. See the canonical types. The frontend plots exact server coordinates without interpolation, extrapolation or external route generation.

## Patient directory

Return optional `directory: { ambulances: [...], transport_requests: [...] }` in the same response so the patient list and map overlay refresh together. The snake_case fields match the supplied dataset. `src/types/index.ts` contains the explicit `DirectoryAmbulance` and `DirectoryRequest` schemas. No runtime fixture dataset remains in the frontend.

Ambulances require original `ambulance_id`, `unit_name`, `current_location`, `current_lat`, `current_lng`, `status`, `crew_count`, `stretcher_capacity`, `service_level`, `last_location_update_at`, `shift_end_at`.

Requests require original `request_id`, `patient_id`, pickup/dropoff location, address and lat/lng fields, `pickup_time`, `status`, nullable `ambulance_id`, `transport_type`, `mobility`, `planned_duration_minutes`, `booking_type`, `service_level`.

Dates must be ISO timestamps with `Z` or explicit timezone offsets; display uses America/New_York with dates across midnight. Unassigned ambulance IDs should be `null` (legacy empty strings are also accepted); assigned IDs must join a returned ambulance. IDs are never renumbered. Return the full relevant directory, not a page whose missing rows break joins. Unknown statuses, invalid coordinates/dates, duplicate IDs and malformed rows reject the complete snapshot. Omit `directory` when unavailable; return two empty arrays for known-empty tables. Neither case generates placeholder records.

Directory request statuses: `scheduled`, `assigned`, `en_route_to_pickup`, `at_pickup`, `transporting`, `completed`, `cancelled`. Ambulance statuses: `available`, `assigned`, `en_route_to_pickup`, `at_pickup`, `transporting`, `out_of_service`.

If the directory and dispatch schedule describe the same operating population, the API must preserve the same trip/unit IDs and assignment state in both projections. The frontend does not manufacture dispatch state from directory rows that lack shift timing or route information.

## Writes and optional results

Advertise `supportedActions: ["assign"]` only when the API implements assignment. The UI otherwise shows assignments as unavailable. `POST /transport/action` sends `{"type":"assign","tripId":"<original trip id>","vehicleId":"<original unit id>"}` and expects the updated complete snapshot. There is no optimistic mutation, direct database write, or fallback to a simulation POST. The server must reject unavailable units or conflicting changes.

Optional `assignmentHistory` and `optimizationResults` use the existing canonical TypeScript types. History is authoritative when supplied, including an empty array. Optimization results must be measured paired-run results; absent results show an empty panel. The browser displays only backend history and metrics; it does not generate either. A zero-trip comparison is valid.

Serve the API under the frontend origin or configure the HTTP service's existing CORS/authentication for its origin. The frontend currently uses same-origin cookies; cross-origin authenticated deployments require an agreed authentication contract. No database secrets may be exposed through `VITE_*` values.
