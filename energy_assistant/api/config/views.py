"""Views for home measurement API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from .schema import ConfigModel, ReadConfigResponse, ReadDeviceConfigResponse
from .use_cases import ReadConfiguration, ReadDeviceConfiguration, WriteDeviceConfiguration

router = APIRouter(prefix="/config")


@router.get("", response_model=ReadConfigResponse)
async def read_configuration(
    request: Request,
    use_case: Annotated[ReadConfiguration, Depends(ReadConfiguration)],
) -> ConfigModel:
    """Rest end point for read all devices."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(energy_assistant.config)


@router.get(
    "/device/{device_id}",
    response_model=ReadDeviceConfigResponse,
)
async def read(
    request: Request,
    device_id: Annotated[uuid.UUID, Path(..., description="")],
    use_case: Annotated[ReadDeviceConfiguration, Depends(ReadDeviceConfiguration)],
) -> ConfigModel:
    """REST end point for read a device configuration."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(energy_assistant.config, device_id)


@router.put(
    "/device/{device_id}",
    response_model=ReadDeviceConfigResponse,
)
async def write(
    request: Request,
    data: dict,
    device_id: Annotated[uuid.UUID, Path(..., description="")],
    use_case: Annotated[WriteDeviceConfiguration, Depends(WriteDeviceConfiguration)],
) -> ConfigModel:
    """REST end point for read a device configuration."""
    energy_assistant = request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(energy_assistant.config, data, device_id, energy_assistant.home)
