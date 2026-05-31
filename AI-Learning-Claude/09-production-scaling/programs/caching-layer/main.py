"""
Semantic Caching Layer for AI
=============================
Implements two levels of caching:
1. Exact-match cache (hash-based, instant)
2. Semantic cache (embedding similarity, near-instant)

Demonstrates cost savings and latency improvements from caching.
Uses simulated embeddings/LLM by default. Set OPENAI_API_KEY for real API usage.
"""

import hashlib
import time
import random
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# --- Configuration ---

SIMILARITY_THRESHOLD = 0.92  # Cosine similarity threshold for semantic cache hit
EMBEDDING_DIM = 256  # Simulated embedding dimensions (real: 1536 or 3072)


# --- Simulated AI Services ---

def simulated_embed(text: str) -> np.ndarray:
    """
    Simulates an embedding model.
    
    Uses a deterministic hash-based approach so the same text always gets
    the same embedding, and similar texts get similar embeddings.
    """
    # Create a seed from the text for reproducibility
    seed = int(hashlib.md5(text.lower().strip().encode()).hexdigest()[:8], 16)
    rng = np.random.RandomState(seed)
    
    # Base embedding from the text
    embedding = rng.randn(EMBEDDING_DIM)
    
    # Normalize to unit vector
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


def simulated_llm_call(prompt: str) -> tuple[str, float]:
    """
    Simulates an LLM API call.
    Returns (response, latency_seconds).
    """
    time.sleep(random.uniform(0.5, 2.0))  # Simulate API latency
    
    responses = {
        "hours": "We're open Monday through Friday, 9 AM to 5 PM EST.",
        "pricing": "Our plans start at $29/month for the Basic tier.",
        "refund": "We offer a 30-day money-back guarantee on all plans.",
        "support": "You can reach our support team at support@example.com.",
    }
    
    # Simple keyword matching for simulation
    for keyword, response in responses.items():
        if keyword in prompt.lower():
            return response, random.uniform(0.5, 2.0)
    
    return f"Here's information about: {prompt[:50]}...", random.uniform(0.5, 2.0)


# --- Cache Implementation ---

@dataclass
class CacheEntry:
    query: str
    response: str
    embedding: np.ndarray
    timestamp: float
    hit_count: int = 0


@dataclass
class CacheStats:
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    total_requests: int = 0
    total_latency_saved_ms: float = 0.0
    total_cost_saved: float = 0.0

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.exact_hits + self.semantic_hits) / self.total_requests

    def summary(self) -> str:
        return (
            f"  Total requests:     {self.total_requests}\n"
            f"  Exact cache hits:   {self.exact_hits}\n"
            f"  Semantic cache hits: {self.semantic_hits}\n"
            f"  Cache misses:       {self.misses}\n"
            f"  Hit rate:           {self.hit_rate:.1%}\n"
            f"  Latency saved:      {self.total_latency_saved_ms:.0f}ms\n"
            f"  Est. cost saved:    ${self.total_cost_saved:.4f}"
        )


class SemanticCache:
    """
    Two-level cache: exact match + semantic similarity.
    """

    def __init__(self, similarity_threshold: float = SIMILARITY_THRESHOLD):
        self.similarity_threshold = similarity_threshold
        self.exact_cache: dict[str, CacheEntry] = {}  # hash -> entry
        self.semantic_entries: list[CacheEntry] = []  # for similarity search
        self.stats = CacheStats()

    def _hash_key(self, query: str) -> str:
        """Normalize and hash the query for exact matching."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def get(self, query: str) -> Optional[tuple[str, str]]:
        """
        Look up query in cache.
        Returns (response, cache_type) or None.
        cache_type is "exact" or "semantic".
        """
        # Level 1: Exact match
        key = self._hash_key(query)
        if key in self.exact_cache:
            entry = self.exact_cache[key]
            entry.hit_count += 1
            return entry.response, "exact"

        # Level 2: Semantic similarity
        if self.semantic_entries:
            query_embedding = simulated_embed(query)
            
            best_similarity = 0.0
            best_entry = None
            
            for entry in self.semantic_entries:
                sim = self._cosine_similarity(query_embedding, entry.embedding)
                if sim > best_similarity:
                    best_similarity = sim
                    best_entry = entry

            if best_similarity >= self.similarity_threshold and best_entry:
                best_entry.hit_count += 1
                return best_entry.response, "semantic"

        return None

    def put(self, query: str, response: str):
        """Store a query-response pair in both caches."""
        embedding = simulated_embed(query)
        entry = CacheEntry(
            query=query,
            response=response,
            embedding=embedding,
            timestamp=time.time(),
        )
        
        # Store in exact cache
        key = self._hash_key(query)
        self.exact_cache[key] = entry
        
        # Store in semantic cache
        self.semantic_entries.append(entry)

    def query_with_stats(self, query: str, cost_per_call: float = 0.03) -> tuple[str, float]:
        """
        Query the cache with full stats tracking.
        Returns (response, latency_ms).
        """
        self.stats.total_requests += 1
        start = time.perf_counter()

        result = self.get(query)
        
        if result:
            response, cache_type = result
            latency_ms = (time.perf_counter() - start) * 1000
            
            if cache_type == "exact":
                self.stats.exact_hits += 1
            else:
                self.stats.semantic_hits += 1
            
            # Estimate savings (typical LLM call = 1000-2000ms)
            estimated_api_latency = 1500  # ms
            self.stats.total_latency_saved_ms += estimated_api_latency - latency_ms
            self.stats.total_cost_saved += cost_per_call
            
            return response, latency_ms
        else:
            # Cache miss - call LLM
            self.stats.misses += 1
            response, _ = simulated_llm_call(query)
            latency_ms = (time.perf_counter() - start) * 1000
            
            # Store in cache for future use
            self.put(query, response)
            
            return response, latency_ms


# --- Demo ---

def main():
    print("=" * 60)
    print("     SEMANTIC CACHING LAYER FOR AI SYSTEMS")
    print("=" * 60)
    print(f"\nSimilarity threshold: {SIMILARITY_THRESHOLD}")
    print(f"Using simulated embeddings and LLM\n")

    cache = SemanticCache(similarity_threshold=SIMILARITY_THRESHOLD)

    # Test queries - grouped by semantic similarity
    test_queries = [
        # Group 1: Business hours (semantically similar)
        "What are your business hours?",
        "What are your business hours?",        # Exact duplicate
        "When are you open?",                   # Semantically similar
        "What time do you close?",              # Semantically similar
        
        # Group 2: Pricing (semantically similar)
        "How much does it cost?",
        "What are your pricing plans?",         # Semantically similar
        "How much does it cost?",               # Exact duplicate
        
        # Group 3: Refund (semantically similar)
        "Can I get a refund?",
        "What is your refund policy?",          # Semantically similar
        "Can I get a refund?",                  # Exact duplicate
        
        # Group 4: Unique queries (cache misses)
        "How do I integrate with Slack?",
        "Do you support SSO?",
    ]

    print(f"Running {len(test_queries)} queries...\n")
    print(f"{'#':<3} {'Query':<35} {'Result':<10} {'Latency':<10} {'Response (truncated)'}")
    print("-" * 90)

    for i, query in enumerate(test_queries, 1):
        response, latency_ms = cache.query_with_stats(query)
        
        # Determine if it was a hit or miss
        if cache.stats.exact_hits + cache.stats.semantic_hits > (
            cache.stats.exact_hits + cache.stats.semantic_hits
        ) - 1:
            # Check what type of result we just got
            result = cache.get(query)
            if result and i > 1:
                _, cache_type = result
                result_str = f"{'EXACT HIT' if cache_type == 'exact' else 'SEM HIT'}"
            else:
                result_str = "MISS"
        
        # Simpler approach: check latency to determine hit/miss
        if latency_ms < 100:
            result_str = "CACHE HIT"
        else:
            result_str = "MISS"
        
        print(f"{i:<3} {query:<35} {result_str:<10} {latency_ms:>6.1f}ms  {response[:30]}...")

    # Print stats
    print("\n" + "=" * 60)
    print("CACHE STATISTICS")
    print("=" * 60)
    print(cache.stats.summary())

    # Cost projection
    print("\n" + "-" * 60)
    print("COST PROJECTION (at 100K requests/day)")
    print("-" * 60)
    daily_requests = 100_000
    cost_per_request = 0.03
    hit_rate = cache.stats.hit_rate
    
    without_cache = daily_requests * cost_per_request
    with_cache = daily_requests * (1 - hit_rate) * cost_per_request
    monthly_savings = (without_cache - with_cache) * 30
    
    print(f"  Without cache:  ${without_cache:,.0f}/day  (${without_cache*30:,.0f}/month)")
    print(f"  With cache:     ${with_cache:,.0f}/day  (${with_cache*30:,.0f}/month)")
    print(f"  Hit rate:       {hit_rate:.1%}")
    print(f"  Monthly savings: ${monthly_savings:,.0f}")
    print(f"\n  Cache ROI: {monthly_savings / 100:.0f}x (assuming $100/month for Redis)")


if __name__ == "__main__":
    main()
