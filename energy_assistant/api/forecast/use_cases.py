"""Use cases for devices."""

from fastapi import HTTPException

from energy_assistant.emhass_optimizer import EmhassOptimizer
from energy_assistant.models.forecast import ForecastSchema

from .schema import CreateModelResponse, TuneModelResponse


class ReadForecast:
    """Read the forecast."""

    async def execute(self, optimizer: EmhassOptimizer) -> ForecastSchema:
        """Execute the read all devices use case."""
        if optimizer is not None:
            return await optimizer.async_get_forecast()
        return None


class CreateModel:
    """Create the forecast model."""

    async def execute(self, days_to_retrieve: int, optimizer: EmhassOptimizer) -> CreateModelResponse:
        """Execute the create model use case."""
        try:
            r2 = optimizer.forecast_model_fit(False, days_to_retrieve)
            return CreateModelResponse(r2=r2)
        except UnboundLocalError as err:
            raise HTTPException(status_code=400, detail="Creation of the model failed.") from err


class TuneModel:
    """Create the forecast model."""

    async def execute(self, optimizer: EmhassOptimizer) -> TuneModelResponse:
        """Execute the create model use case."""
        optimizer.forecast_model_tune()
        return TuneModelResponse(model="Tuned")
