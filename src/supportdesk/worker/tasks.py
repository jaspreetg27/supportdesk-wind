"""Background tasks."""

from typing import Any

from supportdesk.worker.app import celery_app


@celery_app.task(bind=True)
def health_check_task(self) -> dict[str, Any]:
    """Health check task for worker monitoring."""
    return {
        "task_id": self.request.id,
        "status": "healthy",
        "worker": "celery",
    }


@celery_app.task(bind=True)
def async_task_wrapper(self, task_name: str, *args, **kwargs) -> Any:
    """Wrapper for running async tasks in Celery."""
    # This is a placeholder for future async task execution
    # In Phase P0, we only need basic task infrastructure
    return {
        "task_id": self.request.id,
        "task_name": task_name,
        "status": "completed",
        "args": args,
        "kwargs": kwargs,
    }
