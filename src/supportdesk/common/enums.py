"""Common enums used across the application."""

import enum


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


class MessageType(str, enum.Enum):
    """Message type enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    SYSTEM = "system"
