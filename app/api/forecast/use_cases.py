"""Use cases for devices."""

from app.EmhassOptimzer import EmhassOptimzer
from app.models.forecast import ForecastSchema


class ReadForecast:
    """Read the forecast."""

    async def execute(self, optimizer: EmhassOptimzer) -> ForecastSchema:
        """Execute the read all devices use case."""
        if optimizer is not None:
            return optimizer.get_forecast()
