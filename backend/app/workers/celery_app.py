"""Celery application — Redis as broker and result backend.

Run a worker with:  celery -A app.workers.celery_app worker --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "sourcebound",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)
