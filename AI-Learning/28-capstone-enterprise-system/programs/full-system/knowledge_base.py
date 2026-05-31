"""
Knowledge Base module.
Sample documents about NovaTech (fictional company), loaded into ChromaDB.
"""

import chromadb

# --- Sample Documents about NovaTech ---
DOCUMENTS = [
    {
        "id": "doc_company_overview",
        "text": (
            "NovaTech Inc. is a technology company founded in 2019, headquartered in Austin, Texas. "
            "The company specializes in enterprise AI solutions, with 450 employees across 3 offices. "
            "CEO: Sarah Chen. CTO: Marcus Williams. The company went public in 2023."
        ),
        "metadata": {"topic": "company", "category": "overview"},
    },
    {
        "id": "doc_products",
        "text": (
            "NovaTech's main products: (1) NovaAssist - AI-powered customer service platform, "
            "(2) NovaAnalytics - Business intelligence with natural language queries, "
            "(3) NovaGuard - AI security monitoring system. NovaAssist is the flagship product "
            "with 200+ enterprise customers."
        ),
        "metadata": {"topic": "products", "category": "overview"},
    },
    {
        "id": "doc_financial_q1",
        "text": (
            "NovaTech Q1 2024 Financial Results: Revenue $3.1M (up 12% YoY). "
            "Operating expenses: $2.8M. Net income: $0.3M. "
            "NovaAssist revenue: $1.8M. NovaAnalytics: $0.9M. NovaGuard: $0.4M. "
            "Customer count grew to 180 enterprise customers."
        ),
        "metadata": {"topic": "financials", "category": "q1_2024"},
    },
    {
        "id": "doc_financial_q2",
        "text": (
            "NovaTech Q2 2024 Financial Results: Revenue $3.6M (up 16% QoQ). "
            "Operating expenses: $3.0M. Net income: $0.6M. "
            "NovaAssist revenue: $2.1M. NovaAnalytics: $1.0M. NovaGuard: $0.5M. "
            "New product launch: NovaGuard Enterprise tier."
        ),
        "metadata": {"topic": "financials", "category": "q2_2024"},
    },
    {
        "id": "doc_financial_q3",
        "text": (
            "NovaTech Q3 2024 Financial Results: Revenue $4.2M (up 17% QoQ, up 35% YoY). "
            "Operating expenses: $3.2M. Net income: $1.0M. "
            "NovaAssist revenue: $2.4M. NovaAnalytics: $1.2M. NovaGuard: $0.6M. "
            "Record quarter driven by enterprise expansion. Customer count: 220."
        ),
        "metadata": {"topic": "financials", "category": "q3_2024"},
    },
    {
        "id": "doc_engineering_team",
        "text": (
            "NovaTech Engineering: 180 engineers organized into 12 teams. "
            "Platform team (25 people): infrastructure and developer tools. "
            "AI/ML team (40 people): model development and ML ops. "
            "Product teams (115 people): NovaAssist, NovaAnalytics, NovaGuard. "
            "Tech stack: Python, TypeScript, Kubernetes, PostgreSQL, Redis."
        ),
        "metadata": {"topic": "engineering", "category": "team"},
    },
    {
        "id": "doc_roadmap",
        "text": (
            "NovaTech 2025 Product Roadmap: "
            "Q1: NovaAssist v3.0 with multi-modal support (voice + text + image). "
            "Q2: NovaAnalytics real-time streaming analytics. "
            "Q3: NovaGuard autonomous threat response. "
            "Q4: New product launch - NovaDev (AI coding assistant for enterprises). "
            "Investment focus: $5M in R&D for foundation model fine-tuning."
        ),
        "metadata": {"topic": "roadmap", "category": "2025"},
    },
    {
        "id": "doc_policies_remote",
        "text": (
            "NovaTech Remote Work Policy: Hybrid model - 2 days in office minimum. "
            "Offices: Austin (HQ), San Francisco, New York. "
            "Remote exceptions granted for senior engineers (L5+). "
            "Home office stipend: $2,000/year. Internet reimbursement: $100/month."
        ),
        "metadata": {"topic": "policies", "category": "remote_work"},
    },
    {
        "id": "doc_policies_ai_usage",
        "text": (
            "NovaTech AI Usage Policy: All AI-generated code must be reviewed by a human. "
            "Customer data must never be sent to external AI services. "
            "Internal AI tools must use NovaTech's own AI gateway. "
            "Model outputs must include confidence scores. "
            "Quarterly AI ethics review by the AI Safety Board."
        ),
        "metadata": {"topic": "policies", "category": "ai_usage"},
    },
    {
        "id": "doc_culture",
        "text": (
            "NovaTech Culture and Values: (1) Customer obsession - every decision starts with "
            "the customer. (2) Technical excellence - we ship quality. (3) Transparency - open "
            "communication, shared metrics. (4) Responsible AI - we build AI we'd trust with "
            "our own data. Employee satisfaction score: 4.3/5.0 (2024 survey)."
        ),
        "metadata": {"topic": "culture", "category": "values"},
    },
]


class KnowledgeBase:
    """Manages the vector knowledge base using ChromaDB."""

    def __init__(self):
        self.client = chromadb.Client()  # In-memory
        self.collection = self.client.create_collection(
            name="novatech_kb",
            metadata={"description": "NovaTech company knowledge base"},
        )
        self._load_documents()
        print(f"[KB] Knowledge base initialized with {len(DOCUMENTS)} documents")

    def _load_documents(self):
        """Load sample documents into ChromaDB."""
        self.collection.add(
            ids=[doc["id"] for doc in DOCUMENTS],
            documents=[doc["text"] for doc in DOCUMENTS],
            metadatas=[doc["metadata"] for doc in DOCUMENTS],
        )

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search knowledge base. Returns list of {text, metadata, score}."""
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, len(DOCUMENTS)),
        )

        documents = []
        for i in range(len(results["ids"][0])):
            doc = {
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0),
            }
            documents.append(doc)

        print(f"[KB] Search for '{query[:50]}...' returned {len(documents)} results")
        return documents

    def get_document(self, doc_id: str) -> dict:
        """Get a specific document by ID."""
        result = self.collection.get(ids=[doc_id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "text": result["documents"][0],
                "metadata": result["metadatas"][0],
            }
        return {}


# Global instance (initialized on import)
knowledge_base = KnowledgeBase()
