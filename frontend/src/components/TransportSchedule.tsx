import { Clock3, MapPin, ArrowRight } from 'lucide-react';
import type { Action, Snapshot, Vehicle } from '../types';
import { eta, late } from '../mocks/simulation';
import { clock } from '../utils/time';
import { statusLabel } from '../utils/tripStatus';
import ReassignTrip from './ReassignTrip';

type Props = { snapshot: Snapshot; available: Vehicle[]; busy: boolean; onAction: (action: Action) => void };

export default function TransportSchedule({ snapshot: s, available, busy, onAction: act }: Props) {
  const pending = s.trips.filter(t => ['waiting', 'transfer'].includes(t.status));
  return (
            <details className="drawer schedule">
              <summary>
                <span>
                  <Clock3 size={17} />
                  Demo trips
                </span>
                <span className="summary-meta">
                  {pending.length} unassigned
                </span>
              </summary>
              <div className="trip-list">
                {s.trips.map((t) => {
                  const arrival = eta(s, t),
                    delay = late(s, t),
                    assignedUnit = s.vehicles.find(
                      (unit) => unit.id === t.vehicleId,
                    );
                  return (
                    <article
                      className={`trip ${t.status === 'transfer' ? 'needs-transfer' : ''}`}
                      key={t.id}
                    >
                      <div className="trip-time">
                        <strong>{clock(t.scheduled)}</strong>
                        <span>pickup</span>
                      </div>
                      <div className="trip-body">
                        <div className="trip-route">
                          <strong>{t.from}</strong>
                          <ArrowRight size={13} />
                          <strong>{t.to}</strong>
                        </div>
                        <div className="trip-meta">
                          <span>{t.id}</span>
                          <span
                            className={`pill ${t.status === 'complete' ? 'green' : t.status === 'transfer' ? 'red' : t.status === 'waiting' ? 'amber' : 'neutral'}`}
                          >
                            {statusLabel(t)}
                          </span>
                          {assignedUnit &&
                            assignedUnit.holdUntil > s.minute && (
                              <span className="delay">
                                {assignedUnit.holdReason} until{' '}
                                {clock(assignedUnit.holdUntil)}
                              </span>
                            )}
                          {delay > 0 && (
                            <span className="delay">
                              {delay} min{' '}
                              {t.actualPickup !== undefined
                                ? 'late pickup'
                                : 'pickup delay'}
                            </span>
                          )}
                        </div>
                        <div className="trip-bottom">
                          {['waiting', 'transfer'].includes(t.status) ? (
                            <ReassignTrip trip={t} available={available} busy={busy} onAction={act} />
                          ) : (
                            <span>
                              {t.vehicleId} <span className="separator">·</span>{' '}
                              {t.status === 'complete'
                                ? `Delivered ${clock(t.completedAt!)}`
                                : `${t.status === 'onboard' ? 'Drop-off' : t.transferLocation ? 'Transfer' : 'Pickup'} ETA ${arrival === null ? '—' : clock(t.status === 'pickup' ? Math.max(arrival, t.scheduled) : arrival)}`}
                            </span>
                          )}
                          {t.status === 'transfer' && (
                            <span className="transfer-note">
                              Patient remains at stopped vehicle.
                            </span>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
              <div className="schedule-note">
                <MapPin size={14} />
                Fictional facilities around Troy. ETAs update when you add
                delays or change traffic.
              </div>
            </details>
  );
}
