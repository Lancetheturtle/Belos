# Belos

A hackathon emergency dispatch simulator for comparing nearest-available and fleet-wide ambulance assignment.

## Ownership

- Frontend and initial repository setup: Lance
- Backend, routing, and simulation: teammate 2
- Analytics, forecasting, and deployment: teammate 3

## Structure

- `frontend/`: React dashboard, map, controls, and results display.
- `backend/`: FastAPI service, dispatch algorithms, routing, and simulation state.
- `analytics/`: demand forecasting, emissions estimates, and benchmark analysis.
- `contracts/`: shared API agreements and example payloads.
- `data/scenarios/`: small, reproducible synthetic demo scenarios.
- `data/generated/`: local generated datasets and results (ignored by Git).

## Current status

Folder structure only. Application scaffolding, dependencies, and run commands still need to be added by each owner.

## Working together

1. Create a short feature branch from the latest `main`.
2. Work primarily in your owned folders.
3. Agree on API payloads in `contracts/` before integrating.
4. Push small commits and open a pull request for a teammate to review.
5. Merge working pieces frequently and keep `main` ready for a demo.

The backend owns simulation time, vehicle state, and assignments. The frontend displays and animates the backend state.

First integration milestone: load a scenario, request dispatch, and show the assigned vehicle and route on the map.

Never commit API keys or real `.env` files. Use synthetic incident data for the demo.
