"""Thread event repository for audit trail."""

from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.config import settings
from supportdesk.events.models import ThreadEvent


class ThreadEventRepository:
    """Repository for thread event operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, event_data: dict) -> ThreadEvent:
        """Create a new thread event."""
        event = ThreadEvent(
            thread_id=event_data["thread_id"],
            event_type=event_data["event_type"],
            old_state=event_data.get("old_state"),
            new_state=event_data.get("new_state"),
            actor_type=event_data.get("actor_type", "system"),
            actor_id=event_data.get("actor_id"),
            correlation_id=event_data.get("correlation_id"),
            metadata_=event_data.get("metadata", {})
        )
        
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
    
    async def list_paginated(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        offset: int,
        limit: int
    ) -> Tuple[list[ThreadEvent], int]:
        """Get paginated list of events for a thread with tenant validation."""
        
        # Verify thread belongs to tenant first
        from supportdesk.threads.models import Thread
        from supportdesk.common.errors import thread_not_found_exception
        thread_check = await self.db.execute(
            select(Thread).where(
                Thread.id == thread_id,
                Thread.tenant_id == tenant_id
            )
        )
        if not thread_check.scalar_one_or_none():
            raise thread_not_found_exception(thread_id, tenant_id)
        
        # Base query
        base_query = select(ThreadEvent).where(ThreadEvent.thread_id == thread_id)
        
        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        # Data query with ordering (newest first with stable tie-breaker)
        actual_limit = min(limit, settings.page_size_max)
        data_query = base_query.order_by(
            ThreadEvent.created_at.desc(),
            ThreadEvent.id.desc()  # Stable tie-breaker
        ).offset(offset).limit(actual_limit)
        
        data_result = await self.db.execute(data_query)
        events = list(data_result.scalars().all())
        
        return events, total
    
    async def get_by_correlation_id(self, correlation_id: UUID) -> Optional[ThreadEvent]:
        """Get an event by correlation ID for idempotency checks."""
        result = await self.db.execute(
            select(ThreadEvent).where(ThreadEvent.correlation_id == correlation_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, event_id: UUID, tenant_id: UUID) -> Optional[ThreadEvent]:
        """Get an event by ID with tenant validation."""
        # Join with thread to ensure tenant isolation
        from supportdesk.threads.models import Thread
        query = select(ThreadEvent).join(ThreadEvent.thread).where(
            ThreadEvent.id == event_id,
            Thread.tenant_id == tenant_id
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def count_escalations(self, thread_id: UUID) -> int:
        """Count auto-escalation events for a thread."""
        result = await self.db.execute(
            select(func.count()).where(
                ThreadEvent.thread_id == thread_id,
                ThreadEvent.event_type == "auto_escalation"
            )
        )
        return result.scalar() or 0
