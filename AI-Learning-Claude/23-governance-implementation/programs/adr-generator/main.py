"""
ADR (Architecture Decision Record) Generator
Creates, manages, and tracks architecture decisions for AI systems.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import os


@dataclass
class ADR:
    number: int
    title: str
    status: str  # Proposed, Accepted, Rejected, Superseded, Deprecated
    date: str
    context: str
    decision_drivers: list
    options: list  # list of dicts: {name, pros, cons}
    decision: str
    rationale: str
    consequences: list
    superseded_by: Optional[int] = None

    def to_markdown(self) -> str:
        lines = []
        lines.append(f"# ADR-{self.number:03d}: {self.title}")
        lines.append("")
        status_line = f"## Status: {self.status}"
        if self.superseded_by:
            status_line += f" (by ADR-{self.superseded_by:03d})"
        lines.append(status_line)
        lines.append(f"## Date: {self.date}")
        lines.append("")
        lines.append("## Context")
        lines.append(self.context)
        lines.append("")
        lines.append("## Decision Drivers")
        for driver in self.decision_drivers:
            lines.append(f"- {driver}")
        lines.append("")
        lines.append("## Options Considered")
        for i, opt in enumerate(self.options, 1):
            lines.append(f"\n### Option {i}: {opt['name']}")
            lines.append(f"- **Pros**: {opt.get('pros', 'N/A')}")
            lines.append(f"- **Cons**: {opt.get('cons', 'N/A')}")
        lines.append("")
        lines.append("## Decision")
        lines.append(self.decision)
        lines.append("")
        lines.append("## Rationale")
        lines.append(self.rationale)
        lines.append("")
        lines.append("## Consequences")
        for c in self.consequences:
            lines.append(f"- {c}")
        lines.append("")
        return "\n".join(lines)


# Example ADRs
EXAMPLE_ADRS = [
    ADR(
        number=1,
        title="Embedding Model Selection for RAG",
        status="Accepted",
        date="2024-01-15",
        context=(
            "We need to select an embedding model for our RAG system serving 10M documents. "
            "The system powers customer support, answering questions about product documentation "
            "and knowledge base articles. Current keyword search misses semantic matches."
        ),
        decision_drivers=[
            "Quality: must achieve > 85% recall on domain eval set (500 pairs)",
            "Cost: embedding 10M docs must be < $500 one-time",
            "Latency: query-time embedding < 50ms (p99)",
            "Multilingual: support EN, ES, FR with < 5% quality degradation",
        ],
        options=[
            {"name": "OpenAI text-embedding-3-large (3072d)", "pros": "Highest quality (96% recall), strong multilingual", "cons": "Most expensive, 2x storage cost"},
            {"name": "OpenAI text-embedding-3-small (1536d)", "pros": "92% recall, $200 full corpus, Matryoshka support", "cons": "Vendor dependency on OpenAI"},
            {"name": "Cohere embed-v3 (1024d)", "pros": "Search-optimized, lower dimensions", "cons": "89% recall (below threshold for comfort)"},
            {"name": "Self-hosted E5-large (768d)", "pros": "No vendor dependency, lowest per-query cost", "cons": "Requires GPU infra ($500/mo), 85% recall (borderline)"},
        ],
        decision="Option 2: OpenAI text-embedding-3-small",
        rationale=(
            "Best quality-cost ratio on our eval set. 92% recall exceeds target with "
            "$200 one-time cost. Matryoshka support allows future optimization. "
            "Same vendor as LLM simplifies operations."
        ),
        consequences=[
            "Vendor dependency on OpenAI (mitigated by abstraction layer)",
            "Re-embedding cost if we switch: ~$200 + 2 hours",
            "Need to monitor for API pricing changes",
            "Positive: quick implementation, well-documented API",
        ],
    ),
    ADR(
        number=2,
        title="Vector Database Selection",
        status="Accepted",
        date="2024-01-22",
        context=(
            "With our embedding model selected (ADR-001), we need a vector database "
            "to store and query 10M document embeddings (1536 dimensions). "
            "Must support filtering, handle updates, and integrate with our cloud stack (AWS)."
        ),
        decision_drivers=[
            "Scale: 10M vectors now, projected 50M in 12 months",
            "Latency: p99 query < 100ms with metadata filtering",
            "Cost: < $2000/month at current scale",
            "Operations: managed service preferred (small platform team)",
            "Filtering: must support metadata filtering on 5+ fields",
        ],
        options=[
            {"name": "Pinecone (Managed)", "pros": "Fully managed, simple API, fast queries", "cons": "$700/mo at scale, vendor lock-in, limited filtering"},
            {"name": "Weaviate (Self-hosted)", "pros": "Rich features, hybrid search, open-source", "cons": "Operational burden, need Kubernetes expertise"},
            {"name": "pgvector (PostgreSQL extension)", "pros": "Familiar, no new infra, good for < 5M vectors", "cons": "Performance degrades > 10M vectors, limited ANN options"},
            {"name": "Qdrant (Managed Cloud)", "pros": "Fast, great filtering, reasonable cost ($500/mo)", "cons": "Smaller community, newer managed offering"},
        ],
        decision="Option 4: Qdrant Cloud (Managed)",
        rationale=(
            "Best combination of performance, filtering capabilities, and cost. "
            "Handles 50M vectors within our latency budget. Managed service reduces ops burden. "
            "$500/mo is well within budget. Rich filtering supports our metadata-heavy queries."
        ),
        consequences=[
            "Need to build abstraction layer (in case we need to switch)",
            "Team needs to learn Qdrant API (1-2 days onboarding)",
            "Vendor is smaller than alternatives (monitor stability)",
            "Positive: excellent filtering reduces post-retrieval processing",
        ],
    ),
    ADR(
        number=3,
        title="Chunking Strategy for Document Processing",
        status="Superseded",
        date="2024-02-01",
        context=(
            "We need to define how to split our 10M documents into chunks for embedding. "
            "Documents range from 100 words (FAQ entries) to 50,000 words (technical manuals). "
            "Chunk strategy directly affects retrieval quality."
        ),
        decision_drivers=[
            "Retrieval quality: chunks must be self-contained and meaningful",
            "Coverage: important information must not be lost at chunk boundaries",
            "Efficiency: minimize redundant embedding (overlap costs money)",
            "Diversity: strategy must handle FAQs, manuals, and support tickets",
        ],
        options=[
            {"name": "Fixed-size (512 tokens, 50 token overlap)", "pros": "Simple, predictable, fast", "cons": "Splits mid-sentence, loses context"},
            {"name": "Recursive text splitter (by headers, paragraphs, sentences)", "pros": "Respects document structure, semantic boundaries", "cons": "Variable chunk sizes, more complex"},
            {"name": "Semantic chunking (embedding similarity boundaries)", "pros": "Best semantic coherence", "cons": "Slow (requires embedding during chunking), expensive"},
        ],
        decision="Option 2: Recursive text splitter with header-aware boundaries",
        rationale=(
            "Best balance of quality and simplicity. Respects document structure without "
            "the computational overhead of semantic chunking. Variable sizes handled by "
            "our embedding model (supports up to 8191 tokens)."
        ),
        consequences=[
            "Need custom splitter for each document type (FAQ vs manual)",
            "Variable chunk sizes may affect retrieval scoring",
            "Must monitor retrieval quality per document type",
        ],
        superseded_by=4,
    ),
]


class ADRRepository:
    def __init__(self):
        self.adrs: list[ADR] = list(EXAMPLE_ADRS)
        self.next_number = len(self.adrs) + 1

    def add(self, adr: ADR):
        self.adrs.append(adr)
        self.next_number += 1

    def get(self, number: int) -> Optional[ADR]:
        for adr in self.adrs:
            if adr.number == number:
                return adr
        return None

    def supersede(self, old_number: int, new_number: int):
        old = self.get(old_number)
        if old:
            old.status = "Superseded"
            old.superseded_by = new_number

    def print_index(self):
        print("\n  ┌─────┬────────────────────────────────────────────┬────────────┬────────────┐")
        print("  │  #  │ Title                                      │ Status     │ Date       │")
        print("  ├─────┼────────────────────────────────────────────┼────────────┼────────────┤")
        for adr in self.adrs:
            status = adr.status
            if adr.superseded_by:
                status = f"→ ADR-{adr.superseded_by:03d}"
            print(f"  │ {adr.number:03d} │ {adr.title[:42]:<42} │ {status:<10} │ {adr.date} │")
        print("  └─────┴────────────────────────────────────────────┴────────────┴────────────┘")

    def print_adr(self, number: int):
        adr = self.get(number)
        if not adr:
            print(f"  ADR-{number:03d} not found.")
            return
        print("\n" + "─" * 60)
        print(adr.to_markdown())
        print("─" * 60)

    def save_to_files(self, output_dir: str = "adr_output"):
        os.makedirs(output_dir, exist_ok=True)
        # Write each ADR
        for adr in self.adrs:
            filename = f"{adr.number:03d}-{adr.title.lower().replace(' ', '-')[:40]}.md"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w") as f:
                f.write(adr.to_markdown())
        # Write index
        with open(os.path.join(output_dir, "README.md"), "w") as f:
            f.write("# Architecture Decision Records\n\n")
            f.write("| # | Title | Status | Date |\n")
            f.write("|---|-------|--------|------|\n")
            for adr in self.adrs:
                status = adr.status
                if adr.superseded_by:
                    status = f"Superseded by ADR-{adr.superseded_by:03d}"
                f.write(f"| {adr.number:03d} | {adr.title} | {status} | {adr.date} |\n")
        print(f"  ✓ Saved {len(self.adrs)} ADRs to {output_dir}/")


def interactive_create(repo: ADRRepository):
    print("\n--- Create New ADR ---")
    title = input("  Title: ").strip()
    if not title:
        print("  Cancelled.")
        return

    context = input("  Context (why is this decision needed?): ").strip()

    drivers = []
    print("  Decision drivers (empty line to finish):")
    while True:
        d = input("    - ").strip()
        if not d:
            break
        drivers.append(d)

    options = []
    print("  Options (empty title to finish):")
    while True:
        name = input("    Option name: ").strip()
        if not name:
            break
        pros = input("    Pros: ").strip()
        cons = input("    Cons: ").strip()
        options.append({"name": name, "pros": pros, "cons": cons})

    decision = input("  Decision (which option?): ").strip()
    rationale = input("  Rationale (why this option?): ").strip()

    consequences = []
    print("  Consequences (empty line to finish):")
    while True:
        c = input("    - ").strip()
        if not c:
            break
        consequences.append(c)

    adr = ADR(
        number=repo.next_number,
        title=title,
        status="Proposed",
        date=str(date.today()),
        context=context,
        decision_drivers=drivers or ["Not specified"],
        options=options or [{"name": "Default", "pros": "N/A", "cons": "N/A"}],
        decision=decision or "TBD",
        rationale=rationale or "TBD",
        consequences=consequences or ["TBD"],
    )
    repo.add(adr)
    print(f"\n  ✓ Created ADR-{adr.number:03d}: {adr.title} (Status: Proposed)")


def main():
    repo = ADRRepository()

    print("╔══════════════════════════════════════════════════╗")
    print("║        ADR GENERATOR & MANAGER                   ║")
    print("║  Architecture Decision Records for AI Systems    ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Commands: list, show <#>, create, supersede <#>,║")
    print("║            save, help, quit                       ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"\n  Loaded {len(repo.adrs)} example ADRs.\n")

    # Show index on start
    repo.print_index()

    while True:
        cmd = input("\nadr> ").strip().lower()

        if cmd in ("quit", "exit"):
            print("  Goodbye!")
            break
        elif cmd == "list":
            repo.print_index()
        elif cmd.startswith("show"):
            parts = cmd.split()
            if len(parts) > 1:
                try:
                    repo.print_adr(int(parts[1]))
                except ValueError:
                    print("  Usage: show <number>")
            else:
                print("  Usage: show <number>")
        elif cmd == "create":
            interactive_create(repo)
        elif cmd.startswith("supersede"):
            parts = cmd.split()
            if len(parts) > 1:
                try:
                    old_num = int(parts[1])
                    new_title = input("  New ADR title (superseding decision): ").strip()
                    if new_title:
                        new_adr = ADR(
                            number=repo.next_number,
                            title=new_title,
                            status="Accepted",
                            date=str(date.today()),
                            context=f"Supersedes ADR-{old_num:03d}. Revisiting due to new information.",
                            decision_drivers=["Changed requirements"],
                            options=[{"name": "New approach", "pros": "TBD", "cons": "TBD"}],
                            decision="TBD - fill in details",
                            rationale="TBD",
                            consequences=["Previous decision no longer applies"],
                        )
                        repo.add(new_adr)
                        repo.supersede(old_num, new_adr.number)
                        print(f"  ✓ ADR-{old_num:03d} superseded by ADR-{new_adr.number:03d}")
                except ValueError:
                    print("  Usage: supersede <number>")
            else:
                print("  Usage: supersede <number>")
        elif cmd == "save":
            repo.save_to_files()
        elif cmd == "help":
            print("  list          — Show ADR index")
            print("  show <#>      — Display a specific ADR")
            print("  create        — Create a new ADR interactively")
            print("  supersede <#> — Supersede an existing ADR")
            print("  save          — Save all ADRs to files")
            print("  quit          — Exit")
        else:
            print("  Unknown command. Type 'help' for options.")


if __name__ == "__main__":
    main()
