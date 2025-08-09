from __future__ import annotations

import asyncio
import contextlib
import json
import os

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/tasks/{task_id}/ws")
async def ws_task_progress(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    channel = f"task_progress:{task_id}"
    redis = aioredis.from_url(url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        # Send initial message
        await websocket.send_json({"progress": 0, "stage": "queued"})
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if message and message.get("type") == "message":
                data = json.loads(message["data"])  # type: ignore[index]
                await websocket.send_json(data)
            await asyncio.sleep(0.1)
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis.close()


