import json
import os

import requests
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build


class GoogleOAuthManager:
    def __init__(self, credentials_file='creds.json'):
        self.credentials_file = credentials_file
        self.scopes = [
            'https://www.googleapis.com/auth/documents.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        self.credentials = None
        self.service_account_email = None
        self.is_service_account = False

        # Load credentials automatically
        self.load_credentials()

    def load_credentials(self):
        """Load Service Account credentials from creds.json"""
        try:
            if not os.path.exists(self.credentials_file):
                console.log(f"Credentials file not found: {self.credentials_file}")
                return False

            with open(self.credentials_file, 'r') as f:
                creds_data = json.load(f)

            # Check if it's a service account
            if creds_data.get('type') == 'service_account':
                self.is_service_account = True
                self.service_account_email = creds_data.get('client_email')

                # Create service account credentials
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file,
                    scopes=self.scopes
                )

                console.log(f"Service account loaded: {self.service_account_email}")
                return True
            else:
                console.log("Not a service account credentials file")
                return False

        except Exception as e:
            console.log(f"Error loading credentials: {str(e)}")
            return False

    def is_authenticated(self):
        """Check if service account is loaded"""
        return self.credentials is not None and self.is_service_account

    def get_service_account_email(self):
        """Get service account email for sharing documents"""
        return self.service_account_email

    def has_client_config(self):
        """Check if credentials are loaded"""
        return self.credentials is not None

    def get_credentials(self):
        """Get current credentials"""
        return self.credentials

    def logout(self):
        """Clear credentials (reload from file)"""
        console.log("Reloading credentials...")
        self.load_credentials()

    def fetch_authenticated_doc_content(self, doc_url):
        """Fetch document content using service account credentials"""
        if not self.credentials:
            raise Exception("Service account not loaded. Please check creds.json file.")

        # Extract document ID
        import re
        pattern = r'/document/d/([a-zA-Z0-9-_]+)'
        match = re.search(pattern, doc_url)
        if not match:
            raise ValueError("Cannot extract document ID from URL")

        doc_id = match.group(1)

        try:
            # Build Google Docs API service
            service = build('docs', 'v1', credentials=self.credentials)

            # Get document content
            document = service.documents().get(documentId=doc_id).execute()

            # Extract text content
            content = []
            for element in document.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    for text_run in element['paragraph'].get('elements', []):
                        if 'textRun' in text_run:
                            content.append(text_run['textRun']['content'])

            return ''.join(content)

        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "permission" in error_msg or "forbidden" in error_msg:
                raise Exception(f"Document access denied. Please share the document with: {self.service_account_email}")
            else:
                # Try export method as fallback
                try:
                    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

                    # Use credentials to make authenticated request
                    authed_session = requests.Session()

                    # Get access token
                    self.credentials.refresh(requests.Request())
                    authed_session.headers.update({
                        'Authorization': f'Bearer {self.credentials.token}'
                    })

                    response = authed_session.get(export_url, timeout=30)
                    if response.status_code == 200:
                        return response.text
                    elif response.status_code == 403:
                        raise Exception(
                            f"Document access denied. Please share the document with: {self.service_account_email}")
                    else:
                        raise Exception(f"Failed to fetch document: {response.status_code}")

                except Exception as export_error:
                    raise Exception(
                        f"Document access denied. Please share the document with: {self.service_account_email}")


def get_oauth_manager():
    """Get or create OAuth manager instance"""
    if 'oauth_manager' not in st.session_state:
        st.session_state.oauth_manager = GoogleOAuthManager()
    return st.session_state.oauth_manager


# Add console.log function for clean logging
class Console:
    def log(self, message):
        """Simple console logging"""
        print(f"[INFO] {message}")


console = Console()
