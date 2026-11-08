# Transport backend

Run from the root: `python -m uvicorn backend.main:app --port 8000 --loop asyncio:SelectorEventLoop`. Start the UI with `npm run dev:dispatch`. Live metrics: http://127.0.0.1:8000/debug .

Read [CODE_GUIDE.md](../CODE_GUIDE.md) for every module, algorithm, field convention, test, limitation, and extension workflow. The API runs one simulation and requires one server worker.

## Settings

- BELOS_SIM_SPEED: initial speed, default 15; 0 freezes the clock for tests. The UI can change speed to 1–60 at runtime. Restart restores this initial setting.
- BELOS_STATE_DB: SQLite file path, default data/generated/dispatch.sqlite3.
- OSRM_URL: OSRM routing base URL, default https://router.project-osrm.org .
- BELOS_CORS_ORIGINS: explicit comma-separated allowed origins. When unset, HTTP localhost/127.0.0.1 development ports are allowed.

Set these as process environment variables before starting. Root .env files are not automatically loaded. No Tiger Data connection or remote schema changes occur.

## Behavior

Dispatch uses a road-time matrix and Hungarian matching for the next scheduled wave. Onboard transports remain assigned unless their unit breaks down. Transfer replacements visit the patient location before the destination. Road/provider failures retain safe plans and trigger retries. Call creation and availability reports persist in SQLite; retry keys and timestamps reject duplicate calls and stale reports. Busy units cannot report available.

Backend stages: drive to pickup, 15-minute preparation/loading, drive to destination, 32-minute unloading/handoff/paperwork, 5-minute reset. Availability begins after reset. Road durations come from OSRM profiles, not a live traffic feed. Traffic factors are explicit inputs.

The main cycle KPI counts active work only. Elapsed cycle and waiting are separate. Net total saved is the sum of 75 minus active-work minutes across finished compatible cycles, including negative differences. It compares with a user-supplied assumption, not a measured baseline run. Reset the shift after changing the service model policy to start a clean comparison.

## Tests

`python -m unittest discover -s backend -t . -p "test_*.py"`

Tests use deterministic road fakes and temporary SQL files; they do not access Tiger Data.
