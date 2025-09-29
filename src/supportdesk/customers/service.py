"""Customer service layer for business logic."""

from uuid import UUID

from supportdesk.common.errors import (
    customer_external_id_exists_exception,
    customer_not_found_exception,
    tenant_not_found_exception,
)
from supportdesk.common.pagination import PaginatedResponse, PaginationParams
from supportdesk.customers.models import Customer
from supportdesk.customers.repository import CustomerRepository
from supportdesk.customers.schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)
from supportdesk.tenants.repository import TenantRepository


class CustomerService:
    """Service layer for customer operations."""

    def __init__(self, customer_repo: CustomerRepository, tenant_repo: TenantRepository):
        self.customer_repo = customer_repo
        self.tenant_repo = tenant_repo

    async def create_customer(
        self,
        tenant_id: UUID,
        customer_data: CustomerCreate
    ) -> CustomerResponse:
        """Create a new customer with validation."""
        # Verify tenant exists and is active
        tenant = await self.tenant_repo.get_by_id(tenant_id, include_inactive=False)
        if not tenant:
            raise tenant_not_found_exception(tenant_id)

        # Check if external_id already exists within the tenant
        if customer_data.external_id:
            if await self.customer_repo.exists_by_external_id(tenant_id, customer_data.external_id):
                raise customer_external_id_exists_exception(customer_data.external_id, tenant_id)

        # Create the customer
        customer = await self.customer_repo.create(tenant_id, customer_data)
        return CustomerResponse.model_validate(customer)

    async def get_customer(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        include_inactive: bool = False
    ) -> CustomerResponse:
        """Get a customer by ID within a tenant."""
        customer = await self.customer_repo.get_by_id(
            tenant_id, customer_id, include_inactive=include_inactive
        )
        if not customer:
            raise customer_not_found_exception(customer_id, tenant_id)

        return CustomerResponse.model_validate(customer)

    async def get_customer_by_external_id(
        self,
        tenant_id: UUID,
        external_id: str,
        include_inactive: bool = False
    ) -> CustomerResponse:
        """Get a customer by external ID within a tenant."""
        customer = await self.customer_repo.get_by_external_id(
            tenant_id, external_id, include_inactive=include_inactive
        )
        if not customer:
            from fastapi import status

            from supportdesk.common.errors import create_http_exception
            raise create_http_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="CUSTOMER_NOT_FOUND",
                message=f"Customer with external_id '{external_id}' not found or inactive",
                details={"external_id": external_id, "tenant_id": str(tenant_id)}
            )

        return CustomerResponse.model_validate(customer)

    async def list_customers(
        self,
        tenant_id: UUID,
        pagination: PaginationParams,
        include_inactive: bool = False
    ) -> PaginatedResponse[CustomerResponse]:
        """Get paginated list of customers within a tenant."""
        # Verify tenant exists and is active
        tenant = await self.tenant_repo.get_by_id(tenant_id, include_inactive=False)
        if not tenant:
            raise tenant_not_found_exception(tenant_id)

        customers, total = await self.customer_repo.list_paginated(
            tenant_id=tenant_id,
            offset=pagination.offset,
            limit=pagination.limit,
            include_inactive=include_inactive
        )

        customer_responses = [CustomerResponse.model_validate(customer) for customer in customers]

        return PaginatedResponse.create(
            items=customer_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def update_customer(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        customer_data: CustomerUpdate,
        include_inactive: bool = False
    ) -> CustomerResponse:
        """Update a customer within a tenant."""
        customer = await self.customer_repo.get_by_id(
            tenant_id, customer_id, include_inactive=include_inactive
        )
        if not customer:
            raise customer_not_found_exception(customer_id, tenant_id)

        updated_customer = await self.customer_repo.update(customer, customer_data)
        return CustomerResponse.model_validate(updated_customer)

    async def delete_customer(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        include_inactive: bool = False
    ) -> None:
        """Soft delete a customer within a tenant."""
        customer = await self.customer_repo.get_by_id(
            tenant_id, customer_id, include_inactive=include_inactive
        )
        if not customer:
            raise customer_not_found_exception(customer_id, tenant_id)

        await self.customer_repo.soft_delete(customer)

    async def _get_customer_model(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        include_inactive: bool = False
    ) -> Customer:
        """Get customer model (internal use)."""
        customer = await self.customer_repo.get_by_id(
            tenant_id, customer_id, include_inactive=include_inactive
        )
        if not customer:
            raise customer_not_found_exception(customer_id, tenant_id)
        return customer
