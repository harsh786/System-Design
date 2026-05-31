"""
Differential Privacy for Embeddings Demo

Demonstrates:
1. Standard embeddings (no privacy)
2. DP embeddings at various epsilon values (0.1, 1, 5, 10)
3. Search quality comparison at each privacy level
4. The privacy-utility tradeoff visualized as a table
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple


# ─── Documents ───────────────────────────────────────────────────────────────

DOCUMENTS = [
    "Machine learning algorithms process large datasets to find patterns",
    "Neural networks are inspired by biological brain structures",
    "Deep learning requires significant computational resources and GPUs",
    "Natural language processing enables computers to understand text",
    "Computer vision algorithms can identify objects in images",
    "Reinforcement learning agents learn through trial and error",
    "Transfer learning allows models to reuse knowledge across tasks",
    "Generative AI creates new content including text images and code",
    "Privacy preserving machine learning protects sensitive training data",
    "Federated learning trains models without centralizing user data",
    "Differential privacy adds noise to prevent individual identification",
    "Homomorphic encryption allows computation on encrypted data",
    "Secure multi-party computation enables joint analysis without sharing",
    "Data anonymization removes identifying information from datasets",
    "The transformer architecture revolutionized natural language processing",
    "Attention mechanisms allow models to focus on relevant input parts",
    "Large language models are trained on billions of text tokens",
    "Fine-tuning adapts pre-trained models to specific downstream tasks",
    "Prompt engineering designs effective inputs for language models",
    "RAG retrieval augmented generation combines search with generation",
]

QUERIES = [
    ("What is deep learning?", [0, 1, 2]),  # Expected top results
    ("How does privacy work in AI?", [8, 9, 10]),
    ("Tell me about language models", [3, 14, 16]),
    ("What is federated learning?", [9, 12, 8]),
    ("How do transformers work?", [14, 15, 16]),
]


# ─── Differential Privacy Mechanism ─────────────────────────────────────────

def add_gaussian_dp_noise(vectors: np.ndarray, epsilon: float,
                           delta: float = 1e-5) -> np.ndarray:
    """
    Add Gaussian noise to vectors for (epsilon, delta)-differential privacy.
    
    Uses the Gaussian mechanism:
        sigma = sensitivity * sqrt(2 * ln(1.25/delta)) / epsilon
    
    For normalized vectors, sensitivity = 1.0 (max L2 change from one record).
    """
    sensitivity = 1.0  # Normalized embeddings have bounded sensitivity
    sigma = sensitivity * np.sqrt(2 * np.log(1.25 / delta)) / epsilon

    noise = np.random.normal(0, sigma, size=vectors.shape)
    noisy_vectors = vectors + noise

    # Re-normalize each vector
    norms = np.linalg.norm(noisy_vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)  # Avoid division by zero
    noisy_vectors = noisy_vectors / norms

    return noisy_vectors, sigma


# ─── Search Function ─────────────────────────────────────────────────────────

def search(query_vec: np.ndarray, doc_vectors: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
    """Return top-k document indices and scores."""
    scores = cosine_similarity(query_vec.reshape(1, -1), doc_vectors).flatten()
    top_indices = scores.argsort()[-top_k:][::-1]
    return [(int(idx), float(scores[idx])) for idx in top_indices]


# ─── Quality Metrics ─────────────────────────────────────────────────────────

def recall_at_k(expected: List[int], actual: List[int], k: int = 5) -> float:
    """What fraction of expected results appear in top-k?"""
    actual_set = set(actual[:k])
    hits = sum(1 for e in expected if e in actual_set)
    return hits / len(expected) if expected else 0.0


def mrr(expected: List[int], actual: List[int]) -> float:
    """Mean Reciprocal Rank — how high is the first relevant result?"""
    for rank, idx in enumerate(actual, 1):
        if idx in expected:
            return 1.0 / rank
    return 0.0


# ─── Main Demo ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("DIFFERENTIAL PRIVACY FOR EMBEDDINGS")
    print("=" * 70)

    # Create TF-IDF embeddings
    vectorizer = TfidfVectorizer(stop_words="english")
    doc_vectors = vectorizer.fit_transform(DOCUMENTS).toarray()

    # Normalize
    norms = np.linalg.norm(doc_vectors, axis=1, keepdims=True)
    doc_vectors = doc_vectors / np.maximum(norms, 1e-10)

    print(f"\nDocuments: {len(DOCUMENTS)}")
    print(f"Embedding dimensions: {doc_vectors.shape[1]}")
    print(f"Queries: {len(QUERIES)}")

    # ─── Baseline (No Privacy) ───────────────────────────────────────────

    print("\n--- BASELINE SEARCH (No Privacy, ε=∞) ---\n")

    baseline_results = {}
    for query_text, expected in QUERIES:
        query_vec = vectorizer.transform([query_text]).toarray()
        query_vec = query_vec / np.maximum(np.linalg.norm(query_vec), 1e-10)
        results = search(query_vec, doc_vectors, top_k=5)
        baseline_results[query_text] = [idx for idx, score in results]
        print(f"  Query: \"{query_text}\"")
        print(f"    Top-3: {[DOCUMENTS[idx][:50] + '...' for idx, _ in results[:3]]}")
        print()

    # ─── DP at Various Epsilon Values ────────────────────────────────────

    epsilon_values = [0.1, 0.5, 1.0, 5.0, 10.0]
    num_trials = 10  # Average over multiple noise samples

    print("=" * 70)
    print("PRIVACY-UTILITY TRADEOFF")
    print("=" * 70)
    print(f"\n{'ε (epsilon)':<12} {'Noise σ':<10} {'Recall@5':<12} {'MRR':<10} "
          f"{'Privacy':<15} {'Quality':<15}")
    print("─" * 80)

    # Baseline row
    avg_recall = np.mean([
        recall_at_k(expected, baseline_results[query], k=5)
        for query, expected in QUERIES
    ])
    avg_mrr = np.mean([
        mrr(expected, baseline_results[query])
        for query, expected in QUERIES
    ])
    print(f"{'∞ (none)':<12} {'0.000':<10} {avg_recall:<12.3f} {avg_mrr:<10.3f} "
          f"{'None':<15} {'Perfect':<15}")

    results_table = []

    for epsilon in epsilon_values:
        trial_recalls = []
        trial_mrrs = []

        for trial in range(num_trials):
            # Add DP noise to document vectors
            noisy_vectors, sigma = add_gaussian_dp_noise(doc_vectors, epsilon)

            trial_recall = []
            trial_mrr = []

            for query_text, expected in QUERIES:
                query_vec = vectorizer.transform([query_text]).toarray()
                query_vec = query_vec / np.maximum(np.linalg.norm(query_vec), 1e-10)

                results = search(query_vec, noisy_vectors, top_k=5)
                actual_indices = [idx for idx, score in results]

                trial_recall.append(recall_at_k(expected, actual_indices, k=5))
                trial_mrr.append(mrr(expected, actual_indices))

            trial_recalls.append(np.mean(trial_recall))
            trial_mrrs.append(np.mean(trial_mrr))

        avg_recall = np.mean(trial_recalls)
        avg_mrr = np.mean(trial_mrrs)
        _, sigma = add_gaussian_dp_noise(doc_vectors[:1], epsilon)  # Get sigma

        # Determine privacy/quality labels
        if epsilon <= 0.5:
            privacy_label = "Strong"
            quality_label = "Degraded"
        elif epsilon <= 1.0:
            privacy_label = "Good"
            quality_label = "Moderate loss"
        elif epsilon <= 5.0:
            privacy_label = "Moderate"
            quality_label = "Minor loss"
        else:
            privacy_label = "Weak"
            quality_label = "Near-perfect"

        print(f"{epsilon:<12.1f} {sigma:<10.3f} {avg_recall:<12.3f} {avg_mrr:<10.3f} "
              f"{privacy_label:<15} {quality_label:<15}")

        results_table.append({
            "epsilon": epsilon, "sigma": sigma,
            "recall": avg_recall, "mrr": avg_mrr
        })

    # ─── Detailed Example ────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("DETAILED EXAMPLE: Same query at different privacy levels")
    print("=" * 70)

    example_query = "How does privacy work in AI?"
    example_expected = [8, 9, 10]

    print(f"\nQuery: \"{example_query}\"")
    print(f"Expected relevant docs:")
    for idx in example_expected:
        print(f"  [{idx}] {DOCUMENTS[idx]}")

    query_vec = vectorizer.transform([example_query]).toarray()
    query_vec = query_vec / np.maximum(np.linalg.norm(query_vec), 1e-10)

    print(f"\n{'ε':<8} {'Top-5 Results':<70} {'Correct?'}")
    print("─" * 90)

    # Baseline
    results = search(query_vec, doc_vectors, top_k=5)
    result_indices = [idx for idx, _ in results]
    correct = sum(1 for idx in result_indices if idx in example_expected)
    print(f"{'∞':<8} {str(result_indices):<70} {correct}/3 correct")

    for epsilon in epsilon_values:
        noisy_vectors, _ = add_gaussian_dp_noise(doc_vectors, epsilon)
        results = search(query_vec, noisy_vectors, top_k=5)
        result_indices = [idx for idx, _ in results]
        correct = sum(1 for idx in result_indices if idx in example_expected)
        print(f"{epsilon:<8.1f} {str(result_indices):<70} {correct}/3 correct")

    # ─── Membership Inference Demo ───────────────────────────────────────

    print("\n" + "=" * 70)
    print("MEMBERSHIP INFERENCE PROTECTION")
    print("=" * 70)
    print("""
    Without DP: An attacker can query for a specific document and determine
    if it exists based on the high similarity score.
    
    With DP: Noise makes it impossible to distinguish "document exists" 
    from "noise made a random document rank high."
    """)

    # Simulate: search for exact document content
    target_doc = DOCUMENTS[8]  # "Privacy preserving machine learning..."
    target_vec = vectorizer.transform([target_doc]).toarray()
    target_vec = target_vec / np.maximum(np.linalg.norm(target_vec), 1e-10)

    print(f"Target: \"{target_doc[:60]}...\"")
    print(f"\n{'ε':<8} {'Top Score':<12} {'Score Variance':<16} {'Can Infer?'}")
    print("─" * 55)

    # Baseline
    results = search(target_vec, doc_vectors, top_k=1)
    print(f"{'∞':<8} {results[0][1]:<12.4f} {'0.0000':<16} {'YES (score=1.0)'}")

    for epsilon in epsilon_values:
        scores = []
        for _ in range(50):
            noisy_vectors, _ = add_gaussian_dp_noise(doc_vectors, epsilon)
            results = search(target_vec, noisy_vectors, top_k=1)
            scores.append(results[0][1])

        mean_score = np.mean(scores)
        std_score = np.std(scores)
        can_infer = "YES" if mean_score > 0.8 and std_score < 0.1 else "NO (noisy)"
        print(f"{epsilon:<8.1f} {mean_score:<12.4f} {std_score:<16.4f} {can_infer}")

    # ─── Summary ─────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
    Recommendation by use case:
    
    ε = 0.1-0.5  │ Medical/legal data, strong regulatory requirements
                  │ Accept significant quality loss for provable privacy
                  │
    ε = 1.0-5.0  │ Enterprise sensitive data (HR, finance)
                  │ Good balance of privacy and utility
                  │
    ε = 5.0-10.0 │ General enterprise, low-sensitivity data
                  │ Minimal quality impact, some privacy protection
                  │
    No DP         │ Public data, already anonymized data
                  │ When access control alone is sufficient
    """)


if __name__ == "__main__":
    main()
