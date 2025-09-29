"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from supportdesk import __version__
from supportdesk.config import settings
from supportdesk.health.router import router as health_router
from supportdesk.redis_client import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown
    await close_redis()


# Create FastAPI application
app = FastAPI(
    title="SupportDesk AI",
    description="Production-grade AI-powered customer support backend",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if isinstance(settings.cors_origins, list) else [settings.cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SupportDesk AI",
        "version": __version__,
        "status": "running",
    }


@app.get("/debug")
async def debug():
    """Debug endpoint to check configuration."""
    return {
        "cors_origins": settings.cors_origins,
        "cors_origins_type": type(settings.cors_origins).__name__,
        "app_env": settings.app_env,
        "database_url": settings.database_url[:50] + "..." if len(settings.database_url) > 50 else settings.database_url,
        "redis_url": settings.redis_url,
    }
