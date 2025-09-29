"""Health check API endpoints."""


from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from supportdesk.health.checks import get_health_status

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    checks: dict[str, str]


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
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "checks": checks,
                "detail": {"message": "One or more dependencies are unavailable"},
            },
        )

    return response
