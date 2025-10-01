"""Tenant service layer for business logic."""

from uuid import UUID

from supportdesk.common.errors import (
    tenant_not_found_exception,
    slug_already_exists_exception,
)
from supportdesk.tenants.models import Tenant
from supportdesk.tenants.repository import TenantRepository
from supportdesk.tenants.schemas import TenantCreate, TenantResponse, TenantUpdate


class TenantService:
    """Service layer for tenant operations."""

    def __init__(self, tenant_repo: TenantRepository):
        self.tenant_repo = tenant_repo

    async def create_tenant(self, tenant_data: TenantCreate) -> TenantResponse:
        """Create a new tenant with validation."""
        # Check if slug already exists
        if await self.tenant_repo.exists_by_slug(tenant_data.slug):
            raise slug_already_exists_exception(tenant_data.slug)

        # Create the tenant
        tenant = await self.tenant_repo.create(tenant_data)
        return TenantResponse.model_validate(tenant)

    async def get_tenant(self, tenant_id: UUID, include_inactive: bool = False) -> TenantResponse:
        """Get a tenant by ID."""
        tenant = await self.tenant_repo.get_by_id(tenant_id, include_inactive=include_inactive)
        if not tenant:
            raise tenant_not_found_exception(tenant_id)

        return TenantResponse.model_validate(tenant)

    async def get_tenant_by_slug(self, slug: str, include_inactive: bool = False) -> TenantResponse:
        """Get a tenant by slug."""
        tenant = await self.tenant_repo.get_by_slug(slug, include_inactive=include_inactive)
        if not tenant:
            from fastapi import status

            from supportdesk.common.errors import create_http_exception
            raise create_http_exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="TENANT_NOT_FOUND",
                message=f"Tenant with slug '{slug}' not found or inactive",
                details={"slug": slug}
            )

        return TenantResponse.model_validate(tenant)

    async def update_tenant(
        self,
        tenant_id: UUID,
        tenant_data: TenantUpdate,
        include_inactive: bool = False
    ) -> TenantResponse:
        """Update a tenant."""
        tenant = await self.tenant_repo.get_by_id(tenant_id, include_inactive=include_inactive)
        if not tenant:
            raise tenant_not_found_exception(tenant_id)

        updated_tenant = await self.tenant_repo.update(tenant, tenant_data)
        return TenantResponse.model_validate(updated_tenant)

    async def delete_tenant(self, tenant_id: UUID, include_inactive: bool = False) -> None:
        """Soft delete a tenant."""
        tenant = await self.tenant_repo.get_by_id(tenant_id, include_inactive=include_inactive)
        if not tenant:
            raise tenant_not_found_exception(tenant_id)

        await self.tenant_repo.soft_delete(tenant)

    async def _get_tenant_model(self, tenant_id: UUID, include_inactive: bool = False) -> Tenant:
        """Get tenant model (internal use)."""
        tenant = await self.tenant_repo.get_by_id(tenant_id, include_inactive=include_inactive)
        if not tenant:
            raise tenant_not_found_exception(tenant_id)
        return tenant
