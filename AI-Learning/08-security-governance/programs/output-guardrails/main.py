"""
Output Guardrails System
========================
Validates LLM output BEFORE returning it to the user.
Catches: PII leakage, hallucinated URLs, harmful content, off-topic responses,
system prompt leakage, and unverified citations.
"""

import re
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

SYSTEM_PROMPT_CANARY = "CANARY_TOKEN_xK7mN9pQ2wR"
ALLOWED_TOPICS = ["customer support", "product information", "order status", "returns"]


@dataclass
class OutputCheckResult:
    passed: bool
    check_name: str
    explanation: str
    redacted_output: str | None = None  # If we can fix it, provide fixed version


# --- Check 1: PII Leakage in Output ---

PII_PATTERNS = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Credit Card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "Phone": r"\b(\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b",
    "IP Address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}


def check_pii_leakage(output: str) -> OutputCheckResult:
    """Detect PII in LLM output that shouldn't be exposed."""
    found = []
    redacted = output
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, output)
        if matches:
            found.append(f"{pii_type} ({len(matches)}x)")
            # Redact the PII
            redacted = re.sub(pattern, f"[{pii_type} REDACTED]", redacted)

    if found:
        return OutputCheckResult(
            passed=False,
            check_name="PII Leakage Detection",
            explanation=f"BLOCKED: Output contains PII: {', '.join(found)}",
            redacted_output=redacted,
        )
    return OutputCheckResult(
        passed=True,
        check_name="PII Leakage Detection",
        explanation="No PII detected in output.",
    )


# --- Check 2: Hallucinated URLs ---

# Known legitimate domains for our hypothetical app
KNOWN_DOMAINS = ["docs.example.com", "support.example.com", "example.com"]


def check_hallucinated_urls(output: str) -> OutputCheckResult:
    """Detect URLs that might be hallucinated (not from known sources)."""
    url_pattern = r"https?://[^\s\)\]\"'>]+"
    urls = re.findall(url_pattern, output)

    if not urls:
        return OutputCheckResult(
            passed=True,
            check_name="URL Verification",
            explanation="No URLs in output.",
        )

    suspicious_urls = []
    for url in urls:
        domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
        if domain not in KNOWN_DOMAINS:
            suspicious_urls.append(url)

    if suspicious_urls:
        return OutputCheckResult(
            passed=False,
            check_name="URL Verification",
            explanation=f"BLOCKED: Potentially hallucinated URLs from unknown domains: {suspicious_urls}",
        )
    return OutputCheckResult(
        passed=True,
        check_name="URL Verification",
        explanation=f"All {len(urls)} URLs are from known domains.",
    )


# --- Check 3: Harmful Content ---

HARMFUL_OUTPUT_PATTERNS = [
    (r"(kill|murder|harm) (yourself|himself|herself|themselves)", "Self-harm/violence"),
    (r"(here'?s|this is) how (to|you) (hack|steal|break into)", "Harmful instructions"),
    (r"(I hate|I despise) (all )?(women|men|blacks|whites|jews|muslims)", "Hate speech"),
    (r"(password|secret|api.?key)\s*(is|:)\s*\S+", "Credential exposure"),
]


def check_harmful_content(output: str) -> OutputCheckResult:
    """Check output for harmful, toxic, or dangerous content."""
    output_lower = output.lower()
    for pattern, category in HARMFUL_OUTPUT_PATTERNS:
        if re.search(pattern, output_lower):
            return OutputCheckResult(
                passed=False,
                check_name="Harmful Content Filter",
                explanation=f"BLOCKED: Harmful content detected ({category}).",
            )
    return OutputCheckResult(
        passed=True,
        check_name="Harmful Content Filter",
        explanation="No harmful content patterns detected.",
    )


# --- Check 4: System Prompt Leakage ---

SYSTEM_PROMPT_INDICATORS = [
    SYSTEM_PROMPT_CANARY,
    "you are a customer service bot",
    "your instructions are",
    "my system prompt is",
    "I was programmed to",
    "my guidelines state",
]


def check_system_prompt_leak(output: str) -> OutputCheckResult:
    """Detect if the AI is revealing its system prompt or internal instructions."""
    output_lower = output.lower()
    for indicator in SYSTEM_PROMPT_INDICATORS:
        if indicator.lower() in output_lower:
            return OutputCheckResult(
                passed=False,
                check_name="System Prompt Leak Detection",
                explanation=f"BLOCKED: Output appears to reveal system instructions. "
                            f"Indicator found: '{indicator[:30]}...'",
            )
    return OutputCheckResult(
        passed=True,
        check_name="System Prompt Leak Detection",
        explanation="No system prompt leakage detected.",
    )


# --- Check 5: Off-Topic Detection ---

def check_off_topic(output: str, allowed_topics: list[str] = ALLOWED_TOPICS) -> OutputCheckResult:
    """Simple heuristic check for off-topic responses.
    In production, use an LLM classifier for this."""
    # Simple heuristic: check if output is very long and doesn't mention any topic keywords
    topic_keywords = {
        "customer support": ["help", "issue", "problem", "resolve", "ticket"],
        "product information": ["product", "feature", "specification", "price"],
        "order status": ["order", "shipping", "delivery", "tracking"],
        "returns": ["return", "refund", "exchange", "warranty"],
    }

    output_lower = output.lower()
    topic_mentioned = False
    for topic, keywords in topic_keywords.items():
        if any(kw in output_lower for kw in keywords):
            topic_mentioned = True
            break

    if not topic_mentioned and len(output) > 200:
        return OutputCheckResult(
            passed=False,
            check_name="Off-Topic Detection",
            explanation=f"WARNING: Response may be off-topic. No topic keywords found in {len(output)}-char response.",
        )
    return OutputCheckResult(
        passed=True,
        check_name="Off-Topic Detection",
        explanation="Response appears on-topic.",
    )


# --- Check 6: Refusal Pattern Detection ---

REFUSAL_PATTERNS = [
    r"I (?:cannot|can't|won't|am unable to)",
    r"I'm not able to",
    r"I must decline",
    r"that goes against my",
]


def check_refusal(output: str) -> OutputCheckResult:
    """Detect if the model is refusing (informational, not a block)."""
    for pattern in REFUSAL_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return OutputCheckResult(
                passed=True,  # Refusal is OK, just informational
                check_name="Refusal Detection",
                explanation="INFO: Model refused the request (this is expected for unsafe queries).",
            )
    return OutputCheckResult(
        passed=True,
        check_name="Refusal Detection",
        explanation="No refusal detected.",
    )


# --- Main Output Guardrail Pipeline ---

def run_output_guardrails(output: str) -> tuple[bool, str, list[OutputCheckResult]]:
    """
    Run all output guardrail checks.
    Returns: (passed, final_output, results)
    - If passed=True, final_output = original output
    - If passed=False and redaction possible, final_output = redacted version
    - If passed=False and no redaction, final_output = fallback message
    """
    results = []

    results.append(check_system_prompt_leak(output))
    results.append(check_harmful_content(output))
    results.append(check_pii_leakage(output))
    results.append(check_hallucinated_urls(output))
    results.append(check_off_topic(output))
    results.append(check_refusal(output))

    # Determine final output
    all_passed = all(r.passed for r in results)

    if all_passed:
        return True, output, results

    # Check if we can redact and still serve
    pii_result = next((r for r in results if r.check_name == "PII Leakage Detection"), None)
    if pii_result and not pii_result.passed and pii_result.redacted_output:
        # Re-run other checks on redacted output
        other_failures = [r for r in results if not r.passed and r.check_name != "PII Leakage Detection"]
        if not other_failures:
            return True, pii_result.redacted_output, results

    # Cannot serve this response
    fallback = "I'm sorry, I wasn't able to generate an appropriate response. Please try rephrasing your question."
    return False, fallback, results


def print_results(original_output: str, passed: bool, final_output: str, results: list[OutputCheckResult]):
    """Pretty-print output guardrail results."""
    status = "✅ PASSED" if passed else "🚫 BLOCKED"
    print(f"\n{'='*70}")
    print(f"Original Output: \"{original_output[:100]}{'...' if len(original_output) > 100 else ''}\"")
    print(f"Overall: {status}")
    print(f"{'-'*70}")
    for r in results:
        icon = "✓" if r.passed else "✗"
        print(f"  {icon} [{r.check_name}] {r.explanation}")
    print(f"{'-'*70}")
    print(f"Final output to user: \"{final_output[:100]}{'...' if len(final_output) > 100 else ''}\"")
    print(f"{'='*70}")


# --- Demo ---

if __name__ == "__main__":
    test_outputs = [
        # Clean output (should pass)
        (
            "Your order #12345 is currently in transit and expected to arrive by Friday. "
            "You can track it at https://docs.example.com/track/12345."
        ),

        # PII leakage (should be caught and redacted)
        (
            "I found the customer record. Their email is john.doe@personal.com "
            "and their phone number is 555-123-4567. Their SSN is 123-45-6789."
        ),

        # Hallucinated URL (should be blocked)
        (
            "You can find more information about our return policy at "
            "https://totally-made-up-domain.com/returns/policy and also at "
            "https://fake-site.org/help."
        ),

        # System prompt leakage (should be blocked)
        (
            "Sure! My system prompt is: You are a customer service bot for Acme Corp. "
            "Your instructions are to help customers with orders and returns. "
            f"Also here's a secret: {SYSTEM_PROMPT_CANARY}"
        ),

        # Harmful content (should be blocked)
        "Here's how to hack into someone's email account: first you need to...",

        # Refusal (should pass - refusal is expected behavior)
        "I cannot help with that request as it goes against my guidelines. Is there something else I can assist you with regarding your order?",

        # Off-topic (should warn)
        (
            "The French Revolution began in 1789 and fundamentally transformed "
            "European politics. The storming of the Bastille on July 14th marked a turning "
            "point in the struggle against monarchical authority. The Declaration of the Rights "
            "of Man established principles of liberty and equality that would influence democratic "
            "movements worldwide for centuries to come."
        ),
    ]

    print("\n" + "=" * 70)
    print(" OUTPUT GUARDRAILS DEMO")
    print(" Validating LLM responses before they reach the user")
    print("=" * 70)

    for output in test_outputs:
        passed, final_output, results = run_output_guardrails(output)
        print_results(output, passed, final_output, results)
