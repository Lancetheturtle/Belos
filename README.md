# Belos

Medical transport dispatch simulation with a dark Leaflet map, road-time assignment, disruption replanning, call entry, SQLite persistence, and live KPI diagnostics.

Read [CODE_GUIDE.md](CODE_GUIDE.md) for every source file, data flow, editing examples, tests, and current limitations.

## Run

From this folder, start the backend:
```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --port 8000 --loop asyncio:SelectorEventLoop
```

In another terminal:
```powershell
npm install
npm run dev:dispatch
```

Open the URL Vite prints. Diagnostics: http://127.0.0.1:8000/debug . Use `npm run dev` for the standalone local demo, which has simpler timings and no live backend call entry. Use backend mode for KPIs.

## Checks

```powershell
npm test
npm run build
python -m unittest discover -s backend -t . -p "test_*.py"
```

The live backend uses four fictional units and six initial trips. The 60-request CSV directory is a separate static overlay. Road speeds are OSRM estimates. Current storage is SQLite, not Tiger Data. The Vercel configuration hosts the frontend only; the backend needs a separate long-running host. See the guide before changing persistence or scheduling.
