"""Views for history API."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from .schema import (
    HomeMeasurementDailyResponse,
    HomeMeasurementDailySchema,
    HomeMeasurementPeriodSchema,
    ReadHomeMeasurementDifferenceResponse,
)
from .use_cases import ReadHomeMeasurementDaily, ReadHomeMeasurementDifference

router = APIRouter(prefix="/history")


@router.get(
    "/difference",
    response_model=ReadHomeMeasurementDifferenceResponse,
)
async def read_difference(
    request: Request,
    from_date: date,
    to_date: date,
    use_case: Annotated[ReadHomeMeasurementDifference, Depends(ReadHomeMeasurementDifference)],
) -> HomeMeasurementPeriodSchema:
    """Get the measurement difference between two dates."""
    return await use_case.execute(from_date, to_date)


@router.get(
    "/daily",
    response_model=HomeMeasurementDailyResponse,
)
async def read_daily(
    request: Request,
    from_date: date,
    to_date: date,
    use_case: Annotated[ReadHomeMeasurementDaily, Depends(ReadHomeMeasurementDaily)],
) -> HomeMeasurementDailySchema:
    """Get daily measurements between two dates."""
    return await use_case.execute(from_date, to_date)
