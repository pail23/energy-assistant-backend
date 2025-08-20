"""Views for configuration API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from ..base import get_energy_assistant
from .schema import (
    ConfigModel,
    DeviceControlModel,
    ReadConfigResponse,
    ReadDeviceConfigResponse,
    ReadDeviceControlResponse,
    ReadVersionResponse,
    VersionModel,
)
from .use_cases import (
    ReadConfiguration,
    ReadDeviceConfiguration,
    ReadDeviceControl,
    ReadVersion,
    WriteDeviceConfiguration,
    WriteDeviceControl,
)

router = APIRouter(prefix="/config")


@router.get("", response_model=ReadConfigResponse)
async def read_configuration(
    request: Request,
    use_case: Annotated[ReadConfiguration, Depends(ReadConfiguration)],
) -> ConfigModel:
    """Get the configuration."""
    energy_assistant = get_energy_assistant(request)
    return await use_case.execute(energy_assistant.config)


@router.get("/version", response_model=ReadVersionResponse)
async def read_version(
    request: Request,
    use_case: Annotated[ReadVersion, Depends(ReadVersion)],
) -> VersionModel:
    """Get the version information."""

    return await use_case.execute()


@router.get("/device_control", response_model=ReadDeviceControlResponse)
async def read_device_control(
    request: Request,
    use_case: Annotated[ReadDeviceControl, Depends(ReadDeviceControl)],
) -> DeviceControlModel:
    """Get the device control configuration."""
    energy_assistant = get_energy_assistant(request)
    return await use_case.execute(energy_assistant.home)


@router.put("/device_control", response_model=ReadDeviceControlResponse)
async def write_device_control(
    request: Request,
    disable_device_control: bool,
    use_case: Annotated[WriteDeviceControl, Depends(WriteDeviceControl)],
) -> DeviceControlModel:
    """Update the device control configuration."""
    energy_assistant = get_energy_assistant(request)
    return await use_case.execute(disable_device_control, energy_assistant.home)


@router.get(
    "/device/{device_id}",
    response_model=ReadDeviceConfigResponse,
)
async def read(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="ID of the device")],
    use_case: Annotated[ReadDeviceConfiguration, Depends(ReadDeviceConfiguration)],
) -> ConfigModel:
    """Get a device configuration."""
    energy_assistant = get_energy_assistant(request)
    return await use_case.execute(energy_assistant.config, device_id)


@router.put(
    "/device/{device_id}",
    response_model=ReadDeviceConfigResponse,
)
async def write(
    request: Request,
    data: dict,
    device_id: Annotated[uuid.UUID, Path(..., description="ID of the device to configure")],
    use_case: Annotated[WriteDeviceConfiguration, Depends(WriteDeviceConfiguration)],
) -> ConfigModel:
    """Update a device configuration."""
    energy_assistant = get_energy_assistant(request)
    return await use_case.execute(energy_assistant.config, data, device_id, energy_assistant.home)
