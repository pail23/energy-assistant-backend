"""Views for home measurement API."""


import uuid

from fastapi import APIRouter, Depends, Path, Request

from app.models.device import DeviceSchema

from .schema import ReadAllDevicesResponse, ReadDeviceResponse
from .use_cases import DeleteDevice, ReadAllDevices, ReadDevice

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


@router.delete("/{device_id}", status_code=204)
async def delete(
    request: Request,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: DeleteDevice = Depends(DeleteDevice),
) -> None:
    """REST end point for delete a device."""
    await use_case.execute(device_id)
