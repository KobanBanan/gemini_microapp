from __future__ import annotations

import json
import logging
from typing import Any

from google import genai  # type: ignore
from google.genai import types  # type: ignore
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        self.client = genai.Client(api_key=api_key)

    @staticmethod
    def _build_config(system_prompt: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
            response_mime_type="application/json",
            response_schema=genai.types.Schema(
                type=genai.types.Type.ARRAY,
                items=genai.types.Schema(
                    type=genai.types.Type.OBJECT,
                    required=[
                        "error_type",
                        "location_context",
                        "original_text",
                        "suggestion",
                        "page",
                    ],
                    properties={
                        "error_type": genai.types.Schema(type=genai.types.Type.STRING),
                        "location_context": genai.types.Schema(type=genai.types.Type.STRING),
                        "original_text": genai.types.Schema(type=genai.types.Type.STRING),
                        "suggestion": genai.types.Schema(type=genai.types.Type.STRING),
                        "page": genai.types.Schema(type=genai.types.Type.INTEGER),
                    },
                ),
            ),
            system_instruction=[types.Part.from_text(text=system_prompt)],
        )

    def generate(self, system_prompt: str, document_text: str) -> list[dict[str, Any]]:
        config = self._build_config(system_prompt)

        def _call() -> list[dict[str, Any]]:
            result = self.client.models.generate_content(
                model="gemini-2.5-pro",
                config=config,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=f"Analyze this document:\n\n{document_text}"
                            )
                        ],
                    )
                ],
            )
            try:
                return json.loads(result.text)
            except Exception:
                logger.error("Gemini returned non-JSON; returning as raw list with single message")
                return [{"message": result.text}]

        for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type(Exception),
                reraise=True,
        ):
            with attempt:
                return _call()

        return []
