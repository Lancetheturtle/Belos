# Belos

A medical transport coordination prototype for scheduled pickups and facility transfers. Focus: crew delays, road slowdowns, emergency interruptions during transport, and ambulances out of service.

## Start

Run the frontend **from the repository root** (the directory containing `frontend/` and `backend/`):

```powershell
npm ci
npm run dev
```

Open the Vite localhost URL printed in the terminal. Additional root commands:

```powershell
npm test
npm run build
npm run preview
```

The root `package.json` forwards these commands to the `frontend` npm workspace. It does not start the Python backend; see `backend/README.md` for backend setup. Use `npm ci` with the root `package-lock.json` on a clean checkout. See `frontend/README.md` for the demo walkthrough and `contracts/frontend-api.md` for the backend contract.

## Ownership

- Lance: setup and frontend (runnable transport demo).
- Teammate 2: backend, transport state, routing, and reassignment.
- Teammate 3: delay analytics, integration, and deployment.

frontend/ contains the app. backend/ and analytics/ remain placeholders. contracts/ contains API handoff notes. data/ is reserved for synthetic schedules and generated results.

Keep main runnable, work in short feature branches, and review payload changes together. Use synthetic data and keep secrets out of Git.
