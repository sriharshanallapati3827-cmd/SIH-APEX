from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    mode: Optional[str] = "home"
    lang: Optional[str] = "en"
    latitude: float | None = None
    longitude: float | None = None
    session_id: Optional[str] = None
    previous_context: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None


class QueryUnderstanding(BaseModel):
    intent: str
    city: Optional[str] = None
    location: Optional[str] = None
    forecast_period: Optional[str] = None
    time_period: Optional[str] = None
    weather_variable: Optional[str] = None
    requires_location: bool = False

