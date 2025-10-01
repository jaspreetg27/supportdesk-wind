"""Pagination utilities and schemas."""

from math import ceil
from typing import Generic, List, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field, model_validator

from supportdesk.config import settings

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for API requests."""
    
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1)
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        return self.page_size


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, description="Items per page"),
) -> PaginationParams:
    """FastAPI dependency for pagination parameters."""
    return PaginationParams(page=page, page_size=page_size)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response with calculated metadata."""
        total_pages = ceil(total / page_size) if page_size > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )


# TODO: Future cursor-based pagination support
class CursorPaginationParams(BaseModel):
    """Cursor-based pagination parameters (future implementation)."""

    cursor: str = Field(None, description="Cursor for pagination")
    limit: int = Field(
        default=None,
        ge=1,
        le=100,
        description="Number of items to return"
    )

    def __init__(self, **data):
        if data.get("limit") is None:
            data["limit"] = settings.page_size_default
        super().__init__(**data)


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Cursor-based paginated response (future implementation)."""

    items: list[T]
    next_cursor: str = Field(None, description="Cursor for next page")
    has_more: bool = Field(description="Whether there are more items")
