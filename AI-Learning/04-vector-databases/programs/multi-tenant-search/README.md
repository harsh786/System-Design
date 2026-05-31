# Multi-Tenant Vector Search

## What This Program Does

Demonstrates how to implement tenant isolation in vector search — ensuring that one tenant's data is never visible to another. Compares metadata-based isolation vs separate collections.

## Concepts Demonstrated

1. **Metadata-based tenant isolation** — shared collection with tenant_id filter
2. **Separate collection isolation** — one collection per tenant
3. **Security verification** — proving tenants cannot see each other's data
4. **Permission-aware search** — combining tenant filter with access controls
5. **Performance comparison** — shared vs separate collection approaches

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
```

## Running

```bash
python main.py
```

## Key Takeaways

- Metadata filtering is the simplest multi-tenancy pattern
- Always filter server-side — never trust the client
- Shared collections are more memory-efficient
- Separate collections provide stronger isolation guarantees
- Permission-aware search adds latency but is essential for security
