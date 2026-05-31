"""
Parent-Child RAG Implementation
================================
Small chunks for precise search, large chunks for rich context.
Demonstrates how parent-child retrieval provides better answers
than either small or large chunks alone.
"""

import os
import time
import glob
import re
from dotenv import load_dotenv
from openai import OpenAI
import chromadb

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o-mini"


# ============================================================
# Two-Level Chunking: Parents and Children
# ============================================================
def create_parent_child_chunks(text: str, source: str) -> tuple[list[dict], list[dict]]:
    """
    Create two levels of chunks:
    - Parents: Full sections (split by ## headings)
    - Children: Paragraphs within each section
    """
    parents = []
    children = []

    # Split by section headings (## or ###)
    sections = re.split(r'\n(#{2,3} .+)\n', text)

    current_heading = "Introduction"
    parent_id = 0

    for part in sections:
        if re.match(r'^#{2,3} ', part):
            current_heading = part.strip('# ').strip()
            continue

        if len(part.strip()) < 50:
            continue

        # This section becomes a PARENT chunk
        parent = {
            "id": f"parent_{parent_id}",
            "text": f"{current_heading}\n\n{part.strip()}",
            "source": source,
            "heading": current_heading,
        }
        parents.append(parent)

        # Split parent into CHILD chunks (by paragraph)
        paragraphs = [p.strip() for p in part.split("\n\n") if len(p.strip()) > 30]
        for child_idx, para in enumerate(paragraphs):
            child = {
                "id": f"child_{parent_id}_{child_idx}",
                "text": para,
                "parent_id": f"parent_{parent_id}",
                "source": source,
                "heading": current_heading,
            }
            children.append(child)

        parent_id += 1

    return parents, children


# ============================================================
# Build Indexes
# ============================================================
def build_indexes(docs_dir: str = "sample_docs"):
    """Build separate indexes for parents and children."""
    all_parents = []
    all_children = []

    for filepath in glob.glob(os.path.join(docs_dir, "*.txt")):
        with open(filepath, "r") as f:
            content = f.read()
        source = os.path.basename(filepath)
        parents, children = create_parent_child_chunks(content, source)
        all_parents.extend(parents)
        all_children.extend(children)

    print(f"📄 Created {len(all_parents)} parent chunks, {len(all_children)} child chunks")

    # Embed children (search index)
    child_texts = [c["text"] for c in all_children]
    print(f"🔢 Embedding {len(child_texts)} child chunks...")
    response = client.embeddings.create(input=child_texts, model=EMBEDDING_MODEL)
    child_embeddings = [item.embedding for item in response.data]

    # Store children in ChromaDB
    chroma_client = chromadb.Client()
    child_collection = chroma_client.create_collection("children", metadata={"hnsw:space": "cosine"})
    child_collection.add(
        ids=[c["id"] for c in all_children],
        embeddings=child_embeddings,
        documents=child_texts,
        metadatas=[{"parent_id": c["parent_id"], "source": c["source"], "heading": c["heading"]} for c in all_children],
    )

    # Also embed parents for comparison
    parent_texts = [p["text"] for p in all_parents]
    print(f"🔢 Embedding {len(parent_texts)} parent chunks...")
    response = client.embeddings.create(input=parent_texts, model=EMBEDDING_MODEL)
    parent_embeddings = [item.embedding for item in response.data]

    parent_collection = chroma_client.create_collection("parents", metadata={"hnsw:space": "cosine"})
    parent_collection.add(
        ids=[p["id"] for p in all_parents],
        embeddings=parent_embeddings,
        documents=parent_texts,
        metadatas=[{"source": p["source"], "heading": p["heading"]} for p in all_parents],
    )

    # Build parent lookup
    parent_lookup = {p["id"]: p for p in all_parents}

    return child_collection, parent_collection, parent_lookup


# ============================================================
# Parent-Child Retrieval
# ============================================================
def parent_child_retrieve(child_collection, parent_lookup, query: str, top_k: int = 3):
    """Search children, return parents."""
    response = client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
    query_emb = response.data[0].embedding

    # Search against child chunks
    results = child_collection.query(query_embeddings=[query_emb], n_results=top_k)

    retrieved_parents = []
    seen_parent_ids = set()

    print(f"\n  🔍 Child chunks matched:")
    for i in range(len(results["ids"][0])):
        child_text = results["documents"][0][i]
        parent_id = results["metadatas"][0][i]["parent_id"]
        distance = results["distances"][0][i]

        print(f"     Child: \"{child_text[:60]}...\" (dist={distance:.4f})")
        print(f"     → Maps to parent: {parent_id}")

        if parent_id not in seen_parent_ids:
            seen_parent_ids.add(parent_id)
            parent = parent_lookup[parent_id]
            retrieved_parents.append(parent)

    return retrieved_parents


# ============================================================
# Direct Parent Search (for comparison)
# ============================================================
def direct_parent_retrieve(parent_collection, query: str, top_k: int = 3):
    """Search directly against parent chunks."""
    response = client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
    query_emb = response.data[0].embedding

    results = parent_collection.query(query_embeddings=[query_emb], n_results=top_k)
    return [{"text": results["documents"][0][i], "source": results["metadatas"][0][i]["source"]}
            for i in range(len(results["ids"][0]))]


# ============================================================
# Generate Answer
# ============================================================
def generate_answer(query: str, context_chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join([f"[{c.get('heading', 'Section')}]\n{c['text']}" for c in context_chunks])

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": "Answer based ONLY on context. Cite sections. Be thorough."},
            {"role": "user", "content": f"Context:\n{context}\n\n---\nQuestion: {query}"},
        ],
        temperature=0,
        max_tokens=400,
    )
    return response.choices[0].message.content


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("PARENT-CHILD RAG DEMO")
    print("=" * 60)

    child_collection, parent_collection, parent_lookup = build_indexes()

    queries = [
        "What happens when a user is removed from the workspace?",
        "How does API key rotation work?",
        "What are the payment options and what happens if payment is overdue?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"❓ Query: {query}")
        print("=" * 60)

        # Parent-child approach
        print("\n  📐 PARENT-CHILD APPROACH (search children → return parents):")
        parents = parent_child_retrieve(child_collection, parent_lookup, query)
        answer_pc = generate_answer(query, parents)
        print(f"\n  🤖 Answer:\n     {answer_pc}")

        # Compare: direct large chunk search
        print(f"\n  📏 DIRECT PARENT SEARCH (for comparison):")
        direct = direct_parent_retrieve(parent_collection, query)
        answer_direct = generate_answer(query, direct)
        print(f"\n  🤖 Answer:\n     {answer_direct}")


if __name__ == "__main__":
    main()
