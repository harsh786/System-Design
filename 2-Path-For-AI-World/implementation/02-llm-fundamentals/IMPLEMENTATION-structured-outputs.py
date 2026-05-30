"""
IMPLEMENTATION: Structured Outputs with LLMs
=============================================
Complete implementation showing how to get reliable structured data from LLMs.
Covers: Pydantic schemas, parsing, retries, streaming, multiple formats.
"""

import json
import yaml
import asyncio
from typing import Optional, List, Literal
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError
from openai import OpenAI, AsyncOpenAI


# =============================================================================
# 1. PYDANTIC MODELS AS OUTPUT SCHEMAS
# =============================================================================

class Sentiment(str, Enum):
    """Constrained enum ensures model outputs only valid values."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Entity(BaseModel):
    """A named entity extracted from text."""
    name: str = Field(description="The entity name as it appears in text")
    type: Literal["person", "organization", "location", "product", "date"] = Field(
        description="Entity category"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence score")


class AnalysisResult(BaseModel):
    """Complete structured analysis of a text input.
    
    This schema is sent to the API and constrains the model's output
    via constrained decoding — every generated token is guaranteed to
    produce valid JSON matching this schema.
    """
    summary: str = Field(description="One-sentence summary of the text")
    sentiment: Sentiment
    entities: List[Entity] = Field(default_factory=list)
    key_topics: List[str] = Field(description="Main topics discussed", max_length=5)
    language: str = Field(description="ISO 639-1 language code")
    word_count: int = Field(ge=0)


class ProductReview(BaseModel):
    """Schema for product review extraction."""
    product_name: str
    rating: float = Field(ge=1.0, le=5.0)
    pros: List[str] = Field(max_length=5)
    cons: List[str] = Field(max_length=5)
    would_recommend: bool
    summary: str


# =============================================================================
# 2. BASIC STRUCTURED OUTPUT (OpenAI response_format)
# =============================================================================

def extract_structured(text: str) -> AnalysisResult:
    """
    Uses OpenAI's structured output feature (response_format with json_schema).
    The model is constrained at the decoding level to produce valid JSON
    matching our Pydantic schema.
    """
    client = OpenAI()

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",  # Must use a model that supports structured outputs
        messages=[
            {
                "role": "system",
                "content": "You are a text analysis engine. Analyze the provided text and extract structured information."
            },
            {
                "role": "user",
                "content": f"Analyze this text:\n\n{text}"
            }
        ],
        response_format=AnalysisResult,  # Pydantic model as schema
        temperature=0,  # Deterministic for structured extraction
    )

    # The SDK automatically parses into our Pydantic model
    result = response.choices[0].message.parsed

    # Handle refusal (model may refuse to answer for safety reasons)
    if response.choices[0].message.refusal:
        raise ValueError(f"Model refused: {response.choices[0].message.refusal}")

    return result


# =============================================================================
# 3. GRACEFUL PARSING FAILURE HANDLING
# =============================================================================

@dataclass
class ParseResult:
    """Wraps parsing outcome with error information for graceful degradation."""
    success: bool
    data: Optional[BaseModel] = None
    raw_content: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0


def extract_with_fallback(text: str, schema: type[BaseModel]) -> ParseResult:
    """
    Attempts structured output extraction with multiple fallback strategies:
    1. Try structured output mode (constrained decoding)
    2. Fall back to JSON mode + manual parsing
    3. Fall back to plain text + regex extraction
    """
    client = OpenAI()

    # Strategy 1: Constrained decoding (most reliable)
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": "Extract structured data from the input."},
                {"role": "user", "content": text}
            ],
            response_format=schema,
            temperature=0,
        )

        if response.choices[0].message.parsed:
            return ParseResult(success=True, data=response.choices[0].message.parsed, attempts=1)
    except Exception as e:
        pass  # Fall through to next strategy

    # Strategy 2: JSON mode + manual Pydantic validation
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"Output valid JSON matching this schema:\n{schema.model_json_schema()}"
                },
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        raw = response.choices[0].message.content
        parsed = schema.model_validate_json(raw)
        return ParseResult(success=True, data=parsed, raw_content=raw, attempts=2)

    except (ValidationError, json.JSONDecodeError) as e:
        return ParseResult(success=False, raw_content=raw, error=str(e), attempts=2)

    except Exception as e:
        return ParseResult(success=False, error=str(e), attempts=2)


# =============================================================================
# 4. RETRY LOGIC FOR MALFORMED OUTPUTS
# =============================================================================

async def extract_with_retry(
    text: str,
    schema: type[BaseModel],
    max_retries: int = 3,
    fix_prompt: bool = True,
) -> ParseResult:
    """
    Retry loop that feeds parsing errors back to the model for self-correction.
    
    This implements the "error-feedback" pattern:
    - On failure, include the error message in the next attempt
    - The model learns from its own mistakes within the conversation
    - Exponential backoff between retries
    """
    client = AsyncOpenAI()
    messages = [
        {
            "role": "system",
            "content": (
                "Extract structured data from the user's input. "
                f"Output MUST conform to this JSON schema:\n"
                f"{json.dumps(schema.model_json_schema(), indent=2)}"
            )
        },
        {"role": "user", "content": text}
    ]

    last_error = None

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )

            raw = response.choices[0].message.content
            parsed = schema.model_validate_json(raw)
            return ParseResult(success=True, data=parsed, raw_content=raw, attempts=attempt + 1)

        except ValidationError as e:
            last_error = str(e)
            if fix_prompt and attempt < max_retries - 1:
                # Feed the error back to the model for self-correction
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your output had validation errors:\n{last_error}\n\n"
                        "Please fix the output to match the schema exactly."
                    )
                })

        except Exception as e:
            last_error = str(e)
            # Exponential backoff for transient errors
            await asyncio.sleep(2 ** attempt)

    return ParseResult(success=False, error=last_error, attempts=max_retries)


# =============================================================================
# 5. STREAMING WITH STRUCTURED OUTPUT
# =============================================================================

async def stream_structured_output(text: str) -> AnalysisResult:
    """
    Stream a structured output response.
    
    With structured outputs, streaming gives you partial JSON as it's generated.
    You can show progress to the user but must wait for completion to parse.
    
    Use case: Show a loading indicator with partial content for UX,
    while still getting a fully validated result at the end.
    """
    client = AsyncOpenAI()

    # Accumulate chunks for progress reporting
    accumulated = ""

    async with client.beta.chat.completions.stream(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "Analyze the text and provide structured output."},
            {"role": "user", "content": text}
        ],
        response_format=AnalysisResult,
    ) as stream:
        async for event in stream:
            # Each event contains a partial JSON string
            if event.type == "content.delta":
                accumulated += event.delta
                # You could parse partial JSON here for progress indication
                print(f"Streaming... ({len(accumulated)} chars received)", end="\r")

        # Get the final parsed result
        final = await stream.get_final_completion()
        return final.choices[0].message.parsed


# =============================================================================
# 6. MULTIPLE OUTPUT FORMATS
# =============================================================================

class OutputFormatter:
    """
    Converts structured model output to various formats.
    
    Architect principle: Always extract structured data first (JSON/Pydantic),
    then format for presentation. Never ask the model to produce presentation
    formats directly — they're harder to validate.
    """

    def __init__(self, data: BaseModel):
        self.data = data

    def to_json(self, indent: int = 2) -> str:
        """Standard JSON output."""
        return self.data.model_dump_json(indent=indent)

    def to_yaml(self) -> str:
        """YAML output — more readable for configuration-like data."""
        return yaml.dump(
            self.data.model_dump(),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    def to_markdown_table(self) -> str:
        """Markdown table — useful for rendering in chat interfaces."""
        data = self.data.model_dump()
        lines = ["| Field | Value |", "|-------|-------|"]
        for key, value in data.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"| {key} | {value} |")
        return "\n".join(lines)

    def to_csv_row(self, delimiter: str = ",") -> str:
        """Single CSV row — useful for batch processing pipelines."""
        data = self.data.model_dump()
        values = []
        for v in data.values():
            if isinstance(v, (list, dict)):
                v = json.dumps(v)
            values.append(f'"{v}"')
        return delimiter.join(values)


# =============================================================================
# 7. BATCH PROCESSING WITH STRUCTURED OUTPUTS
# =============================================================================

async def batch_extract(
    texts: List[str],
    schema: type[BaseModel],
    concurrency: int = 5,
) -> List[ParseResult]:
    """
    Process multiple texts concurrently with structured output extraction.
    
    Uses a semaphore to limit concurrent API calls (respect rate limits).
    Returns results in the same order as inputs.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(text: str) -> ParseResult:
        async with semaphore:
            return await extract_with_retry(text, schema)

    tasks = [process_one(text) for text in texts]
    return await asyncio.gather(*tasks)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Example: Extract structured data from a product review
    review_text = """
    I bought the Sony WH-1000XM5 headphones last month. The noise cancellation 
    is absolutely incredible - best I've ever used. Sound quality is warm and 
    detailed. Battery lasts about 30 hours which is great. However, they don't 
    fold flat like the XM4s, which makes them harder to travel with. Also, the 
    price at $400 is steep. Overall I'd still recommend them for anyone who 
    prioritizes ANC quality. 4.5/5.
    """

    # Basic extraction
    result = extract_structured(review_text)
    print("=== Structured Output ===")
    print(result.model_dump_json(indent=2))

    # Multiple formats
    formatter = OutputFormatter(result)
    print("\n=== YAML Format ===")
    print(formatter.to_yaml())
    print("\n=== Markdown Table ===")
    print(formatter.to_markdown_table())
