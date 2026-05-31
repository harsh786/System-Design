# Auth Middleware for AI APIs

FastAPI middleware demonstrating JWT-based authentication and role-based access control for AI endpoints. Shows permission-aware query filtering for RAG systems.

## What It Does

1. **JWT validation** — Verifies tokens on every request, extracts user claims
2. **RBAC** — Different roles (admin, analyst, viewer) get different access levels
3. **Permission-aware RAG** — Automatically filters retrieved data based on user permissions
4. **Audit logging** — Logs all access with user identity, action, and timestamp

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
# Visit http://localhost:8000/docs for interactive API docs
```

## Test

```bash
# Get tokens (simulated login)
curl http://localhost:8000/token/admin
curl http://localhost:8000/token/analyst

# Use token to query AI endpoint
curl -H "Authorization: Bearer <token>" http://localhost:8000/ai/query?q=revenue
```
