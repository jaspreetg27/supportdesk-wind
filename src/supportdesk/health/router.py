"""Health check API endpoints."""

from typing import Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from supportdesk.health.checks import get_health_status

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    checks: Dict[str, str]


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns overall system health status including database and Redis connectivity.
    """
    checks = await get_health_status()
    
    # Determine overall status
    overall_status = "ok" if all(status == "ok" for status in checks.values()) else "error"
    
    response = HealthResponse(status=overall_status, checks=checks)
    
    # Return 503 if any service is unhealthy
    if overall_status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )
    
    return response
