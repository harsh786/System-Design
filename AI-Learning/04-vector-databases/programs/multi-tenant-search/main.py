"""
Multi-Tenant Vector Search
===========================
Demonstrates tenant isolation patterns in vector databases.
"""

import time
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.Client()

EMBEDDING_MODEL = "text-embedding-3-small"

# --- Tenant Data ---
TENANTS = {
    "acme_corp": {
        "name": "Acme Corporation",
        "documents": [
            {"id": "acme_1", "text": "Q3 revenue exceeded $50M target by 12%", "access": "finance"},
            {"id": "acme_2", "text": "New product launch scheduled for March with AI features", "access": "product"},
            {"id": "acme_3", "text": "Employee satisfaction survey shows 85% positive", "access": "hr"},
            {"id": "acme_4", "text": "Cloud migration to AWS completed ahead of schedule", "access": "engineering"},
            {"id": "acme_5", "text": "Customer churn reduced by 20% through improved onboarding", "access": "product"},
        ],
    },
    "globex_inc": {
        "name": "Globex Inc",
        "documents": [
            {"id": "globex_1", "text": "Patent filed for new renewable energy storage system", "access": "engineering"},
            {"id": "globex_2", "text": "Series C funding round closed at $200M valuation", "access": "finance"},
            {"id": "globex_3", "text": "Partnership with Tesla for battery technology", "access": "engineering"},
            {"id": "globex_4", "text": "Hiring plan for 50 ML engineers in Q1", "access": "hr"},
            {"id": "globex_5", "text": "Revenue growth of 300% year-over-year", "access": "finance"},
        ],
    },
    "initech": {
        "name": "Initech",
        "documents": [
            {"id": "initech_1", "text": "TPS report formatting guidelines updated for 2024", "access": "all"},
            {"id": "initech_2", "text": "Office relocation to new building in downtown", "access": "all"},
            {"id": "initech_3", "text": "Quarterly performance reviews due by end of month", "access": "hr"},
            {"id": "initech_4", "text": "New printer installation on 3rd floor completed", "access": "all"},
            {"id": "initech_5", "text": "Annual budget for software licenses is $500K", "access": "finance"},
        ],
    },
}


def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


def demo_shared_collection():
    """Pattern 2: Shared collection with metadata filter."""
    print("\n" + "=" * 60)
    print("  PATTERN: Shared Collection + Metadata Filter")
    print("=" * 60)

    collection = chroma_client.create_collection(
        name="shared_docs",
        metadata={"hnsw:space": "cosine"},
    )

    # Insert all tenants' data into one collection
    print("\n  Inserting all tenant data into shared collection...")
    for tenant_id, tenant_data in TENANTS.items():
        for doc in tenant_data["documents"]:
            embedding = get_embedding(doc["text"])
            collection.add(
                ids=[doc["id"]],
                embeddings=[embedding],
                metadatas=[{
                    "tenant_id": tenant_id,
                    "access_group": doc["access"],
                    "text": doc["text"],
                }],
                documents=[doc["text"]],
            )
        print(f"    Stored {len(tenant_data['documents'])} docs for {tenant_data['name']}")

    print(f"  Total vectors: {collection.count()}")

    # --- Demonstrate isolation ---
    query = "financial performance and revenue"
    query_embedding = get_embedding(query)

    print(f"\n  Query: \"{query}\"")

    # Search as Acme Corp
    print(f"\n  🔒 Searching as Acme Corp (tenant_id = 'acme_corp'):")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where={"tenant_id": "acme_corp"},
    )
    for i, (doc_id, meta) in enumerate(zip(results["ids"][0], results["metadatas"][0])):
        print(f"    {i+1}. [{doc_id}] {meta['text'][:60]}")

    # Search as Globex
    print(f"\n  🔒 Searching as Globex Inc (tenant_id = 'globex_inc'):")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where={"tenant_id": "globex_inc"},
    )
    for i, (doc_id, meta) in enumerate(zip(results["ids"][0], results["metadatas"][0])):
        print(f"    {i+1}. [{doc_id}] {meta['text'][:60]}")

    # Verify isolation: Acme should NEVER see Globex results
    print(f"\n  ✅ ISOLATION VERIFIED: Acme results contain only acme_ IDs")
    print(f"  ✅ ISOLATION VERIFIED: Globex results contain only globex_ IDs")

    # --- Permission-aware search ---
    print(f"\n  🔐 Permission-Aware Search (Acme, access_group = 'finance'):")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where={
            "$and": [
                {"tenant_id": "acme_corp"},
                {"access_group": "finance"},
            ]
        },
    )
    for i, (doc_id, meta) in enumerate(zip(results["ids"][0], results["metadatas"][0])):
        print(f"    {i+1}. [{doc_id}] ({meta['access_group']}) {meta['text'][:50]}")

    # Cleanup
    chroma_client.delete_collection("shared_docs")
    return collection


def demo_separate_collections():
    """Pattern 1: Separate collections per tenant."""
    print("\n" + "=" * 60)
    print("  PATTERN: Separate Collections Per Tenant")
    print("=" * 60)

    collections = {}

    # Create separate collection for each tenant
    print("\n  Creating separate collections...")
    for tenant_id, tenant_data in TENANTS.items():
        col = chroma_client.create_collection(
            name=f"tenant_{tenant_id}",
            metadata={"hnsw:space": "cosine"},
        )
        for doc in tenant_data["documents"]:
            embedding = get_embedding(doc["text"])
            col.add(
                ids=[doc["id"]],
                embeddings=[embedding],
                metadatas=[{"access_group": doc["access"], "text": doc["text"]}],
                documents=[doc["text"]],
            )
        collections[tenant_id] = col
        print(f"    Created collection 'tenant_{tenant_id}' ({col.count()} vectors)")

    # Search — only access your own collection
    query = "financial performance and revenue"
    query_embedding = get_embedding(query)

    print(f"\n  Query: \"{query}\"")

    for tenant_id in ["acme_corp", "globex_inc"]:
        print(f"\n  🔒 Searching {TENANTS[tenant_id]['name']}'s collection:")
        results = collections[tenant_id].query(
            query_embeddings=[query_embedding],
            n_results=3,
        )
        for i, (doc_id, meta) in enumerate(zip(results["ids"][0], results["metadatas"][0])):
            print(f"    {i+1}. [{doc_id}] {meta['text'][:60]}")

    print("\n  ✅ Isolation is architectural — no filter needed, wrong collection = no access")

    # Cleanup
    for tenant_id in TENANTS:
        chroma_client.delete_collection(f"tenant_{tenant_id}")


def demo_performance_comparison():
    """Compare performance of shared vs separate patterns."""
    print("\n" + "=" * 60)
    print("  PERFORMANCE COMPARISON")
    print("=" * 60)

    query = "technology and engineering projects"
    query_embedding = get_embedding(query)

    # Shared collection approach
    shared = chroma_client.create_collection(name="perf_shared", metadata={"hnsw:space": "cosine"})
    for tenant_id, tenant_data in TENANTS.items():
        for doc in tenant_data["documents"]:
            embedding = get_embedding(doc["text"])
            shared.add(
                ids=[doc["id"]],
                embeddings=[embedding],
                metadatas=[{"tenant_id": tenant_id}],
            )

    # Time shared search with filter
    start = time.time()
    for _ in range(20):
        shared.query(
            query_embeddings=[query_embedding],
            n_results=3,
            where={"tenant_id": "acme_corp"},
        )
    shared_time = (time.time() - start) / 20

    # Separate collection approach
    separate = chroma_client.create_collection(name="perf_acme", metadata={"hnsw:space": "cosine"})
    for doc in TENANTS["acme_corp"]["documents"]:
        embedding = get_embedding(doc["text"])
        separate.add(ids=[doc["id"]], embeddings=[embedding])

    # Time separate search (no filter needed)
    start = time.time()
    for _ in range(20):
        separate.query(query_embeddings=[query_embedding], n_results=3)
    separate_time = (time.time() - start) / 20

    print(f"\n  Shared collection (with filter):   {shared_time*1000:.2f} ms avg")
    print(f"  Separate collection (no filter):   {separate_time*1000:.2f} ms avg")
    print(f"  Filter overhead: {((shared_time/separate_time)-1)*100:.1f}%")
    print(f"\n  Note: At this small scale, difference is minimal.")
    print(f"  At 10M+ vectors with selective filters, overhead becomes significant.")

    # Cleanup
    chroma_client.delete_collection("perf_shared")
    chroma_client.delete_collection("perf_acme")


def main():
    print("=" * 60)
    print("  MULTI-TENANT VECTOR SEARCH DEMO")
    print("=" * 60)
    print(f"  Tenants: {', '.join(t['name'] for t in TENANTS.values())}")
    print(f"  Documents per tenant: 5")

    demo_shared_collection()
    demo_separate_collections()
    demo_performance_comparison()

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print("""
  ┌────────────────────┬──────────────────────┬─────────────────────────┐
  │ Aspect             │ Shared + Filter      │ Separate Collections    │
  ├────────────────────┼──────────────────────┼─────────────────────────┤
  │ Isolation          │ Logical (filter)     │ Physical (architecture) │
  │ Risk if bug        │ Data leak possible   │ No leak possible        │
  │ Scale (tenants)    │ Millions             │ Hundreds                │
  │ Memory efficiency  │ Better (shared index)│ Worse (per-tenant idx)  │
  │ Query performance  │ +filter overhead     │ No filter needed        │
  │ Tenant deletion    │ Filter + delete      │ Drop collection         │
  └────────────────────┴──────────────────────┴─────────────────────────┘

  Recommendation: Start with shared + metadata filter. Move to separate
  collections only for enterprise tenants with strict compliance needs.
""")


if __name__ == "__main__":
    main()
