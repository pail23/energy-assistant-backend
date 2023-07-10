"""Views for home measurement API."""


import uuid

from fastapi import APIRouter, Depends, Path, Request

from app.models import DeviceSchema

from .schema import (
    ReadAllDevicesResponse,
    ReadDeviceMeasurementsResponse,
    ReadDeviceResponse,
)
from .use_cases import DeleteDevice, ReadAllDevices, ReadDevice, ReadDeviceMeasurements

router = APIRouter(prefix="/devices")


@router.get("", response_model=ReadAllDevicesResponse)
async def read_all(
    request: Request,
    use_case: ReadAllDevices = Depends(ReadAllDevices)
) -> ReadAllDevicesResponse:
    """Rest end point for read all devices."""
    return ReadAllDevicesResponse(devices=[device async for device in use_case.execute()])


@router.get(
    "/{device_id}",
    response_model=ReadDeviceResponse,
)
async def read(
    request: Request,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: ReadDevice = Depends(ReadDevice),
) -> DeviceSchema:
    """REST end pont for read a device."""
    return await use_case.execute(device_id)

@router.get(
    "/{device_id}/measurements"
)
async def read_measurements(
    request: Request,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: ReadDeviceMeasurements = Depends(ReadDeviceMeasurements),
) -> ReadDeviceMeasurementsResponse:
    """REST end pont for read a device."""
    return ReadDeviceMeasurementsResponse(device_measurements=[device_measurement async for device_measurement in use_case.execute(device_id)])



@router.delete("/{device_id}", status_code=204)
async def delete(
    request: Request,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: DeleteDevice = Depends(DeleteDevice),
) -> None:
    """REST end point for delete a device."""
    await use_case.execute(device_id)
