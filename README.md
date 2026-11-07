# Belos

A medical transport coordination prototype for scheduled pickups and facility transfers. Focus: crew delays, road slowdowns, emergency interruptions during transport, and ambulances out of service.

## Start

In frontend/: `npm install`, then `npm run dev`. See frontend/README.md for a walkthrough and contracts/frontend-api.md for the proposed backend interface.

## Ownership

- Lance: setup and frontend (runnable transport demo).
- Teammate 2: backend, transport state, routing, and reassignment.
- Teammate 3: delay analytics, integration, and deployment.

frontend/ contains the app. backend/ and analytics/ remain placeholders. contracts/ contains API handoff notes. data/ is reserved for synthetic schedules and generated results.

Keep main runnable, work in short feature branches, and review payload changes together. Use synthetic data and keep secrets out of Git.
