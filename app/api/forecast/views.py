"""Views for home measurement API."""



from fastapi import APIRouter, Depends, Request

from app.models.forecast import ForecastSchema

from .use_cases import ReadForecast

router = APIRouter(prefix="/forecast")


@router.get("", response_model=ForecastSchema)
async def read_all(
    request: Request,
    use_case: ReadForecast = Depends(ReadForecast)
) -> ForecastSchema:
    """Rest end point for read all devices."""
    return await use_case.execute(request.app.optimizer)
