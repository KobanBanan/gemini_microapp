from __future__ import annotations

import os

from celery import Celery

celery = Celery(
    "worker",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)

celery.conf.task_acks_late = True
celery.conf.worker_prefetch_multiplier = 1
