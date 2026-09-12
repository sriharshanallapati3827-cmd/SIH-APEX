"""
Weather Context Pipeline for WeatherGPT.
Connects structured QueryUnderstanding output to the weather service to assemble
a compact, relevant weather data payload for subsequent grounding.
"""

from typing import Dict, Any, Optional, Union
from models.schemas import QueryUnderstanding
from services.weather_service import (
    get_current_weather_by_city,
    get_weather_summary_by_location,
    get_forecast_by_city,
    get_forecast_by_coords,
    get_alerts_by_city,
    get_alerts_by_coords,
    get_active_provider_name,
)


def build_weather_context(
    query: Union[QueryUnderstanding, Dict[str, Any]],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build a compact, structured weather context payload based on a QueryUnderstanding object.
    Does NOT call the LLM and does NOT generate prose.
    Only retrieves and filters live weather metrics from the active provider.
    """
    # 1. Normalize query input to dictionary
    if isinstance(query, QueryUnderstanding):
        q_intent = query.intent
        q_location = query.location or query.city
        q_time_period = query.time_period or query.forecast_period
        q_weather_variable = query.weather_variable
        q_requires_location = query.requires_location
    elif isinstance(query, dict):
        q_intent = query.get("intent", "unknown")
        q_location = query.get("location") or query.get("city")
        q_time_period = query.get("time_period") or query.get("forecast_period")
        q_weather_variable = query.get("weather_variable")
        q_requires_location = query.get("requires_location", False)
    else:
        raise ValueError("query must be an instance of QueryUnderstanding or dict.")

    # 2. Handle missing location
    use_coords = False
    if not q_location:
        if latitude is not None and longitude is not None:
            use_coords = True
        elif q_requires_location or q_intent != "unknown":
            return {
                "status": "location_required",
                "intent": q_intent,
                "location": None,
                "coordinates": None,
                "time_period": q_time_period,
                "weather_variable": q_weather_variable,
                "message": "Location is required to retrieve weather information. Please specify a city or provide GPS coordinates.",
                "weather_data": None,
                "source": None,
            }

    # 3. Handle unsupported or unknown intent
    if q_intent == "unknown":
        return {
            "status": "unsupported_intent",
            "intent": "unknown",
            "location": q_location,
            "coordinates": {"latitude": latitude, "longitude": longitude} if use_coords else None,
            "time_period": q_time_period,
            "weather_variable": q_weather_variable,
            "message": "The query could not be understood as a supported weather request.",
            "weather_data": None,
            "source": None,
        }

    # 4. Map intent and time period to weather data retrieval
    forecast_periods = {"today", "tomorrow", "next_3_days", "this_week", "next_7_days", "weekend", "hourly"}
    is_forecast_query = q_time_period in forecast_periods or q_intent in (
        "forecast",
        "rain",
        "advisory",
        "farmer_advisory",
        "travel_advisory",
    )
    period = q_time_period if q_time_period in forecast_periods else "today" if q_intent == "rain" else "next_7_days"

    location_name = None
    country = None
    coords = None
    source = get_active_provider_name()
    weather_data: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Case A: Current Weather, Temperature, Humidity, Wind
    # -------------------------------------------------------------------------
    if q_intent in ("current_weather", "temperature", "humidity", "wind") and not (
        q_time_period in ("tomorrow", "weekend", "next_3_days", "next_7_days", "hourly")
    ):
        if use_coords:
            raw_curr = get_weather_summary_by_location(latitude, longitude)
            location_name = f"Coordinates ({latitude}, {longitude})"
            coords = {"latitude": latitude, "longitude": longitude}
            curr = {
                "temperature_2m": raw_curr.get("temperature"),
                "apparent_temperature": raw_curr.get("apparent_temperature"),
                "relative_humidity_2m": raw_curr.get("humidity"),
                "precipitation": raw_curr.get("precipitation"),
                "rain": raw_curr.get("rain", 0),
                "weather_code": raw_curr.get("weather_code"),
                "wind_speed_10m": raw_curr.get("wind_speed"),
                "wind_direction_10m": raw_curr.get("wind_direction"),
            }
            source = raw_curr.get("source", source)
        else:
            raw_curr = get_current_weather_by_city(q_location)
            location_name = raw_curr["city"]
            country = raw_curr.get("country")
            coords = {"latitude": raw_curr["latitude"], "longitude": raw_curr["longitude"]}
            curr = raw_curr.get("weather", {})
            source = raw_curr.get("source", source)

        if q_intent == "temperature":
            weather_data = {
                "temperature": curr.get("temperature_2m"),
                "apparent_temperature": curr.get("apparent_temperature"),
                "unit": "°C",
            }
        elif q_intent == "humidity":
            weather_data = {
                "humidity": curr.get("relative_humidity_2m"),
                "unit": "%",
                "temperature": curr.get("temperature_2m"),
            }
        elif q_intent == "wind":
            weather_data = {
                "wind_speed": curr.get("wind_speed_10m"),
                "wind_direction": curr.get("wind_direction_10m"),
                "unit": "km/h",
            }
        else:  # current_weather
            weather_data = {
                "temperature": curr.get("temperature_2m"),
                "apparent_temperature": curr.get("apparent_temperature"),
                "humidity": curr.get("relative_humidity_2m"),
                "precipitation": curr.get("precipitation"),
                "rain": curr.get("rain", 0),
                "weather_code": curr.get("weather_code"),
                "wind_speed": curr.get("wind_speed_10m"),
                "wind_direction": curr.get("wind_direction_10m"),
            }

    # -------------------------------------------------------------------------
    # Case B: Rain / Precipitation (Current or Forecast)
    # -------------------------------------------------------------------------
    elif q_intent == "rain":
        if use_coords:
            raw_f = get_forecast_by_coords(latitude, longitude, period=period)
            location_name = f"Coordinates ({latitude}, {longitude})"
            coords = {"latitude": latitude, "longitude": longitude}
        else:
            raw_f = get_forecast_by_city(q_location, period=period)
            location_name = raw_f["city"]
            country = raw_f.get("country")
            coords = {"latitude": raw_f.get("latitude"), "longitude": raw_f.get("longitude")}
        source = raw_f.get("source", source)

        forecast_list = raw_f.get("forecast", [])
        weather_data = {
            "forecast_period": period,
            "precipitation_data": [
                {
                    "date": d.get("date"),
                    "rain_probability": d.get("rain_probability"),
                    "rainfall_mm": d.get("rainfall"),
                    "max_temperature": d.get("max_temperature"),
                }
                for d in forecast_list
            ],
        }
        if "hourly_forecast" in raw_f and period in ("hourly", "today", "tomorrow"):
            weather_data["hourly_precipitation"] = [
                {
                    "time": h.get("time"),
                    "rain_probability": h.get("rain_probability"),
                    "precipitation": h.get("precipitation"),
                }
                for h in raw_f["hourly_forecast"][:12]
            ]

    # -------------------------------------------------------------------------
    # Case C: Forecast / Future Temperature / Future Wind / Future Humidity
    # -------------------------------------------------------------------------
    elif q_intent in ("forecast", "temperature", "wind", "humidity"):
        if use_coords:
            raw_f = get_forecast_by_coords(latitude, longitude, period=period)
            location_name = f"Coordinates ({latitude}, {longitude})"
            coords = {"latitude": latitude, "longitude": longitude}
        else:
            raw_f = get_forecast_by_city(q_location, period=period)
            location_name = raw_f["city"]
            country = raw_f.get("country")
            coords = {"latitude": raw_f.get("latitude"), "longitude": raw_f.get("longitude")}
        source = raw_f.get("source", source)

        if q_intent == "temperature":
            weather_data = {
                "forecast_period": period,
                "temperatures": [
                    {
                        "date": d.get("date"),
                        "max_temperature": d.get("max_temperature"),
                        "min_temperature": d.get("min_temperature"),
                    }
                    for d in raw_f.get("forecast", [])
                ],
            }
        elif q_intent == "wind":
            weather_data = {
                "forecast_period": period,
                "wind_data": [
                    {
                        "date": d.get("date"),
                        "max_wind_speed": d.get("max_wind_speed"),
                    }
                    for d in raw_f.get("forecast", [])
                ],
            }
        elif q_intent == "humidity":
            weather_data = {
                "forecast_period": period,
                "forecast": raw_f.get("forecast", []),
            }
        else:  # forecast
            weather_data = {
                "forecast_period": period,
                "forecast": raw_f.get("forecast", []),
            }
            if "hourly_forecast" in raw_f and period in ("hourly", "today", "tomorrow"):
                weather_data["hourly_forecast"] = raw_f["hourly_forecast"][:12]

    # -------------------------------------------------------------------------
    # Case D: Advisories (general, farmer, travel)
    # -------------------------------------------------------------------------
    elif q_intent in ("advisory", "farmer_advisory", "travel_advisory"):
        if use_coords:
            raw_f = get_forecast_by_coords(latitude, longitude, period=period)
            raw_a = get_alerts_by_coords(latitude, longitude)
            location_name = f"Coordinates ({latitude}, {longitude})"
            coords = {"latitude": latitude, "longitude": longitude}
        else:
            raw_f = get_forecast_by_city(q_location, period=period)
            raw_a = get_alerts_by_city(q_location)
            location_name = raw_f["city"]
            country = raw_f.get("country")
            coords = {"latitude": raw_f.get("latitude"), "longitude": raw_f.get("longitude")}
        source = raw_f.get("source", source)

        weather_data = {
            "forecast_period": period,
            "forecast": raw_f.get("forecast", []),
            "alerts": raw_a.get("alerts", []),
        }

    # -------------------------------------------------------------------------
    # Case E: Alerts
    # -------------------------------------------------------------------------
    elif q_intent == "alerts":
        if use_coords:
            raw_a = get_alerts_by_coords(latitude, longitude)
            location_name = f"Coordinates ({latitude}, {longitude})"
            coords = {"latitude": latitude, "longitude": longitude}
        else:
            raw_a = get_alerts_by_city(q_location)
            location_name = raw_a["city"]
            country = raw_a.get("country")
        source = raw_a.get("source", source)
        weather_data = {
            "alerts": raw_a.get("alerts", []),
        }

    # -------------------------------------------------------------------------
    # Case F: General Weather
    # -------------------------------------------------------------------------
    elif q_intent == "general_weather":
        if use_coords:
            raw_c = get_weather_summary_by_location(latitude, longitude)
            raw_f = get_forecast_by_coords(latitude, longitude, period="today")
            location_name = f"Coordinates ({latitude}, {longitude})"
            coords = {"latitude": latitude, "longitude": longitude}
            curr = raw_c
        else:
            raw_c = get_current_weather_by_city(q_location)
            raw_f = get_forecast_by_city(q_location, period="today")
            location_name = raw_c["city"]
            country = raw_c.get("country")
            coords = {"latitude": raw_c["latitude"], "longitude": raw_c["longitude"]}
            curr = raw_c.get("weather", {})
        source = raw_c.get("source", source)

        weather_data = {
            "current": curr,
            "today_forecast": raw_f.get("forecast", []),
        }

    return {
        "status": "success",
        "intent": q_intent,
        "location": location_name,
        "country": country,
        "coordinates": coords,
        "time_period": q_time_period,
        "weather_variable": q_weather_variable,
        "weather_data": weather_data,
        "source": source,
    }
