"""Module for displaying analysis results"""
import html
import json
import streamlit as st
import pandas as pd

from .html_styles import FULL_STYLES_AND_SCRIPTS
from utils import (
    validate_page_numbers, 
    get_navigation_info, 
    highlight_differences,
    extract_context_around_text
)
from backend import convert_to_csv, convert_to_json


def display_enhanced_results_table(parsed_result):
    """Display enhanced results table with improved UX"""
    if not isinstance(parsed_result, list) or len(parsed_result) == 0:
        st.warning("No issues found in the document.")
        return

    # Validate page numbers
    validation_issues = validate_page_numbers(parsed_result)
    if validation_issues:
        st.warning("⚠️ Page number validation issues found:")
        for issue in validation_issues:
            st.write(f"• {issue}")
        st.markdown("---")

    st.info(f"📋 Found {len(parsed_result)} issues in the document")

    # Custom CSS for better table display
    st.markdown(FULL_STYLES_AND_SCRIPTS, unsafe_allow_html=True)

    # Display enhanced table
    for idx, item in enumerate(parsed_result):
        anchor_id = f"issue_{idx + 1}"

        original_text = item.get('original_text', '')
        suggestion = item.get('suggestion', '')

        # Highlight differences
        original_highlighted, suggestion_highlighted = highlight_differences(original_text, suggestion)

        # Get navigation info
        nav_info = get_navigation_info(
            st.session_state.upload_mode,
            st.session_state.document_source_url,
            item.get('page', 1),
            original_text
        )

        with st.container():
            st.markdown(f'''
            <div class="issue-row" id="{anchor_id}">
                <div class="issue-header">
                    <div>
                        <span class="issue-type">{html.escape(item.get('error_type', 'Unknown'))}</span>
                        <span class="page-info">📄 Page {item.get('page', 'N/A')}</span>
                        <span style="margin-left: 10px; font-weight: normal;">Issue #{idx + 1}</span>
                    </div>
                </div>
                <div class="location-info">📍 {html.escape(item.get('location_context', ''))}</div>
                <div>
                    <strong>❌ Original Text:</strong>
                    <div class="original-text difference-highlight">{original_highlighted}</div>
                </div>
                <div>
                    <strong>✅ Suggested Fix:</strong>
                    <div class="suggestion-text difference-highlight">{suggestion_highlighted}</div>
                </div>
                <div class="navigation-section">
                    {'<a href="' + nav_info['url'] + '" target="_blank" class="nav-link">' + nav_info['text'] + '</a>' if nav_info.get('url') and nav_info['type'] == 'link' else ('<a href="' + nav_info['url'] + '" target="_blank" class="nav-link">' + nav_info['text'] + '</a><div style="margin-top: 4px;"><span class="search-instruction">' + nav_info['instruction'] + '</span></div>' if nav_info.get('url') and nav_info['type'] == 'search' else '<div class="search-instruction">' + nav_info['instruction'] + '</div><div style="margin-top: 4px; font-size: 0.85em; color: #495057;">' + nav_info['page_info'] + '</div>' if nav_info['type'] == 'search' else '')}
                </div>
            </div>
            ''', unsafe_allow_html=True)

            # Add expandable section for additional details if needed
            with st.expander(f"🔍 Details for Issue #{idx + 1}", expanded=False):
                # Show context for local files
                if nav_info['type'] == 'search' and st.session_state.document_content:
                    st.markdown("**📄 Document Context:**")
                    context = extract_context_around_text(
                        st.session_state.document_content,
                        original_text
                    )
                    st.text_area(
                        "Context around the issue",
                        context,
                        height=120,
                        key=f"context_{idx}",
                        help="This shows the surrounding text from your document"
                    )
                    st.markdown("---")

                col1, col2 = st.columns(2)
                with col1:
                    st.text_area(
                        "Original Text (Raw)",
                        original_text,
                        height=100,
                        key=f"original_{idx}"
                    )
                with col2:
                    st.text_area(
                        "Suggestion (Raw)",
                        suggestion,
                        height=100,
                        key=f"suggestion_{idx}"
                    )


def display_analysis_results(analysis_result):
    """Display complete analysis results with all views and downloads"""
    if not analysis_result:
        return
        
    # Display results
    st.markdown("---")
    st.subheader("📊 Analysis Results")

    # Show enhanced results
    with st.expander("🔍 Detailed Issues Analysis", expanded=True):
        try:
            parsed_result = json.loads(analysis_result)
            display_enhanced_results_table(parsed_result)

            # Also show traditional table view as backup
            with st.expander("📋 Traditional Table View", expanded=False):
                if isinstance(parsed_result, list) and len(parsed_result) > 0:
                    # Convert list of dicts to DataFrame
                    df = pd.DataFrame(parsed_result)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.text_area("Analysis Result", analysis_result, height=300)

        except json.JSONDecodeError:
            st.error("Could not parse analysis results as JSON")
            st.text_area("Raw Analysis Result", analysis_result, height=300)
        except Exception as e:
            st.error(f"Error displaying results: {str(e)}")
            st.text_area("Raw Analysis Result", analysis_result, height=300)

    # Download buttons under results
    _render_download_buttons(analysis_result)


def _render_download_buttons(analysis_result):
    """Render download buttons for CSV and JSON formats"""
    col1, col2 = st.columns(2)

    with col1:
        # Download CSV
        try:
            csv_data = convert_to_csv(analysis_result)
            st.download_button(
                label="📊 Download CSV",
                data=csv_data,
                file_name="analysis_results.csv",
                mime="text/csv",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Error preparing CSV: {str(e)}")

    with col2:
        # Download JSON
        try:
            json_data = convert_to_json(analysis_result)
            st.download_button(
                label="📄 Download JSON",
                data=json_data,
                file_name="analysis_results.json",
                mime="application/json",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Error preparing JSON: {str(e)}")