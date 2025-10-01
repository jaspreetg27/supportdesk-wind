"""Background tasks for SupportDesk AI."""

import json
import hashlib
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from supportdesk.config import settings

# Create Celery app
celery_app = Celery("supportdesk")

# Configure Celery
celery_app.config_from_object("supportdesk.config", namespace="CELERY")

# Database setup for async tasks
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def generate_deterministic_uuid(input_string: str) -> UUID:
    """Generate a deterministic UUID from a string."""
    hash_object = hashlib.md5(input_string.encode())
    hex_dig = hash_object.hexdigest()
    return UUID(hex_dig)


@celery_app.task(bind=True, max_retries=3)
def debounce_flush(self, tenant_id: str, thread_id: str, window_id: str):
    """Debounce flush task with retry logic and idempotency."""
    import asyncio
    
    async def _flush():
        async with AsyncSessionLocal() as db:
            from supportdesk.events.repository import ThreadEventRepository
            from supportdesk.messages.repository import MessageRepository
            from supportdesk.threads.repository import ThreadRepository
            from supportdesk.threads.models import ThreadState
            
            event_repo = ThreadEventRepository(db)
            message_repo = MessageRepository(db)
            thread_repo = ThreadRepository(db)
            
            try:
                # Idempotency check
                existing_event = await event_repo.get_by_correlation_id(UUID(window_id))
                if existing_event:
                    return {"status": "already_processed", "window_id": window_id}
                
                # Count messages in window
                message_count = await message_repo.count_since_last_flush(UUID(thread_id))
                
                # Create aggregate event
                await event_repo.create({
                    "thread_id": UUID(thread_id),
                    "event_type": "debounce_aggregate",
                    "actor_type": "system",
                    "correlation_id": UUID(window_id),
                    "metadata": {
                        "window_id": window_id,
                        "message_count": message_count,
                        "processed_at": datetime.now(datetime.UTC).isoformat()
                    }
                })
                
                # Auto-transition if needed
                thread = await thread_repo.get_by_id(UUID(thread_id), UUID(tenant_id))
                if thread and thread.state == ThreadState.NEW:
                    await thread_repo.update_state(UUID(thread_id), UUID(tenant_id), ThreadState.ACKNOWLEDGED)
                    
                    # Log transition
                    await event_repo.create({
                        "thread_id": UUID(thread_id),
                        "event_type": "state_transition",
                        "old_state": ThreadState.NEW,
                        "new_state": ThreadState.ACKNOWLEDGED,
                        "actor_type": "system",
                        "correlation_id": UUID(window_id),
                        "metadata": {
                            "reason": "Auto-acknowledged after message burst",
                            "trigger": "debounce_flush",
                            "message_count": message_count
                        }
                    })
                
                return {"status": "processed", "message_count": message_count}
                
            except Exception as exc:
                # Exponential backoff: 30s, 60s, 120s
                countdown = 30 * (2 ** self.request.retries)
    
    return asyncio.run(_flush())


@celery_app.task
def example_task(message: str) -> str:
    """Example background task."""
    return f"Processed: {message}"


@celery_app.task
def escalation_tick():
    """Periodic task to escalate stale threads with idempotency."""
    import asyncio
    
    async def _escalate():
        async with AsyncSessionLocal() as db:
            from supportdesk.events.repository import ThreadEventRepository
            from supportdesk.threads.repository import ThreadRepository
            from supportdesk.threads.models import ThreadState
            from supportdesk.tenants.repository import TenantRepository
            
            event_repo = ThreadEventRepository(db)
            thread_repo = ThreadRepository(db)
            tenant_repo = TenantRepository(db)
            
            thresholds = json.loads(settings.escalation_thresholds)
            current_hour = datetime.now(datetime.UTC).replace(minute=0, second=0, microsecond=0)
            
            # Get all active tenants
            tenants, _ = await tenant_repo.list_paginated(offset=0, limit=1000, include_inactive=False)
            
            for tenant in tenants:
                stale_threads = await thread_repo.find_stale_threads(
                    tenant_id=tenant.id,
                    states=[ThreadState.ACKNOWLEDGED, ThreadState.IN_PROGRESS],
                    older_than_minutes=thresholds['escalation_minutes']
                )
                
                for thread in stale_threads:
                    # Generate deterministic escalation event ID
                    escalation_event_id = generate_deterministic_uuid(
                        f"escalation:{thread.id}:{current_hour.isoformat()}"
                    )
                    
                    # Check if already escalated this hour
                    existing_escalation = await event_repo.get_by_correlation_id(escalation_event_id)
                    if existing_escalation:
                        continue
                    
                    # Count previous auto-escalations
                    escalation_count = await event_repo.count_escalations(thread.id)
                    
                    if escalation_count >= thresholds['max_auto_escalations']:
                        # Log cap reached event
                        await event_repo.create({
                            "thread_id": thread.id,
                            "event_type": "escalation_cap_reached",
                            "actor_type": "system",
                            "correlation_id": escalation_event_id,
                            "metadata": {
                                "max_escalations": thresholds['max_auto_escalations'],
                                "current_priority": thread.priority,
                                "reason": "Maximum auto-escalations reached"
                            }
                        })
                        continue
                    
                    # Perform escalation
                    old_priority = thread.priority
                    new_priority = min(thread.priority + thresholds['priority_increment'], 10)
                    await thread_repo.update_priority(thread.id, new_priority)
                    
                    # Log escalation event
                    await event_repo.create({
                        "thread_id": thread.id,
                        "event_type": "auto_escalation",
                        "actor_type": "system",
                        "correlation_id": escalation_event_id,
                        "metadata": {
                            "old_priority": old_priority,
                            "new_priority": new_priority,
                            "escalation_count": escalation_count + 1,
                            "reason": f"Stale thread auto-escalation (#{escalation_count + 1})"
                        }
                    })
    
    return asyncio.run(_escalate())


@celery_app.task
def handle_message_debounce(tenant_id: str, thread_id: str, correlation_id: str):
    """Handle message debounce with Redis sliding window."""
    import redis
    
    redis_client = redis.from_url(settings.redis_url)
    key = f"debounce:{tenant_id}:{thread_id}"
    
    # Check if key exists (debounce window active)
    if not redis_client.exists(key):
        # Start new debounce window
        redis_client.setex(key, 5, correlation_id)  # 5 second TTL
        
        # In test mode (eager execution), run immediately without countdown
        if settings.celery_task_always_eager:
            debounce_flush.apply_async(args=[tenant_id, thread_id, correlation_id])
        else:
            # Schedule flush task with countdown in production
            debounce_flush.apply_async(
                args=[tenant_id, thread_id, correlation_id],
                countdown=5
            )
    else:
        # Extend existing window
        redis_client.expire(key, 5)


@celery_app.task
def health_check_task() -> dict:
    """Health check task for infrastructure testing."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(datetime.UTC).isoformat(),
        "worker": "celery"
    }
