# Autonomous System Design Agent

## Overview
An AI-powered autonomous agent that takes PRD documents from Confluence and existing system designs (HLD/LLD/DB schemas) as input, and generates comprehensive system design documents including HLD, LLD, and Database Design.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTONOMOUS DESIGN AGENT                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  INPUT LAYER                                                        │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ Confluence API  │  │ Existing HLD/LLD│  │ Existing DB Schemas │  │
│  │ (PRD Docs)      │  │ (Markdown Files)│  │ (DDL/ERDs)          │  │
│  └───────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│          │                    │                       │             │
│          ▼                    ▼                       ▼             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              DOCUMENT PROCESSING PIPELINE                    │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │   │
│  │  │ Chunking │─▶│  Embedding   │─▶│  Vector Store          │ │   │
│  │  │ Engine   │  │  (OpenAI/    │  │  (ChromaDB/Pinecone/  │ │   │
│  │  │          │  │   Cohere)    │  │   Weaviate)            │ │   │
│  │  └──────────┘  └──────────────┘  └───────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              MULTI-AGENT ORCHESTRATOR (LangGraph)            │   │
│  │                                                              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │   │
│  │  │ PRD      │─▶│ HLD      │─▶│ LLD      │─▶│ DB Design  │ │   │
│  │  │ Analyzer │  │ Generator│  │ Generator│  │ Generator  │ │   │
│  │  │ Agent    │  │ Agent    │  │ Agent    │  │ Agent      │ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │   │
│  │       │              │             │              │         │   │
│  │       └──────────────┴─────────────┴──────────────┘         │   │
│  │                              │                               │   │
│  │                              ▼                               │   │
│  │                     ┌──────────────┐                        │   │
│  │                     │   REVIEW     │                        │   │
│  │                     │   AGENT      │                        │   │
│  │                     └──────────────┘                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  OUTPUT LAYER                                                       │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ HLD Document   │  │ LLD Document    │  │ DB Design Document  │  │
│  │ (Markdown)     │  │ (Markdown)      │  │ (Markdown + DDL)    │  │
│  └────────────────┘  └─────────────────┘  └─────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Design

### 1. Document Ingestion Layer

#### 1.1 Confluence Reader
```
Purpose: Fetch PRD documents from Confluence
API: Confluence REST API v2
Auth: OAuth 2.0 / API Token

Flow:
  1. Accept Confluence page URL or Space+Page ID
  2. Fetch page content via REST API (HTML/Storage format)
  3. Convert HTML to clean text/markdown
  4. Extract:
     - Requirements (functional + non-functional)
     - User stories
     - Acceptance criteria
     - Data entities mentioned
     - Integration points
     - Scale/performance requirements
```

#### 1.2 Existing Design Parser
```
Purpose: Parse existing HLD/LLD markdown files from workspace
Supported formats: Markdown, PlantUML, Mermaid, JSON schemas

Flow:
  1. Scan workspace directories (HLD/, LLD/, System-Design/)
  2. Parse markdown files extracting:
     - Architecture patterns used
     - Technology choices
     - Component interactions
     - API contracts
     - Data flow diagrams
  3. Build a knowledge graph of existing system
```

#### 1.3 Schema Parser
```
Purpose: Extract existing database schemas
Sources: DDL files, ER diagrams, ORM models, schema docs

Extracts:
  - Table definitions
  - Column types and constraints
  - Indexes (types and strategies)
  - Relationships (FK, joins)
  - Partitioning strategies
  - Existing query patterns
```

---

### 2. RAG (Retrieval-Augmented Generation) Pipeline

#### 2.1 Chunking Strategy
```
Document Type    │ Chunk Strategy         │ Chunk Size │ Overlap
─────────────────┼────────────────────────┼────────────┼────────
PRD              │ Section-based          │ 1000 tokens│ 200
HLD              │ Component-based        │ 800 tokens │ 150
LLD              │ Module-based           │ 600 tokens │ 100
DB Schema        │ Table-based            │ 500 tokens │ 50
API Docs         │ Endpoint-based         │ 400 tokens │ 100
```

#### 2.2 Embedding & Vector Store
```
Embedding Model: text-embedding-3-large (OpenAI) or Cohere embed-v3
Vector Store: ChromaDB (local) / Pinecone (production)
Metadata stored with each chunk:
  - source_type: prd | hld | lld | schema | api
  - component_name: name of system component
  - technology: relevant tech stack
  - domain: business domain
```

#### 2.3 Retrieval Strategy
```
Hybrid Search:
  1. Dense retrieval (vector similarity) - top 20
  2. Sparse retrieval (BM25 keyword) - top 20
  3. Re-rank using cross-encoder - final top 10
  4. Metadata filtering by source_type for each agent
```

---

### 3. Multi-Agent Orchestrator (LangGraph)

#### 3.1 Agent Definitions

##### PRD Analyzer Agent
```
Role: Extract structured requirements from PRD
Input: Raw PRD document
Output: Structured requirements JSON

Extracts:
  - Functional requirements (with priority)
  - Non-functional requirements (scale, latency, availability)
  - Data entities and relationships
  - External integrations
  - User flows
  - Success metrics / SLAs
```

##### HLD Generator Agent
```
Role: Generate High-Level Design
Input: Structured requirements + existing HLD context
Output: HLD Markdown document

Generates:
  - System context diagram
  - Component architecture (Mermaid diagram)
  - Technology choices with justification
  - Data flow between components
  - Integration patterns (sync/async)
  - Scalability approach
  - Availability & fault tolerance design
  - Security considerations
  - Cost estimation
```

##### LLD Generator Agent
```
Role: Generate Low-Level Design for each component
Input: HLD output + existing LLD context + requirements
Output: LLD Markdown documents (per component)

Generates:
  - Class/module diagrams
  - Sequence diagrams for key flows
  - API contracts (OpenAPI spec)
  - Error handling strategy
  - Retry/circuit breaker patterns
  - Caching strategy
  - Configuration management
  - Logging & monitoring approach
```

##### DB Design Generator Agent
```
Role: Generate database schema and optimization strategy
Input: Data entities from PRD + existing schemas + tech choices from HLD
Output: DB Design document with DDL

Generates:
  - Entity-Relationship diagram
  - Table schemas with types
  - Index strategy (based on query patterns)
  - Partitioning strategy
  - Replication topology
  - Migration plan from existing schema
  - Query optimization notes
  - Capacity planning
```

##### Review Agent
```
Role: Cross-validate all designs against PRD requirements
Input: All generated documents + original PRD
Output: Review report with gaps/issues

Checks:
  - All functional requirements addressed
  - NFRs met by architecture
  - Consistency between HLD ↔ LLD ↔ DB Design
  - No orphaned components
  - Security requirements covered
  - Scalability targets achievable
```

#### 3.2 Agent Orchestration (LangGraph State Machine)

```
                    ┌──────────────┐
                    │    START     │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Ingest &    │
                    │  Index Docs  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  PRD         │
                    │  Analyzer    │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │  Requirements│
                    │  Validated?  │
                    └──┬───────┬───┘
                   No  │       │ Yes
                       ▼       ▼
              ┌──────────┐  ┌──────────────┐
              │ Ask User │  │  HLD         │
              │ Clarify  │  │  Generator   │
              └──────────┘  └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │  LLD         │
                            │  Generator   │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │  DB Design   │
                            │  Generator   │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │  Review      │
                            │  Agent       │
                            └──────┬───────┘
                                   │
                            ┌──────┴───────┐
                            │  All checks  │
                            │  passed?     │
                            └──┬───────┬───┘
                           No  │       │ Yes
                               ▼       ▼
                      ┌──────────┐  ┌──────────────┐
                      │ Re-route │  │  Generate     │
                      │ to Agent │  │  Final Docs   │
                      └──────────┘  └──────────────┘
```

---

### 4. Prompt Engineering Templates

#### 4.1 PRD Analyzer Prompt
```
You are an expert system architect analyzing a Product Requirements Document.

CONTEXT:
- Existing system designs: {retrieved_hld_context}
- Technology stack in use: {tech_stack}

PRD DOCUMENT:
{prd_content}

TASK:
Extract and structure the following:
1. Functional Requirements (list with priority: P0/P1/P2)
2. Non-Functional Requirements:
   - Expected QPS / TPS
   - Latency requirements (p50, p95, p99)
   - Availability target (e.g., 99.9%)
   - Data retention period
   - Data volume estimates
3. Data Entities (name, attributes, relationships)
4. External System Integrations
5. Key User Flows (step by step)
6. Constraints and Assumptions

OUTPUT FORMAT: JSON
```

#### 4.2 HLD Generator Prompt
```
You are a senior system architect generating a High-Level Design document.

CONTEXT:
- Structured Requirements: {requirements_json}
- Existing HLD documents: {retrieved_hld_docs}
- Existing technology choices: {tech_context}
- Organization's tech radar: {tech_radar}

TASK:
Generate a comprehensive HLD document in Markdown format including:

1. **Executive Summary** - One paragraph overview
2. **System Context Diagram** (Mermaid)
3. **Architecture Overview**
   - Architecture pattern chosen (microservices/event-driven/etc.) with justification
   - Component list with responsibilities
4. **Component Architecture Diagram** (Mermaid)
5. **Technology Choices**
   | Component | Technology | Justification |
6. **Data Flow**
   - Write path
   - Read path  
   - Async processing path
7. **Integration Design**
   - Sync APIs
   - Async messaging (Kafka/SQS/etc.)
8. **Scalability Design**
   - Horizontal scaling strategy
   - Caching layers
   - Database scaling (sharding/replication)
9. **Availability & Resilience**
   - Failure modes and mitigation
   - DR strategy
10. **Security Design**
11. **Monitoring & Observability**
12. **Cost Estimation**

STYLE: Match the format of existing HLD documents in the organization.
```

#### 4.3 LLD Generator Prompt
```
You are a senior software engineer generating a Low-Level Design document.

CONTEXT:
- HLD Document: {hld_document}
- Component to design: {component_name}
- Existing LLD documents: {retrieved_lld_docs}
- API contracts of dependent services: {api_contracts}

TASK:
Generate a detailed LLD for the {component_name} component:

1. **Module Overview**
2. **Class Diagram** (Mermaid)
3. **Key Sequence Diagrams** (Mermaid) for:
   - Happy path
   - Error scenarios
4. **API Design** (OpenAPI-style)
   - Endpoints
   - Request/Response schemas
   - Error codes
5. **Data Models** (internal)
6. **Algorithm/Logic** for complex operations
7. **Error Handling Strategy**
8. **Caching Strategy**
   - What to cache
   - TTL
   - Invalidation
9. **Configuration**
10. **Dependencies** (libraries, services)
11. **Testing Strategy**
```

#### 4.4 DB Design Generator Prompt
```
You are a database architect generating a database design document.

CONTEXT:
- Data entities from PRD: {data_entities}
- Query patterns from HLD/LLD: {query_patterns}
- Scale requirements: {scale_requirements}
- Existing database schemas: {existing_schemas}
- Database technology chosen: {db_technology}

TASK:
Generate a comprehensive database design:

1. **ER Diagram** (Mermaid)
2. **Table Schemas**
   - Column definitions with types
   - Primary keys
   - Foreign keys
   - Constraints
3. **Index Strategy**
   - Primary indexes
   - Secondary indexes
   - Composite indexes
   - Covering indexes
   - Index type justification (B-tree, Hash, Inverted, etc.)
4. **Partitioning Strategy**
   - Partition key selection
   - Partition scheme (range/hash/list)
5. **Query Optimization**
   - Key queries with EXPLAIN plans
   - Denormalization decisions
6. **Data Migration Plan**
   - From existing schema
   - Zero-downtime migration steps
7. **Capacity Planning**
   - Storage estimates
   - IOPS estimates
   - Connection pool sizing
8. **Backup & Recovery**
9. **DDL Scripts**
```

---

### 5. Technology Stack for the Agent

```
Component              │ Technology                  │ Purpose
───────────────────────┼─────────────────────────────┼──────────────────────
Agent Framework        │ LangGraph / CrewAI          │ Multi-agent orchestration
LLM                    │ GPT-4o / Claude 3.5         │ Generation engine
Embedding              │ text-embedding-3-large      │ Document embeddings
Vector Store           │ ChromaDB / Pinecone         │ Similarity search
Document Loader        │ LangChain + Confluence API  │ Document ingestion
Diagram Generation     │ Mermaid.js                  │ Architecture diagrams
Output Format          │ Markdown + Mermaid          │ Design documents
MCP Server             │ Custom MCP Server           │ VS Code integration
API Layer              │ FastAPI                     │ REST API for agent
State Management       │ LangGraph State             │ Agent workflow state
Caching                │ Redis                       │ LLM response caching
Observability          │ LangSmith / Phoenix         │ Agent tracing
```

---

### 6. Implementation Plan

#### Phase 1: Foundation (Week 1-2)
- [ ] Set up project structure
- [ ] Implement Confluence document reader
- [ ] Implement local markdown file reader
- [ ] Set up ChromaDB vector store
- [ ] Build document chunking pipeline
- [ ] Basic embedding and retrieval

#### Phase 2: Core Agents (Week 3-4)
- [ ] Implement PRD Analyzer Agent
- [ ] Implement HLD Generator Agent
- [ ] Implement LLD Generator Agent
- [ ] Implement DB Design Generator Agent
- [ ] Set up LangGraph workflow

#### Phase 3: Review & Quality (Week 5-6)
- [ ] Implement Review Agent
- [ ] Add feedback loops
- [ ] Cross-validation between documents
- [ ] Human-in-the-loop approval gates

#### Phase 4: Integration & Polish (Week 7-8)
- [ ] Build MCP Server for VS Code integration
- [ ] Add Mermaid diagram generation
- [ ] Output formatting and templates
- [ ] End-to-end testing
- [ ] Documentation

---

## Sample Project Structure

```
system-design-agent/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── prd_analyzer.py          # PRD extraction agent
│   │   ├── hld_generator.py         # HLD generation agent
│   │   ├── lld_generator.py         # LLD generation agent
│   │   ├── db_design_generator.py   # DB design agent
│   │   └── review_agent.py          # Review/validation agent
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── confluence_reader.py     # Confluence API integration
│   │   ├── markdown_parser.py       # Local MD file parser
│   │   ├── schema_parser.py         # DB schema parser
│   │   └── chunker.py               # Document chunking
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── embeddings.py            # Embedding generation
│   │   ├── vector_store.py          # ChromaDB/Pinecone wrapper
│   │   └── hybrid_search.py         # Hybrid retrieval
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── graph.py                 # LangGraph workflow
│   │   ├── state.py                 # Agent state definitions
│   │   └── router.py                # Conditional routing
│   ├── output/
│   │   ├── __init__.py
│   │   ├── markdown_renderer.py     # MD document generator
│   │   ├── diagram_generator.py     # Mermaid diagram generator
│   │   └── templates/               # Document templates
│   │       ├── hld_template.md
│   │       ├── lld_template.md
│   │       └── db_design_template.md
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   └── server.py                # MCP Server for VS Code
│   ├── config/
│   │   ├── settings.py              # Configuration
│   │   └── prompts.py               # Prompt templates
│   └── main.py                      # Entry point
├── tests/
│   ├── test_agents/
│   ├── test_ingestion/
│   └── test_retrieval/
├── docs/
│   └── architecture.md
├── pyproject.toml
├── Dockerfile
└── README.md
```

---

## Key Design Decisions

### Why Multi-Agent over Single Agent?
| Aspect           | Single Agent              | Multi-Agent (Chosen)         |
|------------------|---------------------------|------------------------------|
| Context Window   | Easily exceeds limits     | Each agent has focused context|
| Quality          | Diluted attention         | Specialized expertise         |
| Debugging        | Hard to trace issues      | Clear agent boundaries        |
| Iteration        | Regenerate everything     | Re-run specific agent         |
| Parallelism      | Sequential only           | HLD→LLD can run per component|

### Why LangGraph over CrewAI?
| Aspect           | CrewAI                    | LangGraph (Chosen)           |
|------------------|---------------------------|------------------------------|
| Control Flow     | Limited                   | Full state machine control    |
| Conditional Logic| Basic                     | Complex branching/loops       |
| State Management | Implicit                  | Explicit typed state          |
| Human-in-loop    | Limited                   | Native support                |
| Debugging        | Black box                 | Full trace visibility         |

### Why Hybrid Search (Dense + Sparse)?
- **Dense search** catches semantic similarity (e.g., "order processing" matches "transaction handling")
- **Sparse search** catches exact technical terms (e.g., "Kafka", "gRPC", specific table names)
- **Cross-encoder re-ranking** combines both for best results

---

## Integration with Existing Workspace

This agent can be integrated with your existing workspace structure:

```
learning-conv/
├── HLD/              ← Agent reads existing HLDs as context
├── LLD/              ← Agent reads existing LLDs as context
├── System-Design/    ← Agent reads existing designs (Pinot, Kafka, etc.)
│   ├── Pinot/        ← Existing Pinot architecture docs
│   ├── Kafka/        ← Existing Kafka design docs
│   └── ...
└── generated-designs/  ← Agent outputs new designs here
    ├── feature-x/
    │   ├── HLD.md
    │   ├── LLD/
    │   │   ├── service-a.md
    │   │   └── service-b.md
    │   └── DB_DESIGN.md
    └── feature-y/
        └── ...
```

---

## MCP Server Integration (VS Code)

The agent can be exposed as an MCP (Model Context Protocol) server, allowing direct interaction from VS Code / GitHub Copilot:

### MCP Tools Exposed:
1. `generate_system_design` - Full pipeline from PRD URL
2. `generate_hld` - Generate only HLD
3. `generate_lld` - Generate only LLD for a component
4. `generate_db_design` - Generate only DB design
5. `review_design` - Review existing design against PRD
6. `index_documents` - Index new documents into vector store

### MCP Resources Exposed:
1. `design://templates/hld` - HLD template
2. `design://templates/lld` - LLD template
3. `design://context/{component}` - Existing design context

---

## Cost & Performance Estimates

| Metric                    | Estimate                              |
|---------------------------|---------------------------------------|
| PRD Analysis              | ~30s, ~5K tokens                      |
| HLD Generation            | ~60s, ~15K tokens                     |
| LLD Generation (per comp) | ~45s, ~10K tokens                     |
| DB Design Generation      | ~45s, ~10K tokens                     |
| Review                    | ~30s, ~8K tokens                      |
| **Total (5 components)**  | **~6-8 min, ~80K tokens (~$0.40)**    |
| Embedding (1000 docs)     | ~2 min, ~$0.02                        |
| Vector Store (ChromaDB)   | Free (local)                          |

---

## Getting Started

```bash
# Clone and setup
pip install langchain langgraph chromadb openai atlassian-python-api

# Set environment variables
export OPENAI_API_KEY="your-key"
export CONFLUENCE_URL="https://your-org.atlassian.net"
export CONFLUENCE_TOKEN="your-token"

# Run the agent
python -m system_design_agent \
  --prd-url "https://confluence.example.com/wiki/spaces/ENG/pages/123456" \
  --context-dir "./System-Design" \
  --output-dir "./generated-designs/feature-x"
```
