# Frontend API handoff (proposed)

This is the frontend's implemented expectation, not an existing backend capability. Review together before integrating. Canonical TypeScript shapes: `frontend/src/types/index.ts`.

Every endpoint below returns a complete Snapshot: scenario, elapsedSeconds, vehicles, incidents, comparison (null before dispatch), and events (newest first). Positions and route points are `[latitude, longitude]`, not GeoJSON coordinate order. Times use seconds except metrics.meanEtaMinutes; distances use kilometers and emissions kilograms.

| Request | Body / behavior |
| --- | --- |
| GET /scenario?name=routine or surge | Load/reset server-side scenario; return initial Snapshot. |
| POST /dispatch | `{ "policy": "nearest", "conditions": { "traffic": "normal", "weather": "clear" } }`; apply assignments; return Snapshot including comparison for both policies against the same pre-dispatch state. |
| POST /simulate | `{ "action": "advance", "seconds": 10 }`; advance backend simulation clock and return Snapshot. |
| POST /simulate | `{ "action": "incident", "priority": "urgent" }`; add a synthetic incident at a preset location; return Snapshot. |

Policy: nearest or optimized. Traffic: normal or heavy. Weather: clear or rain.
Vehicle status: available, enroute, unavailable. Incident status: waiting, assigned, resolved. Priority: critical, urgent, standard.

Snapshot comparison has nearest and optimized Metrics objects: meanEtaMinutes, distanceKm, co2Kg, assigned, unserved. The dashboard labels these as the most recent dispatch comparison.

The client currently expects one active scenario per API session. Agree on session/scenario IDs before supporting multiple users. GET /scenario resetting state is a prototype convention; revise this client and document together if using a POST reset endpoint instead.

The API base URL is frontend/.env.local VITE_API_BASE_URL. Set VITE_DATA_MODE=api and restart Vite. Allow the frontend origin with backend CORS. Non-2xx responses and network errors appear in the UI and pause playback. No demo fallback occurs in API mode.

Forecast, independent benchmark runs, and LLM explanation panels are not connected yet.
