"""
Structured Output - Getting validated, typed data from LLMs.

Demonstrates:
1. Pydantic models for defining output schemas
2. OpenAI function calling for structured extraction
3. Movie review parsing into structured format
4. Entity extraction from unstructured text
5. Validation and error handling
"""

import json
import os
from enum import Enum
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"


# === Schema Definitions ===

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class MovieReview(BaseModel):
    """Structured representation of a movie review."""
    title: str = Field(description="Movie title mentioned in the review")
    sentiment: Sentiment = Field(description="Overall sentiment of the review")
    rating: float = Field(ge=0, le=10, description="Rating from 0 to 10")
    pros: list[str] = Field(description="Positive aspects mentioned")
    cons: list[str] = Field(description="Negative aspects mentioned")
    summary: str = Field(description="One-sentence summary of the review")
    recommended: bool = Field(description="Whether the reviewer recommends it")


class Person(BaseModel):
    """A person entity extracted from text."""
    name: str
    role: Optional[str] = None
    organization: Optional[str] = None


class Location(BaseModel):
    """A location entity extracted from text."""
    name: str
    type: str = Field(description="city, country, building, etc.")


class Event(BaseModel):
    """An event extracted from text."""
    description: str
    date: Optional[str] = None
    location: Optional[str] = None


class ExtractedEntities(BaseModel):
    """All entities extracted from a text."""
    people: list[Person] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    key_topics: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    """An action item extracted from meeting notes."""
    task: str
    assignee: Optional[str] = None
    deadline: Optional[str] = None
    priority: str = Field(description="high, medium, or low")


class MeetingNotes(BaseModel):
    """Structured meeting notes."""
    title: str
    attendees: list[str]
    decisions: list[str]
    action_items: list[ActionItem]
    next_meeting: Optional[str] = None


# === Helper Functions ===

def extract_structured(text: str, schema: type[BaseModel], instruction: str) -> BaseModel:
    """Use function calling to extract structured data from text."""
    # Convert Pydantic model to JSON schema for function calling
    schema_dict = schema.model_json_schema()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "extract_data",
                "description": f"Extract structured data matching the {schema.__name__} schema",
                "parameters": schema_dict,
            }
        }],
        tool_choice={"type": "function", "function": {"name": "extract_data"}},
        temperature=0,
    )

    # Parse the function call arguments
    tool_call = response.choices[0].message.tool_calls[0]
    raw_data = json.loads(tool_call.function.arguments)

    # Validate with Pydantic
    return schema.model_validate(raw_data)


# === Demos ===

def demo_movie_reviews():
    """Parse unstructured movie reviews into structured data."""
    print("\n" + "=" * 70)
    print(" DEMO 1: Movie Review Parsing")
    print("=" * 70)

    reviews = [
        """
        Just saw Oppenheimer last night and WOW. Nolan outdid himself. The cinematography 
        is breathtaking, Cillian Murphy deserves every award, and the sound design is 
        incredible. My only complaints: it's a bit long (3 hours!) and some of the 
        physics scenes felt rushed. Still, easily a 9/10 and a must-watch. Go see it!
        """,
        """
        Watched the new Transformers movie and I want my 2.5 hours back. The plot makes 
        zero sense, the dialogue is painful, and even the action scenes are boring somehow. 
        The only saving grace is the VFX team clearly worked hard. But that's not enough 
        to save this dumpster fire. 3/10, skip it.
        """,
    ]

    for i, review in enumerate(reviews, 1):
        print(f"\n  Review {i}:")
        print(f"  Input: \"{review.strip()[:80]}...\"")

        result = extract_structured(
            review,
            MovieReview,
            "Extract structured information from this movie review. Be accurate to what the reviewer says."
        )

        print(f"\n  Extracted:")
        print(f"    Title:       {result.title}")
        print(f"    Sentiment:   {result.sentiment.value}")
        print(f"    Rating:      {result.rating}/10")
        print(f"    Recommended: {'Yes' if result.recommended else 'No'}")
        print(f"    Pros:        {', '.join(result.pros)}")
        print(f"    Cons:        {', '.join(result.cons)}")
        print(f"    Summary:     {result.summary}")


def demo_entity_extraction():
    """Extract entities from news-style text."""
    print("\n" + "=" * 70)
    print(" DEMO 2: Entity Extraction")
    print("=" * 70)

    text = """
    Apple CEO Tim Cook announced at their Cupertino headquarters on March 15, 2025 
    that the company would invest $10 billion in AI research. The initiative, led by 
    VP of Machine Learning John Giannandrea, will establish new labs in London and 
    Tokyo. Cook stated this was Apple's largest R&D investment to date. The announcement 
    came just days before Google's annual AI summit in Mountain View, where CEO Sundar 
    Pichai is expected to unveil competing plans.
    """

    print(f"\n  Input: \"{text.strip()[:100]}...\"")

    result = extract_structured(
        text,
        ExtractedEntities,
        "Extract all people, locations, events, and key topics from this text."
    )

    print(f"\n  People:")
    for p in result.people:
        print(f"    - {p.name} ({p.role or 'unknown role'}, {p.organization or 'unknown org'})")

    print(f"\n  Locations:")
    for loc in result.locations:
        print(f"    - {loc.name} ({loc.type})")

    print(f"\n  Events:")
    for event in result.events:
        print(f"    - {event.description} [{event.date or 'no date'}] @ {event.location or 'unknown'}")

    print(f"\n  Key Topics: {', '.join(result.key_topics)}")


def demo_meeting_notes():
    """Extract structured meeting notes from raw text."""
    print("\n" + "=" * 70)
    print(" DEMO 3: Meeting Notes Extraction")
    print("=" * 70)

    raw_notes = """
    Team standup March 20 - Present: Sarah, Mike, Chen, Priya
    
    Sarah said the auth service migration is done, we're going with OAuth2.
    Mike needs to finish the API docs by Friday — this is high priority since 
    the partner launch is next week. Chen mentioned the database indexing is 
    causing slow queries, he'll investigate and fix by Wednesday. Priya will 
    set up the monitoring dashboard, low priority, sometime next sprint.
    
    We decided to postpone the UI redesign until Q2. Also agreed to switch 
    from weekly to daily standups during the launch period.
    
    Next meeting: tomorrow 9am same channel.
    """

    print(f"\n  Input: raw meeting notes ({len(raw_notes)} chars)")

    result = extract_structured(
        raw_notes,
        MeetingNotes,
        "Extract structured meeting information including decisions and action items with priorities."
    )

    print(f"\n  Title: {result.title}")
    print(f"  Attendees: {', '.join(result.attendees)}")
    print(f"\n  Decisions:")
    for d in result.decisions:
        print(f"    - {d}")
    print(f"\n  Action Items:")
    for item in result.action_items:
        print(f"    [{item.priority.upper():<6}] {item.task}")
        print(f"            Assignee: {item.assignee or 'unassigned'} | Due: {item.deadline or 'no deadline'}")
    print(f"\n  Next Meeting: {result.next_meeting}")


def demo_validation():
    """Show what happens when validation fails."""
    print("\n" + "=" * 70)
    print(" DEMO 4: Validation & Error Handling")
    print("=" * 70)

    # Demonstrate manual validation
    print("\n  Testing Pydantic validation:")

    # Valid data
    try:
        review = MovieReview(
            title="Test Movie",
            sentiment=Sentiment.POSITIVE,
            rating=8.5,
            pros=["Great acting"],
            cons=["Too long"],
            summary="A good movie",
            recommended=True,
        )
        print(f"    Valid data: OK - {review.title}, rating={review.rating}")
    except ValidationError as e:
        print(f"    Valid data: FAILED - {e}")

    # Invalid rating (out of range)
    try:
        review = MovieReview(
            title="Test",
            sentiment=Sentiment.POSITIVE,
            rating=15.0,  # Invalid! Max is 10
            pros=[],
            cons=[],
            summary="test",
            recommended=True,
        )
        print(f"    Rating=15: OK (unexpected!)")
    except ValidationError as e:
        print(f"    Rating=15: REJECTED - {e.errors()[0]['msg']}")

    # Invalid sentiment
    try:
        review = MovieReview(
            title="Test",
            sentiment="amazing",  # Invalid! Not in enum
            rating=5.0,
            pros=[],
            cons=[],
            summary="test",
            recommended=True,
        )
        print(f"    Sentiment='amazing': OK (unexpected!)")
    except ValidationError as e:
        print(f"    Sentiment='amazing': REJECTED - {e.errors()[0]['msg']}")

    print("\n  Key Insight: Pydantic catches invalid data EVEN IF the LLM generates it.")
    print("  Always validate AI output before using it in your application!")


def main():
    print("\n" + "=" * 70)
    print("  STRUCTURED OUTPUT - Typed, Validated Data from LLMs")
    print(f"  Model: {MODEL}")
    print("=" * 70)

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-key-here":
        print("\n  ERROR: Set your OPENAI_API_KEY in .env file")
        print("  Copy .env.example to .env and add your key")
        return

    demo_movie_reviews()
    demo_entity_extraction()
    demo_meeting_notes()
    demo_validation()

    print("\n" + "=" * 70)
    print("  All demos complete!")
    print("  Structured output = LLM power + type safety + validation")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
