"""
Output Parser Demo
===================
Parses LLM output into typed Pydantic objects with validation and retry logic.
Shows how to build reliable structured output pipelines.
"""

import os
import json
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def call_llm(prompt: str, system: str = "", json_mode: bool = False) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.0, "max_tokens": 1000}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()


# =============================================================================
# Schema Definitions
# =============================================================================

class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Category(str, Enum):
    bug = "bug"
    feature = "feature"
    improvement = "improvement"
    documentation = "documentation"


class TicketV1(BaseModel):
    """V1 schema: basic ticket."""
    title: str = Field(description="Short title")
    category: Category
    severity: Severity
    description: str = Field(description="Detailed description")


class TicketV2(BaseModel):
    """V2 schema: extended with new fields (backward compatible)."""
    title: str = Field(description="Short title")
    category: Category
    severity: Severity
    description: str = Field(description="Detailed description")
    # New fields with defaults (backward compatible)
    affected_component: Optional[str] = Field(default=None, description="Which component is affected")
    estimated_hours: Optional[float] = Field(default=None, description="Estimated fix time")
    tags: list[str] = Field(default_factory=list, description="Relevant tags")


class SentimentResult(BaseModel):
    """Sentiment analysis output."""
    sentiment: str = Field(description="positive, negative, or neutral")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0-1")
    reasoning: str = Field(description="Why this sentiment was chosen")
    key_phrases: list[str] = Field(description="Phrases that indicate sentiment")


class MeetingAction(BaseModel):
    """Single action item from meeting notes."""
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    priority: Severity = Severity.medium


class MeetingMinutes(BaseModel):
    """Parsed meeting minutes."""
    title: str
    date: Optional[str] = None
    attendees: list[str]
    summary: str
    action_items: list[MeetingAction]
    decisions: list[str]


# =============================================================================
# Parser with Retry Logic
# =============================================================================

def parse_output(raw: str, schema: type[BaseModel]) -> BaseModel:
    """Parse LLM output into a Pydantic model with cleaning."""
    cleaned = raw.strip()

    # Remove common LLM artifacts
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return schema.model_validate(data)


def parse_with_retry(
    prompt: str,
    schema: type[BaseModel],
    max_retries: int = 2,
    system: str = "",
) -> tuple[BaseModel, int]:
    """Parse with automatic retry on failure. Returns (result, attempts)."""
    attempts = 0

    for attempt in range(max_retries + 1):
        attempts += 1

        if attempt == 0:
            raw = call_llm(prompt, system=system, json_mode=True)
        else:
            # Retry with error context
            fix_prompt = (
                f"Your previous JSON output had an error: {last_error}\n\n"
                f"Please fix and return valid JSON matching this schema:\n"
                f"{json.dumps(schema.model_json_schema(), indent=2)}\n\n"
                f"Original request: {prompt}"
            )
            raw = call_llm(fix_prompt, system=system, json_mode=True)

        try:
            result = parse_output(raw, schema)
            return result, attempts
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            if attempt == max_retries:
                raise ValueError(f"Failed after {attempts} attempts: {last_error}")

    raise ValueError("Unreachable")


# =============================================================================
# Demo Functions
# =============================================================================

def demo_basic_parsing():
    """Demo 1: Basic parsing into typed objects."""
    print("─" * 70)
    print("DEMO 1: Basic Structured Output Parsing")
    print("─" * 70)

    review = "The app crashes every time I try to upload files larger than 10MB. This has been happening since the last update. Very frustrating!"

    prompt = f"""Analyze this user feedback and return as JSON:
- sentiment: positive, negative, or neutral
- confidence: 0.0 to 1.0
- reasoning: why you chose this sentiment
- key_phrases: list of phrases indicating sentiment

Feedback: "{review}"
"""

    result, attempts = parse_with_retry(prompt, SentimentResult, system="Return valid JSON only.")
    print(f"\n  Input: \"{review[:60]}...\"")
    print(f"  Parsed in {attempts} attempt(s):")
    print(f"    Sentiment:   {result.sentiment}")
    print(f"    Confidence:  {result.confidence}")
    print(f"    Reasoning:   {result.reasoning}")
    print(f"    Key phrases: {result.key_phrases}")
    print(f"    Type:        {type(result).__name__} ✓")


def demo_complex_schema():
    """Demo 2: Complex nested schema."""
    print(f"\n{'─' * 70}")
    print("DEMO 2: Complex Nested Schema (Meeting Minutes)")
    print("─" * 70)

    meeting_notes = """
    Sprint Planning - March 15, 2024
    Attendees: Sarah (PM), John (Backend), Lisa (Frontend), Mike (QA)
    
    Discussed the Q2 roadmap priorities. Decided to postpone the mobile app to Q3.
    John will refactor the auth service by March 22. Lisa to finish the new dashboard 
    by end of sprint. Mike needs to set up integration tests for the payment flow - 
    no specific deadline but should be before the auth refactor lands.
    
    Decision: We'll use PostgreSQL instead of MongoDB for the new service.
    Decision: Hiring budget approved for 2 senior engineers.
    """

    prompt = f"""Parse these meeting notes into structured JSON with:
- title, date, attendees (list of names)
- summary (2 sentences)
- action_items (list with task, assignee, deadline, priority)
- decisions (list of decisions made)

Meeting notes:
{meeting_notes}"""

    result, attempts = parse_with_retry(prompt, MeetingMinutes, system="Return valid JSON only.")
    print(f"\n  Parsed in {attempts} attempt(s):")
    print(f"    Title:     {result.title}")
    print(f"    Date:      {result.date}")
    print(f"    Attendees: {result.attendees}")
    print(f"    Summary:   {result.summary[:80]}...")
    print(f"    Decisions: {result.decisions}")
    print(f"    Action items ({len(result.action_items)}):")
    for item in result.action_items:
        print(f"      - [{item.priority.value}] {item.task} → {item.assignee or 'unassigned'} (by {item.deadline or 'TBD'})")


def demo_validation_errors():
    """Demo 3: Handling validation errors."""
    print(f"\n{'─' * 70}")
    print("DEMO 3: Validation Errors and Recovery")
    print("─" * 70)

    # Intentionally problematic data to show validation
    bad_json_examples = [
        ('{"sentiment": "positive", "confidence": 1.5, "reasoning": "test", "key_phrases": []}', "confidence > 1.0"),
        ('{"sentiment": "positive", "confidence": 0.9, "reasoning": "test"}', "missing key_phrases"),
        ('{"sentiment": 123, "confidence": 0.9, "reasoning": "test", "key_phrases": []}', "wrong type for sentiment"),
    ]

    for bad_json, description in bad_json_examples:
        print(f"\n  Testing: {description}")
        print(f"    Input: {bad_json[:70]}...")
        try:
            data = json.loads(bad_json)
            result = SentimentResult.model_validate(data)
            print(f"    ✓ Passed (unexpected)")
        except ValidationError as e:
            errors = e.errors()
            print(f"    ✗ Validation error: {errors[0]['msg']} (field: {errors[0]['loc']})")


def demo_schema_evolution():
    """Demo 4: Schema evolution from V1 to V2."""
    print(f"\n{'─' * 70}")
    print("DEMO 4: Schema Evolution (V1 → V2)")
    print("─" * 70)

    # V1 data (old format)
    v1_data = {
        "title": "File upload crashes on large files",
        "category": "bug",
        "severity": "high",
        "description": "Uploads over 10MB cause the app to crash",
    }

    print(f"\n  V1 data: {json.dumps(v1_data)}")

    # V1 data validates against V2 (backward compatible!)
    v2_result = TicketV2.model_validate(v1_data)
    print(f"\n  Parsed as V2:")
    print(f"    title:              {v2_result.title}")
    print(f"    category:           {v2_result.category.value}")
    print(f"    severity:           {v2_result.severity.value}")
    print(f"    affected_component: {v2_result.affected_component} (default: None)")
    print(f"    estimated_hours:    {v2_result.estimated_hours} (default: None)")
    print(f"    tags:               {v2_result.tags} (default: [])")
    print(f"\n  ✓ V1 data is forward-compatible with V2 schema (defaults fill in)")

    # Full V2 data
    v2_data = {
        **v1_data,
        "affected_component": "upload-service",
        "estimated_hours": 4.0,
        "tags": ["regression", "p1", "upload"],
    }
    v2_full = TicketV2.model_validate(v2_data)
    print(f"\n  Full V2 data validates: ✓")
    print(f"    tags: {v2_full.tags}")


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 70)
    print("OUTPUT PARSER DEMO")
    print("=" * 70)
    print(f"Model: {MODEL}\n")

    demo_basic_parsing()
    demo_complex_schema()
    demo_validation_errors()
    demo_schema_evolution()

    print(f"\n\n{'=' * 70}")
    print("KEY TAKEAWAYS:")
    print("─" * 70)
    print("""
    1. Pydantic models ARE your output contract — self-documenting + validating
    2. Always implement retry logic — models break schemas ~5-10% of the time
    3. JSON mode (response_format) eliminates most parse errors
    4. Schema evolution: add fields with defaults, never remove required fields
    5. Validation catches model hallucinations (confidence > 1.0, invalid enums)
    6. Log parse failures — they reveal prompt weaknesses to fix
    """)


if __name__ == "__main__":
    main()
