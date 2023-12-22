"""Use cases for devices."""

from energy_assistant.EmhassOptimizer import EmhassOptimizer
from energy_assistant.models.forecast import ForecastSchema

from .schema import CreateModelResponse, TuneModelResponse


class ReadForecast:
    """Read the forecast."""

    async def execute(self, optimizer: EmhassOptimizer) -> ForecastSchema:
        """Execute the read all devices use case."""
        if optimizer is not None:
            return optimizer.get_forecast()


class CreateModel:
    """Create the forecast model."""

    async def execute(self, optimizer: EmhassOptimizer) -> CreateModelResponse:
        """Execute the create model use case."""
        r2 = optimizer.forecast_model_fit(False)
        return CreateModelResponse(r2=r2)


class TuneModel:
    """Create the forecast model."""

    async def execute(self, optimizer: EmhassOptimizer) -> TuneModelResponse:
        """Execute the create model use case."""
        optimizer.forecast_model_tune()
        return TuneModelResponse(model="Tuned")
