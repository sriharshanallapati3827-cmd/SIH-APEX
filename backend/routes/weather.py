from fastapi import APIRouter
from services.weather_service import get_current_weather_by_coords, get_current_weather_by_city, get_weather_summary_by_location

router = APIRouter()

@router.get("/weather")
def get_weather(latitude: float, longitude: float):
    return get_current_weather_by_coords(latitude, longitude)

@router.get("/weather-by-city")
def get_weather_by_city(city: str):
    return get_current_weather_by_city(city)

@router.get("/weather-by-location")
def get_weather_by_location(latitude: float, longitude: float):
    return get_weather_summary_by_location(latitude, longitude)
