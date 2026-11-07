import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

import type { Position, Snapshot } from '../types';
import { isDemo } from '../api/client';
import { distance, target } from '../mocks/simulation';

// Match the dashboard's snapshot update cadence. The map interpolates between
// real simulation positions; it never invents or saves its own dispatch state.
const GLIDE_MS = isDemo ? 200 : 1000;

type Movement = {
  from: Position;
  to: Position;
  marker: L.CircleMarker;
  route?: L.Polyline;
  destination?: Position;
  path: Position[];
};

export default function CityMap({
  snapshot,
  selected,
  onSelect,
}: {
  snapshot: Snapshot;
  selected: string;
  onSelect: (id: string) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string, L.CircleMarker>());
  const routes = useRef(new Map<string, L.Polyline>());
  const destinationMarker = useRef<L.CircleMarker | null>(null);
  const frame = useRef<number | null>(null);
  const previousMinute = useRef<number | null>(null);
  const onSelectRef = useRef(onSelect);
  const [failed, setFailed] = useState(false);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!element.current) return;

    const m = L.map(element.current, { zoomControl: false }).setView(
      [42.731, -73.675],
      13,
    );
    map.current = m;
    L.control.zoom({ position: 'bottomright' }).addTo(m);

    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(m);
    tiles.on('tileerror', () => setFailed(true));
    tiles.on('tileload', () => setFailed(false));

    layer.current = L.layerGroup().addTo(m);
    const observer = new ResizeObserver(() => m.invalidateSize());
    observer.observe(element.current);

    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      observer.disconnect();
      m.remove();
      map.current = null;
      layer.current = null;
      markers.current.clear();
      routes.current.clear();
      destinationMarker.current = null;
      previousMinute.current = null;
    };
  }, []);

  useEffect(() => {
    const g = layer.current;
    if (!g) return;

    // Keep the actual Leaflet markers mounted. Recreating them for each live
    // snapshot causes visible blinking, lost tooltips, and teleportation.
    if (frame.current !== null) cancelAnimationFrame(frame.current);

    const vehicleIds = new Set(snapshot.vehicles.map((v) => v.id));
    for (const [id, marker] of markers.current) {
      if (!vehicleIds.has(id)) {
        marker.remove();
        markers.current.delete(id);
      }
    }
    for (const [id, route] of routes.current) {
      if (!vehicleIds.has(id)) {
        route.remove();
        routes.current.delete(id);
      }
    }

    const movements: Movement[] = [];
    for (const vehicle of snapshot.vehicles) {
      let marker = markers.current.get(vehicle.id);
      if (!marker) {
        const tooltip = document.createElement('span');
        tooltip.textContent = vehicle.id;
        marker = L.circleMarker(vehicle.position, { radius: 8 })
          .bindTooltip(tooltip, {
            permanent: true,
            direction: 'top',
            offset: [0, -8],
          })
          .on('click', () => onSelectRef.current(vehicle.id))
          .addTo(g);
        markers.current.set(vehicle.id, marker);
      }

      const color = vehicle.outOfService
        ? '#89929e'
        : vehicle.holdUntil > snapshot.minute
          ? '#efb24e'
          : '#4ed9b8';
      marker.setStyle({ color, fillColor: color, fillOpacity: 1, weight: 3 });
      marker.setRadius(vehicle.id === selected ? 11 : 8);

      const point = marker.getLatLng();
      const from: Position = [point.lat, point.lng];
      const trip = snapshot.trips.find((t) => t.id === vehicle.tripId);
      let route = routes.current.get(vehicle.id);
      let destination: Position | undefined;
      if (trip) {
        destination = target(trip);
        if (!route) {
          route = L.polyline([from, destination], { interactive: false, opacity: .85 }).addTo(g);
          routes.current.set(vehicle.id, route);
        }
        route.setStyle({
          color: vehicle.id === selected ? '#55dec1' : '#618d88',
          weight: vehicle.id === selected ? 4 : 2,
        });
        route.setLatLngs(vehicle.route ?? []);
      } else if (route) {
        route.remove();
        routes.current.delete(vehicle.id);
        route = undefined;
      }

      marker.bringToFront();
      movements.push({ from, to: vehicle.position, marker, route, destination, path: vehicle.movementPath ?? [from, vehicle.position] });
    }

    const selectedVehicle = snapshot.vehicles.find((v) => v.id === selected);
    const selectedTrip = snapshot.trips.find((t) => t.id === selectedVehicle?.tripId);
    if (selectedTrip) {
      const point = target(selectedTrip);
      const tooltip = document.createElement('span');
      tooltip.textContent = selectedTrip.status === 'onboard'
        ? selectedTrip.to
        : selectedTrip.transferLocation
          ? 'Transfer location'
          : selectedTrip.from;
      if (!destinationMarker.current) {
        destinationMarker.current = L.circleMarker(point, {
          radius: 8,
          color: '#526dc0',
          fillOpacity: 0.2,
        }).bindTooltip(tooltip).addTo(g);
      } else {
        destinationMarker.current.setLatLng(point);
        destinationMarker.current.setTooltipContent(tooltip);
      }
    } else if (destinationMarker.current) {
      destinationMarker.current.remove();
      destinationMarker.current = null;
    }

    // Resets and manual disruptions snap to their authoritative positions.
    // During live updates, interpolate linearly without ease-in/ease-out
    // so that movement doesn't stop briefly between successive ticks.
    const advancing = previousMinute.current !== null && snapshot.minute > previousMinute.current;
    const animate = advancing && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    previousMinute.current = snapshot.minute;

    const update = (progress: number) => {
      for (const { from, to, marker, path } of movements) {
        const position: Position = [
          from[0] + (to[0] - from[0]) * progress,
          from[1] + (to[1] - from[1]) * progress,
        ];
        if(path.length>1){
          const lengths=path.slice(1).map((p,i)=>distance(path[i],p));
          let left=lengths.reduce((a,b)=>a+b,0)*progress;
          let point:Position=path[path.length-1];
          for(let i=0;i<lengths.length;i++){if(left<=lengths[i]&&lengths[i]>0){const t=left/lengths[i];point=[path[i][0]+(path[i+1][0]-path[i][0])*t,path[i][1]+(path[i+1][1]-path[i][1])*t];break;}left-=lengths[i];}
          marker.setLatLng(point);
        }else marker.setLatLng(position);
      }
    };

    if (animate && movements.some(({ from, to }) => from[0] !== to[0] || from[1] !== to[1])) {
      const start = performance.now();
      const glide = (now: number) => {
        const progress = Math.min(1, (now - start) / GLIDE_MS);
        update(progress);
        if (progress < 1) frame.current = requestAnimationFrame(glide);
        else frame.current = null;
      };
      frame.current = requestAnimationFrame(glide);
    } else {
      update(1);
      frame.current = null;
    }

    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [snapshot, selected]);

  // A user selection may recenter once. Live position changes do not pan the map.
  useEffect(() => {
    const vehicle = snapshot.vehicles.find((v) => v.id === selected);
    if (vehicle) map.current?.panTo(vehicle.position);
    // Use only selection changes, not every simulation update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  return (
    <div className="map-wrap">
      <div
        ref={element}
        className="map"
        role="region"
        aria-label="Medical transport map"
      />
      <button
        className="recenter"
        onClick={() => map.current?.setView([42.731, -73.675], 13)}
        aria-label="Recenter map"
      >
        ⌖ Recenter
      </button>
      {failed && <p className="map-error">Map tiles unavailable. Check your connection.</p>}
    </div>
  );
}
