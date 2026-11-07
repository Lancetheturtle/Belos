# Transport backend

Owner: teammate 2. Python modules are still placeholders.

Implement scheduled pickups, destination trips, unit availability, crew holds, traffic delays, and out-of-service reassignment. Preserve a simulated onboard patient's location during a breakdown and require explicit replacement assignment.

See ../contracts/frontend-api.md for the current proposed transport API and ../frontend/src/types/index.ts for data shapes. It replaces the earlier emergency-incident dispatch contract. The frontend currently runs an isolated demo adapter; agree on authoritative road-routing ETA fields before connecting the backend.

Suggested module roles: main.py for API, models.py for transport schemas, dispatch.py for unit assignment, routing.py for routes/ETAs, simulation.py for shift state and clock, database.py for schedule and event persistence.