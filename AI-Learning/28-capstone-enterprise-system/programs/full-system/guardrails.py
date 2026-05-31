"""
Guardrails module.
Input validation (injection, PII) and output validation (hallucination, PII leakage).
"""

import re
from config import GUARDRAILS


class GuardrailResult:
    def __init__(self, passed: bool, reason: str = "", score: float = 0.0):
        self.passed = passed
        self.reason = reason
        self.score = score

    def __repr__(self):
        status = "PASS" if self.passed else "BLOCK"
        return f"GuardrailResult({status}, reason='{self.reason}', score={self.score:.2f})"


# --- Injection Detection Patterns ---
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"show\s+(me\s+)?(the\s+)?system\s+(prompt|message)",
    r"what\s+(is|are)\s+your\s+(instructions|rules|system\s+prompt)",
    r"you\s+are\s+now\s+",
    r"new\s+instructions:",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"jailbreak",
    r"\[system\]",
    r"<\|im_start\|>",
]

# --- PII Patterns ---
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
}


def check_input_guardrails(text: str) -> GuardrailResult:
    """
    Check input text for safety issues.
    Returns GuardrailResult with pass/block decision.
    """
    print(f"[GUARDRAILS] Checking input ({len(text)} chars)...")

    # Check length
    if len(text) > GUARDRAILS["max_input_length"]:
        print("[GUARDRAILS] Input BLOCKED: exceeds max length")
        return GuardrailResult(False, "Input too long", 1.0)

    # Check for injection attempts
    text_lower = text.lower()
    injection_score = 0.0
    matched_patterns = []

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            injection_score += 0.4
            matched_patterns.append(pattern)

    if injection_score >= GUARDRAILS["injection_score_threshold"]:
        reason = f"Potential prompt injection detected (score={injection_score:.2f})"
        print(f"[GUARDRAILS] Input BLOCKED: {reason}")
        return GuardrailResult(False, reason, injection_score)

    # Check for PII in input (warn but don't block)
    pii_found = []
    if GUARDRAILS["pii_block"]:
        for pii_type, pattern in PII_PATTERNS.items():
            if re.search(pattern, text):
                pii_found.append(pii_type)

    if pii_found:
        print(f"[GUARDRAILS] Input WARNING: PII detected ({', '.join(pii_found)})")
        # Don't block input PII - user might be asking about their own data
        # But log it for audit

    print(f"[GUARDRAILS] Input check: PASS (injection_score={injection_score:.2f})")
    return GuardrailResult(True, "OK", injection_score)


def check_output_guardrails(output: str, context: str = "") -> GuardrailResult:
    """
    Check output text for safety issues.
    Checks: PII leakage, hallucination signals, length.
    """
    print(f"[GUARDRAILS] Checking output ({len(output)} chars)...")

    # Check length
    if len(output) > GUARDRAILS["max_output_length"]:
        print("[GUARDRAILS] Output BLOCKED: exceeds max length")
        return GuardrailResult(False, "Output too long", 1.0)

    # Check for PII leakage in output
    pii_found = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, output):
            pii_found.append(pii_type)

    if pii_found:
        reason = f"PII detected in output: {', '.join(pii_found)}"
        print(f"[GUARDRAILS] Output BLOCKED: {reason}")
        return GuardrailResult(False, reason, 0.9)

    # Basic hallucination check: if context provided, check output doesn't
    # contain claims about numbers/dates not in context
    hallucination_score = 0.0
    if context:
        # Extract numbers from output that aren't in context
        output_numbers = set(re.findall(r'\$[\d,.]+|\b\d+\.?\d*%?\b', output))
        context_numbers = set(re.findall(r'\$[\d,.]+|\b\d+\.?\d*%?\b', context))
        unsupported = output_numbers - context_numbers
        if unsupported and len(unsupported) > 2:
            hallucination_score = 0.3 * len(unsupported)

    print(f"[GUARDRAILS] Output check: PASS (hallucination_score={hallucination_score:.2f})")
    return GuardrailResult(True, "OK", hallucination_score)
