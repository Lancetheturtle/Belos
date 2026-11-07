import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clock, clockWithSeconds } from './time';

test('live clock shows simulated seconds while ETA formatter retains its rounding', () => {
  assert.equal(clockWithSeconds(0), '09:00:00');
  assert.equal(clockWithSeconds(0.1), '09:00:06');
  assert.equal(clockWithSeconds(1.5), '09:01:30');
  assert.equal(clock(0.1), '09:01');
});
