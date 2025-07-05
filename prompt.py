from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are reviewing a professional document that has been provided to you for quality check. 
Your task is to analyze the text and identify any issues that need correction.
## Context:
You have been given pages from a business document that requires careful proofreading. 
The document contains information about a professional's career achievements and qualifications.

## Your Analysis Should Focus On:

### 1. Text Quality Issues
- **Spelling and Grammar**: Look for any typos, grammatical errors, or punctuation mistakes
- **Repeated Content**: Identify any sentences or paragraphs that appear multiple times
- **Pronoun Consistency**: Check if pronouns (he/she/they) are used consistently for each person mentioned
- **Name Consistency**: Verify that people's names are spelled the same way throughout

### 2. Logical Consistency
- **Timeline Issues**: Check if dates and timeframes make logical sense
- **Professional Role Alignment**: Ensure job descriptions match the stated professional field
- **Factual Consistency**: Verify that facts about companies, positions, and achievements align throughout

### 3. Document Structure
- **Reference Numbers**: Check if numbered references (like "Exhibit 3") are consistent
- **Section Numbering**: Verify that section numbers match their references
- **Formatting Consistency**: Note any major formatting inconsistencies

## Output Format:

For each issue found, provide a JSON object with the following structure:

{
  "error_type": "[type of error]",
  "location_context": "[section/paragraph description where error is found]",
  "original_text": "[exact problematic text]",
  "page": [page number],
  "suggestion": "[suggested fix]"
}


----- Few Shot Examples -----

### Example 1: Grammar Error
**Output**:
{
  "error_type": "Grammar",
  "location_context": "Memorandum in Support of EB-1A Classification, first paragraph.",
  "original_text": "major brand such as Porsche and Henkel",
  "page": 33,
  "suggestion": "major brands such as Porsche and Henkel"
}

### Example 2: Pronoun Inconsistency
**Output**:
{
  "error_type": "Inconsistency",
  "location_context": "Memorandum in Support of EB-1A Classification, second paragraph.",
  "original_text": "Throughout his career, she has played a critical role",
  "page": 33,
  "suggestion": "Throughout her career, she has played a critical role"
}

### Example 3: Punctuation Error
**Output**:
{
  "error_type": "Punctuation",
  "location_context": "Memorandum in Support of EB-1A Classification, bullet point list.",
  "original_text": "from 900.000 to over 3 million daily active users",
  "page": 33,
  "suggestion": "from 900,000 to over 3 million daily active users"
}

### Example 4: Spelling Error
**Output**:
{
  "error_type": "Typo",
  "location_context": "Memorandum in Support of EB-1A Classification, paragraph on professional discourse.",
  "original_text": "Ms. Khmelniskaia is also an active contributor",
  "page": 33,
  "suggestion": "Ms. Khmelnitskaia is also an active contributor"
}

### Example 5: Factual Error
**Output**:
{
  "error_type": "Factual Error",
  "location_context": "List of regulatory criteria.",
  "original_text": "The beneficiary has been employed in a critical or essential capacity for organizations and establishments that have a distinguished reputation (See 8 CFR 214.2(o)(3)(iii)(B)(7));",
  "page": 34,
  "suggestion": "The citation 8 CFR 214.2(o)(3)(iii)(B)(7) refers to O-1 visas, not EB-1. The list contains multiple incorrect O-1 citations and should be revised to use the correct EB-1 citations from 8 CFR § 204.5(h)(3)."
}

### Example 6: Redundancy
**Output**:
{
  "error_type": "Redundancy",
  "location_context": "List of regulatory criteria.",
  "original_text": "2. The beneficiary has been employed in a critical or essential capacity for organizations and establishments that have a distinguished reputation... 7. The person has performed in a leading or critical role for organizations or establishments that have a distinguished reputation",
  "page": 34,
  "suggestion": "Criteria 2 and 7 describe the same 'leading or critical role' requirement. The list should be consolidated to remove the duplicate entry."
}

### Example 7: Timeline Inconsistency
**Output**:
{
  "error_type": "Inconsistency",
  "location_context": "Section 8. Evidence That the Person Has Performed in a Leading or Critical Role for Organizations or Establishments That Have a Distinguished Reputation.",
  "original_text": "Right now, she is continuing to work on projects in Binomo. ... She has finished her career in Binomo in 2024.",
  "page": 42,
  "suggestion": "These two statements are contradictory. One claims she is currently working with Binomo, while the other states her work there ended in 2024. Please clarify and correct this inconsistency."
}

### Example 8: Name Inconsistency
**Output**:
{
  "error_type": "Factual Error",
  "location_context": "Section 9. Final Merits Determination.",
  "original_text": "In addition, Ms. Ivanova is a member of the Guild of Marketers",
  "page": 46,
  "suggestion": "The petitioner's name is Khmelnitskaia, not Ivanova. Please correct the name."
}

### Example 9: Formatting Error
**Output**:
{
  "error_type": "Formatting",
  "location_context": "Index Of Exhibits.",
  "original_text": "Exhibit 3 ... Evidence of the Person's Membership... Exhibit 3 ... Evidence of Published Material About the Person...",
  "page": 48,
  "suggestion": "There are two 'Exhibit 3' entries. The second one should be renumbered to 'Exhibit 4', and all subsequent exhibit numbers in the index should be adjusted accordingly."
}

----- End of Few Shot Examples -----

## Document Analysis:

Please carefully review the provided document pages and identify any issues following the guidelines above. Focus on accuracy and consistency throughout the text."""


def get_gemini_prompt_config(document_content):
    """Returns the Gemini API prompt configuration with document content"""
    return {
        "model": "gemini-2.5-pro",
        "contents": [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"Analyze this document:\n\n{document_content}")
                ],
            ),
        ]
    }


def get_gemini_config(system_prompt=None):
    """Returns the Gemini generation configuration with system prompt"""
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT

    return types.GenerateContentConfig(
        temperature=0.3,
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
        ),
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                required=["error_type", "location_context", "original_text", "suggestion", "page"],
                properties={
                    "error_type": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        description="Type of the error",
                    ),
                    "location_context": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        description="Context of the error location in the document",
                    ),
                    "original_text": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        description="Original text containing the error",
                    ),
                    "suggestion": genai.types.Schema(
                        type=genai.types.Type.STRING,
                        description="Correction suggestion",
                    ),
                    "page": genai.types.Schema(
                        type=genai.types.Type.INTEGER,
                        description="Page number",
                    ),
                },
            ),
        ),
        system_instruction=[
            types.Part.from_text(text=system_prompt),
        ],
    )
