"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from supportdesk import __version__
from supportdesk.config import settings
from supportdesk.redis_client import close_redis
from supportdesk.customers.router import router as customers_router
from supportdesk.events.router import router as events_router
from supportdesk.health.router import router as health_router
from supportdesk.messages.router import router as messages_router
from supportdesk.threads.router import router as threads_router
from supportdesk.tenants.router import router as tenants_router

# Import all models to register them with SQLAlchemy
from supportdesk.tenants import models as tenant_models  # noqa: F401
from supportdesk.customers import models as customer_models  # noqa: F401
from supportdesk.threads import models as thread_models  # noqa: F401
from supportdesk.messages import models as message_models  # noqa: F401
from supportdesk.events import models as event_models  # noqa: F401


@asynccontextmanager
async def Lifecycle(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application Lifecycle manager."""
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
        "description": "Customer management operations",
    },
    {
        "name": "Threads",
        "description": "Conversation thread management",
    },
    {
        "name": "Messages",
        "description": "Message operations within threads",
    },
    {
        "name": "Thread Events",
        "description": "Thread event audit trail",
    },
]

# Create FastAPI application
app = FastAPI(
    description="Production-grade AI-powered customer support backend with multi-tenant architecture",
    version=__version__,
    lifespan=Lifecycle,
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


# Custom exception handler for Pydantic validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with 422 status."""
    # Clean up errors to make them JSON serializable
    cleaned_errors = []
    for error in exc.errors():
        cleaned_error = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "input": error.get("input")
        }
        # Add URL if present
        if "url" in error:
            cleaned_error["url"] = error["url"]
        cleaned_errors.append(cleaned_error)
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": cleaned_errors
        }
    )


# Custom exception handler for ValueError (domain validation)
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError with 400 status for domain validation errors."""
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc)
        }
    )


# Custom exception handler for ValidationError (Pydantic)
@app.exception_handler(ValidationError)
async def pydantic_validation_error_handler(request: Request, exc: ValidationError):
    """Handle Pydantic ValidationError with 422 status."""
    # Clean up errors to make them JSON serializable
    cleaned_errors = []
    for error in exc.errors():
        cleaned_error = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "input": error.get("input")
        }
        # Add URL if present
        if "url" in error:
            cleaned_error["url"] = error["url"]
        cleaned_errors.append(cleaned_error)
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": cleaned_errors
        }
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
app.include_router(
    threads_router,
    prefix="/api/v1/tenants/{tenant_id}",
    tags=["Threads"]
)
app.include_router(
    messages_router,
    prefix="/api/v1/tenants/{tenant_id}",
    tags=["Messages"]
)
app.include_router(
    events_router,
    prefix="/api/v1/tenants/{tenant_id}",
    tags=["Thread Events"]
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


