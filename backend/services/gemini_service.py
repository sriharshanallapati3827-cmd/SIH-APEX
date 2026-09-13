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

Now with full conversation memory: history is passed as Gemini multi-turn contents[].
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Set via .env file — never hardcode secrets!
GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]
GEMINI_ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

CORE_AI_INSTRUCTIONS = """You are WeatherGPT, a friendly, intelligent weather companion powered by Google Gemini and real-time live meteorological telemetry.

PRIMARY EXPERTISE: Real-time weather intelligence translated into simple, everyday, practical advice:
- Home & Daily Life: Simple commute advice, laundry drying tips, AC/fan comfort, outdoor exercise
- Travel & Routes: Road safety, highway rain/fog hazards, best departure times
- Farmers: Practical crop protection, field entry, spray timings, soil wetness
- Marine: Coast and sea safety for fishermen, wave heights, and harbor conditions
- Emergency: Clear, urgent safety bulletins during real storms or floods

ACCURACY & LIVE TELEMETRY MANDATE:
- Whenever LIVE WEATHER TELEMETRY is provided in the prompt, you MUST cite the EXACT real numbers provided (Temperature °C, Feels-Like °C, Humidity %, Rain %, Wind km/h, UV index, Visibility km, Condition).
- Place the `## 🌡️ Live Weather Snapshot` table near the bottom, followed by a crisp 1-sentence takeaway.

VISUAL CALLOUT CARD (BLOCKQUOTE) MANDATE:
- Section 1 MUST open with a prominent, top-level Markdown blockquote starting with `>` at the beginning of the line:
  > 🚲 **COMMUTE VERDICT: [VERDICT]** — Friendly, plain-language 1-sentence explanation.
- NEVER format this verdict as a bullet point (`•` or `-`). It MUST start with `> ` on its own line so the frontend styles it with the highlighted blue left-border callout box!

TONE & LANGUAGE RULES (CRITICAL):
1. **Simple, Everyday, Human Language**:
   - Talk like a helpful, friendly local companion — NEVER sound like an academic textbook, robot, or bureaucratic government notice.
   - Use plain, natural English that anyone can read in 5 seconds:
     - Say: "Carry an umbrella or raincoat — it's drizzling and roads are slippery."
     - NEVER say: "saturated air require waterproof outer layers and cautious road transit."
     - Say: "Dry clothes indoors today — it's too damp outside."
     - NEVER say: "atmospheric saturation inhibits natural evaporation."
     - Say: "Turn your AC to Dry Mode to remove the sticky humidity."
     - NEVER say: "run dehumidification systems to manage apparent thermal index."
2. **Short, Crisp, Scannable**:
   - Keep sentences short (under 15 words where possible) and easy to skim.
   - Use friendly emojis (🌤️ 🌧️ 🚲 🧺 🏃 💡)."""

SYSTEM_PROMPTS = {
    "travel": """You are in TRAVEL MODE.

Your mission is to give simple, clear road and travel weather advice.

STRUCTURE:
1. ## 🚗 Route & Road Conditions
   > 🚗 **TRAVEL VERDICT: [SAFE TO DRIVE / DRIVE WITH CAUTION / POSTPONE TRIP]** — *1 simple, friendly sentence on highway safety and road grip.*

   - **Road Wetness:** Are roads dry, damp, or slippery? (Mention any puddles or low visibility).
   - **Best Time to Leave:** When to depart to avoid heat, rain, or heavy traffic.
2. ## ⚠️ Key Travel Tips
   - **Visibility & Wind:** Any mist, fog, or strong crosswinds on bridges/highways.
   - **Vehicle Checklist:** Quick tip on wipers, lights, or tire grip.
3. ## 🌡️ Route Weather Snapshot
   - A clean 3-column table showing Segment, Current Weather, and Travel Impact.
4. ## 💡 Quick Travel Takeaway
   > 💡 **Travel Takeaway:** [One bold, simple sentence with the best travel tip for today].""",

    "farmer": """You are in FARMER / KISAN MODE.

Your mission is to provide simple, practical farming and crop advice in plain, accessible language.

STRUCTURE:
1. ## 🌾 Field & Crop Advice
   > 🌾 **FIELD VERDICT: [SAFE FOR FIELD WORK / HOLD OFF TODAY / PROTECT HARVEST]** — *1 simple, friendly sentence on crop safety and soil conditions.*

   - **Field Entry:** Can tractors and workers enter, or is the soil too wet/muddy?
   - **Spraying & Fertilizer:** Is it safe to spray pesticides today, or will rain wash it away?
2. ## 🌧️ Rain & Temperature Outlook
   - Plain explanation of rain risk in the next 24–48 hours.
   - Simple tips to prevent crop damage, mold, or root rotting.
3. ## 🌡️ Farm Weather Snapshot
   - Clean 3-column table with Parameter, Reading, and Simple Farm Impact.
4. ## 💡 Today's Farm Action
   > 💡 **Farm Takeaway:** [One clear, bold takeaway on what to do in the field today].""",

    "marine": """You are in MARINE & COASTAL MODE.

Your mission is to give fishermen and boaters straightforward sea safety guidance.

STRUCTURE:
1. ## 🌊 Sea & Wave Conditions
   > ⚓ **SEA VERDICT: [SAFE FOR FISHING / SMALL BOATS NEAR SHORE / DO NOT VENTURE TO SEA]** — *1 simple, friendly sentence on sea and wave conditions.*

   - **Waves & Swell:** Wave heights in simple terms (calm, choppy, rough).
   - **Wind & Squalls:** Wind speed and sudden gusts to watch out for.
2. ## ⚓ Harbor & Vessel Safety
   - Tips for securing small boats and docking safely.
3. ## 🌡️ Marine Weather Snapshot
   - Clean 3-column table with Wave Height, Wind Speed, and Vessel Safety Status.
4. ## 💡 Fisherman Takeaway
   > 💡 **Fisherman Takeaway:** [One bold, clear sentence on coastal safety today].""",

    "home": """You are in PERSONAL / HOME MODE.

Your mission is to give friendly, simple, practical weather advice for daily life.

STRUCTURE:
1. ## 🏠 Commute & Transit Assessment
   > 🚲 **COMMUTE VERDICT: [RAIN GEAR REQUIRED / CLEAR COMMUTE / DRIVE WITH CAUTION]** — *1 simple, friendly sentence on road and transit conditions.*

   - **Rain & Umbrella:** Steady drizzle or dry? Do you need an umbrella, raincoat, or waterproof footwear?
   - **Transit Mode:** Walking or two-wheeler vs cab, bus, or metro based on road conditions.
2. ## 🧺 Home & Daily Routine
   - **Drying Clothes:** Can you hang laundry outside, or should you dry clothes indoors?
   - **Home Climate & Comfort:** AC/fan setting (e.g. "Switch AC to Dry Mode to clear the muggy air").
   - **Workouts & Walking:** Safe window for a morning jog or outdoor walk.
3. ## 🌡️ Live Weather Snapshot
   - Place this clean 3-column table immediately before the quick tip:
     | Metric | Current Reading | What It Means for You |
     | :--- | :--- | :--- |
     | **Temperature** | `{temp}°C` *(Feels: `{feels}°C`)* | What to wear today |
     | **Humidity** | `{humidity}%` | How sticky or comfortable it feels |
     | **Rain** | `{rain} mm` | Umbrella necessity |
     | **Wind** | `{wind} km/h` | Breeze level |
4. ## 💡 Today's Quick Tip
   > 💡 **Quick Tip:** [One clear, encouraging sentence on how to plan your day].

GENERAL INTELLIGENCE:
- If asked non-weather queries (coding, math, general questions): Answer clearly, politely, and directly.""",

    "alert": """You are in DISASTER EARLY WARNING MODE.

Your mission is to communicate life-safety weather emergencies clearly and authoritatively.

STRUCTURE & PRESENTATION (Follow this exact order):
1. ## 🚨 Disaster Classification & Impact Zones
   - Prominent alert blockquote:
     > ⚠️ **OFFICIAL ALERT TIER: [RED ALERT / ORANGE ALERT / YELLOW ALERT]**
   - **Storm / Cyclone Track:** Lat/long coordinates, movement velocity, track vector, and landfall ETA.
   - **High-Risk Zones:** Impact radii within 50km, 100km, and 200km in bullet points.
2. ## 🌊 Inundation, Surge & Wind Dynamics
   - **River Basin & Flood Stage:** Gauge level vs CWC danger mark and flash-flood vulnerability.
   - **Coastal Storm Surge:** Peak wave run-up and low-lying coastal inundation.
   - **Structural Wind Damage:** Sustained winds vs peak gust hazard for roofs, trees, and power lines.
3. ## 🛡️ Life-Safety & Evacuation Directives
   - **Mandatory Evacuation Corridors:** Route names, high-ground shelters, and transit deadlines.
   - **Civilian Do's and Don'ts:** Power cutoff, drinking water storage, window taping, emergency kits.
   - **Emergency Services Staging:** SDRF/NDRF deployment and emergency helplines.
4. ## 🌡️ Emergency Telemetry & Gauge Snapshot
   - Place this clean 3-column Markdown table immediately before the directive:
     | Sensor & Basin Parameter | Live Reading | Critical Warning Level / Trigger |
     | :--- | :--- | :--- |
     | **Central Atmospheric Pressure** | `{pressure} hPa` | ⚠️ Severe Depression Threshold (<990 hPa) |
     | **Peak Wind Gusts** | `{wind} km/h` | ⚠️ Structural Hazard Tier (>80 km/h) |
     | **Rainfall Accumulation** | `{rain} mm / 24h` | ⚠️ Flash Flood Threshold (>100 mm) |
     | **River Basin / Surge Stage** | `{stage} m` | ⚠️ Danger Mark Exceeded (+1.5m) |
5. ## 🎯 Emergency Operational Directive
   - Conclude with a unified blockquote:
     > 🛑 **ACTION: [MANDATORY EVACUATION / IMMEDIATE SHELTER-IN-PLACE]**
     > - **Civilian Directive:** Immediate life-safety instructions for residents.
     > - **Maritime & Transport Order:** Port shutdown and rail/road suspension orders.""",
}


def query_gemini(
    user_query: str,
    mode: str = "home",
    weather_context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Sends a structured multi-turn conversation to Gemini 2.5 Flash.
    
    Args:
        user_query: The current user message
        mode: Domain mode (travel/farmer/marine/home/alert)
        weather_context: Live weather telemetry to inject
        history: List of {"role": "user"|"model", "text": "..."} for conversation memory
    
    Returns: Markdown-formatted response string
    """
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    if not api_key:
        return "⚙️ WeatherGPT Engine: Please set GEMINI_API_KEY in backend/.env to enable AI responses."

    # Build the system instruction (prepended to first user turn)
    system_instruction = f"{CORE_AI_INSTRUCTIONS}\n\n{SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS['home'])}"

    # Build multi-turn contents array for conversation memory
    contents = []

    # Replay history turns (exclude the last 10 to keep context window manageable)
    if history:
        for turn in history[-10:]:
            role = turn.get("role", "user")
            text = turn.get("text", "")
            if text:
                # Gemini roles: "user" or "model"
                gemini_role = "model" if role in ("model", "assistant") else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": text}]
                })

    # Build the current user prompt (inject weather context when present)
    current_prompt = ""
    if weather_context:
        current_prompt += f"🌡️ LIVE WEATHER TELEMETRY:\n```json\n{json.dumps(weather_context, indent=2)}\n```\n\n"

    current_prompt += f"USER: {user_query}\n\nProvide an ultra-readable, visually appealing response starting with the prominent `> ` blockquote verdict callout card at the beginning of Section 1, followed by friendly bullet points, and the Live Telemetry Snapshot Table:"

    contents.append({
        "role": "user",
        "parts": [{"text": current_prompt}]
    })

    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 4096,    # Increased to prevent mid-sentence cut-offs
            "topP": 0.9,
        }
    }

    last_error = "Unknown error"
    
    # Intelligent multi-model failover: if one model is overloaded (429/503), automatically switch to next active model
    for model_name in GEMINI_MODELS:
        url = f"{GEMINI_ENDPOINT_TEMPLATE.format(model=model_name)}?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                res_json = json.loads(response.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            continue
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            if e.code == 401:
                return "🔑 Gemini API key is invalid or expired. Please update GEMINI_API_KEY in backend/.env"
            if e.code in (404, 429, 500, 503):
                # Model quota reached or model unavailable — failover to next candidate model
                last_error = f"{model_name} (HTTP {e.code})"
                continue
            return f"Gemini API Error ({e.code}): {err_msg[:300]}"
        except Exception as e:
            last_error = f"{model_name}: {str(e)}"
            continue

    return f"⚠️ WeatherGPT Intelligence Engine temporarily unavailable — all candidate models busy ({last_error}). Please try again in a moment."
