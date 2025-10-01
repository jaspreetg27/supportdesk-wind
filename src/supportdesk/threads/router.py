"""Thread FastAPI router."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.deps import TenantContext, get_tenant_context
from supportdesk.common.pagination import PaginatedResponse, PaginationParams, get_pagination_params
from supportdesk.database import get_db
from supportdesk.threads.models import ThreadState, PlatformType
from supportdesk.threads.schemas import ThreadCreate, ThreadResponse, StateTransition
from supportdesk.threads.service import ThreadService

router = APIRouter(prefix="/threads", tags=["Threads"])


def get_thread_service(db: AsyncSession = Depends(get_db)) -> ThreadService:
    """Dependency to get thread service."""
    return ThreadService(db)


@router.post("/", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    thread_data: ThreadCreate,
    tenant_context: TenantContext = Depends(get_tenant_context),
    thread_service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    """Create a new thread."""
    return await thread_service.create_thread(tenant_context.tenant_id, thread_data)


@router.get("/", response_model=PaginatedResponse[ThreadResponse])
async def list_threads(
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
    state: Optional[ThreadState] = Query(None, description="Filter by thread state"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    platform: Optional[PlatformType] = Query(None, description="Filter by platform"),
    priority_min: Optional[int] = Query(None, ge=0, le=10, description="Minimum priority filter"),
    created_after: Optional[datetime] = Query(None, description="Filter threads created after this date"),
    tenant_context: TenantContext = Depends(get_tenant_context),
    thread_service: ThreadService = Depends(get_thread_service),
) -> PaginatedResponse[ThreadResponse]:
    """List threads with filtering and pagination."""
    from uuid import UUID
    
    customer_uuid = None
    if customer_id:
        try:
            customer_uuid = UUID(customer_id)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Invalid customer_id format")
    
    return await thread_service.list_threads(
        tenant_id=tenant_context.tenant_id,
        pagination=pagination,
        state=state,
        customer_id=customer_uuid,
        platform=platform,
        priority_min=priority_min,
        created_after=created_after
    )


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    include_messages: Optional[str] = Query(None, description="Include messages: 'latest', 'all'"),
    message_limit: Optional[int] = Query(10, ge=1, le=100, description="Limit messages when include_messages=latest"),
    tenant_context: TenantContext = Depends(get_tenant_context),
    thread_service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    """Get a thread by ID."""
    from uuid import UUID
    from fastapi import HTTPException
    
    try:
        thread_uuid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid thread_id format")
    
    include_msgs = include_messages in ["latest", "all"]
    limit = message_limit if include_messages == "latest" else None
    
    thread = await thread_service.get_thread(
        thread_id=thread_uuid,
        tenant_id=tenant_context.tenant_id,
        include_messages=include_msgs,
        message_limit=limit
    )
    
    if not thread:
        from supportdesk.common.errors import thread_not_found_exception
        raise thread_not_found_exception(thread_uuid, tenant_context.tenant_id)
    
    return thread


@router.put("/{thread_id}/state", response_model=ThreadResponse)
async def transition_thread_state(
    thread_id: str,
    transition: StateTransition,
    tenant_context: TenantContext = Depends(get_tenant_context),
    thread_service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    """Transition thread state."""
    from uuid import UUID
    from fastapi import HTTPException
    
    try:
        thread_uuid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid thread_id format")
    
    return await thread_service.transition_state(
        thread_id=thread_uuid,
        tenant_id=tenant_context.tenant_id,
        transition=transition
    )
