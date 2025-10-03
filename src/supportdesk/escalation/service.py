"""Escalation service for priority management with idempotency."""

import datetime as dt
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.errors import thread_not_found_exception
from supportdesk.events.repository import ThreadEventRepository
from supportdesk.redis_client import redis_client
from supportdesk.threads.repository import ThreadRepository


class EscalationService:
    """Service for thread priority escalation with idempotency."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.thread_repo = ThreadRepository(db)
        self.event_repo = ThreadEventRepository(db)
    
    async def escalate_priority(
        self, 
        *, 
        tenant_id: UUID, 
        thread_id: UUID, 
        reason: str, 
        actor: str, 
        correlation_id: UUID
    ) -> None:
        """
        Escalate thread priority with idempotency per hour.
        
        - Increments priority by 1, capped at 10
        - Idempotent per thread per rolling hour
        - Creates ThreadEvent for audit trail
        """
        # Load active thread (404 if not active or wrong tenant)
        thread = await self.thread_repo.get_by_id(thread_id, tenant_id, include_inactive=False)
        if not thread:
            raise thread_not_found_exception(thread_id, tenant_id)
        
        # Compute current hour bucket in UTC
        hour_key = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        
        # Idempotency check using Redis
        redis_key = f"esc:{tenant_id}:{thread_id}:{hour_key.isoformat()}"
        
        try:
            # Try Redis first
            is_set = await redis_client.set(redis_key, "1", nx=True, ex=3600)
            if not is_set:
                # Already escalated this hour, skip
                return
        except Exception:
            # Redis unavailable, fall back to checking ThreadEvent
            # Check for recent priority_escalated event within last hour
            cutoff_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
            
            # Get recent escalation events for this thread
            from supportdesk.events.models import ThreadEvent
            from sqlalchemy import select
            
            recent_escalation = await self.db.execute(
                select(ThreadEvent).where(
                    ThreadEvent.thread_id == thread_id,
                    ThreadEvent.event_type == "priority_escalated",
                    ThreadEvent.created_at >= cutoff_time,
                    ThreadEvent.is_active == True
                ).order_by(ThreadEvent.created_at.desc()).limit(1)
            )
            
            if recent_escalation.scalar_one_or_none():
                # Already escalated within the hour, skip
                return
        
        # Calculate new priority (cap at 10)
        new_priority = min(10, thread.priority + 1)
        
        # Update thread priority and timestamp
        thread.priority = new_priority
        thread.updated_at = dt.datetime.now(dt.timezone.utc)
        
        # Create ThreadEvent for audit trail
        await self.event_repo.create({
            "thread_id": thread_id,
            "event_type": "priority_escalated",
            "old_state": thread.state,
            "new_state": thread.state,
            "actor_type": "system",
            "actor_id": actor,
            "correlation_id": correlation_id,
            "metadata": {"reason": reason, "old_priority": thread.priority - 1, "new_priority": new_priority}
        })
        
        # Commit changes
        await self.db.commit()
