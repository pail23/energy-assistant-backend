"""Views for home measurement API."""

import uuid
from typing import Annotated

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
    filter_with_session_log_enties: bool,
    use_case: Annotated[ReadAllDevices, Depends(ReadAllDevices)],
) -> ReadAllDevicesResponse:
    """Rest end point for read all devices."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    return ReadAllDevicesResponse(
        devices=[
            device
            async for device in use_case.execute(
                energy_assistant.home if energy_assistant is not None else None,
                filter_with_session_log_enties,
            )
        ],
    )


@router.get(
    "/{device_id}",
    response_model=ReadDeviceResponse,
)
async def read(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="")],
    use_case: Annotated[ReadDevice, Depends(ReadDevice)],
) -> DeviceSchema:
    """REST end point for read a device."""
    return await use_case.execute(device_id, request.app.home)


@router.get("/{device_id}/measurements")
async def read_measurements(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="")],
    use_case: Annotated[ReadDeviceMeasurements, Depends(ReadDeviceMeasurements)],
) -> ReadDeviceMeasurementsResponse:
    """REST end point for read a device."""
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
    device_id: Annotated[uuid.UUID, Path(..., description="")],
    use_case: Annotated[UpdateDevicePowerMode, Depends(UpdateDevicePowerMode)],
) -> DeviceSchema:
    """Update the power mode of a device."""
    return await use_case.execute(device_id, data.power_mode, request.app.home)


@router.delete("/{device_id}", status_code=204)
async def delete(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="")],
    use_case: Annotated[DeleteDevice, Depends(DeleteDevice)],
) -> None:
    """REST end point for delete a device."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    await use_case.execute(device_id, energy_assistant.home if energy_assistant is not None else None)
