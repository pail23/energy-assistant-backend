"""Tests for the main module."""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_health(ac: AsyncClient) -> None:
    """Test the healt check REST endpoint."""
    # client = await anext(ac)
    response = await ac.get("/check")
    assert response.status_code == 200
