# Memory Architecture - Diagrams

## 1. Memory Types Hierarchy

```mermaid
graph TD
    AM[Agent Memory] --> STM[Short-Term Memory]
    AM --> LTM[Long-Term Memory]
    
    STM --> WM[Working Memory<br/>Current task state]
    STM --> ST[Short-Term Store<br/>Recent context, session]
    STM --> TM[Tool Memory<br/>Cached tool results]
    
    LTM --> EM[Episodic Memory<br/>Past events & conversations]
    LTM --> SM[Semantic Memory<br/>Facts & preferences]
    LTM --> PM[Procedural Memory<br/>Learned workflows]
    LTM --> PrM[Project Memory<br/>Workspace context]
    LTM --> OM[Organization Memory<br/>Enterprise knowledge]
    
    style AM fill:#1a1a2e,color:#fff
    style STM fill:#16213e,color:#fff
    style LTM fill:#0f3460,color:#fff
    style WM fill:#e94560,color:#fff
    style ST fill:#e94560,color:#fff
    style TM fill:#e94560,color:#fff
    style EM fill:#533483,color:#fff
    style SM fill:#533483,color:#fff
    style PM fill:#533483,color:#fff
    style PrM fill:#533483,color:#fff
    style OM fill:#533483,color:#fff
```

## 2. Memory Write Flow with Policy Checks

```mermaid
flowchart TD
    INPUT[/"User Interaction / Agent Output"/] --> WC{Write Controller:<br/>Should we remember this?}
    
    WC -->|"Low importance"| DISCARD[Discard]
    WC -->|"Worth remembering"| CLASSIFY[Memory Classifier]
    
    CLASSIFY --> TYPE{Classify Type}
    TYPE -->|"Preference/Fact"| SEMANTIC[Semantic Memory]
    TYPE -->|"Event/Conversation"| EPISODIC[Episodic Memory]
    TYPE -->|"Workflow/Pattern"| PROCEDURAL[Procedural Memory]
    
    SEMANTIC --> PII
    EPISODIC --> PII
    PROCEDURAL --> PII
    
    PII{PII/Sensitivity<br/>Scanner} -->|"Contains secrets"| BLOCK[🚫 BLOCK<br/>Never store credentials]
    PII -->|"Contains PII"| REDACT{Redact or<br/>Request Consent?}
    PII -->|"Clean"| TENANT
    
    REDACT -->|"High sensitivity"| REDACT_STORE[Redact & Store]
    REDACT -->|"Medium sensitivity"| CONSENT{User Consent?}
    
    CONSENT -->|"Granted"| TENANT
    CONSENT -->|"Denied"| DISCARD
    
    REDACT_STORE --> TENANT
    TENANT{Tenant Policy<br/>Check} -->|"Blocked by org"| DISCARD
    TENANT -->|"Allowed"| STORE
    
    STORE[(Memory Store)] --> TTL[Set TTL &<br/>Expiration]
    TTL --> INDEX[Generate Embedding<br/>& Index]
    INDEX --> AUDIT[📋 Audit Log]
    
    style BLOCK fill:#dc3545,color:#fff
    style STORE fill:#28a745,color:#fff
    style AUDIT fill:#6c757d,color:#fff
    style DISCARD fill:#ffc107,color:#000
```

## 3. Memory Retrieval Strategy Comparison

```mermaid
graph LR
    subgraph Strategies
        R[Recency<br/>score = e^(-λt)]
        REL[Relevance<br/>score = cosine_sim]
        I[Importance<br/>score = base × freq × access]
    end
    
    subgraph Hybrid["Hybrid Scoring"]
        H[final = w₁×recency + w₂×relevance + w₃×importance + context_bonus]
    end
    
    subgraph ContextProfiles["Context-Aware Weights"]
        NEW["New Conversation<br/>recency=0.5, rel=0.3, imp=0.2"]
        QA["Question Answering<br/>recency=0.1, rel=0.7, imp=0.2"]
        CODE["Code Generation<br/>recency=0.2, rel=0.4, imp=0.4"]
        DEBUG["Debugging<br/>recency=0.4, rel=0.4, imp=0.2"]
    end
    
    R --> H
    REL --> H
    I --> H
    
    H --> NEW
    H --> QA
    H --> CODE
    H --> DEBUG
```

## 4. Memory Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created: Write decision approved
    
    Created --> Active: Indexed & stored
    Active --> Accessed: Retrieved for query
    Accessed --> Active: Return to pool
    
    Active --> Summarized: Old & verbose → compress
    Summarized --> Active: Summary replaces original
    
    Active --> Consolidated: Merged with duplicates
    Consolidated --> Active: Single enriched memory
    
    Active --> Stale: Confidence decayed
    Stale --> Updated: New info confirms/updates
    Updated --> Active: Refreshed
    Stale --> Expired: TTL reached
    
    Active --> Expired: TTL reached
    Expired --> Deleted: Cleanup job
    
    Active --> Deleted: User request / GDPR
    Stale --> Deleted: Policy expiry
    
    Deleted --> [*]: Hard delete from all stores
    
    note right of Created: PII check, consent, tenant policy
    note right of Summarized: LLM-based compression
    note right of Deleted: Cascade to embeddings & backups
```

## 5. Memory Architecture for Multi-Turn Agent

```mermaid
flowchart TD
    USER[👤 User Message] --> AGENT[🤖 Agent]
    
    subgraph MemoryRetrieval["Memory Retrieval (before response)"]
        WM[Working Memory<br/>Current task state]
        STM_R[Short-Term<br/>Last few turns]
        LTM_R[Long-Term Search<br/>Relevant memories]
    end
    
    AGENT --> |"1. Gather context"| MemoryRetrieval
    
    WM --> PROMPT
    STM_R --> PROMPT
    LTM_R --> PROMPT
    
    PROMPT[Augmented Prompt<br/>User msg + Memories + Instructions] --> LLM[LLM Generation]
    
    LLM --> RESPONSE[Response]
    LLM --> TOOLS[Tool Calls]
    
    TOOLS --> TOOL_EXEC[Execute Tools]
    TOOL_EXEC --> TOOL_RESULTS[Tool Results]
    TOOL_RESULTS --> LLM
    
    subgraph MemoryWrite["Memory Write (after response)"]
        EVAL{What to remember?}
        EVAL -->|"User preference"| SEM_W[(Semantic Store)]
        EVAL -->|"Conversation"| EP_W[(Episodic Store)]
        EVAL -->|"Tool result"| TOOL_W[(Tool Cache)]
        EVAL -->|"Task state"| WM_W[Working Memory Update]
    end
    
    RESPONSE --> EVAL
    TOOL_RESULTS --> EVAL
    
    RESPONSE --> USER
    
    style USER fill:#4CAF50,color:#fff
    style AGENT fill:#2196F3,color:#fff
    style LLM fill:#FF9800,color:#fff
    style PROMPT fill:#9C27B0,color:#fff
```

## 6. Memory Governance Flow

```mermaid
flowchart LR
    subgraph Ingress["Write Governance"]
        A[Content] --> B{Poisoning<br/>Detection}
        B -->|"Safe"| C{PII<br/>Scanner}
        B -->|"Suspicious"| BLOCK1[🚫 Block]
        C -->|"Secrets"| BLOCK2[🚫 Block]
        C -->|"PII found"| D{Consent<br/>Check}
        C -->|"Clean"| E{Tenant<br/>Policy}
        D -->|"Granted"| E
        D -->|"Denied"| BLOCK3[🚫 Block]
        E -->|"Allowed"| STORE[✅ Store]
        E -->|"Blocked"| BLOCK4[🚫 Block]
    end
    
    subgraph Runtime["Access Governance"]
        F[Query] --> G{Isolation<br/>Check}
        G -->|"Own data"| H[Retrieve]
        G -->|"Other user"| DENY[🚫 Deny]
        H --> I{Sensitivity<br/>Filter}
        I --> J[Return Results]
    end
    
    subgraph Lifecycle["Lifecycle Governance"]
        K[Scheduled Job] --> L{Check TTL}
        L -->|"Expired"| M[Delete]
        L -->|"Active"| N{Check<br/>Limits}
        N -->|"Over limit"| O[Prune lowest]
        N -->|"Within"| P[Keep]
        
        Q[User Request] --> R[GDPR Delete All]
        R --> S[Verify Deletion]
    end
    
    STORE --> AUDIT[(📋 Audit Log)]
    DENY --> AUDIT
    M --> AUDIT
    R --> AUDIT
```

## 7. Memory-Augmented Agent Loop

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant WM as Working Memory
    participant R as Memory Retriever
    participant S as Memory Store
    participant W as Write Controller
    
    U->>A: "Refactor the auth module"
    
    A->>WM: Set task: "refactor auth"
    A->>R: Retrieve(query="auth module refactoring", type=all)
    
    R->>S: Search(embedding, recency, importance)
    S-->>R: [user prefers TS, project uses Next.js, auth uses JWT]
    R-->>A: Top-K relevant memories
    
    Note over A: Construct prompt with<br/>user msg + memories + instructions
    
    A->>A: Generate plan with context
    A->>WM: Store intermediate state
    
    A->>U: "Here's my refactoring plan..."
    
    A->>W: Evaluate: should we remember anything?
    W->>W: Classify importance & sensitivity
    W-->>A: Decision: store "user is refactoring auth" (episodic, medium importance)
    
    A->>S: Store new memory
    S->>S: Generate embedding, set TTL
    
    Note over S: Periodic: consolidate,<br/>summarize, prune, expire
```

## 8. Memory Storage Topology

```mermaid
graph TD
    subgraph Application["Agent Application Layer"]
        MC[Memory Controller]
        WC[Write Controller]
        RC[Read Controller]
    end
    
    subgraph Stores["Storage Layer"]
        subgraph Hot["Hot Storage (< 1ms)"]
            REDIS[(Redis<br/>Working Memory<br/>Tool Cache<br/>Short-Term)]
        end
        
        subgraph Warm["Warm Storage (< 50ms)"]
            PG[(PostgreSQL + pgvector<br/>Episodic Memory<br/>Semantic Memory<br/>Audit Logs)]
            VDB[(Vector DB<br/>Long-Term Embeddings<br/>Similarity Search)]
        end
        
        subgraph Cold["Cold Storage (< 500ms)"]
            GRAPH[(Graph DB<br/>Org Knowledge Graph<br/>Entity Relations)]
            BLOB[(Blob Storage<br/>Archived Memories<br/>Backups)]
        end
    end
    
    MC --> WC
    MC --> RC
    
    WC --> REDIS
    WC --> PG
    WC --> VDB
    WC --> GRAPH
    
    RC --> REDIS
    RC --> PG
    RC --> VDB
    RC --> GRAPH
    
    PG -->|"Archive after 90d"| BLOB
    VDB -->|"Pruned vectors"| BLOB
    
    subgraph Governance["Governance Layer"]
        AUDIT[Audit Log<br/>Immutable]
        POLICY[Policy Engine]
        CONSENT[Consent Store]
    end
    
    WC --> POLICY
    POLICY --> CONSENT
    WC --> AUDIT
    RC --> AUDIT
    
    style Hot fill:#dc3545,color:#fff
    style Warm fill:#fd7e14,color:#fff
    style Cold fill:#6c757d,color:#fff
    style Governance fill:#198754,color:#fff
```

---

## Key Relationships

| Diagram | Shows |
|---------|-------|
| Types Hierarchy | What kinds of memory exist and how they relate |
| Write Flow | Every check a memory passes before storage |
| Retrieval Comparison | How different strategies score memories |
| Lifecycle | States a memory goes through from birth to deletion |
| Multi-Turn Agent | How memory integrates into the agent loop |
| Governance | Full governance pipeline (write + access + lifecycle) |
| Agent Loop | Sequence of operations in a memory-augmented turn |
| Storage Topology | Physical storage architecture with hot/warm/cold tiers |
