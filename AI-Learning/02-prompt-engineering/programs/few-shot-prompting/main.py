"""
Few-Shot Prompting Demo
========================
Shows how providing examples (shots) impacts accuracy and consistency.
Compares zero-shot, 1-shot, 3-shot, and 5-shot on classification and extraction.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def call_llm(prompt: str, temperature: float = 0.0) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


# =============================================================================
# Sentiment Classification with Different Shot Counts
# =============================================================================

# Custom sentiment labels (not standard positive/negative — this is where few-shot shines)
SENTIMENT_EXAMPLES = [
    ("The product works but nothing special", "neutral"),
    ("Absolute garbage, want my money back", "angry"),
    ("Pretty good for the price, minor issues", "satisfied"),
    ("I'm obsessed with this!! Best purchase ever!!", "delighted"),
    ("It broke after 2 days. Disappointing.", "disappointed"),
]

TEST_CASES = [
    ("Not bad, does what it says on the tin", "satisfied"),
    ("HOW IS THIS LEGAL?? SCAM!!", "angry"),
    ("Meh, it's fine I guess", "neutral"),
    ("This changed my life, no exaggeration", "delighted"),
    ("Was excited but it didn't live up to the hype", "disappointed"),
]


def classify_sentiment(text: str, num_shots: int) -> str:
    """Classify sentiment with N examples."""
    categories = "neutral, angry, satisfied, delighted, disappointed"

    if num_shots == 0:
        prompt = f"""Classify the sentiment of this review into one of: {categories}
Return ONLY the category label.

Review: "{text}"
Sentiment:"""
    else:
        examples = SENTIMENT_EXAMPLES[:num_shots]
        example_text = "\n".join(
            f'Review: "{ex[0]}" → Sentiment: {ex[1]}' for ex in examples
        )
        prompt = f"""Classify the sentiment of reviews into one of: {categories}

{example_text}

Review: "{text}" → Sentiment:"""

    return call_llm(prompt).lower().strip()


# =============================================================================
# Entity Extraction with Different Shot Counts
# =============================================================================

EXTRACTION_EXAMPLES = [
    (
        "Apple CEO Tim Cook announced the M3 chip at their Cupertino headquarters on March 8.",
        '{"people": ["Tim Cook"], "orgs": ["Apple"], "products": ["M3 chip"], "locations": ["Cupertino"], "dates": ["March 8"]}',
    ),
    (
        "Microsoft acquired Activision Blizzard for $69B in October 2023.",
        '{"people": [], "orgs": ["Microsoft", "Activision Blizzard"], "products": [], "locations": [], "dates": ["October 2023"]}',
    ),
    (
        "Elon Musk's Tesla delivered 1.8 million vehicles from their Shanghai and Austin factories in 2023.",
        '{"people": ["Elon Musk"], "orgs": ["Tesla"], "products": [], "locations": ["Shanghai", "Austin"], "dates": ["2023"]}',
    ),
]

EXTRACTION_TEST = "Google's Sundar Pichai unveiled Gemini AI at their Mountain View campus in December 2023."


def extract_entities(text: str, num_shots: int) -> str:
    """Extract entities with N examples."""
    if num_shots == 0:
        prompt = f"""Extract entities from this text as JSON with keys: people, orgs, products, locations, dates.
Each value should be a list of strings.

Text: "{text}"
JSON:"""
    else:
        examples = EXTRACTION_EXAMPLES[:num_shots]
        example_text = "\n\n".join(
            f'Text: "{ex[0]}"\nJSON: {ex[1]}' for ex in examples
        )
        prompt = f"""Extract entities from text as JSON.

{example_text}

Text: "{text}"
JSON:"""

    return call_llm(prompt)


# =============================================================================
# Example Ordering Effect
# =============================================================================

def test_ordering_effect():
    """Show how example order affects output."""
    text = "The service was okay, nothing to write home about"

    # Order 1: negative examples last (recency bias toward negative)
    examples_neg_last = [
        ("Amazing product!", "delighted"),
        ("Works perfectly", "satisfied"),
        ("Terrible quality", "angry"),
        ("Very disappointing", "disappointed"),
    ]

    # Order 2: positive examples last (recency bias toward positive)
    examples_pos_last = [
        ("Terrible quality", "angry"),
        ("Very disappointing", "disappointed"),
        ("Amazing product!", "delighted"),
        ("Works perfectly", "satisfied"),
    ]

    def classify_with_examples(examples):
        example_text = "\n".join(f'"{ex[0]}" → {ex[1]}' for ex in examples)
        prompt = f"""Classify sentiment: neutral, angry, satisfied, delighted, disappointed

{example_text}

"{text}" →"""
        return call_llm(prompt)

    return {
        "negative_examples_last": classify_with_examples(examples_neg_last),
        "positive_examples_last": classify_with_examples(examples_pos_last),
    }


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 70)
    print("FEW-SHOT PROMPTING COMPARISON")
    print("=" * 70)
    print(f"Model: {MODEL}\n")

    # --- Sentiment Classification ---
    print("\n" + "─" * 70)
    print("EXPERIMENT 1: Sentiment Classification")
    print("─" * 70)
    print("Custom labels: neutral, angry, satisfied, delighted, disappointed\n")

    print(f"{'Test Case':<45} {'0-shot':<14} {'1-shot':<14} {'3-shot':<14} {'5-shot':<14}")
    print("─" * 100)

    for text, expected in TEST_CASES:
        results = {}
        for shots in [0, 1, 3, 5]:
            results[shots] = classify_sentiment(text, shots)

        display_text = text[:42] + "..." if len(text) > 42 else text
        r0 = results[0][:12]
        r1 = results[1][:12]
        r3 = results[3][:12]
        r5 = results[5][:12]
        print(f"{display_text:<45} {r0:<14} {r1:<14} {r3:<14} {r5:<14}")

    # --- Entity Extraction ---
    print("\n\n" + "─" * 70)
    print("EXPERIMENT 2: Entity Extraction")
    print("─" * 70)
    print(f"Text: {EXTRACTION_TEST}\n")

    for shots in [0, 1, 3]:
        result = extract_entities(EXTRACTION_TEST, shots)
        print(f"\n{shots}-shot result:")
        try:
            parsed = json.loads(result)
            print(f"  {json.dumps(parsed, indent=2)}")
        except json.JSONDecodeError:
            print(f"  (raw) {result[:200]}")

    # --- Ordering Effect ---
    print("\n\n" + "─" * 70)
    print("EXPERIMENT 3: Example Ordering Effect")
    print("─" * 70)
    print('Text: "The service was okay, nothing to write home about"\n')

    ordering_results = test_ordering_effect()
    print(f"  Negative examples last → {ordering_results['negative_examples_last']}")
    print(f"  Positive examples last → {ordering_results['positive_examples_last']}")
    print("\n  (Same examples, different order — may produce different classifications!)")

    # --- Summary ---
    print(f"\n\n{'=' * 70}")
    print("KEY TAKEAWAYS:")
    print("─" * 70)
    print("""
    1. Few-shot is most impactful for CUSTOM categories (not standard pos/neg)
    2. 3 examples usually captures most of the benefit
    3. Examples teach FORMAT as much as they teach LOGIC
    4. Order matters — last example has outsized influence
    5. For entity extraction, even 1 example dramatically improves JSON compliance
    """)


if __name__ == "__main__":
    main()
