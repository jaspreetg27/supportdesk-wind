"""Customer repository for database operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.errors import external_id_already_exists_exception
from supportdesk.customers.models import Customer
from supportdesk.customers.schemas import CustomerCreate, CustomerUpdate


class CustomerRepository:
    """Repository for customer database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        include_inactive: bool = False
    ) -> Optional[Customer]:
        """Get customer by ID within a tenant."""
        query = select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id
        )
        if not include_inactive:
            query = query.where(Customer.is_active == True)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self,
        tenant_id: UUID,
        external_id: str,
        include_inactive: bool = False
    ) -> Optional[Customer]:
        """Get customer by external ID within a tenant."""
        query = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.external_id == external_id
        )
        if not include_inactive:
            query = query.where(Customer.is_active == True)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: UUID,
        offset: int,
        limit: int,
        include_inactive: bool = False
    ) -> tuple[list[Customer], int]:
        """Get paginated list of customers within a tenant."""
        # Base query for filtering
        base_query = select(Customer).where(Customer.tenant_id == tenant_id)
        if not include_inactive:
            base_query = base_query.where(Customer.is_active == True)

        # Count query
        count_query = select(func.count()).select_from(
            base_query.subquery()
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        # Data query with pagination - enforce max page size limit
        from supportdesk.config import settings
        actual_limit = min(limit, settings.page_size_max)
        data_query = base_query.order_by(Customer.created_at.desc()).offset(offset).limit(actual_limit)
        data_result = await self.db.execute(data_query)
        customers = list(data_result.scalars().all())

        return customers, total

    async def create(self, tenant_id: UUID, customer_data: CustomerCreate) -> Customer:
        """Create a new customer within a tenant."""
        customer = Customer(
            tenant_id=tenant_id,
            external_id=customer_data.external_id,
            name=customer_data.name,
            email=customer_data.email,
            phone=customer_data.phone,
            metadata_=customer_data.metadata,
        )

        self.db.add(customer)

        try:
            await self.db.commit()
            await self.db.refresh(customer)
            return customer
        except IntegrityError as e:
            await self.db.rollback()
            # Check if it's an external_id uniqueness violation
            if "uq_customer_tenant_external_id" in str(e) or "external_id" in str(e):
                if customer_data.external_id:
                    raise external_id_already_exists_exception(customer_data.external_id, tenant_id)
            raise

    async def update(self, customer: Customer, customer_data: CustomerUpdate) -> Customer:
        """Update an existing customer."""
        if customer_data.name is not None:
            customer.name = customer_data.name
        if customer_data.email is not None:
            customer.email = customer_data.email
        if customer_data.phone is not None:
            customer.phone = customer_data.phone
        if customer_data.metadata is not None:
            customer.metadata_ = customer_data.metadata

        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def soft_delete(self, customer: Customer) -> None:
        """Soft delete a customer by setting is_active to False."""
        customer.is_active = False
        await self.db.commit()

    async def exists_by_external_id(
        self,
        tenant_id: UUID,
        external_id: str,
        exclude_id: Optional[UUID] = None
    ) -> bool:
        """Check if a customer with the given external_id exists in the tenant."""
        query = select(Customer.id).where(
            Customer.tenant_id == tenant_id,
            Customer.external_id == external_id,
            Customer.is_active == True
        )
        if exclude_id:
            query = query.where(Customer.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
