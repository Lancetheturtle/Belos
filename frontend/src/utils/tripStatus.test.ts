import { test } from 'node:test';
import assert from 'node:assert/strict';
import { needsPickupBeacon } from './tripStatus';
import { createSnapshot } from '../../tests/fixtures';

test('pickup beacon disappears when loading begins, including pickup at minute zero', () => {
  const s = createSnapshot(), t = s.trips[0], v = s.vehicles[0];
  t.status = 'pickup';
  assert.equal(needsPickupBeacon(t, s.minute, v), true);
  t.actualPickup = 0;
  assert.equal(needsPickupBeacon(t, s.minute, v), false);
  delete t.actualPickup;
  v.activity = 'Loading patient';
  assert.equal(needsPickupBeacon(t, s.minute, v), false);
  for (const status of ['onboard','complete','cancelled'] as const) {
    t.status = status;
    assert.equal(needsPickupBeacon(t, s.minute, v), false);
  }
});

test('transfer beacon survives the original pickup but disappears when replacement loads', () => {
  const s = createSnapshot(), t = s.trips[0], v = s.vehicles[0];
  t.status = 'transfer';t.actualPickup = 5;t.transferLocation = [42.7,-73.7];
  assert.equal(needsPickupBeacon(t, s.minute, v), true);
  t.status = 'pickup';
  assert.equal(needsPickupBeacon(t, s.minute, v), true);
  v.activity = 'Loading patient';
  assert.equal(needsPickupBeacon(t, s.minute, v), false);
});

test('another patient at the same facility keeps their own beacon', () => {
  const s = createSnapshot(), collected = s.trips[0], waiting = s.trips[1];
  waiting.pickup = collected.pickup;waiting.status = 'waiting';
  collected.status = 'pickup';collected.actualPickup = 1;
  assert.equal(needsPickupBeacon(collected, s.minute), false);
  assert.equal(needsPickupBeacon(waiting, s.minute), true);
});

test('pickup beacon starts exactly 60 simulated minutes before pickup and stays for overdue trips', () => {
  const t = createSnapshot().trips[0];
  t.scheduled = 180;
  for (const status of ['waiting', 'pickup'] as const) {
    t.status = status;
    assert.equal(needsPickupBeacon(t, 119.99), false);
    assert.equal(needsPickupBeacon(t, 120), true);
    assert.equal(needsPickupBeacon(t, 180), true);
    assert.equal(needsPickupBeacon(t, 240), true);
    assert.equal(needsPickupBeacon(t, 0), false);
  }
});

test('transfer recovery stays visible outside the original pickup window', () => {
  const s = createSnapshot(), t = s.trips[0], v = s.vehicles[0];
  t.scheduled = 500;t.status = 'transfer';t.actualPickup = 5;
  assert.equal(needsPickupBeacon(t, 10, v), true);
  t.status = 'pickup';t.transferLocation = [42.7,-73.7];
  assert.equal(needsPickupBeacon(t, 10, v), true);
  v.activity = 'Loading patient';
  assert.equal(needsPickupBeacon(t, 10, v), false);
});
