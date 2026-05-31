"""
Naive RAG Implementation
========================
The simplest possible RAG: chunk → embed → store → retrieve → generate.
Demonstrates the complete flow with timing at each step.
"""

import os
import time
import glob
from dotenv import load_dotenv
from openai import OpenAI
import chromadb

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o-mini"


# ============================================================
# Step 1: Load Documents
# ============================================================
def load_documents(docs_dir: str = "sample_docs") -> list[dict]:
    """Load all text files from the sample_docs directory."""
    documents = []
    for filepath in glob.glob(os.path.join(docs_dir, "*.txt")):
        with open(filepath, "r") as f:
            content = f.read()
        documents.append({
            "content": content,
            "source": os.path.basename(filepath),
        })
    print(f"📄 Loaded {len(documents)} documents")
    return documents


# ============================================================
# Step 2: Chunk Documents (Fixed-Size with Overlap)
# ============================================================
def chunk_documents(documents: list[dict], chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """Split documents into fixed-size chunks with overlap."""
    chunks = []
    for doc in documents:
        text = doc["content"]
        for i in range(0, len(text), chunk_size - overlap):
            chunk_text = text[i:i + chunk_size]
            if len(chunk_text.strip()) < 50:  # Skip tiny trailing chunks
                continue
            chunks.append({
                "text": chunk_text,
                "source": doc["source"],
                "chunk_index": len(chunks),
            })
    print(f"✂️  Created {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
    return chunks


# ============================================================
# Step 3: Embed and Store in ChromaDB
# ============================================================
def embed_and_store(chunks: list[dict]) -> chromadb.Collection:
    """Embed chunks using OpenAI and store in ChromaDB."""
    # Create ChromaDB collection (in-memory for demo)
    chroma_client = chromadb.Client()
    collection = chroma_client.create_collection(
        name="naive_rag_demo",
        metadata={"hnsw:space": "cosine"}
    )

    # Batch embed all chunks
    texts = [chunk["text"] for chunk in chunks]
    print(f"🔢 Embedding {len(texts)} chunks...")

    start = time.time()
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    embed_time = time.time() - start

    embeddings = [item.embedding for item in response.data]
    print(f"   Done in {embed_time:.2f}s ({len(texts)/embed_time:.0f} chunks/sec)")

    # Store in ChromaDB
    collection.add(
        ids=[f"chunk_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks],
    )
    print(f"💾 Stored {len(chunks)} chunks in ChromaDB")
    return collection


# ============================================================
# Step 4: Retrieve Relevant Chunks
# ============================================================
def retrieve(collection: chromadb.Collection, query: str, top_k: int = 3) -> list[dict]:
    """Embed the query and find the top-K most similar chunks."""
    start = time.time()

    # Embed the query
    response = client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
    query_embedding = response.data[0].embedding

    # Search ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    retrieve_time = time.time() - start

    retrieved = []
    for i in range(len(results["documents"][0])):
        retrieved.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "distance": results["distances"][0][i],
        })

    print(f"\n🔍 Retrieved {len(retrieved)} chunks in {retrieve_time*1000:.0f}ms")
    for i, r in enumerate(retrieved):
        print(f"   [{i+1}] {r['source']} (distance: {r['distance']:.4f})")
        print(f"       \"{r['text'][:80]}...\"")

    return retrieved


# ============================================================
# Step 5: Generate Answer with Citations
# ============================================================
def generate_answer(query: str, retrieved_chunks: list[dict]) -> str:
    """Generate an answer using the retrieved context."""
    # Build context string
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks):
        context_parts.append(f"[Source {i+1}: {chunk['source']}]\n{chunk['text']}")
    context = "\n\n---\n\n".join(context_parts)

    # Build prompt
    system_prompt = """You are a helpful assistant that answers questions based ONLY on the provided context.
Rules:
1. Only use information from the provided context
2. If the context doesn't contain the answer, say "I don't have enough information to answer this."
3. Cite your sources using [Source N] format
4. Be concise and direct"""

    user_prompt = f"""Context:
{context}

---

Question: {query}

Answer (with citations):"""

    start = time.time()
    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=500,
    )
    gen_time = time.time() - start

    answer = response.choices[0].message.content
    tokens_used = response.usage.total_tokens

    print(f"\n🤖 Generated answer in {gen_time:.2f}s ({tokens_used} tokens used)")
    return answer


# ============================================================
# Main: Run the full pipeline
# ============================================================
def main():
    print("=" * 60)
    print("NAIVE RAG DEMO")
    print("=" * 60)

    # Ingestion phase
    print("\n--- INGESTION PHASE ---")
    total_start = time.time()

    documents = load_documents()
    chunks = chunk_documents(documents)
    collection = embed_and_store(chunks)

    ingestion_time = time.time() - total_start
    print(f"\n⏱️  Total ingestion time: {ingestion_time:.2f}s")

    # Query phase
    print("\n--- QUERY PHASE ---")
    queries = [
        "How many vacation days do employees get?",
        "What is the API rate limit for enterprise tier?",
        "What is the salary range for senior engineers?",
        "What were the company's 2023 revenue numbers?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"❓ Question: {query}")
        print("=" * 60)

        query_start = time.time()
        retrieved = retrieve(collection, query)
        answer = generate_answer(query, retrieved)
        total_query_time = time.time() - query_start

        print(f"\n📝 Answer:\n{answer}")
        print(f"\n⏱️  Total query time: {total_query_time:.2f}s")


if __name__ == "__main__":
    main()
