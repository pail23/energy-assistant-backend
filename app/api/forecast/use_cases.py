"""Use cases for devices."""

from app.models.forecast import ForecastSchema
from app.optimizer import EmhassOptimzer


class ReadForecast:
    """Read the forecast."""

    async def execute(self, optimizer: EmhassOptimzer) -> ForecastSchema:
        """Execute the read all devices use case."""
        if optimizer is not None:
            return optimizer.get_forecast()
