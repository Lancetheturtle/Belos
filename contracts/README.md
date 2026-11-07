# Shared API contracts

Agree on request and response examples here before frontend/backend integration.
The endpoints below are planned, not implemented.

| Endpoint | Purpose | Logic owner |
| --- | --- | --- |
| GET /scenario | Initial vehicles, incidents, and city configuration | Backend |
| POST /dispatch | Recommended assignments and routes | Backend |
| POST /simulate | Advance or run a scenario | Backend |
| GET /benchmark | Compare dispatch policies | Backend + analytics |
| GET /forecast | Predicted demand by zone | Analytics |
| GET /analytics | Distance, emissions, and performance | Analytics |
| POST /explain | Explain a recommendation (optional) | Analytics |

Before adding JSON examples, agree on:

- IDs, vehicle statuses, incident priorities, and capability values.
- Coordinate representation and route geometry format.
- Units for duration, distance, and emissions.
- Simulation clock, reset behavior, and scenario identifiers/seeds.
- Error response shape and unavailable/unserved cases.
- Whether dispatch only recommends assignments or also applies them.

Keep these examples synchronized with backend models and frontend types.
