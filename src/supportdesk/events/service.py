"""Thread event service for audit trail."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.pagination import PaginatedResponse, PaginationParams
from supportdesk.common.pagination_helper import create_pagination_envelope, PaginationEnvelope
from supportdesk.events.repository import ThreadEventRepository
from supportdesk.events.schemas import ThreadEventResponse


class ThreadEventService:
    """Service for thread event operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_repo = ThreadEventRepository(db)
    
    async def list_events(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        pagination: PaginationParams
    ) -> PaginationEnvelope[ThreadEventResponse]:
        """List events for a thread with pagination."""
        events, total = await self.event_repo.list_paginated(
            thread_id=thread_id,
            tenant_id=tenant_id,
            offset=pagination.offset,
            limit=pagination.limit
        )
        
        event_responses = [ThreadEventResponse.model_validate(event) for event in events]
        
        return create_pagination_envelope(
            items=event_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    
    async def list_events_raw(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        pagination: PaginationParams
    ) -> tuple[list, int]:
        """List events for a thread returning raw data."""
        return await self.event_repo.list_paginated(
            thread_id=thread_id,
            tenant_id=tenant_id,
            offset=pagination.offset,
            limit=pagination.limit
        )
    
    async def get_event(self, event_id: UUID, tenant_id: UUID) -> Optional[ThreadEventResponse]:
        """Get a single event by ID with tenant validation."""
        event = await self.event_repo.get_by_id(event_id, tenant_id)
        if not event:
            return None
        
        return ThreadEventResponse.model_validate(event)
