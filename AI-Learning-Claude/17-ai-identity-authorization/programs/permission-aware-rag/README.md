# Permission-Aware RAG

Implements a RAG system that enforces document-level permissions, ensuring users only retrieve documents they're authorized to access.

## Concepts Demonstrated
- Document-level ACLs (access control lists)
- Pre-filter approach (permissions applied before vector search)
- Post-filter approach (permissions applied after vector search)
- Cross-tenant isolation
- Group-based permissions

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Expected Output
Shows how different users with different group memberships see different search results from the same query.
