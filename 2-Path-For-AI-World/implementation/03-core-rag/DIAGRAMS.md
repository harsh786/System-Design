# RAG System Diagrams

## 1. End-to-End RAG Pipeline Flow

```mermaid
flowchart TD
    A[User Query] --> B[Query Classification]
    B -->|Conversational| C[Direct Response]
    B -->|Factual/Analytical/Procedural| D[Query Rewriting]
    
    D --> E[Hybrid Retrieval]
    
    E --> F[Dense Search<br/>Embedding → Vector DB]
    E --> G[Sparse Search<br/>BM25 Index]
    
    F --> H[Score Fusion<br/>RRF / Weighted]
    G --> H
    
    H --> I[Reranking<br/>Cross-Encoder]
    I --> J[Context Assembly<br/>Token Budget Management]
    
    J --> K[LLM Generation<br/>Grounded Answer + Citations]
    K --> L[Groundedness Verification]
    
    L -->|Grounded| M[Format Response]
    L -->|Not Grounded| N[Flag Low Confidence]
    N --> M
    
    M --> O[Final Response<br/>Answer + Citations + Metadata]
    
    style A fill:#e1f5fe
    style O fill:#c8e6c9
    style L fill:#fff3e0
```

## 2. Chunking Strategy Comparison

```mermaid
flowchart TD
    A[Raw Document] --> B{Document Type?}
    
    B -->|Simple prose| C[Sentence Chunking]
    B -->|Structured with headings| D[Section-Aware Chunking]
    B -->|Technical with tables| E[Table-Aware Chunking]
    B -->|Mixed/Unknown| F[Recursive Character Splitting]
    
    C --> G{Chunk too large?}
    D --> G
    E --> G
    F --> G
    
    G -->|Yes| H[Sub-chunk with fallback strategy]
    G -->|No| I{Quality validation}
    H --> I
    
    I -->|Pass| J[Enrich Metadata]
    I -->|Fail: too short| K[Merge with adjacent]
    I -->|Fail: too long| L[Split further]
    I -->|Fail: low quality| M[Discard]
    
    K --> J
    L --> J
    
    J --> N[Embed & Store]
    
    subgraph "Advanced Strategies"
        O[Parent-Child] --> P[Small children for search<br/>Large parents for context]
        Q[Semantic] --> R[Split where meaning shifts<br/>Using embedding similarity]
    end
    
    style A fill:#e1f5fe
    style N fill:#c8e6c9
```

## 3. Hybrid Retrieval Architecture

```mermaid
flowchart LR
    subgraph "Query Processing"
        A[User Query] --> B[Query Embedding<br/>text-embedding-3-large]
        A --> C[Query Tokenization<br/>BM25 terms]
    end
    
    subgraph "Dense Path"
        B --> D[(Vector Database<br/>Qdrant/Pinecone/pgvector)]
        D --> E[Top-50 by cosine similarity]
    end
    
    subgraph "Sparse Path"
        C --> F[(BM25 Index<br/>Elasticsearch/Lucene)]
        F --> G[Top-50 by BM25 score]
    end
    
    subgraph "Fusion"
        E --> H[Reciprocal Rank Fusion]
        G --> H
        H --> I[Merged Top-K<br/>Combined scores]
    end
    
    subgraph "Post-Processing"
        I --> J[Metadata Filtering]
        J --> K[ACL Filtering]
        K --> L[Score Threshold]
        L --> M[Final Results]
    end
    
    style A fill:#e1f5fe
    style M fill:#c8e6c9
    style H fill:#fff3e0
```

## 4. Reranking Pipeline

```mermaid
flowchart TD
    A[Initial Retrieval Results<br/>Top-50 candidates] --> B[Create Query-Document Pairs]
    
    B --> C{Reranker Type}
    
    C -->|Local| D[Cross-Encoder<br/>ms-marco-MiniLM-L-6-v2]
    C -->|API| E[Cohere Rerank API<br/>rerank-english-v3.0]
    C -->|ColBERT| F[Late Interaction<br/>Token-level matching]
    
    D --> G[Score Each Pair<br/>Joint query-doc encoding]
    E --> G
    F --> G
    
    G --> H[Sort by Rerank Score]
    H --> I[Take Top-K<br/>typically 5-10]
    
    I --> J[Return Reranked Results]
    
    subgraph "Latency Budget"
        K[Initial Retrieval: ~50ms]
        L[Reranking: ~100-300ms]
        M[Total: ~150-350ms]
    end
    
    style A fill:#e1f5fe
    style J fill:#c8e6c9
    style G fill:#fff3e0
```

## 5. RAG Pattern Decision Tree

```mermaid
flowchart TD
    A[Start: What's your RAG need?] --> B{Data volume?}
    
    B -->|Small < 100 docs| C{Complexity?}
    B -->|Large 100K+ docs| D{Query types?}
    
    C -->|Simple Q&A| E[Naive RAG<br/>Embed + Retrieve + Generate]
    C -->|Need precision| F[Hybrid + Reranking]
    
    D -->|Single-hop factual| F
    D -->|Multi-hop reasoning| G{Data structure?}
    D -->|Mixed/diverse| H[Adaptive RAG<br/>Route by query type]
    
    G -->|Relational/Entities| I[Graph RAG]
    G -->|Hierarchical docs| J[Hierarchical RAG]
    G -->|Flat documents| K[Query Decomposition RAG]
    
    H --> L{Need tools beyond search?}
    L -->|Yes| M[Agentic RAG]
    L -->|No| N[Multi-Query + Reranking]
    
    subgraph "Enhancement Layer"
        O{Short ambiguous queries?}
        O -->|Yes| P[Add HyDE]
        
        Q{Queries reference metadata?}
        Q -->|Yes| R[Add Self-Query filtering]
        
        S{Coverage gaps?}
        S -->|Yes| T[Add Corrective RAG<br/>Web fallback]
    end
    
    style A fill:#e1f5fe
    style E fill:#c8e6c9
    style F fill:#c8e6c9
    style M fill:#ffcdd2
```

## 6. Ingestion Pipeline Architecture

```mermaid
flowchart TD
    subgraph "Sources"
        A1[PDFs]
        A2[HTML Pages]
        A3[Markdown]
        A4[Databases]
        A5[APIs]
    end
    
    A1 & A2 & A3 & A4 & A5 --> B[Format Detection & Parser Selection]
    
    B --> C[Document Parsing<br/>Text + Table Extraction]
    C --> D[Boilerplate Removal<br/>Headers, Footers, Nav]
    D --> E[Metadata Extraction<br/>Title, Author, Date, Tags]
    
    E --> F{Deduplication Check<br/>Content Hash}
    F -->|Duplicate| G[Skip / Log]
    F -->|New| H[Version Management]
    F -->|Updated| I[Delete Old Version<br/>Index New Version]
    
    H --> J[Chunking<br/>Strategy Selection]
    I --> J
    
    J --> K[Chunk Quality Validation]
    K --> L[Embedding Generation<br/>Batch Processing]
    
    L --> M[Vector Store<br/>Upsert Embeddings]
    L --> N[BM25 Index<br/>Update Terms]
    L --> O[Metadata Store<br/>Document Registry]
    
    subgraph "Observability"
        P[Processing Metrics]
        Q[Error Tracking]
        R[Freshness Monitoring]
    end
    
    style B fill:#e1f5fe
    style M fill:#c8e6c9
    style N fill:#c8e6c9
    style O fill:#c8e6c9
```

## 7. RAG Failure Diagnosis Flowchart

```mermaid
flowchart TD
    A[RAG System Producing Bad Answers] --> B{Is the right info<br/>in the index?}
    
    B -->|No| C[INGESTION PROBLEM]
    B -->|Yes| D{Is it being retrieved?<br/>Check retrieval logs}
    
    C --> C1[Fix: Check parsing<br/>Check chunking boundaries<br/>Verify document coverage]
    
    D -->|No| E[RETRIEVAL PROBLEM]
    D -->|Yes| F{Is it in top-k?<br/>Or buried at bottom?}
    
    E --> E1{What kind of miss?}
    E1 -->|Semantic gap| E2[Fix: Try HyDE<br/>or Multi-Query]
    E1 -->|Keyword miss| E3[Fix: Add BM25<br/>Hybrid Search]
    E1 -->|Metadata miss| E4[Fix: Add Self-Query<br/>Metadata Filtering]
    
    F -->|Buried in results| G[RANKING PROBLEM]
    F -->|In top-k| H{Does LLM use it<br/>correctly?}
    
    G --> G1[Fix: Add Reranking<br/>Cross-encoder]
    
    H -->|No - Ignores context| I[GENERATION PROBLEM]
    H -->|No - Hallucinates extra| J[FAITHFULNESS PROBLEM]
    H -->|Yes but incomplete| K[CONTEXT ASSEMBLY PROBLEM]
    
    I --> I1[Fix: Stronger system prompt<br/>Reduce temperature<br/>Better model]
    J --> J1[Fix: Add groundedness check<br/>Constrained generation<br/>Fact verification]
    K --> K1[Fix: Increase context budget<br/>Better chunk ordering<br/>Parent-child retrieval]
    
    style A fill:#ffcdd2
    style C fill:#fff3e0
    style E fill:#fff3e0
    style G fill:#fff3e0
    style I fill:#fff3e0
    style J fill:#fff3e0
    style K fill:#fff3e0
```

---

## How to Render These Diagrams

1. **VS Code**: Install "Markdown Preview Mermaid Support" extension
2. **GitHub**: Mermaid is natively supported in `.md` files
3. **CLI**: `npx @mermaid-js/mermaid-cli mmdc -i DIAGRAMS.md -o output.png`
4. **Online**: Paste into [mermaid.live](https://mermaid.live)
