"""Customer database models."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from supportdesk.models.base import BaseModel

if TYPE_CHECKING:
    from supportdesk.tenants.models import Tenant


class Customer(BaseModel):
    """Customer model representing a customer within a tenant."""

    __tablename__ = "customers"

    # Foreign key to tenant
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )

    # Customer fields
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="customers",
        lazy="select"
    )

    # Constraints and indexes
    __table_args__ = (
        # Unique constraint for external_id within a tenant
        UniqueConstraint(
            "tenant_id",
            "external_id",
            name="uq_customer_tenant_external_id"
        ),
        # Indexes for performance
        Index("idx_customers_tenant_id", "tenant_id"),
        Index("idx_customers_external_id", "tenant_id", "external_id"),
        Index("idx_customers_email", "tenant_id", "email"),
        Index("idx_customers_is_active", "tenant_id", "is_active"),
    )


    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, tenant_id={self.tenant_id}, name='{self.name}', external_id='{self.external_id}')>"
