"""Views for home measurement API."""

from datetime import date

from fastapi import APIRouter, Depends, Path, Request

from energy_assistant.models.schema import HomeMeasurementSchema

from .schema import ReadAllHomeMeasurementResponse, ReadHomeMeasurementResponse
from .use_cases import (
    DeleteHomeMeasurement,
    ReadAllHomeMeasurement,
    ReadHomeMeasurement,
    ReadHomeMeasurementByDate,
    ReadHomeMeasurementLastBeforeDate,
)

router = APIRouter(prefix="/homemeasurements")


@router.get("", response_model=ReadAllHomeMeasurementResponse)
async def read_all(
    request: Request, use_case: ReadAllHomeMeasurement = Depends(ReadAllHomeMeasurement)
) -> ReadAllHomeMeasurementResponse:
    """Rest end point for read all home measurements."""
    return ReadAllHomeMeasurementResponse(
        home_measurements=[home_measurement async for home_measurement in use_case.execute()]
    )


@router.get(
    "/{HomeMeasurement_id}",
    response_model=ReadHomeMeasurementResponse,
)
async def read(
    request: Request,
    home_measurement_id: int = Path(..., description=""),
    use_case: ReadHomeMeasurement = Depends(ReadHomeMeasurement),
) -> HomeMeasurementSchema:
    """REST end pont for read a home measurement."""
    return await use_case.execute(home_measurement_id)


@router.get(
    "/by_date/{measurement_date}",
    response_model=ReadHomeMeasurementResponse,
)
async def read_by_date(
    request: Request,
    measurement_date: date = Path(..., description=""),
    use_case: ReadHomeMeasurementByDate = Depends(ReadHomeMeasurementByDate),
) -> HomeMeasurementSchema:
    """REST end pont for read a home measurement by date."""
    return await use_case.execute(measurement_date)


@router.get(
    "/before_date/{measurement_date}",
    response_model=ReadHomeMeasurementResponse,
)
async def read_before_date(
    request: Request,
    measurement_date: date = Path(..., description=""),
    use_case: ReadHomeMeasurementLastBeforeDate = Depends(ReadHomeMeasurementLastBeforeDate),
) -> HomeMeasurementSchema:
    """REST end pont for read the last home measurement before a date."""
    return await use_case.execute(measurement_date)


@router.delete("/{HomeMeasurement_id}", status_code=204)
async def delete(
    request: Request,
    home_measurement_id: int = Path(..., description=""),
    use_case: DeleteHomeMeasurement = Depends(DeleteHomeMeasurement),
) -> None:
    """REST end point for delete a home measurement."""
    await use_case.execute(home_measurement_id)
