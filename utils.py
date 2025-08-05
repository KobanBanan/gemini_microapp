import difflib
import html


def validate_page_numbers(parsed_result, max_pages=None):
    """Validate page numbers in analysis results"""
    validation_issues = []

    for idx, item in enumerate(parsed_result):
        page = item.get('page')
        if page is None:
            validation_issues.append(f"Issue #{idx + 1}: Missing page number")
        elif not isinstance(page, int) or page <= 0:
            validation_issues.append(f"Issue #{idx + 1}: Invalid page number '{page}'")
        elif max_pages and page > max_pages:
            validation_issues.append(f"Issue #{idx + 1}: Page {page} exceeds document length ({max_pages} pages)")

    return validation_issues


def get_navigation_info(upload_mode, doc_url, page_number, original_text):
    """Generate navigation information based on document source"""
    if upload_mode == "google_drive" and doc_url:
        # Create Google Docs page link
        if 'docs.google.com' in doc_url:
            base_url = doc_url.split('#')[0]  # Remove any existing fragments
            page_link = f"{base_url}#bookmark=page.page{page_number}"
            return {
                "type": "link",
                "url": page_link,
                "text": f"🔗 Open Page {page_number} in Google Docs"
            }
        else:
            # Google Drive file but not Google Docs
            return {
                "type": "link",
                "url": doc_url,
                "text": f"🔗 Open Document (Page {page_number})"
            }
    else:
        # Local file - show search instruction
        search_text = original_text[:50] + "..." if len(original_text) > 50 else original_text
        return {
            "type": "search",
            "instruction": f"🔍 Search in your document: '{search_text}'",
            "page_info": f"Located on Page {page_number}"
        }


def extract_context_around_text(document_content, target_text, context_chars=200):
    """Extract context around target text from document"""
    if not document_content or not target_text:
        return target_text

    # Find the target text in document
    target_lower = target_text.lower().strip()
    doc_lower = document_content.lower()

    index = doc_lower.find(target_lower)
    if index == -1:
        # Try to find partial match
        words = target_lower.split()[:3]  # First 3 words
        if words:
            search_phrase = " ".join(words)
            index = doc_lower.find(search_phrase)

    if index == -1:
        return target_text

    # Extract context
    start = max(0, index - context_chars)
    end = min(len(document_content), index + len(target_text) + context_chars)

    context = document_content[start:end]

    # Add ellipsis if truncated
    if start > 0:
        context = "..." + context
    if end < len(document_content):
        context = context + "..."

    return context


def highlight_differences(original, suggestion):
    """Highlight differences between original and suggested text"""
    differ = difflib.SequenceMatcher(None, original, suggestion)
    original_highlighted = ""
    suggestion_highlighted = ""

    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == 'equal':
            original_highlighted += html.escape(original[i1:i2])
            suggestion_highlighted += html.escape(suggestion[j1:j2])
        elif tag == 'delete':
            original_highlighted += f'<span style="background-color: #ffcccc; text-decoration: line-through;">{html.escape(original[i1:i2])}</span>'
        elif tag == 'insert':
            suggestion_highlighted += f'<span style="background-color: #ccffcc; font-weight: bold;">{html.escape(suggestion[j1:j2])}</span>'
        elif tag == 'replace':
            original_highlighted += f'<span style="background-color: #ffcccc; text-decoration: line-through;">{html.escape(original[i1:i2])}</span>'
            suggestion_highlighted += f'<span style="background-color: #ccffcc; font-weight: bold;">{html.escape(suggestion[j1:j2])}</span>'

    return original_highlighted, suggestion_highlighted


def build_system_prompt_with_knowledge(base_prompt, use_o1_knowledge, use_eb1_knowledge, o1_content, eb1_content):
    """Build system prompt with optional knowledge sections"""
    prompt = base_prompt

    knowledge_sections = []
    if use_o1_knowledge:
        knowledge_sections.append("O-1 visa requirements")
    if use_eb1_knowledge:
        knowledge_sections.append("EB-1 visa requirements")

    if knowledge_sections:
        knowledge_instruction = f"\n\nIMPORTANT: When analyzing documents, pay special attention to {' and '.join(knowledge_sections)}. Use the following legal knowledge as reference:\n\n"
        prompt += knowledge_instruction

        if use_o1_knowledge:
            prompt += "=== O-1 VISA REQUIREMENTS ===\n"
            prompt += o1_content + "\n\n"

        if use_eb1_knowledge:
            prompt += "=== EB-1 VISA REQUIREMENTS ===\n"
            prompt += eb1_content + "\n\n"

    return prompt