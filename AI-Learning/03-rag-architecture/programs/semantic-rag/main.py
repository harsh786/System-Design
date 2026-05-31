"""
Semantic RAG Implementation
============================
Uses local sentence-transformers for embedding, semantic chunking,
metadata filtering, and relevance thresholds.
"""

import os
import time
import glob
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from sentence_transformers import SentenceTransformer
import nltk

# Download sentence tokenizer
nltk.download("punkt_tab", quiet=True)
from nltk.tokenize import sent_tokenize

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GENERATION_MODEL = "gpt-4o-mini"

# Local embedding model - no API key needed!
print("Loading sentence-transformer model (first run downloads ~90MB)...")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")


# ============================================================
# Semantic Chunking: Split at meaning boundaries
# ============================================================
def semantic_chunk(text: str, similarity_threshold: float = 0.5, min_chunk_size: int = 100) -> list[str]:
    """
    Split text into chunks based on semantic similarity between sentences.
    When adjacent sentences are very different (low similarity), we split there.
    """
    sentences = sent_tokenize(text)
    if len(sentences) <= 1:
        return [text]

    # Embed all sentences
    embeddings = embed_model.encode(sentences)

    # Compute cosine similarity between adjacent sentences
    chunks = []
    current_chunk = [sentences[0]]

    for i in range(1, len(sentences)):
        # Cosine similarity between current and previous sentence
        sim = np.dot(embeddings[i], embeddings[i - 1]) / (
            np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i - 1])
        )

        if sim < similarity_threshold and len(" ".join(current_chunk)) >= min_chunk_size:
            # Low similarity = topic shift = chunk boundary
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
        else:
            current_chunk.append(sentences[i])

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# ============================================================
# Load and Process Documents
# ============================================================
def load_and_chunk_documents(docs_dir: str = "sample_docs") -> list[dict]:
    """Load documents and apply semantic chunking with metadata."""
    all_chunks = []

    for filepath in glob.glob(os.path.join(docs_dir, "*.txt")):
        with open(filepath, "r") as f:
            content = f.read()

        source = os.path.basename(filepath)
        # Determine document category from filename
        category = source.replace(".txt", "").replace("_", " ").title()

        chunks = semantic_chunk(content, similarity_threshold=0.45)

        for i, chunk_text in enumerate(chunks):
            all_chunks.append({
                "text": chunk_text,
                "source": source,
                "category": category,
                "chunk_index": i,
            })

    print(f"📄 Loaded {len(glob.glob(os.path.join(docs_dir, '*.txt')))} documents")
    print(f"✂️  Created {len(all_chunks)} semantic chunks")
    return all_chunks


# ============================================================
# Embed and Store
# ============================================================
def embed_and_store(chunks: list[dict]) -> chromadb.Collection:
    """Embed with local model and store in ChromaDB."""
    chroma_client = chromadb.Client()
    collection = chroma_client.create_collection(
        name="semantic_rag_demo",
        metadata={"hnsw:space": "cosine"},
    )

    texts = [c["text"] for c in chunks]

    print(f"🔢 Embedding {len(texts)} chunks locally...")
    start = time.time()
    embeddings = embed_model.encode(texts).tolist()
    embed_time = time.time() - start
    print(f"   Done in {embed_time:.2f}s ({len(texts)/embed_time:.0f} chunks/sec)")

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{
            "source": c["source"],
            "category": c["category"],
            "chunk_index": c["chunk_index"],
        } for c in chunks],
    )

    print(f"💾 Stored in ChromaDB")
    return collection


# ============================================================
# Retrieve with Filtering and Threshold
# ============================================================
def retrieve(
    collection: chromadb.Collection,
    query: str,
    top_k: int = 5,
    relevance_threshold: float = 0.6,
    category_filter: str = None,
) -> list[dict]:
    """Retrieve with optional metadata filter and relevance threshold."""
    start = time.time()

    # Embed query locally
    query_embedding = embed_model.encode([query]).tolist()

    # Build query params
    query_params = {
        "query_embeddings": query_embedding,
        "n_results": top_k,
    }
    if category_filter:
        query_params["where"] = {"category": category_filter}

    results = collection.query(**query_params)
    retrieve_time = time.time() - start

    # Apply relevance threshold (ChromaDB returns distances, lower = more similar for cosine)
    retrieved = []
    for i in range(len(results["documents"][0])):
        distance = results["distances"][0][i]
        similarity = 1 - distance  # Convert distance to similarity

        if similarity >= relevance_threshold:
            retrieved.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "category": results["metadatas"][0][i]["category"],
                "similarity": similarity,
            })

    print(f"\n🔍 Retrieved {len(retrieved)} chunks above threshold ({relevance_threshold}) in {retrieve_time*1000:.0f}ms")
    if category_filter:
        print(f"   Filter: category = '{category_filter}'")

    for i, r in enumerate(retrieved):
        print(f"   [{i+1}] {r['source']} (similarity: {r['similarity']:.4f})")
        print(f"       \"{r['text'][:80]}...\"")

    if not retrieved:
        print("   ⚠️  No chunks met the relevance threshold!")

    return retrieved


# ============================================================
# Generate Answer
# ============================================================
def generate_answer(query: str, retrieved_chunks: list[dict]) -> str:
    """Generate answer using OpenAI with retrieved context."""
    if not retrieved_chunks:
        return "I don't have enough relevant information to answer this question confidently."

    context_parts = []
    for i, chunk in enumerate(retrieved_chunks):
        context_parts.append(
            f"[Source {i+1}: {chunk['source']} | Category: {chunk['category']} | Relevance: {chunk['similarity']:.2f}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    response = openai_client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": "Answer based ONLY on the provided context. Cite sources as [Source N]. If context is insufficient, say so."},
            {"role": "user", "content": f"Context:\n{context}\n\n---\nQuestion: {query}"},
        ],
        temperature=0,
        max_tokens=400,
    )
    return response.choices[0].message.content


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("SEMANTIC RAG DEMO")
    print("=" * 60)

    # Ingestion
    print("\n--- INGESTION (Semantic Chunking + Local Embeddings) ---")
    chunks = load_and_chunk_documents()
    collection = embed_and_store(chunks)

    # Queries demonstrating different features
    test_cases = [
        {
            "query": "What happens if there's a data breach?",
            "filter": None,
            "note": "Semantic match: 'data breach' → incident response docs",
        },
        {
            "query": "How can I get my money back?",
            "filter": None,
            "note": "Semantic match: 'money back' → refund policy (different words!)",
        },
        {
            "query": "What's planned for Q2?",
            "filter": "Product Roadmap",
            "note": "With metadata filter: only search roadmap docs",
        },
        {
            "query": "Tell me about dinosaurs",
            "filter": None,
            "note": "Out-of-scope query — should be rejected by threshold",
        },
    ]

    for tc in test_cases:
        print(f"\n{'='*60}")
        print(f"❓ Question: {tc['query']}")
        print(f"   💡 {tc['note']}")
        print("=" * 60)

        retrieved = retrieve(collection, tc["query"], category_filter=tc["filter"])
        answer = generate_answer(tc["query"], retrieved)
        print(f"\n📝 Answer:\n{answer}")


if __name__ == "__main__":
    main()
