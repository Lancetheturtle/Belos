import type { Position, Snapshot } from '../types';
import cached from '../mocks/roadRoutes.json';
const cache = new Map<string, Position[]>(
  Object.entries(cached) as [string, Position[]][],
);
export async function roadRoute(a: Position, b: Position): Promise<Position[]> {
  const key = `${a.join(',')};${b.join(',')}`;
  if (cache.has(key)) return structuredClone(cache.get(key)!);
  const response = await fetch(
    `https://router.project-osrm.org/route/v1/driving/${a[1]},${a[0]};${b[1]},${b[0]}?overview=full&geometries=geojson`,
    { signal: AbortSignal.timeout(12000) },
  );
  if (!response.ok)
    throw new Error('Road routing unavailable. Retry when connected.');
  const data = await response.json();
  if (data.code !== 'Ok' || !data.routes?.[0]?.geometry?.coordinates?.length)
    throw new Error('No driving route found.');
  const points: Position[] = data.routes[0].geometry.coordinates.map(
    (p: number[]) => [p[1], p[0]],
  );
  cache.set(key, points);
  return structuredClone(points);
}
export async function prepareRoads(state: Snapshot): Promise<Snapshot> {
  const s = structuredClone(state);
  for (const t of s.trips)
    if (!t.transportRoute)
      t.transportRoute = await roadRoute(t.pickup, t.destination);
  for (const v of s.vehicles)
    if (v.tripId && !v.route) {
      const t = s.trips.find((t) => t.id === v.tripId)!;
      v.route = await roadRoute(v.position, t.transferLocation ?? t.pickup);
      v.routeIndex = 0;
      v.position = [...v.route[0]];
    }
  return s;
}
