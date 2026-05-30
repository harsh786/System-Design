"""
LlamaIndex Agent Implementation
================================

Demonstrates:
- Data-aware agent with vector index
- Query engine tools
- Custom tool creation
- ReAct agent with retrieval
- Sub-question query engine
- Router query engine
- Agent with memory
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from llama_index.core import (
    Document,
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    SummaryIndex,
    KeywordTableIndex,
    load_index_from_storage,
)
from llama_index.core.agent import ReActAgent
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.indices.struct_store import SQLTableRetrieverQueryEngine
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.query_engine import (
    RouterQueryEngine,
    SubQuestionQueryEngine,
)
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.tools import (
    FunctionTool,
    QueryEngineTool,
    ToolMetadata,
)
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding


# =============================================================================
# 1. SETUP & CONFIGURATION
# =============================================================================

def setup_llama_index():
    """Configure LlamaIndex global settings."""
    Settings.llm = OpenAI(model="gpt-4o", temperature=0)
    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
    Settings.num_output = 512
    Settings.context_window = 128000


# =============================================================================
# 2. DATA INDEXING - Creating Knowledge Bases
# =============================================================================

def create_sample_documents() -> list[Document]:
    """Create sample documents for demonstration."""
    docs = [
        Document(
            text="""
            Company Overview: TechCorp Inc.
            Founded: 2020
            Employees: 500
            Revenue: $50M ARR
            Products: CloudDB (database service), StreamFlow (data pipeline), 
                     QueryAI (natural language to SQL)
            Key Markets: Enterprise SaaS, Financial Services, Healthcare
            Headquarters: San Francisco, CA
            """,
            metadata={"source": "company_info", "category": "overview"},
        ),
        Document(
            text="""
            CloudDB Technical Documentation:
            - Supports PostgreSQL, MySQL, and MongoDB wire protocols
            - Automatic scaling from 0 to 10,000 connections
            - Built-in connection pooling with PgBouncer
            - Point-in-time recovery up to 30 days
            - Cross-region replication with < 100ms lag
            - SOC2 Type II and HIPAA compliant
            - Pricing: $0.10/GB stored, $0.001/query, $0.05/GB transfer
            - SLA: 99.99% uptime guarantee
            - Max database size: 64TB
            - Supported regions: us-east-1, us-west-2, eu-west-1, ap-southeast-1
            """,
            metadata={"source": "technical_docs", "category": "clouddb", "product": "CloudDB"},
        ),
        Document(
            text="""
            StreamFlow Documentation:
            - Real-time data pipeline service
            - Supports Kafka, Kinesis, and custom sources
            - Built-in transformations: filter, map, aggregate, join
            - Exactly-once delivery guarantee
            - Auto-scaling based on throughput (100 to 1M events/sec)
            - Dead letter queue for failed messages
            - Schema registry integration
            - Pricing: $0.05 per million events processed
            - Latency: P99 < 50ms end-to-end
            - Connectors: 50+ pre-built (S3, Snowflake, BigQuery, etc.)
            """,
            metadata={"source": "technical_docs", "category": "streamflow", "product": "StreamFlow"},
        ),
        Document(
            text="""
            Q4 2024 Financial Report:
            - Revenue: $14.2M (up 35% QoQ)
            - CloudDB revenue: $8.1M (57% of total)
            - StreamFlow revenue: $4.3M (30% of total)
            - QueryAI revenue: $1.8M (13% of total)
            - Net retention rate: 135%
            - New enterprise customers: 23
            - Churn rate: 2.1% (down from 3.4% in Q3)
            - Operating margin: -15% (improving from -28% in Q3)
            - Cash runway: 24 months at current burn
            - Key wins: Fortune 500 bank, top 3 healthcare system
            """,
            metadata={"source": "financial_reports", "category": "q4_2024"},
        ),
        Document(
            text="""
            HR Policy: Remote Work
            - All employees eligible for full remote work
            - Core hours: 10am-3pm in employee's timezone
            - Equipment allowance: $2,500 one-time + $500/year
            - Coworking stipend: $300/month
            - Required in-person: quarterly all-hands (company covers travel)
            - Performance reviews: quarterly, outcome-based
            - PTO: Unlimited with 15-day minimum
            - Parental leave: 16 weeks paid for all parents
            """,
            metadata={"source": "hr_policies", "category": "remote_work"},
        ),
    ]
    return docs


def build_indices(documents: list[Document]) -> dict[str, Any]:
    """Build multiple index types over the documents."""
    
    # Vector index - best for semantic similarity search
    vector_index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True,
    )
    
    # Summary index - best for summarization queries
    summary_index = SummaryIndex.from_documents(documents)
    
    # Keyword index - best for exact term matching
    keyword_index = KeywordTableIndex.from_documents(documents)
    
    return {
        "vector": vector_index,
        "summary": summary_index,
        "keyword": keyword_index,
    }


# =============================================================================
# 3. QUERY ENGINE TOOLS
# =============================================================================

def create_query_engine_tools(indices: dict[str, Any]) -> list[QueryEngineTool]:
    """Create query engine tools from indices."""
    
    # Vector search tool - semantic similarity
    vector_tool = QueryEngineTool(
        query_engine=indices["vector"].as_query_engine(
            similarity_top_k=5,
            response_mode="compact",
        ),
        metadata=ToolMetadata(
            name="semantic_search",
            description=(
                "Search company documents using semantic similarity. "
                "Best for questions about products, features, pricing, "
                "and general company information. Use natural language queries."
            ),
        ),
    )
    
    # Summary tool - for broad overview questions
    summary_tool = QueryEngineTool(
        query_engine=indices["summary"].as_query_engine(
            response_mode="tree_summarize",
        ),
        metadata=ToolMetadata(
            name="document_summary",
            description=(
                "Get a comprehensive summary across all company documents. "
                "Best for broad questions like 'give me an overview' or "
                "'summarize all products' or 'what does the company do'."
            ),
        ),
    )
    
    # Keyword tool - exact match
    keyword_tool = QueryEngineTool(
        query_engine=indices["keyword"].as_query_engine(
            response_mode="compact",
        ),
        metadata=ToolMetadata(
            name="keyword_search",
            description=(
                "Search documents by exact keyword matching. "
                "Best for finding specific terms, product names, "
                "metrics, or technical specifications."
            ),
        ),
    )
    
    return [vector_tool, summary_tool, keyword_tool]


# =============================================================================
# 4. CUSTOM FUNCTION TOOLS
# =============================================================================

def calculate_pricing(
    storage_gb: float,
    queries_per_month: int,
    transfer_gb: float,
    product: str = "CloudDB",
) -> str:
    """Calculate estimated monthly cost for TechCorp products."""
    if product == "CloudDB":
        storage_cost = storage_gb * 0.10
        query_cost = queries_per_month * 0.001
        transfer_cost = transfer_gb * 0.05
        total = storage_cost + query_cost + transfer_cost
        return (
            f"CloudDB Monthly Estimate:\n"
            f"  Storage ({storage_gb}GB): ${storage_cost:.2f}\n"
            f"  Queries ({queries_per_month:,}): ${query_cost:.2f}\n"
            f"  Transfer ({transfer_gb}GB): ${transfer_cost:.2f}\n"
            f"  Total: ${total:.2f}/month"
        )
    elif product == "StreamFlow":
        events_cost = (queries_per_month / 1_000_000) * 0.05
        return f"StreamFlow Monthly Estimate: ${events_cost:.2f}/month ({queries_per_month:,} events)"
    return f"Unknown product: {product}"


def compare_products(feature: str) -> str:
    """Compare TechCorp products on a specific feature."""
    comparisons = {
        "scalability": "CloudDB: 0-10K connections | StreamFlow: 100-1M events/sec | QueryAI: 100 concurrent queries",
        "pricing": "CloudDB: usage-based | StreamFlow: per-event | QueryAI: per-query + seat license",
        "compliance": "CloudDB: SOC2+HIPAA | StreamFlow: SOC2 | QueryAI: SOC2 (HIPAA roadmap Q2)",
        "latency": "CloudDB: <5ms reads | StreamFlow: P99 <50ms | QueryAI: P50 <2s for complex queries",
    }
    return comparisons.get(feature.lower(), f"No comparison data available for '{feature}'")


def get_system_status() -> str:
    """Check current system status for all products."""
    return (
        "System Status (live):\n"
        "  CloudDB: ✅ Operational (99.99% uptime last 30d)\n"
        "  StreamFlow: ✅ Operational (P99 latency: 42ms)\n"
        "  QueryAI: ⚠️ Degraded (elevated latency in eu-west-1)\n"
        "  Status page: https://status.techcorp.example.com"
    )


# Create function tools
pricing_tool = FunctionTool.from_defaults(
    fn=calculate_pricing,
    name="pricing_calculator",
    description="Calculate estimated monthly costs for TechCorp products. Provide storage_gb, queries_per_month, transfer_gb, and product name.",
)

comparison_tool = FunctionTool.from_defaults(
    fn=compare_products,
    name="product_comparison",
    description="Compare TechCorp products on specific features like scalability, pricing, compliance, or latency.",
)

status_tool = FunctionTool.from_defaults(
    fn=get_system_status,
    name="system_status",
    description="Check the current operational status of all TechCorp products.",
)


# =============================================================================
# 5. ReAct AGENT WITH RETRIEVAL
# =============================================================================

def create_react_agent(indices: dict[str, Any]) -> ReActAgent:
    """
    Create a ReAct agent that can reason over data and use tools.
    
    ReAct pattern: Reason → Act → Observe → Reason → ...
    The agent explicitly reasons about which tool to use and why.
    """
    query_tools = create_query_engine_tools(indices)
    
    all_tools = query_tools + [pricing_tool, comparison_tool, status_tool]
    
    # Create agent with memory
    memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
    
    agent = ReActAgent.from_tools(
        tools=all_tools,
        llm=OpenAI(model="gpt-4o", temperature=0),
        memory=memory,
        verbose=True,  # Shows reasoning steps
        max_iterations=10,
        system_prompt="""You are a knowledgeable assistant for TechCorp Inc.
        
You help customers and internal stakeholders with:
- Product information and technical details
- Pricing estimates and comparisons
- Company information and financials
- HR policies and procedures

Always cite specific documents when providing information.
If you're unsure, say so rather than making things up.
Use the pricing calculator for cost estimates rather than computing manually.
Check system status if asked about current availability.""",
    )
    
    return agent


# =============================================================================
# 6. SUB-QUESTION QUERY ENGINE
# =============================================================================

def create_sub_question_engine(indices: dict[str, Any]) -> SubQuestionQueryEngine:
    """
    Create a sub-question query engine that decomposes complex questions
    into simpler sub-questions, queries different sources, and synthesizes.
    
    Example: "How does CloudDB pricing compare to its performance guarantees?"
    → Sub-Q1: "What is CloudDB pricing?" (query financial docs)
    → Sub-Q2: "What are CloudDB performance guarantees?" (query technical docs)
    → Synthesize both answers
    """
    query_tools = create_query_engine_tools(indices)
    
    sub_question_engine = SubQuestionQueryEngine.from_defaults(
        query_engine_tools=query_tools,
        llm=OpenAI(model="gpt-4o", temperature=0),
        verbose=True,
    )
    
    return sub_question_engine


# =============================================================================
# 7. ROUTER QUERY ENGINE
# =============================================================================

def create_router_engine(indices: dict[str, Any]) -> RouterQueryEngine:
    """
    Create a router that intelligently selects the best query engine
    based on the question type.
    
    - Factual/specific → Vector search
    - Broad/overview → Summary
    - Exact terms → Keyword
    """
    query_tools = create_query_engine_tools(indices)
    
    router_engine = RouterQueryEngine(
        selector=LLMSingleSelector.from_defaults(
            llm=OpenAI(model="gpt-4o-mini", temperature=0),
        ),
        query_engine_tools=query_tools,
        verbose=True,
    )
    
    return router_engine


# =============================================================================
# 8. AGENT WITH PERSISTENT MEMORY
# =============================================================================

class ConversationalAgent:
    """
    Agent with conversation memory that persists across interactions.
    Remembers context from previous questions in the session.
    """
    
    def __init__(self, indices: dict[str, Any]):
        self.indices = indices
        self.memory = ChatMemoryBuffer.from_defaults(token_limit=8192)
        self.agent = self._build_agent()
        self.conversation_history: list[dict] = []
    
    def _build_agent(self) -> ReActAgent:
        query_tools = create_query_engine_tools(self.indices)
        all_tools = query_tools + [pricing_tool, comparison_tool, status_tool]
        
        return ReActAgent.from_tools(
            tools=all_tools,
            llm=OpenAI(model="gpt-4o", temperature=0),
            memory=self.memory,
            verbose=True,
            max_iterations=10,
            system_prompt="""You are a helpful assistant for TechCorp Inc.
You have access to company documents and tools.
Remember context from our conversation - refer back to previous questions when relevant.
Be concise but thorough.""",
        )
    
    def chat(self, message: str) -> str:
        """Send a message and get a response (with memory)."""
        response = self.agent.chat(message)
        
        self.conversation_history.append({
            "role": "user",
            "content": message,
        })
        self.conversation_history.append({
            "role": "assistant", 
            "content": str(response),
        })
        
        return str(response)
    
    async def achat(self, message: str) -> str:
        """Async version of chat."""
        response = await self.agent.achat(message)
        
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": str(response)})
        
        return str(response)
    
    def reset(self):
        """Reset conversation memory."""
        self.memory.reset()
        self.conversation_history = []
        self.agent = self._build_agent()
    
    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return self.conversation_history


# =============================================================================
# 9. MULTI-INDEX AGENT (Different data sources)
# =============================================================================

class MultiSourceAgent:
    """
    Agent that queries multiple data sources with different strategies.
    
    - Technical docs → Vector search (semantic)
    - Financial data → Keyword search (exact numbers)
    - HR policies → Summary (broad context needed)
    - Live data → Function tools (API calls)
    """
    
    def __init__(self):
        self.documents = create_sample_documents()
        self.indices = self._build_specialized_indices()
        self.agent = self._build_agent()
    
    def _build_specialized_indices(self) -> dict[str, Any]:
        """Build specialized indices for different document types."""
        # Split documents by category
        tech_docs = [d for d in self.documents if d.metadata.get("category") in ("clouddb", "streamflow")]
        financial_docs = [d for d in self.documents if d.metadata.get("category") == "q4_2024"]
        hr_docs = [d for d in self.documents if d.metadata.get("category") == "remote_work"]
        overview_docs = [d for d in self.documents if d.metadata.get("category") == "overview"]
        
        indices = {}
        if tech_docs:
            indices["technical"] = VectorStoreIndex.from_documents(tech_docs)
        if financial_docs:
            indices["financial"] = VectorStoreIndex.from_documents(financial_docs)
        if hr_docs:
            indices["hr"] = VectorStoreIndex.from_documents(hr_docs)
        if overview_docs:
            indices["overview"] = VectorStoreIndex.from_documents(overview_docs)
        
        return indices
    
    def _build_agent(self) -> ReActAgent:
        tools = []
        
        for name, index in self.indices.items():
            tools.append(QueryEngineTool(
                query_engine=index.as_query_engine(similarity_top_k=3),
                metadata=ToolMetadata(
                    name=f"search_{name}",
                    description=f"Search {name} documents. Use for questions about {name} topics.",
                ),
            ))
        
        tools.extend([pricing_tool, comparison_tool, status_tool])
        
        return ReActAgent.from_tools(
            tools=tools,
            llm=OpenAI(model="gpt-4o", temperature=0),
            verbose=True,
            max_iterations=10,
        )
    
    def query(self, question: str) -> str:
        return str(self.agent.chat(question))


# =============================================================================
# 10. OBSERVABILITY & DEBUGGING
# =============================================================================

def create_agent_with_observability(indices: dict[str, Any]) -> ReActAgent:
    """Create an agent with full observability via callbacks."""
    
    # Debug handler shows all LLM calls, tool calls, and reasoning
    debug_handler = LlamaDebugHandler(print_trace_on_end=True)
    callback_manager = CallbackManager([debug_handler])
    
    Settings.callback_manager = callback_manager
    
    query_tools = create_query_engine_tools(indices)
    
    agent = ReActAgent.from_tools(
        tools=query_tools + [pricing_tool, status_tool],
        llm=OpenAI(model="gpt-4o", temperature=0, callback_manager=callback_manager),
        verbose=True,
        max_iterations=10,
        callback_manager=callback_manager,
    )
    
    return agent, debug_handler


# =============================================================================
# 11. MAIN EXECUTION
# =============================================================================

async def main():
    """Run LlamaIndex agent examples."""
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run this example.")
        print("\nShowing architecture instead:")
        print("""
LlamaIndex Agent Architecture:
    
    User Query
        │
        ▼
    ReAct Agent (Reason → Act → Observe loop)
        │
        ├── Tool: semantic_search (VectorStoreIndex)
        │       → Embeds query → Finds similar chunks → Returns context
        │
        ├── Tool: document_summary (SummaryIndex)  
        │       → Summarizes across all documents
        │
        ├── Tool: keyword_search (KeywordTableIndex)
        │       → Exact term matching in documents
        │
        ├── Tool: pricing_calculator (FunctionTool)
        │       → Computes cost estimates
        │
        ├── Tool: product_comparison (FunctionTool)
        │       → Structured comparisons
        │
        └── Tool: system_status (FunctionTool)
                → Live system status
        """)
        return
    
    # Setup
    setup_llama_index()
    
    # Create documents and indices
    documents = create_sample_documents()
    indices = build_indices(documents)
    
    print("=" * 60)
    print("Example 1: ReAct Agent")
    print("=" * 60)
    
    agent = create_react_agent(indices)
    
    # Simple factual question
    response = agent.chat("What is CloudDB's uptime SLA?")
    print(f"\nAnswer: {response}\n")
    
    # Pricing question (uses calculator tool)
    response = agent.chat("How much would CloudDB cost for 100GB storage, 50000 queries/month, and 10GB transfer?")
    print(f"\nAnswer: {response}\n")
    
    print("=" * 60)
    print("Example 2: Sub-Question Decomposition")
    print("=" * 60)
    
    sub_q_engine = create_sub_question_engine(indices)
    response = sub_q_engine.query(
        "Compare CloudDB's pricing model with its SLA guarantees. Is it good value?"
    )
    print(f"\nAnswer: {response}\n")
    
    print("=" * 60)
    print("Example 3: Conversational Agent with Memory")
    print("=" * 60)
    
    conv_agent = ConversationalAgent(indices)
    
    # Multi-turn conversation
    print(conv_agent.chat("What products does TechCorp offer?"))
    print(conv_agent.chat("Which one has the highest revenue?"))  # Remembers context
    print(conv_agent.chat("What's the pricing for that product?"))  # Refers to previous answer
    
    print("=" * 60)
    print("Example 4: Router Query Engine")
    print("=" * 60)
    
    router = create_router_engine(indices)
    
    # This should route to vector search
    response = router.query("How does StreamFlow guarantee exactly-once delivery?")
    print(f"\nRouted answer: {response}\n")
    
    # This should route to summary
    response = router.query("Give me a high-level overview of all TechCorp products and financials")
    print(f"\nRouted answer: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
