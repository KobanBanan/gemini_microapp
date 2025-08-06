import logging
import os

import streamlit as st
import yaml
from yaml.loader import SafeLoader

from auth import handle_authentication, render_auth_sidebar_info, render_google_drive_status, get_oauth_manager
from backend import call_gemini_api, get_document_content
from docs.knowledge import O1, EB1
from prompt import SYSTEM_PROMPT
from ui.display_results import display_analysis_results
from ui.database_ui import (
    render_full_analysis_history,
    render_database_management,
    render_simple_analysis_history,
    save_current_analysis_to_db
)
from utils import build_system_prompt_with_knowledge, extract_google_drive_filename


def initialize_session_state():
    """Initialize all session state variables"""
    session_defaults = {
        'analysis_result': None,
        'current_url': "",
        'current_system_prompt': SYSTEM_PROMPT,
        'use_o1_knowledge': False,
        'use_eb1_knowledge': False,
        'upload_mode': "google_drive",
        'uploaded_file': None,
        'google_drive_url': "",
        'document_content': None,
        'document_source_url': None,
        'show_full_history': False,
        'show_db_management': False,
        'current_user_email': None
    }

    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def render_system_prompt_configuration():
    """Render system prompt configuration section"""
    with st.expander("System Prompt Configuration", expanded=False):
        st.write("View and edit the system prompt that guides AI analysis:")

        # Build current prompt with knowledge
        current_prompt = build_system_prompt_with_knowledge(
            SYSTEM_PROMPT,
            st.session_state.use_o1_knowledge,
            st.session_state.use_eb1_knowledge,
            O1,
            EB1
        )

        temp_prompt = st.text_area(
            "System Prompt Editor",
            value=current_prompt,
            height=200,
            help="Edit the system prompt that guides AI analysis behavior",
            label_visibility="collapsed"
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Save Prompt", type="secondary"):
                st.session_state.current_system_prompt = temp_prompt
                st.success("Prompt saved!")

        with col2:
            if st.button("Reset to Default"):
                st.session_state.current_system_prompt = SYSTEM_PROMPT
                st.session_state.use_o1_knowledge = False
                st.session_state.use_eb1_knowledge = False
                st.rerun()


def render_sidebar(auth_enabled, token):
    """Render sidebar with authentication and settings"""
    with st.sidebar:
        # Authentication info
        render_auth_sidebar_info(auth_enabled, token)
        st.markdown("---")

        st.header("Settings")

        # API Key for Gemini
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            st.success("✅ Gemini API Key loaded")
        else:
            api_key = st.text_input(
                "Gemini API Key:",
                type="password",
                help="Enter your Gemini API key"
            )

        st.markdown("---")

        # Google OAuth2 Status
        render_google_drive_status(auth_enabled, token)

        st.markdown("---")

        # Knowledge Section
        st.subheader("Knowledge Base")
        st.write("Enable additional legal knowledge for analysis:")

        o1_enabled = st.checkbox(
            "O-1 Visa Requirements",
            value=st.session_state.use_o1_knowledge,
            help="Include O-1 nonimmigrant visa requirements and criteria"
        )

        eb1_enabled = st.checkbox(
            "EB-1 Visa Requirements",
            value=st.session_state.use_eb1_knowledge,
            help="Include EB-1 immigrant visa requirements and criteria"
        )

        # Update session state if checkboxes changed
        if o1_enabled != st.session_state.use_o1_knowledge:
            st.session_state.use_o1_knowledge = o1_enabled

        if eb1_enabled != st.session_state.use_eb1_knowledge:
            st.session_state.use_eb1_knowledge = eb1_enabled

        st.markdown("---")

    return api_key


def render_document_upload():
    """Render document upload section and return upload inputs"""
    st.subheader("📄 Document Upload")

    # Upload mode selection
    upload_mode = st.radio(
        "Choose document source:",
        ["google_drive", "local_upload"],
        format_func=lambda x: "Google Drive Files (Public)" if x == "google_drive" else "Local Upload",
        key="upload_mode",
        horizontal=True,
        help="Select how you want to provide the document"
    )

    # Document input based on selected mode
    doc_url = ""
    uploaded_file = None

    if st.session_state.upload_mode == "google_drive":
        st.markdown("**☁️ Google Drive File URL/ID**")
        st.info("📄 Only public Google Drive documents are accessible without authentication")
        doc_url = st.text_input(
            "Google Drive URL/ID Input",
            placeholder="Paste Google Drive file URL or ID...",
            help="Supports public DOCX, PDF, TXT files from Google Drive",
            label_visibility="collapsed"
        )

    elif st.session_state.upload_mode == "local_upload":
        st.markdown("**💻 Local File Upload**")
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['docx', 'pdf', 'txt'],
            help="Drag and drop or click to upload DOCX, PDF, or TXT files",
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            st.info(f"📊 File size: {uploaded_file.size / 1024:.1f} KB")

    return doc_url, uploaded_file


def process_document_analysis(api_key, doc_url, uploaded_file, oauth_manager):
    """Process document analysis and update session state"""
    logging.info("Starting document analysis")
    
    # Validate inputs based on upload mode
    if st.session_state.upload_mode == "google_drive" and not doc_url:
        st.error("Please enter document URL")
        return
    elif st.session_state.upload_mode == "local_upload" and uploaded_file is None:
        st.error("Please upload a file")
        return

    # Clear session state for new analysis
    st.session_state.analysis_result = None

    # Progress bar and spinner
    with st.spinner("Processing your document..."):
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Create status callback to update UI in real-time
        def status_callback(message):
            status_text.text(message)

        try:
            # Step 1: Fetch document content
            status_text.text("Loading document...")
            progress_bar.progress(25)

            # Use unified function to get document content
            if st.session_state.upload_mode == "google_drive":
                doc_content = get_document_content("google_drive", doc_url, oauth_manager, status_callback)
            elif st.session_state.upload_mode == "local_upload":
                doc_content = get_document_content("uploaded_file", uploaded_file, oauth_manager, status_callback)

            # Check if doc_content is None
            if doc_content is None:
                logging.error("Document content is None after loading")
                st.error("Failed to load document content")
                return
            
            st.success("Document loaded successfully")

            # Step 2: Prepare prompt
            status_text.text("Preparing request...")
            progress_bar.progress(50)

            # Use the current system prompt (which may include knowledge)
            final_prompt = build_system_prompt_with_knowledge(
                SYSTEM_PROMPT,
                st.session_state.use_o1_knowledge,
                st.session_state.use_eb1_knowledge,
                O1,
                EB1
            )

            # Step 3: Call Gemini API with document content
            status_text.text("Analyzing with Gemini AI...")
            progress_bar.progress(75)

            result = call_gemini_api(doc_content, api_key, final_prompt, status_callback)
            
            if result is None:
                logging.error("Gemini API returned None")
                st.error("Failed to get response from Gemini API")
                return

            # Step 4: Process results
            status_text.text("Processing results...")
            progress_bar.progress(100)

            # Save results to session state
            st.session_state.analysis_result = result
            st.session_state.document_content = doc_content
            st.session_state.document_source_url = doc_url if st.session_state.upload_mode == "google_drive" else None

            # Auto-save to database if user is set and result exists
            if st.session_state.current_user_email and result:
                # Determine file name and URL
                if st.session_state.upload_mode == "google_drive":
                    file_url = doc_url
                    file_name = extract_google_drive_filename(doc_url)
                else:
                    file_url = f"local_upload_{uploaded_file.name}"
                    file_name = uploaded_file.name
                
                # Check for None values before saving
                if file_url is None or file_name is None:
                    logging.error(f"None values before DB save: file_url={file_url}, file_name={file_name}")
                    st.warning("Warning: Could not determine file details for database save")
                else:
                    logging.info(
                        f"Saving to database: "
                        f"file_url={file_url}, "
                        f"file_name={file_name}, "
                        f"user={st.session_state.current_user_email}"
                    )
                    save_current_analysis_to_db(file_url, file_name, st.session_state.current_user_email, result)

            # Clear progress
            progress_bar.empty()
            status_text.empty()
            logging.info("Analysis completed")

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            error_msg = str(e)
            
            # Error logging
            logging.error(f"Analysis failed: {error_msg}")
            
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            
            # Provide helpful error messages
            if "Gemini API connection failed" in error_msg:
                st.error(f"Connection to Gemini API failed: {error_msg}")
                st.info("This is usually a temporary server issue. Please try again in a few minutes.")
            else:
                st.error(f"Error during analysis: {error_msg}")


def main():
    """Main application function"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('analysis.log'),
        ]
    )
    
    st.set_page_config(
        page_title="Google Docs Analyzer with Gemini AI",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Load configuration
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)

    auth_config = config.get('auth', {'enabled': False})
    oauth2_config = config['oauth2']

    # Handle authentication
    token = handle_authentication(auth_config, oauth2_config)

    # If authentication is required but not completed, stop here
    if token == 'redirect':
        return

    # Continue with main app
    st.title("Google Docs Analyzer with Gemini AI")
    st.markdown("---")

    # Initialize OAuth manager and session state
    oauth_manager = get_oauth_manager()
    initialize_session_state()

    # Get current user email from token
    if token and isinstance(token, dict):
        user_email = token.get('userinfo', {}).get('email')
        st.session_state.current_user_email = user_email
    else:
        # Set default user for local uploads when no authentication
        st.session_state.current_user_email = "local_user"
    
    # Handle special UI states
    if st.session_state.show_full_history:
        st.title("📚 Analysis History")
        render_full_analysis_history(st.session_state.current_user_email)
        
        if st.button("🔙 Back to Main"):
            st.session_state.show_full_history = False
            st.rerun()
        
        # Show database management section
        st.markdown("---")
        render_database_management(st.session_state.current_user_email)
        return
    
    # Main application UI
    # Render system prompt configuration
    render_system_prompt_configuration()
    
    # Render simplified analysis history under system prompt
    render_simple_analysis_history(st.session_state.current_user_email)

    # Render sidebar and get API key
    api_key = render_sidebar(auth_config.get('enabled', False), token)

    # Render document upload section
    doc_url, uploaded_file = render_document_upload()

    # Analysis button
    analyze_button = st.button(
        "🔍 Analyze Document",
        type="primary",
        use_container_width=False,
        disabled=(
                (st.session_state.upload_mode == "google_drive" and not doc_url) or
                (st.session_state.upload_mode == "local_upload" and uploaded_file is None)
        )
    )

    # Process analysis if button clicked
    if analyze_button:
        if not api_key:
            st.error("Please enter Gemini API key")
            return

        process_document_analysis(api_key, doc_url, uploaded_file, oauth_manager)

    # Display results from session state
    display_analysis_results(st.session_state.analysis_result)


if __name__ == "__main__":
    main()
