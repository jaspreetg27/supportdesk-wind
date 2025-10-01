"""Pytest configuration and fixtures."""

import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from supportdesk.common.deps import clear_admin_override
from supportdesk.database import engine, get_db
from supportdesk.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def _db_clean_between_tests():
    """Clean database between tests to avoid conflicts."""
    async with engine.begin() as conn:
        await conn.exec_driver_sql("TRUNCATE TABLE customers RESTART IDENTITY CASCADE;")
        await conn.exec_driver_sql("TRUNCATE TABLE tenants RESTART IDENTITY CASCADE;")
    yield


@pytest.fixture(autouse=True)
def cleanup_admin_override():
    """Automatically clear admin override after each test."""
    yield
    clear_admin_override()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async for session in get_db():
        yield session


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tenant_id(client: TestClient) -> str:
    """Create a test tenant and return its ID."""
    tenant_data = {
        "name": "Test Tenant",
        "slug": "test-tenant-p2",
        "settings": {"test": True}
    }
    
    response = client.post("/api/v1/tenants/", json=tenant_data)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def customer_id(client: TestClient, tenant_id: str) -> str:
    """Create a test customer and return its ID."""
    customer_data = {
        "name": "Test Customer",
        "email": "test@example.com",
        "phone": "+1234567890",
        "metadata": {"test": True}
    }
    
    response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def thread_id(client: TestClient, tenant_id: str, customer_id: str) -> str:
    """Create a test thread and return its ID."""
    thread_data = {
        "customer_id": customer_id,
        "platform": "whatsapp",
        "subject": "Test Thread",
        "metadata": {"test": True}
    }
    
    response = client.post(f"/api/v1/tenants/{tenant_id}/threads/", json=thread_data)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def message_id(client: TestClient, tenant_id: str, thread_id: str) -> str:
    """Create a test message and return its ID."""
    message_data = {
        "platform_message_id": "test_msg_001",
        "type": "inbound",
        "content": "Test message content",
        "metadata": {"test": True}
    }
    
    response = client.post(f"/api/v1/tenants/{tenant_id}/threads/{thread_id}/messages/", json=message_data)
    assert response.status_code == 201
    return response.json()["id"]
