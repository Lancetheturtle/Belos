import unittest
from unittest.mock import Mock,patch
import requests
from backend.services import osrm

class OsrmTests(unittest.TestCase):
    def setUp(self): osrm._cache.clear()

    def response(self,data):
        response=Mock();response.json.return_value=data;return response

    def test_route_converts_coordinate_order_and_caches_independent_copies(self):
        payload={'code':'Ok','routes':[{'duration':60,'distance':1000,'geometry':{'coordinates':[[-73,42],[-73.1,42.1]]}}]}
        with patch.object(osrm.requests,'get',return_value=self.response(payload)) as get:
            route=osrm.get_road_route([42,-73],[42.1,-73.1])
            self.assertIn('-73,42;-73.1,42.1',get.call_args.args[0])
            self.assertEqual(route['path'],[[42,-73],[42.1,-73.1]])
            route['path'][0][0]=0
            self.assertEqual(osrm.get_road_route([42,-73],[42.1,-73.1])['path'][0][0],42)
            self.assertEqual(get.call_count,1)

    def test_provider_failures_and_invalid_geometry_have_no_direct_line_fallback(self):
        for payload in [{'code':'NoRoute'},{'code':'Ok','routes':[{'duration':60,'distance':1000,'geometry':{'coordinates':[[200,100],[201,101]]}}]}]:
            with patch.object(osrm.requests,'get',return_value=self.response(payload)):
                with self.assertRaises(osrm.RoutingError):osrm.get_road_route([42,-73],[42.1,-73.1])
        with patch.object(osrm.requests,'get',side_effect=requests.Timeout()):
            with self.assertRaises(osrm.RoutingError):osrm.get_road_route([42,-73],[42.1,-73.1])

    def test_unreachable_matrix_entries_are_not_replaced_by_straight_line_estimates(self):
        with patch.object(osrm.requests,'get',return_value=self.response({'code':'Ok','durations':[[0,None],[None,0]]})):
            self.assertEqual(osrm.get_time_matrix([[42,-73],[43,-74]]),[[0,None],[None,0]])

    def test_large_matrices_are_batched_below_service_coordinate_limit(self):
        seen=[]
        def get(url,params,timeout):
            count=len(url.rsplit('/',1)[1].split(';'));seen.append(count)
            rows=len(params['sources'].split(';'));cols=len(params['destinations'].split(';'))
            return self.response({'code':'Ok','durations':[[60]*cols for _ in range(rows)]})
        with patch.object(osrm.requests,'get',side_effect=get):
            result=osrm.get_time_matrix([[42+i/1000,-73] for i in range(81)])
        self.assertEqual([len(result),len(result[0])],[81,81])
        self.assertTrue(all(n<=80 for n in seen))

    def test_same_location_has_zero_travel_without_network(self):
        with patch.object(osrm.requests,'get',side_effect=AssertionError('No request needed')):
            self.assertEqual(osrm.get_time_matrix([[42,-73],[42,-73]]),[[0,0],[0,0]])
            self.assertEqual(osrm.get_road_route([42,-73],[42,-73])['durationSeconds'],0)


    def test_segment_annotations_align_to_geometry_and_include_total_turn_time(self):
        payload={'code':'Ok','routes':[{'duration':120,'distance':1000,
            'geometry':{'coordinates':[[-73,42],[-73.1,42.1],[-73.2,42.2]]},
            'legs':[{'annotation':{'duration':[90,10]}}]}]}
        with patch.object(osrm.requests,'get',return_value=self.response(payload)) as get:
            route=osrm.get_road_route([42,-73],[42.2,-73.2])
            self.assertEqual(get.call_args.kwargs['params']['annotations'],'duration,distance,speed')
            self.assertEqual(route['segmentDurationsSeconds'],[108,12])
            self.assertEqual(route['timingSource'],'OSRM-segment-estimates')
        osrm._cache.clear()
        payload['routes'][0]['legs'][0]['annotation']['duration']=[90]
        with patch.object(osrm.requests,'get',return_value=self.response(payload)):
            with self.assertRaises(osrm.RoutingError): osrm.get_road_route([42,-73],[42.2,-73.2])

if __name__=='__main__':unittest.main()
