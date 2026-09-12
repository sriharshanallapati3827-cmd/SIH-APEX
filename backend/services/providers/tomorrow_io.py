"""
Tomorrow.io Weather Provider (backend/services/providers/tomorrow_io.py)

Integrates Tomorrow.io v4 API for:
  - Current real-time weather (/realtime)
  - 7-day daily + 24h hourly forecast (/forecast)
  - Condition-based weather alerts derived from real-time values

API Key: Set TOMORROW_IO_API_KEY in backend/.env
Docs: https://docs.tomorrow.io/reference/weather-forecast

Note: Uses requests with socket-level IPv4 enforcement to avoid IPv6 TCP resets
      on some ISP/cloud setups where Tomorrow.io's GCP backend resets IPv6 conns.
"""

import os
import socket
import requests
from datetime import datetime
from typing import Dict, Any, List

from fastapi import HTTPException
from .base import BaseWeatherProvider


TOMORROW_IO_API_KEY = os.getenv("TOMORROW_IO_API_KEY", "yKhAZKT6oVO3zKoRXGE5QUfltAg1sNoO")
TOMORROW_BASE_URL = "https://api.tomorrow.io/v4/weather"

# Force IPv4 resolution to avoid connection resets on IPv6 for Tomorrow.io's GCP infra
_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


# --------------------------------------------------------------------------- #
# Field-value mappings from Tomorrow.io documentation                         #
# --------------------------------------------------------------------------- #
WEATHER_CODE_MAP = {
    1000: "Clear Sky", 1001: "Cloudy", 1100: "Mostly Clear",
    1101: "Partly Cloudy", 1102: "Mostly Cloudy",
    2000: "Fog", 2100: "Light Fog",
    3000: "Light Wind", 3001: "Wind", 3002: "Strong Wind",
    4000: "Drizzle", 4001: "Rain", 4200: "Light Rain", 4201: "Heavy Rain",
    5000: "Snow", 5001: "Flurries", 5100: "Light Snow", 5101: "Heavy Snow",
    6000: "Freezing Drizzle", 6001: "Freezing Rain",
    6200: "Light Freezing Rain", 6201: "Heavy Freezing Rain",
    7000: "Ice Pellets", 7101: "Heavy Ice Pellets", 7102: "Light Ice Pellets",
    8000: "Thunderstorm"
}


def _fetch(url: str) -> Dict[str, Any]:
    """
    HTTP GET via requests, forced to IPv4 to avoid TCP resets on IPv6 networks.
    Tomorrow.io runs on GCP; some ISPs get connection-reset on IPv6 paths.
    """
    # Temporarily patch socket to prefer IPv4
    socket.getaddrinfo = _ipv4_getaddrinfo
    try:
        resp = requests.get(url, timeout=12)
    except requests.ConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Tomorrow.io unreachable: {str(e)}"
        )
    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Tomorrow.io request timed out"
        )
    finally:
        # Always restore original getaddrinfo
        socket.getaddrinfo = _original_getaddrinfo

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Tomorrow.io: Invalid API key")
    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail="Tomorrow.io: Rate limit exceeded — try again shortly")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Tomorrow.io error (HTTP {resp.status_code}): {resp.text[:200]}"
        )
    return resp.json()


class TomorrowIOProvider(BaseWeatherProvider):
    """
    Tomorrow.io v4 Weather Provider — richest data set available.
    Provides: UV index, visibility, apparent temp, dew point, cloud cover,
              pressure, snow intensity, thunderstorm detection — beyond Open-Meteo.
    """

    @property
    def name(self) -> str:
        return "Tomorrow.io"

    # ------------------------------------------------------------------ #
    # Current Weather                                                      #
    # ------------------------------------------------------------------ #
    def get_current_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch real-time weather via Tomorrow.io /realtime endpoint.
        Returns normalised dict compatible with WeatherGPT's existing field schema.
        """
        url = (
            f"{TOMORROW_BASE_URL}/realtime"
            f"?location={latitude},{longitude}"
            f"&apikey={TOMORROW_IO_API_KEY}"
            f"&units=metric"
        )
        data = _fetch(url)
        values = data.get("data", {}).get("values", {})
        weather_code = values.get("weatherCode", 0)

        current = {
            # Standard direct aliases for universal consumption
            "temperature_2m":        values.get("temperature"),
            "temperature":           values.get("temperature"),
            "apparent_temperature":  values.get("temperatureApparent"),
            "feels_like":            values.get("temperatureApparent"),
            "relative_humidity_2m":  values.get("humidity"),
            "humidity":              values.get("humidity"),
            "wind_speed_10m":        values.get("windSpeed"),
            "wind_speed":            values.get("windSpeed"),
            "wind_direction_10m":    values.get("windDirection"),
            "precipitation":         values.get("precipitationIntensity"),
            "rain":                  values.get("rainIntensity"),
            "weather_code":          weather_code,
            "weather_description":   WEATHER_CODE_MAP.get(weather_code, "Unknown"),
            "condition":             WEATHER_CODE_MAP.get(weather_code, "Unknown"),
            # Tomorrow.io extras (richer than Open-Meteo)
            "uv_index":              values.get("uvIndex"),
            "uv_health_concern":     values.get("uvHealthConcern"),
            "visibility":            values.get("visibility"),
            "cloud_cover":           values.get("cloudCover"),
            "dew_point":             values.get("dewPoint"),
            "pressure_sea_level":    values.get("pressureSeaLevel"),
            "pressure_surface":      values.get("pressureSurfaceLevel"),
            "snow_intensity":        values.get("snowIntensity"),
            "precipitation_probability": values.get("precipitationProbability"),
        }

        return {
            "current": current,
            "source":    self.name,
            "latitude":  latitude,
            "longitude": longitude,
            "time":      data.get("data", {}).get("time"),
        }

    # ------------------------------------------------------------------ #
    # Forecast                                                             #
    # ------------------------------------------------------------------ #
    def get_forecast(self, latitude: float, longitude: float, period: str = "next_7_days") -> Dict[str, Any]:
        """
        Fetch daily + hourly forecast via Tomorrow.io /forecast endpoint.
        Returns normalised arrays compatible with WeatherGPT schema.
        """
        url = (
            f"{TOMORROW_BASE_URL}/forecast"
            f"?location={latitude},{longitude}"
            f"&apikey={TOMORROW_IO_API_KEY}"
            f"&units=metric"
            f"&timesteps=1d,1h"
        )
        data = _fetch(url)
        timelines = data.get("timelines", {})

        # ---- Daily ---- #
        daily_raw: List[Dict] = timelines.get("daily", [])
        days = []
        for entry in daily_raw:
            v = entry.get("values", {})
            wc = v.get("weatherCodeMax", 0)
            days.append({
                "date":                entry.get("time", "")[:10],
                "max_temperature":     v.get("temperatureMax"),
                "min_temperature":     v.get("temperatureMin"),
                "rain_probability":    v.get("precipitationProbabilityAvg"),
                "rainfall":            v.get("precipitationIntensityAvg"),
                "max_wind_speed":      v.get("windSpeedMax"),
                "weather_code":        wc,
                "weather_description": WEATHER_CODE_MAP.get(wc, "Unknown"),
                "uv_index_max":        v.get("uvIndexMax"),
                "humidity_avg":        v.get("humidityAvg"),
            })

        # ---- Hourly (next 24 h) ---- #
        hourly_raw: List[Dict] = timelines.get("hourly", [])
        hourly_filtered = []
        for entry in hourly_raw[:24]:
            v = entry.get("values", {})
            wc = v.get("weatherCode", 0)
            hourly_filtered.append({
                "time":                entry.get("time", ""),
                "temperature":         v.get("temperature"),
                "rain_probability":    v.get("precipitationProbability"),
                "rainfall":            v.get("precipitationIntensity"),
                "wind_speed":          v.get("windSpeed"),
                "weather_code":        wc,
                "weather_description": WEATHER_CODE_MAP.get(wc, "Unknown"),
            })

        # ---- Period filter ---- #
        period_norm = (period or "next_7_days").lower()
        if period_norm == "today":
            filtered_days = days[:1]
        elif period_norm == "tomorrow":
            filtered_days = days[1:2] if len(days) > 1 else days[:1]
        elif period_norm == "next_3_days":
            filtered_days = days[:3]
        elif period_norm == "weekend":
            try:
                weekend = [d for d in days if datetime.fromisoformat(d["date"]).weekday() in (5, 6)]
                filtered_days = weekend if weekend else days[:2]
            except Exception:
                filtered_days = days[:2]
        else:
            filtered_days = days[:7]

        return {
            "latitude":        latitude,
            "longitude":       longitude,
            "forecast_period": period_norm,
            "forecast":        filtered_days,
            "hourly_forecast": hourly_filtered,
            "source":          self.name,
        }

    # ------------------------------------------------------------------ #
    # Alerts                                                               #
    # ------------------------------------------------------------------ #
    def get_alerts(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Derive real-time alerts from Tomorrow.io live conditions.
        Covers heat, wind, rain, UV, snow, and thunderstorm.
        """
        url = (
            f"{TOMORROW_BASE_URL}/realtime"
            f"?location={latitude},{longitude}"
            f"&apikey={TOMORROW_IO_API_KEY}"
            f"&units=metric"
        )
        data = _fetch(url)
        values = data.get("data", {}).get("values", {})

        alerts = []
        temp         = values.get("temperature", 0) or 0
        wind         = values.get("windSpeed", 0) or 0
        rain         = values.get("rainIntensity", 0) or 0
        uv           = values.get("uvIndex", 0) or 0
        snow         = values.get("snowIntensity", 0) or 0
        weather_code = values.get("weatherCode", 0) or 0

        if temp >= 40:
            alerts.append({"type": "Extreme Heat", "severity": "High",
                           "message": f"Extreme heat: {temp:.1f}°C. Avoid outdoor exposure. Stay hydrated. (Tomorrow.io)"})
        elif temp >= 35:
            alerts.append({"type": "Heat Warning", "severity": "Moderate",
                           "message": f"High temperature: {temp:.1f}°C. Take precautions. (Tomorrow.io)"})

        if wind >= 60:
            alerts.append({"type": "Severe Wind", "severity": "High",
                           "message": f"Dangerous wind: {wind:.1f} km/h. Avoid travel. (Tomorrow.io)"})
        elif wind >= 40:
            alerts.append({"type": "Strong Wind", "severity": "Moderate",
                           "message": f"Strong winds: {wind:.1f} km/h. Exercise caution. (Tomorrow.io)"})

        if rain >= 10:
            alerts.append({"type": "Heavy Rain", "severity": "High",
                           "message": f"Heavy rain: {rain:.1f} mm/hr. Flood risk in low areas. (Tomorrow.io)"})
        elif rain >= 2.5:
            alerts.append({"type": "Rain", "severity": "Moderate",
                           "message": f"Moderate rain: {rain:.1f} mm/hr. Carry an umbrella. (Tomorrow.io)"})

        if uv >= 8:
            alerts.append({"type": "High UV", "severity": "High",
                           "message": f"UV Index {uv:.0f} — Very High. Use SPF 50+ and avoid midday sun. (Tomorrow.io)"})
        elif uv >= 6:
            alerts.append({"type": "UV Warning", "severity": "Moderate",
                           "message": f"UV Index {uv:.0f} — High. Apply sunscreen. (Tomorrow.io)"})

        if snow >= 1:
            alerts.append({"type": "Snowfall", "severity": "Moderate",
                           "message": f"Snowfall: {snow:.1f} mm/hr. Roads may be slippery. (Tomorrow.io)"})

        if weather_code == 8000:
            alerts.append({"type": "Thunderstorm", "severity": "High",
                           "message": "Active thunderstorm. Stay indoors. (Tomorrow.io)"})

        if not alerts:
            alerts.append({"type": "No Major Alert", "severity": "Low",
                           "message": f"{WEATHER_CODE_MAP.get(weather_code, 'Clear')} — no major risks. Enjoy your day! (Tomorrow.io)"})

        return {
            "latitude":  latitude,
            "longitude": longitude,
            "alerts":    alerts,
            "source":    f"{self.name} (Real-time Advisory)",
        }
