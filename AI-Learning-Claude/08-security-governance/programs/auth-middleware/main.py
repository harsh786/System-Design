"""
Auth Middleware for AI APIs
============================
FastAPI app demonstrating JWT auth, RBAC, permission-aware RAG filtering,
and audit logging for AI endpoints.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

load_dotenv()

# --- Configuration ---

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

# --- Logging (Audit Trail) ---

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
audit_log = logging.getLogger("audit")

# --- User/Role Definitions ---

USERS_DB = {
    "admin": {
        "user_id": "user-001",
        "name": "Alice Admin",
        "role": "admin",
        "department": "engineering",
        "clearance": "top-secret",
        "permissions": ["read:all", "write:all", "query:all-data", "tools:all"],
    },
    "analyst": {
        "user_id": "user-002",
        "name": "Bob Analyst",
        "role": "analyst",
        "department": "finance",
        "clearance": "confidential",
        "permissions": ["read:own-dept", "query:finance-data", "tools:read-only"],
    },
    "viewer": {
        "user_id": "user-003",
        "name": "Charlie Viewer",
        "role": "viewer",
        "department": "marketing",
        "clearance": "public",
        "permissions": ["read:public", "query:public-data"],
    },
}

# --- Simulated Document Store (RAG data) ---

DOCUMENTS = [
    {"id": "doc-1", "title": "Q3 Revenue Report", "department": "finance", "classification": "confidential", "content": "Revenue was $10M..."},
    {"id": "doc-2", "title": "Product Roadmap 2025", "department": "engineering", "classification": "top-secret", "content": "Next year we plan..."},
    {"id": "doc-3", "title": "Marketing Campaign Results", "department": "marketing", "classification": "internal", "content": "Campaign reached 1M users..."},
    {"id": "doc-4", "title": "Company Overview", "department": "all", "classification": "public", "content": "Acme Corp is a leader..."},
    {"id": "doc-5", "title": "Employee Compensation Data", "department": "hr", "classification": "top-secret", "content": "CEO salary: $500K..."},
    {"id": "doc-6", "title": "Public API Documentation", "department": "all", "classification": "public", "content": "Our API supports..."},
]

CLEARANCE_LEVELS = {"public": 0, "internal": 1, "confidential": 2, "top-secret": 3}

# --- JWT Token Handling ---

def create_token(username: str) -> str:
    """Create a JWT token for a user."""
    user = USERS_DB.get(username)
    if not user:
        raise ValueError(f"Unknown user: {username}")

    payload = {
        "sub": user["user_id"],
        "username": username,
        "name": user["name"],
        "role": user["role"],
        "department": user["department"],
        "clearance": user["clearance"],
        "permissions": user["permissions"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


# --- FastAPI App ---

app = FastAPI(title="AI Auth Middleware Demo", version="1.0.0")
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency: extract and validate user from JWT token."""
    return decode_token(credentials.credentials)


def require_role(allowed_roles: list[str]):
    """Dependency factory: require specific roles."""
    async def check_role(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            audit_log.warning(f"ACCESS DENIED | user={user['username']} | required_roles={allowed_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' not authorized. Required: {allowed_roles}",
            )
        return user
    return check_role


# --- Permission-Aware RAG Filtering ---

def filter_documents_for_user(user: dict, query: str = "") -> list[dict]:
    """Filter documents based on user's clearance and department.
    This simulates permission-aware RAG retrieval."""
    user_clearance = CLEARANCE_LEVELS.get(user["clearance"], 0)
    user_dept = user["department"]

    accessible_docs = []
    for doc in DOCUMENTS:
        doc_clearance = CLEARANCE_LEVELS.get(doc["classification"], 0)

        # Check clearance level
        if doc_clearance > user_clearance:
            continue

        # Check department (admin sees all, others see own dept + "all")
        if user["role"] != "admin" and doc["department"] not in [user_dept, "all"]:
            continue

        # Simple query matching (in real RAG this would be vector similarity)
        if query and query.lower() not in doc["title"].lower() and query.lower() not in doc["content"].lower():
            continue

        accessible_docs.append(doc)

    return accessible_docs


# --- Endpoints ---

@app.get("/token/{username}")
async def get_token(username: str):
    """Simulate login - get a JWT token for testing."""
    if username not in USERS_DB:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found. Available: {list(USERS_DB.keys())}")
    token = create_token(username)
    return {"access_token": token, "token_type": "bearer", "user": USERS_DB[username]["name"]}


@app.get("/ai/query")
async def ai_query(q: str = "", user: dict = Depends(get_current_user)):
    """AI query endpoint with permission-aware document retrieval."""
    # Audit log
    audit_log.info(f"AI QUERY | user={user['username']} | role={user['role']} | query=\"{q}\"")

    # Permission-aware retrieval
    accessible_docs = filter_documents_for_user(user, q)

    # Log what was accessible
    audit_log.info(f"RETRIEVAL | user={user['username']} | docs_accessible={len(accessible_docs)} | "
                   f"doc_ids={[d['id'] for d in accessible_docs]}")

    return {
        "user": user["name"],
        "role": user["role"],
        "clearance": user["clearance"],
        "query": q,
        "accessible_documents": accessible_docs,
        "total_in_system": len(DOCUMENTS),
        "note": f"User can see {len(accessible_docs)}/{len(DOCUMENTS)} documents based on permissions",
    }


@app.get("/ai/admin-tools")
async def admin_tools(user: dict = Depends(require_role(["admin"]))):
    """Admin-only endpoint for AI system management."""
    audit_log.info(f"ADMIN ACCESS | user={user['username']}")
    return {
        "message": "Admin tools accessible",
        "available_actions": ["retrain_model", "update_guardrails", "view_all_logs", "manage_users"],
    }


@app.get("/ai/my-permissions")
async def my_permissions(user: dict = Depends(get_current_user)):
    """Show current user's permissions and access level."""
    accessible_docs = filter_documents_for_user(user)
    return {
        "user": user["name"],
        "role": user["role"],
        "department": user["department"],
        "clearance": user["clearance"],
        "permissions": user["permissions"],
        "accessible_document_count": len(accessible_docs),
        "total_documents": len(DOCUMENTS),
    }


# --- Run ---

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print(" AUTH MIDDLEWARE FOR AI APIs - DEMO")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET /token/{username}     - Get a JWT token (admin, analyst, viewer)")
    print("  GET /ai/query?q=...       - Query with permission-aware retrieval")
    print("  GET /ai/admin-tools       - Admin-only endpoint")
    print("  GET /ai/my-permissions    - See your access level")
    print("\nTry:")
    print("  1. curl http://localhost:8000/token/admin")
    print("  2. curl -H 'Authorization: Bearer <token>' http://localhost:8000/ai/query?q=revenue")
    print("  3. Compare results with analyst and viewer tokens")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
