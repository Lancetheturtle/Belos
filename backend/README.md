# Tiger Data transport integration

The existing FastAPI app, database configuration, original ORM models, legacy simulation, routing endpoints and truck-dispatch functions remain in place. `main.py` only registers an additional transport router. The new integration reads the populated `ambulances` and `transport_requests` tables directly; it does not seed or copy them into the empty legacy `vehicles`/`trips` tables.

## Run from the Belos repository root

Install runtime dependencies:

```powershell
python -m pip install -r requirements.txt
```

Export your existing Tiger Data PostgreSQL URL as `DATABASE_URL` in each terminal that runs Python. Keep the secret local and out of the frontend. `OSRM_URL` optionally selects your routing server; otherwise the existing public OSRM development server is used. Python reads exported environment variables; a root `.env.local` is not automatically loaded.

Initialize once (idempotent; no existing table is dropped, reset or seeded):

```powershell
python -m backend.transport_runtime init
```

This creates only `belos_transport_runtime`, `belos_transport_plans`, `belos_transport_vehicle_state`, `belos_transport_events`, and `belos_transport_positions`. The reviewed DDL is in `migrations/001_transport_extension.sql`. The initial clock comes from the existing dataset's location-update time and is paused.

Start/restart the existing API in terminal 1:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Stop any older process occupying port 8000 first, or choose another port and match the frontend URL. An already running process without reload will continue serving its previously loaded code.

Start the separate simulation worker in terminal 2 when you want the database's simulated positions/statuses to advance:

```powershell
python -m backend.transport_runtime run --speed 15
```

Starting or restarting this worker leaves the simulation paused, even if the previous process was running. The selected --speed is saved but no vehicles move until you click **Start backend simulation** in the dashboard. It does not create example ambulances, reset the dataset, or delete requests. The UI can pause/resume it and change speed while the worker stays running. Ctrl+C stops the worker and records a paused flag. The worker must remain running for simulation controls to take effect. One transaction locks the shared clock row, moves vehicles and persists the new clock; duplicate workers cannot independently advance the same interval twice. Run one worker for predictable operation.

Start the frontend in terminal 3:

```powershell
npm run dev
```

Set `frontend/.env.local` to `VITE_API_BASE_URL=http://127.0.0.1:8000` (or the chosen API port), then restart Vite. Use Prepare active road routes and Replan fleet schedule in the dashboard as needed. The worker can move already-active trips without planning new assignments; the fleet planner schedules unassigned demand.

## New integration modules

- `transport_store.py`: existing directory table bindings and separate extension metadata. It never calls create_all on the directory tables.
- `services/transport_snapshot.py`: real directory -> frontend state, original IDs and dates preserved.
- `services/osrm.py`: validated Route/Table requests, coordinate conversion, small bounded cache, batching, no straight-line fallback. Active and queued route geometry is persisted in Tiger Data plans.
- `services/transport_planner.py`: greedy insertion by increase in predicted pickup lateness, freezing active work and checking crew, stretcher capacity, service level and shift end. This is a heuristic, not a globally optimal solver.
- `services/transport_motion.py`: backend route progress, scheduled pickup waits, two-minute loading/unloading and completion. OSRM driving duration is the time basis; simulated slowdown doubles driving duration.
- `services/transport_commands.py`: transactional assignment, replanning, delays, traffic and outage/recovery.
- `transport_runtime.py`: explicit storage initialization and the independent simulation worker.
- `routes/transport.py`: read API, validated command API and status/error translation.

The legacy `backend/simulation.py`, `models.py`, `database.py`, `routing.py`, and `services/dispatch.py` are unchanged. Their legacy endpoints operate on their original tables. New frontend actions use `/transport/commands` so they cannot accidentally invoke the legacy `/transport/action` handler that advances time.

## API

- `GET /transport/state`: complete, read-only frontend snapshot. `/transport/snapshot` is an alias.
- `GET /transport/directory`: patient/ambulance directory.
- `GET /vehicles`: frontend vehicle projection of `ambulances`.
- `GET /transport/routes/{vehicle_id}/{trip_id}`: read-only route preview using real directory IDs. The old singular `/transport/route/...` endpoint remains available for legacy model IDs.
- `GET /transport/positions/{vehicle_id}?limit=100`: persisted server position history.
- `GET /transport/diagnostics`: source counts, schema readiness, clock and worker heartbeat.
- `POST /transport/commands`: one of the commands below; returns a complete validated frontend-shaped snapshot after committing.

```json
{"type":"assign","tripId":"TR-0001","vehicleId":"AMB-101"}
{"type":"routes"}
{"type":"optimize"}
{"type":"delay","vehicleId":"AMB-101","minutes":10}
{"type":"outage","vehicleId":"AMB-101"}
{"type":"restore","vehicleId":"AMB-101"}
{"type":"traffic","enabled":true}
{"type":"simulation","running":true,"speed":15}
```

Use actual IDs and eligible records; the IDs above show request shapes only. Missing records return 404, conflicts return 409, malformed commands return 422, routing failures return 502, and missing storage/database failures return 503. Writes roll back as a unit. A pre-pickup outage releases assignments and attempts automatic replanning in a savepoint; if routing fails, the outage remains recorded and a visible event explains the unresolved plan. Onboard outages preserve the stopped patient location and require an explicit replacement assignment. A free replacement unit may release its future queued reservations for that explicit recovery; active transports are never interrupted. Released future work remains visible for replanning. Queued trips depart just in time for their planned pickup instead of tying up free units hours early. Restore never reclaims released work.

GETs do not route the fleet, write data, initialize storage, or advance simulation time. The route-preview GET contacts OSRM but does not persist a plan. Source validation rejects duplicate IDs, broken joins and inconsistent active assignments.

## Existing deployment entrypoint

`api/index.py` now forwards to the same `backend.main.app`, including `/api/...` prefix handling for the existing Vercel rewrite. It no longer starts a separate fake-incident application. For a frontend deployed with that rewrite, set `VITE_API_BASE_URL=/api` at build time and provide `DATABASE_URL` as a server secret. The API adapter is tested locally with prefixed requests; a new hosted deployment was not performed.

The separate simulation worker needs a continuously running Python process; it is not launched by a serverless HTTP invocation. It can run on your machine or a persistent backend host while sharing the same Tiger Data database. Keep the API and worker connected to the same database and OSRM configuration.

## Verification

These checks are isolated and do not access Tiger Data or the public OSRM server:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p test_transport_runtime.py -v
python -m unittest discover -s tests -p test_osrm_service.py -v
npm test
npm run build
```

The older `test_backend.py` and `test_tiger_data_extended.py` are live-database mutation tests; do not include them in an isolated check. The latter also targets fields that are absent from the preserved legacy models. They were not used to claim this integration passes.

Live validation during this implementation read 15 ambulances and 60 requests, verified one OSRM road route and a small duration matrix, initialized the five extension tables, and cached eight active road routes. A fingerprint of every original ambulance/request row was unchanged afterward. No live optimization, assignment, outage, or movement was triggered. Simulation remains paused until explicitly started.

## Limits

OSRM travel times are baseline driving estimates, not live traffic or ambulance-specific road-access predictions. See the [official OSRM Route and Table API](https://project-osrm.org/docs/v5.24.0/api/). Unreachable routes remain unavailable. Requests that cannot fit vehicle eligibility or recorded shifts remain unassigned; the planner does not fabricate extra staff, extend shifts, or delete demand. Optimization comparison cards remain empty until measured paired-run results are provided.


## Resetting the simulation without replacing Tiger Data

Run `python -m backend.transport_runtime init` to add the checkpoint table to an existing installation. Restart the API and worker to load the new code.

Create the baseline once, while paused and before running a new dataset:

```powershell
python -m backend.transport_runtime baseline
```

To restore a previously saved real `/transport/state` snapshot instead, use `python -m backend.transport_runtime baseline --snapshot <snapshot.json>`. Existing baselines cannot be overwritten. For this installation, the saved original 15-ambulance/60-request Tiger Data snapshot was imported; the baseline is now in Tiger Data, not a frontend fixture.

The sidebar's **Reset simulation** button asks for confirmation, then sends `POST /transport/commands` with `{"type":"reset"}`. Reset restores baseline positions, vehicle/trip statuses, assignments, and the original recorded clock; it pauses at 1x with traffic off. It clears derived plans and holds. Reset automatically prepares active road routes while staying paused. If routing is unavailable, the reset still succeeds and logs a retry message; use **Prepare active road routes** to retry. This is the recorded starting state, not a fabricated all-idle fleet or necessarily minute zero.

Reset and worker ticks serialize on the same database clock lock. All updates and a full pre-reset source/plan/hold checkpoint commit atomically. Events and position history remain as an audit trail. Patient details, addresses, schedules, fleet configuration and unrelated tables are not overwritten. Changed directory IDs cause reset to fail without writes. The legacy `/transport/reset` endpoint is not used.

The baseline and backups persist in `belos_transport_checkpoints`. No automatic baseline capture occurs during polling, worker startup or reset. Adding the reset feature does not execute a reset on the live database.


The dashboard now has one pause control: **Pause backend simulation**. Snapshot polling stays live and retries read failures automatically. The backend returns each vehicle route as only the remaining geometry, starting at its authoritative position, with `routePhase` (`pickup`, `dropoff`, or `stopped`). The frontend colors pickup legs green and drop-off legs blue without calculating progress. Multiple distinct patients can legitimately share a pickup facility; assignment remains exclusive per request, not per street coordinate.


## Automatic patient recovery after an outage

Onboard patient transfers now select the fastest feasible free replacement using OSRM approach driving time. Eligibility, crew, capacity, holds, active trips and shift end are checked. The replacement drives to the stopped ambulance, preserves the original pickup record, then continues to the destination. Future reservations may be released and replanned, but active patient trips are never interrupted. A failed or infeasible recovery remains visibly awaiting transfer; Replan fleet schedule / Retry automatic replacement retries selection. Routing failure does not undo the recorded outage or a successful replacement assignment. This supersedes earlier references to requiring manual replacement selection.


Fleet insertion scoring now minimizes added pickup lateness first, then active plus queued call count, then added OSRM driving time. Waiting time is excluded from the driving-cost tie-breaker. This avoids packing equally punctual trips onto a small number of units. Shift limits, service level, crew, capacity and active-trip protection still apply, so equal counts are not guaranteed when feasibility differs. An outage releases future assignments and replans them; patient requests are not cancelled or removed.


## Road timing and 75-minute comparison

OSRM routes request per-segment durations. Motion follows those durations (scaled to include the provider's total route time and turn costs), rather than uniform average speed over the whole path. These are profile-based travel estimates, not verified posted speed limits or live traffic. Providers omitting annotations retain a route-average fallback; malformed annotations are rejected.

Service stages now use the user's assumptions: 15 minutes loading, 32 minutes handoff/paperwork and 5 minutes resetting. Scheduling and availability forecasts use the same durations. The `timeSavings` snapshot object compares fully measured completed jobs against 75 simulated minutes each. Job timing begins on assignment departure or queued-trip activation and ends when the unit becomes available. Idle time before/between jobs does not count. Delays and recovery time during a job do count; transfers retain the original job start. Active totals are separate; negative savings are shown as over baseline. Imported trips without a known start are excluded. Reset clears the measured run with the plans.

After deploying, restart the worker and use Reset simulation then Replan fleet schedule to start a fresh comparison with the new service times and routes. Existing queued plans were calculated under the previous timing assumptions. Do not interpret savings against the supplied 75-minute assumption as a controlled optimization benchmark or measured clinical performance.
