from datetime import datetime
from typing import Dict, Any
import requests
from fastapi import HTTPException
from .base import BaseWeatherProvider


class OpenMeteoProvider(BaseWeatherProvider):
    """
    Active MVP Weather Provider using Open-Meteo API.
    Provides free, keyless global & Indian weather data, forecasts, and condition-derived advisories.
    """

    @property
    def name(self) -> str:
        return "Open-Meteo"

    def get_current_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetch current weather metrics from Open-Meteo including:
        temperature, apparent temperature, humidity, precipitation, rain, weather_code, wind speed, wind direction.
        """
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m"
        )
        try:
            response = requests.get(url, timeout=10)
        except requests.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Open-Meteo service unreachable: {str(e)}"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Open-Meteo error (HTTP {response.status_code}): Weather service is not available"
            )

        data = response.json()
        data["source"] = self.name
        return data

    def get_forecast(self, latitude: float, longitude: float, period: str = "next_7_days") -> Dict[str, Any]:
        """
        Fetch 7-day daily and hourly forecast from Open-Meteo.
        Supports filtering by period: today, tomorrow, next_3_days, next_7_days, weekend, hourly.
        """
        forecast_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&daily=temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,precipitation_sum,wind_speed_10m_max"
            "&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m"
            "&forecast_days=7"
            "&timezone=auto"
        )
        try:
            forecast_response = requests.get(forecast_url, timeout=10)
        except requests.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Open-Meteo service unreachable: {str(e)}"
            )

        if forecast_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Open-Meteo error (HTTP {forecast_response.status_code}): Forecast service is not available"
            )

        forecast_data = forecast_response.json()
        daily = forecast_data.get("daily", {})
        hourly = forecast_data.get("hourly", {})

        days = []
        if "time" in daily:
            for i in range(len(daily["time"])):
                day = {
                    "date": daily["time"][i],
                    "max_temperature": daily["temperature_2m_max"][i],
                    "min_temperature": daily["temperature_2m_min"][i],
                    "rain_probability": daily["precipitation_probability_max"][i],
                    "rainfall": daily["precipitation_sum"][i],
                    "max_wind_speed": daily.get("wind_speed_10m_max", [None] * len(daily["time"]))[i]
                }
                days.append(day)

        period_norm = (period or "next_7_days").lower()
        filtered_days = days
        hourly_filtered = []

        if period_norm == "today":
            filtered_days = days[:1]
            target_date = days[0]["date"] if days else ""
            if hourly and "time" in hourly:
                for h_i, h_time in enumerate(hourly["time"]):
                    if h_time.startswith(target_date):
                        hourly_filtered.append({
                            "time": h_time,
                            "temperature": hourly["temperature_2m"][h_i],
                            "rain_probability": hourly["precipitation_probability"][h_i],
                            "rainfall": hourly["precipitation"][h_i],
                            "wind_speed": hourly["wind_speed_10m"][h_i]
                        })
        elif period_norm == "tomorrow":
            filtered_days = [days[1]] if len(days) > 1 else days[:1]
            target_date = days[1]["date"] if len(days) > 1 else (days[0]["date"] if days else "")
            if hourly and "time" in hourly:
                for h_i, h_time in enumerate(hourly["time"]):
                    if h_time.startswith(target_date):
                        hourly_filtered.append({
                            "time": h_time,
                            "temperature": hourly["temperature_2m"][h_i],
                            "rain_probability": hourly["precipitation_probability"][h_i],
                            "rainfall": hourly["precipitation"][h_i],
                            "wind_speed": hourly["wind_speed_10m"][h_i]
                        })
        elif period_norm == "next_3_days":
            filtered_days = days[:3]
        elif period_norm == "weekend":
            weekend_days = []
            for d in days:
                try:
                    dt = datetime.fromisoformat(d["date"])
                    if dt.weekday() in (5, 6):  # Saturday (5) or Sunday (6)
                        weekend_days.append(d)
                except Exception:
                    pass
            filtered_days = weekend_days if weekend_days else days[:2]
        elif period_norm == "hourly":
            if hourly and "time" in hourly:
                for h_i in range(min(24, len(hourly["time"]))):
                    hourly_filtered.append({
                        "time": hourly["time"][h_i],
                        "temperature": hourly["temperature_2m"][h_i],
                        "rain_probability": hourly["precipitation_probability"][h_i],
                        "rainfall": hourly["precipitation"][h_i],
                        "wind_speed": hourly["wind_speed_10m"][h_i]
                    })
        else:
            period_norm = "next_7_days"
            filtered_days = days[:7]

        result = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_period": period_norm,
            "forecast": filtered_days,
            "source": self.name
        }
        if hourly_filtered:
            result["hourly_forecast"] = hourly_filtered

        return result

    def get_alerts(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Evaluate real weather forecast data to generate condition-based advisories.
        Transparently tags alerts as derived from Open-Meteo, distinct from official IMD warnings.
        """
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m,wind_speed_10m"
            "&daily=precipitation_probability_max,precipitation_sum,temperature_2m_max"
            "&forecast_days=1"
            "&timezone=auto"
        )
        try:
            weather_response = requests.get(weather_url, timeout=10)
        except requests.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Open-Meteo service unreachable: {str(e)}"
            )

        if weather_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Open-Meteo error (HTTP {weather_response.status_code}): Weather service is not available"
            )

        weather_data = weather_response.json()
        current = weather_data.get("current", {})
        daily = weather_data.get("daily", {})
        alerts = []

        temperature = current.get("temperature_2m", 0)
        if temperature >= 40:
            alerts.append({
                "type": "Extreme Heat",
                "severity": "High",
                "message": "Extreme heat conditions are currently present. (Automated advisory derived from Open-Meteo forecast data; not an official IMD government warning)."
            })
        elif temperature >= 35:
            alerts.append({
                "type": "Heat",
                "severity": "Moderate",
                "message": "High temperature detected. Stay hydrated and avoid prolonged exposure to heat. (Automated advisory derived from Open-Meteo forecast data; not an official IMD government warning)."
            })

        wind_speed = current.get("wind_speed_10m", 0)
        if wind_speed >= 60:
            alerts.append({
                "type": "Strong Wind",
                "severity": "High",
                "message": "Very strong winds are currently present. Avoid unnecessary outdoor travel. (Automated advisory derived from Open-Meteo forecast data; not an official IMD government warning)."
            })
        elif wind_speed >= 40:
            alerts.append({
                "type": "Strong Wind",
                "severity": "Moderate",
                "message": "Strong winds are expected. Take caution outdoors. (Automated advisory derived from Open-Meteo forecast data; not an official IMD government warning)."
            })

        rain_probability = daily.get("precipitation_probability_max", [0])[0] if daily.get("precipitation_probability_max") else 0
        rainfall = daily.get("precipitation_sum", [0])[0] if daily.get("precipitation_sum") else 0

        if rain_probability >= 80 and rainfall >= 20:
            alerts.append({
                "type": "Heavy Rain",
                "severity": "High",
                "message": "Heavy rainfall is possible. Be cautious in low-lying areas. (Automated advisory derived from Open-Meteo forecast data; not an official IMD government warning)."
            })
        elif rain_probability >= 70:
            alerts.append({
                "type": "Rain",
                "severity": "Moderate",
                "message": "There is a high probability of rainfall. (Automated advisory derived from Open-Meteo forecast data; not an official IMD government warning)."
            })

        if len(alerts) == 0:
            alerts.append({
                "type": "No Major Alert",
                "severity": "Low",
                "message": "No major weather risk detected from the available Open-Meteo forecast data."
            })

        return {
            "latitude": latitude,
            "longitude": longitude,
            "alerts": alerts,
            "source": f"{self.name} (Derived Advisory)"
        }
