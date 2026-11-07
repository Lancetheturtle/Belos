import { useState } from 'react';
import { isDemo, type ScenarioName } from '../api/client';
export default function ScenarioControls({
  busy,
  onRun,
}: {
  busy: boolean;
  onRun: (name: ScenarioName) => void;
}) {
  const [name, setName] = useState<ScenarioName>('normal');
  return (
    <details className="drawer scenario-controls">
      <summary>
        <span>Demo scenarios</span>
      </summary>
      <div className="feature-body">
        <label htmlFor="demo-scenario">Start a repeatable situation</label>
        <select
          id="demo-scenario"
          value={name}
          onChange={(e) => setName(e.target.value as ScenarioName)}
        >
          <option value="normal">Normal operations</option>
          <option value="breakdown">Ambulance breakdown · AMB-01</option>
          <option value="crew-delay">Crew delay · AMB-01 +10 min</option>
        </select>
        <button
          className="primary"
          disabled={busy || !isDemo}
          onClick={() => onRun(name)}
        >
          Run scenario
        </button>
        <p>
          {isDemo
            ? 'Starts a fresh demo shift. Replaces the current demo state. No automatic reoptimization.'
            : 'Demo presets are disabled for a connected backend.'}
        </p>
      </div>
    </details>
  );
}
