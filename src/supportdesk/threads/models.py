"""Thread SQLAlchemy models."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, 
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID, ENUM as PostgreSQLEnum
from sqlalchemy.orm import relationship

from supportdesk.models.base import BaseModel

if TYPE_CHECKING:
    from supportdesk.customers.models import Customer
    from supportdesk.tenants.models import Tenant
    from supportdesk.messages.models import Message
    from supportdesk.events.models import ThreadEvent

# Import common enums
from supportdesk.common.enums import ActorType, PlatformType, ThreadState


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
    tenant = relationship("Tenant", back_populates="threads", lazy="selectin")
    customer = relationship("Customer", back_populates="threads", lazy="selectin")
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan", lazy="selectin")
    events = relationship("ThreadEvent", back_populates="thread", cascade="all, delete-orphan", lazy="selectin")
    
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
