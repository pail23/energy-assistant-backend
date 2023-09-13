"""Use cases for devices."""

from app.EmhassOptimizer import EmhassOptimizer
from app.models.forecast import ForecastSchema


class ReadForecast:
    """Read the forecast."""

    async def execute(self, optimizer: EmhassOptimizer) -> ForecastSchema:
        """Execute the read all devices use case."""
        if optimizer is not None:
            return optimizer.get_forecast()
