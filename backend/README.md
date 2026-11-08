# Road-time dispatch backend

From the Belos root, use two terminals:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm run dev:dispatch
```

Open the URL Vite prints. The header should say **Server connected**, and the sidebar shows **Automatic dispatch**. `npm run dev` still starts the original local demo without this algorithm. API mode uses the existing four-ambulance/six-trip fictional shift. The 60 CSV patient records remain a separate static overlay.

## Algorithm

At reset, disruptions, explicit replan, and trip completion:

1. Exclude out-of-service ambulances. Keep onboard transports locked to their current vehicle. A breakdown releases an onboard trip at the stopped vehicle's location for simulated transfer.
2. Order outstanding pickups by transfer first, then scheduled time and stable trip ID. Consider the next reachable scheduled wave, up to the eligible fleet size. Map clicks do not affect this order.
3. Query the OSRM driving-time matrix. Cost is current time plus any remaining crew hold plus road travel time, including the supplied traffic factor. Solve the wave's minimum-total-arrival-time assignment with the Hungarian algorithm, rather than choosing the closest unit greedily. Stable IDs make equal-cost outcomes deterministic.
4. Fetch approach and delivery road geometry and per-segment durations for the selected assignments. Commit only after routes are available. Null road matrix cells are excluded, with no straight-line fallback.
5. Move along road geometry using segment durations, including distributed turn costs. Wait for scheduled pickup, load for two simulated minutes, and unload for two minutes. Completion triggers the next dispatch.

This is a rolling next-wave optimizer, not a proof of globally optimal full-day scheduling. It does not yet model service capabilities, capacity, shift-end constraints, clinical priority, or approved patient-transfer procedures. A delayed ambulance already carrying a patient retains that patient. Ordinary pre-pickup assignments can change on a replan.

## Road speeds and traffic

OSRM uses OpenStreetMap roads and its configured driving-speed profile; these are road-based estimates, **not live measured traffic or guaranteed speed limits**. The movement and displayed backend ETAs use the same timings. Reference: https://project-osrm.org/docs/v5.24.0/api/ . Set `OSRM_URL` for your own or traffic-updated OSRM deployment. The public demo server is a best-effort development dependency.

No traffic toggle was added to the UI. An external feed can send:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/transport/action -Method Post -ContentType application/json -Body '{"type":"traffic-update","vehicleId":"AMB-01","factor":2}'
```

This doubles that vehicle's estimated travel times and immediately replans. Send factor 1 to clear it. Factors are explicit simulation/feed inputs; no live feed is connected. These per-vehicle factors compare ambulances; they do not find a different road around a specific congestion segment. The existing global `traffic` action doubles all driving times when enabled. For incident-specific alternative roads, integrate a routing provider whose matrix and geometry incorporate current traffic.

## API and persistence

- `GET /transport/state`: read current snapshot; first read initializes an uninitialized shift.
- `POST /transport/reset`: reset this simulation's state only.
- `POST /transport/action`: existing delay, emergency, outage, restore, assign, and traffic actions; new `reoptimize` and `traffic-update` actions.
- `GET /health`: server availability and configured speed.
- `advance` requests are rejected: server clock owns advancement. Pausing the frontend stops polling only.

`etaMinute` on each trip is authoritative. `assignmentHistory` records assignment releases/replacements. `dispatch` reports readiness or routing failure. No invented optimization KPI savings are returned; the existing KPI examples remain explicitly illustrative.

Routing failures preserve valid assignments. Outages and holds are still applied safely; a stranded trip remains waiting if routing is unavailable. The server retries failed planning every 15 ticks. The sidebar also offers Retry dispatch. SQL write failure leaves the previously committed state intact. Requests and clock ticks share a lock.

This version stores snapshots and assignment history in SQLite at `data/generated/dispatch.sqlite3`. No Tiger Data connection, table migration, reset, or deletion is performed. Replace the `StateStore` adapter to integrate your partner's SQL schema. Existing legacy backend modules remain outside the active API; the broken duplicate FastAPI entry point is replaced by `transport_api`.

Run **one Uvicorn worker**. This is a local hackathon simulator, without authentication, multiple tenants, or a distributed scheduler. Do not expose it as a production dispatch service.

Configuration (PowerShell environment variables before starting backend):

- `BELOS_SIM_SPEED`: 15 by default; 0 freezes movement for API testing, 1 runs real time; max 60.
- `BELOS_STATE_DB`: alternate SQLite file path.
- `OSRM_URL`: routing base URL.
- `BELOS_CORS_ORIGINS`: comma-separated frontend origins; default HTTP localhost/127.0.0.1 on any local development port. Setting this variable disables the flexible local-port default.

## Tests

```powershell
python -m unittest backend.test_dispatch -v
npm test
npm run build
```

Backend tests use deterministic fake roads: optimal matching against exhaustive search, road time vs. greedy distance, delay/traffic replanning, outages, onboard locking/transfers, route-service failure and recovery, unreachable routes, segment speeds, trip completion, SQL restart, and API validation. They never access the real Tiger Data database.


## Live numbers page

Open http://127.0.0.1:8000/debug after restarting the backend. This read-only page polls `/transport/diagnostics` every two seconds and shows live ETAs, crew holds, traffic multipliers, actual simulation pickup delays, assignment history, and the latest decision matrix. Estimated savings compare the optimized assignments against sequential fastest-available assignment using the exact same wave and road matrix. They are combined arrival minutes, not measured full-shift savings, and must not be summed across replans. No synthetic example KPI values are shown. Existing shifts get comparison data on their next successful replan.


### Full-cycle benchmark update

Backend service times are now 15 minutes preparation/loading, 32 minutes unloading/handoff/paperwork, and 5 minutes reset. Driving still uses road estimates; the user-supplied benchmark uses 8+15 driving minutes, totaling 75. A unit stays unavailable throughout handoff and reset; only reset completion releases it for automatic dispatch. Reset shift once after updating to start a clean KPI run. `/debug` reports full-cycle duration from first assignment until availability, including waits/disruptions, separately from estimated next-pickup assignment savings. The 75-minute benchmark is an assumption, not an observed control group. Local frontend-only demo timing is separate; use `npm run dev:dispatch` for these KPIs.


Call entry: the API-mode sidebar has Calls and ambulance status. Existing facilities or custom coordinates can create a new call via `create-call` action. A requestKey prevents retry duplicates; new calls persist in the SQLite state and trigger replanning. `report-status` accepts an aware observedAt timestamp, rejects stale reports, and records available/unavailable/out_of_service. Busy units cannot report available; onboard failures use out_of_service for transfer. Unavailable units are excluded from dispatch. Different patient calls at the same facility remain valid. Status is authoritative server state, not inferred from map clicks. Shift reset intentionally removes added calls from the current simulation. Tiger Data remains separate.


Active-work KPI update: reset shift once to start the active-work policy. Main cycle KPI counts driving + preparation/loading + handoff/paperwork + reset. Idle time between jobs is outside the cycle; waiting for scheduled patients and crew holds are excluded from active time. Elapsed cycle and excluded waiting are shown separately. The metric definition must be disclosed alongside the user-provided 75-minute benchmark.
