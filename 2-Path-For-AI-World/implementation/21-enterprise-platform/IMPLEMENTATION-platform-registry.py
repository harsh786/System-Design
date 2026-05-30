"""
Enterprise AI Platform - Central Registry System
================================================

Production-grade registry system managing models, prompts, tools, agents,
embeddings, vector indexes, and evaluations with full lifecycle management.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class RegistryType(str, Enum):
    MODEL = "model"
    PROMPT = "prompt"
    TOOL = "tool"
    AGENT = "agent"
    EMBEDDING = "embedding"
    VECTOR_INDEX = "vector_index"
    EVAL = "eval"


class LifecycleStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class RiskTier(str, Enum):
    T1_UNRESTRICTED = "t1_unrestricted"
    T2_STANDARD = "t2_standard"
    T3_SENSITIVE = "t3_sensitive"
    T4_CRITICAL = "t4_critical"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class ToolRiskLevel(str, Enum):
    READ_ONLY_INTERNAL = "read_only_internal"
    READ_ONLY_EXTERNAL = "read_only_external"
    WRITE_INTERNAL = "write_internal"
    WRITE_EXTERNAL = "write_external"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# =============================================================================
# BASE REGISTRY ITEM
# =============================================================================

@dataclass
class RegistryMetadata:
    """Common metadata for all registry items."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    owner_team: str = ""
    owner_email: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: LifecycleStatus = LifecycleStatus.DRAFT
    tags: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    risk_tier: RiskTier = RiskTier.T1_UNRESTRICTED
    documentation_url: str = ""
    deprecated_at: Optional[datetime] = None
    retirement_date: Optional[datetime] = None
    successor_id: Optional[str] = None  # ID of replacement when deprecated


@dataclass
class AuditEntry:
    """Audit trail entry for registry changes."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    actor: str = ""
    action: str = ""
    resource_type: RegistryType = RegistryType.MODEL
    resource_id: str = ""
    changes: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


# =============================================================================
# MODEL REGISTRY
# =============================================================================

@dataclass
class ModelCapabilities:
    """What a model can do."""
    text_generation: bool = True
    chat: bool = True
    function_calling: bool = False
    vision: bool = False
    code_generation: bool = False
    embedding: bool = False
    reasoning: bool = False
    structured_output: bool = False
    streaming: bool = True
    max_context_tokens: int = 4096
    max_output_tokens: int = 4096
    supports_system_prompt: bool = True
    supports_json_mode: bool = False


@dataclass
class ModelCost:
    """Cost information for a model."""
    input_cost_per_1k_tokens: float = 0.0
    output_cost_per_1k_tokens: float = 0.0
    cost_per_image: float = 0.0
    cost_per_audio_minute: float = 0.0
    monthly_minimum: float = 0.0
    currency: str = "USD"


@dataclass
class ModelDeployment:
    """Deployment information for a model."""
    provider: str = ""  # openai, anthropic, azure, bedrock, self-hosted
    endpoint: str = ""
    region: str = ""
    api_version: str = ""
    quota_tpm: int = 0  # tokens per minute
    quota_rpm: int = 0  # requests per minute
    environment: Environment = Environment.PRODUCTION
    is_primary: bool = True
    failover_model_id: Optional[str] = None


@dataclass
class ModelRegistryEntry:
    """A model in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    provider: str = ""
    model_id: str = ""  # Provider's model identifier (e.g., gpt-4o)
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    cost: ModelCost = field(default_factory=ModelCost)
    deployments: list[ModelDeployment] = field(default_factory=list)
    license_type: str = ""
    data_residency: list[str] = field(default_factory=list)  # Allowed regions
    compliance_certifications: list[str] = field(default_factory=list)
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    allowed_data_classifications: list[str] = field(default_factory=list)
    fine_tuned: bool = False
    base_model_id: Optional[str] = None  # If fine-tuned, reference to base


# =============================================================================
# PROMPT REGISTRY
# =============================================================================

@dataclass
class PromptVariable:
    """A template variable in a prompt."""
    name: str = ""
    description: str = ""
    type: str = "string"  # string, number, boolean, array, object
    required: bool = True
    default: Optional[Any] = None
    validation_regex: Optional[str] = None
    max_length: Optional[int] = None


@dataclass
class PromptEvalResult:
    """Eval results attached to a prompt version."""
    eval_id: str = ""
    eval_name: str = ""
    score: float = 0.0
    passed: bool = False
    run_at: datetime = field(default_factory=datetime.utcnow)
    dataset_size: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptRegistryEntry:
    """A prompt template in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    template: str = ""
    system_prompt: Optional[str] = None
    variables: list[PromptVariable] = field(default_factory=list)
    model_compatibility: list[str] = field(default_factory=list)  # Compatible model IDs
    recommended_model_id: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    output_format: Optional[str] = None  # json, text, markdown
    parent_prompt_id: Optional[str] = None  # For composition/derivation
    eval_results: list[PromptEvalResult] = field(default_factory=list)
    environments: dict[Environment, bool] = field(default_factory=dict)
    usage_count_30d: int = 0
    average_latency_ms: float = 0.0
    average_token_usage: float = 0.0

    @property
    def content_hash(self) -> str:
        """Hash of prompt content for change detection."""
        content = f"{self.system_prompt or ''}{self.template}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def render(self, variables: dict[str, Any]) -> str:
        """Render the prompt with given variables."""
        result = self.template
        for var in self.variables:
            placeholder = f"{{{{{var.name}}}}}"
            if var.name in variables:
                value = str(variables[var.name])
                if var.validation_regex and not re.match(var.validation_regex, value):
                    raise ValueError(
                        f"Variable '{var.name}' value '{value}' doesn't match "
                        f"pattern '{var.validation_regex}'"
                    )
                if var.max_length and len(value) > var.max_length:
                    raise ValueError(
                        f"Variable '{var.name}' exceeds max length {var.max_length}"
                    )
                result = result.replace(placeholder, value)
            elif var.required and var.default is None:
                raise ValueError(f"Required variable '{var.name}' not provided")
            elif var.default is not None:
                result = result.replace(placeholder, str(var.default))
        return result


# =============================================================================
# TOOL REGISTRY
# =============================================================================

@dataclass
class ToolParameter:
    """A parameter for a tool."""
    name: str = ""
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: Optional[list[str]] = None
    default: Optional[Any] = None


@dataclass
class ToolRegistryEntry:
    """A tool (function) in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY_INTERNAL
    endpoint: str = ""
    method: str = "POST"
    parameters: list[ToolParameter] = field(default_factory=list)
    response_schema: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000
    retry_policy: dict[str, Any] = field(default_factory=lambda: {
        "max_retries": 3, "backoff_ms": 1000
    })
    rate_limit_rpm: int = 100
    allowed_agents: list[str] = field(default_factory=list)  # Agent IDs that can use this
    allowed_teams: list[str] = field(default_factory=list)
    requires_human_approval: bool = False
    idempotent: bool = False
    cost_per_call: float = 0.0
    health_check_endpoint: Optional[str] = None
    sla_latency_p99_ms: int = 5000
    dependencies: list[str] = field(default_factory=list)  # Other tool IDs

    @property
    def json_schema(self) -> dict[str, Any]:
        """Generate JSON Schema for this tool (OpenAI function calling format)."""
        properties = {}
        required = []
        for param in self.parameters:
            prop: dict[str, Any] = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


# =============================================================================
# AGENT REGISTRY
# =============================================================================

@dataclass
class AgentGuardrails:
    """Safety guardrails for an agent."""
    max_tokens_per_turn: int = 4096
    max_tool_calls_per_turn: int = 10
    max_turns_per_session: int = 50
    allowed_tool_ids: list[str] = field(default_factory=list)
    blocked_tool_ids: list[str] = field(default_factory=list)
    allowed_model_ids: list[str] = field(default_factory=list)
    content_filter_enabled: bool = True
    pii_filter_enabled: bool = True
    cost_limit_per_session_usd: float = 1.0
    cost_limit_per_day_usd: float = 100.0
    requires_human_in_loop: bool = False
    human_approval_tool_ids: list[str] = field(default_factory=list)


@dataclass
class AgentRegistryEntry:
    """An AI agent in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    agent_type: str = "conversational"  # conversational, task, autonomous, multi-agent
    model_id: str = ""
    prompt_ids: list[str] = field(default_factory=list)
    tool_ids: list[str] = field(default_factory=list)
    sub_agent_ids: list[str] = field(default_factory=list)
    guardrails: AgentGuardrails = field(default_factory=AgentGuardrails)
    deployment_environment: Environment = Environment.PRODUCTION
    endpoint: str = ""
    health_check_url: str = ""
    sla_availability: float = 99.9
    sla_latency_p95_ms: int = 5000
    escalation_contact: str = ""
    incident_history: list[dict[str, Any]] = field(default_factory=list)
    reliability_score: float = 100.0  # 0-100, based on incident history
    sessions_last_30d: int = 0
    avg_satisfaction_score: float = 0.0


# =============================================================================
# EMBEDDING REGISTRY
# =============================================================================

@dataclass
class EmbeddingBenchmark:
    """Benchmark results for an embedding model on a specific domain."""
    domain: str = ""  # legal, medical, code, general, finance
    dataset: str = ""
    metric: str = "cosine_similarity"
    score: float = 0.0
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmbeddingRegistryEntry:
    """An embedding model in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    provider: str = ""
    model_id: str = ""
    dimensions: int = 0
    max_tokens: int = 8192
    distance_metric: str = "cosine"  # cosine, euclidean, dot_product
    supports_batch: bool = True
    batch_max_size: int = 100
    cost_per_1k_tokens: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    benchmarks: list[EmbeddingBenchmark] = field(default_factory=list)
    compatible_vector_stores: list[str] = field(default_factory=list)
    normalization: str = "l2"  # l2, none
    truncation_strategy: str = "end"  # end, none, error


# =============================================================================
# VECTOR INDEX REGISTRY
# =============================================================================

@dataclass
class VectorIndexSource:
    """Data source feeding a vector index."""
    source_type: str = ""  # database, api, file_system, confluence, sharepoint
    source_uri: str = ""
    sync_frequency: str = "daily"  # realtime, hourly, daily, weekly, manual
    last_sync_at: Optional[datetime] = None
    document_count: int = 0
    chunk_strategy: str = "recursive"  # fixed, recursive, semantic, sentence


@dataclass
class VectorIndexRegistryEntry:
    """A vector index/collection in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    vector_store: str = ""  # pinecone, qdrant, weaviate, pgvector, chromadb
    embedding_model_id: str = ""
    dimensions: int = 0
    distance_metric: str = "cosine"
    total_vectors: int = 0
    sources: list[VectorIndexSource] = field(default_factory=list)
    freshness_sla_hours: int = 24
    last_updated_at: Optional[datetime] = None
    retrieval_precision: float = 0.0  # From eval
    retrieval_recall: float = 0.0  # From eval
    eval_score: float = 0.0
    last_eval_at: Optional[datetime] = None
    allowed_teams: list[str] = field(default_factory=list)
    allowed_agents: list[str] = field(default_factory=list)
    retention_days: int = 365
    size_gb: float = 0.0
    monthly_cost_usd: float = 0.0

    @property
    def is_stale(self) -> bool:
        """Check if index is past its freshness SLA."""
        if not self.last_updated_at:
            return True
        staleness = datetime.utcnow() - self.last_updated_at
        return staleness > timedelta(hours=self.freshness_sla_hours)


# =============================================================================
# EVAL REGISTRY
# =============================================================================

@dataclass
class EvalDatasetEntry:
    """A single entry in a golden dataset."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input: dict[str, Any] = field(default_factory=dict)
    expected_output: Optional[str] = None
    expected_facts: list[str] = field(default_factory=list)
    context: Optional[str] = None
    difficulty: str = "medium"  # easy, medium, hard
    category: str = ""
    created_by: str = ""
    source: str = ""  # manual, production_feedback, adversarial


@dataclass
class EvalMetricDefinition:
    """Definition of an evaluation metric."""
    name: str = ""
    description: str = ""
    type: str = "score"  # score (0-1), binary (pass/fail), ranking
    higher_is_better: bool = True
    threshold: float = 0.8  # Minimum to pass
    weight: float = 1.0  # Weight in composite score


@dataclass
class EvalRunResult:
    """Results from a single eval run."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    eval_id: str = ""
    run_at: datetime = field(default_factory=datetime.utcnow)
    triggered_by: str = ""  # ci, manual, scheduled, deployment
    target_type: str = ""  # prompt, agent, model
    target_id: str = ""
    target_version: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    passed: bool = False
    total_examples: int = 0
    passed_examples: int = 0
    failed_examples: int = 0
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    failure_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalRegistryEntry:
    """An evaluation suite in the registry."""
    metadata: RegistryMetadata = field(default_factory=RegistryMetadata)
    eval_type: str = ""  # accuracy, safety, latency, cost, retrieval, factuality
    dataset: list[EvalDatasetEntry] = field(default_factory=list)
    metrics: list[EvalMetricDefinition] = field(default_factory=list)
    target_types: list[str] = field(default_factory=list)  # prompt, agent, model
    schedule: Optional[str] = None  # cron expression for scheduled runs
    is_gate: bool = False  # Must pass for deployment
    last_run: Optional[EvalRunResult] = None
    run_history: list[EvalRunResult] = field(default_factory=list)
    shared_with_teams: list[str] = field(default_factory=list)

    @property
    def pass_rate_trend(self) -> list[tuple[datetime, float]]:
        """Get pass rate over recent runs."""
        return [
            (run.run_at, run.passed_examples / max(run.total_examples, 1))
            for run in sorted(self.run_history, key=lambda r: r.run_at)[-20:]
        ]


# =============================================================================
# APPROVAL WORKFLOW
# =============================================================================

@dataclass
class ApprovalRequest:
    """Request for approval to register or modify a registry item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    registry_type: RegistryType = RegistryType.MODEL
    item_id: str = ""
    action: str = "register"  # register, promote, modify, deprecate
    requestor: str = ""
    requestor_team: str = ""
    requested_at: datetime = field(default_factory=datetime.utcnow)
    status: ApprovalStatus = ApprovalStatus.PENDING
    required_approvers: list[str] = field(default_factory=list)
    current_approvals: list[dict[str, Any]] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    auto_approve_eligible: bool = False
    risk_tier: RiskTier = RiskTier.T1_UNRESTRICTED
    justification: str = ""
    expires_at: Optional[datetime] = None

    @property
    def is_fully_approved(self) -> bool:
        """Check if all required approvals are obtained."""
        approved_by = {a["approver"] for a in self.current_approvals if a.get("approved")}
        return all(approver in approved_by for approver in self.required_approvers)


# =============================================================================
# DEPRECATION AND RETIREMENT
# =============================================================================

@dataclass
class DeprecationNotice:
    """Notice that a registry item is being deprecated."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    registry_type: RegistryType = RegistryType.MODEL
    item_id: str = ""
    item_name: str = ""
    deprecated_at: datetime = field(default_factory=datetime.utcnow)
    retirement_date: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(days=90))
    successor_id: Optional[str] = None
    successor_name: Optional[str] = None
    migration_guide_url: str = ""
    reason: str = ""
    affected_teams: list[str] = field(default_factory=list)
    affected_agents: list[str] = field(default_factory=list)
    notifications_sent: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# CENTRAL REGISTRY SERVICE
# =============================================================================

class RegistryStore(ABC):
    """Abstract storage backend for registry items."""

    @abstractmethod
    async def get(self, registry_type: RegistryType, item_id: str) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    async def list(
        self, registry_type: RegistryType, filters: dict[str, Any], limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def create(self, registry_type: RegistryType, item: dict[str, Any]) -> str:
        ...

    @abstractmethod
    async def update(self, registry_type: RegistryType, item_id: str, updates: dict[str, Any]) -> bool:
        ...

    @abstractmethod
    async def delete(self, registry_type: RegistryType, item_id: str) -> bool:
        ...

    @abstractmethod
    async def search(self, query: str, registry_types: list[RegistryType], limit: int = 20) -> list[dict[str, Any]]:
        ...


class InMemoryRegistryStore(RegistryStore):
    """In-memory implementation for development/testing."""

    def __init__(self):
        self._store: dict[RegistryType, dict[str, dict[str, Any]]] = {
            rt: {} for rt in RegistryType
        }
        self._audit_log: list[AuditEntry] = []

    async def get(self, registry_type: RegistryType, item_id: str) -> Optional[dict[str, Any]]:
        return self._store[registry_type].get(item_id)

    async def list(
        self, registry_type: RegistryType, filters: dict[str, Any], limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        items = list(self._store[registry_type].values())
        # Apply filters
        for key, value in filters.items():
            items = [i for i in items if self._match_filter(i, key, value)]
        return items[offset:offset + limit]

    async def create(self, registry_type: RegistryType, item: dict[str, Any]) -> str:
        item_id = item.get("metadata", {}).get("id", str(uuid.uuid4()))
        self._store[registry_type][item_id] = item
        return item_id

    async def update(self, registry_type: RegistryType, item_id: str, updates: dict[str, Any]) -> bool:
        if item_id not in self._store[registry_type]:
            return False
        self._store[registry_type][item_id].update(updates)
        return True

    async def delete(self, registry_type: RegistryType, item_id: str) -> bool:
        if item_id in self._store[registry_type]:
            del self._store[registry_type][item_id]
            return True
        return False

    async def search(self, query: str, registry_types: list[RegistryType], limit: int = 20) -> list[dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for rt in registry_types:
            for item in self._store[rt].values():
                meta = item.get("metadata", {})
                searchable = f"{meta.get('name', '')} {meta.get('description', '')} {' '.join(meta.get('tags', []))}".lower()
                if query_lower in searchable:
                    results.append({"registry_type": rt.value, **item})
        return results[:limit]

    def _match_filter(self, item: dict[str, Any], key: str, value: Any) -> bool:
        """Match a single filter against an item."""
        parts = key.split(".")
        current = item
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return False
        if isinstance(value, list):
            return current in value
        return current == value


class CentralRegistryService:
    """
    Central registry service managing all registry types with unified
    lifecycle management, search, approval workflows, and deprecation.
    """

    def __init__(self, store: RegistryStore):
        self._store = store
        self._approval_queue: list[ApprovalRequest] = []
        self._deprecation_notices: list[DeprecationNotice] = []
        self._audit_log: list[AuditEntry] = []

    # -------------------------------------------------------------------------
    # MODEL REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_model(
        self, entry: ModelRegistryEntry, actor: str
    ) -> tuple[str, Optional[ApprovalRequest]]:
        """Register a new model. May require approval based on risk tier."""
        approval = None
        if entry.metadata.risk_tier in (RiskTier.T3_SENSITIVE, RiskTier.T4_CRITICAL):
            approval = ApprovalRequest(
                registry_type=RegistryType.MODEL,
                item_id=entry.metadata.id,
                action="register",
                requestor=actor,
                risk_tier=entry.metadata.risk_tier,
                required_approvers=self._get_required_approvers(entry.metadata.risk_tier),
            )
            entry.metadata.status = LifecycleStatus.PENDING_REVIEW
            self._approval_queue.append(approval)
        else:
            entry.metadata.status = LifecycleStatus.ACTIVE

        item_id = await self._store.create(RegistryType.MODEL, self._serialize(entry))
        self._audit(actor, "register_model", RegistryType.MODEL, item_id)
        return item_id, approval

    async def get_model(self, model_id: str) -> Optional[ModelRegistryEntry]:
        """Get a model by ID."""
        data = await self._store.get(RegistryType.MODEL, model_id)
        if data:
            return self._deserialize_model(data)
        return None

    async def list_models(
        self,
        status: Optional[LifecycleStatus] = None,
        risk_tier: Optional[RiskTier] = None,
        provider: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> list[ModelRegistryEntry]:
        """List models with optional filters."""
        filters: dict[str, Any] = {}
        if status:
            filters["metadata.status"] = status.value
        if risk_tier:
            filters["metadata.risk_tier"] = risk_tier.value
        if provider:
            filters["provider"] = provider
        items = await self._store.list(RegistryType.MODEL, filters)
        models = [self._deserialize_model(i) for i in items]
        if capability:
            models = [m for m in models if getattr(m.capabilities, capability, False)]
        return models

    # -------------------------------------------------------------------------
    # PROMPT REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_prompt(
        self, entry: PromptRegistryEntry, actor: str
    ) -> str:
        """Register a new prompt version."""
        entry.metadata.status = LifecycleStatus.ACTIVE
        item_id = await self._store.create(RegistryType.PROMPT, self._serialize(entry))
        self._audit(actor, "register_prompt", RegistryType.PROMPT, item_id)
        return item_id

    async def get_prompt(self, prompt_id: str) -> Optional[PromptRegistryEntry]:
        """Get a prompt by ID."""
        data = await self._store.get(RegistryType.PROMPT, prompt_id)
        if data:
            return self._deserialize_prompt(data)
        return None

    async def promote_prompt(
        self, prompt_id: str, target_env: Environment, actor: str
    ) -> bool:
        """Promote a prompt to a target environment."""
        prompt = await self.get_prompt(prompt_id)
        if not prompt:
            return False
        if target_env == Environment.PRODUCTION:
            # Check eval gate
            passing_evals = [e for e in prompt.eval_results if e.passed]
            if not passing_evals:
                raise ValueError(
                    "Cannot promote to production without passing eval results"
                )
        prompt.environments[target_env] = True
        await self._store.update(
            RegistryType.PROMPT, prompt_id, {"environments": {e.value: v for e, v in prompt.environments.items()}}
        )
        self._audit(actor, f"promote_prompt_to_{target_env.value}", RegistryType.PROMPT, prompt_id)
        return True

    # -------------------------------------------------------------------------
    # TOOL REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_tool(
        self, entry: ToolRegistryEntry, actor: str
    ) -> tuple[str, Optional[ApprovalRequest]]:
        """Register a new tool. Write tools require approval."""
        approval = None
        if entry.risk_level in (ToolRiskLevel.WRITE_INTERNAL, ToolRiskLevel.WRITE_EXTERNAL):
            approval = ApprovalRequest(
                registry_type=RegistryType.TOOL,
                item_id=entry.metadata.id,
                action="register",
                requestor=actor,
                risk_tier=RiskTier.T3_SENSITIVE if entry.risk_level == ToolRiskLevel.WRITE_INTERNAL else RiskTier.T4_CRITICAL,
                required_approvers=["security-team", "platform-team"],
            )
            entry.metadata.status = LifecycleStatus.PENDING_REVIEW
            self._approval_queue.append(approval)
        else:
            entry.metadata.status = LifecycleStatus.ACTIVE

        item_id = await self._store.create(RegistryType.TOOL, self._serialize(entry))
        self._audit(actor, "register_tool", RegistryType.TOOL, item_id)
        return item_id, approval

    async def get_tool(self, tool_id: str) -> Optional[dict[str, Any]]:
        """Get a tool by ID."""
        return await self._store.get(RegistryType.TOOL, tool_id)

    async def get_tools_for_agent(self, agent_id: str) -> list[dict[str, Any]]:
        """Get all tools an agent is permitted to use."""
        agent_data = await self._store.get(RegistryType.AGENT, agent_id)
        if not agent_data:
            return []
        tool_ids = agent_data.get("tool_ids", [])
        tools = []
        for tid in tool_ids:
            tool = await self._store.get(RegistryType.TOOL, tid)
            if tool and tool.get("metadata", {}).get("status") == LifecycleStatus.ACTIVE.value:
                tools.append(tool)
        return tools

    # -------------------------------------------------------------------------
    # AGENT REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_agent(
        self, entry: AgentRegistryEntry, actor: str
    ) -> str:
        """Register a new agent."""
        entry.metadata.status = LifecycleStatus.ACTIVE
        item_id = await self._store.create(RegistryType.AGENT, self._serialize(entry))
        self._audit(actor, "register_agent", RegistryType.AGENT, item_id)
        return item_id

    async def get_agent(self, agent_id: str) -> Optional[dict[str, Any]]:
        """Get an agent by ID."""
        return await self._store.get(RegistryType.AGENT, agent_id)

    # -------------------------------------------------------------------------
    # EMBEDDING REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_embedding(self, entry: EmbeddingRegistryEntry, actor: str) -> str:
        """Register a new embedding model."""
        entry.metadata.status = LifecycleStatus.ACTIVE
        item_id = await self._store.create(RegistryType.EMBEDDING, self._serialize(entry))
        self._audit(actor, "register_embedding", RegistryType.EMBEDDING, item_id)
        return item_id

    async def get_best_embedding_for_domain(self, domain: str) -> Optional[dict[str, Any]]:
        """Get the best embedding model for a given domain based on benchmarks."""
        items = await self._store.list(RegistryType.EMBEDDING, {"metadata.status": "active"})
        best = None
        best_score = -1.0
        for item in items:
            for benchmark in item.get("benchmarks", []):
                if benchmark.get("domain") == domain and benchmark.get("score", 0) > best_score:
                    best = item
                    best_score = benchmark["score"]
        return best

    # -------------------------------------------------------------------------
    # VECTOR INDEX REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_vector_index(self, entry: VectorIndexRegistryEntry, actor: str) -> str:
        """Register a new vector index."""
        entry.metadata.status = LifecycleStatus.ACTIVE
        item_id = await self._store.create(RegistryType.VECTOR_INDEX, self._serialize(entry))
        self._audit(actor, "register_vector_index", RegistryType.VECTOR_INDEX, item_id)
        return item_id

    async def get_stale_indexes(self) -> list[dict[str, Any]]:
        """Find all vector indexes that are past their freshness SLA."""
        items = await self._store.list(RegistryType.VECTOR_INDEX, {"metadata.status": "active"})
        stale = []
        now = datetime.utcnow()
        for item in items:
            last_updated = item.get("last_updated_at")
            sla_hours = item.get("freshness_sla_hours", 24)
            if not last_updated or (now - datetime.fromisoformat(last_updated)) > timedelta(hours=sla_hours):
                stale.append(item)
        return stale

    # -------------------------------------------------------------------------
    # EVAL REGISTRY OPERATIONS
    # -------------------------------------------------------------------------

    async def register_eval(self, entry: EvalRegistryEntry, actor: str) -> str:
        """Register a new eval suite."""
        entry.metadata.status = LifecycleStatus.ACTIVE
        item_id = await self._store.create(RegistryType.EVAL, self._serialize(entry))
        self._audit(actor, "register_eval", RegistryType.EVAL, item_id)
        return item_id

    async def record_eval_run(self, eval_id: str, result: EvalRunResult, actor: str) -> bool:
        """Record results of an eval run."""
        eval_data = await self._store.get(RegistryType.EVAL, eval_id)
        if not eval_data:
            return False
        run_history = eval_data.get("run_history", [])
        run_history.append(self._serialize(result))
        await self._store.update(
            RegistryType.EVAL, eval_id,
            {"last_run": self._serialize(result), "run_history": run_history}
        )
        self._audit(actor, "record_eval_run", RegistryType.EVAL, eval_id)
        return True

    # -------------------------------------------------------------------------
    # SEARCH AND DISCOVERY
    # -------------------------------------------------------------------------

    async def search(
        self,
        query: str,
        registry_types: Optional[list[RegistryType]] = None,
        status: Optional[LifecycleStatus] = None,
        team: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search across registries."""
        types = registry_types or list(RegistryType)
        results = await self._store.search(query, types, limit=limit * 2)
        # Post-filter
        if status:
            results = [r for r in results if r.get("metadata", {}).get("status") == status.value]
        if team:
            results = [r for r in results if r.get("metadata", {}).get("owner_team") == team]
        return results[:limit]

    async def discover_related(self, registry_type: RegistryType, item_id: str) -> dict[str, list[dict[str, Any]]]:
        """Discover items related to a given registry item."""
        related: dict[str, list[dict[str, Any]]] = {
            "uses": [],
            "used_by": [],
            "same_owner": [],
        }
        item = await self._store.get(registry_type, item_id)
        if not item:
            return related

        owner = item.get("metadata", {}).get("owner_team", "")
        if owner:
            for rt in RegistryType:
                items = await self._store.list(rt, {"metadata.owner_team": owner}, limit=10)
                for i in items:
                    if i.get("metadata", {}).get("id") != item_id:
                        related["same_owner"].append({"type": rt.value, **i})

        # Find usage relationships
        if registry_type == RegistryType.MODEL:
            agents = await self._store.list(RegistryType.AGENT, {"model_id": item_id})
            related["used_by"].extend(agents)
        elif registry_type == RegistryType.TOOL:
            agents = await self._store.list(RegistryType.AGENT, {})
            for agent in agents:
                if item_id in agent.get("tool_ids", []):
                    related["used_by"].append(agent)

        return related

    # -------------------------------------------------------------------------
    # APPROVAL WORKFLOW
    # -------------------------------------------------------------------------

    async def approve(self, approval_id: str, approver: str, approved: bool, reason: str = "") -> bool:
        """Process an approval decision."""
        for req in self._approval_queue:
            if req.id == approval_id:
                if approved:
                    req.current_approvals.append({
                        "approver": approver,
                        "approved": True,
                        "at": datetime.utcnow().isoformat(),
                    })
                    if req.is_fully_approved:
                        req.status = ApprovalStatus.APPROVED
                        await self._store.update(
                            req.registry_type, req.item_id,
                            {"metadata": {"status": LifecycleStatus.ACTIVE.value}}
                        )
                else:
                    req.status = ApprovalStatus.REJECTED
                    req.rejection_reason = reason
                    await self._store.update(
                        req.registry_type, req.item_id,
                        {"metadata": {"status": LifecycleStatus.DRAFT.value}}
                    )
                self._audit(approver, f"{'approve' if approved else 'reject'}_{req.registry_type.value}", req.registry_type, req.item_id)
                return True
        return False

    async def get_pending_approvals(self, approver: Optional[str] = None) -> list[ApprovalRequest]:
        """Get pending approval requests."""
        pending = [r for r in self._approval_queue if r.status == ApprovalStatus.PENDING]
        if approver:
            pending = [r for r in pending if approver in r.required_approvers]
        return pending

    # -------------------------------------------------------------------------
    # DEPRECATION AND RETIREMENT
    # -------------------------------------------------------------------------

    async def deprecate(
        self,
        registry_type: RegistryType,
        item_id: str,
        actor: str,
        reason: str,
        successor_id: Optional[str] = None,
        retirement_days: int = 90,
        migration_guide_url: str = "",
    ) -> DeprecationNotice:
        """Deprecate a registry item with notice period."""
        item = await self._store.get(registry_type, item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found in {registry_type.value}")

        retirement_date = datetime.utcnow() + timedelta(days=retirement_days)
        notice = DeprecationNotice(
            registry_type=registry_type,
            item_id=item_id,
            item_name=item.get("metadata", {}).get("name", ""),
            retirement_date=retirement_date,
            successor_id=successor_id,
            migration_guide_url=migration_guide_url,
            reason=reason,
        )

        # Find affected teams/agents
        if registry_type == RegistryType.MODEL:
            agents = await self._store.list(RegistryType.AGENT, {"model_id": item_id})
            notice.affected_agents = [a.get("metadata", {}).get("id", "") for a in agents]
            notice.affected_teams = list({a.get("metadata", {}).get("owner_team", "") for a in agents})

        # Update the item status
        await self._store.update(registry_type, item_id, {
            "metadata": {
                "status": LifecycleStatus.DEPRECATED.value,
                "deprecated_at": datetime.utcnow().isoformat(),
                "retirement_date": retirement_date.isoformat(),
                "successor_id": successor_id,
            }
        })

        self._deprecation_notices.append(notice)
        self._audit(actor, "deprecate", registry_type, item_id, {"reason": reason})
        return notice

    async def retire(self, registry_type: RegistryType, item_id: str, actor: str) -> bool:
        """Retire a deprecated item (make it unavailable)."""
        item = await self._store.get(registry_type, item_id)
        if not item:
            return False
        if item.get("metadata", {}).get("status") != LifecycleStatus.DEPRECATED.value:
            raise ValueError("Can only retire deprecated items")

        await self._store.update(registry_type, item_id, {
            "metadata": {"status": LifecycleStatus.RETIRED.value}
        })
        self._audit(actor, "retire", registry_type, item_id)
        return True

    async def get_upcoming_retirements(self, days: int = 30) -> list[DeprecationNotice]:
        """Get items retiring within the next N days."""
        cutoff = datetime.utcnow() + timedelta(days=days)
        return [
            n for n in self._deprecation_notices
            if n.retirement_date <= cutoff
        ]

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_required_approvers(self, risk_tier: RiskTier) -> list[str]:
        """Determine required approvers based on risk tier."""
        mapping = {
            RiskTier.T1_UNRESTRICTED: [],
            RiskTier.T2_STANDARD: ["team-lead"],
            RiskTier.T3_SENSITIVE: ["security-team", "team-lead"],
            RiskTier.T4_CRITICAL: ["security-team", "legal-team", "ciso"],
        }
        return mapping.get(risk_tier, [])

    def _audit(
        self, actor: str, action: str, resource_type: RegistryType,
        resource_id: str, changes: Optional[dict[str, Any]] = None
    ):
        """Record an audit entry."""
        self._audit_log.append(AuditEntry(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes or {},
        ))

    def _serialize(self, obj: Any) -> dict[str, Any]:
        """Serialize a dataclass to dict."""
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                result[field_name] = self._serialize(value)
            return result
        elif isinstance(obj, list):
            return [self._serialize(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _deserialize_model(self, data: dict[str, Any]) -> ModelRegistryEntry:
        """Deserialize model data (simplified)."""
        entry = ModelRegistryEntry()
        entry.metadata.id = data.get("metadata", {}).get("id", "")
        entry.metadata.name = data.get("metadata", {}).get("name", "")
        entry.provider = data.get("provider", "")
        entry.model_id = data.get("model_id", "")
        return entry

    def _deserialize_prompt(self, data: dict[str, Any]) -> PromptRegistryEntry:
        """Deserialize prompt data (simplified)."""
        entry = PromptRegistryEntry()
        entry.metadata.id = data.get("metadata", {}).get("id", "")
        entry.metadata.name = data.get("metadata", {}).get("name", "")
        entry.template = data.get("template", "")
        entry.system_prompt = data.get("system_prompt")
        entry.environments = data.get("environments", {})
        entry.eval_results = data.get("eval_results", [])
        return entry


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def main():
    """Demonstrate registry operations."""
    store = InMemoryRegistryStore()
    registry = CentralRegistryService(store)

    # Register a model
    model = ModelRegistryEntry(
        metadata=RegistryMetadata(
            name="gpt-4o",
            description="OpenAI GPT-4o - multimodal, fast, cost-effective",
            version="2024-08-06",
            owner_team="platform-team",
            owner_email="platform@company.com",
            tags=["openai", "multimodal", "production"],
            risk_tier=RiskTier.T2_STANDARD,
        ),
        provider="openai",
        model_id="gpt-4o-2024-08-06",
        capabilities=ModelCapabilities(
            function_calling=True, vision=True, structured_output=True,
            max_context_tokens=128000, max_output_tokens=16384,
        ),
        cost=ModelCost(input_cost_per_1k_tokens=0.0025, output_cost_per_1k_tokens=0.01),
        deployments=[ModelDeployment(
            provider="azure", endpoint="https://myorg.openai.azure.com",
            region="eastus2", quota_tpm=150000, quota_rpm=500,
        )],
    )
    model_id, _ = await registry.register_model(model, "admin@company.com")
    print(f"Registered model: {model_id}")

    # Register a prompt
    prompt = PromptRegistryEntry(
        metadata=RegistryMetadata(
            name="customer-support-classifier",
            description="Classifies customer support tickets into categories",
            version="2.1.0",
            owner_team="support-engineering",
            owner_email="support-eng@company.com",
            tags=["classification", "support", "production"],
        ),
        template="Classify the following support ticket into one of: {{categories}}\n\nTicket: {{ticket_text}}\n\nCategory:",
        system_prompt="You are a support ticket classifier. Respond with only the category name.",
        variables=[
            PromptVariable(name="categories", description="Comma-separated list of valid categories"),
            PromptVariable(name="ticket_text", description="The support ticket text", max_length=5000),
        ],
        recommended_model_id=model_id,
    )
    prompt_id = await registry.register_prompt(prompt, "eng@company.com")
    print(f"Registered prompt: {prompt_id}")

    # Register a tool
    tool = ToolRegistryEntry(
        metadata=RegistryMetadata(
            name="lookup-customer",
            description="Look up customer information by ID or email",
            owner_team="platform-team",
            tags=["customer", "lookup", "crm"],
        ),
        risk_level=ToolRiskLevel.READ_ONLY_INTERNAL,
        endpoint="https://internal-api.company.com/customers/lookup",
        parameters=[
            ToolParameter(name="customer_id", type="string", description="Customer ID", required=False),
            ToolParameter(name="email", type="string", description="Customer email", required=False),
        ],
    )
    tool_id, _ = await registry.register_tool(tool, "eng@company.com")
    print(f"Registered tool: {tool_id}")

    # Search across registries
    results = await registry.search("customer", registry_types=[RegistryType.PROMPT, RegistryType.TOOL])
    print(f"Search results: {len(results)} items found")

    # Deprecate the prompt
    notice = await registry.deprecate(
        RegistryType.PROMPT, prompt_id, "admin@company.com",
        reason="Replacing with v3 that uses structured output",
        retirement_days=60,
    )
    print(f"Deprecated prompt, retirement: {notice.retirement_date}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
