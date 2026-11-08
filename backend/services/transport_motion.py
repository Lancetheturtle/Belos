"""Server-owned movement along persisted OSRM geometry; no browser clock."""
import math
from datetime import timedelta
from backend.services.transport_snapshot import ACTIVE
from backend.services.transport_planner import prepare_active
from backend.services import transport_timing as timing
from backend.transport_store import ambulances, requests, utc


def location(route,progress):
    path=route['path']
    lengths=[]
    for a,b in zip(path,path[1:]):
        lat=math.radians((a[0]+b[0])/2)
        lengths.append(math.hypot(b[0]-a[0],(b[1]-a[1])*math.cos(lat)))
    segments=route.get('segmentDurationsSeconds')
    if segments is not None and len(segments)==len(path)-1 and sum(segments)>0:
        lengths=segments
    total=sum(lengths)
    if total==0 or progress>=1: return path[-1],len(path)-1
    left=total*max(0,progress)
    for i,length in enumerate(lengths):
        if left<=length and length>0:
            fraction=left/length
            return [path[i][0]+(path[i+1][0]-path[i][0])*fraction,
                    path[i][1]+(path[i+1][1]-path[i][1])*fraction],i
        left-=length
    return path[-1],len(path)-1


def advance(store,clock,minutes):
    units,trips=store.source()
    by_unit={v['ambulance_id']:v for v in units}
    by_trip={t['request_id']:t for t in trips}
    prepare_active(store,clock,units,trips)
    all_plans=store.all_plans()
    holds=store.holds()
    start=clock['minute']
    end=start+minutes
    factor=2 if clock['traffic'] else 1
    # Every source change and historical position is committed with the clock.
    for vid,v in by_unit.items():
        if v['status']=='out_of_service': continue
        tasks=[p for p in all_plans.values() if p['vehicle_id']==vid and p['body'].get('stage') not in ('released','complete')]
        tasks.sort(key=lambda p:(p['body'].get('stage')=='queued',p['sequence'],p['trip_id']))
        cursor=start
        changed=False
        for row in tasks:
            t=by_trip.get(row['trip_id'])
            if not t or t['status'] in ('completed','cancelled','transfer'): continue
            body=dict(row['body'])
            if body['stage']=='queued':
                # A stale worker must never steal externally reassigned work.
                if t['ambulance_id']!=vid or t['status']!='scheduled': continue
                cursor=max(cursor,body['stageStarted'],holds.get(vid,{}).get('hold_until',0))
                if cursor>=end: break
                body.update(stage='pickup',stageStarted=cursor,routeIndex=0,jobStarted=cursor)
                store.update_source(requests,'request_id',t['request_id'],status='en_route_to_pickup')
                t['status']='en_route_to_pickup'
                store.update_source(ambulances,'ambulance_id',vid,status='en_route_to_pickup')
            elif t['ambulance_id']!=vid or t['status'] not in ACTIVE:
                continue
            hold=holds.get(vid,{}).get('hold_until',0)
            paused=max(0,min(end,hold)-cursor)
            if paused:
                body['stageStarted']+=paused
                cursor+=paused
            completed=False
            for _ in range(6):
                stage=body['stage']
                if cursor>=end and not (stage=='resetting' and timing.RESET_MINUTES==0): break
                if stage in ('pickup','onboard'):
                    route=body['approach'] if stage=='pickup' else body['transport']
                    duration=route['durationSeconds']/60*factor
                    arrival=body['stageStarted']+duration
                    at,index=location(route,1 if duration<=0 else (end-body['stageStarted'])/duration)
                    v['current_lat'],v['current_lng']=at
                    body['routeIndex']=index
                    changed=True
                    if stage=='pickup':
                        scheduled=(utc(t['pickup_time'])-utc(clock['reference_at'])).total_seconds()/60
                        pickup_at=max(arrival,scheduled) if not body.get('transferLocation') else arrival
                        body['eta']=pickup_at
                        body['predictedAvailable']=pickup_at+timing.LOAD_MINUTES+body['transport']['durationSeconds']/60*factor+timing.HANDOFF_MINUTES+timing.RESET_MINUTES
                        if end<pickup_at:
                            if end>=arrival:
                                store.update_source(requests,'request_id',t['request_id'],status='at_pickup')
                                store.update_source(ambulances,'ambulance_id',vid,status='at_pickup')
                            break
                        body.setdefault('actualPickup',pickup_at)
                        body.update(stage='loading',stageStarted=pickup_at)
                        store.update_source(requests,'request_id',t['request_id'],status='at_pickup')
                        store.update_source(ambulances,'ambulance_id',vid,status='at_pickup')
                        cursor=pickup_at
                    else:
                        body['eta']=arrival
                        body['predictedAvailable']=arrival+timing.HANDOFF_MINUTES+timing.RESET_MINUTES
                        if end<arrival: break
                        body.update(stage='unloading',stageStarted=arrival,completedAt=arrival)
                        cursor=arrival
                elif stage=='loading':
                    departure=body['stageStarted']+timing.LOAD_MINUTES
                    if end<departure: break
                    body.update(stage='onboard',stageStarted=departure,routeIndex=0)
                    body.pop('transferLocation',None)
                    store.update_source(requests,'request_id',t['request_id'],status='transporting')
                    store.update_source(ambulances,'ambulance_id',vid,status='transporting')
                    t['status']='transporting'
                    cursor=departure
                elif stage=='unloading':
                    handoff=body['stageStarted']+timing.HANDOFF_MINUTES
                    if end<handoff: break
                    body.update(stage='resetting',stageStarted=handoff)
                    cursor=handoff
                elif stage=='resetting':
                    available=body['stageStarted']+timing.RESET_MINUTES
                    if end<available: break
                    body['stage']='complete'
                    body['jobEnded']=available
                    store.update_source(requests,'request_id',t['request_id'],status='completed')
                    store.update_source(ambulances,'ambulance_id',vid,status='available')
                    store.event(available,f'{t["request_id"]} completed by {vid}.')
                    t['status']='completed'
                    cursor=available
                    completed=True
                    break
            row['body']=body
            store.save_plan(row)
            if not completed: break
        if changed:
            timestamp=utc(clock['reference_at'])+timedelta(minutes=end)
            store.update_source(ambulances,'ambulance_id',vid,current_lat=v['current_lat'],current_lng=v['current_lng'],
                current_location='Position reported by backend road simulation',last_location_update_at=timestamp)
            store.position(vid,end,[v['current_lat'],v['current_lng']])
    clock['minute']=end


def change_traffic(store,clock,enabled):
    old_factor=2 if clock['traffic'] else 1
    new_factor=2 if enabled else 1
    _,trips=store.source()
    by_trip={t['request_id']:t for t in trips}
    holds=store.holds()
    for row in store.all_plans().values():
        body=dict(row['body'])
        if body.get('stage') not in ('pickup','onboard'): continue
        duration=(body['approach'] if body['stage']=='pickup' else body['transport'])['durationSeconds']/60
        if duration>0:
            progress=max(0,min(1,(clock['minute']-body['stageStarted'])/(duration*old_factor)))
            body['stageStarted']=clock['minute']-progress*duration*new_factor
            remaining=(1-progress)*duration*new_factor
            pending_hold=max(0,holds.get(row['vehicle_id'],{}).get('hold_until',0)-clock['minute'])
            eta=clock['minute']+remaining+pending_hold
            if body['stage']=='pickup':
                scheduled=(utc(by_trip[row['trip_id']]['pickup_time'])-utc(clock['reference_at'])).total_seconds()/60
                eta=max(eta,scheduled)
                body['predictedAvailable']=eta+timing.LOAD_MINUTES+body['transport']['durationSeconds']/60*new_factor+timing.HANDOFF_MINUTES+timing.RESET_MINUTES
            else:
                body['predictedAvailable']=eta+timing.HANDOFF_MINUTES+timing.RESET_MINUTES
            body['eta']=eta
            row['body']=body
            store.save_plan(row)
    clock['traffic']=enabled
