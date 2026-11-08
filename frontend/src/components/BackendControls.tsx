import { useState } from 'react';
import type { Action, Snapshot } from '../types';

import { canAct } from '../api/client';



export default function BackendControls({ snapshot: s, busy, onAction }: {

  snapshot: Snapshot; busy: boolean; onAction: (action: Action) => void;

}) {

  const server = s.integration;
  const [confirmReset, setConfirmReset] = useState(false);

  return (

    <details className="drawer backend-controls" open>

      <summary><span>Backend simulation and planning</span></summary>

      <div className="feature-body">

        <p>{!server?.schemaReady ? 'Server controls are unavailable until transport storage is initialized.'

          : !server.workerConnected ? 'Backend worker is offline. Stored Tiger Data records are still visible.'

          : server.running ? `Backend simulation running at ${server.simulationSpeed}×.` : 'Backend simulation paused.'}</p>

        <button disabled={busy || !canAct(s, 'simulation') || !server?.workerConnected}

          onClick={() => onAction({ type: 'simulation', running: !server?.running, speed: server?.simulationSpeed ?? 1 })}>

          {server?.running ? 'Pause backend simulation' : 'Start backend simulation'}

        </button>

        <div className="backend-speeds" role="group" aria-label="Backend simulation speed">

          {[1, 15, 30, 60].map(speed => (

            <button key={speed} type="button" aria-pressed={server?.simulationSpeed === speed}

              disabled={busy || !canAct(s, 'simulation') || !server?.workerConnected}

              onClick={() => onAction({ type: 'simulation', running: server?.running ?? false, speed })}>

              {speed}×

            </button>

          ))}

        </div>

        <button disabled={busy || !canAct(s, 'routes')} onClick={() => onAction({ type: 'routes' })}>Prepare active road routes</button>

        <button disabled={busy || !canAct(s, 'optimize')} onClick={() => onAction({ type: 'optimize' })}>Replan fleet schedule</button>

        <div className="reset-controls">
          {confirmReset ? (
            <>
              <p>Restore saved starting positions, trip statuses, assignments and clock in TigerDB? This pauses the simulation at 1× and backs up the current state.</p>
              <button disabled={busy || !canAct(s, 'reset')} onClick={() => {
                setConfirmReset(false);
                onAction({ type: 'reset' });
              }}>Confirm reset</button>
              <button disabled={busy} onClick={() => setConfirmReset(false)}>Cancel</button>
            </>
          ) : <button disabled={busy || !canAct(s, 'reset')} onClick={() => setConfirmReset(true)}>Reset simulation</button>}
          {!canAct(s, 'reset') && <p>A saved TigerDB baseline is required to reset.</p>}
        </div>
        <label className="overlay-toggle"><input type="checkbox" checked={s.traffic}

          disabled={busy || !canAct(s, 'traffic')} onChange={e => onAction({ type: 'traffic', enabled: e.target.checked })} /> Simulated road slowdown</label>

        <p>Planning uses OSRM driving estimates and respects active transports, service level, capacity and shift end. Pausing the simulation stops vehicle movement; the dashboard keeps receiving server updates.</p>

      </div>

    </details>

  );

}

