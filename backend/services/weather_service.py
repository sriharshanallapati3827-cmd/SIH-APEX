import os
from typing import Dict, Any
from fastapi import HTTPException
from .geocoding_service import get_coordinates
from .providers.base import BaseWeatherProvider
from .providers.open_meteo import OpenMeteoProvider
from .providers.imd import IMDProvider
from .providers.tomorrow_io import TomorrowIOProvider


def get_weather_provider() -> BaseWeatherProvider:
    """
    Factory function to obtain the configured weather data provider.

    Default: Open-Meteo (100% free, keyless, reliable 10,000 requests/day).
    Optional: Tomorrow.io v4 (when WEATHER_PROVIDER=tomorrow_io) or IMD (when WEATHER_PROVIDER=imd).
    """
    provider_name = os.getenv("WEATHER_PROVIDER", "open_meteo").lower().strip()
    if provider_name == "imd":
        return IMDProvider()
    if provider_name == "tomorrow_io":
        return TomorrowIOProvider()
    # Default: Open-Meteo
    return OpenMeteoProvider()


def get_active_provider_name() -> str:
    """Return the name of the currently active weather provider."""
    return get_weather_provider().name


def get_current_weather_by_coords(latitude: float, longitude: float) -> Dict[str, Any]:
    """Fetch current raw weather for GPS coordinates from the active provider."""
    provider = get_weather_provider()
    return provider.get_current_weather(latitude, longitude)


def get_current_weather_by_city(city: str) -> Dict[str, Any]:
    """Geocode city and fetch current weather from the active provider."""
    location = get_coordinates(city)
    provider = get_weather_provider()
    weather_data = provider.get_current_weather(location["latitude"], location["longitude"])
    current = weather_data.get("current", weather_data)

    return {
        "city": location["name"],
        "country": location.get("country"),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "weather": current,
        "source": provider.name
    }


def get_weather_summary_by_location(latitude: float, longitude: float) -> Dict[str, Any]:
    """Fetch normalized current weather summary for GPS coordinates."""
    provider = get_weather_provider()
    weather_data = provider.get_current_weather(latitude, longitude)
    current = weather_data.get("current", {})

    return {
        "latitude": latitude,
        "longitude": longitude,
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "precipitation": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind_direction": current.get("wind_direction_10m"),
        "source": provider.name
    }


def get_forecast_by_coords(latitude: float, longitude: float, period: str = "next_7_days") -> Dict[str, Any]:
    """Fetch forecast for GPS coordinates from active provider."""
    provider = get_weather_provider()
    return provider.get_forecast(latitude, longitude, period=period)


def get_forecast_by_city(city: str, period: str = "next_7_days") -> Dict[str, Any]:
    """Geocode city and fetch forecast from active provider."""
    location = get_coordinates(city)
    provider = get_weather_provider()
    forecast_result = provider.get_forecast(location["latitude"], location["longitude"], period=period)

    result = {
        "city": location["name"],
        "country": location.get("country"),
        "forecast_period": forecast_result.get("forecast_period", period),
        "forecast": forecast_result["forecast"],
        "source": forecast_result.get("source", provider.name)
    }
    if "hourly_forecast" in forecast_result:
        result["hourly_forecast"] = forecast_result["hourly_forecast"]

    return result


def get_alerts_by_coords(latitude: float, longitude: float) -> Dict[str, Any]:
    """Fetch weather alerts for GPS coordinates from active provider."""
    provider = get_weather_provider()
    return provider.get_alerts(latitude, longitude)


def get_alerts_by_city(city: str) -> Dict[str, Any]:
    """Geocode city and fetch weather alerts from active provider."""
    location = get_coordinates(city)
    provider = get_weather_provider()
    alerts_result = provider.get_alerts(location["latitude"], location["longitude"])

    return {
        "city": location["name"],
        "alerts": alerts_result["alerts"],
        "source": alerts_result.get("source", provider.name)
    }
