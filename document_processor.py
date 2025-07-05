import io
import os
import re
from typing import Union, BinaryIO

import PyPDF2
import docx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


class DocumentProcessor:
    """Class for processing various types of documents"""

    def __init__(self, credentials_file: str = 'creds.json'):
        self.credentials_file = credentials_file
        self.credentials = None
        self.drive_service = None
        self._load_credentials()

    def _load_credentials(self):
        """Load credentials for Google Drive API"""
        try:
            if os.path.exists(self.credentials_file):
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file,
                    scopes=["https://www.googleapis.com/auth/drive.readonly"]
                )
                self.drive_service = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        except Exception as e:
            print(f"Error loading credentials: {e}")

    def extract_text_from_docx(self, file_content: Union[bytes, BinaryIO]) -> str:
        """Extract text from DOCX file"""
        try:
            if isinstance(file_content, bytes):
                file_content = io.BytesIO(file_content)

            doc = docx.Document(file_content)
            text_content = []

            for paragraph in doc.paragraphs:
                text_content.append(paragraph.text)

            return "\n".join(text_content)
        except Exception as e:
            raise Exception(f"Error processing DOCX file: {e}")

    @staticmethod
    def extract_text_from_pdf(file_content: Union[bytes, BinaryIO]) -> str:
        """Extract text from PDF file"""
        try:
            if isinstance(file_content, bytes):
                file_content = io.BytesIO(file_content)

            reader = PyPDF2.PdfReader(file_content)
            text_content = []

            for page in reader.pages:
                text_content.append(page.extract_text())

            return "\n".join(text_content)
        except Exception as e:
            raise Exception(f"Error processing PDF file: {e}")

    @staticmethod
    def extract_text_from_txt(file_content: Union[bytes, str]) -> str:
        """Extract text from TXT file"""
        try:
            if isinstance(file_content, bytes):
                # Try to detect encoding
                encodings = ['utf-8', 'utf-16', 'cp1251', 'latin-1']
                for encoding in encodings:
                    try:
                        return file_content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                # If no encoding works, use utf-8 with error ignore
                return file_content.decode('utf-8', errors='ignore')

            return file_content
        except Exception as e:
            raise Exception(f"Error processing TXT file: {e}")

    def process_uploaded_file(self, uploaded_file) -> str:
        """Process uploaded file based on its type"""
        file_type = uploaded_file.type
        file_content = uploaded_file.read()

        if file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self.extract_text_from_docx(file_content)
        elif file_type == "application/pdf":
            return self.extract_text_from_pdf(file_content)
        elif file_type == "text/plain":
            return self.extract_text_from_txt(file_content)
        else:
            # Try to determine type by extension
            file_name = uploaded_file.name.lower()
            if file_name.endswith('.docx'):
                return self.extract_text_from_docx(file_content)
            elif file_name.endswith('.pdf'):
                return self.extract_text_from_pdf(file_content)
            elif file_name.endswith('.txt'):
                return self.extract_text_from_txt(file_content)
            else:
                raise Exception(f"Unsupported file type: {file_type}")

    @staticmethod
    def extract_google_drive_id(url_or_id: str) -> str:
        """Extract ID from Google Drive URL or return ID as is"""
        # If this is already an ID (no slashes and dots)
        if '/' not in url_or_id and '.' not in url_or_id:
            return url_or_id

        # Patterns for different types of Google Drive URLs
        patterns = [
            r'/file/d/([a-zA-Z0-9-_]+)',  # Google Drive files
            r'/document/d/([a-zA-Z0-9-_]+)',  # Google Docs
            r'id=([a-zA-Z0-9-_]+)',  # URL with id parameter
            r'/([a-zA-Z0-9-_]+)/?$'  # ID at the end of URL
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract ID from URL: {url_or_id}")

    def download_from_google_drive(self, file_id: str) -> str:
        """Download and process file from Google Drive"""
        if not self.drive_service:
            raise Exception("Google Drive API not initialized. Check creds.json file")

        try:
            # Get file metadata
            file_metadata = self.drive_service.files().get(
                fileId=file_id,
                supportsAllDrives=True
            ).execute()

            file_name = file_metadata.get('name', '')
            mime_type = file_metadata.get('mimeType', '')

            # If this is Google Docs, export as DOCX
            if mime_type == 'application/vnd.google-apps.document':
                request = self.drive_service.files().export_media(
                    fileId=file_id,
                    mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
            else:
                # For regular files use get_media
                request = self.drive_service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True
                )

            # Download file
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

            # Process content
            fh.seek(0)
            file_content = fh.read()

            # Determine file type and process
            if mime_type == 'application/vnd.google-apps.document' or file_name.lower().endswith('.docx'):
                return self.extract_text_from_docx(file_content)
            elif file_name.lower().endswith('.pdf'):
                return self.extract_text_from_pdf(file_content)
            elif file_name.lower().endswith('.txt'):
                return self.extract_text_from_txt(file_content)
            else:
                # Try as DOCX (often Google Docs exports as DOCX)
                try:
                    return self.extract_text_from_docx(file_content)
                except:
                    # If that fails, try as text
                    return self.extract_text_from_txt(file_content)

        except Exception as e:
            raise Exception(f"Error downloading file from Google Drive: {e}")

    def process_google_drive_url(self, url_or_id: str) -> str:
        """Process Google Drive URL or ID"""
        file_id = self.extract_google_drive_id(url_or_id)
        return self.download_from_google_drive(file_id)

    @staticmethod
    def get_supported_file_types() -> list:
        """Return list of supported file types"""
        return [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
            "application/pdf",  # PDF
            "text/plain",  # TXT
            "docx", "pdf", "txt"  # By extensions
        ]
