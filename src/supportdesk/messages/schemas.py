from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from supportdesk.common.enums import MessageType


class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    
    platform_message_id: str = Field(max_length=255)
    type: MessageType
    content: Optional[str] = None
    sent_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @model_validator(mode='after')
    def validate_content_for_type(self):
        """Validate content is provided for inbound/outbound messages."""
        if self.type in [MessageType.INBOUND, MessageType.OUTBOUND] and not self.content:
            raise ValueError('Content required for inbound/outbound messages')
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platform_message_id": "wa_msg_123",
                "type": "inbound",
                "content": "Hello, I need help with my order",
                "sent_at": "2024-01-15T15:05:00Z",
                "metadata": {
                    "phone_number": "+1234567890",
                    "media_type": "text"
                }
            }
        }
    )


class MessageResponse(BaseModel):
    """Schema for message API responses."""
    
    id: UUID
    platform_message_id: str
    type: MessageType
    content: Optional[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    existing: bool = False  # Indicates if this was a duplicate

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "platform_message_id": "wa_msg_123",
                "type": "inbound",
                "content": "Hello, I need help with my order",
                "sent_at": "2024-01-15T15:05:00Z",
                "created_at": "2024-01-15T15:05:03Z",
                "existing": False
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
                'platform_message_id': obj.platform_message_id,
                'type': obj.type,
                'content': obj.content,
                'metadata': obj.metadata_ if hasattr(obj, 'metadata_') else {},
                'sent_at': obj.sent_at,
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
                'existing': getattr(obj, 'existing', False)
            }
            return cls(**data)
        return super().model_validate(obj)


class MessageUpdate(BaseModel):
    """Schema for updating an existing message."""
    
    content: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    sent_at: Optional[datetime] = None
    

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Updated message content",
                "metadata": {
                    "edited": True,
                    "edit_reason": "typo correction"
                }
            }
        }
    )
