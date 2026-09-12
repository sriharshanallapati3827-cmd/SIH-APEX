from fastapi import APIRouter
from services.weather_service import get_alerts_by_city

router = APIRouter()

@router.get("/alerts")
def get_alerts(city: str):
    return get_alerts_by_city(city)
