"""
End-to-End RAG Pipeline — Production Implementation

Complete pipeline orchestrating:
- Query classification
- Query rewriting
- Hybrid retrieval
- Reranking
- Context assembly with token budget
- LLM generation with citations
- Groundedness verification
- Response formatting
- Full observability hooks

Dependencies:
    pip install openai tiktoken pydantic numpy
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

import tiktoken
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Domain Models ─────────────────────────────────────────────────────────────


class QueryType(str, Enum):
    FACTUAL = "factual"          # Simple fact lookup
    ANALYTICAL = "analytical"    # Requires synthesis/comparison
    PROCEDURAL = "procedural"    # How-to, step-by-step
    CONVERSATIONAL = "conversational"  # Chit-chat, no retrieval needed
    CLARIFICATION = "clarification"    # Ambiguous, needs clarification


class PipelineStage(str, Enum):
    CLASSIFY = "classify"
    REWRITE = "rewrite"
    RETRIEVE = "retrieve"
    RERANK = "rerank"
    ASSEMBLE = "assemble"
    GENERATE = "generate"
    VERIFY = "verify"
    FORMAT = "format"


class ObservabilityEvent(BaseModel):
    """Event emitted at each pipeline stage for tracing."""
    trace_id: str
    stage: PipelineStage
    duration_ms: float
    input_summary: str = ""
    output_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGRequest(BaseModel):
    """User request to the RAG pipeline."""
    query: str
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    user_id: str = ""
    user_acl_groups: list[str] = Field(default_factory=list)
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int = 1024
    temperature: float = 0.1
    include_citations: bool = True
    verify_groundedness: bool = True


class RAGResponse(BaseModel):
    """Complete RAG pipeline response."""
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    query_type: QueryType = QueryType.FACTUAL
    rewritten_query: str = ""
    groundedness_score: Optional[float] = None
    is_grounded: bool = True
    chunks_used: int = 0
    total_tokens_used: int = 0
    latency_ms: float = 0.0
    trace_id: str = ""
    stage_timings: dict[str, float] = Field(default_factory=dict)
    confidence: str = "high"  # high, medium, low


# ─── Query Classifier ─────────────────────────────────────────────────────────


class QueryClassifier:
    """
    Classify query to determine retrieval strategy.
    Uses LLM for complex classification, rules for obvious cases.
    """

    # Rule-based patterns for fast classification
    CONVERSATIONAL_PATTERNS = ["hello", "hi", "thanks", "thank you", "bye", "how are you"]
    PROCEDURAL_KEYWORDS = ["how to", "how do i", "steps to", "guide for", "tutorial"]

    def classify(self, query: str) -> QueryType:
        """Classify query type — rules first, LLM fallback."""
        query_lower = query.lower().strip()

        # Rule-based fast path
        if any(query_lower.startswith(p) or query_lower == p for p in self.CONVERSATIONAL_PATTERNS):
            return QueryType.CONVERSATIONAL

        if any(kw in query_lower for kw in self.PROCEDURAL_KEYWORDS):
            return QueryType.PROCEDURAL

        if len(query_lower.split()) < 3 and query_lower.endswith("?"):
            return QueryType.FACTUAL

        if any(kw in query_lower for kw in ["compare", "difference", "vs", "pros and cons", "analyze"]):
            return QueryType.ANALYTICAL

        # Default to factual for most queries
        return QueryType.FACTUAL

    def classify_with_llm(self, query: str) -> QueryType:
        """LLM-based classification for ambiguous queries."""
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the user's query into one of these categories:\n"
                        "- factual: Simple fact lookup\n"
                        "- analytical: Requires comparison or synthesis\n"
                        "- procedural: How-to or step-by-step\n"
                        "- conversational: Greeting or chit-chat\n"
                        "- clarification: Too ambiguous to answer\n"
                        "Return ONLY the category name."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=20,
        )

        category = response.choices[0].message.content.strip().lower()
        try:
            return QueryType(category)
        except ValueError:
            return QueryType.FACTUAL


# ─── Context Assembler ─────────────────────────────────────────────────────────


class ContextAssembler:
    """
    Assemble retrieved chunks into a context string that fits within token budget.
    Handles deduplication, ordering, and truncation.
    """

    def __init__(self, max_context_tokens: int = 3000, model: str = "cl100k_base"):
        self.max_context_tokens = max_context_tokens
        self.encoding = tiktoken.get_encoding(model)

    def assemble(
        self,
        chunks: list[dict[str, Any]],
        query_type: QueryType = QueryType.FACTUAL,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Assemble context from chunks within token budget.
        Returns (context_string, chunks_used).
        """
        if not chunks:
            return "", []

        # Deduplicate by content hash
        seen_hashes = set()
        unique_chunks = []
        for chunk in chunks:
            content_hash = hash(chunk.get("content", ""))
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_chunks.append(chunk)

        # Order by relevance (already sorted by retrieval score)
        # For analytical queries, also consider diversity
        if query_type == QueryType.ANALYTICAL:
            unique_chunks = self._diversify(unique_chunks)

        # Build context within token budget
        context_parts = []
        chunks_used = []
        tokens_used = 0

        for i, chunk in enumerate(unique_chunks):
            content = chunk.get("content", "")
            source = chunk.get("source_id", "unknown")
            formatted = f"[{i + 1}] (Source: {source})\n{content}"

            chunk_tokens = len(self.encoding.encode(formatted))

            if tokens_used + chunk_tokens > self.max_context_tokens:
                # Try to fit a truncated version
                remaining_budget = self.max_context_tokens - tokens_used - 20  # buffer
                if remaining_budget > 100:
                    truncated = self._truncate_to_tokens(formatted, remaining_budget)
                    context_parts.append(truncated)
                    chunks_used.append(chunk)
                break

            context_parts.append(formatted)
            chunks_used.append(chunk)
            tokens_used += chunk_tokens

        context = "\n\n---\n\n".join(context_parts)
        logger.info(f"Assembled context: {len(chunks_used)} chunks, ~{tokens_used} tokens")
        return context, chunks_used

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoding.decode(tokens[:max_tokens]) + "..."

    def _diversify(self, chunks: list[dict]) -> list[dict]:
        """For analytical queries, ensure diversity of sources."""
        # Simple: interleave chunks from different sources
        by_source: dict[str, list] = {}
        for chunk in chunks:
            source = chunk.get("source_id", "unknown")
            by_source.setdefault(source, []).append(chunk)

        diversified = []
        source_iters = {k: iter(v) for k, v in by_source.items()}
        while source_iters:
            exhausted = []
            for source, it in source_iters.items():
                try:
                    diversified.append(next(it))
                except StopIteration:
                    exhausted.append(source)
            for source in exhausted:
                del source_iters[source]

        return diversified


# ─── LLM Generator ────────────────────────────────────────────────────────────


class LLMGenerator:
    """
    Generate grounded answers using LLM with retrieved context.
    Includes citation injection and confidence signaling.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant. Answer the user's question using ONLY the provided context.

Rules:
- Only use information from the provided context
- If the context doesn't contain enough information, say "I don't have enough information to answer this fully"
- Cite your sources using [1], [2], etc. matching the context numbers
- Be concise and direct
- If you're uncertain about something, express that uncertainty
- Never make up information not present in the context

Context:
{context}"""

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature

    def generate(
        self,
        query: str,
        context: str,
        conversation_history: list[dict[str, str]] | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
    ) -> tuple[str, int]:
        """
        Generate a grounded answer.
        Returns (answer, total_tokens_used).
        """
        from openai import OpenAI
        client = OpenAI()

        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(context=context)
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history for multi-turn
        if conversation_history:
            for msg in conversation_history[-4:]:  # Last 4 turns
                messages.append(msg)

        messages.append({"role": "user", "content": query})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens,
        )

        answer = response.choices[0].message.content.strip()
        total_tokens = response.usage.total_tokens if response.usage else 0

        return answer, total_tokens


# ─── Groundedness Verifier ────────────────────────────────────────────────────


class GroundednessVerifier:
    """
    Verify that the generated answer is grounded in the retrieved context.
    Uses LLM-as-judge to check each claim.
    """

    def verify(self, answer: str, context: str) -> tuple[float, bool, list[str]]:
        """
        Verify groundedness of answer against context.
        Returns (score 0-1, is_grounded, list_of_ungrounded_claims).
        """
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a fact-checking judge. Given an ANSWER and the CONTEXT it was generated from, "
                        "evaluate whether every claim in the answer is supported by the context.\n\n"
                        "Respond in this exact format:\n"
                        "SCORE: <0.0 to 1.0>\n"
                        "GROUNDED: <yes/no>\n"
                        "UNGROUNDED_CLAIMS:\n"
                        "- <claim 1 not supported>\n"
                        "- <claim 2 not supported>\n"
                        "(or 'none' if all claims are grounded)"
                    ),
                },
                {
                    "role": "user",
                    "content": f"CONTEXT:\n{context}\n\nANSWER:\n{answer}",
                },
            ],
            temperature=0.0,
            max_tokens=300,
        )

        result = response.choices[0].message.content.strip()
        return self._parse_verification(result)

    def _parse_verification(self, result: str) -> tuple[float, bool, list[str]]:
        """Parse the verification response."""
        score = 1.0
        is_grounded = True
        ungrounded_claims = []

        for line in result.split("\n"):
            line = line.strip()
            if line.startswith("SCORE:"):
                try:
                    score = float(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.startswith("GROUNDED:"):
                is_grounded = "yes" in line.lower()
            elif line.startswith("- ") and "none" not in line.lower():
                ungrounded_claims.append(line[2:])

        return score, is_grounded, ungrounded_claims


# ─── Response Formatter ────────────────────────────────────────────────────────


class ResponseFormatter:
    """Format the final response with citations and metadata."""

    def format(
        self,
        answer: str,
        citations: list[dict[str, Any]],
        include_citations: bool = True,
    ) -> str:
        """Format answer with optional citation appendix."""
        if not include_citations or not citations:
            return answer

        # Add citation appendix
        citation_lines = ["\n\n---\n**Sources:**"]
        for cite in citations:
            cite_id = cite.get("citation_id", "?")
            source = cite.get("source_title", cite.get("source_id", "Unknown"))
            section = cite.get("section_title", "")
            page = cite.get("page_number")

            ref = f"[{cite_id}] {source}"
            if section:
                ref += f" — {section}"
            if page:
                ref += f" (p.{page})"
            citation_lines.append(ref)

        return answer + "\n".join(citation_lines)


# ─── Observability Hook ───────────────────────────────────────────────────────


class PipelineObserver:
    """
    Observability hooks for the RAG pipeline.
    Captures timing, inputs/outputs, and errors at each stage.
    """

    def __init__(self):
        self.events: list[ObservabilityEvent] = []
        self._callbacks: list[Callable[[ObservabilityEvent], None]] = []

    def register_callback(self, callback: Callable[[ObservabilityEvent], None]) -> None:
        """Register an external callback (e.g., send to OpenTelemetry, Datadog)."""
        self._callbacks.append(callback)

    def emit(self, event: ObservabilityEvent) -> None:
        """Emit an observability event."""
        self.events.append(event)
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Observer callback failed: {e}")

    def get_trace(self, trace_id: str) -> list[ObservabilityEvent]:
        """Get all events for a trace."""
        return [e for e in self.events if e.trace_id == trace_id]

    def print_trace(self, trace_id: str) -> None:
        """Pretty-print a pipeline trace."""
        events = self.get_trace(trace_id)
        total_ms = sum(e.duration_ms for e in events)
        print(f"\n{'='*60}")
        print(f"Trace: {trace_id} | Total: {total_ms:.1f}ms")
        print(f"{'='*60}")
        for event in events:
            pct = (event.duration_ms / total_ms * 100) if total_ms > 0 else 0
            print(f"  {event.stage.value:<12} {event.duration_ms:>7.1f}ms ({pct:>5.1f}%) | {event.output_summary}")
        print(f"{'='*60}\n")


# ─── Main RAG Pipeline ────────────────────────────────────────────────────────


class RAGPipeline:
    """
    End-to-end RAG pipeline orchestrating all components.

    Pipeline stages:
    1. Query Classification
    2. Query Rewriting (if needed)
    3. Retrieval (hybrid)
    4. Reranking
    5. Context Assembly (with token budget)
    6. LLM Generation (with citations)
    7. Groundedness Verification
    8. Response Formatting
    """

    def __init__(
        self,
        retrieval_service=None,
        classifier: QueryClassifier | None = None,
        assembler: ContextAssembler | None = None,
        generator: LLMGenerator | None = None,
        verifier: GroundednessVerifier | None = None,
        formatter: ResponseFormatter | None = None,
        observer: PipelineObserver | None = None,
        # Config
        generation_model: str = "gpt-4o",
        max_context_tokens: int = 3000,
        retrieval_top_k: int = 10,
        rerank_top_k: int = 5,
    ):
        self.retrieval_service = retrieval_service
        self.classifier = classifier or QueryClassifier()
        self.assembler = assembler or ContextAssembler(max_context_tokens=max_context_tokens)
        self.generator = generator or LLMGenerator(model=generation_model)
        self.verifier = verifier or GroundednessVerifier()
        self.formatter = formatter or ResponseFormatter()
        self.observer = observer or PipelineObserver()

        self.retrieval_top_k = retrieval_top_k
        self.rerank_top_k = rerank_top_k

    def run(self, request: RAGRequest) -> RAGResponse:
        """
        Execute the complete RAG pipeline.
        """
        trace_id = str(uuid.uuid4())[:8]
        pipeline_start = time.perf_counter()
        stage_timings = {}

        logger.info(f"[{trace_id}] RAG pipeline started: '{request.query[:50]}...'")

        # ─── Stage 1: Query Classification ─────────────────────────────
        stage_start = time.perf_counter()
        query_type = self.classifier.classify(request.query)
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["classify"] = stage_ms

        self.observer.emit(ObservabilityEvent(
            trace_id=trace_id,
            stage=PipelineStage.CLASSIFY,
            duration_ms=stage_ms,
            input_summary=request.query[:50],
            output_summary=f"type={query_type.value}",
        ))

        # Short-circuit for conversational queries
        if query_type == QueryType.CONVERSATIONAL:
            return RAGResponse(
                answer="I'm here to help with questions about our knowledge base. What would you like to know?",
                query_type=query_type,
                trace_id=trace_id,
                latency_ms=(time.perf_counter() - pipeline_start) * 1000,
                stage_timings=stage_timings,
            )

        # ─── Stage 2: Query Rewriting ─────────────────────────────────
        stage_start = time.perf_counter()
        rewritten_query = self._rewrite_query(request.query, request.conversation_history)
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["rewrite"] = stage_ms

        self.observer.emit(ObservabilityEvent(
            trace_id=trace_id,
            stage=PipelineStage.REWRITE,
            duration_ms=stage_ms,
            input_summary=request.query[:50],
            output_summary=rewritten_query[:50],
        ))

        # ─── Stage 3: Retrieval ───────────────────────────────────────
        stage_start = time.perf_counter()
        retrieved_chunks = self._retrieve(rewritten_query, request)
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["retrieve"] = stage_ms

        self.observer.emit(ObservabilityEvent(
            trace_id=trace_id,
            stage=PipelineStage.RETRIEVE,
            duration_ms=stage_ms,
            output_summary=f"{len(retrieved_chunks)} chunks retrieved",
        ))

        # ─── Stage 4: Reranking ───────────────────────────────────────
        stage_start = time.perf_counter()
        reranked_chunks = self._rerank(rewritten_query, retrieved_chunks)
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["rerank"] = stage_ms

        self.observer.emit(ObservabilityEvent(
            trace_id=trace_id,
            stage=PipelineStage.RERANK,
            duration_ms=stage_ms,
            output_summary=f"{len(reranked_chunks)} chunks after reranking",
        ))

        # ─── Stage 5: Context Assembly ────────────────────────────────
        stage_start = time.perf_counter()
        context, chunks_used = self.assembler.assemble(reranked_chunks, query_type)
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["assemble"] = stage_ms

        self.observer.emit(ObservabilityEvent(
            trace_id=trace_id,
            stage=PipelineStage.ASSEMBLE,
            duration_ms=stage_ms,
            output_summary=f"{len(chunks_used)} chunks, {len(context)} chars",
        ))

        # Handle no context
        if not context:
            return RAGResponse(
                answer="I couldn't find relevant information to answer your question. Could you rephrase or provide more details?",
                query_type=query_type,
                rewritten_query=rewritten_query,
                trace_id=trace_id,
                confidence="low",
                latency_ms=(time.perf_counter() - pipeline_start) * 1000,
                stage_timings=stage_timings,
            )

        # ─── Stage 6: Generation ──────────────────────────────────────
        stage_start = time.perf_counter()
        answer, tokens_used = self.generator.generate(
            query=request.query,
            context=context,
            conversation_history=request.conversation_history or None,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["generate"] = stage_ms

        self.observer.emit(ObservabilityEvent(
            trace_id=trace_id,
            stage=PipelineStage.GENERATE,
            duration_ms=stage_ms,
            output_summary=f"{len(answer)} chars, {tokens_used} tokens",
        ))

        # ─── Stage 7: Groundedness Verification ───────────────────────
        groundedness_score = None
        is_grounded = True

        if request.verify_groundedness:
            stage_start = time.perf_counter()
            groundedness_score, is_grounded, ungrounded = self.verifier.verify(answer, context)
            stage_ms = (time.perf_counter() - stage_start) * 1000
            stage_timings["verify"] = stage_ms

            self.observer.emit(ObservabilityEvent(
                trace_id=trace_id,
                stage=PipelineStage.VERIFY,
                duration_ms=stage_ms,
                output_summary=f"score={groundedness_score:.2f}, grounded={is_grounded}",
                metadata={"ungrounded_claims": ungrounded},
            ))

            if not is_grounded:
                logger.warning(f"[{trace_id}] Answer not fully grounded. Ungrounded: {ungrounded}")

        # ─── Stage 8: Formatting ──────────────────────────────────────
        stage_start = time.perf_counter()
        citations = self._build_citations(chunks_used)
        formatted_answer = self.formatter.format(answer, citations, request.include_citations)
        stage_ms = (time.perf_counter() - stage_start) * 1000
        stage_timings["format"] = stage_ms

        # Determine confidence
        confidence = "high"
        if groundedness_score is not None and groundedness_score < 0.8:
            confidence = "medium"
        if groundedness_score is not None and groundedness_score < 0.5:
            confidence = "low"

        total_latency = (time.perf_counter() - pipeline_start) * 1000

        # Print trace
        self.observer.print_trace(trace_id)

        return RAGResponse(
            answer=formatted_answer,
            citations=citations,
            query_type=query_type,
            rewritten_query=rewritten_query,
            groundedness_score=groundedness_score,
            is_grounded=is_grounded,
            chunks_used=len(chunks_used),
            total_tokens_used=tokens_used,
            latency_ms=total_latency,
            trace_id=trace_id,
            stage_timings=stage_timings,
            confidence=confidence,
        )

    def _rewrite_query(self, query: str, history: list[dict] | None) -> str:
        """Rewrite query if conversation history exists (resolve references)."""
        if not history:
            return query

        # Simple: use LLM to resolve references
        from openai import OpenAI
        client = OpenAI()

        context_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-3:])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Rewrite the user's query to be self-contained by resolving pronouns and references from the conversation. Return ONLY the rewritten query.",
                },
                {"role": "user", "content": f"Conversation:\n{context_str}\n\nQuery: {query}"},
            ],
            temperature=0.0,
            max_tokens=100,
        )
        return response.choices[0].message.content.strip()

    def _retrieve(self, query: str, request: RAGRequest) -> list[dict[str, Any]]:
        """Execute retrieval using the retrieval service."""
        if self.retrieval_service is None:
            logger.warning("No retrieval service configured — returning empty")
            return []

        # Import from our retrieval module
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            pass

        # Use the retrieval service (assumes it has a .retrieve() method)
        response = self.retrieval_service.retrieve({
            "query": query,
            "top_k": self.retrieval_top_k,
            "metadata_filters": request.metadata_filters,
            "user_acl_groups": request.user_acl_groups,
        })

        # Convert to dicts for the assembler
        if hasattr(response, "chunks"):
            return [
                {"content": c.content, "chunk_id": c.chunk_id, "score": c.score, **c.metadata}
                for c in response.chunks
            ]
        return response if isinstance(response, list) else []

    def _rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        """Rerank chunks (passthrough if no reranker configured)."""
        # In production, use cross-encoder reranking here
        # For now, just take top-k by existing score
        sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0), reverse=True)
        return sorted_chunks[: self.rerank_top_k]

    def _build_citations(self, chunks: list[dict]) -> list[dict[str, Any]]:
        """Build citation metadata from used chunks."""
        citations = []
        for i, chunk in enumerate(chunks, start=1):
            citations.append({
                "citation_id": i,
                "chunk_id": chunk.get("chunk_id", ""),
                "source_id": chunk.get("source_id", ""),
                "source_title": chunk.get("title", ""),
                "section_title": chunk.get("section_title", ""),
                "page_number": chunk.get("page_number"),
            })
        return citations


# ─── Standalone Demo Pipeline (no external deps) ─────────────────────────────


class DemoRAGPipeline:
    """
    Simplified demo pipeline that works without external services.
    Uses mock retrieval for demonstration.
    """

    def __init__(self):
        self.classifier = QueryClassifier()
        self.assembler = ContextAssembler()
        self.formatter = ResponseFormatter()
        self.observer = PipelineObserver()

        # Mock knowledge base
        self._knowledge = [
            {"content": "RAG combines retrieval with generation to ground LLM outputs in facts.", "source_id": "rag-intro", "title": "RAG Introduction"},
            {"content": "Hybrid search combines dense vector search with sparse BM25 using reciprocal rank fusion (RRF).", "source_id": "hybrid-search", "title": "Hybrid Search"},
            {"content": "Reranking uses cross-encoder models to rescore initial retrieval results, improving precision at the cost of ~200ms latency.", "source_id": "reranking", "title": "Reranking Guide"},
            {"content": "Chunking strategies include fixed-size, sentence-based, semantic, and parent-child approaches.", "source_id": "chunking", "title": "Chunking Strategies"},
            {"content": "The RAGAS framework evaluates RAG systems on faithfulness, answer relevance, context recall, and context precision.", "source_id": "evaluation", "title": "RAG Evaluation"},
        ]

    def run(self, query: str) -> RAGResponse:
        """Run the demo pipeline with mock retrieval."""
        trace_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Classify
        query_type = self.classifier.classify(query)

        if query_type == QueryType.CONVERSATIONAL:
            return RAGResponse(answer="How can I help you?", query_type=query_type, trace_id=trace_id)

        # Mock retrieval (simple keyword matching)
        query_words = set(query.lower().split())
        scored = []
        for doc in self._knowledge:
            doc_words = set(doc["content"].lower().split())
            overlap = len(query_words & doc_words)
            if overlap > 0:
                scored.append({**doc, "score": overlap / len(query_words)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        top_chunks = scored[:3]

        # Assemble context
        context, used = self.assembler.assemble(top_chunks, query_type)

        # Build response (without LLM for demo)
        if used:
            answer = f"Based on the retrieved information:\n\n"
            for i, chunk in enumerate(used, 1):
                answer += f"[{i}] {chunk['content']}\n\n"
        else:
            answer = "I couldn't find relevant information for your query."

        citations = [{"citation_id": i + 1, "source_id": c.get("source_id", ""), "source_title": c.get("title", "")} for i, c in enumerate(used)]

        return RAGResponse(
            answer=answer,
            citations=citations,
            query_type=query_type,
            chunks_used=len(used),
            latency_ms=(time.perf_counter() - start) * 1000,
            trace_id=trace_id,
        )


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    """Demo the RAG pipeline."""
    pipeline = DemoRAGPipeline()

    queries = [
        "How does hybrid search work in RAG?",
        "What chunking strategies are available?",
        "How do you evaluate a RAG system?",
        "Hello!",
    ]

    for query in queries:
        print(f"\n{'─'*60}")
        print(f"Query: {query}")
        print(f"{'─'*60}")
        response = pipeline.run(query)
        print(f"Type: {response.query_type.value}")
        print(f"Answer: {response.answer[:200]}")
        print(f"Chunks: {response.chunks_used} | Latency: {response.latency_ms:.1f}ms")


if __name__ == "__main__":
    main()
