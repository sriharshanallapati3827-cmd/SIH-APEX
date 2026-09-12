"""
Test Suite: Sub-Phase 5.2 — Forecast-Aware Recommendations

Focus:
1. Multi-day forecast aggregation across periods (next_3_days, weekend, next_7_days, this_week).
2. Umbrella recommendations across multiple days:
   - Recommends umbrella if rain is expected on any day during the forecast period.
   - Recommends 'not_needed' only when all days have low rain.
   - Returns 'uncertain' when shower chances are moderate during the period.
3. Heat recommendations across multiple days:
   - 'high_heat' if any day exceeds 40°C.
   - 'caution' if any day exceeds 35°C.
   - 'normal' if all days remain comfortable.
4. Wind recommendations across multiple days:
   - 'strong_wind' if any day exceeds 40 km/h.
   - 'windy' if any day exceeds 25 km/h.
   - 'normal' if calm throughout.
5. Outdoor activity aggregation:
   - Unfavorable if any period day is poor (rain, high heat, strong wind).
   - Caution if any period day has moderate conditions.
   - Favorable if all period days are benign.
6. Travel weather suitability aggregation:
   - Unfavorable for severe weather on any day.
   - Caution for showers or breezy winds.
   - Favorable for clear travel conditions across the period.
7. Specific day targeting in multi-day lists (e.g. tomorrow selects index 1).
8. /ask integration for period-aware queries.
"""

import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.recommendation_service import (
    extract_context_metrics,
    get_umbrella_recommendation,
    get_heat_recommendation,
    get_wind_recommendation,
    get_outdoor_recommendation,
    get_travel_recommendation,
    determine_recommendation_type,
    generate_recommendation,
)
from fastapi.testclient import TestClient
from main import app


class TestForecastPeriodUmbrella(unittest.TestCase):
    """Test forecast-aware umbrella recommendations across multi-day periods."""

    def test_umbrella_recommended_when_rain_on_day_2_of_3_day_forecast(self):
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "rain_probability": 5, "rainfall": 0.0},
                    {"date": "2026-09-13", "rain_probability": 80, "rainfall": 4.5},
                    {"date": "2026-09-14", "rain_probability": 10, "rainfall": 0.0},
                ]
            }
        }
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "recommended")
        self.assertIn("during this period", rec["reason"])
        self.assertIn("80% chance of rain", rec["reason"])

    def test_umbrella_not_needed_when_all_days_have_low_rain(self):
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "rain_probability": 5, "rainfall": 0.0},
                    {"date": "2026-09-13", "rain_probability": 10, "rainfall": 0.0},
                    {"date": "2026-09-14", "rain_probability": 0, "rainfall": 0.0},
                ]
            }
        }
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "not_needed")
        self.assertIn("across the period", rec["reason"])

    def test_umbrella_uncertain_when_moderate_rain_probability_during_period(self):
        ctx = {
            "time_period": "weekend",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "rain_probability": 15, "rainfall": 0.0},
                    {"date": "2026-09-13", "rain_probability": 40, "rainfall": 0.5},
                ]
            }
        }
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "uncertain")

    def test_umbrella_targets_tomorrow_specifically_in_multi_day_list(self):
        # Day 0 (today): 90% rain. Day 1 (tomorrow): 5% rain.
        ctx = {
            "time_period": "tomorrow",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "rain_probability": 90, "rainfall": 12.0},
                    {"date": "2026-09-13", "rain_probability": 5, "rainfall": 0.0},
                ]
            }
        }
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "not_needed")


class TestForecastPeriodHeat(unittest.TestCase):
    """Test forecast-aware heat recommendations across multi-day periods."""

    def test_high_heat_detected_on_any_day_in_period(self):
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 32.0},
                    {"date": "2026-09-13", "max_temperature": 41.5},
                    {"date": "2026-09-14", "max_temperature": 33.0},
                ]
            }
        }
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "high_heat")
        self.assertIn("during this period", rec["reason"])
        self.assertIn("41.5", rec["reason"])

    def test_heat_caution_when_moderate_peak_in_period(self):
        ctx = {
            "time_period": "weekend",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 31.0},
                    {"date": "2026-09-13", "max_temperature": 36.5},
                ]
            }
        }
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "caution")
        self.assertIn("during this period", rec["reason"])

    def test_heat_normal_when_all_days_mild(self):
        ctx = {
            "time_period": "next_7_days",
            "weather_data": {
                "forecast": [
                    {"date": f"2026-09-{12+i}", "max_temperature": 28.0 + (i * 0.5)}
                    for i in range(7)
                ]
            }
        }
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "normal")
        self.assertIn("across the period", rec["reason"])


class TestForecastPeriodWind(unittest.TestCase):
    """Test forecast-aware wind recommendations across multi-day periods."""

    def test_strong_wind_detected_in_period(self):
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_wind_speed": 15.0},
                    {"date": "2026-09-13", "max_wind_speed": 46.0},
                    {"date": "2026-09-14", "max_wind_speed": 18.0},
                ]
            }
        }
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "strong_wind")
        self.assertIn("during this period", rec["reason"])

    def test_windy_detected_in_period(self):
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_wind_speed": 12.0},
                    {"date": "2026-09-13", "max_wind_speed": 28.0},
                    {"date": "2026-09-14", "max_wind_speed": 15.0},
                ]
            }
        }
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "windy")

    def test_wind_normal_across_period(self):
        ctx = {
            "time_period": "weekend",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_wind_speed": 10.0},
                    {"date": "2026-09-13", "max_wind_speed": 14.0},
                ]
            }
        }
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "normal")


class TestForecastPeriodOutdoor(unittest.TestCase):
    """Test forecast-aware outdoor suitability aggregation across periods."""

    def test_outdoor_unfavorable_when_one_day_has_rain_in_3_day_forecast(self):
        # Day 1: sunny/favorable. Day 2: heavy rain. Day 3: sunny.
        # Should not blindly report favorable.
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 25.0, "rain_probability": 0, "rainfall": 0.0, "max_wind_speed": 10.0},
                    {"date": "2026-09-13", "max_temperature": 24.0, "rain_probability": 85, "rainfall": 8.0, "max_wind_speed": 15.0},
                    {"date": "2026-09-14", "max_temperature": 26.0, "rain_probability": 5, "rainfall": 0.0, "max_wind_speed": 10.0},
                ]
            }
        }
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["type"], "outdoor")
        self.assertEqual(rec["status"], "unfavorable")
        self.assertIn("rain expected", rec["reason"])
        self.assertIn("during this period", rec["reason"])

    def test_outdoor_caution_when_moderate_heat_or_showers(self):
        ctx = {
            "time_period": "weekend",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 25.0, "rain_probability": 5, "rainfall": 0.0, "max_wind_speed": 10.0},
                    {"date": "2026-09-13", "max_temperature": 36.0, "rain_probability": 10, "rainfall": 0.0, "max_wind_speed": 12.0},
                ]
            }
        }
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["type"], "outdoor")
        self.assertEqual(rec["status"], "caution")
        self.assertIn("warm temperatures", rec["reason"])

    def test_outdoor_favorable_when_all_days_clear(self):
        ctx = {
            "time_period": "weekend",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 26.0, "rain_probability": 0, "rainfall": 0.0, "max_wind_speed": 10.0},
                    {"date": "2026-09-13", "max_temperature": 27.0, "rain_probability": 5, "rainfall": 0.0, "max_wind_speed": 12.0},
                ]
            }
        }
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["type"], "outdoor")
        self.assertEqual(rec["status"], "favorable")


class TestForecastPeriodTravel(unittest.TestCase):
    """Test forecast-aware travel suitability aggregation."""

    def test_travel_unfavorable_when_severe_weather_in_period(self):
        ctx = {
            "time_period": "next_3_days",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 28.0, "rain_probability": 10, "rainfall": 0.0, "max_wind_speed": 15.0},
                    {"date": "2026-09-13", "max_temperature": 24.0, "rain_probability": 95, "rainfall": 28.0, "max_wind_speed": 55.0},
                    {"date": "2026-09-14", "max_temperature": 26.0, "rain_probability": 20, "rainfall": 0.0, "max_wind_speed": 20.0},
                ]
            }
        }
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["type"], "travel")
        self.assertEqual(rec["status"], "unfavorable")
        self.assertIn("heavy rain", rec["reason"])

    def test_travel_caution_when_moderate_showers_or_winds(self):
        ctx = {
            "time_period": "weekend",
            "weather_data": {
                "forecast": [
                    {"date": "2026-09-12", "max_temperature": 28.0, "rain_probability": 10, "rainfall": 0.0, "max_wind_speed": 15.0},
                    {"date": "2026-09-13", "max_temperature": 26.0, "rain_probability": 65, "rainfall": 3.0, "max_wind_speed": 28.0},
                ]
            }
        }
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["type"], "travel")
        self.assertEqual(rec["status"], "caution")

    def test_travel_favorable_when_clear_across_period(self):
        ctx = {
            "time_period": "this_week",
            "weather_data": {
                "forecast": [
                    {"date": f"2026-09-{12+i}", "max_temperature": 28.0, "rain_probability": 5, "rainfall": 0.0, "max_wind_speed": 12.0}
                    for i in range(5)
                ]
            }
        }
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["type"], "travel")
        self.assertEqual(rec["status"], "favorable")


class TestAskEndpointForecastAwareIntegration(unittest.TestCase):
    """Test /ask endpoint for forecast-aware recommendation questions."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_ask_umbrella_weekend_includes_forecast_recommendation(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "rain",
            "location": "Mumbai",
            "city": "Mumbai",
            "time_period": "weekend",
            "weather_variable": "precipitation",
            "requires_location": False,
        })
        mock_context.return_value = {
            "status": "success",
            "intent": "rain",
            "location": "Mumbai",
            "time_period": "weekend",
            "weather_variable": "precipitation",
            "weather_data": {
                "city": "Mumbai",
                "forecast_period": "weekend",
                "forecast": [
                    {"date": "2026-09-12", "rain_probability": 10, "rainfall": 0.0, "max_temperature": 30.0},
                    {"date": "2026-09-13", "rain_probability": 85, "rainfall": 15.0, "max_temperature": 28.0},
                ],
                "source": "open_meteo",
            },
            "source": "open_meteo",
        }
        mock_answer.return_value = "Rain is expected in Mumbai on Sunday during the weekend. Carry an umbrella!"

        resp = self.client.post("/ask", json={"message": "Will I need an umbrella this weekend in Mumbai?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("recommendation", data)
        rec = data["recommendation"]
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "recommended")
        self.assertIn("during this period", rec["reason"])

        # Check grounding in context
        called_context = mock_answer.call_args[0][1]
        self.assertIn("recommendation", called_context)
        self.assertEqual(called_context["recommendation"]["status"], "recommended")


if __name__ == "__main__":
    unittest.main(verbosity=2)
