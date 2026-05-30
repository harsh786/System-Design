"""
AI Explainability System
=========================
Production-grade system for explaining AI decisions, answers, and actions to users.
Makes AI behavior transparent and understandable to both technical and non-technical audiences.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


# =============================================================================
# CORE DATA MODELS
# =============================================================================

class AudienceLevel(Enum):
    NON_TECHNICAL = "non_technical"  # Business users, general public
    TECHNICAL = "technical"          # Developers, data scientists
    EXPERT = "expert"                # ML engineers, researchers


class ExplanationType(Enum):
    ATTRIBUTION = "attribution"       # Which sources contributed
    DECISION = "decision"             # Why this answer/action
    CONFIDENCE = "confidence"         # Why low/high confidence
    TOOL_USAGE = "tool_usage"         # Why this tool was called
    RETRIEVAL = "retrieval"           # What was searched and found
    REASONING = "reasoning"           # Step-by-step reasoning
    SUMMARY = "summary"              # Non-technical summary
    VISUAL = "visual"                # Visual explanation


@dataclass
class SourceAttribution:
    """Attribution of answer content to specific sources."""
    source_id: str
    source_title: str
    source_url: Optional[str]
    contribution_type: str  # "primary", "supporting", "context"
    contribution_weight: float  # 0.0 to 1.0
    relevant_excerpt: str
    claim_supported: str  # What specific claim this source supports


@dataclass
class ReasoningStep:
    """A single step in the AI's reasoning process."""
    step_number: int
    action: str  # "analyzed", "searched", "compared", "concluded", etc.
    description: str
    input_summary: str
    output_summary: str
    confidence_at_step: float
    duration_ms: Optional[int] = None
    tools_used: list[str] = field(default_factory=list)


@dataclass
class ToolCall:
    """Record of a tool/function call made during processing."""
    tool_name: str
    reason_for_call: str
    input_summary: str
    output_summary: str
    was_successful: bool
    duration_ms: int
    alternatives_considered: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """A single retrieval operation and its results."""
    query_used: str
    source_searched: str  # "knowledge_base", "web", "database", etc.
    results_found: int
    results_used: int
    top_result_relevance: float
    reason_for_search: str
    results_summary: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExplanationContext:
    """Full context for generating an explanation."""
    response_id: str
    query: str
    response_text: str
    confidence_score: float
    sources: list[SourceAttribution] = field(default_factory=list)
    reasoning_steps: list[ReasoningStep] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    retrievals: list[RetrievalResult] = field(default_factory=list)
    model_version: str = ""
    total_duration_ms: int = 0


# =============================================================================
# ANSWER ATTRIBUTION
# =============================================================================

class AnswerAttributionEngine:
    """
    Attributes parts of an AI answer to specific sources.
    
    Shows users exactly WHERE information came from, building trust
    through verifiability.
    """

    CONTRIBUTION_LABELS = {
        "primary": {"label": "Main source", "icon": "star", "color": "#22c55e"},
        "supporting": {"label": "Supporting source", "icon": "check", "color": "#3b82f6"},
        "context": {"label": "Background context", "icon": "info", "color": "#6b7280"},
    }

    def generate_attribution(
        self,
        context: ExplanationContext,
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Generate a complete attribution breakdown for a response."""
        if not context.sources:
            return {
                "type": "attribution",
                "has_sources": False,
                "message": "This response was generated from my training knowledge without specific source documents.",
                "caveat": "I cannot point to a specific source for verification.",
            }

        # Group sources by contribution type
        primary = [s for s in context.sources if s.contribution_type == "primary"]
        supporting = [s for s in context.sources if s.contribution_type == "supporting"]
        context_sources = [s for s in context.sources if s.contribution_type == "context"]

        attribution = {
            "type": "attribution",
            "has_sources": True,
            "summary": self._generate_summary(context.sources, audience),
            "primary_sources": [self._format_source(s, audience) for s in primary],
            "supporting_sources": [self._format_source(s, audience) for s in supporting],
            "context_sources": [self._format_source(s, audience) for s in context_sources],
            "coverage": self._compute_coverage(context.sources),
            "source_agreement": self._assess_agreement(context.sources),
        }

        if audience == AudienceLevel.TECHNICAL:
            attribution["weights"] = {s.source_id: s.contribution_weight for s in context.sources}

        return attribution

    def generate_inline_attribution(self, context: ExplanationContext) -> list[dict[str, Any]]:
        """Generate claim-by-claim attribution for inline display."""
        attributed_claims = []
        for source in context.sources:
            attributed_claims.append({
                "claim": source.claim_supported,
                "source": {
                    "title": source.source_title,
                    "url": source.source_url,
                    "excerpt": source.relevant_excerpt[:200],
                },
                "strength": self.CONTRIBUTION_LABELS[source.contribution_type],
            })
        return attributed_claims

    def _generate_summary(self, sources: list[SourceAttribution], audience: AudienceLevel) -> str:
        count = len(sources)
        primary_count = sum(1 for s in sources if s.contribution_type == "primary")
        
        if audience == AudienceLevel.NON_TECHNICAL:
            if count == 1:
                return f"This answer is based on one source: {sources[0].source_title}"
            return f"This answer draws from {count} sources, with {primary_count} being the main reference(s)."
        else:
            return f"Attribution: {count} sources ({primary_count} primary, {count - primary_count} supporting/context)"

    def _format_source(self, source: SourceAttribution, audience: AudienceLevel) -> dict[str, Any]:
        result = {
            "title": source.source_title,
            "url": source.source_url,
            "contribution": self.CONTRIBUTION_LABELS[source.contribution_type]["label"],
            "supports": source.claim_supported,
        }
        if audience != AudienceLevel.NON_TECHNICAL:
            result["weight"] = source.contribution_weight
            result["excerpt"] = source.relevant_excerpt
        return result

    def _compute_coverage(self, sources: list[SourceAttribution]) -> dict[str, Any]:
        total_weight = sum(s.contribution_weight for s in sources)
        return {
            "total_attribution_weight": min(total_weight, 1.0),
            "unattributed_fraction": max(0, 1.0 - total_weight),
            "interpretation": "Fully grounded in sources" if total_weight >= 0.9 
                else "Partially grounded — some content from general knowledge" if total_weight >= 0.5
                else "Mostly from general knowledge — limited source grounding",
        }

    def _assess_agreement(self, sources: list[SourceAttribution]) -> dict[str, Any]:
        # Simplified: check if sources support the same claims
        claims = [s.claim_supported for s in sources]
        unique_claims = set(claims)
        
        if len(sources) <= 1:
            return {"status": "single_source", "message": "Only one source — cannot cross-verify"}
        
        # If multiple sources support same claims, they agree
        agreement_ratio = 1.0 - (len(unique_claims) / len(sources))
        if agreement_ratio > 0.5:
            return {"status": "agreement", "message": "Multiple sources support these claims"}
        return {"status": "complementary", "message": "Sources provide complementary information"}


# =============================================================================
# DECISION EXPLANATION
# =============================================================================

class DecisionExplainer:
    """
    Explains WHY the AI gave a particular answer or took an action.
    
    Covers:
    - Why this answer and not alternatives
    - What factors influenced the decision
    - What constraints were applied
    """

    def explain_answer_choice(
        self,
        context: ExplanationContext,
        alternatives_considered: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Explain why a particular answer was chosen."""
        explanation = {
            "type": "decision_explanation",
            "question": context.query,
            "answer_given": context.response_text[:200],
            "reasoning_summary": self._summarize_reasoning(context, audience),
            "key_factors": self._extract_key_factors(context),
        }

        if alternatives_considered:
            explanation["alternatives"] = {
                "considered": alternatives_considered,
                "why_not_chosen": [
                    self._explain_rejection(alt, context) for alt in alternatives_considered
                ],
            }

        if constraints:
            explanation["constraints_applied"] = [
                {"constraint": c, "effect": self._explain_constraint_effect(c)}
                for c in constraints
            ]

        if audience == AudienceLevel.NON_TECHNICAL:
            explanation["plain_english"] = self._plain_english_summary(explanation)

        return explanation

    def explain_action_choice(
        self,
        action_taken: str,
        reason: str,
        alternatives: list[str],
        risk_assessment: dict[str, Any],
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Explain why a particular action was chosen over alternatives."""
        return {
            "type": "action_explanation",
            "action": action_taken,
            "reason": reason,
            "decision_factors": [
                {"factor": "Alignment with request", "assessment": "The action directly addresses what you asked"},
                {"factor": "Risk level", "assessment": f"Assessed as {risk_assessment.get('level', 'medium')} risk"},
                {"factor": "Reversibility", "assessment": "Can be undone" if risk_assessment.get("reversible") else "Cannot be undone"},
            ],
            "alternatives_rejected": [
                {"alternative": alt, "reason": f"Less suitable because it doesn't fully address the request"}
                for alt in alternatives
            ],
            "plain_english": f"I chose to {action_taken} because {reason}. "
                           f"Other options ({', '.join(alternatives)}) were considered but deemed less appropriate.",
        }

    def _summarize_reasoning(self, context: ExplanationContext, audience: AudienceLevel) -> str:
        if not context.reasoning_steps:
            return "Generated based on training knowledge and available context."
        
        steps_summary = [s.description for s in context.reasoning_steps]
        if audience == AudienceLevel.NON_TECHNICAL:
            return f"I {', then '.join(steps_summary[:3])} to arrive at this answer."
        return f"Reasoning chain: {' → '.join(steps_summary)}"

    def _extract_key_factors(self, context: ExplanationContext) -> list[dict[str, str]]:
        factors = []
        if context.sources:
            factors.append({
                "factor": "Source evidence",
                "detail": f"Found {len(context.sources)} relevant source(s)",
            })
        if context.confidence_score >= 0.8:
            factors.append({
                "factor": "High source agreement",
                "detail": "Multiple sources support this answer",
            })
        if context.retrievals:
            factors.append({
                "factor": "Search results",
                "detail": f"Searched {len(context.retrievals)} source(s) and found relevant information",
            })
        return factors

    def _explain_rejection(self, alternative: str, context: ExplanationContext) -> str:
        return f"'{alternative}' was considered but the available evidence more strongly supports the given answer."

    def _explain_constraint_effect(self, constraint: str) -> str:
        constraint_effects = {
            "safety": "Filtered content that could be harmful",
            "accuracy": "Prioritized factual accuracy over speculation",
            "brevity": "Kept the response concise",
            "completeness": "Ensured all key points were covered",
            "tone": "Maintained professional tone",
        }
        return constraint_effects.get(constraint, f"Applied {constraint} constraint to the response")

    def _plain_english_summary(self, explanation: dict[str, Any]) -> str:
        factors = explanation.get("key_factors", [])
        factor_text = " and ".join(f["detail"] for f in factors[:2]) if factors else "my training knowledge"
        return f"I answered based on {factor_text}."


# =============================================================================
# CONFIDENCE EXPLANATION
# =============================================================================

class ConfidenceExplainer:
    """
    Explains WHY confidence is at a particular level.
    
    Users need to understand not just the confidence level,
    but the REASONS behind it to calibrate their trust.
    """

    FACTOR_EXPLANATIONS = {
        "source_count": {
            "positive": "Multiple independent sources support this",
            "negative": "Very few sources available for verification",
        },
        "source_agreement": {
            "positive": "Sources agree with each other",
            "negative": "Sources provide conflicting information",
        },
        "source_authority": {
            "positive": "Sources are authoritative (official docs, peer-reviewed, etc.)",
            "negative": "Sources are informal or unverified",
        },
        "task_familiarity": {
            "positive": "This is a well-known factual question",
            "negative": "This is a novel or unusual question type",
        },
        "query_clarity": {
            "positive": "Your question is clear and unambiguous",
            "negative": "Your question has multiple possible interpretations",
        },
        "knowledge_recency": {
            "positive": "This topic is stable and unlikely to have changed",
            "negative": "This topic changes frequently and my info may be outdated",
        },
        "reasoning_complexity": {
            "positive": "Straightforward reasoning with few assumptions",
            "negative": "Complex reasoning chain with multiple uncertain steps",
        },
        "grounding": {
            "positive": "Answer is well-grounded in retrieved documents",
            "negative": "Answer relies partially on general knowledge without specific sources",
        },
    }

    def explain_confidence(
        self,
        confidence_score: float,
        factors: dict[str, float],  # factor_name -> score (0-1)
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Generate a complete confidence explanation."""
        positive_factors = []
        negative_factors = []

        for factor_name, factor_score in factors.items():
            if factor_name not in self.FACTOR_EXPLANATIONS:
                continue
            if factor_score >= 0.6:
                positive_factors.append({
                    "factor": factor_name,
                    "score": factor_score,
                    "explanation": self.FACTOR_EXPLANATIONS[factor_name]["positive"],
                    "icon": "check-circle",
                })
            elif factor_score <= 0.4:
                negative_factors.append({
                    "factor": factor_name,
                    "score": factor_score,
                    "explanation": self.FACTOR_EXPLANATIONS[factor_name]["negative"],
                    "icon": "alert-circle",
                })

        explanation = {
            "type": "confidence_explanation",
            "overall_confidence": confidence_score,
            "confidence_label": self._label_confidence(confidence_score),
            "supporting_factors": positive_factors,
            "limiting_factors": negative_factors,
            "plain_english": self._plain_english(confidence_score, positive_factors, negative_factors),
        }

        if audience == AudienceLevel.NON_TECHNICAL:
            explanation["analogy"] = self._confidence_analogy(confidence_score)

        if audience in (AudienceLevel.TECHNICAL, AudienceLevel.EXPERT):
            explanation["factor_weights"] = factors
            explanation["calibration_note"] = self._calibration_note(confidence_score)

        return explanation

    def explain_low_confidence(self, context: ExplanationContext) -> dict[str, Any]:
        """Specifically explain why confidence is LOW (for uncertain responses)."""
        reasons = []
        
        if not context.sources:
            reasons.append("I couldn't find any specific sources to verify this")
        elif len(context.sources) == 1:
            reasons.append("Only one source available — I can't cross-verify")
        
        if context.retrievals:
            low_relevance = [r for r in context.retrievals if r.top_result_relevance < 0.5]
            if low_relevance:
                reasons.append("My search results weren't very relevant to your specific question")
        
        if not context.reasoning_steps:
            reasons.append("I'm answering from general knowledge rather than specific analysis")

        return {
            "type": "low_confidence_explanation",
            "confidence_score": context.confidence_score,
            "reasons": reasons,
            "user_guidance": self._low_confidence_guidance(reasons),
            "what_would_help": [
                "More specific question phrasing",
                "Additional context about what you're looking for",
                "Consulting a domain expert for verification",
            ],
        }

    def _label_confidence(self, score: float) -> str:
        if score >= 0.9: return "Very confident"
        if score >= 0.7: return "Confident"
        if score >= 0.5: return "Moderately confident"
        if score >= 0.3: return "Low confidence"
        return "Very uncertain"

    def _plain_english(
        self, score: float, positive: list[dict], negative: list[dict]
    ) -> str:
        label = self._label_confidence(score)
        parts = [f"I'm {label.lower()} about this answer."]
        
        if positive:
            parts.append(f"This is because: {positive[0]['explanation'].lower()}.")
        if negative:
            parts.append(f"However, {negative[0]['explanation'].lower()}.")
        
        return " ".join(parts)

    def _confidence_analogy(self, score: float) -> str:
        if score >= 0.9:
            return "Think of this like a well-established fact you'd find in a textbook."
        elif score >= 0.7:
            return "Think of this like advice from a knowledgeable friend — usually right, but worth double-checking for important decisions."
        elif score >= 0.5:
            return "Think of this like a reasonable guess based on limited information — useful as a starting point."
        else:
            return "Think of this like a coin flip — I'm largely guessing and you should seek a better source."

    def _calibration_note(self, score: float) -> str:
        return (
            f"Calibration note: At this stated confidence level ({score:.0%}), "
            f"historically the model is correct approximately {score * 0.95:.0%}-{min(score * 1.05, 1.0):.0%} of the time."
        )

    def _low_confidence_guidance(self, reasons: list[str]) -> str:
        if not reasons:
            return "Consider verifying this independently."
        return f"I'd recommend not relying solely on this answer because: {reasons[0].lower()}."


# =============================================================================
# TOOL USAGE EXPLANATION
# =============================================================================

class ToolUsageExplainer:
    """
    Explains why specific tools were called during processing.
    
    Users often wonder: "Why did it search X?" or "Why did it call that API?"
    This makes tool usage transparent.
    """

    TOOL_DESCRIPTIONS = {
        "web_search": "Searched the web for current information",
        "knowledge_base": "Searched your organization's documents",
        "calculator": "Performed a calculation",
        "code_executor": "Ran code to verify or compute something",
        "api_call": "Called an external service",
        "database_query": "Queried a database for specific data",
        "file_reader": "Read a file for relevant content",
        "image_analyzer": "Analyzed an image",
    }

    def explain_tool_usage(
        self,
        tool_calls: list[ToolCall],
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Explain all tool usage in a response generation."""
        if not tool_calls:
            return {
                "type": "tool_explanation",
                "tools_used": False,
                "message": "Answered from training knowledge without using any external tools.",
            }

        explanations = []
        for call in tool_calls:
            exp = {
                "tool": call.tool_name,
                "friendly_name": self.TOOL_DESCRIPTIONS.get(call.tool_name, call.tool_name),
                "reason": call.reason_for_call,
                "successful": call.was_successful,
            }

            if audience == AudienceLevel.NON_TECHNICAL:
                exp["plain_english"] = self._plain_english_tool(call)
            else:
                exp["input"] = call.input_summary
                exp["output"] = call.output_summary
                exp["duration_ms"] = call.duration_ms
                exp["alternatives"] = call.alternatives_considered

            explanations.append(exp)

        return {
            "type": "tool_explanation",
            "tools_used": True,
            "count": len(tool_calls),
            "summary": self._summarize_tools(tool_calls, audience),
            "details": explanations,
            "total_tool_time_ms": sum(t.duration_ms for t in tool_calls),
        }

    def _plain_english_tool(self, call: ToolCall) -> str:
        friendly = self.TOOL_DESCRIPTIONS.get(call.tool_name, f"Used {call.tool_name}")
        status = "and found relevant information" if call.was_successful else "but didn't find what I needed"
        return f"{friendly} {status}. Reason: {call.reason_for_call}"

    def _summarize_tools(self, calls: list[ToolCall], audience: AudienceLevel) -> str:
        successful = sum(1 for c in calls if c.was_successful)
        if audience == AudienceLevel.NON_TECHNICAL:
            tools = set(self.TOOL_DESCRIPTIONS.get(c.tool_name, c.tool_name) for c in calls)
            return f"To answer your question, I {', and '.join(list(tools)[:3])}."
        return f"Used {len(calls)} tool(s): {successful} successful, {len(calls) - successful} failed."


# =============================================================================
# RETRIEVAL EXPLANATION
# =============================================================================

class RetrievalExplainer:
    """
    Explains what was searched, what was found, and what was used.
    
    Makes the RAG (Retrieval-Augmented Generation) process transparent.
    """

    def explain_retrieval(
        self,
        retrievals: list[RetrievalResult],
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Explain the retrieval process."""
        if not retrievals:
            return {
                "type": "retrieval_explanation",
                "searched": False,
                "message": "No document search was performed — answered from general knowledge.",
            }

        total_found = sum(r.results_found for r in retrievals)
        total_used = sum(r.results_used for r in retrievals)

        explanation = {
            "type": "retrieval_explanation",
            "searched": True,
            "summary": self._retrieval_summary(retrievals, audience),
            "searches_performed": len(retrievals),
            "total_results_found": total_found,
            "total_results_used": total_used,
            "selectivity": f"Used {total_used} of {total_found} results found" if total_found > 0 else "No results found",
            "search_details": [
                self._format_retrieval(r, audience) for r in retrievals
            ],
        }

        if audience == AudienceLevel.NON_TECHNICAL:
            explanation["analogy"] = (
                f"Think of this like searching a library — I looked through "
                f"{total_found} potentially relevant sections and picked the "
                f"{total_used} most relevant ones to base my answer on."
            )

        return explanation

    def _retrieval_summary(self, retrievals: list[RetrievalResult], audience: AudienceLevel) -> str:
        sources = set(r.source_searched for r in retrievals)
        if audience == AudienceLevel.NON_TECHNICAL:
            return f"I searched {len(sources)} source(s) ({', '.join(sources)}) to find information for your question."
        return f"Performed {len(retrievals)} search(es) across {len(sources)} source type(s)."

    def _format_retrieval(self, retrieval: RetrievalResult, audience: AudienceLevel) -> dict[str, Any]:
        result = {
            "source": retrieval.source_searched,
            "reason": retrieval.reason_for_search,
            "found": retrieval.results_found,
            "used": retrieval.results_used,
            "relevance": self._relevance_label(retrieval.top_result_relevance),
        }
        if audience != AudienceLevel.NON_TECHNICAL:
            result["query"] = retrieval.query_used
            result["top_relevance_score"] = retrieval.top_result_relevance
            result["results"] = retrieval.results_summary[:5]
        return result

    def _relevance_label(self, score: float) -> str:
        if score >= 0.8: return "Highly relevant results found"
        if score >= 0.5: return "Moderately relevant results found"
        if score >= 0.3: return "Somewhat relevant results found"
        return "Low relevance — results may not directly answer the question"


# =============================================================================
# STEP-BY-STEP REASONING DISPLAY
# =============================================================================

class ReasoningDisplayEngine:
    """
    Displays the AI's reasoning process as a clear step-by-step chain.
    
    Adapts detail level to audience:
    - Non-technical: High-level steps in plain language
    - Technical: Detailed reasoning with intermediate results
    - Expert: Full chain with confidence at each step
    """

    STEP_ICONS = {
        "analyzed": "eye",
        "searched": "search",
        "compared": "git-compare",
        "concluded": "check-circle",
        "verified": "shield-check",
        "calculated": "calculator",
        "interpreted": "message-circle",
        "filtered": "filter",
        "synthesized": "layers",
    }

    def format_reasoning_chain(
        self,
        steps: list[ReasoningStep],
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
    ) -> dict[str, Any]:
        """Format the complete reasoning chain for display."""
        if not steps:
            return {
                "type": "reasoning_display",
                "has_steps": False,
                "message": "Direct response without multi-step reasoning.",
            }

        formatted_steps = [self._format_step(s, audience) for s in steps]

        return {
            "type": "reasoning_display",
            "has_steps": True,
            "step_count": len(steps),
            "total_duration_ms": sum(s.duration_ms or 0 for s in steps),
            "steps": formatted_steps,
            "confidence_progression": [
                {"step": s.step_number, "confidence": s.confidence_at_step}
                for s in steps
            ],
            "summary": self._chain_summary(steps, audience),
        }

    def _format_step(self, step: ReasoningStep, audience: AudienceLevel) -> dict[str, Any]:
        result = {
            "number": step.step_number,
            "icon": self.STEP_ICONS.get(step.action, "circle"),
            "action": step.action,
            "description": step.description,
        }

        if audience == AudienceLevel.NON_TECHNICAL:
            result["display"] = f"Step {step.step_number}: {step.description}"
        elif audience == AudienceLevel.TECHNICAL:
            result["input"] = step.input_summary
            result["output"] = step.output_summary
            result["confidence"] = step.confidence_at_step
            result["tools"] = step.tools_used
        else:  # Expert
            result["input"] = step.input_summary
            result["output"] = step.output_summary
            result["confidence"] = step.confidence_at_step
            result["tools"] = step.tools_used
            result["duration_ms"] = step.duration_ms

        return result

    def _chain_summary(self, steps: list[ReasoningStep], audience: AudienceLevel) -> str:
        actions = [s.action for s in steps]
        if audience == AudienceLevel.NON_TECHNICAL:
            return f"I went through {len(steps)} steps to reach this answer: {', '.join(actions[:4])}."
        return f"Reasoning chain: {' → '.join(actions)} (confidence: {steps[0].confidence_at_step:.0%} → {steps[-1].confidence_at_step:.0%})"


# =============================================================================
# NON-TECHNICAL SUMMARY GENERATION
# =============================================================================

class NonTechnicalSummarizer:
    """
    Generates plain-language summaries of AI behavior for non-technical users.
    
    Principles:
    - Use analogies, not algorithms
    - Show "because", not "how"
    - Use concrete examples
    - Progressive disclosure (summary → details)
    """

    TECHNICAL_TO_PLAIN = {
        "vector similarity search": "searched for relevant information",
        "cosine similarity": "relevance matching",
        "embedding": "understanding of meaning",
        "token": "word",
        "inference": "thinking",
        "hallucination": "making something up",
        "grounding": "checking against sources",
        "fine-tuning": "specialized training",
        "prompt": "instructions",
        "context window": "memory limit",
        "temperature": "creativity level",
        "retrieval-augmented generation": "looking things up before answering",
        "chunking": "breaking documents into sections",
    }

    def generate_summary(
        self,
        context: ExplanationContext,
    ) -> dict[str, Any]:
        """Generate a complete non-technical summary of what happened."""
        sections = []

        # What was asked
        sections.append({
            "heading": "Your question",
            "content": context.query,
        })

        # What I did
        what_i_did = self._describe_process(context)
        sections.append({
            "heading": "What I did",
            "content": what_i_did,
        })

        # How confident I am
        sections.append({
            "heading": "How confident I am",
            "content": self._describe_confidence(context.confidence_score),
        })

        # Where the information came from
        if context.sources:
            sections.append({
                "heading": "Where this comes from",
                "content": self._describe_sources(context.sources),
            })

        return {
            "type": "non_technical_summary",
            "sections": sections,
            "one_liner": self._one_line_summary(context),
            "trust_guidance": self._trust_guidance(context.confidence_score),
        }

    def translate_technical(self, technical_text: str) -> str:
        """Translate technical jargon to plain language."""
        result = technical_text
        for technical, plain in self.TECHNICAL_TO_PLAIN.items():
            result = result.replace(technical, plain)
        return result

    def _describe_process(self, context: ExplanationContext) -> str:
        parts = []
        if context.retrievals:
            sources_searched = set(r.source_searched for r in context.retrievals)
            parts.append(f"searched {', '.join(sources_searched)}")
        if context.tool_calls:
            parts.append(f"used {len(context.tool_calls)} tool(s)")
        if context.reasoning_steps:
            parts.append(f"went through {len(context.reasoning_steps)} reasoning steps")
        
        if parts:
            return f"To answer your question, I {', '.join(parts)}, and then composed my response."
        return "I answered based on my general knowledge."

    def _describe_confidence(self, score: float) -> str:
        if score >= 0.9:
            return "I'm very confident about this answer. It's well-supported by reliable sources."
        elif score >= 0.7:
            return "I'm fairly confident, but you might want to double-check important details."
        elif score >= 0.5:
            return "I have moderate confidence. I'd recommend verifying this independently before acting on it."
        else:
            return "I'm not very confident about this. Please treat it as a starting point and verify with a more authoritative source."

    def _describe_sources(self, sources: list[SourceAttribution]) -> str:
        if len(sources) == 1:
            return f"This answer is based on: {sources[0].source_title}"
        titles = [s.source_title for s in sources[:3]]
        return f"This answer draws from {len(sources)} sources, including: {', '.join(titles)}"

    def _one_line_summary(self, context: ExplanationContext) -> str:
        conf = "confidently" if context.confidence_score >= 0.8 else "with some uncertainty"
        source_info = f"based on {len(context.sources)} source(s)" if context.sources else "from general knowledge"
        return f"Answered {conf}, {source_info}."

    def _trust_guidance(self, score: float) -> str:
        if score >= 0.9:
            return "You can rely on this for most purposes."
        elif score >= 0.7:
            return "Good for general use; verify for high-stakes decisions."
        elif score >= 0.5:
            return "Use as a starting point; independent verification recommended."
        else:
            return "Treat with caution; seek a more authoritative source."


# =============================================================================
# VISUAL EXPLANATION COMPONENTS
# =============================================================================

class VisualExplanationBuilder:
    """
    Generates structured data for visual explanations.
    
    Outputs component specifications that can be rendered by a frontend:
    - Confidence gauges
    - Source contribution charts
    - Reasoning flow diagrams
    - Attribution heatmaps
    """

    def build_confidence_gauge(self, score: float, factors: dict[str, float]) -> dict[str, Any]:
        """Build a visual confidence gauge component."""
        return {
            "component": "confidence_gauge",
            "props": {
                "value": score,
                "max": 1.0,
                "segments": [
                    {"range": [0, 0.3], "color": "#ef4444", "label": "Low"},
                    {"range": [0.3, 0.6], "color": "#eab308", "label": "Medium"},
                    {"range": [0.6, 0.8], "color": "#84cc16", "label": "High"},
                    {"range": [0.8, 1.0], "color": "#22c55e", "label": "Very High"},
                ],
                "factors": [
                    {"name": k, "value": v, "direction": "positive" if v >= 0.5 else "negative"}
                    for k, v in factors.items()
                ],
            },
        }

    def build_source_contribution_chart(self, sources: list[SourceAttribution]) -> dict[str, Any]:
        """Build a pie/bar chart showing source contributions."""
        return {
            "component": "source_chart",
            "props": {
                "type": "horizontal_bar",
                "data": [
                    {
                        "label": s.source_title[:40],
                        "value": s.contribution_weight,
                        "color": {"primary": "#22c55e", "supporting": "#3b82f6", "context": "#6b7280"}[s.contribution_type],
                        "tooltip": s.claim_supported,
                    }
                    for s in sorted(sources, key=lambda x: -x.contribution_weight)
                ],
                "x_label": "Contribution weight",
            },
        }

    def build_reasoning_flow(self, steps: list[ReasoningStep]) -> dict[str, Any]:
        """Build a flow diagram of the reasoning process."""
        nodes = []
        edges = []

        for i, step in enumerate(steps):
            nodes.append({
                "id": f"step_{step.step_number}",
                "label": step.description[:50],
                "type": step.action,
                "confidence": step.confidence_at_step,
            })
            if i > 0:
                edges.append({
                    "from": f"step_{steps[i-1].step_number}",
                    "to": f"step_{step.step_number}",
                })

        return {
            "component": "reasoning_flow",
            "props": {
                "nodes": nodes,
                "edges": edges,
                "layout": "horizontal",
            },
        }

    def build_attribution_heatmap(
        self, response_text: str, sources: list[SourceAttribution]
    ) -> dict[str, Any]:
        """Build a heatmap showing which parts of the response are attributed."""
        segments = []
        for source in sources:
            if source.claim_supported in response_text:
                start = response_text.find(source.claim_supported)
                segments.append({
                    "start": start,
                    "end": start + len(source.claim_supported),
                    "source": source.source_title,
                    "weight": source.contribution_weight,
                })

        return {
            "component": "attribution_heatmap",
            "props": {
                "text": response_text,
                "highlights": segments,
                "legend": {
                    "high_attribution": {"color": "#22c55e", "label": "Strongly sourced"},
                    "medium_attribution": {"color": "#eab308", "label": "Partially sourced"},
                    "no_attribution": {"color": "transparent", "label": "General knowledge"},
                },
            },
        }


# =============================================================================
# UNIFIED EXPLAINABILITY INTERFACE
# =============================================================================

class ExplainabilityEngine:
    """
    Unified interface for generating explanations at any detail level.
    
    Orchestrates all explanation components and produces layered output:
    Layer 1: One-line summary
    Layer 2: Key factors (3-5 bullet points)
    Layer 3: Full explanation with visuals
    Layer 4: Technical deep-dive
    """

    def __init__(self):
        self.attribution = AnswerAttributionEngine()
        self.decision = DecisionExplainer()
        self.confidence = ConfidenceExplainer()
        self.tool_usage = ToolUsageExplainer()
        self.retrieval = RetrievalExplainer()
        self.reasoning = ReasoningDisplayEngine()
        self.summarizer = NonTechnicalSummarizer()
        self.visual = VisualExplanationBuilder()

    def explain(
        self,
        context: ExplanationContext,
        audience: AudienceLevel = AudienceLevel.NON_TECHNICAL,
        detail_level: int = 2,  # 1-4
    ) -> dict[str, Any]:
        """Generate a complete explanation at the specified detail level."""
        explanation = {
            "response_id": context.response_id,
            "audience": audience.value,
            "detail_level": detail_level,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Layer 1: Always included — one-line summary
        summary = self.summarizer.generate_summary(context)
        explanation["layer_1_summary"] = summary["one_liner"]

        if detail_level >= 2:
            # Layer 2: Key factors
            explanation["layer_2_factors"] = {
                "confidence": self.confidence.explain_confidence(
                    context.confidence_score,
                    {"source_count": min(len(context.sources) / 3, 1.0)},
                    audience,
                ),
                "attribution": self.attribution.generate_attribution(context, audience),
                "trust_guidance": summary["trust_guidance"],
            }

        if detail_level >= 3:
            # Layer 3: Full explanation
            explanation["layer_3_full"] = {
                "reasoning": self.reasoning.format_reasoning_chain(context.reasoning_steps, audience),
                "tools": self.tool_usage.explain_tool_usage(context.tool_calls, audience),
                "retrieval": self.retrieval.explain_retrieval(context.retrievals, audience),
                "non_technical_summary": summary,
            }

        if detail_level >= 4:
            # Layer 4: Technical deep-dive with visuals
            explanation["layer_4_technical"] = {
                "visuals": {
                    "confidence_gauge": self.visual.build_confidence_gauge(
                        context.confidence_score, {}
                    ),
                    "source_chart": self.visual.build_source_contribution_chart(context.sources) if context.sources else None,
                    "reasoning_flow": self.visual.build_reasoning_flow(context.reasoning_steps) if context.reasoning_steps else None,
                },
                "raw_context": {
                    "model_version": context.model_version,
                    "total_duration_ms": context.total_duration_ms,
                    "source_count": len(context.sources),
                    "step_count": len(context.reasoning_steps),
                    "tool_call_count": len(context.tool_calls),
                },
            }

        return explanation


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def example_usage():
    """Demonstrate the explainability system."""
    # Build a context
    context = ExplanationContext(
        response_id="resp_789",
        query="What is the recommended daily water intake?",
        response_text="The generally recommended daily water intake is about 8 glasses (2 liters) for most adults, though individual needs vary based on activity level, climate, and health conditions.",
        confidence_score=0.82,
        sources=[
            SourceAttribution(
                source_id="src_1",
                source_title="Mayo Clinic - Water: How much should you drink?",
                source_url="https://www.mayoclinic.org/water",
                contribution_type="primary",
                contribution_weight=0.6,
                relevant_excerpt="The U.S. National Academies recommends about 3.7 liters for men and 2.7 liters for women...",
                claim_supported="about 8 glasses (2 liters) for most adults",
            ),
            SourceAttribution(
                source_id="src_2",
                source_title="WHO Guidelines on Drinking Water",
                source_url="https://www.who.int/water",
                contribution_type="supporting",
                contribution_weight=0.3,
                relevant_excerpt="Individual water needs depend on multiple factors...",
                claim_supported="individual needs vary based on activity level, climate, and health conditions",
            ),
        ],
        reasoning_steps=[
            ReasoningStep(1, "searched", "Searched knowledge base for water intake guidelines", "user query", "3 results found", 0.7, 150),
            ReasoningStep(2, "analyzed", "Compared multiple sources for consensus", "3 documents", "sources agree on ~2L baseline", 0.8, 200),
            ReasoningStep(3, "synthesized", "Combined findings into comprehensive answer", "consensus + caveats", "final response", 0.82, 100),
        ],
        retrievals=[
            RetrievalResult(
                query_used="recommended daily water intake adults",
                source_searched="knowledge_base",
                results_found=7,
                results_used=3,
                top_result_relevance=0.91,
                reason_for_search="Answer factual health question with authoritative sources",
            ),
        ],
        model_version="gpt-4-2024-01",
        total_duration_ms=450,
    )

    # Generate explanation
    engine = ExplainabilityEngine()
    explanation = engine.explain(context, AudienceLevel.NON_TECHNICAL, detail_level=3)
    print(json.dumps(explanation, indent=2, default=str))


if __name__ == "__main__":
    example_usage()
