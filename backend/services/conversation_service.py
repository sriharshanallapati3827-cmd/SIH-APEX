"""
Conversation Service — Sub-Phase 5.3
Provides lightweight, in-memory conversational follow-up resolution and context continuity.

Allows follow-up weather questions to inherit or update:
  - previous location
  - previous time period (forecast period)
  - previous weather variable / intent

Guarantees:
  - No database or persistent storage required.
  - No stale weather values are reused (fresh weather is always fetched for resolved queries).
  - Ambiguous follow-ups prompt for clarification instead of guessing or hallucinating.
  - Zero fabricated locations.
"""

from typing import Any, Dict, List, Optional


# Lightweight in-memory session cache: session_id -> latest conversation context
_SESSION_STORE: Dict[str, Dict[str, Any]] = {}


def get_conversation_context(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the latest context for an in-memory session."""
    if not session_id or not isinstance(session_id, str):
        return None
    return _SESSION_STORE.get(session_id)


def save_conversation_context(session_id: str, context_data: Dict[str, Any]) -> None:
    """Store the latest context for an in-memory session."""
    if not session_id or not isinstance(session_id, str) or not isinstance(context_data, dict):
        return
    _SESSION_STORE[session_id] = dict(context_data)


def clear_conversation_context(session_id: Optional[str] = None) -> None:
    """Clear session store (for testing or session reset)."""
    if session_id:
        _SESSION_STORE.pop(session_id, None)
    else:
        _SESSION_STORE.clear()


def extract_last_context_from_history(history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Extract relevant context from a list of conversation turns.
    Expects items with 'location'/'city', 'time_period', 'weather_variable', etc.
    """
    if not isinstance(history, list) or not history:
        return None

    for turn in reversed(history):
        if not isinstance(turn, dict):
            continue
        # Check direct fields
        loc = turn.get("location") or turn.get("city")
        period = turn.get("time_period") or turn.get("forecast_period")
        var = turn.get("weather_variable")
        intent = turn.get("intent")
        if loc or period or var or intent:
            return {
                "location": loc,
                "city": loc,
                "time_period": period,
                "forecast_period": period,
                "weather_variable": var,
                "intent": intent,
            }
    return None


def resolve_followup_query(
    current_query: Dict[str, Any],
    previous_context: Optional[Dict[str, Any]],
    message: str = "",
) -> Dict[str, Any]:
    """
    Deterministically resolve follow-up queries using previous turn context.

    Rules:
    1. If previous context is empty/missing, return current_query as-is.
    2. Check for ambiguity (e.g. 'which one', 'both of them', conflicting choices);
       if ambiguous, flag clarification_needed without guessing.
    3. Location inheritance:
       - If current_query lacks a location AND previous_context has one: inherit previous location.
       - If current_query explicitly mentions a location: use the new location (do NOT override).
    4. Time-period inheritance:
       - If current_query lacks a forecast period AND previous_context has a non-default forecast period: inherit it.
       - If current_query explicitly specifies a time period: use the new time period.
    5. Variable / Intent inheritance:
       - If current turn asks a specific weather variable (e.g. temperature/rain), update to that variable.
       - If current turn only changes location (e.g. 'What about Mumbai?') and previous was a specific intent (e.g. rain),
         inherit the previous intent/variable for the new location.
    """
    resolved = dict(current_query)

    if not previous_context or not isinstance(previous_context, dict):
        return resolved

    msg_lower = (message or "").lower()

    # Ambiguity detection: prevent guessing when reference is unclear
    ambiguous_phrases = [
        "which one", "both of them", "all of them", "either one",
        "compare them", "which is better", "what about both"
    ]
    if any(p in msg_lower for p in ambiguous_phrases):
        resolved["is_ambiguous"] = True
        resolved["clarification_needed"] = (
            "Could you please clarify which city or time period you would like to check?"
        )
        return resolved

    prev_loc = previous_context.get("location") or previous_context.get("city")
    prev_period = previous_context.get("time_period") or previous_context.get("forecast_period")
    prev_intent = previous_context.get("intent")
    prev_var = previous_context.get("weather_variable")

    # 1. Location Resolution
    curr_loc = resolved.get("location") or resolved.get("city")
    if not curr_loc and prev_loc:
        resolved["location"] = prev_loc
        resolved["city"] = prev_loc
        resolved["requires_location"] = False
        resolved["inherited_location"] = True

    # 2. Time-Period Resolution
    curr_period = resolved.get("time_period")
    explicit_time_keywords = [
        "today", "tomorrow", "tonight", "this week", "next week",
        "weekend", "saturday", "sunday", "now", "currently", "right now",
        "hourly", "3 days", "7 days"
    ]
    has_explicit_time = any(kw in msg_lower for kw in explicit_time_keywords)

    if not curr_period or (curr_period in ("current", "unknown") and not has_explicit_time):
        if prev_period and prev_period not in ("current", "unknown"):
            resolved["time_period"] = prev_period
            resolved["forecast_period"] = prev_period
            resolved["inherited_time_period"] = True

    # 3. Weather Variable / Intent Inheritance for location-shift follow-ups (e.g. "What about Delhi?")
    # If user changed location without specifying a variable, keep previous specific weather variable/intent
    is_location_shift_only = bool(curr_loc) and resolved.get("intent") in ("current_weather", "general_weather") and not resolved.get("weather_variable")
    if is_location_shift_only and prev_intent in ("rain", "temperature", "humidity", "wind", "advisory"):
        resolved["intent"] = prev_intent
        resolved["weather_variable"] = prev_var

    return resolved
