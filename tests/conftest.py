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
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tenant_id(client: TestClient) -> str:
    """Create a test tenant and return its ID."""
    slug = f"test-tenant-{uuid.uuid4().hex[:8]}"
    body = {"name": "Test Tenant", "slug": slug, "settings": {}}
    r = client.post("/api/v1/tenants/", json=body)
    assert r.status_code == 201
    return r.json()["id"]
