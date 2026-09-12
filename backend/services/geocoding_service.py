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

    # If results not found, try fallback strategies (comma split, slash split, or first individual word)
    if "results" not in location_data or not location_data.get("results"):
        candidates = []
        if "," in clean_city:
            candidates.append(clean_city.split(",")[0].strip())
        if "/" in clean_city:
            candidates.append(clean_city.split("/")[0].strip())
        # Also try individual words if multi-word query (e.g. "Hanamkonda Warangal")
        parts = [p.strip() for p in clean_city.split() if len(p.strip()) >= 3]
        for p in parts:
            if p not in candidates:
                candidates.append(p)

        for cand in candidates:
            params["name"] = cand
            alt_response = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params=params,
                timeout=5
            )
            if alt_response.status_code == 200:
                alt_data = alt_response.json()
                if "results" in alt_data and alt_data["results"]:
                    location_data = alt_data
                    break

    if "results" not in location_data or not location_data.get("results"):
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
