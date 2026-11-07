import type { OptimizationComparison } from '../types';
const example: OptimizationComparison = {
  scenarioId: 'Example shift — 20 trips',
  tripsTotal: 20,
  baseline: {
    onTimePickups: 14,
    averageDelayMinutes: 8,
    distanceKm: 145,
    tripsCompleted: 18,
  },
  optimized: {
    onTimePickups: 17,
    averageDelayMinutes: 5,
    distanceKm: 132,
    tripsCompleted: 19,
  },
};
export default function OptimizationResults({
  results,
}: {
  results?: OptimizationComparison;
}) {
  const data = results ?? example;
  const metrics = [
    {
      key: 'onTimePickups' as const,
      label: 'On-time pickups',
      format: (n: number) => `${n} / ${data.tripsTotal}`,
    },
    {
      key: 'averageDelayMinutes' as const,
      label: 'Average pickup delay',
      format: (n: number) => `${n.toFixed(1)} min`,
    },
    {
      key: 'distanceKm' as const,
      label: 'Total fleet distance',
      format: (n: number) => `${n.toFixed(1)} km`,
    },
    {
      key: 'tripsCompleted' as const,
      label: 'Trips completed',
      format: (n: number) => `${n} / ${data.tripsTotal}`,
    },
  ];
  return (
    <details className="drawer optimization-results">
      <summary>
        <span>Optimization results</span>
        <span className="summary-meta">
          {results ? 'Backend results' : 'Example only'}
        </span>
      </summary>
      <div className="feature-body">
        <span className="pill amber">
          {results
            ? 'Reported by backend'
            : 'Illustrative numbers · Not measured'}
        </span>
        <p>{data.scenarioId}</p>
        <div className="kpi-grid">
          {metrics.map((m) => (
            <article key={m.key}>
              <span>{m.label}</span>
              <strong>{m.format(data.optimized[m.key])}</strong>
              <small>Optimized {results ? 'result' : 'example'}</small>
            </article>
          ))}
        </div>
        <table className="results-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Baseline</th>
              <th>Optimized</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.key}>
                <td>{m.label}</td>
                <td>{m.format(data.baseline[m.key])}</td>
                <td>{m.format(data.optimized[m.key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          {results
            ? 'Compare runs using identical requests, fleet, time window, and measurement definitions.'
            : 'Layout preview only. These numbers do not describe your simulation or demonstrate real savings. Your partner can supply actual paired-run results.'}
        </p>
      </div>
    </details>
  );
}
