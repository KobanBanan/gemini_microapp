"""Database UI components for displaying analysis history and management"""

import json
from typing import Optional

import pandas as pd
import streamlit as st

from backend import convert_to_csv, convert_to_json
from database_manager import DatabaseManager


def render_analysis_history_sidebar(user_email: Optional[str] = None):
    """Render analysis history section in sidebar"""
    st.subheader("📚 Analysis History")

    db = DatabaseManager()

    # Get database stats
    stats = db.get_database_stats()

    with st.expander("📊 Database Statistics", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Analyses", stats['total_entries'])
            st.metric("Unique Files", stats['unique_files'])
        with col2:
            st.metric("Unique Users", stats['unique_users'])
            st.metric("Recent (24h)", stats['recent_entries_24h'])

        st.metric("Database Size", f"{stats['db_size_mb']} MB")

    # Show recent history for current user
    if user_email:
        recent_history = db.get_user_analysis_history(user_email, limit=5)

        if recent_history:
            st.write("**🕒 Your Recent Analyses:**")
            for i, entry in enumerate(recent_history):
                with st.container():
                    st.markdown(f"""
                    <div style='border: 1px solid #e0e0e0; padding: 8px; margin: 4px 0; border-radius: 4px; background-color: #f9f9f9;'>
                        <strong>{entry['file_name']}</strong><br/>
                        <small>📅 {entry['check_timestamp']}</small><br/>
                        <small>🔍 {len(entry['check_result']) if isinstance(entry['check_result'], list) else 'N/A'} issues found</small>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"📥 Load Result #{i + 1}", key=f"load_result_{entry['id']}"):
                        # Load this result into session state
                        st.session_state.analysis_result = json.dumps(entry['check_result'])
                        st.session_state.current_url = entry['file_url']
                        st.success(f"✅ Loaded analysis for {entry['file_name']}")
                        st.rerun()
        else:
            st.info("No previous analyses found")

    # Management buttons
    st.markdown("---")
    if st.button("🗂️ View Full History", key="view_full_history"):
        st.session_state.show_full_history = True


def render_full_analysis_history(user_email: Optional[str] = None):
    """Render full analysis history page"""
    st.subheader("📚 Complete Analysis History")

    db = DatabaseManager()

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        show_all_users = st.checkbox("Show all users", value=not user_email)

    with col2:
        limit = st.selectbox("Results per page", [10, 25, 50, 100], index=1)

    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()

    # Get history data
    if show_all_users:
        history = db.get_all_analysis_history()[:limit]
    else:
        history = db.get_user_analysis_history(user_email or "", limit=limit)

    if not history:
        st.info("No analysis history found")
        return

    # Display history table
    st.write(f"Showing {len(history)} most recent analyses:")

    # Convert to DataFrame for better display
    display_data = []
    for entry in history:
        display_data.append({
            'ID': entry['id'],
            'File Name': entry['file_name'],
            'User Email': entry.get('user_email', 'N/A'),
            'Date': entry['check_timestamp'],
            'Issues Found': len(entry['check_result']) if isinstance(entry['check_result'], list) else 'N/A',
            'File URL': entry['file_url'][:50] + '...' if len(entry['file_url']) > 50 else entry['file_url']
        })

    df = pd.DataFrame(display_data)

    # Display table with selection
    event = st.dataframe(
        df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # Handle row selection
    if event.selection.rows:
        selected_idx = event.selection.rows[0]
        selected_entry = history[selected_idx]

        st.markdown("---")
        st.subheader(f"📄 Analysis Details: {selected_entry['file_name']}")

        # Show details in columns
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**📧 User:** {selected_entry.get('user_email', 'N/A')}")
            st.markdown(f"**📅 Date:** {selected_entry['check_timestamp']}")
            st.markdown(f"**🔗 File URL:** [Open]({selected_entry['file_url']})")

        with col2:
            issues_count = len(selected_entry['check_result']) if isinstance(selected_entry['check_result'],
                                                                             list) else 0
            st.markdown(f"**🔍 Issues Found:** {issues_count}")
            st.markdown(f"**📊 Analysis ID:** {selected_entry['id']}")

        # Action buttons
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("📥 Load to Current Session", key=f"load_to_session_{selected_entry['id']}"):
                st.session_state.analysis_result = json.dumps(selected_entry['check_result'])
                st.session_state.current_url = selected_entry['file_url']
                st.success(f"✅ Loaded analysis for {selected_entry['file_name']}")
                st.rerun()

        with col2:
            # Download as CSV
            try:
                csv_data = convert_to_csv(json.dumps(selected_entry['check_result']))
                st.download_button(
                    "📊 Download CSV",
                    data=csv_data,
                    file_name=f"analysis_{selected_entry['id']}.csv",
                    mime="text/csv",
                    key=f"download_csv_{selected_entry['id']}"
                )
            except Exception as e:
                st.error(f"Error preparing CSV: {str(e)}")

        with col3:
            # Download as JSON
            try:
                json_data = convert_to_json(json.dumps(selected_entry['check_result']))
                st.download_button(
                    "📄 Download JSON",
                    data=json_data,
                    file_name=f"analysis_{selected_entry['id']}.json",
                    mime="application/json",
                    key=f"download_json_{selected_entry['id']}"
                )
            except Exception as e:
                st.error(f"Error preparing JSON: {str(e)}")

        with col4:
            if st.button("🗑️ Delete Entry", key=f"delete_{selected_entry['id']}"):
                if db.delete_analysis_entry(selected_entry['id']):
                    st.success("Entry deleted successfully")
                    st.rerun()
                else:
                    st.error("Failed to delete entry")

        # Show the actual analysis results
        st.markdown("---")
        st.subheader("📋 Analysis Results")

        with st.expander("View Analysis Results", expanded=False):
            if isinstance(selected_entry['check_result'], list):
                result_df = pd.DataFrame(selected_entry['check_result'])
                st.dataframe(result_df, use_container_width=True)
            else:
                st.json(selected_entry['check_result'])


def render_database_management(user_email: Optional[str] = None):
    """Render simplified database management section"""
    st.subheader("🛠️ Database Management")

    db = DatabaseManager()
    
    # Get database stats
    stats = db.get_database_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Analyses", stats['total_entries'])
        st.metric("Database Size", f"{stats['db_size_mb']} MB")
    with col2:
        st.metric("Unique Users", stats['unique_users'])
        st.metric("Recent (24h)", stats['recent_entries_24h'])

    # Simple clear actions
    st.warning("⚠️ **Warning:** Clear actions cannot be undone!")
    
    if user_email and user_email != "local_user":
        if st.button(f"🗑️ Clear My History", key="clear_user_history"):
            if db.clear_user_history(user_email):
                st.success("Your history has been cleared")
                st.rerun()
            else:
                st.error("Failed to clear history")


def render_simple_analysis_history(user_email: Optional[str] = None):
    """Render simplified analysis history component for main page"""
    # Add custom CSS for compact button styling
    st.markdown("""
    <style>
    .stButton > button, .stDownloadButton > button {
        height: 32px !important;
        min-height: 32px !important;
        padding: 4px 12px !important;
        font-size: 13px !important;
        border-radius: 4px !important;
        border: 1px solid #ddd !important;
        background-color: #ffffff !important;
        color: #333 !important;
        font-weight: 400 !important;
        line-height: 1.2 !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #f8f9fa !important;
        border-color: #999 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with st.expander("📚 Analysis History", expanded=False):
        if not user_email:
            st.info("No user email available")
            return
            
        db = DatabaseManager()
        
        # Get recent history
        recent_history = db.get_user_analysis_history(user_email, limit=10)
        
        if not recent_history:
            st.info("No analysis history found")
            return
            
        # Create simple table
        table_data = []
        for entry in recent_history:
            table_data.append({
                "File": entry['file_name'][:30] + ('...' if len(entry['file_name']) > 30 else ''),
                "Date": entry['check_timestamp'][:16],  # Remove seconds
                "User": entry.get('user_email', 'N/A')[:20] + ('...' if len(entry.get('user_email', '')) > 20 else ''),
                "Issues": len(entry['check_result']) if isinstance(entry['check_result'], list) else 'N/A'
            })
        
        # Display as DataFrame
        df = pd.DataFrame(table_data)
        
        # Show table with selection
        event = st.dataframe(
            df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True
        )
        
        # Handle selection for download
        if event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_entry = recent_history[selected_idx]
            
            st.markdown("---")
            st.markdown("**Actions for selected entry:**")
            
            # Create uniform button layout
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # Download as CSV
                try:
                    csv_data = convert_to_csv(json.dumps(selected_entry['check_result']))
                    st.download_button(
                        "📊 CSV",
                        data=csv_data,
                        file_name=f"analysis_{selected_entry['id']}.csv",
                        mime="text/csv",
                        key=f"simple_download_csv_{selected_entry['id']}",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"CSV Error: {str(e)}")
            
            with col2:
                # Download as JSON
                try:
                    json_data = convert_to_json(json.dumps(selected_entry['check_result']))
                    st.download_button(
                        "📄 JSON",
                        data=json_data,
                        file_name=f"analysis_{selected_entry['id']}.json",
                        mime="application/json",
                        key=f"simple_download_json_{selected_entry['id']}",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"JSON Error: {str(e)}")
            
            with col3:
                if st.button("📥 Load", key=f"simple_load_{selected_entry['id']}", use_container_width=True):
                    st.session_state.analysis_result = json.dumps(selected_entry['check_result'])
                    st.session_state.current_url = selected_entry['file_url']
                    st.success(f"✅ Loaded: {selected_entry['file_name']}")
                    st.rerun()
            
            with col4:
                if st.button("🗑️ Delete", 
                           key=f"simple_delete_{selected_entry['id']}", 
                           use_container_width=True):
                    if db.delete_analysis_entry(selected_entry['id']):
                        st.success("✅ Entry deleted")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete")


def save_current_analysis_to_db(file_url: str, file_name: str, user_email: str, analysis_result):
    """Save current analysis result to database"""
    if not analysis_result:
        return False

    try:
        # Handle both string and dict formats
        if isinstance(analysis_result, str):
            parsed_result = json.loads(analysis_result)
        else:
            parsed_result = analysis_result

        # Save to database
        db = DatabaseManager()
        success = db.save_analysis_result(file_url, file_name, user_email, parsed_result)

        if success:
            st.success("✅ Analysis saved to history")
        else:
            st.error("❌ Failed to save analysis")

        return success
    except json.JSONDecodeError:
        st.error("❌ Cannot save: Invalid analysis result format")
        return False
    except Exception as e:
        st.error(f"❌ Error saving analysis: {str(e)}")
        return False
