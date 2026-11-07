import { Ambulance, Clock3, TriangleAlert, Plus, Check } from 'lucide-react';
import type { Action, Vehicle } from '../types';

type Props = {
  vehicle: Vehicle;
  busy: boolean;
  onAction: (action: Action) => void;
};

export default function DisruptionControls({
  vehicle: v,
  busy,
  onAction: act,
}: Props) {
  return (
    <>
      <button
        className="action"
        disabled={busy || v.outOfService}
        onClick={() => act({ type: 'delay', vehicleId: v.id })}
      >
        <Clock3 size={18} />
        <span>
          <strong>Crew running late</strong>
          <small>Hold this unit for 10 more minutes</small>
        </span>
        <Plus size={15} />
      </button>
      <button
        className="action"
        disabled={busy || v.outOfService}
        onClick={() => act({ type: 'emergency', vehicleId: v.id })}
      >
        <TriangleAlert size={18} />
        <span>
          <strong>Emergency interruption</strong>
          <small>Pause this transport for 15 minutes</small>
        </span>
        <Plus size={15} />
      </button>
      <button
        className={`action ${v.outOfService ? 'restore' : 'outage'}`}
        disabled={busy}
        onClick={() =>
          act({
            type: v.outOfService ? 'restore' : 'outage',
            vehicleId: v.id,
          })
        }
      >
        {v.outOfService ? <Check size={18} /> : <Ambulance size={18} />}
        <span>
          <strong>
            {v.outOfService ? 'Return to service' : 'Ambulance out of order'}
          </strong>
          <small>
            {v.outOfService
              ? 'Make this unit available again'
              : 'Release its trip for reassignment'}
          </small>
        </span>
      </button>
      <p className="help">
        An interruption holds the selected unit. A breakdown stops it and flags
        its transport for a replacement.
      </p>
    </>
  );
}
