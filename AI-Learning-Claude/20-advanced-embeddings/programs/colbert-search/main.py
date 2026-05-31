"""
ColBERT-Style Multi-Vector Search Simulation

Demonstrates how token-level embeddings with MaxSim scoring
outperform single-vector embeddings for certain query types.

Uses simulated embeddings (no API calls needed) to illustrate the concept.
"""

import numpy as np
from typing import List, Tuple, Dict


# --- Simulated Embedding Functions ---

# We simulate embeddings by creating vectors where similar words
# have high cosine similarity (using a shared semantic space)

WORD_VECTORS = {}
EMBEDDING_DIM = 64  # Simplified dimension for demonstration


def get_word_vector(word: str) -> np.ndarray:
    """Get a simulated word vector. Similar words get similar vectors."""
    if word in WORD_VECTORS:
        return WORD_VECTORS[word]
    
    # Create semantic clusters for demonstration
    semantic_groups = {
        "machine": 0, "learning": 1, "algorithm": 2, "model": 3,
        "neural": 4, "network": 5, "deep": 6, "training": 7,
        "python": 8, "java": 9, "code": 10, "programming": 11,
        "deploy": 12, "deployment": 12, "production": 13, "server": 14,
        "kubernetes": 15, "docker": 16, "container": 17,
        "data": 18, "database": 19, "query": 20, "search": 21,
        "transformer": 22, "attention": 23, "mechanism": 24,
        "the": 25, "is": 26, "a": 27, "and": 28, "for": 29,
        "null": 30, "pointer": 31, "exception": 32, "error": 33,
        "memory": 34, "optimization": 35, "cuda": 36, "gpu": 37,
    }
    
    # Base vector from semantic group (or random for unknown words)
    group_id = semantic_groups.get(word.lower(), hash(word) % 40)
    
    np.random.seed(group_id * 7 + 42)
    base = np.random.randn(EMBEDDING_DIM)
    
    # Add word-specific noise
    np.random.seed(hash(word) % 10000)
    noise = np.random.randn(EMBEDDING_DIM) * 0.3
    
    vec = base + noise
    vec = vec / np.linalg.norm(vec)  # Normalize
    WORD_VECTORS[word] = vec
    return vec


def tokenize(text: str) -> List[str]:
    """Simple whitespace tokenization."""
    return text.lower().split()


def embed_single_vector(text: str) -> np.ndarray:
    """Create a single embedding by averaging token vectors (simulates standard embedding)."""
    tokens = tokenize(text)
    vectors = [get_word_vector(t) for t in tokens]
    avg = np.mean(vectors, axis=0)
    return avg / np.linalg.norm(avg)


def embed_multi_vector(text: str) -> List[Tuple[str, np.ndarray]]:
    """Create per-token embeddings (simulates ColBERT encoding)."""
    tokens = tokenize(text)
    return [(token, get_word_vector(token)) for token in tokens]


# --- Scoring Functions ---

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def single_vector_score(query: str, document: str) -> float:
    """Standard single-vector similarity score."""
    q_vec = embed_single_vector(query)
    d_vec = embed_single_vector(document)
    return cosine_similarity(q_vec, d_vec)


def colbert_maxsim_score(query: str, document: str) -> Tuple[float, Dict[str, Tuple[str, float]]]:
    """
    ColBERT MaxSim scoring.
    
    For each query token, find the max similarity with any document token.
    Final score = sum of max similarities.
    
    Returns: (score, breakdown) where breakdown shows which doc token each query token matched.
    """
    q_tokens = embed_multi_vector(query)
    d_tokens = embed_multi_vector(document)
    
    total_score = 0.0
    breakdown = {}
    
    for q_word, q_vec in q_tokens:
        max_sim = -1.0
        best_match = ""
        
        for d_word, d_vec in d_tokens:
            sim = cosine_similarity(q_vec, d_vec)
            if sim > max_sim:
                max_sim = sim
                best_match = d_word
        
        breakdown[q_word] = (best_match, max_sim)
        total_score += max_sim
    
    return total_score, breakdown


# --- Search Functions ---

def search_single_vector(query: str, documents: List[str], top_k: int = 5) -> List[Tuple[int, float]]:
    """Search using single-vector similarity."""
    scores = [(i, single_vector_score(query, doc)) for i, doc in enumerate(documents)]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def search_colbert(query: str, documents: List[str], top_k: int = 5) -> List[Tuple[int, float, Dict]]:
    """Search using ColBERT MaxSim scoring."""
    scores = []
    for i, doc in enumerate(documents):
        score, breakdown = colbert_maxsim_score(query, doc)
        scores.append((i, score, breakdown))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# --- Demo ---

def main():
    print("=" * 70)
    print("ColBERT-Style Multi-Vector Search vs Single-Vector Search")
    print("=" * 70)
    
    # Document corpus
    documents = [
        "machine learning algorithms process data to find patterns",
        "deep neural network training requires large datasets and gpu",
        "python programming language is popular for data science",
        "kubernetes container deployment for production server",
        "transformer attention mechanism enables parallel processing",
        "database query optimization improves search performance",
        "null pointer exception error in java code",
        "cuda gpu memory optimization for deep learning training",
        "deploy machine learning model to production server",
        "the docker container runs the neural network model",
    ]
    
    print("\nDocument Corpus:")
    print("-" * 50)
    for i, doc in enumerate(documents):
        print(f"  [{i}] {doc}")
    
    # Test queries that highlight differences
    test_queries = [
        ("transformer attention mechanism", "Exact phrase match"),
        ("cuda memory optimization", "Specific technical terms"),
        ("deploy machine learning production", "Multi-concept query"),
        ("null pointer exception", "Error-specific query"),
        ("deep learning gpu training", "Distributed keywords"),
    ]
    
    print("\n")
    print("=" * 70)
    print("SEARCH COMPARISON")
    print("=" * 70)
    
    for query, description in test_queries:
        print(f"\n{'─' * 70}")
        print(f"Query: \"{query}\"")
        print(f"Type:  {description}")
        print(f"{'─' * 70}")
        
        # Single-vector results
        sv_results = search_single_vector(query, documents, top_k=5)
        
        # ColBERT results
        cb_results = search_colbert(query, documents, top_k=5)
        
        # Print comparison table
        print(f"\n  {'Rank':<5} {'Single-Vector':<45} {'ColBERT MaxSim':<45}")
        print(f"  {'─'*5} {'─'*45} {'─'*45}")
        
        for rank in range(5):
            sv_idx, sv_score = sv_results[rank]
            cb_idx, cb_score, _ = cb_results[rank]
            
            sv_text = documents[sv_idx][:38] + "..."  if len(documents[sv_idx]) > 38 else documents[sv_idx]
            cb_text = documents[cb_idx][:38] + "..."  if len(documents[cb_idx]) > 38 else documents[cb_idx]
            
            sv_str = f"[{sv_idx}] {sv_score:.3f} {sv_text}"
            cb_str = f"[{cb_idx}] {cb_score:.3f} {cb_text}"
            
            print(f"  {rank+1:<5} {sv_str:<45} {cb_str:<45}")
        
        # Show ColBERT breakdown for top result
        top_idx, top_score, breakdown = cb_results[0]
        print(f"\n  ColBERT Score Breakdown (top result, doc [{top_idx}]):")
        for q_token, (matched_token, sim) in breakdown.items():
            bar = "█" * int(sim * 20)
            print(f"    \"{q_token}\" → \"{matched_token}\" (sim: {sim:.3f}) {bar}")
    
    # Summary
    print("\n")
    print("=" * 70)
    print("KEY OBSERVATIONS")
    print("=" * 70)
    print("""
  1. EXACT PHRASE MATCHING:
     ColBERT scores documents higher when individual query terms
     have strong token-level matches (e.g., "transformer" matching
     "transformer" directly rather than being diluted).

  2. PARTIAL MATCHING:
     ColBERT gives proportional credit for partial matches.
     If 3 out of 4 query tokens match strongly, the score reflects that.
     Single-vector averages everything together.

  3. INTERPRETABILITY:
     ColBERT breakdown shows WHY a document scored high:
     which query tokens matched which document tokens.
     Single-vector gives one opaque similarity number.

  4. LONG DOCUMENTS:
     For longer documents (simulated here with more tokens),
     ColBERT finds strong matches regardless of position.
     Single-vector dilutes important tokens in the average.

  Note: This uses simulated embeddings. Real ColBERT uses BERT-based
  contextual embeddings, which capture more nuanced similarities.
  The patterns demonstrated here hold with real models.
""")


if __name__ == "__main__":
    main()
