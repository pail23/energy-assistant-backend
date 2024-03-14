"""Tests for the main module."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(ac: AsyncClient) -> None:
    """Test the healt check REST endpoint."""
    # client = await anext(ac)
    response = await ac.get("/check")
    assert response.status_code == 200
