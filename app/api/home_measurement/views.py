"""Views for home measurement API."""

from fastapi import APIRouter, Depends, Path, Request

from app.models.home import HomeMeasurementSchema

from .schema import ReadAllHomeMeasurementResponse, ReadHomeMeasurementResponse
from .use_cases import (
    DeleteHomeMeasurement,
    ReadAllHomeMeasurement,
    ReadHomeMeasurement,
)

router = APIRouter(prefix="/homemeasurements")


@router.get("", response_model=ReadAllHomeMeasurementResponse)
async def read_all(
    request: Request, use_case: ReadAllHomeMeasurement = Depends(ReadAllHomeMeasurement)
) -> ReadAllHomeMeasurementResponse:
    """Rest end point for read all home measurements."""
    return ReadAllHomeMeasurementResponse(home_measurements=[home_measurement async for home_measurement in use_case.execute()])


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


@router.delete("/{HomeMeasurement_id}", status_code=204)
async def delete(
    request: Request,
    home_measurement_id: int = Path(..., description=""),
    use_case: DeleteHomeMeasurement = Depends(DeleteHomeMeasurement),
) -> None:
    """REST end point for delete a home measurement."""
    await use_case.execute(home_measurement_id)
