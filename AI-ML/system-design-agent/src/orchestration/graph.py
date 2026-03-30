"""
LangGraph Workflow - Orchestrates the multi-agent design pipeline.

This is the core orchestration layer that wires all agents together
in a directed graph with conditional routing and feedback loops.
"""

import json

from langgraph.graph import StateGraph, END

from src.config.settings import Settings
from src.orchestration.state import DesignAgentState
from src.agents.prd_analyzer import PRDAnalyzerAgent
from src.agents.hld_generator import HLDGeneratorAgent
from src.agents.lld_generator import LLDGeneratorAgent
from src.agents.db_design_generator import DBDesignGeneratorAgent
from src.agents.review_agent import ReviewAgent
from src.retrieval.vector_store import VectorStoreManager


def build_design_agent_graph(
    vector_store: VectorStoreManager,
    settings: Settings,
) -> StateGraph:
    """
    Build the LangGraph workflow for the design agent pipeline.

    Graph Structure:
        START → prd_analyzer → (requirements_valid?)
            ├── No  → ask_clarification → END (user input needed)
            └── Yes → hld_generator → lld_generator → db_design_generator
                      → review_agent → (review_passed?)
                          ├── PASS → END (output documents)
                          └── NEEDS_REVISION → route_revision → (loop)

    Args:
        vector_store: Vector store for RAG retrieval
        settings: Agent configuration

    Returns:
        Compiled LangGraph StateGraph
    """

    # ── Initialize Agents ──
    prd_analyzer = PRDAnalyzerAgent(
        vector_store=vector_store, settings=settings
    )
    hld_generator = HLDGeneratorAgent(
        vector_store=vector_store, settings=settings
    )
    lld_generator = LLDGeneratorAgent(
        vector_store=vector_store, settings=settings
    )
    db_designer = DBDesignGeneratorAgent(
        vector_store=vector_store, settings=settings
    )
    reviewer = ReviewAgent(
        vector_store=vector_store, settings=settings
    )

    # ── Define Graph ──
    graph = StateGraph(DesignAgentState)

    # ── Add Nodes ──

    async def analyze_prd(state: DesignAgentState) -> dict:
        """Node: Analyze PRD and extract structured requirements."""
        print("  🔍 Running PRD Analyzer Agent...")
        result = await prd_analyzer.run(state)
        return result

    async def generate_hld(state: DesignAgentState) -> dict:
        """Node: Generate High-Level Design."""
        print("  🏗️  Running HLD Generator Agent...")
        result = await hld_generator.run(state)
        return result

    async def generate_lld(state: DesignAgentState) -> dict:
        """Node: Generate Low-Level Design for each component."""
        print("  ⚙️  Running LLD Generator Agent...")
        result = await lld_generator.run(state)
        return result

    async def generate_db_design(state: DesignAgentState) -> dict:
        """Node: Generate Database Design."""
        print("  🗄️  Running DB Design Generator Agent...")
        result = await db_designer.run(state)
        return result

    async def review_designs(state: DesignAgentState) -> dict:
        """Node: Review all generated designs against requirements."""
        print("  📋 Running Review Agent...")
        result = await reviewer.run(state)
        return result

    async def ask_clarification(state: DesignAgentState) -> dict:
        """Node: Handle unclear requirements by asking for clarification."""
        print("  ❓ Requirements need clarification:")
        for q in state.get("clarification_questions", []):
            print(f"    - {q}")
        return {"current_agent": "clarification_needed"}

    async def route_revision(state: DesignAgentState) -> dict:
        """Node: Route review issues back to the appropriate agent."""
        print("  🔄 Routing revisions based on review feedback...")
        current_iter = state.get("review_iteration", 0)
        return {"review_iteration": current_iter + 1}

    # ── Register Nodes ──
    graph.add_node("analyze_prd", analyze_prd)
    graph.add_node("generate_hld", generate_hld)
    graph.add_node("generate_lld", generate_lld)
    graph.add_node("generate_db_design", generate_db_design)
    graph.add_node("review_designs", review_designs)
    graph.add_node("ask_clarification", ask_clarification)
    graph.add_node("route_revision", route_revision)

    # ── Define Edges ──

    # Start → PRD Analyzer
    graph.set_entry_point("analyze_prd")

    # PRD Analyzer → conditional
    def after_prd_analysis(state: DesignAgentState) -> str:
        if state.get("requirements_valid", False):
            return "generate_hld"
        else:
            return "ask_clarification"

    graph.add_conditional_edges(
        "analyze_prd",
        after_prd_analysis,
        {
            "generate_hld": "generate_hld",
            "ask_clarification": "ask_clarification",
        },
    )

    # Ask clarification → END (user needs to provide input)
    graph.add_edge("ask_clarification", END)

    # HLD → LLD → DB Design → Review (linear pipeline)
    graph.add_edge("generate_hld", "generate_lld")
    graph.add_edge("generate_lld", "generate_db_design")
    graph.add_edge("generate_db_design", "review_designs")

    # Review → conditional
    def after_review(state: DesignAgentState) -> str:
        status = state.get("review_status", "")
        if status == "PASS":
            return "end"
        elif status == "PASS_WITH_COMMENTS":
            return "end"  # Comments are included in review report
        elif state.get("review_iteration", 0) >= settings.review_max_iterations:
            print("  ⚠️  Max review iterations reached, finalizing...")
            return "end"
        else:
            return "route_revision"

    graph.add_conditional_edges(
        "review_designs",
        after_review,
        {
            "end": END,
            "route_revision": "route_revision",
        },
    )

    # Route revision → back to appropriate agent
    def after_route_revision(state: DesignAgentState) -> str:
        """Determine which agent to re-run based on review issues."""
        review_issues = state.get("review_issues", [])
        if not review_issues:
            return "end"

        # Check which documents have issues
        docs_with_issues = set()
        for issue in review_issues:
            if issue.get("severity") in ("CRITICAL", "HIGH"):
                docs_with_issues.add(issue.get("document", ""))

        if "HLD" in docs_with_issues:
            return "generate_hld"
        elif "LLD" in docs_with_issues:
            return "generate_lld"
        elif "DB_DESIGN" in docs_with_issues:
            return "generate_db_design"
        else:
            return "end"

    graph.add_conditional_edges(
        "route_revision",
        after_route_revision,
        {
            "generate_hld": "generate_hld",
            "generate_lld": "generate_lld",
            "generate_db_design": "generate_db_design",
            "end": END,
        },
    )

    # ── Compile & Return ──
    return graph.compile()
