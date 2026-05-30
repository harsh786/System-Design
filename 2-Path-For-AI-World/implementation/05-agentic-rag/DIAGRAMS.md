# Agentic RAG — System Diagrams

## 1. Agentic RAG Complete Flow

```mermaid
flowchart TD
    A[User Query] --> B[Intent & Risk Classifier]
    B --> C{Risk Level}
    C -->|low/medium| D[Query Decomposer]
    C -->|high/critical| D
    
    D --> E{Needs Decomposition?}
    E -->|No| F[Single Query Path]
    E -->|Yes| G[Generate Sub-Questions]
    
    G --> H[Build Dependency DAG]
    H --> I[Assign Execution Tiers]
    
    I --> J[Tool Selection per Sub-Q]
    F --> J
    
    J --> K[Execute Retrieval]
    K --> L[Rerank Results]
    L --> M{Evidence Sufficient?}
    
    M -->|No, iter < max| N[Reformulate Query]
    N --> J
    M -->|No, iter >= max| O[Proceed with Partial Evidence]
    M -->|Yes| P[Generate Answer]
    O --> P
    
    P --> Q[Decompose into Claims]
    Q --> R[Verify Each Claim]
    R --> S{All Claims Grounded?}
    
    S -->|Some ungrounded| T[Remove/Flag Claims]
    S -->|All grounded| U[Compute Confidence]
    T --> U
    
    U --> V{Confidence × Risk Matrix}
    V -->|High conf| W[✓ ANSWER]
    V -->|Medium conf| X[⚠ ANSWER + CAVEAT]
    V -->|Low conf, answerable| Y[? ASK CLARIFICATION]
    V -->|Very low conf| Z[✗ ABSTAIN]
    V -->|High risk + low conf| AA[⚡ ESCALATE TO HUMAN]
    
    style W fill:#4CAF50,color:white
    style X fill:#FF9800,color:white
    style Y fill:#2196F3,color:white
    style Z fill:#9E9E9E,color:white
    style AA fill:#F44336,color:white
```

## 2. Query Decomposition Decision Tree

```mermaid
flowchart TD
    A[Incoming Query] --> B{Word Count ≤ 8?}
    
    B -->|Yes| C{Contains Complexity Indicators?}
    B -->|No| D[LLM Complexity Classification]
    
    C -->|No| E[SIMPLE: No Decomposition]
    C -->|Yes| D
    
    D --> F{Classified Complexity}
    
    F -->|simple| E
    F -->|multi_entity| G[Parallel Fan-Out]
    F -->|multi_hop| H[Sequential Chain]
    F -->|comparative| I[Parallel + Compare]
    F -->|temporal| J[Sequential + Time Filter]
    F -->|conditional| K[Conditional Branch]
    
    G --> L[Generate Independent Sub-Qs]
    H --> M[Generate Dependent Sub-Qs]
    I --> N[Generate Parallel Sub-Qs + Synthesis Q]
    J --> O[Generate Time-Ordered Sub-Qs]
    K --> P[Generate Condition + Consequence Sub-Qs]
    
    L --> Q[Execute All in Parallel]
    M --> R[Execute Tier by Tier]
    N --> S[Parallel Retrieve → Compare Synthesis]
    O --> R
    P --> R
    
    Q --> T[Concatenate Strategy]
    R --> U[Chain Strategy]
    S --> V[Compare Strategy]
    
    T --> W[Synthesize Final Answer]
    U --> W
    V --> W
    
    style E fill:#4CAF50,color:white
    style G fill:#2196F3,color:white
    style H fill:#FF9800,color:white
    style I fill:#9C27B0,color:white
    style J fill:#795548,color:white
    style K fill:#607D8B,color:white
```

## 3. Iterative Retrieval Loop

```mermaid
flowchart TD
    A[Start: Query + Selected Tool] --> B[Retrieve Top-K]
    B --> C[Rerank Results]
    C --> D[Evaluate Sufficiency]
    
    D --> E{Score ≥ 0.75?}
    E -->|Yes| F[✓ Evidence Sufficient]
    
    E -->|No| G{Iteration < Max?}
    G -->|No| H[⚠ Proceed with Best Available]
    
    G -->|Yes| I{Diagnosis?}
    
    I -->|wrong_source| J[Switch Retrieval Tool]
    I -->|too_broad| K[Add Filters / Narrow Query]
    I -->|too_narrow| L[Remove Constraints / Broaden]
    I -->|missing_entity| M[Add Entity-Specific Query]
    I -->|partial| N[Formulate Follow-Up for Gaps]
    
    J --> O[Re-Retrieve]
    K --> O
    L --> O
    M --> O
    N --> O
    
    O --> P[Merge with Previous Evidence]
    P --> Q[Deduplicate]
    Q --> C
    
    F --> R[Pass to Answer Generator]
    H --> R
    
    subgraph Stopping Criteria
        S1[Sufficiency threshold met]
        S2[Max iterations reached]
        S3[Diminishing returns < 5%]
        S4[All sources exhausted]
    end
    
    style F fill:#4CAF50,color:white
    style H fill:#FF9800,color:white
```

## 4. Confidence Scoring Pipeline

```mermaid
flowchart LR
    subgraph Signals
        S1[Retrieval Quality<br/>weight: 0.15]
        S2[Reranker Agreement<br/>weight: 0.10]
        S3[Source Freshness<br/>weight: 0.10]
        S4[Source Authority<br/>weight: 0.15]
        S5[Context Coverage<br/>weight: 0.15]
        S6[Groundedness<br/>weight: 0.20]
        S7[Citation Support<br/>weight: 0.05]
        S8[Answer Consistency<br/>weight: 0.10]
    end
    
    subgraph Computation
        S1 --> |score × weight| AGG[Weighted Sum]
        S2 --> |score × weight| AGG
        S3 --> |score × weight| AGG
        S4 --> |score × weight| AGG
        S5 --> |score × weight| AGG
        S6 --> |score × weight| AGG
        S7 --> |score × weight| AGG
        S8 --> |score × weight| AGG
    end
    
    AGG --> CAL{Calibration<br/>Available?}
    CAL -->|Yes| PLATT[Platt Scaling<br/>σ(a·x + b)]
    CAL -->|No| RAW[Raw Score]
    
    PLATT --> FINAL[Calibrated<br/>Confidence Score]
    RAW --> FINAL
    
    FINAL --> MATRIX[Risk × Confidence<br/>Decision Matrix]
    
    style S6 fill:#FF5722,color:white
    style FINAL fill:#2196F3,color:white
```

## 5. Abstention / Escalation Decision Flow

```mermaid
flowchart TD
    A[Confidence Score Computed] --> B{Contains Escalation<br/>Keywords?}
    
    B -->|Yes: legal, compliance,<br/>termination, etc.| C{Confidence ≥ 0.95?}
    C -->|Yes| D[Answer with Strong Caveat]
    C -->|No| E[⚡ FORCE ESCALATE]
    
    B -->|No| F{Groundedness < 0.3?}
    F -->|Yes| G[✗ ABSTAIN<br/>Too many ungrounded claims]
    
    F -->|No| H{Check Risk Level}
    
    H -->|LOW| I{Confidence?}
    I -->|≥ 0.80| J[✓ Answer]
    I -->|0.60-0.80| K[⚠ Answer + Caveat]
    I -->|0.40-0.60| L[? Clarify]
    I -->|< 0.40| M[✗ Abstain]
    
    H -->|MEDIUM| N{Confidence?}
    N -->|≥ 0.85| J
    N -->|0.70-0.85| K
    N -->|0.50-0.70| L
    N -->|0.30-0.50| M
    N -->|< 0.30| E
    
    H -->|HIGH| O{Confidence?}
    O -->|≥ 0.90| J
    O -->|0.80-0.90| K
    O -->|< 0.80| E
    
    H -->|CRITICAL| P{Confidence ≥ 0.95?}
    P -->|Yes| K
    P -->|No| E
    
    style J fill:#4CAF50,color:white
    style K fill:#FF9800,color:white
    style L fill:#2196F3,color:white
    style M fill:#9E9E9E,color:white
    style G fill:#9E9E9E,color:white
    style E fill:#F44336,color:white
    style D fill:#FF9800,color:white
```

## 6. Multi-Source Retrieval Architecture

```mermaid
flowchart TD
    A[Sub-Question] --> B[Tool Selector]
    
    B --> C{Query Characteristics}
    
    C -->|Conceptual / How / Why| D[Vector Search]
    C -->|Numeric / Aggregation| E[SQL Query]
    C -->|Entity Relations| F[Knowledge Graph]
    C -->|Real-time Data| G[API Call]
    C -->|Recent/External| H[Web Search]
    
    D --> D1[(Vector DB<br/>Pinecone/Qdrant)]
    E --> E1[(Relational DB<br/>PostgreSQL)]
    F --> F1[(Graph DB<br/>Neo4j)]
    G --> G1[External APIs]
    H --> H1[Search Engine]
    
    D1 --> I[Retrieved Chunks]
    E1 --> I
    F1 --> I
    G1 --> I
    H1 --> I
    
    I --> J[Unified Reranker]
    
    J --> K[Authority Weighting]
    K --> L[Freshness Scoring]
    L --> M[Cross-Encoder Rerank]
    M --> N[Top-K Final Evidence]
    
    subgraph Source Authority
        T1[Tier 1: Official Docs]
        T2[Tier 2: Internal Wiki]
        T3[Tier 3: Slack/Notes]
        T4[Tier 4: External]
    end
    
    K -.->|weight by tier| Source Authority
    
    style D fill:#4CAF50,color:white
    style E fill:#2196F3,color:white
    style F fill:#9C27B0,color:white
    style G fill:#FF9800,color:white
    style H fill:#795548,color:white
```

## 7. Claim Verification Sequence

```mermaid
sequenceDiagram
    participant Gen as Answer Generator
    participant Dec as Claim Decomposer
    participant Ver as Claim Verifier
    participant Evi as Evidence Store
    participant Out as Output Builder
    
    Gen->>Dec: Generated answer text
    Dec->>Dec: Split into atomic claims
    Dec-->>Ver: List of claims [C1, C2, C3, ...]
    
    loop For each claim Ci
        Ver->>Evi: Find supporting evidence for Ci
        Evi-->>Ver: Matching chunks (or none)
        
        alt Evidence directly supports claim
            Ver->>Ver: Verdict: SUPPORTED ✓
        else Evidence partially supports
            Ver->>Ver: Verdict: PARTIALLY_SUPPORTED ⚠
        else No relevant evidence found
            Ver->>Ver: Verdict: NOT_SUPPORTED ✗
        else Evidence contradicts claim
            Ver->>Ver: Verdict: CONTRADICTED ✗✗
        end
    end
    
    Ver-->>Out: Verification results per claim
    
    alt All SUPPORTED
        Out->>Out: Keep full answer, high confidence
    else Some PARTIALLY_SUPPORTED
        Out->>Out: Add caveats to partial claims
    else Any NOT_SUPPORTED
        Out->>Out: Remove ungrounded claims
    else Any CONTRADICTED
        Out->>Out: Remove claim, flag for review
        Out->>Out: Lower confidence significantly
    end
    
    Out->>Out: Compute groundedness signal
    Note over Out: groundedness = supported_count / total_claims
```
