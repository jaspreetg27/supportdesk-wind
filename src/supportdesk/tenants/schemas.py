"""Tenant Pydantic schemas for API serialization."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from supportdesk.common.utils import validate_slug


class TenantBase(BaseModel):
    """Base tenant schema with common fields."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Tenant display name"
    )
    slug: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique tenant identifier (URL-safe)"
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Tenant-specific configuration settings"
    )

    @field_validator("slug")
    @classmethod
    def validate_slug_format(cls, v: str) -> str:
        """Validate and normalize slug."""
        return validate_slug(v)


class TenantCreate(TenantBase):
    """Schema for creating a new tenant."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "settings": {
                    "timezone": "UTC",
                    "locale": "en-US",
                    "features": ["chat", "email"]
                }
            }
        }
    )


class TenantUpdate(BaseModel):
    """Schema for updating an existing tenant."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Tenant display name"
    )
    settings: Optional[dict[str, Any]] = Field(
        None,
        description="Tenant-specific configuration settings"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation Ltd",
                "settings": {
                    "timezone": "America/New_York",
                    "locale": "en-US",
                    "features": ["chat", "email", "phone"]
                }
            }
        }
    )


class TenantResponse(TenantBase):
    """Schema for tenant API responses."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "settings": {
                    "timezone": "UTC",
                    "locale": "en-US",
                    "features": ["chat", "email"]
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
        if hasattr(obj, 'settings_'):
            # Create a dict with the correct field names
            data = {
                'id': obj.id,
                'name': obj.name,
                'slug': obj.slug,
                'settings': obj.settings_,  # Map settings_ to settings
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
                'is_active': obj.is_active,
            }
            return cls(**data)
        return super().model_validate(obj)
