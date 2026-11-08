// Copied into the frontend by the task script below.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createTransportClient, validateSnapshot } from './transportClient';
import { createScenario } from '../mocks/simulation';

test('initial read and retry preserve server state, reset is explicit POST', async () => {
  const calls: { url: string; method: string }[] = [],
    states: string[] = [];
  let fail = true;
  const fetcher: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), method: init?.method ?? 'GET' });
    if (fail) {
      fail = false;
      return new Response('{}', { status: 503 });
    }
    return Response.json(createScenario());
  };
  const api = createTransportClient('http://backend', fetcher, (state) =>
    states.push(state),
  );
  await assert.rejects(api.load(), /503/);
  await api.load();
  await api.reset();
  assert.deepEqual(
    calls.map((c) => [c.url, c.method]),
    [
      ['http://backend/transport/state', 'GET'],
      ['http://backend/transport/state', 'GET'],
      ['http://backend/transport/reset', 'POST'],
    ],
  );
  assert.deepEqual(states, [
    'connecting',
    'disconnected',
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
  const s = createScenario();
  assert.equal(validateSnapshot(s).vehicles[0].route, undefined);
  s.vehicles[0].route = [[200, 0]];
  assert.throws(() => validateSnapshot(s), /route/);
});
test('backend plans retain authoritative assignment history and reject invalid metrics', () => {
  const s = createScenario();
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

test('successful background polls keep the connection stable, failures still disconnect', async () => {
  const states: string[] = [];
  let failing = false;
  const api = createTransportClient('', async () => {
    if (failing) throw new Error('offline');
    return Response.json(createScenario());
  }, state => states.push(state));
  await api.load(); await api.load(); await api.load();
  assert.deepEqual(states, ['connecting', 'connected']);
  failing = true; await assert.rejects(api.load());
  failing = false; await api.load();
  assert.deepEqual(states, ['connecting', 'connected', 'disconnected', 'connecting', 'connected']);
});
