"""Message repository with deduplication and ordering."""

from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from supportdesk.config import settings
from supportdesk.messages.models import Message, MessageType


class MessageRepository:
    """Repository for message operations with deduplication."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_or_get_existing(
        self,
        thread_id: UUID,
        message_data: dict
    ) -> Tuple[Message, bool]:
        """Create a message or return existing one. Returns (message, is_new)."""
        try:
            message = Message(
                thread_id=thread_id,
                platform_message_id=message_data["platform_message_id"],
                type=message_data["type"],
                content=message_data.get("content"),
                sent_at=message_data.get("sent_at"),
                metadata_=message_data.get("metadata", {})
            )
            
            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)
            
            # Mark as new
            message.existing = False
            return message, True
            
        except IntegrityError:
            await self.db.rollback()
            
            # Get existing message
            result = await self.db.execute(
                select(Message).where(
                    Message.thread_id == thread_id,
                    Message.platform_message_id == message_data["platform_message_id"]
                )
            )
            existing_message = result.scalar_one()
            
            # Mark as existing
            existing_message.existing = True
            return existing_message, False
    
    async def get_by_id(self, message_id: UUID, tenant_id: UUID) -> Optional[Message]:
        """Get a message by ID with tenant validation."""
        # Join with thread to ensure tenant isolation
        query = select(Message).join(Message.thread).where(
            Message.id == message_id,
            Message.thread.has(tenant_id=tenant_id)
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_platform_message_id(
        self, 
        thread_id: UUID, 
        platform_message_id: str
    ) -> Optional[Message]:
        """Get a message by platform message ID within a thread."""
        query = select(Message).where(
            Message.thread_id == thread_id,
            Message.platform_message_id == platform_message_id
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_thread_and_platform_message_id(
        self, 
        tenant_id: UUID,
        thread_id: UUID, 
        platform_message_id: str
    ) -> Optional[Message]:
        """Get a message by platform message ID within a thread with tenant validation."""
        # Join with thread to ensure tenant isolation
        query = select(Message).join(Message.thread).where(
            Message.thread_id == thread_id,
            Message.platform_message_id == platform_message_id,
            Message.thread.has(tenant_id=tenant_id)
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_paginated(
        self,
        thread_id: UUID,
        tenant_id: UUID,
        offset: int,
        limit: int
    ) -> Tuple[list[Message], int]:
        """Get paginated list of messages for a thread with tenant validation."""
        
        # Verify thread belongs to tenant first
        from supportdesk.threads.models import Thread
        thread_check = await self.db.execute(
            select(Thread).where(
                Thread.id == thread_id,
                Thread.tenant_id == tenant_id
            )
        )
        if not thread_check.scalar_one_or_none():
            return [], 0
        
        # Base query
        base_query = select(Message).where(Message.thread_id == thread_id)
        
        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        # Data query with ordering - created_at ASC for creation order
        actual_limit = min(limit, settings.page_size_max)
        data_query = base_query.order_by(
            Message.created_at.asc()
        ).offset(offset).limit(actual_limit)
        
        data_result = await self.db.execute(data_query)
        messages = list(data_result.scalars().all())
        
        return messages, total
    
    async def create_message(self, thread_id: UUID, message_data: dict) -> Message:
        """Create a new message."""
        message = Message(
            thread_id=thread_id,
            platform_message_id=message_data["platform_message_id"],
            type=message_data["type"],
            content=message_data.get("content"),
            sent_at=message_data.get("sent_at"),
            metadata_=message_data.get("metadata", {})
        )
        
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        
        return message
    
    async def update(
        self,
        message_id: UUID,
        tenant_id: UUID,
        update_data: dict
    ) -> Optional[Message]:
        """Update a message with tenant validation and immutability checks."""
        
        # Get message with tenant validation
        message = await self.get_by_id(message_id, tenant_id)
        if not message:
            return None
        
        # Apply allowed updates
        if "content" in update_data:
            message.content = update_data["content"]
        if "metadata" in update_data:
            message.metadata_ = update_data["metadata"]
        if "sent_at" in update_data and message.sent_at is None:
            # Only allow setting sent_at if not previously set
            message.sent_at = update_data["sent_at"]
        
        await self.db.commit()
        await self.db.refresh(message)
        return message
    
    async def count_since_last_flush(self, thread_id: UUID) -> int:
        """Count messages since last debounce flush."""
        # For now, count all messages in thread
        # In production, this would track flush markers
        result = await self.db.execute(
            select(func.count()).where(Message.thread_id == thread_id)
        )
        return result.scalar() or 0
