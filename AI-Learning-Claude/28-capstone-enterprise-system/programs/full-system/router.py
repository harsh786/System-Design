"""
Model Router.
Classifies query complexity and routes to appropriate pipeline.
"""

import re
from config import ROUTING, MODELS, USE_REAL_LLM, PROMPTS
from rag_pipeline import run_rag_pipeline
from agent_pipeline import run_agent_pipeline


def classify_complexity(query: str) -> str:
    """
    Classify query into: simple, medium, complex.
    Uses heuristics (production would use a small classifier model).
    """
    query_lower = query.lower().strip()
    query_length = len(query_lower)

    # Check for complex keywords
    for keyword in ROUTING["complex_keywords"]:
        if keyword in query_lower:
            print(f"[ROUTER] Complexity signal: complex keyword '{keyword}'")
            return "complex"

    # Check for simple patterns
    if query_length <= ROUTING["simple_max_length"]:
        for keyword in ROUTING["simple_keywords"]:
            if keyword in query_lower:
                print(f"[ROUTER] Complexity signal: simple keyword '{keyword}'")
                return "simple"

    # Length-based heuristic
    if query_length >= ROUTING["complex_min_length"]:
        return "complex"

    # Check if it seems to need knowledge (mentions specific entities)
    entity_patterns = [
        r"novatech", r"nova\s*(assist|analytics|guard)",
        r"q[1-4]", r"revenue", r"financial", r"roadmap",
        r"policy", r"team", r"employee",
    ]
    for pattern in entity_patterns:
        if re.search(pattern, query_lower):
            return "medium"

    # Default: simple for short, medium for longer
    if query_length < 60:
        return "simple"
    return "medium"


def route_query(query: str, user_context: dict = None, session_id: str = None) -> dict:
    """
    Route a query to the appropriate pipeline based on complexity.
    Returns the complete response dict.
    """
    complexity = classify_complexity(query)
    print(f"[ROUTER] Classifying complexity... → {complexity.upper()}")

    if complexity == "simple":
        return _handle_simple(query, user_context)
    elif complexity == "medium":
        return _handle_medium(query, user_context)
    else:
        return _handle_complex(query, user_context)


def _handle_simple(query: str, user_context: dict = None) -> dict:
    """Handle simple queries with direct LLM call."""
    print("[SIMPLE] Processing with direct LLM call")

    if USE_REAL_LLM:
        answer = _call_openai_simple(query)
    else:
        answer = _simulate_simple(query)

    input_tokens = len(query.split()) + 20
    output_tokens = len(answer.split())

    return {
        "answer": answer,
        "route": "simple",
        "confidence": 0.95,
        "sources": [],
        "tokens": {"input": input_tokens, "output": output_tokens},
        "model": MODELS["simple"]["name"],
    }


def _handle_medium(query: str, user_context: dict = None) -> dict:
    """Handle medium queries with RAG pipeline."""
    result = run_rag_pipeline(query, user_context)
    result["route"] = "medium"
    return result


def _handle_complex(query: str, user_context: dict = None) -> dict:
    """Handle complex queries with agent pipeline."""
    result = run_agent_pipeline(query, user_context)
    result["route"] = "complex"
    return result


def _call_openai_simple(query: str) -> str:
    """Call OpenAI for simple queries."""
    from openai import OpenAI
    from config import OPENAI_API_KEY

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=MODELS["simple"]["name"],
        temperature=MODELS["simple"]["temperature"],
        max_tokens=MODELS["simple"]["max_tokens"],
        messages=[
            {"role": "system", "content": PROMPTS["system_simple"]},
            {"role": "user", "content": query},
        ],
    )
    return response.choices[0].message.content


def _simulate_simple(query: str) -> str:
    """Simulate response for simple queries."""
    query_lower = query.lower()

    # Math
    if any(op in query for op in ["+", "-", "*", "/"]) or "calculate" in query_lower:
        # Try to extract and solve simple math
        match = re.search(r"(\d+)\s*([+\-*/])\s*(\d+)", query)
        if match:
            a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
            result = eval(f"{a}{op}{b}")
            return f"{a} {op} {b} equals {result}."
        return "I can help with calculations. Please provide a specific expression."

    # Greetings
    if any(w in query_lower for w in ["hello", "hi", "hey"]):
        return "Hello! I'm the NovaTech AI assistant. How can I help you today?"

    if "what is" in query_lower and len(query_lower) < 40:
        # Simple definition-type questions
        return f"That's a great question. Let me provide a concise answer based on general knowledge."

    if "thank" in query_lower:
        return "You're welcome! Let me know if you have any other questions."

    return "I can help with that. Could you provide more details about what you'd like to know?"
