# LLMOps & AgentOps: Architecture Diagrams

## 1. LLMOps Lifecycle Loop

```mermaid
graph LR
    A[Dataset Creation] --> B[Prompt/Model/Retriever Development]
    B --> C[Offline Evaluation]
    C --> D[Safety Evaluation]
    D --> E[Regression Testing]
    E --> F[Canary Release]
    F --> G[Online Monitoring]
    G --> H[Human Feedback]
    H --> I[Dataset Update]
    I --> J[Continuous Improvement]
    J --> A

    style A fill:#e1f5fe
    style C fill:#f3e5f5
    style D fill:#fce4ec
    style F fill:#e8f5e9
    style G fill:#fff3e0
    style H fill:#fbe9e7
```

## 2. AgentOps Lifecycle Loop

```mermaid
graph LR
    A[Agent Design] --> B[Tool Design]
    B --> C[Permission Design]
    C --> D[Trajectory Testing]
    D --> E[Tool-Call Evaluation]
    E --> F[Safety Red-Team]
    F --> G[Deployment]
    G --> H[Trace Monitoring]
    H --> I[Failure Clustering]
    I --> J[Policy/Prompt/Tool Update]
    J --> A

    style A fill:#e8eaf6
    style D fill:#f3e5f5
    style F fill:#fce4ec
    style G fill:#e8f5e9
    style H fill:#fff3e0
    style I fill:#ffebee
```

## 3. Prompt Versioning Workflow

```mermaid
flowchart TD
    subgraph Development
        A[Author writes prompt] --> B[Create version v(n+1)]
        B --> C[Compute content hash]
        C --> D[Run offline eval]
    end

    subgraph Review
        D --> E{Eval passes?}
        E -->|No| A
        E -->|Yes| F[Deploy to DEV]
        F --> G[Integration testing]
        G --> H{Tests pass?}
        H -->|No| A
        H -->|Yes| I[Promote to STAGING]
    end

    subgraph Production
        I --> J[Staging validation]
        J --> K{Validation passes?}
        K -->|No| L[Rollback to v(n)]
        K -->|Yes| M[Canary to PROD 1%]
        M --> N{Canary healthy?}
        N -->|No| L
        N -->|Yes| O[Ramp to 100%]
        O --> P[Monitor production]
        P --> Q{Quality degraded?}
        Q -->|Yes| L
        Q -->|No| R[Version stable ✓]
    end

    style L fill:#ffcdd2
    style R fill:#c8e6c9
```

## 4. Continuous Improvement Pipeline

```mermaid
flowchart TD
    subgraph Collection
        A[Production Traffic] --> B[Trace Collector]
        B --> C[Quality Scorer]
        C --> D[Failure Detector]
    end

    subgraph Analysis
        D --> E[Failure Clusterer]
        E --> F[Impact Scorer]
        F --> G[Top-K Clusters]
    end

    subgraph Review
        G --> H[Human Review Queue]
        H --> I[Expert Review]
        I --> J[Feedback-to-Eval Pipeline]
    end

    subgraph Improvement
        J --> K[New Eval Examples]
        G --> L[Improvement Candidates]
        L --> M[Candidate Ranking]
        M --> N[Targeted Fix]
        N --> O[Regression Test]
        K --> O
        O --> P{Passes?}
        P -->|Yes| Q[Canary Deploy]
        P -->|No| N
        Q --> R[Monitor Impact]
        R --> A
    end

    style A fill:#e3f2fd
    style H fill:#fff9c4
    style Q fill:#c8e6c9
```

## 5. Dataset Management Flow

```mermaid
flowchart TD
    subgraph Sources
        A[Manual Curation] --> E[Dataset Builder]
        B[Production Mining] --> E
        C[Synthetic Generation] --> E
        D[Feedback Pipeline] --> E
    end

    subgraph Versioning
        E --> F[Schema Validation]
        F --> G{Valid?}
        G -->|No| H[Fix Errors]
        H --> F
        G -->|Yes| I[Quality Gates]
        I --> J[Compute Hash]
        J --> K[Create Version v(n)]
    end

    subgraph Quality Gates
        I --> L[Schema Compliance]
        I --> M[Diversity Check]
        I --> N[Size Check]
        I --> O[Deduplication]
        L & M & N & O --> P{All Pass?}
        P -->|No| Q[Report Issues]
        P -->|Yes| K
    end

    subgraph Usage
        K --> R[Split Management]
        R --> S[Train/Val/Test/Golden]
        S --> T[Eval Runs]
        T --> U[Results Tracking]
    end

    style K fill:#c8e6c9
    style Q fill:#ffcdd2
```

## 6. Production Feedback Loop

```mermaid
flowchart TD
    subgraph Production
        A[User Request] --> B[LLM System]
        B --> C[Response]
        C --> D[User]
    end

    subgraph Feedback Signals
        D -->|Thumbs up/down| E[Explicit Feedback]
        D -->|Regenerate| F[Implicit Feedback]
        D -->|Report| G[Bug Reports]
        B -->|Auto-score| H[LLM Judge]
    end

    subgraph Processing
        E & F & G & H --> I[Feedback Aggregator]
        I --> J[Signal Classification]
        J --> K[High-confidence positive]
        J --> L[High-confidence negative]
        J --> M[Ambiguous - needs review]
    end

    subgraph Actions
        K --> N[Add to Golden Dataset]
        L --> O[Human Review Queue]
        M --> O
        O --> P[Expert Annotation]
        P --> Q[Corrected Examples]
        Q --> R[Eval Dataset Update]
        R --> S[Trigger Re-evaluation]
        S --> T[Improvement Cycle]
    end

    style N fill:#c8e6c9
    style T fill:#e3f2fd
```

## 7. LLMOps vs MLOps Comparison

```mermaid
graph TB
    subgraph MLOps["Traditional MLOps"]
        direction TB
        M1[Feature Engineering] --> M2[Model Training]
        M2 --> M3[Validation on Test Set]
        M3 --> M4[Model Registry]
        M4 --> M5[Model Serving]
        M5 --> M6[Data Drift Monitoring]
        M6 --> M7[Retrain Trigger]
        M7 --> M1
    end

    subgraph LLMOps["LLMOps"]
        direction TB
        L1[Dataset Curation] --> L2[Prompt Engineering]
        L2 --> L3[Multi-Dimensional Eval]
        L3 --> L4[Prompt Registry]
        L4 --> L5[Canary Deployment]
        L5 --> L6[Quality + Safety Monitoring]
        L6 --> L7[Human Feedback Loop]
        L7 --> L1
    end

    subgraph KeyDifferences["Key Differences"]
        D1["Artifact: Model weights → Prompts + Config"]
        D2["Eval: Accuracy → Rubric-based judgment"]
        D3["Iteration: Days → Minutes"]
        D4["Failure: Wrong prediction → Hallucination/Harm"]
        D5["Ground truth: Labels → Subjective quality"]
    end

    style MLOps fill:#e3f2fd
    style LLMOps fill:#f3e5f5
    style KeyDifferences fill:#fff9c4
```

## 8. Agent Performance Monitoring

```mermaid
flowchart TD
    subgraph Ingestion
        A[Agent Execution] --> B[Trace Collector]
        B --> C[Step-level Logging]
        C --> D[Metric Extraction]
    end

    subgraph RealTime["Real-Time Dashboard"]
        D --> E[Health Status]
        D --> F[Success Rate]
        D --> G[Latency Percentiles]
        D --> H[Cost Tracking]
        D --> I[Tool Usage Heatmap]
    end

    subgraph Alerting
        E & F & G & H --> J[Alert Engine]
        J --> K{Threshold Breached?}
        K -->|Yes| L[Fire Alert]
        L --> M[Notification]
        L --> N[Auto-rollback?]
        K -->|No| O[Continue Monitoring]
    end

    subgraph Analysis["Deep Analysis"]
        D --> P[Trajectory Visualization]
        D --> Q[Error Clustering]
        D --> R[Tool Performance]
        D --> S[Agent Comparison]
        P & Q & R & S --> T[Root Cause Analysis]
        T --> U[Improvement Actions]
    end

    style L fill:#ffcdd2
    style O fill:#c8e6c9
    style U fill:#e8eaf6
```

## 9. End-to-End LLMOps Platform Architecture

```mermaid
flowchart TD
    subgraph Development["Development Layer"]
        A[Prompt IDE] --> B[Version Control]
        C[Dataset Editor] --> D[Dataset Store]
        E[Eval Builder] --> F[Eval Registry]
    end

    subgraph Evaluation["Evaluation Layer"]
        B & D & F --> G[Eval Orchestrator]
        G --> H[Offline Eval]
        G --> I[Safety Eval]
        G --> J[Regression Tests]
        H & I & J --> K[Results Dashboard]
    end

    subgraph Deployment["Deployment Layer"]
        K --> L{Gates Pass?}
        L -->|Yes| M[Deployment Pipeline]
        M --> N[Canary Controller]
        N --> O[Traffic Router]
        L -->|No| P[Block + Notify]
    end

    subgraph Runtime["Runtime Layer"]
        O --> Q[LLM Gateway]
        Q --> R[Guardrails]
        R --> S[Model Provider]
        S --> T[Response]
        T --> U[Quality Monitor]
    end

    subgraph Feedback["Feedback Layer"]
        U --> V[Trace Store]
        V --> W[Failure Detector]
        W --> X[Review Queue]
        X --> Y[Dataset Pipeline]
        Y --> D
    end

    style M fill:#c8e6c9
    style P fill:#ffcdd2
    style V fill:#e3f2fd
```
