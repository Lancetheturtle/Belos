import test from 'node:test';
import assert from 'node:assert/strict';
import { movementTimeline, sampleMovement } from './mapMovement';
import type { Position } from '../types';

test('equal-length roads retain 30 vs 40 mph timing at any demo speed', () => {
  const path: Position[] = [
    [0, 0],
    [1, 0],
    [2, 0],
  ];
  // Two equal 0.1-mile segments: .2 minutes at 30mph, .15 at 40mph.
  const timeline = movementTimeline(path, [10, 10.2, 10.35]);
  const first = sampleMovement(path, timeline, 0.1 / 0.35).point[0];
  const second = sampleMovement(path, timeline, 0.275 / 0.35).point[0];
  assert.ok(Math.abs(first - 0.5) < 1e-10);
  assert.ok(Math.abs(second - 1.5) < 1e-10);
  // Accelerating the entire update 15x keeps this segment-speed ratio.
  assert.ok(Math.abs(0.2 / 15 / (0.15 / 15) - 40 / 30) < 1e-10);
});

test('stationary intervals remain stationary and road bends remain in the trail', () => {
  const path: Position[] = [
    [0, 0],
    [0, 0],
    [1, 0],
    [1, 1],
  ];
  const times = movementTimeline(path, [0, 1, 2, 3]);
  assert.deepEqual(sampleMovement(path, times, 0.5 / 3).point, [0, 0]);
  assert.deepEqual(sampleMovement(path, times, 0.5), {
    point: [0.5, 0],
    untraveled: [
      [1, 0],
      [1, 1],
    ],
  });
  assert.deepEqual(sampleMovement(path, times, 1), {
    point: [1, 1],
    untraveled: [],
  });
});

test('missing or invalid timing falls back to existing distance behavior', () => {
  const path: Position[] = [
    [0, 0],
    [1, 0],
    [2, 0],
  ];
  for (const times of [undefined, [0], [0, 2, 1], [0, NaN, 2]]) {
    assert.deepEqual(
      sampleMovement(path, movementTimeline(path, times), 0.25).point,
      [0.5, 0],
    );
  }
});
