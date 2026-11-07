import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { Snapshot } from '../types';

export default function CityMap({snapshot,selected,onSelect}:{snapshot:Snapshot;selected:string|null;onSelect:(id:string)=>void}) {
  const container=useRef<HTMLDivElement>(null), map=useRef<L.Map|null>(null), layer=useRef<L.LayerGroup|null>(null);
  const [tileError,setTileError]=useState(false);
  useEffect(()=>{
    if(!container.current) return;
    const city=L.map(container.current,{zoomControl:false}).setView([42.731,-73.674],13);
    map.current=city; L.control.zoom({position:'bottomright'}).addTo(city);
    const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',maxZoom:19}).addTo(city);
    tiles.on('tileerror',()=>setTileError(true));
    tiles.on('tileload',()=>setTileError(false));
    layer.current=L.layerGroup().addTo(city);
    const resize=new ResizeObserver(()=>city.invalidateSize()); resize.observe(container.current);
    return ()=>{resize.disconnect();city.remove();map.current=null;};
  },[]);
  useEffect(()=>{
    if(!layer.current) return; const group=layer.current; group.clearLayers();
    snapshot.vehicles.forEach(v=>{
      if(v.route) L.polyline(v.route,{color:'#0b8b79',weight:3,opacity:.65,dashArray:'7 7'}).addTo(group);
      const marker=L.marker(v.position,{icon:L.divIcon({className:'',html:`<span class="vehicle-pin ${v.status}">✚</span>`,iconSize:[28,28],iconAnchor:[14,14]}),title:v.id});
      const tip=document.createElement('span'); tip.textContent=`${v.id} · ${v.status}`; marker.bindTooltip(tip).addTo(group);
    });
    snapshot.incidents.filter(i=>i.status!=='resolved').forEach(i=>{
      const marker=L.circleMarker(i.location,{radius:selected===i.id?12:8,color:i.priority==='critical'?'#dc594a':i.priority==='urgent'?'#ce902b':'#5874af',fillColor:i.priority==='critical'?'#dc594a':i.priority==='urgent'?'#ce902b':'#5874af',fillOpacity:.22,weight:selected===i.id?4:2});
      const tip=document.createElement('span'); tip.textContent=`${i.id} · ${i.name} · ${i.priority}`; marker.bindTooltip(tip).on('click',()=>onSelect(i.id)).addTo(group);
    });
  },[snapshot,selected,onSelect]);
  useEffect(()=>{const incident=snapshot.incidents.find(i=>i.id===selected);if(incident) map.current?.panTo(incident.location);},[selected]);
  return <div className="map-shell"><div ref={container} className="city-map" role="region" aria-label="Troy ambulance and incident map"/><div className="map-location"><span className="live-dot"/> TROY, NEW YORK <span>42.7284° N · 73.6918° W</span></div><button className="recenter" onClick={()=>map.current?.setView([42.731,-73.674],13)}>⌖ Recenter</button><div className="map-legend"><span><i className="legend-dot green"/> Ambulance</span><span><i className="legend-dot red"/> Critical</span><span><i className="legend-dot amber"/> Urgent</span><span><i className="legend-dot blue"/> Standard</span></div>{tileError&&<div className="tile-warning" role="status">Map tiles unavailable. Check your internet connection; markers remain interactive.</div>}</div>;
}
