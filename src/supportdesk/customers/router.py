"""Customer API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.deps import (
    TenantContext,
    get_tenant_context,
    is_admin_with_override,
)
from supportdesk.common.pagination import PaginatedResponse, PaginationParams, get_pagination_params
from supportdesk.customers.repository import CustomerRepository
from supportdesk.customers.schemas import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)
from supportdesk.customers.service import CustomerService
from supportdesk.database import get_db
from supportdesk.tenants.repository import TenantRepository

router = APIRouter()


def get_customer_service(db: AsyncSession = Depends(get_db)) -> CustomerService:
    """Dependency to get customer service."""
    customer_repo = CustomerRepository(db)
    tenant_repo = TenantRepository(db)
    return CustomerService(customer_repo, tenant_repo)


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
    description="Create a new customer within the specified tenant. External ID must be unique within the tenant.",
)
async def create_customer(
    customer_data: CustomerCreate,
    tenant_context: TenantContext = Depends(get_tenant_context),
    customer_service: CustomerService = Depends(get_customer_service),
) -> CustomerResponse:
    """Create a new customer."""
    return await customer_service.create_customer(tenant_context.tenant_id, customer_data)


@router.get(
    "/",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List customers",
    description="Get a paginated list of customers within the specified tenant.",
)
async def list_customers(
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
    include_inactive: bool = Query(False, description="Include inactive customers (admin only)"),
    tenant_context: TenantContext = Depends(get_tenant_context),
    customer_service: CustomerService = Depends(get_customer_service),
    admin: bool = Depends(is_admin_with_override),
) -> PaginatedResponse[CustomerResponse]:
    """List customers with pagination."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    return await customer_service.list_customers(
        tenant_context.tenant_id, pagination, include_inactive=include_inactive
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get a customer by ID",
    description="Retrieve a customer by its unique identifier within the specified tenant.",
)
async def get_customer(
    customer_id: UUID,
    include_inactive: bool = Query(False, description="Include inactive customers (admin only)"),
    tenant_context: TenantContext = Depends(get_tenant_context),
    customer_service: CustomerService = Depends(get_customer_service),
    admin: bool = Depends(is_admin_with_override),
) -> CustomerResponse:
    """Get a customer by ID."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    return await customer_service.get_customer(
        tenant_context.tenant_id, customer_id, include_inactive=include_inactive
    )


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update a customer",
    description="Update customer information within the specified tenant. Only provided fields will be updated.",
)
async def update_customer(
    customer_id: UUID,
    customer_data: CustomerUpdate,
    include_inactive: bool = Query(False, description="Include inactive customers (admin only)"),
    tenant_context: TenantContext = Depends(get_tenant_context),
    customer_service: CustomerService = Depends(get_customer_service),
    admin: bool = Depends(is_admin_with_override),
) -> CustomerResponse:
    """Update a customer."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    return await customer_service.update_customer(
        tenant_context.tenant_id, customer_id, customer_data, include_inactive=include_inactive
    )


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a customer",
    description="Soft delete a customer by setting is_active to false. The customer data is preserved but hidden from normal operations.",
)
async def delete_customer(
    customer_id: UUID,
    include_inactive: bool = Query(False, description="Include inactive customers (admin only)"),
    tenant_context: TenantContext = Depends(get_tenant_context),
    customer_service: CustomerService = Depends(get_customer_service),
    admin: bool = Depends(is_admin_with_override),
) -> None:
    """Soft delete a customer."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    await customer_service.delete_customer(
        tenant_context.tenant_id, customer_id, include_inactive=include_inactive
    )
