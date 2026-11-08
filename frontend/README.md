# Belos server-driven frontend

React, TypeScript, Vite and Leaflet. Node 22.12+.

From the repository root, run `npm test`, `npm run build`, and `npm run dev`.
Copy `frontend/.env.example` to `frontend/.env.local`; set `VITE_API_BASE_URL` to the running backend, normally `http://127.0.0.1:8000`, and restart Vite. An explicitly blank URL uses the frontend origin. Database credentials must never appear in Vite settings.

All transport records, routes, schedules, assignments, simulation positions and history come from the backend. There is no frontend simulation or fixture fallback. The dashboard reads `GET /transport/state` approximately once per second; the backend independently advances time. Pause updates pauses only this viewer. API errors stop viewer polling and retain the labeled last received snapshot until retry/resume succeeds.

The Backend simulation and planning panel controls the server worker, speed, active route preparation, simulated slowdown and greedy fleet replanning. The worker must be running for movement to occur; its heartbeat is shown separately from API connectivity. Vehicle controls report delays and outages to the server. Assignment/replanning/disruption requests use `POST /transport/commands` and wait for the returned state; the old simulation `/transport/action` endpoint is not called.

Patient records and map overlays use the same `directory` as live dispatch, with original database IDs and timestamp offsets. Planned future assignments appear with vehicle and queue sequence. Backend-only route progress determines marker positions; the map never calculates movement. Missing routes and metrics remain visibly unavailable. Traffic adjustments are explicitly labeled simulated.

See [the backend run guide](../backend/README.md) for installation, one-time extension initialization, the API and separate worker commands. See [API integration](API_INTEGRATION.md) for the data contract.
