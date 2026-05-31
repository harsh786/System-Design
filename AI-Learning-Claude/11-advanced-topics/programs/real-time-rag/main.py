"""
Real-Time RAG System

Demonstrates the "ingest → immediately searchable" pattern.
Unlike batch RAG (reindex every hour), this system makes new
content available for queries within milliseconds of ingestion.

Key architecture decision: ChromaDB handles embedding storage
and similarity search. We embed on ingest, not on a schedule.
"""

import time
import uuid
from datetime import datetime

import chromadb
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Real-Time RAG",
    description="Ingest content and query it immediately — no batch delay"
)

# Initialize clients
openai_client = OpenAI()
chroma_client = chromadb.Client()  # In-memory for demo; use PersistentClient for production
collection = chroma_client.create_collection(
    name="realtime_rag",
    metadata={"hnsw:space": "cosine"}
)

# Statistics
stats = {"ingestions": 0, "queries": 0, "total_chunks": 0}


# --- Helpers ---

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks.
    
    Overlap ensures we don't lose context at chunk boundaries.
    Think of it like overlapping tiles on a roof — no gaps.
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > chunk_size // 2:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1
        
        chunks.append(chunk.strip())
        start = end - overlap
    
    return [c for c in chunks if c]


def get_embedding(text: str) -> list[float]:
    """Get embedding from OpenAI."""
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def generate_answer(query: str, context_chunks: list[str]) -> str:
    """Generate an answer using retrieved context."""
    if not context_chunks:
        return "I don't have any information about that topic yet. Try ingesting some relevant content first."
    
    context = "\n\n---\n\n".join(context_chunks)
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Answer the user's question based ONLY on the provided context. If the context doesn't contain enough information, say so. Cite which parts of the context you used."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}"
            }
        ],
        temperature=0
    )
    
    return response.choices[0].message.content


# --- API Endpoints ---

@app.post("/ingest")
async def ingest(body: dict):
    """
    Ingest new content into the RAG system.
    
    After this endpoint returns, the content is IMMEDIATELY
    available for queries. No batch job, no delay.
    
    Body: {"text": "...", "source": "optional source name"}
    """
    text = body.get("text", "")
    source = body.get("source", "unknown")
    
    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)
    
    start_time = time.time()
    
    # Step 1: Chunk the text
    chunks = chunk_text(text)
    
    # Step 2: Embed and store each chunk
    ids = []
    embeddings = []
    documents = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        embedding = get_embedding(chunk)
        
        ids.append(chunk_id)
        embeddings.append(embedding)
        documents.append(chunk)
        metadatas.append({
            "source": source,
            "chunk_index": i,
            "ingested_at": datetime.now().isoformat(),
            "char_count": len(chunk)
        })
    
    # Step 3: Add to ChromaDB (immediately indexed)
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )
    
    elapsed_ms = (time.time() - start_time) * 1000
    stats["ingestions"] += 1
    stats["total_chunks"] += len(chunks)
    
    return {
        "status": "indexed",
        "chunks_created": len(chunks),
        "ingest_latency_ms": round(elapsed_ms, 2),
        "total_chunks_in_system": stats["total_chunks"],
        "message": f"Content is NOW searchable (took {elapsed_ms:.0f}ms)"
    }


@app.get("/query")
async def query(q: str = Query(..., description="Your question")):
    """
    Query the RAG system. Any previously ingested content
    is searchable, including content added seconds ago.
    """
    start_time = time.time()
    
    # Step 1: Embed the query
    query_embedding = get_embedding(q)
    
    # Step 2: Search ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5
    )
    
    retrieved_chunks = results["documents"][0] if results["documents"] else []
    retrieved_metadata = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []
    
    # Step 3: Generate answer
    answer = generate_answer(q, retrieved_chunks)
    
    elapsed_ms = (time.time() - start_time) * 1000
    stats["queries"] += 1
    
    # Build sources info
    sources = []
    for i, (chunk, meta, dist) in enumerate(zip(retrieved_chunks, retrieved_metadata, distances)):
        sources.append({
            "rank": i + 1,
            "text_preview": chunk[:150] + "..." if len(chunk) > 150 else chunk,
            "source": meta.get("source", "unknown"),
            "ingested_at": meta.get("ingested_at", "unknown"),
            "relevance_score": round(1 - dist, 4)  # Convert distance to similarity
        })
    
    return {
        "query": q,
        "answer": answer,
        "sources": sources,
        "query_latency_ms": round(elapsed_ms, 2),
        "chunks_searched": stats["total_chunks"]
    }


@app.get("/documents")
async def list_documents():
    """List all ingested content with metadata."""
    all_data = collection.get(include=["metadatas", "documents"])
    
    # Group by source
    by_source: dict[str, list] = {}
    for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
        source = meta.get("source", "unknown")
        by_source.setdefault(source, []).append({
            "preview": doc[:100] + "..." if len(doc) > 100 else doc,
            "ingested_at": meta.get("ingested_at")
        })
    
    return {
        "total_chunks": len(all_data["ids"]),
        "sources": {source: {"chunk_count": len(chunks), "sample": chunks[0]} 
                    for source, chunks in by_source.items()},
        "stats": stats
    }


@app.delete("/reset")
async def reset():
    """Clear all data and start fresh."""
    global collection
    chroma_client.delete_collection("realtime_rag")
    collection = chroma_client.create_collection(
        name="realtime_rag",
        metadata={"hnsw:space": "cosine"}
    )
    stats["ingestions"] = 0
    stats["queries"] = 0
    stats["total_chunks"] = 0
    return {"status": "reset", "message": "All data cleared"}


@app.get("/")
async def root():
    return {
        "name": "Real-Time RAG System",
        "description": "Ingest content and query it immediately",
        "demo_workflow": [
            "1. GET /query?q=What is Nextera? → No results (nothing ingested yet)",
            "2. POST /ingest with content about Nextera",
            "3. GET /query?q=What is Nextera? → Accurate answer immediately!",
        ],
        "endpoints": {
            "POST /ingest": "Add content (body: {text, source})",
            "GET /query?q=": "Ask questions",
            "GET /documents": "List all content",
            "DELETE /reset": "Clear everything"
        },
        "current_stats": stats
    }


if __name__ == "__main__":
    print("\n" + "="*60)
    print("REAL-TIME RAG SYSTEM")
    print("Ingest content → Immediately queryable")
    print("="*60)
    print("\nWorkflow:")
    print("  1. POST /ingest with your content")
    print("  2. GET /query?q=your+question")
    print("  3. Content is searchable with ZERO delay")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
