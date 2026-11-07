# Live movement update

- The demo starts moving assigned ambulances automatically, with no time-advance button. It is an **accelerated synthetic simulation**, not live vehicle GPS.
- One real second advances 30 simulated seconds. Dashboard updates arrive about five times per second in demo mode; Leaflet glides permanent ambulance markers between those positions using animation frames.
- Pause live / Resume live pauses or resumes the shift clock. Reset demo resets the scenario and resumes it.
- Delays, outages, road slowdowns, and replacement assignments continue to use the existing `Action` / `Snapshot` contract. The frontend's simulation logic and API endpoint names are unchanged.
- In API mode, the frontend sends the existing `{"type":"advance","minutes":0.5}` action about once per second while live is enabled. Backend integration must implement `POST /transport/reset` and `POST /transport/action` and return a complete `Snapshot` as documented under `contracts/`. **The current Python backend is still an old scaffold and is not yet wired to those endpoints.** Backend mode will not work until this is completed.
- Direct lines are illustrative and facilities/vehicles are synthetic. No patient information is used.

## Running locally from the repository root

```powershell
npm ci
npm run dev
npm test
npm run build
```

The source includes tests for small automatic simulation steps, holds, outages, and the live clock. The normal npm build and test scripts require the Node dependencies to be installed locally.
