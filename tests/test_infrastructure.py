"""Infrastructure tests."""

import pytest
from supportdesk.config import settings
from supportdesk.worker.tasks import health_check_task


def test_settings_loaded() -> None:
    """Test that settings are loaded correctly."""
    assert settings.app_env is not None
    assert settings.health_check_timeout > 0
    assert settings.database_url is not None
    assert settings.redis_url is not None


def test_celery_task() -> None:
    """Test basic Celery task functionality."""
    # Test task creation (not execution, as we don't have Redis in tests)
    task = health_check_task
    assert task is not None
    assert hasattr(task, 'delay')
    assert hasattr(task, 'apply_async')


@pytest.mark.slow
def test_database_url_format() -> None:
    """Test database URL format."""
    assert settings.database_url.startswith("postgresql+asyncpg://")


@pytest.mark.slow
def test_redis_url_format() -> None:
    """Test Redis URL format."""
    assert settings.redis_url.startswith("redis://")


def test_cors_origins() -> None:
    """Test CORS origins configuration."""
    assert isinstance(settings.cors_origins, list)
    assert len(settings.cors_origins) > 0
