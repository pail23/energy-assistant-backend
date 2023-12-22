"""Views for home measurement API."""


from fastapi import APIRouter, Depends, Request

from energy_assistant.models.forecast import ForecastSchema

from .schema import CreateModelResponse, TuneModelResponse
from .use_cases import CreateModel, ReadForecast, TuneModel

router = APIRouter(prefix="/forecast")


@router.get("", response_model=ForecastSchema)
async def read_all(
    request: Request, use_case: ReadForecast = Depends(ReadForecast)
) -> ForecastSchema:
    """Rest end point for read all devices."""
    return await use_case.execute(request.app.optimizer)


@router.post("/create_model", response_model=CreateModelResponse)
async def create_model(
    request: Request, use_case: CreateModel = Depends(CreateModel)
) -> CreateModelResponse:
    """Create the machine learning forecast model."""
    return await use_case.execute(request.app.optimizer)


@router.post("/tune_model", response_model=TuneModelResponse)
async def tune_model(
    request: Request, use_case: TuneModel = Depends(TuneModel)
) -> TuneModelResponse:
    """Tune the machine learning forecast model."""
    return await use_case.execute(request.app.optimizer)
