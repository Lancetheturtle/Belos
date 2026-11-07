import { useEffect, useRef, useState } from 'react';
import {
  Ambulance,
  Clock3,
  MapPin,
  RotateCcw,
  Pause,
  Play,
  Activity,
} from 'lucide-react';
import { client, isDemo } from '../api/client';
import { applyAction, free } from '../mocks/simulation';
import { clockWithSeconds } from '../utils/time';
import type { Action, Snapshot } from '../types';
import CityMap from '../components/CityMap';
import PatientTransports from '../components/PatientTransports';
import VehicleDetails from '../components/VehicleDetails';
import TransportSchedule from '../components/TransportSchedule';
import ConnectionStatus from '../components/ConnectionStatus';
// Accelerated demo time makes movement visible without waiting minutes per trip.
const LIVE_SPEED = 15; // One real second is thirty simulated seconds.
const LIVE_TICK_MS = 200;

export default function Dashboard() {
  const [s, setS] = useState<Snapshot | null>(null),
    [selected, setSelected] = useState('AMB-01'),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [live, setLive] = useState(true);
  const lock = useRef(false);
  const snapshotRef = useRef<Snapshot | null>(null);

  function commit(next: Snapshot) {
    snapshotRef.current = next;
    setS(next);
  }
  async function run(op: () => Promise<Snapshot>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      commit(await op());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
      setLive(false);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    void run(() => client.load());
  }, []);
  // Live updates use the same existing `advance` action and Snapshot contract.
  // Demo mode advances locally at 5 Hz. API mode limits requests to 1 Hz.
  // Only the map animates at display frame rate; React owns the sole data state.
  useEffect(() => {
    if (!s || !live) return;
    let last = performance.now();
    let apiElapsed = 0;
    const timer = window.setInterval(() => {
      const now = performance.now();
      const elapsed = Math.min(400, Math.max(0, now - last));
      last = now;
      if (document.hidden || lock.current || !snapshotRef.current) return;

      if (isDemo) {
        const minutes = elapsed * LIVE_SPEED / 60_000;
        if (minutes <= 0) return;
        try {
          commit(applyAction(snapshotRef.current, { type: 'advance', minutes }));
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Live simulation stopped.');
          setLive(false);
        }
      } else {
        apiElapsed += elapsed;
        if (apiElapsed >= 1000) {
          apiElapsed = 0;
          void run(() => client.act(snapshotRef.current!, {
            type: 'advance', minutes: LIVE_SPEED / 60,
          }));
        }
      }
    }, LIVE_TICK_MS);
    return () => window.clearInterval(timer);
    // Starting and stopping live updates should not recreate this timer for
    // every new Snapshot. The ref always points to the latest committed state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(s), live]);

  if (!s)
    return (
      <main className="loading">
        <Ambulance size={32} />
        <h1>Belos transport</h1>
        <p>{error || 'Loading the transport schedule…'}</p>
        {error && (
          <button onClick={() => void run(() => client.load())}>Retry</button>
        )}
      </main>
    );
  const act = (a: Action) => void run(() => client.act(snapshotRef.current!, a));
  const available = s.vehicles.filter((v) => free(v, s));
  return (
    <div className="app">
      <header>
        <a className="brand" href="#">
          <span>
            <Ambulance size={23} />
          </span>
          belos<span className="brand-sub">TRANSPORT OPERATIONS</span>
        </a>
        <div className="header-right">
          <ConnectionStatus />
          <span className="header-clock">
            <Clock3 size={15} />
            {clockWithSeconds(s.minute)}
          </span>
          <button
            className="quiet"
            disabled={busy}
            onClick={() => {
              setSelected('AMB-01');
              setLive(true);
              void run(() => client.load());
            }}
          >
            <RotateCcw size={14} />
            <span>Reset demo</span>
          </button>
        </div>
      </header>
      <main className="map-workspace">
        <section className="map-stage" aria-label="Transport map workspace">
          <CityMap snapshot={s} selected={selected} onSelect={setSelected} />
          <div className="map-heading">
            <div className="eyebrow">TROY, NEW YORK</div>
            <h1>Your fleet. One clear view.</h1>
            <p>Medical transport coordination</p>
          </div>
          <div className="map-bottom">
            <div className="map-legend">
              <span>
                <i className="dot" />
                Active
              </span>
              <span>
                <i className="dot available" />
                Available
              </span>
              <span>
                <i className="dot gray" />
                Out of service
              </span>
            </div>
            <div className="route-key"><span><i style={{background: "#ffda45", width: 7, height: 7, borderRadius: "50%"}} />Pickup call</span><span><i style={{background: "#55dec1"}} />To pickup</span><span><i style={{background: "#63a5ff"}} />To drop-off</span></div>
            <span className="map-note">
              Synthetic data · {live ? 'Live simulation' : 'Paused'} at {LIVE_SPEED}× speed · Highlighted driving routes
            </span>
          </div>
        </section>
        <aside className="sidebar" aria-label="Transport controls">
          <div className="sidebar-title">
            <div>
              <div className="eyebrow">SHIFT WORKSPACE</div>
              <h2>Transport desk</h2>
            </div>
            <span className="pill neutral">{s.trips.length} trips</span>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <div className="shift-controls">

            <button
              className="primary"
              disabled={busy}
              aria-pressed={live}
              onClick={() => setLive((running) => !running)}
            >
              {live ? <Pause size={14} /> : <Play size={14} />}
              {live ? 'Pause live' : 'Resume live'}
            </button>
          </div>
          <div className="sidebar-sections">
            <PatientTransports />
            <VehicleDetails snapshot={s} selected={selected} onSelect={setSelected} busy={busy} onAction={act} />
            <TransportSchedule snapshot={s} available={available} busy={busy} onAction={act} />
            <details className="drawer fleet">
              <summary>
                <span>
                  <Activity size={17} />
                  Fleet status
                </span>
                <span className="summary-meta">{s.vehicles.length} units</span>
              </summary>
              {s.vehicles.map((unit) => (
                <button
                  key={unit.id}
                  className={`fleet-row ${selected === unit.id ? 'selected' : ''}`}
                  onClick={() => setSelected(unit.id)}
                >
                  <span
                    className={`dot ${unit.outOfService ? 'gray' : unit.tripId || unit.holdUntil > s.minute ? '' : 'available'}`}
                  />
                  <strong>{unit.id}</strong>
                  <span>
                    {unit.outOfService ? 'Out of service' : unit.tripId || unit.holdUntil > s.minute ? 'Active' : 'Available'}
                  </span>
                </button>
              ))}
            </details>
            <details className="drawer log">
              <summary>
                <span>
                  <MapPin size={17} />
                  Shift updates
                </span>
                <span className="summary-meta">{s.events.length}</span>
              </summary>
              <div aria-live="polite">
                {s.events.slice(0, 6).map((e, i) => (
                  <p key={`${i}-${e}`}>
                    <span className="dot" />
                    {e}
                  </p>
                ))}
              </div>
            </details>
            <details className="drawer about">
              <summary>
                <span>About this demo</span>
              </summary>
              <p>
                Scheduled medical pickups and facility transfers. Road-route
                travel at 30 km/h; road slowdown halves speed. Transfers are
                simulated. The demo runs automatically at 15× speed. Pause or
                resume live movement using the control above.
              </p>
            </details>
          </div>
          <div className="sidebar-footer">
            <span className="dot" />
            Transport simulation · No patient data
          </div>
        </aside>
      </main>
    </div>
  );
}
