"""
Action Audit System
====================
Comprehensive audit trail with user+agent attribution, real-time streaming,
anomaly detection, compliance reporting, and searchable audit logs.
"""

import uuid
import time
import json
import hashlib
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Set, Callable, Awaitable, AsyncIterator
from collections import defaultdict
import heapq


# =============================================================================
# ENUMS
# =============================================================================

class AuditOutcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class AuditSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"


class RetentionTier(Enum):
    HOT = "hot"          # Last 30 days, fast query
    WARM = "warm"        # 30-365 days, slower query
    COLD = "cold"        # 1-7 years, archive
    FROZEN = "frozen"    # 7+ years, compliance hold


# =============================================================================
# AUDIT EVENT SCHEMA
# =============================================================================

@dataclass
class AuditEvent:
    """
    Complete audit event capturing WHO did WHAT on WHICH resource,
    with full context for compliance and forensics.
    """
    # Identity
    event_id: str
    timestamp: datetime

    # WHO - dual attribution
    user_id: str                     # The human who delegated
    agent_id: str                    # The agent that executed
    delegation_id: str               # The delegation grant used
    session_id: str                  # User session correlation

    # WHAT
    tool_id: str                     # Which tool was used
    action: str                      # What action was performed
    parameters_hash: str             # Hash of parameters (not raw, for privacy)
    parameters_summary: str          # Human-readable summary

    # WHERE
    resource: str                    # Target resource identifier
    tenant_id: str                   # Tenant boundary
    environment: str                 # prod, staging, dev

    # CONTEXT
    correlation_id: str              # End-to-end trace
    risk_level: int                  # 1-10 risk score
    approval_id: Optional[str] = None
    elevation_id: Optional[str] = None
    parent_event_id: Optional[str] = None  # For chained actions

    # OUTCOME
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    outcome_detail: str = ""
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

    # CHANGES (what was modified)
    changes: Optional[Dict[str, Any]] = None
    # e.g., {"before": {...}, "after": {...}, "diff_summary": "..."}

    # METADATA
    agent_version: str = ""
    policy_version: str = ""
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    severity: AuditSeverity = AuditSeverity.INFO

    # Integrity
    _event_hash: str = ""

    def compute_hash(self) -> str:
        """Compute integrity hash for tamper detection."""
        data = f"{self.event_id}:{self.timestamp.isoformat()}:{self.user_id}:" \
               f"{self.agent_id}:{self.action}:{self.resource}:{self.outcome.value}"
        return hashlib.sha256(data.encode()).hexdigest()

    def __post_init__(self):
        if not self._event_hash:
            self._event_hash = self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "delegation_id": self.delegation_id,
            "session_id": self.session_id,
            "tool_id": self.tool_id,
            "action": self.action,
            "resource": self.resource,
            "tenant_id": self.tenant_id,
            "environment": self.environment,
            "correlation_id": self.correlation_id,
            "risk_level": self.risk_level,
            "outcome": self.outcome.value,
            "outcome_detail": self.outcome_detail,
            "duration_ms": self.duration_ms,
            "severity": self.severity.value,
            "approval_id": self.approval_id,
            "agent_version": self.agent_version,
            "event_hash": self._event_hash,
        }


# =============================================================================
# AUDIT EVENT BUILDER
# =============================================================================

class AuditEventBuilder:
    """Fluent builder for creating audit events with proper defaults."""

    def __init__(self):
        self._data: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "correlation_id": str(uuid.uuid4()),
            "environment": "production",
            "risk_level": 1,
            "outcome": AuditOutcome.SUCCESS,
        }

    def who(self, user_id: str, agent_id: str, delegation_id: str, session_id: str):
        self._data.update(user_id=user_id, agent_id=agent_id,
                          delegation_id=delegation_id, session_id=session_id)
        return self

    def what(self, tool_id: str, action: str, parameters: Optional[Dict] = None):
        self._data["tool_id"] = tool_id
        self._data["action"] = action
        if parameters:
            self._data["parameters_hash"] = hashlib.sha256(
                json.dumps(parameters, sort_keys=True).encode()
            ).hexdigest()[:16]
            self._data["parameters_summary"] = self._summarize_params(parameters)
        else:
            self._data["parameters_hash"] = ""
            self._data["parameters_summary"] = ""
        return self

    def where(self, resource: str, tenant_id: str, environment: str = "production"):
        self._data.update(resource=resource, tenant_id=tenant_id, environment=environment)
        return self

    def context(self, correlation_id: str, risk_level: int,
                approval_id: Optional[str] = None):
        self._data.update(correlation_id=correlation_id, risk_level=risk_level,
                          approval_id=approval_id)
        return self

    def result(self, outcome: AuditOutcome, detail: str = "",
               error: Optional[str] = None, duration_ms: Optional[int] = None,
               changes: Optional[Dict] = None):
        self._data.update(outcome=outcome, outcome_detail=detail,
                          error_message=error, duration_ms=duration_ms,
                          changes=changes)
        return self

    def metadata(self, agent_version: str = "", policy_version: str = "",
                 client_ip: Optional[str] = None):
        self._data.update(agent_version=agent_version, policy_version=policy_version,
                          client_ip=client_ip)
        return self

    def build(self) -> AuditEvent:
        # Determine severity based on outcome and risk
        severity = AuditSeverity.INFO
        if self._data.get("outcome") == AuditOutcome.DENIED:
            severity = AuditSeverity.WARNING
        if self._data.get("risk_level", 0) >= 8:
            severity = AuditSeverity.ALERT
        if self._data.get("outcome") == AuditOutcome.ERROR and self._data.get("risk_level", 0) >= 7:
            severity = AuditSeverity.CRITICAL
        self._data["severity"] = severity
        return AuditEvent(**self._data)

    def _summarize_params(self, params: Dict) -> str:
        """Create a human-readable summary without exposing sensitive data."""
        summary_parts = []
        for key, value in params.items():
            if key.lower() in ("password", "secret", "token", "key", "credential"):
                summary_parts.append(f"{key}=<redacted>")
            elif isinstance(value, str) and len(value) > 50:
                summary_parts.append(f"{key}={value[:20]}...({len(value)} chars)")
            else:
                summary_parts.append(f"{key}={value}")
        return "; ".join(summary_parts[:10])


# =============================================================================
# AUDIT STORE
# =============================================================================

class AuditStore:
    """
    Immutable audit event store with indexing for efficient queries.
    In production, backed by append-only storage (e.g., Azure Table Storage,
    AWS CloudTrail, Elasticsearch).
    """

    def __init__(self):
        self._events: List[AuditEvent] = []
        # Indexes for fast lookup
        self._by_user: Dict[str, List[int]] = defaultdict(list)
        self._by_agent: Dict[str, List[int]] = defaultdict(list)
        self._by_resource: Dict[str, List[int]] = defaultdict(list)
        self._by_session: Dict[str, List[int]] = defaultdict(list)
        self._by_correlation: Dict[str, List[int]] = defaultdict(list)
        self._by_tenant: Dict[str, List[int]] = defaultdict(list)
        self._by_outcome: Dict[str, List[int]] = defaultdict(list)

    async def append(self, event: AuditEvent) -> None:
        """Append an event (immutable - cannot be modified after)."""
        # Verify integrity
        expected_hash = event.compute_hash()
        if event._event_hash != expected_hash:
            raise ValueError("Event integrity check failed")

        idx = len(self._events)
        self._events.append(event)

        # Update indexes
        self._by_user[event.user_id].append(idx)
        self._by_agent[event.agent_id].append(idx)
        self._by_resource[event.resource].append(idx)
        self._by_session[event.session_id].append(idx)
        self._by_correlation[event.correlation_id].append(idx)
        self._by_tenant[event.tenant_id].append(idx)
        self._by_outcome[event.outcome.value].append(idx)

    async def query(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        resource: Optional[str] = None,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        outcome: Optional[AuditOutcome] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_risk_level: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query audit events with multiple filter criteria."""
        # Start with candidate sets from indexes
        candidate_sets: List[Set[int]] = []

        if user_id:
            candidate_sets.append(set(self._by_user.get(user_id, [])))
        if agent_id:
            candidate_sets.append(set(self._by_agent.get(agent_id, [])))
        if resource:
            candidate_sets.append(set(self._by_resource.get(resource, [])))
        if tenant_id:
            candidate_sets.append(set(self._by_tenant.get(tenant_id, [])))
        if session_id:
            candidate_sets.append(set(self._by_session.get(session_id, [])))
        if correlation_id:
            candidate_sets.append(set(self._by_correlation.get(correlation_id, [])))
        if outcome:
            candidate_sets.append(set(self._by_outcome.get(outcome.value, [])))

        # Intersect all candidate sets
        if candidate_sets:
            candidates = candidate_sets[0]
            for s in candidate_sets[1:]:
                candidates &= s
        else:
            candidates = set(range(len(self._events)))

        # Apply time and risk filters
        results = []
        for idx in sorted(candidates, reverse=True):  # Most recent first
            event = self._events[idx]
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if min_risk_level and event.risk_level < min_risk_level:
                continue
            results.append(event)

        return results[offset:offset + limit]

    async def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a single event by ID."""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    async def count(self, **kwargs) -> int:
        """Count events matching criteria."""
        events = await self.query(**kwargs, limit=999999)
        return len(events)

    @property
    def total_events(self) -> int:
        return len(self._events)


# =============================================================================
# REAL-TIME AUDIT STREAMING
# =============================================================================

class AuditStreamSubscriber:
    """A subscriber to the audit event stream."""

    def __init__(self, subscriber_id: str, filter_fn: Optional[Callable[[AuditEvent], bool]] = None):
        self.subscriber_id = subscriber_id
        self.filter_fn = filter_fn or (lambda _: True)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    async def receive(self) -> AuditEvent:
        return await self._queue.get()

    async def push(self, event: AuditEvent) -> None:
        if self.filter_fn(event):
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest if queue is full (back-pressure)
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass


class AuditEventStream:
    """Real-time audit event streaming with pub/sub."""

    def __init__(self):
        self._subscribers: Dict[str, AuditStreamSubscriber] = {}

    def subscribe(
        self,
        subscriber_id: str,
        filter_fn: Optional[Callable[[AuditEvent], bool]] = None,
    ) -> AuditStreamSubscriber:
        """Subscribe to audit events with optional filter."""
        subscriber = AuditStreamSubscriber(subscriber_id, filter_fn)
        self._subscribers[subscriber_id] = subscriber
        return subscriber

    def unsubscribe(self, subscriber_id: str) -> None:
        self._subscribers.pop(subscriber_id, None)

    async def publish(self, event: AuditEvent) -> None:
        """Publish an event to all subscribers."""
        tasks = [sub.push(event) for sub in self._subscribers.values()]
        await asyncio.gather(*tasks, return_exceptions=True)


# =============================================================================
# ANOMALY DETECTION
# =============================================================================

@dataclass
class AnomalyAlert:
    """An anomaly detected in the audit trail."""
    alert_id: str
    alert_type: str
    severity: AuditSeverity
    agent_id: str
    user_id: Optional[str]
    description: str
    evidence: List[str]        # Event IDs that triggered the anomaly
    detected_at: datetime
    acknowledged: bool = False


class AuditAnomalyDetector:
    """
    Detects anomalous patterns in audit events.
    Runs continuously, analyzing events as they arrive.
    """

    def __init__(self):
        self._alerts: List[AnomalyAlert] = []
        self._agent_baselines: Dict[str, Dict] = {}
        # Sliding windows for pattern detection
        self._recent_events: Dict[str, List[AuditEvent]] = defaultdict(list)
        self._window_size = 100

    async def analyze_event(self, event: AuditEvent) -> Optional[AnomalyAlert]:
        """Analyze a single event against known patterns."""
        # Store in sliding window
        key = event.agent_id
        window = self._recent_events[key]
        window.append(event)
        if len(window) > self._window_size:
            window.pop(0)

        # Run anomaly checks
        alerts = []
        alerts.append(self._check_denial_spike(event, window))
        alerts.append(self._check_unusual_resource_access(event, window))
        alerts.append(self._check_off_hours_activity(event, window))
        alerts.append(self._check_privilege_escalation_pattern(event, window))
        alerts.append(self._check_data_exfiltration_pattern(event, window))

        for alert in alerts:
            if alert:
                self._alerts.append(alert)
                return alert
        return None

    def _check_denial_spike(
        self, event: AuditEvent, window: List[AuditEvent]
    ) -> Optional[AnomalyAlert]:
        """Detect spike in permission denials (potential probing)."""
        if len(window) < 10:
            return None
        recent_10 = window[-10:]
        denials = sum(1 for e in recent_10 if e.outcome == AuditOutcome.DENIED)
        if denials >= 7:
            return AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                alert_type="denial_spike",
                severity=AuditSeverity.ALERT,
                agent_id=event.agent_id,
                user_id=event.user_id,
                description=f"Agent {event.agent_id} received {denials}/10 permission denials",
                evidence=[e.event_id for e in recent_10 if e.outcome == AuditOutcome.DENIED],
                detected_at=datetime.now(timezone.utc),
            )
        return None

    def _check_unusual_resource_access(
        self, event: AuditEvent, window: List[AuditEvent]
    ) -> Optional[AnomalyAlert]:
        """Detect access to unusual resources (outside normal pattern)."""
        if len(window) < 20:
            return None

        # Build baseline of resource prefixes
        baseline_resources = set()
        for e in window[:-5]:
            prefix = "/".join(e.resource.split("/")[:3])
            baseline_resources.add(prefix)

        # Check recent events
        current_prefix = "/".join(event.resource.split("/")[:3])
        if baseline_resources and current_prefix not in baseline_resources:
            recent_new = sum(
                1 for e in window[-5:]
                if "/".join(e.resource.split("/")[:3]) not in baseline_resources
            )
            if recent_new >= 3:
                return AnomalyAlert(
                    alert_id=str(uuid.uuid4()),
                    alert_type="unusual_resource_access",
                    severity=AuditSeverity.WARNING,
                    agent_id=event.agent_id,
                    user_id=event.user_id,
                    description=f"Agent accessing unusual resources outside baseline pattern",
                    evidence=[e.event_id for e in window[-5:]],
                    detected_at=datetime.now(timezone.utc),
                )
        return None

    def _check_off_hours_activity(
        self, event: AuditEvent, window: List[AuditEvent]
    ) -> Optional[AnomalyAlert]:
        """Detect activity during unusual hours."""
        hour = event.timestamp.hour
        if 2 <= hour <= 5:  # 2am-5am UTC
            if event.risk_level >= 5:
                return AnomalyAlert(
                    alert_id=str(uuid.uuid4()),
                    alert_type="off_hours_high_risk",
                    severity=AuditSeverity.ALERT,
                    agent_id=event.agent_id,
                    user_id=event.user_id,
                    description=f"High-risk action at unusual hour ({hour}:00 UTC)",
                    evidence=[event.event_id],
                    detected_at=datetime.now(timezone.utc),
                )
        return None

    def _check_privilege_escalation_pattern(
        self, event: AuditEvent, window: List[AuditEvent]
    ) -> Optional[AnomalyAlert]:
        """Detect escalating privilege pattern."""
        if len(window) < 5:
            return None
        recent = window[-5:]
        risk_levels = [e.risk_level for e in recent]
        # Strictly increasing risk
        if risk_levels == sorted(risk_levels) and risk_levels[-1] - risk_levels[0] >= 5:
            return AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                alert_type="privilege_escalation_pattern",
                severity=AuditSeverity.CRITICAL,
                agent_id=event.agent_id,
                user_id=event.user_id,
                description=f"Escalating risk pattern: {risk_levels[0]} -> {risk_levels[-1]}",
                evidence=[e.event_id for e in recent],
                detected_at=datetime.now(timezone.utc),
            )
        return None

    def _check_data_exfiltration_pattern(
        self, event: AuditEvent, window: List[AuditEvent]
    ) -> Optional[AnomalyAlert]:
        """Detect potential data exfiltration (many reads in short time)."""
        if len(window) < 20:
            return None
        recent_20 = window[-20:]
        time_span = (recent_20[-1].timestamp - recent_20[0].timestamp).total_seconds()
        if time_span <= 0:
            return None

        reads = [e for e in recent_20 if "read" in e.action.lower()]
        unique_resources = set(e.resource for e in reads)

        # Many unique resources read very quickly
        if len(reads) >= 15 and len(unique_resources) >= 10 and time_span < 30:
            return AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                alert_type="potential_data_exfiltration",
                severity=AuditSeverity.CRITICAL,
                agent_id=event.agent_id,
                user_id=event.user_id,
                description=f"Rapid reads of {len(unique_resources)} unique resources in {time_span:.0f}s",
                evidence=[e.event_id for e in reads[-10:]],
                detected_at=datetime.now(timezone.utc),
            )
        return None

    def get_alerts(
        self, severity: Optional[AuditSeverity] = None, unacknowledged_only: bool = False
    ) -> List[AnomalyAlert]:
        alerts = self._alerts
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return alerts

    def acknowledge_alert(self, alert_id: str) -> None:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                break


# =============================================================================
# COMPLIANCE REPORTING
# =============================================================================

@dataclass
class ComplianceReport:
    """Generated compliance report."""
    report_id: str
    report_type: str            # "SOC2", "GDPR", "HIPAA", "custom"
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    tenant_id: str
    summary: Dict[str, Any]
    findings: List[Dict[str, Any]]
    recommendations: List[str]


class ComplianceReporter:
    """Generates compliance reports from audit data."""

    def __init__(self, audit_store: AuditStore):
        self._store = audit_store

    async def generate_access_report(
        self, tenant_id: str, start: datetime, end: datetime
    ) -> ComplianceReport:
        """Generate access control compliance report."""
        events = await self._store.query(
            tenant_id=tenant_id, start_time=start, end_time=end, limit=999999
        )

        # Analyze
        total_actions = len(events)
        denied_actions = sum(1 for e in events if e.outcome == AuditOutcome.DENIED)
        unique_agents = len(set(e.agent_id for e in events))
        unique_users = len(set(e.user_id for e in events))
        high_risk_actions = sum(1 for e in events if e.risk_level >= 7)
        approved_actions = sum(1 for e in events if e.approval_id)

        findings = []
        # Finding: agents with high denial rates
        agent_denials: Dict[str, int] = defaultdict(int)
        agent_totals: Dict[str, int] = defaultdict(int)
        for e in events:
            agent_totals[e.agent_id] += 1
            if e.outcome == AuditOutcome.DENIED:
                agent_denials[e.agent_id] += 1

        for agent_id, denials in agent_denials.items():
            total = agent_totals[agent_id]
            rate = denials / total if total > 0 else 0
            if rate > 0.2:
                findings.append({
                    "type": "high_denial_rate",
                    "agent_id": agent_id,
                    "denial_rate": f"{rate:.0%}",
                    "total_actions": total,
                    "severity": "medium",
                })

        recommendations = []
        if denied_actions / max(total_actions, 1) > 0.1:
            recommendations.append(
                "High overall denial rate suggests permission misconfigurations"
            )
        if high_risk_actions > total_actions * 0.2:
            recommendations.append(
                "High proportion of high-risk actions - review agent boundaries"
            )

        return ComplianceReport(
            report_id=str(uuid.uuid4()),
            report_type="access_control",
            generated_at=datetime.now(timezone.utc),
            period_start=start,
            period_end=end,
            tenant_id=tenant_id,
            summary={
                "total_actions": total_actions,
                "denied_actions": denied_actions,
                "denial_rate": f"{denied_actions / max(total_actions, 1):.1%}",
                "unique_agents": unique_agents,
                "unique_users": unique_users,
                "high_risk_actions": high_risk_actions,
                "approved_actions": approved_actions,
            },
            findings=findings,
            recommendations=recommendations,
        )

    async def generate_agent_activity_report(
        self, agent_id: str, start: datetime, end: datetime
    ) -> ComplianceReport:
        """Generate activity report for a specific agent."""
        events = await self._store.query(
            agent_id=agent_id, start_time=start, end_time=end, limit=999999
        )

        # Activity breakdown
        action_counts: Dict[str, int] = defaultdict(int)
        resource_counts: Dict[str, int] = defaultdict(int)
        hourly_distribution: Dict[int, int] = defaultdict(int)

        for e in events:
            action_counts[e.action] += 1
            resource_counts[e.resource.split("/")[0] if "/" in e.resource else e.resource] += 1
            hourly_distribution[e.timestamp.hour] += 1

        return ComplianceReport(
            report_id=str(uuid.uuid4()),
            report_type="agent_activity",
            generated_at=datetime.now(timezone.utc),
            period_start=start,
            period_end=end,
            tenant_id=events[0].tenant_id if events else "",
            summary={
                "total_actions": len(events),
                "unique_actions": len(action_counts),
                "unique_resources": len(resource_counts),
                "top_actions": dict(sorted(action_counts.items(), key=lambda x: -x[1])[:10]),
                "hourly_distribution": dict(hourly_distribution),
                "users_served": len(set(e.user_id for e in events)),
            },
            findings=[],
            recommendations=[],
        )


# =============================================================================
# RETENTION MANAGER
# =============================================================================

class AuditRetentionManager:
    """Manages audit log retention policies."""

    def __init__(self):
        self._policies: Dict[str, Dict[str, Any]] = {
            "default": {"hot_days": 30, "warm_days": 365, "cold_years": 7},
            "financial": {"hot_days": 90, "warm_days": 365, "cold_years": 10},
            "healthcare": {"hot_days": 30, "warm_days": 365, "cold_years": 7},
            "security": {"hot_days": 90, "warm_days": 730, "cold_years": 10},
        }
        self._holds: Dict[str, Dict] = {}  # Legal/compliance holds

    def get_retention_tier(self, event: AuditEvent, policy_name: str = "default") -> RetentionTier:
        """Determine which retention tier an event belongs to."""
        # Check holds first
        for hold_id, hold in self._holds.items():
            if self._event_matches_hold(event, hold):
                return RetentionTier.FROZEN

        policy = self._policies.get(policy_name, self._policies["default"])
        age = datetime.now(timezone.utc) - event.timestamp

        if age.days <= policy["hot_days"]:
            return RetentionTier.HOT
        elif age.days <= policy["warm_days"]:
            return RetentionTier.WARM
        elif age.days <= policy["cold_years"] * 365:
            return RetentionTier.COLD
        else:
            return RetentionTier.FROZEN  # Beyond retention = delete candidate

    def create_hold(self, hold_id: str, criteria: Dict[str, Any], reason: str) -> None:
        """Create a legal/compliance hold preventing deletion."""
        self._holds[hold_id] = {
            "criteria": criteria,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def release_hold(self, hold_id: str) -> None:
        self._holds.pop(hold_id, None)

    def _event_matches_hold(self, event: AuditEvent, hold: Dict) -> bool:
        criteria = hold["criteria"]
        if "user_id" in criteria and event.user_id != criteria["user_id"]:
            return False
        if "agent_id" in criteria and event.agent_id != criteria["agent_id"]:
            return False
        if "tenant_id" in criteria and event.tenant_id != criteria["tenant_id"]:
            return False
        return True


# =============================================================================
# AUDIT SERVICE (Main Facade)
# =============================================================================

class AuditService:
    """
    Main audit service that coordinates storage, streaming, anomaly detection,
    and compliance reporting.
    """

    def __init__(self):
        self._store = AuditStore()
        self._stream = AuditEventStream()
        self._anomaly_detector = AuditAnomalyDetector()
        self._compliance_reporter = ComplianceReporter(self._store)
        self._retention_manager = AuditRetentionManager()

    async def record_action(
        self,
        user_id: str,
        agent_id: str,
        delegation_id: str,
        session_id: str,
        tool_id: str,
        action: str,
        resource: str,
        tenant_id: str,
        outcome: AuditOutcome,
        risk_level: int = 1,
        parameters: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        changes: Optional[Dict] = None,
        approval_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        environment: str = "production",
        error_message: Optional[str] = None,
    ) -> AuditEvent:
        """Record an action in the audit trail."""
        event = (
            AuditEventBuilder()
            .who(user_id, agent_id, delegation_id, session_id)
            .what(tool_id, action, parameters)
            .where(resource, tenant_id, environment)
            .context(correlation_id or str(uuid.uuid4()), risk_level, approval_id)
            .result(outcome, duration_ms=duration_ms, changes=changes, error=error_message)
            .build()
        )

        # Store (immutable)
        await self._store.append(event)

        # Stream to subscribers
        await self._stream.publish(event)

        # Anomaly detection
        alert = await self._anomaly_detector.analyze_event(event)
        if alert:
            # In production, this would trigger alerts/notifications
            pass

        return event

    # Querying
    async def search(self, **kwargs) -> List[AuditEvent]:
        return await self._store.query(**kwargs)

    async def get_user_actions(
        self, user_id: str, start: Optional[datetime] = None, limit: int = 100
    ) -> List[AuditEvent]:
        return await self._store.query(user_id=user_id, start_time=start, limit=limit)

    async def get_agent_actions(
        self, agent_id: str, start: Optional[datetime] = None, limit: int = 100
    ) -> List[AuditEvent]:
        return await self._store.query(agent_id=agent_id, start_time=start, limit=limit)

    async def get_session_trail(self, session_id: str) -> List[AuditEvent]:
        return await self._store.query(session_id=session_id, limit=10000)

    async def get_correlation_trail(self, correlation_id: str) -> List[AuditEvent]:
        return await self._store.query(correlation_id=correlation_id, limit=10000)

    # Streaming
    def subscribe(self, subscriber_id: str, filter_fn=None) -> AuditStreamSubscriber:
        return self._stream.subscribe(subscriber_id, filter_fn)

    # Compliance
    async def generate_compliance_report(
        self, tenant_id: str, days: int = 30
    ) -> ComplianceReport:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return await self._compliance_reporter.generate_access_report(tenant_id, start, end)

    # Anomalies
    def get_anomaly_alerts(self, **kwargs) -> List[AnomalyAlert]:
        return self._anomaly_detector.get_alerts(**kwargs)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def example_usage():
    """Demonstrates the audit system."""
    service = AuditService()

    # Subscribe to high-risk events
    subscriber = service.subscribe(
        "security-monitor",
        filter_fn=lambda e: e.risk_level >= 7,
    )

    # Record some actions
    await service.record_action(
        user_id="user-456",
        agent_id="agent-code-review",
        delegation_id="del-789",
        session_id="session-001",
        tool_id="file-reader",
        action="repo:read",
        resource="org/myteam/api-service/src/main.py",
        tenant_id="tenant-abc",
        outcome=AuditOutcome.SUCCESS,
        risk_level=1,
        parameters={"path": "src/main.py"},
        duration_ms=45,
    )

    await service.record_action(
        user_id="user-456",
        agent_id="agent-code-review",
        delegation_id="del-789",
        session_id="session-001",
        tool_id="database-write",
        action="database:write",
        resource="db/production/users",
        tenant_id="tenant-abc",
        outcome=AuditOutcome.DENIED,
        risk_level=8,
        parameters={"query": "DELETE FROM users WHERE status='inactive'"},
    )

    await service.record_action(
        user_id="user-456",
        agent_id="agent-code-review",
        delegation_id="del-789",
        session_id="session-001",
        tool_id="deploy-production",
        action="deploy:production",
        resource="deploy/production/api-service",
        tenant_id="tenant-abc",
        outcome=AuditOutcome.APPROVAL_REQUIRED,
        risk_level=9,
        approval_id="approval-xyz",
    )

    # Query audit trail
    session_trail = await service.get_session_trail("session-001")
    print(f"Session trail: {len(session_trail)} events")
    for event in session_trail:
        print(f"  [{event.outcome.value}] {event.action} on {event.resource} (risk: {event.risk_level})")

    # Generate compliance report
    report = await service.generate_compliance_report("tenant-abc")
    print(f"\nCompliance Report: {report.summary}")

    # Check anomaly alerts
    alerts = service.get_anomaly_alerts()
    print(f"\nAnomaly alerts: {len(alerts)}")
    for alert in alerts:
        print(f"  [{alert.severity.value}] {alert.alert_type}: {alert.description}")


if __name__ == "__main__":
    asyncio.run(example_usage())
