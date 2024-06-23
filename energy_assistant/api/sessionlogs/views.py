"""Views for home measurement API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from .schema import ReadAllSessionLogEntriesResponse
from .use_cases import ReadAllLogEntries

router = APIRouter(prefix="/sessionlog")


@router.get("", response_model=ReadAllSessionLogEntriesResponse)
async def read_all(
    request: Request,
    use_case: Annotated[ReadAllLogEntries, Depends(ReadAllLogEntries)],
    device_id: uuid.UUID | None = None,
) -> ReadAllSessionLogEntriesResponse:
    """Rest end point for read all devices."""
    return ReadAllSessionLogEntriesResponse(entries=[entry async for entry in use_case.execute(device_id)])
