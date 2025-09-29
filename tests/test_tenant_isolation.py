"""Tests for tenant isolation and cross-tenant access prevention."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


class TestTenantIsolation:
    """Test comprehensive tenant isolation."""

    @pytest.fixture
    def tenant_a_id(self, client: TestClient) -> str:
        """Create tenant A."""
        import uuid
        unique_slug = f"tenant-a-corp-{str(uuid.uuid4())[:8]}"

        tenant_data = {
            "name": "Tenant A Corporation",
            "slug": unique_slug,
            "settings": {"tenant": "A"}
        }
        response = client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        return response.json()["id"]

    @pytest.fixture
    def tenant_b_id(self, client: TestClient) -> str:
        """Create tenant B."""
        import uuid
        unique_slug = f"tenant-b-corp-{str(uuid.uuid4())[:8]}"

        tenant_data = {
            "name": "Tenant B Corporation",
            "slug": unique_slug,
            "settings": {"tenant": "B"}
        }
        response = client.post("/api/v1/tenants/", json=tenant_data)
        assert response.status_code == 201
        return response.json()["id"]

    @pytest.fixture
    def customer_in_tenant_a(self, client: TestClient, tenant_a_id: str) -> dict:
        """Create a customer in tenant A."""
        customer_data = {
            "name": "Customer A1",
            "external_id": "TENANT-A-CUST-001",
            "email": "customer.a1@example.com",
            "metadata": {"tenant": "A", "priority": "high"}
        }
        response = client.post(f"/api/v1/tenants/{tenant_a_id}/customers/", json=customer_data)
        assert response.status_code == 201
        return response.json()

    @pytest.fixture
    def customer_in_tenant_b(self, client: TestClient, tenant_b_id: str) -> dict:
        """Create a customer in tenant B."""
        customer_data = {
            "name": "Customer B1",
            "external_id": "TENANT-B-CUST-001",
            "email": "customer.b1@example.com",
            "metadata": {"tenant": "B", "priority": "medium"}
        }
        response = client.post(f"/api/v1/tenants/{tenant_b_id}/customers/", json=customer_data)
        assert response.status_code == 201
        return response.json()

    def test_customer_cross_tenant_get_denied(
        self,
        client: TestClient,
        tenant_a_id: str,
        tenant_b_id: str,
        customer_in_tenant_a: dict
    ):
        """Test that customers cannot be accessed from different tenants."""
        customer_id = customer_in_tenant_a["id"]

        # Try to access tenant A's customer from tenant B
        response = client.get(f"/api/v1/tenants/{tenant_b_id}/customers/{customer_id}")
        assert response.status_code == 404

        # Verify it's accessible from correct tenant
        response = client.get(f"/api/v1/tenants/{tenant_a_id}/customers/{customer_id}")
        assert response.status_code == 200
        assert response.json()["id"] == customer_id

    def test_customer_cross_tenant_update_denied(
        self,
        client: TestClient,
        tenant_a_id: str,
        tenant_b_id: str,
        customer_in_tenant_a: dict
    ):
        """Test that customers cannot be updated from different tenants."""
        customer_id = customer_in_tenant_a["id"]
        update_data = {"name": "Hacked Name"}

        # Try to update tenant A's customer from tenant B
        response = client.put(f"/api/v1/tenants/{tenant_b_id}/customers/{customer_id}", json=update_data)
        assert response.status_code == 404

        # Verify original data is unchanged
        response = client.get(f"/api/v1/tenants/{tenant_a_id}/customers/{customer_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Customer A1"  # Original name

    def test_customer_cross_tenant_delete_denied(
        self,
        client: TestClient,
        tenant_a_id: str,
        tenant_b_id: str,
        customer_in_tenant_a: dict
    ):
        """Test that customers cannot be deleted from different tenants."""
        customer_id = customer_in_tenant_a["id"]

        # Try to delete tenant A's customer from tenant B
        response = client.delete(f"/api/v1/tenants/{tenant_b_id}/customers/{customer_id}")
        assert response.status_code == 404

        # Verify customer still exists in correct tenant
        response = client.get(f"/api/v1/tenants/{tenant_a_id}/customers/{customer_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_customer_list_isolation(
        self,
        client: TestClient,
        tenant_a_id: str,
        tenant_b_id: str,
        customer_in_tenant_a: dict,
        customer_in_tenant_b: dict
    ):
        """Test that customer lists are isolated by tenant."""
        # List customers for tenant A
        response_a = client.get(f"/api/v1/tenants/{tenant_a_id}/customers/")
        assert response_a.status_code == 200
        customers_a = response_a.json()["items"]

        # List customers for tenant B
        response_b = client.get(f"/api/v1/tenants/{tenant_b_id}/customers/")
        assert response_b.status_code == 200
        customers_b = response_b.json()["items"]

        # Verify each tenant only sees their own customers
        assert len(customers_a) == 1
        assert len(customers_b) == 1
        assert customers_a[0]["id"] == customer_in_tenant_a["id"]
        assert customers_b[0]["id"] == customer_in_tenant_b["id"]

        # Verify no cross-tenant data leakage
        tenant_a_ids = {c["id"] for c in customers_a}
        tenant_b_ids = {c["id"] for c in customers_b}
        assert tenant_a_ids.isdisjoint(tenant_b_ids)

    def test_same_external_id_different_tenants(
        self,
        client: TestClient,
        tenant_a_id: str,
        tenant_b_id: str
    ):
        """Test that same external_id can exist in different tenants."""
        external_id = "SHARED-EXTERNAL-ID-123"

        # Create customer with same external_id in tenant A
        customer_a_data = {
            "name": "Customer A with Shared ID",
            "external_id": external_id,
            "email": "customer.a@example.com"
        }
        response_a = client.post(f"/api/v1/tenants/{tenant_a_id}/customers/", json=customer_a_data)
        assert response_a.status_code == 201
        customer_a = response_a.json()

        # Create customer with same external_id in tenant B
        customer_b_data = {
            "name": "Customer B with Shared ID",
            "external_id": external_id,
            "email": "customer.b@example.com"
        }
        response_b = client.post(f"/api/v1/tenants/{tenant_b_id}/customers/", json=customer_b_data)
        assert response_b.status_code == 201
        customer_b = response_b.json()

        # Verify both customers exist with same external_id but different tenant_ids
        assert customer_a["external_id"] == external_id
        assert customer_b["external_id"] == external_id
        assert customer_a["tenant_id"] == tenant_a_id
        assert customer_b["tenant_id"] == tenant_b_id
        assert customer_a["id"] != customer_b["id"]

    def test_duplicate_external_id_same_tenant_fails(
        self,
        client: TestClient,
        tenant_a_id: str
    ):
        """Test that duplicate external_id within same tenant fails."""
        external_id = "DUPLICATE-IN-SAME-TENANT"

        # Create first customer
        customer_data_1 = {
            "name": "First Customer",
            "external_id": external_id
        }
        response_1 = client.post(f"/api/v1/tenants/{tenant_a_id}/customers/", json=customer_data_1)
        assert response_1.status_code == 201

        # Try to create second customer with same external_id in same tenant
        customer_data_2 = {
            "name": "Second Customer",
            "external_id": external_id
        }
        response_2 = client.post(f"/api/v1/tenants/{tenant_a_id}/customers/", json=customer_data_2)
        assert response_2.status_code == 409

        error = response_2.json()
        # Check if it's a detail-based error (FastAPI format) or our custom format
        if "detail" in error:
            assert error["detail"]["error"] == "CUSTOMER_EXTERNAL_ID_EXISTS"
        else:
            assert error["error"] == "CUSTOMER_EXTERNAL_ID_EXISTS"

    def test_invalid_tenant_id_access(self, client: TestClient):
        """Test that invalid tenant IDs are properly handled."""
        fake_tenant_id = str(uuid4())
        fake_customer_id = str(uuid4())
        # Test customer creation with invalid tenant
        customer_data = {"name": "Test Customer"}
        response = client.post(f"/api/v1/tenants/{fake_tenant_id}/customers/", json=customer_data)
        assert response.status_code == 404
        error = response.json()
        if "detail" in error:
            assert error["detail"]["error"] == "TENANT_NOT_FOUND"
        else:
            assert error["error"] == "TENANT_NOT_FOUND"

        # Test customer listing with invalid tenant
        response = client.get(f"/api/v1/tenants/{fake_tenant_id}/customers/")
        assert response.status_code == 404
        error = response.json()
        if "detail" in error:
            assert error["detail"]["error"] == "TENANT_NOT_FOUND"
        else:
            assert error["error"] == "TENANT_NOT_FOUND"

        # Test customer get with invalid tenant
        response = client.get(f"/api/v1/tenants/{fake_tenant_id}/customers/{fake_customer_id}")
        assert response.status_code == 404
        error = response.json()
        if "detail" in error:
            assert error["detail"]["error"] == "TENANT_NOT_FOUND"
        else:
            assert error["error"] == "TENANT_NOT_FOUND"

    def test_tenant_deletion_isolation(
        self,
        client: TestClient,
        tenant_a_id: str,
        tenant_b_id: str,
        customer_in_tenant_a: dict,
        customer_in_tenant_b: dict
    ):
        """Test that deleting a tenant doesn't affect other tenants."""
        # Verify both customers exist
        response_a = client.get(f"/api/v1/tenants/{tenant_a_id}/customers/{customer_in_tenant_a['id']}")
        assert response_a.status_code == 200

        response_b = client.get(f"/api/v1/tenants/{tenant_b_id}/customers/{customer_in_tenant_b['id']}")
        assert response_b.status_code == 200

        # Delete tenant A
        response = client.delete(f"/api/v1/tenants/{tenant_a_id}")
        assert response.status_code == 204

        # Verify tenant A's customer is no longer accessible
        response_a = client.get(f"/api/v1/tenants/{tenant_a_id}/customers/{customer_in_tenant_a['id']}")
        assert response_a.status_code == 404  # Tenant not found

        # Verify tenant B's customer is still accessible
        response_b = client.get(f"/api/v1/tenants/{tenant_b_id}/customers/{customer_in_tenant_b['id']}")
        assert response_b.status_code == 200
        assert response_b.json()["id"] == customer_in_tenant_b["id"]

    def test_massive_tenant_isolation(self, client: TestClient):
        """Test isolation with multiple tenants and customers."""
        # Create multiple tenants
        tenants = []
        for i in range(5):
            tenant_data = {
                "name": f"Isolation Test Tenant {i}",
                "slug": f"isolation-test-tenant-{i}",
                "settings": {"tenant_number": i}
            }
            response = client.post("/api/v1/tenants/", json=tenant_data)
            assert response.status_code == 201
            tenants.append(response.json())

        # Create customers in each tenant
        tenant_customers = {}
        for tenant in tenants:
            tenant_id = tenant["id"]
            tenant_customers[tenant_id] = []

            for j in range(3):  # 3 customers per tenant
                customer_data = {
                    "name": f"Customer {j} in Tenant {tenant['settings']['tenant_number']}",
                    "external_id": f"TENANT-{tenant['settings']['tenant_number']}-CUST-{j}",
                    "metadata": {"tenant_number": tenant["settings"]["tenant_number"]}
                }
                response = client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)
                assert response.status_code == 201
                tenant_customers[tenant_id].append(response.json())

        # Verify isolation: each tenant should only see their own customers
        for tenant in tenants:
            tenant_id = tenant["id"]
            response = client.get(f"/api/v1/tenants/{tenant_id}/customers/")
            assert response.status_code == 200

            customers = response.json()["items"]
            assert len(customers) == 3  # Each tenant has exactly 3 customers

            # Verify all customers belong to this tenant
            for customer in customers:
                assert customer["tenant_id"] == tenant_id
                assert customer["metadata"]["tenant_number"] == tenant["settings"]["tenant_number"]

            # Verify customer IDs match what we created
            expected_ids = {c["id"] for c in tenant_customers[tenant_id]}
            actual_ids = {c["id"] for c in customers}
            assert expected_ids == actual_ids
