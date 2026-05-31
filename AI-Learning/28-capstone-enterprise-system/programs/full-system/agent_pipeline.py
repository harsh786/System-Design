"""
Agent Pipeline.
Query decomposition → Tool execution → Evidence evaluation → Synthesis.
"""

from config import USE_REAL_LLM, MODELS, PROMPTS
from tools import execute_tool
from evaluation import evaluate_response


def run_agent_pipeline(query: str, user_context: dict = None) -> dict:
    """
    Execute the agent pipeline for complex multi-step queries.
    Returns: {answer, steps, evidence, confidence, tokens, model}
    """
    print("[AGENT] Starting agent pipeline")

    # Step 1: Decompose query into sub-tasks
    print("[AGENT] Decomposing query into steps...")
    plan = decompose_query(query)
    print(f"[AGENT] Plan ({len(plan)} steps):")
    for i, step in enumerate(plan, 1):
        print(f"  Step {i}: {step['action']} - {step['description']}")

    # Step 2: Execute each step
    evidence = []
    total_input_tokens = 100  # Base overhead
    total_output_tokens = 0

    for i, step in enumerate(plan):
        print(f"[AGENT] Executing step {i+1}: {step['action']}({step.get('args', {})})")
        result = execute_step(step)
        evidence.append(result)
        total_input_tokens += 50  # Per-step overhead
        total_output_tokens += 30

    # Step 3: Check evidence sufficiency
    sufficient = check_evidence_sufficiency(query, evidence)
    print(f"[AGENT] Evidence sufficient: {'YES' if sufficient else 'NO'}")

    if not sufficient:
        # Try one more retrieval
        print("[AGENT] Attempting additional retrieval...")
        extra = execute_tool("vector_search", query=query)
        evidence.append(extra)

    # Step 4: Synthesize final answer
    print("[AGENT] Synthesizing final answer...")
    if USE_REAL_LLM:
        answer = _synthesize_with_openai(query, evidence)
    else:
        answer = _simulate_agent_response(query, evidence)

    total_output_tokens += len(answer.split())

    # Step 5: Evaluate
    context = "\n".join(str(e) for e in evidence)
    eval_result = evaluate_response(
        query=query,
        response=answer,
        context=context,
        retrieval_scores=[0.7, 0.8],  # Simulated
    )

    if eval_result.should_abstain:
        answer = (
            "I was unable to gather sufficient evidence to provide a reliable answer "
            "to this complex question. The available data may be incomplete."
        )

    return {
        "answer": answer,
        "steps": [{"action": s["action"], "description": s["description"]} for s in plan],
        "evidence_count": len(evidence),
        "confidence": eval_result.confidence,
        "tokens": {"input": total_input_tokens, "output": total_output_tokens},
        "model": MODELS["complex"]["name"],
    }


def decompose_query(query: str) -> list[dict]:
    """
    Decompose a complex query into executable steps.
    In production, an LLM would do this. Here we use heuristics.
    """
    query_lower = query.lower()
    steps = []

    # Pattern: comparison queries
    if "compare" in query_lower:
        # Extract what to compare
        if "q1" in query_lower and "q3" in query_lower:
            steps = [
                {"action": "vector_search", "description": "Retrieve Q1 data", "args": {"query": "Q1 2024 revenue financial results"}},
                {"action": "vector_search", "description": "Retrieve Q3 data", "args": {"query": "Q3 2024 revenue financial results"}},
                {"action": "calculator", "description": "Calculate difference", "args": {"expression": "4.2 - 3.1"}},
                {"action": "synthesize", "description": "Analyze trend and explain"},
            ]
        else:
            steps = [
                {"action": "vector_search", "description": "Retrieve first entity data", "args": {"query": query}},
                {"action": "vector_search", "description": "Retrieve second entity data", "args": {"query": query}},
                {"action": "synthesize", "description": "Compare and analyze"},
            ]

    # Pattern: trend analysis
    elif "trend" in query_lower or "growth" in query_lower:
        steps = [
            {"action": "sql_query", "description": "Get historical data", "args": {"query_description": "revenue by quarter"}},
            {"action": "calculator", "description": "Calculate growth rates", "args": {"expression": "(4.2 - 3.1) / 3.1 * 100"}},
            {"action": "synthesize", "description": "Explain the trend"},
        ]

    # Pattern: recommendation/evaluation
    elif "recommend" in query_lower or "should" in query_lower:
        steps = [
            {"action": "vector_search", "description": "Gather relevant context", "args": {"query": query}},
            {"action": "vector_search", "description": "Find related policies/guidelines", "args": {"query": "policy guidelines best practices"}},
            {"action": "synthesize", "description": "Form recommendation with evidence"},
        ]

    # Default: search + synthesize
    else:
        steps = [
            {"action": "vector_search", "description": "Primary search", "args": {"query": query}},
            {"action": "vector_search", "description": "Supporting search", "args": {"query": f"details about {query[:50]}"}},
            {"action": "synthesize", "description": "Synthesize comprehensive answer"},
        ]

    return steps


def execute_step(step: dict) -> dict:
    """Execute a single plan step."""
    action = step["action"]
    args = step.get("args", {})

    if action == "synthesize":
        return {"action": "synthesize", "note": "Will synthesize in final step"}

    if action == "vector_search":
        return execute_tool("vector_search", **args)
    elif action == "calculator":
        return execute_tool("calculator", **args)
    elif action == "sql_query":
        return execute_tool("sql_query", **args)
    elif action == "get_current_info":
        return execute_tool("get_current_info", **args)
    else:
        return {"action": action, "error": f"Unknown action: {action}"}


def check_evidence_sufficiency(query: str, evidence: list[dict]) -> bool:
    """Check if we have enough evidence to answer the query."""
    # Heuristic: need at least 2 pieces of actual evidence (not synthesize placeholders)
    real_evidence = [e for e in evidence if e.get("action") != "synthesize" and "error" not in e]
    return len(real_evidence) >= 2


def _synthesize_with_openai(query: str, evidence: list[dict]) -> str:
    """Synthesize answer using OpenAI."""
    from openai import OpenAI
    from config import OPENAI_API_KEY

    evidence_text = "\n".join(str(e) for e in evidence)
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=MODELS["complex"]["name"],
        temperature=MODELS["complex"]["temperature"],
        max_tokens=MODELS["complex"]["max_tokens"],
        messages=[
            {"role": "system", "content": PROMPTS["system_agent"]},
            {"role": "user", "content": f"Evidence:\n{evidence_text}\n\nQuestion: {query}\n\nSynthesize a comprehensive answer."},
        ],
    )
    return response.choices[0].message.content


def _simulate_agent_response(query: str, evidence: list[dict]) -> str:
    """Simulate agent response based on gathered evidence."""
    query_lower = query.lower()

    if "compare" in query_lower and "q1" in query_lower and "q3" in query_lower:
        return (
            "Comparing NovaTech's Q1 and Q3 2024 performance:\n\n"
            "**Revenue Growth**: Q1 revenue was $3.1M, growing to $4.2M in Q3 — "
            "a 35.5% increase over two quarters ($1.1M absolute growth).\n\n"
            "**Trend Analysis**: The growth accelerated quarter-over-quarter "
            "(Q1→Q2: +16%, Q2→Q3: +17%), suggesting strong momentum rather than "
            "a one-time spike.\n\n"
            "**Key Drivers**:\n"
            "- NovaAssist (flagship): $1.8M → $2.4M (+33%)\n"
            "- Enterprise customer growth: 180 → 220 (+22%)\n"
            "- NovaGuard Enterprise tier launch in Q2 added new revenue stream\n\n"
            "**Conclusion**: NovaTech shows healthy, accelerating growth driven by "
            "enterprise expansion and product-line maturation. "
            "[Sources: doc_financial_q1, doc_financial_q3, calculator]"
        )

    elif "trend" in query_lower:
        return (
            "NovaTech revenue trend (2024): Q1 $3.1M → Q2 $3.6M → Q3 $4.2M.\n\n"
            "Growth rate: ~16-17% quarter-over-quarter, indicating consistent acceleration. "
            "At this rate, Q4 projection would be approximately $4.9M. "
            "The trend is driven by enterprise customer acquisition and product expansion. "
            "[Sources: financial data, calculator]"
        )

    else:
        # Generic complex response
        evidence_summary = []
        for e in evidence:
            if isinstance(e, dict) and "results" in e:
                for r in e["results"][:2]:
                    evidence_summary.append(r.get("text", "")[:100])

        context = " | ".join(evidence_summary) if evidence_summary else "Limited evidence available"
        return (
            f"Based on analysis of multiple sources:\n\n"
            f"The available evidence suggests: {context[:300]}...\n\n"
            f"This analysis considered {len(evidence)} data points from the knowledge base. "
            f"[Sources: multiple documents]"
        )
