# Belos frontend

React, TypeScript, Vite and Leaflet. Use Node 22.12+.

## Run and check

From the repository root: `npm test`, `npm run build`, `npm run dev`.
Copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to the HTTP API serving Tiger Data records. Restart Vite after configuration changes.

The frontend always uses the API. An unset/blank API base uses same-origin paths; for local development the example points to `http://127.0.0.1:8000`. Include an API prefix in the base when needed, e.g. `/api`.

The local simulation engine, demo datasets, scenario presets, reset, road-routing requests and sample optimization metrics have been removed. `VITE_DATA_MODE` is no longer read; remove that setting from existing local environment files if present.

The browser accesses Tiger Data through the existing HTTP service. Database URLs and credentials do not belong in Vite environment variables or browser code.

## API handoff

`src/api/transportClient.ts` validates complete snapshots before any view accepts them. `src/api/client.ts` exposes the server-only client and connection status. `src/types/index.ts` defines the expected payloads. See [API integration](API_INTEGRATION.md) for the endpoint contract and current backend gaps.

Map vehicles, dispatch schedule, assignments, activity and optimization results use the returned snapshot. Patient records and purple map pickup markers share its optional `directory`, preserving original database identifiers and timestamps. Missing directory data shows an empty directory; missing metrics show an empty results panel; missing ETA is shown as unavailable. No fixture fallback or estimated road-speed ETA is used.

The dashboard reads approximately once per second while updates are enabled, with one request in flight at a time. Pause stops viewer polling, without changing server state. Failures retain the last valid snapshot, label it as stale, stop polling and disable assignment changes until retry/resume succeeds. Initial load failure shows Retry. Requests time out after ten seconds and bypass browser HTTP caching. Opening, refreshing, retrying and resuming never reset or advance the simulation. Only the backend owns the simulation clock.

Assignments are available only when the snapshot advertises `supportedActions: ["assign"]`. They are POSTed with the original IDs; the frontend renders the returned state without optimistic local assignment. There are no frontend reset, advance-time or simulated disruption controls.

Optional route geometry enables driving-route highlights. Location-only snapshots remain usable, with a warning for assigned vehicles missing routes. Map tiles require internet. Assignment history is displayed only when supplied by the server; the browser does not generate history entries. Vehicle markers are plotted at exact server coordinates without local movement or position interpolation.

## Validation

`npm test` covers time formatting, server-only view rendering and the HTTP boundary, including reconnects, malformed records, directory joins, coordinates, timestamps, empty tables and action permissions. `npm run build` checks TypeScript and builds production assets. Static test fixtures live in `tests/fixtures.ts` and are never imported by the application. These checks do not connect to Tiger Data or execute backend code.
