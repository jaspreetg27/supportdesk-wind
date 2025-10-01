"""Thread event FastAPI router."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.deps import TenantContext, get_tenant_context
from supportdesk.common.pagination import PaginatedResponse, PaginationParams, get_pagination_params
from supportdesk.common.pagination_helper import PaginationEnvelope
from supportdesk.database import get_db
from supportdesk.events.schemas import ThreadEventResponse
from supportdesk.events.service import ThreadEventService

router = APIRouter(prefix="/threads/{thread_id}/events", tags=["Thread Events"])


def get_event_service(db: AsyncSession = Depends(get_db)) -> ThreadEventService:
    """Dependency to get thread event service."""
    return ThreadEventService(db)


@router.get("/")
async def list_thread_events(
    thread_id: str,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
    tenant_context: TenantContext = Depends(get_tenant_context),
    event_service: ThreadEventService = Depends(get_event_service),
):
    """List events for a thread (audit trail)."""
    from uuid import UUID
    from fastapi import HTTPException
    import math
    
    try:
        thread_uuid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid thread_id format")
    
    from supportdesk.common.pagination_helper import create_pagination_envelope
    
    events, total = await event_service.list_events_raw(
        thread_id=thread_uuid,
        tenant_id=tenant_context.tenant_id,
        pagination=pagination
    )
    
    event_responses = [ThreadEventResponse.model_validate(e) for e in events]
    
    return create_pagination_envelope(
        items=event_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.get("/{event_id}", response_model=ThreadEventResponse)
async def get_thread_event(
    thread_id: str,
    event_id: str,
    tenant_context: TenantContext = Depends(get_tenant_context),
    event_service: ThreadEventService = Depends(get_event_service),
) -> ThreadEventResponse:
    """Get a specific thread event by ID."""
    from uuid import UUID
    from fastapi import HTTPException
    
    try:
        event_uuid = UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid event_id format")
    
    event = await event_service.get_event(
        event_id=event_uuid,
        tenant_id=tenant_context.tenant_id
    )
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return event
