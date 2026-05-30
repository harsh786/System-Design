"""
Agentic RAG System — Full Implementation

A production-grade agentic RAG system that plans, retrieves iteratively,
verifies claims, computes confidence, and decides whether to answer, 
caveat, clarify, abstain, or escalate.
"""

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# ─────────────────────────────────────────────────────────────
# Domain Models
# ─────────────────────────────────────────────────────────────

class Intent(Enum):
    INFORMATIONAL = "informational"  # Seeking knowledge
    TRANSACTIONAL = "transactional"  # Wanting to perform an action
    NAVIGATIONAL = "navigational"    # Looking for a specific resource
    AMBIGUOUS = "ambiguous"          # Unclear intent

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class OutputAction(Enum):
    ANSWER = "answer"
    ANSWER_WITH_CAVEAT = "answer_with_caveat"
    CLARIFY = "clarify"
    ABSTAIN = "abstain"
    ESCALATE = "escalate"

class ClaimVerdict(Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NOT_SUPPORTED = "not_supported"
    CONTRADICTED = "contradicted"

class SufficiencyDiagnosis(Enum):
    SUFFICIENT = "sufficient"
    WRONG_SOURCE = "wrong_source"
    TOO_BROAD = "too_broad"
    TOO_NARROW = "too_narrow"
    MISSING_ENTITY = "missing_entity"
    PARTIAL = "partial"
    EXHAUSTED = "exhausted"


@dataclass
class Source:
    id: str
    title: str
    content: str
    authority_tier: int  # 1 (highest) to 4 (lowest)
    last_updated: float  # Unix timestamp
    provenance: str      # "official_docs", "wiki", "slack", "external"
    url: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None


@dataclass
class RetrievedChunk:
    source: Source
    chunk_text: str
    similarity_score: float
    rerank_score: Optional[float] = None
    authority_weight: float = 1.0
    freshness_score: float = 1.0


@dataclass
class SubQuestion:
    id: str
    text: str
    depends_on: list[str] = field(default_factory=list)
    tool: Optional[str] = None
    answer: Optional[str] = None
    evidence: list[RetrievedChunk] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Claim:
    text: str
    verdict: ClaimVerdict = ClaimVerdict.NOT_SUPPORTED
    supporting_evidence: list[RetrievedChunk] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Citation:
    source_id: str
    source_title: str
    page: Optional[int] = None
    section: Optional[str] = None
    url: Optional[str] = None
    quote: str = ""


@dataclass
class ConfidenceBreakdown:
    retrieval_quality: float = 0.0
    reranker_agreement: float = 0.0
    source_authority: float = 0.0
    freshness: float = 0.0
    coverage: float = 0.0
    groundedness: float = 0.0
    consistency: float = 0.0
    citation_density: float = 0.0
    composite: float = 0.0


@dataclass
class AgenticRAGResult:
    action: OutputAction
    answer: Optional[str] = None
    citations: list[Citation] = field(default_factory=list)
    confidence: ConfidenceBreakdown = field(default_factory=ConfidenceBreakdown)
    caveats: list[str] = field(default_factory=list)
    clarification_question: Optional[str] = None
    escalation_reason: Optional[str] = None
    sub_questions: list[SubQuestion] = field(default_factory=list)
    iterations_used: int = 0
    metadata: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# Abstract Tool Interface
# ─────────────────────────────────────────────────────────────

class RetrievalTool(ABC):
    """Base class for all retrieval tools."""
    
    name: str
    description: str
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RetrievedChunk]:
        pass


class VectorSearchTool(RetrievalTool):
    """Semantic similarity search over embedded documents."""
    
    name = "vector_search"
    description = "Semantic search for conceptual/how/why questions"
    
    def __init__(self, collection_name: str = "default"):
        self.collection_name = collection_name
    
    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RetrievedChunk]:
        # In production: call vector DB (Pinecone, Weaviate, Qdrant, etc.)
        # Placeholder implementation
        print(f"[VectorSearch] Searching '{query}' in collection '{self.collection_name}' (top_k={top_k})")
        return []


class SQLTool(RetrievalTool):
    """Structured query over relational data."""
    
    name = "sql_query"
    description = "Exact facts, aggregations, numeric queries over structured data"
    
    def __init__(self, connection_string: str = ""):
        self.connection_string = connection_string
    
    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RetrievedChunk]:
        # In production: use text-to-SQL or predefined query templates
        print(f"[SQL] Executing query for: '{query}'")
        return []


class GraphSearchTool(RetrievalTool):
    """Knowledge graph traversal for entity relationships."""
    
    name = "graph_search"
    description = "Entity relationships, org charts, dependency graphs"
    
    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RetrievedChunk]:
        print(f"[Graph] Traversing graph for: '{query}'")
        return []


class APITool(RetrievalTool):
    """External API calls for real-time data."""
    
    name = "api_call"
    description = "Real-time data, current status, live metrics"
    
    def __init__(self, base_url: str = ""):
        self.base_url = base_url
    
    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RetrievedChunk]:
        print(f"[API] Calling API for: '{query}'")
        return []


class WebSearchTool(RetrievalTool):
    """Web search for public/recent information."""
    
    name = "web_search"
    description = "Recent events, public knowledge, external references"
    
    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict] = None) -> list[RetrievedChunk]:
        print(f"[WebSearch] Searching web for: '{query}'")
        return []


# ─────────────────────────────────────────────────────────────
# LLM Interface (Abstract)
# ─────────────────────────────────────────────────────────────

class LLMClient(ABC):
    """Abstract LLM client for all generation/classification tasks."""
    
    @abstractmethod
    async def generate(self, prompt: str, system: str = "", temperature: float = 0.0) -> str:
        pass
    
    @abstractmethod
    async def generate_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        pass


class OpenAIClient(LLMClient):
    """OpenAI-compatible LLM client."""
    
    def __init__(self, model: str = "gpt-4o", api_key: str = ""):
        self.model = model
        self.api_key = api_key
    
    async def generate(self, prompt: str, system: str = "", temperature: float = 0.0) -> str:
        # In production: call OpenAI API
        # Placeholder
        return ""
    
    async def generate_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        response = await self.generate(prompt, system, temperature)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}


# ─────────────────────────────────────────────────────────────
# Intent & Risk Classifier
# ─────────────────────────────────────────────────────────────

class IntentRiskClassifier:
    """Classifies user query intent and assesses risk level."""
    
    SYSTEM_PROMPT = """You are a query classifier. Given a user question, classify:
1. Intent: informational, transactional, navigational, or ambiguous
2. Risk: low, medium, high, or critical

Risk assessment guidelines:
- LOW: General information queries, no business impact
- MEDIUM: Questions about processes, moderate business impact
- HIGH: Financial, security, or customer-impacting questions
- CRITICAL: Legal, compliance, safety, or irreversible-action questions

Respond in JSON: {"intent": "...", "risk": "...", "reasoning": "..."}"""
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def classify(self, query: str, conversation_context: Optional[str] = None) -> tuple[Intent, RiskLevel]:
        prompt = f"User query: {query}"
        if conversation_context:
            prompt = f"Conversation context: {conversation_context}\n\n{prompt}"
        
        result = await self.llm.generate_json(prompt, system=self.SYSTEM_PROMPT)
        
        intent = Intent(result.get("intent", "informational"))
        risk = RiskLevel(result.get("risk", "low"))
        
        return intent, risk


# ─────────────────────────────────────────────────────────────
# Query Decomposer
# ─────────────────────────────────────────────────────────────

class QueryDecomposer:
    """Breaks complex questions into sub-questions with dependency graph."""
    
    SYSTEM_PROMPT = """You are a query decomposition engine. Given a complex question,
break it into atomic sub-questions that can each be answered independently (or with
dependencies on other sub-questions).

Rules:
1. Simple questions that need no decomposition → return single sub-question
2. Each sub-question should be answerable with a single retrieval
3. Specify dependencies (which sub-questions must be answered first)
4. Suggest the best retrieval tool for each sub-question

Tools available: vector_search, sql_query, graph_search, api_call, web_search

Respond in JSON:
{
  "needs_decomposition": true/false,
  "sub_questions": [
    {
      "id": "sq1",
      "text": "...",
      "depends_on": [],
      "suggested_tool": "vector_search"
    }
  ]
}"""
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def decompose(self, query: str, context: Optional[str] = None) -> list[SubQuestion]:
        prompt = f"Question to decompose: {query}"
        if context:
            prompt += f"\n\nConversation context: {context}"
        
        result = await self.llm.generate_json(prompt, system=self.SYSTEM_PROMPT)
        
        sub_questions = []
        for sq in result.get("sub_questions", [{"id": "sq1", "text": query, "depends_on": [], "suggested_tool": "vector_search"}]):
            sub_questions.append(SubQuestion(
                id=sq["id"],
                text=sq["text"],
                depends_on=sq.get("depends_on", []),
                tool=sq.get("suggested_tool", "vector_search"),
            ))
        
        return sub_questions


# ─────────────────────────────────────────────────────────────
# Tool Selector
# ─────────────────────────────────────────────────────────────

class ToolSelector:
    """Selects the best retrieval tool for a given sub-question."""
    
    TOOL_SELECTION_RULES = {
        "aggregation_keywords": ["sum", "count", "average", "total", "how many", "how much"],
        "relationship_keywords": ["who manages", "reports to", "related to", "connected to", "depends on"],
        "realtime_keywords": ["current", "right now", "latest", "today", "live"],
        "specific_doc_keywords": ["section", "page", "chapter", "document titled", "the policy"],
    }
    
    def __init__(self, available_tools: dict[str, RetrievalTool]):
        self.tools = available_tools
    
    def select(self, sub_question: SubQuestion) -> RetrievalTool:
        """Select the best tool based on sub-question characteristics."""
        query_lower = sub_question.text.lower()
        
        # Use LLM suggestion if available and tool exists
        if sub_question.tool and sub_question.tool in self.tools:
            return self.tools[sub_question.tool]
        
        # Rule-based fallback
        if any(kw in query_lower for kw in self.TOOL_SELECTION_RULES["aggregation_keywords"]):
            if "sql_query" in self.tools:
                return self.tools["sql_query"]
        
        if any(kw in query_lower for kw in self.TOOL_SELECTION_RULES["relationship_keywords"]):
            if "graph_search" in self.tools:
                return self.tools["graph_search"]
        
        if any(kw in query_lower for kw in self.TOOL_SELECTION_RULES["realtime_keywords"]):
            if "api_call" in self.tools:
                return self.tools["api_call"]
        
        # Default to vector search
        return self.tools.get("vector_search", list(self.tools.values())[0])


# ─────────────────────────────────────────────────────────────
# Reranker
# ─────────────────────────────────────────────────────────────

class Reranker:
    """Cross-encoder reranking with authority and freshness weighting."""
    
    def __init__(self, llm: LLMClient, authority_weight: float = 0.2, freshness_weight: float = 0.1):
        self.llm = llm
        self.authority_weight = authority_weight
        self.freshness_weight = freshness_weight
    
    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
        """Rerank chunks using cross-encoder scores + authority + freshness."""
        if not chunks:
            return []
        
        # Compute freshness scores (decay over time)
        now = time.time()
        for chunk in chunks:
            age_days = (now - chunk.source.last_updated) / 86400
            chunk.freshness_score = max(0.1, 1.0 - (age_days / 365))  # Linear decay over 1 year
            
            # Authority weight: tier 1 = 1.0, tier 2 = 0.8, tier 3 = 0.6, tier 4 = 0.4
            chunk.authority_weight = max(0.4, 1.0 - (chunk.source.authority_tier - 1) * 0.2)
        
        # In production: use cross-encoder model (e.g., ms-marco-MiniLM)
        # Here we simulate with LLM-based relevance scoring
        for chunk in chunks:
            # Composite score
            base_score = chunk.similarity_score
            chunk.rerank_score = (
                (1 - self.authority_weight - self.freshness_weight) * base_score +
                self.authority_weight * chunk.authority_weight +
                self.freshness_weight * chunk.freshness_score
            )
        
        # Sort by rerank score and return top_k
        chunks.sort(key=lambda c: c.rerank_score or 0, reverse=True)
        return chunks[:top_k]


# ─────────────────────────────────────────────────────────────
# Evidence Sufficiency Checker
# ─────────────────────────────────────────────────────────────

class EvidenceSufficiencyChecker:
    """Evaluates whether retrieved evidence is sufficient to answer the question."""
    
    SYSTEM_PROMPT = """You are an evidence sufficiency evaluator. Given a question and retrieved evidence,
assess whether the evidence is sufficient to answer the question completely and accurately.

Evaluate these dimensions (each 0.0 to 1.0):
- coverage: Does evidence address all aspects of the question?
- relevance: Is the evidence actually about the question topic?
- specificity: Is the evidence specific enough (not too general)?
- recency: Is the evidence fresh enough for this question?
- consensus: Do multiple pieces of evidence agree?

Also diagnose the issue if insufficient:
- "sufficient": Evidence is adequate
- "wrong_source": Need different type of source
- "too_broad": Need more specific query
- "too_narrow": Need broader query
- "missing_entity": Key entity not found in evidence
- "partial": Some aspects covered, others missing

Respond in JSON:
{
  "coverage": 0.0-1.0,
  "relevance": 0.0-1.0,
  "specificity": 0.0-1.0,
  "recency": 0.0-1.0,
  "consensus": 0.0-1.0,
  "overall_score": 0.0-1.0,
  "diagnosis": "sufficient|wrong_source|too_broad|too_narrow|missing_entity|partial",
  "missing_aspects": ["..."],
  "suggested_reformulation": "..."
}"""
    
    THRESHOLD_SUFFICIENT = 0.75
    THRESHOLD_PARTIAL = 0.50
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def check(self, question: str, evidence: list[RetrievedChunk]) -> tuple[float, SufficiencyDiagnosis, Optional[str]]:
        """
        Returns: (sufficiency_score, diagnosis, suggested_reformulation)
        """
        if not evidence:
            return 0.0, SufficiencyDiagnosis.WRONG_SOURCE, None
        
        evidence_text = "\n\n---\n\n".join([
            f"[Source: {c.source.title} | Authority: Tier {c.source.authority_tier}]\n{c.chunk_text}"
            for c in evidence[:10]  # Limit to top 10 for LLM context
        ])
        
        prompt = f"Question: {question}\n\nRetrieved Evidence:\n{evidence_text}"
        
        result = await self.llm.generate_json(prompt, system=self.SYSTEM_PROMPT)
        
        score = result.get("overall_score", 0.0)
        diagnosis_str = result.get("diagnosis", "partial")
        reformulation = result.get("suggested_reformulation")
        
        try:
            diagnosis = SufficiencyDiagnosis(diagnosis_str)
        except ValueError:
            diagnosis = SufficiencyDiagnosis.PARTIAL
        
        return score, diagnosis, reformulation


# ─────────────────────────────────────────────────────────────
# Claim Verifier
# ─────────────────────────────────────────────────────────────

class ClaimVerifier:
    """Verifies each claim in the generated answer against source evidence."""
    
    DECOMPOSE_PROMPT = """Extract all factual claims from this answer. Each claim should be
an atomic statement that can be independently verified. Return as JSON:
{"claims": ["claim1", "claim2", ...]}

Answer: {answer}"""
    
    VERIFY_PROMPT = """Determine if this claim is supported by the evidence.

Claim: {claim}

Evidence:
{evidence}

Verdict options:
- "supported": Evidence directly states or strongly implies the claim
- "partially_supported": Evidence is related but doesn't fully confirm
- "not_supported": No relevant evidence found
- "contradicted": Evidence contradicts the claim

Respond in JSON: {{"verdict": "...", "supporting_quote": "...", "reasoning": "..."}}"""
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def decompose_claims(self, answer: str) -> list[str]:
        """Split answer into atomic factual claims."""
        prompt = self.DECOMPOSE_PROMPT.format(answer=answer)
        result = await self.llm.generate_json(prompt)
        return result.get("claims", [answer])
    
    async def verify_claim(self, claim: str, evidence: list[RetrievedChunk]) -> Claim:
        """Verify a single claim against evidence."""
        evidence_text = "\n\n".join([
            f"[{c.source.title}]: {c.chunk_text}" for c in evidence[:5]
        ])
        
        prompt = self.VERIFY_PROMPT.format(claim=claim, evidence=evidence_text)
        result = await self.llm.generate_json(prompt)
        
        verdict_str = result.get("verdict", "not_supported")
        try:
            verdict = ClaimVerdict(verdict_str)
        except ValueError:
            verdict = ClaimVerdict.NOT_SUPPORTED
        
        return Claim(
            text=claim,
            verdict=verdict,
            supporting_evidence=[c for c in evidence if result.get("supporting_quote", "") in c.chunk_text],
            confidence={"supported": 1.0, "partially_supported": 0.6, "not_supported": 0.0, "contradicted": 0.0}.get(verdict_str, 0.0),
        )
    
    async def verify_all(self, answer: str, evidence: list[RetrievedChunk]) -> list[Claim]:
        """Verify all claims in an answer."""
        claim_texts = await self.decompose_claims(answer)
        
        # Verify claims in parallel
        tasks = [self.verify_claim(claim, evidence) for claim in claim_texts]
        claims = await asyncio.gather(*tasks)
        return list(claims)


# ─────────────────────────────────────────────────────────────
# Confidence Scorer
# ─────────────────────────────────────────────────────────────

class ConfidenceScorer:
    """Computes composite confidence from multiple signals."""
    
    # Signal weights (must sum to 1.0)
    WEIGHTS = {
        "retrieval_quality": 0.15,
        "reranker_agreement": 0.10,
        "source_authority": 0.15,
        "freshness": 0.10,
        "coverage": 0.15,
        "groundedness": 0.20,
        "consistency": 0.10,
        "citation_density": 0.05,
    }
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    def compute(
        self,
        evidence: list[RetrievedChunk],
        claims: list[Claim],
        sufficiency_score: float,
        answer: str,
        num_generations: int = 1,  # For consistency signal
    ) -> ConfidenceBreakdown:
        """Compute composite confidence score from all signals."""
        
        breakdown = ConfidenceBreakdown()
        
        # 1. Retrieval quality: average similarity of top evidence
        if evidence:
            breakdown.retrieval_quality = sum(c.similarity_score for c in evidence[:5]) / min(5, len(evidence))
        
        # 2. Reranker agreement: correlation between initial rank and rerank
        if evidence and evidence[0].rerank_score is not None:
            rerank_scores = [c.rerank_score for c in evidence[:5] if c.rerank_score]
            breakdown.reranker_agreement = sum(rerank_scores) / len(rerank_scores) if rerank_scores else 0.0
        
        # 3. Source authority: weighted average authority of used sources
        if evidence:
            breakdown.source_authority = sum(c.authority_weight for c in evidence[:5]) / min(5, len(evidence))
        
        # 4. Freshness: average freshness of evidence
        if evidence:
            breakdown.freshness = sum(c.freshness_score for c in evidence[:5]) / min(5, len(evidence))
        
        # 5. Coverage: from sufficiency checker
        breakdown.coverage = sufficiency_score
        
        # 6. Groundedness: fraction of claims that are supported
        if claims:
            supported = sum(1 for c in claims if c.verdict in (ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED))
            breakdown.groundedness = supported / len(claims)
        
        # 7. Consistency: if multiple generations were done, measure agreement
        # (simplified: assume 1.0 if single generation)
        breakdown.consistency = 1.0 if num_generations == 1 else 0.8  # Placeholder
        
        # 8. Citation density: fraction of answer sentences with citations
        sentences = [s.strip() for s in answer.split('.') if s.strip()]
        cited = sum(1 for s in sentences if '[' in s and ']' in s)
        breakdown.citation_density = cited / len(sentences) if sentences else 0.0
        
        # Composite score
        breakdown.composite = sum(
            self.WEIGHTS[signal] * getattr(breakdown, signal)
            for signal in self.WEIGHTS
        )
        
        return breakdown


# ─────────────────────────────────────────────────────────────
# Abstention & Escalation Logic
# ─────────────────────────────────────────────────────────────

class OutputDecider:
    """Decides the output action based on confidence and risk."""
    
    # Behavior matrix: (min_confidence, max_confidence) → action per risk level
    BEHAVIOR_MATRIX = {
        RiskLevel.LOW: [
            (0.80, 1.00, OutputAction.ANSWER),
            (0.65, 0.80, OutputAction.ANSWER_WITH_CAVEAT),
            (0.50, 0.65, OutputAction.CLARIFY),
            (0.00, 0.50, OutputAction.ABSTAIN),
        ],
        RiskLevel.MEDIUM: [
            (0.85, 1.00, OutputAction.ANSWER),
            (0.70, 0.85, OutputAction.ANSWER_WITH_CAVEAT),
            (0.50, 0.70, OutputAction.CLARIFY),
            (0.35, 0.50, OutputAction.ABSTAIN),
            (0.00, 0.35, OutputAction.ESCALATE),
        ],
        RiskLevel.HIGH: [
            (0.90, 1.00, OutputAction.ANSWER),
            (0.80, 0.90, OutputAction.ANSWER_WITH_CAVEAT),
            (0.65, 0.80, OutputAction.ESCALATE),
            (0.00, 0.65, OutputAction.ESCALATE),
        ],
        RiskLevel.CRITICAL: [
            (0.95, 1.00, OutputAction.ANSWER_WITH_CAVEAT),
            (0.00, 0.95, OutputAction.ESCALATE),
        ],
    }
    
    # Topics that always escalate regardless of confidence
    ESCALATION_TOPICS = ["legal", "compliance", "termination", "lawsuit", "regulatory"]
    
    def decide(self, confidence: float, risk: RiskLevel, query: str = "") -> OutputAction:
        """Determine output action from confidence × risk matrix."""
        
        # Check for forced escalation topics
        query_lower = query.lower()
        if any(topic in query_lower for topic in self.ESCALATION_TOPICS):
            if confidence < 0.95:
                return OutputAction.ESCALATE
        
        # Look up in behavior matrix
        thresholds = self.BEHAVIOR_MATRIX.get(risk, self.BEHAVIOR_MATRIX[RiskLevel.MEDIUM])
        for min_conf, max_conf, action in thresholds:
            if min_conf <= confidence < max_conf:
                return action
        
        return OutputAction.ABSTAIN


# ─────────────────────────────────────────────────────────────
# Citation Builder
# ─────────────────────────────────────────────────────────────

class CitationBuilder:
    """Builds precise citations with page/section references."""
    
    def build_citations(self, claims: list[Claim]) -> list[Citation]:
        """Build citation list from verified claims."""
        citations = []
        seen_sources = set()
        
        for claim in claims:
            if claim.verdict in (ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED):
                for evidence in claim.supporting_evidence:
                    source = evidence.source
                    if source.id not in seen_sources:
                        seen_sources.add(source.id)
                        citations.append(Citation(
                            source_id=source.id,
                            source_title=source.title,
                            page=source.page,
                            section=source.section,
                            url=source.url,
                            quote=evidence.chunk_text[:200],  # First 200 chars as quote
                        ))
        
        return citations
    
    def format_inline_citations(self, answer: str, claims: list[Claim]) -> str:
        """Add inline citation markers [1], [2] to the answer."""
        # Map sources to citation numbers
        source_to_num = {}
        counter = 1
        
        for claim in claims:
            for ev in claim.supporting_evidence:
                if ev.source.id not in source_to_num:
                    source_to_num[ev.source.id] = counter
                    counter += 1
        
        # For each claim, append citation marker
        annotated = answer
        for claim in claims:
            if claim.supporting_evidence:
                nums = [source_to_num[ev.source.id] for ev in claim.supporting_evidence if ev.source.id in source_to_num]
                if nums:
                    citation_marker = "".join(f"[{n}]" for n in sorted(set(nums)))
                    # Find and annotate the claim in the answer
                    if claim.text in annotated:
                        annotated = annotated.replace(claim.text, f"{claim.text} {citation_marker}", 1)
        
        return annotated


# ─────────────────────────────────────────────────────────────
# Answer Generator
# ─────────────────────────────────────────────────────────────

class AnswerGenerator:
    """Generates the final answer from evidence."""
    
    SYSTEM_PROMPT = """You are a precise, factual assistant. Generate an answer based ONLY on the
provided evidence. Do not add information not present in the evidence.

Rules:
1. Every statement must be traceable to the evidence
2. If evidence is insufficient for any aspect, explicitly say so
3. Use clear, professional language
4. Structure the answer logically
5. If evidence conflicts, present both perspectives"""
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
    
    async def generate(self, question: str, evidence: list[RetrievedChunk], sub_answers: Optional[list[str]] = None) -> str:
        """Generate answer from evidence."""
        evidence_text = "\n\n---\n\n".join([
            f"[Source: {c.source.title} (Tier {c.source.authority_tier})]\n{c.chunk_text}"
            for c in evidence[:10]
        ])
        
        prompt = f"Question: {question}\n\nEvidence:\n{evidence_text}"
        
        if sub_answers:
            prompt += "\n\nSub-question answers:\n" + "\n".join(f"- {a}" for a in sub_answers)
        
        return await self.llm.generate(prompt, system=self.SYSTEM_PROMPT)
    
    async def generate_clarification(self, question: str, missing_aspects: list[str]) -> str:
        """Generate a clarification question when we can't answer."""
        prompt = f"""The user asked: "{question}"

I couldn't find sufficient evidence. The following aspects are unclear or missing:
{json.dumps(missing_aspects)}

Generate a helpful clarification question to ask the user that would help me provide a better answer."""
        
        return await self.llm.generate(prompt)
    
    async def generate_abstention(self, question: str, partial_info: Optional[str] = None) -> str:
        """Generate a graceful abstention response."""
        prompt = f"""The user asked: "{question}"

I don't have sufficient evidence to answer accurately.
Partial info found: {partial_info or 'None'}

Generate a helpful response that:
1. Acknowledges the limitation
2. Shares any partial relevant info
3. Suggests where/how to find the answer"""
        
        return await self.llm.generate(prompt)


# ─────────────────────────────────────────────────────────────
# Main Orchestrator
# ─────────────────────────────────────────────────────────────

class AgenticRAGOrchestrator:
    """
    Main orchestration loop for Agentic RAG.
    
    Coordinates all components: classification → decomposition → retrieval →
    reranking → sufficiency check → generation → verification → confidence → output decision.
    """
    
    MAX_ITERATIONS = 5
    
    def __init__(
        self,
        llm: LLMClient,
        tools: dict[str, RetrievalTool],
        max_iterations: int = 5,
    ):
        self.llm = llm
        self.max_iterations = max_iterations
        
        # Initialize components
        self.classifier = IntentRiskClassifier(llm)
        self.decomposer = QueryDecomposer(llm)
        self.tool_selector = ToolSelector(tools)
        self.reranker = Reranker(llm)
        self.sufficiency_checker = EvidenceSufficiencyChecker(llm)
        self.claim_verifier = ClaimVerifier(llm)
        self.confidence_scorer = ConfidenceScorer(llm)
        self.output_decider = OutputDecider()
        self.citation_builder = CitationBuilder()
        self.answer_generator = AnswerGenerator(llm)
    
    async def run(self, query: str, conversation_context: Optional[str] = None) -> AgenticRAGResult:
        """Execute the full agentic RAG pipeline."""
        
        # ── Step 1: Classify intent and risk ──
        intent, risk = await self.classifier.classify(query, conversation_context)
        print(f"[Orchestrator] Intent={intent.value}, Risk={risk.value}")
        
        # ── Step 2: Decompose query ──
        sub_questions = await self.decomposer.decompose(query, conversation_context)
        print(f"[Orchestrator] Decomposed into {len(sub_questions)} sub-question(s)")
        
        # ── Step 3-6: Iterative retrieval per sub-question ──
        all_evidence: list[RetrievedChunk] = []
        iterations_used = 0
        
        # Build execution tiers from dependency graph
        tiers = self._build_execution_tiers(sub_questions)
        
        for tier in tiers:
            # Execute sub-questions in this tier in parallel
            tier_tasks = [
                self._retrieve_for_subquestion(sq, sub_questions)
                for sq in tier
            ]
            await asyncio.gather(*tier_tasks)
            
            # Collect evidence
            for sq in tier:
                all_evidence.extend(sq.evidence)
        
        # Track total iterations across all sub-questions
        iterations_used = sum(1 for _ in tiers)
        
        # ── Rerank all evidence ──
        all_evidence = await self.reranker.rerank(query, all_evidence, top_k=10)
        
        # ── Check overall sufficiency ──
        sufficiency_score, diagnosis, reformulation = await self.sufficiency_checker.check(query, all_evidence)
        
        # ── Iterative re-retrieval if insufficient ──
        iteration = 0
        while sufficiency_score < self.sufficiency_checker.THRESHOLD_SUFFICIENT and iteration < self.max_iterations:
            iteration += 1
            iterations_used += 1
            print(f"[Orchestrator] Iteration {iteration}: sufficiency={sufficiency_score:.2f}, diagnosis={diagnosis.value}")
            
            # Re-retrieve based on diagnosis
            new_query = reformulation or query
            # Use vector search as fallback for re-retrieval
            tool = self.tool_selector.tools.get("vector_search", list(self.tool_selector.tools.values())[0])
            new_chunks = await tool.retrieve(new_query, top_k=5)
            
            if not new_chunks:
                break  # No new evidence available
            
            all_evidence.extend(new_chunks)
            all_evidence = await self.reranker.rerank(query, all_evidence, top_k=10)
            
            sufficiency_score, diagnosis, reformulation = await self.sufficiency_checker.check(query, all_evidence)
        
        # ── Step 7: Generate answer ──
        sub_answers = [sq.answer for sq in sub_questions if sq.answer]
        answer = await self.answer_generator.generate(query, all_evidence, sub_answers)
        
        # ── Step 8: Verify claims ──
        claims = await self.claim_verifier.verify_all(answer, all_evidence)
        
        # Remove contradicted claims from answer
        contradicted_claims = [c for c in claims if c.verdict == ClaimVerdict.CONTRADICTED]
        for bad_claim in contradicted_claims:
            answer = answer.replace(bad_claim.text, "[REMOVED: contradicted by evidence]")
        
        # ── Step 9: Compute confidence ──
        confidence = self.confidence_scorer.compute(
            evidence=all_evidence,
            claims=claims,
            sufficiency_score=sufficiency_score,
            answer=answer,
        )
        
        # ── Step 10: Decide output action ──
        action = self.output_decider.decide(confidence.composite, risk, query)
        print(f"[Orchestrator] Confidence={confidence.composite:.2f}, Action={action.value}")
        
        # ── Build result based on action ──
        result = AgenticRAGResult(
            action=action,
            confidence=confidence,
            sub_questions=sub_questions,
            iterations_used=iterations_used,
            metadata={"intent": intent.value, "risk": risk.value},
        )
        
        if action == OutputAction.ANSWER:
            citations = self.citation_builder.build_citations(claims)
            annotated_answer = self.citation_builder.format_inline_citations(answer, claims)
            result.answer = annotated_answer
            result.citations = citations
        
        elif action == OutputAction.ANSWER_WITH_CAVEAT:
            citations = self.citation_builder.build_citations(claims)
            annotated_answer = self.citation_builder.format_inline_citations(answer, claims)
            result.answer = annotated_answer
            result.citations = citations
            # Add caveats for partially supported claims
            result.caveats = [
                f"The following may not be fully verified: {c.text}"
                for c in claims if c.verdict == ClaimVerdict.PARTIALLY_SUPPORTED
            ]
        
        elif action == OutputAction.CLARIFY:
            missing = [sq.text for sq in sub_questions if sq.confidence < 0.5]
            result.clarification_question = await self.answer_generator.generate_clarification(query, missing)
        
        elif action == OutputAction.ABSTAIN:
            partial = answer if sufficiency_score > 0.3 else None
            result.answer = await self.answer_generator.generate_abstention(query, partial)
        
        elif action == OutputAction.ESCALATE:
            result.escalation_reason = self._build_escalation_reason(
                query, risk, confidence, diagnosis, iterations_used
            )
        
        return result
    
    async def _retrieve_for_subquestion(self, sq: SubQuestion, all_sqs: list[SubQuestion]) -> None:
        """Retrieve evidence for a single sub-question."""
        # Resolve dependencies: inject answers from prerequisite sub-questions
        resolved_query = sq.text
        for dep_id in sq.depends_on:
            dep_sq = next((s for s in all_sqs if s.id == dep_id), None)
            if dep_sq and dep_sq.answer:
                resolved_query = resolved_query.replace(f"[{dep_id}]", dep_sq.answer)
                resolved_query = resolved_query.replace(f"[{dep_id}.answer]", dep_sq.answer)
        
        # Select tool and retrieve
        tool = self.tool_selector.select(sq)
        chunks = await tool.retrieve(resolved_query, top_k=5)
        sq.evidence = chunks
        
        # Generate sub-answer from evidence
        if chunks:
            sq.answer = await self.answer_generator.generate(resolved_query, chunks)
            sq.confidence = sum(c.similarity_score for c in chunks[:3]) / min(3, len(chunks))
    
    def _build_execution_tiers(self, sub_questions: list[SubQuestion]) -> list[list[SubQuestion]]:
        """Topologically sort sub-questions into execution tiers."""
        answered = set()
        tiers = []
        remaining = list(sub_questions)
        
        while remaining:
            # Find sub-questions whose dependencies are all satisfied
            tier = [sq for sq in remaining if all(d in answered for d in sq.depends_on)]
            
            if not tier:
                # Circular dependency or unresolvable — just take remaining
                tier = remaining
                remaining = []
            else:
                remaining = [sq for sq in remaining if sq not in tier]
            
            tiers.append(tier)
            answered.update(sq.id for sq in tier)
        
        return tiers
    
    def _build_escalation_reason(
        self,
        query: str,
        risk: RiskLevel,
        confidence: ConfidenceBreakdown,
        diagnosis: SufficiencyDiagnosis,
        iterations: int,
    ) -> str:
        """Build a structured escalation payload for human review."""
        return json.dumps({
            "original_query": query,
            "risk_level": risk.value,
            "confidence_score": confidence.composite,
            "confidence_breakdown": {
                "retrieval_quality": confidence.retrieval_quality,
                "groundedness": confidence.groundedness,
                "coverage": confidence.coverage,
            },
            "diagnosis": diagnosis.value,
            "iterations_attempted": iterations,
            "reason": f"Confidence ({confidence.composite:.2f}) below threshold for risk level '{risk.value}'. "
                     f"Evidence diagnosis: {diagnosis.value}.",
            "suggested_action": "Human review required. Consider consulting domain expert or providing additional source documents.",
        }, indent=2)


# ─────────────────────────────────────────────────────────────
# Usage Example
# ─────────────────────────────────────────────────────────────

async def main():
    """Example usage of the Agentic RAG system."""
    
    # Initialize LLM client
    llm = OpenAIClient(model="gpt-4o", api_key="your-api-key")
    
    # Initialize retrieval tools
    tools = {
        "vector_search": VectorSearchTool(collection_name="company_docs"),
        "sql_query": SQLTool(connection_string="postgresql://..."),
        "graph_search": GraphSearchTool(),
        "api_call": APITool(base_url="https://internal-api.company.com"),
        "web_search": WebSearchTool(),
    }
    
    # Create orchestrator
    orchestrator = AgenticRAGOrchestrator(
        llm=llm,
        tools=tools,
        max_iterations=5,
    )
    
    # Run a query
    result = await orchestrator.run(
        query="How does our Q3 revenue compare to the SLA commitment we made to Enterprise clients?",
        conversation_context=None,
    )
    
    # Handle result
    print(f"\nAction: {result.action.value}")
    print(f"Confidence: {result.confidence.composite:.2f}")
    
    if result.answer:
        print(f"\nAnswer:\n{result.answer}")
    
    if result.citations:
        print("\nCitations:")
        for i, cite in enumerate(result.citations, 1):
            print(f"  [{i}] {cite.source_title} (p.{cite.page}, §{cite.section})")
    
    if result.caveats:
        print("\nCaveats:")
        for caveat in result.caveats:
            print(f"  ⚠ {caveat}")
    
    if result.clarification_question:
        print(f"\nClarification needed: {result.clarification_question}")
    
    if result.escalation_reason:
        print(f"\nEscalated to human:\n{result.escalation_reason}")


if __name__ == "__main__":
    asyncio.run(main())
