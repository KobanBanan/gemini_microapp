from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models.analysis import AnalysisResult
from ...models.document import Document
from ...models.task import Task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["history"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("")
async def list_history(db: DbDep) -> list[dict[str, Any]]:
    res = await db.execute(
        select(AnalysisResult, Task, Document)
        .join(Task, Task.id == AnalysisResult.task_id, isouter=True)
        .join(Document, Document.id == AnalysisResult.document_id, isouter=True)
        .order_by(AnalysisResult.id.desc())
        .limit(100)
    )
    items: list[dict[str, Any]] = []
    for ar, task, doc in res.all():
        items.append(
            {
                "analysis_id": ar.id,
                "task_id": ar.task_id,
                "task_status": getattr(task, "status", None),
                "document_id": ar.document_id,
                "file_name": getattr(doc, "file_name", None),
                "created_at": ar.created_at.isoformat(),
            }
        )
    return items


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: int, db: DbDep) -> dict[str, Any]:
    ar = await db.get(AnalysisResult, analysis_id)
    if not ar:
        return {"detail": "Not found"}
    return {
        "id": ar.id,
        "task_id": ar.task_id,
        "document_id": ar.document_id,
        "result_json": json.loads(ar.result_json),
        "created_at": ar.created_at.isoformat(),
    }


