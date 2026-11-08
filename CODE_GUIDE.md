# Belos code guide

Paths below are relative to the Belos folder. This guide describes the current runnable project.

## Start here

Belos has two modes. Use **backend mode** for dispatch, adding calls, availability reports, the full service cycle, SQL persistence, and KPIs. Local demo mode is an older, self-contained map demo with simpler timing.

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --port 8000 --loop asyncio:SelectorEventLoop
```

In another terminal:

```powershell
npm install
npm run dev:dispatch
```

Open the URL Vite prints. Live numbers: http://127.0.0.1:8000/debug . `npm run dev` starts the local demo. `npm run build` creates the frontend production bundle. A backend code change requires restarting Uvicorn unless you start it with `--reload`.

## How the pieces fit

1. `frontend/src/main.tsx` mounts `Dashboard.tsx`.
2. Dashboard calls `api/client.ts`, which chooses local demo or HTTP backend mode.
3. `api/transportClient.ts` sends requests, validates snapshots, and reports connection state.
4. `backend/main.py` exports the FastAPI app from `transport_api.py`.
5. The API validates actions. `DispatchService` serializes requests and clock ticks with a lock, then delegates to dispatch/call logic.
6. `dispatch_engine.py` uses `road_times.py` for road-time estimates and route geometry. It chooses assignments and advances vehicles through the service stages.
7. `StateStore` saves the complete state to SQLite before replacing the in-memory state.
8. Dashboard polls snapshots about once per second. React renders the sidebar; Leaflet keeps map markers mounted and interpolates their movement.
9. `/debug` polls a smaller diagnostics response every two seconds. Its page is served by Python and is independent of React.

The frontend does not independently dispatch vehicles in backend mode. Map clicks select records; they do not assign priority.

## Root files

| File | Purpose |
|---|---|
| `README.md` | Project overview, current run commands, and link to this guide. |
| `CODE_GUIDE.md` | This guide. Update it when adding or moving files. |
| `package.json` | Root npm workspace and shortcuts. `dev:dispatch` forwards to the frontend's backend-connected mode. |
| `package-lock.json` | Resolved workspace dependency versions. npm maintains this; do not edit it manually. |
| `requirements.txt` | Python runtime and API-test dependencies: FastAPI, Uvicorn, Pydantic, and HTTPX. SQLite is included with Python. |
| `vercel.json` | Frontend build/output and SPA routing for Vercel. It does not host the long-running simulation backend. |
| `.gitignore` | Excludes dependencies, build output, local environment files, caches, and generated databases. Allows the non-secret `.env.dispatch` preset. |
| `.env.example` | Notes about backend environment variables. Root environment files are not automatically loaded by this backend. Use PowerShell environment variables. |
| `.editorconfig` | UTF-8, spaces, final newline, and indentation conventions. Python uses four spaces; other code uses two. |
| `.prettierrc.json` | Frontend/HTML/JSON formatting preferences, including single quotes and trailing commas. |
| `.prettierignore` | Keeps generated files, lockfiles, and large data fixtures out of formatting runs. |

## Frontend configuration

| File | Purpose |
|---|---|
| `frontend/package.json` | React/Leaflet dependencies and Vite/build/test scripts. Add new frontend tests to its explicit test command. |
| `frontend/vite.config.ts` | Enables React and Tailwind's Vite plugin. Add development-server settings here. |
| `frontend/tsconfig.json` | Strict TypeScript settings and included source files. |
| `frontend/index.html` | HTML shell containing the root element and module entry script. |
| `frontend/.env.example` | Documents demo/API mode and backend URL settings. |
| `frontend/.env.dispatch` | Non-secret Vite mode preset: API mode at `http://127.0.0.1:8000`. Loaded by `dev:dispatch`. |
| `frontend/README.md` | Short frontend run instructions and mode differences. |

## Frontend source

| File | Purpose and editing notes |
|---|---|
| `frontend/src/main.tsx` | Imports app/global styles, mounts Dashboard, and enables React StrictMode. |
| `frontend/src/styles.css` | Global dark design, responsive layout, sidebar controls, Leaflet styling, call pulses, and component classes. Change appearance here. |
| `frontend/src/pages/Dashboard.tsx` | Owns the current snapshot, selections, tabs, errors, pause state, request queue, speed-change requests, and polling. Wires all components together. Background polls do not toggle the controls' busy styling. API pause stops viewer updates only. |
| `frontend/src/types/index.ts` | Shared frontend `Position`, `Vehicle`, `Trip`, `Snapshot`, `Action`, history, and KPI types. Coordinates are `[latitude, longitude]`. Change this alongside backend payload validation. |
| `frontend/src/api/client.ts` | Single mode boundary. Exports `isDemo`, observable connection status, local demo presets, and load/reset/action methods. |
| `frontend/src/api/transportClient.ts` | HTTP transport: state GET, explicit reset POST, action POST, timeout, snapshot validation, connection/retry state. Successful polling keeps connection status steady. |
| `frontend/src/api/roadRouting.ts` | Routing for the **local demo only**. Uses cached geometry or requests OSRM for missing routes. Backend mode uses Python routing instead. |
| `frontend/src/components/CityMap.tsx` | Creates one Leaflet map, maintains ambulance markers/routes/call beacons, draws the optional static CSV layer, handles selection/recentering, and animates snapshots without panning on every tick. |
| `frontend/src/components/VehicleDetails.tsx` | Unit selector, current assignment/status/hold, and the Report a problem section. |
| `frontend/src/components/TransportSchedule.tsx` | Lists current live trips, scheduled pickup times, status, ETA, lateness, and reassignment controls. |
| `frontend/src/components/ReassignTrip.tsx` | Available-unit dropdown for manually assigning a waiting/transfer trip. |
| `frontend/src/components/DisruptionControls.tsx` | Crew delay, emergency hold, out-of-service, and restore buttons. Sends explicit actions. |
| `frontend/src/components/DispatchVisibility.tsx` | Affected-trip warnings and before/after assignment history. Uses server history when present. |
| `frontend/src/components/DispatchEntry.tsx` | Backend-mode call form and availability-report form. Supports known facilities/custom coordinates, pickup timing, retry-safe submission keys, and timestamped status reports. |
| `frontend/src/components/SpeedControl.tsx` | 1–60× slider and presets. Keeps a draft value during dragging and submits the chosen speed. |
| `frontend/src/components/ConnectionStatus.tsx` | Subscribes to API connection status and shows retry when disconnected. |
| `frontend/src/components/ScenarioControls.tsx` | Normal/breakdown/crew-delay presets for the local demo. Disabled in backend mode. |
| `frontend/src/components/PatientTransports.tsx` | Searchable/filterable CSV patient and ambulance directory. Selecting a record focuses the static map overlay. It is separate from live dispatch. |
| `frontend/src/components/OptimizationResults.tsx` | Baseline/optimized KPI comparison UI. Uses a server comparison if supplied; otherwise shows clearly labeled examples. The real debug-page cycle totals are a separate calculation. |
| `frontend/src/utils/time.ts` | Shift-time formatting: minutes since 09:00 into clocks. ETA rounding and live-clock seconds have different formatting rules. |
| `frontend/src/utils/tripStatus.ts` | Human-readable trip status labels. |
| `frontend/src/utils/mapMovement.ts` | Builds animation timelines and samples road positions. Backend movement timestamps preserve segment-speed differences and stops; older/demo data uses distance interpolation. |
| `frontend/src/mocks/simulation.ts` | Local-demo scenario, pure cloned-state actions, simplified movement, and shared display helpers such as ETA/lateness/availability. Backend ETA overrides its fixed-speed estimate when provided. Its local demo service timings are not the backend KPI model. |
| `frontend/src/mocks/roadRoutes.json` | Bundled road geometry for the initial local demo. Data fixture, not dispatch logic. |
| `frontend/src/data/transportDataset.json` | Imported 60-request/15-unit CSV snapshot. Does not automatically feed the live four-unit simulation. |

## Backend source

| File | Purpose and editing notes |
|---|---|
| `backend/__init__.py` | Marks backend as a Python package. |
| `backend/main.py` | Small Uvicorn entry point exporting `transport_api.app`. |
| `backend/transport_api.py` | Pydantic payload validation; SQLite `StateStore`; locked `DispatchService`; server clock; CORS; HTTP endpoints; speed changes; assignment consistency checks before save. This is the current database integration point. |
| `backend/dispatch_engine.py` | Minimum-cost Hungarian matching, eligible-unit selection, earliest-scheduled next-wave planning, routes, disruptions, transfers, ETAs, stage transitions, movement timestamps, history, and safe routing-failure recovery. Pure functions work on cloned snapshots. |
| `backend/road_times.py` | OSRM time matrix, geometry, segment timing, turn-time distribution, route cache, timeout, and routing exceptions. Converts OSRM seconds to simulation minutes and `[longitude,latitude]` to frontend coordinate order. Never substitutes straight-line routes. |
| `backend/call_actions.py` | Adds calls with unique IDs; deduplicates retries using request keys; validates availability reports; rejects older timestamps and invalid availability; triggers replanning. |
| `backend/service_times.py` | Benchmark constants: 8+15+15+32+5=75. Backend service durations: 15 loading, 32 handoff/paperwork, 5 reset. Builds active-cycle benchmark metrics and net total saved across finished cycles. Policy version excludes incompatible old runs. |
| `backend/active_work.py` | Accumulates active travel/service time. Excludes idle waiting/holds from the active-work KPI while elapsed/waiting remain separately visible. |
| `backend/diagnostics.py` | Builds same-input greedy-versus-optimized planning comparisons, live observed metrics, and the smaller debug response. Per-plan assignment savings cannot be summed across replans. |
| `backend/diagnostics.html` | Standalone `/debug` page: polls JSON, renders totals/tables, shows stale-data errors. Uses textContent for dynamic values. Add debug-only UI here. |
| `backend/transport_seed.json` | Fictional four-ambulance/six-trip initial shift. Reset loads this, clears assignments, and runs dispatch. Edit this to change the initial backend scenario. |
| `backend/README.md` | Backend-specific setup, algorithm, assumptions, settings, and tests. |

### Current API

| Route | Role |
|---|---|
| `GET /health` | Server status and simulation speed. |
| `GET /transport/state` | Current snapshot; initializes the shift on first use if none exists. |
| `POST /transport/reset` | Resets the local simulation, including added calls. |
| `POST /transport/action` | Validated dispatch/disruption/call/status/speed actions. |
| `GET /transport/diagnostics` | Live metrics and comparisons for the debug page. |
| `GET /debug` | Serves diagnostics HTML. |

Action types include `delay`, `emergency`, `outage`, `restore`, `assign`, `traffic`, `traffic-update`, `reoptimize`, `set-speed`, `create-call`, and `report-status`. The API rejects `advance` because the server owns time. `traffic-update` exists in the backend even though it has no dedicated frontend control/type yet.

### Stored and generated files

| File/folder | Role |
|---|---|
| `data/generated/dispatch.sqlite3` | Runtime SQLite database: one JSON snapshot row, including calls, unit status, history, and counters. Created at runtime; do not hand-edit during a running shift. Back it up before changing persistence. |
| `data/generated/.gitkeep` | Keeps the generated-data directory in Git without committing databases. |
| `data/scenarios/README.md` | Notes about scenario data; active seeds are currently in the backend JSON and frontend mock. |
| `frontend/dist/` | Generated production output. Edit source and rebuild instead. |
| `node_modules/`, `frontend/node_modules/` | Installed npm dependencies. |
| `__pycache__/` | Generated Python bytecode. |
| `frontend/public/` | Optional static assets copied by Vite. It currently has no application logic. |

### Contracts

| File | Role |
|---|---|
| `contracts/README.md` | Where to find current payload documentation. |
| `contracts/frontend-api.md` | API field/action history and current extensions. Later sections supersede older prototype descriptions. Actual implementations and tests are the final reference. |
| `contracts/dataset-directory.md` | CSV source/schema and static-directory behavior. |

## Tests

| File | Checks |
|---|---|
| `frontend/src/api/transportClient.test.ts` | HTTP failures, schema validation, routes, optional results/history, retry, and stable polling connection status. |
| `frontend/src/mocks/simulation.test.ts` | Local movement/disruptions/transfers, road waits, ETA override, and speed limits. |
| `frontend/src/utils/time.test.ts` | Clock/ETA formatting. |
| `frontend/src/utils/mapMovement.test.ts` | Segment-speed interpolation, stationary intervals, road bends, and legacy fallback. |
| `backend/test_dispatch.py` | Matching versus exhaustive optimum, road-time choices, holds, traffic, transfers, failed routing, movement, SQL restart, and API validation. |
| `backend/test_service_cycle.py` | 75-minute stage boundaries, reset lockout, active versus elapsed time, waiting exclusion, old policy exclusion, and total saved including losses. |
| `backend/test_speed.py` | Runtime server speed, clock advancement, shared reporting, and invalid speed rejection. |
| `backend/test_diagnostics.py` | Same-input comparisons, incomparable plans, actual metrics, read-only endpoints, and persistence. |
| `backend/test_call_entry.py` | New calls, duplicate protection, stale reports, availability, unique assignments, and restart persistence. |

Run from the root:

```powershell
npm test
npm run build
python -m unittest discover -s backend -t . -p "test_*.py"
```

## Where to make a change

| Goal | Start with |
|---|---|
| Change colors, sidebar spacing, mobile layout | `styles.css`; relevant component |
| Add a sidebar section | New component, wired in `Dashboard.tsx` |
| Change route colors/markers/pulses | `CityMap.tsx` and `styles.css` |
| Change fastest-unit selection or scheduled-wave ordering | `dispatch_engine.py` → `replan()` / `minimum_assignment()` |
| Change roads, speeds, traffic-aware routing provider | `road_times.py`; ensure matrix and geometry use consistent timings |
| Change loading, paperwork, reset, or benchmark | `service_times.py`; stage transitions in `dispatch_engine.py`; update timing tests and start a fresh shift |
| Change what counts as active time | `active_work.py`; update KPI basis text and tests |
| Add a backend action | Pydantic model/union and handler in `transport_api.py`; engine or call logic; TS `Action`; UI; tests; contract |
| Add a call field | `CreateCall`, `call_actions.py`, TS types, `DispatchEntry.tsx`, and tests |
| Connect Tiger Data | Replace `StateStore` while preserving atomic save/load and history; current code uses SQLite only |
| Change initial demo fleet or trips | Backend `transport_seed.json`; local mode separately uses `createScenario()` |
| Add a debug metric | Compute in `diagnostics.py` or `service_times.py`, display in `diagnostics.html`, test the calculation |

## Rules that prevent subtle bugs

- Keep one authoritative snapshot in Dashboard; do not dispatch or store transport truth in map markers.
- Use simulation minutes for deadlines and KPIs. Wall-clock report timestamps are timezone-aware ISO strings used to reject stale status reports.
- A trip and its ambulance must point to each other. One live trip cannot have two ambulances.
- Onboard patients stay with their unit unless a breakdown requires a transfer. Replacements visit `transferLocation`, then the destination.
- A unit remains unavailable through handoff and reset. Never free it merely because it reached the destination.
- A speed change scales wall-clock playback, not simulated service durations or KPI definitions.
- Route failures retain valid assignments; do not draw direct-line fallbacks.
- Total saved is the net sum of `75 - active work` for finished, compatible cycles. Waiting stays separately visible. This compares with a supplied assumption, not a measured control group.
- Different calls may share a facility. Deduplicate retry keys, not coordinates.

## Remaining limitations

The algorithm optimizes the next scheduled wave, not the entire day. Capability/capacity/shift constraints, full-day planning, paired baseline experiments, real traffic feeds, live GPS ingestion, and Tiger Data integration are future work. Availability reports currently report availability rather than arbitrary patient-stage transitions; the simulation owns those stages. The static CSV directory is separate from live calls. Run one backend worker. Vercel config hosts only the frontend; point a deployed frontend at a separately hosted backend.

## Cleanup performed

Removed the unused old emergency-dispatch API and its SQLAlchemy modules, unused empty analytics modules, and obsolete movement notes. These were outside the current app's import graph. Removed the redundant frontend lockfile (the root workspace lockfile is authoritative), the broken old API rewrite from Vercel configuration and SQLAlchemy from current requirements. Local demo code, fixtures, tests, and static CSV data remain because they are used.
