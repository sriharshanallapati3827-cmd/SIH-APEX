import requests
from fastapi import HTTPException


def get_coordinates(city: str) -> dict:
    """
    Look up a city name and return its coordinates.
    Returns a dict with keys: name, country, latitude, longitude.
    Raises HTTPException if the city is not found or the service is unavailable.
    """
    if not city or not str(city).strip():
        raise HTTPException(
            status_code=404,
            detail="City not found"
        )

    clean_city = str(city).strip()
    for prefix in ["in ", "at ", "around ", "near ", "for "]:
        if clean_city.lower().startswith(prefix):
            clean_city = clean_city[len(prefix):].strip()

    params = {
        "name": clean_city,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    location_response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params=params
    )

    if location_response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Location service is not available"
        )

    location_data = location_response.json()

    # If results not found and there's a comma (e.g. "Hyderabad, India"), try primary city
    if ("results" not in location_data or not location_data["results"]) and "," in clean_city:
        primary_city = clean_city.split(",")[0].strip()
        params["name"] = primary_city
        alt_response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params=params
        )
        if alt_response.status_code == 200:
            alt_data = alt_response.json()
            if "results" in alt_data and alt_data["results"]:
                location_data = alt_data

    if "results" not in location_data or not location_data["results"]:
        raise HTTPException(
            status_code=404,
            detail="City not found"
        )

    location = location_data["results"][0]

    return {
        "name": location["name"],
        "country": location.get("country"),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
    }
