import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import PatientTransports from '../components/PatientTransports';
import OptimizationResults from '../components/OptimizationResults';
import TransportSchedule from '../components/TransportSchedule';
import VehicleDetails from '../components/VehicleDetails';
import { client, getDirectory } from './client';
import { createSnapshot, directory } from '../../tests/fixtures';

test('API mode is default and missing directory never falls back to fixtures', async () => {
  const s = createSnapshot();
  assert.deepEqual(getDirectory(s), { ambulances: [], transport_requests: [] });
  assert.equal('reset' in client, false);
  const html = renderToStaticMarkup(<PatientTransports data={getDirectory(s)} />);
  assert.match(html, /No patient records supplied/);
  assert.doesNotMatch(html, /DEMO-P|60 people|CSV snapshot/);
});

test('server patient view uses response IDs and dynamic counts', () => {
  const request = { ...directory.transport_requests[0], request_id: 'DB-REQUEST-9', patient_id: 'DB-PATIENT-9', status: 'scheduled', ambulance_id: null };
  const data = { ambulances: [], transport_requests: [request] };
  const s = { ...createSnapshot(), directory: data };
  assert.equal(getDirectory(s), data);
  const html = renderToStaticMarkup(<PatientTransports data={getDirectory(s)} />);
  assert.match(html, /DB-REQUEST-9/);
  assert.match(html, /DB-PATIENT-9/);
  assert.match(html, /All transports \(1\)/);
  assert.doesNotMatch(html, /DEMO-P|All transports \(60\)/);
});

test('missing live optimization data shows no sample metrics', () => {
  const html = renderToStaticMarkup(<OptimizationResults />);
  assert.match(html, /No optimization results supplied/);
  assert.doesNotMatch(html, /Example shift|145|132/);
});

test('live dispatch uses only server ETA and hides simulation disruptions', () => {
  const s = createSnapshot();
  const render = () => renderToStaticMarkup(<TransportSchedule snapshot={s} available={s.vehicles} busy={false} onAction={() => {}} />);
  assert.match(render(), /Pickup ETA —/);
  assert.match(render(), /disabled=""/);
  s.trips[0].eta = 5;
  assert.match(render(), /Pickup ETA 09:05/);
  const html = renderToStaticMarkup(<VehicleDetails snapshot={s} selected={s.vehicles[0].id} onSelect={() => {}} />);
  assert.doesNotMatch(html, /Report a problem|Crew delay|Out of order/);
});


test('application client returns server snapshots unchanged and never falls back on failure', async () => {
  const originalFetch = globalThis.fetch;
  const calls: { url: string; method: string }[] = [];
  const s = createSnapshot();
  s.minute = 137;
  s.supportedActions = ['assign'];
  try {
    globalThis.fetch = async (input, init) => {
      calls.push({ url: String(input), method: init?.method ?? 'GET' });
      return Response.json(s);
    };
    const received = await client.load();
    assert.deepEqual(received, s);
    assert.equal(received.directory, undefined);
    await client.act(received, { type: 'assign', tripId: 'TR-104', vehicleId: 'AMB-04' });
    assert.deepEqual(calls, [
      { url: '/transport/state', method: 'GET' },
      { url: '/transport/action', method: 'POST' },
    ]);
    globalThis.fetch = async () => { throw new Error('Server offline'); };
    await assert.rejects(client.load(), /Server offline/);
    assert.deepEqual(received, s);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
