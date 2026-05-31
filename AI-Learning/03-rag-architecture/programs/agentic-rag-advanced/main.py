"""
main.py - Agentic RAG Demonstration

Runs 6 queries that showcase different agentic capabilities:
1. Simple lookup (single tool, high confidence)
2. Multi-hop reasoning (chained retrievals)
3. Computation (SQL + calculator)
4. Multi-tool comparison (graph + SQL + vector)
5. Abstention (insufficient evidence)
6. CRAG self-correction (low relevance → reformulate)
"""

import time
from agent import AgenticRAGAgent


def print_header():
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║          AGENTIC RAG - Advanced Demonstration                    ║")
    print("║  Query Decomposition | Multi-Tool | CRAG | Confidence Scoring    ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print("This demo shows an AI agent reasoning through complex queries,")
    print("selecting tools, chaining retrievals, self-correcting, and deciding")
    print("whether to answer, caveat, or abstain based on evidence quality.")
    print()
    print("Company: NovaTech (fictional) | Mode: Simulated LLM responses")
    print("─" * 70)


def run_query(agent: AgenticRAGAgent, query: str, query_num: int, description: str) -> dict:
    """Run a single query through the agent with formatted output."""
    print()
    print(f"{'═' * 70}")
    print(f"  QUERY {query_num} ({description}): \"{query}\"")
    print(f"{'═' * 70}")
    print()

    result = agent.run(query)

    print()
    print(f"  ┌─────────────────────────────────────────────────────────────────┐")
    print(f"  │ FINAL ANSWER [{result['decision']}]:")
    # Word-wrap the answer
    answer = result["answer"]
    lines = [answer[i:i+60] for i in range(0, len(answer), 60)]
    for line in lines:
        print(f"  │   {line}")
    print(f"  │")
    print(f"  │ Time: {result['elapsed_seconds']}s | Tools: {', '.join(result['tools_used'])} | Iterations: {result['iterations']}")
    print(f"  │ Confidence: {result['confidence']} | Sources: {result['sources'][:3]}")
    print(f"  └─────────────────────────────────────────────────────────────────┘")

    return result


def print_summary(results: list):
    """Print a summary table of all queries."""
    print()
    print()
    print("╔═══════════════════════════════════════════════════════════════════════════════════╗")
    print("║                              SUMMARY TABLE                                       ║")
    print("╠════╦══════════════╦════════════╦════════════╦═══════╦═══════════╦════════════════╣")
    print("║ #  ║ Type         ║ Decision   ║ Confidence ║ Tools ║ Iterations║ Time           ║")
    print("╠════╬══════════════╬════════════╬════════════╬═══════╬═══════════╬════════════════╣")

    for i, r in enumerate(results, 1):
        qtype = r["query_type"][:12].ljust(12)
        decision = r["decision"].ljust(10)
        conf = str(r["confidence"]).ljust(10)
        tools = str(len(r["tools_used"])).ljust(5)
        iters = str(r["iterations"]).ljust(9)
        elapsed = f"{r['elapsed_seconds']}s".ljust(14)
        print(f"║ {i}  ║ {qtype} ║ {decision} ║ {conf} ║ {tools} ║ {iters} ║ {elapsed} ║")

    print("╚════╩══════════════╩════════════╩════════════╩═══════╩═══════════╩════════════════╝")

    print()
    print("KEY OBSERVATIONS:")
    print("─" * 70)
    print("• Simple queries resolve in 1 iteration with high confidence")
    print("• Multi-hop queries chain results across tools automatically")
    print("• The agent ABSTAINS when evidence is insufficient (Query 5)")
    print("• CRAG self-correction broadens search when relevance is low (Query 6)")
    print("• Confidence scoring enables calibrated trust in answers")
    print()
    print("This is fundamentally different from naive RAG which would:")
    print("  ✗ Always attempt to answer (no abstention)")
    print("  ✗ Use only one retrieval step (no multi-hop)")
    print("  ✗ Never verify its own claims")
    print("  ✗ Have no confidence awareness")
    print("  ✗ Cannot use structured data or graphs")
    print()


def main():
    print_header()

    agent = AgenticRAGAgent(use_real_llm=False)

    queries = [
        ("What is NovaTech's main product?", "Simple Lookup"),
        ("Who manages the team that built the payment gateway?", "Multi-Hop"),
        ("What was the revenue growth rate between Q1 and Q3?", "Computation"),
        ("Compare the performance of the engineering team's products vs the sales team's revenue targets", "Multi-Tool Comparison"),
        ("What will NovaTech's stock price be next year?", "Insufficient Evidence"),
        ("What is NovaTech's environmental policy?", "CRAG Self-Correction"),
    ]

    results = []
    for i, (query, desc) in enumerate(queries, 1):
        result = run_query(agent, query, i, desc)
        results.append(result)

    print_summary(results)


if __name__ == "__main__":
    main()
