import {test} from 'node:test';import assert from 'node:assert/strict';
import {createScenario,applyAction,eta,late} from './simulation';
test('crew delay increases ETA, freezes unit until hold ends, then resumes',()=>{const s=createScenario(),t=s.trips[0],before=eta(s,t)!;const d=applyAction(s,{type:'delay',vehicleId:'AMB-01'});assert.equal(Math.round(eta(d,d.trips[0])!-before),10);assert.ok(late(d,d.trips[0])>0);const tick=applyAction(d,{type:'advance',minutes:5});assert.deepEqual(tick.vehicles[0].position,s.vehicles[0].position);assert.equal(s.vehicles[0].holdUntil,0);});
test('traffic affects active-trip ETA and clearing it restores estimate',()=>{const s=createScenario(),d=applyAction(s,{type:'traffic',enabled:true});assert.ok(eta(d,d.trips[0])!>eta(s,s.trips[0])!);assert.equal(eta(applyAction(d,{type:'traffic',enabled:false}),d.trips[0]),eta(s,s.trips[0]));});
test('breakdown before pickup releases trip, requires available replacement, restore does not duplicate assignment',()=>{const s=applyAction(createScenario(),{type:'outage',vehicleId:'AMB-01'});assert.equal(s.trips[0].status,'waiting');assert.equal(s.trips[0].vehicleId,undefined);assert.equal(s.vehicles[0].tripId,undefined);assert.throws(()=>applyAction(s,{type:'assign',tripId:'TR-101',vehicleId:'AMB-02'}));const assigned=applyAction(s,{type:'assign',tripId:'TR-101',vehicleId:'AMB-04'});assert.equal(assigned.trips[0].vehicleId,'AMB-04');const restored=applyAction(assigned,{type:'restore',vehicleId:'AMB-01'});assert.equal(restored.vehicles[0].tripId,undefined);});
test('onboard breakdown preserves patient location and original pickup time until replacement completes transport',()=>{let s=applyAction(createScenario(),{type:'advance',minutes:5});assert.equal(s.trips[0].status,'onboard');const actual=s.trips[0].actualPickup;const stopped=[...s.vehicles[0].position];s=applyAction(s,{type:'outage',vehicleId:'AMB-01'});assert.equal(s.trips[0].status,'transfer');assert.deepEqual(s.trips[0].transferLocation,stopped);s=applyAction(s,{type:'assign',tripId:'TR-101',vehicleId:'AMB-04'});s=applyAction(s,{type:'advance',minutes:30});assert.equal(s.trips[0].status,'complete');assert.equal(s.trips[0].actualPickup,actual);assert.equal(s.vehicles[3].tripId,undefined);});
test('emergency holds stack and reset clears all disruptions',()=>{let s=applyAction(createScenario(),{type:'delay',vehicleId:'AMB-02'});s=applyAction(s,{type:'emergency',vehicleId:'AMB-02'});assert.equal(s.vehicles[1].holdUntil,25);assert.equal(createScenario().vehicles[1].holdUntil,0);assert.equal(createScenario().minute,0);});

test('on-time pickup is not marked late by floating point clock rounding',()=>{const s=applyAction(createScenario(),{type:'advance',minutes:5});assert.equal(late(s,s.trips[0]),0);});
test('advancing the demo moves active ambulances without moving unassigned units', () => {
  const before = createScenario();
  const after = applyAction(before, { type: 'advance', minutes: 1 });
  assert.notDeepEqual(after.vehicles[0].position, before.vehicles[0].position);
  assert.deepEqual(after.vehicles[3].position, before.vehicles[3].position);
  assert.deepEqual(before.vehicles[0].position, [42.720, -73.687]);
});

test('held and out-of-service ambulances do not move when time advances', () => {
  let state = createScenario();
  state = applyAction(state, { type: 'delay', vehicleId: 'AMB-01' });
  state = applyAction(state, { type: 'outage', vehicleId: 'AMB-02' });
  const positions = state.vehicles.map((v) => v.position);
  const after = applyAction(state, { type: 'advance', minutes: 5 });
  assert.deepEqual(after.vehicles[0].position, positions[0]);
  assert.deepEqual(after.vehicles[1].position, positions[1]);
  assert.notDeepEqual(after.vehicles[2].position, positions[2]);
});

test('fractional live ticks move assigned vehicles continuously without moving idle units', () => {
  let state = createScenario();
  const startingPosition = [...state.vehicles[0].position];
  const idlePosition = [...state.vehicles[3].position];
  for (let i = 0; i < 8; i++) {
    const previous = state.vehicles[0].position;
    state = applyAction(state, { type: 'advance', minutes: 0.1 });
    assert.ok(state.vehicles[0].position[0] > previous[0], 'assigned ambulance moves on every small tick');
    assert.deepEqual(state.vehicles[3].position, idlePosition);
  }
  assert.ok(Math.abs(state.minute - 0.8) < 1e-6);
  assert.ok(state.vehicles[0].position[0] > startingPosition[0]);
});

test('small live ticks obey delays and vehicle outages', () => {
  let state = applyAction(createScenario(), { type: 'delay', vehicleId: 'AMB-01' });
  state = applyAction(state, { type: 'outage', vehicleId: 'AMB-02' });
  const stopped = state.vehicles.map((v) => [...v.position]);
  for (let i = 0; i < 20; i++) {
    state = applyAction(state, { type: 'advance', minutes: 0.1 });
  }
  assert.deepEqual(state.vehicles[0].position, stopped[0]);
  assert.deepEqual(state.vehicles[1].position, stopped[1]);
  assert.notDeepEqual(state.vehicles[2].position, stopped[2]);
});
