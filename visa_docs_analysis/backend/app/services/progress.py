from __future__ import annotations

import json
import os
from typing import Any

import redis


class ProgressPublisher:
    def __init__(self, channel_prefix: str = "task_progress:"):
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._r = redis.Redis.from_url(url)
        self._prefix = channel_prefix

    def publish(self, task_id: str, progress: int, stage: str, message: str | None = None) -> None:
        payload: dict[str, Any] = {
            "progress": progress,
            "stage": stage,
            "message": message,
        }
        self._r.publish(self._prefix + task_id, json.dumps(payload))
