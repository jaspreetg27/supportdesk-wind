"""Custom exceptions and error handling."""

from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status


class SupportDeskError(Exception):
    """Base exception for SupportDesk errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class TenantError(SupportDeskError):
    """Tenant-related errors."""

    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    TENANT_INACTIVE = "TENANT_INACTIVE"
    TENANT_SLUG_EXISTS = "TENANT_SLUG_EXISTS"
    TENANT_SLUG_RESERVED = "TENANT_SLUG_RESERVED"


class CustomerError(SupportDeskError):
    """Customer-related errors."""

    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    CUSTOMER_INACTIVE = "CUSTOMER_INACTIVE"
    CUSTOMER_EXTERNAL_ID_EXISTS = "CUSTOMER_EXTERNAL_ID_EXISTS"
    CROSS_TENANT_ACCESS = "CROSS_TENANT_ACCESS"


class ValidationError(SupportDeskError):
    """Validation-related errors."""

    INVALID_SLUG_FORMAT = "INVALID_SLUG_FORMAT"
    INVALID_EMAIL_FORMAT = "INVALID_EMAIL_FORMAT"
    INVALID_PHONE_FORMAT = "INVALID_PHONE_FORMAT"


def create_http_exception(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> HTTPException:
    """Create a standardized HTTP exception."""
    detail = {
        "error": error_code,
        "message": message,
    }
    if details:
        detail.update(details)

    return HTTPException(status_code=status_code, detail=detail)


def tenant_not_found_exception(tenant_id: UUID) -> HTTPException:
    """Create a tenant not found exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code=TenantError.TENANT_NOT_FOUND,
        message="Tenant not found or inactive",
        details={"tenant_id": str(tenant_id)},
    )


def customer_not_found_exception(customer_id: UUID, tenant_id: UUID) -> HTTPException:
    """Create a customer not found exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code=CustomerError.CUSTOMER_NOT_FOUND,
        message="Customer not found or inactive",
        details={"customer_id": str(customer_id), "tenant_id": str(tenant_id)},
    )


def cross_tenant_access_exception(tenant_id: UUID, resource_type: str) -> HTTPException:
    """Create a cross-tenant access exception."""
    return create_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        error_code=CustomerError.CROSS_TENANT_ACCESS,
        message=f"Access denied: {resource_type} belongs to different tenant",
        details={"tenant_id": str(tenant_id), "resource_type": resource_type},
    )


def tenant_slug_exists_exception(slug: str) -> HTTPException:
    """Create a tenant slug exists exception."""
    return create_http_exception(
        status_code=status.HTTP_409_CONFLICT,
        error_code=TenantError.TENANT_SLUG_EXISTS,
        message=f"Tenant with slug '{slug}' already exists",
        details={"slug": slug},
    )


def tenant_slug_reserved_exception(slug: str) -> HTTPException:
    """Create a tenant slug reserved exception."""
    return create_http_exception(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code=TenantError.TENANT_SLUG_RESERVED,
        message=f"Slug '{slug}' is reserved and cannot be used",
        details={"slug": slug},
    )


def customer_external_id_exists_exception(external_id: str, tenant_id: UUID) -> HTTPException:
    """Create a customer external ID exists exception."""
    return create_http_exception(
        status_code=status.HTTP_409_CONFLICT,
        error_code=CustomerError.CUSTOMER_EXTERNAL_ID_EXISTS,
        message=f"Customer with external_id '{external_id}' already exists in this tenant",
        details={"external_id": external_id, "tenant_id": str(tenant_id)},
    )
