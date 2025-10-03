"""Tenant database models."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from supportdesk.models.base import BaseModel

if TYPE_CHECKING:
    from supportdesk.customers.models import Customer
    from supportdesk.threads.models import Thread


class Tenant(BaseModel):
    """Tenant model representing an organization or workspace."""

    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    settings_: Mapped[dict] = mapped_column("settings", JSON, default=dict, nullable=False)

    # Relationships
    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")
    threads = relationship("Thread", back_populates="tenant", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_tenants_is_active", "is_active"),
    )


    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, slug='{self.slug}', name='{self.name}')>"
