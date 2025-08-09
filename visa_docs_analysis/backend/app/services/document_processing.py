from __future__ import annotations

import io
import logging
import re
from typing import BinaryIO

import PyPDF2  # type: ignore
import docx  # type: ignore

logger = logging.getLogger(__name__)


def extract_text_from_docx(file_content: bytes | BinaryIO) -> str:
    try:
        if isinstance(file_content, bytes):
            file_content = io.BytesIO(file_content)

        doc = docx.Document(file_content)
        text_content: list[str] = []
        current_page = 1
        text_content.append(f"\n=== PAGE {current_page} ===\n")

        for paragraph in doc.paragraphs:
            if paragraph._element.xpath('.//w:br[@w:type="page"]'):
                current_page += 1
                text_content.append(f"\n\n=== PAGE {current_page} ===\n")
            if paragraph.text.strip():
                text_content.append(paragraph.text)

        return "\n".join(text_content)
    except Exception as exc:  # noqa: BLE001
        msg = f"Error processing DOCX file: {exc}"
        logger.error(msg)
        raise Exception(msg) from exc


def extract_text_from_pdf(file_content: bytes | BinaryIO) -> str:
    try:
        if isinstance(file_content, bytes):
            file_content = io.BytesIO(file_content)

        reader = PyPDF2.PdfReader(file_content)
        text_content: list[str] = []
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_content.append(f"\n\n=== PAGE {page_num} ===\n" + page_text)
        return "\n".join(text_content)
    except Exception as exc:  # noqa: BLE001
        msg = f"Error processing PDF file: {exc}"
        logger.error(msg)
        raise Exception(msg) from exc


def extract_text_from_txt(file_content: bytes | str) -> str:
    try:
        if isinstance(file_content, bytes):
            for enc in ["utf-8", "utf-16", "cp1251", "latin-1"]:
                try:
                    return file_content.decode(enc)
                except UnicodeDecodeError:
                    continue
            return file_content.decode("utf-8", errors="ignore")
        return file_content
    except Exception as exc:  # noqa: BLE001
        msg = f"Error processing TXT file: {exc}"
        logger.error(msg)
        raise Exception(msg) from exc


def detect_and_extract(file_name: str, content: bytes) -> str:
    name = (file_name or "").lower()
    if name.endswith(".docx"):
        return extract_text_from_docx(content)
    if name.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if name.endswith(".txt"):
        return extract_text_from_txt(content)
    # fallback heuristics
    if content.startswith(b"PK"):
        return extract_text_from_docx(content)
    if content.startswith(b"%PDF"):
        return extract_text_from_pdf(content)
    return extract_text_from_txt(content)


GOOGLE_ID_PATTERNS = [
    r"/file/d/([a-zA-Z0-9-_]+)",
    r"/document/d/([a-zA-Z0-9-_]+)",
    r"id=([a-zA-Z0-9-_]+)",
    r"/([a-zA-Z0-9-_]+)/?$",
]


def extract_google_drive_id(url_or_id: str) -> str:
    if "/" not in url_or_id and "." not in url_or_id:
        return url_or_id
    for pattern in GOOGLE_ID_PATTERNS:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract ID from URL: {url_or_id}")
