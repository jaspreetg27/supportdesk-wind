"""Thread service with state machine integration."""

import datetime as dt
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.errors import StateTransitionError, state_transition_exception, thread_not_found_exception
from supportdesk.common.pagination import PaginatedResponse, PaginationParams
from supportdesk.events.repository import ThreadEventRepository
from supportdesk.common.enums import ThreadState, PlatformType
from supportdesk.threads.repository import ThreadRepository
from supportdesk.threads.schemas import ThreadCreate, ThreadResponse, StateTransition
from supportdesk.threads.state_machine import ThreadStateMachine


class ThreadService:
    """Service for thread operations with state machine."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.thread_repo = ThreadRepository(db)
        self.event_repo = ThreadEventRepository(db)
    
    async def create_thread(self, tenant_id: UUID, thread_data: ThreadCreate) -> ThreadResponse:
        """Create a new thread."""
        # Validate customer exists and is active
        from supportdesk.customers.repository import CustomerRepository
        customer_repo = CustomerRepository(self.db)
        customer = await customer_repo.get_by_id(thread_data.customer_id, tenant_id)
        
        if not customer or not customer.is_active:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail="Customer not found or inactive"
            )
        
        thread_dict = thread_data.model_dump()
        thread = await self.thread_repo.create(tenant_id, thread_dict)
        
        # Log creation event with deterministic correlation_id
        from supportdesk.worker.tasks import generate_deterministic_uuid
        current_hour = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        hour_iso = current_hour.isoformat()
        correlation_id = generate_deterministic_uuid(str(thread.tenant_id), str(thread.id), hour_iso, "thread_created")
        
        await self.event_repo.create({
            "thread_id": thread.id,
            "event_type": "thread_created",
            "new_state": thread.state,
            "actor_type": "system",
            "correlation_id": correlation_id,
            "metadata": {"created_by": "api"}
        })
        
        return ThreadResponse.model_validate(thread)
    
    async def get_thread(
        self, 
        thread_id: UUID, 
        tenant_id: UUID, 
        include_messages: bool = False,
        message_limit: Optional[int] = None
    ) -> Optional[ThreadResponse]:
        """Get a thread by ID."""
        thread = await self.thread_repo.get_by_id(thread_id, tenant_id, include_messages, message_limit)
        if not thread:
            return None
        
        return ThreadResponse.model_validate(thread)
    
    async def list_threads(
        self,
        tenant_id: UUID,
        pagination: PaginationParams,
        state: Optional[ThreadState] = None,
        customer_id: Optional[UUID] = None,
        platform: Optional[PlatformType] = None,
        priority_min: Optional[int] = None,
        created_after: Optional[dt.datetime] = None
    ) -> PaginatedResponse[ThreadResponse]:
        """List threads with filtering and pagination."""
        threads, total = await self.thread_repo.list_paginated(
            tenant_id=tenant_id,
            offset=pagination.offset,
            limit=pagination.limit,
            state=state,
            customer_id=customer_id,
            platform=platform,
            priority_min=priority_min,
            created_after=created_after
        )
        
        thread_responses = [ThreadResponse.model_validate(thread) for thread in threads]
        
        return PaginatedResponse.create(
            items=thread_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    
    async def transition_state(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        transition: StateTransition
    ) -> ThreadResponse:
        """Transition thread state with validation."""
        # Get current thread
        thread = await self.thread_repo.get_by_id(thread_id, tenant_id)
        if not thread:
            raise thread_not_found_exception(thread_id, tenant_id)
        
        # Validate current state matches
        if thread.state != transition.current_state:
            raise StateTransitionError(
                current_state=str(thread.state),
                attempted_state=str(transition.next_state),
                allowed_transitions=[str(s) for s in ThreadStateMachine.get_allowed_transitions(thread.state)],
                thread_id=thread_id
            )
        
        # Validate transition
        try:
            ThreadStateMachine.validate_transition(thread.state, transition.next_state, thread_id)
        except StateTransitionError as e:
            raise state_transition_exception(e)
        
        # Perform transition
        updated_thread = await self.thread_repo.update_state(thread_id, tenant_id, transition.next_state)
        
        # Log transition event
        await self.event_repo.create({
            "thread_id": thread_id,
            "event_type": "state_transition",
            "old_state": transition.current_state,
            "new_state": transition.next_state,
            "actor_type": transition.actor_type,
            "actor_id": transition.actor_id,
            "correlation_id": transition.correlation_id,
            "metadata": {
                "reason": transition.reason,
                **transition.metadata
            }
        })
        
        return ThreadResponse.model_validate(updated_thread)
    
    async def auto_acknowledge_thread(self, thread_id: UUID, correlation_id: UUID) -> None:
        """Auto-acknowledge a thread after first message."""
        # Get thread without tenant check (internal operation)
        from sqlalchemy import select
        result = await self.db.execute(select(self.thread_repo.__class__.__table__).where(
            self.thread_repo.__class__.__table__.c.id == thread_id
        ))
        thread_data = result.first()
        
        if thread_data and thread_data.state == ThreadState.NEW:
            await self.thread_repo.update_state(thread_id, thread_data.tenant_id, ThreadState.ACKNOWLEDGED)
            
            # Log auto-acknowledgment
            await self.event_repo.create({
                "thread_id": thread_id,
                "event_type": "state_transition",
                "old_state": ThreadState.NEW,
                "new_state": ThreadState.ACKNOWLEDGED,
                "actor_type": "system",
                "correlation_id": correlation_id,
                "metadata": {
                    "reason": "Auto-acknowledged after first message",
                    "trigger": "first_message"
                }
            })

    async def soft_delete(self, thread_id: UUID, tenant_id: UUID) -> None:
        """Cascade soft delete a thread and all related data."""
        # Verify thread exists
        thread = await self.thread_repo.get_by_id(thread_id, tenant_id)
        if not thread:
            raise thread_not_found_exception(thread_id, tenant_id)
        
        await self.thread_repo.cascade_soft_delete_thread(thread_id, tenant_id)
