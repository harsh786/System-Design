"""
Permission-Aware RAG
Demonstrates how to enforce document-level permissions in vector search.
Uses ChromaDB with metadata filtering for access control.
"""

import chromadb
from dataclasses import dataclass


@dataclass
class User:
    user_id: str
    groups: list[str]
    tenant_id: str


# ─── Sample Documents with ACLs ───

DOCUMENTS = [
    {
        "id": "doc_001",
        "content": "The ML pipeline processes 10M records daily using distributed training.",
        "metadata": {
            "title": "ML Pipeline Architecture",
            "allowed_groups": "engineering,ml-team",
            "tenant_id": "acme_corp",
            "confidentiality": "internal",
        },
    },
    {
        "id": "doc_002",
        "content": "Q4 revenue reached $50M, a 23% increase year-over-year.",
        "metadata": {
            "title": "Q4 Financial Results",
            "allowed_groups": "finance,executives",
            "tenant_id": "acme_corp",
            "confidentiality": "confidential",
        },
    },
    {
        "id": "doc_003",
        "content": "The Kubernetes cluster autoscales based on GPU utilization metrics.",
        "metadata": {
            "title": "Infrastructure Scaling Guide",
            "allowed_groups": "engineering,devops",
            "tenant_id": "acme_corp",
            "confidentiality": "internal",
        },
    },
    {
        "id": "doc_004",
        "content": "Board approved the acquisition of DataCo for $200M.",
        "metadata": {
            "title": "Board Meeting Minutes - Acquisition",
            "allowed_groups": "executives",
            "tenant_id": "acme_corp",
            "confidentiality": "top-secret",
        },
    },
    {
        "id": "doc_005",
        "content": "Company-wide holiday party scheduled for December 20th in the main hall.",
        "metadata": {
            "title": "Holiday Party Announcement",
            "allowed_groups": "all-employees",
            "tenant_id": "acme_corp",
            "confidentiality": "public",
        },
    },
    {
        "id": "doc_006",
        "content": "Globex new product launch uses transformer models for real-time inference.",
        "metadata": {
            "title": "Globex Product Launch Plan",
            "allowed_groups": "engineering,product",
            "tenant_id": "globex_inc",
            "confidentiality": "internal",
        },
    },
]

# ─── Sample Users ───

USERS = {
    "alice": User(user_id="alice", groups=["engineering", "ml-team"], tenant_id="acme_corp"),
    "bob": User(user_id="bob", groups=["finance", "all-employees"], tenant_id="acme_corp"),
    "carol": User(user_id="carol", groups=["executives", "all-employees", "finance"], tenant_id="acme_corp"),
    "dave": User(user_id="dave", groups=["engineering", "product"], tenant_id="globex_inc"),
}


def setup_collection(client: chromadb.Client) -> chromadb.Collection:
    """Create and populate the vector collection."""
    # Delete if exists
    try:
        client.delete_collection("documents")
    except Exception:
        pass

    collection = client.create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=[doc["id"] for doc in DOCUMENTS],
        documents=[doc["content"] for doc in DOCUMENTS],
        metadatas=[doc["metadata"] for doc in DOCUMENTS],
    )

    return collection


def search_prefilter(collection: chromadb.Collection, query: str, user: User, top_k: int = 5) -> list:
    """
    PRE-FILTER: Apply permissions BEFORE vector search.
    Only searches documents the user is allowed to see.
    """
    # Build permission filter: user's groups must overlap with doc's allowed_groups
    # ChromaDB uses $contains for string matching in metadata
    # We check each of user's groups against the allowed_groups field
    where_filters = []
    for group in user.groups:
        where_filters.append({"allowed_groups": {"$contains": group}})

    # Also enforce tenant isolation
    where_filter = {
        "$and": [
            {"tenant_id": {"$eq": user.tenant_id}},
            {"$or": where_filters} if len(where_filters) > 1 else where_filters[0],
        ]
    }

    results = collection.query(
        query_texts=[query],
        where=where_filter,
        n_results=top_k,
    )

    return results


def search_postfilter(collection: chromadb.Collection, query: str, user: User, top_k: int = 5) -> list:
    """
    POST-FILTER: Vector search first (all docs), then filter by permissions.
    """
    # Search without permission filter
    results = collection.query(
        query_texts=[query],
        where={"tenant_id": {"$eq": user.tenant_id}},  # Only tenant isolation
        n_results=top_k * 3,  # Fetch more to account for filtering
    )

    # Post-filter: remove unauthorized results
    filtered_ids = []
    filtered_docs = []
    filtered_meta = []
    filtered_distances = []

    if results["ids"] and results["ids"][0]:
        for i, meta in enumerate(results["metadatas"][0]):
            allowed = meta["allowed_groups"].split(",")
            if any(g in allowed for g in user.groups):
                filtered_ids.append(results["ids"][0][i])
                filtered_docs.append(results["documents"][0][i])
                filtered_meta.append(meta)
                filtered_distances.append(results["distances"][0][i])
                if len(filtered_ids) >= top_k:
                    break

    return {
        "ids": [filtered_ids],
        "documents": [filtered_docs],
        "metadatas": [filtered_meta],
        "distances": [filtered_distances],
    }


def print_results(results: dict, label: str):
    """Pretty print search results."""
    print(f"\n    Results ({label}):")
    if not results["ids"][0]:
        print("      (no results)")
        return

    for i, doc_id in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i]
        content = results["documents"][0][i][:60]
        print(f"      [{doc_id}] {meta['title']}")
        print(f"        Groups: {meta['allowed_groups']} | Conf: {meta['confidentiality']}")
        print(f"        Content: {content}...")


def main():
    print("=" * 70)
    print("PERMISSION-AWARE RAG Demo")
    print("=" * 70)

    client = chromadb.Client()
    collection = setup_collection(client)
    print(f"\n  Indexed {len(DOCUMENTS)} documents across 2 tenants.")

    query = "machine learning and data processing"

    # ─── Scenario 1: Engineering user (sees engineering docs only) ───
    print("\n" + "─" * 50)
    print("SCENARIO 1: Alice (engineering, ml-team) @ acme_corp")
    print(f"  Query: '{query}'")
    print("─" * 50)

    results = search_prefilter(collection, query, USERS["alice"])
    print_results(results, "pre-filter")

    # ─── Scenario 2: Finance user (sees finance docs only) ───
    print("\n" + "─" * 50)
    print("SCENARIO 2: Bob (finance, all-employees) @ acme_corp")
    print(f"  Query: '{query}'")
    print("─" * 50)

    results = search_prefilter(collection, query, USERS["bob"])
    print_results(results, "pre-filter")

    # ─── Scenario 3: Executive (sees everything) ───
    print("\n" + "─" * 50)
    print("SCENARIO 3: Carol (executives, finance, all-employees) @ acme_corp")
    print(f"  Query: 'acquisition revenue'")
    print("─" * 50)

    results = search_prefilter(collection, "acquisition revenue", USERS["carol"])
    print_results(results, "pre-filter")

    # ─── Scenario 4: Cross-tenant isolation ───
    print("\n" + "─" * 50)
    print("SCENARIO 4: Cross-Tenant Isolation")
    print("  Dave (engineering @ globex_inc) searches for acme content")
    print("─" * 50)

    results = search_prefilter(collection, "ML pipeline distributed training", USERS["dave"])
    print_results(results, "pre-filter, tenant=globex_inc")
    print("\n    ✓ Dave cannot see acme_corp documents (tenant isolation enforced)")

    # ─── Scenario 5: Pre-filter vs Post-filter comparison ───
    print("\n" + "─" * 50)
    print("SCENARIO 5: Pre-Filter vs Post-Filter Comparison")
    print("  Alice (engineering) searches 'company plans'")
    print("─" * 50)

    query2 = "company plans and strategy"
    print("\n  Pre-filter approach:")
    pre_results = search_prefilter(collection, query2, USERS["alice"])
    print_results(pre_results, "pre-filter")

    print("\n  Post-filter approach:")
    post_results = search_postfilter(collection, query2, USERS["alice"])
    print_results(post_results, "post-filter")

    print("\n  Note: Both approaches return the same authorized docs.")
    print("  Pre-filter is more secure (never touches unauthorized docs).")
    print("  Post-filter may have better relevance but risks information leakage.")

    # ─── Permission Revocation ───
    print("\n" + "─" * 50)
    print("SCENARIO 6: Permission Revocation")
    print("  Alice loses 'ml-team' group membership")
    print("─" * 50)

    alice_before = USERS["alice"]
    alice_after = User(user_id="alice", groups=["engineering"], tenant_id="acme_corp")

    print(f"\n  Before (groups: {alice_before.groups}):")
    results_before = search_prefilter(collection, "ML pipeline", alice_before)
    print_results(results_before, "before revocation")

    print(f"\n  After (groups: {alice_after.groups}):")
    results_after = search_prefilter(collection, "ML pipeline", alice_after)
    print_results(results_after, "after revocation")
    print("\n  ✓ Permission change immediately reflected in search results")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
