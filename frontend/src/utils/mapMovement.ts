import type { Position } from '../types';
import { distance } from '../mocks/simulation';

// Backend timestamps preserve each road segment's speed and any stationary time.
// Older/demo snapshots fall back to distance-weighted interpolation.
export function movementTimeline(path: Position[], times?: number[]): number[] {
  if (
    times?.length === path.length &&
    times.every(
      (value, i) =>
        Number.isFinite(value) && (i === 0 || value >= times[i - 1]),
    ) &&
    times.length > 1 &&
    times[times.length - 1] > times[0]
  )
    return times.map((value) => value - times[0]);

  const result = [0];
  for (let i = 1; i < path.length; i++) {
    result.push(result[i - 1] + distance(path[i - 1], path[i]));
  }
  return result;
}

export function sampleMovement(
  path: Position[],
  timeline: number[],
  progress: number,
) {
  const elapsed =
    (timeline[timeline.length - 1] ?? 0) * Math.max(0, Math.min(1, progress));
  for (let i = 1; i < path.length; i++) {
    const duration = timeline[i] - timeline[i - 1];
    if (duration > 0 && elapsed < timeline[i]) {
      const fraction = (elapsed - timeline[i - 1]) / duration;
      const point: Position = [
        path[i - 1][0] + (path[i][0] - path[i - 1][0]) * fraction,
        path[i - 1][1] + (path[i][1] - path[i - 1][1]) * fraction,
      ];
      return { point, untraveled: path.slice(i) };
    }
  }
  return { point: path[path.length - 1], untraveled: [] as Position[] };
}
