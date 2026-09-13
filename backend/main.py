import os
from pathlib import Path
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables before starting app
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)
load_dotenv()

from routes.weather import router as weather_router
from routes.forecast import router as forecast_router
from routes.alerts import router as alerts_router
from routes.ai import router as ai_router
from services.safety_guardrail import init_postgis_database

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="WeatherGPT", version="1.0.0")

@app.on_event("startup")
def on_startup():
    init_postgis_database()

# Enable CORS for frontend website
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(weather_router)
app.include_router(forecast_router)
app.include_router(alerts_router)
app.include_router(ai_router)

@app.get("/")
def home():
    return {"message": "Welcome to WeatherGPT"}
