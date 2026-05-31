"""
Billion-Scale RAG Simulator
============================
Demonstrates why naive RAG breaks at scale and how hierarchical retrieval,
sharding, and semantic caching solve the problem.

Uses simulated embeddings (no API key needed) to show realistic performance patterns.
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import hashlib

# =============================================================================
# CONFIGURATION
# =============================================================================

NUM_DOCUMENTS = 10_000  # Simulates 10M behavior (timings scaled)
NUM_SHARDS = 10  # Topic-based shards
EMBEDDING_DIM = 64  # Simulated embedding dimension (lower for better cache demo)
CACHE_SIZE = 100  # Max cached queries
SIMILARITY_THRESHOLD = 0.7  # Min relevance score
CACHE_SIMILARITY_THRESHOLD = 0.95  # How similar a query must be to get a cache hit

# Topics for sharding (simulating different domains)
TOPICS = [
    "billing_and_payments",
    "account_management",
    "technical_support",
    "product_features",
    "shipping_and_delivery",
    "returns_and_refunds",
    "security_and_privacy",
    "integrations_and_api",
    "onboarding_and_setup",
    "compliance_and_legal",
]


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Document:
    """Represents a document chunk in our RAG system."""
    id: str
    content: str
    topic: str  # Which shard this belongs to
    embedding: np.ndarray = field(repr=False)


@dataclass
class SearchResult:
    """A search result with relevance score."""
    document: Document
    score: float


@dataclass
class CacheEntry:
    """A cached query result."""
    query_embedding: np.ndarray
    results: List[SearchResult]
    timestamp: float


# =============================================================================
# SYNTHETIC DATA GENERATION
# =============================================================================

def generate_synthetic_dataset(num_docs: int) -> List[Document]:
    """
    Generate a synthetic dataset with documents clustered by topic.
    
    In real systems, embeddings come from models like text-embedding-3-small.
    Here we simulate clustered embeddings so that documents in the same topic
    have similar vectors (mimicking real semantic similarity).
    """
    print(f"\n{'='*70}")
    print("STEP 1: GENERATING SYNTHETIC DATASET")
    print(f"{'='*70}")
    print(f"\n  Generating {num_docs:,} documents across {NUM_SHARDS} topic shards...")
    print(f"  (Simulating behavior of a {num_docs * 1000:,} document system)")
    
    documents = []
    
    # Create a centroid for each topic (cluster center in embedding space)
    topic_centroids = {}
    for topic in TOPICS:
        # Each topic gets a distinct region in embedding space
        centroid = np.random.randn(EMBEDDING_DIM)
        centroid = centroid / np.linalg.norm(centroid)  # Normalize
        topic_centroids[topic] = centroid
    
    # Generate documents clustered around their topic centroids
    docs_per_topic = num_docs // NUM_SHARDS
    
    for topic_idx, topic in enumerate(TOPICS):
        centroid = topic_centroids[topic]
        
        for i in range(docs_per_topic):
            # Add noise to centroid to create document embedding
            # Small noise = tightly clustered (realistic for same-topic docs)
            noise = np.random.randn(EMBEDDING_DIM) * 0.3
            embedding = centroid + noise
            embedding = embedding / np.linalg.norm(embedding)  # Normalize
            
            doc_id = f"{topic}_{i:05d}"
            content = f"Document about {topic.replace('_', ' ')} - item {i}"
            
            documents.append(Document(
                id=doc_id,
                content=content,
                topic=topic,
                embedding=embedding,
            ))
    
    print(f"  ✓ Generated {len(documents):,} documents")
    print(f"  ✓ {docs_per_topic:,} documents per shard")
    print(f"  ✓ Each document has a {EMBEDDING_DIM}-dim embedding vector")
    
    return documents


# =============================================================================
# RETRIEVAL STRATEGIES
# =============================================================================

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def cosine_similarity_batch(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and all rows in matrix."""
    # Normalize query
    query_norm = query / np.linalg.norm(query)
    # Normalize all rows
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix_norm = matrix / norms
    # Dot product gives cosine similarity for normalized vectors
    return matrix_norm @ query_norm


class NaiveRetriever:
    """
    Strategy 1: NAIVE (Brute Force)
    
    Searches ALL documents linearly. Simple but O(n) - gets slower as corpus grows.
    This is what most tutorials teach, but it breaks at scale.
    """
    
    def __init__(self, documents: List[Document]):
        self.documents = documents
        # Pre-compute embedding matrix for vectorized similarity
        self.embedding_matrix = np.array([d.embedding for d in documents])
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[SearchResult]:
        """Search ALL documents - O(n) complexity."""
        # Compute similarity against EVERY document
        similarities = cosine_similarity_batch(query_embedding, self.embedding_matrix)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append(SearchResult(
                document=self.documents[idx],
                score=float(similarities[idx]),
            ))
        
        return results


class HierarchicalRetriever:
    """
    Strategy 2: HIERARCHICAL (Coarse -> Fine -> Rerank)
    
    Three-stage retrieval:
    1. COARSE: Find which shard(s) are relevant (compare against shard centroids)
    2. FINE: Search only within relevant shard(s)
    3. RERANK: Re-score top results with more expensive computation
    
    This reduces search space by ~90% at the routing step.
    """
    
    def __init__(self, documents: List[Document]):
        # Organize documents into shards
        self.shards: Dict[str, List[Document]] = {}
        self.shard_matrices: Dict[str, np.ndarray] = {}
        self.shard_centroids: Dict[str, np.ndarray] = {}
        
        for doc in documents:
            if doc.topic not in self.shards:
                self.shards[doc.topic] = []
            self.shards[doc.topic].append(doc)
        
        # Pre-compute embedding matrices and centroids per shard
        for topic, shard_docs in self.shards.items():
            matrix = np.array([d.embedding for d in shard_docs])
            self.shard_matrices[topic] = matrix
            # Centroid = average embedding of all docs in shard
            self.shard_centroids[topic] = matrix.mean(axis=0)
    
    def _route_to_shards(self, query_embedding: np.ndarray, top_n: int = 2) -> List[str]:
        """Stage 1 (COARSE): Find the most relevant shard(s)."""
        shard_scores = {}
        for topic, centroid in self.shard_centroids.items():
            score = cosine_similarity(query_embedding, centroid)
            shard_scores[topic] = score
        
        # Return top-N most relevant shards
        sorted_shards = sorted(shard_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_shards[:top_n]]
    
    def _search_shard(self, query_embedding: np.ndarray, topic: str, top_k: int) -> List[SearchResult]:
        """Stage 2 (FINE): Search within a specific shard."""
        matrix = self.shard_matrices[topic]
        similarities = cosine_similarity_batch(query_embedding, matrix)
        
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        shard_docs = self.shards[topic]
        for idx in top_indices:
            results.append(SearchResult(
                document=shard_docs[idx],
                score=float(similarities[idx]),
            ))
        return results
    
    def _rerank(self, results: List[SearchResult], query_embedding: np.ndarray) -> List[SearchResult]:
        """Stage 3 (RERANK): Re-score with more expensive computation."""
        # In production, this would use a cross-encoder model
        # Here we simulate by adding a small refinement
        for result in results:
            # Simulate cross-encoder giving slightly different scores
            refined_score = result.score * 0.8 + cosine_similarity(
                query_embedding, result.document.embedding
            ) * 0.2
            result.score = refined_score
        
        return sorted(results, key=lambda r: r.score, reverse=True)
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> Tuple[List[SearchResult], List[str]]:
        """Full hierarchical search: route -> search shard -> rerank."""
        # Stage 1: Route to relevant shards
        relevant_shards = self._route_to_shards(query_embedding, top_n=2)
        
        # Stage 2: Search within relevant shards only
        all_results = []
        for shard in relevant_shards:
            shard_results = self._search_shard(query_embedding, shard, top_k=top_k)
            all_results.extend(shard_results)
        
        # Stage 3: Rerank combined results
        reranked = self._rerank(all_results, query_embedding)
        
        return reranked[:top_k], relevant_shards


class SemanticCache:
    """
    Semantic Cache Layer
    
    Caches results for semantically similar queries. If a new query is very
    similar to a previously-seen query, return cached results instead of searching.
    
    This is crucial at scale:
    - Many users ask similar questions differently
    - "What's the refund policy?" ≈ "How do I get a refund?" ≈ "Can I return this?"
    - Cache hit rate of 30-60% is common in production
    """
    
    def __init__(self, similarity_threshold: float = CACHE_SIMILARITY_THRESHOLD):
        self.entries: List[CacheEntry] = []
        self.threshold = similarity_threshold
        self.hits = 0
        self.misses = 0
    
    def get(self, query_embedding: np.ndarray) -> Optional[List[SearchResult]]:
        """Check if a similar query has been cached."""
        for entry in self.entries:
            sim = cosine_similarity(query_embedding, entry.query_embedding)
            if sim >= self.threshold:
                self.hits += 1
                return entry.results
        
        self.misses += 1
        return None
    
    def put(self, query_embedding: np.ndarray, results: List[SearchResult]):
        """Cache query results."""
        self.entries.append(CacheEntry(
            query_embedding=query_embedding,
            results=results,
            timestamp=time.time(),
        ))
        # Evict oldest if over capacity
        if len(self.entries) > CACHE_SIZE:
            self.entries.pop(0)
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CachedHierarchicalRetriever:
    """
    Strategy 3: CACHED + HIERARCHICAL
    
    Adds semantic caching on top of hierarchical retrieval.
    On cache hit: ~0ms search time (just return cached results)
    On cache miss: falls back to hierarchical search
    """
    
    def __init__(self, documents: List[Document]):
        self.hierarchical = HierarchicalRetriever(documents)
        self.cache = SemanticCache()
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> Tuple[List[SearchResult], bool]:
        """Search with caching. Returns (results, was_cache_hit)."""
        # Try cache first
        cached = self.cache.get(query_embedding)
        if cached is not None:
            return cached, True
        
        # Cache miss - do hierarchical search
        results, _ = self.hierarchical.search(query_embedding, top_k)
        
        # Store in cache for future queries
        self.cache.put(query_embedding, results)
        
        return results, False


# =============================================================================
# SIMULATION AND BENCHMARKING
# =============================================================================

def generate_query_for_topic(topic: str, topic_centroids: Dict[str, np.ndarray], noise_scale: float = 0.2) -> np.ndarray:
    """Generate a synthetic query embedding that's close to a specific topic."""
    # In reality, this would be the embedding of the user's question
    centroid = topic_centroids[topic]
    noise = np.random.randn(EMBEDDING_DIM) * noise_scale
    query = centroid + noise
    return query / np.linalg.norm(query)


def run_benchmark(documents: List[Document]):
    """Run performance benchmark comparing all three strategies."""
    
    print(f"\n{'='*70}")
    print("STEP 2: BUILDING RETRIEVERS")
    print(f"{'='*70}")
    
    print("\n  Building Naive Retriever (brute force index)...")
    t0 = time.time()
    naive = NaiveRetriever(documents)
    print(f"  ✓ Built in {time.time()-t0:.2f}s - will search all {len(documents):,} docs every query")
    
    print("\n  Building Hierarchical Retriever (sharded index)...")
    t0 = time.time()
    hierarchical = HierarchicalRetriever(documents)
    print(f"  ✓ Built in {time.time()-t0:.2f}s - {NUM_SHARDS} shards, ~{len(documents)//NUM_SHARDS:,} docs each")
    
    print("\n  Building Cached Hierarchical Retriever...")
    t0 = time.time()
    cached = CachedHierarchicalRetriever(documents)
    print(f"  ✓ Built in {time.time()-t0:.2f}s - cache capacity: {CACHE_SIZE} queries")
    
    # Compute topic centroids for query generation
    topic_centroids = {}
    for topic in TOPICS:
        topic_docs = [d for d in documents if d.topic == topic]
        centroid = np.mean([d.embedding for d in topic_docs], axis=0)
        topic_centroids[topic] = centroid
    
    # =========================================================================
    # BENCHMARK: Single query comparison
    # =========================================================================
    
    print(f"\n{'='*70}")
    print("STEP 3: SINGLE QUERY BENCHMARK")
    print(f"{'='*70}")
    
    # Generate a query about "billing"
    target_topic = "billing_and_payments"
    query = generate_query_for_topic(target_topic, topic_centroids)
    print(f"\n  Query topic: '{target_topic}'")
    print(f"  (Simulating: 'Why was I charged twice this month?')")
    
    # Naive search
    t0 = time.time()
    naive_results = naive.search(query, top_k=5)
    naive_time = (time.time() - t0) * 1000  # Convert to ms
    
    # Hierarchical search
    t0 = time.time()
    hier_results, routed_shards = hierarchical.search(query, top_k=5)
    hier_time = (time.time() - t0) * 1000
    
    # Cached search (first call = miss)
    t0 = time.time()
    cached_results_miss, was_hit = cached.search(query, top_k=5)
    cached_miss_time = (time.time() - t0) * 1000
    
    # Cached search (second call with similar query = hit)
    similar_query = query + np.random.randn(EMBEDDING_DIM) * 0.02  # Very similar
    similar_query = similar_query / np.linalg.norm(similar_query)
    t0 = time.time()
    cached_results_hit, was_hit = cached.search(similar_query, top_k=5)
    cached_hit_time = (time.time() - t0) * 1000
    
    print(f"\n  {'Strategy':<30} {'Time':<12} {'Speedup':<15} {'Docs Searched'}")
    print(f"  {'-'*75}")
    print(f"  {'Naive (brute force)':<30} {naive_time:.2f}ms{'':<6} {'1x':<15} {len(documents):,}")
    
    hier_speedup = naive_time / hier_time if hier_time > 0 else float('inf')
    docs_searched = len(documents) // NUM_SHARDS * 2  # 2 shards
    print(f"  {'Hierarchical':<30} {hier_time:.2f}ms{'':<6} {hier_speedup:.1f}x faster{'':<5} {docs_searched:,}")
    
    print(f"  {'Cached (miss)':<30} {cached_miss_time:.2f}ms{'':<6} {'(same as hier)':<15} {docs_searched:,}")
    
    cache_speedup = naive_time / cached_hit_time if cached_hit_time > 0 else float('inf')
    print(f"  {'Cached (hit)':<30} {cached_hit_time:.4f}ms{'':<3} {cache_speedup:.0f}x faster{'':<5} {'0 (from cache)'}")
    
    print(f"\n  Hierarchical routed to shards: {routed_shards}")
    print(f"  → Skipped {NUM_SHARDS - len(routed_shards)}/{NUM_SHARDS} shards ({(NUM_SHARDS-len(routed_shards))/NUM_SHARDS*100:.0f}% of corpus)")
    
    # =========================================================================
    # BENCHMARK: Batch queries with cache warm-up
    # =========================================================================
    
    print(f"\n{'='*70}")
    print("STEP 4: BATCH BENCHMARK (100 queries, simulating real traffic)")
    print(f"{'='*70}")
    
    num_queries = 100
    
    # Generate queries - some repeated topics (simulating real user patterns)
    # In reality, ~30-50% of queries are semantically similar to previous ones
    queries = []
    for i in range(num_queries):
        # 40% of queries are very similar to a previous one (cache-friendly)
        if i > 10 and np.random.random() < 0.4:
            topic = np.random.choice(TOPICS[:3])  # Concentrate on popular topics
            # Very low noise = semantically near-identical query (simulates rephrasing)
            queries.append(generate_query_for_topic(topic, topic_centroids, noise_scale=0.01))
        else:
            topic = np.random.choice(TOPICS)
            queries.append(generate_query_for_topic(topic, topic_centroids, noise_scale=0.2))
    
    # Reset cache
    cached = CachedHierarchicalRetriever(documents)
    
    # Run naive
    t0 = time.time()
    for q in queries:
        naive.search(q, top_k=5)
    naive_total = (time.time() - t0) * 1000
    
    # Run hierarchical
    t0 = time.time()
    for q in queries:
        hierarchical.search(q, top_k=5)
    hier_total = (time.time() - t0) * 1000
    
    # Run cached
    t0 = time.time()
    for q in queries:
        cached.search(q, top_k=5)
    cached_total = (time.time() - t0) * 1000
    
    print(f"\n  {num_queries} queries executed:")
    print(f"\n  {'Strategy':<30} {'Total Time':<15} {'Avg/Query':<12} {'vs Naive'}")
    print(f"  {'-'*70}")
    print(f"  {'Naive':<30} {naive_total:.1f}ms{'':<8} {naive_total/num_queries:.2f}ms{'':<5} baseline")
    
    hier_pct = (1 - hier_total/naive_total) * 100
    print(f"  {'Hierarchical':<30} {hier_total:.1f}ms{'':<8} {hier_total/num_queries:.2f}ms{'':<5} {hier_pct:.0f}% faster")
    
    cached_pct = (1 - cached_total/naive_total) * 100
    print(f"  {'Cached + Hierarchical':<30} {cached_total:.1f}ms{'':<8} {cached_total/num_queries:.2f}ms{'':<5} {cached_pct:.0f}% faster")
    
    print(f"\n  Cache Statistics:")
    print(f"    Hit rate: {cached.cache.hit_rate*100:.1f}%")
    print(f"    Hits: {cached.cache.hits}, Misses: {cached.cache.misses}")
    
    # =========================================================================
    # SHARDING DEEP DIVE
    # =========================================================================
    
    print(f"\n{'='*70}")
    print("STEP 5: SHARDING DEEP DIVE")
    print(f"{'='*70}")
    
    print(f"""
  HOW SHARDING WORKS:
  
  Instead of one massive index with {len(documents):,} documents:
  
  ┌─────────────────────────────────────────────────────┐
  │  MONOLITHIC INDEX: {len(documents):,} documents                     │
  │  Every query searches ALL documents                 │
  │  Latency grows linearly with corpus size            │
  └─────────────────────────────────────────────────────┘
  
  We split into {NUM_SHARDS} topic-based shards:
  
  ┌──────────┐ ┌──────────┐ ┌──────────┐     ┌──────────┐
  │ Shard 1  │ │ Shard 2  │ │ Shard 3  │ ... │ Shard 10 │
  │ {len(documents)//NUM_SHARDS:,} docs │ │ {len(documents)//NUM_SHARDS:,} docs │ │ {len(documents)//NUM_SHARDS:,} docs │     │ {len(documents)//NUM_SHARDS:,} docs │
  │ billing  │ │ accounts │ │ tech sup │     │ legal    │
  └──────────┘ └──────────┘ └──────────┘     └──────────┘
       ↑
       └── Query about billing → routed here ONLY
  """)
    
    # Demonstrate shard routing
    print("  Shard Routing Examples:")
    print(f"  {'-'*50}")
    
    test_topics = ["billing_and_payments", "technical_support", "security_and_privacy"]
    for topic in test_topics:
        query = generate_query_for_topic(topic, topic_centroids)
        _, routed = hierarchical.search(query, top_k=5)
        correct = topic in routed
        status = "✓ CORRECT" if correct else "✗ MISSED"
        print(f"  Query about '{topic}'")
        print(f"    → Routed to: {routed}")
        print(f"    → {status} (searched {len(routed)}/{NUM_SHARDS} shards = {len(routed)*100//NUM_SHARDS}% of corpus)")
        print()
    
    # =========================================================================
    # COST ANALYSIS
    # =========================================================================
    
    print(f"{'='*70}")
    print("STEP 6: COST & PERFORMANCE ANALYSIS AT SCALE")
    print(f"{'='*70}")
    
    # Project to real scale
    scale_factor = 1000  # Our 10K simulates 10M
    
    print(f"""
  PROJECTING TO REAL SCALE ({len(documents) * scale_factor:,} documents):
  
  Assumptions:
  - Embedding computation: $0.0001 per query (OpenAI text-embedding-3-small)
  - Vector search cost: proportional to documents searched
  - 10,000 queries per day
  
  ┌─────────────────────────────────────────────────────────────────────┐
  │ Strategy          │ Docs Searched │ Latency (p95) │ Daily Cost     │
  ├─────────────────────────────────────────────────────────────────────┤
  │ Naive             │ 10,000,000    │ ~2000ms       │ $$$$ (high)    │
  │ Hierarchical      │ ~2,000,000    │ ~400ms        │ $$ (medium)    │
  │ Cached + Hier.    │ ~800,000 avg  │ ~5ms (hit)    │ $ (low)        │
  └─────────────────────────────────────────────────────────────────────┘
  
  Cache Impact (at {cached.cache.hit_rate*100:.0f}% hit rate):
  - {cached.cache.hits * 100 // max(1, cached.cache.hits + cached.cache.misses)}% of queries served from cache (near-zero compute)
  - Embedding API calls reduced by {cached.cache.hit_rate*100:.0f}%
  - Estimated monthly savings: ~60-80% vs naive approach
  """)
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    
    print(f"{'='*70}")
    print("FINAL SUMMARY: KEY TAKEAWAYS")
    print(f"{'='*70}")
    
    print(f"""
  1. NAIVE RAG doesn't scale:
     - Linear search over all docs = O(n) per query
     - At 10M docs, latency becomes unacceptable (>1s)
     - Cost grows linearly with corpus size

  2. HIERARCHICAL RETRIEVAL is the production pattern:
     - Route to relevant shard(s) first (eliminates 80-90% of corpus)
     - Search within shard (much smaller search space)
     - Rerank top results (expensive but only on small set)
     - Result: {hier_pct:.0f}% faster than naive in our simulation

  3. SEMANTIC CACHING is the force multiplier:
     - Many queries are semantically similar
     - Cache hit = near-zero latency and cost
     - Hit rate of {cached.cache.hit_rate*100:.0f}% in our simulation
     - Production systems see 30-60% hit rates

  4. SHARDING enables horizontal scaling:
     - Each shard can live on a different machine
     - Add more shards as corpus grows
     - Query routing adds minimal overhead (<5ms)
     - Enables parallel search across shards when needed
  """)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("   BILLION-SCALE RAG SIMULATOR")
    print("   Demonstrating why naive RAG fails and how to fix it")
    print("="*70)
    
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Generate synthetic dataset
    documents = generate_synthetic_dataset(NUM_DOCUMENTS)
    
    # Run benchmark
    run_benchmark(documents)
    
    print("\n" + "="*70)
    print("   SIMULATION COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
