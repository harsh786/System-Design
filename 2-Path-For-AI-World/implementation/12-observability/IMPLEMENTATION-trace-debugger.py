"""
Module 12: AI Observability - Trace Debugger

Tool for reconstructing, analyzing, and debugging AI agent traces.
Supports: trace reconstruction, decision point analysis, root cause identification,
good vs bad trace comparison, trace search/filtering, and replay.
"""

import json
import time
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


# =============================================================================
# DATA MODELS
# =============================================================================

class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class DecisionQuality(Enum):
    GOOD = "good"
    SUSPICIOUS = "suspicious"
    BAD = "bad"
    UNKNOWN = "unknown"


@dataclass
class SpanRecord:
    """Represents a single span from a stored trace."""
    span_id: str
    parent_span_id: Optional[str]
    trace_id: str
    name: str
    start_time: float
    end_time: float
    status: SpanStatus
    attributes: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    children: list = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def is_llm_span(self) -> bool:
        return "ai.llm" in self.name or "gen_ai" in str(self.attributes)

    @property
    def is_retrieval_span(self) -> bool:
        return "retrieval" in self.name

    @property
    def is_tool_span(self) -> bool:
        return "ai.tool" in self.name

    @property
    def is_guardrail_span(self) -> bool:
        return "guardrail" in self.name

    @property
    def is_agent_step(self) -> bool:
        return "ai.agent.step" in self.name


@dataclass
class TraceRecord:
    """Complete trace containing all spans."""
    trace_id: str
    root_span: SpanRecord
    all_spans: list[SpanRecord]
    metadata: dict = field(default_factory=dict)

    @property
    def total_duration_ms(self) -> float:
        return self.root_span.duration_ms

    @property
    def total_cost(self) -> float:
        return sum(
            s.attributes.get("gen_ai.usage.cost_usd", 0)
            for s in self.all_spans
        )

    @property
    def total_tokens(self) -> int:
        return sum(
            s.attributes.get("gen_ai.usage.input_tokens", 0)
            + s.attributes.get("gen_ai.usage.output_tokens", 0)
            for s in self.all_spans
        )

    @property
    def error_spans(self) -> list[SpanRecord]:
        return [s for s in self.all_spans if s.status == SpanStatus.ERROR]

    @property
    def llm_calls(self) -> list[SpanRecord]:
        return [s for s in self.all_spans if s.is_llm_span]

    @property
    def tool_calls(self) -> list[SpanRecord]:
        return [s for s in self.all_spans if s.is_tool_span]


@dataclass
class DecisionPoint:
    """A point in the trace where a decision was made."""
    span: SpanRecord
    decision_type: str  # "retrieval", "rerank", "tool_selection", "guardrail", "generation"
    input_summary: str
    output_summary: str
    quality: DecisionQuality
    issue: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class RootCauseAnalysis:
    """Result of root cause analysis on a trace."""
    trace_id: str
    identified_cause: str
    confidence: float
    failed_at_span: SpanRecord
    contributing_factors: list[str]
    recommendations: list[str]
    timeline: list[dict]


# =============================================================================
# TRACE STORE (Interface + In-Memory Implementation)
# =============================================================================

class TraceStore:
    """
    Interface for trace storage backend.
    In production, this would query Jaeger, Tempo, or a data lake.
    """

    def __init__(self):
        self._traces: dict[str, TraceRecord] = {}
        self._index_by_tenant: dict[str, list[str]] = defaultdict(list)
        self._index_by_session: dict[str, list[str]] = defaultdict(list)
        self._index_by_status: dict[str, list[str]] = defaultdict(list)

    def store(self, trace: TraceRecord):
        self._traces[trace.trace_id] = trace
        tenant = trace.root_span.attributes.get("ai.tenant.id", "unknown")
        session = trace.root_span.attributes.get("ai.session.id", "unknown")
        self._index_by_tenant[tenant].append(trace.trace_id)
        self._index_by_session[session].append(trace.trace_id)

        status = "error" if trace.error_spans else "ok"
        self._index_by_status[status].append(trace.trace_id)

    def get(self, trace_id: str) -> Optional[TraceRecord]:
        return self._traces.get(trace_id)

    def search(
        self,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        has_errors: Optional[bool] = None,
        min_duration_ms: Optional[float] = None,
        max_duration_ms: Optional[float] = None,
        min_cost: Optional[float] = None,
        time_range: Optional[tuple[float, float]] = None,
        limit: int = 100,
    ) -> list[TraceRecord]:
        """Search traces with filtering."""
        candidates = list(self._traces.values())

        if tenant_id:
            trace_ids = set(self._index_by_tenant.get(tenant_id, []))
            candidates = [t for t in candidates if t.trace_id in trace_ids]

        if session_id:
            trace_ids = set(self._index_by_session.get(session_id, []))
            candidates = [t for t in candidates if t.trace_id in trace_ids]

        if has_errors is not None:
            if has_errors:
                candidates = [t for t in candidates if t.error_spans]
            else:
                candidates = [t for t in candidates if not t.error_spans]

        if min_duration_ms is not None:
            candidates = [t for t in candidates if t.total_duration_ms >= min_duration_ms]

        if max_duration_ms is not None:
            candidates = [t for t in candidates if t.total_duration_ms <= max_duration_ms]

        if min_cost is not None:
            candidates = [t for t in candidates if t.total_cost >= min_cost]

        if time_range:
            start, end = time_range
            candidates = [
                t for t in candidates
                if start <= t.root_span.start_time <= end
            ]

        # Sort by start time descending
        candidates.sort(key=lambda t: t.root_span.start_time, reverse=True)
        return candidates[:limit]


# =============================================================================
# TRACE RECONSTRUCTOR
# =============================================================================

class TraceReconstructor:
    """Reconstructs a human-readable narrative from a trace."""

    def reconstruct(self, trace: TraceRecord) -> dict:
        """
        Reconstruct the full agent conversation/pipeline from a trace.
        Returns a structured narrative of what happened.
        """
        narrative = {
            "trace_id": trace.trace_id,
            "timestamp": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(trace.root_span.start_time)
            ),
            "duration_ms": trace.total_duration_ms,
            "total_cost_usd": trace.total_cost,
            "total_tokens": trace.total_tokens,
            "status": "error" if trace.error_spans else "success",
            "user_input": trace.root_span.attributes.get("ai.request.input_preview", ""),
            "tenant_id": trace.root_span.attributes.get("ai.tenant.id", ""),
            "session_id": trace.root_span.attributes.get("ai.session.id", ""),
            "steps": [],
            "final_response": trace.root_span.attributes.get("ai.response.content", ""),
            "errors": [],
        }

        # Build timeline of steps
        sorted_spans = sorted(trace.all_spans, key=lambda s: s.start_time)

        for span in sorted_spans:
            if span == trace.root_span:
                continue

            step = {
                "name": span.name,
                "duration_ms": span.duration_ms,
                "status": span.status.value,
                "timestamp_offset_ms": (span.start_time - trace.root_span.start_time) * 1000,
            }

            if span.is_retrieval_span:
                step["type"] = "retrieval"
                step["query"] = span.attributes.get("ai.retrieval.query", "")
                step["chunks_returned"] = span.attributes.get("ai.retrieval.chunks_returned", 0)
                step["max_score"] = span.attributes.get("ai.retrieval.max_score", 0)
                step["min_score"] = span.attributes.get("ai.retrieval.min_score", 0)

            elif span.is_llm_span:
                step["type"] = "llm_call"
                step["model"] = span.attributes.get("gen_ai.request.model", "")
                step["input_tokens"] = span.attributes.get("gen_ai.usage.input_tokens", 0)
                step["output_tokens"] = span.attributes.get("gen_ai.usage.output_tokens", 0)
                step["cost_usd"] = span.attributes.get("gen_ai.usage.cost_usd", 0)
                step["finish_reason"] = span.attributes.get("gen_ai.response.finish_reasons", "")
                if "gen_ai.response.content" in span.attributes:
                    step["output_preview"] = span.attributes["gen_ai.response.content"][:200]

            elif span.is_tool_span:
                step["type"] = "tool_call"
                step["tool_name"] = span.attributes.get("ai.tool.name", "")
                step["arguments"] = span.attributes.get("ai.tool.arguments", "")
                step["result_status"] = span.attributes.get("ai.tool.result_status", "")
                step["result_summary"] = span.attributes.get("ai.tool.result_summary", "")

            elif span.is_guardrail_span:
                step["type"] = "guardrail"
                step["guardrail_name"] = span.attributes.get("ai.guardrail.name", "")
                step["decision"] = span.attributes.get("ai.guardrail.decision", "")
                step["reason"] = span.attributes.get("ai.guardrail.reason", "")
                step["score"] = span.attributes.get("ai.guardrail.score", None)

            elif span.is_agent_step:
                step["type"] = "agent_step"
                step["step_number"] = span.attributes.get("ai.agent.step_number", 0)
                step["reasoning"] = span.attributes.get("ai.agent.reasoning", "")
                step["action"] = span.attributes.get("ai.agent.action", "")

            else:
                step["type"] = "other"

            narrative["steps"].append(step)

            if span.status == SpanStatus.ERROR:
                narrative["errors"].append({
                    "span": span.name,
                    "error": span.attributes.get("error.message", "unknown"),
                    "at_offset_ms": step["timestamp_offset_ms"],
                })

        return narrative


# =============================================================================
# DECISION POINT ANALYZER
# =============================================================================

class DecisionPointAnalyzer:
    """Identifies and evaluates decision points in a trace."""

    def __init__(self, quality_thresholds: dict = None):
        self.thresholds = quality_thresholds or {
            "retrieval_min_score": 0.7,
            "groundedness_min": 0.7,
            "tool_max_latency_ms": 5000,
            "max_agent_steps": 10,
        }

    def analyze(self, trace: TraceRecord) -> list[DecisionPoint]:
        """Identify all decision points and evaluate their quality."""
        decisions = []

        for span in sorted(trace.all_spans, key=lambda s: s.start_time):
            if span == trace.root_span:
                continue

            if span.is_retrieval_span:
                decisions.append(self._analyze_retrieval(span))
            elif span.is_llm_span:
                decisions.append(self._analyze_generation(span))
            elif span.is_tool_span:
                decisions.append(self._analyze_tool_selection(span))
            elif span.is_guardrail_span:
                decisions.append(self._analyze_guardrail(span))

        return decisions

    def _analyze_retrieval(self, span: SpanRecord) -> DecisionPoint:
        max_score = span.attributes.get("ai.retrieval.max_score", 0)
        chunks = span.attributes.get("ai.retrieval.chunks_returned", 0)
        query = span.attributes.get("ai.retrieval.query", "")

        if max_score < self.thresholds["retrieval_min_score"]:
            quality = DecisionQuality.BAD
            issue = f"Best retrieval score ({max_score:.2f}) below threshold ({self.thresholds['retrieval_min_score']})"
            suggestion = "Check if relevant documents exist in index. Consider query reformulation."
        elif chunks == 0:
            quality = DecisionQuality.BAD
            issue = "No chunks retrieved"
            suggestion = "Index may be empty or query embedding may be poor."
        else:
            quality = DecisionQuality.GOOD
            issue = None
            suggestion = None

        return DecisionPoint(
            span=span,
            decision_type="retrieval",
            input_summary=f"Query: {query[:100]}",
            output_summary=f"{chunks} chunks, max_score={max_score:.2f}",
            quality=quality,
            issue=issue,
            suggestion=suggestion,
        )

    def _analyze_generation(self, span: SpanRecord) -> DecisionPoint:
        finish_reason = span.attributes.get("gen_ai.response.finish_reasons", "stop")
        model = span.attributes.get("gen_ai.request.model", "unknown")

        if finish_reason == "length":
            quality = DecisionQuality.SUSPICIOUS
            issue = "Response was truncated (finish_reason=length)"
            suggestion = "Increase max_tokens or reduce context size."
        elif finish_reason == "content_filter":
            quality = DecisionQuality.BAD
            issue = "Content filter triggered by provider"
            suggestion = "Review prompt for policy-violating content."
        elif span.status == SpanStatus.ERROR:
            quality = DecisionQuality.BAD
            issue = "LLM call failed"
            suggestion = "Check provider status and rate limits."
        else:
            quality = DecisionQuality.GOOD
            issue = None
            suggestion = None

        return DecisionPoint(
            span=span,
            decision_type="generation",
            input_summary=f"Model: {model}, tokens_in={span.attributes.get('gen_ai.usage.input_tokens', 0)}",
            output_summary=f"tokens_out={span.attributes.get('gen_ai.usage.output_tokens', 0)}, finish={finish_reason}",
            quality=quality,
            issue=issue,
            suggestion=suggestion,
        )

    def _analyze_tool_selection(self, span: SpanRecord) -> DecisionPoint:
        tool_name = span.attributes.get("ai.tool.name", "")
        status = span.attributes.get("ai.tool.result_status", "")
        latency = span.duration_ms

        if status == "error":
            quality = DecisionQuality.BAD
            issue = f"Tool '{tool_name}' failed: {span.attributes.get('ai.tool.error', '')}"
            suggestion = "Verify tool availability and input validation."
        elif latency > self.thresholds["tool_max_latency_ms"]:
            quality = DecisionQuality.SUSPICIOUS
            issue = f"Tool '{tool_name}' took {latency:.0f}ms (threshold: {self.thresholds['tool_max_latency_ms']}ms)"
            suggestion = "Consider timeout configuration or caching."
        else:
            quality = DecisionQuality.GOOD
            issue = None
            suggestion = None

        return DecisionPoint(
            span=span,
            decision_type="tool_selection",
            input_summary=f"Tool: {tool_name}, args: {span.attributes.get('ai.tool.arguments', '')[:100]}",
            output_summary=f"Status: {status}, latency: {latency:.0f}ms",
            quality=quality,
            issue=issue,
            suggestion=suggestion,
        )

    def _analyze_guardrail(self, span: SpanRecord) -> DecisionPoint:
        name = span.attributes.get("ai.guardrail.name", "")
        decision = span.attributes.get("ai.guardrail.decision", "")
        score = span.attributes.get("ai.guardrail.score", None)

        if decision == "block":
            quality = DecisionQuality.SUSPICIOUS  # Might be false positive
            issue = f"Guardrail '{name}' blocked output"
            suggestion = "Review if block was justified. Check for false positives."
        else:
            quality = DecisionQuality.GOOD
            issue = None
            suggestion = None

        return DecisionPoint(
            span=span,
            decision_type="guardrail",
            input_summary=f"Guardrail: {name}",
            output_summary=f"Decision: {decision}, score: {score}",
            quality=quality,
            issue=issue,
            suggestion=suggestion,
        )


# =============================================================================
# ROOT CAUSE ANALYZER
# =============================================================================

class RootCauseAnalyzer:
    """Performs root cause analysis on failed or degraded traces."""

    def analyze(self, trace: TraceRecord) -> RootCauseAnalysis:
        """Identify the root cause of a trace failure or quality issue."""

        timeline = []
        contributing_factors = []
        failed_span = None
        identified_cause = "unknown"
        confidence = 0.0

        sorted_spans = sorted(trace.all_spans, key=lambda s: s.start_time)

        for span in sorted_spans:
            entry = {
                "time_offset_ms": (span.start_time - trace.root_span.start_time) * 1000,
                "span": span.name,
                "duration_ms": span.duration_ms,
                "status": span.status.value,
            }
            timeline.append(entry)

            # Check for issues
            if span.status == SpanStatus.ERROR and failed_span is None:
                failed_span = span

            if span.is_retrieval_span:
                max_score = span.attributes.get("ai.retrieval.max_score", 1.0)
                if max_score < 0.7:
                    contributing_factors.append(
                        f"Low retrieval score ({max_score:.2f}) - relevant content may not be in index"
                    )

            if span.is_llm_span:
                finish = span.attributes.get("gen_ai.response.finish_reasons", "")
                if finish == "length":
                    contributing_factors.append("LLM response truncated - context may be too large")

            if span.is_tool_span and span.status == SpanStatus.ERROR:
                tool = span.attributes.get("ai.tool.name", "")
                contributing_factors.append(f"Tool '{tool}' failed - agent may have bad info")

        # Determine root cause
        if failed_span:
            if failed_span.is_tool_span:
                identified_cause = f"Tool failure: {failed_span.attributes.get('ai.tool.name', '')} - {failed_span.attributes.get('ai.tool.error', '')}"
                confidence = 0.85
            elif failed_span.is_llm_span:
                identified_cause = f"LLM error: {failed_span.attributes.get('error.message', 'unknown')}"
                confidence = 0.90
            elif failed_span.is_retrieval_span:
                identified_cause = "Retrieval failure - no relevant context available"
                confidence = 0.80
            else:
                identified_cause = f"Failure in {failed_span.name}"
                confidence = 0.60
        elif contributing_factors:
            identified_cause = "Quality degradation: " + contributing_factors[0]
            confidence = 0.65
            failed_span = trace.root_span

        # Recommendations
        recommendations = self._generate_recommendations(
            identified_cause, contributing_factors, trace
        )

        return RootCauseAnalysis(
            trace_id=trace.trace_id,
            identified_cause=identified_cause,
            confidence=confidence,
            failed_at_span=failed_span or trace.root_span,
            contributing_factors=contributing_factors,
            recommendations=recommendations,
            timeline=timeline,
        )

    def _generate_recommendations(
        self, cause: str, factors: list[str], trace: TraceRecord
    ) -> list[str]:
        recommendations = []

        if "retrieval" in cause.lower() or any("retrieval" in f.lower() for f in factors):
            recommendations.extend([
                "Check index freshness - when was it last updated?",
                "Review query rewriting logic - is the search query representative?",
                "Consider adding hybrid search (keyword + vector)",
                "Verify embedding model hasn't changed",
            ])

        if "tool" in cause.lower():
            recommendations.extend([
                "Add retry logic with exponential backoff",
                "Implement tool health checks",
                "Consider fallback tools for critical operations",
            ])

        if "llm" in cause.lower() or "truncat" in cause.lower():
            recommendations.extend([
                "Reduce context size by more aggressive chunk selection",
                "Increase max_tokens if budget allows",
                "Consider a model with larger context window",
            ])

        if trace.total_cost > 0.10:
            recommendations.append(
                f"High cost trace (${trace.total_cost:.3f}) - review if all LLM calls were necessary"
            )

        if len(trace.llm_calls) > 5:
            recommendations.append(
                f"Many LLM calls ({len(trace.llm_calls)}) - consider if agent is looping"
            )

        return recommendations


# =============================================================================
# TRACE COMPARATOR
# =============================================================================

class TraceComparator:
    """Compare good vs bad traces to identify patterns."""

    def compare(self, good_trace: TraceRecord, bad_trace: TraceRecord) -> dict:
        """Compare a good trace against a bad trace to find differences."""
        comparison = {
            "good_trace_id": good_trace.trace_id,
            "bad_trace_id": bad_trace.trace_id,
            "duration_diff_ms": bad_trace.total_duration_ms - good_trace.total_duration_ms,
            "cost_diff_usd": bad_trace.total_cost - good_trace.total_cost,
            "token_diff": bad_trace.total_tokens - good_trace.total_tokens,
            "llm_call_diff": len(bad_trace.llm_calls) - len(good_trace.llm_calls),
            "tool_call_diff": len(bad_trace.tool_calls) - len(good_trace.tool_calls),
            "differences": [],
        }

        # Compare retrieval quality
        good_retrieval = [s for s in good_trace.all_spans if s.is_retrieval_span]
        bad_retrieval = [s for s in bad_trace.all_spans if s.is_retrieval_span]

        if good_retrieval and bad_retrieval:
            good_score = good_retrieval[0].attributes.get("ai.retrieval.max_score", 0)
            bad_score = bad_retrieval[0].attributes.get("ai.retrieval.max_score", 0)
            if abs(good_score - bad_score) > 0.1:
                comparison["differences"].append({
                    "component": "retrieval",
                    "metric": "max_score",
                    "good_value": good_score,
                    "bad_value": bad_score,
                    "interpretation": "Bad trace had lower retrieval quality"
                    if bad_score < good_score
                    else "Bad trace had better retrieval but still failed",
                })

        # Compare LLM usage
        good_llm_tokens = sum(
            s.attributes.get("gen_ai.usage.input_tokens", 0) for s in good_trace.llm_calls
        )
        bad_llm_tokens = sum(
            s.attributes.get("gen_ai.usage.input_tokens", 0) for s in bad_trace.llm_calls
        )
        if bad_llm_tokens > good_llm_tokens * 1.5:
            comparison["differences"].append({
                "component": "llm",
                "metric": "total_input_tokens",
                "good_value": good_llm_tokens,
                "bad_value": bad_llm_tokens,
                "interpretation": "Bad trace used significantly more tokens - possible context bloat or looping",
            })

        # Compare errors
        if bad_trace.error_spans and not good_trace.error_spans:
            for err_span in bad_trace.error_spans:
                comparison["differences"].append({
                    "component": err_span.name,
                    "metric": "error",
                    "good_value": "no error",
                    "bad_value": err_span.attributes.get("error.message", "unknown error"),
                    "interpretation": f"Bad trace had error in {err_span.name}",
                })

        # Summary
        if comparison["differences"]:
            comparison["likely_root_cause"] = comparison["differences"][0]["interpretation"]
        else:
            comparison["likely_root_cause"] = "No obvious structural differences found"

        return comparison


# =============================================================================
# TRACE REPLAY
# =============================================================================

class TraceReplayer:
    """Replay a trace step-by-step for debugging."""

    def replay(self, trace: TraceRecord, speed: float = 1.0) -> list[dict]:
        """
        Generate a step-by-step replay of the trace.
        Returns events in chronological order with timing info.
        """
        events = []
        sorted_spans = sorted(trace.all_spans, key=lambda s: s.start_time)
        base_time = trace.root_span.start_time

        for span in sorted_spans:
            offset = (span.start_time - base_time) * 1000
            event = {
                "offset_ms": round(offset, 1),
                "replay_delay_ms": round(offset / speed, 1),
                "event": "span_start",
                "span_name": span.name,
                "span_type": self._get_span_type(span),
                "details": self._get_span_details(span),
            }
            events.append(event)

            # Add end event
            end_offset = (span.end_time - base_time) * 1000
            events.append({
                "offset_ms": round(end_offset, 1),
                "replay_delay_ms": round(end_offset / speed, 1),
                "event": "span_end",
                "span_name": span.name,
                "duration_ms": round(span.duration_ms, 1),
                "status": span.status.value,
            })

        events.sort(key=lambda e: e["offset_ms"])
        return events

    def _get_span_type(self, span: SpanRecord) -> str:
        if span.is_llm_span:
            return "llm"
        if span.is_retrieval_span:
            return "retrieval"
        if span.is_tool_span:
            return "tool"
        if span.is_guardrail_span:
            return "guardrail"
        if span.is_agent_step:
            return "agent_step"
        return "other"

    def _get_span_details(self, span: SpanRecord) -> dict:
        details = {}
        if span.is_llm_span:
            details["model"] = span.attributes.get("gen_ai.request.model", "")
            details["temperature"] = span.attributes.get("gen_ai.request.temperature", "")
        elif span.is_retrieval_span:
            details["query"] = span.attributes.get("ai.retrieval.query", "")[:100]
            details["top_k"] = span.attributes.get("ai.retrieval.top_k", "")
        elif span.is_tool_span:
            details["tool"] = span.attributes.get("ai.tool.name", "")
            details["args"] = span.attributes.get("ai.tool.arguments", "")[:100]
        elif span.is_guardrail_span:
            details["name"] = span.attributes.get("ai.guardrail.name", "")
        return details


# =============================================================================
# MAIN DEBUGGER INTERFACE
# =============================================================================

class TraceDebugger:
    """
    Main interface for trace debugging.
    Combines all analysis capabilities.
    """

    def __init__(self, store: TraceStore = None):
        self.store = store or TraceStore()
        self.reconstructor = TraceReconstructor()
        self.decision_analyzer = DecisionPointAnalyzer()
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.comparator = TraceComparator()
        self.replayer = TraceReplayer()

    def debug_trace(self, trace_id: str) -> dict:
        """Full debug analysis of a single trace."""
        trace = self.store.get(trace_id)
        if not trace:
            return {"error": f"Trace {trace_id} not found"}

        narrative = self.reconstructor.reconstruct(trace)
        decisions = self.decision_analyzer.analyze(trace)
        root_cause = None

        if trace.error_spans or any(d.quality == DecisionQuality.BAD for d in decisions):
            root_cause = self.root_cause_analyzer.analyze(trace)

        return {
            "narrative": narrative,
            "decision_points": [
                {
                    "type": d.decision_type,
                    "quality": d.quality.value,
                    "input": d.input_summary,
                    "output": d.output_summary,
                    "issue": d.issue,
                    "suggestion": d.suggestion,
                }
                for d in decisions
            ],
            "root_cause": {
                "cause": root_cause.identified_cause,
                "confidence": root_cause.confidence,
                "failed_at": root_cause.failed_at_span.name,
                "factors": root_cause.contributing_factors,
                "recommendations": root_cause.recommendations,
            }
            if root_cause
            else None,
            "summary": {
                "duration_ms": trace.total_duration_ms,
                "cost_usd": trace.total_cost,
                "tokens": trace.total_tokens,
                "llm_calls": len(trace.llm_calls),
                "tool_calls": len(trace.tool_calls),
                "errors": len(trace.error_spans),
                "bad_decisions": sum(1 for d in decisions if d.quality == DecisionQuality.BAD),
            },
        }

    def compare_traces(self, good_trace_id: str, bad_trace_id: str) -> dict:
        """Compare a good trace against a bad one."""
        good = self.store.get(good_trace_id)
        bad = self.store.get(bad_trace_id)
        if not good or not bad:
            return {"error": "One or both traces not found"}
        return self.comparator.compare(good, bad)

    def search_traces(self, **kwargs) -> list[dict]:
        """Search traces with filtering. Returns summaries."""
        traces = self.store.search(**kwargs)
        return [
            {
                "trace_id": t.trace_id,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t.root_span.start_time)),
                "duration_ms": t.total_duration_ms,
                "cost_usd": t.total_cost,
                "status": "error" if t.error_spans else "ok",
                "user_input_preview": t.root_span.attributes.get("ai.request.input_preview", "")[:80],
            }
            for t in traces
        ]

    def replay_trace(self, trace_id: str, speed: float = 1.0) -> list[dict]:
        """Get replay events for a trace."""
        trace = self.store.get(trace_id)
        if not trace:
            return []
        return self.replayer.replay(trace, speed)


# =============================================================================
# EXAMPLE: Create and debug a sample trace
# =============================================================================

def create_sample_bad_trace() -> TraceRecord:
    """Create a sample trace with issues for debugging demonstration."""
    now = time.time()

    root = SpanRecord(
        span_id="span-root",
        parent_span_id=None,
        trace_id="trace-bad-001",
        name="ai.request",
        start_time=now,
        end_time=now + 5.2,
        status=SpanStatus.OK,
        attributes={
            "ai.request.input_preview": "What is the refund policy for enterprise customers?",
            "ai.tenant.id": "tenant-acme",
            "ai.session.id": "session-123",
            "ai.response.content": "I'm not sure about the refund policy. Please contact support.",
            "ai.response.length": 65,
        },
    )

    retrieval = SpanRecord(
        span_id="span-retrieval",
        parent_span_id="span-root",
        trace_id="trace-bad-001",
        name="ai.retrieval",
        start_time=now + 0.1,
        end_time=now + 0.3,
        status=SpanStatus.OK,
        attributes={
            "ai.retrieval.query": "refund policy enterprise customers",
            "ai.retrieval.top_k": 10,
            "ai.retrieval.chunks_returned": 5,
            "ai.retrieval.max_score": 0.52,  # LOW SCORE - this is the problem
            "ai.retrieval.min_score": 0.31,
        },
    )

    llm_call = SpanRecord(
        span_id="span-llm",
        parent_span_id="span-root",
        trace_id="trace-bad-001",
        name="ai.llm.openai.gpt-4o",
        start_time=now + 0.4,
        end_time=now + 2.1,
        status=SpanStatus.OK,
        attributes={
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.request.temperature": 0.1,
            "gen_ai.usage.input_tokens": 2100,
            "gen_ai.usage.output_tokens": 45,
            "gen_ai.usage.cost_usd": 0.0058,
            "gen_ai.response.finish_reasons": "stop",
        },
    )

    guardrail = SpanRecord(
        span_id="span-guardrail",
        parent_span_id="span-root",
        trace_id="trace-bad-001",
        name="ai.guardrail.groundedness_check",
        start_time=now + 2.2,
        end_time=now + 2.3,
        status=SpanStatus.OK,
        attributes={
            "ai.guardrail.name": "groundedness_check",
            "ai.guardrail.decision": "warn",
            "ai.guardrail.score": 0.35,
            "ai.guardrail.threshold": 0.7,
            "ai.guardrail.reason": "Response not well-supported by context",
        },
    )

    return TraceRecord(
        trace_id="trace-bad-001",
        root_span=root,
        all_spans=[root, retrieval, llm_call, guardrail],
    )


def create_sample_good_trace() -> TraceRecord:
    """Create a sample successful trace for comparison."""
    now = time.time() - 100

    root = SpanRecord(
        span_id="span-root-g",
        parent_span_id=None,
        trace_id="trace-good-001",
        name="ai.request",
        start_time=now,
        end_time=now + 2.1,
        status=SpanStatus.OK,
        attributes={
            "ai.request.input_preview": "What is the refund policy for enterprise customers?",
            "ai.tenant.id": "tenant-acme",
            "ai.session.id": "session-456",
            "ai.response.content": "Enterprise customers can request a full refund within 30 days...",
            "ai.response.length": 250,
        },
    )

    retrieval = SpanRecord(
        span_id="span-retrieval-g",
        parent_span_id="span-root-g",
        trace_id="trace-good-001",
        name="ai.retrieval",
        start_time=now + 0.1,
        end_time=now + 0.25,
        status=SpanStatus.OK,
        attributes={
            "ai.retrieval.query": "refund policy enterprise customers",
            "ai.retrieval.top_k": 10,
            "ai.retrieval.chunks_returned": 5,
            "ai.retrieval.max_score": 0.94,
            "ai.retrieval.min_score": 0.72,
        },
    )

    llm_call = SpanRecord(
        span_id="span-llm-g",
        parent_span_id="span-root-g",
        trace_id="trace-good-001",
        name="ai.llm.openai.gpt-4o",
        start_time=now + 0.3,
        end_time=now + 1.8,
        status=SpanStatus.OK,
        attributes={
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.usage.input_tokens": 1900,
            "gen_ai.usage.output_tokens": 180,
            "gen_ai.usage.cost_usd": 0.0065,
            "gen_ai.response.finish_reasons": "stop",
        },
    )

    return TraceRecord(
        trace_id="trace-good-001",
        root_span=root,
        all_spans=[root, retrieval, llm_call],
    )


def example_debug_session():
    """Demonstrate the trace debugger."""

    debugger = TraceDebugger()

    # Store sample traces
    bad_trace = create_sample_bad_trace()
    good_trace = create_sample_good_trace()
    debugger.store.store(bad_trace)
    debugger.store.store(good_trace)

    # Debug the bad trace
    print("=" * 70)
    print("DEBUGGING BAD TRACE")
    print("=" * 70)
    result = debugger.debug_trace("trace-bad-001")
    print(json.dumps(result, indent=2, default=str))

    # Compare good vs bad
    print("\n" + "=" * 70)
    print("COMPARING GOOD vs BAD TRACE")
    print("=" * 70)
    comparison = debugger.compare_traces("trace-good-001", "trace-bad-001")
    print(json.dumps(comparison, indent=2, default=str))

    # Search for error traces
    print("\n" + "=" * 70)
    print("SEARCHING TRACES")
    print("=" * 70)
    results = debugger.search_traces(tenant_id="tenant-acme")
    print(json.dumps(results, indent=2, default=str))

    # Replay
    print("\n" + "=" * 70)
    print("TRACE REPLAY")
    print("=" * 70)
    replay = debugger.replay_trace("trace-bad-001")
    for event in replay:
        print(f"  [{event['offset_ms']:7.1f}ms] {event['event']:10s} | {event['span_name']}")


if __name__ == "__main__":
    example_debug_session()
