"""
Module 12: AI Observability - OpenTelemetry Tracing Implementation

Complete distributed tracing for AI systems using OpenTelemetry.
Covers: LLM calls, retrieval, reranking, tool execution, guardrails, agent steps.
"""

import time
import json
import hashlib
import uuid
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import StatusCode, SpanKind
from opentelemetry.trace.propagation import TraceContextTextMapPropagator
from opentelemetry.sdk.trace.sampling import (
    TraceIdRatioBased,
    ParentBasedTraceIdRatio,
    ALWAYS_ON,
)
from opentelemetry.semconv.resource import ResourceAttributes


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TracingConfig:
    service_name: str = "ai-agent-service"
    service_version: str = "1.0.0"
    environment: str = "production"
    otlp_endpoint: str = "http://localhost:4317"
    sampling_rate: float = 1.0  # 1.0 = trace everything
    max_attribute_length: int = 4096  # Truncate large values
    record_full_prompts: bool = False  # Privacy: store full prompts?
    record_full_responses: bool = False
    blob_storage_url: Optional[str] = None  # For large payload storage
    export_to_console: bool = False


# =============================================================================
# COST CALCULATOR
# =============================================================================

# Pricing per 1M tokens (as of 2024, approximate)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a model call."""
    pricing = MODEL_PRICING.get(model, {"input": 5.0, "output": 15.0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


# =============================================================================
# TRACER PROVIDER SETUP
# =============================================================================

class AITracerProvider:
    """Sets up OpenTelemetry tracing for AI workloads."""

    def __init__(self, config: TracingConfig):
        self.config = config
        self._provider = self._create_provider()
        trace.set_tracer_provider(self._provider)
        self.tracer = trace.get_tracer(
            instrumentor_name="ai-observability",
            instrumentor_version="1.0.0",
        )
        self.propagator = TraceContextTextMapPropagator()

    def _create_provider(self) -> TracerProvider:
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: self.config.service_name,
            ResourceAttributes.SERVICE_VERSION: self.config.service_version,
            "deployment.environment": self.config.environment,
        })

        # Sampling strategy
        if self.config.sampling_rate >= 1.0:
            sampler = ALWAYS_ON
        else:
            sampler = ParentBasedTraceIdRatio(self.config.sampling_rate)

        provider = TracerProvider(resource=resource, sampler=sampler)

        # OTLP exporter (Jaeger, Tempo, etc.)
        otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Console exporter for development
        if self.config.export_to_console:
            provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )

        return provider

    def shutdown(self):
        self._provider.shutdown()

    def inject_context(self, carrier: dict) -> dict:
        """Inject trace context into headers for cross-service propagation."""
        self.propagator.inject(carrier)
        return carrier

    def extract_context(self, carrier: dict):
        """Extract trace context from incoming headers."""
        return self.propagator.extract(carrier=carrier)


# =============================================================================
# AI SPAN BUILDERS
# =============================================================================

class AISpanAttributes:
    """Standard attribute keys for AI observability spans."""

    # GenAI semantic conventions
    GEN_AI_SYSTEM = "gen_ai.system"
    GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
    GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
    GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    GEN_AI_RESPONSE_ID = "gen_ai.response.id"
    GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
    GEN_AI_RESPONSE_FINISH_REASON = "gen_ai.response.finish_reasons"
    GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
    GEN_AI_USAGE_COST_USD = "gen_ai.usage.cost_usd"

    # Retrieval
    RETRIEVAL_QUERY = "ai.retrieval.query"
    RETRIEVAL_TOP_K = "ai.retrieval.top_k"
    RETRIEVAL_CHUNKS_RETURNED = "ai.retrieval.chunks_returned"
    RETRIEVAL_MAX_SCORE = "ai.retrieval.max_score"
    RETRIEVAL_MIN_SCORE = "ai.retrieval.min_score"
    RETRIEVAL_STRATEGY = "ai.retrieval.strategy"
    RETRIEVAL_INDEX = "ai.retrieval.index"

    # Reranking
    RERANK_MODEL = "ai.rerank.model"
    RERANK_INPUT_COUNT = "ai.rerank.input_count"
    RERANK_OUTPUT_COUNT = "ai.rerank.output_count"
    RERANK_TOP_SCORE = "ai.rerank.top_score"

    # Tool execution
    TOOL_NAME = "ai.tool.name"
    TOOL_ARGS = "ai.tool.arguments"
    TOOL_RESULT_STATUS = "ai.tool.result_status"
    TOOL_RESULT_SUMMARY = "ai.tool.result_summary"
    TOOL_ERROR = "ai.tool.error"

    # Agent
    AGENT_STEP_NUMBER = "ai.agent.step_number"
    AGENT_REASONING = "ai.agent.reasoning"
    AGENT_ACTION = "ai.agent.action"
    AGENT_TOTAL_STEPS = "ai.agent.total_steps"

    # Guardrail
    GUARDRAIL_NAME = "ai.guardrail.name"
    GUARDRAIL_DECISION = "ai.guardrail.decision"
    GUARDRAIL_REASON = "ai.guardrail.reason"
    GUARDRAIL_SCORE = "ai.guardrail.score"
    GUARDRAIL_THRESHOLD = "ai.guardrail.threshold"

    # Request context
    SESSION_ID = "ai.session.id"
    TENANT_ID = "ai.tenant.id"
    USER_ID = "ai.user.id"
    REQUEST_TYPE = "ai.request.type"


# =============================================================================
# AI TRACER - Main instrumentation class
# =============================================================================

class AITracer:
    """
    High-level tracing API for AI systems.
    Wraps OpenTelemetry with AI-specific span creation.
    """

    def __init__(self, provider: AITracerProvider):
        self.provider = provider
        self.tracer = provider.tracer
        self.config = provider.config

    def _truncate(self, value: str) -> str:
        """Truncate large attribute values."""
        if len(value) > self.config.max_attribute_length:
            return value[: self.config.max_attribute_length] + "...[TRUNCATED]"
        return value

    # -------------------------------------------------------------------------
    # ROOT SPAN: Full request lifecycle
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_request(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_type: str = "chat",
        parent_context=None,
    ):
        """Create root span for an AI request."""
        ctx = parent_context or context.get_current()

        with self.tracer.start_as_current_span(
            name="ai.request",
            kind=SpanKind.SERVER,
            context=ctx,
            attributes={
                AISpanAttributes.SESSION_ID: session_id or "",
                AISpanAttributes.TENANT_ID: tenant_id or "",
                AISpanAttributes.USER_ID: user_id or "",
                AISpanAttributes.REQUEST_TYPE: request_type,
                "ai.request.input_preview": self._truncate(user_input[:500]),
                "ai.request.input_length": len(user_input),
            },
        ) as span:
            request_context = RequestTraceContext(span=span, tracer=self)
            try:
                yield request_context
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                # Record final metrics
                span.set_attribute(
                    "ai.request.total_cost_usd", request_context.total_cost
                )
                span.set_attribute(
                    "ai.request.total_tokens", request_context.total_tokens
                )
                span.set_attribute(
                    "ai.request.total_llm_calls", request_context.llm_call_count
                )

    # -------------------------------------------------------------------------
    # LLM CALL SPAN
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_llm_call(
        self,
        model: str,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        provider: str = "openai",
    ):
        """Trace a single LLM inference call."""
        attributes = {
            AISpanAttributes.GEN_AI_SYSTEM: provider,
            AISpanAttributes.GEN_AI_REQUEST_MODEL: model,
            AISpanAttributes.GEN_AI_REQUEST_TEMPERATURE: temperature,
        }
        if max_tokens:
            attributes[AISpanAttributes.GEN_AI_REQUEST_MAX_TOKENS] = max_tokens

        # Optionally record prompts
        if self.config.record_full_prompts and system_prompt:
            attributes["gen_ai.request.system_prompt"] = self._truncate(system_prompt)
        if self.config.record_full_prompts and user_prompt:
            attributes["gen_ai.request.user_prompt"] = self._truncate(user_prompt)

        # Record token counts of input
        if system_prompt:
            attributes["gen_ai.request.system_prompt_length"] = len(system_prompt)
        if user_prompt:
            attributes["gen_ai.request.user_prompt_length"] = len(user_prompt)

        with self.tracer.start_as_current_span(
            name=f"ai.llm.{provider}.{model}",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ) as span:
            result = LLMCallResult(span=span, model=model, tracer=self)
            start_time = time.time()
            try:
                yield result
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.llm.latency_ms", latency_ms)

    # -------------------------------------------------------------------------
    # RETRIEVAL SPAN
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_retrieval(
        self,
        query: str,
        top_k: int = 10,
        strategy: str = "vector",
        index_name: str = "default",
    ):
        """Trace a retrieval operation (vector search, hybrid, etc.)."""
        with self.tracer.start_as_current_span(
            name="ai.retrieval",
            kind=SpanKind.CLIENT,
            attributes={
                AISpanAttributes.RETRIEVAL_QUERY: self._truncate(query),
                AISpanAttributes.RETRIEVAL_TOP_K: top_k,
                AISpanAttributes.RETRIEVAL_STRATEGY: strategy,
                AISpanAttributes.RETRIEVAL_INDEX: index_name,
            },
        ) as span:
            result = RetrievalResult(span=span, tracer=self)
            start_time = time.time()
            try:
                yield result
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.retrieval.latency_ms", latency_ms)

    # -------------------------------------------------------------------------
    # RERANK SPAN
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_rerank(
        self,
        model: str = "cross-encoder",
        input_count: int = 0,
    ):
        """Trace a reranking operation."""
        with self.tracer.start_as_current_span(
            name="ai.rerank",
            kind=SpanKind.CLIENT,
            attributes={
                AISpanAttributes.RERANK_MODEL: model,
                AISpanAttributes.RERANK_INPUT_COUNT: input_count,
            },
        ) as span:
            result = RerankResult(span=span)
            start_time = time.time()
            try:
                yield result
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.rerank.latency_ms", latency_ms)

    # -------------------------------------------------------------------------
    # TOOL CALL SPAN
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_tool_call(
        self,
        tool_name: str,
        tool_args: dict,
    ):
        """Trace a tool/function call execution."""
        with self.tracer.start_as_current_span(
            name=f"ai.tool.{tool_name}",
            kind=SpanKind.CLIENT,
            attributes={
                AISpanAttributes.TOOL_NAME: tool_name,
                AISpanAttributes.TOOL_ARGS: self._truncate(json.dumps(tool_args)),
            },
        ) as span:
            result = ToolCallResult(span=span, tracer=self)
            start_time = time.time()
            try:
                yield result
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.set_attribute(AISpanAttributes.TOOL_ERROR, str(e))
                span.set_attribute(AISpanAttributes.TOOL_RESULT_STATUS, "error")
                span.record_exception(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.tool.latency_ms", latency_ms)

    # -------------------------------------------------------------------------
    # AGENT STEP SPAN
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_agent_step(
        self,
        step_number: int,
        reasoning: Optional[str] = None,
        action: Optional[str] = None,
    ):
        """Trace a single agent reasoning step (think → act → observe)."""
        attributes = {
            AISpanAttributes.AGENT_STEP_NUMBER: step_number,
        }
        if reasoning:
            attributes[AISpanAttributes.AGENT_REASONING] = self._truncate(reasoning)
        if action:
            attributes[AISpanAttributes.AGENT_ACTION] = action

        with self.tracer.start_as_current_span(
            name=f"ai.agent.step_{step_number}",
            kind=SpanKind.INTERNAL,
            attributes=attributes,
        ) as span:
            result = AgentStepResult(span=span)
            start_time = time.time()
            try:
                yield result
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.agent.step_latency_ms", latency_ms)

    # -------------------------------------------------------------------------
    # GUARDRAIL SPAN
    # -------------------------------------------------------------------------

    @contextmanager
    def trace_guardrail(
        self,
        guardrail_name: str,
        check_type: str = "output",  # "input" or "output"
    ):
        """Trace a guardrail/safety check."""
        with self.tracer.start_as_current_span(
            name=f"ai.guardrail.{guardrail_name}",
            kind=SpanKind.INTERNAL,
            attributes={
                AISpanAttributes.GUARDRAIL_NAME: guardrail_name,
                "ai.guardrail.check_type": check_type,
            },
        ) as span:
            result = GuardrailResult(span=span)
            start_time = time.time()
            try:
                yield result
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("ai.guardrail.latency_ms", latency_ms)


# =============================================================================
# RESULT OBJECTS (used to record span data after operation completes)
# =============================================================================

@dataclass
class RequestTraceContext:
    """Accumulates metrics across the full request."""
    span: Any
    tracer: AITracer
    total_cost: float = 0.0
    total_tokens: int = 0
    llm_call_count: int = 0

    def record_response(self, response: str, citations: Optional[list] = None):
        if self.tracer.config.record_full_responses:
            self.span.set_attribute(
                "ai.response.content", self.tracer._truncate(response)
            )
        self.span.set_attribute("ai.response.length", len(response))
        if citations:
            self.span.set_attribute("ai.response.citation_count", len(citations))
            self.span.set_attribute(
                "ai.response.citations", json.dumps(citations[:10])
            )

    def record_feedback(self, score: float, comment: Optional[str] = None):
        self.span.set_attribute("ai.feedback.score", score)
        if comment:
            self.span.set_attribute("ai.feedback.comment", comment)

    def add_cost(self, cost: float, tokens: int):
        self.total_cost += cost
        self.total_tokens += tokens
        self.llm_call_count += 1


@dataclass
class LLMCallResult:
    """Records LLM call results into the span."""
    span: Any
    model: str
    tracer: AITracer

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        response_id: Optional[str] = None,
        finish_reason: str = "stop",
        response_model: Optional[str] = None,
        output: Optional[str] = None,
    ):
        cost = calculate_cost(self.model, input_tokens, output_tokens)

        self.span.set_attribute(AISpanAttributes.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
        self.span.set_attribute(AISpanAttributes.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)
        self.span.set_attribute(AISpanAttributes.GEN_AI_USAGE_COST_USD, cost)
        self.span.set_attribute(AISpanAttributes.GEN_AI_RESPONSE_FINISH_REASON, finish_reason)

        if response_id:
            self.span.set_attribute(AISpanAttributes.GEN_AI_RESPONSE_ID, response_id)
        if response_model:
            self.span.set_attribute(AISpanAttributes.GEN_AI_RESPONSE_MODEL, response_model)
        if output and self.tracer.config.record_full_responses:
            self.span.set_attribute("gen_ai.response.content", self.tracer._truncate(output))

        return cost


@dataclass
class RetrievalResult:
    """Records retrieval results into the span."""
    span: Any
    tracer: AITracer

    def record(
        self,
        chunks: list[dict],  # [{"id": ..., "score": ..., "text": ...}]
        total_available: Optional[int] = None,
    ):
        self.span.set_attribute(
            AISpanAttributes.RETRIEVAL_CHUNKS_RETURNED, len(chunks)
        )
        if chunks:
            scores = [c.get("score", 0) for c in chunks]
            self.span.set_attribute(AISpanAttributes.RETRIEVAL_MAX_SCORE, max(scores))
            self.span.set_attribute(AISpanAttributes.RETRIEVAL_MIN_SCORE, min(scores))
            self.span.set_attribute("ai.retrieval.mean_score", sum(scores) / len(scores))

            # Record chunk IDs and scores (not full text)
            chunk_summary = [
                {"id": c.get("id", ""), "score": c.get("score", 0)}
                for c in chunks[:20]
            ]
            self.span.set_attribute(
                "ai.retrieval.chunk_summary", json.dumps(chunk_summary)
            )

        if total_available:
            self.span.set_attribute("ai.retrieval.total_available", total_available)


@dataclass
class RerankResult:
    """Records reranking results."""
    span: Any

    def record(self, output_count: int, top_score: float, scores: list[float] = None):
        self.span.set_attribute(AISpanAttributes.RERANK_OUTPUT_COUNT, output_count)
        self.span.set_attribute(AISpanAttributes.RERANK_TOP_SCORE, top_score)
        if scores:
            self.span.set_attribute("ai.rerank.scores", json.dumps(scores[:20]))


@dataclass
class ToolCallResult:
    """Records tool execution results."""
    span: Any
    tracer: AITracer

    def record(self, status: str = "success", result_summary: str = "", output: Any = None):
        self.span.set_attribute(AISpanAttributes.TOOL_RESULT_STATUS, status)
        self.span.set_attribute(
            AISpanAttributes.TOOL_RESULT_SUMMARY,
            self.tracer._truncate(result_summary),
        )
        if output is not None:
            self.span.set_attribute(
                "ai.tool.output", self.tracer._truncate(str(output)[:1000])
            )


@dataclass
class AgentStepResult:
    """Records agent step observation."""
    span: Any

    def record_observation(self, observation: str):
        self.span.set_attribute("ai.agent.observation", observation[:2000])

    def record_action_result(self, result: str):
        self.span.set_attribute("ai.agent.action_result", result[:2000])


@dataclass
class GuardrailResult:
    """Records guardrail decision."""
    span: Any

    def record(
        self,
        decision: str,  # "allow", "block", "warn", "modify"
        reason: str = "",
        score: Optional[float] = None,
        threshold: Optional[float] = None,
    ):
        self.span.set_attribute(AISpanAttributes.GUARDRAIL_DECISION, decision)
        if reason:
            self.span.set_attribute(AISpanAttributes.GUARDRAIL_REASON, reason)
        if score is not None:
            self.span.set_attribute(AISpanAttributes.GUARDRAIL_SCORE, score)
        if threshold is not None:
            self.span.set_attribute(AISpanAttributes.GUARDRAIL_THRESHOLD, threshold)

        if decision == "block":
            self.span.add_event("guardrail_blocked", {"reason": reason})


# =============================================================================
# TRACE CONTEXT PROPAGATION HELPERS
# =============================================================================

class TraceContextPropagator:
    """Helpers for propagating trace context across service boundaries."""

    def __init__(self, provider: AITracerProvider):
        self.provider = provider

    def inject_into_headers(self, headers: Optional[dict] = None) -> dict:
        """Inject current trace context into HTTP headers."""
        headers = headers or {}
        self.provider.inject_context(headers)
        return headers

    def extract_from_headers(self, headers: dict):
        """Extract trace context from incoming HTTP headers."""
        return self.provider.extract_context(headers)

    def inject_into_message(self, message: dict) -> dict:
        """Inject trace context into a message (queue, event)."""
        carrier = {}
        self.provider.inject_context(carrier)
        message["_trace_context"] = carrier
        return message

    def extract_from_message(self, message: dict):
        """Extract trace context from a message."""
        carrier = message.get("_trace_context", {})
        return self.provider.extract_context(carrier)


# =============================================================================
# SAMPLING STRATEGIES
# =============================================================================

class AISampler:
    """
    Custom sampling strategies for AI workloads.
    
    Strategies:
    1. Always sample errors
    2. Always sample slow requests
    3. Always sample high-cost requests
    4. Sample a percentage of normal requests
    5. Always sample negative feedback
    """

    @staticmethod
    def cost_based_sampler(cost_threshold: float = 0.10):
        """Always sample requests that exceed cost threshold."""
        # In practice, implement as a custom SpanProcessor that checks
        # cost after the fact and exports even if initially not sampled.
        # OpenTelemetry's tail-based sampling requires a collector.
        pass

    @staticmethod
    def error_always_sampler():
        """Always export spans that have errors (tail-based)."""
        pass

    @staticmethod
    def get_head_sampler(rate: float) -> ParentBasedTraceIdRatio:
        """Standard head-based sampling with parent propagation."""
        return ParentBasedTraceIdRatio(rate)


# =============================================================================
# EXAMPLE: Full RAG Agent Traced End-to-End
# =============================================================================

def example_traced_rag_agent():
    """
    Demonstrates full tracing of a RAG agent request.
    Shows parent-child span relationships and attribute recording.
    """

    # Setup
    config = TracingConfig(
        service_name="rag-agent",
        environment="development",
        export_to_console=True,
        record_full_prompts=True,
        record_full_responses=True,
        sampling_rate=1.0,
    )
    provider = AITracerProvider(config)
    ai_tracer = AITracer(provider)

    # Simulate a user request
    user_query = "What are the benefits of using vector databases for RAG?"

    with ai_tracer.trace_request(
        user_input=user_query,
        session_id="session-abc-123",
        tenant_id="tenant-acme",
        user_id="user-42",
    ) as request_ctx:

        # Step 1: Query rewriting (would be its own span in production)
        rewritten_query = "vector database benefits RAG retrieval augmented generation"

        # Step 2: Retrieval
        with ai_tracer.trace_retrieval(
            query=rewritten_query,
            top_k=10,
            strategy="hybrid",
            index_name="knowledge-base-v2",
        ) as retrieval:
            # Simulate retrieval results
            chunks = [
                {"id": "doc-1-chunk-3", "score": 0.92, "text": "Vector databases enable..."},
                {"id": "doc-5-chunk-1", "score": 0.87, "text": "Benefits include fast..."},
                {"id": "doc-2-chunk-7", "score": 0.81, "text": "Compared to keyword..."},
                {"id": "doc-9-chunk-2", "score": 0.73, "text": "Scalability of vector..."},
                {"id": "doc-3-chunk-4", "score": 0.68, "text": "Some limitations..."},
            ]
            retrieval.record(chunks=chunks, total_available=1500)

        # Step 3: Reranking
        with ai_tracer.trace_rerank(model="cohere-rerank-v3", input_count=5) as rerank:
            reranked_scores = [0.95, 0.89, 0.82]
            rerank.record(output_count=3, top_score=0.95, scores=reranked_scores)

        # Step 4: LLM Call
        system_prompt = "You are a helpful assistant. Answer based on the provided context."
        context_text = "\n".join([c["text"] for c in chunks[:3]])
        full_prompt = f"Context:\n{context_text}\n\nQuestion: {user_query}"

        with ai_tracer.trace_llm_call(
            model="gpt-4o",
            system_prompt=system_prompt,
            user_prompt=full_prompt,
            temperature=0.1,
            max_tokens=1000,
            provider="openai",
        ) as llm_result:
            # Simulate model response
            cost = llm_result.record(
                input_tokens=1850,
                output_tokens=320,
                response_id="chatcmpl-abc123",
                finish_reason="stop",
                output="Vector databases offer several benefits for RAG systems...",
            )
            request_ctx.add_cost(cost, 1850 + 320)

        # Step 5: Guardrail check
        with ai_tracer.trace_guardrail(
            guardrail_name="groundedness_check",
            check_type="output",
        ) as guardrail:
            guardrail.record(
                decision="allow",
                score=0.91,
                threshold=0.7,
                reason="All claims supported by retrieved context",
            )

        # Record final response
        request_ctx.record_response(
            response="Vector databases offer several benefits for RAG systems...",
            citations=["doc-1-chunk-3", "doc-5-chunk-1"],
        )

    # Cleanup
    provider.shutdown()


# =============================================================================
# EXAMPLE: Agentic Workflow with Tool Calls
# =============================================================================

def example_traced_agent_with_tools():
    """Demonstrates tracing an agent that uses tools across multiple steps."""

    config = TracingConfig(
        service_name="tool-agent",
        export_to_console=True,
        sampling_rate=1.0,
    )
    provider = AITracerProvider(config)
    ai_tracer = AITracer(provider)

    user_query = "What's the weather in NYC and should I bring an umbrella?"

    with ai_tracer.trace_request(
        user_input=user_query,
        session_id="session-xyz",
        tenant_id="tenant-acme",
    ) as request_ctx:

        # Agent Step 1: Decide to call weather tool
        with ai_tracer.trace_agent_step(
            step_number=1,
            reasoning="User wants weather info for NYC. I should call the weather tool.",
            action="call_tool:get_weather",
        ) as step:

            # LLM decides to use tool
            with ai_tracer.trace_llm_call(
                model="gpt-4o-mini", temperature=0.0, provider="openai"
            ) as llm:
                cost = llm.record(input_tokens=500, output_tokens=50, finish_reason="tool_calls")
                request_ctx.add_cost(cost, 550)

            # Execute tool
            with ai_tracer.trace_tool_call(
                tool_name="get_weather",
                tool_args={"city": "New York", "units": "fahrenheit"},
            ) as tool:
                # Simulate tool execution
                tool.record(
                    status="success",
                    result_summary="72°F, 60% chance of rain",
                    output={"temp": 72, "rain_chance": 0.6, "conditions": "partly cloudy"},
                )

            step.record_observation("Weather data retrieved: 72°F, 60% rain chance")

        # Agent Step 2: Generate final answer
        with ai_tracer.trace_agent_step(
            step_number=2,
            reasoning="I have the weather data. 60% rain chance means umbrella recommended.",
            action="generate_response",
        ) as step:

            with ai_tracer.trace_llm_call(
                model="gpt-4o-mini", temperature=0.3, provider="openai"
            ) as llm:
                cost = llm.record(
                    input_tokens=700,
                    output_tokens=150,
                    finish_reason="stop",
                    output="It's 72°F in NYC with a 60% chance of rain. Yes, bring an umbrella!",
                )
                request_ctx.add_cost(cost, 850)

        # Record final
        request_ctx.record_response(
            response="It's 72°F in NYC with a 60% chance of rain. Yes, bring an umbrella!"
        )

    provider.shutdown()


# =============================================================================
# CROSS-SERVICE PROPAGATION EXAMPLE
# =============================================================================

def example_cross_service_propagation():
    """Shows how to propagate trace context between microservices."""

    config = TracingConfig(service_name="api-gateway", export_to_console=True)
    provider = AITracerProvider(config)
    ai_tracer = AITracer(provider)
    propagator = TraceContextPropagator(provider)

    # Service A: API Gateway creates root span
    with ai_tracer.trace_request(
        user_input="Find documents about AI safety",
        tenant_id="tenant-1",
    ) as request_ctx:

        # Prepare headers for downstream service call
        headers = propagator.inject_into_headers()
        print(f"Propagated headers: {headers}")
        # headers now contains: {'traceparent': '00-<trace_id>-<span_id>-01'}

        # Service B would extract these headers:
        # ctx = propagator.extract_from_headers(headers)
        # with tracer.start_as_current_span("downstream_op", context=ctx):
        #     ...

        # For async messaging (queues):
        message = {"query": "AI safety", "top_k": 10}
        message = propagator.inject_into_message(message)
        print(f"Message with trace context: {message.keys()}")

    provider.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: Traced RAG Agent")
    print("=" * 60)
    example_traced_rag_agent()

    print("\n" + "=" * 60)
    print("Example 2: Traced Agent with Tools")
    print("=" * 60)
    example_traced_agent_with_tools()

    print("\n" + "=" * 60)
    print("Example 3: Cross-Service Propagation")
    print("=" * 60)
    example_cross_service_propagation()
