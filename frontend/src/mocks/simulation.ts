import type { Conditions, Incident, Metrics, Policy, Position, Snapshot, Vehicle } from '../types';

const bases: Position[] = [[42.731,-73.687],[42.744,-73.682],[42.718,-73.686],[42.731,-73.665],[42.749,-73.668],[42.712,-73.674],[42.739,-73.656],[42.724,-73.65]];
const locations: Position[] = [[42.728,-73.691],[42.735,-73.675],[42.746,-73.677],[42.717,-73.669],[42.738,-73.658],[42.725,-73.662],[42.752,-73.683],[42.711,-73.682],[42.742,-73.667],[42.722,-73.677],[42.734,-73.649],[42.747,-73.656]];
const names = ['Downtown Troy','College Hill','North Central','South Troy','Eastside','Prospect Park','Lansingburgh','Riverfront','Samaritan area','Little Italy','Upper Eastside','Frear Park'];
export function createScenario(scenario: Snapshot['scenario'] = 'routine'): Snapshot {
  return { scenario, elapsedSeconds: 0, comparison: null, events: [scenario === 'routine' ? 'Routine scenario loaded · 8 units, 4 incidents' : 'Surge scenario loaded · 6 units available, 12 incidents'],
    vehicles: bases.map((position, i) => ({ id: `EMS-${String(i + 1).padStart(2, '0')}`, position: [...position], status: scenario === 'surge' && i > 5 ? 'unavailable' : 'available' })),
    incidents: locations.slice(0, scenario === 'surge' ? 12 : 4).map((location,i) => ({ id: `INC-${String(i+1).padStart(3,'0')}`, name: names[i], location: [...location], priority: i % 3 === 0 ? 'critical' : i % 3 === 1 ? 'urgent' : 'standard', status:'waiting' })) };
}
export function distance(a: Position, b: Position): number {
  const rad = Math.PI / 180;
  const dLat = (b[0]-a[0])*rad, dLng = (b[1]-a[1])*rad;
  const h = Math.sin(dLat/2)**2 + Math.cos(a[0]*rad)*Math.cos(b[0]*rad)*Math.sin(dLng/2)**2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1-h));
}
type Pair = { vehicle: Vehicle; incident: Incident; km: number; minutes: number };
function assignments(state: Snapshot, policy: Policy, conditions: Conditions): Pair[] {
  const vehicles = state.vehicles.filter(v => v.status === 'available');
  const incidents = state.incidents.filter(i => i.status === 'waiting');
  const factor = (conditions.traffic === 'heavy' ? 1.65 : 1) * (conditions.weather === 'rain' ? 1.2 : 1);
  const pair = (i: number, v: number): Pair => { const km = distance(vehicles[v].position, incidents[i].location); return {vehicle: vehicles[v], incident: incidents[i], km, minutes: km / 32 * 60 * factor + .5}; };
  if (policy === 'nearest') {
    const used = new Set<number>();
    return incidents.flatMap((_, i) => {
      const available = vehicles.map((_,v) => v).filter(v => !used.has(v)).sort((a,b) => pair(i,a).minutes - pair(i,b).minutes);
      if (!available.length) return [];
      used.add(available[0]); return [pair(i,available[0])];
    });
  }
  // Small demo-only exact assignment via vehicle bitmask DP. No road or clinical model.
  const memo = new Map<string,{cost:number;pairs:Pair[]}>();
  function solve(i:number, mask:number): {cost:number;pairs:Pair[]} {
    if (i === incidents.length) return {cost:0,pairs:[]};
    const key = `${i}:${mask}`; if (memo.has(key)) return memo.get(key)!;
    const skip = solve(i+1,mask); let best = {cost:skip.cost+10000,pairs:skip.pairs};
    for (let v=0;v<vehicles.length;v++) if (!(mask & (1<<v))) {
      const p = pair(i,v), tail = solve(i+1,mask|(1<<v));
      if (p.minutes+tail.cost < best.cost) best={cost:p.minutes+tail.cost,pairs:[p,...tail.pairs]};
    }
    memo.set(key,best); return best;
  }
  return solve(0,0).pairs;
}
function metrics(state:Snapshot,pairs:Pair[]):Metrics {
  const km = pairs.reduce((sum,p)=>sum+p.km,0);
  return {meanEtaMinutes:pairs.length ? pairs.reduce((sum,p)=>sum+p.minutes,0)/pairs.length : 0, distanceKm:km, co2Kg:km*.35, assigned:pairs.length, unserved:state.incidents.filter(i=>i.status==='waiting').length-pairs.length};
}
export function dispatch(state:Snapshot, policy:Policy, conditions:Conditions):Snapshot {
  const baseline=assignments(state,'nearest',conditions), optimized=assignments(state,'optimized',conditions);
  const pairs=policy==='nearest'?baseline:optimized;
  const next=structuredClone(state);
  next.comparison={nearest:metrics(state,baseline),optimized:metrics(state,optimized)};
  for (const p of pairs) {
    const vehicle=next.vehicles.find(v=>v.id===p.vehicle.id)!;
    vehicle.status='enroute'; vehicle.incidentId=p.incident.id; vehicle.route=[[...vehicle.position],[...p.incident.location]]; vehicle.progress=0; vehicle.durationSeconds=p.minutes*60;
    next.incidents.find(i=>i.id===p.incident.id)!.status='assigned';
  }
  next.events=[`${policy==='nearest'?'Nearest available':'Fleet optimizer'} assigned ${pairs.length} unit${pairs.length===1?'':'s'}`, ...next.events].slice(0,8);
  return next;
}
export function advance(state:Snapshot,seconds:number):Snapshot {
  const next=structuredClone(state); next.elapsedSeconds+=seconds;
  for (const v of next.vehicles) if(v.status==='enroute' && v.route && v.durationSeconds) {
    v.progress=Math.min(1,(v.progress??0)+seconds/v.durationSeconds);
    const a=v.route[0], b=v.route[v.route.length-1];
    v.position=[a[0]+(b[0]-a[0])*v.progress,a[1]+(b[1]-a[1])*v.progress];
    if(v.progress===1) {
      const incident=next.incidents.find(i=>i.id===v.incidentId); if(incident) incident.status='resolved';
      next.events=[`${v.id} reached ${v.incidentId} · demo incident resolved`,...next.events].slice(0,8);
      v.status='available'; delete v.incidentId; delete v.route; delete v.progress; delete v.durationSeconds;
    }
  }
  return next;
}
export function addIncident(state:Snapshot,priority:Incident['priority']):Snapshot {
  const next=structuredClone(state), n=next.incidents.length, index=n%locations.length;
  next.incidents.push({id:`INC-${String(n+1).padStart(3,'0')}`,name:names[index],location:[locations[index][0]+.0003*Math.floor(n/locations.length),locations[index][1]],priority,status:'waiting'});
  next.events=[`New ${priority} incident added · ${names[index]}`,...next.events].slice(0,8);
  next.comparison=null; return next;
}
