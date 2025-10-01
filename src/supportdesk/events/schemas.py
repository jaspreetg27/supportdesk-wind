"""Thread event Pydantic schemas for API serialization."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from supportdesk.threads.models import ThreadState, ActorType


class ThreadEventResponse(BaseModel):
    """Schema for thread event API responses."""
    
    id: UUID
    thread_id: UUID
    event_type: str
    old_state: Optional[ThreadState]
    new_state: Optional[ThreadState]
    actor_type: ActorType
    actor_id: Optional[UUID]
    correlation_id: Optional[UUID]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "event_type": "state_transition",
                "old_state": "new",
                "new_state": "acknowledged",
                "actor_type": "system",
                "actor_id": None,
                "correlation_id": "550e8400-e29b-41d4-a716-446655440002",
                "metadata": {
                    "reason": "Auto-acknowledged after message",
                    "message_count": 1
                },
                "created_at": "2024-01-15T10:00:05Z"
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
                'thread_id': obj.thread_id,
                'event_type': obj.event_type,
                'old_state': obj.old_state,
                'new_state': obj.new_state,
                'actor_type': obj.actor_type,
                'actor_id': obj.actor_id,
                'correlation_id': obj.correlation_id,
                'metadata': obj.metadata_,
                'created_at': obj.created_at,
                'updated_at': obj.updated_at,
            }
            return cls(**data)
        return super().model_validate(obj)
