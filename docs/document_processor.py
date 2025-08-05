import io
import re
from typing import Union, BinaryIO, Optional

import PyPDF2
import docx
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


class DocumentProcessor:
    """Class for processing various types of documents"""

    def __init__(self, oauth_credentials: Optional[Credentials] = None):
        self.credentials = oauth_credentials
        self.drive_service = None
        if self.credentials:
            self._load_drive_service()

    def _load_drive_service(self):
        """Load Google Drive service with OAuth2 credentials"""
        try:
            if self.credentials:
                self.drive_service = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        except Exception as e:
            print(f"Error loading Drive service: {e}")

    def extract_text_from_docx(self, file_content: Union[bytes, BinaryIO]) -> str:
        """Extract text from DOCX file with page breaks"""
        try:
            if isinstance(file_content, bytes):
                file_content = io.BytesIO(file_content)

            doc = docx.Document(file_content)
            text_content = []
            current_page = 1
            text_content.append(f"\n=== PAGE {current_page} ===\n")

            for paragraph in doc.paragraphs:
                # Check for page breaks
                if paragraph._element.xpath('.//w:br[@w:type="page"]'):
                    current_page += 1
                    text_content.append(f"\n\n=== PAGE {current_page} ===\n")
                
                if paragraph.text.strip():
                    text_content.append(paragraph.text)

            return "\n".join(text_content)
        except Exception as e:
            raise Exception(f"Error processing DOCX file: {e}")

    @staticmethod
    def extract_text_from_pdf(file_content: Union[bytes, BinaryIO]) -> str:
        """Extract text from PDF file with page markers"""
        try:
            if isinstance(file_content, bytes):
                file_content = io.BytesIO(file_content)

            reader = PyPDF2.PdfReader(file_content)
            text_content = []

            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():  # Only add non-empty pages
                    # Add page marker for AI to understand page boundaries
                    page_marker = f"\n\n=== PAGE {page_num} ===\n"
                    text_content.append(page_marker + page_text)

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
        """Download and process file from Google Drive using OAuth2 credentials"""
        if not self.drive_service:
            raise Exception("Google Drive API not initialized. Please authenticate with Google.")

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
            error_msg = str(e).lower()
            if "not found" in error_msg or "permission" in error_msg or "forbidden" in error_msg:
                raise Exception(
                    "File access denied. You don't have permission to access this file, or it doesn't exist.")
            else:
                raise Exception(f"Error downloading file from Google Drive: {e}")

    def process_google_drive_url(self, url_or_id: str) -> str:
        """Process Google Drive URL or ID with public access fallback"""
        file_id = self.extract_google_drive_id(url_or_id)
        
        # If we have credentials, try authenticated access first
        if self.credentials:
            try:
                return self.download_from_google_drive(file_id)
            except Exception as auth_error:
                # If authenticated access fails, try public access
                pass
        
        # Try public access methods
        try:
            return self._try_public_google_drive_access(file_id)
        except Exception as public_error:
            # If both public and authenticated failed, require OAuth2
            if not self.credentials:
                raise Exception("OAuth2 credentials required for Google Drive access. Please authenticate with Google.")
            else:
                # Re-raise the original authenticated error
                return self.download_from_google_drive(file_id)
    
    def _try_public_google_drive_access(self, file_id: str) -> str:
        """Try to access Google Drive file as public document"""
        
        # Try different public access URLs
        public_urls = [
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"https://docs.google.com/document/d/{file_id}/export?format=txt",
            f"https://docs.google.com/document/d/{file_id}/export?format=docx",
            f"https://docs.google.com/presentation/d/{file_id}/export?format=txt",
            f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        ]
        
        for url in public_urls:
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200 and response.content:
                    # Handle different content types
                    if 'txt' in url or 'csv' in url:
                        return response.text
                    elif 'docx' in url:
                        return self.extract_text_from_docx(response.content)
                    else:
                        # Try to detect file type from content
                        content = response.content
                        if content.startswith(b'PK'):  # ZIP/DOCX signature
                            return self.extract_text_from_docx(content)
                        elif content.startswith(b'%PDF'):  # PDF signature
                            return self.extract_text_from_pdf(content)
                        else:
                            # Try as text
                            return content.decode('utf-8', errors='ignore')
            except Exception:
                continue
        
        raise Exception("Could not access file as public document. File may be private or does not exist.")