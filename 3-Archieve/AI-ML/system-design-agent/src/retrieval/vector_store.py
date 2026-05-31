"""
Vector Store Manager - Handles embedding, indexing, and retrieval.
"""

from dataclasses import dataclass

import chromadb
from openai import AsyncOpenAI, AsyncAzureOpenAI

from src.config.settings import Settings
from src.ingestion.chunker import DocumentChunk, DocumentChunker
from src.ingestion.markdown_parser import ParsedDocument


@dataclass
class RetrievalResult:
    """A single retrieval result with content and metadata."""
    content: str
    metadata: dict
    score: float


class VectorStoreManager:
    """
    Manages the vector store for RAG retrieval.
    
    Supports:
    - ChromaDB (local, default)
    - Extensible to Pinecone, Weaviate, etc.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.chunker = DocumentChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        # Initialize OpenAI client (Azure or standard)
        if settings.llm_provider == "azure_openai":
            self.openai_client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
            self.embedding_model = settings.azure_openai_embedding_deployment
        else:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.embedding_model = settings.embedding_model

        # Initialize ChromaDB (current API)
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def index_documents(self, documents: list[ParsedDocument]):
        """
        Chunk, embed, and index a list of documents.

        Args:
            documents: List of parsed documents to index
        """
        # Step 1: Chunk documents
        chunks = self.chunker.chunk_documents(documents)
        print(f"  📄 Created {len(chunks)} chunks from {len(documents)} documents")

        # Step 2: Generate embeddings
        embeddings = await self._generate_embeddings(
            [chunk.content for chunk in chunks]
        )
        print(f"  🔢 Generated {len(embeddings)} embeddings")

        # Step 3: Upsert into vector store
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.content for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
        )
        print(f"  💾 Indexed {len(chunks)} chunks into vector store")

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        source_type_filter: str | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant document chunks for a query.

        Args:
            query: Search query
            top_k: Number of results to return
            source_type_filter: Filter by document type (hld, lld, db_design, etc.)

        Returns:
            List of RetrievalResult objects
        """
        k = top_k or self.settings.retrieval_top_k

        # Generate query embedding
        query_embedding = await self._generate_embeddings([query])

        # Build where filter
        where_filter = None
        if source_type_filter:
            where_filter = {"source_type": source_type_filter}

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=k,
            where=where_filter,
        )

        # Format results
        retrieval_results = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                retrieval_results.append(RetrievalResult(
                    content=doc,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    score=1 - results["distances"][0][i] if results["distances"] else 0,
                ))

        return retrieval_results

    async def retrieve_for_hld(self, query: str) -> str:
        """Retrieve context relevant for HLD generation."""
        results = await self.retrieve(
            query=query,
            source_type_filter="hld",
            top_k=5,
        )
        # Also get architecture docs
        arch_results = await self.retrieve(
            query=query,
            source_type_filter="architecture",
            top_k=5,
        )
        all_results = results + arch_results
        return self._format_results(all_results)

    async def retrieve_for_lld(self, query: str) -> str:
        """Retrieve context relevant for LLD generation."""
        results = await self.retrieve(
            query=query,
            source_type_filter="lld",
            top_k=5,
        )
        return self._format_results(results)

    async def retrieve_for_db_design(self, query: str) -> str:
        """Retrieve context relevant for DB design generation."""
        results = await self.retrieve(
            query=query,
            source_type_filter="db_design",
            top_k=5,
        )
        # Also get architecture docs with DB-related content
        arch_results = await self.retrieve(
            query=f"database schema index partition {query}",
            top_k=5,
        )
        all_results = results + arch_results
        return self._format_results(all_results)

    async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Azure OpenAI or standard OpenAI."""
        # Process in batches of 100
        all_embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _format_results(self, results: list[RetrievalResult]) -> str:
        """Format retrieval results into a context string."""
        if not results:
            return "No relevant existing documents found."

        context_parts = []
        for i, result in enumerate(results, 1):
            source = result.metadata.get("title", "Unknown")
            section = result.metadata.get("section", "")
            context_parts.append(
                f"--- Context #{i} (Source: {source}"
                f"{f', Section: {section}' if section else ''}) ---\n"
                f"{result.content}\n"
            )

        return "\n".join(context_parts)
