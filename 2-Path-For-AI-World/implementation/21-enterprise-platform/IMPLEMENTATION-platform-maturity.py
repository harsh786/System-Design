"""
Enterprise AI Platform - Platform Maturity Assessment
=====================================================

Maturity model definition, assessment questionnaire, scoring engine,
gap analysis, and roadmap generation for AI platform capabilities.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# =============================================================================
# MATURITY MODEL DEFINITION
# =============================================================================

class MaturityLevel(int, Enum):
    L0_AD_HOC = 0
    L1_REACTIVE = 1
    L2_MANAGED = 2
    L3_OPTIMIZED = 3
    L4_PROACTIVE = 4
    L5_ADAPTIVE = 5


MATURITY_LEVEL_DESCRIPTIONS = {
    MaturityLevel.L0_AD_HOC: {
        "name": "Ad Hoc",
        "description": "No coordination. Teams independently adopt AI with no shared infrastructure.",
        "characteristics": [
            "No central AI infrastructure",
            "API keys managed per-developer",
            "No cost visibility or control",
            "No quality standards or evaluation",
            "No security governance for AI",
            "Each team picks own models/tools independently",
        ],
    },
    MaturityLevel.L1_REACTIVE: {
        "name": "Reactive",
        "description": "Basic shared services emerge reactively as problems surface.",
        "characteristics": [
            "Centralized API key management",
            "Basic cost dashboards",
            "Informal list of approved models",
            "Manual approval processes",
            "Ad hoc incident response",
            "Some documentation exists",
        ],
    },
    MaturityLevel.L2_MANAGED: {
        "name": "Managed",
        "description": "Platform is operational with core components mandated.",
        "characteristics": [
            "AI Gateway deployed and required for all teams",
            "Model and prompt registries operational",
            "Policy engine with basic rules",
            "Observability with dashboards",
            "SDK available for major languages",
            "Eval infrastructure available (optional use)",
            "Defined SLAs for platform services",
        ],
    },
    MaturityLevel.L3_OPTIMIZED: {
        "name": "Optimized",
        "description": "Full platform with self-service and enforced quality gates.",
        "characteristics": [
            "All 13 components operational",
            "Self-service for 80%+ of operations",
            "Eval-gated deployments enforced",
            "Experiment platform actively used",
            "Golden paths for all common patterns",
            "Cost optimization active (caching, routing)",
            "Developer satisfaction > 4/5",
            "Full audit trail and compliance reporting",
        ],
    },
    MaturityLevel.L4_PROACTIVE: {
        "name": "Proactive",
        "description": "Platform anticipates needs and provides intelligent automation.",
        "characteristics": [
            "ML-driven cost optimization (auto model routing)",
            "Automated quality improvement loops",
            "Predictive capacity planning",
            "Cross-team knowledge sharing automated",
            "Platform suggests optimizations to teams",
            "Automated regression detection and remediation",
            "Advanced security (anomaly detection, auto-blocking)",
        ],
    },
    MaturityLevel.L5_ADAPTIVE: {
        "name": "Adaptive",
        "description": "Self-optimizing platform with autonomous improvement.",
        "characteristics": [
            "Platform self-optimizes based on usage patterns",
            "Autonomous policy adaptation",
            "Self-healing infrastructure",
            "AI-powered developer experience",
            "Continuous architecture evolution",
            "Industry-leading efficiency metrics",
            "Zero-touch operations for standard workflows",
        ],
    },
}


# =============================================================================
# CAPABILITY DIMENSIONS
# =============================================================================

class CapabilityDimension(str, Enum):
    GATEWAY = "ai_gateway"
    MODEL_MANAGEMENT = "model_management"
    PROMPT_ENGINEERING = "prompt_engineering"
    TOOL_ECOSYSTEM = "tool_ecosystem"
    AGENT_OPERATIONS = "agent_operations"
    EVALUATION = "evaluation"
    EXPERIMENTATION = "experimentation"
    OBSERVABILITY = "observability"
    SECURITY_GOVERNANCE = "security_governance"
    COST_MANAGEMENT = "cost_management"
    DEVELOPER_EXPERIENCE = "developer_experience"
    DATA_MANAGEMENT = "data_management"
    ORGANIZATIONAL = "organizational"


DIMENSION_DESCRIPTIONS = {
    CapabilityDimension.GATEWAY: "AI Gateway and unified model access",
    CapabilityDimension.MODEL_MANAGEMENT: "Model registry, lifecycle, and selection",
    CapabilityDimension.PROMPT_ENGINEERING: "Prompt versioning, testing, and deployment",
    CapabilityDimension.TOOL_ECOSYSTEM: "Tool/MCP registry and management",
    CapabilityDimension.AGENT_OPERATIONS: "Agent deployment, monitoring, and lifecycle",
    CapabilityDimension.EVALUATION: "Eval infrastructure, golden datasets, quality gates",
    CapabilityDimension.EXPERIMENTATION: "A/B testing, canary, experiment management",
    CapabilityDimension.OBSERVABILITY: "Monitoring, tracing, alerting, dashboards",
    CapabilityDimension.SECURITY_GOVERNANCE: "Policies, compliance, audit, access control",
    CapabilityDimension.COST_MANAGEMENT: "Cost tracking, budgets, optimization, chargeback",
    CapabilityDimension.DEVELOPER_EXPERIENCE: "SDK, docs, portal, playground, golden paths",
    CapabilityDimension.DATA_MANAGEMENT: "Vector indexes, embeddings, data governance",
    CapabilityDimension.ORGANIZATIONAL: "Team structure, processes, culture, skills",
}


# =============================================================================
# ASSESSMENT QUESTIONNAIRE
# =============================================================================

@dataclass
class AssessmentQuestion:
    """A single question in the maturity assessment."""
    id: str = ""
    dimension: CapabilityDimension = CapabilityDimension.GATEWAY
    question: str = ""
    description: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)
    # Each option: {"level": 0-5, "text": "...", "evidence": "What to look for"}
    weight: float = 1.0  # Relative importance within dimension


def build_assessment_questionnaire() -> list[AssessmentQuestion]:
    """Build the complete maturity assessment questionnaire."""
    questions = [
        # --- AI GATEWAY ---
        AssessmentQuestion(
            id="gw-1", dimension=CapabilityDimension.GATEWAY,
            question="How do teams access LLM providers?",
            options=[
                {"level": 0, "text": "Direct API calls with individual keys", "evidence": "API keys in code/env vars per developer"},
                {"level": 1, "text": "Shared keys managed centrally, but direct calls", "evidence": "Central key vault, no proxy"},
                {"level": 2, "text": "Centralized gateway proxy required for all calls", "evidence": "Gateway deployed, routing configured"},
                {"level": 3, "text": "Gateway with caching, failover, and policy enforcement", "evidence": "Cache hit rates, failover logs, policy blocks"},
                {"level": 4, "text": "Intelligent routing optimizes cost/latency/quality automatically", "evidence": "ML router metrics, auto-optimization logs"},
                {"level": 5, "text": "Self-tuning gateway adapts to patterns autonomously", "evidence": "Autonomous config changes, zero-touch routing"},
            ],
            weight=2.0,
        ),
        AssessmentQuestion(
            id="gw-2", dimension=CapabilityDimension.GATEWAY,
            question="How is rate limiting and quota management handled?",
            options=[
                {"level": 0, "text": "No rate limiting", "evidence": "No controls on API usage"},
                {"level": 1, "text": "Provider-level limits only", "evidence": "Rely on OpenAI/Anthropic limits"},
                {"level": 2, "text": "Per-team rate limits configured manually", "evidence": "Rate limit configs per team"},
                {"level": 3, "text": "Dynamic limits with burst handling and fair queuing", "evidence": "Adaptive limit configs, queue metrics"},
                {"level": 4, "text": "Predictive scaling based on usage patterns", "evidence": "Forecast models, pre-scaling triggers"},
                {"level": 5, "text": "Autonomous capacity management with zero throttling", "evidence": "Zero throttle events, self-healing capacity"},
            ],
        ),

        # --- MODEL MANAGEMENT ---
        AssessmentQuestion(
            id="mm-1", dimension=CapabilityDimension.MODEL_MANAGEMENT,
            question="How are AI models selected and approved for use?",
            options=[
                {"level": 0, "text": "Teams pick any model without oversight", "evidence": "No approval process, varied model usage"},
                {"level": 1, "text": "Informal guidance on recommended models", "evidence": "Wiki/doc with suggestions"},
                {"level": 2, "text": "Formal registry with approval workflow", "evidence": "Registry exists, approval records"},
                {"level": 3, "text": "Risk-tiered registry with automated compliance checks", "evidence": "Risk tiers, automated gates, compliance reports"},
                {"level": 4, "text": "Registry with benchmarks, auto-recommendations per use case", "evidence": "Benchmark data, recommendation engine"},
                {"level": 5, "text": "Self-updating registry with autonomous evaluation and selection", "evidence": "Auto-benchmark runs, autonomous model switching"},
            ],
            weight=1.5,
        ),

        # --- PROMPT ENGINEERING ---
        AssessmentQuestion(
            id="pe-1", dimension=CapabilityDimension.PROMPT_ENGINEERING,
            question="How are prompts managed and versioned?",
            options=[
                {"level": 0, "text": "Prompts hardcoded in application code", "evidence": "Prompts as string literals in source"},
                {"level": 1, "text": "Prompts in config files, basic version control", "evidence": "Prompt files in git"},
                {"level": 2, "text": "Dedicated prompt registry with versioning", "evidence": "Registry API, version history"},
                {"level": 3, "text": "Registry with eval-gated promotion and A/B testing", "evidence": "Eval gates, promotion logs, experiment data"},
                {"level": 4, "text": "Automated prompt optimization with human oversight", "evidence": "Auto-optimization runs, human approval checkpoints"},
                {"level": 5, "text": "Self-improving prompts with autonomous testing", "evidence": "Autonomous prompt iterations, regression-free history"},
            ],
            weight=1.5,
        ),

        # --- TOOL ECOSYSTEM ---
        AssessmentQuestion(
            id="te-1", dimension=CapabilityDimension.TOOL_ECOSYSTEM,
            question="How are tools/functions for AI agents managed?",
            options=[
                {"level": 0, "text": "No tool management, ad hoc integrations", "evidence": "Tools defined inline, no catalog"},
                {"level": 1, "text": "Some documentation of available tools", "evidence": "Tool list in wiki"},
                {"level": 2, "text": "Tool registry with schemas and permissions", "evidence": "Registry with JSON schemas, ACLs"},
                {"level": 3, "text": "Registry with health monitoring, risk classification, versioning", "evidence": "Health dashboards, risk tiers, version history"},
                {"level": 4, "text": "Auto-discovery, composition, and optimization suggestions", "evidence": "Tool recommendation engine, composition patterns"},
                {"level": 5, "text": "Self-healing tool ecosystem with autonomous maintenance", "evidence": "Auto-failover, self-repair logs, zero downtime"},
            ],
        ),

        # --- AGENT OPERATIONS ---
        AssessmentQuestion(
            id="ao-1", dimension=CapabilityDimension.AGENT_OPERATIONS,
            question="How are AI agents deployed and operated?",
            options=[
                {"level": 0, "text": "No standardized agent deployment", "evidence": "Each team deploys differently"},
                {"level": 1, "text": "Basic deployment templates exist", "evidence": "Shared Dockerfile/configs"},
                {"level": 2, "text": "Standardized deployment with registry and health checks", "evidence": "Agent registry, health endpoints"},
                {"level": 3, "text": "Full lifecycle with guardrails, canary, and auto-scaling", "evidence": "Canary deploys, guardrail logs, HPA configs"},
                {"level": 4, "text": "Intelligent orchestration with anomaly detection", "evidence": "Anomaly alerts, auto-remediation logs"},
                {"level": 5, "text": "Self-managing agents with autonomous improvement", "evidence": "Autonomous config tuning, zero-ops metrics"},
            ],
        ),

        # --- EVALUATION ---
        AssessmentQuestion(
            id="ev-1", dimension=CapabilityDimension.EVALUATION,
            question="How is AI output quality measured and enforced?",
            options=[
                {"level": 0, "text": "No systematic evaluation", "evidence": "Manual spot checks only"},
                {"level": 1, "text": "Ad hoc testing before deployment", "evidence": "Manual test scripts run occasionally"},
                {"level": 2, "text": "Eval infrastructure available, optional use", "evidence": "Eval service exists, some teams use it"},
                {"level": 3, "text": "Mandatory eval gates for production, golden datasets", "evidence": "Gate enforcement, curated datasets, CI integration"},
                {"level": 4, "text": "Continuous evaluation with regression detection", "evidence": "Continuous eval runs, regression alerts, trend dashboards"},
                {"level": 5, "text": "Self-improving evaluation with autonomous dataset curation", "evidence": "Auto-generated test cases, evolving benchmarks"},
            ],
            weight=2.0,
        ),

        # --- EXPERIMENTATION ---
        AssessmentQuestion(
            id="ex-1", dimension=CapabilityDimension.EXPERIMENTATION,
            question="How are changes to AI systems tested in production?",
            options=[
                {"level": 0, "text": "No experimentation, direct deployment", "evidence": "All changes go straight to 100% traffic"},
                {"level": 1, "text": "Manual canary with monitoring", "evidence": "Manual traffic splitting, eyeball monitoring"},
                {"level": 2, "text": "Basic A/B testing infrastructure", "evidence": "A/B framework, basic metrics"},
                {"level": 3, "text": "Full experiment platform with stats, guardrails, promotion", "evidence": "Statistical analysis, guardrail logs, promotion records"},
                {"level": 4, "text": "Intelligent experimentation with bandit algorithms", "evidence": "Bandit allocation data, adaptive experiments"},
                {"level": 5, "text": "Autonomous experimentation and optimization", "evidence": "Auto-launched experiments, autonomous decisions"},
            ],
        ),

        # --- OBSERVABILITY ---
        AssessmentQuestion(
            id="ob-1", dimension=CapabilityDimension.OBSERVABILITY,
            question="What visibility do teams have into AI system behavior?",
            options=[
                {"level": 0, "text": "No AI-specific observability", "evidence": "Only basic application logs"},
                {"level": 1, "text": "Basic logging of inputs/outputs", "evidence": "Request/response logs"},
                {"level": 2, "text": "Structured observability with metrics and tracing", "evidence": "Dashboards, trace IDs, token metrics"},
                {"level": 3, "text": "Full observability with cost attribution, alerting, SLAs", "evidence": "Cost dashboards, SLA reports, alert configs"},
                {"level": 4, "text": "AI-powered anomaly detection and root cause analysis", "evidence": "Anomaly detection models, RCA automation"},
                {"level": 5, "text": "Predictive observability preventing issues before they occur", "evidence": "Predictive alerts, preemptive scaling"},
            ],
            weight=1.5,
        ),

        # --- SECURITY & GOVERNANCE ---
        AssessmentQuestion(
            id="sg-1", dimension=CapabilityDimension.SECURITY_GOVERNANCE,
            question="How is AI security and compliance managed?",
            options=[
                {"level": 0, "text": "No AI-specific security controls", "evidence": "No PII detection, no content filtering"},
                {"level": 1, "text": "Basic guidelines documented", "evidence": "Security guidelines exist but no enforcement"},
                {"level": 2, "text": "Policy engine with automated enforcement", "evidence": "Policy engine deployed, violation logs"},
                {"level": 3, "text": "Comprehensive policies with audit trail and compliance reporting", "evidence": "Audit reports, compliance dashboards, exception management"},
                {"level": 4, "text": "Adaptive security with threat detection", "evidence": "Threat models, adaptive policies, ML-based detection"},
                {"level": 5, "text": "Autonomous security with self-adapting policies", "evidence": "Auto-policy updates, zero security incidents"},
            ],
            weight=2.0,
        ),

        # --- COST MANAGEMENT ---
        AssessmentQuestion(
            id="cm-1", dimension=CapabilityDimension.COST_MANAGEMENT,
            question="How are AI costs tracked and optimized?",
            options=[
                {"level": 0, "text": "No cost tracking for AI usage", "evidence": "Monthly bill is a surprise"},
                {"level": 1, "text": "Basic cost dashboards from provider bills", "evidence": "Provider cost pages checked manually"},
                {"level": 2, "text": "Per-team cost attribution with budgets", "evidence": "Team-level cost reports, budget alerts"},
                {"level": 3, "text": "Real-time cost tracking with optimization (caching, routing)", "evidence": "Cache savings reports, routing optimization logs"},
                {"level": 4, "text": "ML-driven cost optimization with predictive budgeting", "evidence": "Cost prediction models, auto-optimization actions"},
                {"level": 5, "text": "Autonomous cost optimization with guaranteed efficiency", "evidence": "Self-optimizing cost metrics, SLA on cost-per-query"},
            ],
            weight=1.5,
        ),

        # --- DEVELOPER EXPERIENCE ---
        AssessmentQuestion(
            id="dx-1", dimension=CapabilityDimension.DEVELOPER_EXPERIENCE,
            question="What is the developer experience for AI platform consumers?",
            options=[
                {"level": 0, "text": "No platform, developers figure it out themselves", "evidence": "No SDK, no docs, tribal knowledge"},
                {"level": 1, "text": "Basic documentation and examples", "evidence": "README files, scattered examples"},
                {"level": 2, "text": "SDK, CLI, and portal available", "evidence": "Published SDK, CLI tool, web portal"},
                {"level": 3, "text": "Full DX with playground, templates, golden paths", "evidence": "Playground usage, template adoption, DX score > 4/5"},
                {"level": 4, "text": "AI-assisted DX (code generation, auto-config)", "evidence": "AI assistant usage, auto-generated boilerplate"},
                {"level": 5, "text": "Zero-friction DX with intent-based provisioning", "evidence": "Natural language to deployment, < 1 min time-to-first-call"},
            ],
        ),

        # --- DATA MANAGEMENT ---
        AssessmentQuestion(
            id="dm-1", dimension=CapabilityDimension.DATA_MANAGEMENT,
            question="How are vector indexes and embeddings managed?",
            options=[
                {"level": 0, "text": "Each team manages their own, no standards", "evidence": "Multiple vector DBs, no shared approach"},
                {"level": 1, "text": "Recommended vector store, basic guidance", "evidence": "Standard recommendation, some adoption"},
                {"level": 2, "text": "Shared embedding service and vector index registry", "evidence": "Registry exists, shared embedding endpoints"},
                {"level": 3, "text": "Managed service with freshness SLAs, quality evals", "evidence": "SLA dashboards, retrieval eval scores"},
                {"level": 4, "text": "Intelligent data management with auto-optimization", "evidence": "Auto-reindexing, embedding model selection"},
                {"level": 5, "text": "Self-optimizing data layer with autonomous curation", "evidence": "Autonomous data quality improvement, zero-stale indexes"},
            ],
        ),

        # --- ORGANIZATIONAL ---
        AssessmentQuestion(
            id="or-1", dimension=CapabilityDimension.ORGANIZATIONAL,
            question="How is the platform team structured and operating?",
            options=[
                {"level": 0, "text": "No dedicated platform team", "evidence": "AI infra is side project for various teams"},
                {"level": 1, "text": "Part-time platform responsibilities", "evidence": "1-2 people spend some time on platform"},
                {"level": 2, "text": "Dedicated platform team (3-5 people)", "evidence": "Team charter, dedicated headcount"},
                {"level": 3, "text": "Full platform team with PM, treating platform as product", "evidence": "Product roadmap, customer feedback loops, DX metrics"},
                {"level": 4, "text": "Platform team with embedded ML engineers and researchers", "evidence": "ML expertise on team, research-driven improvements"},
                {"level": 5, "text": "Platform organization with specialized sub-teams", "evidence": "Sub-teams (gateway, DX, security), org chart"},
            ],
            weight=1.5,
        ),
    ]
    return questions


# =============================================================================
# SCORING ENGINE
# =============================================================================

@dataclass
class AssessmentResponse:
    """A response to a single assessment question."""
    question_id: str = ""
    selected_level: int = 0
    evidence: str = ""
    notes: str = ""


@dataclass
class DimensionScore:
    """Score for a single capability dimension."""
    dimension: CapabilityDimension = CapabilityDimension.GATEWAY
    score: float = 0.0  # 0-5
    level: MaturityLevel = MaturityLevel.L0_AD_HOC
    questions_answered: int = 0
    weighted_score: float = 0.0
    gap_to_next: float = 0.0
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


@dataclass
class AssessmentResult:
    """Complete assessment result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assessed_at: datetime = field(default_factory=datetime.utcnow)
    assessor: str = ""
    organization: str = ""
    overall_score: float = 0.0
    overall_level: MaturityLevel = MaturityLevel.L0_AD_HOC
    dimension_scores: dict[CapabilityDimension, DimensionScore] = field(default_factory=dict)
    responses: list[AssessmentResponse] = field(default_factory=list)
    target_level: MaturityLevel = MaturityLevel.L3_OPTIMIZED
    gaps: list[dict[str, Any]] = field(default_factory=list)
    roadmap: list[dict[str, Any]] = field(default_factory=list)


class ScoringEngine:
    """Calculates maturity scores from assessment responses."""

    def __init__(self):
        self._questions = build_assessment_questionnaire()
        self._questions_by_id = {q.id: q for q in self._questions}

    def score_assessment(
        self, responses: list[AssessmentResponse], target_level: MaturityLevel = MaturityLevel.L3_OPTIMIZED
    ) -> AssessmentResult:
        """Score a complete assessment."""
        result = AssessmentResult(target_level=target_level, responses=responses)

        # Group responses by dimension
        dimension_responses: dict[CapabilityDimension, list[tuple[AssessmentQuestion, AssessmentResponse]]] = {}
        for resp in responses:
            q = self._questions_by_id.get(resp.question_id)
            if q:
                if q.dimension not in dimension_responses:
                    dimension_responses[q.dimension] = []
                dimension_responses[q.dimension].append((q, resp))

        # Score each dimension
        total_weighted_score = 0.0
        total_weight = 0.0

        for dimension in CapabilityDimension:
            dim_data = dimension_responses.get(dimension, [])
            if not dim_data:
                result.dimension_scores[dimension] = DimensionScore(dimension=dimension)
                continue

            weighted_sum = 0.0
            weight_sum = 0.0
            strengths = []
            gaps = []

            for question, response in dim_data:
                weighted_sum += response.selected_level * question.weight
                weight_sum += question.weight

                if response.selected_level >= target_level.value:
                    strengths.append(question.question)
                elif response.selected_level < target_level.value - 1:
                    gaps.append({
                        "question": question.question,
                        "current_level": response.selected_level,
                        "target_level": target_level.value,
                        "gap": target_level.value - response.selected_level,
                    })

            score = weighted_sum / max(weight_sum, 1)
            level = MaturityLevel(min(int(score), 5))
            gap_to_next = (level.value + 1) - score if level.value < 5 else 0

            dim_score = DimensionScore(
                dimension=dimension,
                score=round(score, 2),
                level=level,
                questions_answered=len(dim_data),
                weighted_score=round(weighted_sum, 2),
                gap_to_next=round(gap_to_next, 2),
                strengths=strengths,
                gaps=[g["question"] for g in gaps],
            )
            result.dimension_scores[dimension] = dim_score
            result.gaps.extend(gaps)

            total_weighted_score += score
            total_weight += 1

        # Overall score
        result.overall_score = round(total_weighted_score / max(total_weight, 1), 2)
        result.overall_level = MaturityLevel(min(int(result.overall_score), 5))

        # Generate roadmap
        result.roadmap = self._generate_roadmap(result)

        return result

    def _generate_roadmap(self, result: AssessmentResult) -> list[dict[str, Any]]:
        """Generate a prioritized roadmap to reach target level."""
        roadmap = []
        priority = 1

        # Sort gaps by size (largest first) and weight
        sorted_gaps = sorted(result.gaps, key=lambda g: g["gap"], reverse=True)

        for gap in sorted_gaps:
            # Find the question to determine dimension
            q = self._questions_by_id.get("")
            roadmap_item = {
                "priority": priority,
                "area": gap["question"],
                "current_level": gap["current_level"],
                "target_level": gap["target_level"],
                "effort": self._estimate_effort(gap["current_level"], gap["target_level"]),
                "impact": "high" if gap["gap"] >= 2 else "medium",
                "recommended_actions": self._get_actions(gap["current_level"], gap["target_level"]),
                "timeline_weeks": self._estimate_timeline(gap["current_level"], gap["target_level"]),
            }
            roadmap.append(roadmap_item)
            priority += 1

        return roadmap

    def _estimate_effort(self, current: int, target: int) -> str:
        gap = target - current
        if gap <= 1:
            return "low"
        elif gap <= 2:
            return "medium"
        elif gap <= 3:
            return "high"
        return "very_high"

    def _estimate_timeline(self, current: int, target: int) -> int:
        """Estimate weeks to close the gap."""
        gap = target - current
        # Rough heuristic: each level takes increasing effort
        weeks_per_level = {1: 4, 2: 8, 3: 16, 4: 24, 5: 36}
        return sum(weeks_per_level.get(current + i + 1, 12) for i in range(gap))

    def _get_actions(self, current: int, target: int) -> list[str]:
        """Get recommended actions for closing a gap."""
        actions_by_transition = {
            (0, 1): ["Identify stakeholders", "Establish basic guidelines", "Start documentation"],
            (1, 2): ["Deploy core infrastructure", "Define processes", "Train teams"],
            (2, 3): ["Enforce standards", "Automate workflows", "Measure and optimize"],
            (3, 4): ["Add intelligence/ML", "Automate decision-making", "Build predictive capabilities"],
            (4, 5): ["Enable autonomy", "Self-healing systems", "Continuous self-improvement"],
        }
        actions = []
        for level in range(current, target):
            transition_actions = actions_by_transition.get((level, level + 1), [])
            actions.extend(transition_actions)
        return actions


# =============================================================================
# PROGRESS TRACKING
# =============================================================================

@dataclass
class AssessmentHistory:
    """Track assessment results over time."""
    organization: str = ""
    assessments: list[AssessmentResult] = field(default_factory=list)

    def add_assessment(self, result: AssessmentResult):
        self.assessments.append(result)

    @property
    def latest(self) -> Optional[AssessmentResult]:
        return self.assessments[-1] if self.assessments else None

    def get_progress(self) -> dict[str, Any]:
        """Calculate progress between assessments."""
        if len(self.assessments) < 2:
            return {"progress": "insufficient_data", "assessments_count": len(self.assessments)}

        prev = self.assessments[-2]
        curr = self.assessments[-1]
        delta = curr.overall_score - prev.overall_score
        days_between = (curr.assessed_at - prev.assessed_at).days

        dimension_progress = {}
        for dim in CapabilityDimension:
            prev_score = prev.dimension_scores.get(dim, DimensionScore()).score
            curr_score = curr.dimension_scores.get(dim, DimensionScore()).score
            dimension_progress[dim.value] = {
                "previous": prev_score,
                "current": curr_score,
                "delta": round(curr_score - prev_score, 2),
                "improved": curr_score > prev_score,
            }

        improving_dims = [d for d, v in dimension_progress.items() if v["delta"] > 0]
        declining_dims = [d for d, v in dimension_progress.items() if v["delta"] < 0]

        return {
            "overall_delta": round(delta, 2),
            "previous_score": prev.overall_score,
            "current_score": curr.overall_score,
            "previous_level": prev.overall_level.name,
            "current_level": curr.overall_level.name,
            "days_between": days_between,
            "velocity": round(delta / max(days_between, 1) * 30, 2),  # Score change per month
            "improving_dimensions": improving_dims,
            "declining_dimensions": declining_dims,
            "dimension_progress": dimension_progress,
            "on_track": delta > 0,
        }

    def benchmark_against_target(self) -> dict[str, Any]:
        """Compare current state against target."""
        if not self.assessments:
            return {}
        curr = self.assessments[-1]
        target = curr.target_level.value

        dimensions_at_target = []
        dimensions_below = []
        for dim, score in curr.dimension_scores.items():
            if score.score >= target:
                dimensions_at_target.append(dim.value)
            else:
                dimensions_below.append({
                    "dimension": dim.value,
                    "current": score.score,
                    "target": target,
                    "gap": round(target - score.score, 2),
                })

        return {
            "target_level": curr.target_level.name,
            "target_score": target,
            "current_score": curr.overall_score,
            "gap": round(target - curr.overall_score, 2),
            "dimensions_at_target": len(dimensions_at_target),
            "dimensions_below_target": len(dimensions_below),
            "completion_pct": round(len(dimensions_at_target) / len(CapabilityDimension) * 100, 1),
            "details_below": sorted(dimensions_below, key=lambda x: x["gap"], reverse=True),
        }


# =============================================================================
# MATURITY ASSESSMENT SERVICE
# =============================================================================

class MaturityAssessmentService:
    """Main service for conducting and tracking maturity assessments."""

    def __init__(self):
        self._scoring_engine = ScoringEngine()
        self._histories: dict[str, AssessmentHistory] = {}

    def get_questionnaire(self) -> list[dict[str, Any]]:
        """Get the assessment questionnaire."""
        questions = build_assessment_questionnaire()
        return [
            {
                "id": q.id,
                "dimension": q.dimension.value,
                "dimension_description": DIMENSION_DESCRIPTIONS[q.dimension],
                "question": q.question,
                "description": q.description,
                "options": q.options,
                "weight": q.weight,
            }
            for q in questions
        ]

    def submit_assessment(
        self, organization: str, assessor: str,
        responses: list[AssessmentResponse],
        target_level: MaturityLevel = MaturityLevel.L3_OPTIMIZED
    ) -> AssessmentResult:
        """Submit and score an assessment."""
        result = self._scoring_engine.score_assessment(responses, target_level)
        result.assessor = assessor
        result.organization = organization

        # Track history
        if organization not in self._histories:
            self._histories[organization] = AssessmentHistory(organization=organization)
        self._histories[organization].add_assessment(result)

        return result

    def get_progress(self, organization: str) -> dict[str, Any]:
        """Get progress over time for an organization."""
        history = self._histories.get(organization)
        if not history:
            return {"error": "No assessments found"}
        return history.get_progress()

    def get_benchmark(self, organization: str) -> dict[str, Any]:
        """Get benchmark against target for an organization."""
        history = self._histories.get(organization)
        if not history:
            return {"error": "No assessments found"}
        return history.benchmark_against_target()

    def get_maturity_model(self) -> dict[str, Any]:
        """Get the complete maturity model definition."""
        return {
            "levels": {
                level.value: info
                for level, info in MATURITY_LEVEL_DESCRIPTIONS.items()
            },
            "dimensions": {
                dim.value: desc
                for dim, desc in DIMENSION_DESCRIPTIONS.items()
            },
        }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main():
    """Demonstrate maturity assessment."""
    service = MaturityAssessmentService()

    # Get questionnaire
    questionnaire = service.get_questionnaire()
    print(f"Assessment has {len(questionnaire)} questions across {len(CapabilityDimension)} dimensions\n")

    # Simulate an assessment (typical enterprise at early stages)
    responses = [
        AssessmentResponse(question_id="gw-1", selected_level=2, evidence="Gateway deployed on Azure APIM"),
        AssessmentResponse(question_id="gw-2", selected_level=2, evidence="Per-team limits in gateway config"),
        AssessmentResponse(question_id="mm-1", selected_level=1, evidence="Wiki page with model recommendations"),
        AssessmentResponse(question_id="pe-1", selected_level=1, evidence="Prompts in git, no registry"),
        AssessmentResponse(question_id="te-1", selected_level=0, evidence="Tools defined inline per agent"),
        AssessmentResponse(question_id="ao-1", selected_level=1, evidence="Shared Docker template"),
        AssessmentResponse(question_id="ev-1", selected_level=1, evidence="Manual testing before deploy"),
        AssessmentResponse(question_id="ex-1", selected_level=0, evidence="No experimentation"),
        AssessmentResponse(question_id="ob-1", selected_level=2, evidence="Langfuse deployed, dashboards exist"),
        AssessmentResponse(question_id="sg-1", selected_level=1, evidence="Security guidelines written"),
        AssessmentResponse(question_id="cm-1", selected_level=1, evidence="Check Azure bill monthly"),
        AssessmentResponse(question_id="dx-1", selected_level=1, evidence="Basic README and examples"),
        AssessmentResponse(question_id="dm-1", selected_level=1, evidence="Recommended AI Search, some adoption"),
        AssessmentResponse(question_id="or-1", selected_level=2, evidence="4-person platform team exists"),
    ]

    result = service.submit_assessment(
        organization="Contoso Corp",
        assessor="platform-lead@contoso.com",
        responses=responses,
        target_level=MaturityLevel.L3_OPTIMIZED,
    )

    print(f"Overall Score: {result.overall_score}/5.0")
    print(f"Overall Level: {result.overall_level.name}")
    print(f"Target Level: {result.target_level.name}")
    print(f"\nDimension Scores:")
    for dim, score in sorted(result.dimension_scores.items(), key=lambda x: x[1].score, reverse=True):
        bar = "█" * int(score.score) + "░" * (5 - int(score.score))
        print(f"  {dim.value:25s} {bar} {score.score:.1f}/5  (L{score.level.value})")

    print(f"\nTop Gaps ({len(result.gaps)} total):")
    for gap in sorted(result.gaps, key=lambda g: g["gap"], reverse=True)[:5]:
        print(f"  - {gap['question'][:60]:60s} (L{gap['current_level']} → L{gap['target_level']})")

    print(f"\nRoadmap ({len(result.roadmap)} items):")
    for item in result.roadmap[:5]:
        print(f"  P{item['priority']}: {item['area'][:50]:50s} | Effort: {item['effort']:8s} | ~{item['timeline_weeks']} weeks")

    # Benchmark against target
    benchmark = service.get_benchmark("Contoso Corp")
    print(f"\nBenchmark: {benchmark.get('completion_pct', 0)}% of dimensions at target level")
    print(f"  Gap to target: {benchmark.get('gap', 0)}")


if __name__ == "__main__":
    main()
