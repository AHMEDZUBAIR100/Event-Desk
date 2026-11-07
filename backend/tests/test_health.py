import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient) -> None:
    """Test /health returns 200 and expected status/service."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "EventDesk"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_readiness(client: AsyncClient) -> None:
    """Test /health/ready connects to postgres and redis."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    assert data["service"] == "EventDesk"
