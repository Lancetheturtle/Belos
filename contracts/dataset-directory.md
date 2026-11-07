# Dataset directory

The sidebar Patient transports and Dataset ambulances sections read a build-time snapshot from frontend/src/data/transportDataset.json, converted from the supplied transport_requests.csv and ambulances.csv. The SQL files were inspected as schema/reference only; no SQL was executed. 60 transports and 15 ambulances are included. All patients are fictional IDs.

Join transport_requests.ambulance_id to ambulances.ambulance_id. Needs pickup includes scheduled, assigned, en_route_to_pickup, and at_pickup. Transporting means patient onboard; en_route_to_pickup means the vehicle is heading to the patient. For transporting patients, show the assigned vehicle's recorded coordinates. For completed trips show the dropoff facility, not the ambulance's later location. Pickup timestamps are displayed with date in America/New_York.

This directory is explicitly a static CSV snapshot and is independent of the existing four-unit road simulation. It does not query Tiger Data or update on simulation actions. The SQL seed uses NOW()-relative times while CSV dates are fixed, so database-import timestamps may differ. To connect later, return these original fields through a backend directory endpoint and replace the JSON data source; never put database credentials in the browser.
