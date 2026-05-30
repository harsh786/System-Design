"""
AI SRE - Incident Management System
=====================================
Complete incident lifecycle management for AI systems: detection, classification,
response, escalation, communication, root cause analysis, and postmortem generation.
"""

import uuid
import json
import logging
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# INCIDENT CLASSIFICATION
# =============================================================================

class IncidentSeverity(Enum):
    P0 = "p0"  # Critical: data loss, security breach, complete outage
    P1 = "p1"  # High: major feature broken, significant user impact
    P2 = "p2"  # Medium: degraded quality, partial impact
    P3 = "p3"  # Low: minor issues, limited impact


class IncidentType(Enum):
    MODEL_PROVIDER_OUTAGE = "model_provider_outage"
    VECTOR_DB_OUTAGE = "vector_db_outage"
    BAD_PROMPT_DEPLOYMENT = "bad_prompt_deployment"
    RETRIEVAL_INDEX_CORRUPTION = "retrieval_index_corruption"
    EMBEDDING_VERSION_MISMATCH = "embedding_version_mismatch"
    TOOL_API_PERMISSION_BUG = "tool_api_permission_bug"
    COST_SPIKE = "cost_spike"
    LATENCY_SPIKE = "latency_spike"
    PROMPT_INJECTION = "prompt_injection"
    DATA_LEAKAGE = "data_leakage"
    RUNAWAY_AGENT_LOOP = "runaway_agent_loop"
    UNKNOWN = "unknown"


class IncidentStatus(Enum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"  # Root cause identified
    MITIGATING = "mitigating"
    MONITORING = "monitoring"  # Fix applied, watching metrics
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"
    CLOSED = "closed"


@dataclass
class TimelineEntry:
    timestamp: datetime
    action: str
    actor: str  # Person or system
    details: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Incident:
    """Complete incident record."""
    id: str
    title: str
    severity: IncidentSeverity
    type: IncidentType
    status: IncidentStatus
    
    # Detection
    detected_at: datetime
    detected_by: str  # "alert", "user_report", "monitoring", "manual"
    detection_source: str  # Specific alert/report
    
    # Impact
    impact_description: str = ""
    affected_users: int = 0
    affected_requests: int = 0
    slos_breached: list = field(default_factory=list)
    error_budget_consumed_pct: float = 0.0
    
    # Assignment
    incident_commander: str = ""
    responders: list = field(default_factory=list)
    
    # Timeline
    timeline: list[TimelineEntry] = field(default_factory=list)
    
    # Resolution
    root_cause: str = ""
    mitigation_applied: str = ""
    resolved_at: Optional[datetime] = None
    total_duration_minutes: Optional[float] = None
    time_to_detect_minutes: Optional[float] = None
    time_to_mitigate_minutes: Optional[float] = None
    
    # Postmortem
    postmortem_url: str = ""
    action_items: list = field(default_factory=list)
    lessons_learned: list = field(default_factory=list)
    
    # Communication
    status_page_updated: bool = False
    stakeholders_notified: list = field(default_factory=list)
    
    def add_timeline(self, action: str, actor: str, details: str, **metadata):
        self.timeline.append(TimelineEntry(
            timestamp=datetime.utcnow(), action=action,
            actor=actor, details=details, metadata=metadata,
        ))


# =============================================================================
# INCIDENT DETECTION
# =============================================================================

@dataclass
class AlertSignal:
    """A signal that may indicate an incident."""
    source: str  # "metrics", "user_report", "health_check", "security_scanner"
    signal_type: str
    severity_hint: str
    message: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)


class IncidentDetector:
    """Detects incidents from various signal sources."""
    
    def __init__(self):
        self._rules: list[dict] = []
        self._recent_signals: list[AlertSignal] = []
        self._signal_window = timedelta(minutes=15)
        self._correlation_rules = self._build_correlation_rules()
    
    def _build_correlation_rules(self) -> list[dict]:
        """Rules to correlate multiple signals into a single incident."""
        return [
            {
                "name": "model_provider_outage",
                "signals": ["model_5xx_rate_high", "model_timeout_rate_high"],
                "min_signals": 1,
                "incident_type": IncidentType.MODEL_PROVIDER_OUTAGE,
                "severity": IncidentSeverity.P1,
            },
            {
                "name": "vector_db_outage",
                "signals": ["vector_db_errors", "retrieval_empty_rate_high", "vector_db_health_fail"],
                "min_signals": 1,
                "incident_type": IncidentType.VECTOR_DB_OUTAGE,
                "severity": IncidentSeverity.P1,
            },
            {
                "name": "bad_prompt_deployment",
                "signals": ["quality_drop", "user_complaints_spike", "recent_prompt_deployment"],
                "min_signals": 2,
                "incident_type": IncidentType.BAD_PROMPT_DEPLOYMENT,
                "severity": IncidentSeverity.P2,
            },
            {
                "name": "cost_spike",
                "signals": ["cost_anomaly", "token_usage_spike", "agent_step_count_high"],
                "min_signals": 1,
                "incident_type": IncidentType.COST_SPIKE,
                "severity": IncidentSeverity.P2,
            },
            {
                "name": "prompt_injection",
                "signals": ["safety_violation_critical", "output_anomaly", "instruction_bypass_detected"],
                "min_signals": 1,
                "incident_type": IncidentType.PROMPT_INJECTION,
                "severity": IncidentSeverity.P0,
            },
            {
                "name": "data_leakage",
                "signals": ["pii_in_output", "cross_tenant_data", "internal_data_exposed"],
                "min_signals": 1,
                "incident_type": IncidentType.DATA_LEAKAGE,
                "severity": IncidentSeverity.P0,
            },
            {
                "name": "runaway_agent_loop",
                "signals": ["agent_step_count_extreme", "single_request_cost_spike", "tool_call_loop_detected"],
                "min_signals": 1,
                "incident_type": IncidentType.RUNAWAY_AGENT_LOOP,
                "severity": IncidentSeverity.P2,
            },
            {
                "name": "latency_spike",
                "signals": ["latency_p95_breach", "timeout_rate_high", "queue_depth_high"],
                "min_signals": 1,
                "incident_type": IncidentType.LATENCY_SPIKE,
                "severity": IncidentSeverity.P2,
            },
            {
                "name": "embedding_mismatch",
                "signals": ["retrieval_recall_drop_sudden", "similarity_scores_uniformly_low"],
                "min_signals": 2,
                "incident_type": IncidentType.EMBEDDING_VERSION_MISMATCH,
                "severity": IncidentSeverity.P2,
            },
            {
                "name": "tool_permission_bug",
                "signals": ["tool_401_403_spike", "specific_tool_always_fails"],
                "min_signals": 1,
                "incident_type": IncidentType.TOOL_API_PERMISSION_BUG,
                "severity": IncidentSeverity.P2,
            },
        ]
    
    def ingest_signal(self, signal: AlertSignal) -> Optional[Incident]:
        """Ingest a signal and determine if it triggers an incident."""
        self._recent_signals.append(signal)
        
        # Clean old signals
        cutoff = datetime.utcnow() - self._signal_window
        self._recent_signals = [s for s in self._recent_signals if s.timestamp > cutoff]
        
        # Check correlation rules
        for rule in self._correlation_rules:
            matching_signals = [
                s for s in self._recent_signals 
                if s.signal_type in rule["signals"]
            ]
            
            if len(matching_signals) >= rule["min_signals"]:
                # Create incident
                incident = self._create_incident(rule, matching_signals)
                # Clear matched signals to avoid re-triggering
                for s in matching_signals:
                    if s in self._recent_signals:
                        self._recent_signals.remove(s)
                return incident
        
        return None
    
    def _create_incident(self, rule: dict, signals: list[AlertSignal]) -> Incident:
        """Create an incident from correlated signals."""
        now = datetime.utcnow()
        incident = Incident(
            id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            title=f"[{rule['severity'].value.upper()}] {rule['name'].replace('_', ' ').title()}",
            severity=rule["severity"],
            type=rule["incident_type"],
            status=IncidentStatus.DETECTED,
            detected_at=now,
            detected_by="alert_correlation",
            detection_source=", ".join(s.signal_type for s in signals),
        )
        
        incident.add_timeline(
            action="incident_created",
            actor="incident_detector",
            details=f"Incident created from {len(signals)} correlated signals: "
                    f"{', '.join(s.signal_type for s in signals)}",
        )
        
        return incident


# =============================================================================
# SEVERITY CLASSIFIER
# =============================================================================

class SeverityClassifier:
    """Classifies and potentially upgrades/downgrades incident severity."""
    
    def __init__(self):
        self._severity_rules = {
            # Auto-upgrade conditions
            "upgrade_to_p0": [
                lambda i: i.type == IncidentType.DATA_LEAKAGE,
                lambda i: i.type == IncidentType.PROMPT_INJECTION,
                lambda i: i.affected_users > 10000,
                lambda i: "safety" in [s.lower() for s in i.slos_breached],
            ],
            "upgrade_to_p1": [
                lambda i: i.affected_users > 1000,
                lambda i: i.error_budget_consumed_pct > 50,
                lambda i: i.type == IncidentType.MODEL_PROVIDER_OUTAGE,
            ],
        }
    
    def classify(self, incident: Incident, context: dict = None) -> IncidentSeverity:
        """Classify or reclassify incident severity based on current information."""
        current = incident.severity
        
        # Check upgrade conditions
        for rule in self._severity_rules.get("upgrade_to_p0", []):
            try:
                if rule(incident):
                    if current.value > IncidentSeverity.P0.value:
                        incident.add_timeline(
                            action="severity_upgraded",
                            actor="severity_classifier",
                            details=f"Upgraded from {current.value} to P0",
                        )
                        return IncidentSeverity.P0
            except Exception:
                pass
        
        for rule in self._severity_rules.get("upgrade_to_p1", []):
            try:
                if rule(incident):
                    if current == IncidentSeverity.P2 or current == IncidentSeverity.P3:
                        incident.add_timeline(
                            action="severity_upgraded",
                            actor="severity_classifier",
                            details=f"Upgraded from {current.value} to P1",
                        )
                        return IncidentSeverity.P1
            except Exception:
                pass
        
        return current


# =============================================================================
# AUTOMATED INITIAL RESPONSE
# =============================================================================

class AutomatedResponder:
    """Executes immediate automated responses based on incident type."""
    
    def __init__(self):
        self._response_playbooks: dict[IncidentType, list[Callable]] = {
            IncidentType.MODEL_PROVIDER_OUTAGE: [
                self._check_provider_status,
                self._activate_fallback,
                self._notify_on_call,
            ],
            IncidentType.COST_SPIKE: [
                self._identify_cost_source,
                self._apply_cost_caps,
                self._notify_on_call,
            ],
            IncidentType.PROMPT_INJECTION: [
                self._enable_enhanced_filtering,
                self._block_suspicious_users,
                self._notify_security,
                self._notify_on_call,
            ],
            IncidentType.DATA_LEAKAGE: [
                self._halt_affected_responses,
                self._notify_security,
                self._notify_legal,
                self._notify_on_call,
            ],
            IncidentType.RUNAWAY_AGENT_LOOP: [
                self._lower_max_steps,
                self._kill_active_loops,
                self._notify_on_call,
            ],
            IncidentType.BAD_PROMPT_DEPLOYMENT: [
                self._identify_recent_deployments,
                self._prepare_rollback,
                self._notify_on_call,
            ],
        }
    
    def respond(self, incident: Incident) -> list[dict]:
        """Execute automated initial response for an incident."""
        playbook = self._response_playbooks.get(incident.type, [self._notify_on_call])
        results = []
        
        for action in playbook:
            try:
                result = action(incident)
                results.append({"action": action.__name__, "success": True, "result": result})
                incident.add_timeline(
                    action=f"auto_response:{action.__name__}",
                    actor="automated_responder",
                    details=result,
                )
            except Exception as e:
                results.append({"action": action.__name__, "success": False, "error": str(e)})
                logger.error(f"Auto-response failed: {action.__name__}: {e}")
        
        incident.status = IncidentStatus.ACKNOWLEDGED
        return results
    
    def _check_provider_status(self, incident: Incident) -> str:
        return "Checked provider status page: incident confirmed on their end"
    
    def _activate_fallback(self, incident: Incident) -> str:
        return "Fallback model activated"
    
    def _notify_on_call(self, incident: Incident) -> str:
        return f"On-call paged: {incident.severity.value} - {incident.title}"
    
    def _identify_cost_source(self, incident: Incident) -> str:
        return "Cost source identified: tenant-xyz with runaway agent loops"
    
    def _apply_cost_caps(self, incident: Incident) -> str:
        return "Per-request cost cap of $1.00 applied"
    
    def _enable_enhanced_filtering(self, incident: Incident) -> str:
        return "Enhanced input/output safety filtering enabled"
    
    def _block_suspicious_users(self, incident: Incident) -> str:
        return "Suspicious users rate-limited pending review"
    
    def _notify_security(self, incident: Incident) -> str:
        return "Security team notified via security-incidents channel"
    
    def _notify_legal(self, incident: Incident) -> str:
        return "Legal team notified per data breach protocol"
    
    def _halt_affected_responses(self, incident: Incident) -> str:
        return "Affected response pipeline halted pending investigation"
    
    def _lower_max_steps(self, incident: Incident) -> str:
        return "Max agent steps lowered from 20 to 3"
    
    def _kill_active_loops(self, incident: Incident) -> str:
        return "Killed 5 active runaway agent executions"
    
    def _identify_recent_deployments(self, incident: Incident) -> str:
        return "Recent deployments: prompt v2.3 deployed 45 min ago"
    
    def _prepare_rollback(self, incident: Incident) -> str:
        return "Rollback prepared: ready to revert to prompt v2.2"


# =============================================================================
# ESCALATION ENGINE
# =============================================================================

@dataclass
class EscalationPolicy:
    """Defines when and how to escalate."""
    name: str
    conditions: list[Callable[[Incident], bool]]
    target: str  # Team or person to escalate to
    channel: str  # "page", "slack", "email", "phone"
    message_template: str
    cooldown_minutes: int = 30


class EscalationEngine:
    """Manages incident escalation based on policies and time."""
    
    def __init__(self):
        self._policies: list[EscalationPolicy] = self._default_policies()
        self._escalation_history: dict[str, list[datetime]] = defaultdict(list)
    
    def _default_policies(self) -> list[EscalationPolicy]:
        return [
            EscalationPolicy(
                name="p0_immediate_escalation",
                conditions=[lambda i: i.severity == IncidentSeverity.P0],
                target="engineering_leadership",
                channel="phone",
                message_template="P0 INCIDENT: {title} - Immediate attention required",
                cooldown_minutes=15,
            ),
            EscalationPolicy(
                name="p1_15min_no_ack",
                conditions=[
                    lambda i: i.severity == IncidentSeverity.P1,
                    lambda i: i.status == IncidentStatus.DETECTED,
                    lambda i: (datetime.utcnow() - i.detected_at).total_seconds() > 900,
                ],
                target="secondary_on_call",
                channel="page",
                message_template="P1 unacknowledged for 15min: {title}",
                cooldown_minutes=15,
            ),
            EscalationPolicy(
                name="p1_60min_no_mitigation",
                conditions=[
                    lambda i: i.severity == IncidentSeverity.P1,
                    lambda i: i.status in (IncidentStatus.INVESTIGATING, IncidentStatus.ACKNOWLEDGED),
                    lambda i: (datetime.utcnow() - i.detected_at).total_seconds() > 3600,
                ],
                target="engineering_manager",
                channel="page",
                message_template="P1 unresolved for 60min: {title} - Manager escalation",
                cooldown_minutes=30,
            ),
            EscalationPolicy(
                name="safety_incident_security",
                conditions=[
                    lambda i: i.type in (IncidentType.PROMPT_INJECTION, IncidentType.DATA_LEAKAGE),
                ],
                target="security_team",
                channel="page",
                message_template="SECURITY: {title} - Security team response required",
                cooldown_minutes=5,
            ),
        ]
    
    def evaluate_escalations(self, incident: Incident) -> list[dict]:
        """Evaluate all escalation policies for an incident."""
        escalations = []
        now = datetime.utcnow()
        
        for policy in self._policies:
            # Check cooldown
            key = f"{incident.id}:{policy.name}"
            last_escalations = self._escalation_history.get(key, [])
            if last_escalations:
                last = last_escalations[-1]
                if (now - last).total_seconds() < policy.cooldown_minutes * 60:
                    continue
            
            # Check all conditions
            all_met = all(cond(incident) for cond in policy.conditions)
            if all_met:
                escalation = {
                    "policy": policy.name,
                    "target": policy.target,
                    "channel": policy.channel,
                    "message": policy.message_template.format(title=incident.title),
                    "timestamp": now.isoformat(),
                }
                escalations.append(escalation)
                self._escalation_history[key].append(now)
                
                incident.add_timeline(
                    action="escalation",
                    actor="escalation_engine",
                    details=f"Escalated to {policy.target} via {policy.channel}: {policy.name}",
                )
        
        return escalations


# =============================================================================
# COMMUNICATION MANAGEMENT
# =============================================================================

class CommunicationManager:
    """Manages stakeholder communication during incidents."""
    
    def __init__(self):
        self._templates: dict[str, str] = {
            "initial_notification": (
                "🚨 **Incident Declared**: {title}\n"
                "**Severity**: {severity}\n"
                "**Type**: {type}\n"
                "**Impact**: {impact}\n"
                "**Status**: Investigating\n"
                "**Commander**: {commander}\n"
                "Next update in 15 minutes."
            ),
            "status_update": (
                "📋 **Incident Update**: {title}\n"
                "**Status**: {status}\n"
                "**Duration**: {duration}\n"
                "**Update**: {update}\n"
                "Next update in {next_update_minutes} minutes."
            ),
            "resolution": (
                "✅ **Incident Resolved**: {title}\n"
                "**Duration**: {duration}\n"
                "**Root Cause**: {root_cause}\n"
                "**Mitigation**: {mitigation}\n"
                "Postmortem will follow within 48 hours."
            ),
        }
        self._communication_log: list[dict] = []
    
    def send_initial_notification(self, incident: Incident) -> dict:
        """Send initial incident notification to stakeholders."""
        message = self._templates["initial_notification"].format(
            title=incident.title,
            severity=incident.severity.value.upper(),
            type=incident.type.value,
            impact=incident.impact_description or "Assessing impact",
            commander=incident.incident_commander or "Unassigned",
        )
        
        # Determine audience based on severity
        channels = self._get_channels(incident.severity)
        
        comm = {
            "type": "initial_notification",
            "incident_id": incident.id,
            "message": message,
            "channels": channels,
            "sent_at": datetime.utcnow().isoformat(),
        }
        self._communication_log.append(comm)
        
        incident.add_timeline(
            action="communication_sent",
            actor="communication_manager",
            details=f"Initial notification sent to: {', '.join(channels)}",
        )
        
        return comm
    
    def send_status_update(self, incident: Incident, update: str, 
                           next_update_minutes: int = 15) -> dict:
        """Send status update during incident."""
        duration = datetime.utcnow() - incident.detected_at
        duration_str = f"{int(duration.total_seconds() / 60)} minutes"
        
        message = self._templates["status_update"].format(
            title=incident.title,
            status=incident.status.value,
            duration=duration_str,
            update=update,
            next_update_minutes=next_update_minutes,
        )
        
        comm = {
            "type": "status_update",
            "incident_id": incident.id,
            "message": message,
            "sent_at": datetime.utcnow().isoformat(),
        }
        self._communication_log.append(comm)
        return comm
    
    def send_resolution(self, incident: Incident) -> dict:
        """Send resolution notification."""
        duration = (incident.resolved_at or datetime.utcnow()) - incident.detected_at
        duration_str = f"{int(duration.total_seconds() / 60)} minutes"
        
        message = self._templates["resolution"].format(
            title=incident.title,
            duration=duration_str,
            root_cause=incident.root_cause or "Under investigation",
            mitigation=incident.mitigation_applied or "Issue resolved",
        )
        
        comm = {
            "type": "resolution",
            "incident_id": incident.id,
            "message": message,
            "sent_at": datetime.utcnow().isoformat(),
        }
        self._communication_log.append(comm)
        return comm
    
    def _get_channels(self, severity: IncidentSeverity) -> list[str]:
        if severity == IncidentSeverity.P0:
            return ["#incidents", "#engineering-all", "#leadership", "status-page"]
        elif severity == IncidentSeverity.P1:
            return ["#incidents", "#engineering-on-call", "status-page"]
        elif severity == IncidentSeverity.P2:
            return ["#incidents", "#engineering-on-call"]
        return ["#incidents"]


# =============================================================================
# ROOT CAUSE ANALYSIS SUPPORT
# =============================================================================

class RootCauseAnalyzer:
    """Assists with root cause analysis for AI incidents."""
    
    def __init__(self):
        self._analysis_templates: dict[IncidentType, dict] = {
            IncidentType.MODEL_PROVIDER_OUTAGE: {
                "investigation_steps": [
                    "Check provider status page",
                    "Verify from multiple regions",
                    "Check rate limit headers",
                    "Review recent usage patterns",
                    "Check for billing issues",
                ],
                "common_root_causes": [
                    "Provider infrastructure issue",
                    "Rate limit exhaustion",
                    "Region-specific outage",
                    "API deprecation",
                    "Account suspension",
                ],
                "data_to_collect": [
                    "Error responses (full body)",
                    "Latency trend before outage",
                    "Rate limit header values",
                    "Traffic volume at time of incident",
                ],
            },
            IncidentType.BAD_PROMPT_DEPLOYMENT: {
                "investigation_steps": [
                    "Identify exact prompt version deployed",
                    "Diff with previous version",
                    "Run A/B comparison on golden test set",
                    "Check for unintended template variable changes",
                    "Review prompt testing results before deployment",
                ],
                "common_root_causes": [
                    "Instruction ambiguity causing behavior change",
                    "Removed guardrails accidentally",
                    "Template variable format changed",
                    "Context window overflow from longer prompt",
                    "Incompatible with current model version",
                ],
                "data_to_collect": [
                    "Prompt diff (old vs new)",
                    "Quality metrics before/after",
                    "Sample bad responses",
                    "Deployment timestamp",
                    "Test results before deployment",
                ],
            },
            IncidentType.COST_SPIKE: {
                "investigation_steps": [
                    "Identify cost source (per-tenant, per-feature)",
                    "Check for runaway agent loops",
                    "Review token usage patterns",
                    "Check for model routing errors (expensive model used incorrectly)",
                    "Look for retry storms",
                ],
                "common_root_causes": [
                    "Runaway agent loop (no termination condition)",
                    "Prompt injection causing max-length outputs",
                    "Model routing error (GPT-4 instead of GPT-3.5)",
                    "Retry storm from transient errors",
                    "Context window stuffing (too many retrieved docs)",
                    "Traffic spike from partner integration",
                ],
                "data_to_collect": [
                    "Per-request cost distribution",
                    "Token usage breakdown (input vs output)",
                    "Agent step counts",
                    "Top cost contributors (tenants/users)",
                    "Correlation with recent deployments",
                ],
            },
            IncidentType.PROMPT_INJECTION: {
                "investigation_steps": [
                    "Identify the injected payload",
                    "Determine scope of bypass",
                    "Check if data was exfiltrated",
                    "Review all responses to attacking user",
                    "Check for lateral movement (actions taken)",
                ],
                "common_root_causes": [
                    "Insufficient input sanitization",
                    "Weak system prompt boundaries",
                    "Tool action without proper authorization check",
                    "Context window manipulation",
                    "Multi-turn attack bypassing single-turn defenses",
                ],
                "data_to_collect": [
                    "Full conversation history with attacker",
                    "All actions taken by AI during attack",
                    "Any data returned to attacker",
                    "Similar patterns from other users",
                    "Safety filter bypass method",
                ],
            },
            IncidentType.DATA_LEAKAGE: {
                "investigation_steps": [
                    "Identify what data was exposed",
                    "Determine how many users affected",
                    "Trace the data source",
                    "Check tenant isolation",
                    "Review PII filtering effectiveness",
                ],
                "common_root_causes": [
                    "Tenant isolation failure in retrieval",
                    "PII not redacted from training/context data",
                    "Cross-tenant document retrieval bug",
                    "System prompt leakage",
                    "Memory/context bleed between sessions",
                ],
                "data_to_collect": [
                    "Exact data exposed (redacted for logs)",
                    "Source of exposed data",
                    "Requesting user details",
                    "Data owner details",
                    "Exposure window (first and last occurrence)",
                ],
            },
        }
    
    def get_investigation_guide(self, incident_type: IncidentType) -> dict:
        """Get investigation guide for an incident type."""
        template = self._analysis_templates.get(incident_type, {
            "investigation_steps": ["Gather logs", "Check recent changes", "Review metrics"],
            "common_root_causes": ["Configuration error", "Code bug", "External dependency"],
            "data_to_collect": ["Error logs", "Metrics", "Recent deployments"],
        })
        return template
    
    def suggest_root_cause(self, incident: Incident, evidence: dict) -> list[dict]:
        """Suggest likely root causes based on evidence."""
        template = self._analysis_templates.get(incident.type, {})
        causes = template.get("common_root_causes", [])
        
        # Score each potential cause based on evidence
        scored_causes = []
        for cause in causes:
            score = self._score_cause(cause, evidence)
            scored_causes.append({"cause": cause, "likelihood": score})
        
        scored_causes.sort(key=lambda x: x["likelihood"], reverse=True)
        return scored_causes
    
    def _score_cause(self, cause: str, evidence: dict) -> float:
        """Heuristic scoring of cause likelihood based on evidence."""
        # Simplified scoring - in production this would be more sophisticated
        score = 0.3  # Base likelihood
        
        # Keyword matching against evidence
        evidence_text = json.dumps(evidence).lower()
        cause_keywords = cause.lower().split()
        
        for keyword in cause_keywords:
            if keyword in evidence_text:
                score += 0.1
        
        return min(score, 1.0)


# =============================================================================
# POSTMORTEM GENERATION
# =============================================================================

class PostmortemGenerator:
    """Generates structured postmortem documents from incident data."""
    
    def generate(self, incident: Incident) -> str:
        """Generate a complete postmortem document."""
        duration = "Unknown"
        if incident.resolved_at:
            dur = incident.resolved_at - incident.detected_at
            duration = f"{int(dur.total_seconds() / 60)} minutes"
        
        # Format timeline
        timeline_text = ""
        for entry in incident.timeline:
            timeline_text += f"- **{entry.timestamp.strftime('%H:%M UTC')}** - [{entry.actor}] {entry.action}: {entry.details}\n"
        
        # Format action items
        action_items_text = ""
        for idx, item in enumerate(incident.action_items, 1):
            action_items_text += f"| {idx} | {item.get('action', '')} | {item.get('owner', '')} | {item.get('priority', '')} | {item.get('due_date', '')} |\n"
        
        postmortem = f"""# Incident Postmortem: {incident.title}

## Summary

| Field | Value |
|-------|-------|
| Incident ID | {incident.id} |
| Severity | {incident.severity.value.upper()} |
| Type | {incident.type.value} |
| Duration | {duration} |
| Impact | {incident.impact_description} |
| Affected Users | {incident.affected_users} |
| Affected Requests | {incident.affected_requests} |
| SLOs Breached | {', '.join(incident.slos_breached) or 'None'} |
| Error Budget Consumed | {incident.error_budget_consumed_pct:.1f}% |

## Timeline

{timeline_text}

## Root Cause

{incident.root_cause or 'Under investigation'}

## Mitigation Applied

{incident.mitigation_applied or 'Described in timeline'}

## AI-Specific Analysis

### Was this a model behavior change?
_[To be filled by postmortem author]_

### Was this a data/retrieval issue?
_[To be filled by postmortem author]_

### Could automated evaluation have caught this earlier?
_[To be filled by postmortem author]_

### Did non-determinism make this harder to detect?
_[To be filled by postmortem author]_

### Was the failure mode in our chaos engineering scenarios?
_[To be filled by postmortem author]_

## What Went Well

- Automated detection triggered within expected timeframe
- Runbook was available and followed
- Communication was timely

## What Went Wrong

- _[To be filled during postmortem meeting]_

## Action Items

| # | Action | Owner | Priority | Due Date |
|---|--------|-------|----------|----------|
{action_items_text or '| 1 | _To be determined in postmortem meeting_ | - | - | - |'}

## Lessons Learned

{chr(10).join(f'- {lesson}' for lesson in incident.lessons_learned) or '- _To be discussed in postmortem meeting_'}

---

_Generated at {datetime.utcnow().isoformat()} by AI Incident Management System_
"""
        return postmortem


# =============================================================================
# INCIDENT METRICS AND TRENDS
# =============================================================================

class IncidentMetrics:
    """Tracks incident metrics and trends over time."""
    
    def __init__(self):
        self._incidents: list[Incident] = []
    
    def record_incident(self, incident: Incident):
        self._incidents.append(incident)
    
    def get_metrics(self, period_days: int = 30) -> dict:
        """Get incident metrics for a time period."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        incidents = [i for i in self._incidents if i.detected_at > cutoff]
        
        if not incidents:
            return {"period_days": period_days, "total_incidents": 0}
        
        # Basic counts
        by_severity = defaultdict(int)
        by_type = defaultdict(int)
        durations = []
        ttd_values = []  # Time to detect
        ttm_values = []  # Time to mitigate
        
        for inc in incidents:
            by_severity[inc.severity.value] += 1
            by_type[inc.type.value] += 1
            if inc.total_duration_minutes:
                durations.append(inc.total_duration_minutes)
            if inc.time_to_detect_minutes:
                ttd_values.append(inc.time_to_detect_minutes)
            if inc.time_to_mitigate_minutes:
                ttm_values.append(inc.time_to_mitigate_minutes)
        
        return {
            "period_days": period_days,
            "total_incidents": len(incidents),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "mttr_minutes": statistics.mean(durations) if durations else None,
            "mttd_minutes": statistics.mean(ttd_values) if ttd_values else None,
            "mttm_minutes": statistics.mean(ttm_values) if ttm_values else None,
            "incidents_per_week": len(incidents) / (period_days / 7),
            "p0_count": by_severity.get("p0", 0),
            "p1_count": by_severity.get("p1", 0),
        }
    
    def get_trends(self, weeks: int = 12) -> list[dict]:
        """Get weekly incident trends."""
        trends = []
        now = datetime.utcnow()
        
        for week in range(weeks):
            week_end = now - timedelta(weeks=week)
            week_start = week_end - timedelta(weeks=1)
            
            week_incidents = [
                i for i in self._incidents 
                if week_start <= i.detected_at < week_end
            ]
            
            trends.append({
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total": len(week_incidents),
                "p0": sum(1 for i in week_incidents if i.severity == IncidentSeverity.P0),
                "p1": sum(1 for i in week_incidents if i.severity == IncidentSeverity.P1),
                "p2": sum(1 for i in week_incidents if i.severity == IncidentSeverity.P2),
            })
        
        trends.reverse()
        return trends


# =============================================================================
# COMPLETE INCIDENT MANAGER
# =============================================================================

class AIIncidentManager:
    """
    Complete incident management system for AI applications.
    
    Orchestrates detection, classification, response, escalation,
    communication, and postmortem for AI-specific incidents.
    """
    
    def __init__(self):
        self.detector = IncidentDetector()
        self.classifier = SeverityClassifier()
        self.responder = AutomatedResponder()
        self.escalation = EscalationEngine()
        self.comms = CommunicationManager()
        self.rca = RootCauseAnalyzer()
        self.postmortem_gen = PostmortemGenerator()
        self.metrics = IncidentMetrics()
        
        self._active_incidents: dict[str, Incident] = {}
    
    def process_signal(self, signal: AlertSignal) -> Optional[Incident]:
        """Process an incoming signal - may create a new incident."""
        incident = self.detector.ingest_signal(signal)
        
        if incident:
            # Classify severity
            incident.severity = self.classifier.classify(incident)
            
            # Automated response
            self.responder.respond(incident)
            
            # Initial communication
            self.comms.send_initial_notification(incident)
            
            # Evaluate escalations
            self.escalation.evaluate_escalations(incident)
            
            # Track
            self._active_incidents[incident.id] = incident
            self.metrics.record_incident(incident)
            
            logger.info(f"New incident: {incident.id} - {incident.title} [{incident.severity.value}]")
            return incident
        
        return None
    
    def update_incident(self, incident_id: str, update: str, 
                        new_status: Optional[IncidentStatus] = None):
        """Update an active incident."""
        incident = self._active_incidents.get(incident_id)
        if not incident:
            raise ValueError(f"No active incident: {incident_id}")
        
        if new_status:
            incident.status = new_status
        
        incident.add_timeline(
            action="manual_update",
            actor="incident_commander",
            details=update,
        )
        
        self.comms.send_status_update(incident, update)
        self.escalation.evaluate_escalations(incident)
    
    def resolve_incident(self, incident_id: str, root_cause: str, 
                         mitigation: str):
        """Resolve an incident."""
        incident = self._active_incidents.get(incident_id)
        if not incident:
            raise ValueError(f"No active incident: {incident_id}")
        
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.root_cause = root_cause
        incident.mitigation_applied = mitigation
        incident.total_duration_minutes = (
            incident.resolved_at - incident.detected_at
        ).total_seconds() / 60
        
        incident.add_timeline(
            action="resolved",
            actor="incident_commander",
            details=f"Root cause: {root_cause}. Mitigation: {mitigation}",
        )
        
        self.comms.send_resolution(incident)
        
        del self._active_incidents[incident_id]
        return incident
    
    def generate_postmortem(self, incident: Incident) -> str:
        """Generate postmortem document for a resolved incident."""
        return self.postmortem_gen.generate(incident)
    
    def get_active_incidents(self) -> list[Incident]:
        """Get all active incidents."""
        return list(self._active_incidents.values())
    
    def get_metrics_summary(self) -> dict:
        """Get incident metrics summary."""
        return self.metrics.get_metrics()


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    manager = AIIncidentManager()
    
    # Simulate a model provider outage
    print("=== Simulating Model Provider Outage ===\n")
    
    signal = AlertSignal(
        source="metrics",
        signal_type="model_5xx_rate_high",
        severity_hint="p1",
        message="Model provider error rate at 75%",
        timestamp=datetime.utcnow(),
        metadata={"provider": "openai", "error_rate": 0.75},
    )
    
    incident = manager.process_signal(signal)
    if incident:
        print(f"Incident created: {incident.id}")
        print(f"Title: {incident.title}")
        print(f"Severity: {incident.severity.value}")
        print(f"Status: {incident.status.value}")
        print(f"Timeline entries: {len(incident.timeline)}")
        
        # Simulate investigation
        manager.update_incident(
            incident.id,
            "Confirmed OpenAI experiencing elevated error rates in us-east-1",
            IncidentStatus.INVESTIGATING,
        )
        
        manager.update_incident(
            incident.id,
            "Fallback to Anthropic Claude active, monitoring quality",
            IncidentStatus.MITIGATING,
        )
        
        # Resolve
        resolved = manager.resolve_incident(
            incident.id,
            root_cause="OpenAI infrastructure issue in us-east-1 region",
            mitigation="Switched to fallback provider (Anthropic Claude)",
        )
        
        print(f"\nResolved after {resolved.total_duration_minutes:.1f} minutes")
        print(f"\nTimeline ({len(resolved.timeline)} entries):")
        for entry in resolved.timeline:
            print(f"  {entry.timestamp.strftime('%H:%M:%S')} [{entry.actor}] {entry.action}: {entry.details}")
        
        # Generate postmortem
        print("\n=== Generated Postmortem (first 50 lines) ===\n")
        postmortem = manager.generate_postmortem(resolved)
        for line in postmortem.split("\n")[:50]:
            print(line)
    
    # Show metrics
    print("\n=== Incident Metrics ===")
    metrics = manager.get_metrics_summary()
    print(json.dumps(metrics, indent=2))
