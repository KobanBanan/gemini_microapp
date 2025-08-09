from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .document_processing import detect_and_extract
from .gemini import GeminiClient
from .google_docs import GoogleDocsFetcher
from .progress import ProgressPublisher
from .prompt_builder import build_system_prompt
from ..models.analysis import AnalysisResult
from ..models.document import Document
from ..models.task import Task

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_analyze(self, task: Task, payload: dict[str, Any]) -> AnalysisResult:
        logger.info("Running analyze task", extra={"task_id": task.id})
        publisher = ProgressPublisher()
        publisher.publish(task.id, 10, "started")

        source_type = payload.get("source_type", "upload")
        source_ref = payload.get("source_ref") or "unknown"
        file_name = payload.get("file_name")
        use_o1 = bool(payload.get("use_o1", False))
        use_eb1 = bool(payload.get("use_eb1", False))
        override = payload.get("system_prompt_override")

        # 1) Fetch/prepare text
        text: str
        if source_type == "google_drive":
            publisher.publish(task.id, 25, "fetching_google_drive")
            fetcher = GoogleDocsFetcher()
            text = await fetcher.fetch_public_or_authenticated(source_ref)
        else:
            # For upload flow we expect that file is pre-staged elsewhere; here we use ref as path
            publisher.publish(task.id, 25, "loading_upload")
            with open(source_ref, "rb") as f:
                content = f.read()
            text = detect_and_extract(file_name or source_ref, content)

        publisher.publish(task.id, 40, "building_prompt")
        system_prompt = build_system_prompt(use_o1=use_o1, use_eb1=use_eb1, override=override)

        # 2) Call Gemini
        publisher.publish(task.id, 60, "gemini_call")
        gemini = GeminiClient()
        results = gemini.generate(system_prompt=system_prompt, document_text=text)

        # 3) Persist
        publisher.publish(task.id, 90, "persisting")
        document = Document(
            source_type=source_type,
            source_ref=source_ref,
            file_name=file_name,
        )
        self.db.add(document)
        await self.db.flush()

        result = AnalysisResult(
            task_id=task.id,
            document_id=document.id,
            result_json=json.dumps(results),
        )
        self.db.add(result)
        await self.db.flush()
        publisher.publish(task.id, 100, "done")
        return result
