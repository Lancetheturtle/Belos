"""A deterministic greedy schedule using OSRM times, with active work frozen.

This is a scheduling heuristic, not a claim of global optimality. It never
replaces the existing legacy truck-dispatch service.
"""
from backend.services.osrm import get_road_route, get_time_matrix, RoutingError
from backend.services.transport_snapshot import ACTIVE
from backend.transport_store import Store, TransportError, utc, ambulances, requests

SERVICE_MINUTES=2.0


def eligible(v,t):
    return (v['status']!='out_of_service' and v['crew_count'] is not None and v['crew_count']>0
        and (t['mobility']!='stretcher' or (v['stretcher_capacity'] or 0)>0)
        and v['service_level']==t['service_level'])


def route_plan(v,t,minute,reference,*,start=None,stage='pickup',factor=1):
    start=start or [v['current_lat'],v['current_lng']]
    pickup=[t['pickup_lat'],t['pickup_lng']]
    destination=[t['dropoff_lat'],t['dropoff_lng']]
    approach=get_road_route(start,pickup) if stage!='onboard' else None
    transport=get_road_route(pickup if stage!='onboard' else start,destination)
    scheduled=(utc(t['pickup_time'])-utc(reference)).total_seconds()/60
    pickup_at=max(minute+(approach['durationSeconds']/60*factor if approach else 0),scheduled)
    return {'stage':stage,'stageStarted':minute,'routeIndex':0,'approach':approach,'transport':transport,
        'eta':(minute+transport['durationSeconds']/60*factor if stage=='onboard' else pickup_at),
        'predictedAvailable':(minute if stage=='onboard' else pickup_at+SERVICE_MINUTES)+transport['durationSeconds']/60*factor+SERVICE_MINUTES}


def prepare_active(store,clock,units,trips):
    existing=store.all_plans()
    by_unit={v['ambulance_id']:v for v in units}
    factor=2 if clock['traffic'] else 1
    for t in trips:
        if t['status'] not in ACTIVE or not t['ambulance_id']: continue
        prior=existing.get(t['request_id'])
        compatible_stages=('onboard','unloading') if t['status']=='transporting' else ('pickup','loading')
        if prior and prior['vehicle_id']==t['ambulance_id'] and prior['body'].get('stage') in compatible_stages: continue
        stage='onboard' if t['status']=='transporting' else 'pickup'
        body=route_plan(by_unit[t['ambulance_id']],t,clock['minute'],clock['reference_at'],stage=stage,factor=factor)
        remaining_hold=max(0,store.holds().get(t['ambulance_id'],{}).get('hold_until',0)-clock['minute'])
        body['eta']+=remaining_hold
        body['predictedAvailable']+=remaining_hold
        store.save_plan({'trip_id':t['request_id'],'vehicle_id':t['ambulance_id'],'sequence':0,'body':body})


def assign(store,clock,trip_id,vehicle_id):
    units,trips=store.source()
    v=next((v for v in units if v['ambulance_id']==vehicle_id),None)
    t=next((t for t in trips if t['request_id']==trip_id),None)
    if not v or not t: raise TransportError('Vehicle or transport not found.',404)
    if t['status'] not in ('scheduled','transfer') or t['ambulance_id']:
        raise TransportError('Transport is already assigned or cannot be reassigned.')
    if any(x['ambulance_id']==vehicle_id and x['status'] in ACTIVE for x in trips):
        raise TransportError('Ambulance already has an active transport.')
    hold=store.holds().get(vehicle_id,{})
    if hold.get('hold_until',0)>clock['minute'] or not eligible(v,t):
        raise TransportError('Ambulance is not available or does not meet the transport requirements.')
    reserved=[p for p in store.all_plans().values() if p['vehicle_id']==vehicle_id and p['body'].get('stage')=='queued']
    if reserved and t['status']!='transfer':
        raise TransportError('Ambulance has a reserved schedule; reoptimize or choose another unit.')
    if (utc(v['shift_end_at'])-utc(clock['reference_at'])).total_seconds()/60<=clock['minute']:
        raise TransportError('Ambulance shift has ended.')
    prior=store.all_plans().get(trip_id,{}).get('body',{})
    target=dict(t)
    if t['status']=='transfer':
        location=prior.get('transferLocation')
        if not location: raise TransportError('Transfer location has not been recorded.')
        target.update(pickup_lat=location[0],pickup_lng=location[1],pickup_time=clock['reference_at'])
    body=route_plan(v,target,clock['minute'],clock['reference_at'],factor=2 if clock['traffic'] else 1)
    if t['status']=='transfer':
        body['transferLocation']=location
        if 'actualPickup' in prior: body['actualPickup']=prior['actualPickup']
    shift_end=(utc(v['shift_end_at'])-utc(clock['reference_at'])).total_seconds()/60
    if body['predictedAvailable']>shift_end: raise TransportError('Transport would finish after the ambulance shift ends.')
    # Explicit patient recovery can displace only future, not-yet-active work.
    for reservation in reserved:
        queued=next((q for q in trips if q['request_id']==reservation['trip_id']),None)
        if not queued or queued['status']!='scheduled' or queued['ambulance_id']!=vehicle_id:
            raise TransportError('A reserved transport changed; refresh before assigning a replacement.')
        reservation['body']={**reservation['body'],'stage':'released'}
        store.save_plan(reservation)
        store.update_source(requests,'request_id',reservation['trip_id'],ambulance_id=None)
        store.event(clock['minute'],f'{reservation["trip_id"]} released to make {vehicle_id} available for explicit patient recovery.','assignment',reservation['trip_id'],vehicle_id,None)
    store.save_plan({'trip_id':trip_id,'vehicle_id':vehicle_id,'sequence':0,'body':body})
    store.update_source(requests,'request_id',trip_id,ambulance_id=vehicle_id,status='en_route_to_pickup')
    store.update_source(ambulances,'ambulance_id',vehicle_id,status='en_route_to_pickup')
    store.event(clock['minute'],f'{trip_id} assigned to {vehicle_id}.','assignment',trip_id,None,vehicle_id)



def recover_transfers(store,clock):
    """Send the fastest feasible free unit to each stranded patient, before queued work."""
    _,pending=store.source()
    for trip in pending:
        if trip['status']!='transfer' or trip['ambulance_id']: continue
        units,trips=store.source()
        prior=store.all_plans().get(trip['request_id'],{}).get('body',{})
        location=prior.get('transferLocation')
        if not location:
            store.event(clock['minute'],f"{trip['request_id']}: automatic replacement unavailable; transfer location is missing.")
            continue
        target={**trip,'pickup_lat':location[0],'pickup_lng':location[1],'pickup_time':clock['reference_at']}
        busy={t['ambulance_id'] for t in trips if t['status'] in ACTIVE}
        holds=store.holds()
        candidates=[]
        routing_failed=False
        for unit in units:
            vid=unit['ambulance_id']
            if vid in busy or not eligible(unit,trip) or holds.get(vid,{}).get('hold_until',0)>clock['minute']: continue
            shift_end=(utc(unit['shift_end_at'])-utc(clock['reference_at'])).total_seconds()/60
            if shift_end<=clock['minute']: continue
            try:
                plan=route_plan(unit,target,clock['minute'],clock['reference_at'],factor=2 if clock['traffic'] else 1)
            except RoutingError:
                routing_failed=True
                continue
            if plan['predictedAvailable']<=shift_end:
                candidates.append((plan['approach']['durationSeconds'],vid))
        for _,vid in sorted(candidates):
            try:
                with store.db.begin_nested(): assign(store,clock,trip['request_id'],vid)
            except (RoutingError,TransportError):
                continue
            store.event(clock['minute'],f"{trip['request_id']}: {vid} automatically dispatched to the stopped ambulance for patient transfer.")
            break
        else:
            reason='road routing unavailable or no feasible replacement' if routing_failed else 'no feasible replacement currently available'
            store.event(clock['minute'],f"{trip['request_id']}: awaiting transfer; {reason}. Replan fleet schedule retries automatic recovery.")


def optimize(store,clock,*,recover=True):
    if recover: recover_transfers(store,clock)
    units,trips=store.source()
    prepare_active(store,clock,units,trips)
    existing=store.all_plans()
    pending=[t for t in trips if t['status']=='scheduled']
    if not pending: return
    usable=[v for v in units if v['status']!='out_of_service']
    if not usable: raise TransportError('No available ambulances.')
    locations=[(v['current_lat'],v['current_lng']) for v in usable]
    locations+= [(t['pickup_lat'],t['pickup_lng']) for t in trips]
    locations+= [(t['dropoff_lat'],t['dropoff_lng']) for t in trips]
    unique=list(dict.fromkeys(locations))
    matrix=get_time_matrix(unique)
    index={p:i for i,p in enumerate(unique)}
    factor=2 if clock['traffic'] else 1
    def duration(a,b):
        value=matrix[index[tuple(a)]][index[tuple(b)]]
        return None if value is None else value/60*factor
    schedules={v['ambulance_id']:[] for v in usable}
    base={v['ambulance_id']:([v['current_lat'],v['current_lng']], max(clock['minute'],store.holds().get(v['ambulance_id'],{}).get('hold_until',0))) for v in usable}
    for t in trips:
        if t['status'] in ACTIVE and t['ambulance_id'] in base:
            body=existing.get(t['request_id'],{}).get('body',{})
            base[t['ambulance_id']]=([t['dropoff_lat'],t['dropoff_lng']],max(clock['minute'],body.get('predictedAvailable',clock['minute'])))

    def evaluate(v,sequence):
        start,available=base[v['ambulance_id']]
        shift_end=(utc(v['shift_end_at'])-utc(clock['reference_at'])).total_seconds()/60
        lateness=0
        result=[]
        for t in sequence:
            if not eligible(v,t): return None
            pickup=[t['pickup_lat'],t['pickup_lng']]
            destination=[t['dropoff_lat'],t['dropoff_lng']]
            approach=duration(start,pickup)
            transport=duration(pickup,destination)
            if approach is None or transport is None: return None
            scheduled=(utc(t['pickup_time'])-utc(clock['reference_at'])).total_seconds()/60
            at=max(available+approach,scheduled)
            finish=at+SERVICE_MINUTES+transport+SERVICE_MINUTES
            if finish>shift_end: return None
            result.append((t,v,start,available,at,finish))
            lateness+=max(0,at-scheduled)
            start,available=destination,finish
        return lateness,available,result

    # Try every feasible insertion; minimize the increase in predicted lateness.
    for t in sorted(pending,key=lambda t:(utc(t['pickup_time']),t['request_id'])):
        choices=[]
        for v in usable:
            sequence=schedules[v['ambulance_id']]
            previous=evaluate(v,sequence)
            if previous is None: continue
            for position in range(len(sequence)+1):
                candidate=sequence[:position]+[t]+sequence[position:]
                evaluated=evaluate(v,candidate)
                if evaluated is None: continue
                late,finish,_=evaluated
                choices.append(((late-previous[0],finish-previous[1],v['ambulance_id'],position),v['ambulance_id'],candidate))
        if choices:
            _,vid,candidate=min(choices,key=lambda item:item[0])
            schedules[vid]=candidate
    prepared=[]
    for v in usable:
        evaluated=evaluate(v,schedules[v['ambulance_id']])
        for sequence,(t,vehicle,start,available,at,finish) in enumerate(evaluated[2] if evaluated else [],1):
            body=route_plan(vehicle,t,available,clock['reference_at'],start=start,stage='queued',factor=factor)
            body.update(eta=at,predictedAvailable=finish,stageStarted=max(available,at-body['approach']['durationSeconds']/60*factor))
            prepared.append((t,{'trip_id':t['request_id'],'vehicle_id':v['ambulance_id'],'sequence':sequence,'body':body}))
    selected={row['trip_id']:row['vehicle_id'] for _,row in prepared}
    for t in pending:
        old=t['ambulance_id'] or None
        new=selected.get(t['request_id'])
        if t['request_id'] in existing and existing[t['request_id']]['body'].get('stage')=='queued' and not new:
            row=existing[t['request_id']]
            row['body']={**row['body'],'stage':'released'}
            store.save_plan(row)
        store.update_source(requests,'request_id',t['request_id'],ambulance_id=new)
        if old!=new:
            store.event(clock['minute'],f'{t["request_id"]} '+(f'scheduled on {new} by greedy road-time planning.' if new else 'requires a new feasible ambulance assignment.'),'assignment',t['request_id'],old,new)
    for _,row in prepared:
        store.save_plan(row)
    store.event(clock['minute'],'Fleet schedule recalculated using OSRM driving times; heuristic results, not guaranteed optimal.')


def reflow_queue(store,clock):
    """Refresh persisted queue forecasts after a delay/traffic change, without OSRM calls."""
    _,trips=store.source()
    by_trip={t['request_id']:t for t in trips}
    rows=store.all_plans()
    holds=store.holds()
    factor=2 if clock['traffic'] else 1
    for vid in {row['vehicle_id'] for row in rows.values()}:
        available=max(clock['minute'],holds.get(vid,{}).get('hold_until',0))
        for row in rows.values():
            if row['vehicle_id']==vid and row['body'].get('stage') not in ('queued','complete','released'):
                available=max(available,row['body'].get('predictedAvailable',available))
        for row in sorted(rows.values(),key=lambda row:row['sequence']):
            if row['vehicle_id']!=vid or row['body'].get('stage')!='queued':continue
            t=by_trip.get(row['trip_id'])
            if not t or t['status']!='scheduled' or t['ambulance_id']!=vid:continue
            body=dict(row['body'])
            scheduled=(utc(t['pickup_time'])-utc(clock['reference_at'])).total_seconds()/60
            eta=max(available+body['approach']['durationSeconds']/60*factor,scheduled)
            finish=eta+SERVICE_MINUTES+body['transport']['durationSeconds']/60*factor+SERVICE_MINUTES
            body.update(stageStarted=max(available,eta-body['approach']['durationSeconds']/60*factor),eta=eta,predictedAvailable=finish)
            row['body']=body;store.save_plan(row)
            available=finish
