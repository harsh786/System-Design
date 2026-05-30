"""
==============================================================================
PROJECT 2: Agentic RAG Assistant
==============================================================================
An AI assistant that goes beyond simple RAG by:
- Decomposing complex queries into sub-queries with dependency tracking
- Iteratively retrieving until sufficiency is established
- Using SQL and API tools for structured data access
- Verifying claims at the individual statement level
- Computing composite confidence scores
- Abstaining when confidence is too low
- Escalating to humans when appropriate

Demonstrates: agent orchestration, tool use, confidence calibration,
graceful degradation, and production-grade error handling.
==============================================================================
"""

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np

# ==============================================================================
# DOMAIN MODELS
# ==============================================================================

class QueryComplexity(Enum):
    SIMPLE = "simple"          # Single fact lookup
    MODERATE = "moderate"      # Requires 2-3 sub-queries
    COMPLEX = "complex"        # Requires decomposition + tools
    MULTI_HOP = "multi_hop"   # Requires chained reasoning


class ToolType(Enum):
    RAG_RETRIEVAL = "rag_retrieval"
    SQL_QUERY = "sql_query"
    API_CALL = "api_call"
    CALCULATOR = "calculator"
    DATE_RESOLVER = "date_resolver"


class EscalationReason(Enum):
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING_SOURCES = "conflicting_sources"
    SENSITIVE_TOPIC = "sensitive_topic"
    POLICY_VIOLATION = "policy_violation"
    TOOL_FAILURE = "tool_failure"
    USER_REQUEST = "user_request"
    OUT_OF_SCOPE = "out_of_scope"


class AgentState(Enum):
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    REASONING = "reasoning"
    VERIFYING = "verifying"
    GENERATING = "generating"
    ABSTAINING = "abstaining"
    ESCALATING = "escalating"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class SubQuery:
    """A decomposed sub-query with dependencies."""
    sub_query_id: str
    text: str
    depends_on: List[str] = field(default_factory=list)  # sub_query_ids
    tool_hint: Optional[ToolType] = None
    resolved: bool = False
    result: Optional[str] = None
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)


@dataclass
class ToolCall:
    """A tool invocation with input/output tracking."""
    tool_id: str
    tool_type: ToolType
    input_params: Dict[str, Any]
    output: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0


@dataclass
class Claim:
    """An individual claim extracted from generated text."""
    claim_id: str
    text: str
    source_chunk_ids: List[str] = field(default_factory=list)
    verified: bool = False
    verification_score: float = 0.0
    verification_method: str = ""


@dataclass
class AgentTrace:
    """Complete execution trace for debugging and evaluation."""
    trace_id: str
    query: str
    sub_queries: List[SubQuery] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)
    states: List[Tuple[AgentState, float]] = field(default_factory=list)  # (state, timestamp)
    final_answer: Optional[str] = None
    confidence: float = 0.0
    escalated: bool = False
    escalation_reason: Optional[EscalationReason] = None
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class EscalationTicket:
    """Ticket created when agent escalates to human."""
    ticket_id: str
    query: str
    reason: EscalationReason
    context: Dict[str, Any]
    partial_answer: Optional[str] = None
    confidence: float = 0.0
    trace_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    status: str = "open"


@dataclass
class AgentConfig:
    """Configuration for the agentic RAG assistant."""
    max_iterations: int = 10
    max_sub_queries: int = 5
    confidence_threshold: float = 0.7
    abstention_threshold: float = 0.4
    max_tool_retries: int = 3
    sufficiency_check_after: int = 2  # Check sufficiency after N retrievals
    enable_claim_verification: bool = True
    enable_escalation: bool = True
    sensitive_topics: List[str] = field(default_factory=lambda: [
        "legal", "medical", "financial_advice", "pii", "security_vulnerability"
    ])
    cost_budget_per_query: float = 0.50  # USD


# ==============================================================================
# TOOL INTERFACES
# ==============================================================================

class Tool(ABC):
    """Base class for agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        pass

    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema for tool inputs."""
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Any:
        pass


class RAGRetrievalTool(Tool):
    """Tool for retrieving information from the knowledge base."""

    @property
    def name(self) -> str:
        return "knowledge_base_search"

    @property
    def description(self) -> str:
        return (
            "Search the internal knowledge base for information. "
            "Returns relevant document chunks with similarity scores."
        )

    @property
    def tool_type(self) -> ToolType:
        return ToolType.RAG_RETRIEVAL

    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 5},
                "filters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "date_range": {"type": "object"},
                    }
                }
            },
            "required": ["query"]
        }

    async def execute(self, params: Dict[str, Any]) -> Any:
        """Execute knowledge base search."""
        query = params["query"]
        top_k = params.get("top_k", 5)

        # Simulated retrieval results
        await asyncio.sleep(0.05)
        results = []
        for i in range(min(top_k, 3)):
            results.append({
                "chunk_id": f"chunk_{hash(query) % 1000}_{i}",
                "content": f"Relevant information for '{query[:30]}...' "
                           f"from document section {i+1}. This contains "
                           f"specific details about the topic including "
                           f"key facts and figures.",
                "score": 0.85 - (i * 0.1),
                "source": f"doc_{i+1}",
                "section": f"Section {i+1}",
            })

        return {"results": results, "total_found": len(results)}


class SQLQueryTool(Tool):
    """Tool for executing SQL queries against structured databases."""

    def __init__(self):
        self._schema_cache: Dict[str, List[Dict]] = {
            "employees": [
                {"column": "id", "type": "INTEGER", "primary_key": True},
                {"column": "name", "type": "VARCHAR(255)"},
                {"column": "department", "type": "VARCHAR(100)"},
                {"column": "salary", "type": "DECIMAL(10,2)"},
                {"column": "hire_date", "type": "DATE"},
                {"column": "manager_id", "type": "INTEGER"},
            ],
            "projects": [
                {"column": "id", "type": "INTEGER", "primary_key": True},
                {"column": "name", "type": "VARCHAR(255)"},
                {"column": "status", "type": "VARCHAR(50)"},
                {"column": "budget", "type": "DECIMAL(12,2)"},
                {"column": "start_date", "type": "DATE"},
                {"column": "end_date", "type": "DATE"},
            ],
            "metrics": [
                {"column": "id", "type": "INTEGER", "primary_key": True},
                {"column": "metric_name", "type": "VARCHAR(100)"},
                {"column": "value", "type": "DECIMAL(10,4)"},
                {"column": "recorded_at", "type": "TIMESTAMP"},
                {"column": "dimension", "type": "VARCHAR(100)"},
            ],
        }

    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return (
            "Execute SQL queries against the company database. "
            "Available tables: employees, projects, metrics. "
            "Use for quantitative questions about headcount, budgets, performance."
        )

    @property
    def tool_type(self) -> ToolType:
        return ToolType.SQL_QUERY

    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL query to execute (SELECT only)"
                },
                "explain": {
                    "type": "boolean",
                    "description": "Whether to include query plan",
                    "default": False,
                }
            },
            "required": ["query"]
        }

    async def execute(self, params: Dict[str, Any]) -> Any:
        """Execute SQL query with safety checks."""
        query = params["query"]

        # Safety: only allow SELECT
        if not query.strip().upper().startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed", "rows": []}

        # Safety: check for dangerous patterns
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
        for keyword in dangerous:
            if keyword in query.upper():
                return {"error": f"Forbidden keyword: {keyword}", "rows": []}

        # Simulated query execution
        await asyncio.sleep(0.03)
        return {
            "columns": ["name", "value"],
            "rows": [
                ["Engineering Headcount", "142"],
                ["Average Salary", "125000"],
                ["Active Projects", "23"],
            ],
            "row_count": 3,
            "execution_time_ms": 45,
        }

    def get_schema(self) -> Dict[str, List[Dict]]:
        """Return database schema for LLM context."""
        return self._schema_cache


class APICallTool(Tool):
    """Tool for making structured API calls to internal services."""

    def __init__(self):
        self._available_apis = {
            "user_service": {
                "base_url": "https://api.internal/users",
                "endpoints": ["GET /users/{id}", "GET /users/search"],
            },
            "project_service": {
                "base_url": "https://api.internal/projects",
                "endpoints": ["GET /projects/{id}", "GET /projects/status/{status}"],
            },
            "metrics_service": {
                "base_url": "https://api.internal/metrics",
                "endpoints": ["GET /metrics/{name}", "GET /metrics/dashboard"],
            },
        }

    @property
    def name(self) -> str:
        return "api_call"

    @property
    def description(self) -> str:
        return (
            "Make API calls to internal services. "
            "Available: user_service, project_service, metrics_service."
        )

    @property
    def tool_type(self) -> ToolType:
        return ToolType.API_CALL

    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service": {"type": "string", "enum": list(self._available_apis.keys())},
                "endpoint": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["service", "endpoint"]
        }

    async def execute(self, params: Dict[str, Any]) -> Any:
        """Execute API call with retry and error handling."""
        service = params["service"]
        endpoint = params["endpoint"]

        if service not in self._available_apis:
            return {"error": f"Unknown service: {service}"}

        # Simulated API response
        await asyncio.sleep(0.04)
        return {
            "status": 200,
            "data": {
                "result": f"Response from {service}/{endpoint}",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }


class CalculatorTool(Tool):
    """Tool for mathematical calculations."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform mathematical calculations. Supports basic arithmetic and common functions."

    @property
    def tool_type(self) -> ToolType:
        return ToolType.CALCULATOR

    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate"},
            },
            "required": ["expression"]
        }

    async def execute(self, params: Dict[str, Any]) -> Any:
        """Safely evaluate mathematical expression."""
        expression = params["expression"]

        # Safety: only allow safe math operations
        allowed_chars = set("0123456789+-*/().%^ ")
        if not all(c in allowed_chars for c in expression):
            return {"error": "Invalid characters in expression"}

        try:
            # Safe eval with restricted builtins
            result = eval(expression, {"__builtins__": {}}, {})
            return {"result": result, "expression": expression}
        except Exception as e:
            return {"error": str(e)}


# ==============================================================================
# QUERY DECOMPOSITION ENGINE
# ==============================================================================

class QueryDecomposer:
    """
    Decomposes complex queries into sub-queries with dependency tracking.
    Uses LLM to understand query structure and plan retrieval strategy.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def decompose(self, query: str) -> Tuple[List[SubQuery], QueryComplexity]:
        """
        Decompose query into sub-queries.
        Returns sub-queries and assessed complexity.
        """
        complexity = self._assess_complexity(query)

        if complexity == QueryComplexity.SIMPLE:
            # No decomposition needed
            sub_queries = [SubQuery(
                sub_query_id="sq_0",
                text=query,
                tool_hint=ToolType.RAG_RETRIEVAL,
            )]
        elif complexity == QueryComplexity.MODERATE:
            sub_queries = await self._moderate_decomposition(query)
        else:
            sub_queries = await self._complex_decomposition(query)

        self.logger.info(
            f"Decomposed query into {len(sub_queries)} sub-queries "
            f"(complexity: {complexity.value})"
        )
        return sub_queries, complexity

    def _assess_complexity(self, query: str) -> QueryComplexity:
        """Assess query complexity based on linguistic signals."""
        signals = {
            "comparison": ["compare", "versus", "vs", "difference between", "better"],
            "aggregation": ["how many", "total", "average", "sum", "count"],
            "multi_hop": ["and also", "in addition", "furthermore", "as well as"],
            "temporal": ["over time", "trend", "changed", "history", "previously"],
            "conditional": ["if", "when", "assuming", "given that", "depending"],
        }

        query_lower = query.lower()
        matched_signals = sum(
            1 for patterns in signals.values()
            if any(p in query_lower for p in patterns)
        )

        # Count question marks and conjunctions
        conjunctions = query_lower.count(" and ") + query_lower.count(" or ")

        if matched_signals == 0 and conjunctions == 0:
            return QueryComplexity.SIMPLE
        elif matched_signals <= 1 and conjunctions <= 1:
            return QueryComplexity.MODERATE
        elif matched_signals <= 2:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.MULTI_HOP

    async def _moderate_decomposition(self, query: str) -> List[SubQuery]:
        """Decompose moderate complexity queries."""
        # In production: use LLM for decomposition
        # Simplified: split on conjunctions and identify tool needs
        parts = re.split(r'\band\b|\bor\b|,\s*(?=\w)', query, flags=re.IGNORECASE)
        sub_queries = []

        for i, part in enumerate(parts):
            part = part.strip().rstrip("?.")
            if not part:
                continue

            tool_hint = self._infer_tool(part)
            sub_queries.append(SubQuery(
                sub_query_id=f"sq_{i}",
                text=part + "?",
                tool_hint=tool_hint,
                depends_on=[f"sq_{i-1}"] if i > 0 and self._has_dependency(part) else [],
            ))

        return sub_queries[:self.config.max_sub_queries]

    async def _complex_decomposition(self, query: str) -> List[SubQuery]:
        """Decompose complex/multi-hop queries using LLM planning."""
        # In production: use LLM with structured output
        # Simulated: create a research plan

        sub_queries = [
            SubQuery(
                sub_query_id="sq_0",
                text=f"What are the key concepts related to: {query[:50]}?",
                tool_hint=ToolType.RAG_RETRIEVAL,
            ),
            SubQuery(
                sub_query_id="sq_1",
                text=f"What quantitative data is available for: {query[:50]}?",
                tool_hint=ToolType.SQL_QUERY,
                depends_on=["sq_0"],
            ),
            SubQuery(
                sub_query_id="sq_2",
                text=f"What is the current status of: {query[:50]}?",
                tool_hint=ToolType.API_CALL,
                depends_on=["sq_0"],
            ),
            SubQuery(
                sub_query_id="sq_3",
                text=query,
                tool_hint=ToolType.RAG_RETRIEVAL,
                depends_on=["sq_1", "sq_2"],
            ),
        ]

        return sub_queries[:self.config.max_sub_queries]

    def _infer_tool(self, text: str) -> ToolType:
        """Infer the best tool for a sub-query."""
        text_lower = text.lower()

        sql_signals = ["how many", "count", "average", "total", "sum",
                       "salary", "budget", "headcount", "revenue"]
        api_signals = ["current status", "right now", "latest", "real-time",
                       "live", "active"]

        if any(s in text_lower for s in sql_signals):
            return ToolType.SQL_QUERY
        elif any(s in text_lower for s in api_signals):
            return ToolType.API_CALL
        else:
            return ToolType.RAG_RETRIEVAL

    def _has_dependency(self, text: str) -> bool:
        """Check if a sub-query likely depends on a previous answer."""
        dependency_signals = ["that", "those", "this", "it", "they",
                             "the result", "based on", "given"]
        return any(s in text.lower() for s in dependency_signals)


# ==============================================================================
# SUFFICIENCY CHECKER
# ==============================================================================

class SufficiencyChecker:
    """
    Determines if enough information has been gathered to answer the query.
    Prevents unnecessary additional retrievals (saves cost/latency).
    """

    def __init__(self, config: AgentConfig):
        self.config = config

    async def check(
        self,
        query: str,
        sub_queries: List[SubQuery],
        gathered_info: List[Dict[str, Any]],
    ) -> Tuple[bool, float, str]:
        """
        Check if gathered information is sufficient to answer.
        Returns: (is_sufficient, confidence, reason)
        """
        if not gathered_info:
            return False, 0.0, "No information gathered yet"

        # Check sub-query resolution
        resolved_count = sum(1 for sq in sub_queries if sq.resolved)
        total_count = len(sub_queries)
        resolution_ratio = resolved_count / max(total_count, 1)

        # Check information coverage
        coverage = self._compute_coverage(query, gathered_info)

        # Check source agreement
        agreement = self._check_source_agreement(gathered_info)

        # Composite sufficiency score
        sufficiency_score = (
            0.4 * resolution_ratio +
            0.4 * coverage +
            0.2 * agreement
        )

        is_sufficient = sufficiency_score >= self.config.confidence_threshold
        reason = self._explain_decision(
            is_sufficient, resolution_ratio, coverage, agreement
        )

        return is_sufficient, sufficiency_score, reason

    def _compute_coverage(
        self, query: str, gathered_info: List[Dict[str, Any]]
    ) -> float:
        """Estimate how well gathered info covers the query."""
        query_terms = set(query.lower().split())
        covered_terms = set()

        for info in gathered_info:
            content = str(info.get("content", "")).lower()
            covered_terms.update(query_terms & set(content.split()))

        return len(covered_terms) / max(len(query_terms), 1)

    def _check_source_agreement(self, gathered_info: List[Dict[str, Any]]) -> float:
        """Check if multiple sources agree (higher agreement = higher confidence)."""
        if len(gathered_info) <= 1:
            return 0.5  # Neutral when single source

        # Simplified: check overlap between source contents
        contents = [str(info.get("content", "")) for info in gathered_info]
        total_overlap = 0
        comparisons = 0

        for i in range(len(contents)):
            for j in range(i + 1, len(contents)):
                words_i = set(contents[i].lower().split())
                words_j = set(contents[j].lower().split())
                if words_i and words_j:
                    overlap = len(words_i & words_j) / max(len(words_i | words_j), 1)
                    total_overlap += overlap
                    comparisons += 1

        return total_overlap / max(comparisons, 1)

    def _explain_decision(
        self, is_sufficient: bool, resolution: float,
        coverage: float, agreement: float
    ) -> str:
        """Explain the sufficiency decision."""
        if is_sufficient:
            return (f"Sufficient: {resolution:.0%} sub-queries resolved, "
                    f"{coverage:.0%} coverage, {agreement:.0%} source agreement")
        else:
            gaps = []
            if resolution < 0.7:
                gaps.append(f"only {resolution:.0%} sub-queries resolved")
            if coverage < 0.6:
                gaps.append(f"low coverage ({coverage:.0%})")
            if agreement < 0.3:
                gaps.append("sources disagree")
            return f"Insufficient: {', '.join(gaps)}"


# ==============================================================================
# CLAIM VERIFIER
# ==============================================================================

class ClaimVerifier:
    """
    Extracts and verifies individual claims in generated answers.
    Each claim must be traceable to source material.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def extract_and_verify(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
    ) -> List[Claim]:
        """Extract claims from answer and verify against sources."""
        claims = self._extract_claims(answer)

        for claim in claims:
            verification = await self._verify_claim(claim, sources)
            claim.verified = verification["verified"]
            claim.verification_score = verification["score"]
            claim.verification_method = verification["method"]
            claim.source_chunk_ids = verification["source_ids"]

        verified_count = sum(1 for c in claims if c.verified)
        self.logger.info(
            f"Verified {verified_count}/{len(claims)} claims"
        )

        return claims

    def _extract_claims(self, text: str) -> List[Claim]:
        """Extract individual factual claims from text."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        claims = []

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            # Skip non-factual sentences
            if self._is_factual_claim(sentence):
                claims.append(Claim(
                    claim_id=f"claim_{i}",
                    text=sentence,
                ))

        return claims

    def _is_factual_claim(self, sentence: str) -> bool:
        """Determine if a sentence contains a verifiable factual claim."""
        # Skip questions, hedges, meta-statements
        if sentence.endswith("?"):
            return False
        if sentence.startswith(("I think", "Perhaps", "Maybe", "It seems")):
            return False
        if len(sentence.split()) < 5:
            return False
        return True

    async def _verify_claim(
        self, claim: Claim, sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify a single claim against source material."""
        claim_words = set(claim.text.lower().split())
        best_score = 0.0
        best_sources = []

        for source in sources:
            content = str(source.get("content", "")).lower()
            source_words = set(content.split())

            # Compute support score
            if source_words:
                overlap = len(claim_words & source_words) / max(len(claim_words), 1)
                if overlap > best_score:
                    best_score = overlap
                    best_sources = [source.get("chunk_id", "unknown")]
                elif overlap == best_score and overlap > 0.3:
                    best_sources.append(source.get("chunk_id", "unknown"))

        verified = best_score > 0.4  # Threshold for verification

        return {
            "verified": verified,
            "score": best_score,
            "method": "term_overlap" if verified else "insufficient_support",
            "source_ids": best_sources,
        }

    def compute_groundedness(self, claims: List[Claim]) -> float:
        """Compute overall groundedness score."""
        if not claims:
            return 0.0
        verified_scores = [c.verification_score for c in claims]
        return sum(verified_scores) / len(verified_scores)


# ==============================================================================
# CONFIDENCE SCORER
# ==============================================================================

class ConfidenceScorer:
    """
    Computes composite confidence scores from multiple signals.
    Calibrated against human judgments.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        # Calibration parameters (learned from human feedback)
        self._weights = {
            "retrieval_quality": 0.25,
            "source_agreement": 0.20,
            "claim_verification": 0.25,
            "coverage": 0.15,
            "tool_success": 0.15,
        }

    def compute(
        self,
        retrieval_scores: List[float],
        claim_verification_scores: List[float],
        source_agreement: float,
        coverage: float,
        tool_success_rate: float,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute composite confidence with component breakdown.
        Returns: (overall_confidence, component_scores)
        """
        components = {}

        # Retrieval quality: top scores indicate good matches
        if retrieval_scores:
            components["retrieval_quality"] = min(
                sum(retrieval_scores[:3]) / 3, 1.0
            )
        else:
            components["retrieval_quality"] = 0.0

        # Source agreement
        components["source_agreement"] = source_agreement

        # Claim verification
        if claim_verification_scores:
            components["claim_verification"] = (
                sum(claim_verification_scores) / len(claim_verification_scores)
            )
        else:
            components["claim_verification"] = 0.5  # Neutral

        # Coverage
        components["coverage"] = coverage

        # Tool success
        components["tool_success"] = tool_success_rate

        # Weighted combination
        overall = sum(
            self._weights[k] * components[k]
            for k in self._weights
        )

        # Apply calibration (slight sigmoid to push towards extremes)
        overall = self._calibrate(overall)

        return overall, components

    def _calibrate(self, score: float) -> float:
        """Apply calibration function."""
        # Sigmoid-like calibration centered at 0.5
        # Makes scores more decisive (closer to 0 or 1)
        x = (score - 0.5) * 4  # Scale
        calibrated = 1 / (1 + np.exp(-x))
        return float(calibrated)

    def should_abstain(self, confidence: float) -> bool:
        """Determine if confidence is too low to provide an answer."""
        return confidence < self.config.abstention_threshold

    def should_escalate(
        self, confidence: float, components: Dict[str, float]
    ) -> Tuple[bool, Optional[EscalationReason]]:
        """Determine if the query should be escalated to a human."""
        if not self.config.enable_escalation:
            return False, None

        # Low overall confidence
        if confidence < self.config.abstention_threshold:
            return True, EscalationReason.LOW_CONFIDENCE

        # Conflicting sources
        if components.get("source_agreement", 1.0) < 0.3:
            return True, EscalationReason.CONFLICTING_SOURCES

        # Tool failures
        if components.get("tool_success", 1.0) < 0.5:
            return True, EscalationReason.TOOL_FAILURE

        return False, None


# ==============================================================================
# ESCALATION MANAGER
# ==============================================================================

class EscalationManager:
    """Manages human escalation workflow."""

    def __init__(self):
        self._tickets: Dict[str, EscalationTicket] = {}
        self._routing_rules: Dict[EscalationReason, str] = {
            EscalationReason.LOW_CONFIDENCE: "general_support",
            EscalationReason.CONFLICTING_SOURCES: "subject_matter_expert",
            EscalationReason.SENSITIVE_TOPIC: "compliance_team",
            EscalationReason.POLICY_VIOLATION: "security_team",
            EscalationReason.TOOL_FAILURE: "engineering_oncall",
        }
        self.logger = logging.getLogger(__name__)

    async def escalate(
        self,
        query: str,
        reason: EscalationReason,
        trace: AgentTrace,
        partial_answer: Optional[str] = None,
    ) -> EscalationTicket:
        """Create an escalation ticket and route to appropriate team."""
        ticket = EscalationTicket(
            ticket_id=f"esc_{uuid.uuid4().hex[:8]}",
            query=query,
            reason=reason,
            context={
                "sub_queries": [asdict(sq) for sq in trace.sub_queries],
                "tool_calls_count": len(trace.tool_calls),
                "confidence": trace.confidence,
                "gathered_sources": len(trace.tool_calls),
            },
            partial_answer=partial_answer,
            confidence=trace.confidence,
            trace_id=trace.trace_id,
            assigned_to=self._routing_rules.get(reason, "general_support"),
        )

        self._tickets[ticket.ticket_id] = ticket

        self.logger.info(
            f"Escalated to {ticket.assigned_to}: {ticket.ticket_id} "
            f"(reason: {reason.value})"
        )

        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[EscalationTicket]:
        return self._tickets.get(ticket_id)

    def get_open_tickets(self) -> List[EscalationTicket]:
        return [t for t in self._tickets.values() if t.status == "open"]


# ==============================================================================
# AGENT ORCHESTRATOR
# ==============================================================================

class AgenticRAGAssistant:
    """
    Main orchestrator implementing the ReAct (Reason-Act-Observe) loop
    with iterative retrieval, tool use, verification, and confidence estimation.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.decomposer = QueryDecomposer(config)
        self.sufficiency_checker = SufficiencyChecker(config)
        self.claim_verifier = ClaimVerifier()
        self.confidence_scorer = ConfidenceScorer(config)
        self.escalation_manager = EscalationManager()

        # Register tools
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

        # Metrics
        self._query_count = 0
        self._escalation_count = 0
        self._abstention_count = 0

    def _register_default_tools(self):
        """Register default tool set."""
        tools = [
            RAGRetrievalTool(),
            SQLQueryTool(),
            APICallTool(),
            CalculatorTool(),
        ]
        for tool in tools:
            self.tools[tool.name] = tool

    async def answer(self, query: str) -> Dict[str, Any]:
        """
        Main entry point: answer a query using the agentic RAG pipeline.

        Flow:
        1. Decompose query into sub-queries
        2. For each sub-query (respecting dependencies):
           a. Select appropriate tool
           b. Execute tool
           c. Check sufficiency
        3. Generate answer from gathered information
        4. Verify claims
        5. Score confidence
        6. Decide: answer, abstain, or escalate
        """
        self._query_count += 1
        start_time = time.time()

        trace = AgentTrace(
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            query=query,
        )
        trace.states.append((AgentState.PLANNING, time.time()))

        # --- Step 1: Check for sensitive topics ---
        if self._is_sensitive(query):
            trace.states.append((AgentState.ESCALATING, time.time()))
            ticket = await self.escalation_manager.escalate(
                query, EscalationReason.SENSITIVE_TOPIC, trace
            )
            self._escalation_count += 1
            return self._build_escalation_response(ticket, trace, start_time)

        # --- Step 2: Decompose query ---
        sub_queries, complexity = await self.decomposer.decompose(query)
        trace.sub_queries = sub_queries

        # --- Step 3: Iterative retrieval loop ---
        trace.states.append((AgentState.RETRIEVING, time.time()))
        gathered_info: List[Dict[str, Any]] = []
        tool_successes = 0
        tool_attempts = 0
        iteration = 0

        for iteration in range(self.config.max_iterations):
            # Find next resolvable sub-query
            next_sq = self._get_next_sub_query(sub_queries)
            if next_sq is None:
                break  # All resolved or blocked

            # Select and execute tool
            tool_call = await self._execute_tool_for_subquery(next_sq, gathered_info)
            trace.tool_calls.append(tool_call)
            tool_attempts += 1

            if tool_call.error is None:
                tool_successes += 1
                next_sq.resolved = True
                next_sq.result = json.dumps(tool_call.output)
                if isinstance(tool_call.output, dict):
                    results = tool_call.output.get("results", [])
                    gathered_info.extend(results)
                    next_sq.sources = [r.get("chunk_id", "") for r in results]

            # Check sufficiency (after minimum retrievals)
            if iteration >= self.config.sufficiency_check_after:
                is_sufficient, suff_score, reason = await self.sufficiency_checker.check(
                    query, sub_queries, gathered_info
                )
                if is_sufficient:
                    self.logger.info(f"Sufficiency reached at iteration {iteration}: {reason}")
                    break

        # --- Step 4: Generate answer ---
        trace.states.append((AgentState.GENERATING, time.time()))
        answer_text = await self._generate_answer(query, sub_queries, gathered_info)

        # --- Step 5: Verify claims ---
        claims = []
        if self.config.enable_claim_verification:
            trace.states.append((AgentState.VERIFYING, time.time()))
            claims = await self.claim_verifier.extract_and_verify(
                answer_text, gathered_info
            )
            trace.claims = claims

        # --- Step 6: Compute confidence ---
        retrieval_scores = [
            info.get("score", 0.0) for info in gathered_info if "score" in info
        ]
        verification_scores = [c.verification_score for c in claims]
        source_agreement = self.sufficiency_checker._check_source_agreement(gathered_info)
        coverage = self.sufficiency_checker._compute_coverage(query, gathered_info)
        tool_success_rate = tool_successes / max(tool_attempts, 1)

        confidence, confidence_components = self.confidence_scorer.compute(
            retrieval_scores=retrieval_scores,
            claim_verification_scores=verification_scores,
            source_agreement=source_agreement,
            coverage=coverage,
            tool_success_rate=tool_success_rate,
        )

        trace.confidence = confidence
        trace.final_answer = answer_text

        # --- Step 7: Decision ---
        # Check if should escalate
        should_escalate, escalation_reason = self.confidence_scorer.should_escalate(
            confidence, confidence_components
        )

        if should_escalate and escalation_reason:
            trace.states.append((AgentState.ESCALATING, time.time()))
            trace.escalated = True
            trace.escalation_reason = escalation_reason
            self._escalation_count += 1
            ticket = await self.escalation_manager.escalate(
                query, escalation_reason, trace, partial_answer=answer_text
            )
            return self._build_escalation_response(ticket, trace, start_time)

        # Check if should abstain
        if self.confidence_scorer.should_abstain(confidence):
            trace.states.append((AgentState.ABSTAINING, time.time()))
            self._abstention_count += 1
            return self._build_abstention_response(
                query, confidence, confidence_components, trace, start_time
            )

        # --- Success: return answer ---
        trace.states.append((AgentState.COMPLETE, time.time()))
        trace.total_latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "success",
            "answer": answer_text,
            "confidence": confidence,
            "confidence_components": confidence_components,
            "claims": [asdict(c) for c in claims],
            "sources_used": len(gathered_info),
            "iterations": iteration + 1,
            "trace_id": trace.trace_id,
            "latency_ms": trace.total_latency_ms,
            "metadata": {
                "complexity": complexity.value,
                "sub_queries": len(sub_queries),
                "tools_used": [tc.tool_type.value for tc in trace.tool_calls],
                "groundedness": self.claim_verifier.compute_groundedness(claims),
            },
        }

    def _get_next_sub_query(self, sub_queries: List[SubQuery]) -> Optional[SubQuery]:
        """Get next unresolved sub-query whose dependencies are met."""
        for sq in sub_queries:
            if sq.resolved:
                continue
            # Check dependencies
            deps_met = all(
                any(other.sub_query_id == dep and other.resolved
                    for other in sub_queries)
                for dep in sq.depends_on
            )
            if deps_met:
                return sq
        return None

    async def _execute_tool_for_subquery(
        self, sub_query: SubQuery, context: List[Dict[str, Any]]
    ) -> ToolCall:
        """Select and execute the appropriate tool for a sub-query."""
        start_time = time.time()

        # Select tool based on hint
        tool_name = self._select_tool(sub_query)
        tool = self.tools.get(tool_name)

        if not tool:
            return ToolCall(
                tool_id=f"tc_{uuid.uuid4().hex[:8]}",
                tool_type=sub_query.tool_hint or ToolType.RAG_RETRIEVAL,
                input_params={"query": sub_query.text},
                error=f"Tool not found: {tool_name}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Build tool parameters
        params = self._build_tool_params(tool, sub_query, context)

        # Execute with retry
        last_error = None
        for attempt in range(self.config.max_tool_retries):
            try:
                output = await tool.execute(params)
                latency_ms = (time.time() - start_time) * 1000

                return ToolCall(
                    tool_id=f"tc_{uuid.uuid4().hex[:8]}",
                    tool_type=tool.tool_type,
                    input_params=params,
                    output=output,
                    latency_ms=latency_ms,
                    retry_count=attempt,
                )
            except Exception as e:
                last_error = str(e)
                await asyncio.sleep(0.1 * (attempt + 1))  # Backoff

        return ToolCall(
            tool_id=f"tc_{uuid.uuid4().hex[:8]}",
            tool_type=tool.tool_type,
            input_params=params,
            error=last_error,
            latency_ms=(time.time() - start_time) * 1000,
            retry_count=self.config.max_tool_retries,
        )

    def _select_tool(self, sub_query: SubQuery) -> str:
        """Select tool name based on sub-query hints."""
        tool_mapping = {
            ToolType.RAG_RETRIEVAL: "knowledge_base_search",
            ToolType.SQL_QUERY: "sql_query",
            ToolType.API_CALL: "api_call",
            ToolType.CALCULATOR: "calculator",
        }
        hint = sub_query.tool_hint or ToolType.RAG_RETRIEVAL
        return tool_mapping.get(hint, "knowledge_base_search")

    def _build_tool_params(
        self, tool: Tool, sub_query: SubQuery, context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build appropriate parameters for the tool."""
        if tool.tool_type == ToolType.RAG_RETRIEVAL:
            return {"query": sub_query.text, "top_k": 5}
        elif tool.tool_type == ToolType.SQL_QUERY:
            # In production: use LLM to generate SQL from natural language
            return {"query": f"SELECT * FROM metrics LIMIT 5"}
        elif tool.tool_type == ToolType.API_CALL:
            return {
                "service": "metrics_service",
                "endpoint": "/metrics/dashboard",
                "params": {},
            }
        elif tool.tool_type == ToolType.CALCULATOR:
            return {"expression": "42"}
        else:
            return {"query": sub_query.text}

    async def _generate_answer(
        self, query: str, sub_queries: List[SubQuery],
        gathered_info: List[Dict[str, Any]]
    ) -> str:
        """Generate final answer from gathered information."""
        # In production: call LLM with structured context
        # Simulated: build answer from gathered info

        if not gathered_info:
            return "I was unable to find sufficient information to answer this question."

        # Build context from gathered info
        context_parts = []
        for i, info in enumerate(gathered_info[:5]):
            content = info.get("content", str(info))
            context_parts.append(f"[{i+1}] {content}")

        context = "\n".join(context_parts)

        # Simulated LLM generation
        await asyncio.sleep(0.05)
        return (
            f"Based on my research across {len(gathered_info)} sources, "
            f"here is what I found regarding your question about "
            f"'{query[:50]}': {context_parts[0] if context_parts else 'No information available'}. "
            f"This is supported by {len(gathered_info)} sources consulted during analysis."
        )

    def _is_sensitive(self, query: str) -> bool:
        """Check if query touches sensitive topics."""
        query_lower = query.lower()
        return any(topic in query_lower for topic in self.config.sensitive_topics)

    def _build_escalation_response(
        self, ticket: EscalationTicket, trace: AgentTrace, start_time: float
    ) -> Dict[str, Any]:
        """Build response for escalated queries."""
        return {
            "status": "escalated",
            "message": (
                f"This question has been routed to {ticket.assigned_to} "
                f"for human review (reason: {ticket.reason.value}). "
                f"Ticket ID: {ticket.ticket_id}"
            ),
            "ticket_id": ticket.ticket_id,
            "partial_answer": ticket.partial_answer,
            "confidence": trace.confidence,
            "reason": ticket.reason.value,
            "trace_id": trace.trace_id,
            "latency_ms": (time.time() - start_time) * 1000,
        }

    def _build_abstention_response(
        self, query: str, confidence: float,
        components: Dict[str, float], trace: AgentTrace, start_time: float
    ) -> Dict[str, Any]:
        """Build response when agent abstains from answering."""
        # Identify what's missing
        gaps = []
        if components.get("retrieval_quality", 0) < 0.5:
            gaps.append("relevant documents not found in knowledge base")
        if components.get("source_agreement", 0) < 0.3:
            gaps.append("available sources contain conflicting information")
        if components.get("coverage", 0) < 0.5:
            gaps.append("query topics not well covered by available documents")

        return {
            "status": "abstained",
            "message": (
                "I don't have enough confidence to provide a reliable answer. "
                f"Confidence: {confidence:.0%}. "
                f"Gaps: {'; '.join(gaps) if gaps else 'insufficient supporting evidence'}."
            ),
            "confidence": confidence,
            "confidence_components": components,
            "gaps": gaps,
            "suggestion": "Please try rephrasing your question or contact the relevant team directly.",
            "trace_id": trace.trace_id,
            "latency_ms": (time.time() - start_time) * 1000,
        }

    # --- Observability ---

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_queries": self._query_count,
            "escalation_count": self._escalation_count,
            "abstention_count": self._abstention_count,
            "escalation_rate": self._escalation_count / max(self._query_count, 1),
            "abstention_rate": self._abstention_count / max(self._query_count, 1),
            "open_tickets": len(self.escalation_manager.get_open_tickets()),
        }


# ==============================================================================
# DEMONSTRATION
# ==============================================================================

async def main():
    """Demonstrate the Agentic RAG Assistant."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = AgentConfig()
    assistant = AgenticRAGAssistant(config)

    logger.info("=" * 60)
    logger.info("Agentic RAG Assistant - Demonstration")
    logger.info("=" * 60)

    # Test queries of varying complexity
    queries = [
        # Simple query
        "What is retrieval-augmented generation?",
        # Moderate query requiring multiple sources
        "How does our engineering headcount compare to last quarter and what projects are active?",
        # Complex query requiring tools
        "What is the average salary in engineering, and how does it relate to our project budgets?",
        # Sensitive topic (should escalate)
        "What are the security vulnerabilities in our production system?",
    ]

    for i, query in enumerate(queries, 1):
        logger.info(f"\n--- Query {i}: {query[:60]}... ---")
        result = await assistant.answer(query)

        status = result["status"]
        logger.info(f"  Status: {status}")

        if status == "success":
            logger.info(f"  Answer: {result['answer'][:100]}...")
            logger.info(f"  Confidence: {result['confidence']:.2%}")
            logger.info(f"  Sources: {result['sources_used']}")
            logger.info(f"  Iterations: {result['iterations']}")
            logger.info(f"  Groundedness: {result['metadata']['groundedness']:.2%}")
        elif status == "escalated":
            logger.info(f"  Message: {result['message']}")
            logger.info(f"  Ticket: {result['ticket_id']}")
        elif status == "abstained":
            logger.info(f"  Message: {result['message']}")
            logger.info(f"  Gaps: {result['gaps']}")

        logger.info(f"  Latency: {result['latency_ms']:.1f}ms")

    # Print stats
    logger.info(f"\n--- Agent Statistics ---")
    stats = assistant.stats
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
