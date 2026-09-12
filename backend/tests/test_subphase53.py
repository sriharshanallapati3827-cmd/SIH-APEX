"""
Test Suite: Sub-Phase 5.3 — Conversational Follow-Up & Context Continuity

Focus:
1. follow-up inherits previous location
2. follow-up inherits previous time period
3. follow-up changes weather variable correctly
4. follow-up can change location
5. follow-up can change time period
6. ambiguous/missing context asks for clarification
7. no fabricated location
8. no stale weather data used as fresh weather (fresh context is built)
9. recommendation follow-up preserves relevant context
10. existing non-conversational request remains compatible
11. session_id based multi-turn continuity
"""

import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.conversation_service import (
    get_conversation_context,
    save_conversation_context,
    clear_conversation_context,
    extract_last_context_from_history,
    resolve_followup_query,
)
from fastapi.testclient import TestClient
from main import app


class TestConversationServiceUnit(unittest.TestCase):
    """Unit tests for conversation_service helper methods."""

    def setUp(self):
        clear_conversation_context()

    def test_save_and_get_session_context(self):
        save_conversation_context("session_1", {"location": "Hyderabad", "time_period": "tomorrow"})
        ctx = get_conversation_context("session_1")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["location"], "Hyderabad")
        self.assertEqual(ctx["time_period"], "tomorrow")

    def test_clear_session_context(self):
        save_conversation_context("session_1", {"location": "Hyderabad"})
        clear_conversation_context("session_1")
        self.assertIsNone(get_conversation_context("session_1"))

    def test_extract_last_context_from_history(self):
        history = [
            {"location": "Delhi", "time_period": "today"},
            {"location": "Hyderabad", "time_period": "tomorrow", "weather_variable": "precipitation"},
        ]
        ctx = extract_last_context_from_history(history)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["location"], "Hyderabad")
        self.assertEqual(ctx["time_period"], "tomorrow")

    def test_followup_inherits_previous_location(self):
        current_query = {
            "intent": "rain",
            "location": None,
            "city": None,
            "time_period": None,
            "weather_variable": "precipitation",
            "requires_location": True,
        }
        previous_context = {
            "location": "Hyderabad",
            "city": "Hyderabad",
            "time_period": "current",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="Will it rain?")
        self.assertEqual(resolved["location"], "Hyderabad")
        self.assertFalse(resolved["requires_location"])
        self.assertTrue(resolved.get("inherited_location"))

    def test_followup_inherits_previous_time_period(self):
        current_query = {
            "intent": "rain",
            "location": "Mumbai",
            "city": "Mumbai",
            "time_period": None,
            "weather_variable": "precipitation",
            "requires_location": False,
        }
        previous_context = {
            "location": "Mumbai",
            "time_period": "weekend",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="Will it rain?")
        self.assertEqual(resolved["time_period"], "weekend")
        self.assertTrue(resolved.get("inherited_time_period"))

    def test_followup_changes_weather_variable_correctly(self):
        current_query = {
            "intent": "temperature",
            "location": None,
            "city": None,
            "time_period": None,
            "weather_variable": "temperature",
            "requires_location": True,
        }
        previous_context = {
            "location": "Delhi",
            "time_period": "tomorrow",
            "weather_variable": "precipitation",
            "intent": "rain",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="What about the temperature?")
        self.assertEqual(resolved["location"], "Delhi")
        self.assertEqual(resolved["time_period"], "tomorrow")
        self.assertEqual(resolved["intent"], "temperature")
        self.assertEqual(resolved["weather_variable"], "temperature")

    def test_followup_can_change_location(self):
        current_query = {
            "intent": "current_weather",
            "location": "Mumbai",
            "city": "Mumbai",
            "time_period": None,
            "weather_variable": None,
            "requires_location": False,
        }
        previous_context = {
            "location": "Hyderabad",
            "city": "Hyderabad",
            "time_period": "tomorrow",
            "intent": "rain",
            "weather_variable": "precipitation",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="What about Mumbai?")
        # Location changes to Mumbai, inherits rain & tomorrow from prior context
        self.assertEqual(resolved["location"], "Mumbai")
        self.assertEqual(resolved["time_period"], "tomorrow")
        self.assertEqual(resolved["intent"], "rain")

    def test_followup_can_change_time_period(self):
        current_query = {
            "intent": "forecast",
            "location": None,
            "city": None,
            "time_period": "tomorrow",
            "weather_variable": None,
            "requires_location": True,
        }
        previous_context = {
            "location": "Chennai",
            "time_period": "today",
            "intent": "current_weather",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="How about tomorrow?")
        self.assertEqual(resolved["location"], "Chennai")
        self.assertEqual(resolved["time_period"], "tomorrow")

    def test_ambiguous_context_asks_for_clarification(self):
        current_query = {
            "intent": "current_weather",
            "location": None,
            "city": None,
            "time_period": None,
            "requires_location": True,
        }
        previous_context = {
            "location": "Hyderabad",
            "time_period": "today",
        }
        resolved = resolve_followup_query(current_query, previous_context, message="Which one is better?")
        self.assertTrue(resolved.get("is_ambiguous"))
        self.assertIn("clarify", resolved.get("clarification_needed", "").lower())

    def test_no_fabricated_location_when_no_prior_context(self):
        current_query = {
            "intent": "rain",
            "location": None,
            "city": None,
            "time_period": "tomorrow",
            "requires_location": True,
        }
        resolved = resolve_followup_query(current_query, None, message="Will it rain tomorrow?")
        self.assertIsNone(resolved["location"])
        self.assertTrue(resolved["requires_location"])


class TestConversationalAskIntegration(unittest.TestCase):
    """Integration tests for /ask with multi-turn conversation and session handling."""

    def setUp(self):
        clear_conversation_context()
        self.client = TestClient(app)

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_turn1_and_turn2_session_continuity(
        self, mock_understand, mock_context, mock_answer
    ):
        # Turn 1: "What's the weather in Hyderabad tomorrow?"
        mock_understand.side_effect = [
            json.dumps({
                "intent": "forecast",
                "location": "Hyderabad",
                "city": "Hyderabad",
                "time_period": "tomorrow",
                "weather_variable": None,
                "requires_location": False,
            }),
            # Turn 2: "Will I need an umbrella?" (missing location and time_period)
            json.dumps({
                "intent": "rain",
                "location": None,
                "city": None,
                "time_period": None,
                "weather_variable": "precipitation",
                "requires_location": True,
            }),
        ]

        mock_context.side_effect = [
            {
                "status": "success",
                "intent": "forecast",
                "location": "Hyderabad",
                "time_period": "tomorrow",
                "weather_variable": None,
                "weather_data": {"city": "Hyderabad", "temperature": 29.0},
                "source": "open_meteo",
            },
            {
                "status": "success",
                "intent": "rain",
                "location": "Hyderabad",
                "time_period": "tomorrow",
                "weather_variable": "precipitation",
                "weather_data": {
                    "city": "Hyderabad",
                    "precipitation_data": [{"rain_probability": 85, "rainfall": 6.0}],
                },
                "source": "open_meteo",
            },
        ]
        mock_answer.side_effect = [
            "Tomorrow in Hyderabad the temperature will be 29.0°C.",
            "Yes, carrying an umbrella tomorrow in Hyderabad is recommended due to an 85% chance of rain.",
        ]

        # Call Turn 1
        resp1 = self.client.post("/ask", json={
            "message": "What's the weather in Hyderabad tomorrow?",
            "session_id": "session_test_1",
        })
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertEqual(data1["city"], "Hyderabad")
        self.assertEqual(data1["time_period"], "tomorrow")
        self.assertEqual(data1.get("session_id"), "session_test_1")

        # Call Turn 2 with same session_id
        resp2 = self.client.post("/ask", json={
            "message": "Will I need an umbrella?",
            "session_id": "session_test_1",
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()

        # Follow-up inherited location and time_period from Turn 1
        self.assertEqual(data2["city"], "Hyderabad")
        self.assertEqual(data2["time_period"], "tomorrow")
        self.assertEqual(data2["intent"], "rain")

        # Recommendation was generated for umbrella in Hyderabad tomorrow
        self.assertIn("recommendation", data2)
        self.assertEqual(data2["recommendation"]["type"], "umbrella")
        self.assertEqual(data2["recommendation"]["status"], "recommended")

        # Verify build_weather_context was called freshly on Turn 2 with resolved query
        second_call_query = mock_context.call_args_list[1][0][0]
        self.assertEqual(second_call_query["location"], "Hyderabad")
        self.assertEqual(second_call_query["time_period"], "tomorrow")

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_followup_with_explicit_previous_context(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "temperature",
            "location": None,
            "city": None,
            "time_period": None,
            "weather_variable": "temperature",
            "requires_location": True,
        })
        mock_context.return_value = {
            "status": "success",
            "intent": "temperature",
            "location": "Delhi",
            "time_period": "weekend",
            "weather_variable": "temperature",
            "weather_data": {"city": "Delhi", "temperatures": [{"max_temperature": 38.0}]},
            "source": "open_meteo",
        }
        mock_answer.return_value = "The high temperature this weekend in Delhi will be around 38.0°C."

        resp = self.client.post("/ask", json={
            "message": "What about the temperature?",
            "previous_context": {
                "location": "Delhi",
                "time_period": "weekend",
                "intent": "forecast",
            }
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["city"], "Delhi")
        self.assertEqual(data["time_period"], "weekend")
        self.assertEqual(data["intent"], "temperature")

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_ambiguous_followup_prompts_clarification_no_guessing(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "current_weather",
            "location": None,
            "city": None,
            "time_period": None,
            "requires_location": True,
        })

        resp = self.client.post("/ask", json={
            "message": "Which one has more rain?",
            "session_id": "test_ambig",
            "previous_context": {"location": "Hyderabad"}
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["intent"], "clarification_needed")
        self.assertIsNone(data["city"])
        self.assertIn("clarify", data["answer"].lower())
        # Weather context was NOT built and no data was fabricated
        mock_context.assert_not_called()

    @patch("routes.ai.get_final_answer")
    @patch("routes.ai.build_weather_context")
    @patch("routes.ai.understand_query")
    def test_existing_non_conversational_request_compatibility(
        self, mock_understand, mock_context, mock_answer
    ):
        mock_understand.return_value = json.dumps({
            "intent": "current_weather",
            "location": "Pune",
            "city": "Pune",
            "time_period": "current",
            "weather_variable": None,
            "requires_location": False,
        })
        mock_context.return_value = {
            "status": "success",
            "intent": "current_weather",
            "location": "Pune",
            "time_period": "current",
            "weather_variable": None,
            "weather_data": {"city": "Pune", "temperature": 26.0},
            "source": "open_meteo",
        }
        mock_answer.return_value = "The current weather in Pune is 26.0°C."

        # Plain call without any conversational fields
        resp = self.client.post("/ask", json={"message": "What is the weather in Pune?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        for k in ["question", "intent", "city", "time_period", "weather_variable", "answer", "weather_data", "source"]:
            self.assertIn(k, data)
        self.assertNotIn("session_id", data)
        self.assertNotIn("conversation_context", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
