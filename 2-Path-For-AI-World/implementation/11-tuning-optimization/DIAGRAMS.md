# Tuning and Optimization - Diagrams

## 1. Tuning Order Pyramid

```mermaid
graph TB
    subgraph "Tuning Order (Start from Bottom)"
        P[🏗️ PLATFORM<br/>Caching, batching, routing<br/>Cost: High | Impact: Medium]
        M[🤖 MODEL<br/>Fine-tuning, distillation<br/>Cost: High | Impact: Medium]
        A[🔧 AGENT<br/>Tool use, planning, orchestration<br/>Cost: Medium | Impact: Medium-High]
        PR[📝 PROMPT<br/>Instructions, examples, format<br/>Cost: Low | Impact: High]
        R[🔍 RETRIEVAL<br/>Chunking, indexing, reranking<br/>Cost: Medium | Impact: High]
        D[📊 DATA<br/>Clean, deduplicate, enrich<br/>Cost: Medium | Impact: Very High]
        PROD[🎯 PRODUCT<br/>Scope, UX, constraints<br/>Cost: Low | Impact: Massive]
    end

    PROD --> D --> R --> PR --> A --> M --> P

    style PROD fill:#22c55e,color:#fff
    style D fill:#34d399,color:#000
    style R fill:#60a5fa,color:#fff
    style PR fill:#818cf8,color:#fff
    style A fill:#a78bfa,color:#fff
    style M fill:#f472b6,color:#fff
    style P fill:#fb923c,color:#fff
```

## 2. Model Routing Decision Tree

```mermaid
graph TD
    START[Incoming Request] --> CLASSIFY[Classify Task]
    
    CLASSIFY --> RISK{Risk Level?}
    
    RISK -->|Critical| SAFETY[Safety Model<br/>GPT-4o + Guardrails]
    RISK -->|High| STRONG[Strong Model<br/>GPT-4o / Claude Sonnet]
    RISK -->|Low/Medium| COMPLEX{Complexity?}
    
    COMPLEX -->|Trivial| CACHE{Cache Hit?}
    COMPLEX -->|Simple| CHEAP[Cheap Model<br/>GPT-4o-mini]
    COMPLEX -->|Moderate| BUDGET{Budget OK?}
    COMPLEX -->|Complex/Expert| STRONG
    
    CACHE -->|Yes| CACHED[Return Cached<br/>Cost: ~$0]
    CACHE -->|No| CHEAP
    
    BUDGET -->|Yes| MID[Mid Model<br/>GPT-4o-mini]
    BUDGET -->|No| CHEAP
    
    CHEAP --> LATENCY{Latency SLA?}
    MID --> LATENCY
    STRONG --> LATENCY
    
    LATENCY -->|< 500ms| FAST[Fast Model<br/>Haiku / Local]
    LATENCY -->|Normal| EXECUTE[Execute Request]
    
    FAST --> EXECUTE
    SAFETY --> EXECUTE
    CACHED --> DONE[Return Response]
    EXECUTE --> DONE

    style CACHED fill:#22c55e,color:#fff
    style CHEAP fill:#60a5fa,color:#fff
    style STRONG fill:#f472b6,color:#fff
    style SAFETY fill:#ef4444,color:#fff
    style FAST fill:#fbbf24,color:#000
```

## 3. Token Budget Allocation

```mermaid
pie title Token Budget Allocation (8192 tokens total)
    "System Prompt (6%)" : 500
    "Retrieved Context (37%)" : 3000
    "Conversation History (24%)" : 2000
    "Current Query (2%)" : 200
    "Tool Schemas (6%)" : 500
    "Output Reserve (24%)" : 2000
```

```mermaid
graph LR
    subgraph "Token Budget Manager"
        TOTAL[Total: 8192 tokens]
        
        subgraph "Input Budget: 6192"
            SYS[System Prompt<br/>500 tokens<br/>CRITICAL]
            CTX[Retrieved Context<br/>3000 tokens<br/>HIGH]
            HIST[History<br/>2000 tokens<br/>MEDIUM]
            QUERY[Query<br/>200 tokens<br/>CRITICAL]
            TOOLS[Tool Schemas<br/>500 tokens<br/>LOW]
        end
        
        subgraph "Output Budget: 2000"
            OUT[Response<br/>2000 tokens]
        end
    end
    
    TOTAL --> SYS
    TOTAL --> CTX
    TOTAL --> HIST
    TOTAL --> QUERY
    TOTAL --> TOOLS
    TOTAL --> OUT

    style SYS fill:#ef4444,color:#fff
    style QUERY fill:#ef4444,color:#fff
    style CTX fill:#f97316,color:#fff
    style HIST fill:#eab308,color:#000
    style TOOLS fill:#22c55e,color:#fff
    style OUT fill:#6366f1,color:#fff
```

## 4. Caching Architecture Layers

```mermaid
graph TB
    REQ[Incoming Request] --> L1

    subgraph "Layer 1: Semantic Cache"
        L1[Embed Query] --> L1CHECK{Similar query<br/>cached? >0.93}
        L1CHECK -->|HIT| L1RET[Return cached response<br/>Cost: $0.0001]
    end

    L1CHECK -->|MISS| L2

    subgraph "Layer 2: Retrieval Cache"
        L2[Hash Query + Filters] --> L2CHECK{Exact retrieval<br/>cached?}
        L2CHECK -->|HIT| L2RET[Use cached chunks<br/>Skip vector search]
    end

    L2CHECK -->|MISS| RETRIEVE[Vector Search + Rerank]
    L2RET --> L3

    RETRIEVE --> L3

    subgraph "Layer 3: Prefix Cache (Provider)"
        L3[Build Messages] --> L3NOTE[System prompt + tools<br/>cached by provider<br/>50-90% discount]
    end

    L3NOTE --> L4

    subgraph "Layer 4: Tool Result Cache"
        L4{Tool calls<br/>needed?}
        L4 -->|Yes| L4CHECK{Idempotent tool?<br/>Result cached?}
        L4CHECK -->|HIT| L4RET[Use cached result]
        L4CHECK -->|MISS| EXEC[Execute tool]
        L4 -->|No| GEN
    end

    L4RET --> GEN[Generate Response]
    EXEC --> GEN
    GEN --> CACHE_RESP[Cache response for<br/>future semantic hits]
    CACHE_RESP --> RESP[Return Response]
    L1RET --> RESP

    style L1RET fill:#22c55e,color:#fff
    style L2RET fill:#34d399,color:#000
    style L4RET fill:#60a5fa,color:#fff
    style RESP fill:#8b5cf6,color:#fff
```

## 5. Cost Tracking Pipeline

```mermaid
graph LR
    subgraph "Request Processing"
        REQ[Request] --> EMBED[Embedding<br/>$0.00002]
        EMBED --> RETRIEVE[Retrieval<br/>$0.001]
        RETRIEVE --> RERANK[Reranker<br/>$0.002]
        RERANK --> LLM[LLM Call<br/>$0.01-0.10]
        LLM --> TOOLS[Tool Calls<br/>$0.001]
        TOOLS --> RESP[Response]
    end

    subgraph "Cost Tracking"
        RESP --> RECORD[Record Breakdown]
        RECORD --> AGG[Aggregate by<br/>Tenant/Model/Task]
        AGG --> CHECK[Budget Check]
        CHECK --> ALERT{Over budget?}
        ALERT -->|Yes| NOTIFY[Alert + Throttle]
        ALERT -->|No| STORE[Store Metrics]
    end

    subgraph "Analysis"
        STORE --> DASH[Dashboard]
        STORE --> FORECAST[Forecasting]
        STORE --> RECOMMEND[Recommendations]
    end

    style LLM fill:#f472b6,color:#fff
    style NOTIFY fill:#ef4444,color:#fff
    style DASH fill:#60a5fa,color:#fff
```

## 6. Quality-Cost Frontier

```mermaid
graph TB
    subgraph "Quality-Cost Frontier"
        direction LR
        
        C1[Config 1<br/>Small model, no RAG<br/>$0.01/req, Quality: 0.60]
        C2[Config 2<br/>Small model + RAG<br/>$0.03/req, Quality: 0.78]
        C3[Config 3<br/>Small + RAG + Rerank<br/>$0.05/req, Quality: 0.85]
        C4[Config 4<br/>Large + RAG<br/>$0.08/req, Quality: 0.90]
        C5[Config 5<br/>Large + Full Pipeline<br/>$0.12/req, Quality: 0.93]
        C6[Config 6<br/>Best of everything<br/>$0.20/req, Quality: 0.95]
    end

    C1 -.->|"+18% quality<br/>+$0.02"| C2
    C2 -.->|"+7% quality<br/>+$0.02"| C3
    C3 -.->|"+5% quality<br/>+$0.03"| C4
    C4 -.->|"+3% quality<br/>+$0.04"| C5
    C5 -.->|"+2% quality<br/>+$0.08"| C6

    SWEET[SWEET SPOT] --> C3
    DIMRET[Diminishing Returns] --> C5

    style C3 fill:#22c55e,color:#fff
    style SWEET fill:#22c55e,color:#fff
    style C5 fill:#fbbf24,color:#000
    style DIMRET fill:#fbbf24,color:#000
    style C6 fill:#ef4444,color:#fff
```

## 7. Fine-Tuning vs RAG Decision Flowchart

```mermaid
graph TD
    START[Need to improve AI system] --> Q1{Knowledge changes<br/>frequently?}
    
    Q1 -->|Yes| RAG1[Use RAG]
    Q1 -->|No| Q2{Need citations<br/>and sources?}
    
    Q2 -->|Yes| RAG2[Use RAG]
    Q2 -->|No| Q3{Have 100+<br/>quality examples?}
    
    Q3 -->|No| PROMPT[Improve Prompts<br/>+ Collect Data]
    Q3 -->|Yes| Q4{Task is narrow<br/>and well-defined?}
    
    Q4 -->|No| RAG3[Use RAG +<br/>Better Orchestration]
    Q4 -->|Yes| Q5{Need consistent<br/>style/format?}
    
    Q5 -->|Yes| FT1[Fine-Tune]
    Q5 -->|No| Q6{Latency or cost<br/>critical?}
    
    Q6 -->|Yes| FT2[Fine-Tune<br/>smaller model]
    Q6 -->|No| Q7{Multi-tenant with<br/>different data?}
    
    Q7 -->|Yes| RAG4[Use RAG<br/>per-tenant retrieval]
    Q7 -->|No| HYBRID[Hybrid:<br/>RAG + Fine-tuned model]

    style RAG1 fill:#60a5fa,color:#fff
    style RAG2 fill:#60a5fa,color:#fff
    style RAG3 fill:#60a5fa,color:#fff
    style RAG4 fill:#60a5fa,color:#fff
    style FT1 fill:#f472b6,color:#fff
    style FT2 fill:#f472b6,color:#fff
    style HYBRID fill:#8b5cf6,color:#fff
    style PROMPT fill:#22c55e,color:#fff
```

## 8. Optimization Loop

```mermaid
graph TD
    subgraph "1. MEASURE"
        M1[Quality Metrics<br/>accuracy, relevance, hallucination]
        M2[Cost Metrics<br/>$/request, $/task, $/tenant]
        M3[Latency Metrics<br/>p50, p95, p99]
        M4[User Metrics<br/>satisfaction, retention, escalation]
    end

    subgraph "2. IDENTIFY"
        I1[Biggest quality gaps]
        I2[Highest cost components]
        I3[Most common failures]
        I4[Slowest pipeline stages]
    end

    subgraph "3. CHANGE (one lever)"
        C1[Follow tuning order]
        C2[Pick highest ROI]
        C3[Feature flag deploy]
    end

    subgraph "4. EVALUATE"
        E1[A/B test or shadow]
        E2[Statistical significance]
        E3[Regression check]
    end

    subgraph "5. DEPLOY or ROLLBACK"
        D1[Gradual: 1% → 10% → 100%]
        D2[Monitor degradation]
        D3[Document learnings]
    end

    M1 --> I1
    M2 --> I2
    M3 --> I4
    M4 --> I3

    I1 --> C1
    I2 --> C2
    I3 --> C1
    I4 --> C3

    C1 --> E1
    C2 --> E2
    C3 --> E3

    E1 --> D1
    E2 --> D2
    E3 --> D3

    D3 -->|"Next cycle<br/>(weekly)"| M1

    style M1 fill:#60a5fa,color:#fff
    style I1 fill:#f97316,color:#fff
    style C1 fill:#22c55e,color:#fff
    style E1 fill:#a78bfa,color:#fff
    style D1 fill:#f472b6,color:#fff
```

## 9. Distillation Pipeline

```mermaid
graph TD
    subgraph "Data Collection"
        PROD[Production Queries<br/>5000+ diverse queries]
        TEACHER[Teacher Model<br/>GPT-4 / Claude Sonnet]
        PROD --> TEACHER
        TEACHER --> RAW[Raw Outputs<br/>5000 responses]
    end

    subgraph "Quality Filtering"
        RAW --> EVAL[Quality Evaluation<br/>Score each response]
        EVAL --> FILTER{Score > 0.8?}
        FILTER -->|Yes| GOOD[High-Quality Set<br/>~3500 examples]
        FILTER -->|No| DISCARD[Discard<br/>~1500 low quality]
    end

    subgraph "Training"
        GOOD --> SPLIT[Split 80/10/10<br/>Train/Val/Test]
        SPLIT --> TRAIN[Fine-tune Student<br/>GPT-4o-mini / Llama-8B]
        TRAIN --> STUDENT[Trained Student Model]
    end

    subgraph "Evaluation"
        STUDENT --> COMPARE[Compare on Test Set]
        TEACHER --> COMPARE
        COMPARE --> GAP{Quality Gap < 5%?}
        GAP -->|Yes| DEPLOY[Deploy Student<br/>80% of traffic]
        GAP -->|No| ITERATE[More data / training]
        ITERATE --> TRAIN
    end

    subgraph "Production"
        DEPLOY --> ROUTER[Model Router]
        TEACHER --> ROUTER
        ROUTER --> SIMPLE[Simple queries → Student<br/>80% traffic, 10x cheaper]
        ROUTER --> HARD[Complex queries → Teacher<br/>20% traffic, high quality]
    end

    style TEACHER fill:#f472b6,color:#fff
    style STUDENT fill:#60a5fa,color:#fff
    style DEPLOY fill:#22c55e,color:#fff
    style SIMPLE fill:#22c55e,color:#fff
    style HARD fill:#f472b6,color:#fff
```
