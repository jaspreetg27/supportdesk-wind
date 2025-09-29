"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from supportdesk import __version__
from supportdesk.config import settings
from supportdesk.customers.router import router as customers_router
from supportdesk.health.router import router as health_router
from supportdesk.redis_client import close_redis
from supportdesk.tenants.router import router as tenants_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown
    await close_redis()


# OpenAPI tags metadata
tags_metadata = [
    {
        "name": "health",
        "description": "Health check endpoints for monitoring service status.",
    },
    {
        "name": "tenants",
        "description": "Tenant management operations. Tenants are the top-level organizational units that provide multi-tenant isolation.",
    },
    {
        "name": "customers",
        "description": "Customer management within tenants. All customer operations are tenant-scoped for data isolation.",
    },
]

# Create FastAPI application
app = FastAPI(
    title="SupportDesk AI",
    description="Production-grade AI-powered customer support backend with multi-tenant architecture",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_tags=tags_metadata,
)


# Custom exception handler for HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException with proper JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
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
app.include_router(health_router, tags=["health"])
app.include_router(
    tenants_router,
    prefix="/api/v1/tenants",
    tags=["tenants"]
)
app.include_router(
    customers_router,
    prefix="/api/v1/tenants/{tenant_id}/customers",
    tags=["customers"]
)


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


