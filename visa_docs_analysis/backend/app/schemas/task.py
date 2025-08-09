from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

TaskType = Literal["document_inconsistency_check", "compare"]
TaskStatus = Literal["pending", "running", "succeeded", "failed", "canceled"]


class CreateDocumentInconsistencyCheckTask(BaseModel):
    source_type: Literal["google_drive", "upload"]
    source_ref: str | None = None
    file_name: str | None = None
    use_o1: bool = False
    use_eb1: bool = False
    system_prompt_override: str | None = None


class TaskOut(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    progress: int
    created_at: str
    updated_at: str
    error: str | None = None


class TaskWithResult(TaskOut):
    result_json: Any | None = None


