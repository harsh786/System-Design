"""
Streaming AI Pipeline - Real-Time RAG Demo

This demonstrates how new data becomes searchable within seconds.
Events arrive → get embedded → get indexed → immediately queryable.

Key learning: The latency from "event received" to "searchable" is
the critical metric for real-time AI systems.
"""

import asyncio
import time
import json
import numpy as np
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
import uvicorn
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Streaming AI Pipeline", description="Real-time RAG demonstration")

# --- In-Memory Vector Store (simulates a vector database) ---

class StreamingVectorStore:
    """
    A simple in-memory vector store that supports real-time ingestion.
    In production, this would be ChromaDB, Pinecone, or similar.
    """
    
    def __init__(self):
        self.documents: list[dict] = []
        self.embeddings: list[list[float]] = []
        self.ingest_times: list[float] = []  # Track latency
        self.total_ingest_latency: float = 0
        self.ingest_count: int = 0
    
    def add(self, text: str, embedding: list[float], metadata: dict = None):
        """Add a document with its embedding."""
        self.documents.append({
            "text": text,
            "metadata": metadata or {},
            "indexed_at": datetime.now().isoformat()
        })
        self.embeddings.append(embedding)
    
    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """Search by cosine similarity."""
        if not self.embeddings:
            return []
        
        # Compute cosine similarity
        query_np = np.array(query_embedding)
        similarities = []
        
        for i, emb in enumerate(self.embeddings):
            emb_np = np.array(emb)
            similarity = np.dot(query_np, emb_np) / (
                np.linalg.norm(query_np) * np.linalg.norm(emb_np) + 1e-8
            )
            similarities.append((i, float(similarity)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, score in similarities[:top_k]:
            results.append({
                "text": self.documents[idx]["text"],
                "score": score,
                "metadata": self.documents[idx]["metadata"],
                "indexed_at": self.documents[idx]["indexed_at"]
            })
        
        return results
    
    def record_latency(self, latency_ms: float):
        """Track ingest latency statistics."""
        self.ingest_times.append(latency_ms)
        self.total_ingest_latency += latency_ms
        self.ingest_count += 1
    
    @property
    def avg_latency_ms(self) -> float:
        if self.ingest_count == 0:
            return 0
        return self.total_ingest_latency / self.ingest_count


# --- Globals ---

store = StreamingVectorStore()
client: Optional[OpenAI] = None
connected_websockets: list[WebSocket] = []

# Simulated event sources
SIMULATED_EVENTS = [
    {"source": "support_ticket", "text": "Customer reports login failures after password reset. Error code AUTH_EXPIRED_TOKEN appears in logs."},
    {"source": "documentation", "text": "The authentication service uses JWT tokens with a 24-hour expiry. Refresh tokens are valid for 30 days."},
    {"source": "incident_report", "text": "Database failover completed at 14:32 UTC. Primary restored at 15:01 UTC. No data loss confirmed."},
    {"source": "product_update", "text": "Version 2.4.1 introduces rate limiting on the /api/search endpoint. Default limit: 100 requests per minute per user."},
    {"source": "support_ticket", "text": "Multiple users reporting slow dashboard load times since the v2.4.1 deployment. P95 latency increased from 200ms to 2.1 seconds."},
    {"source": "meeting_notes", "text": "Decision: migrate vector database from Pinecone to self-hosted Qdrant by Q2. Reason: cost reduction and data residency requirements."},
    {"source": "alert", "text": "Memory usage on embedding-service-03 exceeded 90% threshold. Auto-scaling triggered, new instance launching."},
    {"source": "documentation", "text": "To configure rate limiting, set RATE_LIMIT_PER_MINUTE in environment variables. Apply per-user limits via the X-User-ID header."},
]


# --- Helper Functions ---

def get_embedding(text: str) -> list[float]:
    """Get embedding from OpenAI API."""
    global client
    if client is None:
        client = OpenAI()
    
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def chunk_text(text: str, max_chunk_size: int = 500) -> list[str]:
    """
    Simple chunking by sentences. In production, use more sophisticated
    chunking (semantic, recursive, etc.)
    """
    if len(text) <= max_chunk_size:
        return [text]
    
    sentences = text.replace(". ", ".\n").split("\n")
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += " " + sentence
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [text]


async def notify_websockets(message: dict):
    """Send update to all connected WebSocket clients."""
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    
    for ws in disconnected:
        connected_websockets.remove(ws)


# --- API Endpoints ---

@app.post("/ingest")
async def ingest_document(body: dict):
    """
    Ingest a new document into the streaming pipeline.
    
    This is the core of real-time RAG: the document becomes
    searchable within seconds of being ingested.
    
    Pipeline: Receive → Chunk → Embed → Index → Done
    """
    start_time = time.time()
    
    text = body.get("text", "")
    source = body.get("source", "unknown")
    
    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)
    
    # Step 1: Chunk the document
    chunks = chunk_text(text)
    
    # Step 2: Embed each chunk
    indexed_chunks = 0
    for chunk in chunks:
        embedding = get_embedding(chunk)
        
        # Step 3: Index immediately
        store.add(
            text=chunk,
            embedding=embedding,
            metadata={"source": source, "ingested_at": time.time()}
        )
        indexed_chunks += 1
    
    # Calculate latency
    end_time = time.time()
    latency_ms = (end_time - start_time) * 1000
    store.record_latency(latency_ms)
    
    # Notify WebSocket clients
    await notify_websockets({
        "event": "document_indexed",
        "source": source,
        "chunks": indexed_chunks,
        "latency_ms": round(latency_ms, 2),
        "total_documents": len(store.documents),
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "status": "indexed",
        "chunks_created": indexed_chunks,
        "latency_ms": round(latency_ms, 2),
        "total_documents": len(store.documents),
        "message": f"Document searchable in {latency_ms:.0f}ms"
    }


@app.get("/query")
async def query_documents(q: str = Query(..., description="Search query")):
    """
    Query the vector store. Any recently ingested document
    is immediately available for search.
    """
    start_time = time.time()
    
    # Embed the query
    query_embedding = get_embedding(q)
    
    # Search
    results = store.search(query_embedding, top_k=5)
    
    query_latency_ms = (time.time() - start_time) * 1000
    
    return {
        "query": q,
        "results": results,
        "query_latency_ms": round(query_latency_ms, 2),
        "total_documents_searched": len(store.documents)
    }


@app.get("/stats")
async def get_stats():
    """Pipeline statistics showing real-time performance."""
    return {
        "total_documents": len(store.documents),
        "total_ingestions": store.ingest_count,
        "avg_ingest_latency_ms": round(store.avg_latency_ms, 2),
        "last_10_latencies_ms": [round(l, 2) for l in store.ingest_times[-10:]],
        "message": "These stats show how quickly new data becomes searchable"
    }


@app.post("/start-simulation")
async def start_simulation():
    """
    Start a simulated event stream. Events arrive every 2 seconds,
    mimicking real-world data flowing into the system.
    """
    asyncio.create_task(run_simulation())
    return {"status": "Simulation started", "events_to_process": len(SIMULATED_EVENTS)}


async def run_simulation():
    """Simulate events arriving in real-time."""
    for i, event in enumerate(SIMULATED_EVENTS):
        # Notify that an event arrived
        await notify_websockets({
            "event": "new_event_received",
            "source": event["source"],
            "preview": event["text"][:100] + "...",
            "event_number": i + 1,
            "total_events": len(SIMULATED_EVENTS)
        })
        
        # Process the event (ingest it)
        start_time = time.time()
        chunks = chunk_text(event["text"])
        
        for chunk in chunks:
            embedding = get_embedding(chunk)
            store.add(text=chunk, embedding=embedding, metadata={"source": event["source"]})
        
        latency_ms = (time.time() - start_time) * 1000
        store.record_latency(latency_ms)
        
        await notify_websockets({
            "event": "event_processed",
            "source": event["source"],
            "latency_ms": round(latency_ms, 2),
            "total_searchable": len(store.documents),
            "event_number": i + 1
        })
        
        # Wait before next event (simulates real-time arrival)
        await asyncio.sleep(2)
    
    await notify_websockets({
        "event": "simulation_complete",
        "total_documents": len(store.documents),
        "avg_latency_ms": round(store.avg_latency_ms, 2)
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time pipeline updates.
    Connect to see events being processed in real-time.
    """
    await websocket.accept()
    connected_websockets.append(websocket)
    
    await websocket.send_json({
        "event": "connected",
        "message": "Connected to streaming pipeline. You'll see real-time updates here.",
        "current_documents": len(store.documents)
    })
    
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Client can send queries via WebSocket too
            if data.startswith("query:"):
                query = data[6:].strip()
                query_embedding = get_embedding(query)
                results = store.search(query_embedding, top_k=3)
                await websocket.send_json({
                    "event": "query_result",
                    "query": query,
                    "results": results
                })
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)


@app.get("/")
async def root():
    """Welcome page with usage instructions."""
    return {
        "name": "Streaming AI Pipeline",
        "description": "Real-time RAG demonstration - new data searchable in seconds",
        "usage": {
            "1_start_simulation": "POST /start-simulation (generates events)",
            "2_manual_ingest": "POST /ingest {\"text\": \"...\", \"source\": \"...\"}",
            "3_query": "GET /query?q=your+question",
            "4_stats": "GET /stats",
            "5_websocket": "WS /ws (real-time updates)"
        },
        "key_metric": "Average ingest latency (time from received to searchable)",
        "current_stats": {
            "documents": len(store.documents),
            "avg_latency_ms": round(store.avg_latency_ms, 2)
        }
    }


if __name__ == "__main__":
    print("\n🚀 Streaming AI Pipeline")
    print("=" * 50)
    print("This demonstrates real-time RAG: new data becomes")
    print("searchable within seconds of ingestion.")
    print()
    print("Endpoints:")
    print("  POST /start-simulation  - Start event simulation")
    print("  POST /ingest            - Ingest new content")
    print("  GET  /query?q=...       - Search indexed content")
    print("  GET  /stats             - View pipeline metrics")
    print("  WS   /ws               - Real-time WebSocket updates")
    print("=" * 50)
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
