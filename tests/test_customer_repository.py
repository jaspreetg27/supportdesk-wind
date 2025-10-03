"""Unit tests for customer repository parameter order."""

import pytest
from uuid import uuid4
from supportdesk.customers.repository import CustomerRepository
from supportdesk.customers.schemas import CustomerCreate


class TestCustomerRepositoryParameterOrder:
    """Test customer repository parameter order correctness."""

    @pytest.mark.asyncio
    async def test_get_by_id_parameter_order(self, db_session, tenant_id):
        """Test that get_by_id uses correct parameter order: customer_id, tenant_id."""
        repo = CustomerRepository(db_session)
        
        # Create a customer
        customer_data = CustomerCreate(
            name="Test Customer",
            phone="+1234567890",
            external_id="test-customer-123"
        )
        created_customer = await repo.create(tenant_id, customer_data)
        
        # Test correct parameter order: customer_id first, tenant_id second
        found_customer = await repo.get_by_id(created_customer.id, tenant_id)
        assert found_customer is not None
        assert found_customer.id == created_customer.id
        assert found_customer.name == "Test Customer"
        
        # Test swapped parameters should return None (wrong tenant_id in customer_id position)
        not_found = await repo.get_by_id(tenant_id, created_customer.id)
        assert not_found is None
        
        # Test with non-existent customer_id
        fake_customer_id = uuid4()
        not_found = await repo.get_by_id(fake_customer_id, tenant_id)
        assert not_found is None
