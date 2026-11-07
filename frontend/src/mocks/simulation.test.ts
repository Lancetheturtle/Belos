import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createScenario, dispatch, advance, addIncident } from './simulation';
const conditions={traffic:'normal',weather:'clear'} as const;
test('dispatch assigns each available unit at most once and optimizer does not increase total distance',()=>{
  for(const scenario of ['routine','surge'] as const) {
    const state=createScenario(scenario), next=dispatch(state,'optimized',conditions);
    const assigned=next.vehicles.filter(v=>v.status==='enroute');
    assert.equal(new Set(assigned.map(v=>v.incidentId)).size,assigned.length);
    assert.equal(assigned.length,scenario==='routine'?4:6);
    assert.ok(next.comparison!.optimized.distanceKm<=next.comparison!.nearest.distanceKm+1e-9);
    assert.equal(next.comparison!.optimized.unserved,scenario==='routine'?0:6);
    assert.equal(state.vehicles.filter(v=>v.status==='enroute').length,0);
  }
});
test('arrival releases units and resolves only assigned incidents',()=>{
  const next=advance(dispatch(createScenario('surge'),'nearest',conditions),3600);
  assert.equal(next.incidents.filter(i=>i.status==='resolved').length,6);
  assert.equal(next.incidents.filter(i=>i.status==='waiting').length,6);
  assert.equal(next.vehicles.filter(v=>v.status==='available').length,6);
  assert.equal(next.vehicles.filter(v=>v.status==='unavailable').length,2);
});
test('traffic increases travel estimates and new incidents invalidate old comparisons',()=>{
  const initial=createScenario(); const normal=dispatch(initial,'nearest',conditions), heavy=dispatch(initial,'nearest',{...conditions,traffic:'heavy'});
  assert.ok(heavy.comparison!.nearest.meanEtaMinutes>normal.comparison!.nearest.meanEtaMinutes);
  const next=addIncident(normal,'critical'); assert.equal(next.incidents.length,5); assert.equal(next.comparison,null); assert.equal(next.incidents[4].priority,'critical');
});
