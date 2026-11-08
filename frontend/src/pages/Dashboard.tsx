import { useEffect, useRef, useState } from 'react';
import {
  Ambulance,
  Clock3,
  MapPin,
  Pause,
  Play,
  Activity,
} from 'lucide-react';
import { client, getDirectory, canAct } from '../api/client';
import { clockWithSeconds } from '../utils/time';
import type { Action, Snapshot } from '../types';
import CityMap from '../components/CityMap';
import PatientTransports from '../components/PatientTransports';
import VehicleDetails from '../components/VehicleDetails';
import TransportSchedule from '../components/TransportSchedule';
import ConnectionStatus from '../components/ConnectionStatus';
import OptimizationResults from '../components/OptimizationResults';
import DispatchVisibility from '../components/DispatchVisibility';
export default function Dashboard() {
  const [s, setS] = useState<Snapshot | null>(null),
    [selected, setSelected] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [live, setLive] = useState(true);
  const [panel, setPanel] = useState<'live' | 'records'>('live');
  const [requestFocus, setRequestFocus] = useState(0);
  const [showSchedule, setShowSchedule] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<string | null>(null);
  const lock = useRef(false);
  const snapshotRef = useRef<Snapshot | null>(null);

  function commit(next: Snapshot) {
    setSelected((current) =>
      next.vehicles.some((v) => v.id === current)
        ? current
        : (next.vehicles[0]?.id ?? ''),
    );
    setSelectedRequest((id) => getDirectory(next).transport_requests.some((t) => t.request_id === id) ? id : null);
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
  // Refresh server state only. Polling never advances the simulation clock.
  useEffect(() => {
    if (!s || !live) return;
    const timer = window.setInterval(() => {
      if (!document.hidden && !lock.current) void run(() => client.load());
    }, 1000);
    return () => window.clearInterval(timer);
    // The request lock serializes reads/actions; commit owns the latest snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(s), live]);

  if (!s)
    return (
      <main className="loading">
        <Ambulance size={32} />
        <h1>Belos transport</h1>
        <p>{error || 'Loading the transport schedule…'}</p>
        {error && (
          <button onClick={() => { setLive(true); void run(() => client.load()); }}>Retry</button>
        )}
      </main>
    );
  const act = (a: Action) => {
    if (!canAct(snapshotRef.current!, a.type)) return;
    void run(() => client.act(snapshotRef.current!, a));
  };
  const selectRequest = (id: string) => {
    setSelectedRequest(id);
    setRequestFocus((n) => n + 1);
    setShowSchedule(true);
    setPanel('records');
  };
  const missingRoutes = s.vehicles.filter(
    (v) => v.tripId && (!v.route || v.route.length < 2),
  );
  const directory = getDirectory(s);
  const actionsBusy = busy || !live || Boolean(error);
  const available = s.vehicles.filter((v) => !v.outOfService && !v.tripId && v.holdUntil <= s.minute);
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

        </div>
      </header>
      <main className="map-workspace">
        <section className="map-stage" aria-label="Transport map workspace">
          <CityMap
            requestFocus={requestFocus}
            showSchedule={showSchedule}
            selectedRequest={selectedRequest}
            onSelectRequest={selectRequest}
            snapshot={s}
            scheduleData={directory}
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
              Server data · {error ? 'Last received snapshot · Updates stopped' : live ? 'Live updates' : 'Updates paused'}
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
              Server data
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
                  Show {directory.transport_requests.length} scheduled pickups on map
                </label>
                <p>Schedule supplied by the server.</p>
              </div>
              <PatientTransports
                data={directory}
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
                  {live ? 'Pause updates' : 'Resume updates'}
                </button>
              </div>
              {missingRoutes.length > 0 && (
                <div className="route-warning" role="status">
                  Road routes missing for{' '}
                  {missingRoutes.map((v) => v.id).join(', ')}. Locations are
                  shown without a road highlight.
                </div>
              )}
              <DispatchVisibility
                snapshot={s}
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
              />
              <TransportSchedule
                snapshot={s}
                available={available}
                busy={actionsBusy}
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
                      className={`dot ${unit.outOfService ? 'gray' : unit.tripId || unit.holdUntil > s.minute ? '' : 'available'}`}
                    />
                    <strong>{unit.id}</strong>
                    <span>
                      {unit.outOfService
                        ? 'Out of service'
                        : unit.tripId || unit.holdUntil > s.minute
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

            </div>
          </div>
          <div className="sidebar-footer">
            <span className="dot" />
            Transport workspace · Server data
          </div>
        </aside>
      </main>
    </div>
  );
}
