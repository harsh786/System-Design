"""
Agentic RAG Implementation
============================
An agent that decides: whether to search, what to search for,
evaluates results, refines queries, and abstains when uncertain.
"""

import os
import json
import time
import glob
from dotenv import load_dotenv
from openai import OpenAI
import chromadb

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o-mini"
MAX_RETRIEVAL_ATTEMPTS = 3


# ============================================================
# Build Knowledge Base
# ============================================================
def build_knowledge_base(docs_dir: str = "sample_docs") -> chromadb.Collection:
    """Load docs, chunk, embed, store."""
    chunks = []
    for filepath in glob.glob(os.path.join(docs_dir, "*.txt")):
        with open(filepath, "r") as f:
            content = f.read()
        source = os.path.basename(filepath)
        # Paragraph-based chunking
        paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 50]
        for i, para in enumerate(paragraphs):
            chunks.append({"text": para, "source": source, "id": f"chunk_{len(chunks)}"})

    print(f"📄 Built knowledge base: {len(chunks)} chunks from {docs_dir}")

    # Embed
    texts = [c["text"] for c in chunks]
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    embeddings = [item.embedding for item in response.data]

    # Store
    chroma_client = chromadb.Client()
    collection = chroma_client.create_collection("agentic_rag", metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c["source"]} for c in chunks],
    )
    return collection


# ============================================================
# Search Tool
# ============================================================
def search_knowledge_base(collection: chromadb.Collection, query: str, top_k: int = 5) -> list[dict]:
    """Search the knowledge base and return results with scores."""
    response = client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
    query_emb = response.data[0].embedding

    results = collection.query(query_embeddings=[query_emb], n_results=top_k)

    retrieved = []
    for i in range(len(results["ids"][0])):
        retrieved.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "similarity": 1 - results["distances"][0][i],
        })
    return retrieved


# ============================================================
# Agent: Decide Action
# ============================================================
def agent_decide(query: str, context_so_far: list[dict], attempt: int) -> dict:
    """
    Agent decides what to do next:
    - search: perform a retrieval with a specific search query
    - answer: generate final answer from accumulated context
    - abstain: not enough information to answer
    """
    context_summary = ""
    if context_so_far:
        context_summary = f"\n\nPrevious retrieval results (attempt {attempt}):\n"
        for c in context_so_far:
            context_summary += f"- [{c['source']}] (sim={c['similarity']:.3f}): {c['text'][:100]}...\n"

    decision_prompt = f"""You are a RAG agent. Given a user query and any previous retrieval results, decide your next action.

User Query: "{query}"
{context_summary}
Attempt: {attempt} of {MAX_RETRIEVAL_ATTEMPTS}

Respond with JSON:
{{
    "action": "search" | "answer" | "abstain",
    "reasoning": "why this action",
    "search_query": "what to search for (only if action=search)",
    "confidence": 0.0-1.0
}}

Rules:
- If you haven't searched yet, search with a well-crafted query
- If previous results are relevant, action=answer
- If previous results are irrelevant, try a different search_query
- If you've tried {MAX_RETRIEVAL_ATTEMPTS} times with poor results, abstain
- A query like "what is 2+2" doesn't need search — answer directly with confidence 1.0"""

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[{"role": "user", "content": decision_prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)


# ============================================================
# Agent: Evaluate Retrieved Results
# ============================================================
def agent_evaluate(query: str, results: list[dict]) -> dict:
    """Agent evaluates if retrieved results are sufficient to answer."""
    results_text = "\n".join([f"[{r['source']}] (sim={r['similarity']:.3f}): {r['text'][:200]}" for r in results])

    eval_prompt = f"""Evaluate if these retrieved documents can answer the query.

Query: "{query}"

Retrieved Documents:
{results_text}

Respond with JSON:
{{
    "sufficient": true/false,
    "relevant_count": number of relevant docs,
    "reasoning": "why sufficient or not",
    "suggested_refinement": "alternative search query if insufficient"
}}"""

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[{"role": "user", "content": eval_prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# ============================================================
# Agent: Generate Final Answer
# ============================================================
def agent_generate(query: str, context: list[dict], confidence: float) -> str:
    """Generate final answer with confidence indicator."""
    context_text = "\n\n---\n\n".join([f"[{c['source']}]: {c['text']}" for c in context])

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": f"""Answer based ONLY on the provided context. 
Your confidence level: {confidence:.0%}.
If confidence < 70%, caveat your answer.
Always cite sources."""},
            {"role": "user", "content": f"Context:\n{context_text}\n\n---\nQuestion: {query}"},
        ],
        temperature=0,
        max_tokens=400,
    )
    return response.choices[0].message.content


# ============================================================
# Agent Loop
# ============================================================
def run_agent(collection: chromadb.Collection, query: str):
    """Run the full agentic RAG loop."""
    print(f"\n{'='*60}")
    print(f"❓ User Query: {query}")
    print("=" * 60)

    accumulated_context = []
    attempt = 0

    while attempt < MAX_RETRIEVAL_ATTEMPTS:
        attempt += 1
        print(f"\n  🧠 Agent thinking (attempt {attempt}/{MAX_RETRIEVAL_ATTEMPTS})...")

        # Agent decides
        decision = agent_decide(query, accumulated_context, attempt)
        print(f"     Action: {decision['action']}")
        print(f"     Reasoning: {decision['reasoning']}")

        if decision["action"] == "answer":
            print(f"     Confidence: {decision['confidence']:.0%}")
            if accumulated_context:
                answer = agent_generate(query, accumulated_context, decision["confidence"])
            else:
                # Direct answer without retrieval
                response = client.chat.completions.create(
                    model=GENERATION_MODEL,
                    messages=[{"role": "user", "content": query}],
                    temperature=0,
                    max_tokens=200,
                )
                answer = response.choices[0].message.content
            print(f"\n  ✅ FINAL ANSWER (confidence: {decision['confidence']:.0%}):")
            print(f"     {answer}")
            return

        elif decision["action"] == "abstain":
            print(f"\n  ⛔ ABSTAINING: {decision['reasoning']}")
            print("     I don't have enough information to answer this question reliably.")
            return

        elif decision["action"] == "search":
            search_query = decision.get("search_query", query)
            print(f"     Search query: \"{search_query}\"")

            # Perform search
            results = search_knowledge_base(collection, search_query)
            print(f"     Found {len(results)} results")
            for i, r in enumerate(results[:3]):
                print(f"       [{i+1}] {r['source']} (sim={r['similarity']:.3f}): \"{r['text'][:60]}...\"")

            # Evaluate results
            evaluation = agent_evaluate(query, results)
            print(f"\n     📊 Evaluation: sufficient={evaluation['sufficient']}, relevant={evaluation['relevant_count']}")
            print(f"        {evaluation['reasoning']}")

            if evaluation["sufficient"]:
                # Filter to relevant results and generate
                relevant = [r for r in results if r["similarity"] > 0.3]
                accumulated_context.extend(relevant)
                answer = agent_generate(query, accumulated_context, 0.85)
                print(f"\n  ✅ FINAL ANSWER:")
                print(f"     {answer}")
                return
            else:
                # Keep top results and try again
                accumulated_context.extend([r for r in results[:2] if r["similarity"] > 0.4])

    # Exhausted attempts
    print(f"\n  ⚠️  Exhausted {MAX_RETRIEVAL_ATTEMPTS} attempts.")
    if accumulated_context:
        answer = agent_generate(query, accumulated_context, 0.4)
        print(f"  📝 Best-effort answer (LOW CONFIDENCE):\n     {answer}")
    else:
        print("  ⛔ Unable to find relevant information. Abstaining.")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("AGENTIC RAG DEMO")
    print("Agent decides: search? what for? enough info? try again?")
    print("=" * 60)

    collection = build_knowledge_base()

    # Test with various query types
    queries = [
        # Straightforward - should find and answer quickly
        "What is the disaster recovery RTO?",
        # Requires reasoning about which doc to search
        "Can I work from another country for 3 weeks?",
        # Out of scope - should abstain
        "What is the best restaurant near the Austin office?",
        # No retrieval needed
        "What is 15% of 200?",
        # Multi-faceted - may need multiple searches
        "How do I create a workflow via API and what happens if it fails?",
    ]

    for query in queries:
        run_agent(collection, query)
        print()


if __name__ == "__main__":
    main()
