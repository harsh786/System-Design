# Inference Economics - Diagrams

## 1. KV Cache Memory Management (PagedAttention)

```mermaid
graph TB
    subgraph "Physical GPU Memory (Block Pool)"
        B0[Block 0<br/>16 tokens]
        B1[Block 1<br/>16 tokens]
        B2[Block 2<br/>16 tokens]
        B3[Block 3<br/>16 tokens]
        B4[Block 4<br/>16 tokens]
        B5[Block 5<br/>16 tokens]
        B6[Block 6<br/>FREE]
        B7[Block 7<br/>FREE]
    end

    subgraph "Sequence A (45 tokens)"
        A_BT[Block Table A]
        A_BT --> B0
        A_BT --> B1
        A_BT --> B2
    end

    subgraph "Sequence B (shared prefix + 20 unique)"
        B_BT[Block Table B]
        B_BT --> B0
        B_BT --> B1
        B_BT --> B3
    end

    subgraph "Sequence C (28 tokens)"
        C_BT[Block Table C]
        C_BT --> B4
        C_BT --> B5
    end

    style B0 fill:#f9a825
    style B1 fill:#f9a825
    style B6 fill:#c8e6c9
    style B7 fill:#c8e6c9

    note1[B0, B1 shared via<br/>Copy-on-Write<br/>ref_count = 2]
```

## 2. Continuous Batching Timeline

```mermaid
gantt
    title Continuous Batching - Iteration-Level Scheduling
    dateFormat X
    axisFormat %s

    section Request A
    Prefill (500 tok)    :a1, 0, 1
    Decode (50 tok)      :a2, 1, 3
    Complete ✓           :milestone, 3, 0

    section Request B
    Prefill (200 tok)    :b1, 0, 1
    Decode (200 tok)     :b2, 1, 7
    Complete ✓           :milestone, 7, 0

    section Request C
    Queue (waiting)      :c0, 0, 3
    Prefill (300 tok)    :c1, 3, 4
    Decode (80 tok)      :c2, 4, 6
    Complete ✓           :milestone, 6, 0

    section Request D
    Queue (waiting)      :d0, 0, 6
    Prefill (100 tok)    :d1, 6, 7
    Decode (30 tok)      :d2, 7, 8
    Complete ✓           :milestone, 8, 0

    section GPU Batch
    [A,B] batch=2        :g1, 0, 3
    [B,C] batch=2        :g2, 3, 6
    [B,D] batch=2        :g3, 6, 7
    [D] batch=1          :g4, 7, 8
```

## 3. Tensor Parallelism vs Pipeline Parallelism

```mermaid
graph LR
    subgraph "Tensor Parallelism (TP=4)"
        direction TB
        subgraph "Layer N"
            TP0["GPU 0<br/>Heads 0-15<br/>FFN slice 0"]
            TP1["GPU 1<br/>Heads 16-31<br/>FFN slice 1"]
            TP2["GPU 2<br/>Heads 32-47<br/>FFN slice 2"]
            TP3["GPU 3<br/>Heads 48-63<br/>FFN slice 3"]
        end
        TP0 <-->|"AllReduce<br/>(NVLink)"| TP1
        TP1 <-->|"AllReduce"| TP2
        TP2 <-->|"AllReduce"| TP3
    end

    subgraph "Pipeline Parallelism (PP=4)"
        direction TB
        PP0["GPU 0<br/>Layers 0-19"] -->|"Activations"| PP1["GPU 1<br/>Layers 20-39"]
        PP1 -->|"Activations"| PP2["GPU 2<br/>Layers 40-59"]
        PP2 -->|"Activations"| PP3["GPU 3<br/>Layers 60-79"]
    end
```

## 4. GPU Serving Architecture

```mermaid
graph TB
    Client[Client Requests] --> LB[Load Balancer<br/>Token-aware routing]
    
    LB --> Router[Model Router<br/>Complexity classifier]
    
    Router -->|"Simple tasks"| Small[Small Model Pool<br/>8B INT4 × 4 replicas<br/>A10G GPUs]
    Router -->|"Complex tasks"| Large[Large Model Pool<br/>70B INT4 × 8 replicas<br/>H100 GPUs]
    Router -->|"Embeddings"| Embed[Embedding Pool<br/>Dedicated × 2 replicas]
    
    subgraph "Inference Server (per replica)"
        direction TB
        Sched[Request Scheduler<br/>Priority + Fair-share]
        Sched --> Engine[Continuous Batching Engine]
        Engine --> KV[PagedAttention<br/>KV Cache Manager]
        Engine --> LoRA[Multi-LoRA<br/>Adapter Manager]
        Engine --> GPU[GPU Execution<br/>FlashAttention + CUDA Graphs]
    end
    
    Large --> Sched
    
    subgraph "Supporting Infrastructure"
        Cache[(Prefix Cache<br/>RadixAttention)]
        Metrics[Prometheus<br/>Metrics]
        Scaler[Auto-Scaler<br/>Token/s based]
    end
    
    Engine --> Cache
    Engine --> Metrics
    Metrics --> Scaler
    Scaler -->|"Scale up/down"| Large
    Scaler -->|"Scale up/down"| Small
```

## 5. Cost Breakdown Waterfall

```mermaid
graph LR
    subgraph "Cost Per Request: $0.031"
        direction TB
        A["LLM Output<br/>$0.0075<br/>(24.2%)"] 
        B["Reranker<br/>$0.010<br/>(32.3%)"]
        C["LLM Input<br/>$0.009<br/>(29.0%)"]
        D["Tool Calls<br/>$0.002<br/>(6.5%)"]
        E["Infrastructure<br/>$0.002<br/>(6.5%)"]
        F["Embedding<br/>$0.000005"]
        G["Vector DB<br/>$0.000004"]
        H["Observability<br/>$0.0001"]
    end
    
    style B fill:#e53935,color:#fff
    style C fill:#fb8c00
    style A fill:#fb8c00
    style D fill:#fdd835
    style E fill:#fdd835
```

```mermaid
pie title Cost Distribution Per Request ($0.031)
    "Reranker" : 32.3
    "LLM Input" : 29.0
    "LLM Output" : 24.2
    "Tool Calls" : 6.5
    "Infrastructure" : 6.5
    "Other" : 1.5
```

## 6. Self-Hosted vs Managed Decision Tree

```mermaid
flowchart TD
    Start[Monthly AI spend?] -->|"< $5K"| Managed1[Use Managed APIs<br/>Not worth the ops overhead]
    Start -->|"$5K - $50K"| Q1{Need custom models<br/>or data privacy?}
    Start -->|"> $50K"| Q2{Load pattern?}
    
    Q1 -->|No| Managed2[Use Managed APIs<br/>Flexibility > cost savings]
    Q1 -->|Yes| Hybrid[Hybrid Approach<br/>Self-host sensitive workloads<br/>API for burst/experimentation]
    
    Q2 -->|"Steady (>60% util)"| Q3{Have GPU expertise?}
    Q2 -->|"Bursty (10x peaks)"| Q4{Peak duration?}
    
    Q3 -->|Yes| SelfHost[Self-Host<br/>30-50% cheaper at scale]
    Q3 -->|No| ManagedScale[Managed + Reserved<br/>Committed use discounts]
    
    Q4 -->|"< 2 hours"| BurstManaged[Managed for bursts<br/>Self-host for baseline]
    Q4 -->|"> 2 hours"| AutoScale[Self-host with<br/>aggressive autoscaling]
    
    style Managed1 fill:#4caf50,color:#fff
    style Managed2 fill:#4caf50,color:#fff
    style SelfHost fill:#2196f3,color:#fff
    style Hybrid fill:#ff9800,color:#fff
    style BurstManaged fill:#ff9800,color:#fff
```

## 7. Inference Optimization Loop

```mermaid
flowchart TD
    Measure[📊 Measure<br/>- Cost per request<br/>- Latency P50/P99<br/>- Throughput tok/s<br/>- GPU utilization<br/>- Quality scores]
    
    Measure --> Identify[🔍 Identify Bottleneck]
    
    Identify -->|"High cost,<br/>low complexity tasks"| Route[Model Routing<br/>Send easy tasks to<br/>small model]
    
    Identify -->|"High latency,<br/>low GPU util"| Batch[Batching Optimization<br/>Increase batch size<br/>or enable continuous batching]
    
    Identify -->|"Memory limited,<br/>can't increase batch"| Quant[Quantization<br/>INT8 → INT4<br/>Free memory for KV cache]
    
    Identify -->|"Repeated prompts,<br/>high prefill cost"| PrefixCache[Prefix Caching<br/>Cache system prompt<br/>KV blocks]
    
    Identify -->|"High latency,<br/>sequential decoding"| SpecDec[Speculative Decoding<br/>Draft model +<br/>parallel verification]
    
    Identify -->|"Large prompts,<br/>high input cost"| Compress[Prompt Compression<br/>LLMLingua or<br/>structured formats]
    
    Route --> Validate[✅ Validate<br/>- Quality maintained?<br/>- Cost reduced?<br/>- SLOs met?]
    Batch --> Validate
    Quant --> Validate
    PrefixCache --> Validate
    SpecDec --> Validate
    Compress --> Validate
    
    Validate -->|"Quality dropped"| Rollback[↩️ Rollback]
    Validate -->|"Success"| Deploy[🚀 Deploy to Prod]
    
    Deploy --> Measure
    Rollback --> Measure
```

## 8. Auto-Scaling Architecture

```mermaid
graph TB
    subgraph "Metrics Pipeline"
        GPU_Metrics[GPU Metrics<br/>DCGM Exporter] --> Prometheus[(Prometheus)]
        App_Metrics[App Metrics<br/>- queue_depth<br/>- tokens/sec<br/>- latency_p99] --> Prometheus
        Prometheus --> Evaluator
    end
    
    subgraph "Scaling Controller"
        Evaluator[Scaling Evaluator<br/>Multi-signal decision]
        Evaluator -->|"Scale Up"| ScaleUp[Scale Up Logic<br/>- Provision GPU instance<br/>- Download model<br/>- Load to GPU<br/>- Warmup<br/>- Add to pool]
        Evaluator -->|"Scale Down"| ScaleDown[Scale Down Logic<br/>- Drain connections<br/>- Wait for in-flight<br/>- Remove from pool<br/>- Terminate instance]
        Evaluator -->|"No Action"| Wait[Wait & Re-evaluate<br/>every 30s]
    end
    
    subgraph "Scaling Signals"
        S1["tokens_per_sec_demand /<br/>tokens_per_sec_capacity > 0.8"]
        S2["queue_depth > 100<br/>AND growing"]
        S3["p99_latency ><br/>SLO × 0.9"]
        S4["gpu_util < 0.3<br/>for > 5 min"]
    end
    
    S1 -->|"Scale UP"| Evaluator
    S2 -->|"Scale UP"| Evaluator
    S3 -->|"Scale UP"| Evaluator
    S4 -->|"Scale DOWN"| Evaluator
    
    subgraph "Constraints"
        C1[Min replicas: 2]
        C2[Max replicas: 16]
        C3[Cooldown: 2 min up, 5 min down]
        C4[Budget cap: $X/hour]
    end
    
    Evaluator -.-> C1
    Evaluator -.-> C2
    Evaluator -.-> C3
    Evaluator -.-> C4
```

## 9. Multi-Model Serving Topology

```mermaid
graph TB
    subgraph "Request Ingress"
        API[API Gateway] --> Classifier[Task Complexity<br/>Classifier<br/>(lightweight rules/model)]
    end
    
    subgraph "GPU Node 1 (8× H100)"
        direction TB
        N1_M1["GPU 0-3: LLaMA-70B INT4<br/>+ 15 LoRA adapters<br/>TP=4"]
        N1_M2["GPU 4-5: LLaMA-70B INT4<br/>Replica 2, TP=2"]
        N1_M3["GPU 6: Embedding Model<br/>+ Reranker"]
        N1_M4["GPU 7: Draft Model (7B)<br/>for speculative decoding"]
    end
    
    subgraph "GPU Node 2 (8× A100)"
        direction TB
        N2_M1["GPU 0-3: Mixtral-8x7B<br/>TP=4 (medium tasks)"]
        N2_M2["GPU 4-7: LLaMA-8B × 4<br/>One per GPU (simple tasks)"]
    end
    
    subgraph "Fallback (API)"
        F1[OpenAI GPT-4o<br/>Primary fallback]
        F2[Anthropic Claude<br/>Secondary fallback]
    end
    
    Classifier -->|"Complex"| N1_M1
    Classifier -->|"Complex (overflow)"| N1_M2
    Classifier -->|"Medium"| N2_M1
    Classifier -->|"Simple"| N2_M2
    Classifier -->|"Embedding/Rerank"| N1_M3
    
    N1_M1 -->|"Timeout/Error"| F1
    N1_M2 -->|"Timeout/Error"| F1
    F1 -->|"Rate limited"| F2
    
    N1_M4 -.->|"Speculative<br/>drafts"| N1_M1
```

## 10. Speculative Decoding Flow

```mermaid
sequenceDiagram
    participant Draft as Draft Model (1B)
    participant Target as Target Model (70B)
    participant Output as Output Buffer
    
    Note over Draft,Output: Generate 5 speculative tokens
    
    Draft->>Draft: Generate t1 (2ms)
    Draft->>Draft: Generate t2 (2ms)
    Draft->>Draft: Generate t3 (2ms)
    Draft->>Draft: Generate t4 (2ms)
    Draft->>Draft: Generate t5 (2ms)
    
    Note over Draft,Output: Total draft time: 10ms
    
    Draft->>Target: Send [t1, t2, t3, t4, t5]
    
    Note over Target: Single forward pass (30ms)<br/>Verify all 5 tokens in parallel
    
    Target->>Target: P(t1) ✓ Accept
    Target->>Target: P(t2) ✓ Accept  
    Target->>Target: P(t3) ✓ Accept
    Target->>Target: P(t4) ✗ Reject!
    Target->>Target: Resample t4' from target distribution
    
    Target->>Output: Emit [t1, t2, t3, t4']
    
    Note over Draft,Output: Result: 4 tokens in 40ms<br/>vs Standard: 4 tokens in 120ms<br/>= 3x speedup
```

## 11. GPU Memory Layout

```mermaid
graph TB
    subgraph "80GB H100 VRAM"
        direction TB
        MW["Model Weights (INT4)<br/>35 GB<br/>▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"]
        LA["LoRA Adapters (5×100MB)<br/>0.5 GB<br/>▓"]
        CUDA["CUDA/Framework Overhead<br/>1.5 GB<br/>▓▓"]
        ACT["Activation Memory<br/>1.0 GB<br/>▓▓"]
        KV["KV Cache (dynamic)<br/>38 GB<br/>▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"]
        FREE["Free / Buffer<br/>4 GB<br/>▓▓▓"]
    end
    
    style MW fill:#1565c0,color:#fff
    style LA fill:#4527a0,color:#fff
    style CUDA fill:#424242,color:#fff
    style ACT fill:#e65100,color:#fff
    style KV fill:#2e7d32,color:#fff
    style FREE fill:#c8e6c9

    KV_Detail["KV Cache supports:<br/>~28 concurrent sequences<br/>@ 4096 context length<br/>(1.34 GB per sequence)"]
    KV --> KV_Detail
```
