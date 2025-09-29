"""Redis client configuration and health checks."""

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from supportdesk.config import settings

# Create Redis connection pool
redis_pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_connections,
    decode_responses=True,
)

# Create Redis client
redis_client = redis.Redis(connection_pool=redis_pool)


async def check_redis_health() -> bool:
    """Check Redis connectivity."""
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False


async def close_redis():
    """Close Redis connections."""
    await redis_client.close()
    await redis_pool.disconnect()
