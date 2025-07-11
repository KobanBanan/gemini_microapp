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
        self.credentials = None
        self.user_email = None

        # Load credentials from streamlit session state (OAuth2)
        self.load_oauth_credentials()

    def load_oauth_credentials(self):
        """Load OAuth2 credentials from Streamlit session state"""
        try:
            # Get OAuth2 token from streamlit session state
            if 'oauth_token' in st.session_state and st.session_state.oauth_token:
                token_data = st.session_state.oauth_token

                # Create credentials object from OAuth2 token
                self.credentials = Credentials(
                    token=token_data.get('access_token'),
                    refresh_token=token_data.get('refresh_token'),
                    id_token=token_data.get('id_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=token_data.get('client_id'),
                    client_secret=token_data.get('client_secret'),
                    scopes=self.scopes
                )

                # Extract user email from token
                if 'email' in token_data:
                    self.user_email = token_data['email']

                console.log(f"OAuth2 credentials loaded for: {self.user_email}")
                return True
            else:
                console.log("No OAuth2 token found in session state")
                return False

        except Exception as e:
            console.log(f"Error loading OAuth2 credentials: {str(e)}")
            return False

    def is_authenticated(self):
        """Check if user is authenticated via OAuth2"""
        return (
                self.credentials is not None and
                st.session_state.get('authentication_status') is True and
                'oauth_token' in st.session_state
        )

    def get_user_email(self):
        """Get authenticated user's email"""
        if self.user_email:
            return self.user_email

        # Try to get email from session state
        if 'email' in st.session_state:
            return st.session_state['email']

        return None

    def has_client_config(self):
        """Check if OAuth2 credentials are loaded"""
        return self.credentials is not None

    def get_credentials(self):
        """Get current OAuth2 credentials"""
        return self.credentials

    def refresh_credentials(self):
        """Refresh OAuth2 credentials if needed"""
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
                console.log("OAuth2 credentials refreshed")
                return True
            except Exception as e:
                console.log(f"Error refreshing credentials: {str(e)}")
                return False
        return True

    def logout(self):
        """Clear OAuth2 credentials"""
        console.log("Clearing OAuth2 credentials...")
        self.credentials = None
        self.user_email = None

        # Clear session state
        if 'oauth_token' in st.session_state:
            del st.session_state['oauth_token']

    def fetch_authenticated_doc_content(self, doc_url):
        """Fetch document content using user's OAuth2 credentials"""
        if not self.credentials:
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
                        'Authorization': f'Bearer {self.credentials.token}'
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
    else:
        # Reload credentials in case they changed
        st.session_state.oauth_manager.load_oauth_credentials()
    return st.session_state.oauth_manager


# Add console.log function for clean logging
class Console:
    def log(self, message):
        """Simple console logging"""
        print(f"[INFO] {message}")


console = Console()
