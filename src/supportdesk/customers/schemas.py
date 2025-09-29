"""Customer Pydantic schemas for API serialization."""

import re
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Accept common formatting by stripping spaces, (), -, then validate E.164-ish
_PHONE_CORE_RE = re.compile(r"^\+?[0-9]{7,15}$")

def _normalize_phone(raw: str) -> str:
    # keep digits and + only, drop spaces, dashes, parentheses etc.
    cleaned = re.sub(r"[^\d+]", "", raw)
    return cleaned


class CustomerBase(BaseModel):
    """Base customer schema with common fields."""

    external_id: Optional[str] = Field(
        None,
        max_length=255,
        description="External system identifier (unique within tenant)"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Customer full name"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Customer email address"
    )
    phone: Optional[str] = Field(
        None,
        description="Customer phone number in E.164 format"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional customer metadata"
    )

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v is None or v == "":
            return None
        norm = _normalize_phone(v)
        if not _PHONE_CORE_RE.match(norm):
            raise ValueError("invalid phone number format")
        return norm


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "CRM-12345",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "metadata": {
                    "source": "website",
                    "priority": "high",
                    "tags": ["vip", "enterprise"]
                }
            }
        }
    )


class CustomerUpdate(BaseModel):
    """Schema for updating an existing customer."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Customer full name"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Customer email address"
    )
    phone: Optional[str] = Field(
        None,
        description="Customer phone number in E.164 format"
    )
    metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Additional customer metadata"
    )

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v is None or v == "":
            return None
        norm = _normalize_phone(v)
        if not _PHONE_CORE_RE.match(norm):
            raise ValueError("invalid phone number format")
        return norm

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Smith",
                "email": "john.smith@example.com",
                "phone": "+1987654321",
                "metadata": {
                    "source": "mobile_app",
                    "priority": "medium",
                    "tags": ["mobile", "active"]
                }
            }
        }
    )


class CustomerResponse(CustomerBase):
    """Schema for customer API responses."""

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "external_id": "CRM-12345",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "metadata": {
                    "source": "website",
                    "priority": "high",
                    "tags": ["vip", "enterprise"]
                },
                "is_active": True,
                "created_at": "2024-12-29T15:30:00Z",
                "updated_at": "2024-12-29T15:30:00Z"
            }
        }
    )

    @classmethod
    def model_validate(cls, obj):
        """Custom validation to handle field mapping."""
        if hasattr(obj, 'metadata_'):
            # Create a dict with the correct field names
            data = {
                'id': obj.id,
                'tenant_id': obj.tenant_id,
                'external_id': obj.external_id,
                'name': obj.name,
                'email': obj.email,
                'phone': obj.phone,
                'metadata': obj.metadata_,  # Map metadata_ to metadata
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
                'is_active': obj.is_active,
            }
            return cls(**data)
        return super().model_validate(obj)
