"""
Context Budget Allocator
========================
Simulates intelligent context window packing for LLM requests.
Demonstrates how to allocate a finite token budget across competing
demands: system prompt, examples, retrieved docs, conversation history.

Run: python3 main.py
No dependencies required.
"""

import dataclasses
import enum
from typing import Optional


class Priority(enum.IntEnum):
    """Priority tiers for context components."""
    CRITICAL = 0      # Must include (system prompt, user query)
    HIGH = 1          # Strongly prefer (most relevant docs)
    MEDIUM = 2        # Include if space (recent history, supporting docs)
    LOW = 3           # Nice to have (examples, old history)
    EXPENDABLE = 4    # First to cut (metadata, verbose formatting)


@dataclasses.dataclass
class ContextItem:
    """A candidate item for inclusion in the context window."""
    name: str
    content: str
    token_count: int
    priority: Priority
    relevance_score: float  # 0.0 to 1.0
    compressible: bool = False
    compressed_content: Optional[str] = None
    compressed_tokens: Optional[int] = None

    @property
    def sort_key(self):
        """Lower is better (higher priority, higher relevance)."""
        return (self.priority, -self.relevance_score)


@dataclasses.dataclass
class AllocationResult:
    """Result of the budget allocation process."""
    included: list
    excluded: list
    compressed: list
    total_tokens_used: int
    budget_remaining: int
    utilization_pct: float


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English."""
    return max(1, len(text) // 4)


def create_sample_context_items() -> list:
    """Create realistic sample context items for demonstration."""
    items = []

    # System prompt (always critical)
    system_prompt = (
        "You are a senior software architect assistant. You help engineers "
        "design scalable systems. Always cite specific documents when available. "
        "Provide concrete numbers (latency, throughput, cost) not vague statements. "
        "If you're unsure, say so rather than speculating."
    )
    items.append(ContextItem(
        name="System Prompt",
        content=system_prompt,
        token_count=estimate_tokens(system_prompt),
        priority=Priority.CRITICAL,
        relevance_score=1.0,
    ))

    # User query (always critical)
    user_query = (
        "How should we architect our document search system to handle 100K documents "
        "with sub-second latency? We currently use pure RAG but accuracy is only 75%."
    )
    items.append(ContextItem(
        name="User Query",
        content=user_query,
        token_count=estimate_tokens(user_query),
        priority=Priority.CRITICAL,
        relevance_score=1.0,
    ))

    # Highly relevant retrieved documents
    doc1 = "Technical paper: Hybrid RAG architectures show 15-20% accuracy improvement " * 50
    items.append(ContextItem(
        name="Retrieved Doc: Hybrid RAG Paper",
        content=doc1,
        token_count=estimate_tokens(doc1),
        priority=Priority.HIGH,
        relevance_score=0.95,
        compressible=True,
        compressed_content="Hybrid RAG: 15-20% accuracy gain over pure RAG by combining retrieval with long-context reasoning.",
        compressed_tokens=25,
    ))

    doc2 = "Case study: Enterprise search at 100K docs, migrated from RAG to hybrid. " * 40
    items.append(ContextItem(
        name="Retrieved Doc: Enterprise Case Study",
        content=doc2,
        token_count=estimate_tokens(doc2),
        priority=Priority.HIGH,
        relevance_score=0.91,
        compressible=True,
        compressed_content="Enterprise case study: 100K docs, hybrid architecture achieved 92% accuracy at $0.15/query.",
        compressed_tokens=22,
    ))

    doc3 = "Benchmark results: Vector search latency at various scales. " * 30
    items.append(ContextItem(
        name="Retrieved Doc: Latency Benchmarks",
        content=doc3,
        token_count=estimate_tokens(doc3),
        priority=Priority.HIGH,
        relevance_score=0.87,
    ))

    # Medium priority: conversation history
    history1 = "User previously asked about vector database selection and was recommended Pinecone."
    items.append(ContextItem(
        name="History: Previous turn (vector DB discussion)",
        content=history1,
        token_count=estimate_tokens(history1),
        priority=Priority.MEDIUM,
        relevance_score=0.70,
    ))

    history2 = "Three turns ago, user mentioned budget constraint of $5000/month for infrastructure."
    items.append(ContextItem(
        name="History: Budget constraint mention",
        content=history2,
        token_count=estimate_tokens(history2),
        priority=Priority.MEDIUM,
        relevance_score=0.65,
    ))

    history3 = "Five turns ago, user discussed team size (4 engineers) and timeline (3 months)."
    items.append(ContextItem(
        name="History: Team context",
        content=history3,
        token_count=estimate_tokens(history3),
        priority=Priority.MEDIUM,
        relevance_score=0.45,
    ))

    # Low priority: few-shot examples
    example1 = "Example Q&A showing architecture recommendation format. " * 20
    items.append(ContextItem(
        name="Few-shot Example 1",
        content=example1,
        token_count=estimate_tokens(example1),
        priority=Priority.LOW,
        relevance_score=0.50,
        compressible=True,
        compressed_content="[Example format: state architecture, give numbers, list trade-offs]",
        compressed_tokens=15,
    ))

    example2 = "Example Q&A showing cost analysis format. " * 20
    items.append(ContextItem(
        name="Few-shot Example 2",
        content=example2,
        token_count=estimate_tokens(example2),
        priority=Priority.LOW,
        relevance_score=0.40,
    ))

    # Expendable: supporting but tangential docs
    doc4 = "General overview of embedding models and their dimensions. " * 25
    items.append(ContextItem(
        name="Retrieved Doc: Embedding Models Overview",
        content=doc4,
        token_count=estimate_tokens(doc4),
        priority=Priority.EXPENDABLE,
        relevance_score=0.35,
    ))

    doc5 = "History of vector databases from 2020 to 2024. " * 30
    items.append(ContextItem(
        name="Retrieved Doc: Vector DB History",
        content=doc5,
        token_count=estimate_tokens(doc5),
        priority=Priority.EXPENDABLE,
        relevance_score=0.25,
    ))

    return items


def allocate_budget(
    items: list,
    total_budget: int,
    output_reserve: int = 4096,
    safety_margin: int = 256,
) -> AllocationResult:
    """
    Allocate context budget using priority-based greedy packing.
    
    Algorithm:
    1. Reserve space for output and safety margin
    2. Sort items by priority tier, then by relevance within tier
    3. Greedily pack items that fit
    4. For items that don't fit but are compressible, include compressed version
    5. Skip items that don't fit and aren't compressible
    """
    available = total_budget - output_reserve - safety_margin
    
    # Sort by priority (lower number = higher priority), then relevance (higher = better)
    sorted_items = sorted(items, key=lambda x: x.sort_key)
    
    included = []
    excluded = []
    compressed = []
    tokens_used = 0

    for item in sorted_items:
        if item.token_count <= (available - tokens_used):
            # Fits in budget - include fully
            included.append(item)
            tokens_used += item.token_count
        elif item.compressible and item.compressed_tokens and item.compressed_tokens <= (available - tokens_used):
            # Doesn't fit fully, but compressed version fits
            compressed.append(item)
            tokens_used += item.compressed_tokens
        else:
            # Doesn't fit at all
            excluded.append(item)

    utilization = tokens_used / available * 100 if available > 0 else 0

    return AllocationResult(
        included=included,
        excluded=excluded,
        compressed=compressed,
        total_tokens_used=tokens_used,
        budget_remaining=available - tokens_used,
        utilization_pct=utilization,
    )


def print_allocation_report(result: AllocationResult, total_budget: int):
    """Print a detailed report of allocation decisions."""
    print("=" * 70)
    print("CONTEXT BUDGET ALLOCATION REPORT")
    print("=" * 70)
    print(f"\nTotal Context Window:  {total_budget:,} tokens")
    print(f"Output Reserve:        4,096 tokens")
    print(f"Safety Margin:         256 tokens")
    print(f"Available for Input:   {total_budget - 4096 - 256:,} tokens")
    print(f"Tokens Used:           {result.total_tokens_used:,} tokens")
    print(f"Budget Remaining:      {result.budget_remaining:,} tokens")
    print(f"Utilization:           {result.utilization_pct:.1f}%")

    print("\n" + "-" * 70)
    print("INCLUDED (Full)")
    print("-" * 70)
    for item in result.included:
        priority_name = item.priority.name
        print(f"  [{priority_name:10s}] {item.name:45s} | {item.token_count:6,} tokens | rel={item.relevance_score:.2f}")

    if result.compressed:
        print("\n" + "-" * 70)
        print("INCLUDED (Compressed)")
        print("-" * 70)
        for item in result.compressed:
            savings = item.token_count - (item.compressed_tokens or 0)
            print(f"  [{item.priority.name:10s}] {item.name:45s} | {item.compressed_tokens:6,} tokens (saved {savings:,}) | rel={item.relevance_score:.2f}")

    if result.excluded:
        print("\n" + "-" * 70)
        print("EXCLUDED (Didn't fit)")
        print("-" * 70)
        for item in result.excluded:
            print(f"  [{item.priority.name:10s}] {item.name:45s} | {item.token_count:6,} tokens | rel={item.relevance_score:.2f}")

    # Cost analysis
    print("\n" + "-" * 70)
    print("COST ANALYSIS")
    print("-" * 70)
    cost_per_m = 3.0  # $3 per million input tokens (Claude Sonnet pricing)
    cost = result.total_tokens_used * cost_per_m / 1_000_000
    print(f"  Input cost at $3/M tokens: ${cost:.4f}")
    print(f"  With prompt caching (90% hit): ${cost * 0.1:.4f}")


def demonstrate_different_budgets(items: list):
    """Show how allocation changes with different context window sizes."""
    print("\n\n" + "=" * 70)
    print("COMPARISON: Same Query, Different Context Windows")
    print("=" * 70)

    budgets = [
        (8192, "8K (GPT-3.5 era)"),
        (32768, "32K (GPT-4 early)"),
        (131072, "128K (GPT-4 Turbo / Claude 3)"),
    ]

    for budget, label in budgets:
        result = allocate_budget(items, budget)
        included_count = len(result.included) + len(result.compressed)
        excluded_count = len(result.excluded)
        print(f"\n  {label}:")
        print(f"    Included: {included_count} items | Excluded: {excluded_count} items | Utilization: {result.utilization_pct:.0f}%")
        
        if result.excluded:
            excluded_names = [item.name for item in result.excluded[:3]]
            print(f"    Key exclusions: {', '.join(excluded_names)}")


def demonstrate_query_type_allocation():
    """Show how different query types get different allocations."""
    print("\n\n" + "=" * 70)
    print("QUERY-TYPE ADAPTIVE ALLOCATION")
    print("=" * 70)
    print("\nDifferent queries allocate the same 128K budget differently:\n")

    profiles = {
        "Factual Lookup": {"docs": 0.70, "history": 0.10, "examples": 0.05, "system": 0.15},
        "Multi-turn Chat": {"docs": 0.30, "history": 0.50, "examples": 0.05, "system": 0.15},
        "Code Generation": {"docs": 0.50, "history": 0.10, "examples": 0.25, "system": 0.15},
        "Analysis Task":   {"docs": 0.60, "history": 0.15, "examples": 0.10, "system": 0.15},
    }

    available = 128000 - 4096 - 256  # After reserves

    for query_type, alloc in profiles.items():
        print(f"  {query_type}:")
        for component, pct in alloc.items():
            tokens = int(available * pct)
            print(f"    {component:12s}: {tokens:6,} tokens ({pct*100:.0f}%)")
        print()


def main():
    print("Context Budget Allocator - Educational Simulation")
    print("Demonstrates intelligent context window packing for LLM requests\n")

    # Create sample items
    items = create_sample_context_items()

    print(f"Total candidate items: {len(items)}")
    total_candidate_tokens = sum(item.token_count for item in items)
    print(f"Total candidate tokens: {total_candidate_tokens:,}")
    print(f"Target context window: 32,768 tokens (simulating constrained budget)\n")

    # Run allocation with a constrained budget to show trade-offs
    result = allocate_budget(items, total_budget=32768)
    print_allocation_report(result, total_budget=32768)

    # Show how different window sizes change the game
    demonstrate_different_budgets(items)

    # Show query-type adaptive allocation
    demonstrate_query_type_allocation()

    # Key takeaways
    print("\n" + "=" * 70)
    print("KEY ARCHITECTURAL INSIGHTS")
    print("=" * 70)
    print("""
    1. Budget allocation is NOT static - it adapts to query type and complexity
    2. Compression allows including more items at reduced fidelity
    3. Larger context windows don't eliminate the need for prioritization
       (more context can dilute attention - lost-in-the-middle problem)
    4. The output reserve is often underestimated in production systems
    5. Cost scales linearly with context used - don't fill the window blindly
    6. With prompt caching, stable prefixes (system + docs) become 90% cheaper
    """)


if __name__ == "__main__":
    main()
