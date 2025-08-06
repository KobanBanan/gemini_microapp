import json
import logging
import re

import pandas as pd
import requests
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from docs.document_processor import DocumentProcessor
from prompt import get_gemini_prompt_config, get_gemini_config


def extract_google_doc_id(url):
    """Extract document ID from Google Docs URL"""
    pattern = r'/document/d/([a-zA-Z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


def parse_table_of_contents(text_content):
    """Extract page mappings from Table of Contents"""
    import re
    import logging
    
    # Find Table of Contents section
    toc_pattern = r'TABLE OF CONTENTS.*?(?=\n\n|\Z)'
    toc_match = re.search(toc_pattern, text_content, re.IGNORECASE | re.DOTALL)
    
    if not toc_match:
        logging.info("No Table of Contents found in document")
        return {}
    
    toc_text = toc_match.group(0)
    logging.info(f"Found Table of Contents with {len(toc_text)} characters")
    
    # Parse entries: "Section Title ... Page Number"
    # Pattern: text followed by dots/spaces and a number at the end of line
    page_mappings = {}
    lines = toc_text.split('\n')
    
    for line in lines:
        # Look for pattern: "Text ... Number" or "Text Number" at end of line
        match = re.search(r'^(.+?)[\s\.]{2,}(\d+)\s*$', line.strip())
        if match:
            section_title = match.group(1).strip()
            page_num = int(match.group(2))
            page_mappings[section_title.lower()] = page_num
            logging.info(f"TOC mapping: '{section_title}' -> page {page_num}")
            
    logging.info(f"Extracted {len(page_mappings)} page mappings from TOC")
    return page_mappings


def add_page_markers_to_text(text_content):
    """Add page markers to text content using Table of Contents if available"""
    import re
    
    # Try to get precise page mappings from Table of Contents
    page_mappings = parse_table_of_contents(text_content)
    
    lines = text_content.split('\n')
    result_lines = []
    current_page = 1
    
    # Add initial page marker
    result_lines.append(f"=== PAGE {current_page} ===")
    
    for line in lines:
        # Check if this line matches a section from TOC
        line_lower = line.strip().lower()
        
        for section_title, page_num in page_mappings.items():
            # Check if line contains the section title
            if section_title in line_lower and len(line.strip()) > 10:
                # Found a section header - update page number
                if page_num != current_page:
                    current_page = page_num
                    result_lines.append(f"\n=== PAGE {current_page} ===")
                break
        else:
            # No TOC match found, use word count fallback
            if not page_mappings:  # Only use fallback if no TOC found
                line_words = len(line.split())
                if hasattr(add_page_markers_to_text, '_current_word_count'):
                    add_page_markers_to_text._current_word_count += line_words
                else:
                    add_page_markers_to_text._current_word_count = line_words
                
                # Add page break if exceeded word count (fallback method)
                if add_page_markers_to_text._current_word_count > 500 and line.strip():
                    current_page += 1
                    result_lines.append(f"\n=== PAGE {current_page} ===")
                    add_page_markers_to_text._current_word_count = line_words
        
        result_lines.append(line)
    
    return '\n'.join(result_lines)


def fetch_doc_content(doc_url, oauth_manager=None, status_callback=None):
    """Fetch Google document content with optional OAuth authentication"""
    doc_id = extract_google_doc_id(doc_url)
    
    if not doc_id:
        logging.error("Cannot extract document ID from URL")
        raise ValueError("Cannot extract document ID from URL")

    # Try OAuth authentication first if available
    if oauth_manager and oauth_manager.is_authenticated():
        try:
            if status_callback:
                status_callback("Trying authenticated access...")
            content = oauth_manager.fetch_authenticated_doc_content(doc_url)
            # Add page markers to OAuth content
            return add_page_markers_to_text(content)
        except Exception as oauth_error:
            logging.error(f"OAuth access failed: {str(oauth_error)}")
            if status_callback:
                status_callback("OAuth failed, trying public access...")
            # Fall back to public access if OAuth fails
            pass

    # Try public export in different formats
    export_formats = [
        f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
        f"https://docs.google.com/document/d/{doc_id}/export?format=docx",
        f"https://docs.google.com/document/u/0/d/{doc_id}/export?format=txt"
    ]

    for i, export_url in enumerate(export_formats):
        try:
            if status_callback:
                status_callback(f"Trying export format {i+1}/{len(export_formats)}...")
            response = requests.get(export_url, timeout=30)
            
            if response.status_code == 200:
                if 'txt' in export_url:
                    # Add page markers to text content
                    return add_page_markers_to_text(response.text)
                else:
                    # For docx return binary content (will be processed by DocumentProcessor)
                    return response.content
        except Exception:
            continue

    error_msg = "Could not fetch document content. Make sure the document is publicly accessible or authenticate with Google."
    logging.error(error_msg)
    raise Exception(error_msg)


def _create_retry_callback(status_callback, call_type):
    """Create retry callback that updates UI"""
    def retry_callback(retry_state):
        sleep_time = retry_state.next_action.sleep
        attempt = retry_state.attempt_number
        message = f"API attempt {attempt} failed, retrying {call_type} in {sleep_time} seconds..."
        logging.info(message)
        if status_callback:
            status_callback(message)
    return retry_callback


def _call_gemini_streaming(client, model, contents, config, status_callback=None):
    """Call Gemini API with streaming using tenacity retry"""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=_create_retry_callback(status_callback, "streaming API call")
    )
    def _do_streaming_call():
        logging.info("Attempting streaming API call")
        if status_callback:
            status_callback("Calling Gemini API (streaming)...")
        
        result = ""
        for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
        ):
            if chunk.text:
                result += chunk.text
        
        return result
    
    return _do_streaming_call()


def _call_gemini_non_streaming(client, model, contents, config, status_callback=None):
    """Call Gemini API without streaming using tenacity retry"""
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=_create_retry_callback(status_callback, "non-streaming API call")
    )
    def _do_non_streaming_call():
        logging.info("Attempting non-streaming API call")
        if status_callback:
            status_callback("Calling Gemini API (non-streaming)...")
        
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        
        # Handle different response formats
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            return response.candidates[0].content.parts[0].text
        else:
            return str(response)
    
    return _do_non_streaming_call()


def call_gemini_api(doc_content, api_key, system_prompt=None, status_callback=None):
    """Call Gemini API for document analysis using custom or default system prompt"""
    
    # Check for None values that could cause concatenation errors
    if doc_content is None:
        logging.error("doc_content is None - this will cause string concatenation errors")
        raise ValueError("Document content cannot be None")
    
    if api_key is None:
        logging.error("api_key is None")
        raise ValueError("API key cannot be None")
    
    # Check if document is too large and split if necessary
    max_content_length = 800000  # ~800k characters limit
    if len(doc_content) > max_content_length:
        logging.info(f"Document is large ({len(doc_content)} chars), splitting into chunks")
        if status_callback:
            status_callback("Document is large, processing in chunks...")
        return _process_large_document(doc_content, api_key, system_prompt, max_content_length, status_callback)
    
    # Prepare client and configs
    client = genai.Client(api_key=api_key)
    prompt_config = get_gemini_prompt_config(doc_content)
    generation_config = get_gemini_config(system_prompt)
    contents = prompt_config["contents"]
    model = prompt_config["model"]
    
    # Try streaming first, then fallback to non-streaming
    try:
        return _call_gemini_streaming(client, model, contents, generation_config, status_callback)
    except Exception as streaming_error:
        error_msg = str(streaming_error)
        if any(keyword in error_msg.lower() for keyword in ["disconnected", "timeout", "connection", "remote"]):
            logging.error(f"Streaming failed: {error_msg}")
            logging.info("Falling back to non-streaming approach...")
            if status_callback:
                status_callback("Streaming failed, trying non-streaming approach...")
            try:
                return _call_gemini_non_streaming(client, model, contents, generation_config, status_callback)
            except Exception as final_error:
                logging.error(f"All API approaches failed. Final error: {str(final_error)}")
                import traceback
                logging.error(f"Traceback: {traceback.format_exc()}")
                # Create more user-friendly error for Gemini API failures
                if "RetryError" in str(final_error) or "RemoteProtocolError" in str(final_error):
                    raise Exception("Gemini API connection failed after 5 retry attempts (3 streaming + 2 non-streaming)")
                raise final_error
        else:
            logging.error(f"Non-network error in streaming: {error_msg}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            # Create more user-friendly error for streaming RetryError
            if "RetryError" in str(streaming_error):
                raise Exception("Gemini API connection failed after 3 streaming retry attempts")
            raise streaming_error


def _process_large_document(doc_content, api_key, system_prompt, max_length, status_callback=None):
    """Process large document by splitting it into chunks"""
    
    # Split document into chunks
    chunk_size = max_length - 10000  # Leave room for prompt
    chunks = []
    
    for i in range(0, len(doc_content), chunk_size):
        chunk = doc_content[i:i + chunk_size]
        chunks.append(chunk)
    
    logging.info(f"Split document into {len(chunks)} chunks")
    if status_callback:
        status_callback(f"Split document into {len(chunks)} chunks")
    
    all_results = []
    
    for i, chunk in enumerate(chunks):
        try:
            logging.info(f"Processing chunk {i+1}/{len(chunks)}")
            if status_callback:
                status_callback(f"Processing chunk {i+1}/{len(chunks)}...")
            
            # Modify system prompt to indicate this is a chunk
            chunk_prompt = system_prompt + f"\n\nNote: This is part {i+1} of {len(chunks)} of a larger document."
            
            # Process each chunk with the regular function (but force single attempt)
            result = _call_gemini_single_chunk(chunk, api_key, chunk_prompt, status_callback)
            
            if result:
                try:
                    # Parse JSON result
                    chunk_results = json.loads(result)
                    if isinstance(chunk_results, list):
                        all_results.extend(chunk_results)
                    else:
                        all_results.append(chunk_results)
                except json.JSONDecodeError:
                    logging.error(f"Failed to parse chunk {i+1} results as JSON")
                    
        except Exception as e:
            logging.error(f"Failed to process chunk {i+1}: {str(e)}")
            if status_callback:
                status_callback(f"Warning: chunk {i+1} failed, continuing...")
            continue
    
    # Return combined results as JSON
    return json.dumps(all_results, ensure_ascii=False, indent=2)


def _call_gemini_single_chunk(doc_content, api_key, system_prompt, status_callback=None):
    """Call Gemini API for a single chunk with tenacity retry"""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=_create_retry_callback(status_callback, "chunk processing")
    )
    def _do_chunk_call():
        client = genai.Client(api_key=api_key)
        
        prompt_config = get_gemini_prompt_config(doc_content)
        generation_config = get_gemini_config(system_prompt)
        contents = prompt_config["contents"]
        
        # Use non-streaming for chunks (more reliable)
        response = client.models.generate_content(
            model=prompt_config["model"],
            contents=contents,
            config=generation_config,
        )
        
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            return response.candidates[0].content.parts[0].text
        else:
            return str(response)
    
    return _do_chunk_call()


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


def process_uploaded_file(uploaded_file, status_callback=None):
    """Process uploaded file"""
    if uploaded_file is None:
        logging.error("uploaded_file is None")
        raise ValueError("Uploaded file cannot be None")
    
    try:
        if status_callback:
            status_callback(f"Processing {uploaded_file.name}...")
        processor = DocumentProcessor()
        result = processor.process_uploaded_file(uploaded_file)
        return result
    except Exception as e:
        logging.error(f"Error processing uploaded file: {str(e)}")
        raise


def process_google_drive_file(url_or_id, oauth_manager=None, status_callback=None):
    """Process file from Google Drive using OAuth2 credentials"""
    if url_or_id is None:
        logging.error("url_or_id is None")
        raise ValueError("URL or ID cannot be None")
    
    try:
        if status_callback:
            status_callback("Preparing Google Drive access...")
        credentials = None
        if oauth_manager and oauth_manager.is_authenticated():
            credentials = oauth_manager.get_credentials()

        processor = DocumentProcessor(oauth_credentials=credentials)
        result = processor.process_google_drive_url(url_or_id)
        return result
    except Exception as e:
        logging.error(f"Error processing Google Drive file: {str(e)}")
        raise


def get_document_content(source_type, source_data, oauth_manager=None, status_callback=None):
    """Get document content from various sources"""
    try:
        if source_type == "google_docs":
            if status_callback:
                status_callback("Accessing Google Docs...")
            return fetch_doc_content(source_data, oauth_manager, status_callback)
        elif source_type == "google_drive":
            if status_callback:
                status_callback("Accessing Google Drive...")
            # Try public access first, then authenticated if needed
            try:
                return fetch_doc_content(source_data, oauth_manager, status_callback)
            except Exception:
                if status_callback:
                    status_callback("Trying authenticated Google Drive access...")
                return process_google_drive_file(source_data, oauth_manager, status_callback)
        elif source_type == "uploaded_file":
            if status_callback:
                status_callback("Processing uploaded file...")
            return process_uploaded_file(source_data, status_callback)
        else:
            error_msg = f"Unsupported source type: {source_type}"
            logging.error(error_msg)
            raise ValueError(error_msg)
    except Exception as e:
        logging.error(f"Error in get_document_content: {str(e)}")
        raise
