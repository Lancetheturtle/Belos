import { Ambulance } from 'lucide-react';
import type { Action, Snapshot } from '../types';
import { clock } from '../utils/time';
import { statusLabel } from '../utils/tripStatus';
import DisruptionControls from './DisruptionControls';

type Props = { snapshot: Snapshot; selected: string; onSelect: (id: string) => void; busy: boolean; onAction: (action: Action) => void };

export default function VehicleDetails({ snapshot: s, selected, onSelect: setSelected, busy, onAction: act }: Props) {
  const v = s.vehicles.find(unit => unit.id === selected) ?? s.vehicles[0];
  if (!v) return null;
  const vehicleTrip = s.trips.find(t => t.id === v.tripId);
  const held = v.holdUntil > s.minute;
  return (
            <details className="drawer controls" open>
              <summary>
                <span>
                  <Ambulance size={17} />
                  Selected ambulance
                </span>
                <span className="summary-meta">{selected}</span>
              </summary>
              <div className="control-content">
                <label htmlFor="unit">Ambulance</label>
                <select
                  id="unit"
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  {s.vehicles.map((unit) => (
                    <option key={unit.id} value={unit.id}>
                      {unit.id} · {unit.crew}
                    </option>
                  ))}
                </select>
                <div className="unit-state">
                  <span
                    className={`dot ${v.outOfService ? 'gray' : v.tripId || held ? '' : 'available'}`}
                  />
                  {v.outOfService
                    ? 'Out of service'
                    : held
                      ? `${v.holdReason} until ${clock(v.holdUntil)}`
                      : vehicleTrip
                        ? statusLabel(vehicleTrip)
                        : 'Available for transport'}
                </div>
                {vehicleTrip && (
                  <p className="current-trip">
                    {vehicleTrip.id} ·{' '}
                    {vehicleTrip.status === 'onboard'
                      ? vehicleTrip.to
                      : vehicleTrip.from}
                  </p>
                )}
                <DisruptionControls vehicle={v} busy={busy} onAction={act} />
              </div>
            </details>
  );
}
