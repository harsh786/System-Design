"""
User Feedback Management System
================================
Production-grade system for collecting, categorizing, analyzing, and acting on user feedback.
"""

from __future__ import annotations

import json
import hashlib
import statistics
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict


# =============================================================================
# FEEDBACK COLLECTION API
# =============================================================================

class FeedbackSignal(Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING_1 = "rating_1"
    RATING_2 = "rating_2"
    RATING_3 = "rating_3"
    RATING_4 = "rating_4"
    RATING_5 = "rating_5"
    CORRECTION = "correction"
    REPORT_INCORRECT = "report_incorrect"
    REPORT_HARMFUL = "report_harmful"
    REPORT_IRRELEVANT = "report_irrelevant"
    REPORT_OUTDATED = "report_outdated"
    FREE_TEXT = "free_text"
    IMPLICIT_COPY = "implicit_copy"
    IMPLICIT_IGNORE = "implicit_ignore"
    IMPLICIT_RETRY = "implicit_retry"
    IMPLICIT_EDIT = "implicit_edit"


class FeedbackCategory(Enum):
    QUALITY = "quality"         # Accuracy, completeness, correctness
    RELEVANCE = "relevance"     # Did it answer the actual question
    SAFETY = "safety"           # Harmful, biased, inappropriate
    UX = "ux"                   # Formatting, tone, clarity
    LATENCY = "latency"        # Too slow
    CITATION = "citation"      # Sources quality
    CONFIDENCE = "confidence"  # Confidence was miscalibrated


@dataclass
class FeedbackRecord:
    """Complete feedback record with all metadata."""
    feedback_id: str
    timestamp: datetime
    user_id: str
    session_id: str
    response_id: str
    signal: FeedbackSignal
    category: Optional[FeedbackCategory] = None
    free_text: Optional[str] = None
    correction_text: Optional[str] = None
    original_response: Optional[str] = None
    query: Optional[str] = None
    model_version: Optional[str] = None
    confidence_score: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    action_taken: Optional[str] = None


class FeedbackCollectionAPI:
    """
    API for collecting all types of user feedback.
    
    Supports:
    - Explicit feedback (ratings, corrections, reports)
    - Implicit feedback (copy, ignore, retry, edit behavior)
    - Contextual metadata collection
    - Rate limiting and spam prevention
    """

    def __init__(self):
        self._records: list[FeedbackRecord] = []
        self._rate_limits: dict[str, list[datetime]] = defaultdict(list)
        self.MAX_FEEDBACK_PER_MINUTE = 10

    def submit_thumbs(
        self,
        user_id: str,
        session_id: str,
        response_id: str,
        is_positive: bool,
        query: Optional[str] = None,
        response_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """Submit a thumbs up/down signal."""
        if not self._check_rate_limit(user_id):
            return {"success": False, "error": "Rate limit exceeded. Please try again later."}

        signal = FeedbackSignal.THUMBS_UP if is_positive else FeedbackSignal.THUMBS_DOWN
        record = FeedbackRecord(
            feedback_id=self._generate_id(user_id, response_id, signal.value),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            response_id=response_id,
            signal=signal,
            query=query,
            original_response=response_text,
        )
        self._records.append(record)
        return {
            "success": True,
            "feedback_id": record.feedback_id,
            "acknowledgment": "Thanks for the feedback!" if is_positive else "Thanks — this helps us improve.",
            "follow_up": None if is_positive else {
                "prompt": "Would you like to tell us what went wrong?",
                "options": ["incorrect", "irrelevant", "outdated", "unclear", "harmful"],
            },
        }

    def submit_rating(
        self,
        user_id: str,
        session_id: str,
        response_id: str,
        rating: int,  # 1-5
        dimensions: Optional[dict[str, int]] = None,  # e.g., {"accuracy": 4, "helpfulness": 3}
    ) -> dict[str, Any]:
        """Submit a numeric rating (1-5) with optional dimensional ratings."""
        if not 1 <= rating <= 5:
            return {"success": False, "error": "Rating must be between 1 and 5"}

        signal = FeedbackSignal[f"RATING_{rating}"]
        record = FeedbackRecord(
            feedback_id=self._generate_id(user_id, response_id, "rating"),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            response_id=response_id,
            signal=signal,
            metadata={"rating": rating, "dimensions": dimensions or {}},
        )
        self._records.append(record)
        return {"success": True, "feedback_id": record.feedback_id}

    def submit_correction(
        self,
        user_id: str,
        session_id: str,
        response_id: str,
        original_text: str,
        corrected_text: str,
        correction_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Submit a user correction (edited AI output)."""
        record = FeedbackRecord(
            feedback_id=self._generate_id(user_id, response_id, "correction"),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            response_id=response_id,
            signal=FeedbackSignal.CORRECTION,
            category=FeedbackCategory.QUALITY,
            original_response=original_text,
            correction_text=corrected_text,
            metadata={"reason": correction_reason, "edit_distance": self._edit_distance(original_text, corrected_text)},
        )
        self._records.append(record)
        return {
            "success": True,
            "feedback_id": record.feedback_id,
            "acknowledgment": "Thanks for the correction! This helps us improve accuracy.",
        }

    def submit_report(
        self,
        user_id: str,
        session_id: str,
        response_id: str,
        report_category: str,
        details: Optional[str] = None,
        response_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """Submit a content report (incorrect, harmful, etc.)."""
        signal_map = {
            "incorrect": FeedbackSignal.REPORT_INCORRECT,
            "harmful": FeedbackSignal.REPORT_HARMFUL,
            "irrelevant": FeedbackSignal.REPORT_IRRELEVANT,
            "outdated": FeedbackSignal.REPORT_OUTDATED,
        }
        signal = signal_map.get(report_category, FeedbackSignal.REPORT_INCORRECT)
        
        category_map = {
            "incorrect": FeedbackCategory.QUALITY,
            "harmful": FeedbackCategory.SAFETY,
            "irrelevant": FeedbackCategory.RELEVANCE,
            "outdated": FeedbackCategory.QUALITY,
        }

        record = FeedbackRecord(
            feedback_id=self._generate_id(user_id, response_id, f"report_{report_category}"),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            response_id=response_id,
            signal=signal,
            category=category_map.get(report_category, FeedbackCategory.QUALITY),
            free_text=details,
            original_response=response_text,
        )
        self._records.append(record)

        priority = "urgent" if report_category == "harmful" else "normal"
        return {
            "success": True,
            "feedback_id": record.feedback_id,
            "priority": priority,
            "acknowledgment": "Reported. Our team will review this.",
        }

    def submit_implicit(
        self,
        user_id: str,
        session_id: str,
        response_id: str,
        behavior: str,  # copy, ignore, retry, edit
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Record implicit feedback from user behavior."""
        signal_map = {
            "copy": FeedbackSignal.IMPLICIT_COPY,
            "ignore": FeedbackSignal.IMPLICIT_IGNORE,
            "retry": FeedbackSignal.IMPLICIT_RETRY,
            "edit": FeedbackSignal.IMPLICIT_EDIT,
        }
        signal = signal_map.get(behavior, FeedbackSignal.IMPLICIT_IGNORE)

        record = FeedbackRecord(
            feedback_id=self._generate_id(user_id, response_id, f"implicit_{behavior}"),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            response_id=response_id,
            signal=signal,
            metadata=metadata or {},
        )
        self._records.append(record)
        return {"success": True, "feedback_id": record.feedback_id}

    def _check_rate_limit(self, user_id: str) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=1)
        self._rate_limits[user_id] = [t for t in self._rate_limits[user_id] if t > cutoff]
        if len(self._rate_limits[user_id]) >= self.MAX_FEEDBACK_PER_MINUTE:
            return False
        self._rate_limits[user_id].append(now)
        return True

    def _generate_id(self, user_id: str, response_id: str, signal: str) -> str:
        content = f"{user_id}:{response_id}:{signal}:{datetime.now(timezone.utc).isoformat()}"
        return f"fb_{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    def _edit_distance(self, a: str, b: str) -> int:
        """Simple character-level edit distance (Levenshtein)."""
        if len(a) > 1000 or len(b) > 1000:
            return abs(len(a) - len(b))  # Approximate for long texts
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                temp = dp[j]
                if a[i-1] == b[j-1]:
                    dp[j] = prev
                else:
                    dp[j] = 1 + min(dp[j], dp[j-1], prev)
                prev = temp
        return dp[n]


# =============================================================================
# FEEDBACK CATEGORIZATION
# =============================================================================

class FeedbackCategorizer:
    """
    Automatically categorizes feedback into actionable categories.
    
    Categories:
    - Quality: accuracy, completeness, correctness
    - Relevance: answered the right question
    - Safety: harmful, biased, inappropriate content
    - UX: formatting, tone, clarity, presentation
    - Latency: performance issues
    - Citation: source quality issues
    - Confidence: calibration issues
    """

    KEYWORD_CATEGORIES = {
        FeedbackCategory.QUALITY: [
            "wrong", "incorrect", "inaccurate", "outdated", "error", "mistake",
            "false", "not true", "incomplete", "missing",
        ],
        FeedbackCategory.RELEVANCE: [
            "irrelevant", "off-topic", "didn't answer", "not what I asked",
            "unrelated", "different question", "misunderstood",
        ],
        FeedbackCategory.SAFETY: [
            "harmful", "offensive", "biased", "inappropriate", "dangerous",
            "racist", "sexist", "toxic", "unsafe",
        ],
        FeedbackCategory.UX: [
            "confusing", "unclear", "too long", "too short", "formatting",
            "hard to read", "tone", "verbose", "terse",
        ],
        FeedbackCategory.LATENCY: [
            "slow", "took too long", "timeout", "waiting", "performance",
        ],
        FeedbackCategory.CITATION: [
            "source", "citation", "reference", "link broken", "no sources",
            "unreliable source",
        ],
        FeedbackCategory.CONFIDENCE: [
            "overconfident", "too certain", "should have said unsure",
            "wrong confidence", "claimed to know",
        ],
    }

    def categorize(self, record: FeedbackRecord) -> FeedbackCategory:
        """Categorize a feedback record."""
        # If explicitly categorized, use that
        if record.category:
            return record.category

        # Signal-based categorization
        signal_categories = {
            FeedbackSignal.REPORT_HARMFUL: FeedbackCategory.SAFETY,
            FeedbackSignal.REPORT_INCORRECT: FeedbackCategory.QUALITY,
            FeedbackSignal.REPORT_IRRELEVANT: FeedbackCategory.RELEVANCE,
            FeedbackSignal.REPORT_OUTDATED: FeedbackCategory.QUALITY,
            FeedbackSignal.CORRECTION: FeedbackCategory.QUALITY,
        }
        if record.signal in signal_categories:
            return signal_categories[record.signal]

        # Text-based categorization
        text = (record.free_text or "") + " " + (record.correction_text or "")
        if text.strip():
            return self._categorize_by_text(text.lower())

        return FeedbackCategory.QUALITY  # Default

    def _categorize_by_text(self, text: str) -> FeedbackCategory:
        scores: dict[FeedbackCategory, int] = {}
        for category, keywords in self.KEYWORD_CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score
        if scores:
            return max(scores, key=scores.get)
        return FeedbackCategory.QUALITY

    def categorize_batch(self, records: list[FeedbackRecord]) -> dict[FeedbackCategory, list[FeedbackRecord]]:
        """Categorize a batch of records and group by category."""
        result: dict[FeedbackCategory, list[FeedbackRecord]] = defaultdict(list)
        for record in records:
            category = self.categorize(record)
            record.category = category
            result[category].append(record)
        return dict(result)


# =============================================================================
# FEEDBACK-TO-IMPROVEMENT PIPELINE
# =============================================================================

@dataclass
class ImprovementAction:
    """A specific improvement action derived from feedback."""
    action_id: str
    action_type: str  # retrain, update_prompt, fix_retrieval, update_guardrails, ui_fix
    priority: str  # critical, high, medium, low
    description: str
    evidence_count: int  # How many feedback items support this
    estimated_impact: str  # high, medium, low
    feedback_ids: list[str] = field(default_factory=list)
    status: str = "proposed"  # proposed, approved, in_progress, completed, rejected


class FeedbackToImprovementPipeline:
    """
    Converts feedback signals into actionable improvements.
    
    Pipeline stages:
    1. Aggregate: Group related feedback
    2. Prioritize: Rank by frequency, severity, impact
    3. Diagnose: Identify root cause
    4. Propose: Generate improvement actions
    5. Track: Monitor if improvements work
    """

    SEVERITY_WEIGHTS = {
        FeedbackSignal.REPORT_HARMFUL: 10,
        FeedbackSignal.REPORT_INCORRECT: 5,
        FeedbackSignal.CORRECTION: 4,
        FeedbackSignal.THUMBS_DOWN: 2,
        FeedbackSignal.REPORT_IRRELEVANT: 3,
        FeedbackSignal.REPORT_OUTDATED: 3,
        FeedbackSignal.IMPLICIT_RETRY: 2,
        FeedbackSignal.IMPLICIT_IGNORE: 1,
    }

    def process_batch(self, records: list[FeedbackRecord]) -> list[ImprovementAction]:
        """Process a batch of feedback into improvement actions."""
        # Stage 1: Aggregate by category and pattern
        categorized = self._aggregate(records)
        
        # Stage 2: Prioritize
        prioritized = self._prioritize(categorized)
        
        # Stage 3-4: Diagnose and propose
        actions = []
        for cluster in prioritized:
            action = self._propose_action(cluster)
            if action:
                actions.append(action)
        
        return sorted(actions, key=lambda a: {"critical": 0, "high": 1, "medium": 2, "low": 3}[a.priority])

    def _aggregate(self, records: list[FeedbackRecord]) -> list[dict[str, Any]]:
        """Group related feedback items."""
        clusters: dict[str, list[FeedbackRecord]] = defaultdict(list)
        for record in records:
            # Cluster by category + signal type
            key = f"{record.category}:{record.signal.value}" if record.category else record.signal.value
            clusters[key].append(record)
        
        return [
            {
                "key": key,
                "records": recs,
                "count": len(recs),
                "severity_score": sum(self.SEVERITY_WEIGHTS.get(r.signal, 1) for r in recs),
            }
            for key, recs in clusters.items()
        ]

    def _prioritize(self, clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank clusters by importance."""
        return sorted(clusters, key=lambda c: -c["severity_score"])

    def _propose_action(self, cluster: dict[str, Any]) -> Optional[ImprovementAction]:
        """Propose an improvement action for a feedback cluster."""
        key = cluster["key"]
        count = cluster["count"]
        records = cluster["records"]

        if count < 3:  # Need minimum signal before acting
            return None

        # Determine action type based on cluster
        if "safety" in key or "harmful" in key:
            return ImprovementAction(
                action_id=f"imp_{hashlib.sha256(key.encode()).hexdigest()[:8]}",
                action_type="update_guardrails",
                priority="critical",
                description=f"Safety issue reported {count} times — update content filters",
                evidence_count=count,
                estimated_impact="high",
                feedback_ids=[r.feedback_id for r in records[:20]],
            )
        elif "quality" in key or "incorrect" in key:
            return ImprovementAction(
                action_id=f"imp_{hashlib.sha256(key.encode()).hexdigest()[:8]}",
                action_type="retrain" if count > 10 else "update_prompt",
                priority="high" if count > 10 else "medium",
                description=f"Quality issues ({count} reports) — {'retrain model' if count > 10 else 'update system prompt'}",
                evidence_count=count,
                estimated_impact="high" if count > 10 else "medium",
                feedback_ids=[r.feedback_id for r in records[:20]],
            )
        elif "relevance" in key:
            return ImprovementAction(
                action_id=f"imp_{hashlib.sha256(key.encode()).hexdigest()[:8]}",
                action_type="fix_retrieval",
                priority="medium",
                description=f"Relevance issues ({count} reports) — improve retrieval/ranking",
                evidence_count=count,
                estimated_impact="medium",
                feedback_ids=[r.feedback_id for r in records[:20]],
            )
        elif "ux" in key:
            return ImprovementAction(
                action_id=f"imp_{hashlib.sha256(key.encode()).hexdigest()[:8]}",
                action_type="ui_fix",
                priority="low",
                description=f"UX issues ({count} reports) — improve formatting/presentation",
                evidence_count=count,
                estimated_impact="low",
                feedback_ids=[r.feedback_id for r in records[:20]],
            )
        return None


# =============================================================================
# FEEDBACK ANALYTICS AND TRENDS
# =============================================================================

class FeedbackAnalytics:
    """
    Analyze feedback patterns, trends, and insights.
    """

    def compute_summary(
        self,
        records: list[FeedbackRecord],
        period_days: int = 7,
    ) -> dict[str, Any]:
        """Compute summary analytics for a given period."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=period_days)
        period_records = [r for r in records if r.timestamp >= cutoff]

        positive = sum(1 for r in period_records if r.signal == FeedbackSignal.THUMBS_UP)
        negative = sum(1 for r in period_records if r.signal == FeedbackSignal.THUMBS_DOWN)
        total_binary = positive + negative

        ratings = [
            int(r.signal.value.split("_")[1])
            for r in period_records
            if r.signal.value.startswith("rating_")
        ]

        return {
            "period": f"Last {period_days} days",
            "total_feedback": len(period_records),
            "thumbs": {
                "positive": positive,
                "negative": negative,
                "ratio": positive / total_binary if total_binary > 0 else None,
            },
            "ratings": {
                "count": len(ratings),
                "average": statistics.mean(ratings) if ratings else None,
                "median": statistics.median(ratings) if ratings else None,
                "distribution": {i: ratings.count(i) for i in range(1, 6)} if ratings else {},
            },
            "reports": {
                "total": sum(1 for r in period_records if r.signal.value.startswith("report_")),
                "safety": sum(1 for r in period_records if r.signal == FeedbackSignal.REPORT_HARMFUL),
                "quality": sum(1 for r in period_records if r.signal == FeedbackSignal.REPORT_INCORRECT),
            },
            "corrections": sum(1 for r in period_records if r.signal == FeedbackSignal.CORRECTION),
            "implicit_signals": {
                "copies": sum(1 for r in period_records if r.signal == FeedbackSignal.IMPLICIT_COPY),
                "retries": sum(1 for r in period_records if r.signal == FeedbackSignal.IMPLICIT_RETRY),
                "ignores": sum(1 for r in period_records if r.signal == FeedbackSignal.IMPLICIT_IGNORE),
            },
        }

    def compute_trends(
        self,
        records: list[FeedbackRecord],
        window_days: int = 7,
        num_windows: int = 4,
    ) -> dict[str, Any]:
        """Compute trends over multiple time windows."""
        now = datetime.now(timezone.utc)
        windows = []

        for i in range(num_windows):
            end = now - timedelta(days=i * window_days)
            start = end - timedelta(days=window_days)
            window_records = [r for r in records if start <= r.timestamp < end]

            positive = sum(1 for r in window_records if r.signal == FeedbackSignal.THUMBS_UP)
            negative = sum(1 for r in window_records if r.signal == FeedbackSignal.THUMBS_DOWN)
            total = positive + negative

            windows.append({
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "satisfaction_rate": positive / total if total > 0 else None,
                "total_feedback": len(window_records),
                "report_count": sum(1 for r in window_records if r.signal.value.startswith("report_")),
            })

        # Compute trend direction
        satisfaction_rates = [w["satisfaction_rate"] for w in windows if w["satisfaction_rate"] is not None]
        trend = "stable"
        if len(satisfaction_rates) >= 2:
            if satisfaction_rates[0] > satisfaction_rates[-1] + 0.05:
                trend = "improving"
            elif satisfaction_rates[0] < satisfaction_rates[-1] - 0.05:
                trend = "declining"

        return {
            "windows": windows,
            "trend": trend,
            "trend_description": self._describe_trend(trend, satisfaction_rates),
        }

    def identify_problem_areas(self, records: list[FeedbackRecord]) -> list[dict[str, Any]]:
        """Identify specific problem areas from feedback patterns."""
        # Group by query patterns or topics
        problems: dict[str, dict[str, Any]] = {}
        
        for record in records:
            if record.signal in (FeedbackSignal.THUMBS_DOWN, FeedbackSignal.REPORT_INCORRECT, FeedbackSignal.CORRECTION):
                category = record.category.value if record.category else "unknown"
                if category not in problems:
                    problems[category] = {"count": 0, "examples": [], "severity_total": 0}
                problems[category]["count"] += 1
                problems[category]["severity_total"] += FeedbackToImprovementPipeline.SEVERITY_WEIGHTS.get(record.signal, 1)
                if len(problems[category]["examples"]) < 5:
                    problems[category]["examples"].append({
                        "query": record.query,
                        "signal": record.signal.value,
                        "text": record.free_text,
                    })

        return sorted(
            [{"category": k, **v} for k, v in problems.items()],
            key=lambda x: -x["severity_total"],
        )

    def _describe_trend(self, trend: str, rates: list[float]) -> str:
        if trend == "improving":
            return f"Satisfaction is improving (from {rates[-1]:.0%} to {rates[0]:.0%})"
        elif trend == "declining":
            return f"Satisfaction is declining (from {rates[-1]:.0%} to {rates[0]:.0%})"
        return "Satisfaction is stable"


# =============================================================================
# USER CORRECTION TRACKING
# =============================================================================

@dataclass
class CorrectionPattern:
    """A recurring pattern in user corrections."""
    pattern_id: str
    description: str
    frequency: int
    examples: list[dict[str, str]]
    suggested_fix: str
    category: str


class UserCorrectionTracker:
    """
    Tracks and analyzes user corrections to find systematic issues.
    
    Looks for:
    - Repeated corrections of the same type
    - Patterns in what users change
    - Systematic biases in AI output
    """

    def analyze_corrections(self, corrections: list[FeedbackRecord]) -> dict[str, Any]:
        """Analyze a set of corrections to find patterns."""
        correction_records = [r for r in corrections if r.signal == FeedbackSignal.CORRECTION]

        if not correction_records:
            return {"patterns": [], "summary": "No corrections to analyze"}

        # Analyze edit types
        edit_analysis = self._analyze_edits(correction_records)
        patterns = self._find_patterns(correction_records)

        return {
            "total_corrections": len(correction_records),
            "edit_analysis": edit_analysis,
            "patterns": patterns,
            "recommendations": self._generate_recommendations(patterns),
        }

    def _analyze_edits(self, records: list[FeedbackRecord]) -> dict[str, Any]:
        """Analyze the types of edits users make."""
        edit_types = defaultdict(int)
        
        for record in records:
            if record.original_response and record.correction_text:
                orig_len = len(record.original_response)
                corr_len = len(record.correction_text)
                
                if corr_len < orig_len * 0.5:
                    edit_types["major_reduction"] += 1
                elif corr_len > orig_len * 1.5:
                    edit_types["major_expansion"] += 1
                elif corr_len < orig_len * 0.9:
                    edit_types["minor_reduction"] += 1
                elif corr_len > orig_len * 1.1:
                    edit_types["minor_expansion"] += 1
                else:
                    edit_types["replacement"] += 1

        return {
            "edit_type_distribution": dict(edit_types),
            "most_common": max(edit_types, key=edit_types.get) if edit_types else None,
            "insight": self._edit_insight(edit_types),
        }

    def _find_patterns(self, records: list[FeedbackRecord]) -> list[CorrectionPattern]:
        """Find recurring correction patterns."""
        # Simplified pattern detection based on metadata
        patterns = []
        reason_counts: dict[str, list[FeedbackRecord]] = defaultdict(list)
        
        for record in records:
            reason = record.metadata.get("reason", "unspecified")
            reason_counts[reason].append(record)

        for reason, recs in reason_counts.items():
            if len(recs) >= 3:
                patterns.append(CorrectionPattern(
                    pattern_id=f"pat_{hashlib.sha256(reason.encode()).hexdigest()[:8]}",
                    description=f"Users frequently correct due to: {reason}",
                    frequency=len(recs),
                    examples=[
                        {"original": r.original_response[:100] if r.original_response else "", 
                         "corrected": r.correction_text[:100] if r.correction_text else ""}
                        for r in recs[:3]
                    ],
                    suggested_fix=self._suggest_fix_for_reason(reason),
                    category=reason,
                ))

        return sorted(patterns, key=lambda p: -p.frequency)

    def _edit_insight(self, edit_types: dict[str, int]) -> str:
        total = sum(edit_types.values())
        if not total:
            return "No edits to analyze"
        if edit_types.get("major_reduction", 0) / max(total, 1) > 0.4:
            return "AI responses tend to be too verbose — users frequently shorten them significantly"
        if edit_types.get("major_expansion", 0) / max(total, 1) > 0.4:
            return "AI responses tend to be too brief — users frequently add more detail"
        if edit_types.get("replacement", 0) / max(total, 1) > 0.4:
            return "Users frequently replace content entirely — suggesting accuracy issues"
        return "Edit patterns are mixed — no single dominant issue"

    def _suggest_fix_for_reason(self, reason: str) -> str:
        suggestions = {
            "too_verbose": "Reduce response length; add conciseness instruction to prompt",
            "inaccurate": "Review knowledge sources; add fact-checking step",
            "wrong_tone": "Adjust tone instructions in system prompt",
            "missing_context": "Improve retrieval to include more relevant context",
            "outdated": "Update knowledge base; add temporal awareness",
        }
        return suggestions.get(reason, "Review examples and update prompt/training accordingly")

    def _generate_recommendations(self, patterns: list[CorrectionPattern]) -> list[str]:
        """Generate actionable recommendations from patterns."""
        recs = []
        for pattern in patterns[:5]:
            recs.append(f"[{pattern.frequency} occurrences] {pattern.suggested_fix}")
        return recs


# =============================================================================
# SATISFACTION SCORING
# =============================================================================

class SatisfactionScorer:
    """
    Computes satisfaction metrics analogous to CSAT and NPS for AI interactions.
    
    Metrics:
    - AI-CSAT: Customer Satisfaction Score adapted for AI
    - AI-NPS: Net Promoter Score adapted for AI
    - Task Completion Rate
    - First-Response Resolution Rate
    """

    def compute_ai_csat(self, records: list[FeedbackRecord]) -> dict[str, Any]:
        """
        Compute AI-CSAT (Customer Satisfaction for AI).
        Based on thumbs up/down and ratings.
        """
        positive_signals = {FeedbackSignal.THUMBS_UP, FeedbackSignal.RATING_4, FeedbackSignal.RATING_5}
        negative_signals = {FeedbackSignal.THUMBS_DOWN, FeedbackSignal.RATING_1, FeedbackSignal.RATING_2}
        
        positive = sum(1 for r in records if r.signal in positive_signals)
        negative = sum(1 for r in records if r.signal in negative_signals)
        neutral = sum(1 for r in records if r.signal == FeedbackSignal.RATING_3)
        total = positive + negative + neutral

        csat = (positive / total * 100) if total > 0 else None

        return {
            "metric": "AI-CSAT",
            "score": round(csat, 1) if csat else None,
            "interpretation": self._interpret_csat(csat),
            "breakdown": {
                "satisfied": positive,
                "neutral": neutral,
                "dissatisfied": negative,
                "total_responses": total,
            },
            "benchmark": "Good: >75%, Excellent: >85%",
        }

    def compute_ai_nps(self, records: list[FeedbackRecord]) -> dict[str, Any]:
        """
        Compute AI-NPS (Net Promoter Score for AI).
        Based on: "How likely are you to recommend this AI assistant?"
        Uses 1-5 scale mapped to NPS logic (5=promoter, 4=passive, 1-3=detractor).
        """
        ratings = []
        for r in records:
            if r.signal.value.startswith("rating_"):
                ratings.append(int(r.signal.value.split("_")[1]))

        if not ratings:
            return {"metric": "AI-NPS", "score": None, "interpretation": "Insufficient data"}

        promoters = sum(1 for r in ratings if r >= 5) / len(ratings) * 100
        detractors = sum(1 for r in ratings if r <= 3) / len(ratings) * 100
        nps = promoters - detractors

        return {
            "metric": "AI-NPS",
            "score": round(nps, 1),
            "interpretation": self._interpret_nps(nps),
            "breakdown": {
                "promoters_pct": round(promoters, 1),
                "passives_pct": round(100 - promoters - detractors, 1),
                "detractors_pct": round(detractors, 1),
                "total_ratings": len(ratings),
            },
            "benchmark": "Good: >20, Excellent: >50",
        }

    def compute_resolution_rate(self, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Compute first-response resolution rate.
        A session is "resolved" if the user didn't retry or escalate.
        """
        total = len(sessions)
        resolved = sum(1 for s in sessions if not s.get("had_retry") and not s.get("escalated"))
        
        rate = (resolved / total * 100) if total > 0 else None
        return {
            "metric": "First-Response Resolution",
            "rate": round(rate, 1) if rate else None,
            "resolved": resolved,
            "total": total,
            "benchmark": "Good: >70%, Excellent: >85%",
        }

    def _interpret_csat(self, score: Optional[float]) -> str:
        if score is None:
            return "Insufficient data"
        if score >= 85:
            return "Excellent — users are highly satisfied"
        elif score >= 75:
            return "Good — most users are satisfied"
        elif score >= 60:
            return "Fair — significant room for improvement"
        else:
            return "Poor — users are largely dissatisfied"

    def _interpret_nps(self, score: float) -> str:
        if score >= 50:
            return "Excellent — strong user advocacy"
        elif score >= 20:
            return "Good — more promoters than detractors"
        elif score >= 0:
            return "Fair — balanced but needs improvement"
        else:
            return "Poor — more detractors than promoters"


# =============================================================================
# FEEDBACK-DRIVEN EVAL DATASET UPDATES
# =============================================================================

class FeedbackToEvalPipeline:
    """
    Converts user feedback (especially corrections) into evaluation dataset entries.
    
    This closes the loop: user feedback → eval cases → measured improvement.
    """

    def generate_eval_cases(self, corrections: list[FeedbackRecord]) -> list[dict[str, Any]]:
        """Generate eval dataset entries from user corrections."""
        eval_cases = []
        
        for record in corrections:
            if record.signal != FeedbackSignal.CORRECTION:
                continue
            if not record.query or not record.correction_text:
                continue

            eval_case = {
                "eval_id": f"eval_from_fb_{record.feedback_id}",
                "source": "user_correction",
                "query": record.query,
                "expected_output": record.correction_text,
                "bad_output": record.original_response,
                "category": record.category.value if record.category else "quality",
                "metadata": {
                    "feedback_id": record.feedback_id,
                    "user_id": record.user_id,
                    "timestamp": record.timestamp.isoformat(),
                    "correction_reason": record.metadata.get("reason"),
                },
                "weight": self._compute_case_weight(record),
            }
            eval_cases.append(eval_case)

        return eval_cases

    def generate_regression_tests(self, records: list[FeedbackRecord]) -> list[dict[str, Any]]:
        """Generate regression test cases from reported issues."""
        tests = []
        for record in records:
            if record.signal not in (FeedbackSignal.REPORT_INCORRECT, FeedbackSignal.REPORT_HARMFUL):
                continue
            if not record.query:
                continue

            tests.append({
                "test_id": f"regression_{record.feedback_id}",
                "query": record.query,
                "must_not_contain": record.original_response[:200] if record.original_response else None,
                "category": record.category.value if record.category else "quality",
                "severity": "critical" if record.signal == FeedbackSignal.REPORT_HARMFUL else "high",
            })

        return tests

    def _compute_case_weight(self, record: FeedbackRecord) -> float:
        """Compute importance weight for an eval case."""
        weight = 1.0
        # Higher weight for safety issues
        if record.category == FeedbackCategory.SAFETY:
            weight *= 3.0
        # Higher weight for corrections with explanations
        if record.metadata.get("reason"):
            weight *= 1.5
        # Higher weight for smaller edits (more targeted corrections)
        edit_dist = record.metadata.get("edit_distance", 100)
        if edit_dist < 50:
            weight *= 1.3
        return round(weight, 2)


# =============================================================================
# FEEDBACK REPORTING
# =============================================================================

class FeedbackReporter:
    """
    Generates reports for teams summarizing feedback insights.
    """

    def generate_weekly_report(
        self,
        records: list[FeedbackRecord],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Generate a weekly feedback report for the team."""
        period_records = [r for r in records if period_start <= r.timestamp < period_end]
        
        analytics = FeedbackAnalytics()
        scorer = SatisfactionScorer()
        categorizer = FeedbackCategorizer()
        pipeline = FeedbackToImprovementPipeline()

        categorized = categorizer.categorize_batch(period_records)
        improvements = pipeline.process_batch(period_records)

        return {
            "report_type": "weekly_feedback",
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "executive_summary": {
                "total_feedback": len(period_records),
                "csat": scorer.compute_ai_csat(period_records),
                "top_issue": improvements[0].description if improvements else "No significant issues",
            },
            "category_breakdown": {
                cat.value: {
                    "count": len(recs),
                    "percentage": round(len(recs) / max(len(period_records), 1) * 100, 1),
                }
                for cat, recs in categorized.items()
            },
            "top_improvements": [
                {
                    "priority": imp.priority,
                    "description": imp.description,
                    "evidence_count": imp.evidence_count,
                    "action_type": imp.action_type,
                }
                for imp in improvements[:5]
            ],
            "trends": analytics.compute_trends(records),
            "problem_areas": analytics.identify_problem_areas(period_records)[:5],
            "action_items": [
                f"[{imp.priority.upper()}] {imp.description}" for imp in improvements[:3]
            ],
        }

    def generate_alert(self, records: list[FeedbackRecord], window_minutes: int = 60) -> Optional[dict[str, Any]]:
        """Generate an alert if feedback indicates acute issues."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        recent = [r for r in records if r.timestamp >= cutoff]

        # Alert thresholds
        safety_reports = sum(1 for r in recent if r.signal == FeedbackSignal.REPORT_HARMFUL)
        negative_rate = sum(1 for r in recent if r.signal == FeedbackSignal.THUMBS_DOWN) / max(len(recent), 1)

        alerts = []
        if safety_reports >= 3:
            alerts.append({
                "severity": "critical",
                "message": f"{safety_reports} safety reports in the last {window_minutes} minutes",
                "action": "Investigate immediately — potential harmful output pattern",
            })
        if negative_rate > 0.5 and len(recent) >= 10:
            alerts.append({
                "severity": "high",
                "message": f"Negative feedback rate at {negative_rate:.0%} ({len(recent)} responses)",
                "action": "Review recent responses for quality degradation",
            })

        if not alerts:
            return None

        return {
            "type": "feedback_alert",
            "generated_at": now.isoformat(),
            "window_minutes": window_minutes,
            "alerts": alerts,
        }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def example_usage():
    """Demonstrate the feedback system end-to-end."""
    api = FeedbackCollectionAPI()
    
    # User submits thumbs down
    result = api.submit_thumbs(
        user_id="user_123",
        session_id="sess_abc",
        response_id="resp_456",
        is_positive=False,
        query="What is the capital of Australia?",
        response_text="The capital of Australia is Sydney.",
    )
    print("Thumbs down result:", json.dumps(result, indent=2))

    # User submits correction
    result = api.submit_correction(
        user_id="user_123",
        session_id="sess_abc",
        response_id="resp_456",
        original_text="The capital of Australia is Sydney.",
        corrected_text="The capital of Australia is Canberra.",
        correction_reason="inaccurate",
    )
    print("\nCorrection result:", json.dumps(result, indent=2))

    # Compute satisfaction
    scorer = SatisfactionScorer()
    print("\nCSAT:", json.dumps(scorer.compute_ai_csat(api._records), indent=2))


if __name__ == "__main__":
    example_usage()
