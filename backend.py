import json
import re

import pandas as pd
import requests
from google import genai

from docs.document_processor import DocumentProcessor
from prompt import get_gemini_prompt_config, get_gemini_config


def extract_google_doc_id(url):
    """Extract document ID from Google Docs URL"""
    pattern = r'/document/d/([a-zA-Z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def fetch_doc_content(doc_url, oauth_manager=None):
    """Fetch Google document content with optional OAuth authentication"""
    doc_id = extract_google_doc_id(doc_url)
    if not doc_id:
        raise ValueError("Cannot extract document ID from URL")

    # Try OAuth authentication first if available
    if oauth_manager and oauth_manager.is_authenticated():
        try:
            return oauth_manager.fetch_authenticated_doc_content(doc_url)
        except Exception as oauth_error:
            # Fall back to public access if OAuth fails
            pass

    # Try public export in different formats
    export_formats = [
        f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
        f"https://docs.google.com/document/d/{doc_id}/export?format=docx",
        f"https://docs.google.com/document/u/0/d/{doc_id}/export?format=txt"
    ]

    for export_url in export_formats:
        try:
            response = requests.get(export_url, timeout=30)
            if response.status_code == 200:
                if 'txt' in export_url:
                    return response.text
                else:
                    # For docx return binary content
                    return response.content
        except:
            continue

    raise Exception(
        "Could not fetch document content. Make sure the document is publicly accessible or authenticate with Google.")


def call_gemini_api(doc_content, api_key, system_prompt=None):
    """Call Gemini API for document analysis using custom or default system prompt"""
    client = genai.Client(api_key=api_key)

    # Get prompt configuration with document content
    prompt_config = get_gemini_prompt_config(doc_content)
    generation_config = get_gemini_config(system_prompt)

    # Use the configured contents
    contents = prompt_config["contents"]

    result = ""
    for chunk in client.models.generate_content_stream(
            model=prompt_config["model"],
            contents=contents,
            config=generation_config,
    ):
        result += chunk.text

    return result


def convert_to_csv(json_data):
    """Convert JSON response to CSV with enhanced formatting"""
    try:
        data = json.loads(json_data)
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)

            # Reorder columns for better readability
            preferred_order = ['error_type', 'page', 'location_context', 'original_text', 'suggestion']
            columns = [col for col in preferred_order if col in df.columns] + [col for col in df.columns if
                                                                               col not in preferred_order]
            df = df[columns]

            # Format column names
            df.columns = [
                col.replace('_', ' ').title()
                for col in df.columns
            ]

            return df.to_csv(index=False, encoding='utf-8-sig')
        else:
            return "No data to export"
    except Exception as e:
        raise Exception(f"Error converting to CSV: {str(e)}")


def convert_to_json(json_data):
    """Format JSON response with metadata"""
    try:
        data = json.loads(json_data)

        # Add metadata
        formatted_data = {
            "metadata": {
                "total_issues": len(data) if isinstance(data, list) else 1,
                "export_timestamp": pd.Timestamp.now().isoformat(),
                "summary": {
                    "error_types": {},
                    "pages_with_issues": set()
                }
            },
            "issues": data
        }

        # Calculate summary statistics
        if isinstance(data, list):
            for item in data:
                error_type = item.get('error_type', 'Unknown')
                page = item.get('page')

                # Count error types
                if error_type in formatted_data["metadata"]["summary"]["error_types"]:
                    formatted_data["metadata"]["summary"]["error_types"][error_type] += 1
                else:
                    formatted_data["metadata"]["summary"]["error_types"][error_type] = 1

                # Track pages with issues
                if page:
                    formatted_data["metadata"]["summary"]["pages_with_issues"].add(page)

        # Convert set to sorted list for JSON serialization
        pages_with_issues = sorted(list(formatted_data["metadata"]["summary"]["pages_with_issues"]))
        formatted_data["metadata"]["summary"]["pages_with_issues"] = pages_with_issues

        return json.dumps(formatted_data, indent=2, ensure_ascii=False)
    except Exception as e:
        raise Exception(f"Error formatting JSON: {str(e)}")


def process_uploaded_file(uploaded_file):
    """Process uploaded file"""
    processor = DocumentProcessor()
    return processor.process_uploaded_file(uploaded_file)


def process_google_drive_file(url_or_id, oauth_manager=None):
    """Process file from Google Drive using OAuth2 credentials"""
    credentials = None
    if oauth_manager and oauth_manager.is_authenticated():
        credentials = oauth_manager.get_credentials()

    processor = DocumentProcessor(oauth_credentials=credentials)
    return processor.process_google_drive_url(url_or_id)


def get_document_content(source_type, source_data, oauth_manager=None):
    """Get document content from various sources"""
    if source_type == "google_docs":
        # Use existing logic for Google Docs
        return fetch_doc_content(source_data, oauth_manager)
    elif source_type == "google_drive":
        # Try public access first, then authenticated if needed
        try:
            # First try the public access method which works for Google Docs
            return fetch_doc_content(source_data, oauth_manager)
        except Exception as public_error:
            # If public access fails, try authenticated Google Drive API
            return process_google_drive_file(source_data, oauth_manager)
    elif source_type == "uploaded_file":
        # Process uploaded file
        return process_uploaded_file(source_data)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
