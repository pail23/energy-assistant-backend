"""Views for home measurement API."""

from datetime import date
from typing import Annotated

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
    request: Request,
    use_case: Annotated[ReadAllHomeMeasurement, Depends(ReadAllHomeMeasurement)],
) -> ReadAllHomeMeasurementResponse:
    """Get all home measurements."""
    return ReadAllHomeMeasurementResponse(
        home_measurements=[home_measurement async for home_measurement in use_case.execute()],
    )


@router.get(
    "/{home_measurement_id}",
    response_model=ReadHomeMeasurementResponse,
)
async def read(
    request: Request,
    home_measurement_id: Annotated[int, Path(..., description="ID of the home measurement")],
    use_case: Annotated[ReadHomeMeasurement, Depends(ReadHomeMeasurement)],
) -> HomeMeasurementSchema:
    """Get a home measurement by ID."""
    return await use_case.execute(home_measurement_id)


@router.get(
    "/by_date/{measurement_date}",
    response_model=ReadHomeMeasurementResponse,
)
async def read_by_date(
    request: Request,
    measurement_date: Annotated[date, Path(..., description="Date of the measurement")],
    use_case: Annotated[ReadHomeMeasurementByDate, Depends(ReadHomeMeasurementByDate)],
) -> HomeMeasurementSchema:
    """Get a home measurement by date."""
    return await use_case.execute(measurement_date)


@router.get(
    "/before_date/{measurement_date}",
    response_model=ReadHomeMeasurementResponse,
)
async def read_before_date(
    request: Request,
    measurement_date: Annotated[date, Path(..., description="Date before which to find measurement")],
    use_case: Annotated[ReadHomeMeasurementLastBeforeDate, Depends(ReadHomeMeasurementLastBeforeDate)],
) -> HomeMeasurementSchema:
    """Get the last home measurement before a date."""
    return await use_case.execute(measurement_date)


@router.delete("/{home_measurement_id}", status_code=204)
async def delete(
    request: Request,
    home_measurement_id: Annotated[int, Path(..., description="ID of the home measurement to delete")],
    use_case: Annotated[DeleteHomeMeasurement, Depends(DeleteHomeMeasurement)],
) -> None:
    """Delete a home measurement."""
    await use_case.execute(home_measurement_id)
