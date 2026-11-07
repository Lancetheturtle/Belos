# Belos frontend

React + TypeScript + Vite, Tailwind CSS, Leaflet, and Lucide icons.

## Run locally

Requires Node.js 22.12+ (Node 24 works).

```sh
npm install
npm run dev
```

Open the localhost URL printed by Vite. Production: `npm run build`, then `npm run preview`. Tests: `npm test`.

## Demo walkthrough

1. Load Routine operations or Disaster surge.
2. Choose traffic, weather, and assignment policy.
3. Click Run dispatch. Routes, unit statuses, and comparison results update.
4. Click Play; adjust playback speed to see units arrive. Pause freezes simulation time.
5. Use + in the incident queue to add a preset incident. Click an incident to locate it.
6. Reset scenario restores its original fleet and incidents. The sidebar chart icon opens analytics.

Demo data is synthetic. Routes are straight lines, not roads. Estimates assume 32 km/h plus 30 seconds of dispatch overhead, heavy traffic 1.65x travel time, rain 1.2x, and 0.35 kg CO2/km. The demo optimizer minimizes summed travel estimates via small exact assignment; it ignores priority, clinical capabilities, coverage, and service time. Units become available immediately on arrival. Metrics compare only the most recent dispatch batch, not a full experiment. These are frontend demonstration calculations, not the team's final dispatch implementation.

Map tiles require internet and use OpenStreetMap with visible attribution. If tiles fail, markers and controls continue working.

## Backend handoff

Default mode is demo and needs no backend. Copy `.env.example` to `.env.local`, set `VITE_DATA_MODE=api` and `VITE_API_BASE_URL`, then restart Vite after the backend implements `../contracts/frontend-api.md`.

- `src/api/client.ts`: sole HTTP integration point; API errors are shown, never silently replaced with demo data.
- `src/types/index.ts`: proposed shared data shapes.
- `src/mocks/simulation.ts`: isolated demo adapter, replaceable by backend endpoints.
- `src/components/CityMap.tsx`: Leaflet rendering.
- `src/pages/Dashboard.tsx`: dashboard and actions.
- `src/styles.css`: responsive design and theme.

In API mode the backend owns state and time. The UI requests advances and renders returned snapshots. Configure backend CORS for the Vite origin. Do not put secrets in VITE_ variables; they are public browser configuration.

Official setup references: https://vite.dev/guide/ , https://tailwindcss.com/docs/installation/using-vite , https://leafletjs.com/reference-1.9.4.html .
