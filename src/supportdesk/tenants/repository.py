"""Tenant repository for database operations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.errors import slug_already_exists_exception
from supportdesk.tenants.models import Tenant
from supportdesk.tenants.schemas import TenantCreate, TenantUpdate


class TenantRepository:
    """Repository for tenant database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, tenant_id: UUID, include_inactive: bool = False) -> Optional[Tenant]:
        """Get tenant by ID."""
        query = select(Tenant).where(Tenant.id == tenant_id)
        if not include_inactive:
            query = query.where(Tenant.is_active == True)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str, include_inactive: bool = False) -> Optional[Tenant]:
        """Get tenant by slug."""
        query = select(Tenant).where(Tenant.slug == slug)
        if not include_inactive:
            query = query.where(Tenant.is_active == True)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, tenant_data: TenantCreate) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(
            name=tenant_data.name,
            slug=tenant_data.slug,
            settings_=tenant_data.settings,
        )

        self.db.add(tenant)

        try:
            await self.db.commit()
            await self.db.refresh(tenant)
            return tenant
        except IntegrityError as e:
            await self.db.rollback()
            # Check if it's a slug uniqueness violation
            if "tenants_slug_key" in str(e) or "uq_tenants_slug" in str(e):
                raise slug_already_exists_exception(tenant_data.slug)
            raise

    async def update(self, tenant: Tenant, tenant_data: TenantUpdate) -> Tenant:
        """Update an existing tenant."""
        if tenant_data.name is not None:
            tenant.name = tenant_data.name
        if tenant_data.settings is not None:
            tenant.settings_ = tenant_data.settings

        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def soft_delete(self, tenant: Tenant) -> None:
        """Soft delete a tenant by setting is_active to False."""
        tenant.is_active = False
        await self.db.commit()

    async def exists_by_slug(self, slug: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if a tenant with the given slug exists."""
        query = select(Tenant.id).where(Tenant.slug == slug, Tenant.is_active == True)
        if exclude_id:
            query = query.where(Tenant.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_active(self) -> List[Tenant]:
        """Get all active tenants."""
        query = select(Tenant).where(Tenant.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())
