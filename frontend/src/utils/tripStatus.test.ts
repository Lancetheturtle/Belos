import { test } from 'node:test';
import assert from 'node:assert/strict';
import { needsPickupBeacon } from './tripStatus';
import { createSnapshot } from '../../tests/fixtures';

test('pickup beacon disappears when loading begins, including pickup at minute zero', () => {
  const s = createSnapshot(), t = s.trips[0], v = s.vehicles[0];
  t.status = 'pickup';
  assert.equal(needsPickupBeacon(t, v), true);
  t.actualPickup = 0;
  assert.equal(needsPickupBeacon(t, v), false);
  delete t.actualPickup;
  v.activity = 'Loading patient';
  assert.equal(needsPickupBeacon(t, v), false);
  for (const status of ['onboard','complete','cancelled'] as const) {
    t.status = status;
    assert.equal(needsPickupBeacon(t, v), false);
  }
});

test('transfer beacon survives the original pickup but disappears when replacement loads', () => {
  const s = createSnapshot(), t = s.trips[0], v = s.vehicles[0];
  t.status = 'transfer';t.actualPickup = 5;t.transferLocation = [42.7,-73.7];
  assert.equal(needsPickupBeacon(t, v), true);
  t.status = 'pickup';
  assert.equal(needsPickupBeacon(t, v), true);
  v.activity = 'Loading patient';
  assert.equal(needsPickupBeacon(t, v), false);
});

test('another patient at the same facility keeps their own beacon', () => {
  const s = createSnapshot(), collected = s.trips[0], waiting = s.trips[1];
  waiting.pickup = collected.pickup;waiting.status = 'waiting';
  collected.status = 'pickup';collected.actualPickup = 1;
  assert.equal(needsPickupBeacon(collected), false);
  assert.equal(needsPickupBeacon(waiting), true);
});
