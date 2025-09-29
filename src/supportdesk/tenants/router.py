"""Tenant API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.deps import is_admin_with_override
from supportdesk.database import get_db
from supportdesk.tenants.repository import TenantRepository
from supportdesk.tenants.schemas import TenantCreate, TenantResponse, TenantUpdate
from supportdesk.tenants.service import TenantService

router = APIRouter()


def get_tenant_service(db: AsyncSession = Depends(get_db)) -> TenantService:
    """Dependency to get tenant service."""
    tenant_repo = TenantRepository(db)
    return TenantService(tenant_repo)


@router.post(
    "/",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant",
    description="Create a new tenant organization with a unique slug and configuration settings.",
)
async def create_tenant(
    tenant_data: TenantCreate,
    tenant_service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    """Create a new tenant."""
    return await tenant_service.create_tenant(tenant_data)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get a tenant by ID",
    description="Retrieve a tenant by its unique identifier. Returns 404 if tenant is not found or inactive.",
)
async def get_tenant(
    tenant_id: UUID,
    include_inactive: bool = False,
    tenant_service: TenantService = Depends(get_tenant_service),
    admin: bool = Depends(is_admin_with_override),
) -> TenantResponse:
    """Get a tenant by ID."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    return await tenant_service.get_tenant(tenant_id, include_inactive=include_inactive)


@router.put(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Update a tenant",
    description="Update tenant information. Only provided fields will be updated.",
)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    include_inactive: bool = False,
    tenant_service: TenantService = Depends(get_tenant_service),
    admin: bool = Depends(is_admin_with_override),
) -> TenantResponse:
    """Update a tenant."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    return await tenant_service.update_tenant(tenant_id, tenant_data, include_inactive=include_inactive)


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tenant",
    description="Soft delete a tenant by setting is_active to false. The tenant and its data are preserved but hidden from normal operations.",
)
async def delete_tenant(
    tenant_id: UUID,
    include_inactive: bool = False,
    tenant_service: TenantService = Depends(get_tenant_service),
    admin: bool = Depends(is_admin_with_override),
) -> None:
    """Soft delete a tenant."""
    # Only allow include_inactive if user is admin
    if include_inactive and not admin:
        include_inactive = False

    await tenant_service.delete_tenant(tenant_id, include_inactive=include_inactive)
