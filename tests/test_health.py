"""Health endpoint tests."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_health_endpoint_sync(client: TestClient) -> None:
    """Test health endpoint with sync client."""
    response = client.get("/healthz")
    
    # Check response structure regardless of service availability
    assert response.status_code in [200, 503]
    data = response.json()
    
    if response.status_code == 503:
        # If services are unavailable, check error response structure
        assert "detail" in data
        detail = data["detail"]
        assert "status" in detail
        assert "checks" in detail
        assert "database" in detail["checks"]
        assert "redis" in detail["checks"]
    else:
        # If services are available, check success response
        assert data["status"] == "ok"
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]


@pytest.mark.asyncio
async def test_health_endpoint_async(async_client: AsyncClient) -> None:
    """Test health endpoint with async client."""
    response = await async_client.get("/healthz")
    
    # Check response structure regardless of service availability
    assert response.status_code in [200, 503]
    data = response.json()
    
    if response.status_code == 503:
        # If services are unavailable, check error response structure
        assert "detail" in data
        detail = data["detail"]
        assert "status" in detail
        assert "checks" in detail
        assert "database" in detail["checks"]
        assert "redis" in detail["checks"]
    else:
        # If services are available, check success response
        assert data["status"] == "ok"
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]


def test_root_endpoint(client: TestClient) -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "SupportDesk AI"
    assert data["version"] == "0.1.0"
    assert data["status"] == "running"
