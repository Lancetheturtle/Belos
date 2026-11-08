import type { Snapshot } from '../types';
import { clock } from '../utils/time';
export default function DispatchVisibility({
  snapshot: s,
  onShowTrips,
}: {
  snapshot: Snapshot;
  onShowTrips: () => void;
}) {
  const history = s.assignmentHistory ?? [];
  const affected = s.trips.filter((t) => {
    if (t.status === 'complete' || t.status === 'cancelled') return false;
    // A queued reservation is a real replacement, even while the trip is waiting.
    const assigned = t.vehicleId ?? t.plannedVehicleId;
    if (assigned) return !s.vehicles.some(v => v.id === assigned && !v.outOfService);
    if (t.status === 'transfer') return true;
    const latest = history.filter(h => h.tripId === t.id).at(-1);
    return t.status === 'waiting' && !latest?.toVehicleId && Boolean(latest?.fromVehicleId) &&
      s.vehicles.some(v => v.id === latest?.fromVehicleId && v.outOfService);
  });
  return (
    <>
      {affected.length > 0 && (
        <div className="dispatch-alert" role="alert">
          <strong>
            {affected.length} transport{affected.length === 1 ? '' : 's'} need a
            replacement
          </strong>
          {affected.map((t) => (
            <p key={t.id}>
              <b>{t.id}</b> ·{' '}
              {t.status === 'transfer'
                ? 'Patient waiting at stopped ambulance.'
                : 'Pickup has lost its ambulance.'}
            </p>
          ))}
          <button onClick={onShowTrips}>
            Review unresolved trips
          </button>
        </div>
      )}
      <details className="drawer assignment-history">
        <summary>
          <span>Assignment changes</span>
          <span className="summary-meta">{history.length}</span>
        </summary>
        <div className="feature-body">
          {history.length ? (
            history
              .slice()
              .reverse()
              .slice(0, 20)
              .map((h, i) => (
                <article
                  className="history-entry"
                  key={`${h.tripId}-${h.minute}-${i}`}
                >
                  <strong>
                    {h.tripId} · {clock(h.minute)}
                  </strong>
                  <p>
                    {h.fromVehicleId ?? 'Unassigned'} →{' '}
                    {h.toVehicleId ?? 'Unassigned'}
                  </p>
                  <small>{h.reason}</small>
                </article>
              ))
          ) : (
            <p>{s.assignmentHistory ? 'No assignment changes reported.' : 'Assignment history has not been supplied by the server.'}</p>
          )}
          <p>
            Shows{' '}
            history provided by the backend
            .
          </p>
        </div>
      </details>
    </>
  );
}
