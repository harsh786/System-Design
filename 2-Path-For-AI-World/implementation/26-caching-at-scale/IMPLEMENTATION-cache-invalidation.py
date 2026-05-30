"""
Cache Invalidation System for Enterprise AI
=============================================
Event-driven invalidation with version tracking, freshness watermarks,
cross-region propagation, and bypass rules for high-risk scenarios.

Invalidation is the hardest problem in caching. In AI systems it's even harder
because staleness can mean security breaches (stale permissions) or
misinformation (stale source data).

Design principles:
1. When in doubt, invalidate (false invalidation = cache miss, false cache = security risk)
2. Permission changes = immediate, aggressive invalidation
3. Data changes = version bump (lazy invalidation via key change)
4. Policy changes = nuclear invalidation (all affected responses)
5. Every invalidation is logged for audit
"""

import asyncio
import hashlib
import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

class InvalidationTrigger(Enum):
    # Data changes
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    DATABASE_UPDATED = "database_updated"
    
    # Permission changes
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_CHANGED = "role_changed"
    GROUP_MEMBERSHIP_CHANGED = "group_membership_changed"
    
    # Version changes
    MODEL_VERSION_CHANGED = "model_version_changed"
    PROMPT_VERSION_CHANGED = "prompt_version_changed"
    INDEX_REBUILT = "index_rebuilt"
    TOOL_SCHEMA_CHANGED = "tool_schema_changed"
    EMBEDDING_MODEL_CHANGED = "embedding_model_changed"
    RERANKER_MODEL_CHANGED = "reranker_model_changed"
    PARSER_VERSION_CHANGED = "parser_version_changed"
    
    # Policy changes
    SAFETY_POLICY_UPDATED = "safety_policy_updated"
    GOVERNANCE_POLICY_UPDATED = "governance_policy_updated"
    RETENTION_POLICY_UPDATED = "retention_policy_updated"
    
    # Operational
    MANUAL_INVALIDATION = "manual_invalidation"
    SECURITY_INCIDENT = "security_incident"
    CACHE_POISONING_DETECTED = "cache_poisoning_detected"


class InvalidationScope(Enum):
    GLOBAL = "global"           # All tenants, all regions
    TENANT = "tenant"           # Single tenant, all regions
    USER = "user"               # Single user within tenant
    RESOURCE = "resource"       # Specific resource/document
    LAYER = "layer"             # Specific cache layer


class CacheLayerType(Enum):
    PROMPT_PREFIX = "prompt_prefix"
    SEMANTIC_RESPONSE = "semantic_response"
    RETRIEVAL_RESULT = "retrieval_result"
    EMBEDDING = "embedding"
    TOOL_RESULT = "tool_result"
    RERANKER = "reranker"
    AUTH_DECISION = "auth_decision"
    DOCUMENT_PARSE = "document_parse"
    EVAL_QUALITY = "eval_quality"


@dataclass
class InvalidationCommand:
    """A specific invalidation instruction."""
    trigger: InvalidationTrigger
    scope: InvalidationScope
    target_layers: List[CacheLayerType]
    tenant_id: str
    user_id: Optional[str] = None
    resource_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    propagate_regions: List[str] = field(default_factory=list)
    priority: int = 1  # 1=immediate, 2=high, 3=normal

    @property
    def command_id(self) -> str:
        return hashlib.md5(
            f"{self.trigger.value}:{self.tenant_id}:{self.timestamp}:{id(self)}".encode()
        ).hexdigest()[:16]


@dataclass
class FreshnessWatermark:
    """Tracks latest known data timestamp per tenant/source."""
    tenant_id: str
    source_id: str
    watermark: float  # Unix timestamp of latest data
    updated_at: float = field(default_factory=time.time)


@dataclass
class VersionState:
    """Tracks current versions of all versioned components."""
    model_version: str = "unknown"
    prompt_versions: Dict[str, str] = field(default_factory=dict)  # template_id -> version
    index_versions: Dict[str, str] = field(default_factory=dict)   # index_id -> version
    tool_schemas: Dict[str, str] = field(default_factory=dict)     # tool_name -> schema_hash
    embedding_model_version: str = "unknown"
    reranker_model_version: str = "unknown"
    parser_version: str = "unknown"
    safety_policy_version: str = "unknown"
    governance_policy_version: str = "unknown"


@dataclass
class InvalidationMetrics:
    total_events: int = 0
    events_by_trigger: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    events_by_scope: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    keys_invalidated: int = 0
    propagation_failures: int = 0
    avg_propagation_latency_ms: float = 0.0
    bypass_activations: int = 0

    def to_dict(self) -> Dict:
        return {
            "total_events": self.total_events,
            "by_trigger": dict(self.events_by_trigger),
            "by_scope": dict(self.events_by_scope),
            "keys_invalidated": self.keys_invalidated,
            "propagation_failures": self.propagation_failures,
            "avg_propagation_latency_ms": self.avg_propagation_latency_ms,
            "bypass_activations": self.bypass_activations,
        }


# =============================================================================
# Invalidation Rule Engine
# =============================================================================

class InvalidationRuleEngine:
    """
    Maps triggers to invalidation commands.
    Determines WHAT to invalidate based on WHAT changed.
    """

    # Mapping: trigger → (affected layers, scope, priority)
    RULES: Dict[InvalidationTrigger, Dict] = {
        # --- Data changes ---
        InvalidationTrigger.DOCUMENT_CREATED: {
            "layers": [CacheLayerType.RETRIEVAL_RESULT, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RERANKER],
            "scope": InvalidationScope.TENANT,
            "priority": 2,
        },
        InvalidationTrigger.DOCUMENT_UPDATED: {
            "layers": [CacheLayerType.RETRIEVAL_RESULT, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RERANKER, CacheLayerType.DOCUMENT_PARSE],
            "scope": InvalidationScope.RESOURCE,
            "priority": 2,
        },
        InvalidationTrigger.DOCUMENT_DELETED: {
            "layers": [CacheLayerType.RETRIEVAL_RESULT, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RERANKER, CacheLayerType.DOCUMENT_PARSE],
            "scope": InvalidationScope.RESOURCE,
            "priority": 1,  # Immediate — deleted data must not be served
        },
        InvalidationTrigger.DATABASE_UPDATED: {
            "layers": [CacheLayerType.TOOL_RESULT, CacheLayerType.SEMANTIC_RESPONSE],
            "scope": InvalidationScope.TENANT,
            "priority": 2,
        },

        # --- Permission changes (ALWAYS immediate) ---
        InvalidationTrigger.PERMISSION_REVOKED: {
            "layers": [CacheLayerType.AUTH_DECISION, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RETRIEVAL_RESULT, CacheLayerType.TOOL_RESULT],
            "scope": InvalidationScope.USER,
            "priority": 1,
        },
        InvalidationTrigger.PERMISSION_GRANTED: {
            "layers": [CacheLayerType.AUTH_DECISION],
            "scope": InvalidationScope.USER,
            "priority": 2,
        },
        InvalidationTrigger.ROLE_CHANGED: {
            "layers": [CacheLayerType.AUTH_DECISION, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RETRIEVAL_RESULT, CacheLayerType.TOOL_RESULT],
            "scope": InvalidationScope.USER,
            "priority": 1,
        },
        InvalidationTrigger.GROUP_MEMBERSHIP_CHANGED: {
            "layers": [CacheLayerType.AUTH_DECISION, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RETRIEVAL_RESULT],
            "scope": InvalidationScope.USER,
            "priority": 1,
        },

        # --- Version changes ---
        InvalidationTrigger.MODEL_VERSION_CHANGED: {
            "layers": [CacheLayerType.SEMANTIC_RESPONSE, CacheLayerType.EVAL_QUALITY],
            "scope": InvalidationScope.GLOBAL,
            "priority": 3,
        },
        InvalidationTrigger.PROMPT_VERSION_CHANGED: {
            "layers": [CacheLayerType.SEMANTIC_RESPONSE, CacheLayerType.PROMPT_PREFIX],
            "scope": InvalidationScope.GLOBAL,
            "priority": 2,
        },
        InvalidationTrigger.INDEX_REBUILT: {
            "layers": [CacheLayerType.RETRIEVAL_RESULT, CacheLayerType.SEMANTIC_RESPONSE,
                      CacheLayerType.RERANKER],
            "scope": InvalidationScope.TENANT,
            "priority": 2,
        },
        InvalidationTrigger.TOOL_SCHEMA_CHANGED: {
            "layers": [CacheLayerType.TOOL_RESULT],
            "scope": InvalidationScope.GLOBAL,
            "priority": 2,
        },
        InvalidationTrigger.EMBEDDING_MODEL_CHANGED: {
            "layers": [CacheLayerType.EMBEDDING, CacheLayerType.RETRIEVAL_RESULT,
                      CacheLayerType.SEMANTIC_RESPONSE, CacheLayerType.RERANKER],
            "scope": InvalidationScope.GLOBAL,
            "priority": 1,  # Embeddings are foundational
        },

        # --- Policy changes ---
        InvalidationTrigger.SAFETY_POLICY_UPDATED: {
            "layers": [CacheLayerType.SEMANTIC_RESPONSE, CacheLayerType.EVAL_QUALITY],
            "scope": InvalidationScope.GLOBAL,
            "priority": 1,
        },
        InvalidationTrigger.GOVERNANCE_POLICY_UPDATED: {
            "layers": [CacheLayerType.SEMANTIC_RESPONSE, CacheLayerType.AUTH_DECISION],
            "scope": InvalidationScope.GLOBAL,
            "priority": 1,
        },

        # --- Operational ---
        InvalidationTrigger.SECURITY_INCIDENT: {
            "layers": list(CacheLayerType),  # ALL layers
            "scope": InvalidationScope.GLOBAL,
            "priority": 1,
        },
        InvalidationTrigger.CACHE_POISONING_DETECTED: {
            "layers": list(CacheLayerType),
            "scope": InvalidationScope.GLOBAL,
            "priority": 1,
        },
    }

    def get_command(
        self,
        trigger: InvalidationTrigger,
        tenant_id: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        regions: Optional[List[str]] = None,
    ) -> InvalidationCommand:
        """Generate invalidation command from trigger."""
        rule = self.RULES.get(trigger, {
            "layers": [CacheLayerType.SEMANTIC_RESPONSE],
            "scope": InvalidationScope.TENANT,
            "priority": 3,
        })

        return InvalidationCommand(
            trigger=trigger,
            scope=rule["scope"],
            target_layers=rule["layers"],
            tenant_id=tenant_id,
            user_id=user_id,
            resource_id=resource_id,
            metadata=metadata or {},
            propagate_regions=regions or ["*"],
            priority=rule["priority"],
        )


# =============================================================================
# Cache Bypass Rules
# =============================================================================

class CacheBypassPolicy:
    """
    Determines when to SKIP the cache entirely.
    Some requests should never be served from cache.
    """

    @staticmethod
    def should_bypass(
        risk_tier: str,
        query_metadata: Dict[str, Any],
        confidence_score: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Returns (should_bypass, reason).
        """
        # Rule 1: Critical risk tier with live-data requirement
        if risk_tier == "critical" and query_metadata.get("requires_live_data"):
            return True, "critical_risk_live_data"

        # Rule 2: Explicit no-cache header from client
        if query_metadata.get("no_cache"):
            return True, "client_no_cache"

        # Rule 3: Low confidence from previous cached response
        if confidence_score is not None and confidence_score < 0.7:
            return True, "low_confidence_previous"

        # Rule 4: Query involves real-time data sources
        realtime_tools = {"stock_price", "live_feed", "current_time", "exchange_rate"}
        if query_metadata.get("tools_required", set()) & realtime_tools:
            return True, "realtime_data_required"

        # Rule 5: Audit/compliance queries (must always be fresh)
        if query_metadata.get("audit_trail_required"):
            return True, "audit_compliance"

        # Rule 6: Write operations disguised as queries
        if query_metadata.get("has_side_effects"):
            return True, "side_effects_detected"

        # Rule 7: First query in a new session (cold start — establish baseline)
        if query_metadata.get("session_first_query") and risk_tier in ("critical", "high"):
            return True, "session_cold_start_high_risk"

        return False, ""


# =============================================================================
# Freshness Watermark Tracker
# =============================================================================

class FreshnessWatermarkTracker:
    """
    Tracks the latest known data timestamp per tenant and source.
    Used to detect when cached responses are stale relative to source data.
    """

    def __init__(self):
        self._watermarks: Dict[str, Dict[str, FreshnessWatermark]] = {}  # tenant -> source -> watermark
        self._change_callbacks: List[Callable] = []

    def update_watermark(self, tenant_id: str, source_id: str, timestamp: float):
        """Update watermark when source data changes."""
        if tenant_id not in self._watermarks:
            self._watermarks[tenant_id] = {}

        old = self._watermarks[tenant_id].get(source_id)
        self._watermarks[tenant_id][source_id] = FreshnessWatermark(
            tenant_id=tenant_id,
            source_id=source_id,
            watermark=timestamp,
        )

        if old is None or timestamp > old.watermark:
            logger.info(
                f"Watermark advanced: tenant={tenant_id}, source={source_id}, "
                f"old={old.watermark if old else 'none'}, new={timestamp}"
            )
            # Notify subscribers
            for cb in self._change_callbacks:
                asyncio.create_task(cb(tenant_id, source_id, timestamp))

    def get_watermark(self, tenant_id: str, source_id: str = "*") -> float:
        """Get current watermark. Returns 0 if unknown."""
        tenant_marks = self._watermarks.get(tenant_id, {})
        if source_id == "*":
            # Return max across all sources
            if not tenant_marks:
                return 0.0
            return max(w.watermark for w in tenant_marks.values())
        mark = tenant_marks.get(source_id)
        return mark.watermark if mark else 0.0

    def is_stale(self, tenant_id: str, cached_watermark: float, source_id: str = "*") -> bool:
        """Check if a cached entry is stale relative to current watermark."""
        current = self.get_watermark(tenant_id, source_id)
        return cached_watermark < current

    def on_watermark_change(self, callback: Callable):
        """Register callback for watermark changes."""
        self._change_callbacks.append(callback)


# =============================================================================
# Version Tracker
# =============================================================================

class VersionTracker:
    """
    Tracks versions of all system components.
    Version changes trigger lazy invalidation (new keys won't match old entries).
    """

    def __init__(self):
        self._state = VersionState()
        self._change_callbacks: List[Callable] = []
        self._history: List[Dict] = []

    @property
    def current(self) -> VersionState:
        return self._state

    def update_model_version(self, version: str) -> InvalidationTrigger:
        old = self._state.model_version
        self._state.model_version = version
        self._record_change("model_version", old, version)
        return InvalidationTrigger.MODEL_VERSION_CHANGED

    def update_prompt_version(self, template_id: str, version: str) -> InvalidationTrigger:
        old = self._state.prompt_versions.get(template_id)
        self._state.prompt_versions[template_id] = version
        self._record_change(f"prompt_version:{template_id}", old, version)
        return InvalidationTrigger.PROMPT_VERSION_CHANGED

    def update_index_version(self, index_id: str, version: str) -> InvalidationTrigger:
        old = self._state.index_versions.get(index_id)
        self._state.index_versions[index_id] = version
        self._record_change(f"index_version:{index_id}", old, version)
        return InvalidationTrigger.INDEX_REBUILT

    def update_safety_policy(self, version: str) -> InvalidationTrigger:
        old = self._state.safety_policy_version
        self._state.safety_policy_version = version
        self._record_change("safety_policy_version", old, version)
        return InvalidationTrigger.SAFETY_POLICY_UPDATED

    def update_embedding_model(self, version: str) -> InvalidationTrigger:
        old = self._state.embedding_model_version
        self._state.embedding_model_version = version
        self._record_change("embedding_model_version", old, version)
        return InvalidationTrigger.EMBEDDING_MODEL_CHANGED

    def _record_change(self, component: str, old: Any, new: Any):
        self._history.append({
            "component": component,
            "old_version": old,
            "new_version": new,
            "timestamp": time.time(),
        })
        logger.info(f"Version change: {component} {old} → {new}")

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self._history[-limit:]


# =============================================================================
# Cross-Region Invalidation Propagator
# =============================================================================

class CrossRegionPropagator:
    """
    Propagates invalidation events to other regions.
    In production: uses message queue (Kafka, SNS/SQS, Event Grid).
    """

    def __init__(self, current_region: str, all_regions: List[str]):
        self.current_region = current_region
        self.all_regions = all_regions
        self._outbound_queue: asyncio.Queue = asyncio.Queue()
        self._propagation_latencies: List[float] = []
        self._failures: int = 0

    async def propagate(self, command: InvalidationCommand):
        """Send invalidation to other regions."""
        target_regions = [r for r in self.all_regions if r != self.current_region]

        if command.propagate_regions != ["*"]:
            target_regions = [r for r in target_regions if r in command.propagate_regions]

        start = time.time()
        results = await asyncio.gather(
            *[self._send_to_region(r, command) for r in target_regions],
            return_exceptions=True,
        )

        latency_ms = (time.time() - start) * 1000
        self._propagation_latencies.append(latency_ms)

        failures = sum(1 for r in results if isinstance(r, Exception))
        self._failures += failures

        if failures:
            logger.error(
                f"Invalidation propagation: {failures}/{len(target_regions)} regions failed "
                f"(command={command.command_id})"
            )

    async def _send_to_region(self, region: str, command: InvalidationCommand):
        """Send invalidation command to a specific region. Mock implementation."""
        # In production: publish to cross-region message bus
        await asyncio.sleep(0.01)  # Simulate network latency
        logger.debug(f"Propagated invalidation to region={region}, cmd={command.command_id}")

    @property
    def avg_latency_ms(self) -> float:
        if not self._propagation_latencies:
            return 0.0
        return sum(self._propagation_latencies[-100:]) / len(self._propagation_latencies[-100:])


# =============================================================================
# Main Invalidation Service
# =============================================================================

class CacheInvalidationService:
    """
    Central invalidation service that:
    1. Receives change events from various sources
    2. Applies rules to determine what to invalidate
    3. Executes invalidation across layers
    4. Propagates to other regions
    5. Logs everything for audit
    """

    def __init__(
        self,
        current_region: str = "us-east-1",
        all_regions: Optional[List[str]] = None,
    ):
        self.rule_engine = InvalidationRuleEngine()
        self.watermark_tracker = FreshnessWatermarkTracker()
        self.version_tracker = VersionTracker()
        self.bypass_policy = CacheBypassPolicy()
        self.propagator = CrossRegionPropagator(
            current_region=current_region,
            all_regions=all_regions or ["us-east-1", "eu-west-1", "ap-southeast-1"],
        )
        self.metrics = InvalidationMetrics()

        # Cache layer handlers (injected)
        self._layer_handlers: Dict[CacheLayerType, Callable] = {}

        # Audit log
        self._audit_log: List[Dict] = []

        # Processing queue for non-immediate invalidations
        self._queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None

    def register_layer_handler(self, layer: CacheLayerType, handler: Callable):
        """Register a handler that performs actual cache clearing for a layer."""
        self._layer_handlers[layer] = handler

    async def start(self):
        """Start background processing."""
        self._processing_task = asyncio.create_task(self._process_queue())
        logger.info("CacheInvalidationService started")

    async def stop(self):
        if self._processing_task:
            self._processing_task.cancel()

    # -------------------------------------------------------------------------
    # Event Handlers (called by external systems)
    # -------------------------------------------------------------------------

    async def on_document_change(
        self, tenant_id: str, document_id: str, change_type: str
    ):
        """Called when a document is created/updated/deleted."""
        trigger_map = {
            "created": InvalidationTrigger.DOCUMENT_CREATED,
            "updated": InvalidationTrigger.DOCUMENT_UPDATED,
            "deleted": InvalidationTrigger.DOCUMENT_DELETED,
        }
        trigger = trigger_map.get(change_type, InvalidationTrigger.DOCUMENT_UPDATED)

        command = self.rule_engine.get_command(
            trigger=trigger,
            tenant_id=tenant_id,
            resource_id=document_id,
            metadata={"change_type": change_type, "document_id": document_id},
        )

        # Update freshness watermark
        self.watermark_tracker.update_watermark(tenant_id, "documents", time.time())

        await self._execute_invalidation(command)

    async def on_permission_change(
        self, tenant_id: str, user_id: str, change_type: str, details: Dict
    ):
        """Called when user permissions change. ALWAYS immediate."""
        trigger_map = {
            "revoked": InvalidationTrigger.PERMISSION_REVOKED,
            "granted": InvalidationTrigger.PERMISSION_GRANTED,
            "role_changed": InvalidationTrigger.ROLE_CHANGED,
            "group_changed": InvalidationTrigger.GROUP_MEMBERSHIP_CHANGED,
        }
        trigger = trigger_map.get(change_type, InvalidationTrigger.PERMISSION_REVOKED)

        command = self.rule_engine.get_command(
            trigger=trigger,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata={"change_type": change_type, **details},
        )

        # Permission changes are ALWAYS immediate, never queued
        await self._execute_invalidation(command)

    async def on_version_change(self, component: str, version: str, tenant_id: str = "*"):
        """Called when a system component version changes."""
        trigger = None
        if component == "model":
            trigger = self.version_tracker.update_model_version(version)
        elif component.startswith("prompt:"):
            template_id = component.split(":", 1)[1]
            trigger = self.version_tracker.update_prompt_version(template_id, version)
        elif component.startswith("index:"):
            index_id = component.split(":", 1)[1]
            trigger = self.version_tracker.update_index_version(index_id, version)
        elif component == "safety_policy":
            trigger = self.version_tracker.update_safety_policy(version)
        elif component == "embedding_model":
            trigger = self.version_tracker.update_embedding_model(version)

        if trigger:
            command = self.rule_engine.get_command(
                trigger=trigger,
                tenant_id=tenant_id,
                metadata={"component": component, "version": version},
            )
            await self._execute_invalidation(command)

    async def on_security_incident(self, tenant_id: str = "*", details: Optional[Dict] = None):
        """Nuclear option: clear everything."""
        command = self.rule_engine.get_command(
            trigger=InvalidationTrigger.SECURITY_INCIDENT,
            tenant_id=tenant_id,
            metadata=details or {"reason": "security_incident"},
        )
        await self._execute_invalidation(command)

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    async def _execute_invalidation(self, command: InvalidationCommand):
        """Execute an invalidation command."""
        start = time.time()
        self.metrics.total_events += 1
        self.metrics.events_by_trigger[command.trigger.value] += 1
        self.metrics.events_by_scope[command.scope.value] += 1

        if command.priority == 1:
            # Immediate execution
            await self._do_invalidate(command)
        else:
            # Queue for batch processing
            await self._queue.put(command)
            return

        # Cross-region propagation
        await self.propagator.propagate(command)

        # Audit log
        self._audit_log.append({
            "command_id": command.command_id,
            "trigger": command.trigger.value,
            "scope": command.scope.value,
            "tenant_id": command.tenant_id,
            "user_id": command.user_id,
            "layers": [l.value for l in command.target_layers],
            "timestamp": command.timestamp,
            "execution_ms": (time.time() - start) * 1000,
        })

        logger.info(
            f"Invalidation executed: cmd={command.command_id}, "
            f"trigger={command.trigger.value}, scope={command.scope.value}, "
            f"layers={len(command.target_layers)}, "
            f"latency_ms={(time.time() - start) * 1000:.1f}"
        )

    async def _do_invalidate(self, command: InvalidationCommand):
        """Perform the actual cache invalidation."""
        keys_invalidated = 0
        for layer in command.target_layers:
            handler = self._layer_handlers.get(layer)
            if handler:
                count = await handler(command)
                keys_invalidated += count or 0
        self.metrics.keys_invalidated += keys_invalidated

    async def _process_queue(self):
        """Background processor for non-immediate invalidations."""
        batch: List[InvalidationCommand] = []
        while True:
            try:
                # Collect batch
                try:
                    cmd = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                    batch.append(cmd)
                    # Drain queue up to batch size
                    while len(batch) < 50:
                        try:
                            cmd = self._queue.get_nowait()
                            batch.append(cmd)
                        except asyncio.QueueEmpty:
                            break
                except asyncio.TimeoutError:
                    pass

                if batch:
                    # Deduplicate and merge
                    merged = self._merge_commands(batch)
                    for cmd in merged:
                        await self._do_invalidate(cmd)
                        await self.propagator.propagate(cmd)
                    batch.clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
                batch.clear()

    def _merge_commands(self, commands: List[InvalidationCommand]) -> List[InvalidationCommand]:
        """Merge overlapping invalidation commands to reduce work."""
        # Group by (tenant_id, scope) and union layers
        groups: Dict[str, InvalidationCommand] = {}
        for cmd in commands:
            group_key = f"{cmd.tenant_id}:{cmd.scope.value}"
            if group_key in groups:
                existing = groups[group_key]
                # Merge layers
                existing_layers = set(existing.target_layers)
                existing_layers.update(cmd.target_layers)
                existing.target_layers = list(existing_layers)
                # Take highest priority
                existing.priority = min(existing.priority, cmd.priority)
            else:
                groups[group_key] = cmd
        return list(groups.values())

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------

    def get_metrics(self) -> Dict:
        return {
            **self.metrics.to_dict(),
            "propagation_avg_latency_ms": self.propagator.avg_latency_ms,
            "queue_size": self._queue.qsize(),
            "version_state": {
                "model": self.version_tracker.current.model_version,
                "safety_policy": self.version_tracker.current.safety_policy_version,
            },
        }

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        return self._audit_log[-limit:]


# =============================================================================
# Write-Through Invalidation Decorator
# =============================================================================

def write_through_invalidate(invalidation_service: CacheInvalidationService):
    """
    Decorator that automatically triggers cache invalidation
    when a write operation completes.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Extract invalidation context from result or kwargs
            tenant_id = kwargs.get("tenant_id") or getattr(result, "tenant_id", None)
            resource_id = kwargs.get("resource_id") or getattr(result, "resource_id", None)
            change_type = kwargs.get("change_type", "updated")

            if tenant_id and resource_id:
                await invalidation_service.on_document_change(
                    tenant_id=tenant_id,
                    document_id=resource_id,
                    change_type=change_type,
                )

            return result
        return wrapper
    return decorator


# =============================================================================
# Usage Example
# =============================================================================

async def main():
    """Demonstrate cache invalidation system."""

    service = CacheInvalidationService(
        current_region="us-east-1",
        all_regions=["us-east-1", "eu-west-1", "ap-southeast-1"],
    )

    # Register mock layer handlers
    async def mock_handler(command: InvalidationCommand) -> int:
        # Simulate invalidating N keys
        return random.randint(10, 100)

    for layer in CacheLayerType:
        service.register_layer_handler(layer, mock_handler)

    await service.start()

    # Simulate events
    print("--- Document Update ---")
    await service.on_document_change("acme_corp", "doc_123", "updated")

    print("\n--- Permission Revocation (IMMEDIATE) ---")
    await service.on_permission_change(
        "acme_corp", "user_456", "revoked",
        {"resource": "dataset_finance", "old_role": "editor"}
    )

    print("\n--- Model Version Change ---")
    await service.on_version_change("model", "gpt-4-0301")

    print("\n--- Safety Policy Update ---")
    await service.on_version_change("safety_policy", "v5.0")

    # Check bypass policy
    print("\n--- Bypass Policy Checks ---")
    bypass, reason = CacheBypassPolicy.should_bypass(
        "critical", {"requires_live_data": True}
    )
    print(f"Critical + live data: bypass={bypass}, reason={reason}")

    bypass, reason = CacheBypassPolicy.should_bypass(
        "low", {"requires_live_data": False}
    )
    print(f"Low risk, no live data: bypass={bypass}, reason={reason}")

    # Print metrics
    await asyncio.sleep(0.1)
    print(f"\nMetrics: {json.dumps(service.get_metrics(), indent=2)}")
    print(f"\nAudit log entries: {len(service.get_audit_log())}")

    await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
