"""
RAG Pipeline.
Embedding → Vector Search → Rerank → Generate → Evaluate.
"""

from config import USE_REAL_LLM, MODELS, PROMPTS
from knowledge_base import knowledge_base
from evaluation import evaluate_response


def run_rag_pipeline(query: str, user_context: dict = None) -> dict:
    """
    Execute the full RAG pipeline.
    Returns: {answer, sources, confidence, tokens, model}
    """
    print("[RAG] Starting RAG pipeline")

    # Step 1: Embed query (ChromaDB handles this internally)
    print("[RAG] Embedding query...")

    # Step 2: Vector search
    print("[RAG] Performing vector search...")
    results = knowledge_base.search(query, n_results=5)
    print(f"[RAG] Found {len(results)} candidates")

    if not results:
        return {
            "answer": "I couldn't find any relevant information in the knowledge base.",
            "sources": [],
            "confidence": 0.1,
            "tokens": {"input": 50, "output": 20},
            "model": MODELS["medium"]["name"],
        }

    # Step 3: Rerank by score
    print("[RAG] Reranking results...")
    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    top_results = ranked[:3]
    retrieval_scores = [r["score"] for r in top_results]
    print(f"[RAG] Top scores: {[f'{s:.3f}' for s in retrieval_scores]}")

    # Step 4: Assemble context
    context_parts = []
    sources = []
    for r in top_results:
        context_parts.append(f"[{r['id']}]: {r['text']}")
        sources.append({"id": r["id"], "score": r["score"], "topic": r["metadata"].get("topic", "")})

    context = "\n\n".join(context_parts)

    # Step 5: Generate response
    print("[RAG] Generating grounded response...")
    if USE_REAL_LLM:
        answer = _generate_with_openai(query, context)
    else:
        answer = _simulate_rag_response(query, top_results)

    # Step 6: Evaluate
    eval_result = evaluate_response(
        query=query,
        response=answer,
        context=context,
        retrieval_scores=retrieval_scores,
    )

    # If should abstain, replace answer
    if eval_result.should_abstain:
        answer = (
            "I don't have sufficient information to answer this reliably. "
            "The knowledge base doesn't contain enough relevant information for this query."
        )

    # Estimate tokens (simulated)
    input_tokens = len(context.split()) + len(query.split()) + 50  # prompt overhead
    output_tokens = len(answer.split())

    return {
        "answer": answer,
        "sources": sources,
        "confidence": eval_result.confidence,
        "faithful": eval_result.faithful,
        "tokens": {"input": input_tokens, "output": output_tokens},
        "model": MODELS["medium"]["name"],
    }


def _generate_with_openai(query: str, context: str) -> str:
    """Generate response using OpenAI API."""
    from openai import OpenAI
    from config import OPENAI_API_KEY

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=MODELS["medium"]["name"],
        temperature=MODELS["medium"]["temperature"],
        max_tokens=MODELS["medium"]["max_tokens"],
        messages=[
            {"role": "system", "content": PROMPTS["system_rag"]},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )
    return response.choices[0].message.content


def _simulate_rag_response(query: str, results: list[dict]) -> str:
    """Simulate a RAG response based on retrieved documents."""
    query_lower = query.lower()

    # Check if results are relevant enough
    if not results or results[0]["score"] < 0.3:
        return "I don't have sufficient information to answer this question based on the available knowledge base."

    top_doc = results[0]
    doc_text = top_doc["text"]

    # Generate contextual answer based on query type
    if "revenue" in query_lower and "q3" in query_lower:
        return (
            "NovaTech's Q3 2024 revenue was $4.2M, representing a 17% increase quarter-over-quarter "
            "and 35% year-over-year growth. This was a record quarter driven by enterprise expansion, "
            "with the customer count reaching 220. [Source: doc_financial_q3]"
        )
    elif "revenue" in query_lower and "q1" in query_lower:
        return (
            "NovaTech's Q1 2024 revenue was $3.1M, up 12% year-over-year. "
            "NovaAssist contributed $1.8M, NovaAnalytics $0.9M, and NovaGuard $0.4M. "
            "[Source: doc_financial_q1]"
        )
    elif "revenue" in query_lower:
        return (
            "NovaTech's most recent reported revenue (Q3 2024) was $4.2M. "
            "The company has shown consistent growth: Q1 $3.1M → Q2 $3.6M → Q3 $4.2M. "
            "[Source: doc_financial_q3, doc_financial_q2, doc_financial_q1]"
        )
    elif "product" in query_lower:
        return (
            "NovaTech has three main products: (1) NovaAssist - AI customer service platform "
            "(flagship, 200+ customers), (2) NovaAnalytics - BI with natural language, "
            "(3) NovaGuard - AI security monitoring. [Source: doc_products]"
        )
    elif "roadmap" in query_lower or "2025" in query_lower:
        return (
            "NovaTech's 2025 roadmap includes: Q1 - NovaAssist v3.0 with multi-modal support, "
            "Q2 - NovaAnalytics streaming, Q3 - NovaGuard autonomous response, "
            "Q4 - New product NovaDev (AI coding assistant). $5M R&D investment planned. "
            "[Source: doc_roadmap]"
        )
    elif "remote" in query_lower or "work from home" in query_lower:
        return (
            "NovaTech uses a hybrid model: 2 days minimum in office. Remote exceptions for "
            "senior engineers (L5+). Home office stipend: $2,000/year. Internet reimbursement: "
            "$100/month. [Source: doc_policies_remote]"
        )
    elif "stock" in query_lower or "price" in query_lower or "predict" in query_lower:
        return (
            "I don't have information about NovaTech's stock price predictions. "
            "The knowledge base contains historical financial data but not forward-looking "
            "stock price estimates."
        )
    else:
        # Generic response using top document
        return f"Based on the knowledge base: {doc_text[:200]}... [Source: {top_doc['id']}]"
