"""Tests for tenant functionality."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from supportdesk.common.deps import clear_admin_override, set_admin_override


class TestTenantAPI:
    """Test tenant API endpoints."""

    def test_create_tenant_success(self, client: TestClient):
        """Test successful tenant creation."""
        import uuid
        unique_slug = f"test-corp-{str(uuid.uuid4())[:8]}"

        tenant_data = {
            "name": "Test Corporation",
            "slug": unique_slug,
            "settings": {"timezone": "UTC", "locale": "en-US"}
        }

        response = client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == tenant_data["name"]
        assert data["slug"] == tenant_data["slug"]
        assert data["settings"] == tenant_data["settings"]
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_tenant_duplicate_slug(self, client: TestClient):
        """Test creating tenant with duplicate slug fails."""
        import uuid
        unique_slug = f"duplicate-test-{str(uuid.uuid4())[:8]}"

        tenant_data = {
            "name": "Test Corporation",
            "slug": unique_slug,
            "settings": {}
        }

        # Create first tenant
        response1 = client.post("/api/v1/tenants/", json=tenant_data)
        assert response1.status_code == 201

        # Try to create second tenant with same slug
        tenant_data["name"] = "Another Corporation"
        response2 = client.post("/api/v1/tenants/", json=tenant_data)
        assert response2.status_code == 409

        error = response2.json()
        # Check if it's a detail-based error (FastAPI format) or our custom format
        if "detail" in error:
            assert error["detail"]["error"] == "TENANT_SLUG_EXISTS"
            assert unique_slug in error["detail"]["message"]
        else:
            assert error["error"] == "TENANT_SLUG_EXISTS"
            assert unique_slug in error["message"]

    def test_create_tenant_reserved_slug(self, client: TestClient):
        """Test creating tenant with reserved slug fails."""
        tenant_data = {
            "name": "Admin Corp",
            "slug": "admin",  # Reserved slug
            "settings": {}
        }

        response = client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 422

        # Check validation error in detail
        detail = response.json()["detail"]
        assert any("reserved" in str(error).lower() for error in detail)

    def test_create_tenant_invalid_slug(self, client: TestClient):
        """Test creating tenant with invalid slug format fails."""
        invalid_slugs = [
            "a",  # Too short
            "-invalid",  # Starts with hyphen
            "invalid-",  # Ends with hyphen
            "Invalid_Slug",  # Contains uppercase and underscore
            "a" * 51,  # Too long
        ]

        for invalid_slug in invalid_slugs:
            tenant_data = {
                "name": "Test Corp",
                "slug": invalid_slug,
                "settings": {}
            }

            response = client.post("/api/v1/tenants/", json=tenant_data)
            assert response.status_code == 422, f"Slug '{invalid_slug}' should be invalid"

    def test_get_tenant_success(self, client: TestClient):
        """Test successful tenant retrieval."""
        import uuid
        unique_slug = f"get-test-corp-{str(uuid.uuid4())[:8]}"

        # Create tenant first
        tenant_data = {
            "name": "Get Test Corp",
            "slug": unique_slug,
            "settings": {"feature": "enabled"}
        }

        create_response = client.post("/api/v1/tenants/", json=tenant_data)
        assert create_response.status_code == 201
        tenant_id = create_response.json()["id"]

        # Get tenant
        response = client.get(f"/api/v1/tenants/{tenant_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == tenant_id
        assert data["name"] == tenant_data["name"]
        assert data["slug"] == tenant_data["slug"]

    def test_get_tenant_not_found(self, client: TestClient):
        """Test getting non-existent tenant returns 404."""
        fake_id = str(uuid4())
        response = client.get(f"/api/v1/tenants/{fake_id}")
        assert response.status_code == 404

        error = response.json()
        # Check if it's a detail-based error (FastAPI format) or our custom format
        if "detail" in error:
            assert error["detail"]["error"] == "TENANT_NOT_FOUND"
        else:
            assert error["error"] == "TENANT_NOT_FOUND"

    def test_update_tenant_success(self, client: TestClient):
        """Test successful tenant update."""
        import uuid
        unique_slug = f"update-test-corp-{str(uuid.uuid4())[:8]}"

        # Create tenant first
        tenant_data = {
            "name": "Update Test Corp",
            "slug": unique_slug,
            "settings": {"old": "value"}
        }

        create_response = client.post("/api/v1/tenants/", json=tenant_data)
        assert create_response.status_code == 201
        tenant_id = create_response.json()["id"]

        # Update tenant
        update_data = {
            "name": "Updated Corp Name",
            "settings": {"new": "value", "updated": True}
        }

        response = client.put(f"/api/v1/tenants/{tenant_id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["settings"] == update_data["settings"]
        assert data["slug"] == tenant_data["slug"]  # Slug shouldn't change

    def test_delete_tenant_success(self, client: TestClient):
        """Test successful tenant soft delete."""
        import uuid
        unique_slug = f"delete-test-corp-{str(uuid.uuid4())[:8]}"

        # Create tenant first
        tenant_data = {
            "name": "Delete Test Corp",
            "slug": unique_slug,
            "settings": {}
        }

        create_response = client.post("/api/v1/tenants/", json=tenant_data)
        assert create_response.status_code == 201
        tenant_id = create_response.json()["id"]

        # Delete tenant
        response = client.delete(f"/api/v1/tenants/{tenant_id}")
        assert response.status_code == 204

        # Verify tenant is not accessible
        get_response = client.get(f"/api/v1/tenants/{tenant_id}")
        assert get_response.status_code == 404

    def test_get_inactive_tenant_admin_only(self, client: TestClient):
        """Test that inactive tenants are only accessible by admin."""
        import uuid
        unique_slug = f"admin-test-corp-{str(uuid.uuid4())[:8]}"

        # Create and delete tenant
        tenant_data = {
            "name": "Admin Test Corp",
            "slug": unique_slug,
            "settings": {}
        }

        create_response = client.post("/api/v1/tenants/", json=tenant_data)
        tenant_id = create_response.json()["id"]

        client.delete(f"/api/v1/tenants/{tenant_id}")

        # Regular user cannot access inactive tenant
        response = client.get(f"/api/v1/tenants/{tenant_id}?include_inactive=true")
        assert response.status_code == 404

        # Admin can access inactive tenant
        try:
            set_admin_override(True)
            response = client.get(f"/api/v1/tenants/{tenant_id}?include_inactive=true")
            assert response.status_code == 200
            assert response.json()["is_active"] is False
        finally:
            clear_admin_override()


@pytest.mark.asyncio
class TestTenantAPIAsync:
    """Test tenant API endpoints with async client."""

    async def test_create_tenant_async(self, async_client: AsyncClient):
        """Test async tenant creation."""
        import uuid
        unique_slug = f"async-test-corp-{str(uuid.uuid4())[:8]}"

        tenant_data = {
            "name": "Async Test Corp",
            "slug": unique_slug,
            "settings": {"async": True}
        }

        response = await async_client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == tenant_data["name"]
        assert data["slug"] == tenant_data["slug"]


class TestTenantValidation:
    """Test tenant validation logic."""

    def test_slug_normalization(self, client: TestClient):
        """Test that slugs are normalized to lowercase."""
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        tenant_data = {
            "name": "Normalization Test",
            "slug": f"Test-Corp-{unique_suffix}",  # Mixed case
            "settings": {}
        }

        response = client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201

        data = response.json()
        assert data["slug"] == f"test-corp-{unique_suffix}"  # Should be normalized

    def test_valid_slug_formats(self, client: TestClient):
        """Test various valid slug formats."""
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]

        valid_slugs = [
            f"abc-{unique_suffix}",  # Minimum length
            f"test-corp-{unique_suffix}",  # With hyphen
            f"company123-{unique_suffix}",  # With numbers
            f"a1b2c3-{unique_suffix}",  # Mixed alphanumeric
            f"x{unique_suffix}" + "x" * (50 - len(unique_suffix) - 1),  # Maximum length
        ]

        for i, valid_slug in enumerate(valid_slugs):
            tenant_data = {
                "name": f"Valid Slug Test {i}",
                "slug": valid_slug,
                "settings": {}
            }

            response = client.post("/api/v1/tenants/", json=tenant_data)
            assert response.status_code == 201, f"Slug '{valid_slug}' should be valid"
