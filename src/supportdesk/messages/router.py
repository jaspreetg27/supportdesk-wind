"""Message FastAPI router."""

from typing import Annotated

from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.common.deps import TenantContext, get_tenant_context
from supportdesk.common.pagination import PaginatedResponse, PaginationParams, get_pagination_params
from supportdesk.database import get_db
from supportdesk.messages.schemas import MessageCreate, MessageResponse, MessageUpdate
from supportdesk.messages.service import MessageService

router = APIRouter(prefix="/threads/{thread_id}/messages", tags=["Messages"])


def get_message_service(db: AsyncSession = Depends(get_db)) -> MessageService:
    """Dependency to get message service."""
    return MessageService(db)


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    thread_id: str,
    message_data: MessageCreate,
    tenant_context: TenantContext = Depends(get_tenant_context),
    message_service: MessageService = Depends(get_message_service),
):
    """Create a new message in a thread."""
    from uuid import UUID
    from fastapi import HTTPException, Response
    
    try:
        thread_uuid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid thread_id format")
    
    message_response, is_new = await message_service.create_message(
        thread_id=thread_uuid,
        tenant_id=tenant_context.tenant_id,
        message_data=message_data
    )
    
    # Set existing flag and return appropriate status
    message_response.existing = not is_new
    
    # Adjust status for duplicates
    if not is_new:
        # FastAPI trick: return Response with status override but same body
        return Response(
            content=message_response.model_dump_json(),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
    return message_response  # 201 by decorator


@router.get("/")
async def list_messages(
    thread_id: str,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
    tenant_context: TenantContext = Depends(get_tenant_context),
    message_service: MessageService = Depends(get_message_service),
):
    """List messages for a thread with pagination."""
    from uuid import UUID
    from fastapi import HTTPException
    import math
    
    try:
        thread_uuid = UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid thread_id format")
    
    from supportdesk.common.pagination_helper import create_pagination_envelope
    
    messages, total = await message_service.list_messages_raw(
        thread_id=thread_uuid,
        tenant_id=tenant_context.tenant_id,
        pagination=pagination
    )
    
    message_responses = [MessageResponse.model_validate(m) for m in messages]
    
    return create_pagination_envelope(
        items=message_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    thread_id: str,
    message_id: str,
    request: Request,
    tenant_context: TenantContext = Depends(get_tenant_context),
    message_service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """Update a message."""
    from uuid import UUID
    from fastapi import HTTPException
    from pydantic import ValidationError
    import json
    
    try:
        message_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid message_id format")
    
    # Get raw request data to check for immutable fields
    try:
        body = await request.body()
        raw_data = json.loads(body) if body else {}
    except:
        raw_data = {}
    
    # Check for immutable fields in raw request
    immutable_fields = {'platform_message_id', 'type', 'thread_id'}
    attempted_immutable = set(raw_data.keys()) & immutable_fields
    
    if attempted_immutable:
        field = list(attempted_immutable)[0]  # Get first immutable field
        raise HTTPException(
            status_code=422, 
            detail={"error": "IMMUTABLE_FIELD", "attempted_field": field}
        )
    
    # Parse the update data normally
    from supportdesk.messages.schemas import MessageUpdate
    try:
        update_data = MessageUpdate.model_validate(raw_data)
    except ValidationError as e:
        # Let FastAPI handle normal validation errors
        raise HTTPException(status_code=422, detail=e.errors())
    
    return await message_service.update_message(
        message_id=message_uuid,
        tenant_id=tenant_context.tenant_id,
        update_data=update_data
    )


# Separate router for message updates (different path pattern)
message_router = APIRouter(prefix="/messages", tags=["Messages"])
