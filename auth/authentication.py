"""Authentication module for Google OAuth2"""
import streamlit as st
from streamlit_oauth import OAuth2Component


def setup_oauth2_component(oauth2_config):
    """Setup OAuth2Component with configuration"""
    return OAuth2Component(
        oauth2_config['client_id'],
        oauth2_config['client_secret'],
        oauth2_config['authorize_url'],
        oauth2_config['token_url'],
        oauth2_config['refresh_token_url'],
        oauth2_config['revoke_token_url']
    )


def handle_authentication(auth_config, oauth2_config):
    """
    Handle authentication flow based on configuration.
    Returns token if user is authenticated, None otherwise.
    If authentication is required but not completed, returns 'redirect'.
    """
    auth_enabled = auth_config.get('enabled', False)
    
    if not auth_enabled:
        # Authentication disabled - proceed without token
        return None
    
    # Authentication is enabled
    oauth2 = setup_oauth2_component(oauth2_config)
    
    # Check if token exists in session state
    if 'token' not in st.session_state:
        # If not, show login page
        st.title("Google Docs Analyzer with Gemini AI")
        st.markdown("---")
        st.write("Please authenticate with Google to access your documents")

        # Show authorize button
        result = oauth2.authorize_button(
            "🔐 Login with Google",
            oauth2_config['redirect_uri'],
            oauth2_config['scope']
        )

        if result and 'token' in result:
            # If authorization successful, save token in session state
            st.session_state.token = result.get('token')
            st.success("✅ Successfully authenticated!")
            st.rerun()

        # Return special value to indicate redirect needed
        return 'redirect'

    # User is authenticated - get token
    return st.session_state['token']


def render_auth_sidebar_info(auth_enabled, token):
    """Render authentication information in sidebar"""
    if auth_enabled and token:
        # User info and logout
        user_email = token.get('userinfo', {}).get('email', 'Unknown')
        st.success(f"✅ Logged in as: {user_email}")

        if st.button("🚪 Logout"):
            # Clear token and rerun
            del st.session_state.token
            st.rerun()
    elif auth_enabled:
        st.warning("⚠️ Authentication required but not completed")
    else:
        st.info("🔧 Authentication disabled in configuration")


def render_google_drive_status(auth_enabled, token):
    """Render Google Drive access status in sidebar"""
    if auth_enabled:
        if token:
            st.success("✅ Google Drive: Full access")
            st.caption("You can access private Google Drive documents")
        else:
            st.warning("⚠️ Google Drive: Limited access")
            st.caption("Only public documents accessible")
    else:
        st.info("ℹ️ Google Drive: Public documents only")
        st.caption("Authentication disabled / Local upload: fully available")