# Scaling Architecture — Real-World Examples

## Case Study: How ChatGPT Scales to 100M+ Users

### Inferred Architecture (Based on Public Information)

OpenAI serves ChatGPT at a scale unprecedented for generative AI:
- **100M+ weekly active users** (as of 2024)
- **10M+ concurrent sessions** at peak
- **Billions of tokens generated per day**

### Key Architectural Patterns

#### 1. Multi-Tier Inference Infrastructure

```
User Request Flow:
┌─────────┐     ┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  Client  │────▶│  Edge/CDN │────▶│  API Gateway  │────▶│ Request      │
│  (Web/   │     │  (CF)     │     │  (Rate limit, │     │ Classifier   │
│   App)   │     │           │     │   auth, route)│     │ (model/tier) │
└─────────┘     └──────────┘     └──────────────┘     └──────┬──────┘
                                                              │
                    ┌─────────────────────────────────────────┼──────────┐
                    ▼                    ▼                     ▼          │
             ┌────────────┐      ┌────────────┐       ┌────────────┐    │
             │ GPT-4 Pool  │      │ GPT-4o Pool │       │ GPT-4o-mini│    │
             │ (A100 80GB) │      │ (H100)      │       │ Pool       │    │
             │ Low throughput│    │ High throughput│    │ Highest     │    │
             └────────────┘      └────────────┘       └────────────┘    │
                                                                         │
                                                              ┌──────────▼──┐
                                                              │ Queue/Buffer │
                                                              │ (overflow)   │
                                                              └─────────────┘
```

#### 2. Request Routing & Queue Management

```python
# Conceptual model of ChatGPT's request routing
class RequestRouter:
    def route(self, request: ChatRequest) -> InferencePool:
        # Tier 1: Subscription level determines priority
        if request.user.is_plus_subscriber:
            priority = Priority.HIGH
            pool_preference = "dedicated_plus"
        else:
            priority = Priority.STANDARD
            pool_preference = "shared"
        
        # Tier 2: Model selection determines GPU pool
        model_pool = self.get_pool(request.model)
        
        # Tier 3: If preferred pool is at capacity, queue or downgrade
        if model_pool.utilization > 0.95:
            if priority == Priority.HIGH:
                # Plus users: queue with short timeout, then overflow pool
                return model_pool.queue(timeout=5_000, fallback=self.overflow_pool)
            else:
                # Free users: longer queue, possible "we're at capacity" message
                return model_pool.queue(timeout=30_000, fallback=self.capacity_error)
        
        return model_pool
```

#### 3. Streaming & Connection Management

ChatGPT uses Server-Sent Events (SSE) for token streaming. At 10M concurrent connections:
- Each connection holds ~2KB memory on the edge
- Average session: 45 seconds of active streaming
- Connection multiplexing through regional PoPs

#### 4. KV-Cache Management (The Hidden Scaling Challenge)

The biggest scaling bottleneck isn't compute — it's memory for KV-cache:
```
Per-request KV-cache memory (GPT-4 scale):
- Context: 8K tokens × 96 layers × 128 heads × 128 dim × 2 (K+V) × 2 bytes
- ≈ 6GB per active request at max context

For 10,000 concurrent requests on a single node cluster:
- 60TB of KV-cache memory needed (impossible on single machine)
- Solution: Distributed KV-cache across machines, paged attention (vLLM-style)
```

OpenAI likely uses:
- **Paged attention** to avoid memory fragmentation
- **KV-cache offloading** to CPU memory / NVMe for long contexts
- **Prefix caching** — system prompts shared across requests (huge savings)
- **Speculative decoding** for faster token generation

---

## Case Study: 100 to 100,000 Queries/Day — What Breaks at Each Scale

### Company: DocuSearch AI (Enterprise document search)

#### Stage 1: 100 queries/day (Month 1)

**Architecture:** Single FastAPI server + Pinecone + OpenAI API
```python
# This was literally production
app = FastAPI()

@app.post("/search")
async def search(query: str):
    embedding = openai.embeddings.create(input=query, model="text-embedding-3-small")
    results = pinecone_index.query(vector=embedding, top_k=5)
    answer = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"Answer based on: {results}\n\nQuestion: {query}"}]
    )
    return {"answer": answer.choices[0].message.content}
```
**What worked:** Everything. Single server, no caching, no queue. $50/month total.

#### Stage 2: 1,000 queries/day (Month 3) — First Problems

**What broke:**
- OpenAI rate limits hit during peak hours (company-wide standup → everyone asks questions simultaneously)
- Latency spikes to 15s when 20+ concurrent requests (single-threaded embedding calls)
- Cost jumped to $500/month (no caching, every query = fresh LLM call)

**Fixes:**
```python
# Added: semantic caching, rate limiting, async
from functools import lru_cache
import asyncio

class SemanticCache:
    """If a similar question was asked recently, return cached answer."""
    def __init__(self, similarity_threshold=0.95):
        self.cache = {}  # embedding -> response
        self.threshold = similarity_threshold
    
    async def get(self, query_embedding):
        for cached_emb, response in self.cache.items():
            if cosine_similarity(query_embedding, cached_emb) > self.threshold:
                return response
        return None

# Result: 40% cache hit rate, costs dropped to $300/month
```

#### Stage 3: 10,000 queries/day (Month 6) — Architecture Rewrite

**What broke:**
- Single server couldn't handle load during peaks (100+ concurrent)
- Pinecone query latency increased as index grew to 2M vectors
- Users complained about inconsistent response times (2s to 30s)
- OpenAI outage at 2 AM took down the entire service

**Fixes — first real architecture:**
```yaml
# Moved to Kubernetes with proper separation of concerns
services:
  api-gateway:
    replicas: 3
    responsibilities: auth, rate-limit, request validation
  
  embedding-service:
    replicas: 4
    responsibilities: generate embeddings, cache embeddings
    optimization: batch requests every 100ms (up to 20 queries batched)
  
  retrieval-service:
    replicas: 3
    responsibilities: vector search, reranking
    optimization: pre-filter by namespace to reduce search space
  
  generation-service:
    replicas: 5
    responsibilities: LLM calls with retry + fallback
    fallback_chain: [gpt-4o, claude-3-sonnet, gpt-4o-mini]
  
  cache:
    type: Redis Cluster
    size: 16GB
    stores: [semantic_cache, session_cache, embedding_cache]
```

#### Stage 4: 50,000 queries/day (Month 9) — Queue Architecture

**What broke:**
- Peak load: 200 concurrent requests, generation service overwhelmed
- LLM API costs: $8,000/month (even with caching)
- Some queries took 45s (complex multi-document synthesis) blocking simpler queries
- Enterprise customers complained their queries were slow during peak

**Fixes — priority queues and request classification:**
```python
class RequestClassifier:
    """Classify requests by complexity and route to appropriate queue."""
    
    def classify(self, request) -> RequestClass:
        # Simple factual lookup — fast path
        if self.is_simple_lookup(request):
            return RequestClass(
                queue="fast",
                model="gpt-4o-mini",
                timeout=5_000,
                priority=request.user.tier
            )
        
        # Multi-document synthesis — slow path
        if self.needs_multi_doc(request):
            return RequestClass(
                queue="complex",
                model="gpt-4o",
                timeout=30_000,
                priority=request.user.tier
            )
        
        # Default path
        return RequestClass(queue="standard", model="gpt-4o", timeout=15_000)

# Queue configuration
queues:
  fast:
    workers: 20
    max_latency_target: 3s
    concurrency_per_worker: 10
  standard:
    workers: 10
    max_latency_target: 10s
    concurrency_per_worker: 5
  complex:
    workers: 5
    max_latency_target: 30s
    concurrency_per_worker: 2
```

#### Stage 5: 100,000 queries/day (Month 14) — Cell Architecture

**What broke:**
- Noisy neighbor: One enterprise customer ran a bulk import that degraded everyone
- Single Redis cluster became bottleneck (thundering herd on cache misses)
- Deployment risk: one bad deploy affected all customers simultaneously

**Fix: Cell-based architecture** (see next section)

---

## Cell-Based Architecture: Customer Isolation

### Design

```
┌─────────────────────────────────────────────────────────┐
│                    Global Router                          │
│  (Routes customers to cells based on assignment table)   │
└─────────┬──────────────┬──────────────┬────────────────┘
          │              │              │
     ┌────▼────┐    ┌───▼────┐    ┌───▼────┐
     │ Cell A   │    │ Cell B  │    │ Cell C  │
     │ (US-E1)  │    │ (US-E1) │    │ (EU-W1) │
     │          │    │         │    │         │
     │ - API    │    │ - API   │    │ - API   │
     │ - Queue  │    │ - Queue │    │ - Queue │
     │ - Redis  │    │ - Redis │    │ - Redis │
     │ - Qdrant │    │ - Qdrant│    │ - Qdrant│
     │          │    │         │    │         │
     │ Tenants: │    │ Tenants:│    │ Tenants:│
     │ Acme Co  │    │ BigCorp │    │ EuroFin │
     │ StartupX │    │ MedTech │    │ DataGmbH│
     │ 48 others│    │ 45 other│    │ 30 other│
     └──────────┘    └─────────┘    └─────────┘
```

### Cell Assignment Logic

```python
class CellRouter:
    def __init__(self):
        # Cell assignment table (stored in DynamoDB for fast lookup)
        self.assignments = {}  # tenant_id -> cell_id
        self.cells = {
            "cell-a": CellConfig(region="us-east-1", capacity=50, current_load=0.72),
            "cell-b": CellConfig(region="us-east-1", capacity=50, current_load=0.65),
            "cell-c": CellConfig(region="eu-west-1", capacity=35, current_load=0.58),
        }
    
    def route(self, request: Request) -> str:
        tenant_id = request.tenant_id
        
        # Check existing assignment
        if tenant_id in self.assignments:
            cell = self.assignments[tenant_id]
            if self.cells[cell].is_healthy():
                return cell
            else:
                # Cell unhealthy — failover to backup
                return self.failover(tenant_id)
        
        # New tenant — assign to least loaded cell (with geo preference)
        return self.assign_new_tenant(tenant_id, request.geo_region)
    
    def assign_new_tenant(self, tenant_id: str, geo: str) -> str:
        """Assign to cell with matching geo and lowest utilization."""
        candidates = [c for c in self.cells.values() if c.region_matches(geo)]
        if not candidates:
            candidates = list(self.cells.values())
        
        selected = min(candidates, key=lambda c: c.current_load)
        self.assignments[tenant_id] = selected.id
        return selected.id
```

### Blast Radius Containment

Real incident that validated this architecture:
- **November 2024:** Cell B had a Qdrant node failure (disk full from uncontrolled vector writes by one tenant)
- **Impact:** Only 47 tenants in Cell B affected (10 minutes degraded search)
- **Without cells:** Would have been 100% of customers affected
- **Recovery:** Failed cell drained, tenants migrated to overflow cell in 4 minutes

---

## Backpressure: Token-Budget-Based Admission Control

### The Problem
AI requests are unpredictable in cost. A single request might need 50 tokens (cache hit) or 50,000 tokens (long document synthesis). Without admission control, a burst of expensive requests OOMs the system.

### Implementation

```python
import asyncio
import time
from dataclasses import dataclass

@dataclass
class TokenBudget:
    """Sliding window token budget for admission control."""
    max_tokens_per_second: int = 500_000  # Cluster capacity
    window_seconds: int = 10
    current_tokens: int = 0
    window_start: float = 0
    
    # Per-tier allocation
    tier_allocation: dict = None
    
    def __post_init__(self):
        self.tier_allocation = {
            "enterprise": 0.50,  # 50% of budget reserved for enterprise
            "pro": 0.30,         # 30% for pro
            "free": 0.20,        # 20% for free tier
        }
        self.window_start = time.time()

class AdmissionController:
    def __init__(self, budget: TokenBudget):
        self.budget = budget
        self.tier_usage = {"enterprise": 0, "pro": 0, "free": 0}
        self.lock = asyncio.Lock()
        self.queue = asyncio.PriorityQueue(maxsize=10_000)
    
    async def admit(self, request: InferenceRequest) -> AdmissionDecision:
        """Decide whether to admit, queue, or reject a request."""
        estimated_tokens = self.estimate_tokens(request)
        tier = request.user.tier
        
        async with self.lock:
            self._maybe_reset_window()
            
            tier_budget = self.budget.max_tokens_per_second * self.budget.tier_allocation[tier]
            tier_remaining = tier_budget * self.budget.window_seconds - self.tier_usage[tier]
            
            if estimated_tokens <= tier_remaining:
                # Admit immediately
                self.tier_usage[tier] += estimated_tokens
                return AdmissionDecision(action="admit", estimated_tokens=estimated_tokens)
            
            # Budget exceeded for this tier
            if tier == "enterprise":
                # Enterprise can borrow from free tier's unused budget
                free_remaining = (self.budget.max_tokens_per_second * 
                                 self.budget.tier_allocation["free"] * 
                                 self.budget.window_seconds - self.tier_usage["free"])
                if estimated_tokens <= tier_remaining + free_remaining:
                    self.tier_usage[tier] += estimated_tokens
                    return AdmissionDecision(action="admit", borrowed=True)
            
            if tier == "free":
                # Free tier: reject with retry-after header
                return AdmissionDecision(
                    action="reject",
                    retry_after=self._time_until_budget_reset(),
                    message="Rate limited. Upgrade to Pro for higher limits."
                )
            
            # Pro/Enterprise: queue with timeout
            return AdmissionDecision(
                action="queue",
                position=self.queue.qsize(),
                estimated_wait=self._estimate_wait_time()
            )
    
    def estimate_tokens(self, request: InferenceRequest) -> int:
        """Estimate total tokens (input + output) before execution."""
        input_tokens = len(request.messages_text) // 4  # Rough: 4 chars per token
        # Estimate output based on request type
        if request.task_type == "summary":
            estimated_output = min(input_tokens // 3, 1000)
        elif request.task_type == "generation":
            estimated_output = request.max_tokens or 2000
        else:
            estimated_output = 500
        
        return input_tokens + estimated_output
    
    def report_actual_usage(self, request_id: str, actual_tokens: int):
        """After completion, adjust budget with actual usage."""
        estimated = self.estimates[request_id]
        difference = actual_tokens - estimated
        # Adjust tier usage for accurate accounting
        self.tier_usage[self.request_tiers[request_id]] += difference
```

---

## Load Testing AI Systems

### Why Standard Load Testing Fails for AI

Traditional load testing sends identical requests. AI systems have highly variable behavior:
- A 50-token query takes 200ms; a 4000-token query takes 12s
- Tool-calling requests make 3-5x more LLM calls
- Streaming responses hold connections open for 10-30 seconds

### Realistic AI Traffic Simulation

```python
# load_test/ai_traffic_generator.py
import random
import asyncio
from locust import HttpUser, task, between

class AIUserBehavior(HttpUser):
    wait_time = between(2, 30)  # Realistic think time between queries
    
    # Distribution matching real production traffic
    QUERY_DISTRIBUTION = {
        "simple_question": 0.40,      # "What is X?" — short, fast
        "document_search": 0.25,      # RAG query — medium complexity
        "multi_turn_conversation": 0.20,  # Follow-up questions
        "complex_synthesis": 0.10,    # "Compare these 5 documents"
        "tool_use": 0.05,            # Queries requiring external tool calls
    }
    
    PROMPT_LENGTH_DISTRIBUTION = {
        "short": (50, 200, 0.35),     # (min_tokens, max_tokens, probability)
        "medium": (200, 1000, 0.40),
        "long": (1000, 4000, 0.20),
        "very_long": (4000, 16000, 0.05),
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = str(uuid.uuid4())
        self.conversation_history = []
    
    @task(40)
    def simple_question(self):
        query = random.choice(self.simple_queries)
        self.client.post("/v1/chat", json={
            "messages": [{"role": "user", "content": query}],
            "stream": True,
            "max_tokens": 500,
        }, headers={"X-Session-ID": self.session_id})
    
    @task(25)
    def document_search(self):
        """Simulates RAG query with context retrieval."""
        query = self._generate_rag_query()
        with self.client.post("/v1/chat", json={
            "messages": [{"role": "user", "content": query}],
            "stream": True,
            "max_tokens": 1500,
            "tools": [{"type": "retrieval"}],
        }, stream=True, catch_response=True) as response:
            # Consume streaming response (realistic client behavior)
            tokens_received = 0
            for chunk in response.iter_lines():
                tokens_received += 1
            if tokens_received < 10:
                response.failure("Too few tokens in response")
    
    @task(20)
    def multi_turn_conversation(self):
        """Simulates a 3-5 turn conversation."""
        turns = random.randint(3, 5)
        for i in range(turns):
            query = self._generate_followup(i)
            self.conversation_history.append({"role": "user", "content": query})
            
            response = self.client.post("/v1/chat", json={
                "messages": self.conversation_history[-10:],  # Last 10 messages
                "stream": True,
            })
            
            if response.status_code == 200:
                self.conversation_history.append({
                    "role": "assistant", 
                    "content": response.text[:500]
                })
            
            # Think time between turns
            time.sleep(random.uniform(3, 15))
    
    @task(10)
    def complex_synthesis(self):
        """Long context, expensive query."""
        # Generate a prompt with 2000-4000 tokens of context
        context = self._generate_long_context(tokens=random.randint(2000, 4000))
        self.client.post("/v1/chat", json={
            "messages": [
                {"role": "system", "content": "Synthesize the following documents."},
                {"role": "user", "content": context}
            ],
            "max_tokens": 3000,
            "stream": True,
        }, timeout=60)  # Allow longer timeout for complex queries
    
    @task(5)
    def tool_use_query(self):
        """Query that triggers tool calls (3-5 LLM roundtrips)."""
        self.client.post("/v1/chat", json={
            "messages": [{"role": "user", "content": "Search for recent news about AI regulation and summarize the key points"}],
            "tools": [
                {"type": "function", "function": {"name": "web_search"}},
                {"type": "function", "function": {"name": "summarize"}},
            ],
            "stream": True,
        }, timeout=45)
```

### Load Test Execution Plan

```yaml
# load_test/config.yaml
scenarios:
  - name: "steady_state"
    description: "Normal production traffic"
    users: 500
    spawn_rate: 10/s
    duration: 30m
    assertions:
      p50_latency: "< 3s"
      p95_latency: "< 12s"
      p99_latency: "< 25s"
      error_rate: "< 0.5%"
      
  - name: "peak_hour"
    description: "Monday 9 AM spike"
    users: 2000
    spawn_rate: 50/s
    duration: 15m
    assertions:
      p95_latency: "< 20s"
      error_rate: "< 2%"
      queue_depth: "< 500"
      
  - name: "viral_spike"
    description: "HackerNews front page scenario"
    users: 10000
    spawn_rate: 200/s
    duration: 10m
    assertions:
      availability: "> 95%"  # Accept some degradation
      enterprise_p95: "< 15s"  # Enterprise must still work
      graceful_degradation: true  # Free tier shows queue message
```

---

## Auto-Scaling: Real HPA Configurations

```yaml
# Custom metrics HPA for AI inference service
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-inference-hpa
  namespace: prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-inference
  minReplicas: 3
  maxReplicas: 30
  
  behavior:
    # Scale up aggressively (AI traffic is bursty)
    scaleUp:
      stabilizationWindowSeconds: 30   # React within 30s
      policies:
        - type: Percent
          value: 100                   # Can double pods in one step
          periodSeconds: 30
        - type: Pods
          value: 5                     # Or add 5 pods, whichever is more
          periodSeconds: 30
      selectPolicy: Max
    
    # Scale down conservatively (avoid flapping, GPU startup is slow)
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down
      policies:
        - type: Percent
          value: 25                    # Remove max 25% per step
          periodSeconds: 60
  
  metrics:
    # Metric 1: Requests per second per pod
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "50"           # Scale when avg > 50 req/s per pod
    
    # Metric 2: GPU utilization (from DCGM exporter)
    - type: Pods
      pods:
        metric:
          name: DCGM_FI_DEV_GPU_UTIL
        target:
          type: AverageValue
          averageValue: "75"           # Scale when GPU > 75% utilized
    
    # Metric 3: Queue depth (from Redis)
    - type: External
      external:
        metric:
          name: redis_queue_length
          selector:
            matchLabels:
              queue: "inference-requests"
        target:
          type: Value
          value: "100"                 # Scale when queue > 100 pending

---
# KEDA ScaledObject for more advanced scaling (alternative to HPA)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ai-inference-keda
  namespace: prod
spec:
  scaleTargetRef:
    name: ai-inference
  minReplicaCount: 3
  maxReplicaCount: 30
  cooldownPeriod: 300
  
  triggers:
    # Scale based on pending messages in queue
    - type: redis-lists
      metadata:
        address: redis-cluster.prod.svc:6379
        listName: inference-queue
        listLength: "20"       # 20 pending items per replica
        activationListLength: "5"
    
    # Scale based on Prometheus custom metric
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring.svc:9090
        metricName: ai_inference_active_requests
        query: |
          sum(ai_inference_active_requests{namespace="prod"}) / 
          count(kube_pod_info{namespace="prod", pod=~"ai-inference.*"})
        threshold: "8"         # More than 8 concurrent requests per pod
    
    # Scale based on token generation throughput
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring.svc:9090
        metricName: tokens_per_second_capacity
        query: |
          1 - (sum(rate(ai_tokens_generated_total[2m])) / 
               (count(kube_pod_info{pod=~"ai-inference.*"}) * 200))
        threshold: "0.2"       # Scale when less than 20% capacity remaining
```

---

## Capacity Planning: Forecasting GPU Needs

### Real Capacity Planning Spreadsheet Logic

```python
class GPUCapacityPlanner:
    """Forecasts GPU needs for next quarter based on growth and model changes."""
    
    def __init__(self):
        # Historical data
        self.monthly_queries = [100_000, 150_000, 210_000, 310_000, 420_000, 580_000]
        self.avg_tokens_per_query = [1800, 1900, 2100, 2200, 2400, 2500]  # Growing as users send longer queries
        
        # GPU performance baselines (measured)
        self.gpu_specs = {
            "A100_80GB": {
                "tokens_per_second": 2000,    # With batching, Llama-3-70B
                "max_batch_size": 32,
                "cost_per_hour_ondemand": 3.67,
                "cost_per_hour_reserved": 2.20,
                "cost_per_hour_spot": 1.10,
            },
            "H100_80GB": {
                "tokens_per_second": 4500,
                "max_batch_size": 64,
                "cost_per_hour_ondemand": 5.12,
                "cost_per_hour_reserved": 3.07,
                "cost_per_hour_spot": 1.80,
            }
        }
    
    def forecast_next_quarter(self) -> CapacityPlan:
        # 1. Project query volume (fit growth curve)
        growth_rate = self._calculate_growth_rate()  # ~40% MoM
        projected_daily_queries = {
            "month_1": self.monthly_queries[-1] * (1 + growth_rate) / 30,
            "month_2": self.monthly_queries[-1] * (1 + growth_rate)**2 / 30,
            "month_3": self.monthly_queries[-1] * (1 + growth_rate)**3 / 30,
        }
        # Month 3 projection: 580K * 1.4^3 = 1,590,000 queries/month = 53K/day
        
        # 2. Account for model upgrade (Llama-3-70B → Llama-3.1-405B)
        # 405B needs 4x more compute per token than 70B
        model_multiplier = 4.0  # If upgrading to larger model
        # OR: model_multiplier = 0.7 if new model is more efficient
        
        # 3. Calculate peak tokens per second needed
        peak_multiplier = 3.0  # Peak is 3x average
        avg_tokens_per_second = (
            projected_daily_queries["month_3"] * 2600 / 86400  # 2600 avg tokens at month 3
        )
        peak_tokens_per_second = avg_tokens_per_second * peak_multiplier * model_multiplier
        # = (53,000 * 2,600 / 86,400) * 3 * 4 = 19,167 tokens/sec peak
        
        # 4. Calculate GPUs needed
        gpu_type = "H100_80GB"
        gpus_needed = peak_tokens_per_second / self.gpu_specs[gpu_type]["tokens_per_second"]
        # = 19,167 / 4,500 ≈ 4.3 → round up to 5 GPUs
        
        # 5. Add headroom (20% for unexpected spikes + 1 for redundancy)
        gpus_with_headroom = int(gpus_needed * 1.2) + 1  # = 7 GPUs
        
        # 6. Cost projection
        hours_per_month = 730
        monthly_cost_reserved = gpus_with_headroom * self.gpu_specs[gpu_type]["cost_per_hour_reserved"] * hours_per_month
        # = 7 * $3.07 * 730 = $15,687/month
        
        return CapacityPlan(
            gpus_needed=gpus_with_headroom,
            gpu_type=gpu_type,
            monthly_cost=monthly_cost_reserved,
            procurement_action="Reserve 5 H100s now, keep 2 on-demand for burst",
            lead_time="Reserve instances: apply 2 weeks ahead",
            risk_factors=[
                "If growth exceeds 50% MoM, need 9 GPUs",
                "Model upgrade may need 4-node tensor parallel (16 GPUs)",
                "Spot interruption rate for H100: ~15% — don't rely on spot for real-time",
            ]
        )
```

---

## Rate Limiting at Scale: Real Comparison

### Token Bucket (Best for Steady-State AI Traffic)

```python
class TokenBucketRateLimiter:
    """
    Best for: API endpoints where you want to allow bursts but enforce average rate.
    Used by: OpenAI, Anthropic for their API rate limits.
    """
    def __init__(self, tokens_per_minute: int, burst_size: int):
        self.rate = tokens_per_minute / 60.0  # Tokens added per second
        self.burst = burst_size
        self.tokens = burst_size  # Start full
        self.last_refill = time.time()
    
    def allow(self, token_cost: int) -> tuple[bool, dict]:
        self._refill()
        if self.tokens >= token_cost:
            self.tokens -= token_cost
            return True, {"remaining": self.tokens, "reset_in": self._time_to_full()}
        return False, {
            "retry_after": (token_cost - self.tokens) / self.rate,
            "limit": self.burst
        }
    
    # Pro: Simple, allows bursts, predictable
    # Con: Doesn't adapt to system health
```

### Sliding Window (Best for Per-User Fairness)

```python
class SlidingWindowLimiter:
    """
    Best for: Fair per-user limits that don't allow gaming at window boundaries.
    Used by: Stripe, many SaaS platforms.
    """
    def __init__(self, redis_client, window_seconds: int = 60, max_requests: int = 100):
        self.redis = redis_client
        self.window = window_seconds
        self.max = max_requests
    
    async def allow(self, user_id: str) -> bool:
        now = time.time()
        window_start = now - self.window
        key = f"ratelimit:{user_id}"
        
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
        pipe.zcard(key)                               # Count current window
        pipe.zadd(key, {str(now): now})               # Add current request
        pipe.expire(key, self.window)                 # Auto-cleanup
        results = await pipe.execute()
        
        current_count = results[1]
        return current_count < self.max
    
    # Pro: Precise, no boundary gaming
    # Con: Redis memory per user, higher latency
```

### Adaptive Rate Limiting (Best for AI Systems)

```python
class AdaptiveRateLimiter:
    """
    Best for: AI systems where capacity varies based on:
    - Current GPU utilization
    - Queue depth
    - Model serving latency
    - Provider rate limits (upstream)
    
    Dynamically adjusts limits based on system health.
    """
    def __init__(self):
        self.base_rate = 1000  # requests/min baseline
        self.current_rate = self.base_rate
        self.health_check_interval = 5  # seconds
    
    async def adjust_rates(self):
        """Called every 5 seconds to adjust based on system state."""
        metrics = await self.get_system_metrics()
        
        # Factor 1: GPU utilization
        gpu_factor = 1.0
        if metrics.gpu_utilization > 0.90:
            gpu_factor = 0.5   # Cut rate in half when GPU saturated
        elif metrics.gpu_utilization > 0.80:
            gpu_factor = 0.75
        elif metrics.gpu_utilization < 0.50:
            gpu_factor = 1.25  # Can handle more
        
        # Factor 2: Queue depth
        queue_factor = 1.0
        if metrics.queue_depth > 500:
            queue_factor = 0.3  # Aggressive backoff
        elif metrics.queue_depth > 100:
            queue_factor = 0.6
        
        # Factor 3: Upstream provider limits remaining
        provider_factor = 1.0
        if metrics.openai_remaining_tokens < 10_000:
            provider_factor = 0.4
        
        # Factor 4: P95 latency
        latency_factor = 1.0
        if metrics.p95_latency > 15.0:
            latency_factor = 0.5
        elif metrics.p95_latency < 5.0:
            latency_factor = 1.2
        
        # Combined adjustment (take the most restrictive)
        adjustment = min(gpu_factor, queue_factor, provider_factor, latency_factor)
        self.current_rate = int(self.base_rate * adjustment)
        
        # Never go below 10% of base (maintain minimum service)
        self.current_rate = max(self.current_rate, self.base_rate * 0.10)
    
    # Pro: Responds to actual system capacity in real-time
    # Con: Complex, needs good metrics, can oscillate if not dampened
```

---

## Geographic Distribution: Multi-Region AI Serving

### Architecture: 3-Region Deployment

```yaml
# Region configuration for global AI service
regions:
  us-east-1:
    role: primary
    services:
      - inference (GPT-4o via Azure OpenAI East US)
      - inference (self-hosted Llama-3 on H100 cluster)
      - vector_db (Qdrant primary, 3 replicas)
      - cache (Redis Cluster, 32GB)
      - embedding_service (GPU, e5-large-v2)
    traffic_sources: [North America, South America]
    
  eu-west-1:
    role: secondary
    services:
      - inference (Claude via AWS Bedrock EU)
      - inference (self-hosted Llama-3, 2 nodes)
      - vector_db (Qdrant replica, read-only, async replication from US)
      - cache (Redis, 16GB)
      - embedding_service (GPU)
    traffic_sources: [Europe, Africa, Middle East]
    data_residency: GDPR  # EU data never leaves EU
    
  ap-southeast-1:
    role: secondary
    services:
      - inference (GPT-4o via Azure OpenAI Japan)
      - vector_db (Qdrant replica, read-only)
      - cache (Redis, 16GB)
      - embedding_service (CPU-only, ONNX optimized)
    traffic_sources: [Asia-Pacific, Oceania]
```

### Vector DB Replication Strategy

```python
class VectorDBReplicator:
    """
    Async replication of vector DB writes from primary (US) to secondaries.
    
    Design decisions:
    - Writes only go to primary (consistency)
    - Reads can go to any region (availability + latency)
    - Replication lag target: < 30 seconds
    - If lag exceeds 60s, secondary reads fall back to primary
    """
    
    def __init__(self):
        self.primary = QdrantClient("qdrant-us-east.internal:6334")
        self.secondaries = {
            "eu": QdrantClient("qdrant-eu-west.internal:6334"),
            "ap": QdrantClient("qdrant-ap-southeast.internal:6334"),
        }
        self.replication_lag = {"eu": 0, "ap": 0}
    
    async def write(self, collection: str, points: list[dict]):
        """Write to primary, then async replicate."""
        # Synchronous write to primary
        await self.primary.upsert(collection, points)
        
        # Async replication (fire and forget, with retry queue)
        for region, client in self.secondaries.items():
            asyncio.create_task(
                self._replicate_with_retry(region, client, collection, points)
            )
    
    async def read(self, collection: str, query_vector: list, region: str):
        """Read from nearest region, fallback to primary if stale."""
        if region in self.secondaries and self.replication_lag[region] < 60:
            return await self.secondaries[region].search(collection, query_vector)
        # Fallback to primary
        return await self.primary.search(collection, query_vector)
```

### DNS-Based Routing

```hcl
# Terraform: Route53 latency-based routing
resource "aws_route53_record" "ai_api" {
  zone_id        = aws_route53_zone.main.id
  name           = "api.aiplatform.com"
  type           = "A"
  set_identifier = "us-east-1"
  
  latency_routing_policy {
    region = "us-east-1"
  }
  
  alias {
    name    = aws_lb.ai_api_us.dns_name
    zone_id = aws_lb.ai_api_us.zone_id
  }
}

resource "aws_route53_record" "ai_api_eu" {
  zone_id        = aws_route53_zone.main.id
  name           = "api.aiplatform.com"
  type           = "A"
  set_identifier = "eu-west-1"
  
  latency_routing_policy {
    region = "eu-west-1"
  }
  
  alias {
    name    = aws_lb.ai_api_eu.dns_name
    zone_id = aws_lb.ai_api_eu.zone_id
  }
}
```

---

## Thundering Herd: Handling Viral Traffic (10x Normal)

### Incident: AI Writing Tool Goes Viral on TikTok

**Company:** WriteAI (AI writing assistant)  
**Normal traffic:** 50,000 requests/day  
**Viral spike:** 500,000 requests in 2 hours (10x sustained for 2 hours)

### What Happened (Timeline)

```
10:00 — TikTok creator posts video "This AI wrote my entire college essay in 30 seconds"
10:15 — Traffic starts climbing: 2x normal
10:30 — 5x normal. Auto-scaler adds pods (works for API layer)
10:35 — Problem: LLM provider rate limit hit (10K req/min, normally use 3K)
10:37 — Requests start queuing. Queue depth: 500 → 2,000 → 8,000
10:40 — Queue memory exceeds Redis max → OOM → Redis crash
10:41 — Without Redis: no caching, no rate limiting, no session state
10:42 — All 500K queued requests retry simultaneously (actual thundering herd)
10:43 — Cascading failure: API servers overwhelmed, health checks fail
10:44 — Kubernetes kills "unhealthy" pods, restarts them, they immediately die again
10:45 — FULL OUTAGE
10:47 — On-call paged
11:02 — Manual intervention: scale to 0, then carefully bring back up
11:15 — Service restored with aggressive rate limiting
```

### The Fix: Multi-Layer Protection Against Thundering Herd

```python
# Layer 1: Edge-level rate limiting (Cloudflare Workers)
# Runs before traffic even reaches your infrastructure

# cloudflare-worker/rate-limit.js (conceptual)
"""
addEventListener('fetch', event => {
  const ip = event.request.headers.get('CF-Connecting-IP')
  const rateLimited = checkRateLimit(ip, {
    requests: 10,
    window: '1m',
    // During detected surge: auto-tighten to 3 req/min
    surge_mode: { requests: 3, window: '1m' }
  })
  
  if (rateLimited) {
    return new Response('Too many requests. Please wait.', { 
      status: 429,
      headers: { 'Retry-After': '30' }
    })
  }
})
"""

# Layer 2: Admission control with circuit breaker
class ThunderingHerdProtection:
    def __init__(self):
        self.max_concurrent = 200          # Max concurrent LLM calls
        self.max_queue_size = 1000         # Max queued requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.queue_size = 0
        self.circuit_state = "closed"      # closed, open, half-open
        self.failure_count = 0
        self.surge_detected = False
    
    async def handle_request(self, request) -> Response:
        # Check circuit breaker
        if self.circuit_state == "open":
            return Response(
                status=503,
                body={"message": "Service temporarily unavailable", 
                      "retry_after": 30,
                      "queue_position": None}
            )
        
        # Check queue capacity
        if self.queue_size >= self.max_queue_size:
            # Shed load gracefully
            return Response(
                status=429,
                body={"message": "High demand. Please try again in a few minutes.",
                      "estimated_wait": self._estimate_wait()}
            )
        
        # Try to acquire semaphore (with timeout)
        self.queue_size += 1
        try:
            acquired = await asyncio.wait_for(
                self.semaphore.acquire(), 
                timeout=30.0  # Max 30s wait in queue
            )
            if acquired:
                self.queue_size -= 1
                return await self._process_request(request)
        except asyncio.TimeoutError:
            self.queue_size -= 1
            return Response(status=429, body={"message": "Request timed out in queue"})
    
    def detect_surge(self, requests_per_second: float):
        """Called by metrics collector every second."""
        baseline = 50  # Normal RPS
        if requests_per_second > baseline * 5:
            self.surge_detected = True
            self._activate_surge_mode()
    
    def _activate_surge_mode(self):
        """Engage surge protections."""
        # 1. Tighten rate limits (per-user)
        self.per_user_limit = 3  # Down from 20 req/min
        
        # 2. Enable aggressive caching (lower similarity threshold)
        self.cache_threshold = 0.90  # Down from 0.95
        
        # 3. Switch to cheaper/faster model for free tier
        self.free_tier_model = "gpt-4o-mini"  # Was gpt-4o
        
        # 4. Disable non-essential features
        self.features_disabled = ["advanced_formatting", "multi_language", "citations"]
        
        # 5. Show queue position to users (set expectations)
        self.show_queue_ui = True

# Layer 3: Request coalescing (for identical/similar requests)
class RequestCoalescer:
    """
    During viral events, many users ask the same thing.
    Coalesce identical requests into a single LLM call.
    """
    def __init__(self):
        self.pending = {}  # hash(request) -> Future
    
    async def deduplicated_call(self, request) -> Response:
        request_hash = self._semantic_hash(request)
        
        if request_hash in self.pending:
            # Another identical request is in-flight — wait for its result
            return await self.pending[request_hash]
        
        # First request with this hash — execute it
        future = asyncio.Future()
        self.pending[request_hash] = future
        
        try:
            result = await self._call_llm(request)
            future.set_result(result)
            return result
        finally:
            del self.pending[request_hash]
```

### Post-Viral Improvements

After the incident, WriteAI implemented:

1. **Pre-provisioned burst capacity:** 3x normal GPU reservation with auto-scaling trigger at 1.5x
2. **Edge caching for popular prompts:** Cloudflare KV stores responses for trending queries
3. **Graceful degradation UI:** "We're experiencing high demand" page with queue position
4. **Multi-provider load spreading:** During surge, distribute across OpenAI + Anthropic + Cohere
5. **Chaos engineering:** Monthly "surge drills" simulating 10x traffic to validate protections

**Result:** Next viral event (3 months later, Twitter/X post) — handled 8x traffic with 0 downtime, p95 latency increased from 4s to 9s for free tier, enterprise customers unaffected.

---

## Priority Queues: Tiered Latency for AI Requests

### Production Implementation

```python
import heapq
import asyncio
from dataclasses import dataclass, field

@dataclass(order=True)
class PrioritizedRequest:
    priority: int                           # Lower = higher priority
    timestamp: float = field(compare=False)
    request: dict = field(compare=False)
    user_tier: str = field(compare=False)

class TieredAIQueue:
    """
    Priority queue ensuring enterprise users get sub-5s latency
    even when free tier is experiencing 30s+ waits.
    """
    
    TIER_CONFIG = {
        "enterprise": {
            "priority": 0,          # Highest priority
            "max_wait_ms": 5_000,
            "dedicated_workers": 5,  # Guaranteed worker pool
            "model": "gpt-4o",
            "max_tokens": 8192,
        },
        "pro": {
            "priority": 10,
            "max_wait_ms": 15_000,
            "dedicated_workers": 3,
            "model": "gpt-4o",
            "max_tokens": 4096,
        },
        "free": {
            "priority": 100,
            "max_wait_ms": 60_000,   # Up to 60s wait acceptable
            "dedicated_workers": 0,   # Uses shared pool only
            "model": "gpt-4o-mini",  # Cheaper model
            "max_tokens": 2048,
        },
    }
    
    def __init__(self):
        self.queues = {tier: asyncio.PriorityQueue() for tier in self.TIER_CONFIG}
        self.shared_workers = 10
        self.metrics = QueueMetrics()
    
    async def enqueue(self, request: dict, user_tier: str) -> str:
        config = self.TIER_CONFIG[user_tier]
        item = PrioritizedRequest(
            priority=config["priority"],
            timestamp=time.time(),
            request=request,
            user_tier=user_tier,
        )
        
        await self.queues[user_tier].put(item)
        queue_position = self.queues[user_tier].qsize()
        
        self.metrics.record_enqueue(user_tier, queue_position)
        
        return {
            "request_id": request["id"],
            "queue_position": queue_position,
            "estimated_wait_ms": self._estimate_wait(user_tier, queue_position),
        }
    
    async def worker_loop(self, worker_id: int, assigned_tier: str = None):
        """
        Workers either serve a dedicated tier or pull from priority queue.
        Dedicated workers ensure enterprise SLA even under load.
        """
        while True:
            if assigned_tier:
                # Dedicated worker: only serve assigned tier
                item = await self.queues[assigned_tier].get()
            else:
                # Shared worker: serve highest priority available request
                item = await self._get_highest_priority()
            
            wait_time = time.time() - item.timestamp
            self.metrics.record_dequeue(item.user_tier, wait_time)
            
            # Check if request has expired (user may have given up)
            max_wait = self.TIER_CONFIG[item.user_tier]["max_wait_ms"] / 1000
            if wait_time > max_wait:
                self.metrics.record_expired(item.user_tier)
                continue  # Skip expired requests
            
            await self._process(item)
```

---

## Summary: Key Scaling Lessons

| Scale | Primary Challenge | Solution Pattern |
|-------|------------------|-----------------|
| 0-1K req/day | Getting it working | Single server, managed services |
| 1K-10K | Rate limits, cost | Caching, batching, async |
| 10K-100K | Reliability, latency variance | Queue architecture, priority tiers |
| 100K-1M | Noisy neighbors, blast radius | Cell architecture, isolation |
| 1M-10M | Infrastructure cost, global latency | Multi-region, self-hosted models |
| 10M+ | Everything at once | All of the above + custom infrastructure |

The most common mistake: **over-engineering at small scale** and **under-engineering at medium scale**. Teams build Kubernetes clusters for 100 req/day (wasteful) but skip rate limiting until they're drowning at 50K req/day (dangerous).
