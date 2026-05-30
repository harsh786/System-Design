# Evaluation Mastery - Diagrams

## 1. Evaluation Layers Pyramid

```mermaid
graph TB
    subgraph "Evaluation Layers (Bottom = Foundation)"
        L1[Layer 1: Model Evaluation]
        L2[Layer 2: Prompt Evaluation]
        L3[Layer 3: Retrieval Evaluation]
        L4[Layer 4: RAG Evaluation]
        L5[Layer 5: Agent Evaluation]
        L6[Layer 6: Tool Evaluation]
        L7[Layer 7: Safety Evaluation]
        L8[Layer 8: Business Evaluation]
        L9[Layer 9: System Evaluation]
        L10[Layer 10: Human Evaluation]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    L5 --> L6
    L6 --> L7
    L7 --> L8
    L8 --> L9
    L9 --> L10

    style L7 fill:#ff6b6b,color:#fff
    style L10 fill:#4ecdc4,color:#fff
    style L4 fill:#45b7d1,color:#fff
    style L5 fill:#96ceb4,color:#fff
```

## 2. CI/CD Evaluation Pipeline Flow

```mermaid
flowchart TD
    A[Code Change / PR] --> B{Pre-commit Checks}
    B -->|Pass| C[Fast Eval<br/>50 examples, <5min]
    B -->|Fail| X[Block: Fix Issues]
    
    C -->|Pass| D[Full Eval<br/>All examples, <30min]
    C -->|Fail| X
    
    D -->|Pass| E[Safety Eval<br/>Adversarial suite, <15min]
    D -->|Fail| X
    
    E -->|Pass| F[Regression Analysis<br/>vs Baseline]
    E -->|Fail| X
    
    F -->|No Regression| G[Statistical Significance Test]
    F -->|Significant Regression| X
    
    G -->|p < 0.05 improvement| H[PASS: Deploy]
    G -->|No significant change| I{Marginal?}
    G -->|p < 0.05 regression| X
    
    I -->|Yes| J[CANARY: 5% traffic]
    I -->|No| H
    
    J --> K{Canary Metrics OK?}
    K -->|Yes| L[Promote to 100%]
    K -->|No| M[Rollback]
    
    H --> N[Update Baseline]
    L --> N
    
    style X fill:#ff4444,color:#fff
    style H fill:#00cc66,color:#fff
    style J fill:#ffaa00,color:#fff
    style L fill:#00cc66,color:#fff
    style M fill:#ff4444,color:#fff
```

## 3. Golden Dataset Lifecycle

```mermaid
flowchart LR
    subgraph Sources
        S1[Domain Expert]
        S2[Production Failures]
        S3[Synthetic Generation]
        S4[Adversarial Red Team]
        S5[User-Reported Issues]
    end
    
    subgraph Creation
        C1[Draft Example]
        C2[Validate Schema]
        C3[Peer Review]
        C4[Approve]
    end
    
    subgraph Active Use
        U1[CI/CD Evaluation]
        U2[A/B Testing]
        U3[Model Selection]
        U4[Regression Detection]
    end
    
    subgraph Maintenance
        M1[Coverage Audit<br/>Quarterly]
        M2[Staleness Check<br/>Monthly]
        M3[Adversarial Refresh<br/>Monthly]
        M4[Deprecation]
    end
    
    S1 & S2 & S3 & S4 & S5 --> C1
    C1 --> C2 --> C3 --> C4
    C4 --> U1 & U2 & U3 & U4
    U1 & U2 & U3 & U4 --> M1
    M1 --> M2 --> M3
    M3 -->|Stale| M4
    M4 -->|Replace| S3
    
    style C4 fill:#00cc66,color:#fff
    style M4 fill:#ff6b6b,color:#fff
```

## 4. RAG Evaluation Metrics Flow

```mermaid
flowchart TD
    Q[Query] --> R[Retriever]
    R --> D[Retrieved Documents]
    D --> G[Generator/LLM]
    G --> A[Generated Answer]
    
    subgraph "Retrieval Metrics"
        RM1[Recall@k]
        RM2[Precision@k]
        RM3[MRR]
        RM4[nDCG@k]
    end
    
    subgraph "Context Metrics"
        CM1[Context Precision]
        CM2[Context Recall]
        CM3[Context Relevance]
    end
    
    subgraph "Answer Metrics"
        AM1[Faithfulness]
        AM2[Groundedness]
        AM3[Answer Relevance]
        AM4[Answer Correctness]
        AM5[Abstention Accuracy]
    end
    
    subgraph "Citation Metrics"
        CT1[Citation Precision]
        CT2[Citation Recall]
    end
    
    D --> RM1 & RM2 & RM3 & RM4
    D --> CM1 & CM2 & CM3
    A --> AM1 & AM2 & AM3 & AM4 & AM5
    A --> CT1 & CT2
    
    style AM1 fill:#ff6b6b,color:#fff
    style AM5 fill:#ff6b6b,color:#fff
    style RM1 fill:#45b7d1,color:#fff
```

## 5. Agent Trajectory Evaluation

```mermaid
sequenceDiagram
    participant U as User Task
    participant A as Agent
    participant T as Tools
    participant E as Evaluator
    participant G as Ground Truth
    
    U->>A: Task description
    
    rect rgb(240, 248, 255)
        Note over A,T: Trajectory Recording
        A->>A: Reasoning step 1
        A->>T: Tool call 1 (lookup_customer)
        T-->>A: Result 1
        A->>A: Reasoning step 2
        A->>T: Tool call 2 (get_orders)
        T-->>A: Result 2
        A->>T: Tool call 3 (unnecessary call!)
        T-->>A: Result 3
        A->>U: Final answer
    end
    
    rect rgb(255, 245, 238)
        Note over E,G: Evaluation Phase
        E->>G: Load expected trajectory
        G-->>E: Expected: [lookup_customer, get_orders]
        E->>E: Tool Selection: 2/3 correct (precision)
        E->>E: Tool Arguments: check args match
        E->>E: Efficiency: 3 calls vs 2 optimal
        E->>E: Loop Detection: no loops
        E->>E: Safety: no forbidden tools used
        E->>E: Answer: matches expected?
    end
    
    E-->>U: Evaluation Report
```

## 6. Quality-Cost Frontier Analysis

```mermaid
graph LR
    subgraph "Configuration Space"
        C1[GPT-4o-mini<br/>Top-3, No rerank<br/>$0.002/query]
        C2[GPT-4o-mini<br/>Top-5, Rerank<br/>$0.008/query]
        C3[GPT-4o<br/>Top-5, No rerank<br/>$0.03/query]
        C4[GPT-4o<br/>Top-10, Rerank<br/>$0.08/query]
        C5[GPT-4<br/>Top-10, Rerank + Summary<br/>$0.15/query]
    end
    
    subgraph "Pareto Frontier"
        P1[Optimal for<br/>$0.01 budget]
        P2[Optimal for<br/>$0.05 budget]
        P3[Optimal for<br/>$0.10 budget]
    end
    
    subgraph "Dominated (Inefficient)"
        D1[Same quality as C2<br/>but 3x cost]
    end
    
    C1 -.->|Quality: 0.72| P1
    C2 -.->|Quality: 0.81| P1
    C4 -.->|Quality: 0.89| P2
    C5 -.->|Quality: 0.93| P3
    C3 -.->|Quality: 0.80| D1
    
    style P1 fill:#00cc66,color:#fff
    style P2 fill:#00cc66,color:#fff
    style P3 fill:#00cc66,color:#fff
    style D1 fill:#ff6b6b,color:#fff
```

## 7. LLM-as-Judge Calibration

```mermaid
flowchart TD
    subgraph "Calibration Process"
        A[Human-labeled examples<br/>n=200] --> B[LLM Judge scores same examples]
        B --> C[Compute Agreement]
        C --> D{Cohen's κ ≥ 0.7?}
        D -->|Yes| E[Judge Calibrated<br/>Use for automation]
        D -->|No| F[Diagnose Issues]
        F --> G[Position bias?<br/>Randomize A/B order]
        F --> H[Verbosity bias?<br/>Add length control]
        F --> I[Self-enhancement?<br/>Use different judge model]
        G & H & I --> J[Adjust prompts/settings]
        J --> B
    end
    
    subgraph "Production Usage"
        E --> K[Score new examples]
        K --> L{Confidence > 0.8?}
        L -->|Yes| M[Accept automated score]
        L -->|No| N[Route to human review]
    end
    
    style E fill:#00cc66,color:#fff
    style N fill:#ffaa00,color:#fff
```

## 8. Evaluation Decision Gates

```mermaid
flowchart TD
    subgraph "Hard Gates (Binary)"
        HG1{Faithfulness ≥ 0.90?}
        HG2{Safety Score ≥ 0.95?}
        HG3{Abstention Accuracy ≥ 0.85?}
    end
    
    subgraph "Soft Gates (Statistical)"
        SG1{Recall@5 regressed<br/>significantly?<br/>p < 0.05}
        SG2{Answer relevance<br/>regressed?<br/>p < 0.05}
        SG3{Citation F1<br/>regressed?<br/>p < 0.05}
    end
    
    subgraph "Decisions"
        PASS[✅ PASS<br/>Deploy to production]
        CANARY[🐤 CANARY<br/>Deploy to 5%]
        BLOCK[❌ BLOCK<br/>Fix required]
        REVIEW[👀 MANUAL REVIEW<br/>Human decision needed]
    end
    
    START[Evaluation Results] --> HG1
    HG1 -->|No| BLOCK
    HG1 -->|Yes| HG2
    HG2 -->|No| BLOCK
    HG2 -->|Yes| HG3
    HG3 -->|No| BLOCK
    HG3 -->|Yes| SG1
    
    SG1 -->|Yes, significant| BLOCK
    SG1 -->|No| SG2
    SG2 -->|Yes, significant| CANARY
    SG2 -->|No| SG3
    SG3 -->|Yes, marginal| REVIEW
    SG3 -->|No| PASS
    
    style PASS fill:#00cc66,color:#fff
    style BLOCK fill:#ff4444,color:#fff
    style CANARY fill:#ffaa00,color:#000
    style REVIEW fill:#9b59b6,color:#fff
```
