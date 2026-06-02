# LLM & GenAI Architecture Decisions

> Critical architecture decisions every staff+ engineer must understand when building LLM-powered systems.

---

## Diagram 1: RAG vs Fine-tuning vs Prompt Engineering Decision

The #1 architecture decision for any LLM application.

```mermaid
flowchart TD
    Start[What does your application need?] --> Q1{Does the model already<br/>know how to do this task?}
    
    Q1 -->|Yes, just needs guidance| PE[Prompt Engineering]
    Q1 -->|No, needs new capabilities| Q2{What's missing?}
    
    Q2 --> Q3{Does it need KNOWLEDGE<br/>it doesn't have?}
    Q2 --> Q4{Does it need to BEHAVE<br/>differently?}
    
    Q3 -->|Yes| RAG[RAG - Retrieval Augmented Generation]
    Q4 -->|Yes| FT[Fine-tuning]
    Q3 -->|Yes + behavior change| BOTH[RAG + Fine-tuning]
    Q4 -->|Yes + needs knowledge| BOTH
    
    PE --> PE_Details["WHY: Cheapest, fastest iteration, no infra<br/>WHEN: GPT-4 already knows how<br/>COST: Low - just API calls<br/>LATENCY: Baseline<br/>BEST FOR: General tasks, prototyping, simple automation"]
    
    RAG --> RAG_Details["WHY: External knowledge without retraining<br/>WHEN: Company docs, recent info, domain data<br/>COST: Medium - embedding + vector DB + retrieval<br/>LATENCY: +200-500ms per query retrieval overhead<br/>DATA: Your documents, no labeling needed<br/>BEST FOR: QA over docs, support bots, search"]
    
    FT --> FT_Details["WHY: Change style, format, task behavior<br/>WHEN: Consistent format, brand voice, specific task<br/>COST: High upfront training, lower per-query<br/>DATA NEEDED: 100-10,000 labeled examples<br/>BEST FOR: Code gen in your style, classification, extraction"]
    
    BOTH --> BOTH_Details["WHY: Domain expert + current data access<br/>WHEN: Specialized behavior + evolving knowledge<br/>EXAMPLE: Medical assistant - fine-tuned on<br/>medical style + RAG for latest research"]

    %% Decision criteria
    Start --> Criteria["KEY QUESTIONS TO ASK:<br/>1. Is the knowledge static or changing? → Changing = RAG<br/>2. Do you have labeled examples? → Yes = Fine-tuning candidate<br/>3. Is output FORMAT the problem? → Fine-tuning<br/>4. Is output CONTENT the problem? → RAG<br/>5. Budget < $1000? → Prompt Engineering first"]

    style PE fill:#90EE90
    style RAG fill:#87CEEB
    style FT fill:#FFB347
    style BOTH fill:#DDA0DD
    style Criteria fill:#FFFACD
```

### Decision Checklist

```mermaid
flowchart TD
    A[Start Here] --> B{Can GPT-4 do it with<br/>a good prompt?}
    B -->|Yes| C[Use Prompt Engineering]
    B -->|No| D{Is the problem missing<br/>KNOWLEDGE or wrong BEHAVIOR?}
    D -->|Missing Knowledge| E{Is data changing frequently?}
    D -->|Wrong Behavior| F{Do you have 100+ examples?}
    D -->|Both| G[RAG + Fine-tuning]
    
    E -->|Yes, daily/weekly| H[RAG - dynamic retrieval]
    E -->|No, mostly static| I{More than 10M tokens<br/>of knowledge?}
    I -->|Yes| H
    I -->|No| J[Consider long-context window<br/>or RAG]
    
    F -->|Yes, 100-10K| K[Fine-tune]
    F -->|No| L[Prompt Engineering with<br/>few-shot examples]
    
    C --> M[Cost: ~$0.01-0.10/query]
    H --> N[Cost: ~$0.05-0.50/query]
    K --> O[Cost: $100-10K training<br/>then $0.01-0.05/query]
    G --> P[Cost: Highest but most capable]
```

---

## Diagram 2: LLM Serving Architecture Patterns

Three fundamental patterns for serving LLM inference.

### Pattern A: Direct API (Simplest)

```mermaid
sequenceDiagram
    participant U as User
    participant App as Your Application
    participant API as OpenAI/Anthropic API
    
    Note over U,API: Pattern A: Direct API Call
    Note over U,API: WHY: Simplest, no infra, pay-per-use
    Note over U,API: WHEN: Prototype, <100K req/month, no privacy concerns
    
    U->>App: Request
    Note right of App: ~10ms processing
    App->>API: POST /chat/completions
    Note right of API: ~500-2000ms generation
    API-->>App: Response (streamed)
    App-->>U: Streamed response
    
    Note over U,API: TOTAL LATENCY: 600-2500ms
    Note over U,API: COST: $1-30 per 1M tokens (model dependent)
    Note over U,API: RISK: Vendor lock-in, cost at scale, data leaves your network
```

### Pattern B: Self-hosted (Full Control)

```mermaid
sequenceDiagram
    participant U as User
    participant App as Your Application
    participant LB as Load Balancer
    participant GPU as GPU Cluster (vLLM/TGI)
    participant Cache as KV Cache
    
    Note over U,Cache: Pattern B: Self-Hosted Inference
    Note over U,Cache: WHY: Privacy, cost at scale, full customization
    Note over U,Cache: WHEN: Sensitive data, >1M req/month, fine-tuned models
    
    U->>App: Request
    App->>LB: Route request
    LB->>GPU: Forward to available GPU
    GPU->>Cache: Check prefix cache
    Cache-->>GPU: Cached KV states
    Note right of GPU: ~200-1000ms generation
    GPU-->>LB: Generated tokens
    LB-->>App: Response
    App-->>U: Streamed response
    
    Note over U,Cache: TOTAL LATENCY: 300-1500ms (faster with caching)
    Note over U,Cache: COST: $2-4/hr per A100 ≈ $0.12/M tokens
    Note over U,Cache: RISK: Ops burden, need ML infra team, GPU availability
```

### Pattern C: Hybrid Router (Best of Both)

```mermaid
sequenceDiagram
    participant U as User
    participant App as Your Application
    participant R as Complexity Router
    participant Small as Local Small Model (7B)
    participant Large as GPT-4 API
    
    Note over U,Large: Pattern C: Hybrid Routing
    Note over U,Large: WHY: 80% of queries don't need GPT-4
    Note over U,Large: WHEN: Mixed complexity, cost-sensitive
    
    U->>App: Request
    App->>R: Classify query complexity
    Note right of R: ~20ms classification
    
    alt Simple query (80% of traffic)
        R->>Small: Route to local 7B model
        Note right of Small: ~100-300ms (fast, cheap)
        Small-->>App: Response
        Note over R,Small: COST: ~$0.01/M tokens
    else Complex query (20% of traffic)
        R->>Large: Route to GPT-4
        Note right of Large: ~1000-3000ms (powerful)
        Large-->>App: Response
        Note over R,Large: COST: ~$30/M tokens
    end
    
    App-->>U: Response
    
    Note over U,Large: BLENDED COST: 80% × $0.01 + 20% × $30 = ~$6/M tokens
    Note over U,Large: vs ALL GPT-4: $30/M tokens (5x savings!)
```

---

## Diagram 3: RAG Architecture Deep Dive

Complete RAG pipeline with decision points at every stage.

```mermaid
flowchart TD
    subgraph Ingestion["Document Ingestion Pipeline"]
        Docs[Raw Documents] --> Loader[Document Loader]
        Loader --> Chunk[Chunking Strategy]
        
        Chunk --> C1["Fixed Size (512 tokens)<br/>WHY: Predictable context usage<br/>WHEN: Uniform docs, simple setup"]
        Chunk --> C2["Semantic (paragraph/section)<br/>WHY: Don't split mid-thought<br/>WHEN: Well-structured docs"]
        Chunk --> C3["Recursive (by hierarchy)<br/>WHY: Respects document structure<br/>WHEN: Mixed doc types - RECOMMENDED START"]
        
        C1 & C2 & C3 --> Embed[Embedding Model]
        
        Embed --> E1["OpenAI ada-002<br/>WHY: Best effort/quality ratio<br/>COST: $0.10/M tokens"]
        Embed --> E2["Cohere embed-v3<br/>WHY: 100+ languages<br/>WHEN: Multilingual corpus"]
        Embed --> E3["BGE/E5 (self-hosted)<br/>WHY: No API dependency<br/>WHEN: >10M docs OR privacy required"]
        
        E1 & E2 & E3 --> VectorDB[Vector Store]
    end
    
    subgraph Storage["Vector Store Selection"]
        VectorDB --> V1["Pgvector<br/>WHY: No new infra if using Postgres<br/>WHEN: <1M vectors, already have PG"]
        VectorDB --> V2["Pinecone<br/>WHY: Zero ops, scales easily<br/>WHEN: Need managed, scaling fast"]
        VectorDB --> V3["Weaviate<br/>WHY: BM25 + vector built-in<br/>WHEN: Need hybrid search natively"]
        VectorDB --> V4["FAISS (in-memory)<br/>WHY: Sub-ms latency<br/>WHEN: Small dataset, max speed"]
    end
    
    subgraph Retrieval["Retrieval Strategy"]
        Query[User Query] --> QE[Query Embedding]
        QE --> R1["Naive Top-K<br/>WHY: Simple baseline"]
        QE --> R2["Hybrid BM25 + Vector<br/>WHY: Keywords + semantic = better recall<br/>PRODUCTION STANDARD"]
        QE --> R3["Multi-Query Expansion<br/>WHY: Catches different phrasings"]
        
        R1 & R2 & R3 --> Rerank["Re-ranking (Cross-Encoder)<br/>WHY: More accurate final ordering<br/>COST: +50-100ms latency"]
        Rerank --> Context[Retrieved Context]
    end
    
    subgraph Generation["Generation"]
        Context --> Prompt[Construct Prompt<br/>System + Context + Query]
        Prompt --> LLM[LLM Generation]
        LLM --> Verify["Citation Verification<br/>WHY: Detect hallucination"]
        Verify --> Response[Final Response]
    end

    style C3 fill:#90EE90
    style R2 fill:#90EE90
    style Rerank fill:#90EE90
```

---

## Diagram 4: LLM Agent Architecture Patterns

Progressive complexity levels for LLM agents.

```mermaid
flowchart TD
    subgraph L1["Level 1: Single-Turn Tool Use"]
        L1_Flow["User Query → LLM picks tool → Execute → Return result"]
        L1_Why["WHY: Simplest, deterministic, easy to debug"]
        L1_Ex["EXAMPLE: 'Calculate 25% of 500' → calculator tool"]
        L1_When["WHEN: Single-step tasks, function calling"]
    end
    
    subgraph L2["Level 2: Multi-Turn ReAct Loop"]
        L2_Flow["Query → Think → Act → Observe → Think → ... → Answer"]
        L2_Why["WHY: Multi-step reasoning with tool use"]
        L2_Ex["EXAMPLE: Research needing multiple web searches"]
        L2_When["WHEN: 2-5 step tasks, exploration needed"]
        L2_Risk["RISK: Can loop indefinitely - add max_steps"]
    end
    
    subgraph L3["Level 3: Planning + Execution"]
        L3_Flow["Query → Planner LLM → Plan → Executor → Step-by-step → Verify"]
        L3_Why["WHY: Complex tasks need upfront planning"]
        L3_Ex["EXAMPLE: 'Book a trip' - flights + hotel + car"]
        L3_When["WHEN: 5+ steps, dependencies between steps"]
        L3_Arch["ARCHITECTURE: Separate planner & executor models"]
    end
    
    subgraph L4["Level 4: Multi-Agent Collaboration"]
        L4_Flow["Orchestrator → Specialist Agents → Merge Results"]
        L4_Why["WHY: Different expertise for subtasks"]
        L4_Ex["EXAMPLE: Coder + Reviewer + Tester agents"]
        L4_When["WHEN: Tasks needing diverse skills"]
        L4_Pattern["PATTERNS: Debate, delegation, pipeline"]
    end
    
    subgraph L5["Level 5: Autonomous Agents"]
        L5_Flow["Goal → Plan → Execute → Self-correct → Iterate"]
        L5_Why["WHY: Minimal human oversight"]
        L5_Risk["RISKS: Hallucination loops, cost explosion, safety"]
        L5_Guard["GUARDRAILS NEEDED:<br/>- Budget limits ($X max per task)<br/>- Action approval for destructive ops<br/>- Sandboxed execution<br/>- Human-in-the-loop checkpoints"]
    end
    
    L1 -->|Need multi-step| L2
    L2 -->|Need planning| L3
    L3 -->|Need specialization| L4
    L4 -->|Need autonomy| L5
    
    Decision["CHOOSE LOWEST LEVEL THAT WORKS<br/>WHY: Each level adds latency, cost, and failure modes"]
    
    style L1 fill:#90EE90
    style L5 fill:#FFB3B3
    style Decision fill:#FFFACD
```

---

## Diagram 5: LLM Cost Optimization Decision Tree

```mermaid
flowchart TD
    Start["Your LLM costs are too high"] --> A[Reduce Token Count]
    Start --> B[Use Smaller Models]
    Start --> C[Caching]
    Start --> D[Batching]
    Start --> E[Self-Hosting Economics]
    
    A --> A1["Shorter prompts<br/>WHY: Cost directly proportional to tokens<br/>Often prompts are 10x longer than needed"]
    A --> A2["Summarize RAG context before sending<br/>WHY: Retrieval often returns too much<br/>SAVINGS: 50-70% token reduction"]
    A --> A3["Cache/reuse system prompts<br/>WHY: Same prefix = wasted computation<br/>OpenAI prompt caching: 50% discount"]
    
    B --> B1["Classification → Fine-tuned small model<br/>WHY: GPT-4 is 30x price of GPT-3.5<br/>A fine-tuned 7B often matches GPT-4 on narrow tasks"]
    B --> B2["Extraction → Regex or small model<br/>WHY: Structured extraction doesn't need reasoning"]
    B --> B3["Router: Classify complexity → route accordingly<br/>WHY: 80% of queries need only a small model<br/>SAVINGS: 5x cost reduction typical"]
    
    C --> C1["Semantic cache<br/>WHY: Many users ask same thing differently<br/>Similar embeddings → cached answer<br/>HIT RATE: 20-40% typical"]
    C --> C2["Exact match cache<br/>WHY: Identical prompts = instant response<br/>LATENCY: <10ms vs 500-2000ms"]
    C --> C3["Prefix caching (KV cache reuse)<br/>WHY: Saves recomputing attention for static prefix<br/>SAVINGS: 30-50% on long system prompts"]
    
    D --> D1["Batch similar requests<br/>WHY: Higher throughput, lower per-request cost<br/>OpenAI Batch API: 50% discount"]
    D --> D2["Async for non-urgent tasks<br/>WHY: Can use off-peak, batch pricing"]
    
    E --> E1["< 1M tokens/day → Use API<br/>WHY: GPU costs exceed API costs at low volume"]
    E --> E2["1-100M tokens/day → Consider self-host with vLLM<br/>BREAK-EVEN: ~5M tokens/day for 7B model"]
    E --> E3["100M+ tokens/day → Definitely self-host<br/>WHY: 5-10x cheaper than API"]
    E --> E4["MATH: 1x A100 at $2/hr<br/>≈ 200 tok/sec ≈ 17M tokens/day<br/>= $0.12/M tokens<br/>vs GPT-4: $30/M input tokens<br/>= 250x cheaper for same throughput!"]
    
    style B3 fill:#90EE90
    style C1 fill:#90EE90
    style E4 fill:#FFFACD
```

---

## Diagram 6: LLM Safety & Guardrails Architecture

```mermaid
sequenceDiagram
    participant User
    participant InputGuard as Input Guardrails
    participant LLM as LLM
    participant OutputGuard as Output Guardrails
    participant Log as Logging & Monitoring
    participant HR as Human Review Queue

    User->>InputGuard: User message
    
    Note over InputGuard: CHECK 1: PII Detection<br/>Strip SSN, credit cards, emails
    Note over InputGuard: CHECK 2: Prompt Injection<br/>Pattern matching + classifier
    Note over InputGuard: CHECK 3: Topic Allowlist<br/>Is this within scope?
    Note over InputGuard: CHECK 4: Rate limiting<br/>Abuse prevention
    
    alt Blocked by input guard
        InputGuard-->>User: "I can't help with that"
        InputGuard->>Log: Log: blocked input, reason, user_id
    else Passes input guard
        InputGuard->>LLM: Sanitized input + system prompt + guardrail instructions
        Note over LLM: Generation with<br/>constrained system prompt
        LLM->>OutputGuard: Raw LLM response
        
        Note over OutputGuard: CHECK 1: Hallucination<br/>Are claims supported by context?
        Note over OutputGuard: CHECK 2: Harmful content<br/>Toxicity classifier
        Note over OutputGuard: CHECK 3: PII leakage<br/>Model might reveal training data
        Note over OutputGuard: CHECK 4: Confidence threshold<br/>Is model uncertain? Add disclaimer
        Note over OutputGuard: CHECK 5: Format compliance<br/>Does output match expected schema?
        
        alt Blocked by output guard
            OutputGuard-->>User: Sanitized/rephrased response
            OutputGuard->>Log: Log: blocked output, original, reason
        else Low confidence
            OutputGuard-->>User: Response + "I'm not fully certain..."
            OutputGuard->>Log: Log: low confidence response
        else Passes all checks
            OutputGuard-->>User: Final response
            OutputGuard->>Log: Log: successful response
        end
    end
    
    Note over Log: WHY full logging:<br/>1. Audit trail for compliance<br/>2. Improve guards over time<br/>3. Detect emerging attack patterns<br/>4. Track quality metrics
    
    Log->>HR: Sample 1-5% for quality review
    Note over HR: Human reviewers check:<br/>- Factual accuracy<br/>- Appropriate tone<br/>- Guard effectiveness<br/>- Edge cases missed
```

---

## Diagram 7: Embedding & Vector Search Architecture

```mermaid
flowchart LR
    subgraph IndexSelection["Index Strategy by Vector Count"]
        Count["How many vectors?"] --> S1["< 10K: Brute Force<br/>WHY: Fast enough, exact results<br/>LATENCY: <5ms<br/>RAM: Minimal"]
        Count --> S2["10K-1M: HNSW<br/>WHY: Fast, high recall, in-memory<br/>PARAMS: M=16, ef=200<br/>LATENCY: <10ms<br/>RAM: 4KB × N vectors<br/>1M vectors = 4GB RAM"]
        Count --> S3["1M-100M: IVF + PQ<br/>WHY: Disk-friendly, lower memory<br/>IVF: Clusters for coarse search<br/>PQ: Compresses vectors 4-8x<br/>TRADEOFF: Lower recall, needs training<br/>LATENCY: 10-50ms"]
        Count --> S4["> 100M: Distributed Cluster<br/>Pinecone / Milvus / Qdrant<br/>WHY: Can't fit in single machine<br/>LATENCY: 20-100ms"]
    end
    
    subgraph HybridSearch["Hybrid Search Architecture"]
        Query[User Query] --> Vec[Vector Search<br/>Finds: semantic similarity<br/>Catches: paraphrases, concepts]
        Query --> BM25[BM25 / Keyword Search<br/>Finds: exact term matches<br/>Catches: names, codes, acronyms]
        
        Vec --> Fusion["RRF: Reciprocal Rank Fusion<br/>WHY: Simple, no training needed<br/>Formula: 1/(k + rank)<br/>RESULT: +10-15% recall vs either alone"]
        BM25 --> Fusion
        
        Fusion --> Rerank["Cross-Encoder Re-ranking<br/>WHY: Most accurate ordering<br/>COST: +50-100ms<br/>Only re-rank top 20-50 results"]
        Rerank --> Final[Final Top-K Results]
    end
    
    subgraph Dimensions["Embedding Dimensions Trade-off"]
        Dim["Dimension choice"] --> D1["384d: Fast, small, good for simple tasks"]
        Dim --> D2["768d: Balanced - RECOMMENDED"]
        Dim --> D3["1536d: OpenAI ada-002, high quality"]
        Dim --> D4["3072d: Diminishing returns for most use cases"]
    end

    style S2 fill:#90EE90
    style Fusion fill:#90EE90
    style D2 fill:#90EE90
```

---

## Diagram 8: LLM Evaluation Framework

```mermaid
flowchart TD
    Start["What are you evaluating?"] --> Factual
    Start --> Relevance
    Start --> Safety
    Start --> RAGEval["RAG-Specific"]
    Start --> AgentEval["Agent-Specific"]
    
    subgraph Factual["Factual Accuracy"]
        F1["Exact Match / F1 Score<br/>WHEN: Extractive QA with ground truth"]
        F2["LLM-as-Judge<br/>'Is this factually correct given context?'<br/>WHY: Scales better than human eval<br/>COST: 2x LLM calls per evaluation"]
        F3["Citation Verification<br/>Does response cite retrievable sources?"]
    end
    
    subgraph Relevance["Response Relevance"]
        R1["Human Evaluation<br/>Gold standard but expensive<br/>WHEN: Launch decisions, benchmarking"]
        R2["LLM-as-Judge with Rubric<br/>Structured scoring criteria<br/>WHY: Reproducible, cheap, correlates with human"]
        R3["User Feedback (thumbs up/down)<br/>WHY: Real signal, but noisy and sparse"]
    end
    
    subgraph Safety["Safety & Harmlessness"]
        S1["Red-teaming<br/>Adversarial prompts to find failures"]
        S2["Toxicity Classifiers<br/>Perspective API, custom models"]
        S3["PII Detection<br/>Regex + NER models"]
        S4["Bias Testing<br/>Demographic parity in outputs"]
    end
    
    subgraph RAGEval["RAG Evaluation Metrics"]
        RAG1["Retrieval Quality:<br/>Precision@K, Recall@K, MRR, NDCG"]
        RAG2["Faithfulness:<br/>Does answer match retrieved context?<br/>NOT hallucinating beyond sources"]
        RAG3["Answer Relevance:<br/>Does it actually address the question?"]
        RAG4["Context Relevance:<br/>Were the RIGHT chunks retrieved?"]
        RAG5["RAGAS Framework:<br/>Automates all above with LLM-as-judge"]
    end
    
    subgraph AgentEval["Agent Evaluation"]
        A1["Task Completion Rate<br/>Did it achieve the goal?"]
        A2["Tool Selection Accuracy<br/>Did it pick the right tools?"]
        A3["Step Efficiency<br/># of steps vs optimal path"]
        A4["Cost per Task<br/>Total tokens × price"]
        A5["Error Recovery<br/>Does it self-correct on failure?"]
    end
    
    KeyInsight["KEY INSIGHT: Build eval suite BEFORE building the system<br/>WHY: Without eval, you cannot measure if changes improve or degrade<br/>MINIMUM: 50-100 test cases covering edge cases<br/>RUN: On every prompt change, model change, or pipeline change"]
    
    style KeyInsight fill:#FFB3B3
    style RAG5 fill:#90EE90
```

---

## Summary: Architecture Decision Quick Reference

| Decision | Default Choice | Switch When |
|----------|---------------|-------------|
| RAG vs Fine-tune | RAG first | Need behavior change, have labeled data |
| Serving | API (OpenAI) | >1M req/month or privacy requirements |
| Vector DB | Pgvector | >1M vectors → Pinecone/Weaviate |
| Chunking | Recursive | Benchmarks show fixed is better for your docs |
| Retrieval | Hybrid + Re-rank | Latency-critical → skip re-ranking |
| Agent level | Lowest that works | Proven need for more autonomy |
| Eval | LLM-as-Judge + RAGAS | High stakes → add human eval |
| Cost | Router + Cache | Predictable load → self-host |
