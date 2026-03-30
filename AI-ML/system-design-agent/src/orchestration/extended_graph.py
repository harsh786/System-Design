"""
Extended LangGraph Workflow - Complete SDLC Automation

Orchestrates the full software development lifecycle from PRD to deployment.
"""

from langgraph.graph import StateGraph, END

from src.config.settings import Settings
from src.orchestration.extended_state import ExtendedDesignAgentState
from src.retrieval.vector_store import VectorStoreManager

# Import all agents
from src.agents.prd_analyzer import PRDAnalyzerAgent
from src.agents.code_analyzer import CodeAnalyzerAgent
from src.agents.hld_generator import HLDGeneratorAgent
from src.agents.lld_generator import LLDGeneratorAgent
from src.agents.db_design_generator import DBDesignGeneratorAgent
from src.agents.code_generator import CodeGeneratorAgent
from src.agents.security_review_agent import SecurityReviewAgent
from src.agents.pr_review_agent import PRReviewAgent
from src.agents.deployment_agent import DeploymentAgent
from src.agents.review_agent import ReviewAgent


def build_extended_agent_graph(
    vector_store: VectorStoreManager,
    settings: Settings,
    enable_phases: dict = None,
) -> StateGraph:
    """
    Build the complete SDLC automation graph.

    Graph Flow:
        START → prd_analyzer → code_analyzer
              → hld_generator → lld_generator → db_designer → design_reviewer
              → code_generator → security_reviewer → (fix_loop?)
              → pr_reviewer → (approved?) → deployment_agent → END

    Args:
        vector_store: Vector store for RAG
        settings: Configuration
        enable_phases: Dict to enable/disable phases (e.g., {'implementation': True})

    Returns:
        Compiled LangGraph StateGraph
    """

    # Default: enable all phases
    if enable_phases is None:
        enable_phases = {
            "analysis": True,
            "design": True,
            "implementation": True,
            "security_review": True,
            "pr_review": True,
            "deployment": True,
        }

    # ── Initialize All Agents ──
    prd_analyzer = PRDAnalyzerAgent(vector_store, settings)
    code_analyzer = CodeAnalyzerAgent(vector_store, settings)
    hld_generator = HLDGeneratorAgent(vector_store, settings)
    lld_generator = LLDGeneratorAgent(vector_store, settings)
    db_designer = DBDesignGeneratorAgent(vector_store, settings)
    design_reviewer = ReviewAgent(vector_store, settings)
    code_generator = CodeGeneratorAgent(vector_store, settings)
    security_reviewer = SecurityReviewAgent(vector_store, settings)
    pr_reviewer = PRReviewAgent(vector_store, settings)
    deployment_agent = DeploymentAgent(vector_store, settings)

    # ── Define Graph ──
    graph = StateGraph(ExtendedDesignAgentState)

    # ── Define Node Functions ──

    async def analyze_prd(state: ExtendedDesignAgentState) -> dict:
        """Node: Analyze PRD and extract requirements."""
        print("\n" + "=" * 80)
        print("PHASE 1: ANALYSIS & PLANNING")
        print("=" * 80)
        print("  🔍 Running PRD Analyzer...")
        result = await prd_analyzer.run(state)
        result["current_phase"] = "analysis"
        return result

    async def analyze_code(state: ExtendedDesignAgentState) -> dict:
        """Node: Analyze existing codebase."""
        print("  📊 Running Code & Architecture Analyzer...")
        result = await code_analyzer.run(state)
        result["current_phase"] = "analysis"
        return result

    async def generate_hld(state: ExtendedDesignAgentState) -> dict:
        """Node: Generate High-Level Design."""
        print("\n" + "=" * 80)
        print("PHASE 2: DESIGN")
        print("=" * 80)
        print("  🏗️  Running HLD Generator...")
        result = await hld_generator.run(state)
        result["current_phase"] = "design"
        return result

    async def generate_lld(state: ExtendedDesignAgentState) -> dict:
        """Node: Generate Low-Level Design."""
        print("  ⚙️  Running LLD Generator...")
        result = await lld_generator.run(state)
        result["current_phase"] = "design"
        return result

    async def generate_db_design(state: ExtendedDesignAgentState) -> dict:
        """Node: Generate Database Design."""
        print("  🗄️  Running DB Design Generator...")
        result = await db_designer.run(state)
        result["current_phase"] = "design"
        return result

    async def review_designs(state: ExtendedDesignAgentState) -> dict:
        """Node: Review all design documents."""
        print("  📋 Running Design Review Agent...")
        result = await design_reviewer.run(state)
        result["current_phase"] = "design"
        return result

    async def generate_code(state: ExtendedDesignAgentState) -> dict:
        """Node: Generate production code."""
        print("\n" + "=" * 80)
        print("PHASE 3: IMPLEMENTATION")
        print("=" * 80)
        print("  💻 Running Code Generator...")
        result = await code_generator.run(state)
        result["current_phase"] = "implementation"
        return result

    async def review_security(state: ExtendedDesignAgentState) -> dict:
        """Node: Security review of generated code."""
        print("\n" + "=" * 80)
        print("PHASE 4: SECURITY REVIEW")
        print("=" * 80)
        print("  🔒 Running Security Review Agent...")
        result = await security_reviewer.run(state)
        result["current_phase"] = "security_review"
        return result

    async def review_pr(state: ExtendedDesignAgentState) -> dict:
        """Node: PR review of generated code."""
        print("\n" + "=" * 80)
        print("PHASE 5: PR REVIEW")
        print("=" * 80)
        print("  🔍 Running PR Review Agent...")
        result = await pr_reviewer.run(state)
        result["current_phase"] = "pr_review"
        return result

    async def generate_deployment(state: ExtendedDesignAgentState) -> dict:
        """Node: Generate deployment configurations."""
        print("\n" + "=" * 80)
        print("PHASE 6: DEPLOYMENT CONFIGURATION")
        print("=" * 80)
        print("  🚀 Running Deployment Agent...")
        result = await deployment_agent.run(state)
        result["current_phase"] = "deployment"
        return result

    async def request_human_feedback(state: ExtendedDesignAgentState) -> dict:
        """Node: Request human feedback for critical decisions."""
        print("\n" + "⏸️  HUMAN REVIEW REQUIRED")
        print("=" * 80)
        issues = state.get("pr_review_comments", [])
        print(f"  Issues requiring human review: {len(issues)}")
        for issue in issues[:5]:
            print(f"    - {issue.get('comment', 'Unknown issue')}")
        
        # In a real system, this would wait for human input
        # For now, we'll simulate approval
        print("\n  ⚠️  In production, waiting for human feedback...")
        print("  Simulating: PROCEED WITH SUGGESTIONS\n")
        
        return {
            "human_feedback": "proceed_with_suggestions",
            "human_review_required": False,
        }

    # ── Register Nodes ──
    
    # Phase 1: Analysis
    if enable_phases.get("analysis", True):
        graph.add_node("analyze_prd", analyze_prd)
        graph.add_node("analyze_code", analyze_code)

    # Phase 2: Design
    if enable_phases.get("design", True):
        graph.add_node("generate_hld", generate_hld)
        graph.add_node("generate_lld", generate_lld)
        graph.add_node("generate_db_design", generate_db_design)
        graph.add_node("review_designs", review_designs)

    # Phase 3: Implementation
    if enable_phases.get("implementation", True):
        graph.add_node("generate_code", generate_code)

    # Phase 4: Security
    if enable_phases.get("security_review", True):
        graph.add_node("review_security", review_security)

    # Phase 5: PR Review
    if enable_phases.get("pr_review", True):
        graph.add_node("review_pr", review_pr)
        graph.add_node("request_human_feedback", request_human_feedback)

    # Phase 6: Deployment
    if enable_phases.get("deployment", True):
        graph.add_node("generate_deployment", generate_deployment)

    # ── Define Edges & Conditional Routing ──

    # Start with PRD analysis
    graph.set_entry_point("analyze_prd")

    # Phase 1: Analysis Pipeline
    if enable_phases.get("analysis", True):
        # PRD Analyzer → conditional
        def after_prd_analysis(state: ExtendedDesignAgentState) -> str:
            if state.get("requirements_valid", False):
                return "analyze_code"
            else:
                return "end"  # Need clarification

        graph.add_conditional_edges(
            "analyze_prd",
            after_prd_analysis,
            {
                "analyze_code": "analyze_code",
                "end": END,
            },
        )

        # Code Analyzer → HLD
        if enable_phases.get("design", True):
            graph.add_edge("analyze_code", "generate_hld")
        else:
            graph.add_edge("analyze_code", END)

    # Phase 2: Design Pipeline
    if enable_phases.get("design", True):
        if not enable_phases.get("analysis", True):
            graph.set_entry_point("generate_hld")

        graph.add_edge("generate_hld", "generate_lld")
        graph.add_edge("generate_lld", "generate_db_design")
        graph.add_edge("generate_db_design", "review_designs")

        # After design review → Implementation or END
        def after_design_review(state: ExtendedDesignAgentState) -> str:
            review_status = state.get("review_status", "")
            if review_status in ["PASS", "PASS_WITH_COMMENTS"]:
                if enable_phases.get("implementation", True):
                    return "generate_code"
                else:
                    return "end"
            elif state.get("review_iteration", 0) >= settings.review_max_iterations:
                return "end"
            else:
                # Loop back to fix design
                return "generate_hld"

        graph.add_conditional_edges(
            "review_designs",
            after_design_review,
            {
                "generate_code": "generate_code",
                "generate_hld": "generate_hld",
                "end": END,
            },
        )

    # Phase 3: Implementation → Security
    if enable_phases.get("implementation", True):
        if not enable_phases.get("design", True):
            graph.set_entry_point("generate_code")

        if enable_phases.get("security_review", True):
            graph.add_edge("generate_code", "review_security")
        elif enable_phases.get("pr_review", True):
            graph.add_edge("generate_code", "review_pr")
        elif enable_phases.get("deployment", True):
            graph.add_edge("generate_code", "generate_deployment")
        else:
            graph.add_edge("generate_code", END)

    # Phase 4: Security Review with auto-fix loop
    if enable_phases.get("security_review", True):
        def after_security_review(state: ExtendedDesignAgentState) -> str:
            # Check for critical unresolved issues
            sast = state.get("sast_results", {})
            critical_issues = len(sast.get("critical", []))
            
            # Check dependency vulnerabilities
            dep_vulns = state.get("dependency_vulnerabilities", [])
            critical_dep_vulns = sum(
                1 for v in dep_vulns if v.get("severity") == "CRITICAL"
            )

            iteration = state.get("security_auto_fix_iteration", 0)

            # If critical issues exist and haven't exceeded max iterations, loop back
            if (critical_issues > 0 or critical_dep_vulns > 0) and iteration < 3:
                print(f"\n  🔄 Security issues found, attempting auto-fix (iteration {iteration + 1}/3)...")
                return "generate_code"
            else:
                if enable_phases.get("pr_review", True):
                    return "review_pr"
                elif enable_phases.get("deployment", True):
                    return "generate_deployment"
                else:
                    return "end"

        graph.add_conditional_edges(
            "review_security",
            after_security_review,
            {
                "generate_code": "generate_code",
                "review_pr": "review_pr",
                "generate_deployment": "generate_deployment",
                "end": END,
            },
        )

    # Phase 5: PR Review with human-in-the-loop
    if enable_phases.get("pr_review", True):
        def after_pr_review(state: ExtendedDesignAgentState) -> str:
            approval_status = state.get("pr_approval_status", "")

            if approval_status in ["APPROVED", "APPROVED_WITH_SUGGESTIONS"]:
                if enable_phases.get("deployment", True):
                    return "generate_deployment"
                else:
                    return "end"
            elif approval_status == "CHANGES_REQUESTED":
                # Check if human review is required
                if state.get("human_review_required", False):
                    return "request_human_feedback"
                else:
                    # Auto-fix based on comments
                    return "generate_code"
            else:
                return "end"

        graph.add_conditional_edges(
            "review_pr",
            after_pr_review,
            {
                "generate_deployment": "generate_deployment",
                "request_human_feedback": "request_human_feedback",
                "generate_code": "generate_code",
                "end": END,
            },
        )

        # After human feedback → continue
        def after_human_feedback(state: ExtendedDesignAgentState) -> str:
            feedback = state.get("human_feedback", "")
            if feedback == "approve":
                if enable_phases.get("deployment", True):
                    return "generate_deployment"
                else:
                    return "end"
            elif feedback in ["proceed_with_suggestions", "revise"]:
                return "generate_code"
            else:
                return "end"

        graph.add_conditional_edges(
            "request_human_feedback",
            after_human_feedback,
            {
                "generate_deployment": "generate_deployment",
                "generate_code": "generate_code",
                "end": END,
            },
        )

    # Phase 6: Deployment → END
    if enable_phases.get("deployment", True):
        graph.add_edge("generate_deployment", END)

    # ── Compile & Return ──
    return graph.compile()
