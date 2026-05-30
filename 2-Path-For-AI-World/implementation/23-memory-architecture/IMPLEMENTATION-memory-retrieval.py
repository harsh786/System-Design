"""
Memory Retrieval Strategies - Complete Implementation

Production-grade retrieval system implementing:
- Recency-based retrieval
- Relevance-based retrieval (semantic similarity)
- Importance-weighted retrieval
- Hybrid retrieval (combined scoring)
- Context-aware memory selection
- Memory summarization (compress old memories)
- Memory consolidation (merge related memories)
- Memory pruning (remove outdated/irrelevant)
- Working memory management (fit within context window)
"""

import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import numpy as np


# =============================================================================
# CORE TYPES
# =============================================================================

@dataclass
class MemoryItem:
    """A single memory item for retrieval operations."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    summary: Optional[str] = None
    memory_type: str = "episodic"
    embedding: Optional[np.ndarray] = None
    importance: float = 0.5  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    source: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    token_count: int = 0  # Estimated tokens

    @property
    def age_hours(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds() / 3600

    @property
    def display_content(self) -> str:
        """Return summary if available, otherwise truncated content."""
        return self.summary or self.content


@dataclass
class RetrievalResult:
    """Result of a retrieval operation with scoring breakdown."""
    memory: MemoryItem
    final_score: float = 0.0
    recency_score: float = 0.0
    relevance_score: float = 0.0
    importance_score: float = 0.0
    context_bonus: float = 0.0


@dataclass
class RetrievalConfig:
    """Configuration for retrieval operations."""
    max_results: int = 10
    max_tokens: int = 4000
    recency_weight: float = 0.3
    relevance_weight: float = 0.5
    importance_weight: float = 0.2
    # Recency decay parameters
    recency_half_life_hours: float = 168  # 7 days
    # Relevance threshold
    min_relevance_score: float = 0.1
    # Context bonuses
    same_project_bonus: float = 0.1
    same_session_bonus: float = 0.15
    recently_accessed_bonus: float = 0.05


# =============================================================================
# EMBEDDING SERVICE
# =============================================================================

class EmbeddingService:
    """Embedding service for semantic similarity. Mock for demonstration."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def embed(self, text: str) -> np.ndarray:
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension)
        return vec / np.linalg.norm(vec)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


# =============================================================================
# RETRIEVAL STRATEGIES
# =============================================================================

class RecencyRetriever:
    """
    Retrieve memories based on how recently they were created/accessed.
    Uses exponential decay: score = exp(-lambda * age_hours)
    """

    def __init__(self, half_life_hours: float = 168):
        # lambda such that score = 0.5 at half_life
        self.decay_rate = np.log(2) / half_life_hours

    def score(self, memory: MemoryItem) -> float:
        """Score a memory based on recency. Returns 0-1."""
        age = memory.age_hours
        return float(np.exp(-self.decay_rate * age))

    def score_batch(self, memories: list[MemoryItem]) -> list[float]:
        return [self.score(m) for m in memories]

    def retrieve(self, memories: list[MemoryItem], limit: int = 10) -> list[tuple[MemoryItem, float]]:
        """Retrieve top-k most recent memories."""
        scored = [(m, self.score(m)) for m in memories]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


class RelevanceRetriever:
    """
    Retrieve memories based on semantic similarity to query.
    Uses cosine similarity between query embedding and memory embeddings.
    """

    def __init__(self, embedding_service: EmbeddingService):
        self.embedder = embedding_service

    def score(self, query_embedding: np.ndarray, memory: MemoryItem) -> float:
        """Score a memory based on relevance to query."""
        if memory.embedding is None:
            return 0.0
        return max(0.0, self.embedder.similarity(query_embedding, memory.embedding))

    def retrieve(
        self,
        query: str,
        memories: list[MemoryItem],
        limit: int = 10,
        min_score: float = 0.1,
    ) -> list[tuple[MemoryItem, float]]:
        """Retrieve top-k most relevant memories."""
        query_embedding = self.embedder.embed(query)
        scored = [(m, self.score(query_embedding, m)) for m in memories]
        scored = [(m, s) for m, s in scored if s >= min_score]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


class ImportanceRetriever:
    """
    Retrieve memories weighted by importance.
    Importance combines base importance, access frequency, and recency bonus.
    """

    def __init__(self, frequency_weight: float = 0.3, recency_bonus_weight: float = 0.2):
        self.frequency_weight = frequency_weight
        self.recency_bonus_weight = recency_bonus_weight

    def score(self, memory: MemoryItem) -> float:
        """Score a memory based on importance."""
        base = memory.importance  # 0-1

        # Frequency bonus (log scale, capped)
        freq_bonus = min(1.0, np.log1p(memory.access_count) / 5.0)

        # Recency of access bonus
        hours_since_access = (datetime.utcnow() - memory.last_accessed).total_seconds() / 3600
        access_recency = float(np.exp(-0.01 * hours_since_access))

        score = (
            (1.0 - self.frequency_weight - self.recency_bonus_weight) * base
            + self.frequency_weight * freq_bonus
            + self.recency_bonus_weight * access_recency
        )
        return min(1.0, max(0.0, score))

    def retrieve(self, memories: list[MemoryItem], limit: int = 10) -> list[tuple[MemoryItem, float]]:
        scored = [(m, self.score(m)) for m in memories]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


# =============================================================================
# HYBRID RETRIEVER (Main Strategy)
# =============================================================================

class HybridRetriever:
    """
    Combines recency, relevance, and importance with configurable weights.
    This is the recommended retrieval strategy for most use cases.
    
    final_score = w_recency * recency + w_relevance * relevance + w_importance * importance + context_bonus
    """

    def __init__(self, embedding_service: EmbeddingService, config: RetrievalConfig = None):
        self.config = config or RetrievalConfig()
        self.embedder = embedding_service
        self.recency = RecencyRetriever(self.config.recency_half_life_hours)
        self.relevance = RelevanceRetriever(embedding_service)
        self.importance = ImportanceRetriever()

    def retrieve(
        self,
        query: str,
        memories: list[MemoryItem],
        context: dict = None,
        config_override: Optional[RetrievalConfig] = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve memories using hybrid scoring.
        
        Args:
            query: Current query/context string
            memories: Pool of candidate memories
            context: Additional context (project_id, session_id, etc.)
            config_override: Override default config for this query
        """
        config = config_override or self.config
        context = context or {}

        query_embedding = self.embedder.embed(query) if query else None

        results = []
        for mem in memories:
            # Individual scores
            rec_score = self.recency.score(mem)
            rel_score = self.relevance.score(query_embedding, mem) if query_embedding is not None else 0.0
            imp_score = self.importance.score(mem)

            # Context bonus
            ctx_bonus = self._compute_context_bonus(mem, context, config)

            # Weighted combination
            final = (
                config.recency_weight * rec_score
                + config.relevance_weight * rel_score
                + config.importance_weight * imp_score
                + ctx_bonus
            )

            results.append(RetrievalResult(
                memory=mem,
                final_score=final,
                recency_score=rec_score,
                relevance_score=rel_score,
                importance_score=imp_score,
                context_bonus=ctx_bonus,
            ))

        # Sort by final score
        results.sort(key=lambda r: r.final_score, reverse=True)

        # Apply token budget
        selected = self._apply_token_budget(results, config.max_tokens)

        return selected[:config.max_results]

    def _compute_context_bonus(self, memory: MemoryItem, context: dict, config: RetrievalConfig) -> float:
        """Compute bonus score based on contextual relevance."""
        bonus = 0.0

        # Same project bonus
        if context.get("project_id") and memory.metadata.get("project_id") == context["project_id"]:
            bonus += config.same_project_bonus

        # Same session bonus
        if context.get("session_id") and memory.metadata.get("session_id") == context["session_id"]:
            bonus += config.same_session_bonus

        # Recently accessed bonus (accessed in last hour)
        hours_since = (datetime.utcnow() - memory.last_accessed).total_seconds() / 3600
        if hours_since < 1:
            bonus += config.recently_accessed_bonus

        return bonus

    def _apply_token_budget(self, results: list[RetrievalResult], max_tokens: int) -> list[RetrievalResult]:
        """Select results that fit within token budget."""
        selected = []
        total_tokens = 0
        for result in results:
            tokens = result.memory.token_count or len(result.memory.content) // 4
            if total_tokens + tokens > max_tokens:
                break
            selected.append(result)
            total_tokens += tokens
        return selected


# =============================================================================
# CONTEXT-AWARE MEMORY SELECTION
# =============================================================================

class ContextAwareSelector:
    """
    Selects memories based on the current task context.
    Adjusts retrieval weights dynamically based on what the agent is doing.
    """

    def __init__(self, hybrid_retriever: HybridRetriever):
        self.retriever = hybrid_retriever
        self._context_profiles = {
            "new_conversation": RetrievalConfig(
                recency_weight=0.5, relevance_weight=0.3, importance_weight=0.2,
                max_results=5, max_tokens=2000,
            ),
            "question_answering": RetrievalConfig(
                recency_weight=0.1, relevance_weight=0.7, importance_weight=0.2,
                max_results=10, max_tokens=4000,
            ),
            "code_generation": RetrievalConfig(
                recency_weight=0.2, relevance_weight=0.4, importance_weight=0.4,
                max_results=8, max_tokens=3000,
            ),
            "debugging": RetrievalConfig(
                recency_weight=0.4, relevance_weight=0.4, importance_weight=0.2,
                max_results=10, max_tokens=4000,
            ),
            "personalization": RetrievalConfig(
                recency_weight=0.1, relevance_weight=0.2, importance_weight=0.7,
                max_results=15, max_tokens=2000,
            ),
            "continuation": RetrievalConfig(
                recency_weight=0.7, relevance_weight=0.2, importance_weight=0.1,
                max_results=5, max_tokens=3000,
            ),
        }

    def select(
        self,
        query: str,
        memories: list[MemoryItem],
        task_type: str = "general",
        context: dict = None,
    ) -> list[RetrievalResult]:
        """Select memories appropriate for the current task context."""
        config = self._context_profiles.get(task_type, RetrievalConfig())
        return self.retriever.retrieve(query, memories, context, config_override=config)

    def add_profile(self, name: str, config: RetrievalConfig):
        """Add a custom context profile."""
        self._context_profiles[name] = config


# =============================================================================
# MEMORY SUMMARIZATION
# =============================================================================

class MemorySummarizer:
    """
    Compresses old or verbose memories into concise summaries.
    Reduces token usage while preserving key information.
    
    In production: use LLM for summarization. Here we use heuristic extraction.
    """

    def __init__(self, max_summary_tokens: int = 100):
        self.max_summary_tokens = max_summary_tokens

    def summarize_single(self, memory: MemoryItem) -> str:
        """Create a concise summary of a single memory."""
        content = memory.content

        # Heuristic summarization (in production, use LLM)
        # Take first sentence + key phrases
        sentences = content.replace('\n', '. ').split('. ')
        if len(sentences) <= 2:
            return content[:self.max_summary_tokens * 4]

        # First sentence + important keywords
        summary = sentences[0]
        important_words = self._extract_key_phrases(content)
        if important_words:
            summary += f" (key: {', '.join(important_words[:5])})"

        return summary[:self.max_summary_tokens * 4]

    def summarize_group(self, memories: list[MemoryItem], group_label: str = "") -> str:
        """Summarize a group of related memories into one."""
        if not memories:
            return ""

        if len(memories) == 1:
            return self.summarize_single(memories[0])

        # Combine key points from each memory
        # In production: send all to LLM with "summarize these related memories" prompt
        key_points = []
        for mem in memories[:10]:  # Limit to 10 for summarization
            point = mem.content.split('.')[0][:100]
            if point and point not in key_points:
                key_points.append(point)

        label = f"[{group_label}] " if group_label else ""
        summary = f"{label}Summary of {len(memories)} memories: " + "; ".join(key_points[:5])
        return summary[:self.max_summary_tokens * 4]

    def should_summarize(self, memory: MemoryItem, threshold_tokens: int = 200) -> bool:
        """Determine if a memory should be summarized."""
        estimated_tokens = memory.token_count or len(memory.content) // 4
        # Summarize if: old + verbose + low access
        is_old = memory.age_hours > 168  # Older than 7 days
        is_verbose = estimated_tokens > threshold_tokens
        is_low_access = memory.access_count < 3
        return is_old and is_verbose and is_low_access

    def _extract_key_phrases(self, text: str) -> list[str]:
        """Simple key phrase extraction (heuristic)."""
        # In production: use NLP/LLM for proper extraction
        words = text.lower().split()
        # Filter to meaningful words (> 4 chars, not common)
        stopwords = {"this", "that", "with", "from", "have", "been", "they", "their", "which", "would", "could"}
        meaningful = [w.strip('.,!?()[]{}') for w in words if len(w) > 4 and w not in stopwords]
        # Return unique words by frequency
        from collections import Counter
        counts = Counter(meaningful)
        return [word for word, _ in counts.most_common(10)]


# =============================================================================
# MEMORY CONSOLIDATION
# =============================================================================

class MemoryConsolidator:
    """
    Merges related memories to reduce redundancy and improve retrieval.
    Groups similar memories and creates consolidated entries.
    """

    def __init__(self, embedding_service: EmbeddingService, summarizer: MemorySummarizer):
        self.embedder = embedding_service
        self.summarizer = summarizer
        self.similarity_threshold = 0.85  # Threshold to consider memories "related"

    def find_duplicates(self, memories: list[MemoryItem]) -> list[list[MemoryItem]]:
        """Find groups of duplicate/near-duplicate memories."""
        if len(memories) < 2:
            return []

        groups: list[list[MemoryItem]] = []
        used = set()

        for i, mem_a in enumerate(memories):
            if i in used or mem_a.embedding is None:
                continue
            group = [mem_a]
            for j, mem_b in enumerate(memories[i+1:], start=i+1):
                if j in used or mem_b.embedding is None:
                    continue
                sim = self.embedder.similarity(mem_a.embedding, mem_b.embedding)
                if sim >= self.similarity_threshold:
                    group.append(mem_b)
                    used.add(j)
            if len(group) > 1:
                groups.append(group)
                used.add(i)

        return groups

    def consolidate_group(self, group: list[MemoryItem]) -> MemoryItem:
        """Merge a group of related memories into one consolidated memory."""
        if len(group) == 1:
            return group[0]

        # Keep the most important/recent as base
        base = max(group, key=lambda m: (m.importance, m.created_at.timestamp()))

        # Create consolidated content
        summary = self.summarizer.summarize_group(group, group_label=base.memory_type)

        consolidated = MemoryItem(
            content=summary,
            summary=summary,
            memory_type=base.memory_type,
            embedding=base.embedding,  # Use base embedding
            importance=max(m.importance for m in group),
            created_at=min(m.created_at for m in group),  # Earliest creation
            last_accessed=max(m.last_accessed for m in group),  # Most recent access
            access_count=sum(m.access_count for m in group),
            source="consolidation",
            tags=list(set(tag for m in group for tag in m.tags)),
            metadata={
                "consolidated_from": [m.id for m in group],
                "original_count": len(group),
                "consolidation_time": datetime.utcnow().isoformat(),
            },
            token_count=len(summary) // 4,
        )
        return consolidated

    def run_consolidation(self, memories: list[MemoryItem]) -> tuple[list[MemoryItem], list[str]]:
        """
        Run consolidation on a set of memories.
        Returns: (consolidated memories, IDs of memories that were merged)
        """
        duplicate_groups = self.find_duplicates(memories)
        merged_ids = set()
        new_memories = []

        for group in duplicate_groups:
            consolidated = self.consolidate_group(group)
            new_memories.append(consolidated)
            merged_ids.update(m.id for m in group)

        # Keep non-merged memories as-is
        for mem in memories:
            if mem.id not in merged_ids:
                new_memories.append(mem)

        return new_memories, list(merged_ids)


# =============================================================================
# MEMORY PRUNING
# =============================================================================

class MemoryPruner:
    """
    Removes outdated, irrelevant, or low-value memories.
    Uses multi-factor scoring to identify prune candidates.
    """

    def __init__(self):
        self.min_age_hours: float = 72  # Don't prune anything < 3 days old
        self.max_importance_to_prune: float = 0.3
        self.min_access_gap_hours: float = 168  # Not accessed in 7 days

    def score_for_pruning(self, memory: MemoryItem) -> float:
        """
        Score how much a memory should be pruned. Higher = more pruneable.
        Returns 0-1 where 1 = definitely prune.
        """
        # Don't prune recent memories
        if memory.age_hours < self.min_age_hours:
            return 0.0

        # Factor 1: Age (older = more pruneable)
        age_factor = min(1.0, memory.age_hours / (30 * 24))  # Max at 30 days

        # Factor 2: Low importance
        importance_factor = 1.0 - memory.importance

        # Factor 3: Low access (not used recently)
        hours_since_access = (datetime.utcnow() - memory.last_accessed).total_seconds() / 3600
        access_factor = min(1.0, hours_since_access / self.min_access_gap_hours)

        # Factor 4: Low access count
        count_factor = 1.0 - min(1.0, memory.access_count / 10.0)

        # Weighted combination
        score = (
            0.2 * age_factor
            + 0.3 * importance_factor
            + 0.3 * access_factor
            + 0.2 * count_factor
        )
        return score

    def identify_candidates(
        self,
        memories: list[MemoryItem],
        max_prune_ratio: float = 0.2,
        score_threshold: float = 0.7,
    ) -> list[MemoryItem]:
        """Identify memories that should be pruned."""
        candidates = []
        for mem in memories:
            score = self.score_for_pruning(mem)
            if score >= score_threshold:
                candidates.append((score, mem))

        # Sort by score (most pruneable first)
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Limit to max_prune_ratio of total
        max_prune = int(len(memories) * max_prune_ratio)
        return [mem for _, mem in candidates[:max_prune]]

    def prune(
        self,
        memories: list[MemoryItem],
        max_prune_ratio: float = 0.2,
    ) -> tuple[list[MemoryItem], list[str]]:
        """
        Prune memories. Returns (remaining memories, pruned IDs).
        """
        to_prune = self.identify_candidates(memories, max_prune_ratio)
        pruned_ids = {m.id for m in to_prune}
        remaining = [m for m in memories if m.id not in pruned_ids]
        return remaining, list(pruned_ids)


# =============================================================================
# WORKING MEMORY MANAGER (Context Window)
# =============================================================================

class WorkingMemoryWindow:
    """
    Manages which memories fit into the LLM's context window.
    Implements a priority-based allocation of limited token budget.
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self._allocations: dict[str, int] = {
            "system_prompt": 1000,
            "user_message": 2000,
            "retrieved_memories": 3000,
            "working_state": 1000,
            "response_buffer": 1000,
        }

    @property
    def memory_budget(self) -> int:
        return self._allocations["retrieved_memories"]

    def set_budget(self, category: str, tokens: int):
        self._allocations[category] = tokens

    def fit_memories(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Select memories that fit within the allocated token budget."""
        budget = self.memory_budget
        selected = []
        used = 0

        for result in results:
            tokens = result.memory.token_count or len(result.memory.display_content) // 4
            if used + tokens > budget:
                # Try to fit summary instead
                if result.memory.summary:
                    summary_tokens = len(result.memory.summary) // 4
                    if used + summary_tokens <= budget:
                        selected.append(result)
                        used += summary_tokens
                        continue
                break
            selected.append(result)
            used += tokens

        return selected

    def format_for_prompt(self, results: list[RetrievalResult]) -> str:
        """Format retrieved memories for inclusion in the prompt."""
        if not results:
            return ""

        lines = ["## Relevant Memories", ""]
        for i, result in enumerate(results, 1):
            mem = result.memory
            content = mem.display_content
            age_str = self._format_age(mem.age_hours)
            lines.append(f"[{i}] ({mem.memory_type}, {age_str}) {content}")

        return "\n".join(lines)

    def _format_age(self, hours: float) -> str:
        if hours < 1:
            return "just now"
        elif hours < 24:
            return f"{int(hours)}h ago"
        elif hours < 168:
            return f"{int(hours/24)}d ago"
        else:
            return f"{int(hours/168)}w ago"


# =============================================================================
# UNIFIED RETRIEVAL SYSTEM
# =============================================================================

class MemoryRetrievalSystem:
    """
    Unified retrieval system orchestrating all strategies.
    Main entry point for memory retrieval operations.
    """

    def __init__(self, max_context_tokens: int = 8000):
        self.embedder = EmbeddingService()
        self.hybrid = HybridRetriever(self.embedder)
        self.context_selector = ContextAwareSelector(self.hybrid)
        self.summarizer = MemorySummarizer()
        self.consolidator = MemoryConsolidator(self.embedder, self.summarizer)
        self.pruner = MemoryPruner()
        self.window = WorkingMemoryWindow(max_context_tokens)
        self._memory_pool: list[MemoryItem] = []

    def add_memory(self, content: str, memory_type: str = "episodic", importance: float = 0.5, **kwargs) -> MemoryItem:
        """Add a memory to the pool."""
        mem = MemoryItem(
            content=content,
            memory_type=memory_type,
            embedding=self.embedder.embed(content),
            importance=importance,
            token_count=len(content) // 4,
            **kwargs,
        )
        self._memory_pool.append(mem)
        return mem

    def retrieve(
        self,
        query: str,
        task_type: str = "general",
        context: dict = None,
        include_formatting: bool = True,
    ) -> dict:
        """
        Main retrieval entry point.
        Returns scored memories fitted to context window.
        """
        # 1. Context-aware retrieval
        results = self.context_selector.select(query, self._memory_pool, task_type, context)

        # 2. Fit to context window
        fitted = self.window.fit_memories(results)

        # 3. Update access metadata
        for result in fitted:
            result.memory.last_accessed = datetime.utcnow()
            result.memory.access_count += 1

        output = {
            "results": fitted,
            "total_candidates": len(self._memory_pool),
            "retrieved": len(fitted),
            "task_type": task_type,
        }

        if include_formatting:
            output["formatted"] = self.window.format_for_prompt(fitted)

        return output

    def maintain(self) -> dict:
        """Run maintenance: summarize, consolidate, prune."""
        stats = {"summarized": 0, "consolidated": 0, "pruned": 0}

        # 1. Summarize verbose old memories
        for mem in self._memory_pool:
            if self.summarizer.should_summarize(mem):
                mem.summary = self.summarizer.summarize_single(mem)
                stats["summarized"] += 1

        # 2. Consolidate duplicates
        self._memory_pool, merged_ids = self.consolidator.run_consolidation(self._memory_pool)
        stats["consolidated"] = len(merged_ids)

        # 3. Prune low-value memories
        self._memory_pool, pruned_ids = self.pruner.prune(self._memory_pool)
        stats["pruned"] = len(pruned_ids)

        return stats

    @property
    def pool_size(self) -> int:
        return len(self._memory_pool)

    @property
    def total_tokens(self) -> int:
        return sum(m.token_count or len(m.content) // 4 for m in self._memory_pool)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main():
    print("=" * 60)
    print("MEMORY RETRIEVAL SYSTEM - DEMONSTRATION")
    print("=" * 60)

    system = MemoryRetrievalSystem(max_context_tokens=8000)

    # Add diverse memories
    print("\n--- Adding Memories ---")

    system.add_memory("User prefers TypeScript for all new projects", "semantic", importance=0.9, tags=["preference"])
    system.add_memory("Project uses Next.js 14 with App Router", "semantic", importance=0.8, tags=["tech_stack"])
    system.add_memory("Deployment failed yesterday due to memory limits on ECS", "episodic", importance=0.6)
    system.add_memory("User asked about database indexing strategies", "episodic", importance=0.4)
    system.add_memory("Team uses GitHub Actions for CI/CD with auto-deploy to staging", "procedural", importance=0.7)
    system.add_memory("PostgreSQL 15 with pgvector extension for embeddings", "semantic", importance=0.8)
    system.add_memory("User's coding style: functional, minimal classes, extensive type annotations", "semantic", importance=0.9)
    system.add_memory("Last code review feedback: improve error handling in API routes", "episodic", importance=0.5)

    # Simulate some older memories
    old_mem = system.add_memory("User explored using Redis for caching", "episodic", importance=0.3)
    old_mem.created_at = datetime.utcnow() - timedelta(days=30)

    print(f"Memory pool: {system.pool_size} memories, ~{system.total_tokens} tokens")

    # Retrieve for different contexts
    print("\n--- Retrieval: Question Answering ---")
    result = system.retrieve("What database and vector store do we use?", task_type="question_answering")
    print(f"Retrieved {result['retrieved']}/{result['total_candidates']} memories")
    print(result["formatted"])

    print("\n--- Retrieval: Code Generation ---")
    result = system.retrieve("Generate a new API endpoint", task_type="code_generation")
    print(f"Retrieved {result['retrieved']}/{result['total_candidates']} memories")
    for r in result["results"][:3]:
        print(f"  [{r.memory.memory_type}] score={r.final_score:.3f} | {r.memory.content[:60]}")

    print("\n--- Retrieval: Debugging ---")
    result = system.retrieve("Application is running out of memory", task_type="debugging")
    print(f"Retrieved {result['retrieved']}/{result['total_candidates']} memories")
    for r in result["results"][:3]:
        print(f"  [{r.memory.memory_type}] score={r.final_score:.3f} | {r.memory.content[:60]}")

    # Run maintenance
    print("\n--- Running Maintenance ---")
    stats = system.maintain()
    print(f"Maintenance stats: {stats}")
    print(f"Pool after maintenance: {system.pool_size} memories")


if __name__ == "__main__":
    main()
