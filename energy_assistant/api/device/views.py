"""Views for home measurement API."""


import uuid

from fastapi import APIRouter, Depends, Path, Request

from energy_assistant.models.schema import DeviceSchema

from .schema import (
    ReadAllDevicesResponse,
    ReadDeviceMeasurementsResponse,
    ReadDeviceResponse,
    UpdateDevicePowerModeRequest,
    UpdateDevicePowerModeResponse,
)
from .use_cases import (
    DeleteDevice,
    ReadAllDevices,
    ReadDevice,
    ReadDeviceMeasurements,
    UpdateDevicePowerMode,
)

router = APIRouter(prefix="/devices")


@router.get("", response_model=ReadAllDevicesResponse)
async def read_all(
    request: Request,
    filter_with_session_log_enties: bool = False,
    use_case: ReadAllDevices = Depends(ReadAllDevices),
) -> ReadAllDevicesResponse:
    """Rest end point for read all devices."""
    home = request.app.home if hasattr(request.app, "home") else None
    return ReadAllDevicesResponse(
        devices=[device async for device in use_case.execute(home, filter_with_session_log_enties)]
    )


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
    return await use_case.execute(device_id, request.app.home)


@router.get("/{device_id}/measurements")
async def read_measurements(
    request: Request,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: ReadDeviceMeasurements = Depends(ReadDeviceMeasurements),
) -> ReadDeviceMeasurementsResponse:
    """REST end pont for read a device."""
    return ReadDeviceMeasurementsResponse(
        device_measurements=[
            device_measurement async for device_measurement in use_case.execute(device_id)
        ]
    )


@router.put(
    "/{device_id}/power_mode",
    response_model=UpdateDevicePowerModeResponse,
)
async def update_power_mode(
    request: Request,
    data: UpdateDevicePowerModeRequest,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: UpdateDevicePowerMode = Depends(UpdateDevicePowerMode),
) -> DeviceSchema:
    """Update the power mode of a device."""
    return await use_case.execute(device_id, data.power_mode, request.app.home)


@router.delete("/{device_id}", status_code=204)
async def delete(
    request: Request,
    device_id: uuid.UUID = Path(..., description=""),
    use_case: DeleteDevice = Depends(DeleteDevice),
) -> None:
    """REST end point for delete a device."""
    home = request.app.home if hasattr(request.app, "home") else None
    await use_case.execute(device_id, home)
