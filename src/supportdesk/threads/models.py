"""Thread SQLAlchemy models."""

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, 
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID, ENUM as PostgreSQLEnum
from sqlalchemy.orm import relationship

from supportdesk.models.base import BaseModel


class ThreadState(str, enum.Enum):
    """Thread state enumeration."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    NEEDS_REVIEW = "needs_review"
    URGENT = "urgent"
    RESOLVED = "resolved"
    CLOSED = "closed"


class PlatformType(str, enum.Enum):
    """Platform type enumeration."""
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    INTERNAL = "internal"


class ActorType(str, enum.Enum):
    """Actor type enumeration."""
    SYSTEM = "system"
    USER = "user"


class Thread(BaseModel):
    """Thread model for conversation management."""
    
    __tablename__ = "threads"
    tenant_id: UUID = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True
    )
    customer_id: UUID = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )
    platform: PlatformType = Column(
        PostgreSQLEnum('whatsapp', 'instagram', 'facebook', 'internal', name='platform_type'),
        nullable=False
    )
    platform_thread_id: Optional[str] = Column(
        String(255),
        nullable=True
    )
    state: ThreadState = Column(
        PostgreSQLEnum('new', 'acknowledged', 'in_progress', 'waiting_for_customer', 'needs_review', 'urgent', 'resolved', 'closed', name='thread_state'),
        nullable=False,
        default=ThreadState.NEW
    )
    priority: int = Column(
        Integer,
        nullable=False,
        default=0
    )
    subject: Optional[str] = Column(
        String(500),
        nullable=True
    )
    metadata_: dict[str, Any] = Column(
        "metadata",
        JSON,
        nullable=False,
        default=dict
    )
    last_message_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="threads")
    customer = relationship("Customer", back_populates="threads")
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")
    events = relationship("ThreadEvent", back_populates="thread", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("priority BETWEEN 0 AND 10", name="threads_priority_check"),
        UniqueConstraint(
            "tenant_id", "platform", "platform_thread_id",
            name="unique_platform_thread",
            deferrable=True,
            initially="IMMEDIATE"
        ),
    )
