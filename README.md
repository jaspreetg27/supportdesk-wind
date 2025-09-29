# SupportDesk AI

Production-grade AI-powered customer support backend built with FastAPI, SQLAlchemy, and Celery.

## Features

- **Multi-tenant Architecture**: Complete tenant isolation with path-scoped APIs
- **Customer Management**: Full CRUD operations with tenant-scoped data isolation
- **Async-first architecture**: Built on FastAPI with full async/await support
- **Background processing**: Celery with Redis for reliable task execution
- **Database migrations**: Alembic with async SQLAlchemy 2.x
- **Pagination**: Configurable pagination with defaults (20 items/page, max 100)
- **Soft Deletes**: Data preservation with admin-only access to inactive records
- **Input Validation**: Comprehensive validation for emails, phones, slugs
- **Health monitoring**: Comprehensive health checks for all services
- **Developer experience**: Hot-reload, linting, type checking, testing

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)

### Development Setup

1. **Clone and setup environment**:
   ```bash
   git clone <repository-url>
   cd supportdesk-ai
   cp .env.example .env
   ```

2. **Start services**:
   ```bash
   docker-compose up -d --build
   ```

3. **Run migrations**:
   ```bash
   make migrate
   # or
   ./scripts/dev.ps1 migrate
   # or directly with docker-compose
   docker-compose exec api alembic upgrade head
   ```

4. **Verify health**:
   ```bash
   curl http://localhost:8000/healthz
   # or use the built-in command
   make health-check
   # or on Windows
   ./scripts/dev.ps1 health-check
   ```

### Development Commands

**Using Makefile (Unix/Linux/macOS)**:
```bash
make format    # Format code with black and ruff
make lint      # Lint with ruff
make type      # Type check with mypy
make test      # Run tests
make up        # Start services
make down      # Stop services
make health-check # Test health endpoint
```

**Using PowerShell (Windows)**:
```powershell
./scripts/dev.ps1 format    # Format code
./scripts/dev.ps1 lint      # Lint code
./scripts/dev.ps1 type      # Type check
./scripts/dev.ps1 test      # Run tests
./scripts/dev.ps1 up        # Start services
./scripts/dev.ps1 down      # Stop services
./scripts/dev.ps1 health-check # Test health endpoint
```

## Architecture

- **API**: FastAPI with async/await
- **Database**: PostgreSQL with async SQLAlchemy 2.x
- **Cache/Queue**: Redis for caching and Celery broker
- **Background Jobs**: Celery workers
- **Migrations**: Alembic with async support

## API Endpoints

### Health Checks
- `GET /healthz` - Overall system health

### Tenants (Multi-tenant Management)
- `POST /api/v1/tenants` - Create a new tenant
- `GET /api/v1/tenants/{tenant_id}` - Get tenant by ID
- `PUT /api/v1/tenants/{tenant_id}` - Update tenant
- `DELETE /api/v1/tenants/{tenant_id}` - Soft delete tenant

### Customers (Tenant-scoped)
- `POST /api/v1/tenants/{tenant_id}/customers` - Create customer
- `GET /api/v1/tenants/{tenant_id}/customers` - List customers (paginated)
- `GET /api/v1/tenants/{tenant_id}/customers/{customer_id}` - Get customer
- `PUT /api/v1/tenants/{tenant_id}/customers/{customer_id}` - Update customer
- `DELETE /api/v1/tenants/{tenant_id}/customers/{customer_id}` - Soft delete customer

#### Sample Requests

**Create Tenant:**
```bash
curl -X POST "http://localhost:8000/api/v1/tenants/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "settings": {"timezone": "UTC", "locale": "en-US"}
  }'
```

**Create Customer:**
```bash
curl -X POST "http://localhost:8000/api/v1/tenants/{tenant_id}/customers/" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "CRM-12345",
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "metadata": {"source": "website", "priority": "high"}
  }'
```

**List Customers (Paginated):**
```bash
curl "http://localhost:8000/api/v1/tenants/{tenant_id}/customers/?page=1&page_size=20"
```

## Development

### Code Quality
- **Linting**: ruff
- **Formatting**: black
- **Type checking**: mypy
- **Testing**: pytest with async support

### Testing
```bash
# Run all tests
make test

# Run fast tests only
make test-fast

# Run with coverage
pytest --cov=src/supportdesk
```

## Troubleshooting

### Health Check Issues
If `curl http://localhost:8000/healthz` fails:

1. **Check container status**:
   ```bash
   docker-compose ps
   ```

2. **Check API logs**:
   ```bash
   docker-compose logs api
   ```

3. **Test inside container**:
   ```bash
   docker-compose exec api curl http://localhost:8000/healthz
   ```

4. **Run migrations**:
   ```bash
   docker-compose exec api alembic upgrade head
   ```

### Windows-Specific Issues
- **File watching**: Set `WATCHFILES_FORCE_POLLING=1` (already configured)
- **Volume mounts**: Use named volumes for data, bind mounts for code
- **Reload stability**: Uvicorn reload is disabled by default for stability

### Development vs Production
- **Development**: Use `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up` for hot reload
- **Production**: Use `docker-compose up` with reload disabled

## Deployment

See deployment documentation for production setup instructions.

## License

MIT License - see LICENSE file for details.
