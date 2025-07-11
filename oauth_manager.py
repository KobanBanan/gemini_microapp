import requests
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleOAuthManager:
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/documents.readonly',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]

    @staticmethod
    def is_authenticated():
        """Check if user is authenticated via streamlit_oauth"""
        return 'token' in st.session_state

    def get_user_email(self):
        """Get authenticated user's email"""
        if self.is_authenticated():
            token = st.session_state['token']
            return token.get('userinfo', {}).get('email')
        return None

    def get_credentials(self):
        """Get OAuth2 credentials from streamlit_oauth token"""
        if not self.is_authenticated():
            return None

        token = st.session_state['token']

        # Create credentials from token
        credentials = Credentials(
            token=token.get('access_token'),
            refresh_token=token.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            scopes=self.scopes
        )

        return credentials

    def refresh_credentials(self):
        """Refresh OAuth2 credentials if needed"""
        credentials = self.get_credentials()
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                # Update token in session state
                st.session_state['token']['access_token'] = credentials.token
                print("[INFO] OAuth2 credentials refreshed")
                return True
            except Exception as e:
                print(f"[INFO] Error refreshing credentials: {str(e)}")
                return False
        return True

    def fetch_authenticated_doc_content(self, doc_url):
        """Fetch document content using user's OAuth2 credentials"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("User not authenticated. Please login with Google.")

        # Refresh credentials if needed
        if not self.refresh_credentials():
            raise Exception("Failed to refresh credentials. Please login again.")

        # Extract document ID
        import re
        pattern = r'/document/d/([a-zA-Z0-9-_]+)'
        match = re.search(pattern, doc_url)
        if not match:
            raise ValueError("Cannot extract document ID from URL")

        doc_id = match.group(1)

        try:
            # Build Google Docs API service with user credentials
            service = build('docs', 'v1', credentials=credentials)

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
                raise Exception(
                    f"Document access denied. You don't have permission to access this document, or it doesn't exist.")
            else:
                # Try export method as fallback
                try:
                    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

                    # Use OAuth2 credentials to make authenticated request
                    authed_session = requests.Session()

                    # Refresh credentials if needed
                    if not self.refresh_credentials():
                        raise Exception("Failed to refresh credentials")

                    authed_session.headers.update({
                        'Authorization': f'Bearer {credentials.token}'
                    })

                    response = authed_session.get(export_url, timeout=30)
                    if response.status_code == 200:
                        return response.text
                    elif response.status_code == 403:
                        raise Exception("Document access denied. You don't have permission to access this document.")
                    else:
                        raise Exception(f"Failed to fetch document: {response.status_code}")

                except Exception as export_error:
                    raise Exception("Document access denied. You don't have permission to access this document.")


def get_oauth_manager():
    """Get or create OAuth manager instance"""
    if 'oauth_manager' not in st.session_state:
        st.session_state.oauth_manager = GoogleOAuthManager()
    return st.session_state.oauth_manager
