import {useEffect,useRef,useState} from 'react';
import L from 'leaflet';
import type {Snapshot} from '../types';
import {target} from '../mocks/simulation';
export default function CityMap({snapshot,selected,onSelect}:{snapshot:Snapshot;selected:string;onSelect:(id:string)=>void}){
 const element=useRef<HTMLDivElement>(null),map=useRef<L.Map|null>(null),layer=useRef<L.LayerGroup|null>(null);const [failed,setFailed]=useState(false);
 useEffect(()=>{if(!element.current)return;const m=L.map(element.current,{zoomControl:false}).setView([42.731,-73.675],13);map.current=m;L.control.zoom({position:"bottomright"}).addTo(m);
 const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',maxZoom:19}).addTo(m);
 tiles.on('tileerror',()=>setFailed(true));tiles.on('tileload',()=>setFailed(false));layer.current=L.layerGroup().addTo(m);
 const observer=new ResizeObserver(()=>m.invalidateSize());observer.observe(element.current);return()=>{observer.disconnect();m.remove();};},[]);
 useEffect(()=>{const g=layer.current;if(!g)return;g.clearLayers();
 snapshot.vehicles.forEach(v=>{const t=snapshot.trips.find(t=>t.id===v.tripId);if(t)L.polyline([v.position,target(t)],{color:v.id===selected?'#55dec1':'#618d88',weight:v.id===selected?4:2,dashArray:'6 7'}).addTo(g);
 const color=v.outOfService?'#89929e':v.holdUntil>snapshot.minute?'#efb24e':'#4ed9b8';
 const marker=L.circleMarker(v.position,{radius:v.id===selected?11:8,color,fillColor:color,fillOpacity:1,weight:3});const label=document.createElement('span');label.textContent=v.id;marker.bindTooltip(label,{permanent:true,direction:'top',offset:[0,-8]}).on('click',()=>onSelect(v.id)).addTo(g);
 });
 const v=snapshot.vehicles.find(v=>v.id===selected),t=snapshot.trips.find(t=>t.id===v?.tripId);if(t){const marker=L.circleMarker(target(t),{radius:8,color:'#526dc0',fillOpacity:.2});const label=document.createElement('span');label.textContent=t.status==='onboard'?t.to:t.transferLocation?'Transfer location':t.from;marker.bindTooltip(label).addTo(g);}
 },[snapshot,selected,onSelect]);
 useEffect(()=>{const v=snapshot.vehicles.find(v=>v.id===selected);if(v)map.current?.panTo(v.position);},[selected]);
 return <div className="map-wrap"><div ref={element} className="map" role="region" aria-label="Medical transport map"/><button className="recenter" onClick={()=>map.current?.setView([42.731,-73.675],13)} aria-label="Recenter map">⌖ Recenter</button>{failed&&<p className="map-error">Map tiles unavailable. Check your connection.</p>}</div>;
}
