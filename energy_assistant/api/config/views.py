"""Views for home measurement API."""


from fastapi import APIRouter, Depends, HTTPException, Request

from .schema import ConfigModel, ReadConfigResponse
from .use_cases import ReadConfiguration

router = APIRouter(prefix="/config")


@router.get("", response_model=ReadConfigResponse)
async def read_configuration(
    request: Request,
    use_case: ReadConfiguration = Depends(ReadConfiguration),
) -> ConfigModel:
    """Rest end point for read all devices."""
    energy_assistant = (
        request.app.energy_assistant if hasattr(request.app, "energy_assistant") else None
    )
    if energy_assistant is None:
        raise HTTPException(status_code=500)
    return await use_case.execute(energy_assistant.config)
