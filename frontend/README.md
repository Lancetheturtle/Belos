# Belos medical transport frontend

React, TypeScript, Vite, Tailwind CSS, Leaflet. Node 22.12+ required.

## Run and check

From this folder: `npm install`, then `npm run dev`. Open the printed localhost address.
`npm test` checks disruption and reassignment behavior. `npm run build` checks TypeScript and creates the production build.

## Simple demo

The 09:00 shift has four ambulances and six scheduled transports between fictional facilities around Troy. Three pickups start assigned.

1. Choose an ambulance under What changed?
2. Add a 10-minute crew delay or 15-minute emergency interruption. Holds stack and update its trip ETA.
3. Toggle Road slowdown to halve travel speed for all units.
4. Mark an ambulance out of order. Before pickup, its trip needs reassignment. With a patient onboard, a transfer is flagged at the stopped vehicle's location.
5. Choose an available replacement in the schedule. The original unit does not regain that trip when returned to service.
6. Ambulances glide across the map automatically during the live demo. One real second advances thirty simulated seconds. Pause/Resume live to stop or restart the demo clock. Units wait for scheduled pickup time, deliver to their destination, and become available. Reset demo starts over.

This is a transport scheduling simulator, not a 911 dispatch app. There are no triage priorities or emergency-call generation. Emergency interruption means a generic hold affecting an existing unit, not a new 911 call or medical procedure.

Demo limitations: direct-line travel at 30 km/h, no loading/unloading duration, generic units with no capability constraints, and simulated immediate patient handoffs. Map tiles require internet. Pickup delay compares estimated or actual pickup against the scheduled time; drop-off ETA is shown once onboard. Needs attention counts active late pickups, held transports, and transfers. Unassigned trips have no ETA.

## Backend integration

The transport contract replaces the earlier 911-style endpoints. See `../contracts/frontend-api.md`. Default demo mode requires no backend. For API mode, copy `.env.example` to `.env.local`, set VITE_DATA_MODE=api and VITE_API_BASE_URL, and restart Vite. API errors are displayed; no silent demo fallback.

`src/api/client.ts` is the single API boundary. `src/types/index.ts` defines transport snapshots and actions. `src/mocks/simulation.ts` contains isolated demo logic and display helpers. `src/pages/Dashboard.tsx` contains the simplified screen.

## Map workspace

The home screen is a dark map with a right sidebar. Expand Selected ambulance, Transport schedule, Fleet status, or Shift updates for details. Click a unit on the map or select it in the sidebar. The schedule retains the replacement assignment dropdowns. On mobile the map stays first and the sidebar sections stack underneath. OpenStreetMap tiles are styled dark using a CSS filter applied only to the tile pane; markers, labels, controls, and attribution keep their own styling.

## Current continuous road demo

The latest demo starts moving automatically at 15x speed. Pause live / Resume live controls the clock. The Advance 5 min workflow is retired. Highlighted routes are OSRM driving paths; vehicles traverse the same geometry, wait for scheduled pickups, load for two simulated minutes, and wait two minutes to unload. Initial routes are cached in src/mocks/roadRoutes.json; new replacement routes require internet. See the road simulation section in contracts/frontend-api.md for optional route fields. Earlier direct-line descriptions above describe the retired prototype.

## New map and dispatch features

- Patient records: toggle Show 60 scheduled pickups on map; expand a patient to focus its pickup and destination. Purple markers are static CSV locations, not live patients.
- Live map > Demo scenarios: run normal operations, AMB-01 breakdown, or AMB-01 crew delay. Presets replace the local shift and are disabled in API mode.
- Replacement alerts open Demo trips for manual assignment. Assignment changes show observed before/after unit IDs; server history is used when supplied.
- Live map > Optimization results: four KPI cards and baseline/optimized comparison. Example values are explicitly illustrative until the backend provides optimizationResults.
- API mode reads GET /transport/state and polls it while running. Connection status reflects actual validated requests and offers Retry on failure. Reset is POST /transport/reset only. Backend owns the clock. Missing route geometry has an explicit warning.

See ../contracts/frontend-api.md for the new optional result/history payloads and state endpoint. Tests include mocked HTTP errors, invalid snapshots, missing routes, and successful reconnection.