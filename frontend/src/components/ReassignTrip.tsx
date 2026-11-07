import type { Action, Trip, Vehicle } from '../types';

type Props = {
  trip: Trip;
  available: Vehicle[];
  busy: boolean;
  onAction: (action: Action) => void;
};

export default function ReassignTrip({
  trip: t,
  available,
  busy,
  onAction: act,
}: Props) {
  return (
    <label className="assign-label">
      {t.status === 'transfer' ? 'Send replacement' : 'Assign ambulance'}
      <select
        aria-label={`Assign ${t.id}`}
        value=""
        disabled={busy || available.length === 0}
        onChange={(e) =>
          act({
            type: 'assign',
            tripId: t.id,
            vehicleId: e.target.value,
          })
        }
      >
        <option value="">
          {available.length ? 'Choose unit…' : 'No units available'}
        </option>
        {available.map((unit) => (
          <option key={unit.id} value={unit.id}>
            {unit.id} · {unit.crew}
          </option>
        ))}
      </select>
    </label>
  );
}
