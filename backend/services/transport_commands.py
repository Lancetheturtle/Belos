"""Transactional commands over the populated directory; legacy services remain intact."""
from datetime import datetime, timezone
from sqlalchemy import insert
from backend.transport_store import Store, TransportError, runtime, ambulances, requests
from backend.services.transport_snapshot import recorded_clock, ACTIVE
from backend.services.transport_planner import assign, optimize, prepare_active, reflow_queue
from backend.services.transport_motion import change_traffic
from backend.services.osrm import RoutingError


def initialize(db):
    store=Store(db)
    units,trips=store.source()
    if db.execute(runtime.select().where(runtime.c.id=='default')).first(): return
    clock=recorded_clock(units,trips)
    db.execute(insert(runtime).values(id='default',reference_at=clock['reference_at'],minute=clock['minute'],
        wall_at=datetime.now(timezone.utc),running=False,speed=1,traffic=False))


def command(db,payload):
    store=Store(db)
    if not store.ready(): raise TransportError('Initialize transport extension storage before sending commands.',503)
    clock=store.clock(lock=True)
    kind=payload['type']
    if kind=='reset':
        from backend.services.transport_reset import reset
        reset(store,clock)
    elif kind=='assign':
        assign(store,clock,payload['tripId'],payload['vehicleId'])
    elif kind=='optimize':
        optimize(store,clock)
    elif kind=='routes':
        units,trips=store.source()
        prepare_active(store,clock,units,trips)
        store.event(clock['minute'],'Active road routes prepared from OSRM.')
    elif kind=='simulation':
        # Starting only changes the worker flag. HTTP reads never advance time.
        clock['running']=payload['running']
        clock['speed']=payload.get('speed',clock['speed'])
        clock['wall_at']=datetime.now(timezone.utc)
        store.event(clock['minute'],f'Backend simulation {"started" if clock["running"] else "paused"} at {clock["speed"]}×.')
    elif kind=='traffic':
        change_traffic(store,clock,payload['enabled'])
        reflow_queue(store,clock)
        store.event(clock['minute'],'Simulated road slowdown '+('enabled.' if payload['enabled'] else 'disabled.'))
    else:
        units,trips=store.source()
        vid=payload['vehicleId']
        v=next((v for v in units if v['ambulance_id']==vid),None)
        if v is None: raise TransportError('Ambulance not found.',404)
        if kind=='delay':
            hold=store.holds().get(vid,{})
            until=max(clock['minute'],hold.get('hold_until',0))+payload['minutes']
            store.hold(vid,until,'Crew delay')
            for row in store.all_plans().values():
                if row['vehicle_id']==vid and row['body'].get('stage') not in ('complete','released'):
                    body=dict(row['body'])
                    for field in ['eta','predictedAvailable']:
                        if field in body: body[field]+=payload['minutes']
                    row['body']=body
                    store.save_plan(row)
            reflow_queue(store,clock)
            store.event(clock['minute'],f'{vid} delayed for {payload["minutes"]} simulated minutes.')
        elif kind=='restore':
            if v['status']!='out_of_service': raise TransportError('Ambulance is not out of service.')
            store.update_source(ambulances,'ambulance_id',vid,status='available')
            store.event(clock['minute'],f'{vid} restored. Released trips were not reclaimed.')
        elif kind=='outage':
            rows=store.all_plans()
            store.update_source(ambulances,'ambulance_id',vid,status='out_of_service')
            transfer_required=False
            for t in trips:
                if t['ambulance_id']!=vid or t['status'] in ('completed','cancelled'): continue
                row=rows.get(t['request_id'])
                body=dict(row['body']) if row else {}
                onboard=t['status']=='transporting' or 'actualPickup' in body
                if onboard:
                    transfer_required=True
                    body['transferLocation']=[v['current_lat'],v['current_lng']]
                body.update(stage='released')
                store.save_plan({'trip_id':t['request_id'],'vehicle_id':vid,'sequence':row['sequence'] if row else 0,'body':body})
                store.update_source(requests,'request_id',t['request_id'],ambulance_id=None,status='transfer' if onboard else 'scheduled')
                store.event(clock['minute'],f'{t["request_id"]} released after {vid} outage'+('; patient remains at stopped ambulance.' if onboard else '.'),
                    'assignment',t['request_id'],vid,None)
            store.event(clock['minute'],f'{vid} marked out of service.')
            if transfer_required:
                store.event(clock['minute'],'Patient transfer requires an explicit replacement assignment; queued planning was not automatically changed.')
            else:
                # Keep the outage even if the routing provider is unavailable.
                try:
                    with db.begin_nested(): optimize(store,clock)
                except (RoutingError,TransportError):
                    store.event(clock['minute'],'Outage recorded. Automatic replanning unavailable; affected trips need manual replacement or a later replan.')
    store.save_clock(clock)
