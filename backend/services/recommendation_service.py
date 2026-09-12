"""
Recommendation Service — Sub-Phase 5.1 & 5.2
Deterministic, grounded weather recommendations derived strictly from retrieved weather context.
Supports both single-snapshot and multi-day / period-aware forecast evaluations.

Categories supported:
  - umbrella (recommended, not_needed, uncertain, insufficient_data)
  - heat (normal, caution, high_heat, insufficient_data)
  - wind (normal, windy, strong_wind, insufficient_data)
  - outdoor (favorable, caution, unfavorable, insufficient_data)
  - travel (favorable, caution, unfavorable, insufficient_data)

Rules are conservative, deterministic, and fail-safe (return insufficient_data if required data is missing).
No imaginary weather values, no medical claims, no unsupported travel/traffic claims.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime


def extract_context_metrics(weather_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract numeric weather metrics from any weather_context dictionary.
    Handles:
      - scalar current weather / single-day weather
      - multi-day daily forecasts (next_3_days, weekend, next_7_days, this_week, etc.)
      - specific forecast targets (tomorrow, today)
      - precipitation lists, temperature lists, wind lists
      - alert payloads
    """
    metrics: Dict[str, Any] = {
        "temperature": None,
        "apparent_temperature": None,
        "rain_probability": None,
        "rainfall_mm": None,
        "wind_speed_kmh": None,
        "has_temp_data": False,
        "has_rain_data": False,
        "has_wind_data": False,
        "alerts": [],
        "period": None,
        "days_count": 0,
        "daily_breakdown": [],
    }

    if not isinstance(weather_context, dict):
        return metrics

    raw_data = weather_context.get("weather_data")
    if not isinstance(raw_data, dict):
        return metrics

    period = weather_context.get("time_period") or raw_data.get("forecast_period")
    if period:
        period = str(period).strip().lower()
    metrics["period"] = period

    # Extract alerts if any
    alerts_list = raw_data.get("alerts")
    if isinstance(alerts_list, list):
        metrics["alerts"] = alerts_list

    # Collect daily records from any list in raw_data
    records: List[Dict[str, Any]] = []

    # Source 1: forecast array
    forecast_list = raw_data.get("forecast")
    if isinstance(forecast_list, list) and forecast_list:
        for f in forecast_list:
            if isinstance(f, dict):
                records.append({
                    "date": f.get("date"),
                    "temperature": float(f["max_temperature"]) if f.get("max_temperature") is not None else None,
                    "min_temperature": float(f["min_temperature"]) if f.get("min_temperature") is not None else None,
                    "apparent_temperature": float(f["apparent_temperature"]) if f.get("apparent_temperature") is not None else None,
                    "rain_probability": int(f["rain_probability"]) if f.get("rain_probability") is not None else None,
                    "rainfall_mm": float(f["rainfall"]) if f.get("rainfall") is not None else None,
                    "wind_speed_kmh": float(f["max_wind_speed"]) if f.get("max_wind_speed") is not None else None,
                })

    # Source 2: precipitation_data array
    precip_list = raw_data.get("precipitation_data")
    if isinstance(precip_list, list) and precip_list and not records:
        for p in precip_list:
            if isinstance(p, dict):
                rain_val = p.get("rainfall_mm") if p.get("rainfall_mm") is not None else p.get("rainfall")
                records.append({
                    "date": p.get("date"),
                    "temperature": float(p["max_temperature"]) if p.get("max_temperature") is not None else None,
                    "min_temperature": None,
                    "apparent_temperature": None,
                    "rain_probability": int(p["rain_probability"]) if p.get("rain_probability") is not None else None,
                    "rainfall_mm": float(rain_val) if rain_val is not None else None,
                    "wind_speed_kmh": None,
                })

    # Source 3: temperatures array
    temps_list = raw_data.get("temperatures")
    if isinstance(temps_list, list) and temps_list and not records:
        for t in temps_list:
            if isinstance(t, dict):
                records.append({
                    "date": t.get("date"),
                    "temperature": float(t["max_temperature"]) if t.get("max_temperature") is not None else None,
                    "min_temperature": float(t["min_temperature"]) if t.get("min_temperature") is not None else None,
                    "apparent_temperature": None,
                    "rain_probability": None,
                    "rainfall_mm": None,
                    "wind_speed_kmh": None,
                })

    # Source 4: wind_data array
    wind_list = raw_data.get("wind_data")
    if isinstance(wind_list, list) and wind_list and not records:
        for w in wind_list:
            if isinstance(w, dict):
                records.append({
                    "date": w.get("date"),
                    "temperature": None,
                    "min_temperature": None,
                    "apparent_temperature": None,
                    "rain_probability": None,
                    "rainfall_mm": None,
                    "wind_speed_kmh": float(w["max_wind_speed"]) if w.get("max_wind_speed") is not None else None,
                })

    # Period-specific filtering when multiple records exist
    selected_records = records
    if records:
        if period == "tomorrow" and len(records) > 1:
            selected_records = [records[1]]
        elif period == "today" and len(records) > 1:
            selected_records = [records[0]]
        elif period == "next_3_days" and len(records) > 3:
            selected_records = records[:3]
        elif period == "weekend" and len(records) > 2:
            wk_records = []
            for r in records:
                d_str = r.get("date")
                if d_str:
                    try:
                        dt = datetime.fromisoformat(str(d_str))
                        if dt.weekday() in (5, 6):
                            wk_records.append(r)
                    except Exception:
                        pass
            if wk_records:
                selected_records = wk_records
            else:
                selected_records = records[:2]

    # Aggregate across selected_records if available
    if selected_records:
        metrics["daily_breakdown"] = selected_records
        metrics["days_count"] = len(selected_records)

        temps = [r["temperature"] for r in selected_records if r["temperature"] is not None]
        app_temps = [r["apparent_temperature"] for r in selected_records if r["apparent_temperature"] is not None]
        probs = [r["rain_probability"] for r in selected_records if r["rain_probability"] is not None]
        rains = [r["rainfall_mm"] for r in selected_records if r["rainfall_mm"] is not None]
        winds = [r["wind_speed_kmh"] for r in selected_records if r["wind_speed_kmh"] is not None]

        if temps:
            metrics["temperature"] = max(temps)
            metrics["has_temp_data"] = True
        if app_temps:
            metrics["apparent_temperature"] = max(app_temps)
            metrics["has_temp_data"] = True
        if probs:
            metrics["rain_probability"] = max(probs)
            metrics["has_rain_data"] = True
        if rains:
            metrics["rainfall_mm"] = max(rains)
            metrics["has_rain_data"] = True
        if winds:
            metrics["wind_speed_kmh"] = max(winds)
            metrics["has_wind_data"] = True

    # 1. Check direct scalar fields (from current weather or single-variable query)
    if "temperature" in raw_data and raw_data["temperature"] is not None:
        metrics["temperature"] = float(raw_data["temperature"])
        metrics["has_temp_data"] = True

    if "apparent_temperature" in raw_data and raw_data["apparent_temperature"] is not None:
        metrics["apparent_temperature"] = float(raw_data["apparent_temperature"])
        metrics["has_temp_data"] = True

    if "wind_speed" in raw_data and raw_data["wind_speed"] is not None:
        metrics["wind_speed_kmh"] = float(raw_data["wind_speed"])
        metrics["has_wind_data"] = True

    if "precipitation" in raw_data and raw_data["precipitation"] is not None:
        metrics["rainfall_mm"] = float(raw_data["precipitation"])
        metrics["has_rain_data"] = True

    if "rain" in raw_data and raw_data["rain"] is not None:
        rain_val = float(raw_data["rain"])
        if rain_val > 0:
            metrics["rainfall_mm"] = rain_val
            metrics["has_rain_data"] = True

    return metrics


def get_umbrella_recommendation(weather_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic umbrella recommendation:
      - recommended: rain_probability >= 50% or rainfall >= 1.0mm
      - not_needed: rain_probability < 20% and (rainfall == 0 or None)
      - uncertain: rain_probability 20%..49%
      - insufficient_data: no rain/precipitation metrics available
    Forecast-aware: reasons across the requested forecast period (e.g. 3-day, weekend, 7-day).
    """
    m = extract_context_metrics(weather_context)
    if not m["has_rain_data"] and m["rain_probability"] is None and m["rainfall_mm"] is None:
        return {
            "type": "umbrella",
            "status": "insufficient_data",
            "reason": "No precipitation or rainfall data is available in the weather context.",
        }

    prob = m["rain_probability"]
    rain = m["rainfall_mm"]
    days = m.get("days_count", 0)

    if (prob is not None and prob >= 50) or (rain is not None and rain >= 1.0):
        details = []
        if prob is not None:
            details.append(f"{prob}% chance of rain")
        if rain is not None and rain > 0:
            details.append(f"{rain} mm precipitation")
        detail_str = f" ({', '.join(details)})" if details else ""
        period_phrase = f"during this period{detail_str}" if days > 1 else f"likely{detail_str}"
        return {
            "type": "umbrella",
            "status": "recommended",
            "reason": f"Rain is {period_phrase}. Carrying an umbrella is recommended.",
        }

    if (prob is not None and prob < 20) and (rain is None or rain == 0.0):
        detail_str = f" ({prob}% rain chance)" if prob is not None else ""
        if days > 1:
            reason = f"Low likelihood of precipitation across the period{detail_str}. An umbrella is not needed."
        else:
            reason = f"Low likelihood of precipitation{detail_str}. An umbrella is not needed."
        return {
            "type": "umbrella",
            "status": "not_needed",
            "reason": reason,
        }

    detail_str = f" ({prob}% rain chance)" if prob is not None else ""
    return {
        "type": "umbrella",
        "status": "uncertain",
        "reason": f"Scattered or moderate chance of showers{detail_str}. Carrying an umbrella is advised as a precaution.",
    }


def get_heat_recommendation(weather_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic heat precaution recommendation:
      - high_heat: temperature or apparent_temperature >= 40°C
      - caution: temperature or apparent_temperature >= 35°C
      - normal: temperature < 35°C
      - insufficient_data: no temperature metrics available
    Forecast-aware: evaluates peak and daily temperatures across the forecast period.
    """
    m = extract_context_metrics(weather_context)
    if not m["has_temp_data"] and m["temperature"] is None and m["apparent_temperature"] is None:
        return {
            "type": "heat",
            "status": "insufficient_data",
            "reason": "No temperature data is available in the weather context.",
        }

    eff_temp = m["apparent_temperature"] if m["apparent_temperature"] is not None else m["temperature"]
    days = m.get("days_count", 0)

    if eff_temp >= 40.0:
        if days > 1:
            reason = f"High temperatures expected during this period (highs up to {eff_temp}°C). Stay hydrated and minimize direct sun exposure."
        else:
            reason = f"High temperatures expected ({eff_temp}°C). Stay hydrated and minimize direct sun exposure."
        return {
            "type": "heat",
            "status": "high_heat",
            "reason": reason,
        }

    if eff_temp >= 35.0:
        if days > 1:
            reason = f"Warm conditions expected during this period (highs up to {eff_temp}°C). Take regular hydration breaks if outdoors."
        else:
            reason = f"Warm weather conditions ({eff_temp}°C). Take regular hydration breaks if outdoors."
        return {
            "type": "heat",
            "status": "caution",
            "reason": reason,
        }

    if days > 1:
        reason = f"Temperatures are expected to remain in a comfortable range across the period (highs around {eff_temp}°C)."
    else:
        reason = f"Temperatures are in a comfortable range ({eff_temp}°C)."
    return {
        "type": "heat",
        "status": "normal",
        "reason": reason,
    }


def get_wind_recommendation(weather_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic wind precaution recommendation:
      - strong_wind: wind_speed >= 40 km/h
      - windy: wind_speed >= 25 km/h
      - normal: wind_speed < 25 km/h
      - insufficient_data: no wind metrics available
    Forecast-aware: evaluates peak wind speeds across the forecast period.
    """
    m = extract_context_metrics(weather_context)
    if not m["has_wind_data"] and m["wind_speed_kmh"] is None:
        return {
            "type": "wind",
            "status": "insufficient_data",
            "reason": "No wind speed data is available in the weather context.",
        }

    speed = m["wind_speed_kmh"]
    days = m.get("days_count", 0)

    if speed >= 40.0:
        if days > 1:
            reason = f"Strong winds expected during this period (winds up to {speed} km/h). Secure loose outdoor objects and exercise care outside."
        else:
            reason = f"Strong winds expected ({speed} km/h). Secure loose outdoor objects and exercise care outside."
        return {
            "type": "wind",
            "status": "strong_wind",
            "reason": reason,
        }

    if speed >= 25.0:
        if days > 1:
            reason = f"Moderately windy conditions expected during this period (winds up to {speed} km/h)."
        else:
            reason = f"Moderately windy conditions ({speed} km/h)."
        return {
            "type": "wind",
            "status": "windy",
            "reason": reason,
        }

    return {
        "type": "wind",
        "status": "normal",
        "reason": f"Gentle to moderate wind ({speed} km/h).",
    }


def get_outdoor_recommendation(weather_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic outdoor activity suitability:
      - unfavorable: rain recommended, high_heat, or strong_wind
      - caution: rain uncertain, heat caution, or windy
      - favorable: all available metrics are normal
      - insufficient_data: no weather metrics available
    Forecast-aware: aggregates across the requested period using deterministic rules.
    If any day has unfavorable conditions, reports unfavorable with the contributing factors.
    """
    m = extract_context_metrics(weather_context)
    if not m["has_temp_data"] and not m["has_rain_data"] and not m["has_wind_data"]:
        return {
            "type": "outdoor",
            "status": "insufficient_data",
            "reason": "Insufficient weather metrics to determine outdoor suitability.",
        }

    days_records = m.get("daily_breakdown", [])
    if len(days_records) > 1:
        # Multi-day forecast aggregation
        has_unfavorable = False
        has_caution = False
        factors = []

        for r in days_records:
            r_prob = r.get("rain_probability")
            r_rain = r.get("rainfall_mm")
            r_temp = r.get("temperature")
            r_wind = r.get("wind_speed_kmh")

            if (r_prob is not None and r_prob >= 50) or (r_rain is not None and r_rain >= 1.0):
                has_unfavorable = True
                if "rain expected" not in factors:
                    factors.append("rain expected")
            elif r_prob is not None and 20 <= r_prob < 50:
                has_caution = True
                if "chance of showers" not in factors:
                    factors.append("chance of showers")

            if r_temp is not None and r_temp >= 40.0:
                has_unfavorable = True
                if "extreme heat" not in factors:
                    factors.append("extreme heat")
            elif r_temp is not None and r_temp >= 35.0:
                has_caution = True
                if "warm temperatures" not in factors:
                    factors.append("warm temperatures")

            if r_wind is not None and r_wind >= 40.0:
                has_unfavorable = True
                if "high winds" not in factors:
                    factors.append("high winds")
            elif r_wind is not None and r_wind >= 25.0:
                has_caution = True
                if "breezy winds" not in factors:
                    factors.append("breezy winds")

        if has_unfavorable:
            return {
                "type": "outdoor",
                "status": "unfavorable",
                "reason": f"Weather conditions ({', '.join(factors)}) are unfavorable for outdoor activities during this period.",
            }
        if has_caution:
            return {
                "type": "outdoor",
                "status": "caution",
                "reason": f"Outdoor activities may proceed with caution during this period ({', '.join(factors)}).",
            }
        return {
            "type": "outdoor",
            "status": "favorable",
            "reason": "Weather conditions are generally favorable for outdoor activities throughout the period.",
        }

    # Single-day / snapshot logic
    u = get_umbrella_recommendation(weather_context)
    h = get_heat_recommendation(weather_context)
    w = get_wind_recommendation(weather_context)

    if u["status"] == "recommended" or h["status"] == "high_heat" or w["status"] == "strong_wind":
        factors = []
        if u["status"] == "recommended":
            factors.append("rain expected")
        if h["status"] == "high_heat":
            factors.append("extreme heat")
        if w["status"] == "strong_wind":
            factors.append("high winds")
        return {
            "type": "outdoor",
            "status": "unfavorable",
            "reason": f"Weather conditions ({', '.join(factors)}) are unfavorable for outdoor activities.",
        }

    if u["status"] == "uncertain" or h["status"] == "caution" or w["status"] == "windy":
        factors = []
        if u["status"] == "uncertain":
            factors.append("chance of showers")
        if h["status"] == "caution":
            factors.append("warm temperatures")
        if w["status"] == "windy":
            factors.append("breezy winds")
        return {
            "type": "outdoor",
            "status": "caution",
            "reason": f"Outdoor activities may proceed with caution ({', '.join(factors)}).",
        }

    return {
        "type": "outdoor",
        "status": "favorable",
        "reason": "Weather conditions are generally favorable for outdoor activities.",
    }


def get_travel_recommendation(weather_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic travel weather suitability:
      - unfavorable: severe weather (heavy rainfall >= 20mm or winds >= 50 km/h)
      - caution: adverse weather (rain recommended or windy >= 25km/h or high_heat >= 38°C)
      - favorable: benign weather conditions
      - insufficient_data: no metrics available
    Forecast-aware: evaluates weather across the entire requested forecast travel period.
    Does NOT claim road safety, accident probability, or official government alerts.
    """
    m = extract_context_metrics(weather_context)
    if not m["has_temp_data"] and not m["has_rain_data"] and not m["has_wind_data"]:
        return {
            "type": "travel",
            "status": "insufficient_data",
            "reason": "Insufficient weather data to evaluate travel weather suitability.",
        }

    days_records = m.get("daily_breakdown", [])
    if len(days_records) > 1:
        has_unfavorable = False
        has_caution = False
        factors = []

        for r in days_records:
            prob = r.get("rain_probability") or 0
            rain = r.get("rainfall_mm") or 0.0
            wind = r.get("wind_speed_kmh") or 0.0
            temp = r.get("temperature")

            if (rain >= 20.0 and prob >= 70) or wind >= 50.0:
                has_unfavorable = True
                if rain >= 20.0 and "heavy rain" not in factors:
                    factors.append(f"heavy rain ({rain} mm)")
                if wind >= 50.0 and "high winds" not in factors:
                    factors.append(f"high winds ({wind} km/h)")
            elif prob >= 50 or rain >= 1.0 or wind >= 25.0 or (temp and temp >= 38.0):
                has_caution = True
                if (prob >= 50 or rain >= 1.0) and "showers likely" not in factors:
                    factors.append("showers likely")
                if wind >= 25.0 and "breezy winds" not in factors:
                    factors.append("breezy winds")
                if temp and temp >= 38.0 and "elevated heat" not in factors:
                    factors.append("elevated heat")

        if has_unfavorable:
            return {
                "type": "travel",
                "status": "unfavorable",
                "reason": f"Adverse weather detected ({', '.join(factors)}). Allow extra time or delay non-essential travel.",
            }
        if has_caution:
            return {
                "type": "travel",
                "status": "caution",
                "reason": f"Weather conditions suggest taking standard travel precautions during this period ({', '.join(factors)}).",
            }
        return {
            "type": "travel",
            "status": "favorable",
            "reason": "Weather conditions are expected to be generally clear and favorable for travel across the period.",
        }

    # Single-day / snapshot logic
    prob = m["rain_probability"] or 0
    rain = m["rainfall_mm"] or 0.0
    wind = m["wind_speed_kmh"] or 0.0

    if (rain >= 20.0 and prob >= 70) or wind >= 50.0:
        factors = []
        if rain >= 20.0:
            factors.append(f"heavy rain ({rain} mm)")
        if wind >= 50.0:
            factors.append(f"high winds ({wind} km/h)")
        return {
            "type": "travel",
            "status": "unfavorable",
            "reason": f"Adverse weather detected ({', '.join(factors)}). Allow extra time or delay non-essential travel.",
        }

    if prob >= 50 or rain >= 1.0 or wind >= 25.0 or (m["temperature"] and m["temperature"] >= 38.0):
        factors = []
        if prob >= 50 or rain >= 1.0:
            factors.append("showers likely")
        if wind >= 25.0:
            factors.append("breezy winds")
        if m["temperature"] and m["temperature"] >= 38.0:
            factors.append("elevated heat")
        return {
            "type": "travel",
            "status": "caution",
            "reason": f"Weather conditions suggest taking standard travel precautions ({', '.join(factors)}).",
        }

    return {
        "type": "travel",
        "status": "favorable",
        "reason": "Weather conditions are expected to be generally clear and favorable for travel.",
    }


def determine_recommendation_type(
    query: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None
) -> Optional[str]:
    """
    Deterministically map query parameters and message keywords to a recommendation category.
    Returns one of: 'umbrella', 'heat', 'wind', 'outdoor', 'travel', or None.
    """
    msg = (message or "").lower()

    # Keyword mappings on the raw message take highest priority
    if any(k in msg for k in ["umbrella", "raincoat", "poncho"]):
        return "umbrella"
    if any(k in msg for k in ["hot", "heat", "temperature", "sunstroke", "heatwave"]):
        return "heat"
    if any(k in msg for k in ["wind", "windy", "breeze", "gale"]):
        return "wind"
    if any(k in msg for k in ["travel", "drive", "driving", "flight", "commute", "road trip", "journey"]):
        return "travel"
    if any(k in msg for k in ["outdoor", "outside", "walk", "picnic", "run", "sports", "match", "play"]):
        return "outdoor"

    if isinstance(query, dict):
        intent = query.get("intent", "")
        variable = query.get("weather_variable", "")

        if intent == "travel_advisory":
            return "travel"
        if intent in ("advisory", "farmer_advisory"):
            if variable == "precipitation":
                return "umbrella"
            if variable == "temperature":
                return "heat"
            if variable == "wind":
                return "wind"
            return "outdoor"
        if intent == "rain" and "umbrella" in msg:
            return "umbrella"

    return None


def generate_recommendation(
    weather_context: Dict[str, Any],
    recommendation_type: Optional[str] = None,
    query: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate a deterministic weather recommendation.
    If recommendation_type is not provided, it is inferred from query/message.
    """
    rec_type = recommendation_type or determine_recommendation_type(query=query, message=message)
    if not rec_type:
        return None

    rec_type = rec_type.lower()
    if rec_type == "umbrella":
        return get_umbrella_recommendation(weather_context)
    if rec_type == "heat":
        return get_heat_recommendation(weather_context)
    if rec_type == "wind":
        return get_wind_recommendation(weather_context)
    if rec_type == "outdoor":
        return get_outdoor_recommendation(weather_context)
    if rec_type == "travel":
        return get_travel_recommendation(weather_context)

    return None
