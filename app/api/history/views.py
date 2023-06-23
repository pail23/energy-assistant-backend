"""Views for home measurement API."""

from datetime import date
from typing import Union

from fastapi import APIRouter, Depends, Path, Request

from .schema import (
    HomeMeasurementDifferenceSchema,
    ReadHomeMeasurementDifferenceResponse,
)
from .use_cases import ReadHomeMeasurementDifference

router = APIRouter(prefix="/history")


@router.get(
    "/difference/{from_date}",
    response_model=ReadHomeMeasurementDifferenceResponse,
)
async def read_difference(
    request: Request,
    from_date: date = Path(..., description=""),
    to_date: Union[date, None] = None,
    use_case: ReadHomeMeasurementDifference = Depends(ReadHomeMeasurementDifference),
) -> HomeMeasurementDifferenceSchema:
    """Get the difference of the measurements between to dates."""
    return await use_case.execute(from_date, to_date)
