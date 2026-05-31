"""
PII Detector and Anonymizer
============================
Uses Microsoft Presidio to detect and anonymize PII in text.
Demonstrates: detection, multiple anonymization strategies, configurable sensitivity.
"""

import os
from dotenv import load_dotenv
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

load_dotenv()

# --- Initialize Presidio ---

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

CONFIDENCE_THRESHOLD = float(os.getenv("PII_CONFIDENCE_THRESHOLD", "0.7"))


# --- Detection ---

def detect_pii(text: str, language: str = "en") -> list[RecognizerResult]:
    """Detect all PII entities in text."""
    results = analyzer.analyze(
        text=text,
        language=language,
        score_threshold=CONFIDENCE_THRESHOLD,
    )
    # Sort by position for readable output
    return sorted(results, key=lambda x: x.start)


def print_detection_report(text: str, results: list[RecognizerResult]):
    """Print a detailed report of what PII was found."""
    print(f"\n{'─'*60}")
    print(f"Input text: \"{text}\"")
    print(f"{'─'*60}")

    if not results:
        print("  No PII detected.")
        return

    print(f"  Found {len(results)} PII entities:\n")
    for r in results:
        entity_text = text[r.start:r.end]
        print(f"  • {r.entity_type:<20} | \"{entity_text:<25}\" | "
              f"Position: {r.start}-{r.end} | Confidence: {r.score:.2f}")


# --- Anonymization Strategies ---

def anonymize_redact(text: str, results: list[RecognizerResult]) -> str:
    """Strategy 1: REDACT - completely remove PII."""
    operators = {
        "DEFAULT": OperatorConfig("redact", {})
    }
    result = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return result.text


def anonymize_mask(text: str, results: list[RecognizerResult]) -> str:
    """Strategy 2: MASK - replace with asterisks, keeping length hint."""
    operators = {
        "DEFAULT": OperatorConfig("mask", {
            "masking_char": "*",
            "chars_to_mask": 100,  # mask all characters
            "from_end": False,
        })
    }
    result = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return result.text


def anonymize_replace(text: str, results: list[RecognizerResult]) -> str:
    """Strategy 3: REPLACE - replace with placeholder showing entity type."""
    operators = {
        "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE>"}),
        "PERSON": OperatorConfig("replace", {"new_value": "<PERSON>"}),
        "CREDIT_CARD": OperatorConfig("replace", {"new_value": "<CREDIT_CARD>"}),
        "US_SSN": OperatorConfig("replace", {"new_value": "<SSN>"}),
        "LOCATION": OperatorConfig("replace", {"new_value": "<LOCATION>"}),
    }
    result = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return result.text


def anonymize_hash(text: str, results: list[RecognizerResult]) -> str:
    """Strategy 4: HASH - replace with hash (useful for de-duplication without revealing data)."""
    operators = {
        "DEFAULT": OperatorConfig("hash", {"hash_type": "sha256"})
    }
    result = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return result.text


# --- Main Demo ---

def demonstrate_anonymization(text: str):
    """Show all anonymization strategies for a given text."""
    results = detect_pii(text)
    print_detection_report(text, results)

    if not results:
        return

    print(f"\n  Anonymization Strategies:")
    print(f"  {'─'*50}")
    print(f"  Original:  {text}")
    print(f"  Redacted:  {anonymize_redact(text, results)}")
    print(f"  Masked:    {anonymize_mask(text, results)}")
    print(f"  Replaced:  {anonymize_replace(text, results)}")
    print(f"  Hashed:    {anonymize_hash(text, results)[:120]}...")


if __name__ == "__main__":
    print("=" * 60)
    print(" PII DETECTOR & ANONYMIZER DEMO")
    print(" Using Microsoft Presidio for detection and anonymization")
    print("=" * 60)

    test_texts = [
        # Multiple PII types
        "My name is John Smith and my email is john.smith@example.com. Call me at 555-123-4567.",

        # Financial PII
        "Please charge my credit card 4532-1234-5678-9012 for the order. My SSN is 123-45-6789.",

        # Address and location
        "Ship it to 123 Main Street, Springfield. My colleague Sarah Johnson can receive it.",

        # Mixed in natural language
        "I spoke with Dr. Michael Brown at the clinic on Oak Avenue. His number is (555) 987-6543 and email is mbrown@hospital.org.",

        # No PII (should pass clean)
        "What is the return policy for electronics purchased more than 30 days ago?",

        # Subtle PII
        "The patient ID is P-12345 and their date of birth is 03/15/1985. Labs were ordered by Dr. Williams.",
    ]

    for text in test_texts:
        demonstrate_anonymization(text)
        print()

    # --- Configurable sensitivity demo ---
    print("\n" + "=" * 60)
    print(" SENSITIVITY COMPARISON")
    print("=" * 60)

    ambiguous_text = "Call John at extension 4567 or room 201B."
    print(f"\n  Text: \"{ambiguous_text}\"")

    for threshold in [0.3, 0.5, 0.7, 0.9]:
        results = analyzer.analyze(
            text=ambiguous_text,
            language="en",
            score_threshold=threshold,
        )
        entities = [f"{r.entity_type}({r.score:.1f})" for r in results]
        print(f"  Threshold {threshold}: {entities if entities else 'No PII detected'}")
