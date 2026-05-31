"""
RAG vs Long-Context Benchmark Simulator
========================================
Simulates comparing RAG retrieval vs context-stuffing approaches
across different query types, measuring accuracy, latency, cost, and tokens.

Run: python3 main.py
No dependencies required.
"""

import dataclasses
import hashlib
import math
import random
import time
from typing import Optional


random.seed(42)


@dataclasses.dataclass
class Document:
    """Simulated document in the knowledge base."""
    id: str
    title: str
    content: str
    tokens: int
    topic: str
    key_facts: list  # Facts that can be queried


@dataclasses.dataclass
class Query:
    """A test query with known ground truth."""
    text: str
    query_type: str  # "factoid", "synthesis", "comparison", "multi_hop"
    relevant_doc_ids: list
    ground_truth: str
    requires_cross_reference: bool = False


@dataclasses.dataclass
class RetrievalResult:
    """Result from simulated retrieval."""
    doc_id: str
    chunk_text: str
    relevance_score: float
    is_correct_doc: bool


@dataclasses.dataclass
class BenchmarkResult:
    """Result of running a query through an approach."""
    query: Query
    approach: str
    accuracy: float  # 0.0 to 1.0
    latency_ms: float
    cost_usd: float
    tokens_used: int
    correct: bool


def generate_knowledge_base(n_docs: int = 50) -> list:
    """Generate a simulated knowledge base with interconnected documents."""
    topics = [
        "distributed_systems", "machine_learning", "databases",
        "networking", "security", "cloud_architecture",
        "data_engineering", "api_design", "monitoring", "caching"
    ]
    
    docs = []
    for i in range(n_docs):
        topic = topics[i % len(topics)]
        doc_id = f"doc_{i:03d}"
        title = f"{topic.replace('_', ' ').title()} - Document {i}"
        
        # Generate content with embedded facts
        facts = [
            f"Fact_{i}_A: The {topic} system handles {random.randint(1000, 100000)} requests per second.",
            f"Fact_{i}_B: Latency p99 is {random.randint(5, 500)}ms under load.",
            f"Fact_{i}_C: The recommended approach uses {random.choice(['sharding', 'replication', 'caching', 'batching'])}.",
        ]
        
        # Some docs reference other docs (for cross-reference queries)
        if i > 5:
            ref_doc = random.randint(0, i - 1)
            facts.append(f"Fact_{i}_D: This extends the approach described in doc_{ref_doc:03d}.")
        
        content = f"# {title}\n\n" + "\n".join(facts) + "\n" + "Background context. " * random.randint(50, 200)
        tokens = len(content) // 4
        
        docs.append(Document(
            id=doc_id,
            title=title,
            content=content,
            tokens=tokens,
            topic=topic,
            key_facts=facts,
        ))
    
    return docs


def generate_queries(docs: list, n_queries: int = 20) -> list:
    """Generate test queries of varying complexity."""
    queries = []
    
    # Simple factoid queries (RAG should handle well)
    for i in range(5):
        doc = docs[random.randint(0, len(docs) - 1)]
        queries.append(Query(
            text=f"What is the p99 latency for the {doc.topic} system?",
            query_type="factoid",
            relevant_doc_ids=[doc.id],
            ground_truth=doc.key_facts[1],
        ))
    
    # Synthesis queries (need multiple docs, long-context excels)
    for i in range(5):
        topic = ["distributed_systems", "machine_learning", "databases"][i % 3]
        relevant = [d for d in docs if d.topic == topic][:5]
        queries.append(Query(
            text=f"Summarize all approaches to {topic.replace('_', ' ')} across our documentation.",
            query_type="synthesis",
            relevant_doc_ids=[d.id for d in relevant],
            ground_truth="Synthesis of multiple documents required.",
            requires_cross_reference=True,
        ))
    
    # Comparison queries (need side-by-side analysis)
    for i in range(5):
        doc_a = docs[i * 3]
        doc_b = docs[i * 3 + 1]
        queries.append(Query(
            text=f"Compare the approaches in '{doc_a.title}' vs '{doc_b.title}'.",
            query_type="comparison",
            relevant_doc_ids=[doc_a.id, doc_b.id],
            ground_truth="Detailed comparison needed.",
            requires_cross_reference=True,
        ))
    
    # Multi-hop queries (need to follow references)
    for i in range(5):
        doc = docs[random.randint(10, len(docs) - 1)]
        # Find docs that reference other docs
        queries.append(Query(
            text=f"What approach does {doc.title} extend, and what are the differences?",
            query_type="multi_hop",
            relevant_doc_ids=[doc.id, f"doc_{random.randint(0, 9):03d}"],
            ground_truth="Must follow cross-references.",
            requires_cross_reference=True,
        ))
    
    return queries


def simulate_rag_retrieval(query: Query, docs: list, top_k: int = 5) -> list:
    """
    Simulate RAG retrieval with realistic accuracy characteristics.
    
    RAG retrieval is good at finding relevant docs for specific queries
    but can miss documents for synthesis/comparison/multi-hop queries.
    """
    results = []
    
    # Simulate embedding similarity - relevant docs get higher scores
    for doc in docs:
        if doc.id in query.relevant_doc_ids:
            # Relevant doc: high score but not always retrieved (simulates misses)
            base_score = random.uniform(0.75, 0.98)
            # Factoid queries: high retrieval accuracy
            # Complex queries: lower retrieval accuracy
            if query.query_type == "factoid":
                score = base_score
            elif query.query_type == "synthesis":
                score = base_score * random.uniform(0.6, 0.9)  # May miss some
            else:
                score = base_score * random.uniform(0.5, 0.85)  # Harder to retrieve
        else:
            # Irrelevant doc: low score but occasionally appears (noise)
            score = random.uniform(0.1, 0.55)
        
        # Simulate chunking: only return a chunk, not full doc
        chunk = doc.content[:512]  # Arbitrary 512-char chunk
        results.append(RetrievalResult(
            doc_id=doc.id,
            chunk_text=chunk,
            relevance_score=score,
            is_correct_doc=(doc.id in query.relevant_doc_ids),
        ))
    
    # Sort by score and return top-k
    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results[:top_k]


def simulate_rag_approach(query: Query, docs: list) -> BenchmarkResult:
    """
    Simulate full RAG pipeline: embed query → retrieve → generate.
    
    Characteristics:
    - Fast (retrieval + short context generation)
    - Cheap (small context window)
    - Good for factoid, weaker for synthesis
    """
    start = time.time()
    
    # Simulate retrieval latency (embedding + vector search + reranking)
    time.sleep(random.uniform(0.01, 0.03))  # Simulated 10-30ms
    
    retrieved = simulate_rag_retrieval(query, docs, top_k=5)
    
    # Calculate accuracy based on retrieval quality
    correct_retrieved = sum(1 for r in retrieved if r.is_correct_doc)
    total_relevant = len(query.relevant_doc_ids)
    recall = correct_retrieved / total_relevant if total_relevant > 0 else 0
    
    # Accuracy depends on query type and retrieval quality
    if query.query_type == "factoid":
        # If we retrieved the right doc, high accuracy
        accuracy = 0.90 * recall + 0.05
    elif query.query_type == "synthesis":
        # Need multiple docs; partial retrieval = partial accuracy
        accuracy = 0.60 * recall + 0.15  # Cap lower due to chunk boundaries
    elif query.query_type == "comparison":
        # Need both docs side by side
        accuracy = 0.70 * recall + 0.10
    else:  # multi_hop
        # Need to follow references; chunking breaks this
        accuracy = 0.50 * recall + 0.10
    
    # Add noise
    accuracy = min(1.0, max(0.0, accuracy + random.uniform(-0.05, 0.05)))
    
    # Token usage: short context (retrieved chunks + query)
    tokens_used = sum(len(r.chunk_text) // 4 for r in retrieved) + len(query.text) // 4 + 500  # system prompt
    
    # Cost: embedding ($0.0001) + generation (tokens × $3/M)
    cost = 0.0001 + tokens_used * 3.0 / 1_000_000
    
    # Latency: retrieval (30ms) + generation (~200ms for short context)
    latency = 30 + random.uniform(150, 300)
    
    elapsed = time.time() - start
    
    return BenchmarkResult(
        query=query,
        approach="RAG",
        accuracy=accuracy,
        latency_ms=latency,
        cost_usd=cost,
        tokens_used=tokens_used,
        correct=(accuracy > 0.7),
    )


def simulate_longcontext_approach(query: Query, docs: list) -> BenchmarkResult:
    """
    Simulate long-context approach: load all relevant docs fully into context.
    
    Characteristics:
    - Slow (large context = slow prefill)
    - Expensive (many tokens)
    - Excellent for synthesis/comparison (full context available)
    - Subject to lost-in-the-middle for very long contexts
    """
    # Load ALL docs into context (simulating stuffing the full knowledge base)
    total_tokens = sum(d.tokens for d in docs)
    
    # Accuracy: generally higher because full context is available
    # But degrades with context length (lost-in-the-middle)
    relevant_count = len(query.relevant_doc_ids)
    
    if query.query_type == "factoid":
        # For simple factoid with full context, very high accuracy
        # But slight penalty for needle-in-haystack at scale
        base_accuracy = 0.93
        length_penalty = min(0.1, total_tokens / 5_000_000)  # Degrades with context size
        accuracy = base_accuracy - length_penalty
    elif query.query_type == "synthesis":
        # Long context excels at synthesis - can see all docs simultaneously
        accuracy = 0.92
    elif query.query_type == "comparison":
        # Can do side-by-side comparison with full context
        accuracy = 0.90
    else:  # multi_hop
        # Can follow references within context
        accuracy = 0.85
    
    accuracy = min(1.0, max(0.0, accuracy + random.uniform(-0.03, 0.03)))
    
    # Cost: all tokens at input price
    cost = total_tokens * 3.0 / 1_000_000
    
    # Latency: proportional to context length
    # ~10ms per 1K tokens for prefill + generation time
    latency = (total_tokens / 1000) * 10 + random.uniform(200, 500)
    
    return BenchmarkResult(
        query=query,
        approach="Long-Context",
        accuracy=accuracy,
        latency_ms=latency,
        cost_usd=cost,
        tokens_used=total_tokens,
        correct=(accuracy > 0.7),
    )


def simulate_hybrid_approach(query: Query, docs: list) -> BenchmarkResult:
    """
    Simulate hybrid: RAG retrieval + load full docs of top results into long context.
    
    Characteristics:
    - Medium latency (retrieval + medium context generation)
    - Medium cost (only relevant docs in full)
    - Best accuracy (retrieval precision + reasoning depth)
    """
    # Retrieve candidates
    retrieved = simulate_rag_retrieval(query, docs, top_k=10)
    
    # Load full documents for top-5 retrieved (not just chunks)
    top_doc_ids = [r.doc_id for r in retrieved[:5]]
    loaded_docs = [d for d in docs if d.id in top_doc_ids]
    context_tokens = sum(d.tokens for d in loaded_docs) + 500  # + system prompt
    
    # Accuracy: combines retrieval precision with full-doc reasoning
    correct_loaded = sum(1 for d in loaded_docs if d.id in query.relevant_doc_ids)
    total_relevant = len(query.relevant_doc_ids)
    recall = correct_loaded / total_relevant if total_relevant > 0 else 0
    
    if query.query_type == "factoid":
        accuracy = 0.92 * recall + 0.05
    elif query.query_type == "synthesis":
        # Better than RAG because full docs loaded; slightly worse than full long-context
        # because might miss some docs in retrieval
        accuracy = 0.85 * recall + 0.10
    elif query.query_type == "comparison":
        accuracy = 0.88 * recall + 0.08
    else:  # multi_hop
        accuracy = 0.80 * recall + 0.10
    
    accuracy = min(1.0, max(0.0, accuracy + random.uniform(-0.03, 0.03)))
    
    # Cost: retrieval ($0.001) + context tokens at input price
    cost = 0.001 + context_tokens * 3.0 / 1_000_000
    
    # Latency: retrieval (50ms) + reranking (100ms) + generation with medium context
    latency = 50 + 100 + (context_tokens / 1000) * 10 + random.uniform(200, 400)
    
    return BenchmarkResult(
        query=query,
        approach="Hybrid",
        accuracy=accuracy,
        latency_ms=latency,
        cost_usd=cost,
        tokens_used=context_tokens,
        correct=(accuracy > 0.7),
    )


def run_benchmark(docs: list, queries: list) -> dict:
    """Run all queries through all three approaches."""
    results = {"RAG": [], "Long-Context": [], "Hybrid": []}
    
    for query in queries:
        results["RAG"].append(simulate_rag_approach(query, docs))
        results["Long-Context"].append(simulate_longcontext_approach(query, docs))
        results["Hybrid"].append(simulate_hybrid_approach(query, docs))
    
    return results


def print_comparison_report(results: dict, queries: list):
    """Print comprehensive comparison report."""
    print("=" * 80)
    print("RAG vs LONG-CONTEXT vs HYBRID BENCHMARK REPORT")
    print("=" * 80)
    
    # Overall metrics
    print("\n" + "-" * 80)
    print("OVERALL METRICS")
    print("-" * 80)
    print(f"{'Metric':<25} {'RAG':>15} {'Long-Context':>15} {'Hybrid':>15}")
    print("-" * 80)
    
    for approach in ["RAG", "Long-Context", "Hybrid"]:
        r = results[approach]
        avg_accuracy = sum(x.accuracy for x in r) / len(r)
        avg_latency = sum(x.latency_ms for x in r) / len(r)
        avg_cost = sum(x.cost_usd for x in r) / len(r)
        avg_tokens = sum(x.tokens_used for x in r) / len(r)
        correct_pct = sum(1 for x in r if x.correct) / len(r) * 100
        
        if approach == "RAG":
            print(f"{'Avg Accuracy':<25} {avg_accuracy:>14.1%} {'-':>15} {'-':>15}")
        elif approach == "Long-Context":
            avg_acc_rag = sum(x.accuracy for x in results['RAG']) / len(results['RAG'])
            print(f"{'Avg Accuracy':<25} {avg_acc_rag:>14.1%} {avg_accuracy:>14.1%} {'-':>15}")
        else:
            avg_acc_rag = sum(x.accuracy for x in results['RAG']) / len(results['RAG'])
            avg_acc_lc = sum(x.accuracy for x in results['Long-Context']) / len(results['Long-Context'])
            print(f"{'Avg Accuracy':<25} {avg_acc_rag:>14.1%} {avg_acc_lc:>14.1%} {avg_accuracy:>14.1%}")
    
    # Print full metrics table
    print()
    for metric_name, metric_fn, fmt in [
        ("Avg Latency (ms)", lambda r: sum(x.latency_ms for x in r) / len(r), "{:>12.0f}ms"),
        ("Avg Cost ($)", lambda r: sum(x.cost_usd for x in r) / len(r), "{:>13.4f}"),
        ("Avg Tokens", lambda r: sum(x.tokens_used for x in r) / len(r), "{:>13,.0f}"),
        ("Correct (%)", lambda r: sum(1 for x in r if x.correct) / len(r) * 100, "{:>13.0f}%"),
    ]:
        vals = []
        for approach in ["RAG", "Long-Context", "Hybrid"]:
            vals.append(metric_fn(results[approach]))
        print(f"{metric_name:<25} {fmt.format(vals[0]):>15} {fmt.format(vals[1]):>15} {fmt.format(vals[2]):>15}")
    
    # Breakdown by query type
    print("\n" + "-" * 80)
    print("ACCURACY BY QUERY TYPE")
    print("-" * 80)
    print(f"{'Query Type':<20} {'RAG':>12} {'Long-Context':>14} {'Hybrid':>12} {'Winner':>12}")
    print("-" * 80)
    
    query_types = ["factoid", "synthesis", "comparison", "multi_hop"]
    for qt in query_types:
        accs = {}
        for approach in ["RAG", "Long-Context", "Hybrid"]:
            qt_results = [r for r in results[approach] if r.query.query_type == qt]
            if qt_results:
                accs[approach] = sum(r.accuracy for r in qt_results) / len(qt_results)
            else:
                accs[approach] = 0
        
        winner = max(accs, key=accs.get)
        print(f"{qt:<20} {accs['RAG']:>11.1%} {accs['Long-Context']:>13.1%} {accs['Hybrid']:>11.1%} {winner:>12}")
    
    # Cost-effectiveness analysis
    print("\n" + "-" * 80)
    print("COST-EFFECTIVENESS (Accuracy per Dollar)")
    print("-" * 80)
    
    for approach in ["RAG", "Long-Context", "Hybrid"]:
        r = results[approach]
        total_cost = sum(x.cost_usd for x in r)
        avg_accuracy = sum(x.accuracy for x in r) / len(r)
        cost_per_correct = total_cost / sum(1 for x in r if x.correct) if any(x.correct for x in r) else float('inf')
        print(f"  {approach:<15}: ${total_cost:.4f} total | {avg_accuracy:.1%} accuracy | ${cost_per_correct:.4f}/correct answer")
    
    # Recommendations
    print("\n" + "-" * 80)
    print("RECOMMENDATIONS")
    print("-" * 80)
    
    rag_acc = sum(x.accuracy for x in results['RAG']) / len(results['RAG'])
    lc_acc = sum(x.accuracy for x in results['Long-Context']) / len(results['Long-Context'])
    hybrid_acc = sum(x.accuracy for x in results['Hybrid']) / len(results['Hybrid'])
    
    rag_cost = sum(x.cost_usd for x in results['RAG']) / len(results['RAG'])
    lc_cost = sum(x.cost_usd for x in results['Long-Context']) / len(results['Long-Context'])
    hybrid_cost = sum(x.cost_usd for x in results['Hybrid']) / len(results['Hybrid'])
    
    print(f"""
  For SIMPLE FACTOID queries:
    → Use RAG (fast, cheap, sufficient accuracy)
    → Cost savings vs long-context: {(1 - rag_cost/lc_cost)*100:.0f}%
    
  For SYNTHESIS/COMPARISON queries:
    → Use Hybrid (best accuracy-cost balance)
    → Accuracy gain over RAG: +{(hybrid_acc - rag_acc)*100:.1f}%
    
  For COST-SENSITIVE workloads (>10K queries/day):
    → Route 80% to RAG, 20% complex queries to Hybrid
    → Estimated blended cost: ${0.8*rag_cost + 0.2*hybrid_cost:.4f}/query
    
  For ACCURACY-CRITICAL workloads (legal, medical, financial):
    → Use Hybrid for all queries
    → Consider Long-Context for small corpora with prompt caching

  BREAK-EVEN ANALYSIS:
    Long-Context justified when wrong-answer cost > ${(lc_cost - rag_cost) / (lc_acc - rag_acc + 0.001):.2f}
    Hybrid justified when wrong-answer cost > ${(hybrid_cost - rag_cost) / (hybrid_acc - rag_acc + 0.001):.2f}
    """)


def main():
    print("RAG vs Long-Context Benchmark Simulator")
    print("Comparing retrieval approaches across query types\n")
    
    # Generate knowledge base
    print("Generating simulated knowledge base...")
    docs = generate_knowledge_base(n_docs=50)
    total_tokens = sum(d.tokens for d in docs)
    print(f"  Documents: {len(docs)}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Topics: {len(set(d.topic for d in docs))}")
    
    # Generate queries
    print("\nGenerating test queries...")
    queries = generate_queries(docs, n_queries=20)
    print(f"  Total queries: {len(queries)}")
    for qt in ["factoid", "synthesis", "comparison", "multi_hop"]:
        count = sum(1 for q in queries if q.query_type == qt)
        print(f"    {qt}: {count}")
    
    # Run benchmark
    print("\nRunning benchmark (3 approaches × 20 queries = 60 evaluations)...")
    results = run_benchmark(docs, queries)
    
    # Print report
    print_comparison_report(results, queries)
    
    # Scale projections
    print("\n" + "-" * 80)
    print("SCALE PROJECTIONS (Daily Cost at Different Query Volumes)")
    print("-" * 80)
    
    rag_per_query = sum(x.cost_usd for x in results['RAG']) / len(results['RAG'])
    lc_per_query = sum(x.cost_usd for x in results['Long-Context']) / len(results['Long-Context'])
    hybrid_per_query = sum(x.cost_usd for x in results['Hybrid']) / len(results['Hybrid'])
    
    print(f"{'Queries/Day':<15} {'RAG':>12} {'Long-Context':>14} {'Hybrid':>12}")
    for volume in [100, 1000, 10000, 100000]:
        rag_daily = rag_per_query * volume
        lc_daily = lc_per_query * volume
        hybrid_daily = hybrid_per_query * volume
        print(f"{volume:<15,} ${rag_daily:>10.2f} ${lc_daily:>12.2f} ${hybrid_daily:>10.2f}")


if __name__ == "__main__":
    main()
