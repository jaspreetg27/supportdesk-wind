"""Celery application configuration."""

from celery import Celery

from supportdesk.config import settings

# Create Celery app
celery_app = Celery(
    "supportdesk",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["supportdesk.worker.tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=["json"],
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
    # Enable eager execution for testing
    task_always_eager=getattr(settings, 'celery_task_always_eager', False),
    task_eager_propagates=True,
)
