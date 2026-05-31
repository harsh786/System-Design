"""
Main FastAPI application - Entry point for the Enterprise AI System.
"""

import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from config import USE_REAL_LLM, FEATURES
from auth import validate_token, check_permission, generate_token
from gateway import process_request
from observability import observability
from cost_tracker import cost_tracker
from memory import memory

# Initialize FastAPI app
app = FastAPI(
    title="Enterprise AI System",
    description="Capstone: Complete enterprise AI platform with routing, RAG, agents, guardrails, and observability",
    version="1.0.0",
)


# --- Request/Response Models ---

class QueryRequest(BaseModel):
    text: str
    session_id: Optional[str] = "default"


class QueryResponse(BaseModel):
    answer: str
    status: str
    route: Optional[str] = None
    confidence: Optional[float] = None
    sources: Optional[list] = None
    cost: Optional[float] = None
    trace_id: Optional[str] = None


# --- Middleware ---

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Add request timing to all responses."""
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration:.1f}"
    return response


# --- Endpoints ---

@app.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "knowledge_base": "loaded (10 documents)",
            "guardrails": "active" if FEATURES["guardrails_enabled"] else "disabled",
            "observability": "active" if FEATURES["observability_enabled"] else "disabled",
            "memory": "active" if FEATURES["memory_enabled"] else "disabled",
            "mode": "real LLM (OpenAI)" if USE_REAL_LLM else "simulated (no API key)",
        },
        "metrics": observability.get_summary(),
    }


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: Request, body: QueryRequest):
    """
    Main query endpoint. The single entry point for all AI queries.
    Requires JWT auth token in Authorization header.
    """
    # Extract and validate auth token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.replace("Bearer ", "")
    try:
        user_context = validate_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Check permission
    if not check_permission(user_context, "query"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Create trace
    trace = observability.create_trace()
    span = trace.start_span("auth_validation")
    span.end()

    # Process through gateway
    result = process_request(
        query=body.text,
        user_context=user_context,
        session_id=body.session_id or "default",
        trace=trace,
    )

    # Record and print trace
    observability.record_request(trace)
    if FEATURES["observability_enabled"]:
        observability.print_trace(trace)

    # Handle error responses
    if result.get("status") == "rate_limited":
        raise HTTPException(status_code=429, detail=result)
    if result.get("status") == "budget_exceeded":
        raise HTTPException(status_code=402, detail=result)

    return QueryResponse(
        answer=result.get("answer", "No response generated"),
        status=result.get("status", "unknown"),
        route=result.get("route"),
        confidence=result.get("confidence"),
        sources=result.get("sources"),
        cost=result.get("cost"),
        trace_id=result.get("trace_id"),
    )


@app.get("/token")
async def get_test_token(user_id: str = "test-user", role: str = "user"):
    """Generate a test JWT token (for demo/testing only)."""
    token = generate_token(user_id, role)
    return {"token": token, "user_id": user_id, "role": role}


@app.get("/metrics")
async def get_metrics():
    """Get system metrics (admin only in production)."""
    return {
        "observability": observability.get_summary(),
        "costs": cost_tracker.get_system_report(),
        "memory": memory.get_stats(),
    }


# --- Startup ---

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  ENTERPRISE AI SYSTEM - CAPSTONE")
    print("=" * 60)
    print(f"[STARTUP] Loading configuration...")
    print(f"[STARTUP] Mode: {'Real LLM (OpenAI)' if USE_REAL_LLM else 'Simulated responses'}")
    print(f"[STARTUP] Initializing knowledge base with 10 documents...")
    # Knowledge base is initialized on import
    from knowledge_base import knowledge_base  # noqa: F401
    print(f"[STARTUP] Knowledge base loaded into ChromaDB")
    print(f"[STARTUP] Initializing observability...")
    print(f"[STARTUP] System ready!")
    print(f"[STARTUP] Server starting on http://0.0.0.0:8000")
    print(f"[STARTUP] Docs available at http://0.0.0.0:8000/docs")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
