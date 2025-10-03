"""Thread Pydantic schemas for API serialization."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from supportdesk.common.enums import ThreadState, PlatformType, ActorType


class ThreadCreate(BaseModel):
    """Schema for creating a new thread."""
    
    customer_id: UUID
    platform: PlatformType
    platform_thread_id: Optional[str] = Field(None, max_length=255)
    subject: Optional[str] = Field(None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "550e8400-e29b-41d4-a716-446655440000",
                "platform": "whatsapp",
                "platform_thread_id": "wa_thread_123",
                "subject": "Product inquiry",
                "metadata": {
                    "source": "mobile_app",
                    "agent_id": "agent_123"
                }
            }
        }
    )


class ThreadResponse(BaseModel):
    """Schema for thread API responses."""
    
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    platform: PlatformType
    platform_thread_id: Optional[str]
    state: ThreadState
    priority: int = Field(ge=0, le=10)
    subject: Optional[str]
    message_count: int
    last_message_at: Optional[datetime]
    messages: Optional[list["MessageResponse"]] = None  # When included
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "customer_id": "550e8400-e29b-41d4-a716-446655440001",
                "platform": "whatsapp",
                "platform_thread_id": "wa_thread_123",
                "state": "new",
                "priority": 0,
                "subject": "Product inquiry",
                "message_count": 3,
                "last_message_at": "2024-01-15T10:30:00Z",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    )

    @classmethod
    def model_validate(cls, obj):
        """Custom validation to handle field mapping."""
        if hasattr(obj, 'metadata_'):
            # Create a dict with the correct field names, avoiding any lazy loading
            data = {
                'id': obj.id,
                'tenant_id': obj.tenant_id,
                'customer_id': obj.customer_id,
                'platform': obj.platform,
                'platform_thread_id': obj.platform_thread_id,
                'state': obj.state,
                'priority': obj.priority,
                'subject': obj.subject,
                'message_count': getattr(obj, 'message_count', 0),
                'last_message_at': obj.last_message_at,
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
            }
            # Only include messages if explicitly preloaded in __dict__
            if 'messages' in obj.__dict__:
                from supportdesk.messages.schemas import MessageResponse
                data['messages'] = [MessageResponse.model_validate(msg) for msg in obj.__dict__['messages']]
            
            # Only include events if explicitly preloaded in __dict__
            if 'events' in obj.__dict__:
                from supportdesk.events.schemas import ThreadEventResponse
                data['events'] = [ThreadEventResponse.model_validate(event) for event in obj.__dict__['events']]
            
            return cls(**data)
        return super().model_validate(obj)


class StateTransition(BaseModel):
    """Schema for thread state transitions."""
    
    current_state: ThreadState
    next_state: ThreadState
    reason: str = Field(min_length=1, max_length=500)
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: Optional[str] = None
    correlation_id: Optional[UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_state": "new",
                "next_state": "acknowledged",
                "reason": "Customer message received",
                "actor_type": "system",
                "actor_id": None,
                "correlation_id": "550e8400-e29b-41d4-a716-446655440002",
                "metadata": {
                    "message_count": 1,
                    "trigger": "auto_ack"
                }
            }
        }
    )


# Forward reference resolution
from supportdesk.messages.schemas import MessageResponse
ThreadResponse.model_rebuild()
