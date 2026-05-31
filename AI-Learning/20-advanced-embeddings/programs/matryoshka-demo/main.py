"""
Matryoshka Embeddings Demo

Demonstrates how OpenAI's text-embedding-3-small supports variable dimensions,
allowing you to trade quality for storage/speed at query time.
"""

import os
import time
import numpy as np
from typing import List, Dict, Tuple

try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# --- Configuration ---

DIMENSIONS = [64, 128, 256, 512, 1536]
MODEL = "text-embedding-3-small"


# --- Document Corpus ---

DOCUMENTS = [
    "Machine learning algorithms learn patterns from data to make predictions",
    "Neural networks are inspired by biological neurons in the human brain",
    "Kubernetes orchestrates containerized applications across clusters",
    "Docker containers package applications with their dependencies",
    "Python is a versatile programming language popular in data science",
    "SQL databases use structured query language for data management",
    "Natural language processing enables computers to understand human language",
    "Reinforcement learning trains agents through reward and punishment signals",
    "Cloud computing provides on-demand computing resources over the internet",
    "Microservices architecture decomposes applications into small independent services",
    "Transfer learning reuses pre-trained models for new tasks with less data",
    "Graph databases store data as nodes and relationships for connected data",
    "Transformer models use self-attention to process sequential data in parallel",
    "DevOps practices combine development and operations for faster delivery",
    "Gradient descent optimizes neural network weights by minimizing loss functions",
]

QUERIES = [
    "how do neural networks learn",
    "container orchestration tools",
    "language understanding by computers",
    "optimizing deep learning models",
    "deploying applications to the cloud",
]


# --- Embedding Functions ---

def get_embeddings_openai(texts: List[str], dimensions: int) -> List[np.ndarray]:
    """Get embeddings from OpenAI API at specified dimensions."""
    client = OpenAI()
    response = client.embeddings.create(
        model=MODEL,
        input=texts,
        dimensions=dimensions,
    )
    return [np.array(item.embedding) for item in response.data]


def get_embeddings_simulated(texts: List[str], full_dim: int = 1536) -> Dict[str, np.ndarray]:
    """
    Simulate Matryoshka embeddings for demo purposes (no API key needed).
    Creates embeddings where first N dims are more informative.
    """
    embeddings = {}
    for i, text in enumerate(texts):
        # Create a full embedding with decreasing importance per dimension
        np.random.seed(hash(text) % 2**31)
        
        # Simulate Matryoshka property: first dims encode coarse semantics
        vec = np.random.randn(full_dim)
        
        # Make similar texts have similar first dimensions
        words = set(text.lower().split())
        # Semantic signal in first dimensions
        semantic_topics = {
            "ml": ["machine", "learning", "neural", "network", "model", "training"],
            "infra": ["kubernetes", "docker", "container", "cloud", "deploy"],
            "data": ["data", "database", "sql", "query"],
            "nlp": ["language", "natural", "processing", "transformer", "text"],
            "prog": ["python", "programming", "code", "software"],
        }
        
        for dim_offset, (topic, keywords) in enumerate(semantic_topics.items()):
            overlap = len(words & set(keywords))
            if overlap > 0:
                # Inject signal into first few dimensions per topic
                for d in range(dim_offset * 12, dim_offset * 12 + 12):
                    if d < full_dim:
                        vec[d] += overlap * 2.0
        
        vec = vec / np.linalg.norm(vec)
        embeddings[text] = vec
    
    return embeddings


def truncate_and_normalize(embedding: np.ndarray, dims: int) -> np.ndarray:
    """Truncate embedding to first N dims and re-normalize."""
    truncated = embedding[:dims]
    norm = np.linalg.norm(truncated)
    if norm > 0:
        return truncated / norm
    return truncated


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


# --- Search Functions ---

def search_at_dimension(
    query_emb: np.ndarray,
    doc_embs: List[np.ndarray],
    dims: int,
    top_k: int = 5
) -> List[Tuple[int, float]]:
    """Search using truncated embeddings at specified dimension."""
    q = truncate_and_normalize(query_emb, dims)
    scores = []
    for i, d_emb in enumerate(doc_embs):
        d = truncate_and_normalize(d_emb, dims)
        scores.append((i, cosine_similarity(q, d)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def adaptive_retrieval(
    query_emb: np.ndarray,
    doc_embs: List[np.ndarray],
    coarse_dims: int = 128,
    fine_dims: int = 1536,
    coarse_k: int = 8,
    fine_k: int = 3,
) -> List[Tuple[int, float]]:
    """
    Two-stage adaptive retrieval:
    Stage 1: Coarse search with fewer dimensions (fast, broad)
    Stage 2: Fine reranking with full dimensions (precise)
    """
    # Stage 1: Coarse retrieval
    coarse_results = search_at_dimension(query_emb, doc_embs, coarse_dims, top_k=coarse_k)
    candidate_ids = [idx for idx, _ in coarse_results]
    
    # Stage 2: Fine reranking of candidates only
    q_full = truncate_and_normalize(query_emb, fine_dims)
    fine_scores = []
    for idx in candidate_ids:
        d_full = truncate_and_normalize(doc_embs[idx], fine_dims)
        fine_scores.append((idx, cosine_similarity(q_full, d_full)))
    
    fine_scores.sort(key=lambda x: x[1], reverse=True)
    return fine_scores[:fine_k]


# --- Main Demo ---

def main():
    print("=" * 70)
    print("Matryoshka Embeddings Demo")
    print("=" * 70)
    
    # Determine mode
    use_api = HAS_OPENAI and os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your-api-key-here"
    
    if use_api:
        print(f"\nMode: LIVE (using OpenAI {MODEL})")
        print("Fetching embeddings at full dimensions...")
        all_texts = DOCUMENTS + QUERIES
        full_embeddings = get_embeddings_openai(all_texts, dimensions=1536)
        doc_embs = full_embeddings[:len(DOCUMENTS)]
        query_embs = full_embeddings[len(DOCUMENTS):]
    else:
        print("\nMode: SIMULATED (no API key found)")
        print("Using simulated Matryoshka embeddings for demonstration.")
        print("Set OPENAI_API_KEY in .env for real embeddings.\n")
        all_texts = DOCUMENTS + QUERIES
        emb_dict = get_embeddings_simulated(all_texts)
        doc_embs = [emb_dict[t] for t in DOCUMENTS]
        query_embs = [emb_dict[t] for t in QUERIES]
    
    # --- Demo 1: Quality vs Dimensions ---
    print("\n" + "=" * 70)
    print("DEMO 1: Search Quality at Different Dimensions")
    print("=" * 70)
    
    for qi, query in enumerate(QUERIES):
        print(f"\n{'─' * 60}")
        print(f"Query: \"{query}\"")
        print(f"{'─' * 60}")
        
        # Full-dimension results as ground truth
        full_results = search_at_dimension(query_embs[qi], doc_embs, 1536, top_k=3)
        ground_truth_ids = [idx for idx, _ in full_results]
        
        print(f"\n  {'Dims':<8} {'Top-3 Results':<50} {'Recall vs Full'}")
        print(f"  {'─'*8} {'─'*50} {'─'*15}")
        
        for dims in DIMENSIONS:
            results = search_at_dimension(query_embs[qi], doc_embs, dims, top_k=3)
            result_ids = [idx for idx, _ in results]
            
            # Recall: how many of the full-dim top-3 are in this top-3?
            recall = len(set(result_ids) & set(ground_truth_ids)) / len(ground_truth_ids)
            
            top_doc = DOCUMENTS[results[0][0]][:45] + "..."
            recall_bar = "█" * int(recall * 10)
            
            marker = " ← baseline" if dims == 1536 else ""
            print(f"  {dims:<8} [{results[0][0]:>2}] {top_doc:<47} {recall*100:>5.0f}% {recall_bar}{marker}")
    
    # --- Demo 2: Storage Savings ---
    print("\n\n" + "=" * 70)
    print("DEMO 2: Storage Savings")
    print("=" * 70)
    
    num_docs = 1_000_000  # Hypothetical 1M documents
    
    print(f"\n  Assuming {num_docs:,} documents:\n")
    print(f"  {'Dims':<8} {'Bytes/Vec':<12} {'Total Storage':<15} {'Savings':<10} {'Approx Quality'}")
    print(f"  {'─'*8} {'─'*12} {'─'*15} {'─'*10} {'─'*15}")
    
    base_storage = 1536 * 4 * num_docs
    for dims in DIMENSIONS:
        bytes_per_vec = dims * 4  # float32
        total_bytes = bytes_per_vec * num_docs
        savings = 1 - (total_bytes / base_storage)
        
        # Approximate quality based on typical Matryoshka results
        quality_map = {64: "85-88%", 128: "90-93%", 256: "95-97%", 512: "97-98%", 1536: "100%"}
        quality = quality_map[dims]
        
        total_gb = total_bytes / (1024**3)
        print(f"  {dims:<8} {bytes_per_vec:<12} {total_gb:<13.1f}GB {savings*100:<8.0f}%  {quality}")
    
    # --- Demo 3: Adaptive Retrieval ---
    print("\n\n" + "=" * 70)
    print("DEMO 3: Adaptive Retrieval (Coarse → Fine)")
    print("=" * 70)
    
    for qi, query in enumerate(QUERIES[:3]):
        print(f"\n{'─' * 60}")
        print(f"Query: \"{query}\"")
        
        # Simulate timing
        t0 = time.perf_counter()
        coarse_results = search_at_dimension(query_embs[qi], doc_embs, 128, top_k=8)
        t_coarse = time.perf_counter() - t0
        
        t0 = time.perf_counter()
        adaptive_results = adaptive_retrieval(query_embs[qi], doc_embs, 
                                              coarse_dims=128, fine_dims=1536,
                                              coarse_k=8, fine_k=3)
        t_adaptive = time.perf_counter() - t0
        
        t0 = time.perf_counter()
        full_results = search_at_dimension(query_embs[qi], doc_embs, 1536, top_k=3)
        t_full = time.perf_counter() - t0
        
        print(f"\n  Stage 1 (128-dim, top-8 candidates):")
        for idx, score in coarse_results[:5]:
            print(f"    [{idx:>2}] score={score:.3f}  {DOCUMENTS[idx][:50]}...")
        
        print(f"\n  Stage 2 (1536-dim rerank of 8 candidates → top-3):")
        for idx, score in adaptive_results:
            marker = " ✓" if idx in [r[0] for r in full_results] else " ✗"
            print(f"    [{idx:>2}] score={score:.3f}  {DOCUMENTS[idx][:50]}...{marker}")
        
        print(f"\n  Full search (1536-dim, top-3):")
        for idx, score in full_results:
            print(f"    [{idx:>2}] score={score:.3f}  {DOCUMENTS[idx][:50]}...")
        
        # Quality comparison
        adaptive_ids = set(r[0] for r in adaptive_results)
        full_ids = set(r[0] for r in full_results)
        overlap = len(adaptive_ids & full_ids) / len(full_ids)
        print(f"\n  Adaptive vs Full agreement: {overlap*100:.0f}%")
    
    # --- Summary ---
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
  Matryoshka embeddings let you:
  
  1. REDUCE STORAGE: Use 256 dims instead of 1536 for 6x savings
     with only ~3-5% quality loss.
  
  2. SPEED UP SEARCH: Fewer dimensions = faster distance computation.
     128-dim search is ~12x faster than 1536-dim.
  
  3. ADAPTIVE RETRIEVAL: Use coarse dims for initial candidate selection,
     then full dims for precise reranking. Gets near-full quality at
     a fraction of the compute cost.
  
  4. CHOOSE AT QUERY TIME: Embed once at full dimensions, truncate
     as needed. No re-embedding required to change the tradeoff.
""")


if __name__ == "__main__":
    main()
