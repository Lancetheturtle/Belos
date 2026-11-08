import { useMemo, useState } from 'react';
import type { Action, Snapshot } from '../types';

export default function DispatchEntry({
  snapshot,
  busy,
  onAction,
}: {
  snapshot: Snapshot;
  busy: boolean;
  onAction: (action: Action) => void;
}) {
  const places = useMemo(
    () =>
      Array.from(
        new Map(
          snapshot.trips.flatMap(
            (t) =>
              [
                [t.from, t.pickup],
                [t.to, t.destination],
              ] as const,
          ),
        ).entries(),
      ),
    [snapshot.trips],
  );
  const [pickup, setPickup] = useState(0),
    [destination, setDestination] = useState(1);
  const [customPickup, setCustomPickup] = useState(''),
    [customDestination, setCustomDestination] = useState('');
  const [pLat, setPLat] = useState(''),
    [pLng, setPLng] = useState(''),
    [dLat, setDLat] = useState(''),
    [dLng, setDLng] = useState('');
  const [minutes, setMinutes] = useState(0),
    [unit, setUnit] = useState(snapshot.vehicles[0]?.id ?? ''),
    [status, setStatus] = useState<
      'available' | 'unavailable' | 'out_of_service'
    >('unavailable');
  const [requestKey, setRequestKey] = useState(crypto.randomUUID());
  const callExists = snapshot.trips.some((t) => t.requestKey === requestKey);
  return (
    <details className="drawer">
      <summary>
        <span>Calls and ambulance status</span>
      </summary>
      <div className="feature-body">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onAction({
              type: 'create-call',
              requestKey: requestKey,
              pickupName: pickup < 0 ? customPickup : places[pickup][0],
              destinationName:
                destination < 0 ? customDestination : places[destination][0],
              pickup:
                pickup < 0 ? [Number(pLat), Number(pLng)] : places[pickup][1],
              destination:
                destination < 0
                  ? [Number(dLat), Number(dLng)]
                  : places[destination][1],
              pickupInMinutes: minutes,
            });
          }}
        >
          <strong>Add transport call</strong>
          <label>
            Pickup
            <select
              value={pickup}
              onChange={(e) => setPickup(Number(e.target.value))}
            >
              {places.map(([name], i) => (
                <option key={name} value={i}>
                  {name}
                </option>
              ))}
              <option value={-1}>Custom coordinates</option>
            </select>
          </label>
          {pickup < 0 && (
            <>
              <label>
                Pickup name
                <input
                  required
                  maxLength={120}
                  value={customPickup}
                  onChange={(e) => setCustomPickup(e.target.value)}
                />
              </label>
              <label>
                Pickup latitude
                <input
                  required
                  type="number"
                  step="any"
                  min={-90}
                  max={90}
                  value={pLat}
                  onChange={(e) => setPLat(e.target.value)}
                />
              </label>
              <label>
                Pickup longitude
                <input
                  required
                  type="number"
                  step="any"
                  min={-180}
                  max={180}
                  value={pLng}
                  onChange={(e) => setPLng(e.target.value)}
                />
              </label>
            </>
          )}
          <label>
            Destination
            <select
              value={destination}
              onChange={(e) => setDestination(Number(e.target.value))}
            >
              {places.map(([name], i) => (
                <option key={name} value={i}>
                  {name}
                </option>
              ))}
              <option value={-1}>Custom coordinates</option>
            </select>
          </label>
          {destination < 0 && (
            <>
              <label>
                Destination name
                <input
                  required
                  maxLength={120}
                  value={customDestination}
                  onChange={(e) => setCustomDestination(e.target.value)}
                />
              </label>
              <label>
                Destination latitude
                <input
                  required
                  type="number"
                  step="any"
                  min={-90}
                  max={90}
                  value={dLat}
                  onChange={(e) => setDLat(e.target.value)}
                />
              </label>
              <label>
                Destination longitude
                <input
                  required
                  type="number"
                  step="any"
                  min={-180}
                  max={180}
                  value={dLng}
                  onChange={(e) => setDLng(e.target.value)}
                />
              </label>
            </>
          )}
          <label>
            Pickup in simulated minutes
            <input
              type="number"
              min={0}
              max={1440}
              required
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            />
          </label>
          <button disabled={busy || callExists} type="submit">
            Add call and dispatch
          </button>
          {callExists && (
            <p role="status">
              Saved as{' '}
              {snapshot.trips.find((t) => t.requestKey === requestKey)?.id}.{' '}
              <button
                type="button"
                onClick={() => {
                  setRequestKey(crypto.randomUUID());
                }}
              >
                Start another call
              </button>
            </p>
          )}
        </form>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onAction({
              type: 'report-status',
              vehicleId: unit,
              status,
              observedAt: new Date().toISOString(),
            });
          }}
        >
          <p>
            <strong>Report ambulance availability</strong>
          </p>
          <label>
            Ambulance
            <select value={unit} onChange={(e) => setUnit(e.target.value)}>
              {snapshot.vehicles.map((v) => (
                <option key={v.id}>{v.id}</option>
              ))}
            </select>
          </label>
          <p>
            {snapshot.vehicles.find((v) => v.id === unit)?.tripId
              ? `Assigned: ${snapshot.vehicles.find((v) => v.id === unit)?.tripId}`
              : 'No current trip'}
          </p>
          <label>
            Availability
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as typeof status)}
            >
              <option value="available">Available</option>
              <option value="unavailable">Unavailable / crew not ready</option>
              <option value="out_of_service">Out of service / breakdown</option>
            </select>
          </label>
          <button disabled={busy || !unit}>Send status to backend</button>
          <p>
            Onboard, handoff, and reset stages are tracked by the server. A busy
            unit cannot be reported available.
          </p>
        </form>
      </div>
    </details>
  );
}
