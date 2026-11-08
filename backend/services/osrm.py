"""Validated OSRM road geometry and batched travel-time matrices.

Only coordinates are sent to OSRM. No patient IDs or database credentials leave
the backend. There is deliberately no straight-line routing fallback.
"""
import math
import os
import threading
import time
from collections import OrderedDict
import requests

OSRM_URL = os.getenv('OSRM_URL','https://router.project-osrm.org').rstrip('/')
_cache = OrderedDict()
_lock = threading.Lock()


class RoutingError(Exception):
    pass


def _point(p):
    if not isinstance(p,(list,tuple)) or len(p)!=2 or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in p) or abs(p[0])>90 or abs(p[1])>180:
        raise RoutingError('Invalid route coordinates.')
    return tuple(p)


def _number(n):
    return not isinstance(n,bool) and isinstance(n,(float,int)) and math.isfinite(n) and n>=0


def _request(service, coordinates, **params):
    values=';'.join(f'{lng},{lat}' for lat,lng in coordinates)
    try:
        response=requests.get(f'{OSRM_URL}/{service}/v1/driving/{values}',params=params,timeout=(5,15))
        response.raise_for_status()
        data=response.json()
    except (requests.RequestException,ValueError) as exc:
        raise RoutingError('Road-routing service unavailable.') from exc
    if not isinstance(data,dict) or data.get('code')!='Ok':
        raise RoutingError('No driving route is available for these coordinates.')
    return data


def get_road_route(start,end):
    start,end=_point(start),_point(end)
    if start==end:
        return {'path':[list(start),list(end)],'durationSeconds':0,'distanceMeters':0}
    key=(start,end)
    with _lock:
        cached=_cache.get(key)
        if cached and time.monotonic()-cached[0]<300:
            _cache.move_to_end(key)
            # Callers persist/modify their own copy, never the shared cache.
            import copy
            return copy.deepcopy(cached[1])
    data=_request('route',[start,end],overview='full',geometries='geojson',steps='false',annotations='duration,distance,speed')
    try:
        route=data['routes'][0]
        coordinates=route['geometry']['coordinates']
        if len(coordinates)<2 or not _number(route['duration']) or not _number(route['distance']):
            raise ValueError()
        path=[list(_point((p[1],p[0]))) for p in coordinates if len(p)==2]
        if len(path)!=len(coordinates): raise ValueError()
        result={'path':path,'durationSeconds':route['duration'],'distanceMeters':route['distance'],
                'timingSource':'route-average'}
        durations=[value for leg in route.get('legs',[]) for value in leg.get('annotation',{}).get('duration',[])]
        if durations:
            if len(durations)!=len(path)-1 or not all(_number(n) for n in durations):
                raise ValueError()
            total=sum(durations)
            if total>0:
                # Include aggregate turn costs while retaining per-segment speed variation.
                scale=route['duration']/total
                result['segmentDurationsSeconds']=[n*scale for n in durations]
                result['timingSource']='OSRM-segment-estimates'

    except (KeyError,IndexError,TypeError,ValueError) as exc:
        raise RoutingError('Road-routing service returned invalid geometry.') from exc
    with _lock:
        _cache[key]=(time.monotonic(),result)
        _cache.move_to_end(key)
        while len(_cache)>256: _cache.popitem(last=False)
    import copy
    return copy.deepcopy(result)


def get_time_matrix(locations):
    points=[_point(p) for p in locations]
    if not points: return []
    unique=list(dict.fromkeys(points))
    if len(unique)==1: return [[0 for _ in points] for _ in points]
    matrix=[[None]*len(unique) for _ in unique]
    # Each request contains at most 80 distinct coordinates. Null means no route.
    for i in range(0,len(unique),40):
        for j in range(0,len(unique),40):
            sources=unique[i:i+40]
            destinations=unique[j:j+40]
            block=list(dict.fromkeys(sources+destinations))
            indices={p:k for k,p in enumerate(block)}
            data=_request('table',block,
                sources=';'.join(str(indices[p]) for p in sources),
                destinations=';'.join(str(indices[p]) for p in destinations),annotations='duration')
            durations=data.get('durations')
            if not isinstance(durations,list) or len(durations)!=len(sources) or any(not isinstance(r,list) or len(r)!=len(destinations) or any(v is not None and not _number(v) for v in r) for r in durations):
                raise RoutingError('Road-routing service returned an invalid time matrix.')
            for a,row in enumerate(durations):
                for b,value in enumerate(row): matrix[i+a][j+b]=value
    indices={p:k for k,p in enumerate(unique)}
    return [[matrix[indices[a]][indices[b]] for b in points] for a in points]
