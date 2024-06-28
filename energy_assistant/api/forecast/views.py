"""Views for home measurement API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from energy_assistant.models.forecast import ForecastSchema

from .schema import CreateModelResponse, TuneModelResponse
from .use_cases import CreateModel, ReadForecast, TuneModel

router = APIRouter(prefix="/forecast")


@router.get("", response_model=ForecastSchema)
async def read_all(request: Request, use_case: Annotated[ReadForecast, Depends(ReadForecast)]) -> ForecastSchema:
    """Rest end point for read all devices."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(energy_assistant.optimizer)


@router.post("/create_model", response_model=CreateModelResponse)
async def create_model(
    request: Request,
    days_to_retrieve: int,
    use_case: Annotated[CreateModel, Depends(CreateModel)],
) -> CreateModelResponse:
    """Create the machine learning forecast model."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(days_to_retrieve, energy_assistant.optimizer)


@router.post("/tune_model", response_model=TuneModelResponse)
async def tune_model(request: Request, use_case: Annotated[TuneModel, Depends(TuneModel)]) -> TuneModelResponse:
    """Tune the machine learning forecast model."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(energy_assistant.optimizer)
