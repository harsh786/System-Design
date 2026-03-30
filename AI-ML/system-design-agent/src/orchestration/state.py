"""
LangGraph State Definitions - Defines the state that flows through the agent graph.
"""

from typing import TypedDict


class DesignAgentState(TypedDict, total=False):
    """
    State object that flows through the LangGraph design pipeline.
    Each agent reads from and writes to this shared state.
    Uses TypedDict as required by LangGraph.
    """

    # ── Input ──
    prd_content: str
    existing_docs: list
    context_dir: str
    output_dir: str

    # ── PRD Analyzer Output ──
    requirements_json: str
    project_name: str
    data_entities: list[dict]
    integrations: list[dict]
    nfr: dict
    requirements_valid: bool
    clarification_questions: list[str]

    # ── HLD Generator Output ──
    hld_document: str
    components: list[dict]
    tech_choices: dict
    db_technology: str

    # ── LLD Generator Output ──
    lld_documents: dict
    api_contracts: dict
    query_patterns: list[str]

    # ── DB Design Generator Output ──
    db_design_document: str
    ddl_scripts: str

    # ── Review Agent Output ──
    review_report: str
    review_status: str
    review_issues: list[dict]
    review_iteration: int

    # ── Workflow Control ──
    current_agent: str
    error: str
