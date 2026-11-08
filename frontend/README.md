# Frontend

From the repository root, `npm run dev:dispatch` starts the backend-connected UI. Start `python -m uvicorn backend.main:app --port 8000 --loop asyncio:SelectorEventLoop` in a separate terminal first. `npm run dev` uses the independent local demo instead.

`npm test` runs the frontend tests. `npm run build` type-checks and creates `frontend/dist`. The root package-lock.json controls workspace dependencies.

Dashboard owns shared state and polling. CityMap owns Leaflet display only. API requests go through api/client.ts and api/transportClient.ts. API pause stops viewer polling; backend time continues. The speed slider changes backend time for all connected viewers. Static patient records are independent of live trips.

See [the complete code guide](../CODE_GUIDE.md) for every component, contract, and editing workflow. Environment settings are in .env.example and .env.dispatch. Vite picks another port when occupied; the local backend allows HTTP loopback origins on development ports.
