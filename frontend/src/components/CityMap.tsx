import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

import type { Snapshot, TransportDirectory } from '../types';

export default function CityMap({
  snapshot,
  scheduleData,
  selected,
  onSelect,
  requestFocus = 0,
  showSchedule = false,
  selectedRequest = null,
  onSelectRequest,
}: {
  snapshot: Snapshot;
  scheduleData: TransportDirectory;
  selected: string;
  onSelect: (id: string) => void;
  requestFocus?: number;
  showSchedule?: boolean;
  selectedRequest?: string | null;
  onSelectRequest?: (id: string) => void;
}) {
  const scheduleRef = useRef(scheduleData);
  scheduleRef.current = scheduleData;
  const scheduleLayer = useRef<L.LayerGroup | null>(null);
  const requestSelectRef = useRef(onSelectRequest);
  requestSelectRef.current = onSelectRequest;
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string, L.CircleMarker>());
  const routes = useRef(new Map<string, L.Polyline>());
  const calls = useRef(new Map<string, L.Marker>());
  const destinationMarker = useRef<L.CircleMarker | null>(null);
  const onSelectRef = useRef(onSelect);
  const snapshotRef = useRef(snapshot);
  snapshotRef.current = snapshot;
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

    const tiles = L.tileLayer(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      },
    ).addTo(m);
    tiles.on('tileerror', () => setFailed(true));
    tiles.on('tileload', () => setFailed(false));

    layer.current = L.layerGroup().addTo(m);
    scheduleLayer.current = L.layerGroup().addTo(m);
    const observer = new ResizeObserver(() => m.invalidateSize());
    observer.observe(element.current);

    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
      layer.current = null;
      markers.current.clear();
      routes.current.clear();
      calls.current.clear();
      destinationMarker.current = null;
    };
  }, []);

  useEffect(() => {
    const g = layer.current;
    if (!g) return;

    // Keep the actual Leaflet markers mounted. Recreating them for each live
    // snapshot causes visible blinking, lost tooltips, and teleportation.

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
        : vehicle.tripId || vehicle.holdUntil > snapshot.minute
          ? '#4ed9b8'
          : '#8bb7f0';
      marker.setStyle({ color, fillColor: color, fillOpacity: 1, weight: 3 });
      marker.setRadius(vehicle.id === selected ? 11 : 8);

      // Plot exactly the position returned by the server; do not extrapolate.
      marker.setLatLng(vehicle.position);
      const trip = snapshot.trips.find((t) => t.id === vehicle.tripId);
      const tooltip = document.createElement('span');
      tooltip.textContent = trip
        ? `${vehicle.id} · ${trip.id} · ${trip.status === 'onboard' ? 'Drop-off' : 'Pickup'}`
        : vehicle.id;
      marker.setTooltipContent(tooltip);
      let route = routes.current.get(vehicle.id);
      if (trip && vehicle.route && vehicle.route.length >= 2) {
        if (!route) {
          route = L.polyline(vehicle.route, {
            interactive: false,
            opacity: 0.85,
          }).addTo(g);
          routes.current.set(vehicle.id, route);
        }
        route.setStyle({
          color: (vehicle.routePhase === 'dropoff' || trip.status === 'onboard') ? '#63a5ff' : '#22c55e',
          weight: vehicle.id === selected ? 4 : 2,
        });
        // Geometry is authoritative backend data, including its endpoints.
        route.setLatLngs(vehicle.route);
      } else if (route) {
        route.remove();
        routes.current.delete(vehicle.id);
        route = undefined;
      }

      marker.bringToFront();

    }

    // Keep pickup beacons mounted so their pulse continues across live ticks.
    const pendingCalls = snapshot.trips.filter((t) =>
      ['waiting', 'pickup', 'transfer'].includes(t.status),
    );
    const callIds = new Set(pendingCalls.map((t) => t.id));
    for (const [id, marker] of calls.current) {
      if (!callIds.has(id)) {
        marker.remove();
        calls.current.delete(id);
      }
    }
    for (const trip of pendingCalls) {
      const location = trip.transferLocation ?? trip.pickup;
      let marker = calls.current.get(trip.id);
      const label = document.createElement('span');
      label.textContent = `${trip.id} · ${trip.transferLocation ? 'Transfer pickup' : trip.from}`;
      if (!marker) {
        marker = L.marker(location, {
          icon: L.divIcon({
            className: 'call-beacon',
            html: '<span class="call-ring"></span><span class="call-ring call-ring-second"></span><span class="call-dot"></span>',
            iconSize: [20, 20],
            iconAnchor: [10, 10],
          }),
          title: `Pickup call ${trip.id}`,
          zIndexOffset: -100,
        })
          .bindTooltip(label)
          .on('click', () => {
            const unit = snapshotRef.current.vehicles.find(
              (v) => v.tripId === trip.id,
            );
            if (unit) onSelectRef.current(unit.id);
          })
          .addTo(g);
        calls.current.set(trip.id, marker);
      } else {
        marker.setLatLng(location);
        marker.setTooltipContent(label);
      }
    }
    const selectedVehicle = snapshot.vehicles.find((v) => v.id === selected);
    const selectedTrip = snapshot.trips.find(
      (t) => t.id === selectedVehicle?.tripId,
    );
    if (selectedTrip?.status === 'onboard') {
      const point = selectedTrip.destination;
      const tooltip = document.createElement('span');
      tooltip.textContent = selectedTrip.to;
      if (!destinationMarker.current) {
        destinationMarker.current = L.circleMarker(point, {
          radius: 8,
          color: '#526dc0',
          fillOpacity: 0.2,
        })
          .bindTooltip(tooltip)
          .addTo(g);
      } else {
        destinationMarker.current.setLatLng(point);
        destinationMarker.current.setTooltipContent(tooltip);
      }
    } else if (destinationMarker.current) {
      destinationMarker.current.remove();
      destinationMarker.current = null;
    }

  }, [snapshot, selected]);

  useEffect(() => {
    const group = scheduleLayer.current;
    if (!group) return;
    group.clearLayers();
    if (!showSchedule) return;
    for (const request of scheduleData.transport_requests) {
      const label = document.createElement('span');
      label.textContent = `${request.patient_id} · ${request.pickup_location}`;
      L.circleMarker([request.pickup_lat, request.pickup_lng], {
        radius: request.request_id === selectedRequest ? 9 : 5,
        color: '#d4a8ff',
        fillColor: '#d4a8ff',
        fillOpacity: request.status === 'completed' ? 0.2 : 0.55,
        weight: 2,
      })
        .bindTooltip(label)
        .on('click', () => requestSelectRef.current?.(request.request_id))
        .addTo(group);
    }
    const request = scheduleData.transport_requests.find(
      (t) => t.request_id === selectedRequest,
    );
    if (request) {
      const label = document.createElement('span');
      label.textContent = `Destination: ${request.dropoff_location}`;
      L.circleMarker([request.dropoff_lat, request.dropoff_lng], {
        radius: 11,
        color: '#75b7ff',
        fillOpacity: 0.15,
        weight: 3,
      })
        .bindTooltip(label, { permanent: true })
        .addTo(group);
    }
  }, [showSchedule, selectedRequest, scheduleData]);
  useEffect(() => {
    const request = scheduleRef.current.transport_requests.find(
      (t) => t.request_id === selectedRequest,
    );
    if (showSchedule && request)
      map.current?.fitBounds(
        [
          [request.pickup_lat, request.pickup_lng],
          [request.dropoff_lat, request.dropoff_lng],
        ],
        { padding: [65, 65], maxZoom: 14 },
      );
  }, [selectedRequest, showSchedule, requestFocus]);
  // A user selection may recenter once. Live position changes do not pan the map.
  useEffect(() => {
    const vehicle = snapshot.vehicles.find((v) => v.id === selected);
    if (vehicle) map.current?.panTo(vehicle.position);
    // Use only selection changes, not every server update.
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
      {showSchedule && (
        <div className="static-map-label">
          Purple dots: server schedule pickups · Blue ring: selected destination
        </div>
      )}
      {failed && (
        <p className="map-error">
          Map tiles unavailable. Check your connection.
        </p>
      )}
    </div>
  );
}
