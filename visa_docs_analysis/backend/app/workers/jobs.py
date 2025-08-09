from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select

from .celery_app import celery
from ..db.session import SessionLocal
from ..models.task import Task
from ..models.task import TaskInput
from ..services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def run_analyze_task(self, task_id: str) -> None:
    # Run in sync Celery context; create async session for DB operations
    logger.info(f"Starting analysis task {task_id}")

    async def _inner() -> None:
        async with SessionLocal() as db:  # type: AsyncSession
            task = await db.get(Task, task_id)
            if task is None:
                logger.error(f"Task {task_id} not found")
                return
            task.status = "running"
            task.progress = 10
            await db.flush()

            res = await db.execute(select(TaskInput).where(TaskInput.task_id == task_id))
            input_row = res.scalars().first()
            payload = json.loads(input_row.payload) if input_row else {}

            # If Google Drive source, try to load user token (future: bind by user id)
            svc = AnalysisService(db)
            try:
                await svc.run_analyze(task, payload)
                task.status = "succeeded"
                task.progress = 100
                await db.commit()
                logger.info(f"Task {task_id} succeeded")
            except Exception as e:  # noqa: BLE001
                await db.rollback()
                task.status = "failed"
                task.error = str(e)
                await db.commit()
                logger.error(f"Task {task_id} failed: {e}")

    asyncio.run(_inner())
