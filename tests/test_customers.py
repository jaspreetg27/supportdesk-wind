"""Tests for customer functionality."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from supportdesk.common.deps import clear_admin_override, set_admin_override


class TestCustomerAPI:
    """Test customer API endpoints."""


    @pytest.fixture
    def second_tenant_id(self, client: TestClient) -> str:
        """Create a second test tenant for isolation tests."""
        import uuid
        unique_slug = f"second-test-tenant-{str(uuid.uuid4())[:8]}"

        tenant_data = {
            "name": "Second Test Tenant",
            "slug": unique_slug,
            "settings": {}
        }
        response = client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        return response.json()["id"]

    def test_create_customer_success(self, client: TestClient, tenant_id: str):
        """Test successful customer creation."""
        customer_data = {
            "external_id": "CRM-12345",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "metadata": {"source": "website", "priority": "high"}
        }

        response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == customer_data["name"]
        assert data["email"] == customer_data["email"]
        assert data["phone"] == customer_data["phone"]
        assert data["external_id"] == customer_data["external_id"]
        assert data["metadata"] == customer_data["metadata"]
        assert data["tenant_id"] == tenant_id
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_customer_minimal_data(self, client: TestClient, tenant_id: str):
        """Test creating customer with minimal required data."""
        customer_data = {
            "name": "Jane Smith"
        }

        response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == customer_data["name"]
        assert data["email"] is None
        assert data["phone"] is None
        assert data["external_id"] is None
        assert data["metadata"] == {}

    def test_create_customer_duplicate_external_id_same_tenant(self, client: TestClient, tenant_id: str):
        """Test creating customer with duplicate external_id in same tenant fails."""
        customer_data = {
            "external_id": "DUPLICATE-123",
            "name": "First Customer"
        }

        # Create first customer
        response1 = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response1.status_code == 201

        # Try to create second customer with same external_id
        customer_data["name"] = "Second Customer"
        response2 = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response2.status_code == 409

        error = response2.json()
        # Check if it's a detail-based error (FastAPI format) or our custom format
        if "detail" in error:
            assert error["detail"]["error"] == "CUSTOMER_EXTERNAL_ID_EXISTS"
            assert "DUPLICATE-123" in error["detail"]["message"]
            assert error["detail"]["external_id"] == "DUPLICATE-123"
            assert error["detail"]["tenant_id"] == tenant_id
        else:
            assert error["error"] == "CUSTOMER_EXTERNAL_ID_EXISTS"
            assert "DUPLICATE-123" in error["message"]
            assert error["external_id"] == "DUPLICATE-123"
            assert error["tenant_id"] == tenant_id

    def test_create_customer_same_external_id_different_tenants(self, client: TestClient, tenant_id: str, second_tenant_id: str):
        """Test that same external_id can exist in different tenants."""
        customer_data = {
            "external_id": "SHARED-123",
            "name": "Customer in Tenant 1"
        }

        # Create customer in first tenant
        response1 = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response1.status_code == 201

        # Create customer with same external_id in second tenant
        customer_data["name"] = "Customer in Tenant 2"
        response2 = client.post(f"/api/v1/tenants/{second_tenant_id}/customers/", json=customer_data)
        assert response2.status_code == 201

        # Both should succeed
        assert response1.json()["external_id"] == "SHARED-123"
        assert response2.json()["external_id"] == "SHARED-123"
        assert response1.json()["tenant_id"] != response2.json()["tenant_id"]

    def test_create_customer_invalid_tenant(self, client: TestClient):
        """Test creating customer with invalid tenant ID fails."""
        fake_tenant_id = str(uuid4())
        customer_data = {
            "name": "Test Customer"
        }

        response = client.post(f"/api/v1/tenants/{fake_tenant_id}/customers/", json=customer_data)
        assert response.status_code == 404

        error = response.json()
        # Check if it's a detail-based error (FastAPI format) or our custom format
        if "detail" in error:
            assert error["detail"]["error"] == "TENANT_NOT_FOUND"
        else:
            assert error["error"] == "TENANT_NOT_FOUND"

    def test_create_customer_invalid_email(self, client: TestClient, tenant_id: str):
        """Test creating customer with invalid email fails."""
        customer_data = {
            "name": "Test Customer",
            "email": "invalid-email"
        }

        response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response.status_code == 422

    def test_create_customer_invalid_phone(self, client: TestClient, tenant_id: str):
        """Test creating customer with invalid phone fails."""
        invalid_phones = [
            "123",  # Too short
            "abc123",  # Contains letters
            "+",  # Just plus sign
            "123456789012345678",  # Too long
        ]

        for invalid_phone in invalid_phones:
            customer_data = {
                "name": "Test Customer",
                "phone": invalid_phone
            }

            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 422, f"Phone '{invalid_phone}' should be invalid"

    def test_list_customers_success(self, client: TestClient, tenant_id: str):
        """Test successful customer listing with pagination."""
        # Create multiple customers
        for i in range(5):
            customer_data = {
                "name": f"Customer {i}",
                "external_id": f"CUST-{i}"
            }
            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201

        # List customers
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert "has_next" in data
        assert "has_prev" in data

        assert len(data["items"]) == 5
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 20  # Default page size
        assert data["total_pages"] == 1
        assert data["has_next"] is False
        assert data["has_prev"] is False

    def test_list_customers_pagination(self, client: TestClient, tenant_id: str):
        """Test customer listing pagination."""
        # Create customers
        for i in range(25):
            customer_data = {
                "name": f"Customer {i:02d}",
                "external_id": f"CUST-{i:02d}"
            }
            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201

        # Test first page
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=1&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total_pages"] == 3
        assert data["has_next"] is True
        assert data["has_prev"] is False

        # Test second page
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=2&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 10
        assert data["page"] == 2
        assert data["has_next"] is True
        assert data["has_prev"] is True

    def test_list_customers_tenant_isolation(self, client: TestClient, tenant_id: str, second_tenant_id: str):
        """Test that customers are isolated by tenant."""
        # Create customers in first tenant
        for i in range(3):
            customer_data = {
                "name": f"Tenant1 Customer {i}",
                "external_id": f"T1-CUST-{i}"
            }
            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201

        # Create customers in second tenant
        for i in range(2):
            customer_data = {
                "name": f"Tenant2 Customer {i}",
                "external_id": f"T2-CUST-{i}"
            }
            response = client.post(f"/api/v1/tenants/{second_tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201

        # List customers for first tenant
        response1 = client.get(f"/api/v1/tenants/{tenant_id}/customers/")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["total"] == 3

        # List customers for second tenant
        response2 = client.get(f"/api/v1/tenants/{second_tenant_id}/customers/")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["total"] == 2

        # Verify no cross-tenant data
        tenant1_names = {item["name"] for item in data1["items"]}
        tenant2_names = {item["name"] for item in data2["items"]}
        assert tenant1_names.isdisjoint(tenant2_names)

    def test_get_customer_success(self, client: TestClient, tenant_id: str):
        """Test successful customer retrieval."""
        # Create customer
        customer_data = {
            "name": "Get Test Customer",
            "external_id": "GET-TEST-123",
            "email": "get.test@example.com"
        }

        create_response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert create_response.status_code == 201
        customer_id = create_response.json()["id"]

        # Get customer
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == customer_id
        assert data["name"] == customer_data["name"]
        assert data["external_id"] == customer_data["external_id"]
        assert data["email"] == customer_data["email"]

    def test_get_customer_cross_tenant_access_denied(self, client: TestClient, tenant_id: str, second_tenant_id: str):
        """Test that customers cannot be accessed across tenants."""
        # Create customer in first tenant
        customer_data = {
            "name": "Cross Tenant Test",
            "external_id": "CROSS-TEST-123"
        }

        create_response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert create_response.status_code == 201
        customer_id = create_response.json()["id"]

        # Try to access from second tenant
        response = client.get(f"/api/v1/tenants/{second_tenant_id}/customers/{customer_id}")
        assert response.status_code == 404  # Should not be found in different tenant

    def test_update_customer_success(self, client: TestClient, tenant_id: str):
        """Test successful customer update."""
        # Create customer
        customer_data = {
            "name": "Update Test Customer",
            "email": "old.email@example.com",
            "metadata": {"old": "value"}
        }

        create_response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert create_response.status_code == 201
        customer_id = create_response.json()["id"]

        # Update customer
        update_data = {
            "name": "Updated Customer Name",
            "email": "new.email@example.com",
            "phone": "+9876543210",
            "metadata": {"new": "value", "updated": True}
        }

        response = client.put(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["email"] == update_data["email"]
        assert data["phone"] == update_data["phone"]
        assert data["metadata"] == update_data["metadata"]

    def test_delete_customer_success(self, client: TestClient, tenant_id: str):
        """Test successful customer soft delete."""
        # Create customer
        customer_data = {
            "name": "Delete Test Customer",
            "external_id": "DELETE-TEST-123"
        }

        create_response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert create_response.status_code == 201
        customer_id = create_response.json()["id"]

        # Delete customer
        response = client.delete(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}")
        assert response.status_code == 204

        # Verify customer is not accessible
        get_response = client.get(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}")
        assert get_response.status_code == 404

    def test_get_inactive_customer_admin_only(self, client: TestClient, tenant_id: str):
        """Test that inactive customers are only accessible by admin."""
        # Create and delete customer
        customer_data = {
            "name": "Admin Test Customer",
            "external_id": "ADMIN-TEST-123"
        }

        create_response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        customer_id = create_response.json()["id"]

        client.delete(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}")

        # Regular user cannot access inactive customer
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}?include_inactive=true")
        assert response.status_code == 404

        # Admin can access inactive customer
        try:
            set_admin_override(True)
            response = client.get(f"/api/v1/tenants/{tenant_id}/customers/{customer_id}?include_inactive=true")
            assert response.status_code == 200
            assert response.json()["is_active"] is False
        finally:
            clear_admin_override()


@pytest.mark.asyncio
class TestCustomerAPIAsync:
    """Test customer API endpoints with async client."""

    async def test_create_customer_async(self, async_client: AsyncClient):
        """Test async customer creation."""
        import uuid
        unique_slug = f"async-customer-test-tenant-{str(uuid.uuid4())[:8]}"

        # Create tenant first
        tenant_data = {
            "name": "Async Customer Test Tenant",
            "slug": unique_slug,
            "settings": {}
        }
        tenant_response = await async_client.post("/api/v1/tenants/", json=tenant_data)
        assert tenant_response.status_code == 201
        tenant_id = tenant_response.json()["id"]

        # Create customer
        customer_data = {
            "name": "Async Test Customer",
            "email": "async.test@example.com",
            "metadata": {"async": True}
        }

        response = await async_client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == customer_data["name"]
        assert data["email"] == customer_data["email"]


class TestCustomerValidation:
    """Test customer validation logic."""

    def test_valid_phone_formats(self, client: TestClient, tenant_id: str):
        """Test various valid phone formats."""
        valid_phones = [
            "+1234567890",
            "+12345678901234",  # Maximum length
            "1234567890",  # Without plus
            "+919876543210",  # Indian format
        ]

        for i, valid_phone in enumerate(valid_phones):
            customer_data = {
                "name": f"Phone Test Customer {i}",
                "phone": valid_phone,
                "external_id": f"PHONE-TEST-{i}"
            }

            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201, f"Phone '{valid_phone}' should be valid"

    def test_valid_email_formats(self, client: TestClient, tenant_id: str):
        """Test various valid email formats."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "123@numbers.com",
        ]

        for i, valid_email in enumerate(valid_emails):
            customer_data = {
                "name": f"Email Test Customer {i}",
                "email": valid_email,
                "external_id": f"EMAIL-TEST-{i}"
            }

            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201, f"Email '{valid_email}' should be valid"


@pytest.mark.slow
class TestCustomerPerformance:
    """Test customer performance with larger datasets."""

    def test_pagination_performance(self, client: TestClient, tenant_id: str):
        """Test pagination performance with many customers."""
        # Create many customers
        for i in range(100):
            customer_data = {
                "name": f"Performance Test Customer {i:03d}",
                "external_id": f"PERF-{i:03d}"
            }
            response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
            assert response.status_code == 201

        # Test pagination performance
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=1&page_size=50")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 50
        assert data["total"] == 100
        assert data["total_pages"] == 2
