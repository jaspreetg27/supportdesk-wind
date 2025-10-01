"""Custom exceptions and error handling."""

from typing import Any, List, Optional
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
    detail = {
        "error": error_code,
        "message": message,
    }
    if details:
        detail.update(details)

    return HTTPException(status_code=status_code, detail=detail)


def tenant_not_found_exception(tenant_id: UUID) -> HTTPException:
    """Create a 404 exception for tenant not found."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "TENANT_NOT_FOUND",
            "message": f"Tenant with id '{tenant_id}' not found or inactive",
            "tenant_id": str(tenant_id)
        }
    )


def customer_not_found_exception(customer_id: UUID, tenant_id: UUID) -> HTTPException:
    """Create a 404 exception for customer not found."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "CUSTOMER_NOT_FOUND",
            "message": f"Customer with id '{customer_id}' not found in tenant '{tenant_id}'",
            "customer_id": str(customer_id),
            "tenant_id": str(tenant_id)
        }
    )


def thread_not_found_exception(thread_id: UUID, tenant_id: UUID) -> HTTPException:
    """Create a 404 exception for thread not found."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "THREAD_NOT_FOUND",
            "message": f"Thread with id '{thread_id}' not found in tenant '{tenant_id}'",
            "thread_id": str(thread_id),
            "tenant_id": str(tenant_id)
        }
    )


def message_not_found_exception(message_id: UUID, tenant_id: UUID) -> HTTPException:
    """Create a 404 exception for message not found."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "MESSAGE_NOT_FOUND",
            "message": f"Message with id '{message_id}' not found in tenant '{tenant_id}'",
            "message_id": str(message_id),
            "tenant_id": str(tenant_id)
        }
    )


def slug_already_exists_exception(slug: str) -> HTTPException:
    """Create a 409 exception for duplicate slug."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "TENANT_SLUG_EXISTS",
            "message": f"Tenant with slug '{slug}' already exists",
            "slug": slug
        }
    )


def external_id_already_exists_exception(external_id: str, tenant_id: UUID) -> HTTPException:
    """Create a 409 exception for duplicate external_id."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "CUSTOMER_EXTERNAL_ID_EXISTS",
            "message": f"Customer with external_id '{external_id}' already exists in tenant '{tenant_id}'",
            "external_id": external_id,
            "tenant_id": str(tenant_id)
        }
    )


def platform_thread_exists_exception(
    platform: str, 
    platform_thread_id: str, 
    tenant_id: UUID,
    existing_thread_id: UUID
) -> HTTPException:
    """Create a 409 exception for duplicate platform thread."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "PLATFORM_THREAD_EXISTS",
            "message": f"Thread with platform_thread_id '{platform_thread_id}' already exists for this tenant and platform",
            "platform": platform,
            "platform_thread_id": platform_thread_id,
            "existing_thread_id": str(existing_thread_id),
            "tenant_id": str(tenant_id)
        }
    )


def platform_message_exists_exception(
    thread_id: UUID,
    platform_message_id: str,
    existing_message_id: UUID
) -> HTTPException:
    """Create a 409 exception for duplicate platform message."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "PLATFORM_MESSAGE_EXISTS",
            "message": f"Message with platform_message_id '{platform_message_id}' already exists in this thread",
            "thread_id": str(thread_id),
            "platform_message_id": platform_message_id,
            "existing_message_id": str(existing_message_id)
        }
    )


def immutable_field_exception(attempted_field: str) -> HTTPException:
    """Create a 422 exception for immutable field modification."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "IMMUTABLE_FIELD",
            "message": f"Cannot modify immutable field '{attempted_field}'",
            "immutable_fields": ["platform_message_id", "type", "thread_id"],
            "allowed_fields": ["content", "metadata", "sent_at"],
            "attempted_field": attempted_field
        }
    )


class StateTransitionError(Exception):
    """Exception for invalid state transitions."""
    
    def __init__(
        self,
        current_state: str,
        attempted_state: str,
        allowed_transitions: List[str],
        thread_id: UUID
    ):
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.allowed_transitions = allowed_transitions
        self.thread_id = thread_id
        super().__init__(f"Cannot transition from '{current_state}' to '{attempted_state}'")


def state_transition_exception(error: StateTransitionError) -> HTTPException:
    """Create a 422 exception for invalid state transition."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "STATE_TRANSITION_INVALID",
            "message": f"Cannot transition from '{error.current_state}' to '{error.attempted_state}'",
            "details": {
                "current_state": error.current_state,
                "attempted_state": error.attempted_state,
                "allowed_transitions": error.allowed_transitions,
                "thread_id": str(error.thread_id)
            }
        }
    )
