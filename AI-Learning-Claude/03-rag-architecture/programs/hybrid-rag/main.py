"""
Hybrid RAG Implementation
==========================
Combines BM25 keyword search with vector semantic search using
Reciprocal Rank Fusion (RRF). Shows side-by-side comparison.
"""

import os
import time
import glob
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from rank_bm25 import BM25Okapi

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o-mini"


# ============================================================
# Document Loading & Chunking
# ============================================================
def load_and_chunk(docs_dir: str = "sample_docs", chunk_size: int = 400, overlap: int = 50) -> list[dict]:
    """Load and chunk documents."""
    chunks = []
    for filepath in glob.glob(os.path.join(docs_dir, "*.txt")):
        with open(filepath, "r") as f:
            content = f.read()
        source = os.path.basename(filepath)
        for i in range(0, len(content), chunk_size - overlap):
            chunk_text = content[i:i + chunk_size]
            if len(chunk_text.strip()) < 50:
                continue
            chunks.append({"text": chunk_text, "source": source, "id": f"chunk_{len(chunks)}"})
    print(f"📄 Loaded {len(chunks)} chunks from {docs_dir}")
    return chunks


# ============================================================
# BM25 Index (Keyword Search)
# ============================================================
class BM25Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        # Tokenize for BM25
        tokenized = [chunk["text"].lower().split() for chunk in chunks]
        self.bm25 = BM25Okapi(tokenized)
        print(f"📚 BM25 index built over {len(chunks)} chunks")

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Returns list of (chunk_index, score) tuples."""
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        # Get top-K indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(i, scores[i]) for i in top_indices if scores[i] > 0]


# ============================================================
# Vector Index (Semantic Search)
# ============================================================
class VectorIndex:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.create_collection("hybrid_rag", metadata={"hnsw:space": "cosine"})

        texts = [c["text"] for c in chunks]
        print(f"🔢 Embedding {len(texts)} chunks...")
        response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
        embeddings = [item.embedding for item in response.data]

        self.collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"source": c["source"]} for c in chunks],
        )
        print(f"💾 Vector index built")

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Returns list of (chunk_index, score) tuples."""
        response = client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
        query_emb = response.data[0].embedding

        results = self.collection.query(query_embeddings=[query_emb], n_results=top_k)

        ranked = []
        for i in range(len(results["ids"][0])):
            chunk_idx = int(results["ids"][0][i].split("_")[1])
            similarity = 1 - results["distances"][0][i]
            ranked.append((chunk_idx, similarity))
        return ranked


# ============================================================
# Reciprocal Rank Fusion
# ============================================================
def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[int, float]]], k: int = 60
) -> list[tuple[int, float]]:
    """
    Combine multiple ranked lists using RRF.
    Each ranked_list is [(chunk_index, score), ...] in descending order.
    Returns combined ranking.
    """
    rrf_scores = {}
    for ranked_list in ranked_lists:
        for rank, (chunk_idx, _) in enumerate(ranked_list):
            rrf_scores[chunk_idx] = rrf_scores.get(chunk_idx, 0) + 1 / (k + rank + 1)

    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)


# ============================================================
# Display Results
# ============================================================
def display_results(label: str, results: list[tuple[int, float]], chunks: list[dict], top_k: int = 3):
    """Print retrieval results."""
    print(f"\n  📋 {label} (top {top_k}):")
    for rank, (idx, score) in enumerate(results[:top_k]):
        text_preview = chunks[idx]["text"][:80].replace("\n", " ")
        print(f"     [{rank+1}] score={score:.4f} | {chunks[idx]['source']}")
        print(f"         \"{text_preview}...\"")


# ============================================================
# Generate Answer
# ============================================================
def generate_answer(query: str, chunks: list[dict], result_indices: list[tuple[int, float]], top_k: int = 3) -> str:
    """Generate answer from top results."""
    context_parts = []
    for i, (idx, score) in enumerate(result_indices[:top_k]):
        context_parts.append(f"[Source {i+1}: {chunks[idx]['source']}]\n{chunks[idx]['text']}")
    context = "\n\n---\n\n".join(context_parts)

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": "Answer based ONLY on the provided context. Cite sources. Be concise."},
            {"role": "user", "content": f"Context:\n{context}\n\n---\nQuestion: {query}"},
        ],
        temperature=0,
        max_tokens=300,
    )
    return response.choices[0].message.content


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("HYBRID RAG DEMO: BM25 + Vector + RRF")
    print("=" * 60)

    # Build indexes
    chunks = load_and_chunk()
    bm25_index = BM25Index(chunks)
    vector_index = VectorIndex(chunks)

    # Test queries designed to show hybrid advantage
    queries = [
        {
            "query": "ERROR_CODE_2001",
            "note": "Exact keyword — BM25 wins, semantic may miss",
        },
        {
            "query": "How do I connect my CRM system to FlowEngine?",
            "note": "Semantic meaning — Vector wins (no exact 'CRM' in docs, but Salesforce is a CRM)",
        },
        {
            "query": "workflow not running after schedule",
            "note": "Mix of keywords + meaning — Hybrid wins",
        },
    ]

    for tc in queries:
        query = tc["query"]
        print(f"\n{'='*60}")
        print(f"❓ Query: {query}")
        print(f"   💡 {tc['note']}")
        print("=" * 60)

        # BM25 search
        bm25_results = bm25_index.search(query, top_k=10)
        display_results("BM25 (Keyword)", bm25_results, chunks)

        # Vector search
        vector_results = vector_index.search(query, top_k=10)
        display_results("Vector (Semantic)", vector_results, chunks)

        # Hybrid with RRF
        hybrid_results = reciprocal_rank_fusion([bm25_results, vector_results])
        display_results("HYBRID (RRF Fusion)", hybrid_results, chunks)

        # Generate answer using hybrid results
        answer = generate_answer(query, chunks, hybrid_results)
        print(f"\n  🤖 Answer (from hybrid results):\n     {answer}")


if __name__ == "__main__":
    main()
