import json
import os
import yaml
from yaml.loader import SafeLoader

import streamlit as st
from streamlit_authenticator import Authenticate

from backend import call_gemini_api, convert_to_csv, convert_to_json, get_document_content
from cache_manager import CacheManager
from knowledge import O1, EB1
from oauth_manager import get_oauth_manager
from prompt import SYSTEM_PROMPT


def main():
    st.set_page_config(
        page_title="Google Docs Analyzer with Gemini AI",
        page_icon="📄",
        layout="wide"
    )

    # Load authentication configuration
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)

    # Create authenticator object for OAuth2 only
    # Minimal credentials structure required by streamlit_authenticator
    minimal_credentials = {'usernames': {}}
    
    authenticator = Authenticate(
        minimal_credentials,
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

    # OAuth2 Google Authentication
    try:
        authenticator.experimental_guest_login('Login with Google',
                                               provider='google',
                                               oauth2=config['oauth2'])
    except Exception as e:
        st.error(f"OAuth2 setup error: {str(e)}")
        st.stop()

    # Get authentication status from session state
    name = st.session_state.get('name')
    authentication_status = st.session_state.get('authentication_status')
    username = st.session_state.get('username')

    # Check authentication status
    if authentication_status == False:
        st.error('Username/password is incorrect')
        return
    elif authentication_status is None:
        st.warning('Please enter your username and password')
        return
    elif authentication_status:
        # User is authenticated, show main app
        st.title("Google Docs Analyzer with Gemini AI")
        st.markdown("---")

        # Initialize OAuth manager
        oauth_manager = get_oauth_manager()

        # Initialize Cache manager
        cache_manager = CacheManager()

        # Initialize session state
        if 'analysis_result' not in st.session_state:
            st.session_state.analysis_result = None
        if 'current_url' not in st.session_state:
            st.session_state.current_url = ""
        if 'current_system_prompt' not in st.session_state:
            st.session_state.current_system_prompt = SYSTEM_PROMPT
        if 'use_o1_knowledge' not in st.session_state:
            st.session_state.use_o1_knowledge = True
        if 'use_eb1_knowledge' not in st.session_state:
            st.session_state.use_eb1_knowledge = True
        if 'upload_mode' not in st.session_state:
            st.session_state.upload_mode = "google_drive"
        if 'uploaded_file' not in st.session_state:
            st.session_state.uploaded_file = None
        if 'google_drive_url' not in st.session_state:
            st.session_state.google_drive_url = ""

        # Function to build system prompt with knowledge
        def build_system_prompt():
            prompt = SYSTEM_PROMPT

            knowledge_sections = []
            if st.session_state.use_o1_knowledge:
                knowledge_sections.append("O-1 visa requirements")
            if st.session_state.use_eb1_knowledge:
                knowledge_sections.append("EB-1 visa requirements")

            if knowledge_sections:
                knowledge_instruction = f"\n\nIMPORTANT: When analyzing documents, pay special attention to {' and '.join(knowledge_sections)}. Use the following legal knowledge as reference:\n\n"
                prompt += knowledge_instruction

                if st.session_state.use_o1_knowledge:
                    prompt += "=== O-1 VISA REQUIREMENTS ===\n"
                    prompt += O1 + "\n\n"

                if st.session_state.use_eb1_knowledge:
                    prompt += "=== EB-1 VISA REQUIREMENTS ===\n"
                    prompt += EB1 + "\n\n"

            return prompt

        # System Prompt Configuration (expandable)
        with st.expander("System Prompt Configuration", expanded=False):
            st.write("View and edit the system prompt that guides AI analysis:")

            # Build current prompt with knowledge
            current_prompt = build_system_prompt()

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

        # Sidebar with settings
        with st.sidebar:
            # Logout button and welcome message
            st.write(f'Welcome *{name}*')
            authenticator.logout(location='sidebar')
            st.markdown("---")

            st.header("Settings")

            # API Key for Gemini
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if api_key:
                st.success("API Key loaded from environment variables")
            else:
                api_key = st.text_input(
                    "Gemini API Key:",
                    type="password",
                    help="Enter your Gemini API key"
                )

            st.markdown("---")

            # Google OAuth2 Status
            if oauth_manager.is_authenticated():
                user_email = oauth_manager.get_user_email()
                st.success("✅ Google authenticated")
                if user_email:
                    st.info(f"**Logged in as:** {user_email}")
                st.caption("You can access your Google Drive documents")
            else:
                st.warning("⚠️ Google OAuth2 required")
                st.info("Please login with Google to access your documents")

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

        # Main application area - Document upload section
        st.subheader("📄 Document Upload")

        # Upload mode selection
        upload_mode = st.radio(
            "Choose document source:",
            ["google_drive", "local_upload"],
            format_func=lambda x: "Google Drive Files" if x == "google_drive" else "Local Upload",
            key="upload_mode",
            horizontal=True,
            help="Select how you want to provide the document"
        )

        # Document input based on selected mode
        doc_url = ""
        uploaded_file = None

        if st.session_state.upload_mode == "google_drive":
            st.markdown("**☁️ Google Drive File URL/ID**")
            doc_url = st.text_input(
                "Google Drive URL/ID Input",
                placeholder="Paste Google Drive file URL or ID...",
                help="Supports DOCX, PDF, TXT files from Google Drive",
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

        # Process analysis
        if analyze_button:
            if not api_key:
                st.error("Please enter Gemini API key")
                return

            # Validate inputs based on upload mode
            if st.session_state.upload_mode == "google_drive" and not doc_url:
                st.error("Please enter document URL")
                return
            elif st.session_state.upload_mode == "local_upload" and uploaded_file is None:
                st.error("Please upload a file")
                return

            # Clear session state for new analysis
            st.session_state.analysis_result = None

            # Create cache key based on source
            if st.session_state.upload_mode == "local_upload":
                cache_key = f"local_file_{uploaded_file.name}_{uploaded_file.size}"
            else:
                cache_key = doc_url

            st.session_state.current_url = cache_key

            # Check cache first
            final_prompt = build_system_prompt()
            cached_result = cache_manager.get_cached_result(
                cache_key, final_prompt,
                st.session_state.use_o1_knowledge,
                st.session_state.use_eb1_knowledge
            )

            if cached_result:
                st.info(f"Found cached result from {cached_result['created_at']}")
                use_cache = st.button("Use Cached Result", type="secondary")
                if use_cache:
                    st.session_state.analysis_result = cached_result['analysis_result']
                    st.success("Used cached result!")
                    st.rerun()

                proceed_anyway = st.button("Analyze Anyway", type="primary")
                if not proceed_anyway:
                    return

            # Progress bar and spinner
            with st.spinner("Processing your document..."):
                progress_bar = st.progress(0)
                status_text = st.empty()

                try:
                    # Step 1: Fetch document content
                    status_text.text("Loading document...")
                    progress_bar.progress(25)

                    # Use new unified function to get document content
                    if st.session_state.upload_mode == "google_drive":
                        doc_content = get_document_content("google_drive", doc_url, oauth_manager)
                    elif st.session_state.upload_mode == "local_upload":
                        doc_content = get_document_content("uploaded_file", uploaded_file, oauth_manager)

                    st.success("Document loaded successfully")

                    # Step 2: Prepare prompt
                    status_text.text("Preparing request...")
                    progress_bar.progress(50)

                    # Step 3: Call Gemini API with document content
                    status_text.text("Analyzing with Gemini AI...")
                    progress_bar.progress(75)

                    # Use the current system prompt (which may include knowledge)
                    final_prompt = build_system_prompt()
                    result = call_gemini_api(doc_content, api_key, final_prompt)

                    # Step 4: Process results
                    status_text.text("Processing results...")
                    progress_bar.progress(100)

                    # Save results to session state
                    st.session_state.analysis_result = result

                    # Save to cache
                    if cache_manager.save_to_cache(
                            cache_key, result, final_prompt,
                            st.session_state.use_o1_knowledge,
                            st.session_state.use_eb1_knowledge
                    ):
                        st.success("Result saved to cache!")

                    # Clear progress
                    progress_bar.empty()
                    status_text.empty()

                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    error_msg = str(e)

                    # Provide helpful error messages
                    st.error(f"Error during analysis: {error_msg}")

        # Display results from session state
        if st.session_state.analysis_result:
            # Display results
            st.markdown("---")
            st.subheader("Analysis Results")

            # Show JSON result
            with st.expander("View Results", expanded=True):
                try:
                    parsed_result = json.loads(st.session_state.analysis_result)
                    st.json(parsed_result)

                    # Statistics
                    if isinstance(parsed_result, list):
                        st.info(f"Errors found: {len(parsed_result)}")

                except json.JSONDecodeError:
                    st.text_area("Analysis Result", st.session_state.analysis_result, height=300)

            # Download buttons under results
            col1, col2 = st.columns(2)

            with col1:
                # Download JSON
                try:
                    json_data = convert_to_json(st.session_state.analysis_result)
                    st.download_button(
                        label="Download JSON",
                        data=json_data,
                        file_name="analysis_results.json",
                        mime="application/json",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error preparing JSON: {str(e)}")

            with col2:
                # Download CSV
                try:
                    csv_data = convert_to_csv(st.session_state.analysis_result)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name="analysis_results.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error preparing CSV: {str(e)}")

        # Cache History Section
        st.markdown("---")

        # Get cache stats
        cache_stats = cache_manager.get_cache_stats()

        with st.expander(f"Cache History ({cache_stats['total_entries']} entries)", expanded=False):
            if cache_stats['total_entries'] > 0:
                st.write(f"📊 **Stats:** {cache_stats['unique_urls']} unique URLs, {cache_stats['db_size_mb']} MB")

                # Clear all cache button
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("🗑️ Clear All Cache", type="secondary"):
                        if cache_manager.clear_all_cache():
                            st.success("Cache cleared!")
                            st.rerun()
                        else:
                            st.error("Failed to clear cache")

                st.markdown("---")

                # Display cached results
                cached_results = cache_manager.get_all_cached_results()

                for i, result in enumerate(cached_results):
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])

                        with col1:
                            # Display URL (truncated)
                            url_display = result['doc_url']
                            if len(url_display) > 60:
                                url_display = url_display[:60] + "..."

                            st.write(f"**{url_display}**")

                            # Knowledge flags
                            flags = []
                            if result['o1_enabled']:
                                flags.append("O1")
                            if result['eb1_enabled']:
                                flags.append("EB1")

                            flag_str = " | ".join(flags) if flags else "No knowledge"
                            st.caption(f"🗓️ {result['created_at']} | 🧠 {flag_str}")

                        with col2:
                            # Download buttons
                            try:
                                # JSON download
                                json_data = convert_to_json(result['analysis_result'])
                                st.download_button(
                                    label="JSON",
                                    data=json_data,
                                    file_name=f"cached_analysis_{result['id']}.json",
                                    mime="application/json",
                                    key=f"json_{result['id']}",
                                    use_container_width=True
                                )
                            except:
                                st.write("JSON error")

                        with col3:
                            try:
                                # CSV download
                                csv_data = convert_to_csv(result['analysis_result'])
                                st.download_button(
                                    label="CSV",
                                    data=csv_data,
                                    file_name=f"cached_analysis_{result['id']}.csv",
                                    mime="text/csv",
                                    key=f"csv_{result['id']}",
                                    use_container_width=True
                                )
                            except:
                                st.write("CSV error")

                        # Delete button
                        if st.button(f"🗑️ Delete", key=f"delete_{result['id']}", type="secondary"):
                            if cache_manager.delete_cache_entry(result['id']):
                                st.success("Entry deleted!")
                                st.rerun()
                            else:
                                st.error("Failed to delete entry")

                        if i < len(cached_results) - 1:
                            st.markdown("---")
            else:
                st.write("No cached results yet. Analyze some documents to build your cache!")


if __name__ == "__main__":
    main()
