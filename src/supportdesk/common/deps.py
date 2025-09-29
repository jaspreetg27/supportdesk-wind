"""FastAPI dependencies for common functionality."""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from supportdesk.tenants.models import Tenant
from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.errors import tenant_not_found_exception
from supportdesk.database import get_db


class TenantContext:
    """Context object containing tenant information for request processing."""

    def __init__(self, tenant_id: UUID, tenant: "Tenant"):
        self.tenant_id = tenant_id
        self.tenant = tenant


async def get_tenant_context(
    tenant_id: UUID = Path(..., description="Tenant ID"),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Dependency to validate tenant existence and create tenant context.

    This dependency:
    1. Validates that the tenant_id exists and is active
    2. Returns a TenantContext object for use in endpoints
    3. Raises 404 if tenant is not found or inactive
    """
    # Import here to avoid circular imports
    from supportdesk.tenants.repository import TenantRepository

    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(tenant_id, include_inactive=False)

    if not tenant:
        raise tenant_not_found_exception(tenant_id)

    return TenantContext(tenant_id=tenant_id, tenant=tenant)


async def is_admin() -> bool:
    """
    Stub dependency for admin check.

    Returns False by default. In tests, this can be overridden to return True
    to test admin-only functionality like include_inactive queries.

    TODO: Replace with real authentication/authorization logic in future phases.
    """
    return False


# Test helper to override admin status
_admin_override: Optional[bool] = None


def set_admin_override(is_admin_user: bool) -> None:
    """Set admin override for testing purposes."""
    global _admin_override
    _admin_override = is_admin_user


def clear_admin_override() -> None:
    """Clear admin override."""
    global _admin_override
    _admin_override = None


async def is_admin_with_override() -> bool:
    """Admin dependency with test override support."""
    if _admin_override is not None:
        return _admin_override
    return await is_admin()
