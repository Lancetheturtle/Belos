
import os
import requests

OSRM_URL = os.getenv(
    "OSRM_URL",
    "https://router.project-osrm.org"
).rstrip("/")


def get_road_route(start, end):
    """
    start/end: (latitude, longitude)
    Returns road route in Leaflet coordinate order.
    """

    start_lat, start_lng = start
    end_lat, end_lng = end

    coordinates = (
        f"{start_lng},{start_lat};"
        f"{end_lng},{end_lat}"
    )

    url = f"{OSRM_URL}/route/v1/driving/{coordinates}"

    response = requests.get(
        url,
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "false"
        },
        timeout=10
    )
    response.raise_for_status()

    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(
            f"OSRM could not find a route: {data.get('code')}"
        )

    result = data["routes"][0]

    path = [
        [lat, lng]
        for lng, lat in result["geometry"]["coordinates"]
    ]

    return {
        "path": path,
        "durationSeconds": result["duration"],
        "distanceMeters": result["distance"]
    }
