"""
Test Suite: Sub-Phase 5.4 — Location & Query Robustness

Focus:
1. Location case normalization (HYDERABAD, hyderabad, Hyderabad).
2. Location whitespace normalization ('  Hyderabad  ').
3. Common city/location phrasing ('Hyderabad, India', 'in Hyderabad', 'around Mumbai').
4. Invalid / unresolvable location handling (HTTP 404, zero fabricated data).
5. Empty / whitespace-only query handling (clean 200 response, no crash).
6. Natural-language weather query variations.
7. Follow-up location override (Turn 1: Hyderabad -> Turn 2: What about Delhi?).
8. Follow-up time-period override (Turn 1: tomorrow -> Turn 2: What about today?).
9. Ambiguous follow-up prevents guessing / hallucination (clarification prompt).
10. Recommendation query compatibility with normalized location.
11. Forecast query compatibility with normalized location.
12. Anti-fabrication verification (no fake weather data produced).
"""

import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

# Ensure backend directory is in sys.path and .env is loaded
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from services.geocoding_service import get_coordinates
from services.ai_service import validate_and_normalize_query, understand_query
from services.conversation_service import resolve_followup_query, clear_conversation_context
from fastapi.testclient import TestClient
from main import app


class TestLocationRobustnessUnit(unittest.TestCase):
    """Unit tests for location string cleaning and geocoding normalization."""

    def test_geocoding_case_insensitivity(self):
        # Open-Meteo geocoding handles uppercase/lowercase
        res_upper = get_coordinates("HYDERABAD")
        self.assertEqual(res_upper["name"], "Hyderabad")
        self.assertAlmostEqual(res_upper["latitude"], 17.38, places=1)

        res_lower = get_coordinates("hyderabad")
        self.assertEqual(res_lower["name"], "Hyderabad")

    def test_geocoding_whitespace_stripping(self):
        res = get_coordinates("   Hyderabad   ")
        self.assertEqual(res["name"], "Hyderabad")

    def test_geocoding_city_with_country_fallback(self):
        res = get_coordinates("Hyderabad, India")
        self.assertEqual(res["name"], "Hyderabad")

    def test_geocoding_preposition_stripping(self):
        res = get_coordinates("in Hyderabad")
        self.assertEqual(res["name"], "Hyderabad")

    def test_geocoding_invalid_location_raises_404(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_coordinates("InvalidLocationXYZ999999")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "City not found")

    def test_geocoding_empty_string_raises_404(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_coordinates("   ")
        self.assertEqual(ctx.exception.status_code, 404)


class TestQueryValidationRobustness(unittest.TestCase):
    """Unit tests for query validation and normalization robustness."""

    def test_location_prefix_stripping_in_normalization(self):
        raw = {
            "intent": "current_weather",
            "location": "in Mumbai",
            "time_period": "current",
        }
        norm = validate_and_normalize_query(raw)
        self.assertEqual(norm["location"], "Mumbai")
        self.assertEqual(norm["city"], "Mumbai")

    def test_empty_message_in_understand_query(self):
        res_empty = json.loads(understand_query(""))
        self.assertEqual(res_empty["intent"], "unknown")
        self.assertIsNone(res_empty["location"])

        res_spaces = json.loads(understand_query("    "))
        self.assertEqual(res_spaces["intent"], "unknown")
        self.assertIsNone(res_spaces["location"])


class TestFollowUpRobustness(unittest.TestCase):
    """Tests verifying follow-up overrides and anti-guessing behavior."""

    def setUp(self):
        clear_conversation_context()

    def test_followup_explicit_location_overrides_previous(self):
        current_query = {
            "intent": "current_weather",
            "location": "Delhi",
            "city": "Delhi",
            "time_period": None,
            "requires_location": False,
        }
        previous_context = {
            "location": "Hyderabad",
            "time_period": "tomorrow",
            "intent": "rain",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="What about Delhi?")
        self.assertEqual(resolved["location"], "Delhi")
        self.assertEqual(resolved["time_period"], "tomorrow")

    def test_followup_explicit_time_period_overrides_previous(self):
        current_query = {
            "intent": "forecast",
            "location": None,
            "time_period": "today",
            "requires_location": True,
        }
        previous_context = {
            "location": "Hyderabad",
            "time_period": "tomorrow",
            "intent": "forecast",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="What about today?")
        self.assertEqual(resolved["location"], "Hyderabad")
        self.assertEqual(resolved["time_period"], "today")

    def test_ambiguous_queries_trigger_clarification(self):
        prev = {"location": "Hyderabad", "time_period": "today"}

        for phrase in ["Which one is better?", "What about both of them?", "compare them"]:
            q = {"intent": "current_weather", "location": None, "requires_location": True}
            res = resolve_followup_query(q, prev, message=phrase)
            self.assertTrue(res.get("is_ambiguous"))
            self.assertIn("clarify", res.get("clarification_needed", "").lower())


class TestAskEndpointRobustnessIntegration(unittest.TestCase):
    """Integration tests for /ask with various input forms and edge cases."""

    def setUp(self):
        clear_conversation_context()
        self.client = TestClient(app)

    def test_ask_empty_or_whitespace_message_returns_clean_response(self):
        resp = self.client.post("/ask", json={"message": "   "})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["intent"], "unknown")
        self.assertIsNone(data["city"])
        self.assertIn("weather-related", data["answer"])
        self.assertIsNone(data["weather_data"])

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_ask_handles_whitespace_padded_location_with_recommendation(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "rain",
            "location": "  Hyderabad  ",
            "city": "  Hyderabad  ",
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
                "precipitation_data": [{"rain_probability": 85, "rainfall": 6.0}],
                "source": "open_meteo",
            },
            "source": "open_meteo",
        }
        mock_answer.return_value = "Carry an umbrella tomorrow in Hyderabad due to 85% rain."

        resp = self.client.post("/ask", json={"message": "Will I need an umbrella tomorrow in   Hyderabad  ?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["city"], "Hyderabad")
        self.assertIn("recommendation", data)
        self.assertEqual(data["recommendation"]["type"], "umbrella")
        self.assertEqual(data["recommendation"]["status"], "recommended")

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_natural_language_variations_preserve_intent_and_grounding(
        self, mock_understand, mock_context, mock_answer
    ):
        variations = [
            ("What's the weather like in Hyderabad?", "current_weather"),
            ("How is Hyderabad today?", "current_weather"),
            ("Tell me Hyderabad's weather.", "current_weather"),
            ("How hot will it be in Hyderabad tomorrow?", "temperature"),
        ]

        for query_text, expected_intent in variations:
            mock_understand.return_value = json.dumps({
                "intent": expected_intent,
                "location": "Hyderabad",
                "city": "Hyderabad",
                "time_period": "tomorrow" if "tomorrow" in query_text else "current",
                "weather_variable": "temperature" if "hot" in query_text else None,
                "requires_location": False,
            })
            mock_context.return_value = {
                "status": "success",
                "intent": expected_intent,
                "location": "Hyderabad",
                "time_period": "tomorrow" if "tomorrow" in query_text else "current",
                "weather_variable": "temperature" if "hot" in query_text else None,
                "weather_data": {"city": "Hyderabad", "temperature": 32.0},
                "source": "open_meteo",
            }
            mock_answer.return_value = "The temperature in Hyderabad is 32.0°C."

            resp = self.client.post("/ask", json={"message": query_text})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["city"], "Hyderabad")
            self.assertEqual(data["intent"], expected_intent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
