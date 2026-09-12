# WeatherGPT — Architecture

## Project

**Name:** WeatherGPT  
**Event:** Smart India Hackathon (SIH) 2026  
**Purpose:** An AI-powered weather assistant that understands natural language questions and returns real weather data.

---

## Repository Layout

```
WeatherGPT/
├── ARCHITECTURE.md          ← Architecture and provider strategy
├── CURRENT_STATUS.md        ← Phase status tracking
└── backend/
    ├── main.py              ← FastAPI application & router registration
    ├── routes/              ← API endpoint routers
    │   ├── weather.py       ← Current weather endpoints
    │   ├── forecast.py      ← Forecast endpoints
    │   ├── alerts.py        ← Advisory and alert endpoints
    │   └── ai.py            ← AI query engine (/ask, /understand, /ask-demo)
    ├── services/            ← Business logic & integrations
    │   ├── weather_service.py   ← Central provider-agnostic weather service
    │   ├── weather_context.py   ← Context pipeline: maps QueryUnderstanding to compact weather data
    │   ├── geocoding_service.py ← Geocoding via Open-Meteo
    │   ├── ai_service.py        ← OpenAI integration & structured NLU
    │   └── providers/       ← Weather data providers
    │       ├── base.py          ← Abstract BaseWeatherProvider interface
    │       ├── open_meteo.py    ← Active MVP provider
    │       └── imd.py           ← Future/optional IMD provider
    ├── models/              ← Pydantic schemas (ChatRequest, QueryUnderstanding)
    ├── .env                 ← API keys & provider config (gitignored)
    ├── .env.example         ← Template for environment configuration
    ├── .gitignore           ← Ignores .env, venv/, __pycache__/, *.log
    └── venv/                ← Python virtual environment (gitignored)
```

---

## Weather Provider Architecture & Query Pipeline

```
Frontend / Clients
       ↓
Backend API Routes (/weather, /forecast, /alerts, /ask)
       ↓
AI Query Understanding (understand_query)
       ↓
Structured QueryUnderstanding
       ↓
Weather Context Pipeline (build_weather_context)
       ↓
weather_service.py (Provider-Agnostic Abstraction Layer)
       ↓
BaseWeatherProvider Interface
       ├── OpenMeteoProvider  ← ACTIVE MVP PROVIDER (Default, Keyless)
       └── IMDProvider        ← FUTURE OPTIONAL PROVIDER (Requires IMD_API_KEY)
```

- **Active MVP Provider**: Open-Meteo provides global and pan-India weather, multi-period forecasts, hourly data, and condition advisories without requiring credentials.
- **Future IMD Integration**: `IMDProvider` is prepared to interface with official India Meteorological Department APIs when credentials become available (`WEATHER_PROVIDER=imd` and `IMD_API_KEY`). It safely raises HTTP 503 if selected without credentials.
- **Transparency**: Data returned explicitly notes its provider source (`"source": "Open-Meteo"`). Advisories derived from forecast metrics are clearly identified as automated condition-based advisories, not official IMD government warnings.

---

## Backend Stack

| Layer               | Technology                                      |
|---------------------|-------------------------------------------------|
| Framework           | FastAPI                                         |
| Server              | Uvicorn (--reload in dev)                       |
| AI / NLU            | OpenAI API (client.responses)                   |
| Active Weather MVP  | Open-Meteo (free, keyless)                      |
| Optional/Future API | IMD (India Meteorological Department)           |
| Geocoding           | Open-Meteo Geocoding API                        |
| Config              | python-dotenv (.env)                            |
| Language            | Python 3.x                                      |

---

## Endpoints

### Non-AI Endpoints (no OpenAI dependency)

| Method | Path                   | Parameters                                | Description                                      |
|--------|------------------------|-------------------------------------------|--------------------------------------------------|
| GET    | `/`                    | —                                         | Health check / welcome message                   |
| GET    | `/weather`             | `latitude`, `longitude`                   | Raw current weather by GPS coordinates           |
| GET    | `/weather-by-city`     | `city`                                    | Geocode city → fetch current weather + metadata  |
| GET    | `/forecast`            | `city`, optional `period`                 | Forecast by city (today, tomorrow, 7-day, etc.)  |
| GET    | `/alerts`              | `city`                                    | Condition-derived weather advisories             |
| GET    | `/weather-by-location` | `latitude`, `longitude`                   | Clean normalized current weather summary by GPS  |
| GET    | `/chat`                | `message`                                 | Keyword-based chat fallback (no AI)              |
| POST   | `/ask-demo`            | body: `{message, latitude?, longitude?}`  | Grounded NLU demo — no OpenAI dependency         |

### AI Endpoints (require OpenAI credits)

| Method | Path          | Parameters                                | Description                                              |
|--------|---------------|-------------------------------------------|----------------------------------------------------------|
| GET    | `/ai-test`    | `message`                                 | Direct OpenAI call, returns raw answer                   |
| GET    | `/understand` | `message`                                 | NLU: returns structured JSON from OpenAI                 |
| POST   | `/ask`        | body: `{message, latitude?, longitude?}`  | Full pipeline: NLU → weather fetch → AI natural answer   |

---

## Environment Variables

| Variable           | Default      | Description                                                |
|--------------------|--------------|------------------------------------------------------------|
| `OPENAI_API_KEY`   | None         | Required by AI endpoints (`/ai-test`, `/understand`, `/ask`)|
| `WEATHER_PROVIDER` | `open_meteo` | Active weather provider (`open_meteo` or `imd`)            |
| `IMD_API_KEY`      | None         | Optional future IMD API key (not required for MVP)         |
| `IMD_BASE_URL`     | None         | Optional future IMD API base URL                           |
