
import os
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

ROUTING_API_URL = (
    "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
)


def get_driving_route(start_lat, start_lng, end_lat, end_lng):
    api_key = os.getenv("OPENROUTESERVICE_API_KEY")

    if not api_key:
        raise RuntimeError("Routing API key is not configured.")

    # OpenRouteService expects [longitude, latitude].
    payload = {
        "coordinates": [
            [float(start_lng), float(start_lat)],
            [float(end_lng), float(end_lat)],
        ]
    }

    response = requests.post(
        ROUTING_API_URL,
        json=payload,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        timeout=15,
    )

    if response.status_code != 200:
        raise RuntimeError("The routing service could not calculate a route.")

    data = response.json()
    features = data.get("features", [])

    if not features:
        raise RuntimeError("No driving route was found.")

    feature = features[0]
    properties = feature.get("properties", {})
    summary = properties.get("summary", {})
    coordinates = feature.get("geometry", {}).get("coordinates", [])

    # Convert [longitude, latitude] to Leaflet's [latitude, longitude].
    route_points = [
        [point[1], point[0]]
        for point in coordinates
        if len(point) >= 2
    ]

    return {
        "distance_meters": summary.get("distance"),
        "duration_seconds": summary.get("duration"),
        "route_points": route_points,
    }
