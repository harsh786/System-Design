"""
Configuration settings for the System Design Agent.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Agent configuration loaded from environment variables."""

    # LLM Settings
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "azure_openai")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    # Azure OpenAI Settings
    azure_openai_api_key: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", "")
    )
    azure_openai_endpoint: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    azure_openai_api_version: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    )
    azure_openai_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    )
    azure_openai_embedding_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    )

    # Embedding Settings
    embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-large"
        )
    )
    embedding_dimensions: int = 1536

    # Vector Store Settings
    vector_store_type: str = field(
        default_factory=lambda: os.getenv("VECTOR_STORE_TYPE", "chromadb")
    )
    chroma_persist_dir: str = field(
        default_factory=lambda: os.getenv(
            "CHROMA_PERSIST_DIR", "./.chromadb"
        )
    )
    chroma_collection_name: str = "system_designs"
    pinecone_api_key: str = field(
        default_factory=lambda: os.getenv("PINECONE_API_KEY", "")
    )
    pinecone_index_name: str = field(
        default_factory=lambda: os.getenv(
            "PINECONE_INDEX_NAME", "system-designs"
        )
    )

    # Confluence Settings
    confluence_url: str = field(
        default_factory=lambda: os.getenv("CONFLUENCE_URL", "")
    )
    confluence_token: str = field(
        default_factory=lambda: os.getenv("CONFLUENCE_TOKEN", "")
    )
    confluence_username: str = field(
        default_factory=lambda: os.getenv("CONFLUENCE_USERNAME", "")
    )

    # Chunking Settings
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Retrieval Settings
    retrieval_top_k: int = 10
    use_hybrid_search: bool = True
    use_reranker: bool = True

    # Agent Settings
    max_retries: int = 3
    review_max_iterations: int = 2
    temperature: float = 0.2  # Low temperature for consistent outputs

    # Output Settings
    generate_mermaid_diagrams: bool = True
    output_format: str = "markdown"  # markdown | confluence | notion

    def create_llm(self, max_tokens: int = 4096, temperature: float | None = None):
        """
        Factory method to create the appropriate LLM client.
        Returns AzureChatOpenAI or ChatOpenAI based on llm_provider setting.
        """
        temp = temperature if temperature is not None else self.temperature

        if self.llm_provider == "azure_openai":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=self.azure_openai_deployment,
                azure_endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_api_key,
                api_version=self.azure_openai_api_version,
                temperature=temp,
                max_tokens=max_tokens,
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.llm_model,
                temperature=temp,
                api_key=self.openai_api_key,
                max_tokens=max_tokens,
            )
