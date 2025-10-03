"""Message service with debounce integration."""

from typing import Optional
from uuid import UUID, uuid4
import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from supportdesk.common.errors import message_not_found_exception, immutable_field_exception
from supportdesk.common.pagination import PaginatedResponse, PaginationParams
from supportdesk.config import settings
from supportdesk.common.enums import MessageType
from supportdesk.messages.repository import MessageRepository
from supportdesk.messages.schemas import MessageCreate, MessageResponse, MessageUpdate
from supportdesk.threads.repository import ThreadRepository


class MessageService:
    """Service for message operations with debounce integration."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.thread_repo = ThreadRepository(db)
    
    async def create_message(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        message_data: MessageCreate
    ) -> tuple[MessageResponse, bool]:
        """Create a message with deduplication and debounce handling."""
        
        # Verify thread exists and belongs to tenant
        thread = await self.thread_repo.get_by_id(thread_id, tenant_id)
        if not thread:
            raise thread_not_found_exception(thread_id, tenant_id)
        
        # Try to create message, handle deduplication
        try:
            message = await self.message_repo.create_message(thread_id, message_data.model_dump())
            is_new = True
        except IntegrityError as e:
            # Handle deduplication - find existing message
            await self.db.rollback()
            message = await self.message_repo.get_by_platform_message_id(
                thread_id, message_data.platform_message_id
            )
            if not message:
                raise  # Re-raise if we can't find the existing message
            is_new = False
        
        if is_new:
            # Update thread's last_message_at
            message_time = message.sent_at or message.created_at
            await self.thread_repo.update_last_message_at(thread_id, message_time)
            # Trigger debounce for inbound messages
            if message.type == MessageType.INBOUND:
                await self._trigger_debounce(tenant_id, thread_id)
                
                # In test mode, also perform immediate auto-ACK if enabled
                if settings.auto_ack_test_mode:
                    await self._perform_auto_ack(tenant_id, thread_id)
        
        # Create response manually to avoid lazy loading issues
        response = MessageResponse(
            id=message.id,
            platform_message_id=message.platform_message_id,
            type=message.type,
            content=message.content,
            metadata=message.metadata_ if hasattr(message, 'metadata_') else {},
            sent_at=message.sent_at,
            created_at=message.created_at,
            updated_at=message.updated_at,
            existing=not is_new  # Set existing flag based on is_new
        )
        
        return response, is_new
    
    async def list_messages_raw(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        pagination: PaginationParams
    ) -> tuple[list, int]:
        """List messages for a thread returning raw data."""
        return await self.message_repo.list_paginated(
            thread_id=thread_id,
            tenant_id=tenant_id,
            offset=pagination.offset,
            limit=pagination.limit
        )
    
    async def get_message(self, message_id: UUID, tenant_id: UUID) -> Optional[MessageResponse]:
        """Get a message by ID."""
        message = await self.message_repo.get_by_id(message_id, tenant_id)
        if not message:
            return None
        
        # Create response manually to avoid lazy loading issues
        return MessageResponse(
            id=message.id,
            platform_message_id=message.platform_message_id,
            type=message.type,
            content=message.content,
            metadata=message.metadata_ if hasattr(message, 'metadata_') else {},
            sent_at=message.sent_at,
            created_at=message.created_at,
            updated_at=message.updated_at,
            existing=getattr(message, 'existing', False)
        )
    
    async def list_messages(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        pagination: PaginationParams
    ) -> PaginatedResponse[MessageResponse]:
        """List messages for a thread with pagination."""
        messages, total = await self.message_repo.list_paginated(
            thread_id=thread_id,
            tenant_id=tenant_id,
            offset=pagination.offset,
            limit=pagination.limit
        )
        
        # Create responses manually to avoid lazy loading issues
        message_responses = []
        for message in messages:
            response = MessageResponse(
                id=message.id,
                platform_message_id=message.platform_message_id,
                type=message.type,
                content=message.content,
                metadata=message.metadata_ if hasattr(message, 'metadata_') else {},
                sent_at=message.sent_at,
                created_at=message.created_at,
                updated_at=message.updated_at,
                existing=getattr(message, 'existing', False)
            )
            message_responses.append(response)
        
        return PaginatedResponse.create(
            items=message_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    
    async def update_message(
        self,
        message_id: UUID,
        tenant_id: UUID,
        update_data: MessageUpdate
    ) -> MessageResponse:
        """Update a message with immutability checks."""
        
        # Get existing message
        existing_message = await self.message_repo.get_by_id(message_id, tenant_id)
        if not existing_message:
            raise message_not_found_exception(message_id, tenant_id)
        
        # Convert update data, excluding None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        
        # Check for sent_at update when already set
        if "sent_at" in update_dict and existing_message.sent_at is not None:
            raise immutable_field_exception("sent_at")
        
        # Perform update
        updated_message = await self.message_repo.update(message_id, tenant_id, update_dict)
        
        # Create response manually to avoid lazy loading issues
        return MessageResponse(
            id=updated_message.id,
            platform_message_id=updated_message.platform_message_id,
            type=updated_message.type,
            content=updated_message.content,
            metadata=updated_message.metadata_ if hasattr(updated_message, 'metadata_') else {},
            sent_at=updated_message.sent_at,
            created_at=updated_message.created_at,
            updated_at=updated_message.updated_at,
            existing=getattr(updated_message, 'existing', False)
        )
    
    async def _trigger_debounce(self, tenant_id: UUID, thread_id: UUID) -> None:
        """Trigger debounce mechanism for message bursts."""
        # Import here to avoid circular imports
        from supportdesk.worker.tasks import handle_message_debounce
        
        # Generate correlation ID for this debounce window
        correlation_id = uuid4()
        
        # Trigger async debounce handling
        handle_message_debounce.delay(str(tenant_id), str(thread_id), str(correlation_id))
    
    async def _perform_auto_ack(self, tenant_id: UUID, thread_id: UUID) -> None:
        """Perform immediate auto-ACK for test mode."""
        from supportdesk.common.enums import ThreadState
        from supportdesk.database import AsyncSessionLocal
        
        # Use a separate database session to avoid transaction conflicts
        async with AsyncSessionLocal() as separate_db:
            from supportdesk.threads.repository import ThreadRepository
            from supportdesk.events.repository import ThreadEventRepository
            
            thread_repo = ThreadRepository(separate_db)
            event_repo = ThreadEventRepository(separate_db)
            
            # Get thread and check if it's in NEW state
            thread = await thread_repo.get_by_id(thread_id, tenant_id)
            
            if thread and thread.state == ThreadState.NEW:
                # Update thread state to ACKNOWLEDGED
                await thread_repo.update_state(thread_id, tenant_id, ThreadState.ACKNOWLEDGED)
                
                # Create state transition event with deterministic correlation_id
                from supportdesk.worker.tasks import generate_deterministic_uuid
                current_hour = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
                hour_iso = current_hour.isoformat()
                correlation_id = generate_deterministic_uuid(str(tenant_id), str(thread_id), hour_iso, "debounce_window")
                
                await event_repo.create({
                    "thread_id": thread_id,
                    "event_type": "state_transition",
                    "old_state": ThreadState.NEW,
                    "new_state": ThreadState.ACKNOWLEDGED,
                    "actor_type": "system",
                    "correlation_id": correlation_id,
                    "metadata": {"reason": "auto_ack_test_mode"}
                })
