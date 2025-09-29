"""Health check implementations."""

import asyncio

from supportdesk.config import settings
from supportdesk.database import check_database_health
from supportdesk.redis_client import check_redis_health


async def check_service_health(check_func, timeout: int = None) -> str:
    """Run a health check with timeout."""
    if timeout is None:
        timeout = settings.health_check_timeout

    try:
        result = await asyncio.wait_for(check_func(), timeout=timeout)
        return "ok" if result else "error"
    except asyncio.TimeoutError:
        return "timeout"
    except Exception:
        return "error"


async def get_health_status() -> dict[str, str]:
    """Get overall health status."""
    # Run health checks concurrently
    db_task = asyncio.create_task(
        check_service_health(check_database_health, settings.health_check_timeout)
    )
    redis_task = asyncio.create_task(
        check_service_health(check_redis_health, settings.health_check_timeout)
    )

    # Wait for all checks to complete
    db_status, redis_status = await asyncio.gather(db_task, redis_task)

    return {
        "database": db_status,
        "redis": redis_status,
    }
