"""
Extended State Definitions for Full SDLC Agent Pipeline
"""

from typing import TypedDict, List, Dict, Any


class ExtendedDesignAgentState(TypedDict, total=False):
    """
    Extended state object for the complete SDLC automation pipeline.
    Flows through all phases from PRD analysis to deployment.
    """

    # ═══════════════════════════════════════════════════════════════════
    # INPUT
    # ═══════════════════════════════════════════════════════════════════
    prd_content: str
    prd_url: str
    existing_docs: List[str]
    context_dir: str
    output_dir: str
    repo_path: str

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: ANALYSIS & PLANNING
    # ═══════════════════════════════════════════════════════════════════
    
    # PRD Analyzer Output
    requirements_json: str
    project_name: str
    data_entities: List[Dict]
    integrations: List[Dict]
    nfr: Dict
    requirements_valid: bool
    clarification_questions: List[str]

    # Code & Architecture Analyzer Output
    codebase_summary: Dict
    current_architecture: Dict
    tech_stack: Dict
    reusable_components: List[Dict]

    # Planning Agent Output
    work_items: List[Dict]
    critical_path: List[str]
    risk_areas: List[Dict]

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: DESIGN
    # ═══════════════════════════════════════════════════════════════════
    
    # HLD Generator Output
    hld_document: str
    components: List[Dict]
    tech_choices: Dict
    db_technology: str

    # LLD Generator Output
    lld_documents: Dict[str, str]  # component_name -> lld_content
    api_contracts: Dict
    query_patterns: List[str]

    # DB Design Generator Output
    db_design_document: str
    ddl_scripts: str

    # Security Planning Output
    security_requirements: str
    threat_models: List[Dict]
    compliance_checklist: Dict

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: IMPLEMENTATION
    # ═══════════════════════════════════════════════════════════════════
    
    # Code Generator Output
    generated_code: Dict[str, str]  # file_path -> code_content
    
    # Database Schema Implementation Output
    database_migrations: List[str]
    orm_models: Dict[str, str]
    
    # IaC Generator Output
    iac_configs: Dict[str, str]
    
    # Test Generator Output
    unit_tests: Dict[str, str]
    integration_tests: Dict[str, str]
    e2e_tests: Dict[str, str]
    load_tests: Dict[str, str]
    
    # Performance Optimizer Output
    caching_strategy: Dict
    query_optimizations: List[Dict]
    performance_improvements: List[str]

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 4: SECURITY REVIEW
    # ═══════════════════════════════════════════════════════════════════
    
    sast_results: Dict
    dependency_vulnerabilities: List[Dict]
    security_review_report: str
    security_issues_fixed: List[str]
    security_auto_fix_iteration: int

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 5: PR REVIEW
    # ═══════════════════════════════════════════════════════════════════
    
    code_quality_score: float
    pr_review_comments: List[Dict]
    nfr_validation_results: Dict
    documentation_complete: bool
    pr_approval_status: str  # APPROVED, APPROVED_WITH_SUGGESTIONS, CHANGES_REQUESTED
    pr_review_report: str

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 6: DEPLOYMENT
    # ═══════════════════════════════════════════════════════════════════
    
    deployment_strategy: str  # blue_green, canary, rolling, recreate
    ci_cd_pipeline: Dict[str, str]
    deployment_configs: Dict[str, str]
    monitoring_setup: Dict[str, str]
    alert_rules: List[Dict]

    # ═══════════════════════════════════════════════════════════════════
    # WORKFLOW CONTROL
    # ═══════════════════════════════════════════════════════════════════
    
    current_agent: str
    current_phase: str  # analysis, design, implementation, security, pr_review, deployment
    phases_completed: List[str]
    review_iteration: int
    error: str
    human_review_required: bool
    human_feedback: str
