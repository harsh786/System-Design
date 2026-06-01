"""
Project 7: RAG (Retrieval-Augmented Generation) Chatbot
=======================================================

A complete RAG pipeline that works locally without API keys.
Uses TF-IDF for embeddings and cosine similarity for retrieval.

Educational Purpose:
- Understand how RAG grounds LLM responses in factual documents
- Learn document chunking strategies (fixed-size with overlap)
- See how vector similarity search works under the hood
- Observe prompt construction with retrieved context

Run: python rag_chatbot.py
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Sample Knowledge Base (documents to search over)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_DOCUMENTS: dict[str, str] = {
    "photosynthesis.txt": (
        "Photosynthesis is the process by which green plants and some other organisms "
        "use sunlight to synthesize foods from carbon dioxide and water. Photosynthesis "
        "in plants generally involves the green pigment chlorophyll and generates oxygen "
        "as a byproduct. The light-dependent reactions occur in the thylakoid membranes "
        "of the chloroplasts. Here, water molecules are split using light energy, "
        "releasing oxygen and producing ATP and NADPH. The light-independent reactions, "
        "also known as the Calvin cycle, occur in the stroma. Carbon dioxide is fixed "
        "into glucose using the ATP and NADPH from the light reactions. The overall "
        "equation is: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2."
    ),
    "machine_learning.txt": (
        "Machine learning is a subset of artificial intelligence that enables systems "
        "to learn and improve from experience without being explicitly programmed. "
        "Supervised learning uses labeled training data to learn a mapping from inputs "
        "to outputs. Common algorithms include linear regression, decision trees, and "
        "neural networks. Unsupervised learning finds hidden patterns in unlabeled data "
        "using techniques like clustering (K-means) and dimensionality reduction (PCA). "
        "Reinforcement learning trains agents to make decisions by rewarding desired "
        "behaviors. Deep learning uses multi-layer neural networks to learn hierarchical "
        "representations. Overfitting occurs when a model memorizes training data but "
        "fails to generalize. Regularization techniques like dropout and L2 penalty "
        "help prevent overfitting."
    ),
    "solar_system.txt": (
        "The Solar System consists of the Sun and the objects that orbit it, including "
        "eight planets, their moons, and smaller bodies. The four inner planets—Mercury, "
        "Venus, Earth, and Mars—are rocky terrestrial planets. The four outer planets—"
        "Jupiter, Saturn, Uranus, and Neptune—are gas and ice giants. Jupiter is the "
        "largest planet, with a mass more than twice that of all other planets combined. "
        "The asteroid belt lies between Mars and Jupiter. Beyond Neptune lies the Kuiper "
        "Belt, home to Pluto and other dwarf planets. The Sun contains 99.86% of the "
        "Solar System's mass and is primarily composed of hydrogen and helium."
    ),
    "python_programming.txt": (
        "Python is a high-level, interpreted programming language known for its simple "
        "syntax and readability. It supports multiple paradigms including procedural, "
        "object-oriented, and functional programming. Python's standard library is "
        "extensive, providing modules for file I/O, networking, and data processing. "
        "Popular frameworks include Django and Flask for web development, NumPy and "
        "Pandas for data science, and TensorFlow and PyTorch for deep learning. "
        "Python uses dynamic typing and garbage collection. List comprehensions and "
        "generators provide elegant ways to process data. The Global Interpreter Lock "
        "(GIL) limits true multi-threading but multiprocessing can bypass this."
    ),
    "climate_change.txt": (
        "Climate change refers to long-term shifts in global temperatures and weather "
        "patterns. Since the 1800s, human activities—primarily burning fossil fuels—"
        "have been the main driver of climate change. Greenhouse gases like carbon "
        "dioxide and methane trap heat in the atmosphere, causing global warming. "
        "Effects include rising sea levels, more frequent extreme weather events, "
        "and disruption of ecosystems. The Paris Agreement aims to limit warming to "
        "1.5°C above pre-industrial levels. Mitigation strategies include renewable "
        "energy adoption, carbon capture, reforestation, and energy efficiency "
        "improvements. Adaptation measures help communities cope with unavoidable impacts."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Core RAG Components
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Chunk:
    """A chunk of text with metadata about its source."""
    text: str
    source: str
    chunk_index: int


@dataclass
class RetrievalResult:
    """A retrieved chunk with its similarity score."""
    chunk: Chunk
    score: float


class DocumentChunker:
    """Splits documents into overlapping chunks for better retrieval."""

    def __init__(self, chunk_size: int = 200, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, text: str, source: str) -> list[Chunk]:
        """Split text into character-level chunks with overlap."""
        chunks: list[Chunk] = []
        start = 0
        idx = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            # Try to break at a word boundary
            if end < len(text):
                last_space = chunk_text.rfind(" ")
                if last_space > self.chunk_size // 2:
                    chunk_text = chunk_text[:last_space]
                    end = start + last_space
            chunks.append(Chunk(text=chunk_text.strip(), source=source, chunk_index=idx))
            start = end - self.overlap
            idx += 1
        return chunks


class VectorStore:
    """In-memory vector store using TF-IDF and cosine similarity."""

    def __init__(self):
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.vectors: Optional[np.ndarray] = None
        self.chunks: list[Chunk] = []

    def index(self, chunks: list[Chunk]) -> None:
        """Build TF-IDF vectors for all chunks."""
        self.chunks = chunks
        texts = [c.text for c in chunks]
        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        self.vectors = self.vectorizer.fit_transform(texts).toarray()
        logger.info(
            f"Vector store ready: {len(chunks)} vectors of dimension {self.vectors.shape[1]}"
        )

    def search(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        """Find the most similar chunks to a query."""
        if self.vectorizer is None or self.vectors is None:
            raise RuntimeError("Vector store not indexed. Call index() first.")
        query_vec = self.vectorizer.transform([query]).toarray()
        similarities = cosine_similarity(query_vec, self.vectors)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for i in top_indices:
            if similarities[i] > 0:
                results.append(RetrievalResult(chunk=self.chunks[i], score=float(similarities[i])))
        return results


class RAGChatbot:
    """Complete RAG pipeline: chunk → embed → retrieve → generate."""

    def __init__(self, chunk_size: int = 200, overlap: int = 50, top_k: int = 3):
        self.chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap)
        self.store = VectorStore()
        self.top_k = top_k
        self._all_chunks: list[Chunk] = []

    def ingest_documents(self, documents: dict[str, str]) -> None:
        """Ingest and index a collection of documents."""
        print(f"\n[INDEXING] Loading {len(documents)} documents...")
        for source, text in documents.items():
            chunks = self.chunker.chunk_document(text, source)
            self._all_chunks.extend(chunks)
        print(
            f"[INDEXING] Chunking documents (chunk_size={self.chunker.chunk_size}, "
            f"overlap={self.chunker.overlap})..."
        )
        print(f"[INDEXING] Created {len(self._all_chunks)} chunks from {len(documents)} documents")
        print("[INDEXING] Generating TF-IDF embeddings...")
        self.store.index(self._all_chunks)

    def query(self, question: str) -> str:
        """Run the full RAG pipeline for a question."""
        separator = "=" * 60
        print(f"\n{separator}")
        print(f'QUERY: "{question}"')
        print(separator)

        # Step 1: Retrieve
        print("\n[RETRIEVAL] Embedding query...")
        print(f"[RETRIEVAL] Searching vector store (top_k={self.top_k})...")
        results = self.store.search(question, top_k=self.top_k)
        print("[RETRIEVAL] Results:")
        for i, r in enumerate(results, 1):
            preview = r.chunk.text[:80] + "..." if len(r.chunk.text) > 80 else r.chunk.text
            print(f'  {i}. [Score: {r.score:.3f}] Source: {r.chunk.source}, Chunk {r.chunk.chunk_index}')
            print(f'     "{preview}"')

        # Step 2: Assemble context
        context = "\n\n".join(
            f"[Source: {r.chunk.source}] {r.chunk.text}" for r in results
        )
        total_tokens = sum(len(r.chunk.text.split()) for r in results)
        print(f"\n[GENERATION] Assembled prompt with {len(results)} context chunks (~{total_tokens} words)")

        # Step 3: Build the prompt (what would be sent to an LLM)
        prompt = self._build_prompt(question, context)
        print("[GENERATION] Prompt sent to LLM:")
        print("  " + "-" * 56)
        for line in prompt.split("\n"):
            print(f"  {line}")
        print("  " + "-" * 56)

        # Step 4: Generate response (template-based since no LLM API)
        response = self._generate_response(question, results)
        print(f"\n[RESPONSE] {response}")
        return response

    def _build_prompt(self, question: str, context: str) -> str:
        """Construct the prompt that would be sent to an LLM."""
        return (
            "Answer the question based ONLY on the following context.\n"
            "If the context doesn't contain enough information, say so.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

    def _generate_response(self, question: str, results: list[RetrievalResult]) -> str:
        """Generate a response from retrieved chunks (template-based demo)."""
        if not results:
            return "I couldn't find any relevant information to answer your question."
        # Simulate a grounded response by summarizing top chunks
        top = results[0]
        source_info = f"(source: {top.chunk.source}, relevance: {top.score:.1%})"
        return (
            f"Based on the retrieved context {source_info}: "
            f"{top.chunk.text[:200]}..."
            "\n\n         [In production, an LLM would synthesize a natural answer from all retrieved chunks]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main Demo
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the RAG chatbot demo with sample queries."""
    print("=" * 60)
    print("       RAG CHATBOT - Retrieval Augmented Generation")
    print("=" * 60)

    # Initialize and ingest
    chatbot = RAGChatbot(chunk_size=200, overlap=50, top_k=3)
    chatbot.ingest_documents(SAMPLE_DOCUMENTS)

    # Sample queries demonstrating different retrieval scenarios
    queries = [
        "How does photosynthesis work?",
        "What is overfitting in machine learning?",
        "Which planet is the largest in our solar system?",
        "What are Python's popular frameworks?",
        "What causes climate change?",
        "How do neural networks relate to deep learning?",
    ]

    for q in queries:
        chatbot.query(q)

    print("\n" + "=" * 60)
    print("Demo complete! In production, replace _generate_response()")
    print("with an actual LLM API call (OpenAI, Anthropic, local model).")
    print("=" * 60)


if __name__ == "__main__":
    main()
