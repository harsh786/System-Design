"""
AI UX Trust Components - Trust-Calibrated User Experience
=========================================================
Production-grade components for building AI interfaces that calibrate user trust.
"""

from __future__ import annotations

import json
import time
import hashlib
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


# =============================================================================
# CONFIDENCE DISPLAY
# =============================================================================

class ConfidenceLevel(Enum):
    VERY_HIGH = "very_high"      # >95%
    HIGH = "high"                 # 80-95%
    MEDIUM = "medium"            # 60-80%
    LOW = "low"                  # 40-60%
    VERY_LOW = "very_low"        # <40%
    UNKNOWN = "unknown"


@dataclass
class ConfidenceMetadata:
    """Metadata explaining why confidence is at a given level."""
    score: float  # 0.0 to 1.0
    level: ConfidenceLevel
    factors: list[ConfidenceFactor] = field(default_factory=list)
    explanation: str = ""
    calibration_note: str = ""


@dataclass
class ConfidenceFactor:
    """A single factor contributing to confidence."""
    name: str
    direction: str  # "increases" or "decreases"
    weight: float
    description: str


class ConfidenceDisplayFormatter:
    """
    Formats confidence information for display in various contexts.
    
    Principles:
    - Never show fake precision (e.g., "73.2% confident")
    - Use natural language primarily, visual indicators secondarily
    - Adapt to context (chat, dashboard, report)
    """

    LEVEL_THRESHOLDS = [
        (0.95, ConfidenceLevel.VERY_HIGH),
        (0.80, ConfidenceLevel.HIGH),
        (0.60, ConfidenceLevel.MEDIUM),
        (0.40, ConfidenceLevel.LOW),
        (0.0, ConfidenceLevel.VERY_LOW),
    ]

    DISPLAY_CONFIG = {
        ConfidenceLevel.VERY_HIGH: {
            "color": "#22c55e",
            "icon": "shield-check",
            "bar_fill": 0.95,
            "label": "Very confident",
            "caveat": None,
            "badge_variant": "success",
        },
        ConfidenceLevel.HIGH: {
            "color": "#84cc16",
            "icon": "check-circle",
            "bar_fill": 0.80,
            "label": "Confident",
            "caveat": "You may want to verify critical details",
            "badge_variant": "success-muted",
        },
        ConfidenceLevel.MEDIUM: {
            "color": "#eab308",
            "icon": "alert-circle",
            "bar_fill": 0.60,
            "label": "Moderately confident",
            "caveat": "I'd recommend verifying this independently",
            "badge_variant": "warning",
        },
        ConfidenceLevel.LOW: {
            "color": "#f97316",
            "icon": "alert-triangle",
            "bar_fill": 0.40,
            "label": "Low confidence",
            "caveat": "This is my best guess — please verify before acting on it",
            "badge_variant": "warning-strong",
        },
        ConfidenceLevel.VERY_LOW: {
            "color": "#ef4444",
            "icon": "x-circle",
            "bar_fill": 0.20,
            "label": "Very uncertain",
            "caveat": "I don't have enough information to answer reliably",
            "badge_variant": "danger",
        },
        ConfidenceLevel.UNKNOWN: {
            "color": "#6b7280",
            "icon": "help-circle",
            "bar_fill": 0.0,
            "label": "Unable to assess",
            "caveat": "I cannot determine how reliable this answer is",
            "badge_variant": "neutral",
        },
    }

    NATURAL_LANGUAGE_TEMPLATES = {
        ConfidenceLevel.VERY_HIGH: [
            "I'm very confident about this.",
            "This is well-established and supported by multiple sources.",
        ],
        ConfidenceLevel.HIGH: [
            "I'm fairly confident about this, though you may want to double-check key details.",
            "This is well-supported, but not definitively established.",
        ],
        ConfidenceLevel.MEDIUM: [
            "I have moderate confidence in this answer. I'd suggest verifying independently.",
            "This seems correct based on what I found, but there's meaningful uncertainty.",
        ],
        ConfidenceLevel.LOW: [
            "I'm not very confident about this. Treat it as a starting point, not a final answer.",
            "This is my best interpretation, but I could easily be wrong here.",
        ],
        ConfidenceLevel.VERY_LOW: [
            "I really don't have enough information to answer this reliably.",
            "I'm largely guessing here — please consult a more authoritative source.",
        ],
    }

    def classify(self, score: float) -> ConfidenceLevel:
        """Classify a numeric score into a confidence level."""
        if score is None or score < 0:
            return ConfidenceLevel.UNKNOWN
        for threshold, level in self.LEVEL_THRESHOLDS:
            if score >= threshold:
                return level
        return ConfidenceLevel.VERY_LOW

    def format_for_chat(self, metadata: ConfidenceMetadata) -> dict[str, Any]:
        """Format confidence for inline chat display."""
        config = self.DISPLAY_CONFIG[metadata.level]
        result = {
            "badge": {
                "label": config["label"],
                "variant": config["badge_variant"],
                "icon": config["icon"],
            },
            "caveat": config["caveat"],
            "explanation": metadata.explanation or self._generate_explanation(metadata),
        }
        return result

    def format_for_dashboard(self, metadata: ConfidenceMetadata) -> dict[str, Any]:
        """Format confidence for dashboard/card display with visual bar."""
        config = self.DISPLAY_CONFIG[metadata.level]
        return {
            "bar": {
                "fill_percentage": config["bar_fill"] * 100,
                "color": config["color"],
            },
            "label": config["label"],
            "score_display": self._humanize_score(metadata.score),
            "factors": [
                {
                    "name": f.name,
                    "direction": f.direction,
                    "description": f.description,
                }
                for f in metadata.factors
            ],
        }

    def format_natural_language(self, metadata: ConfidenceMetadata) -> str:
        """Generate a natural language confidence statement."""
        templates = self.NATURAL_LANGUAGE_TEMPLATES.get(metadata.level, [])
        if not templates:
            return "I'm unable to assess my confidence on this."
        # Use first template; in production, vary based on context
        base = templates[0]
        if metadata.factors:
            reasons = self._summarize_factors(metadata.factors)
            base += f" {reasons}"
        return base

    def _generate_explanation(self, metadata: ConfidenceMetadata) -> str:
        """Generate explanation from factors."""
        if not metadata.factors:
            return ""
        increasing = [f for f in metadata.factors if f.direction == "increases"]
        decreasing = [f for f in metadata.factors if f.direction == "decreases"]
        parts = []
        if increasing:
            parts.append(f"Supporting: {', '.join(f.description for f in increasing[:3])}")
        if decreasing:
            parts.append(f"Limiting: {', '.join(f.description for f in decreasing[:3])}")
        return ". ".join(parts)

    def _humanize_score(self, score: float) -> str:
        """Convert score to human-friendly display (avoid fake precision)."""
        if score >= 0.95:
            return "Very high"
        elif score >= 0.80:
            return "High"
        elif score >= 0.60:
            return "Moderate"
        elif score >= 0.40:
            return "Low"
        else:
            return "Very low"

    def _summarize_factors(self, factors: list[ConfidenceFactor]) -> str:
        increasing = [f for f in factors if f.direction == "increases"]
        decreasing = [f for f in factors if f.direction == "decreases"]
        parts = []
        if increasing:
            parts.append(f"Confidence is supported by: {increasing[0].description}")
        if decreasing:
            parts.append(f"However, {decreasing[0].description}")
        return " ".join(parts)


# =============================================================================
# CITATION PRESENTER
# =============================================================================

@dataclass
class Citation:
    """A single citation/source reference."""
    id: str
    title: str
    url: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    snippet: str = ""
    relevance_score: float = 0.0
    source_type: str = "document"  # document, webpage, api, database
    authority_level: str = "medium"  # high, medium, low
    highlighted_text: str = ""  # The specific text from source that supports claim


@dataclass
class CitedClaim:
    """A claim in the response with its supporting citations."""
    claim_text: str
    citations: list[Citation]
    support_strength: str = "strong"  # strong, moderate, weak, conflicting


class CitationPresenter:
    """
    Presents citations in user-friendly formats.
    
    Supports:
    - Inline numbered references [1]
    - Sidebar source panels
    - Expandable source details
    - Confidence-weighted source display
    """

    AUTHORITY_DISPLAY = {
        "high": {"icon": "verified", "label": "Authoritative source"},
        "medium": {"icon": "document", "label": "Standard source"},
        "low": {"icon": "globe", "label": "Unverified source"},
    }

    SUPPORT_DISPLAY = {
        "strong": {"color": "#22c55e", "label": "Well-supported", "icon": "check-double"},
        "moderate": {"color": "#eab308", "label": "Partially supported", "icon": "check"},
        "weak": {"color": "#f97316", "label": "Weakly supported", "icon": "alert"},
        "conflicting": {"color": "#ef4444", "label": "Sources conflict", "icon": "x"},
    }

    def format_inline(self, text: str, cited_claims: list[CitedClaim]) -> dict[str, Any]:
        """
        Format response text with inline citation markers.
        Returns structured content for rendering.
        """
        annotated_segments = []
        footnotes = []
        citation_index = 1
        citation_map: dict[str, int] = {}

        for claim in cited_claims:
            segment = {"text": claim.claim_text, "citation_refs": []}
            for citation in claim.citations:
                if citation.id not in citation_map:
                    citation_map[citation.id] = citation_index
                    footnotes.append(self._format_footnote(citation, citation_index))
                    citation_index += 1
                segment["citation_refs"].append(citation_map[citation.id])
            segment["support_strength"] = self.SUPPORT_DISPLAY[claim.support_strength]
            annotated_segments.append(segment)

        return {
            "format": "inline_citations",
            "segments": annotated_segments,
            "footnotes": footnotes,
            "total_sources": len(citation_map),
        }

    def format_sidebar(self, citations: list[Citation]) -> dict[str, Any]:
        """Format citations as a sidebar panel with grouped sources."""
        grouped = self._group_by_authority(citations)
        sections = []
        for authority, cites in grouped.items():
            display = self.AUTHORITY_DISPLAY[authority]
            sections.append({
                "header": display["label"],
                "icon": display["icon"],
                "sources": [
                    {
                        "title": c.title,
                        "url": c.url,
                        "snippet": c.snippet[:200],
                        "date": c.date,
                        "relevance": self._relevance_label(c.relevance_score),
                    }
                    for c in sorted(cites, key=lambda x: -x.relevance_score)
                ],
            })
        return {"format": "sidebar", "sections": sections}

    def format_expandable(self, claim: CitedClaim) -> dict[str, Any]:
        """Format a single claim with expandable source details."""
        return {
            "format": "expandable",
            "claim": claim.claim_text,
            "support_badge": self.SUPPORT_DISPLAY[claim.support_strength],
            "sources_summary": f"{len(claim.citations)} source(s)",
            "expanded_content": [
                {
                    "title": c.title,
                    "url": c.url,
                    "highlighted_text": c.highlighted_text,
                    "author": c.author,
                    "date": c.date,
                    "authority": self.AUTHORITY_DISPLAY[c.authority_level],
                }
                for c in claim.citations
            ],
        }

    def _format_footnote(self, citation: Citation, index: int) -> dict[str, Any]:
        return {
            "index": index,
            "title": citation.title,
            "url": citation.url,
            "author": citation.author,
            "date": citation.date,
            "type": citation.source_type,
            "authority": self.AUTHORITY_DISPLAY[citation.authority_level],
        }

    def _group_by_authority(self, citations: list[Citation]) -> dict[str, list[Citation]]:
        grouped: dict[str, list[Citation]] = {"high": [], "medium": [], "low": []}
        for c in citations:
            grouped.setdefault(c.authority_level, []).append(c)
        return {k: v for k, v in grouped.items() if v}

    def _relevance_label(self, score: float) -> str:
        if score >= 0.8:
            return "Highly relevant"
        elif score >= 0.5:
            return "Relevant"
        else:
            return "Tangentially related"


# =============================================================================
# UNCERTAINTY COMMUNICATOR
# =============================================================================

@dataclass
class UncertaintyContext:
    """Context about why uncertainty exists."""
    uncertainty_type: str  # epistemic, aleatoric, model, input, temporal
    confidence_score: float
    source_count: int = 0
    sources_agree: bool = True
    knowledge_cutoff: Optional[str] = None
    query_ambiguity: float = 0.0  # 0 = clear, 1 = very ambiguous
    task_complexity: float = 0.0  # 0 = simple, 1 = very complex


class UncertaintyCommunicator:
    """
    Generates appropriate uncertainty language and caveats.
    
    Adapts language based on:
    - Type of uncertainty
    - User expertise level
    - Communication context (chat, report, notification)
    """

    UNCERTAINTY_TEMPLATES = {
        "epistemic": {
            "high_uncertainty": "I don't have enough information about this topic to give a reliable answer.",
            "medium_uncertainty": "My knowledge on this specific topic is limited. Here's what I found, but please verify.",
            "suggestion": "You might want to check {source_suggestion} for more authoritative information.",
        },
        "aleatoric": {
            "high_uncertainty": "This outcome is inherently unpredictable — there's genuine randomness involved.",
            "medium_uncertainty": "There's natural variability here, so the actual outcome may differ.",
            "suggestion": "Consider the range of possible outcomes rather than a single prediction.",
        },
        "temporal": {
            "high_uncertainty": "My information may be significantly outdated. This topic changes rapidly.",
            "medium_uncertainty": "This was accurate as of {cutoff}, but may have changed since.",
            "suggestion": "Check {source_suggestion} for the most current information.",
        },
        "input": {
            "high_uncertainty": "Your question could be interpreted multiple ways. I'll answer based on my best interpretation.",
            "medium_uncertainty": "I'm making some assumptions about what you're asking. Let me know if I misunderstood.",
            "suggestion": "Could you clarify whether you mean {alternatives}?",
        },
        "model": {
            "high_uncertainty": "This type of question is at the edge of my capabilities.",
            "medium_uncertainty": "I can attempt this, but it's not my strongest area.",
            "suggestion": "A human expert in {domain} would give you a more reliable answer.",
        },
    }

    def generate_caveat(self, context: UncertaintyContext) -> dict[str, Any]:
        """Generate an appropriate caveat for the given uncertainty context."""
        templates = self.UNCERTAINTY_TEMPLATES.get(context.uncertainty_type, {})
        severity = "high_uncertainty" if context.confidence_score < 0.4 else "medium_uncertainty"
        
        caveat_text = templates.get(severity, "I'm not fully certain about this answer.")
        
        # Add source-specific context
        additional_notes = []
        if context.source_count == 0:
            additional_notes.append("I couldn't find any sources to verify this.")
        elif not context.sources_agree:
            additional_notes.append("The sources I found provide conflicting information.")
        
        if context.query_ambiguity > 0.7:
            additional_notes.append("Your question has multiple possible interpretations.")
        
        return {
            "caveat": caveat_text,
            "additional_notes": additional_notes,
            "suggestion": templates.get("suggestion", ""),
            "severity": severity,
            "show_alternatives": context.confidence_score < 0.6,
            "recommend_verification": context.confidence_score < 0.8,
            "recommend_escalation": context.confidence_score < 0.3,
        }

    def generate_disclaimer(self, context: UncertaintyContext) -> str:
        """Generate a single-line disclaimer for compact display."""
        if context.confidence_score >= 0.9:
            return ""
        elif context.confidence_score >= 0.7:
            return "Verify critical details before acting on this."
        elif context.confidence_score >= 0.5:
            return "Moderate uncertainty — I recommend independent verification."
        elif context.confidence_score >= 0.3:
            return "Low confidence — treat as a starting point only."
        else:
            return "I cannot reliably answer this. Please consult an authoritative source."

    def should_abstain(self, context: UncertaintyContext, risk_level: str = "medium") -> dict[str, Any]:
        """Determine if AI should abstain from answering."""
        thresholds = {
            "critical": 0.90,
            "high": 0.75,
            "medium": 0.50,
            "low": 0.30,
        }
        threshold = thresholds.get(risk_level, 0.50)
        should = context.confidence_score < threshold
        return {
            "should_abstain": should,
            "reason": f"Confidence ({context.confidence_score:.0%}) below threshold ({threshold:.0%}) for {risk_level}-risk task",
            "alternative_action": "escalate_to_human" if should else "proceed_with_caveat",
        }


# =============================================================================
# APPROVAL REQUEST BUILDER
# =============================================================================

@dataclass
class ProposedAction:
    """An action the AI wants to perform that requires approval."""
    action_id: str
    action_type: str  # send_email, delete_data, modify_config, create_record, etc.
    description: str
    target: str  # What/who is affected
    reversible: bool
    risk_level: str  # critical, high, medium, low
    parameters: dict[str, Any] = field(default_factory=dict)
    preview_data: Optional[dict[str, Any]] = None
    timeout_seconds: int = 86400  # Auto-cancel after 24h
    batch_id: Optional[str] = None  # Group related actions


class ApprovalRequestBuilder:
    """
    Builds structured approval requests for human review.
    
    Principles:
    - State WHAT will happen clearly
    - Show WHY the action was proposed
    - Indicate RISK level and reversibility
    - Provide PREVIEW of outcome
    - Offer EDIT option, not just approve/reject
    """

    RISK_DISPLAY = {
        "critical": {
            "icon": "alert-octagon",
            "color": "#ef4444",
            "label": "Critical — Irreversible impact",
            "requires_confirmation": True,
            "requires_reason": True,
        },
        "high": {
            "icon": "alert-triangle",
            "color": "#f97316",
            "label": "High risk — Difficult to reverse",
            "requires_confirmation": True,
            "requires_reason": False,
        },
        "medium": {
            "icon": "alert-circle",
            "color": "#eab308",
            "label": "Medium risk — Reversible but impactful",
            "requires_confirmation": False,
            "requires_reason": False,
        },
        "low": {
            "icon": "info",
            "color": "#3b82f6",
            "label": "Low risk — Easily reversible",
            "requires_confirmation": False,
            "requires_reason": False,
        },
    }

    def build_request(
        self,
        action: ProposedAction,
        context: str = "",
        alternatives: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Build a complete approval request UI payload."""
        risk_config = self.RISK_DISPLAY[action.risk_level]

        request = {
            "request_id": f"approval_{action.action_id}_{int(time.time())}",
            "header": {
                "title": f"Action Requires Your Approval",
                "icon": risk_config["icon"],
                "urgency": action.risk_level,
            },
            "summary": {
                "what": action.description,
                "target": action.target,
                "why": context,
                "risk": risk_config["label"],
                "reversible": action.reversible,
                "reversibility_note": "This action can be undone" if action.reversible else "This action CANNOT be undone",
            },
            "preview": self._build_preview(action),
            "actions": self._build_action_buttons(action, risk_config),
            "metadata": {
                "timeout": action.timeout_seconds,
                "timeout_action": "cancel",
                "timeout_display": self._format_timeout(action.timeout_seconds),
                "batch_id": action.batch_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        if alternatives:
            request["alternatives"] = {
                "label": "Alternative approaches",
                "options": alternatives,
            }

        return request

    def build_batch_request(self, actions: list[ProposedAction], context: str = "") -> dict[str, Any]:
        """Build a batched approval request for related actions."""
        batch_id = hashlib.sha256(
            json.dumps([a.action_id for a in actions]).encode()
        ).hexdigest()[:12]

        return {
            "request_id": f"batch_{batch_id}",
            "type": "batch_approval",
            "header": {
                "title": f"Batch Action: {len(actions)} related actions",
                "description": context,
            },
            "summary": {
                "total_actions": len(actions),
                "risk_breakdown": self._risk_breakdown(actions),
                "all_reversible": all(a.reversible for a in actions),
            },
            "actions_list": [
                {
                    "action_id": a.action_id,
                    "description": a.description,
                    "target": a.target,
                    "risk": a.risk_level,
                    "individually_selectable": True,
                }
                for a in actions
            ],
            "batch_actions": {
                "approve_all": {"label": "Approve All", "variant": "primary"},
                "reject_all": {"label": "Reject All", "variant": "danger"},
                "review_individually": {"label": "Review Each", "variant": "secondary"},
            },
        }

    def _build_preview(self, action: ProposedAction) -> Optional[dict[str, Any]]:
        if not action.preview_data:
            return None
        return {
            "type": action.action_type,
            "content": action.preview_data,
            "expandable": True,
            "label": "Preview what will happen",
        }

    def _build_action_buttons(self, action: ProposedAction, risk_config: dict) -> dict[str, Any]:
        buttons = {
            "approve": {
                "label": "Approve",
                "variant": "primary",
                "requires_confirmation": risk_config["requires_confirmation"],
                "confirmation_text": "Are you sure? This action cannot be undone." if not action.reversible else None,
            },
            "edit_first": {
                "label": "Edit First",
                "variant": "secondary",
                "enabled": action.preview_data is not None,
            },
            "reject": {
                "label": "Reject",
                "variant": "danger-outline",
                "requires_reason": risk_config["requires_reason"],
            },
            "defer": {
                "label": "Decide Later",
                "variant": "ghost",
            },
        }
        return buttons

    def _risk_breakdown(self, actions: list[ProposedAction]) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for a in actions:
            breakdown[a.risk_level] = breakdown.get(a.risk_level, 0) + 1
        return breakdown

    def _format_timeout(self, seconds: int) -> str:
        if seconds >= 86400:
            days = seconds // 86400
            return f"Auto-cancels in {days} day(s) if no response"
        elif seconds >= 3600:
            hours = seconds // 3600
            return f"Auto-cancels in {hours} hour(s) if no response"
        else:
            minutes = seconds // 60
            return f"Auto-cancels in {minutes} minute(s) if no response"


# =============================================================================
# ACTION PREVIEW GENERATOR
# =============================================================================

class ActionPreviewGenerator:
    """
    Generates previews showing users what will happen before execution.
    
    Supports:
    - Email previews
    - Data modification diffs
    - API call summaries
    - File change previews
    """

    def generate_preview(self, action_type: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Generate a preview for the given action type."""
        generators = {
            "send_email": self._preview_email,
            "modify_data": self._preview_data_change,
            "api_call": self._preview_api_call,
            "file_change": self._preview_file_change,
            "notification": self._preview_notification,
        }
        generator = generators.get(action_type, self._preview_generic)
        return generator(parameters)

    def _preview_email(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "preview_type": "email",
            "rendered": {
                "to": params.get("recipients", []),
                "cc": params.get("cc", []),
                "subject": params.get("subject", ""),
                "body_preview": params.get("body", "")[:500],
                "attachments": params.get("attachments", []),
                "recipient_count": len(params.get("recipients", [])),
            },
            "warnings": self._email_warnings(params),
        }

    def _preview_data_change(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "preview_type": "diff",
            "changes": [
                {
                    "field": change.get("field"),
                    "old_value": change.get("old"),
                    "new_value": change.get("new"),
                    "type": "modify" if change.get("old") else "add",
                }
                for change in params.get("changes", [])
            ],
            "affected_records": params.get("record_count", 1),
            "table": params.get("table", "unknown"),
        }

    def _preview_api_call(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "preview_type": "api_call",
            "method": params.get("method", "GET"),
            "endpoint": params.get("endpoint", ""),
            "body_summary": str(params.get("body", ""))[:200],
            "expected_effect": params.get("effect_description", ""),
        }

    def _preview_file_change(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "preview_type": "file_diff",
            "file_path": params.get("path", ""),
            "operation": params.get("operation", "modify"),  # create, modify, delete
            "diff_lines": params.get("diff", []),
            "size_change": params.get("size_change", 0),
        }

    def _preview_notification(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "preview_type": "notification",
            "channel": params.get("channel", ""),
            "recipients": params.get("recipients", []),
            "message": params.get("message", "")[:300],
        }

    def _preview_generic(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "preview_type": "generic",
            "description": params.get("description", "Action will be performed"),
            "parameters": {k: str(v)[:100] for k, v in params.items()},
        }

    def _email_warnings(self, params: dict[str, Any]) -> list[str]:
        warnings = []
        recipients = params.get("recipients", [])
        if len(recipients) > 50:
            warnings.append(f"This will be sent to {len(recipients)} recipients")
        if params.get("contains_pii"):
            warnings.append("Email body contains personally identifiable information")
        if not params.get("subject"):
            warnings.append("No subject line specified")
        return warnings


# =============================================================================
# FEEDBACK COLLECTOR
# =============================================================================

class FeedbackType(Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CORRECTION = "correction"
    REPORT = "report"
    RATING = "rating"
    FREE_TEXT = "free_text"


@dataclass
class FeedbackItem:
    """A single piece of user feedback."""
    feedback_id: str
    response_id: str
    user_id: str
    feedback_type: FeedbackType
    timestamp: datetime
    value: Any  # bool for thumbs, str for correction, int for rating, etc.
    category: Optional[str] = None  # quality, relevance, safety, ux
    free_text: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)


class FeedbackCollector:
    """
    Collects user feedback with minimal friction.
    
    Design principles:
    - 1 click for basic signal (thumbs up/down)
    - Optional depth (explain why, suggest correction)
    - Never interrupt the user's flow
    - Acknowledge briefly
    """

    REPORT_CATEGORIES = [
        {"id": "incorrect", "label": "Incorrect information", "icon": "x-circle"},
        {"id": "outdated", "label": "Outdated information", "icon": "clock"},
        {"id": "harmful", "label": "Harmful or unsafe", "icon": "alert-octagon"},
        {"id": "irrelevant", "label": "Not relevant to my question", "icon": "target"},
        {"id": "incomplete", "label": "Missing important information", "icon": "list"},
        {"id": "unclear", "label": "Confusing or unclear", "icon": "help-circle"},
    ]

    def build_feedback_ui(self, response_id: str, context: str = "chat") -> dict[str, Any]:
        """Build the feedback UI component for a given response."""
        return {
            "response_id": response_id,
            "context": context,
            "primary_actions": {
                "thumbs_up": {"icon": "thumb-up", "label": "Helpful", "aria_label": "Mark as helpful"},
                "thumbs_down": {"icon": "thumb-down", "label": "Not helpful", "aria_label": "Mark as not helpful"},
            },
            "secondary_actions": {
                "copy": {"icon": "copy", "label": "Copy"},
                "report": {"icon": "flag", "label": "Report issue"},
                "suggest_edit": {"icon": "edit", "label": "Suggest correction"},
            },
            "expanded_feedback": {
                "triggered_by": "thumbs_down",
                "options": self.REPORT_CATEGORIES,
                "free_text": {
                    "placeholder": "What would a better answer look like? (optional)",
                    "max_length": 1000,
                },
            },
            "acknowledgment": {
                "thumbs_up": "Thanks for the feedback!",
                "thumbs_down": "Thanks — this helps us improve.",
                "report": "Reported. We'll review this.",
                "correction": "Thanks for the correction!",
            },
        }

    def process_feedback(self, feedback: FeedbackItem) -> dict[str, Any]:
        """Process and store a feedback item."""
        # Validate
        if feedback.feedback_type == FeedbackType.RATING:
            if not isinstance(feedback.value, int) or not (1 <= feedback.value <= 5):
                return {"success": False, "error": "Rating must be 1-5"}

        # Categorize if not provided
        if not feedback.category:
            feedback.category = self._auto_categorize(feedback)

        # Determine if this needs immediate attention
        priority = self._assess_priority(feedback)

        return {
            "success": True,
            "feedback_id": feedback.feedback_id,
            "category": feedback.category,
            "priority": priority,
            "acknowledgment": self._get_acknowledgment(feedback),
            "follow_up": self._suggest_follow_up(feedback),
        }

    def _auto_categorize(self, feedback: FeedbackItem) -> str:
        if feedback.feedback_type == FeedbackType.REPORT:
            return "safety"
        elif feedback.feedback_type == FeedbackType.CORRECTION:
            return "quality"
        elif feedback.feedback_type == FeedbackType.THUMBS_DOWN:
            return "relevance"
        return "general"

    def _assess_priority(self, feedback: FeedbackItem) -> str:
        if feedback.feedback_type == FeedbackType.REPORT and feedback.category == "harmful":
            return "urgent"
        elif feedback.feedback_type == FeedbackType.REPORT:
            return "high"
        elif feedback.feedback_type == FeedbackType.CORRECTION:
            return "medium"
        return "low"

    def _get_acknowledgment(self, feedback: FeedbackItem) -> str:
        acks = {
            FeedbackType.THUMBS_UP: "Thanks for the feedback!",
            FeedbackType.THUMBS_DOWN: "Thanks — this helps us improve.",
            FeedbackType.CORRECTION: "Thanks for the correction! We'll review it.",
            FeedbackType.REPORT: "Reported. Our team will review this.",
            FeedbackType.RATING: "Thanks for rating!",
            FeedbackType.FREE_TEXT: "Thanks for your detailed feedback!",
        }
        return acks.get(feedback.feedback_type, "Feedback received.")

    def _suggest_follow_up(self, feedback: FeedbackItem) -> Optional[dict[str, Any]]:
        if feedback.feedback_type == FeedbackType.THUMBS_DOWN:
            return {
                "prompt": "Would you like to tell us what went wrong?",
                "options": self.REPORT_CATEGORIES[:4],
                "dismissible": True,
            }
        return None


# =============================================================================
# ESCALATION HANDLER
# =============================================================================

@dataclass
class EscalationContext:
    """Context for escalating to a human."""
    reason: str
    confidence_score: float
    conversation_summary: str
    partial_answer: Optional[str] = None
    actions_taken: list[str] = field(default_factory=list)
    relevant_sources: list[str] = field(default_factory=list)
    user_frustration_signals: int = 0  # count of negative signals


class EscalationHandler:
    """
    Manages smooth handoff from AI to human agents.
    
    Principles:
    - Explain WHY escalating
    - Share context so human doesn't re-ask
    - Show partial work
    - Set expectations (wait time)
    - Offer async alternative
    """

    ESCALATION_REASONS = {
        "low_confidence": "I'm not confident enough to help reliably with this",
        "user_request": "You've asked to speak with a human",
        "capability_limit": "This requires capabilities beyond what I can provide",
        "safety_concern": "This topic requires human judgment for safety reasons",
        "repeated_failures": "I haven't been able to help effectively after multiple attempts",
        "regulatory": "Regulations require human oversight for this type of decision",
        "complex_judgment": "This requires nuanced judgment that's best handled by a specialist",
    }

    def build_escalation(
        self,
        context: EscalationContext,
        estimated_wait_minutes: Optional[int] = None,
        available_channels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Build an escalation UI with full context."""
        return {
            "type": "escalation",
            "header": {
                "title": "Connecting you with a human specialist",
                "icon": "user-switch",
            },
            "reason": {
                "explanation": self.ESCALATION_REASONS.get(context.reason, context.reason),
                "ai_confidence": f"{context.confidence_score:.0%}",
            },
            "context_shared": {
                "label": "Context being shared with the specialist",
                "items": [
                    {"type": "summary", "content": context.conversation_summary},
                    *([{"type": "partial_answer", "content": context.partial_answer}] if context.partial_answer else []),
                    *[{"type": "action_taken", "content": a} for a in context.actions_taken],
                    *[{"type": "source", "content": s} for s in context.relevant_sources[:5]],
                ],
                "editable": True,  # User can remove context before sharing
            },
            "expectations": {
                "estimated_wait": f"~{estimated_wait_minutes} minutes" if estimated_wait_minutes else "Unknown",
                "channels": available_channels or ["live_chat"],
            },
            "actions": {
                "continue_waiting": {"label": "Continue waiting", "variant": "primary"},
                "leave_message": {"label": "Leave a message instead", "variant": "secondary"},
                "cancel": {"label": "Cancel — I'll figure it out", "variant": "ghost"},
            },
            "while_waiting": {
                "partial_answer": context.partial_answer,
                "helpful_links": context.relevant_sources[:3],
                "message": "While you wait, here's what I was able to find:",
            },
        }

    def should_escalate(self, context: EscalationContext) -> dict[str, Any]:
        """Determine if escalation is appropriate."""
        reasons = []
        if context.confidence_score < 0.3:
            reasons.append("low_confidence")
        if context.user_frustration_signals >= 3:
            reasons.append("repeated_failures")
        
        return {
            "should_escalate": len(reasons) > 0,
            "reasons": reasons,
            "urgency": "high" if context.user_frustration_signals >= 3 else "normal",
        }


# =============================================================================
# ERROR MESSAGE COMPOSER
# =============================================================================

class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context about an error that occurred."""
    error_type: str  # transient, input, capacity, logic, system
    error_code: Optional[str] = None
    user_action: str = ""  # What user was trying to do
    technical_details: str = ""
    is_retryable: bool = False
    retry_after_seconds: Optional[int] = None
    data_preserved: bool = True
    partial_result: Optional[Any] = None


class ErrorMessageComposer:
    """
    Composes helpful, actionable error messages.
    
    Formula: [What happened] + [Impact on you] + [What you can do] + [What we're doing]
    
    Anti-patterns avoided:
    - Raw error codes shown to users
    - Blaming the user
    - Technical jargon without explanation
    - No actionable next steps
    """

    ERROR_TEMPLATES = {
        "transient": {
            "title": "Temporary issue",
            "icon": "refresh-cw",
            "color": "#eab308",
        },
        "input": {
            "title": "Let me help you fix that",
            "icon": "edit-3",
            "color": "#3b82f6",
        },
        "capacity": {
            "title": "System is busy",
            "icon": "clock",
            "color": "#eab308",
        },
        "logic": {
            "title": "Something went wrong",
            "icon": "alert-circle",
            "color": "#f97316",
        },
        "system": {
            "title": "Service disruption",
            "icon": "alert-triangle",
            "color": "#ef4444",
        },
    }

    def compose(self, context: ErrorContext) -> dict[str, Any]:
        """Compose a user-friendly error message."""
        template = self.ERROR_TEMPLATES.get(context.error_type, self.ERROR_TEMPLATES["logic"])

        message = {
            "type": "error",
            "severity": self._determine_severity(context),
            "header": {
                "title": template["title"],
                "icon": template["icon"],
                "color": template["color"],
            },
            "body": {
                "what_happened": self._explain_what_happened(context),
                "impact": self._explain_impact(context),
                "next_steps": self._suggest_next_steps(context),
                "our_action": self._explain_our_action(context),
            },
            "data_status": {
                "preserved": context.data_preserved,
                "message": "Your work has been saved." if context.data_preserved else "Some data may not have been saved.",
            },
            "actions": self._build_error_actions(context),
        }

        if context.partial_result:
            message["partial_result"] = {
                "label": "Partial results (before the error)",
                "content": context.partial_result,
            }

        return message

    def _determine_severity(self, context: ErrorContext) -> str:
        if context.error_type == "system":
            return ErrorSeverity.CRITICAL.value
        elif context.error_type in ("logic", "capacity"):
            return ErrorSeverity.ERROR.value
        elif context.error_type == "transient":
            return ErrorSeverity.WARNING.value
        return ErrorSeverity.INFO.value

    def _explain_what_happened(self, context: ErrorContext) -> str:
        explanations = {
            "transient": f"The request failed due to a temporary network or service issue.",
            "input": f"There's an issue with the input provided.",
            "capacity": f"The system is experiencing high demand right now.",
            "logic": f"An unexpected error occurred while processing your request.",
            "system": f"One of our services is currently unavailable.",
        }
        return explanations.get(context.error_type, "An unexpected error occurred.")

    def _explain_impact(self, context: ErrorContext) -> str:
        if context.data_preserved:
            return f"Your {context.user_action or 'request'} couldn't be completed, but your data is safe."
        return f"Your {context.user_action or 'request'} couldn't be completed and some changes may be lost."

    def _suggest_next_steps(self, context: ErrorContext) -> list[str]:
        steps = []
        if context.is_retryable:
            if context.retry_after_seconds:
                steps.append(f"Try again in {context.retry_after_seconds} seconds")
            else:
                steps.append("Try again")
        if context.error_type == "input":
            steps.append("Check your input and try rephrasing")
        if context.error_type == "capacity":
            steps.append("Wait a few minutes and try again")
        steps.append("If this persists, contact support")
        return steps

    def _explain_our_action(self, context: ErrorContext) -> Optional[str]:
        if context.error_type == "system":
            return "Our team has been notified and is working on a fix."
        elif context.error_type == "transient" and context.is_retryable:
            return "We'll automatically retry in the background."
        return None

    def _build_error_actions(self, context: ErrorContext) -> dict[str, Any]:
        actions = {}
        if context.is_retryable:
            actions["retry"] = {"label": "Try Again", "variant": "primary"}
        actions["help"] = {"label": "Get Help", "variant": "secondary"}
        if context.technical_details:
            actions["details"] = {"label": "Technical Details", "variant": "ghost", "expandable": True}
        return actions


# =============================================================================
# AUDIT TRAIL VIEWER
# =============================================================================

@dataclass
class AuditEvent:
    """A single event in the audit trail."""
    event_id: str
    timestamp: datetime
    event_type: str  # received, searched, retrieved, generated, verified, delivered, error
    description: str
    details: Optional[dict[str, Any]] = None
    duration_ms: Optional[int] = None
    confidence: Optional[float] = None
    actor: str = "ai"  # ai, user, system


class AuditTrailViewer:
    """
    Presents audit trail information at appropriate detail levels.
    
    Supports:
    - Summary view (end users)
    - Detailed view (power users)
    - Full trace (admins)
    - Export for compliance
    """

    EVENT_ICONS = {
        "received": "inbox",
        "searched": "search",
        "retrieved": "download",
        "generated": "cpu",
        "verified": "shield-check",
        "delivered": "send",
        "error": "alert-circle",
        "approved": "check-circle",
        "rejected": "x-circle",
        "escalated": "arrow-up-right",
    }

    def format_summary(self, events: list[AuditEvent]) -> dict[str, Any]:
        """Format audit trail for end-user summary view."""
        key_events = [e for e in events if e.event_type in ("received", "searched", "generated", "delivered", "error")]
        
        return {
            "view": "summary",
            "title": "What I did",
            "timeline": [
                {
                    "time": e.timestamp.strftime("%H:%M:%S"),
                    "icon": self.EVENT_ICONS.get(e.event_type, "circle"),
                    "description": e.description,
                }
                for e in key_events
            ],
            "total_duration_ms": self._total_duration(events),
            "sources_consulted": sum(1 for e in events if e.event_type == "retrieved"),
        }

    def format_detailed(self, events: list[AuditEvent]) -> dict[str, Any]:
        """Format audit trail for power-user detailed view."""
        return {
            "view": "detailed",
            "title": "Processing Details",
            "timeline": [
                {
                    "time": e.timestamp.strftime("%H:%M:%S.%f")[:-3],
                    "icon": self.EVENT_ICONS.get(e.event_type, "circle"),
                    "type": e.event_type,
                    "description": e.description,
                    "duration_ms": e.duration_ms,
                    "details": e.details,
                    "confidence": e.confidence,
                    "actor": e.actor,
                }
                for e in events
            ],
            "statistics": {
                "total_events": len(events),
                "total_duration_ms": self._total_duration(events),
                "errors": sum(1 for e in events if e.event_type == "error"),
                "sources_consulted": sum(1 for e in events if e.event_type == "retrieved"),
            },
        }

    def format_export(self, events: list[AuditEvent]) -> dict[str, Any]:
        """Format audit trail for compliance export."""
        return {
            "export_format": "audit_log_v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "event_count": len(events),
            "events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "actor": e.actor,
                    "description": e.description,
                    "details": e.details,
                    "duration_ms": e.duration_ms,
                    "integrity_hash": self._hash_event(e),
                }
                for e in events
            ],
        }

    def _total_duration(self, events: list[AuditEvent]) -> int:
        if len(events) < 2:
            return 0
        first = events[0].timestamp
        last = events[-1].timestamp
        return int((last - first).total_seconds() * 1000)

    def _hash_event(self, event: AuditEvent) -> str:
        content = f"{event.event_id}:{event.timestamp.isoformat()}:{event.event_type}:{event.description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# INTEGRATION EXAMPLE
# =============================================================================

def example_usage():
    """Demonstrate how all components work together in a typical AI response flow."""

    # 1. AI generates a response with confidence
    confidence_formatter = ConfidenceDisplayFormatter()
    metadata = ConfidenceMetadata(
        score=0.72,
        level=confidence_formatter.classify(0.72),
        factors=[
            ConfidenceFactor("source_agreement", "increases", 0.3, "Multiple sources confirm key facts"),
            ConfidenceFactor("recency", "decreases", 0.2, "Information may be outdated (6+ months old)"),
        ],
    )
    chat_display = confidence_formatter.format_for_chat(metadata)
    print("Confidence Display:", json.dumps(chat_display, indent=2))

    # 2. Present citations
    presenter = CitationPresenter()
    citations = [
        Citation(
            id="src_1",
            title="Official Python Docs",
            url="https://docs.python.org/3/",
            relevance_score=0.95,
            authority_level="high",
            snippet="Python is a programming language...",
        ),
    ]
    sidebar = presenter.format_sidebar(citations)
    print("\nCitation Sidebar:", json.dumps(sidebar, indent=2))

    # 3. Generate uncertainty caveat
    communicator = UncertaintyCommunicator()
    uncertainty = UncertaintyContext(
        uncertainty_type="temporal",
        confidence_score=0.72,
        source_count=3,
        sources_agree=True,
        knowledge_cutoff="2024-01",
    )
    caveat = communicator.generate_caveat(uncertainty)
    print("\nUncertainty Caveat:", json.dumps(caveat, indent=2))

    # 4. Request approval for an action
    builder = ApprovalRequestBuilder()
    action = ProposedAction(
        action_id="act_123",
        action_type="send_email",
        description="Send quarterly report to all team leads",
        target="15 team leads",
        reversible=False,
        risk_level="high",
        preview_data={"subject": "Q4 Report", "body": "Hi team..."},
    )
    approval = builder.build_request(action, context="User requested campaign launch")
    print("\nApproval Request:", json.dumps(approval, indent=2, default=str))


if __name__ == "__main__":
    example_usage()
