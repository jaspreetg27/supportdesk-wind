# Multi-stage Dockerfile for development
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WATCHFILES_FORCE_POLLING=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set work directory
WORKDIR /app

# Bring in metadata first to leverage layer cache
COPY pyproject.toml ./
COPY README.md ./

# IMPORTANT: copy source before editable install (src-layout project)
COPY ./src ./src
COPY ./alembic ./alembic
COPY ./alembic.ini ./
COPY ./tests ./tests

# Install deps (editable)
RUN pip install --upgrade pip && \
    pip install -e .[dev]

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Default command for API service (reload controlled by env var)
CMD ["sh", "-c", "if [ \"$UVICORN_RELOAD\" = \"true\" ]; then uvicorn supportdesk.main:app --host 0.0.0.0 --port 8000 --reload; else uvicorn supportdesk.main:app --host 0.0.0.0 --port 8000; fi"]
