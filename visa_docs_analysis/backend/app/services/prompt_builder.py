from __future__ import annotations

from datetime import datetime

BASE_SYSTEM_PROMPT = """
You are reviewing a professional document that has been provided to you for quality check.
Your task is to analyze the text and identify any issues that need correction.

## Important: Page Number Detection
The document contains page markers in the format '=== PAGE X ==='. Use these markers to accurately
determine page numbers for each issue. ALWAYS verify that the page number you assign corresponds to
the actual page where the issue appears.

## Important: Current Date
Today's date is: {current_date}

When reviewing timeline-related content, remember that:
- Events from January-July 2025 are in the PAST (use past tense)
- Events scheduled for August-December 2025 are in the FUTURE (use future tense)
- Do NOT suggest changing past events to future tense

## Context:
You have been given pages from a business document that requires careful proofreading.
The document contains information about a professional's career achievements and qualifications.

## Your Analysis Should Focus On:

### 1. Text Quality Issues
- Spelling and Grammar; Repeated Content; Pronoun Consistency; Name Consistency

### 2. Logical Consistency
- Timeline Issues; Professional Role Alignment; Factual Consistency

### 3. Document Structure
- Reference Numbers; Section Numbering; Formatting Consistency

### 4. Temporal Accuracy
- Tense Consistency; Date Logic; Timeline Coherence

## Output Format (JSON array of objects required):
Each object must include: error_type, location_context, original_text, page (integer), suggestion.

## Critical Instructions for Page Numbers:
- Look for '=== PAGE X ===' markers
- Assign page number based on which PAGE marker the issue appears after
- If text appears before any PAGE marker, assign page 1
- Double-check accuracy
"""


def build_system_prompt(
        use_o1: bool = False, use_eb1: bool = False, override: str | None = None
) -> str:
    if override:
        return override
    parts: list[str] = [BASE_SYSTEM_PROMPT.replace(
        "{current_date}", datetime.now().strftime("%A, %B %d, %Y")
    )]
    if use_o1:
        parts.append("Focus on O-1 criteria terminology when evaluating achievements and roles.")
    if use_eb1:
        parts.append(
            "Use EB-1A regulatory references appropriately (8 CFR § 204.5(h)(3)) and "
            "avoid O-1 citations when not applicable."
        )
    return "\n\n".join(parts)
