import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createTransportClient, validateSnapshot } from './transportClient';
import { createSnapshot, directory } from '../../tests/fixtures';

test('initial read and retry only GET server state', async () => {
  const calls: { url: string; method: string }[] = [],
    states: string[] = [];
  let fail = true;
  const fetcher: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), method: init?.method ?? 'GET' });
    if (fail) {
      fail = false;
      return new Response('{}', { status: 503 });
    }
    return Response.json(createSnapshot());
  };
  const api = createTransportClient('http://backend', fetcher, (state) =>
    states.push(state),
  );
  await assert.rejects(api.load(), /503/);
  await api.load();
  await api.load();
  assert.deepEqual(
    calls.map((c) => [c.url, c.method]),
    [
      ['http://backend/transport/state', 'GET'],
      ['http://backend/transport/state', 'GET'],
      ['http://backend/transport/state', 'GET'],
    ],
  );
  assert.deepEqual(states, [
    'connecting',
    'disconnected',
    'connecting',
    'connected',
    'connecting',
    'connected',
  ]);
});
test('network failures and malformed snapshots become disconnected', async () => {
  const states: string[] = [];
  const down = createTransportClient(
    '',
    async () => {
      throw new Error('offline');
    },
    (s) => states.push(s),
  );
  await assert.rejects(down.load(), /offline/);
  const bad = createTransportClient(
    '',
    async () => Response.json({ vehicles: [] }),
    (s) => states.push(s),
  );
  await assert.rejects(bad.load(), /Invalid/);
  assert.deepEqual(states, [
    'connecting',
    'disconnected',
    'connecting',
    'disconnected',
  ]);
});
test('missing routes are allowed for a location-only snapshot, malformed geometry is rejected', () => {
  const s = createSnapshot();
  assert.equal(validateSnapshot(s).vehicles[0].route, undefined);
  s.vehicles[0].route = [[200, 0]];
  assert.throws(() => validateSnapshot(s), /route/);
});
test('backend plans retain authoritative assignment history and reject invalid metrics', () => {
  const s = createSnapshot();
  s.assignmentHistory = [
    {
      tripId: 'TR-101',
      fromVehicleId: 'AMB-01',
      toVehicleId: 'AMB-04',
      minute: 2,
      reason: 'Backend replan',
    },
  ];
  assert.equal(
    validateSnapshot(s).assignmentHistory?.[0].toVehicleId,
    'AMB-04',
  );
  s.optimizationResults = {
    scenarioId: 'paired-run',
    tripsTotal: 6,
    baseline: {
      onTimePickups: 2,
      averageDelayMinutes: 4,
      distanceKm: 10,
      tripsCompleted: 2,
    },
    optimized: {
      onTimePickups: 5,
      averageDelayMinutes: 1,
      distanceKm: 9,
      tripsCompleted: 5,
    },
  };
  assert.equal(
    validateSnapshot(s).optimizationResults?.optimized.onTimePickups,
    5,
  );
  s.optimizationResults.optimized.onTimePickups = 100;
  assert.throws(() => validateSnapshot(s), /metrics/);
});


test('server directory replaces fixtures and accepts empty tables and unassigned requests', () => {
  const s = createSnapshot();
  s.directory = structuredClone(directory);
  s.directory.transport_requests[0].ambulance_id = null;
  assert.equal(validateSnapshot(s).directory?.transport_requests[0].ambulance_id, null);
  s.directory = { ambulances: [], transport_requests: [] };
  assert.deepEqual(validateSnapshot(s).directory, s.directory);
  delete s.directory;
  assert.equal(validateSnapshot(s).directory, undefined);
});

test('malformed records, coordinates, timestamps and joins reject the whole snapshot', () => {
  const invalid = [
    (s: any) => s.directory.ambulances.push(s.directory.ambulances[0]),
    (s: any) => s.directory.transport_requests.push(s.directory.transport_requests[0]),
    (s: any) => s.directory.ambulances[0].current_lat = 100,
    (s: any) => s.directory.ambulances[0].crew_count = -1,
    (s: any) => s.directory.transport_requests[0].pickup_time = '2026-11-07T12:00:00',
    (s: any) => s.directory.transport_requests[0].ambulance_id = 'missing',
    (s: any) => s.directory.transport_requests[0].status = 'invalid',
    (s: any) => s.directory.transport_requests[0] = null,
    (s: any) => s.vehicles[0].movementPath = [[91, 0]],
    (s: any) => s.trips[0].eta = 'soon',
    (s: any) => s.trips[0].vehicleId = 'missing',
    (s: any) => s.trips.push(s.trips[0]),
    (s: any) => s.assignmentHistory = [null],
    (s: any) => s.supportedActions = ['unknown'],
  ];
  for (const change of invalid) {
    const s = { ...createSnapshot(), directory: structuredClone(directory) };
    change(s);
    assert.throws(() => validateSnapshot(s));
  }
});

test('actions require advertised support and send server IDs without local mutation', async () => {
  const calls: { url: string; body: unknown }[] = [];
  const s = createSnapshot();
  const api = createTransportClient('/api/', async (input, init) => {
    calls.push({ url: String(input), body: JSON.parse(String(init?.body)) });
    assert.equal(init?.cache, 'no-store');
    return Response.json(s);
  }, () => {});
  const action = { type: 'assign' as const, tripId: 'TR-104', vehicleId: 'AMB-04' };
  await assert.rejects(api.act(s, action), /not supported/);
  assert.equal(calls.length, 0);
  s.supportedActions = ['assign'];
  const before = structuredClone(s);
  await api.act(s, action);
  assert.deepEqual(s, before);
  assert.deepEqual(calls, [{ url: '/api/transport/action', body: action }]);
});

test('bad directory data disconnects and a later valid empty snapshot reconnects', async () => {
  let bad = true;
  const states: string[] = [];
  const api = createTransportClient('', async () => {
    const s = createSnapshot();
    s.directory = bad ? { ambulances: [null as any], transport_requests: [] } : { ambulances: [], transport_requests: [] };
    return Response.json(s);
  }, state => states.push(state));
  await assert.rejects(api.load(), /ambulance/);
  bad = false;
  assert.deepEqual((await api.load()).directory?.transport_requests, []);
  assert.deepEqual(states, ['connecting', 'disconnected', 'connecting', 'connected']);
});
