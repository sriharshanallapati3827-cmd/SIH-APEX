from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseWeatherProvider(ABC):
    """
    Abstract interface for Weather Data Providers.
    Allows seamless switching between Open-Meteo (MVP active) and future providers (e.g. IMD).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the weather provider."""
        pass

    @abstractmethod
    def get_current_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Fetch current weather data for given GPS coordinates."""
        pass

    @abstractmethod
    def get_forecast(self, latitude: float, longitude: float, period: str = "next_7_days") -> Dict[str, Any]:
        """Fetch forecast data for given GPS coordinates and period."""
        pass

    @abstractmethod
    def get_alerts(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Fetch or derive weather alerts for given GPS coordinates."""
        pass
