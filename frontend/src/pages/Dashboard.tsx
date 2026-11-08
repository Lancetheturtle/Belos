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
import { client, isDemo, demoScenario, type ScenarioName } from '../api/client';
import { applyAction, free } from '../mocks/simulation';
import { clockWithSeconds } from '../utils/time';
import type { Action, Snapshot, AssignmentChange } from '../types';
import CityMap from '../components/CityMap';
import PatientTransports from '../components/PatientTransports';
import VehicleDetails from '../components/VehicleDetails';
import TransportSchedule from '../components/TransportSchedule';
import ConnectionStatus from '../components/ConnectionStatus';
import ScenarioControls from '../components/ScenarioControls';
import SpeedControl from '../components/SpeedControl';
import DispatchEntry from '../components/DispatchEntry';
import OptimizationResults from '../components/OptimizationResults';
import DispatchVisibility from '../components/DispatchVisibility';
// Accelerated demo time makes movement visible without waiting minutes per trip.
const LIVE_SPEED = 15; // One real second is fifteen simulated seconds.
const LIVE_TICK_MS = 200;

export default function Dashboard() {
  const [s, setS] = useState<Snapshot | null>(null),
    [selected, setSelected] = useState('AMB-01'),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [live, setLive] = useState(true);
  const [panel, setPanel] = useState<'live' | 'records'>('live');
  const [cameraReset, setCameraReset] = useState(0);
  const [requestFocus, setRequestFocus] = useState(0);
  const [showSchedule, setShowSchedule] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<string | null>(null);
  const [history, setHistory] = useState<AssignmentChange[]>([]);
  const [requestedSpeed, setRequestedSpeed] = useState<number | null>(null);
  const lock = useRef(false);
  const pendingOperations = useRef<Array<() => Promise<Snapshot>>>([]);
  const snapshotRef = useRef<Snapshot | null>(null);

  function commit(next: Snapshot) {
    const previous = snapshotRef.current;
    if (previous) {
      const changes: AssignmentChange[] = next.trips.flatMap((trip) => {
        const old = previous.trips.find((t) => t.id === trip.id);
        if (!old || old.vehicleId === trip.vehicleId) return [];
        return [
          {
            tripId: trip.id,
            fromVehicleId: old.vehicleId,
            toVehicleId: trip.vehicleId,
            minute: next.minute,
            reason: !trip.vehicleId
              ? 'Assignment released; replacement required.'
              : 'New assignment received.',
          },
        ];
      });
      if (changes.length)
        setHistory((items) => [...items, ...changes].slice(-100));
    }

    setSelected((current) =>
      next.vehicles.some((v) => v.id === current)
        ? current
        : (next.vehicles[0]?.id ?? ''),
    );
    snapshotRef.current = next;
    setS(next);
  }
  async function run(op: () => Promise<Snapshot>, background = false) {
    if (lock.current) {
      if (!background) pendingOperations.current.push(op);
      return;
    }
    lock.current = true;
    if (!background) {
      setBusy(true);
      setError('');
    }
    try {
      commit(await op());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
      setLive(false);
    } finally {
      lock.current = false;
      if (!background) setBusy(false);
      const next = pendingOperations.current.shift();
      if (next) void run(next);
    }
  }
  useEffect(() => {
    void run(() => client.load());
  }, []);
  // Demo updates advance locally; API updates read the server-owned state.
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
        const minutes =
          (elapsed * (snapshotRef.current.simulationSpeed ?? LIVE_SPEED)) /
          60_000;
        if (minutes <= 0) return;
        try {
          commit(
            applyAction(snapshotRef.current, { type: 'advance', minutes }),
          );
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Live simulation stopped.');
          setLive(false);
        }
      } else {
        apiElapsed += elapsed;
        if (apiElapsed >= 1000) {
          apiElapsed = 0;
          void run(() => client.load(), true);
        }
      }
    }, LIVE_TICK_MS);
    return () => window.clearInterval(timer);
    // Starting and stopping live updates should not recreate this timer for
    // every new Snapshot. The ref always points to the latest committed state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(s), live]);

  // Queue a speed change if a polling request is currently in flight.
  useEffect(() => {
    if (requestedSpeed === null || busy || !snapshotRef.current) return;
    const speed = requestedSpeed;
    setRequestedSpeed(null);
    void run(() =>
      client.act(snapshotRef.current!, { type: 'set-speed', speed }),
    );
  }, [requestedSpeed, busy]);

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
  const act = (a: Action) =>
    void run(() => client.act(snapshotRef.current!, a));
  const selectRequest = (id: string) => {
    setSelectedRequest(id);
    setRequestFocus((n) => n + 1);
    setShowSchedule(true);
    setPanel('records');
  };
  const runScenario = (name: ScenarioName) => {
    setPanel('live');
    setShowSchedule(false);
    setSelectedRequest(null);
    setCameraReset((n) => n + 1);
    setHistory([]);
    snapshotRef.current = null;
    setSelected('AMB-01');
    setLive(true);
    void run(async () => {
      const next = await demoScenario(name);
      if (name === 'breakdown')
        setHistory([
          {
            tripId: 'TR-101',
            fromVehicleId: 'AMB-01',
            reason: 'Scenario: ambulance breakdown. Replacement required.',
            minute: 0,
          },
        ]);
      return next;
    });
  };
  const viewHistory = s.assignmentHistory ?? history;
  const missingRoutes = s.vehicles.filter(
    (v) => v.tripId && (!v.route || v.route.length < 2),
  );
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
          <ConnectionStatus
            busy={busy}
            onRetry={() => {
              setLive(true);
              void run(() => client.load());
            }}
          />
          <span className="header-clock">
            <Clock3 size={15} />
            {clockWithSeconds(s.minute)}
          </span>
          <button
            className="quiet"
            disabled={busy}
            onClick={() => {
              setLive(true);
              setShowSchedule(false);
              setSelectedRequest(null);
              setCameraReset((n) => n + 1);
              setHistory([]);
              snapshotRef.current = null;
              void run(() => client.reset());
            }}
          >
            <RotateCcw size={14} />
            <span>{isDemo ? 'Reset demo' : 'Reset shift'}</span>
          </button>
        </div>
      </header>
      <main className="map-workspace">
        <section className="map-stage" aria-label="Transport map workspace">
          <CityMap
            cameraReset={cameraReset}
            requestFocus={requestFocus}
            showSchedule={showSchedule}
            selectedRequest={selectedRequest}
            onSelectRequest={selectRequest}
            snapshot={s}
            selected={selected}
            onSelect={(id) => {
              setSelected(id);
              setPanel('live');
            }}
          />
          <div className="map-heading">
            <div className="eyebrow">TROY, NEW YORK</div>
            <h1>Transport map</h1>
            <p>Click an ambulance to see its trip.</p>
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
            <div className="route-key">
              <span>
                <i
                  style={{
                    background: '#ffda45',
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                  }}
                />
                Pickup call
              </span>
              <span>
                <i style={{ background: '#55dec1' }} />
                To pickup
              </span>
              <span>
                <i style={{ background: '#63a5ff' }} />
                To drop-off
              </span>
            </div>
            <span className="map-note">
              {isDemo
                ? `Synthetic data · ${live ? 'Live simulation' : 'Paused'} at ${s.simulationSpeed ?? LIVE_SPEED}× speed · Highlighted driving routes`
                : `Backend dispatch simulation · ${s.simulationSpeed ?? LIVE_SPEED}× speed · Road-time estimates · No live traffic feed`}
            </span>
          </div>
        </section>
        <aside className="sidebar" aria-label="Transport controls">
          <div className="sidebar-title">
            <div>
              <div className="eyebrow">SHIFT WORKSPACE</div>
              <h2>Dispatch</h2>
            </div>
            <span className="pill neutral">
              {panel === 'live'
                ? isDemo
                  ? 'Live demo'
                  : 'Auto dispatch'
                : 'CSV snapshot'}
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <div className="workspace-tabs" role="tablist" aria-label="Workspace">
            <button
              id="live-tab"
              role="tab"
              aria-selected={panel === 'live'}
              aria-controls="live-panel"
              onClick={() => setPanel('live')}
            >
              Live map
            </button>
            <button
              id="records-tab"
              role="tab"
              aria-selected={panel === 'records'}
              aria-controls="records-panel"
              onClick={() => setPanel('records')}
            >
              Patient records
            </button>
          </div>
          <div className="sidebar-sections">
            <div
              id="records-panel"
              role="tabpanel"
              aria-labelledby="records-tab"
              hidden={panel !== 'records'}
            >
              <div className="feature-body">
                <label className="overlay-toggle">
                  <input
                    type="checkbox"
                    checked={showSchedule}
                    onChange={(e) => setShowSchedule(e.target.checked)}
                  />{' '}
                  Show 60 scheduled pickups on map
                </label>
                <p>Static CSV schedule, independent of the moving demo.</p>
              </div>
              <PatientTransports
                selectedRequest={selectedRequest}
                onSelectRequest={selectRequest}
              />
            </div>
            <div
              id="live-panel"
              role="tabpanel"
              aria-labelledby="live-tab"
              hidden={panel !== 'live'}
            >
              <div className="shift-controls">
                <button
                  className="primary"
                  disabled={busy}
                  aria-pressed={live}
                  onClick={() => setLive((running) => !running)}
                >
                  {live ? <Pause size={14} /> : <Play size={14} />}
                  {isDemo
                    ? live
                      ? 'Pause simulation'
                      : 'Resume simulation'
                    : live
                      ? 'Pause map updates'
                      : 'Resume map updates'}
                </button>
              </div>
              <SpeedControl
                speed={s.simulationSpeed ?? LIVE_SPEED}
                disabled={busy}
                onChange={setRequestedSpeed}
              />
              {!isDemo && (
                <DispatchEntry snapshot={s} busy={busy} onAction={act} />
              )}
              <ScenarioControls busy={busy} onRun={runScenario} />
              {!isDemo && (
                <div className="feature-body" role="status">
                  <strong>Automatic dispatch</strong>
                  <p>{s.dispatch?.message ?? 'Waiting for dispatch status'}</p>
                  <p>{s.dispatch?.routingSource}</p>
                  <p>
                    Replans after delays, traffic updates, breakdowns, and
                    completed trips. Onboard patients stay assigned unless their
                    ambulance breaks down.
                  </p>
                  <button
                    disabled={busy}
                    onClick={() => act({ type: 'reoptimize' })}
                  >
                    {s.dispatch?.status === 'routing-unavailable'
                      ? 'Retry dispatch'
                      : 'Recalculate assignments'}
                  </button>
                </div>
              )}
              {missingRoutes.length > 0 && (
                <div className="route-warning" role="status">
                  Road routes missing for{' '}
                  {missingRoutes.map((v) => v.id).join(', ')}. Locations are
                  shown without a road highlight.
                </div>
              )}
              <DispatchVisibility
                snapshot={s}
                history={viewHistory}
                onShowTrips={() => {
                  const node =
                    document.querySelector<HTMLDetailsElement>(
                      '.drawer.schedule',
                    );
                  if (node) {
                    node.open = true;
                    node.scrollIntoView({
                      block: 'nearest',
                      behavior: 'smooth',
                    });
                  }
                }}
              />
              <p className="workspace-hint">
                Choose a unit below or click one on the map.
              </p>
              <VehicleDetails
                snapshot={s}
                selected={selected}
                onSelect={setSelected}
                busy={busy}
                onAction={act}
              />
              <TransportSchedule
                snapshot={s}
                available={available}
                busy={busy}
                onAction={act}
              />
              <details className="drawer fleet">
                <summary>
                  <span>
                    <Activity size={17} />
                    Ambulances
                  </span>
                  <span className="summary-meta">
                    {s.vehicles.length} units
                  </span>
                </summary>
                {s.vehicles.map((unit) => (
                  <button
                    key={unit.id}
                    className={`fleet-row ${selected === unit.id ? 'selected' : ''}`}
                    onClick={() => setSelected(unit.id)}
                  >
                    <span
                      className={`dot ${unit.outOfService ? 'gray' : unit.tripId || unit.dispatchUnavailable || unit.holdUntil > s.minute ? '' : 'available'}`}
                    />
                    <strong>{unit.id}</strong>
                    <span>
                      {unit.outOfService
                        ? 'Out of service'
                        : unit.dispatchUnavailable
                          ? 'Unavailable'
                          : unit.tripId ||
                              unit.dispatchUnavailable ||
                              unit.holdUntil > s.minute
                            ? 'Active'
                            : 'Available'}
                    </span>
                  </button>
                ))}
              </details>
              <details className="drawer log">
                <summary>
                  <span>
                    <MapPin size={17} />
                    Recent activity
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
              <OptimizationResults results={s.optimizationResults} />
              <details className="drawer about">
                <summary>
                  <span>About this demo</span>
                </summary>
                <p>
                  {!isDemo ? (
                    'Backend runs the simulation clock. Pausing map updates only pauses this view. Uses road-profile travel times, simulated traffic factors, 15-minute loading, 32-minute handoff/paperwork, and a 5-minute reset. This is the four-unit demo; CSV patient records remain separate.'
                  ) : (
                    <>
                      Scheduled medical pickups and facility transfers.
                      Road-route travel at 30 km/h; road slowdown halves speed.
                      Transfers are simulated. The demo runs automatically at
                      {s.simulationSpeed ?? LIVE_SPEED}× speed. Pause or resume
                      live movement using the control above.
                    </>
                  )}
                </p>
              </details>
            </div>
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
