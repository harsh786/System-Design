"""
Autonomous System Design Agent - Main Entry Point

This agent takes PRD documents from Confluence and existing system designs
as input, and generates comprehensive HLD, LLD, and Database Design documents.
"""

import asyncio
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from src.ingestion.confluence_reader import ConfluenceReader
from src.ingestion.markdown_parser import MarkdownParser
from src.retrieval.vector_store import VectorStoreManager
from src.orchestration.graph import build_design_agent_graph
from src.config.settings import Settings


async def main(
    prd_url: str | None = None,
    prd_file: str | None = None,
    context_dir: str = "./System-Design",
    output_dir: str = "./generated-designs",
    skip_indexing: bool = False,
):
    """
    Main entry point for the System Design Agent.

    Args:
        prd_url: Confluence page URL for the PRD document
        prd_file: Local file path for the PRD document (alternative to URL)
        context_dir: Directory containing existing HLD/LLD/System-Design docs
        output_dir: Directory to write generated design documents
        skip_indexing: Skip re-indexing if documents haven't changed
    """
    settings = Settings()

    # ------------------------------------------------------------------
    # Step 1: Ingest Documents
    # ------------------------------------------------------------------
    print("📥 Step 1: Ingesting documents...")

    # Read PRD document
    if prd_url:
        confluence = ConfluenceReader(
            url=settings.confluence_url,
            token=settings.confluence_token,
        )
        prd_content = await confluence.fetch_page(prd_url)
    elif prd_file:
        prd_content = Path(prd_file).read_text()
    else:
        raise ValueError("Either --prd-url or --prd-file must be provided")

    # Read existing design documents
    md_parser = MarkdownParser()
    existing_docs = md_parser.parse_directory(context_dir)

    print(f"  ✅ PRD loaded ({len(prd_content)} chars)")
    print(f"  ✅ Existing docs loaded ({len(existing_docs)} documents)")

    # ------------------------------------------------------------------
    # Step 2: Build Vector Store (RAG)
    # ------------------------------------------------------------------
    print("🔍 Step 2: Building vector store...")

    vector_store = VectorStoreManager(settings=settings)

    if not skip_indexing:
        await vector_store.index_documents(existing_docs)
        print(f"  ✅ Indexed {len(existing_docs)} documents")
    else:
        print("  ⏭️  Skipping indexing (using existing index)")

    # ------------------------------------------------------------------
    # Step 3: Run Multi-Agent Design Pipeline
    # ------------------------------------------------------------------
    print("🤖 Step 3: Running design agent pipeline...")

    graph = build_design_agent_graph(
        vector_store=vector_store,
        settings=settings,
    )

    # Execute the agent graph
    result = await graph.ainvoke({
        "prd_content": prd_content,
        "existing_docs": existing_docs,
        "context_dir": context_dir,
        "output_dir": output_dir,
    })

    # ------------------------------------------------------------------
    # Step 4: Write Output Documents
    # ------------------------------------------------------------------
    print("📝 Step 4: Writing design documents...")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Write HLD
    hld_path = output_path / "HLD.md"
    hld_path.write_text(result["hld_document"])
    print(f"  ✅ HLD written to {hld_path}")

    # Write LLD documents (one per component)
    lld_dir = output_path / "LLD"
    lld_dir.mkdir(exist_ok=True)
    for component_name, lld_content in result["lld_documents"].items():
        lld_path = lld_dir / f"{component_name}.md"
        lld_path.write_text(lld_content)
        print(f"  ✅ LLD written to {lld_path}")

    # Write DB Design
    db_path = output_path / "DB_DESIGN.md"
    db_path.write_text(result["db_design_document"])
    print(f"  ✅ DB Design written to {db_path}")

    # Write Review Report
    review_path = output_path / "REVIEW_REPORT.md"
    review_path.write_text(result["review_report"])
    print(f"  ✅ Review Report written to {review_path}")

    print("\n✨ Design generation complete!")
    print(f"📂 Output directory: {output_path.absolute()}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Autonomous System Design Agent"
    )
    parser.add_argument(
        "--prd-url",
        help="Confluence page URL for the PRD document",
    )
    parser.add_argument(
        "--prd-file",
        help="Local file path for the PRD document",
    )
    parser.add_argument(
        "--context-dir",
        default="./System-Design",
        help="Directory containing existing design documents",
    )
    parser.add_argument(
        "--output-dir",
        default="./generated-designs",
        help="Directory to write generated design documents",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Skip re-indexing existing documents",
    )

    args = parser.parse_args()
    asyncio.run(
        main(
            prd_url=args.prd_url,
            prd_file=args.prd_file,
            context_dir=args.context_dir,
            output_dir=args.output_dir,
            skip_indexing=args.skip_indexing,
        )
    )
