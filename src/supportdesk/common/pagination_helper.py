"""Shared pagination helper for consistent response envelopes."""

from typing import TypeVar, Generic, List
from math import ceil
from pydantic import BaseModel

T = TypeVar('T')


class PaginationEnvelope(BaseModel, Generic[T]):
    """Standard pagination envelope for all list endpoints."""
    
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


def create_pagination_envelope(
    items: List[T], 
    total: int, 
    page: int, 
    page_size: int
) -> PaginationEnvelope[T]:
    """Create a standardized pagination envelope."""
    total_pages = ceil(total / page_size) if page_size > 0 else 0
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginationEnvelope(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )
