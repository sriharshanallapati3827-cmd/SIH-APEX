from fastapi import APIRouter, HTTPException
import json
from models.schemas import ChatRequest
from services.ai_service import get_ai_test, understand_query, get_final_answer
from services.weather_context import build_weather_context
from services.recommendation_service import generate_recommendation
from services.conversation_service import (
    get_conversation_context,
    save_conversation_context,
    extract_last_context_from_history,
    resolve_followup_query,
)
from services.weather_service import (
    get_current_weather_by_city,
    get_forecast_by_city,
    get_alerts_by_city,
    get_weather_summary_by_location,
    get_forecast_by_coords,
    get_alerts_by_coords,
)
from services.gemini_service import query_gemini

router = APIRouter()

@router.get("/chat")
def chat(message: str):
    message_lower = message.lower()
    if "weather" in message_lower:
        return {
            "message": message,
            "response": "I can help you with weather information."
        }
    return {
        "message": message,
        "response": "I am WeatherGPT. Please ask me a weather-related question."
    }

@router.get("/ai-test")
def ai_test(message: str):
    return get_ai_test(message)

@router.get("/understand")
def understand_question(message: str):
    ai_output = understand_query(message)
    return {
        "question": message,
        "ai_output": ai_output
    }

@router.post("/ask")
def ask_weather(request: ChatRequest):
    """
    Full grounded weather Q&A pipeline with conversational follow-up continuity (Sub-Phase 5.3):
      resolve_followup_query() -> QueryUnderstanding -> build_weather_context() -> get_final_answer()
    """
    message = request.message
    if not message or not str(message).strip():
        return {
            "question": message,
            "intent": "unknown",
            "city": None,
            "time_period": None,
            "weather_variable": None,
            "answer": "Please ask me a weather-related question.",
            "weather_data": None,
            "source": None,
        }

    # --- Step 0: Conversational context retrieval (Sub-Phase 5.3) ---
    prev_ctx = request.previous_context
    if not prev_ctx and request.session_id:
        prev_ctx = get_conversation_context(request.session_id)
    elif not prev_ctx and request.conversation_history:
        prev_ctx = extract_last_context_from_history(request.conversation_history)

    # --- Step 1: AI query understanding ---
    ai_output = understand_query(message)
    try:
        query = json.loads(ai_output)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid JSON")

    # --- Step 1b: Resolve follow-up query against previous context (Sub-Phase 5.3) ---
    query = resolve_followup_query(query, prev_ctx, message=message)

    if query.get("is_ambiguous"):
        return {
            "question": message,
            "intent": "clarification_needed",
            "city": None,
            "answer": query.get(
                "clarification_needed",
                "Could you please clarify which city or time period you would like to check?"
            ),
            "weather_data": None,
        }

    intent = query.get("intent", "unknown")

    # --- Step 2: Build grounded weather context via pipeline ---
    context = build_weather_context(
        query,
        latitude=request.latitude,
        longitude=request.longitude,
    )

    # --- Step 3: Handle non-success context statuses ---
    if context["status"] == "location_required":
        return {
            "question": message,
            "intent": intent,
            "city": None,
            "answer": (
                "Location is required to provide weather information. "
                "Please specify a city or provide GPS coordinates."
            ),
            "weather_data": None,
        }

    if context["status"] == "unsupported_intent":
        return {
            "question": message,
            "intent": intent,
            "city": context.get("location"),
            "answer": (
                "Sorry, I could not understand your weather question. "
                "Please ask about current weather, forecasts, rain, or alerts."
            ),
            "weather_data": None,
        }

    # --- Step 4: Generate deterministic weather recommendations (Sub-Phase 5.1 & 5.2) ---
    recommendation = generate_recommendation(
        context,
        query=query,
        message=message,
    )
    if recommendation:
        context["recommendation"] = recommendation

    # --- Step 5: Generate natural-language answer grounded in weather context ---
    final_answer = get_final_answer(message, context)

    # Ensure source attribution is present both at top-level and inside weather_data
    weather_payload = dict(context["weather_data"]) if isinstance(context.get("weather_data"), dict) else context.get("weather_data")
    if isinstance(weather_payload, dict) and "source" not in weather_payload:
        weather_payload["source"] = context.get("source")

    # Update session memory if session_id was provided
    if request.session_id:
        save_conversation_context(request.session_id, {
            "location": context.get("location"),
            "city": context.get("location"),
            "time_period": context.get("time_period"),
            "forecast_period": context.get("forecast_period") or context.get("time_period"),
            "weather_variable": context.get("weather_variable"),
            "intent": context.get("intent"),
        })

    # --- Step 6: Return structured response ---
    response_payload = {
        "question": message,
        "intent": context["intent"],
        "city": context["location"],
        "time_period": context.get("time_period"),
        "weather_variable": context.get("weather_variable"),
        "answer": final_answer,
        "weather_data": weather_payload,
        "source": context.get("source"),
    }
    if recommendation:
        response_payload["recommendation"] = recommendation

    if request.session_id:
        response_payload["session_id"] = request.session_id

    if request.session_id or request.previous_context or request.conversation_history:
        response_payload["conversation_context"] = {
            "location": context.get("location"),
            "time_period": context.get("time_period"),
            "weather_variable": context.get("weather_variable"),
            "intent": context.get("intent"),
        }

    return response_payload

@router.post("/ask-demo")
def ask_demo(request: ChatRequest):
    message = request.message
    message_lower = message.lower()

    # Priority 1: Explicit city in message
    city = None
    if "hyderabad" in message_lower or "hyd" in message_lower:
        city = "Hyderabad"
    elif "delhi" in message_lower:
        city = "Delhi"
    elif "mumbai" in message_lower:
        city = "Mumbai"
    elif "chennai" in message_lower:
        city = "Chennai"
    elif "bangalore" in message_lower or "bengaluru" in message_lower:
        city = "Bengaluru"

    # Priority 2: GPS coordinates if no explicit city
    use_coords = False
    is_here = any(phrase in message_lower for phrase in ["here", "my location", "current location", "where i am"])

    if not city:
        if request.latitude is not None and request.longitude is not None:
            use_coords = True
        elif is_here or "weather" in message_lower or "forecast" in message_lower or "rain" in message_lower or "alert" in message_lower or "temperature" in message_lower or "hot" in message_lower:
            return {
                "question": request.message,
                "intent": "forecast" if any(w in message_lower for w in ["forecast", "tomorrow", "rain", "weekend"]) else "current_weather",
                "city": None,
                "forecast_period": None,
                "answer": "Location is required to provide weather information. Please specify a city or provide GPS coordinates.",
                "weather_data": None
            }
        else:
            return {
                "question": request.message,
                "intent": "unknown",
                "city": None,
                "forecast_period": None,
                "answer": "Please ask me about weather, forecast, rain or alerts.",
                "weather_data": None
            }

    # Identify forecast periods
    forecast_period = "next_7_days"
    if "tomorrow" in message_lower:
        forecast_period = "tomorrow"
    elif "weekend" in message_lower or "saturday" in message_lower or "sunday" in message_lower:
        forecast_period = "weekend"
    elif "3 days" in message_lower or "three days" in message_lower:
        forecast_period = "next_3_days"
    elif "7 days" in message_lower or "seven days" in message_lower or "week" in message_lower:
        forecast_period = "next_7_days"
    elif any(h in message_lower for h in ["pm", "am", "hour", "afternoon", "morning", "evening", "tonight"]):
        forecast_period = "hourly"
    elif "today" in message_lower:
        forecast_period = "today"

    # Decide intent
    target_name = city if city else f"coordinates ({request.latitude}, {request.longitude})"

    if "alert" in message_lower or "warning" in message_lower:
        intent = "alerts"
        weather_data = get_alerts_by_coords(request.latitude, request.longitude) if use_coords else get_alerts_by_city(city)
        answer = f"Alerts check for {target_name}: {weather_data['alerts'][0]['message']}"
        forecast_period = None
    elif any(w in message_lower for w in ["forecast", "tomorrow", "rain", "weekend", "hot", "next"]):
        intent = "forecast"
        weather_data = get_forecast_by_coords(request.latitude, request.longitude, period=forecast_period) if use_coords else get_forecast_by_city(city, period=forecast_period)

        # Build natural grounded answer for demo
        f_list = weather_data.get("forecast", [])
        if forecast_period == "tomorrow" and f_list:
            d = f_list[0]
            answer = (
                f"Tomorrow's forecast for {target_name}: Max Temp: {d['max_temperature']}°C, "
                f"Min Temp: {d['min_temperature']}°C, Rain Probability: {d['rain_probability']}%, "
                f"Expected Rainfall: {d['rainfall']} mm, Max Wind: {d.get('max_wind_speed', 'N/A')} km/h."
            )
        elif forecast_period == "next_7_days" and f_list:
            max_temps = [d['max_temperature'] for d in f_list]
            rain_probs = [d['rain_probability'] for d in f_list]
            answer = (
                f"7-day forecast for {target_name}: Highs from {min(max_temps)}°C to {max(max_temps)}°C. "
                f"Highest rain probability is {max(rain_probs)}% across the 7 days."
            )
        elif forecast_period == "weekend" and f_list:
            d_strs = [f"{d['date']} (Max {d['max_temperature']}°C, Rain {d['rain_probability']}%)" for d in f_list]
            answer = f"Weekend forecast for {target_name}: {', '.join(d_strs)}."
        elif forecast_period == "hourly" and "hourly_forecast" in weather_data:
            h_sample = weather_data["hourly_forecast"][:6]
            h_strs = [f"{h['time'].split('T')[-1]}: {h['temperature']}°C ({h['rain_probability']}% rain)" for h in h_sample]
            answer = f"Upcoming hourly forecast for {target_name}: {', '.join(h_strs)}."
        else:
            answer = f"Forecast data retrieved for {target_name} ({forecast_period})."
    elif "weather" in message_lower or "temperature" in message_lower or use_coords:
        intent = "current_weather"
        weather_data = get_weather_summary_by_location(request.latitude, request.longitude) if use_coords else get_current_weather_by_city(city)
        answer = f"Current weather in {target_name}: Temperature {weather_data.get('temperature', weather_data.get('weather', {}).get('temperature_2m'))}°C."
        forecast_period = None
    else:
        intent = "unknown"
        return {
            "question": request.message,
            "intent": intent,
            "city": city,
            "forecast_period": None,
            "answer": "Please ask me about weather, forecast, rain or alerts.",
            "weather_data": None
        }

    res = {
        "question": request.message,
        "intent": intent,
        "city": city,
        "answer": answer,
        "weather_data": weather_data
    }
    if intent == "forecast":
        res["forecast_period"] = forecast_period

    return res


@router.post("/api/chat")
def chat_with_gemini(request: ChatRequest):
    """
    Core WeatherGPT Mode Intelligence Endpoint:
    Directly orchestrates user query with Gemini 2.5 Flash and domain system prompts
    (travel, farmer, marine, home, alert).
    """
    message = request.message
    mode = (request.mode or "home").lower()
    
    # Generate live context-aware decision from Gemini
    gemini_answer = query_gemini(message, mode=mode)
    
    return {
        "question": message,
        "mode": mode,
        "answer": gemini_answer,
        "source": "Google Gemini 2.5 Flash + Open-Meteo Telemetry Engine"
    }
