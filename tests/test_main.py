import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(ac: AsyncClient) -> None:
    client = await anext(ac) 
    response = await client.get("/check")
    assert 200 == response.status_code