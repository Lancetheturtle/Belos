import type { OptimizationComparison } from '../types';
export default function OptimizationResults({
  results,
}: {
  results?: OptimizationComparison;
}) {
  if (!results) return (
    <details className="drawer optimization-results">
      <summary>Optimization results</summary>
      <p className="feature-body">No optimization results supplied by the server.</p>
    </details>
  );
  const data = results;
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
          Backend results
        </span>
      </summary>
      <div className="feature-body">
        <span className="pill amber">
          Reported by backend
        </span>
        <p>{data.scenarioId}</p>
        <div className="kpi-grid">
          {metrics.map((m) => (
            <article key={m.key}>
              <span>{m.label}</span>
              <strong>{m.format(data.optimized[m.key])}</strong>
              <small>Optimized result</small>
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
          Compare runs using identical requests, fleet, time window, and measurement definitions.
        </p>
      </div>
    </details>
  );
}
