from __future__ import annotations

import io
import logging

import httpx
from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.http import MediaIoBaseDownload  # type: ignore

from .document_processing import (
    detect_and_extract,
    extract_google_drive_id,
)

logger = logging.getLogger(__name__)


class GoogleDocsFetcher:
    def __init__(self, credentials: Credentials | None = None):
        self.credentials = credentials
        self.drive_service = None
        if self.credentials is not None:
            try:
                self._ensure_fresh_credentials()
                self.drive_service = build(
                    "drive", "v3", credentials=self.credentials, cache_discovery=False
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error loading Drive service: {exc}")

    async def fetch_public_or_authenticated(self, url_or_id: str) -> str:
        file_id = extract_google_drive_id(url_or_id)
        # Try authenticated first if available
        if self.drive_service is not None:
            try:
                return await self._download_authenticated(file_id)
            except Exception:
                pass
        # Fallback to public
        return await self._try_public(file_id)

    async def _download_authenticated(self, file_id: str) -> str:
        if self.drive_service is None:
            raise RuntimeError("Drive API not initialized")
        meta = (
            self.drive_service.files()
            .get(fileId=file_id, supportsAllDrives=True)
            .execute()
        )
        name = meta.get("name", "")
        mime = meta.get("mimeType", "")

        if mime == "application/vnd.google-apps.document":
            request = self.drive_service.files().export_media(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            request = self.drive_service.files().get_media(
                fileId=file_id, supportsAllDrives=True
            )

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        content = fh.read()
        return detect_and_extract(name, content)

    def _ensure_fresh_credentials(self) -> None:
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to refresh Google credentials: {exc}")

    @staticmethod
    async def _try_public(file_id: str) -> str:
        urls = [
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"https://docs.google.com/document/d/{file_id}/export?format=txt",
            f"https://docs.google.com/document/d/{file_id}/export?format=docx",
            f"https://docs.google.com/presentation/d/{file_id}/export?format=txt",
            f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv",
        ]
        async with httpx.AsyncClient(timeout=30) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and resp.content:
                        name = "public"
                        content = resp.content
                        return detect_and_extract(name, content)
                except Exception:
                    continue
        raise Exception("Could not access file as public document. File may be private or missing.")
