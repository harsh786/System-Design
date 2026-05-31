"""
Vector Search Basics - ChromaDB + OpenAI Embeddings
====================================================
Demonstrates: embedding, storage, similarity search, metadata filtering.
"""

import chromadb
from openai import OpenAI
from dotenv import load_dotenv
import numpy as np
import os

load_dotenv()

# --- Configuration ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.Client()  # In-memory for demo

EMBEDDING_MODEL = "text-embedding-3-small"


def get_embedding(text: str) -> list[float]:
    """Get embedding from OpenAI API."""
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# --- Sample Data: Movie Descriptions ---
MOVIES = [
    {
        "id": "movie_1",
        "title": "The Matrix",
        "description": "A computer hacker discovers that reality is a simulation created by machines, and joins a rebellion to free humanity.",
        "genre": "sci-fi",
        "year": 1999,
    },
    {
        "id": "movie_2",
        "title": "Inception",
        "description": "A thief who steals corporate secrets through dream-sharing technology is given the task of planting an idea into a CEO's mind.",
        "genre": "sci-fi",
        "year": 2010,
    },
    {
        "id": "movie_3",
        "title": "The Shawshank Redemption",
        "description": "A banker sentenced to life in prison forms a friendship with a fellow inmate and finds hope and redemption through acts of decency.",
        "genre": "drama",
        "year": 1994,
    },
    {
        "id": "movie_4",
        "title": "Jurassic Park",
        "description": "Scientists clone dinosaurs to create a theme park, but things go terribly wrong when the dinosaurs escape their enclosures.",
        "genre": "sci-fi",
        "year": 1993,
    },
    {
        "id": "movie_5",
        "title": "The Godfather",
        "description": "The aging patriarch of an organized crime dynasty transfers control of his empire to his reluctant youngest son.",
        "genre": "drama",
        "year": 1972,
    },
    {
        "id": "movie_6",
        "title": "Interstellar",
        "description": "A team of explorers travel through a wormhole in space in an attempt to save humanity from a dying Earth.",
        "genre": "sci-fi",
        "year": 2014,
    },
    {
        "id": "movie_7",
        "title": "Forrest Gump",
        "description": "A simple man with a low IQ accomplishes great things in life and inspires the people around him through kindness.",
        "genre": "drama",
        "year": 1994,
    },
    {
        "id": "movie_8",
        "title": "The Dark Knight",
        "description": "Batman faces a criminal mastermind known as the Joker who wants to plunge Gotham City into anarchy.",
        "genre": "action",
        "year": 2008,
    },
]


def main():
    print("=" * 60)
    print("VECTOR SEARCH BASICS - ChromaDB + OpenAI")
    print("=" * 60)

    # --- Step 1: Create Collection ---
    print("\n📦 Step 1: Creating ChromaDB collection...")
    collection = chroma_client.create_collection(
        name="movies",
        metadata={"hnsw:space": "cosine"},  # Use cosine similarity
    )

    # --- Step 2: Embed and Store Movies ---
    print("\n🔢 Step 2: Embedding and storing movie descriptions...")
    for movie in MOVIES:
        embedding = get_embedding(movie["description"])
        collection.add(
            ids=[movie["id"]],
            embeddings=[embedding],
            metadatas=[{
                "title": movie["title"],
                "genre": movie["genre"],
                "year": movie["year"],
            }],
            documents=[movie["description"]],
        )
        print(f"   Stored: {movie['title']} ({len(embedding)} dimensions)")

    print(f"\n   Total vectors in collection: {collection.count()}")

    # --- Step 3: Similarity Search ---
    print("\n" + "=" * 60)
    print("🔍 Step 3: Similarity Search")
    print("=" * 60)

    queries = [
        "a movie about virtual reality and computers",
        "a story about hope and friendship in difficult times",
        "space exploration and saving the world",
        "a superhero fighting a villain",
    ]

    for query in queries:
        print(f"\n   Query: \"{query}\"")
        print("   " + "-" * 50)

        query_embedding = get_embedding(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3,
        )

        for i, (doc_id, distance, metadata) in enumerate(zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        )):
            similarity = 1 - distance  # ChromaDB returns distance, not similarity
            bar = "█" * int(similarity * 20)
            print(f"   {i+1}. {metadata['title']:<25} similarity: {similarity:.4f} {bar}")

    # --- Step 4: Metadata Filtering ---
    print("\n" + "=" * 60)
    print("🏷️  Step 4: Metadata Filtering")
    print("=" * 60)

    query = "an exciting adventure story"
    query_embedding = get_embedding(query)

    print(f"\n   Query: \"{query}\"")

    # Without filter
    print("\n   WITHOUT filter (all genres):")
    results = collection.query(query_embeddings=[query_embedding], n_results=3)
    for i, meta in enumerate(results["metadatas"][0]):
        dist = results["distances"][0][i]
        print(f"   {i+1}. {meta['title']:<25} genre: {meta['genre']:<8} sim: {1-dist:.4f}")

    # With genre filter
    print("\n   WITH filter (genre = 'sci-fi' only):")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where={"genre": "sci-fi"},
    )
    for i, meta in enumerate(results["metadatas"][0]):
        dist = results["distances"][0][i]
        print(f"   {i+1}. {meta['title']:<25} genre: {meta['genre']:<8} sim: {1-dist:.4f}")

    # With year filter
    print("\n   WITH filter (year >= 2000):")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where={"year": {"$gte": 2000}},
    )
    for i, meta in enumerate(results["metadatas"][0]):
        dist = results["distances"][0][i]
        print(f"   {i+1}. {meta['title']:<25} year: {meta['year']:<8} sim: {1-dist:.4f}")

    # --- Step 5: Direct Similarity Comparison ---
    print("\n" + "=" * 60)
    print("📊 Step 5: Pairwise Similarity Matrix")
    print("=" * 60)

    # Compare a few movies directly
    titles = ["The Matrix", "Inception", "Interstellar", "The Godfather"]
    selected = [m for m in MOVIES if m["title"] in titles]
    embeddings = {m["title"]: get_embedding(m["description"]) for m in selected}

    print(f"\n   {'':20}", end="")
    for t in titles:
        print(f"{t[:12]:>13}", end="")
    print()

    for t1 in titles:
        print(f"   {t1:20}", end="")
        for t2 in titles:
            sim = cosine_similarity(embeddings[t1], embeddings[t2])
            print(f"{sim:13.4f}", end="")
        print()

    print("\n" + "=" * 60)
    print("✅ Done! Key observations:")
    print("   - Semantically similar queries find relevant movies")
    print("   - Metadata filters narrow results without losing relevance")
    print("   - Sci-fi movies cluster together in vector space")
    print("=" * 60)


if __name__ == "__main__":
    main()
