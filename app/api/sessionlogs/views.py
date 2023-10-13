"""Views for home measurement API."""


import uuid

from fastapi import APIRouter, Depends, Request

from .schema import ReadAllSessionLogEntriesResponse
from .use_cases import ReadAllLogEntries

router = APIRouter(prefix="/sessionlog")


@router.get("", response_model=ReadAllSessionLogEntriesResponse)
async def read_all(
    request: Request,
    device_id: uuid.UUID | None = None,
    use_case: ReadAllLogEntries = Depends(ReadAllLogEntries),
) -> ReadAllSessionLogEntriesResponse:
    """Rest end point for read all devices."""
    return ReadAllSessionLogEntriesResponse(
        entries=[entry async for entry in use_case.execute(device_id)]
    )
