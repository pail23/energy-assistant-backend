"""Views for device API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from energy_assistant.models.schema import DeviceSchema

from ..base import get_energy_assistant, get_home
from .schema import (
    CreateDeviceRequest,
    CreateDeviceResponse,
    ReadAllDevicesResponse,
    ReadDeviceMeasurementsResponse,
    ReadDeviceResponse,
    UpdateDevicePowerModeRequest,
    UpdateDevicePowerModeResponse,
)
from .use_cases import (
    CreateDevice,
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
    filter_with_session_log_enties: bool,
    use_case: Annotated[ReadAllDevices, Depends(ReadAllDevices)],
) -> ReadAllDevicesResponse:
    """Get all devices."""
    energy_assistant = get_energy_assistant(request)
    return ReadAllDevicesResponse(
        devices=[
            device
            async for device in use_case.execute(
                energy_assistant.home,
                filter_with_session_log_enties,
            )
        ],
    )


@router.post("", response_model=CreateDeviceResponse, status_code=201)
async def create(
    request: Request,
    data: CreateDeviceRequest,
    use_case: Annotated[CreateDevice, Depends(CreateDevice)],
) -> CreateDeviceResponse:
    """Create a new device."""
    energy_assistant = get_energy_assistant(request)
    device_id = await use_case.execute(data.device_type, data.device_name, data.config, energy_assistant.home)
    return CreateDeviceResponse(device_id=str(device_id))


@router.get(
    "/{device_id}",
    response_model=ReadDeviceResponse,
)
async def read(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="ID of the device")],
    use_case: Annotated[ReadDevice, Depends(ReadDevice)],
) -> DeviceSchema:
    """Get a device by ID."""
    home = get_home(request)
    return await use_case.execute(device_id, home)


@router.get("/{device_id}/measurements")
async def read_measurements(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="ID of the device")],
    use_case: Annotated[ReadDeviceMeasurements, Depends(ReadDeviceMeasurements)],
) -> ReadDeviceMeasurementsResponse:
    """Get device measurements."""
    return ReadDeviceMeasurementsResponse(
        device_measurements=[device_measurement async for device_measurement in use_case.execute(device_id)],
    )


@router.put(
    "/{device_id}/power_mode",
    response_model=UpdateDevicePowerModeResponse,
)
async def update_power_mode(
    request: Request,
    data: UpdateDevicePowerModeRequest,
    device_id: Annotated[uuid.UUID, Path(..., description="ID of the device to update")],
    use_case: Annotated[UpdateDevicePowerMode, Depends(UpdateDevicePowerMode)],
) -> DeviceSchema:
    """Update the power mode of a device."""
    home = get_home(request)
    return await use_case.execute(device_id, data.power_mode, home)


@router.delete("/{device_id}", status_code=204)
async def delete(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="ID of the device to delete")],
    use_case: Annotated[DeleteDevice, Depends(DeleteDevice)],
) -> None:
    """Delete a device."""
    energy_assistant = get_energy_assistant(request)
    await use_case.execute(device_id, energy_assistant.home)
