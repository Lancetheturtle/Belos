import DispatchVisibility from '../components/DispatchVisibility';
import TimeSavings from '../components/TimeSavings';
import { test } from 'node:test';

import assert from 'node:assert/strict';

import { renderToStaticMarkup } from 'react-dom/server';

import PatientTransports from '../components/PatientTransports';

import OptimizationResults from '../components/OptimizationResults';

import TransportSchedule from '../components/TransportSchedule';

import VehicleDetails from '../components/VehicleDetails';

import BackendControls from '../components/BackendControls';

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

    assert.deepEqual(calls.map(c => ({...c, url: new URL(c.url, 'http://test').pathname})), [

      { url: '/transport/state', method: 'GET' },

      { url: '/transport/commands', method: 'POST' },

    ]);

    globalThis.fetch = async () => { throw new Error('Server offline'); };

    await assert.rejects(client.load(), /Server offline/);

    assert.deepEqual(received, s);

  } finally {

    globalThis.fetch = originalFetch;

  }

});





test('backend controls distinguish offline worker from API connectivity', () => {

  const s=createSnapshot();

  s.supportedActions=['simulation','optimize','routes'];

  s.integration={source:'Tiger Data',schemaReady:true,running:false,workerConnected:false,simulationSpeed:15,referenceAt:'2026-11-07T09:00:00-05:00',routing:'OSRM'};

  const html=renderToStaticMarkup(<BackendControls snapshot={s} busy={false} onAction={() => {}} />);

  assert.match(html,/Backend worker is offline/);

  assert.match(html,/<button disabled="">Start backend simulation/);

  assert.match(html,/Replan fleet schedule/);

});



test('future assignments display server queue information instead of manual reassignment', () => {

  const s=createSnapshot();

  s.trips[1].plannedVehicleId=s.vehicles[1].id;

  s.trips[1].plannedSequence=2;

  const html=renderToStaticMarkup(<TransportSchedule snapshot={s} available={s.vehicles} busy={false} onAction={() => {}} />);

  assert.match(html,/Scheduled on AMB-04/);

  assert.match(html,/Queue 2/);

  assert.doesNotMatch(html,/aria-label="Assign TR-104"/);

});





test('speed buttons show all choices and select only the backend speed', () => {

  const s = createSnapshot();

  s.supportedActions = ['simulation'];

  s.integration = {source:'Tiger Data',schemaReady:true,running:true,workerConnected:true,simulationSpeed:30,referenceAt:'2026-11-07T09:00:00-05:00',routing:'OSRM'};

  const html = renderToStaticMarkup(<BackendControls snapshot={s} busy={false} onAction={() => {}} />);

  for (const speed of [1, 15, 30, 60])

    assert.match(html, new RegExp(`aria-pressed="${speed === 30}"[^>]*>${speed}×</button>`));

  assert.doesNotMatch(html, /<select/);

});


test('reset is available only when the backend advertises a saved baseline', () => {
  const s=createSnapshot();
  const render=()=>renderToStaticMarkup(<BackendControls snapshot={s} busy={false} onAction={()=>{}} />);
  assert.match(render(), /<button disabled="">Reset simulation/);
  s.supportedActions=['reset'];
  assert.match(render(), /<button>Reset simulation/);
  assert.doesNotMatch(render(), /Confirm reset/);
});

test('time savings shows backend totals and preserves over-baseline results', () => {
  const metrics={baselineMinutesPerJob:75,completedJobs:1,completedJobMinutes:90,baselineTotalMinutes:75,netMinutesSaved:-15,averageJobMinutes:90,activeJobMinutes:0,activeJobs:0,serviceMinutes:{loading:15,handoff:32,reset:5}};
  const html=renderToStaticMarkup(<TimeSavings metrics={metrics} />);
  assert.match(html,/15.0 min over baseline/);
  assert.match(html,/Idle time between jobs is excluded/);
  metrics.completedJobs=0;metrics.averageJobMinutes=null as any;
  assert.match(renderToStaticMarkup(<TimeSavings metrics={metrics} />),/No completed timed jobs yet/);
});

test('outage alerts clear for reassigned queues and completed or cancelled requests', () => {
  const s=createSnapshot();
  const broken=s.vehicles[0].id, replacement=s.vehicles[1].id;
  s.vehicles[0].outOfService=true;
  s.trips[0].status='complete';
  const t=s.trips[1];t.status='waiting';delete t.vehicleId;
  s.assignmentHistory=[{tripId:t.id,minute:1,fromVehicleId:broken,reason:'Outage'}];
  const render=()=>renderToStaticMarkup(<DispatchVisibility snapshot={s} onShowTrips={()=>{}} />);
  assert.match(render(),/class="dispatch-alert"/);
  t.plannedVehicleId=replacement;
  assert.doesNotMatch(render(),/class="dispatch-alert"/);
  delete t.plannedVehicleId;
  t.vehicleId=replacement;t.status='pickup';
  assert.doesNotMatch(render(),/class="dispatch-alert"/);
  t.vehicleId=broken;t.status='cancelled';
  assert.doesNotMatch(render(),/class="dispatch-alert"/);
  t.status='complete';
  assert.doesNotMatch(render(),/class="dispatch-alert"/);
});
