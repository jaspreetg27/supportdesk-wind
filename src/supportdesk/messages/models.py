"""Message SQLAlchemy models."""

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, JSON, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID, ENUM as PostgreSQLEnum
from sqlalchemy.orm import relationship

from supportdesk.models.base import BaseModel


class MessageType(str, enum.Enum):
    """Message type enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    SYSTEM = "system"


class Message(BaseModel):
    """Message model for thread conversations."""
    
    __tablename__ = "messages"
    thread_id: UUID = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    platform_message_id: str = Column(
        String(255),
        nullable=False
    )
    type: MessageType = Column(
        PostgreSQLEnum('inbound', 'outbound', 'system', name='message_type'),
        nullable=False
    )
    content: Optional[str] = Column(
        Text,
        nullable=True
    )
    metadata_: dict[str, Any] = Column(
        "metadata",
        JSON,
        nullable=False,
        default=dict
    )
    sent_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    thread = relationship("Thread", back_populates="messages")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "thread_id", "platform_message_id",
            name="unique_platform_message"
        ),
    )
