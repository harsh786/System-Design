"""
Embedding Model Comparison
===========================
Compares OpenAI text-embedding-3-small vs sentence-transformers all-MiniLM-L6-v2.
"""

import time
import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

# --- Models ---
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
local_model = SentenceTransformer("all-MiniLM-L6-v2")

# --- Test Sentences ---
SENTENCES = [
    "The cat sat on the mat.",
    "A kitten was resting on the rug.",
    "Dogs are loyal companions.",
    "Machine learning is transforming industries.",
    "Artificial intelligence is changing how businesses operate.",
    "The weather today is sunny and warm.",
    "It's a beautiful bright day outside.",
    "Quantum computing will revolutionize cryptography.",
    "I love eating pizza on Friday nights.",
    "The stock market crashed yesterday.",
]

# Pairs to compare (indices into SENTENCES)
PAIRS = [
    (0, 1, "Cat/kitten paraphrase"),
    (0, 2, "Cat vs dog (same domain)"),
    (3, 4, "ML/AI paraphrase"),
    (5, 6, "Weather paraphrase"),
    (0, 7, "Cat vs quantum (unrelated)"),
    (3, 7, "ML vs quantum (related tech)"),
    (5, 8, "Weather vs pizza (unrelated)"),
    (8, 9, "Pizza vs stocks (unrelated)"),
]


def cosine_similarity(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def embed_openai(texts: list[str], dimensions: int = 1536) -> list[list[float]]:
    """Embed with OpenAI."""
    response = openai_client.embeddings.create(
        input=texts,
        model="text-embedding-3-small",
        dimensions=dimensions,
    )
    return [item.embedding for item in response.data]


def embed_local(texts: list[str]) -> list[list[float]]:
    """Embed with sentence-transformers."""
    embeddings = local_model.encode(texts)
    return embeddings.tolist()


def main():
    print("=" * 70)
    print("EMBEDDING MODEL COMPARISON")
    print("OpenAI text-embedding-3-small vs all-MiniLM-L6-v2")
    print("=" * 70)

    # --- Step 1: Embed with both models ---
    print("\n⏱️  Step 1: Embedding speed comparison")
    print("-" * 50)

    start = time.time()
    openai_embeddings = embed_openai(SENTENCES)
    openai_time = time.time() - start

    start = time.time()
    local_embeddings = embed_local(SENTENCES)
    local_time = time.time() - start

    print(f"   OpenAI ({len(openai_embeddings[0])}d): {openai_time:.3f}s for {len(SENTENCES)} sentences")
    print(f"   MiniLM ({len(local_embeddings[0])}d):  {local_time:.3f}s for {len(SENTENCES)} sentences")
    print(f"   Speed ratio: local is {openai_time/local_time:.1f}x faster")

    # --- Step 2: Compare similarity rankings ---
    print("\n📊 Step 2: Similarity comparison for sentence pairs")
    print("-" * 70)
    print(f"   {'Pair':<30} {'OpenAI':>8} {'MiniLM':>8} {'Diff':>8} {'Agree?':>8}")
    print("   " + "-" * 66)

    openai_scores = []
    local_scores = []

    for i, j, label in PAIRS:
        oa_sim = cosine_similarity(openai_embeddings[i], openai_embeddings[j])
        lc_sim = cosine_similarity(local_embeddings[i], local_embeddings[j])
        diff = abs(oa_sim - lc_sim)
        agree = "✓" if (oa_sim > 0.5) == (lc_sim > 0.5) else "✗"
        openai_scores.append(oa_sim)
        local_scores.append(lc_sim)
        print(f"   {label:<30} {oa_sim:>8.4f} {lc_sim:>8.4f} {diff:>8.4f} {agree:>8}")

    # --- Step 3: Ranking correlation ---
    print("\n📈 Step 3: Ranking agreement")
    print("-" * 50)

    openai_ranking = np.argsort(openai_scores)[::-1]
    local_ranking = np.argsort(local_scores)[::-1]

    print("   OpenAI ranking (most to least similar):")
    for rank, idx in enumerate(openai_ranking):
        print(f"     {rank+1}. {PAIRS[idx][2]} ({openai_scores[idx]:.4f})")

    print("\n   MiniLM ranking (most to least similar):")
    for rank, idx in enumerate(local_ranking):
        print(f"     {rank+1}. {PAIRS[idx][2]} ({local_scores[idx]:.4f})")

    # Spearman rank correlation
    from scipy.stats import spearmanr
    try:
        corr, _ = spearmanr(openai_scores, local_scores)
        print(f"\n   Spearman rank correlation: {corr:.4f}")
        print(f"   (1.0 = perfect agreement, 0.0 = no correlation)")
    except ImportError:
        # scipy not required, skip
        pass

    # --- Step 4: Dimension reduction (Matryoshka) ---
    print("\n🪆 Step 4: Dimension reduction (Matryoshka embeddings)")
    print("-" * 50)

    dimensions_to_test = [64, 128, 256, 512, 1536]
    print(f"   Testing pair: '{SENTENCES[0]}' vs '{SENTENCES[1]}'")
    print(f"\n   {'Dimensions':>12} {'Similarity':>12} {'vs Full':>12}")
    print("   " + "-" * 38)

    # Get full embeddings and test truncation
    full_sim = cosine_similarity(openai_embeddings[0], openai_embeddings[1])

    for dims in dimensions_to_test:
        reduced_embs = embed_openai([SENTENCES[0], SENTENCES[1]], dimensions=dims)
        sim = cosine_similarity(reduced_embs[0], reduced_embs[1])
        delta = abs(sim - full_sim)
        print(f"   {dims:>12} {sim:>12.4f} {f'Δ={delta:.4f}':>12}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("📋 Summary")
    print("=" * 70)
    print(f"""
   Model Comparison:
   ┌────────────────────┬──────────────┬──────────────┐
   │ Property           │ OpenAI       │ MiniLM       │
   ├────────────────────┼──────────────┼──────────────┤
   │ Dimensions         │ 1536         │ 384          │
   │ Embedding speed    │ {openai_time:.3f}s       │ {local_time:.3f}s       │
   │ Cost               │ $0.02/1M tok │ Free (GPU)   │
   │ Quality (MTEB)     │ ~62%         │ ~56%         │
   │ Matryoshka support │ Yes          │ No           │
   │ Privacy            │ Data sent    │ Local        │
   └────────────────────┴──────────────┴──────────────┘

   Key Findings:
   - Both models agree on obvious similarity (paraphrases vs unrelated)
   - They may disagree on subtle cases (related but different topics)
   - Dimension reduction has minimal impact until very low dims
   - Local model is faster per-call but lower quality overall
""")


if __name__ == "__main__":
    main()
