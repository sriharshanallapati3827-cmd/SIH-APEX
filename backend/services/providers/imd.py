import os
from typing import Dict, Any
from fastapi import HTTPException
from .base import BaseWeatherProvider


class IMDProvider(BaseWeatherProvider):
    """
    Optional / Future Weather Provider for India Meteorological Department (IMD) API.
    Does not run or claim data unless valid official credentials are configured in .env.
    """

    def __init__(self):
        self.api_key = os.getenv("IMD_API_KEY")
        self.base_url = os.getenv("IMD_BASE_URL", "https://api.imd.gov.in")

    @property
    def name(self) -> str:
        return "IMD"

    def is_configured(self) -> bool:
        """Check if required IMD credentials and configuration are present."""
        return bool(self.api_key and self.api_key.strip())

    def _ensure_configured(self):
        """Raise a clean 503 error if IMD credentials are not set."""
        if not self.is_configured():
            raise HTTPException(
                status_code=503,
                detail=(
                    "IMD weather provider is selected, but official IMD credentials (IMD_API_KEY) "
                    "are not configured in .env. Please set WEATHER_PROVIDER=open_meteo for the MVP, "
                    "or provide valid IMD credentials to enable this provider."
                )
            )

    def get_current_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        self._ensure_configured()
        # Future implementation once official IMD API credentials and endpoints are acquired:
        # response = requests.get(f"{self.base_url}/current", headers={"Authorization": f"Bearer {self.api_key}"}, ...)
        raise HTTPException(
            status_code=501,
            detail="IMD current weather endpoint integration pending official API release/documentation."
        )

    def get_forecast(self, latitude: float, longitude: float, period: str = "next_7_days") -> Dict[str, Any]:
        self._ensure_configured()
        raise HTTPException(
            status_code=501,
            detail="IMD forecast endpoint integration pending official API release/documentation."
        )

    def get_alerts(self, latitude: float, longitude: float) -> Dict[str, Any]:
        self._ensure_configured()
        raise HTTPException(
            status_code=501,
            detail="IMD alerts endpoint integration pending official API release/documentation."
        )
