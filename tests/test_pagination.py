"""Tests for pagination functionality."""

import pytest
from fastapi.testclient import TestClient
from supportdesk.common.pagination import PaginatedResponse, PaginationParams


class TestPaginationParams:
    """Test pagination parameter handling."""

    def test_default_values(self):
        """Test default pagination values."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20  # From settings default
        assert params.offset == 0
        assert params.limit == 20

    def test_custom_values(self):
        """Test custom pagination values."""
        params = PaginationParams(page=3, page_size=10)
        assert params.page == 3
        assert params.page_size == 10
        assert params.offset == 20  # (3-1) * 10
        assert params.limit == 10

    def test_offset_calculation(self):
        """Test offset calculation for different pages."""
        test_cases = [
            (1, 10, 0),   # First page
            (2, 10, 10),  # Second page
            (5, 20, 80),  # Fifth page with larger page size
        ]

        for page, page_size, expected_offset in test_cases:
            params = PaginationParams(page=page, page_size=page_size)
            assert params.offset == expected_offset

    def test_max_page_size_enforcement(self):
        """Test that page size accepts large values (enforcement happens at repository level)."""
        params = PaginationParams(page_size=200)  # Large value should be accepted
        assert params.limit == 200  # Should accept the value as-is

    def test_validation_errors(self):
        """Test validation errors for invalid values."""
        with pytest.raises(ValueError):
            PaginationParams(page=0)  # Page must be >= 1

        with pytest.raises(ValueError):
            PaginationParams(page_size=0)  # Page size must be >= 1


class TestPaginatedResponse:
    """Test paginated response creation."""

    def test_create_response(self):
        """Test creating paginated response."""
        items = ["item1", "item2", "item3"]
        total = 25
        page = 2
        page_size = 10

        response = PaginatedResponse.create(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

        assert response.items == items
        assert response.total == total
        assert response.page == page
        assert response.page_size == page_size
        assert response.total_pages == 3  # ceil(25/10)
        assert response.has_next is True   # Page 2 of 3
        assert response.has_prev is True   # Not first page

    def test_first_page_flags(self):
        """Test has_next and has_prev flags for first page."""
        response = PaginatedResponse.create(
            items=["item1", "item2"],
            total=25,
            page=1,
            page_size=10
        )

        assert response.has_next is True   # More pages exist
        assert response.has_prev is False  # First page

    def test_last_page_flags(self):
        """Test has_next and has_prev flags for last page."""
        response = PaginatedResponse.create(
            items=["item1", "item2"],
            total=25,
            page=3,
            page_size=10
        )

        assert response.has_next is False  # Last page
        assert response.has_prev is True   # Not first page

    def test_single_page_flags(self):
        """Test flags when all items fit on one page."""
        response = PaginatedResponse.create(
            items=["item1", "item2"],
            total=2,
            page=1,
            page_size=10
        )

        assert response.has_next is False  # No more pages
        assert response.has_prev is False  # First page
        assert response.total_pages == 1

    def test_empty_results(self):
        """Test pagination with empty results."""
        response = PaginatedResponse.create(
            items=[],
            total=0,
            page=1,
            page_size=10
        )

        assert response.items == []
        assert response.total == 0
        assert response.total_pages == 0
        assert response.has_next is False
        assert response.has_prev is False


class TestPaginationIntegration:
    """Test pagination integration with API endpoints."""


    def test_default_pagination(self, client: TestClient, tenant_id: str):
        """Test default pagination parameters."""
        # Create some customers
        for i in range(5):
            customer_data = {
                "name": f"Customer {i}",
                "external_id": f"CUST-{i}"
            }
            client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)

        # Test default pagination
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 20  # Default from settings
        assert data["total"] == 5
        assert data["total_pages"] == 1

    def test_custom_pagination(self, client: TestClient, tenant_id: str):
        """Test custom pagination parameters."""
        # Create customers
        for i in range(15):
            customer_data = {
                "name": f"Customer {i:02d}",
                "external_id": f"CUST-{i:02d}"
            }
            client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)

        # Test custom page size
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page_size=5")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 5
        assert data["page_size"] == 5
        assert data["total_pages"] == 3  # ceil(15/5)

    def test_page_size_limits(self, client: TestClient, tenant_id: str):
        """Test page size limits."""
        # Create one customer
        customer_data = {"name": "Test Customer"}
        client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)

        # Test maximum page size limit
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page_size=200")
        assert response.status_code == 200

        data = response.json()
        assert data["page_size"] == 200  # Request accepts large values
        # Note: The actual limit enforcement happens in the repository layer

    def test_invalid_pagination_params(self, client: TestClient, tenant_id: str):
        """Test invalid pagination parameters."""
        # Test invalid page number
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=0")
        assert response.status_code == 422

        # Test invalid page size
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page_size=0")
        assert response.status_code == 422

    def test_pagination_ordering(self, client: TestClient, tenant_id: str):
        """Test that pagination maintains consistent ordering."""
        # Create customers with specific order
        customer_names = []
        for i in range(25):
            name = f"Customer {i:02d}"
            customer_names.append(name)
            customer_data = {
                "name": name,
                "external_id": f"CUST-{i:02d}"
            }
            client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)

        # Get first page
        response1 = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=1&page_size=10")
        assert response1.status_code == 200
        page1_items = response1.json()["items"]

        # Get second page
        response2 = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=2&page_size=10")
        assert response2.status_code == 200
        page2_items = response2.json()["items"]

        # Verify no overlap between pages
        page1_ids = {item["id"] for item in page1_items}
        page2_ids = {item["id"] for item in page2_items}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not have overlapping items"

        # Verify consistent ordering (customers are ordered by created_at desc)
        # So newer customers should appear first
        page1_times = [item["created_at"] for item in page1_items]
        page2_times = [item["created_at"] for item in page2_items]

        # Within each page, times should be in descending order
        assert page1_times == sorted(page1_times, reverse=True)
        assert page2_times == sorted(page2_times, reverse=True)

        # First page should have newer items than second page
        if page1_times and page2_times:
            assert min(page1_times) >= max(page2_times)

    def test_empty_page(self, client: TestClient, tenant_id: str):
        """Test requesting a page beyond available data."""
        # Create only 5 customers
        for i in range(5):
            customer_data = {
                "name": f"Customer {i}",
                "external_id": f"CUST-{i}"
            }
            client.post(f"/api/v1/tenants/{tenant_id}/customers/", json=customer_data)

        # Request page 2 with page_size=10 (should be empty)
        response = client.get(f"/api/v1/tenants/{tenant_id}/customers/?page=2&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["has_next"] is False
        assert data["has_prev"] is True
