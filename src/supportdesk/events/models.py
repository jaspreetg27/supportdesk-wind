"""Thread event SQLAlchemy models."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, JSON, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID, ENUM as PostgreSQLEnum
from sqlalchemy.orm import relationship

from supportdesk.models.base import BaseModel
from supportdesk.threads.models import ActorType, ThreadState


class ThreadEvent(BaseModel):
    """Thread event model for audit trail."""
    
    __tablename__ = "thread_events"
    thread_id: UUID = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    event_type: str = Column(
        String(100),
        nullable=False
    )
    old_state: Optional[ThreadState] = Column(
        PostgreSQLEnum('new', 'acknowledged', 'in_progress', 'waiting_for_customer', 'needs_review', 'urgent', 'resolved', 'closed', name='thread_state'),
        nullable=True
    )
    new_state: Optional[ThreadState] = Column(
        PostgreSQLEnum('new', 'acknowledged', 'in_progress', 'waiting_for_customer', 'needs_review', 'urgent', 'resolved', 'closed', name='thread_state'),
        nullable=True
    )
    actor_type: ActorType = Column(
        PostgreSQLEnum('system', 'user', name='actor_type'),
        nullable=False,
        default=ActorType.SYSTEM
    )
    actor_id: Optional[str] = Column(
        String(255),
        nullable=True
    )
    correlation_id: Optional[UUID] = Column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True
    )
    metadata_: dict[str, Any] = Column(
        "metadata",
        JSON,
        nullable=False,
        default=dict
    )
    
    # Relationships
    thread = relationship("Thread", back_populates="events")
