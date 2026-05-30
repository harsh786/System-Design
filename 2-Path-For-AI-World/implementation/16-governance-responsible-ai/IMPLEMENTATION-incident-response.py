"""
AI Incident Response System
=============================
Comprehensive incident detection, classification, response, and post-incident
review system for AI-specific incidents including bias, safety, security,
reliability, and misuse incidents.
"""

import uuid
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field, asdict


# =============================================================================
# Enumerations
# =============================================================================

class IncidentSeverity(Enum):
    SEV1_CRITICAL = "sev1"  # Active harm, regulatory breach, system weaponized
    SEV2_HIGH = "sev2"      # Significant bias, data breach, major degradation
    SEV3_MEDIUM = "sev3"    # Performance issues, minor fairness, limited impact
    SEV4_LOW = "sev4"       # Near-miss, minor anomalies, documentation gaps


class IncidentType(Enum):
    SAFETY = "safety"                # Harm to individuals
    FAIRNESS_BIAS = "fairness_bias"  # Discrimination, unfair outcomes
    PRIVACY_SECURITY = "privacy_security"  # Data breach, unauthorized access
    RELIABILITY = "reliability"      # Outage, degradation, incorrect outputs
    MISUSE_ABUSE = "misuse_abuse"    # System used for unintended harmful purposes
    COMPLIANCE = "compliance"        # Regulatory violation discovered
    HALLUCINATION = "hallucination"  # Factually incorrect outputs causing harm
    ADVERSARIAL = "adversarial"      # Successful adversarial attack


class IncidentStatus(Enum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    POST_REVIEW = "post_review"
    CLOSED = "closed"


class EscalationLevel(Enum):
    L1_TEAM = "l1_team"           # On-call team handles
    L2_MANAGEMENT = "l2_management"  # Engineering management
    L3_EXECUTIVE = "l3_executive"    # VP/C-level
    L4_BOARD = "l4_board"           # Board notification
    EXTERNAL = "external"           # Regulator/public notification


class DetectionSource(Enum):
    AUTOMATED_MONITORING = "automated_monitoring"
    USER_REPORT = "user_report"
    INTERNAL_REPORT = "internal_report"
    EXTERNAL_REPORT = "external_report"
    AUDIT = "audit"
    RED_TEAM = "red_team"
    MEDIA = "media"
    REGULATOR = "regulator"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ImpactAssessment:
    affected_users_count: int = 0
    affected_user_groups: list = field(default_factory=list)
    harm_type: str = ""  # "financial", "reputational", "physical", "psychological", "rights"
    harm_severity: str = ""  # "none", "minor", "moderate", "severe", "critical"
    reversibility: str = ""  # "fully_reversible", "partially_reversible", "irreversible"
    geographic_scope: str = ""
    financial_impact_estimate: str = ""
    regulatory_implications: list = field(default_factory=list)
    reputational_impact: str = ""


@dataclass
class TimelineEntry:
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = ""
    actor: str = ""
    details: str = ""
    artifacts: list = field(default_factory=list)  # links to logs, screenshots, etc.


@dataclass
class ContainmentAction:
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""
    executed_by: str = ""
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    effectiveness: str = ""  # "effective", "partially_effective", "ineffective"
    rollback_plan: str = ""


@dataclass
class RootCause:
    category: str = ""  # "model", "data", "infrastructure", "process", "human"
    description: str = ""
    contributing_factors: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    five_whys: list = field(default_factory=list)
    preventable: bool = True


@dataclass
class RemediationAction:
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    owner: str = ""
    target_date: str = ""
    status: str = "open"  # "open", "in_progress", "completed", "verified"
    verification_method: str = ""
    completed_at: Optional[str] = None


@dataclass
class PostIncidentReview:
    review_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    review_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    participants: list = field(default_factory=list)
    root_cause: RootCause = field(default_factory=RootCause)
    what_went_well: list = field(default_factory=list)
    what_went_wrong: list = field(default_factory=list)
    lessons_learned: list = field(default_factory=list)
    action_items: list = field(default_factory=list)  # list of RemediationAction
    systemic_improvements: list = field(default_factory=list)
    follow_up_date: str = ""


@dataclass
class Incident:
    """Core incident record."""
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    severity: str = IncidentSeverity.SEV3_MEDIUM.value
    incident_type: str = IncidentType.RELIABILITY.value
    status: str = IncidentStatus.DETECTED.value

    # System information
    ai_system_id: str = ""
    ai_system_name: str = ""
    model_version: str = ""
    environment: str = ""  # "production", "staging", "development"

    # Detection
    detection_source: str = DetectionSource.AUTOMATED_MONITORING.value
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    detected_by: str = ""
    detection_details: str = ""

    # Response
    responder: str = ""
    escalation_level: str = EscalationLevel.L1_TEAM.value
    impact_assessment: ImpactAssessment = field(default_factory=ImpactAssessment)

    # Timeline
    timeline: list = field(default_factory=list)  # list of TimelineEntry

    # Containment
    containment_actions: list = field(default_factory=list)
    contained_at: Optional[str] = None

    # Investigation
    root_cause: Optional[RootCause] = None
    related_incidents: list = field(default_factory=list)

    # Resolution
    resolution_description: str = ""
    resolved_at: Optional[str] = None
    remediation_actions: list = field(default_factory=list)

    # Post-incident
    post_incident_review: Optional[PostIncidentReview] = None

    # Communication
    communications_sent: list = field(default_factory=list)
    external_notifications: list = field(default_factory=list)  # regulators, affected parties

    # Metadata
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    closed_at: Optional[str] = None

    @property
    def time_to_detect(self) -> Optional[str]:
        """Time from incident start to detection (if start time known)."""
        return None  # Would need incident_start_time

    @property
    def time_to_contain(self) -> Optional[float]:
        """Hours from detection to containment."""
        if self.contained_at:
            detected = datetime.fromisoformat(self.detected_at)
            contained = datetime.fromisoformat(self.contained_at)
            return (contained - detected).total_seconds() / 3600
        return None

    @property
    def time_to_resolve(self) -> Optional[float]:
        """Hours from detection to resolution."""
        if self.resolved_at:
            detected = datetime.fromisoformat(self.detected_at)
            resolved = datetime.fromisoformat(self.resolved_at)
            return (resolved - detected).total_seconds() / 3600
        return None


# =============================================================================
# Detection Triggers
# =============================================================================

class IncidentDetectionEngine:
    """Evaluates monitoring signals and triggers incident creation."""

    def __init__(self):
        self.triggers: list[dict] = self._default_triggers()
        self._handlers: list = []

    def _default_triggers(self) -> list[dict]:
        """Default detection triggers for AI incidents."""
        return [
            {
                "id": "accuracy_drop",
                "name": "Model Accuracy Degradation",
                "condition": "accuracy_metric < threshold",
                "threshold_config": {"metric": "accuracy", "drop_percent": 10, "window_hours": 1},
                "incident_type": IncidentType.RELIABILITY.value,
                "default_severity": IncidentSeverity.SEV3_MEDIUM.value,
            },
            {
                "id": "fairness_violation",
                "name": "Fairness Metric Violation",
                "condition": "disparity_ratio > threshold",
                "threshold_config": {"metric": "demographic_parity_ratio", "max_disparity": 0.2},
                "incident_type": IncidentType.FAIRNESS_BIAS.value,
                "default_severity": IncidentSeverity.SEV2_HIGH.value,
            },
            {
                "id": "hallucination_spike",
                "name": "Hallucination Rate Spike",
                "condition": "hallucination_rate > baseline * multiplier",
                "threshold_config": {"baseline_rate": 0.02, "multiplier": 3},
                "incident_type": IncidentType.HALLUCINATION.value,
                "default_severity": IncidentSeverity.SEV3_MEDIUM.value,
            },
            {
                "id": "prompt_injection_detected",
                "name": "Prompt Injection Attack",
                "condition": "injection_attempts > threshold in window",
                "threshold_config": {"max_attempts": 10, "window_minutes": 5},
                "incident_type": IncidentType.ADVERSARIAL.value,
                "default_severity": IncidentSeverity.SEV2_HIGH.value,
            },
            {
                "id": "pii_leakage",
                "name": "PII in Model Output",
                "condition": "pii_detected_in_output == true",
                "threshold_config": {"pii_types": ["ssn", "credit_card", "medical_record"]},
                "incident_type": IncidentType.PRIVACY_SECURITY.value,
                "default_severity": IncidentSeverity.SEV1_CRITICAL.value,
            },
            {
                "id": "harmful_output",
                "name": "Harmful Content Generated",
                "condition": "safety_classifier_score > threshold",
                "threshold_config": {"safety_score_threshold": 0.9, "categories": ["violence", "self_harm"]},
                "incident_type": IncidentType.SAFETY.value,
                "default_severity": IncidentSeverity.SEV1_CRITICAL.value,
            },
            {
                "id": "unusual_usage_pattern",
                "name": "Anomalous Usage Pattern (Potential Misuse)",
                "condition": "usage_anomaly_score > threshold",
                "threshold_config": {"anomaly_score_threshold": 0.95},
                "incident_type": IncidentType.MISUSE_ABUSE.value,
                "default_severity": IncidentSeverity.SEV3_MEDIUM.value,
            },
        ]

    def evaluate_signal(self, signal: dict) -> Optional[dict]:
        """
        Evaluate a monitoring signal against triggers.

        signal: {trigger_id, metric_value, context, timestamp}
        Returns incident creation request if trigger fires, None otherwise.
        """
        trigger_id = signal.get("trigger_id")
        trigger = next((t for t in self.triggers if t["id"] == trigger_id), None)
        if not trigger:
            return None

        # Simple threshold evaluation (in production, this would be more sophisticated)
        metric_value = signal.get("metric_value")
        threshold_config = trigger["threshold_config"]

        fired = False
        if "drop_percent" in threshold_config:
            baseline = signal.get("baseline_value", 1.0)
            if baseline > 0 and (baseline - metric_value) / baseline * 100 > threshold_config["drop_percent"]:
                fired = True
        elif "max_disparity" in threshold_config:
            if metric_value > threshold_config["max_disparity"]:
                fired = True
        elif "multiplier" in threshold_config:
            if metric_value > threshold_config["baseline_rate"] * threshold_config["multiplier"]:
                fired = True
        elif "max_attempts" in threshold_config:
            if metric_value > threshold_config["max_attempts"]:
                fired = True
        elif trigger_id in ("pii_leakage", "harmful_output"):
            if metric_value:  # boolean or score above threshold
                fired = True

        if fired:
            return {
                "trigger": trigger,
                "signal": signal,
                "suggested_severity": trigger["default_severity"],
                "suggested_type": trigger["incident_type"],
                "auto_create": trigger["default_severity"] in (
                    IncidentSeverity.SEV1_CRITICAL.value,
                    IncidentSeverity.SEV2_HIGH.value,
                ),
            }
        return None


# =============================================================================
# Response Playbooks
# =============================================================================

class ResponsePlaybook:
    """Defines response procedures by incident type."""

    PLAYBOOKS = {
        IncidentType.SAFETY.value: {
            "name": "Safety Incident Response",
            "immediate_actions": [
                "Disable/throttle the affected AI system immediately",
                "Activate fallback/non-AI path for affected users",
                "Notify incident commander and safety team",
                "Preserve all logs and model state",
            ],
            "containment": [
                "Block the specific input patterns causing harmful output",
                "Enable maximum content filtering",
                "Restrict system to known-safe use cases only",
                "Implement rate limiting if not already in place",
            ],
            "investigation": [
                "Identify all instances of harmful output in logs",
                "Determine root cause (model issue, data issue, prompt issue)",
                "Assess total user exposure and potential harm",
                "Check if issue is reproducible or stochastic",
            ],
            "communication": [
                "Internal: Notify leadership within 1 hour",
                "Affected users: Notify within 24 hours if harm occurred",
                "Regulator: Assess notification obligations (72h for serious incidents under EU AI Act)",
            ],
            "resolution": [
                "Deploy fix (model update, guardrail, filter)",
                "Validate fix does not introduce regressions",
                "Gradually restore full functionality with monitoring",
                "Confirm no ongoing harm",
            ],
            "sla": {"acknowledge": "15 min", "contain": "1 hour", "resolve": "4 hours"},
        },
        IncidentType.FAIRNESS_BIAS.value: {
            "name": "Fairness/Bias Incident Response",
            "immediate_actions": [
                "Assess scope: how many decisions affected and over what period",
                "Determine if decisions are reversible",
                "Notify AI ethics team and legal",
                "Continue operation with enhanced monitoring OR pause if harm is ongoing",
            ],
            "containment": [
                "Add fairness guardrails/thresholds to affected decision path",
                "Route affected demographic groups to human review",
                "Implement temporary equal-outcome override if appropriate",
            ],
            "investigation": [
                "Run full disaggregated evaluation across protected attributes",
                "Trace bias source: data, model, feature engineering, or post-processing",
                "Quantify disparate impact using appropriate legal/ethical frameworks",
                "Identify affected individuals for potential remediation",
            ],
            "communication": [
                "Internal: Notify DEI team, legal, product leadership",
                "Assess individual notification obligations",
                "Prepare public statement if issue is widespread",
            ],
            "resolution": [
                "Implement bias mitigation (pre/in/post-processing)",
                "Retrain if data-level fix needed",
                "Validate fix meets fairness criteria",
                "Remediate affected individuals (reverse decisions if possible)",
            ],
            "sla": {"acknowledge": "1 hour", "contain": "4 hours", "resolve": "72 hours"},
        },
        IncidentType.PRIVACY_SECURITY.value: {
            "name": "Privacy/Security Incident Response",
            "immediate_actions": [
                "Isolate affected system from network if active breach",
                "Revoke compromised credentials/tokens",
                "Notify CISO and DPO immediately",
                "Begin evidence preservation (forensic copy of logs)",
            ],
            "containment": [
                "Block attack vector (IP, endpoint, input pattern)",
                "Disable affected API endpoints",
                "Rotate all secrets/keys that may be compromised",
                "Enable enhanced logging",
            ],
            "investigation": [
                "Determine data exposed: type, volume, sensitivity",
                "Identify attack method and timeline",
                "Assess if model weights/IP were exfiltrated",
                "Check for lateral movement or persistence",
            ],
            "communication": [
                "DPA notification within 72 hours (GDPR Art. 33)",
                "Affected individuals without undue delay if high risk (GDPR Art. 34)",
                "Law enforcement if criminal activity suspected",
            ],
            "resolution": [
                "Patch vulnerability",
                "Implement additional security controls",
                "Re-assess model if training data was compromised",
                "Conduct security review of similar systems",
            ],
            "sla": {"acknowledge": "15 min", "contain": "1 hour", "resolve": "24 hours"},
        },
        IncidentType.RELIABILITY.value: {
            "name": "Reliability Incident Response",
            "immediate_actions": [
                "Assess current error rate and user impact",
                "Check if automatic failover/fallback activated",
                "Notify on-call team and product owner",
            ],
            "containment": [
                "Route traffic to backup model/system if available",
                "Reduce traffic load (rate limit, feature flag)",
                "Serve cached/default responses if appropriate",
            ],
            "investigation": [
                "Check for infrastructure issues (GPU, memory, network)",
                "Analyze recent deployments or config changes",
                "Check input data distribution for anomalies",
                "Review dependency health",
            ],
            "communication": [
                "Status page update for customer-facing issues",
                "Internal stakeholder notification",
            ],
            "resolution": [
                "Fix underlying cause (rollback, scale, repair)",
                "Validate system health metrics return to baseline",
                "Remove traffic restrictions gradually",
            ],
            "sla": {"acknowledge": "5 min", "contain": "30 min", "resolve": "4 hours"},
        },
        IncidentType.HALLUCINATION.value: {
            "name": "Hallucination Incident Response",
            "immediate_actions": [
                "Assess harm: did users act on false information?",
                "Determine scope (specific topic or general degradation)",
                "Enable confidence thresholds / abstention",
            ],
            "containment": [
                "Add fact-checking layer for affected domain",
                "Restrict model responses to verified information",
                "Add disclaimers to model outputs",
                "Route affected queries to human agents",
            ],
            "investigation": [
                "Identify pattern in hallucinated content",
                "Check knowledge cutoff and retrieval system health",
                "Assess if caused by adversarial input or model issue",
                "Review RAG pipeline for failures",
            ],
            "communication": [
                "Correct false information publicly if it spread",
                "Notify affected users of potential inaccuracies",
            ],
            "resolution": [
                "Update knowledge base / retrieval corpus",
                "Tune confidence thresholds",
                "Implement output verification for affected domains",
                "Add regression tests for identified failure cases",
            ],
            "sla": {"acknowledge": "30 min", "contain": "2 hours", "resolve": "24 hours"},
        },
    }

    @classmethod
    def get_playbook(cls, incident_type: str) -> dict:
        """Get the response playbook for an incident type."""
        return cls.PLAYBOOKS.get(incident_type, cls.PLAYBOOKS[IncidentType.RELIABILITY.value])


# =============================================================================
# Escalation Procedures
# =============================================================================

class EscalationManager:
    """Manages incident escalation based on severity and time."""

    ESCALATION_MATRIX = {
        IncidentSeverity.SEV1_CRITICAL.value: {
            "initial": EscalationLevel.L2_MANAGEMENT.value,
            "30_min": EscalationLevel.L3_EXECUTIVE.value,
            "2_hours": EscalationLevel.L4_BOARD.value,
            "external_notification": True,
            "regulator_notification": True,
        },
        IncidentSeverity.SEV2_HIGH.value: {
            "initial": EscalationLevel.L1_TEAM.value,
            "1_hour": EscalationLevel.L2_MANAGEMENT.value,
            "4_hours": EscalationLevel.L3_EXECUTIVE.value,
            "external_notification": False,
            "regulator_notification": "assess",
        },
        IncidentSeverity.SEV3_MEDIUM.value: {
            "initial": EscalationLevel.L1_TEAM.value,
            "4_hours": EscalationLevel.L2_MANAGEMENT.value,
            "external_notification": False,
            "regulator_notification": False,
        },
        IncidentSeverity.SEV4_LOW.value: {
            "initial": EscalationLevel.L1_TEAM.value,
            "external_notification": False,
            "regulator_notification": False,
        },
    }

    def get_escalation_path(self, severity: str) -> dict:
        return self.ESCALATION_MATRIX.get(severity, self.ESCALATION_MATRIX[IncidentSeverity.SEV4_LOW.value])

    def check_escalation_needed(self, incident: Incident) -> Optional[str]:
        """Check if an incident needs escalation based on elapsed time."""
        path = self.get_escalation_path(incident.severity)
        elapsed_hours = 0
        if incident.detected_at:
            elapsed = datetime.utcnow() - datetime.fromisoformat(incident.detected_at)
            elapsed_hours = elapsed.total_seconds() / 3600

        current_level = incident.escalation_level
        levels = [EscalationLevel.L1_TEAM.value, EscalationLevel.L2_MANAGEMENT.value,
                  EscalationLevel.L3_EXECUTIVE.value, EscalationLevel.L4_BOARD.value]
        current_idx = levels.index(current_level) if current_level in levels else 0

        # Check time-based escalation
        if elapsed_hours >= 4 and "4_hours" in path:
            target = path["4_hours"]
            if levels.index(target) > current_idx:
                return target
        elif elapsed_hours >= 2 and "2_hours" in path:
            target = path["2_hours"]
            if levels.index(target) > current_idx:
                return target
        elif elapsed_hours >= 1 and "1_hour" in path:
            target = path["1_hour"]
            if levels.index(target) > current_idx:
                return target
        elif elapsed_hours >= 0.5 and "30_min" in path:
            target = path["30_min"]
            if levels.index(target) > current_idx:
                return target

        return None


# =============================================================================
# Communication Templates
# =============================================================================

class CommunicationTemplates:
    """Templates for incident communications."""

    TEMPLATES = {
        "internal_notification": {
            "subject": "[{severity}] AI Incident: {title}",
            "body": """
INCIDENT NOTIFICATION
=====================
Incident ID: {incident_id}
Severity: {severity}
Type: {incident_type}
System: {system_name}
Detected: {detected_at}

DESCRIPTION:
{description}

CURRENT STATUS: {status}
RESPONDER: {responder}

IMPACT:
- Affected users: {affected_users}
- Harm type: {harm_type}

IMMEDIATE ACTIONS TAKEN:
{actions_taken}

NEXT STEPS:
{next_steps}

Escalation path: {escalation_level}
""",
        },
        "external_affected_parties": {
            "subject": "Important Notice: Issue with {system_name}",
            "body": """
Dear {recipient},

We are writing to inform you about an issue we identified with our {system_name} system that may have affected you.

WHAT HAPPENED:
{description_external}

WHAT WE ARE DOING:
{remediation_summary}

WHAT YOU CAN DO:
{user_actions}

We take this matter seriously and are committed to resolving it fully. If you have questions or concerns, please contact {contact_info}.

Sincerely,
{organization}
""",
        },
        "regulator_notification": {
            "subject": "AI Incident Notification - {organization} - {incident_id}",
            "body": """
REGULATORY INCIDENT NOTIFICATION
=================================
Organization: {organization}
AI System: {system_name} (Registration: {system_registration})
Incident ID: {incident_id}
Date of Discovery: {detected_at}

1. NATURE OF INCIDENT:
{description}

2. CATEGORIES OF DATA/INDIVIDUALS AFFECTED:
{affected_categories}

3. APPROXIMATE NUMBER OF AFFECTED INDIVIDUALS:
{affected_count}

4. CONSEQUENCES OF THE INCIDENT:
{consequences}

5. MEASURES TAKEN OR PROPOSED:
{measures}

6. CONTACT POINT:
{dpo_contact}

This notification is made pursuant to {regulatory_basis}.
""",
        },
    }

    @classmethod
    def render(cls, template_name: str, context: dict) -> dict:
        """Render a communication template with context."""
        template = cls.TEMPLATES.get(template_name)
        if not template:
            return {"error": f"Template '{template_name}' not found"}

        rendered = {}
        for key, value in template.items():
            try:
                rendered[key] = value.format(**context)
            except KeyError as e:
                rendered[key] = value  # Leave unformatted if context incomplete
        return rendered


# =============================================================================
# Incident Management System
# =============================================================================

class AIIncidentResponseSystem:
    """Central incident management system."""

    def __init__(self):
        self.incidents: dict[str, Incident] = {}
        self.detection_engine = IncidentDetectionEngine()
        self.escalation_manager = EscalationManager()

    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        incident_type: IncidentType,
        ai_system_id: str,
        ai_system_name: str,
        detected_by: str,
        detection_source: DetectionSource,
        model_version: str = "",
        environment: str = "production",
    ) -> Incident:
        """Create a new incident."""
        incident = Incident(
            title=title,
            description=description,
            severity=severity.value,
            incident_type=incident_type.value,
            ai_system_id=ai_system_id,
            ai_system_name=ai_system_name,
            detected_by=detected_by,
            detection_source=detection_source.value,
            model_version=model_version,
            environment=environment,
        )

        # Add detection to timeline
        incident.timeline.append(asdict(TimelineEntry(
            action="incident_detected",
            actor=detected_by,
            details=f"Incident detected via {detection_source.value}",
        )))

        # Auto-escalation for SEV1
        path = self.escalation_manager.get_escalation_path(incident.severity)
        incident.escalation_level = path.get("initial", EscalationLevel.L1_TEAM.value)

        self.incidents[incident.incident_id] = incident
        return incident

    def triage(self, incident_id: str, responder: str, confirmed_severity: IncidentSeverity,
               initial_assessment: str) -> Incident:
        """Triage an incident - assign responder and confirm severity."""
        incident = self.incidents[incident_id]
        incident.status = IncidentStatus.TRIAGED.value
        incident.responder = responder
        incident.severity = confirmed_severity.value
        incident.updated_at = datetime.utcnow().isoformat()

        incident.timeline.append(asdict(TimelineEntry(
            action="incident_triaged",
            actor=responder,
            details=f"Severity confirmed as {confirmed_severity.value}. {initial_assessment}",
        )))

        return incident

    def assess_impact(self, incident_id: str, impact: ImpactAssessment) -> Incident:
        """Record impact assessment."""
        incident = self.incidents[incident_id]
        incident.impact_assessment = impact
        incident.updated_at = datetime.utcnow().isoformat()

        incident.timeline.append(asdict(TimelineEntry(
            action="impact_assessed",
            actor=incident.responder,
            details=f"Impact: {impact.affected_users_count} users, {impact.harm_severity} severity",
        )))

        return incident

    def contain(self, incident_id: str, actions: list[ContainmentAction]) -> Incident:
        """Record containment actions."""
        incident = self.incidents[incident_id]
        incident.status = IncidentStatus.CONTAINED.value
        incident.contained_at = datetime.utcnow().isoformat()
        incident.containment_actions = [asdict(a) for a in actions]
        incident.updated_at = datetime.utcnow().isoformat()

        for action in actions:
            incident.timeline.append(asdict(TimelineEntry(
                action="containment_action",
                actor=action.executed_by,
                details=action.action,
            )))

        return incident

    def resolve(self, incident_id: str, resolution: str, remediation_actions: list[RemediationAction]) -> Incident:
        """Mark incident as resolved."""
        incident = self.incidents[incident_id]
        incident.status = IncidentStatus.RESOLVED.value
        incident.resolved_at = datetime.utcnow().isoformat()
        incident.resolution_description = resolution
        incident.remediation_actions = [asdict(a) for a in remediation_actions]
        incident.updated_at = datetime.utcnow().isoformat()

        incident.timeline.append(asdict(TimelineEntry(
            action="incident_resolved",
            actor=incident.responder,
            details=resolution,
        )))

        return incident

    def conduct_post_incident_review(self, incident_id: str, review: PostIncidentReview) -> Incident:
        """Record post-incident review results."""
        incident = self.incidents[incident_id]
        incident.status = IncidentStatus.POST_REVIEW.value
        incident.post_incident_review = asdict(review)
        incident.updated_at = datetime.utcnow().isoformat()

        incident.timeline.append(asdict(TimelineEntry(
            action="post_incident_review",
            actor=", ".join(review.participants[:3]),
            details=f"PIR completed. {len(review.action_items)} action items identified.",
        )))

        return incident

    def close(self, incident_id: str, closed_by: str) -> Incident:
        """Close an incident after all remediation is verified."""
        incident = self.incidents[incident_id]
        incident.status = IncidentStatus.CLOSED.value
        incident.closed_at = datetime.utcnow().isoformat()
        incident.updated_at = datetime.utcnow().isoformat()

        incident.timeline.append(asdict(TimelineEntry(
            action="incident_closed",
            actor=closed_by,
            details="All remediation actions verified. Incident closed.",
        )))

        return incident

    # -------------------------------------------------------------------------
    # Metrics and Trending
    # -------------------------------------------------------------------------

    def get_incident_metrics(self, days: int = 90) -> dict:
        """Calculate incident metrics for trending."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        recent = [i for i in self.incidents.values() if i.created_at >= cutoff]

        # Time to contain/resolve
        ttc_values = [i.time_to_contain for i in recent if i.time_to_contain is not None]
        ttr_values = [i.time_to_resolve for i in recent if i.time_to_resolve is not None]

        severity_dist = {}
        type_dist = {}
        for i in recent:
            severity_dist[i.severity] = severity_dist.get(i.severity, 0) + 1
            type_dist[i.incident_type] = type_dist.get(i.incident_type, 0) + 1

        return {
            "period_days": days,
            "total_incidents": len(recent),
            "open_incidents": sum(1 for i in recent if i.status not in (
                IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value)),
            "severity_distribution": severity_dist,
            "type_distribution": type_dist,
            "mean_time_to_contain_hours": (sum(ttc_values) / len(ttc_values)) if ttc_values else None,
            "mean_time_to_resolve_hours": (sum(ttr_values) / len(ttr_values)) if ttr_values else None,
            "repeat_incidents": self._identify_repeat_patterns(recent),
        }

    def _identify_repeat_patterns(self, incidents: list[Incident]) -> list[dict]:
        """Identify recurring incident patterns."""
        patterns = {}
        for i in incidents:
            key = f"{i.ai_system_id}:{i.incident_type}"
            if key not in patterns:
                patterns[key] = {"system": i.ai_system_name, "type": i.incident_type, "count": 0}
            patterns[key]["count"] += 1

        return [p for p in patterns.values() if p["count"] > 1]


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    system = AIIncidentResponseSystem()

    # 1. Detect and create incident
    incident = system.create_incident(
        title="Customer chatbot generating discriminatory responses about loan eligibility",
        description="Multiple user reports indicate the customer service chatbot is providing "
                    "different loan eligibility information based on the inferred ethnicity of "
                    "the customer's name, suggesting pre-approval for some groups while directing "
                    "others to 'additional verification requirements'.",
        severity=IncidentSeverity.SEV1_CRITICAL,
        incident_type=IncidentType.FAIRNESS_BIAS,
        ai_system_id="sys-chatbot-loans-001",
        ai_system_name="Loan Advisor Chatbot",
        detected_by="user-reports-aggregator",
        detection_source=DetectionSource.USER_REPORT,
        model_version="gpt-4-ft-loans-v3.2",
        environment="production",
    )

    print(f"=== INCIDENT CREATED ===")
    print(f"ID: {incident.incident_id}")
    print(f"Severity: {incident.severity}")
    print(f"Escalation: {incident.escalation_level}")

    # 2. Get playbook
    playbook = ResponsePlaybook.get_playbook(incident.incident_type)
    print(f"\n=== PLAYBOOK: {playbook['name']} ===")
    print("Immediate Actions:")
    for action in playbook["immediate_actions"]:
        print(f"  - {action}")
    print(f"SLA: Contain within {playbook['sla']['contain']}, Resolve within {playbook['sla']['resolve']}")

    # 3. Triage
    system.triage(
        incident.incident_id,
        responder="ai-ethics-oncall@company.com",
        confirmed_severity=IncidentSeverity.SEV1_CRITICAL,
        initial_assessment="Confirmed bias in responses. Affecting loan-related queries.",
    )

    # 4. Impact assessment
    system.assess_impact(incident.incident_id, ImpactAssessment(
        affected_users_count=2500,
        affected_user_groups=["loan applicants", "minority communities"],
        harm_type="financial",
        harm_severity="severe",
        reversibility="partially_reversible",
        regulatory_implications=["ECOA violation", "EU AI Act Art. 6 high-risk system"],
        reputational_impact="high",
    ))

    # 5. Containment
    system.contain(incident.incident_id, [
        ContainmentAction(
            action="Disabled loan eligibility advice feature in chatbot",
            executed_by="platform-team",
            effectiveness="effective",
        ),
        ContainmentAction(
            action="Routing all loan queries to human agents",
            executed_by="ops-team",
            effectiveness="effective",
        ),
    ])

    # 6. Generate communication
    comms = CommunicationTemplates.render("internal_notification", {
        "severity": incident.severity,
        "title": incident.title,
        "incident_id": incident.incident_id,
        "incident_type": incident.incident_type,
        "system_name": incident.ai_system_name,
        "detected_at": incident.detected_at,
        "description": incident.description,
        "status": incident.status,
        "responder": incident.responder,
        "affected_users": "~2,500",
        "harm_type": "Financial (discriminatory loan advice)",
        "actions_taken": "- Loan advice feature disabled\n- All queries routed to humans",
        "next_steps": "Root cause investigation, full audit of affected interactions",
        "escalation_level": incident.escalation_level,
    })
    print(f"\n=== INTERNAL COMMUNICATION ===")
    print(comms["subject"])

    # 7. Metrics
    metrics = system.get_incident_metrics()
    print(f"\n=== METRICS ===")
    print(json.dumps(metrics, indent=2, default=str))
