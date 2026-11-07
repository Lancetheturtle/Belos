import { useMemo, useState } from 'react';
import { Ambulance, Users } from 'lucide-react';
import data from '../data/transportDataset.json';

const labels: Record<string, string> = {
  scheduled: 'Needs pickup · Unassigned',
  assigned: 'Needs pickup · Unit assigned',
  en_route_to_pickup: 'Ambulance heading to pickup',
  at_pickup: 'Ambulance at pickup',
  transporting: 'Patient onboard · En route',
  completed: 'Completed',
  cancelled: 'Cancelled',
  available: 'Available',
  out_of_service: 'Out of service',
};
const stamp = (value: string) =>
  new Date(value).toLocaleString('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
const words = (value: string) => value.replaceAll('_', ' ');
const tone = (status: string) =>
  status === 'transporting' || status === 'completed' || status === 'available'
    ? 'green'
    : status === 'out_of_service'
      ? 'red'
      : status === 'scheduled'
        ? 'amber'
        : 'neutral';
const pickupStatuses = new Set([
  'scheduled',
  'assigned',
  'en_route_to_pickup',
  'at_pickup',
]);
export default function PatientTransports({
  selectedRequest,
  onSelectRequest,
}: {
  selectedRequest?: string | null;
  onSelectRequest?: (id: string) => void;
}) {
  const [filter, setFilter] = useState('pickup'),
    [search, setSearch] = useState('');
  const units = useMemo(
    () => new Map(data.ambulances.map((unit) => [unit.ambulance_id, unit])),
    [],
  );
  const counts = {
    pickup: data.transport_requests.filter((t) => pickupStatuses.has(t.status))
      .length,
    transporting: data.transport_requests.filter(
      (t) => t.status === 'transporting',
    ).length,
    completed: data.transport_requests.filter((t) => t.status === 'completed')
      .length,
  };
  const rows = data.transport_requests
    .filter((t) => {
      const status =
        filter === 'all' ||
        (filter === 'pickup'
          ? pickupStatuses.has(t.status)
          : t.status === filter);
      const haystack = [
        t.request_id,
        t.patient_id,
        t.pickup_location,
        t.dropoff_location,
        t.ambulance_id,
      ]
        .join(' ')
        .toLowerCase();
      return status && haystack.includes(search.trim().toLowerCase());
    })
    .sort((a, b) => Date.parse(a.pickup_time) - Date.parse(b.pickup_time));
  return (
    <>
      <details className="drawer dataset-patients" open>
        <summary>
          <span>
            <Users size={17} />
            Patients
          </span>
          <span className="summary-meta">
            {data.transport_requests.length} people
          </span>
        </summary>
        <div className="dataset-intro">
          <strong>Patient records · CSV snapshot</strong>
          <p>
            60 fictional patients · Nov 7–8, 2026, Eastern time. Not connected
            to the live map yet.
          </p>
        </div>
        <div className="dataset-counts">
          <span>
            <strong>{counts.pickup}</strong> need pickup
          </span>
          <span>
            <strong>{counts.transporting}</strong> onboard
          </span>
          <span>
            <strong>{counts.completed}</strong> completed
          </span>
        </div>
        <div className="dataset-filters">
          <label htmlFor="patient-filter">Show transports</label>
          <select
            id="patient-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="pickup">Still need pickup ({counts.pickup})</option>
            <option value="transporting">
              Patient onboard / en route ({counts.transporting})
            </option>
            <option value="en_route_to_pickup">
              Ambulance heading to pickup
            </option>
            <option value="at_pickup">Ambulance at pickup</option>
            <option value="completed">Completed ({counts.completed})</option>
            <option value="all">All transports (60)</option>
          </select>
          <label htmlFor="patient-search">
            Search patient, trip, unit, or facility
          </label>
          <input
            id="patient-search"
            type="search"
            placeholder="e.g. DEMO-P0006 or Samaritan"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="dataset-result" role="status">
            {rows.length} matching transports
          </span>
        </div>
        <div className="dataset-list">
          {rows.map((t) => {
            const unit = units.get(t.ambulance_id);
            const patientLocation =
              t.status === 'completed'
                ? t.dropoff_location
                : t.status === 'transporting'
                  ? (unit?.current_location ?? 'Location unavailable')
                  : t.status === 'cancelled'
                    ? 'Not tracked'
                    : t.pickup_location;
            return (
              <details
                key={t.request_id}
                className={`dataset-record ${selectedRequest === t.request_id ? 'record-selected' : ''}`}
              >
                <summary onClick={() => onSelectRequest?.(t.request_id)}>
                  <span>
                    <strong>{t.patient_id}</strong>
                    <small>
                      {t.request_id} · Pickup {stamp(t.pickup_time)}
                    </small>
                    <span className={`pill ${tone(t.status)}`}>
                      {labels[t.status] ?? words(t.status)}
                    </span>
                  </span>
                </summary>
                <dl>
                  <dt>Map</dt>
                  <dd>
                    <button onClick={() => onSelectRequest?.(t.request_id)}>
                      Show pickup and destination
                    </button>
                  </dd>
                  <dt>Patient location in snapshot</dt>
                  <dd>
                    {patientLocation}
                    {t.status === 'transporting' && unit && (
                      <small>
                        {unit.current_lat.toFixed(5)},{' '}
                        {unit.current_lng.toFixed(5)}
                      </small>
                    )}
                  </dd>
                  <dt>Pickup</dt>
                  <dd>
                    {t.pickup_location}
                    <small>{t.pickup_address}</small>
                  </dd>
                  <dt>Going to</dt>
                  <dd>
                    {t.dropoff_location}
                    <small>{t.dropoff_address}</small>
                  </dd>
                  <dt>
                    {t.status === 'completed'
                      ? 'Transported by'
                      : 'Assigned ambulance'}
                  </dt>
                  <dd>
                    {unit
                      ? `${unit.ambulance_id} · ${unit.unit_name}`
                      : 'Not assigned'}
                  </dd>
                  {unit && t.status !== 'completed' && (
                    <>
                      <dt>Ambulance location in snapshot</dt>
                      <dd>
                        {unit.current_location}
                        <small>
                          {unit.current_lat.toFixed(5)},{' '}
                          {unit.current_lng.toFixed(5)} · Updated{' '}
                          {stamp(unit.last_location_update_at)}
                        </small>
                      </dd>
                    </>
                  )}
                  <dt>Transport details</dt>
                  <dd>
                    {words(t.transport_type)} · {words(t.mobility)}
                    <small>
                      {t.planned_duration_minutes} min planned ·{' '}
                      {words(t.service_level)}
                    </small>
                  </dd>
                </dl>
              </details>
            );
          })}
          {!rows.length && (
            <p className="dataset-empty">
              No transports match. Try another status or search.
            </p>
          )}
        </div>
      </details>
      <details className="drawer dataset-fleet">
        <summary>
          <span>
            <Ambulance size={17} />
            Ambulances
          </span>
          <span className="summary-meta">{data.ambulances.length} units</span>
        </summary>
        <p className="dataset-caption">
          CSV snapshot locations, separate from the four-unit live demo.
        </p>
        {data.ambulances.map((unit) => {
          const active = data.transport_requests.find(
            (t) =>
              t.ambulance_id === unit.ambulance_id &&
              [
                'assigned',
                'en_route_to_pickup',
                'at_pickup',
                'transporting',
              ].includes(t.status),
          );
          return (
            <details className="dataset-record" key={unit.ambulance_id}>
              <summary>
                <span>
                  <strong>{unit.ambulance_id}</strong>
                  <span className={`pill ${tone(unit.status)}`}>
                    {labels[unit.status] ?? words(unit.status)}
                  </span>
                </span>
              </summary>
              <dl>
                <dt>Unit</dt>
                <dd>{unit.unit_name}</dd>
                <dt>Location in snapshot</dt>
                <dd>
                  {unit.current_location}
                  <small>
                    {unit.current_lat.toFixed(5)}, {unit.current_lng.toFixed(5)}
                  </small>
                </dd>
                <dt>Current transport</dt>
                <dd>
                  {active
                    ? `${active.patient_id} · ${active.request_id}`
                    : 'No active transport'}
                  {active && (
                    <small>
                      {active.pickup_location} → {active.dropoff_location}
                    </small>
                  )}
                </dd>
                <dt>Crew / capacity</dt>
                <dd>
                  {unit.crew_count} crew · {unit.stretcher_capacity} stretcher
                </dd>
                <dt>Last location update</dt>
                <dd>{stamp(unit.last_location_update_at)}</dd>
                <dt>Shift ends</dt>
                <dd>{stamp(unit.shift_end_at)}</dd>
              </dl>
            </details>
          );
        })}
      </details>
    </>
  );
}
