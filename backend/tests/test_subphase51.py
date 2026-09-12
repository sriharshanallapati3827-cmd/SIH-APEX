"""
Test Suite: Sub-Phase 5.1 — Advanced Weather Intelligence: Recommendations & Advisory Logic

Tests:
1. extract_context_metrics: scalar weather data, precipitation lists, forecast lists, temperatures, wind.
2. Umbrella Recommendation:
   - recommended (rain_prob >= 50% or rain >= 1.0mm)
   - not_needed (rain_prob < 20% and no rain)
   - uncertain (20% <= rain_prob < 50%)
   - insufficient_data (missing rain info)
3. Heat Recommendation:
   - high_heat (>= 40°C)
   - caution (>= 35°C)
   - normal (< 35°C)
   - insufficient_data (missing temp info)
4. Wind Recommendation:
   - strong_wind (>= 40 km/h)
   - windy (>= 25 km/h)
   - normal (< 25 km/h)
   - insufficient_data (missing wind info)
5. Outdoor Recommendation:
   - unfavorable (rain recommended / high heat / strong wind)
   - caution (uncertain rain / heat caution / breezy)
   - favorable (normal conditions)
   - insufficient_data (no metrics)
6. Travel Recommendation:
   - unfavorable (severe weather: rain >= 20mm or wind >= 50 km/h)
   - caution (rain likely or wind >= 25 km/h or elevated heat)
   - favorable (clear/mild)
   - insufficient_data (no metrics)
7. determine_recommendation_type:
   - keyword matching from messages (umbrella, heat, wind, outdoor, travel)
   - query intent/variable mapping
8. generate_recommendation:
   - complete payload validation (type, status, reason)
   - return None when not applicable
9. /ask Integration:
   - recommendation field returned in response for advisory/umbrella query
   - backwards compatibility: all 8 standard keys present
   - recommendation embedded in context passed to final answer generation
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


class TestExtractContextMetrics(unittest.TestCase):
    """Test extracting metrics safely from various context formats."""

    def test_empty_or_invalid_context(self):
        m = extract_context_metrics({})
        self.assertFalse(m["has_temp_data"])
        self.assertFalse(m["has_rain_data"])
        self.assertFalse(m["has_wind_data"])
        self.assertIsNone(m["temperature"])

    def test_scalar_current_weather(self):
        ctx = {
            "weather_data": {
                "temperature": 32.5,
                "apparent_temperature": 36.0,
                "wind_speed": 18.2,
                "precipitation": 0.0,
            }
        }
        m = extract_context_metrics(ctx)
        self.assertEqual(m["temperature"], 32.5)
        self.assertEqual(m["apparent_temperature"], 36.0)
        self.assertEqual(m["wind_speed_kmh"], 18.2)
        self.assertEqual(m["rainfall_mm"], 0.0)
        self.assertTrue(m["has_temp_data"])
        self.assertTrue(m["has_wind_data"])
        self.assertTrue(m["has_rain_data"])

    def test_precipitation_data_array(self):
        ctx = {
            "weather_data": {
                "precipitation_data": [
                    {
                        "date": "2026-09-12",
                        "rain_probability": 75,
                        "rainfall": 6.4,
                        "max_temperature": 29.0,
                    }
                ]
            }
        }
        m = extract_context_metrics(ctx)
        self.assertEqual(m["rain_probability"], 75)
        self.assertEqual(m["rainfall_mm"], 6.4)
        self.assertEqual(m["temperature"], 29.0)
        self.assertTrue(m["has_rain_data"])

    def test_forecast_array(self):
        ctx = {
            "weather_data": {
                "forecast": [
                    {
                        "date": "2026-09-13",
                        "max_temperature": 38.5,
                        "rain_probability": 10,
                        "rainfall": 0.0,
                        "max_wind_speed": 28.0,
                    }
                ]
            }
        }
        m = extract_context_metrics(ctx)
        self.assertEqual(m["temperature"], 38.5)
        self.assertEqual(m["rain_probability"], 10)
        self.assertEqual(m["wind_speed_kmh"], 28.0)


class TestUmbrellaRecommendation(unittest.TestCase):
    """Test deterministic umbrella recommendation logic."""

    def test_umbrella_recommended_high_probability(self):
        ctx = {"weather_data": {"forecast": [{"rain_probability": 80, "rainfall": 2.0}]}}
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "recommended")
        self.assertIn("recommended", rec["reason"].lower())

    def test_umbrella_recommended_significant_rainfall(self):
        ctx = {"weather_data": {"precipitation": 3.5}}
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["status"], "recommended")

    def test_umbrella_not_needed_low_probability(self):
        ctx = {"weather_data": {"forecast": [{"rain_probability": 5, "rainfall": 0.0}]}}
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "not_needed")
        self.assertIn("not needed", rec["reason"].lower())

    def test_umbrella_uncertain_moderate_probability(self):
        ctx = {"weather_data": {"forecast": [{"rain_probability": 35, "rainfall": 0.2}]}}
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "uncertain")

    def test_umbrella_insufficient_data(self):
        ctx = {"weather_data": {"temperature": 25.0}}  # no rain data
        rec = get_umbrella_recommendation(ctx)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "insufficient_data")


class TestHeatRecommendation(unittest.TestCase):
    """Test deterministic heat advisory logic."""

    def test_high_heat(self):
        ctx = {"weather_data": {"temperature": 42.0}}
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "high_heat")
        self.assertIn("hydrated", rec["reason"].lower())

    def test_heat_caution(self):
        ctx = {"weather_data": {"temperature": 36.5}}
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "caution")

    def test_heat_normal(self):
        ctx = {"weather_data": {"temperature": 26.0}}
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "normal")

    def test_heat_apparent_temperature_takes_precedence_when_higher(self):
        ctx = {"weather_data": {"temperature": 33.0, "apparent_temperature": 40.5}}
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["status"], "high_heat")

    def test_heat_insufficient_data(self):
        ctx = {"weather_data": {"wind_speed": 15.0}}  # no temp
        rec = get_heat_recommendation(ctx)
        self.assertEqual(rec["type"], "heat")
        self.assertEqual(rec["status"], "insufficient_data")


class TestWindRecommendation(unittest.TestCase):
    """Test deterministic wind advisory logic."""

    def test_strong_wind(self):
        ctx = {"weather_data": {"wind_speed": 45.0}}
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "strong_wind")

    def test_windy(self):
        ctx = {"weather_data": {"wind_speed": 28.0}}
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "windy")

    def test_wind_normal(self):
        ctx = {"weather_data": {"wind_speed": 12.0}}
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "normal")

    def test_wind_insufficient_data(self):
        ctx = {"weather_data": {"temperature": 24.0}}
        rec = get_wind_recommendation(ctx)
        self.assertEqual(rec["type"], "wind")
        self.assertEqual(rec["status"], "insufficient_data")


class TestOutdoorRecommendation(unittest.TestCase):
    """Test outdoor activity suitability."""

    def test_outdoor_favorable(self):
        ctx = {
            "weather_data": {
                "temperature": 24.0,
                "wind_speed": 10.0,
                "forecast": [{"rain_probability": 5, "rainfall": 0.0, "max_temperature": 24.0, "max_wind_speed": 10.0}]
            }
        }
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["type"], "outdoor")
        self.assertEqual(rec["status"], "favorable")

    def test_outdoor_unfavorable_due_to_rain(self):
        ctx = {
            "weather_data": {
                "temperature": 24.0,
                "forecast": [{"rain_probability": 85, "rainfall": 5.0}]
            }
        }
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["status"], "unfavorable")
        self.assertIn("rain expected", rec["reason"])

    def test_outdoor_caution_due_to_moderate_heat(self):
        ctx = {
            "weather_data": {
                "temperature": 36.0,
                "forecast": [{"rain_probability": 5, "rainfall": 0.0}]
            }
        }
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["status"], "caution")

    def test_outdoor_insufficient_data(self):
        ctx = {"weather_data": {}}
        rec = get_outdoor_recommendation(ctx)
        self.assertEqual(rec["status"], "insufficient_data")


class TestTravelRecommendation(unittest.TestCase):
    """Test travel weather suitability."""

    def test_travel_favorable(self):
        ctx = {
            "weather_data": {
                "temperature": 25.0,
                "wind_speed": 10.0,
                "precipitation": 0.0,
            }
        }
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["type"], "travel")
        self.assertEqual(rec["status"], "favorable")

    def test_travel_caution(self):
        ctx = {
            "weather_data": {
                "temperature": 25.0,
                "forecast": [{"rain_probability": 60, "rainfall": 2.0}]
            }
        }
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["status"], "caution")

    def test_travel_unfavorable_severe_rain(self):
        ctx = {
            "weather_data": {
                "forecast": [{"rain_probability": 90, "rainfall": 25.0}]
            }
        }
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["status"], "unfavorable")

    def test_travel_insufficient_data(self):
        ctx = {"weather_data": {}}
        rec = get_travel_recommendation(ctx)
        self.assertEqual(rec["status"], "insufficient_data")


class TestDetermineRecommendationType(unittest.TestCase):
    """Test deterministic mapping of messages/queries to recommendation types."""

    def test_message_keywords(self):
        self.assertEqual(determine_recommendation_type(message="Should I carry an umbrella today?"), "umbrella")
        self.assertEqual(determine_recommendation_type(message="Will it be very hot outside?"), "heat")
        self.assertEqual(determine_recommendation_type(message="Is it windy right now?"), "wind")
        self.assertEqual(determine_recommendation_type(message="Is it safe for travel tomorrow?"), "travel")
        self.assertEqual(determine_recommendation_type(message="Can we have an outdoor picnic?"), "outdoor")

    def test_query_intent_mapping(self):
        self.assertEqual(
            determine_recommendation_type(query={"intent": "travel_advisory"}),
            "travel"
        )
        self.assertEqual(
            determine_recommendation_type(query={"intent": "advisory", "weather_variable": "precipitation"}),
            "umbrella"
        )
        self.assertEqual(
            determine_recommendation_type(query={"intent": "advisory", "weather_variable": "temperature"}),
            "heat"
        )
        self.assertEqual(
            determine_recommendation_type(query={"intent": "advisory", "weather_variable": "wind"}),
            "wind"
        )
        self.assertEqual(
            determine_recommendation_type(query={"intent": "advisory", "weather_variable": None}),
            "outdoor"
        )

    def test_no_recommendation_for_generic_query(self):
        self.assertIsNone(
            determine_recommendation_type(query={"intent": "current_weather"}, message="What is the weather in Delhi?")
        )


class TestGenerateRecommendation(unittest.TestCase):
    """Test the end-to-end generate_recommendation helper."""

    def test_generate_umbrella_from_message(self):
        ctx = {
            "weather_data": {
                "forecast": [{"rain_probability": 75, "rainfall": 3.0}]
            }
        }
        rec = generate_recommendation(ctx, message="Do I need an umbrella in Mumbai?")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "recommended")

    def test_generate_none_when_unrelated(self):
        ctx = {"weather_data": {"temperature": 25.0}}
        rec = generate_recommendation(ctx, message="What is the capital of France?")
        self.assertIsNone(rec)


class TestAskEndpointWithRecommendation(unittest.TestCase):
    """Test /ask endpoint integration with recommendation generation."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_ask_umbrella_includes_recommendation(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "rain",
            "location": "Hyderabad",
            "city": "Hyderabad",
            "time_period": "tomorrow",
            "weather_variable": "precipitation",
            "requires_location": False,
        })
        mock_context.return_value = {
            "status": "success",
            "intent": "rain",
            "location": "Hyderabad",
            "time_period": "tomorrow",
            "weather_variable": "precipitation",
            "weather_data": {
                "city": "Hyderabad",
                "precipitation_data": [
                    {"rain_probability": 85, "rainfall": 8.0, "max_temperature": 28.0}
                ],
                "source": "open_meteo",
            },
            "source": "open_meteo",
        }
        mock_answer.return_value = "Rain is very likely tomorrow in Hyderabad (85% probability, 8.0 mm). Carry an umbrella!"

        resp = self.client.post("/ask", json={"message": "Do I need an umbrella tomorrow in Hyderabad?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Check all standard keys are present
        for key in ["question", "intent", "city", "time_period", "weather_variable", "answer", "weather_data", "source"]:
            self.assertIn(key, data)

        # Check recommendation is included
        self.assertIn("recommendation", data)
        rec = data["recommendation"]
        self.assertEqual(rec["type"], "umbrella")
        self.assertEqual(rec["status"], "recommended")

        # Verify context passed to mock_answer had recommendation embedded
        called_context = mock_answer.call_args[0][1]
        self.assertIn("recommendation", called_context)
        self.assertEqual(called_context["recommendation"]["status"], "recommended")

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_ask_general_weather_omits_recommendation_cleanly(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "current_weather",
            "location": "Delhi",
            "city": "Delhi",
            "time_period": "current",
            "weather_variable": None,
            "requires_location": False,
        })
        mock_context.return_value = {
            "status": "success",
            "intent": "current_weather",
            "location": "Delhi",
            "time_period": "current",
            "weather_variable": None,
            "weather_data": {
                "city": "Delhi",
                "temperature": 27.5,
                "source": "open_meteo",
            },
            "source": "open_meteo",
        }
        mock_answer.return_value = "The current temperature in Delhi is 27.5°C with mild conditions."

        resp = self.client.post("/ask", json={"message": "What is the weather in Delhi?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # All 8 standard keys present
        for key in ["question", "intent", "city", "time_period", "weather_variable", "answer", "weather_data", "source"]:
            self.assertIn(key, data)

        # Recommendation should NOT be attached to response if not requested
        self.assertNotIn("recommendation", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
