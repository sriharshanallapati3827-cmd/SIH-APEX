"""
WeatherGPT — Google Gemini Intelligence Engine
(backend/services/gemini_service.py)

Direct integration with Google Gemini 2.5 Flash using user's active API key.
Orchestrates domain-specific reasoning for:
  1. Travel Mode (Road vehicle feasibility, multi-city timeline, departure shifts)
  2. Farmer Mode (Manual spray 48h dry window vs tractor soil compaction)
  3. Marine Mode (Artisanal boat capsize risk, swell period, tidal docking)
  4. Home / Personal Mode (Commute umbrella, laundry drying, AQI elderly alerts)
  5. Disaster Alerts (Cyclone track, river flood levels, evacuation triggers)
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Set via .env file — never hardcode secrets!
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

CORE_AI_INSTRUCTIONS = """You are WeatherGPT, an advanced multimodal intelligence system powered by Google Gemini 2.5 Flash.
PRIMARY EXPERTISE: Real-time weather intelligence and situation-specific domain reasoning (Travel route road risks, Farmer crop/spray windows, Marine sea-state/wave heights, Home living, Disaster alerts).
GENERAL INTELLIGENCE & CODING CAPABILITIES:
You are ALSO an expert software engineer and algorithm specialist.
If the user asks ANY programming question, LeetCode problem, data structures & algorithms challenge, debugging task, or math/logic problem:
1. Provide the optimal, clean, well-commented solution (in Python, C++, Java, JavaScript, or whatever language requested).
2. NEVER refuse to answer coding, LeetCode, or general questions! Treat them with equal mastery."""

SYSTEM_PROMPTS = {
    "travel": """You are in specialized TRAVEL MODE.
Your mission is to evaluate weather hazards for journey corridors.
CRITICAL INSTRUCTIONS:
1. Identify origin, destination, departure time, and vehicle/transit mode (Car, Motorcycle, Bus, Bicycle, Walking/Running).
2. Physical Feasibility Check: If walking/cycling long distances (>50km), treat it as a multi-day endurance expedition or flag physical impossibility.
3. For Motorcycles: Heavily penalize rain (skidding, zero cabin protection, hypothermia) and high crosswinds.
4. Provide a structured timeline of arrival weather at 3-4 key waypoint cities along the route.
5. Conclude with a bold, clear ACTIONABLE DECISION (e.g. "Delay departure by 75 minutes to 7:15 AM to let the mountain storm cell pass").
Format cleanly with markdown bullet points.""",

    "farmer": """You are in specialized FARMER / KISAN MODE.
Your mission is to provide agro-meteorological guidance based on crop, acreage, and farming equipment.
CRITICAL INSTRUCTIONS:
1. Chemical Wash-Off Rule: Pesticides & fungicides require at least 3-4 rain-free hours to adhere to canopy. If manual spraying takes multiple days, evaluate the 48-hour rain window.
2. Equipment vs Manual Labor: Heavy tractors cannot enter fields when topsoil moisture exceeds 70% (tires sink and compact root bed). Manual labor requires wet-bulb temperature safety checks to prevent heat exhaustion.
3. Irrigation Advice: If rain probability > 60% within 36 hours, advise holding tube-well irrigation to conserve water and prevent root rot.
4. Support multilingual nuance (Hindi / Telugu terms when queried in regional languages).
Format with clear actionable steps.""",

    "marine": """You are in specialized MARINE & COASTAL MODE.
Your mission is to protect fishermen, coastal vessels, and port operations using ocean state physics.
CRITICAL INSTRUCTIONS:
1. Craft Classification:
   - Artisanal / Traditional craft (<15m, wooden/FRP dinghies): High capsize hazard if Significant Wave Height (SWH) > 2.0m or Swell Period > 10s.
   - Deep-sea mechanized trawlers: Unsafe if SWH > 3.5m or Gale wind > 45 km/h.
2. Tidal & Harbor Operations: Provide tidal heights and safe harbor docking windows.
3. Issue a direct ENTRY CLEARANCE or SUSPENSION ADVISORY.
Format with sea-state telemetry parameters.""",

    "home": """You are in PERSONAL / HOME / FLASH MODE.
Your mission is to assist with everyday lifestyle decisions as well as general knowledge and coding:
1. Everyday Weather & Living: Translate local weather into lifestyle decisions (umbrellas, laundry drying windows, outdoor fitness/running AQI checks, AC dry mode vs cooling).
2. General : If the user asks general questions, math problems, or LeetCode/algorithm challenges, solve them with clear explanations.
Keep responses concise, friendly, and practical.""",

    "alert": """You are in DISASTER EARLY WARNING MODE.
Your mission is to communicate IMD cyclone tracks, CWC river basin levels, and severe thunderstorm alerts.
CRITICAL INSTRUCTIONS:
1. Give exact coordinates, movement speed, and landfall ETA.
2. State official IMD color alert (Red / Orange / Yellow).
3. Provide concrete life-safety and evacuation directives."""
}


def query_gemini(user_query: str, mode: str = "home", weather_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Sends structured prompt and telemetry context to Gemini 2.5 Flash.
    Returns markdown response.
    """
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key:
        return "WeatherGPT Engine: Please set GEMINI_API_KEY in backend/.env"

    system_instruction = f"{CORE_AI_INSTRUCTIONS}\n\n{SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS['home'])}"

    prompt = f"{system_instruction}\n\n"
    if weather_context:
        prompt += f"REAL-TIME METEOROLOGICAL CONTEXT:\n{json.dumps(weather_context, indent=2)}\n\n"
    prompt += f"USER QUERY:\n{user_query}\n\nProvide an intelligent, situation-specific, actionable answer:"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 1024
        }
    }

    url = f"{GEMINI_ENDPOINT}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return "No response generated by Gemini."
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return f"Gemini API Error ({e.code}): {err_msg}"
    except Exception as e:
        return f"WeatherGPT Connection Error: {str(e)}"
