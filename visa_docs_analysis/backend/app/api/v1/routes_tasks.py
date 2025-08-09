from __future__ import annotations

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.v1.routes_auth import get_current_user
from ...db.session import get_db
from ...models.analysis import AnalysisResult
from ...models.task import Task, TaskInput
from ...schemas.task import (
    CreateDocumentInconsistencyCheckTask,
    TaskOut,
    TaskWithResult,
)
from ...workers.jobs import run_analyze_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


logger = logging.getLogger(__name__)


DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/document-inconsistency-check",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_doc_inconsistency_task(
    body: CreateDocumentInconsistencyCheckTask,
    db: DbDep,
    username: str = Depends(get_current_user),
) -> TaskOut:
    task = Task(type="document_inconsistency_check")
    db.add(task)
    await db.flush()

    payload = body.model_dump()
    db.add(TaskInput(task_id=task.id, payload=json.dumps(payload)))
    await db.commit()

    # Enqueue background job (don't fail request if broker unavailable)
    try:
        run_analyze_task.delay(task.id)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to enqueue task {task.id}: {e}")

    return TaskOut(
        id=task.id,
        type="document_inconsistency_check",
        status=task.status,
        progress=task.progress,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


@router.get("/{task_id}", response_model=TaskWithResult)
async def get_task(task_id: UUID, db: DbDep) -> TaskWithResult:
    task = await db.get(Task, str(task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    res = await db.execute(
        select(AnalysisResult).where(AnalysisResult.task_id == str(task_id)).order_by(
            AnalysisResult.id.desc()
        )
    )
    analysis = res.scalars().first()
    return TaskWithResult(
        id=task.id,
        type=task.type,  # type: ignore[arg-type]
        status=task.status,  # type: ignore[arg-type]
        progress=task.progress,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        error=task.error,
        result_json=json.loads(analysis.result_json) if analysis else None,
    )


@router.post(
    "/document-inconsistency-check-local",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_doc_inconsistency_task_local(
    file: Annotated[UploadFile, File(description="Upload document file")],
    db: DbDep,
    username: str = Depends(get_current_user),
    use_o1: bool = Form(False),
    use_eb1: bool = Form(False),
    system_prompt_override: str | None = Form(None),
) -> TaskOut:
    # Save file to shared volume
    import os
    import uuid

    uploads_dir = "/app/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    file_id = f"{uuid.uuid4()}{ext}"
    dest_path = os.path.join(uploads_dir, file_id)
    with open(dest_path, "wb") as f:
        f.write(await file.read())

    task = Task(type="document_inconsistency_check")
    db.add(task)
    await db.flush()

    payload = {
        "source_type": "upload",
        "source_ref": dest_path,
        "file_name": file.filename,
        "use_o1": use_o1,
        "use_eb1": use_eb1,
        "system_prompt_override": system_prompt_override,
    }
    db.add(TaskInput(task_id=task.id, payload=json.dumps(payload)))
    await db.commit()

    try:
        run_analyze_task.delay(task.id)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to enqueue task {task.id}: {e}")

    return TaskOut(
        id=task.id,
        type="document_inconsistency_check",
        status=task.status,  # type: ignore[arg-type]
        progress=task.progress,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        error=task.error,
    )


