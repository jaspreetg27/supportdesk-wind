"""Thread repository with tenant isolation and filtering."""

from datetime import datetime, timedelta, UTC
from typing import Optional, Tuple
from uuid import UUID
import datetime as dt

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from supportdesk.common.errors import platform_thread_exists_exception
from supportdesk.config import settings
from supportdesk.threads.models import Thread
from supportdesk.common.enums import ThreadState, PlatformType


class ThreadRepository:
    """Repository for thread operations with tenant isolation."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, tenant_id: UUID, thread_data: dict) -> Thread:
        """Create a new thread within a tenant."""
        try:
            thread = Thread(
                tenant_id=tenant_id,
                customer_id=thread_data["customer_id"],
                platform=thread_data["platform"],
                platform_thread_id=thread_data.get("platform_thread_id"),
                subject=thread_data.get("subject"),
                metadata_=thread_data.get("metadata", {}),
                state=ThreadState.NEW,
                priority=0
            )
            
            self.db.add(thread)
            await self.db.commit()
            await self.db.refresh(thread)
            
            # Set message count for new thread (always 0)
            thread.message_count = 0
            return thread
            
        except IntegrityError as e:
            await self.db.rollback()
            if "unique_platform_thread" in str(e):
                # Find existing thread to get its ID
                existing = await self.db.execute(
                    select(Thread).where(
                        Thread.tenant_id == tenant_id,
                        Thread.platform == thread_data["platform"],
                        Thread.platform_thread_id == thread_data.get("platform_thread_id")
                    )
                )
                existing_thread = existing.scalar_one()
                raise platform_thread_exists_exception(
                    platform=thread_data["platform"],
                    platform_thread_id=thread_data.get("platform_thread_id"),
                    tenant_id=tenant_id,
                    existing_thread_id=existing_thread.id
                )
            raise
    
    async def get_by_id(self, thread_id: UUID, tenant_id: UUID, include_messages: bool = False, message_limit: int = 10, include_inactive: bool = False) -> Optional[Thread]:
        """Get a thread by ID within tenant scope."""
        query = select(Thread).where(
            Thread.id == thread_id,
            Thread.tenant_id == tenant_id
        )
        if not include_inactive:
            query = query.where(Thread.is_active == True)
        
        result = await self.db.execute(query)
        thread = result.scalar_one_or_none()
        
        if not thread:
            return None
        
        if include_messages:
            # Run separate SELECT for messages to avoid lazy loading
            from supportdesk.messages.models import Message
            messages_query = select(Message).where(
                Message.thread_id == thread_id,
                Message.is_active == True
            ).order_by(
                Message.sent_at.desc().nulls_last(),
                Message.created_at.desc()
            ).limit(message_limit)
            
            messages_result = await self.db.execute(messages_query)
            messages = messages_result.scalars().all()
            
            # Explicitly assign to __dict__ to avoid relationship access
            thread.__dict__['messages'] = list(messages)
            thread.message_count = len(messages)
        else:
            # Count messages separately without loading them
            from supportdesk.messages.models import Message
            count_result = await self.db.execute(
                select(func.count()).where(
                    Message.thread_id == thread_id,
                    Message.is_active == True
                )
            )
            thread.message_count = count_result.scalar() or 0
        
        return thread
    
    async def list_paginated(
        self,
        tenant_id: UUID,
        offset: int,
        limit: int,
        state: Optional[ThreadState] = None,
        customer_id: Optional[UUID] = None,
        platform: Optional[PlatformType] = None,
        priority_min: Optional[int] = None,
        created_after: Optional[datetime] = None
    ) -> Tuple[list[Thread], int]:
        """Get paginated list of threads within a tenant with filters."""
        
        # Base query with tenant isolation
        base_query = select(Thread).where(Thread.tenant_id == tenant_id)
        
        # Apply filters
        if state:
            base_query = base_query.where(Thread.state == state)
        if customer_id:
            base_query = base_query.where(Thread.customer_id == customer_id)
        if platform:
            base_query = base_query.where(Thread.platform == platform)
        if priority_min is not None:
            base_query = base_query.where(Thread.priority >= priority_min)
        if created_after:
            base_query = base_query.where(Thread.created_at >= created_after)
        
        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        # Data query with ordering and pagination
        actual_limit = min(limit, settings.page_size_max)
        data_query = base_query.order_by(
            Thread.last_message_at.desc().nulls_last(),
            Thread.created_at.desc()
        ).offset(offset).limit(actual_limit)
        
        data_result = await self.db.execute(data_query)
        threads = list(data_result.scalars().all())
        
        # Add message counts
        for thread in threads:
            count_result = await self.db.execute(
                select(func.count()).select_from(
                    select(1).where(
                        Thread.id == thread.id
                    ).join(Thread.messages).subquery()
                )
            )
            thread.message_count = count_result.scalar() or 0
        
        return threads, total
    
    async def update_state(self, thread_id: UUID, tenant_id: UUID, new_state: ThreadState) -> Optional[Thread]:
        """Update thread state within tenant scope."""
        result = await self.db.execute(
            select(Thread).where(
                Thread.id == thread_id,
                Thread.tenant_id == tenant_id
            )
        )
        thread = result.scalar_one_or_none()
        
        if thread:
            thread.state = new_state
            # Auto-adjust priority based on state
            if new_state == ThreadState.URGENT:
                thread.priority = 10
            elif new_state == ThreadState.RESOLVED:
                thread.priority = 0
            
            await self.db.commit()
            await self.db.refresh(thread)
        
        return thread
    
    async def update_priority(self, thread_id: UUID, new_priority: int) -> Optional[Thread]:
        """Update thread priority."""
        result = await self.db.execute(
            select(Thread).where(Thread.id == thread_id)
        )
        thread = result.scalar_one_or_none()
        
        if thread:
            thread.priority = min(max(new_priority, 0), 10)  # Clamp between 0-10
            await self.db.commit()
            await self.db.refresh(thread)
        
        return thread
    
    async def update_last_message_at(self, thread_id: UUID, message_time: datetime) -> None:
        """Update the last_message_at timestamp for a thread."""
        result = await self.db.execute(
            select(Thread).where(Thread.id == thread_id)
        )
        thread = result.scalar_one_or_none()
        
        if thread:
            # Use the later of sent_at or current time
            current_time = datetime.now(UTC)
            thread.last_message_at = max(message_time, current_time) if message_time else current_time
            await self.db.commit()
    
    async def find_stale_threads(
        self,
        tenant_id: UUID,
        states: list[ThreadState],
        older_than_minutes: int
    ) -> list[Thread]:
        """Find threads that haven't been updated recently."""
        cutoff_time = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=older_than_minutes)
        
        query = select(Thread).where(
            Thread.tenant_id == tenant_id,
            Thread.state.in_(states),
            Thread.updated_at < cutoff_time
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def cascade_soft_delete_thread(self, thread_id: UUID, tenant_id: UUID) -> None:
        """Cascade soft delete a thread and all related messages and events."""
        now = dt.datetime.now(dt.timezone.utc)
        
        # Soft delete the thread
        await self.db.execute(
            update(Thread)
            .where(Thread.id == thread_id, Thread.tenant_id == tenant_id)
            .values(is_active=False, updated_at=now)
        )
        
        # Import here to avoid circular imports
        from supportdesk.messages.models import Message
        from supportdesk.events.models import ThreadEvent
        
        # Soft delete all messages for this thread
        await self.db.execute(
            update(Message)
            .where(Message.thread_id == thread_id)
            .values(is_active=False, updated_at=now)
        )
        
        # Soft delete all events for this thread
        await self.db.execute(
            update(ThreadEvent)
            .where(ThreadEvent.thread_id == thread_id)
            .values(is_active=False, updated_at=now)
        )
        
        await self.db.commit()
