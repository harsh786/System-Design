# System Design Patterns for AI (Questions 166-170)

## Q166: Design the event-driven architecture for an AI platform. Compare request-response vs event-sourcing vs CQRS patterns for AI workloads. When does each make sense?

### Answer

**Architecture Overview:**

```
┌──────────────────────────────────────────────────────────────────┐
│              Event-Driven AI Platform                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Pattern 1: Request-Response (Synchronous)                         │
│  ┌────────┐  HTTP/gRPC  ┌──────────┐  ┌──────────┐              │
│  │ Client │────────────▶│ API GW   │─▶│ AI Svc   │              │
│  │        │◀────────────│          │◀─│          │              │
│  └────────┘             └──────────┘  └──────────┘              │
│                                                                    │
│  Pattern 2: Event Sourcing                                         │
│  ┌────────┐   ┌────────────┐   ┌──────────┐   ┌────────────┐   │
│  │Command │──▶│Event Store │──▶│Projector │──▶│ Read Model │   │
│  │        │   │(Immutable) │   │          │   │            │   │
│  └────────┘   └────────────┘   └──────────┘   └────────────┘   │
│                                                                    │
│  Pattern 3: CQRS                                                   │
│  ┌─────────┐    ┌──────────────┐     ┌────────────────────┐     │
│  │Write Cmd│───▶│Write Model   │     │ Read Model         │     │
│  └─────────┘    │(Source DB +  │────▶│ (Vector Index +    │     │
│                  │ Event Emit)  │     │  Materialized View)│     │
│  ┌─────────┐    └──────────────┘     └────────┬───────────┘     │
│  │Read Qry │──────────────────────────────────▶│                  │
│  └─────────┘                                                      │
└──────────────────────────────────────────────────────────────────┘
```

**Comparison for AI Workloads:**

| Aspect | Request-Response | Event Sourcing | CQRS |
|--------|-----------------|---------------|------|
| Use case | Real-time Q&A, chat | Audit-heavy, replay needed | High-read RAG, async indexing |
| Latency | Synchronous (p99 target) | Eventual (async projection) | Write: async, Read: fast |
| Complexity | Low | High | Medium |
| Auditability | Manual logging | Built-in (event log IS audit) | Partial (write side) |
| Scalability | Limited by slowest step | Excellent (replay/reproject) | Independent read/write scale |
| AI fit | Simple chatbot | Training pipeline, feedback loops | RAG (separate ingest from query) |

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Any
from datetime import datetime
import asyncio

# ===== Event Sourcing for AI Feedback Loop =====

@dataclass
class AIEvent:
    event_id: str
    event_type: str  # "QueryReceived", "RetrievalCompleted", "ResponseGenerated", "FeedbackReceived"
    timestamp: datetime
    payload: dict
    metadata: dict = field(default_factory=dict)

class AIEventStore:
    """Immutable event log for full AI interaction history."""
    
    def __init__(self, kafka_producer, event_db):
        self.kafka = kafka_producer
        self.db = event_db
    
    async def append(self, event: AIEvent):
        """Append event (never modify past events)."""
        await self.db.insert(event)
        await self.kafka.produce("ai-events", event.to_json())
    
    async def get_session_events(self, session_id: str) -> List[AIEvent]:
        """Replay all events for a session (for debugging/audit)."""
        return await self.db.query(
            filter={"metadata.session_id": session_id},
            order_by="timestamp"
        )

class AIEventProjector:
    """Project events into different read models."""
    
    async def handle_event(self, event: AIEvent):
        if event.event_type == "QueryReceived":
            await self.update_query_analytics(event)
        elif event.event_type == "RetrievalCompleted":
            await self.update_retrieval_metrics(event)
        elif event.event_type == "FeedbackReceived":
            await self.update_quality_model(event)
            await self.update_training_data(event)  # Feedback → future training

# ===== CQRS for RAG (separate ingest from query) =====

class RAGWriteSide:
    """Handles document ingestion (write-optimized)."""
    
    async def ingest_document(self, doc: dict):
        # 1. Store source of truth
        await self.document_store.save(doc)
        
        # 2. Emit event for async processing
        await self.event_bus.emit("DocumentIngested", {
            "doc_id": doc["id"],
            "content": doc["content"],
            "metadata": doc["metadata"]
        })
        
        # Write side doesn't wait for indexing — returns immediately
        return {"status": "accepted", "doc_id": doc["id"]}

class RAGReadSide:
    """Handles queries (read-optimized, eventually consistent with writes)."""
    
    def __init__(self, vector_index, cache):
        self.index = vector_index  # Materialized read model
        self.cache = cache
    
    async def query(self, query: str, filters: dict) -> List[dict]:
        # Read from optimized index (not source DB)
        embedding = await self.embed(query)
        return await self.index.search(embedding, filters=filters)

class RAGEventHandler:
    """Keeps read model (vector index) in sync with write model."""
    
    async def on_document_ingested(self, event):
        """Async handler: processes write events to update read model."""
        doc = event.payload
        chunks = self.chunk(doc["content"])
        embeddings = await self.embed_batch(chunks)
        
        # Update the read model (vector index)
        await self.vector_index.upsert(
            doc_id=doc["doc_id"],
            chunks=chunks,
            embeddings=embeddings
        )
```

**When to Use Each Pattern:**

| Scenario | Recommended Pattern | Reason |
|----------|-------------------|--------|
| Chat/Q&A (real-time) | Request-Response | User expects immediate response |
| Document ingestion | CQRS | Decouple slow indexing from fast acknowledgment |
| AI feedback/learning | Event Sourcing | Need full history for model improvement |
| Batch training pipeline | Event Sourcing | Replay events to regenerate training data |
| Multi-modal search | CQRS | Different indices for text/image/audio (separate read models) |
| Compliance-heavy | Event Sourcing | Immutable audit trail of all AI decisions |

**Production Considerations:**
- **Hybrid is common**: Real-time query path uses request-response; indexing uses CQRS; feedback uses event sourcing
- **Event schema evolution**: Use Avro/Protobuf with schema registry for backward-compatible event evolution
- **Consistency window**: CQRS means queries may not immediately reflect new documents; communicate this SLA
- **Event replay**: Ability to rebuild any read model from events is powerful for migrations and debugging
- **Dead letter handling**: Events that fail processing go to DLQ with alerting

---

## Q167: Design a saga pattern implementation for complex AI workflows (document processing → embedding → indexing → notification) where each step can fail and needs compensation.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Saga Orchestrator for AI Workflows                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Happy Path:                                                      │
│  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌─────┐ │
│  │ Parse  │──▶│ Embed  │──▶│ Index  │──▶│ Notify │──▶│Done │ │
│  │Document│   │Chunks  │   │Vectors │   │ Users  │   │     │ │
│  └────────┘   └────────┘   └────────┘   └────────┘   └─────┘ │
│                                                                   │
│  Compensation (Rollback on failure at Index step):                │
│  ┌────────┐   ┌────────┐   ┌────────┐                          │
│  │Undo    │◀──│Delete  │◀──│FAILED  │                          │
│  │Parse   │   │Embeddings  │Index   │                          │
│  │Artifacts│   │from Store│  │        │                          │
│  └────────┘   └────────┘   └────────┘                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Saga State Machine                               ││
│  │  PENDING → PARSING → EMBEDDING → INDEXING → NOTIFYING → DONE││
│  │     ↓          ↓          ↓           ↓                      ││
│  │  FAILED   COMPENSATING_PARSE  COMPENSATING_EMBED  COMP_INDEX ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any
from enum import Enum
from datetime import datetime
import asyncio

class SagaState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"

@dataclass
class SagaStep:
    name: str
    execute: Callable       # Forward action
    compensate: Callable    # Rollback action
    timeout_seconds: int = 300
    max_retries: int = 3

@dataclass
class SagaExecution:
    saga_id: str
    state: SagaState = SagaState.PENDING
    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    step_results: dict = field(default_factory=dict)
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)

class SagaOrchestrator:
    """Orchestrates multi-step AI workflows with compensation."""
    
    def __init__(self, state_store, event_bus):
        self.state_store = state_store
        self.event_bus = event_bus
    
    async def execute_saga(self, saga_id: str, steps: List[SagaStep], 
                           context: dict) -> SagaExecution:
        execution = SagaExecution(saga_id=saga_id)
        await self.state_store.save(execution)
        
        try:
            for i, step in enumerate(steps):
                execution.current_step = i
                execution.state = SagaState.RUNNING
                await self.state_store.save(execution)
                
                # Execute step with retry
                result = await self.execute_step_with_retry(step, context)
                
                # Store result for potential compensation
                execution.step_results[step.name] = result
                execution.completed_steps.append(step.name)
                context[f"{step.name}_result"] = result
                
                await self.state_store.save(execution)
                await self.event_bus.emit(f"saga.{saga_id}.step_completed", {
                    "step": step.name, "result": result
                })
            
            execution.state = SagaState.COMPLETED
            
        except Exception as e:
            execution.error = str(e)
            execution.state = SagaState.COMPENSATING
            await self.state_store.save(execution)
            
            # Compensate in reverse order
            await self.compensate(execution, steps, context)
            execution.state = SagaState.FAILED
        
        await self.state_store.save(execution)
        return execution
    
    async def execute_step_with_retry(self, step: SagaStep, context: dict) -> Any:
        last_error = None
        for attempt in range(step.max_retries):
            try:
                return await asyncio.wait_for(
                    step.execute(context),
                    timeout=step.timeout_seconds
                )
            except asyncio.TimeoutError:
                last_error = f"Timeout after {step.timeout_seconds}s"
            except RetryableError as e:
                last_error = str(e)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except NonRetryableError:
                raise  # Don't retry, go straight to compensation
        
        raise SagaStepFailed(f"{step.name} failed after {step.max_retries} retries: {last_error}")
    
    async def compensate(self, execution: SagaExecution, 
                         steps: List[SagaStep], context: dict):
        """Compensate completed steps in reverse order."""
        for step_name in reversed(execution.completed_steps):
            step = next(s for s in steps if s.name == step_name)
            try:
                await step.compensate(context)
                await self.event_bus.emit(f"saga.{execution.saga_id}.compensated", {
                    "step": step_name
                })
            except Exception as e:
                # Compensation failed — requires manual intervention
                await self.alert_ops(execution.saga_id, step_name, e)

# ===== Document Processing Saga =====

class DocumentProcessingSaga:
    """Concrete saga for document ingestion workflow."""
    
    def build_steps(self) -> List[SagaStep]:
        return [
            SagaStep(
                name="parse",
                execute=self.parse_document,
                compensate=self.delete_parsed_artifacts,
                timeout_seconds=120
            ),
            SagaStep(
                name="embed",
                execute=self.generate_embeddings,
                compensate=self.delete_embeddings,
                timeout_seconds=300
            ),
            SagaStep(
                name="index",
                execute=self.write_to_index,
                compensate=self.remove_from_index,
                timeout_seconds=60
            ),
            SagaStep(
                name="notify",
                execute=self.send_notification,
                compensate=self.noop,  # Notifications can't be unsent
                timeout_seconds=10
            ),
        ]
    
    async def parse_document(self, ctx: dict) -> dict:
        doc = ctx["document"]
        chunks = await self.parser.parse(doc["url"], doc["format"])
        # Store chunks for next step
        chunk_ids = await self.chunk_store.save_batch(chunks)
        return {"chunk_ids": chunk_ids, "chunk_count": len(chunks)}
    
    async def delete_parsed_artifacts(self, ctx: dict):
        result = ctx.get("parse_result", {})
        if chunk_ids := result.get("chunk_ids"):
            await self.chunk_store.delete_batch(chunk_ids)
    
    async def generate_embeddings(self, ctx: dict) -> dict:
        chunk_ids = ctx["parse_result"]["chunk_ids"]
        chunks = await self.chunk_store.get_batch(chunk_ids)
        embeddings = await self.embedder.embed_batch([c.text for c in chunks])
        embedding_ids = await self.embedding_store.save_batch(embeddings)
        return {"embedding_ids": embedding_ids}
    
    async def delete_embeddings(self, ctx: dict):
        result = ctx.get("embed_result", {})
        if emb_ids := result.get("embedding_ids"):
            await self.embedding_store.delete_batch(emb_ids)
    
    async def write_to_index(self, ctx: dict) -> dict:
        embedding_ids = ctx["embed_result"]["embedding_ids"]
        embeddings = await self.embedding_store.get_batch(embedding_ids)
        await self.vector_index.upsert(ctx["document"]["id"], embeddings)
        return {"indexed": True}
    
    async def remove_from_index(self, ctx: dict):
        await self.vector_index.delete(ctx["document"]["id"])
```

**Production Considerations:**
- **Idempotent steps**: Every step must be safely re-executable (use idempotency keys)
- **Saga persistence**: Store saga state in durable storage; resume after process crash
- **Timeout handling**: Each step has independent timeout; prevent hung sagas from blocking resources
- **Observability**: Trace ID propagated through all steps; distributed tracing shows saga flow
- **Partial completion**: Some steps (notifications) can't be compensated; design saga order accordingly (put non-compensatable steps last)

---

## Q168: Design a sidecar pattern for AI observability where every microservice gets an AI-aware sidecar that handles prompt logging, token counting, safety scanning, and cost tracking without modifying the main service.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                AI Observability Sidecar Pattern                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Pod/Container Group:                                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ┌─────────────┐         ┌─────────────────────────┐    │    │
│  │  │  Main App   │◀──────▶│  AI Observability       │    │    │
│  │  │  Container  │ (proxy) │  Sidecar               │    │    │
│  │  │             │         │                         │    │    │
│  │  │ - Business  │         │ - Prompt logging        │    │    │
│  │  │   logic     │         │ - Token counting        │    │    │
│  │  │ - LLM calls │         │ - Safety scanning       │    │    │
│  │  │   via proxy │         │ - Cost tracking         │    │    │
│  │  │             │         │ - Latency metrics       │    │    │
│  │  └─────────────┘         └───────────┬─────────────┘    │    │
│  └──────────────────────────────────────┼───────────────────┘    │
│                                          │                        │
│                              ┌───────────▼────────────┐          │
│                              │  Observability Backend  │          │
│                              │  (Prometheus, Loki,     │          │
│                              │   Custom AI Metrics)    │          │
│                              └────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import time
import json
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional
from aiohttp import web
import tiktoken

@dataclass
class AICallMetrics:
    request_id: str
    service_name: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0
    cost_usd: float = 0
    safety_flags: list = field(default_factory=list)
    cached: bool = False

class AISidecar:
    """Transparent proxy sidecar for AI observability."""
    
    def __init__(self, config):
        self.config = config
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.safety_scanner = SafetyScanner()
        self.metrics_exporter = MetricsExporter()
        self.cost_tracker = CostTracker()
        self.prompt_logger = PromptLogger(config.log_level)
    
    async def proxy_llm_request(self, request: web.Request) -> web.Response:
        """Intercept LLM calls, add observability, forward to provider."""
        start_time = time.monotonic()
        body = await request.json()
        
        # --- Pre-request processing ---
        # 1. Count input tokens
        prompt_tokens = self.count_tokens(body)
        
        # 2. Safety scan on input
        input_safety = await self.safety_scanner.scan_input(body)
        if input_safety.blocked:
            return web.json_response(
                {"error": "blocked_by_safety", "reason": input_safety.reason},
                status=403
            )
        
        # 3. Log prompt (with PII redaction if configured)
        await self.prompt_logger.log_request(body, request.headers)
        
        # --- Forward to actual LLM provider ---
        response = await self.forward_to_provider(body, request.headers)
        
        # --- Post-response processing ---
        latency_ms = (time.monotonic() - start_time) * 1000
        response_body = await response.json()
        
        # 4. Count output tokens
        completion_tokens = self.count_response_tokens(response_body)
        
        # 5. Safety scan on output
        output_safety = await self.safety_scanner.scan_output(response_body)
        
        # 6. Compute cost
        cost = self.cost_tracker.compute_cost(
            model=body.get("model", "unknown"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
        
        # 7. Export metrics
        metrics = AICallMetrics(
            request_id=request.headers.get("X-Request-ID", ""),
            service_name=self.config.service_name,
            model=body.get("model", "unknown"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
            safety_flags=output_safety.flags
        )
        await self.metrics_exporter.export(metrics)
        
        # 8. Add observability headers to response
        response.headers["X-AI-Tokens-Used"] = str(metrics.total_tokens)
        response.headers["X-AI-Cost-USD"] = f"{cost:.6f}"
        response.headers["X-AI-Latency-MS"] = f"{latency_ms:.1f}"
        
        return response
    
    def count_tokens(self, body: dict) -> int:
        """Count tokens in request (model-aware)."""
        messages = body.get("messages", [])
        total = 0
        for msg in messages:
            total += len(self.tokenizer.encode(msg.get("content", "")))
            total += 4  # Message overhead tokens
        return total

class CostTracker:
    """Track and attribute AI costs per service, team, tenant."""
    
    PRICING = {
        "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
        "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "claude-sonnet-4-20250514": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    }
    
    def compute_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = self.PRICING.get(model, {"input": 0.01/1000, "output": 0.03/1000})
        return (prompt_tokens * pricing["input"] + 
                completion_tokens * pricing["output"])

class SafetyScanner:
    """Lightweight safety scanning in sidecar."""
    
    async def scan_input(self, body: dict) -> "SafetyResult":
        content = " ".join(m.get("content", "") for m in body.get("messages", []))
        
        # Fast regex-based checks (< 1ms)
        flags = []
        if self.contains_pii_patterns(content):
            flags.append("potential_pii")
        if self.contains_injection_patterns(content):
            flags.append("potential_injection")
        
        return SafetyResult(
            blocked=("potential_injection" in flags and self.config.block_injections),
            flags=flags
        )
```

**Kubernetes Deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-service
spec:
  template:
    spec:
      containers:
      - name: main-app
        image: my-ai-service:latest
        env:
        - name: LLM_ENDPOINT
          value: "http://localhost:8081"  # Points to sidecar
      - name: ai-observability-sidecar
        image: ai-sidecar:latest
        ports:
        - containerPort: 8081
        env:
        - name: UPSTREAM_LLM_URL
          value: "https://api.openai.com/v1"
        - name: SERVICE_NAME
          value: "ai-service"
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
```

**Production Considerations:**
- **Zero-code integration**: Main service just points LLM_ENDPOINT to localhost; no SDK changes needed
- **Latency overhead**: Sidecar adds < 5ms (mostly async post-processing); safety scan is the bottleneck
- **Failure mode**: If sidecar crashes, main service should failover to direct LLM call (circuit breaker)
- **Sampling**: For high-volume services, sample prompt logging at 10%; always count tokens/cost at 100%
- **Multi-provider**: Sidecar handles routing to OpenAI/Anthropic/local models transparently

---

## Q169: Design a strangler fig migration pattern for moving from a monolithic AI application to microservices. How do you incrementally decompose an AI monolith without breaking production?

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│             Strangler Fig Migration for AI Monolith                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Phase 1: Intercept                                                   │
│  ┌────────┐    ┌──────────────┐    ┌──────────────────────────────┐ │
│  │ Client │───▶│  Router/     │───▶│  AI Monolith (all traffic)   │ │
│  │        │    │  Facade      │    │  - Ingestion                 │ │
│  └────────┘    └──────────────┘    │  - Embedding                 │ │
│                                     │  - Search                    │ │
│                                     │  - Generation                │ │
│  Phase 3: Strangled                 │  - Feedback                  │ │
│  ┌────────┐    ┌──────────────┐    └──────────────────────────────┘ │
│  │ Client │───▶│  Router      │                                      │
│  │        │    │              │    ┌────────────┐                    │
│  └────────┘    │  ┌───────┐  │───▶│ Ingestion  │ (new microservice)│
│                │  │ Rules │  │    │ Service    │                    │
│                │  └───────┘  │    └────────────┘                    │
│                │              │    ┌────────────┐                    │
│                │              │───▶│ Embedding  │ (new microservice)│
│                │              │    │ Service    │                    │
│                │              │    └────────────┘                    │
│                │              │    ┌────────────┐                    │
│                │              │───▶│ Search     │ (new microservice)│
│                │              │    │ Service    │                    │
│                │              │    └────────────┘                    │
│                │              │    ┌────────────────────────────┐   │
│                │              │───▶│ Monolith (only Generation) │   │
│                │              │    └────────────────────────────┘   │
│                └──────────────┘                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from enum import Enum
import asyncio
import random

class RoutingStrategy(Enum):
    MONOLITH = "monolith"
    MICROSERVICE = "microservice"
    SHADOW = "shadow"      # Send to both, return monolith result
    CANARY = "canary"      # Small % to microservice

@dataclass
class MigrationRule:
    capability: str
    strategy: RoutingStrategy
    canary_percent: float = 0.0
    shadow_enabled: bool = False
    rollback_on_error: bool = True

class StranglerFigRouter:
    """Routes traffic between monolith and new microservices."""
    
    def __init__(self, monolith_client, service_registry, rules_store):
        self.monolith = monolith_client
        self.services = service_registry
        self.rules = rules_store
        self.comparator = ResultComparator()
    
    async def route(self, capability: str, request: dict) -> dict:
        rule = self.rules.get(capability)
        
        if rule.strategy == RoutingStrategy.MONOLITH:
            return await self.monolith.call(capability, request)
        
        elif rule.strategy == RoutingStrategy.MICROSERVICE:
            service = self.services.get(capability)
            try:
                return await service.call(request)
            except Exception as e:
                if rule.rollback_on_error:
                    # Fallback to monolith on failure
                    self.metrics.increment("microservice_fallback", capability=capability)
                    return await self.monolith.call(capability, request)
                raise
        
        elif rule.strategy == RoutingStrategy.SHADOW:
            # Send to both, compare results, return monolith
            monolith_result, micro_result = await asyncio.gather(
                self.monolith.call(capability, request),
                self.services.get(capability).call(request),
                return_exceptions=True
            )
            
            # Compare async (don't block response)
            asyncio.create_task(
                self.comparator.compare(capability, monolith_result, micro_result)
            )
            
            return monolith_result  # Always return monolith in shadow mode
        
        elif rule.strategy == RoutingStrategy.CANARY:
            if random.random() < rule.canary_percent:
                service = self.services.get(capability)
                try:
                    result = await service.call(request)
                    self.metrics.increment("canary_success", capability=capability)
                    return result
                except Exception:
                    self.metrics.increment("canary_failure", capability=capability)
                    return await self.monolith.call(capability, request)
            else:
                return await self.monolith.call(capability, request)

class MigrationOrchestrator:
    """Manages the phased migration of capabilities."""
    
    MIGRATION_PHASES = [
        # Phase 1: Shadow mode (compare results, zero risk)
        {"strategy": RoutingStrategy.SHADOW, "duration_days": 7},
        # Phase 2: Canary 5%
        {"strategy": RoutingStrategy.CANARY, "canary_percent": 0.05, "duration_days": 3},
        # Phase 3: Canary 25%
        {"strategy": RoutingStrategy.CANARY, "canary_percent": 0.25, "duration_days": 3},
        # Phase 4: Canary 50%
        {"strategy": RoutingStrategy.CANARY, "canary_percent": 0.50, "duration_days": 3},
        # Phase 5: Full migration
        {"strategy": RoutingStrategy.MICROSERVICE},
    ]
    
    async def migrate_capability(self, capability: str):
        """Progressively migrate a capability through phases."""
        for phase in self.MIGRATION_PHASES:
            rule = MigrationRule(
                capability=capability,
                strategy=phase["strategy"],
                canary_percent=phase.get("canary_percent", 0),
                shadow_enabled=phase["strategy"] == RoutingStrategy.SHADOW
            )
            await self.rules_store.update(capability, rule)
            
            # Wait and verify
            if "duration_days" in phase:
                await self.wait_and_verify(capability, phase["duration_days"])
    
    async def wait_and_verify(self, capability: str, days: int):
        """Monitor metrics and auto-rollback if quality degrades."""
        for _ in range(days * 24):  # Check hourly
            await asyncio.sleep(3600)
            metrics = await self.get_metrics(capability)
            
            if metrics.error_rate > 0.01 or metrics.latency_p99_increase > 0.2:
                await self.rollback(capability)
                raise MigrationFailed(f"Quality degraded: {metrics}")
```

**Migration Order for AI Monolith:**

| Priority | Capability | Reason to Extract First |
|----------|-----------|------------------------|
| 1 | Ingestion/Parsing | Stateless, easy to isolate, high CPU |
| 2 | Embedding | Stateless, GPU-intensive, scales independently |
| 3 | Search/Retrieval | Clear API boundary, performance-critical |
| 4 | Generation | Stateful (conversation), most complex |
| 5 | Feedback/Analytics | Low-risk, async, separate data model |

**Production Considerations:**
- **Shared database problem**: Extract service but initially share DB; later migrate to own DB (another strangler within the strangler)
- **Shadow mode validation**: Compare not just final results but intermediate signals (retrieval quality, latency distribution)
- **Feature parity**: New microservice must match monolith behavior exactly before traffic shift
- **Data migration**: Use dual-write during transition; verify consistency before cutting over
- **Kill switch**: Instant rollback to monolith on any metric degradation (automated)

---

## Q170: Design a plugin architecture for an AI platform that allows third-party developers to add custom retrievers, generators, safety filters, and post-processors without risking platform stability.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              AI Platform Plugin Architecture                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Plugin Registry                            │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │    │
│  │  │Retriever │ │Generator │ │Safety    │ │Post-Processor│  │    │
│  │  │Plugins   │ │Plugins   │ │Plugins   │ │Plugins       │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Plugin Runtime                             │    │
│  │                                                               │    │
│  │  ┌───────────┐  ┌────────────┐  ┌─────────────────────┐    │    │
│  │  │ Sandbox   │  │ Resource   │  │ Contract            │    │    │
│  │  │ (WASM /   │  │ Limiter    │  │ Validator           │    │    │
│  │  │  Container)│  │ (CPU/Mem/  │  │ (Input/Output       │    │    │
│  │  │           │  │  Network)  │  │  Schema Enforce)    │    │    │
│  │  └───────────┘  └────────────┘  └─────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Pipeline Engine                            │    │
│  │  Query → [Retriever Plugins] → [Generator] → [Safety] →     │    │
│  │          [Post-Processors] → Response                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import asyncio
import resource

# ===== Plugin Interface Contracts =====

class RetrieverPlugin(ABC):
    """Interface that all retriever plugins must implement."""
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int, 
                       filters: dict) -> List["RetrievalResult"]:
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def metadata(self) -> "PluginMetadata":
        pass

class SafetyPlugin(ABC):
    @abstractmethod
    async def scan(self, content: str, context: dict) -> "SafetyScanResult":
        pass

class PostProcessorPlugin(ABC):
    @abstractmethod
    async def process(self, response: str, context: dict) -> str:
        pass

@dataclass
class PluginMetadata:
    name: str
    version: str
    author: str
    description: str
    input_schema: dict    # JSON Schema for inputs
    output_schema: dict   # JSON Schema for outputs
    resource_requirements: dict = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)

# ===== Plugin Sandbox =====

class PluginSandbox:
    """Isolates plugin execution with resource limits."""
    
    def __init__(self, config):
        self.max_memory_mb = config.get("max_memory_mb", 256)
        self.max_cpu_seconds = config.get("max_cpu_seconds", 5)
        self.max_network_calls = config.get("max_network_calls", 10)
        self.timeout_seconds = config.get("timeout_seconds", 10)
        self.allowed_domains = config.get("allowed_domains", [])
    
    async def execute(self, plugin: Any, method: str, *args, **kwargs):
        """Execute plugin method in sandbox with resource limits."""
        
        # Create isolated execution context
        ctx = SandboxContext(
            memory_limit=self.max_memory_mb * 1024 * 1024,
            network_allowlist=self.allowed_domains,
            network_calls_remaining=self.max_network_calls
        )
        
        try:
            result = await asyncio.wait_for(
                self._run_sandboxed(plugin, method, ctx, *args, **kwargs),
                timeout=self.timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            self.metrics.increment("plugin_timeout", plugin=plugin.metadata.name)
            raise PluginTimeoutError(
                f"Plugin {plugin.metadata.name} timed out after {self.timeout_seconds}s"
            )
        except MemoryError:
            raise PluginResourceError("Memory limit exceeded")
    
    async def _run_sandboxed(self, plugin, method, ctx, *args, **kwargs):
        """Run with resource tracking."""
        func = getattr(plugin, method)
        
        # Inject sandboxed HTTP client (network restrictions)
        if hasattr(plugin, '_http_client'):
            plugin._http_client = SandboxedHTTPClient(
                allowed_domains=ctx.network_allowlist,
                max_calls=ctx.network_calls_remaining
            )
        
        return await func(*args, **kwargs)

# ===== Plugin Registry & Lifecycle =====

class PluginRegistry:
    """Manages plugin discovery, validation, and lifecycle."""
    
    def __init__(self, sandbox_config, validator):
        self.plugins: Dict[str, Dict[str, Any]] = {
            "retrievers": {},
            "generators": {},
            "safety": {},
            "post_processors": {}
        }
        self.sandbox = PluginSandbox(sandbox_config)
        self.validator = validator
    
    async def register_plugin(self, plugin_type: str, plugin: Any) -> bool:
        """Register a new plugin with validation."""
        
        # 1. Validate implements correct interface
        if not self.validator.check_interface(plugin_type, plugin):
            raise PluginValidationError("Does not implement required interface")
        
        # 2. Validate metadata
        metadata = plugin.metadata
        if not self.validator.check_metadata(metadata):
            raise PluginValidationError("Invalid metadata")
        
        # 3. Validate permissions are acceptable
        if not self.validator.check_permissions(metadata.permissions):
            raise PluginValidationError(f"Unacceptable permissions: {metadata.permissions}")
        
        # 4. Run health check
        if not plugin.health_check():
            raise PluginValidationError("Health check failed")
        
        # 5. Run integration test in sandbox
        test_result = await self.sandbox.execute(
            plugin, "retrieve" if plugin_type == "retrievers" else "scan",
            "test query", 5, {}
        )
        
        # 6. Validate output schema
        if not self.validator.check_output(plugin_type, test_result):
            raise PluginValidationError("Output doesn't match declared schema")
        
        # Register
        self.plugins[plugin_type][metadata.name] = {
            "plugin": plugin,
            "metadata": metadata,
            "enabled": True,
            "error_count": 0
        }
        return True

# ===== Pipeline with Plugin Execution =====

class PluginPipeline:
    """Execute AI pipeline with plugin extensions at each stage."""
    
    def __init__(self, registry: PluginRegistry, sandbox: PluginSandbox):
        self.registry = registry
        self.sandbox = sandbox
    
    async def execute(self, query: str, config: dict) -> dict:
        # 1. Retrieval (run all enabled retriever plugins in parallel)
        retriever_names = config.get("retrievers", ["default"])
        retrieval_tasks = []
        
        for name in retriever_names:
            plugin_entry = self.registry.plugins["retrievers"].get(name)
            if plugin_entry and plugin_entry["enabled"]:
                task = self.safe_execute_plugin(
                    plugin_entry, "retrieve", query, config.get("top_k", 10), {}
                )
                retrieval_tasks.append(task)
        
        results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)
        
        # Filter out failures (graceful degradation)
        all_results = []
        for r in results:
            if isinstance(r, Exception):
                continue  # Log and skip failed plugins
            all_results.extend(r)
        
        # 2. Safety scan on retrieved content
        for safety_plugin in self.registry.plugins["safety"].values():
            if safety_plugin["enabled"]:
                all_results = await self.apply_safety(safety_plugin, all_results)
        
        return {"results": all_results}
    
    async def safe_execute_plugin(self, plugin_entry, method, *args):
        """Execute with circuit breaker pattern."""
        try:
            result = await self.sandbox.execute(
                plugin_entry["plugin"], method, *args
            )
            plugin_entry["error_count"] = 0
            return result
        except Exception as e:
            plugin_entry["error_count"] += 1
            if plugin_entry["error_count"] > 5:
                plugin_entry["enabled"] = False  # Auto-disable
                self.alert(f"Plugin {plugin_entry['metadata'].name} auto-disabled")
            raise
```

**Plugin Security Model:**

| Control | Implementation | Purpose |
|---------|---------------|---------|
| Sandboxing | WASM / container / process isolation | Prevent host access |
| Resource limits | CPU/memory/network caps | Prevent resource exhaustion |
| Network allowlist | Only declared domains accessible | Prevent data exfiltration |
| Schema validation | Input/output contract enforcement | Prevent malformed data |
| Circuit breaker | Auto-disable after N failures | Prevent cascade failures |
| Permission model | Declared capabilities (network, storage, PII access) | Principle of least privilege |

**Production Considerations:**
- **Plugin marketplace**: Review process before plugin is available (automated + manual review)
- **Versioning**: Plugins declare compatible platform API version; platform supports N-1 for migration
- **Hot reload**: Plugins can be updated without platform restart; use graceful drain
- **Billing**: Track resource usage per plugin for chargeback to plugin developer
- **Fallback**: If all plugins fail, platform has built-in default behavior for each stage
# Production Operations for AI (Questions 171-175)

## Q171: Design the deployment pipeline for AI model updates (new LLM version, new embedding model, new prompt template). Include blue-green deployments, canary analysis, and automated rollback.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              AI Model Deployment Pipeline                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────┐│
│  │ Build  │──▶│ Eval     │──▶│ Canary   │──▶│ Promote  │──▶│Live││
│  │& Test  │   │ Gate     │   │ Deploy   │   │ (or Roll │   │    ││
│  │        │   │          │   │ (5%)     │   │  back)   │   │    ││
│  └────────┘   └──────────┘   └──────────┘   └──────────┘   └────┘│
│                                                                       │
│  Blue-Green for Embedding Model Changes:                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ┌────────────────┐         ┌────────────────┐              │    │
│  │  │  Blue (Current)│         │  Green (New)   │              │    │
│  │  │  Embed v1      │         │  Embed v2      │              │    │
│  │  │  Index v1      │  ←swap→ │  Index v2      │              │    │
│  │  └────────────────┘         └────────────────┘              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class DeploymentType(Enum):
    LLM_VERSION = "llm_version"          # New GPT-4 version
    EMBEDDING_MODEL = "embedding_model"   # New embedding model (requires re-index)
    PROMPT_TEMPLATE = "prompt_template"   # New prompt
    RETRIEVAL_CONFIG = "retrieval_config"  # Parameters change

@dataclass
class DeploymentConfig:
    deployment_type: DeploymentType
    artifact_version: str
    canary_percent: float = 0.05
    canary_duration: timedelta = timedelta(hours=2)
    auto_rollback_threshold: float = 0.05  # 5% quality degradation
    eval_dataset: str = "golden_set_v3"
    required_eval_score: float = 0.85

class AIDeploymentPipeline:
    def __init__(self, model_registry, traffic_router, eval_engine, monitor):
        self.registry = model_registry
        self.router = traffic_router
        self.eval = eval_engine
        self.monitor = monitor
    
    async def deploy(self, config: DeploymentConfig) -> "DeploymentResult":
        # Phase 1: Offline Evaluation Gate
        eval_score = await self.eval.run_evaluation(
            artifact=config.artifact_version,
            dataset=config.eval_dataset
        )
        if eval_score < config.required_eval_score:
            return DeploymentResult(status="rejected", 
                                   reason=f"Eval score {eval_score} < {config.required_eval_score}")
        
        # Phase 2: Blue-Green for embedding models (need full re-index)
        if config.deployment_type == DeploymentType.EMBEDDING_MODEL:
            await self.blue_green_embedding_deploy(config)
        else:
            await self.canary_deploy(config)
    
    async def canary_deploy(self, config: DeploymentConfig):
        """Progressive canary rollout with auto-analysis."""
        # Start canary
        await self.router.set_canary(
            new_version=config.artifact_version,
            percent=config.canary_percent
        )
        
        # Monitor canary metrics
        start = datetime.utcnow()
        while datetime.utcnow() - start < config.canary_duration:
            await asyncio.sleep(60)  # Check every minute
            
            metrics = await self.monitor.compare_canary_vs_baseline()
            
            # Auto-rollback conditions
            if metrics.error_rate_increase > config.auto_rollback_threshold:
                await self.rollback(config, f"Error rate +{metrics.error_rate_increase}")
                return
            if metrics.latency_p99_increase > 0.5:  # 50% latency increase
                await self.rollback(config, f"Latency regression: {metrics.latency_p99_increase}")
                return
            if metrics.quality_score_decrease > config.auto_rollback_threshold:
                await self.rollback(config, f"Quality drop: {metrics.quality_score_decrease}")
                return
        
        # Canary passed — progressive rollout
        for percent in [0.25, 0.50, 0.75, 1.0]:
            await self.router.set_canary(config.artifact_version, percent)
            await asyncio.sleep(300)  # 5 min between stages
            
            if not await self.monitor.is_healthy(config.artifact_version):
                await self.rollback(config, f"Unhealthy at {percent*100}%")
                return
        
        # Full promotion
        await self.router.promote(config.artifact_version)
    
    async def blue_green_embedding_deploy(self, config: DeploymentConfig):
        """Blue-green for embedding model changes (requires re-indexing)."""
        # 1. Build new index in background (green)
        green_index = await self.build_new_index(config.artifact_version)
        
        # 2. Run eval against green index
        green_score = await self.eval.evaluate_index(green_index, config.eval_dataset)
        if green_score < config.required_eval_score:
            await self.cleanup_index(green_index)
            return
        
        # 3. Shadow traffic to green (compare results)
        await self.router.enable_shadow(green_index, sample_rate=0.1)
        await asyncio.sleep(3600)  # 1 hour shadow
        
        comparison = await self.monitor.get_shadow_comparison()
        if comparison.green_better or comparison.equivalent:
            # 4. Atomic swap
            await self.router.swap_to_green(green_index)
            # Keep blue alive for rollback window
            await asyncio.sleep(86400)  # 24h rollback window
            await self.cleanup_index("blue")
        else:
            await self.cleanup_index(green_index)
    
    async def rollback(self, config: DeploymentConfig, reason: str):
        await self.router.rollback_to_previous()
        await self.alert(f"Auto-rollback: {config.artifact_version}. Reason: {reason}")
```

**Deployment Strategy by Change Type:**

| Change Type | Strategy | Downtime | Risk | Duration |
|-------------|----------|----------|------|----------|
| Prompt template | Canary (instant) | Zero | Low | 2 hours |
| LLM version | Canary (gradual) | Zero | Medium | 4 hours |
| Retrieval params | Canary + A/B test | Zero | Medium | 24 hours |
| Embedding model | Blue-green + re-index | Zero | High | Days (re-index time) |

**Production Considerations:**
- **Eval dataset versioning**: Golden eval set must be versioned and updated independently of deployments
- **Metric bake time**: Don't declare canary success too quickly; some regressions appear only at scale
- **Embedding model changes**: Most expensive — requires full re-indexing; schedule during low-traffic
- **Feature flags**: Use feature flags for prompt changes; instant rollback without redeployment
- **Deployment frequency**: Prompt templates weekly, model versions monthly, embedding models quarterly

---

## Q172: Design a configuration management system for AI applications where configurations include model selections, temperature settings, retrieval parameters, and safety thresholds. Include feature flags and gradual rollouts.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│            AI Configuration Management System                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                Configuration Store                          │  │
│  │                                                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │ Static Config│  │ Feature Flags│  │ Dynamic Params   │ │  │
│  │  │ (Git-based)  │  │ (LaunchDarkly│  │ (Real-time       │ │  │
│  │  │              │  │  /Flagsmith) │  │  tunable)        │ │  │
│  │  │ - Model IDs  │  │              │  │                  │ │  │
│  │  │ - Endpoints  │  │ - New RAG    │  │ - Temperature    │ │  │
│  │  │ - API keys   │  │   strategy   │  │ - Top-K          │ │  │
│  │  │              │  │ - Safety v2  │  │ - Thresholds     │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              Config Resolution Engine                        │  │
│  │  (tenant, user, environment, experiment) → resolved config  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from datetime import datetime
import hashlib

@dataclass
class AIConfig:
    """Resolved AI configuration for a specific request context."""
    # Model selection
    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-large"
    
    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.95
    
    # Retrieval parameters
    retrieval_top_k: int = 10
    rerank_top_n: int = 5
    similarity_threshold: float = 0.7
    chunk_size: int = 512
    
    # Safety thresholds
    safety_threshold: float = 0.8
    pii_detection_enabled: bool = True
    content_filter_level: str = "medium"
    
    # Feature flags
    use_hybrid_search: bool = False
    use_query_expansion: bool = False
    use_cross_encoder_rerank: bool = True

@dataclass
class ConfigContext:
    """Context for config resolution (who/what/where)."""
    tenant_id: str
    user_id: Optional[str] = None
    environment: str = "production"
    region: str = "us-east-1"
    user_segment: Optional[str] = None  # "beta", "enterprise", "internal"

class AIConfigManager:
    """Hierarchical config resolution with overrides and experiments."""
    
    def __init__(self, config_store, flag_service, experiment_service):
        self.store = config_store
        self.flags = flag_service
        self.experiments = experiment_service
        self.cache = {}
        self.config_version = 0
    
    def resolve(self, context: ConfigContext) -> AIConfig:
        """Resolve config with precedence: experiment > tenant > environment > default."""
        
        # 1. Start with defaults
        config = AIConfig()
        
        # 2. Apply environment overrides
        env_overrides = self.store.get_env_config(context.environment)
        config = self.apply_overrides(config, env_overrides)
        
        # 3. Apply tenant overrides
        tenant_overrides = self.store.get_tenant_config(context.tenant_id)
        config = self.apply_overrides(config, tenant_overrides)
        
        # 4. Apply feature flags
        config = self.apply_feature_flags(config, context)
        
        # 5. Apply experiment overrides (A/B tests)
        config = self.apply_experiments(config, context)
        
        return config
    
    def apply_feature_flags(self, config: AIConfig, context: ConfigContext) -> AIConfig:
        """Evaluate feature flags for this context."""
        flags = self.flags.evaluate_all(
            user_id=context.user_id,
            attributes={
                "tenant": context.tenant_id,
                "segment": context.user_segment,
                "region": context.region
            }
        )
        
        if flags.get("hybrid_search_enabled"):
            config.use_hybrid_search = True
        if flags.get("new_safety_model"):
            config.safety_threshold = 0.85
            config.content_filter_level = "strict"
        if flags.get("gpt4o_mini_rollout"):
            config.llm_model = "gpt-4o-mini"
        
        return config
    
    def apply_experiments(self, config: AIConfig, context: ConfigContext) -> AIConfig:
        """Apply A/B experiment variants."""
        experiments = self.experiments.get_active(context.user_id)
        
        for exp in experiments:
            if exp.name == "temperature_optimization":
                config.temperature = exp.variant_value  # e.g., 0.3 vs 0.7
            elif exp.name == "retrieval_top_k_test":
                config.retrieval_top_k = exp.variant_value
        
        return config

class GradualRollout:
    """Manage gradual rollout of config changes."""
    
    async def rollout_config_change(self, param: str, new_value: Any, 
                                     schedule: List[dict]):
        """
        schedule = [
            {"percent": 5, "duration_hours": 2},
            {"percent": 25, "duration_hours": 4},
            {"percent": 50, "duration_hours": 12},
            {"percent": 100, "duration_hours": 0},
        ]
        """
        for stage in schedule:
            await self.flags.update_rollout(
                flag=f"config_{param}_rollout",
                percent=stage["percent"],
                value=new_value
            )
            
            if stage["duration_hours"] > 0:
                # Monitor and wait
                healthy = await self.monitor_and_wait(
                    param, hours=stage["duration_hours"]
                )
                if not healthy:
                    await self.flags.rollback(f"config_{param}_rollout")
                    return False
        
        # Bake into static config
        await self.store.update_default(param, new_value)
        await self.flags.delete(f"config_{param}_rollout")
        return True
```

**Configuration Hierarchy:**

| Level | Source | Change Speed | Review Required |
|-------|--------|-------------|-----------------|
| Default | Git (code review) | Days | Yes (PR) |
| Environment | Git + deploy | Hours | Yes (PR) |
| Tenant | Admin API | Minutes | Ops approval |
| Feature flag | Flag service | Seconds | Flag owner |
| Experiment | Experiment platform | Instant | Data science |
| Emergency | Kill switch | Instant | On-call only |

**Production Considerations:**
- **Config drift detection**: Alert when runtime config diverges from declared config (indicates stale cache)
- **Audit trail**: Every config change logged with who/when/why; revertible
- **Validation**: Schema validation prevents invalid configs (temperature must be 0-2, top_k must be positive)
- **Dependencies**: Some configs are interdependent (changing embedding model requires changing index)
- **Hot reload**: Config changes propagate without restart; use push (webhook) not poll

---

## Q173: Design a runbook automation system for common AI operational tasks: index rebuilding, model swapping, cache warming, embedding migration, and quality regression investigation.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Runbook Automation System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Runbook Registry                               │  │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │  │
│  │  │Index Rebuild  │  │Model Swap     │  │Cache Warm     │  │  │
│  │  │              │  │              │  │              │  │  │
│  │  │Trigger: manual│  │Trigger: deploy│  │Trigger: scale│  │  │
│  │  │  or schedule │  │  pipeline    │  │  event       │  │  │
│  │  └───────────────┘  └───────────────┘  └───────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              Execution Engine                               │  │
│  │  ┌──────────┐  ┌───────────┐  ┌────────────────────────┐  │  │
│  │  │Pre-checks│─▶│Step Runner│─▶│Verification + Rollback │  │  │
│  │  └──────────┘  └───────────┘  └────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Human-in-Loop: Approval gates for destructive operations   │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Dict
from datetime import datetime
from enum import Enum
import asyncio

class RunbookStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

@dataclass
class RunbookStep:
    name: str
    execute: Callable
    verify: Callable              # Verify step succeeded
    rollback: Optional[Callable] = None
    requires_approval: bool = False
    timeout_minutes: int = 30
    
@dataclass
class RunbookExecution:
    runbook_name: str
    execution_id: str
    triggered_by: str
    status: RunbookStatus = RunbookStatus.PENDING
    current_step: int = 0
    logs: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class RunbookEngine:
    """Executes operational runbooks with safety checks."""
    
    async def execute_runbook(self, runbook_name: str, params: dict, 
                              triggered_by: str) -> RunbookExecution:
        runbook = self.registry.get(runbook_name)
        execution = RunbookExecution(
            runbook_name=runbook_name,
            execution_id=self.generate_id(),
            triggered_by=triggered_by,
            started_at=datetime.utcnow()
        )
        
        # Pre-flight checks
        preflight = await self.run_preflight(runbook, params)
        if not preflight.passed:
            execution.status = RunbookStatus.FAILED
            execution.logs.append(f"Preflight failed: {preflight.reason}")
            return execution
        
        execution.status = RunbookStatus.RUNNING
        
        for i, step in enumerate(runbook.steps):
            execution.current_step = i
            execution.logs.append(f"Starting step: {step.name}")
            
            # Approval gate
            if step.requires_approval:
                execution.status = RunbookStatus.AWAITING_APPROVAL
                approved = await self.wait_for_approval(execution, step)
                if not approved:
                    execution.status = RunbookStatus.FAILED
                    return execution
                execution.status = RunbookStatus.RUNNING
            
            # Execute step
            try:
                await asyncio.wait_for(
                    step.execute(params),
                    timeout=step.timeout_minutes * 60
                )
            except Exception as e:
                execution.logs.append(f"Step {step.name} failed: {e}")
                await self.rollback_completed_steps(runbook.steps[:i], params)
                execution.status = RunbookStatus.ROLLED_BACK
                return execution
            
            # Verify step
            if not await step.verify(params):
                execution.logs.append(f"Verification failed for: {step.name}")
                await self.rollback_completed_steps(runbook.steps[:i+1], params)
                execution.status = RunbookStatus.ROLLED_BACK
                return execution
            
            execution.logs.append(f"Completed: {step.name}")
        
        execution.status = RunbookStatus.COMPLETED
        execution.completed_at = datetime.utcnow()
        return execution

# ===== Concrete Runbooks =====

class IndexRebuildRunbook:
    """Runbook: Full vector index rebuild."""
    
    @property
    def steps(self) -> List[RunbookStep]:
        return [
            RunbookStep(
                name="snapshot_current_index",
                execute=self.snapshot_index,
                verify=self.verify_snapshot,
            ),
            RunbookStep(
                name="build_new_index",
                execute=self.build_index,
                verify=self.verify_new_index,
                timeout_minutes=240  # 4 hours for large indices
            ),
            RunbookStep(
                name="run_quality_eval",
                execute=self.evaluate_quality,
                verify=self.verify_quality_meets_threshold,
            ),
            RunbookStep(
                name="swap_index_alias",
                execute=self.swap_alias,
                verify=self.verify_serving_new_index,
                requires_approval=True,  # Human approval before swap
                rollback=self.restore_old_alias,
            ),
            RunbookStep(
                name="warm_cache",
                execute=self.warm_cache_with_top_queries,
                verify=self.verify_cache_hit_rate,
            ),
            RunbookStep(
                name="cleanup_old_index",
                execute=self.schedule_old_index_deletion,
                verify=lambda _: True,  # Best effort
                timeout_minutes=5
            ),
        ]

class QualityRegressionInvestigation:
    """Runbook: Automated quality regression investigation."""
    
    @property
    def steps(self) -> List[RunbookStep]:
        return [
            RunbookStep(
                name="collect_regression_samples",
                execute=self.collect_failed_queries,
                verify=lambda _: True,
            ),
            RunbookStep(
                name="compare_with_baseline",
                execute=self.run_ab_comparison,
                verify=lambda _: True,
            ),
            RunbookStep(
                name="identify_root_cause",
                execute=self.classify_regression_type,
                verify=lambda _: True,
            ),
            RunbookStep(
                name="generate_report",
                execute=self.create_investigation_report,
                verify=lambda _: True,
            ),
            RunbookStep(
                name="propose_remediation",
                execute=self.suggest_fix,
                verify=lambda _: True,
            ),
        ]
    
    async def classify_regression_type(self, params):
        """Automated root cause classification."""
        samples = params["regression_samples"]
        
        # Check: Is it retrieval or generation?
        retrieval_quality = await self.eval_retrieval_only(samples)
        generation_quality = await self.eval_generation_only(samples)
        
        if retrieval_quality.degraded:
            params["root_cause"] = "retrieval"
            params["details"] = await self.diagnose_retrieval(samples)
        elif generation_quality.degraded:
            params["root_cause"] = "generation"
            params["details"] = await self.diagnose_generation(samples)
        else:
            params["root_cause"] = "data_quality"
            params["details"] = await self.diagnose_data(samples)
```

**Runbook Catalog:**

| Runbook | Trigger | Duration | Approval | Risk |
|---------|---------|----------|----------|------|
| Index Rebuild | Schedule/Manual | 4-8 hours | Yes (swap) | Medium |
| Model Swap | Deploy pipeline | 30 min | No (automated) | Low |
| Cache Warm | Scale event | 15 min | No | Low |
| Embedding Migration | Manual | Days | Yes (each phase) | High |
| Quality Investigation | Alert | 1 hour | No | None |
| Emergency Rollback | PagerDuty | 5 min | No (auto) | Recovery |

**Production Considerations:**
- **Runbook versioning**: Runbooks are code, stored in git, reviewed via PR
- **Dry-run mode**: Every runbook supports `--dry-run` that logs actions without executing
- **Parallel execution prevention**: Lock mechanism prevents two conflicting runbooks from running simultaneously
- **Notifications**: Slack/PagerDuty updates at each step; final summary on completion
- **Metrics**: Track runbook success rate, duration, and manual intervention frequency

---

## Q174: Design the on-call rotation and escalation process for an AI platform team. What pages are AI-specific? How does on-call differ for AI vs traditional services? Include response time SLAs.

### Answer

**On-Call Structure:**

```
┌─────────────────────────────────────────────────────────────────┐
│              AI Platform On-Call Structure                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Tier 1: Primary On-Call (AI Platform Engineer)                   │
│  ├── Response: 5 min (P1), 15 min (P2), 1 hour (P3)             │
│  ├── Scope: Infrastructure, availability, latency                │
│  └── Tools: Runbook automation, dashboards, rollback             │
│                                                                   │
│  Tier 2: AI/ML Specialist (ML Engineer)                          │
│  ├── Response: 15 min (P1), 30 min (P2)                         │
│  ├── Scope: Model quality, embedding drift, RAG accuracy         │
│  └── Tools: Eval pipelines, model comparison, data analysis      │
│                                                                   │
│  Tier 3: Domain Expert / Team Lead                               │
│  ├── Response: 30 min (P1)                                       │
│  ├── Scope: Architecture decisions, customer escalations         │
│  └── Tools: Cross-team coordination, vendor escalation           │
│                                                                   │
│  Escalation Path:                                                 │
│  Alert → Tier 1 (5min) → No ack → Tier 2 (10min) → Tier 3      │
└─────────────────────────────────────────────────────────────────┘
```

**AI-Specific Alert Categories:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import List

class Severity(Enum):
    P1_CRITICAL = "p1"   # Service down, data loss risk
    P2_HIGH = "p2"       # Degraded quality, partial outage
    P3_MEDIUM = "p3"     # Quality drift, non-urgent
    P4_LOW = "p4"        # Informational, optimization opportunity

@dataclass
class AIAlert:
    name: str
    severity: Severity
    description: str
    response_sla_minutes: int
    runbook_link: str
    ai_specific: bool = True

AI_ALERT_CATALOG = [
    # === Infrastructure Alerts (similar to traditional) ===
    AIAlert("vector_db_down", Severity.P1_CRITICAL,
            "Vector database unreachable", 5,
            "runbooks/vector_db_recovery"),
    AIAlert("llm_provider_5xx", Severity.P1_CRITICAL,
            "LLM provider returning 500s", 5,
            "runbooks/llm_failover"),
    AIAlert("embedding_service_latency", Severity.P2_HIGH,
            "Embedding p99 > 500ms", 15,
            "runbooks/embedding_scaling"),
    
    # === AI-SPECIFIC Alerts (unique to AI platforms) ===
    AIAlert("quality_score_drop", Severity.P2_HIGH,
            "RAG quality score dropped >10% in 1 hour", 15,
            "runbooks/quality_regression_investigation",
            ai_specific=True),
    AIAlert("embedding_drift_detected", Severity.P3_MEDIUM,
            "Embedding distribution drift > threshold", 60,
            "runbooks/embedding_drift_analysis",
            ai_specific=True),
    AIAlert("hallucination_rate_spike", Severity.P2_HIGH,
            "Hallucination rate >5% (normally <1%)", 15,
            "runbooks/hallucination_investigation",
            ai_specific=True),
    AIAlert("cost_anomaly", Severity.P3_MEDIUM,
            "Token spend 3x above normal", 60,
            "runbooks/cost_investigation",
            ai_specific=True),
    AIAlert("safety_filter_bypass", Severity.P1_CRITICAL,
            "Safety filter failed to catch harmful content", 5,
            "runbooks/safety_incident",
            ai_specific=True),
    AIAlert("index_staleness", Severity.P3_MEDIUM,
            "Documents not indexed for >1 hour", 60,
            "runbooks/ingestion_pipeline_check",
            ai_specific=True),
    AIAlert("model_version_mismatch", Severity.P2_HIGH,
            "Serving model differs from deployed config", 15,
            "runbooks/model_version_check",
            ai_specific=True),
    AIAlert("retrieval_empty_rate_spike", Severity.P2_HIGH,
            "Empty retrieval results >20% (normally <5%)", 15,
            "runbooks/retrieval_debug",
            ai_specific=True),
]
```

**How AI On-Call Differs from Traditional:**

| Dimension | Traditional Service | AI Platform |
|-----------|-------------------|-------------|
| Failure mode | Binary (up/down) | Gradual (quality degradation) |
| Detection | Health checks, error rates | Quality metrics, drift detection |
| Root cause | Code bug, infra failure | Data change, model drift, prompt issue |
| Fix | Rollback code, scale infra | Rollback model, fix data, tune params |
| Investigation | Logs, traces | Eval pipelines, sample analysis |
| Time to detect | Seconds (errors spike) | Minutes-hours (quality drift) |
| Vendor dependency | Low (own infra) | High (LLM provider outages) |
| Cost risk | Linear (more traffic) | Nonlinear (prompt injection → infinite loops) |

**Escalation Decision Tree:**

```python
class EscalationEngine:
    def determine_escalation(self, alert: AIAlert, context: dict):
        """AI-specific escalation logic."""
        
        if alert.name == "safety_filter_bypass":
            # Always escalate safety to leadership immediately
            return [Tier.T1, Tier.T3, "security_team", "legal"]
        
        if alert.name == "quality_score_drop":
            # Run automated investigation first
            investigation = self.run_auto_investigation(context)
            if investigation.root_cause == "data":
                return [Tier.T1]  # Ops can handle data pipeline issues
            elif investigation.root_cause == "model":
                return [Tier.T2]  # ML engineer needed
            else:
                return [Tier.T1, Tier.T2]  # Both
        
        if alert.name == "cost_anomaly":
            # Check if it's a runaway prompt or legitimate traffic
            if context["token_per_request"] > 10 * context["baseline_tokens"]:
                return [Tier.T1]  # Likely prompt injection, ops can kill
            else:
                return [Tier.T1]  # Traffic spike, scale or rate limit
```

**Production Considerations:**
- **On-call training**: AI on-call requires ML fundamentals training; not just infra skills
- **Quality dashboards**: Real-time quality metrics visible to on-call (not just latency/errors)
- **Incident taxonomy**: Classify AI incidents separately (quality vs availability vs safety vs cost)
- **Blameless postmortems**: AI failures are often subtle; focus on detection speed improvement
- **Rotation balance**: Mix platform engineers and ML engineers in rotation pairs

---

## Q175: Design a capacity reservation and scheduling system for GPU infrastructure. Handle competing priorities between training jobs, batch inference, and real-time serving on shared GPU clusters.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│            GPU Capacity Management System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Priority Scheduler                              │  │
│  │                                                              │  │
│  │  P0: Real-time Serving (guaranteed, non-preemptible)        │  │
│  │  P1: SLA-bound Batch Inference (preemptible after deadline) │  │
│  │  P2: Training Jobs (preemptible, checkpointable)            │  │
│  │  P3: Experiments (best-effort, spot-like)                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              GPU Pool Management                             │  │
│  │                                                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │ Reserved Pool│  │ Shared Pool  │  │ Burst Pool       │ │  │
│  │  │ (Serving)    │  │ (Scheduled)  │  │ (Auto-scale/Spot)│ │  │
│  │  │ A100×16      │  │ A100×48      │  │ A100×0-32        │ │  │
│  │  │ Always-on    │  │ Time-sliced  │  │ On-demand        │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Scheduling: Bin-packing + Priority + Preemption            │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from enum import Enum
import heapq

class JobPriority(Enum):
    SERVING = 0      # Highest: real-time inference
    BATCH_SLA = 1    # Batch with deadline
    TRAINING = 2     # Training jobs
    EXPERIMENT = 3   # Best-effort experiments

@dataclass
class GPURequest:
    job_id: str
    priority: JobPriority
    gpu_count: int
    gpu_type: str = "A100"
    memory_gb: int = 80
    duration_estimate: timedelta = timedelta(hours=4)
    deadline: Optional[datetime] = None
    preemptible: bool = True
    checkpointable: bool = True
    team: str = ""
    cost_center: str = ""

@dataclass
class GPUAllocation:
    job_id: str
    gpu_ids: List[str]
    node_id: str
    allocated_at: datetime
    expires_at: Optional[datetime] = None

class GPUScheduler:
    """Priority-based GPU scheduler with preemption and bin-packing."""
    
    def __init__(self, cluster_state, quota_manager):
        self.cluster = cluster_state
        self.quotas = quota_manager
        self.queue: List[GPURequest] = []
    
    def schedule(self, request: GPURequest) -> Optional[GPUAllocation]:
        # 1. Check team quota
        if not self.quotas.can_allocate(request.team, request.gpu_count):
            return self.queue_request(request)
        
        # 2. Try direct allocation (find free GPUs)
        free_gpus = self.cluster.find_free_gpus(
            count=request.gpu_count,
            gpu_type=request.gpu_type,
            memory_gb=request.memory_gb
        )
        
        if free_gpus:
            return self.allocate(request, free_gpus)
        
        # 3. Try preemption (only if higher priority)
        if request.priority.value < JobPriority.TRAINING.value:
            preemptable = self.find_preemptable_jobs(request)
            if preemptable:
                return self.preempt_and_allocate(request, preemptable)
        
        # 4. Queue if no capacity
        return self.queue_request(request)
    
    def find_preemptable_jobs(self, request: GPURequest) -> List[str]:
        """Find lower-priority jobs that can be preempted."""
        candidates = []
        needed = request.gpu_count
        
        # Find running jobs with lower priority
        running = self.cluster.get_running_jobs(
            gpu_type=request.gpu_type,
            min_priority=request.priority.value + 1  # Lower priority only
        )
        
        # Sort by priority (lowest first), then by runtime (longest first)
        running.sort(key=lambda j: (j.priority.value, -j.runtime_minutes))
        
        for job in running:
            if not job.preemptible:
                continue
            candidates.append(job.job_id)
            needed -= job.gpu_count
            if needed <= 0:
                break
        
        return candidates if needed <= 0 else []
    
    async def preempt_and_allocate(self, request, victim_jobs):
        """Preempt jobs gracefully (checkpoint first)."""
        for job_id in victim_jobs:
            job = self.cluster.get_job(job_id)
            
            if job.checkpointable:
                # Give 60s to checkpoint
                await self.signal_checkpoint(job_id, grace_period=60)
                await self.wait_for_checkpoint(job_id, timeout=60)
            
            await self.evict_job(job_id)
            # Re-queue evicted job
            self.queue_request(job.request, reason="preempted")
        
        # Now allocate freed GPUs
        free_gpus = self.cluster.find_free_gpus(
            count=request.gpu_count, gpu_type=request.gpu_type
        )
        return self.allocate(request, free_gpus)

class CapacityReservation:
    """Advance reservation for guaranteed capacity."""
    
    def __init__(self, reservation_store):
        self.reservations = reservation_store
    
    def reserve(self, team: str, gpu_count: int, gpu_type: str,
                start: datetime, end: datetime) -> str:
        """Reserve GPU capacity for a future time window."""
        
        # Check availability in time window
        available = self.check_availability(gpu_type, start, end)
        if available < gpu_count:
            raise InsufficientCapacity(
                f"Only {available} {gpu_type} available in window"
            )
        
        reservation_id = self.reservations.create({
            "team": team,
            "gpu_count": gpu_count,
            "gpu_type": gpu_type,
            "start": start,
            "end": end,
            "status": "confirmed"
        })
        
        return reservation_id
    
    def get_utilization_forecast(self, hours_ahead: int = 24) -> dict:
        """Forecast GPU utilization based on reservations + historical patterns."""
        reservations = self.reservations.get_upcoming(hours=hours_ahead)
        historical = self.get_historical_demand(hours_ahead)
        
        forecast = {}
        for hour in range(hours_ahead):
            reserved = sum(r.gpu_count for r in reservations 
                         if r.covers_hour(hour))
            predicted_spot = historical.get_demand(hour)
            forecast[hour] = {
                "reserved": reserved,
                "predicted_demand": predicted_spot,
                "available": self.cluster.total_gpus - reserved
            }
        
        return forecast
```

**Scheduling Policy:**

| Job Type | Preemptible | Checkpoint | Max Wait | GPU Pool |
|----------|-------------|------------|----------|----------|
| Real-time Serving | No | N/A | 0 (always on) | Reserved |
| Batch Inference (SLA) | After deadline | Yes | Until deadline | Shared |
| Training | Yes (with grace) | Every 30min | Hours | Shared + Burst |
| Experiments | Yes (immediate) | Optional | Days | Burst (spot) |

**Production Considerations:**
- **Fragmentation**: Use bin-packing to avoid GPU fragmentation across nodes; prefer filling nodes completely
- **Quota system**: Each team gets guaranteed minimum + burst capacity; prevents hoarding
- **Cost attribution**: Track GPU-hours per team/project for chargeback
- **Spot/preemptible savings**: Experiments use spot instances (60-70% cheaper); auto-checkpoint on preemption signal
- **Monitoring**: Track GPU utilization (target >80%), queue wait times, preemption frequency, and waste (allocated but idle)
# AI Agents and Autonomous Systems (Questions 181-185)

## Q181: Design a production AI agent framework that supports tool use, multi-step planning, memory, and error recovery. Include safety boundaries, cost limits, and human-in-the-loop breakpoints.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Production AI Agent Framework                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Agent Loop                                 │    │
│  │                                                               │    │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────────────┐ │    │
│  │  │ Plan   │──▶│ Select │──▶│Execute │──▶│ Observe/Reflect│ │    │
│  │  │        │   │ Tool   │   │ Tool   │   │                │ │    │
│  │  └────────┘   └────────┘   └───┬────┘   └────────┬───────┘ │    │
│  │       ▲                         │                  │         │    │
│  │       └─────────────────────────┴──────────────────┘         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Safety & Control Layer                                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐  │   │
│  │  │ Cost     │ │ Step     │ │ Permission │ │ Human-in-    │  │   │
│  │  │ Budget   │ │ Limit    │ │ Boundary   │ │ the-Loop     │  │   │
│  │  └──────────┘ └──────────┘ └────────────┘ └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Memory Layer                                                  │   │
│  │  ┌──────────┐ ┌────────────────┐ ┌──────────────────────┐   │   │
│  │  │ Working  │ │ Episodic       │ │ Semantic (Long-term) │   │   │
│  │  │ Memory   │ │ (Session)      │ │ (Cross-session)      │   │   │
│  │  └──────────┘ └────────────────┘ └──────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import asyncio

class AgentState(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_APPROVAL = "waiting_approval"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class SafetyConfig:
    max_steps: int = 25
    max_cost_usd: float = 5.0
    max_duration_seconds: int = 300
    max_tool_calls: int = 50
    require_approval_for: List[str] = field(default_factory=lambda: [
        "write_file", "execute_code", "send_email", "deploy"
    ])
    blocked_actions: List[str] = field(default_factory=lambda: [
        "delete_production_db", "rm_rf"
    ])

@dataclass
class AgentContext:
    goal: str
    state: AgentState = AgentState.PLANNING
    steps_taken: int = 0
    cost_spent: float = 0.0
    working_memory: List[dict] = field(default_factory=list)
    plan: List[str] = field(default_factory=list)
    tool_results: List[dict] = field(default_factory=list)
    errors: List[dict] = field(default_factory=list)

class ProductionAgent:
    def __init__(self, llm, tools: Dict[str, "Tool"], safety: SafetyConfig, 
                 memory_store, approval_queue):
        self.llm = llm
        self.tools = tools
        self.safety = safety
        self.memory = memory_store
        self.approval = approval_queue
    
    async def run(self, goal: str, session_id: str) -> dict:
        ctx = AgentContext(goal=goal)
        
        # Load relevant memory from past sessions
        past_context = await self.memory.retrieve_relevant(goal)
        if past_context:
            ctx.working_memory.append({"type": "past_experience", "data": past_context})
        
        while ctx.state not in (AgentState.COMPLETED, AgentState.FAILED):
            # Safety checks
            if violation := self.check_safety(ctx):
                ctx.state = AgentState.FAILED
                return {"status": "failed", "reason": f"Safety limit: {violation}"}
            
            try:
                if ctx.state == AgentState.PLANNING:
                    ctx.plan = await self.plan(ctx)
                    ctx.state = AgentState.EXECUTING
                
                elif ctx.state == AgentState.EXECUTING:
                    next_action = await self.select_action(ctx)
                    
                    if next_action["action"] == "complete":
                        ctx.state = AgentState.COMPLETED
                    elif next_action["tool"] in self.safety.require_approval_for:
                        ctx.state = AgentState.WAITING_APPROVAL
                        await self.request_approval(ctx, next_action)
                    else:
                        result = await self.execute_action(next_action, ctx)
                        ctx.tool_results.append(result)
                        ctx.steps_taken += 1
                        ctx.state = AgentState.REFLECTING
                
                elif ctx.state == AgentState.WAITING_APPROVAL:
                    approved = await self.approval.wait(timeout=300)
                    if approved:
                        result = await self.execute_action(approved.action, ctx)
                        ctx.tool_results.append(result)
                        ctx.state = AgentState.REFLECTING
                    else:
                        ctx.state = AgentState.REFLECTING  # Replan without this action
                
                elif ctx.state == AgentState.REFLECTING:
                    reflection = await self.reflect(ctx)
                    if reflection["needs_replan"]:
                        ctx.state = AgentState.PLANNING
                    else:
                        ctx.state = AgentState.EXECUTING
            
            except Exception as e:
                ctx.errors.append({"step": ctx.steps_taken, "error": str(e)})
                recovery = await self.recover(ctx, e)
                if recovery == "retry":
                    continue
                elif recovery == "replan":
                    ctx.state = AgentState.PLANNING
                else:
                    ctx.state = AgentState.FAILED
        
        # Save experience to memory
        await self.memory.save_episode(session_id, ctx)
        
        return {"status": ctx.state.value, "steps": ctx.steps_taken, 
                "cost": ctx.cost_spent, "results": ctx.tool_results}
    
    def check_safety(self, ctx: AgentContext) -> Optional[str]:
        if ctx.steps_taken >= self.safety.max_steps:
            return f"Max steps ({self.safety.max_steps}) exceeded"
        if ctx.cost_spent >= self.safety.max_cost_usd:
            return f"Cost budget (${self.safety.max_cost_usd}) exceeded"
        return None
    
    async def recover(self, ctx: AgentContext, error: Exception) -> str:
        """Error recovery strategy."""
        # Check if same error repeated
        similar_errors = [e for e in ctx.errors if e["error"] == str(error)]
        
        if len(similar_errors) >= 3:
            return "fail"  # Same error 3 times, give up
        elif len(similar_errors) == 2:
            return "replan"  # Try different approach
        else:
            return "retry"  # First time, retry
    
    async def reflect(self, ctx: AgentContext) -> dict:
        """Reflect on last action result and decide next step."""
        prompt = f"""Goal: {ctx.goal}
Plan: {ctx.plan}
Last result: {ctx.tool_results[-1] if ctx.tool_results else 'None'}
Progress: Step {ctx.steps_taken}/{self.safety.max_steps}

Did the last action move us toward the goal? Should we continue with the plan or replan?"""
        
        reflection = await self.llm.generate(prompt)
        return {"needs_replan": "replan" in reflection.lower()}
```

**Tool Permission Model:**

| Permission Level | Tools | Approval | Example |
|-----------------|-------|----------|---------|
| Read-only | search, read_file, query_db | None | Safe exploration |
| Write-safe | create_file, update_doc | None | Reversible writes |
| Write-destructive | delete, overwrite | Human approval | Irreversible |
| External | send_email, API calls | Human approval | Side effects |
| Privileged | deploy, admin commands | Admin approval + MFA | Production impact |

**Production Considerations:**
- **Idempotent tools**: Design tools to be safely re-callable (agent may retry on error)
- **Cost tracking**: Count tokens per LLM call + tool execution cost; surface real-time budget remaining
- **Audit trail**: Every action logged with reasoning; replayable for debugging
- **Graceful timeout**: On timeout, save state; allow resume from checkpoint
- **Observability**: Real-time streaming of agent's reasoning and actions to monitoring dashboard

---

## Q182: Design a multi-agent system where specialized agents (researcher, coder, reviewer, deployer) collaborate on complex tasks. Include coordination protocols, conflict resolution, and shared state management.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Multi-Agent Collaboration System                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  Orchestrator Agent                           │    │
│  │  (Decomposes task, assigns to specialists, manages flow)     │    │
│  └────────────────────────────┬────────────────────────────────┘    │
│                                │                                     │
│       ┌────────────────────────┼─────────────────────┐              │
│       ▼                        ▼                     ▼              │
│  ┌──────────┐          ┌──────────┐          ┌──────────┐          │
│  │Researcher│          │  Coder   │          │ Reviewer │          │
│  │Agent     │          │  Agent   │          │ Agent    │          │
│  │          │          │          │          │          │          │
│  │- Search  │          │- Write   │          │- Review  │          │
│  │- Analyze │          │- Test    │          │- Critique│          │
│  │- Summarize│         │- Debug   │          │- Approve │          │
│  └─────┬────┘          └─────┬────┘          └─────┬────┘          │
│        └──────────────────────┴──────────────────────┘              │
│                               │                                      │
│  ┌────────────────────────────▼────────────────────────────────┐   │
│  │              Shared State (Blackboard Pattern)                │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │   │
│  │  │ Task Board  │  │ Artifacts    │  │ Communication Log  │ │   │
│  │  │ (Kanban)    │  │ (Files, Docs)│  │ (Message History)  │ │   │
│  │  └─────────────┘  └──────────────┘  └────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import asyncio

class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    DEPLOYER = "deployer"

@dataclass
class Task:
    id: str
    description: str
    assigned_to: AgentRole
    status: str = "pending"  # pending, in_progress, blocked, completed, failed
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    
@dataclass
class Message:
    from_agent: AgentRole
    to_agent: AgentRole  # or "all" for broadcast
    content: str
    message_type: str  # "request", "response", "critique", "approval"
    references: List[str] = field(default_factory=list)

class SharedState:
    """Blackboard pattern for shared agent state."""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.artifacts: Dict[str, Any] = {}
        self.messages: List[Message] = []
        self.locks: Dict[str, str] = {}  # artifact_id -> agent_role
    
    async def acquire_artifact(self, artifact_id: str, agent: AgentRole) -> bool:
        """Pessimistic lock on shared artifacts."""
        if artifact_id in self.locks and self.locks[artifact_id] != agent.value:
            return False
        self.locks[artifact_id] = agent.value
        return True
    
    def release_artifact(self, artifact_id: str, agent: AgentRole):
        if self.locks.get(artifact_id) == agent.value:
            del self.locks[artifact_id]

class MultiAgentOrchestrator:
    """Coordinates multiple specialized agents."""
    
    def __init__(self, agents: Dict[AgentRole, "Agent"], shared_state: SharedState):
        self.agents = agents
        self.state = shared_state
        self.max_iterations = 10
    
    async def execute_complex_task(self, goal: str) -> dict:
        # Step 1: Decompose into subtasks
        tasks = await self.decompose(goal)
        for task in tasks:
            self.state.tasks[task.id] = task
        
        # Step 2: Execute with dependency resolution
        iteration = 0
        while not self.all_complete() and iteration < self.max_iterations:
            iteration += 1
            
            # Find ready tasks (dependencies met)
            ready = [t for t in self.state.tasks.values() 
                    if t.status == "pending" and self.dependencies_met(t)]
            
            # Execute ready tasks in parallel (different agents)
            execute_tasks = []
            for task in ready:
                agent = self.agents[task.assigned_to]
                execute_tasks.append(self.execute_task(agent, task))
            
            results = await asyncio.gather(*execute_tasks, return_exceptions=True)
            
            # Handle results and conflicts
            for task, result in zip(ready, results):
                if isinstance(result, Exception):
                    task.status = "failed"
                    await self.handle_failure(task, result)
                else:
                    task.result = result
                    task.status = "completed"
            
            # Check for conflicts between agents' outputs
            conflicts = self.detect_conflicts()
            if conflicts:
                await self.resolve_conflicts(conflicts)
        
        return self.compile_results()
    
    async def execute_task(self, agent, task: Task):
        """Execute a single task with an agent."""
        task.status = "in_progress"
        
        # Provide agent with relevant context
        context = {
            "task": task.description,
            "dependencies_results": self.get_dependency_results(task),
            "messages": self.get_relevant_messages(task),
            "artifacts": self.get_relevant_artifacts(task)
        }
        
        result = await agent.execute(context)
        
        # Store artifacts produced
        if result.get("artifacts"):
            for name, content in result["artifacts"].items():
                self.state.artifacts[name] = content
        
        return result
    
    async def resolve_conflicts(self, conflicts: List[dict]):
        """Resolve conflicts between agents' outputs."""
        for conflict in conflicts:
            if conflict["type"] == "code_conflict":
                # Reviewer agent arbitrates
                reviewer = self.agents[AgentRole.REVIEWER]
                resolution = await reviewer.resolve_conflict(
                    conflict["agent_a_output"],
                    conflict["agent_b_output"],
                    conflict["context"]
                )
                self.apply_resolution(conflict, resolution)
            
            elif conflict["type"] == "design_disagreement":
                # Orchestrator makes final call based on constraints
                resolution = await self.orchestrator_decide(conflict)
                self.apply_resolution(conflict, resolution)
    
    async def decompose(self, goal: str) -> List[Task]:
        """Decompose goal into tasks assigned to specialist agents."""
        orchestrator = self.agents[AgentRole.ORCHESTRATOR]
        
        plan = await orchestrator.plan(goal)
        
        # Example decomposition:
        # "Build a REST API for user management" →
        # [Research(best practices), Code(implement), Review(quality), Deploy(ship)]
        
        tasks = []
        for step in plan["steps"]:
            tasks.append(Task(
                id=step["id"],
                description=step["description"],
                assigned_to=AgentRole(step["agent"]),
                dependencies=step.get("depends_on", [])
            ))
        
        return tasks

class SpecializedAgent:
    """Base class for specialized agents."""
    
    def __init__(self, role: AgentRole, llm, tools: List["Tool"]):
        self.role = role
        self.llm = llm
        self.tools = tools
    
    async def execute(self, context: dict) -> dict:
        """Execute task within specialization."""
        system_prompt = self.get_system_prompt()
        
        result = await self.agent_loop(
            system_prompt=system_prompt,
            task=context["task"],
            context=context
        )
        
        return result
    
    def get_system_prompt(self) -> str:
        prompts = {
            AgentRole.RESEARCHER: "You are a research agent. Find relevant information, analyze it, and provide summaries with citations.",
            AgentRole.CODER: "You are a coding agent. Write clean, tested, production-ready code based on requirements.",
            AgentRole.REVIEWER: "You are a code reviewer. Analyze code for bugs, security issues, performance, and best practices.",
        }
        return prompts[self.role]
```

**Coordination Protocols:**

| Protocol | Use Case | Pattern |
|----------|----------|---------|
| Pipeline | Sequential tasks (research → code → review) | Chain |
| Blackboard | Shared artifact editing | Publish-subscribe with locks |
| Contract Net | Task assignment to best-suited agent | Bid/award |
| Voting | Design decisions with disagreement | Majority/weighted vote |
| Escalation | Unresolvable conflicts | Orchestrator decides |

**Production Considerations:**
- **Token efficiency**: Agents share summaries not full context; avoid re-processing same information
- **Deadlock prevention**: Timeout on locks; orchestrator can force-release after deadline
- **Cost allocation**: Track cost per agent; optimize expensive agents (reduce unnecessary LLM calls)
- **Observability**: Visualize agent communication graph; identify bottleneck agents
- **Failure isolation**: One agent failing doesn't kill the whole system; orchestrator reassigns or works around

---

## Q183: Design a sandboxed code execution environment for AI agents that need to write and run code. Include security isolation, resource limits, network restrictions, and output validation.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Sandboxed Code Execution Environment                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Agent Request: "Run this Python code"                      │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                            ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Pre-Execution Pipeline                                     │  │
│  │  1. Static analysis (detect dangerous patterns)             │  │
│  │  2. Dependency resolution (approved packages only)          │  │
│  │  3. Resource estimation                                     │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                            ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Execution Sandbox (gVisor / Firecracker / nsjail)          │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  ┌─────────────┐  ┌────────────┐  ┌─────────────┐   │  │  │
│  │  │  │ CPU: 2 core │  │ Mem: 512MB │  │ Disk: 1GB   │   │  │  │
│  │  │  │ Time: 30s   │  │ No swap    │  │ tmpfs only  │   │  │  │
│  │  │  └─────────────┘  └────────────┘  └─────────────┘   │  │  │
│  │  │  ┌─────────────────────────────────────────────────┐ │  │  │
│  │  │  │ Network: BLOCKED (or allowlist only)            │ │  │  │
│  │  │  │ Filesystem: Read-only root + /tmp writable      │ │  │  │
│  │  │  │ Syscalls: Restricted (seccomp)                  │ │  │  │
│  │  │  │ No: fork bombs, raw sockets, mount, ptrace      │ │  │  │
│  │  │  └─────────────────────────────────────────────────┘ │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                            ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Post-Execution Pipeline                                    │  │
│  │  1. Output size validation                                  │  │
│  │  2. Secret scanning (no credentials in output)              │  │
│  │  3. Result sanitization                                     │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import asyncio

@dataclass
class SandboxConfig:
    max_cpu_seconds: int = 30
    max_memory_mb: int = 512
    max_disk_mb: int = 1024
    max_output_bytes: int = 1_000_000
    max_processes: int = 10
    network_enabled: bool = False
    network_allowlist: List[str] = field(default_factory=list)
    allowed_languages: List[str] = field(default_factory=lambda: ["python", "javascript", "bash"])
    blocked_imports: List[str] = field(default_factory=lambda: [
        "os.system", "subprocess", "shutil.rmtree", "ctypes"
    ])
    approved_packages: List[str] = field(default_factory=lambda: [
        "numpy", "pandas", "requests", "json", "math", "datetime",
        "collections", "itertools", "functools", "typing"
    ])

@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    memory_used_mb: float
    files_created: Dict[str, bytes] = field(default_factory=dict)
    truncated: bool = False

class CodeSandbox:
    """Secure code execution sandbox using container isolation."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.static_analyzer = StaticAnalyzer(config)
    
    async def execute(self, code: str, language: str, 
                      input_files: Dict[str, bytes] = None) -> ExecutionResult:
        # 1. Pre-execution validation
        if language not in self.config.allowed_languages:
            return ExecutionResult(stdout="", stderr=f"Language {language} not allowed",
                                  exit_code=1, execution_time_ms=0, memory_used_mb=0)
        
        # 2. Static analysis
        issues = self.static_analyzer.analyze(code, language)
        if issues.has_critical():
            return ExecutionResult(
                stdout="", stderr=f"Blocked: {issues.critical_reasons()}",
                exit_code=1, execution_time_ms=0, memory_used_mb=0
            )
        
        # 3. Prepare sandbox container
        container_id = await self.create_sandbox(language, input_files)
        
        try:
            # 4. Execute in sandbox
            result = await self.run_in_sandbox(container_id, code, language)
            
            # 5. Post-execution validation
            result = self.validate_output(result)
            
            return result
        finally:
            # 6. Always cleanup
            await self.destroy_sandbox(container_id)
    
    async def create_sandbox(self, language: str, input_files: Dict = None) -> str:
        """Create isolated execution environment."""
        # Using gVisor (runsc) for syscall filtering
        cmd = [
            "docker", "run", "-d",
            "--runtime=runsc",  # gVisor for syscall isolation
            "--memory", f"{self.config.max_memory_mb}m",
            "--cpus", "2",
            "--pids-limit", str(self.config.max_processes),
            "--read-only",
            "--tmpfs", "/tmp:size=100m",
            "--network", "none" if not self.config.network_enabled else "bridge",
            "--security-opt", "no-new-privileges",
            f"sandbox-{language}:latest",
            "sleep", "infinity"
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()
    
    async def run_in_sandbox(self, container_id: str, code: str, 
                             language: str) -> ExecutionResult:
        """Execute code inside the sandbox with timeout."""
        # Write code to container
        await self.docker_exec(container_id, f"cat > /tmp/code.{self.get_ext(language)}", 
                              input=code.encode())
        
        # Run with timeout
        run_cmd = self.get_run_command(language)
        
        try:
            start = asyncio.get_event_loop().time()
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id, 
                "timeout", str(self.config.max_cpu_seconds), *run_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.max_cpu_seconds + 5
            )
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            
            return ExecutionResult(
                stdout=stdout.decode()[:self.config.max_output_bytes],
                stderr=stderr.decode()[:self.config.max_output_bytes],
                exit_code=proc.returncode,
                execution_time_ms=elapsed,
                memory_used_mb=await self.get_memory_usage(container_id),
                truncated=len(stdout) > self.config.max_output_bytes
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                stdout="", stderr="Execution timed out",
                exit_code=137, execution_time_ms=self.config.max_cpu_seconds * 1000,
                memory_used_mb=self.config.max_memory_mb
            )

class StaticAnalyzer:
    """Pre-execution static analysis to catch dangerous patterns."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.dangerous_patterns = [
            r"os\.system\(", r"subprocess\.", r"eval\(",
            r"exec\(", r"__import__\(", r"open\(.*/etc",
            r"shutil\.rmtree", r"os\.remove\(",
            r"while\s+True", r"fork\(\)",
        ]
    
    def analyze(self, code: str, language: str) -> "AnalysisResult":
        issues = []
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, code):
                issues.append(f"Dangerous pattern: {pattern}")
        
        # Check imports against allowlist
        if language == "python":
            imports = self.extract_imports(code)
            for imp in imports:
                if imp not in self.config.approved_packages:
                    issues.append(f"Unapproved import: {imp}")
        
        # Check for resource exhaustion patterns
        if self.detect_resource_exhaustion(code):
            issues.append("Potential resource exhaustion detected")
        
        return AnalysisResult(issues=issues)
```

**Security Layers:**

| Layer | Protection | Implementation |
|-------|-----------|----------------|
| Static analysis | Dangerous code patterns | Regex + AST analysis |
| Container isolation | Process/filesystem isolation | Docker + gVisor |
| Seccomp | Syscall filtering | Allowlisted syscalls only |
| Network | Data exfiltration | Disabled or strict allowlist |
| Resource limits | DoS prevention | cgroups (CPU, memory, PIDs) |
| Output validation | Secret leakage | Scan output for patterns |
| Time limits | Infinite loops | Process timeout |

**Production Considerations:**
- **Warm pools**: Keep pre-warmed containers ready; cold start takes 2-3s, warm start <100ms
- **Language-specific images**: Minimal images per language with only approved packages pre-installed
- **Audit logging**: Log all executed code, who ran it, and results for security review
- **Escape detection**: Monitor for sandbox escape attempts; alert security team immediately
- **Cost**: Each execution costs ~$0.001 (compute); batch executions for efficiency

---

## Q184: Design a persistent memory system for AI agents that maintains context across sessions (days/weeks). Include memory consolidation, forgetting strategies, and privacy controls.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Persistent Agent Memory System                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Memory Types                                                ││
│  │                                                               ││
│  │  ┌────────────┐  ┌────────────────┐  ┌──────────────────┐  ││
│  │  │ Working    │  │ Episodic       │  │ Semantic          │  ││
│  │  │ Memory     │  │ Memory         │  │ Memory            │  ││
│  │  │            │  │                │  │                    │  ││
│  │  │ Current    │  │ Past sessions, │  │ Facts, skills,    │  ││
│  │  │ session    │  │ interactions,  │  │ preferences       │  ││
│  │  │ context    │  │ outcomes       │  │ (consolidated)    │  ││
│  │  │            │  │                │  │                    │  ││
│  │  │ TTL: hours │  │ TTL: weeks     │  │ TTL: indefinite   │  ││
│  │  └────────────┘  └────────────────┘  └──────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Memory Operations                                           ││
│  │  Store → Consolidate → Retrieve → Forget                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Privacy Layer                                               ││
│  │  Consent → Classification → Retention → Deletion            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import numpy as np

@dataclass
class Memory:
    id: str
    content: str
    memory_type: str  # "episodic", "semantic", "procedural"
    embedding: List[float]
    importance: float  # 0-1
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    source_session: str = ""
    privacy_level: str = "standard"  # "public", "standard", "sensitive", "delete_on_expire"
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

class PersistentMemorySystem:
    def __init__(self, vector_store, llm, privacy_engine):
        self.store = vector_store
        self.llm = llm
        self.privacy = privacy_engine
    
    async def remember(self, content: str, context: dict) -> Memory:
        """Store a new memory with importance scoring."""
        
        # Score importance
        importance = await self.score_importance(content, context)
        
        # Classify privacy level
        privacy_level = await self.privacy.classify(content)
        
        # Compute embedding
        embedding = await self.embed(content)
        
        memory = Memory(
            id=self.generate_id(),
            content=content,
            memory_type=self.classify_type(content, context),
            embedding=embedding,
            importance=importance,
            privacy_level=privacy_level,
            source_session=context.get("session_id", ""),
            expires_at=self.compute_expiry(privacy_level, importance)
        )
        
        await self.store.upsert(memory)
        return memory
    
    async def recall(self, query: str, context: dict, top_k: int = 10) -> List[Memory]:
        """Retrieve relevant memories for current context."""
        query_embedding = await self.embed(query)
        
        # Retrieve candidates
        candidates = await self.store.query(
            vector=query_embedding,
            top_k=top_k * 3,  # Over-retrieve for re-ranking
            filter={
                "privacy_level": {"$ne": "expired"},
                "user_id": context["user_id"]
            }
        )
        
        # Re-rank by recency + importance + relevance
        scored = []
        for mem in candidates:
            relevance = self.cosine_sim(query_embedding, mem.embedding)
            recency = self.recency_score(mem.last_accessed)
            
            final_score = (
                0.5 * relevance + 
                0.3 * mem.importance + 
                0.2 * recency
            )
            scored.append((mem, final_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Update access patterns
        selected = [mem for mem, _ in scored[:top_k]]
        for mem in selected:
            mem.access_count += 1
            mem.last_accessed = datetime.utcnow()
            await self.store.update(mem)
        
        return selected
    
    def recency_score(self, last_accessed: datetime) -> float:
        """Exponential decay based on time since last access."""
        hours_ago = (datetime.utcnow() - last_accessed).total_seconds() / 3600
        half_life = 168  # 1 week
        return 2 ** (-hours_ago / half_life)
    
    async def consolidate(self, user_id: str):
        """Periodic consolidation: compress episodic → semantic memories."""
        
        # Find episodic memories ready for consolidation
        episodes = await self.store.query_by_type(
            user_id=user_id,
            memory_type="episodic",
            older_than=timedelta(days=3),
            min_access_count=2
        )
        
        if not episodes:
            return
        
        # Group related episodes
        clusters = self.cluster_memories(episodes)
        
        for cluster in clusters:
            # Generate semantic summary from episodes
            episode_texts = [m.content for m in cluster]
            summary = await self.llm.generate(
                f"Summarize these related experiences into a general insight:\n"
                + "\n".join(episode_texts)
            )
            
            # Create consolidated semantic memory
            semantic_mem = await self.remember(
                content=summary,
                context={"type": "consolidation", "source_count": len(cluster)}
            )
            semantic_mem.memory_type = "semantic"
            semantic_mem.importance = max(m.importance for m in cluster)
            await self.store.update(semantic_mem)
            
            # Mark episodes as consolidated (reduce importance)
            for ep in cluster:
                ep.importance *= 0.5
                ep.metadata["consolidated_into"] = semantic_mem.id
                await self.store.update(ep)
    
    async def forget(self, user_id: str):
        """Forgetting strategy: remove low-value memories."""
        
        # 1. Delete expired memories
        await self.store.delete_expired(user_id)
        
        # 2. Forget low-importance, rarely-accessed memories
        candidates = await self.store.query_forgettable(
            user_id=user_id,
            max_importance=0.2,
            max_access_count=1,
            older_than=timedelta(days=30)
        )
        
        for mem in candidates:
            await self.store.delete(mem.id)
        
        # 3. Enforce memory budget (max memories per user)
        count = await self.store.count(user_id)
        if count > 10000:
            # Remove lowest scored memories
            to_remove = count - 8000  # Remove 20% buffer
            lowest = await self.store.get_lowest_scored(user_id, to_remove)
            for mem in lowest:
                await self.store.delete(mem.id)

class PrivacyControls:
    """User-controlled privacy for agent memory."""
    
    async def delete_memories_by_topic(self, user_id: str, topic: str):
        """User can delete memories related to a topic."""
        related = await self.store.semantic_search(user_id, topic, top_k=100)
        for mem in related:
            await self.store.delete(mem.id)
    
    async def export_memories(self, user_id: str) -> dict:
        """GDPR: User can export all their stored memories."""
        all_memories = await self.store.get_all(user_id)
        return {"memories": [m.to_dict() for m in all_memories]}
    
    async def delete_all(self, user_id: str):
        """GDPR: Right to erasure."""
        await self.store.delete_all(user_id)
```

**Memory Lifecycle:**

| Phase | Trigger | Action | Storage |
|-------|---------|--------|---------|
| Encode | During session | Store with importance score | Vector DB |
| Consolidate | Nightly job | Cluster episodes → semantic | Merge + summarize |
| Retrieve | Query time | Relevance + recency + importance | Vector search |
| Forget | Nightly job | Remove low-value memories | Delete |
| Expire | Time-based | Auto-delete after TTL | Delete |

**Production Considerations:**
- **Importance scoring**: Use LLM to judge "Will this be useful in future sessions?" (score 0-1)
- **Memory budget**: Cap at ~10K memories per user; beyond that, consolidation must compress
- **Retrieval augmentation**: When agent starts new session, auto-load top-5 relevant memories
- **Privacy-first**: Users see and control their memory; delete button is prominent
- **No hallucinated memories**: Validate stored memories against source; don't store agent's incorrect outputs

---

## Q185: Design a human-in-the-loop system for AI agents where certain actions require human approval. Include approval queues, timeout handling, context preservation, and escalation paths.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Human-in-the-Loop System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Agent Execution                                            │  │
│  │  ... → Action Needs Approval → ┐                           │  │
│  │                                  │ (Agent pauses)           │  │
│  │                                  ▼                          │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Approval Request                                     │  │  │
│  │  │  - Action description                                 │  │  │
│  │  │  - Context & reasoning                                │  │  │
│  │  │  - Risk assessment                                    │  │  │
│  │  │  - Suggested alternatives                             │  │  │
│  │  └──────────────────────────────┬───────────────────────┘  │  │
│  └─────────────────────────────────┼──────────────────────────┘  │
│                                     │                             │
│  ┌──────────────────────────────────▼─────────────────────────┐  │
│  │  Approval Queue                                             │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │  │
│  │  │Request 1│  │Request 2│  │Request 3│  ...               │  │
│  │  │TTL: 5min│  │TTL: 1hr │  │TTL: 24hr│                   │  │
│  │  └─────────┘  └─────────┘  └─────────┘                   │  │
│  └──────────────────────────────────┬─────────────────────────┘  │
│                                      │                            │
│  ┌───────────────────────────────────▼────────────────────────┐  │
│  │  Human Reviewer Interface                                   │  │
│  │  [Approve] [Reject] [Modify] [Escalate] [Delegate]         │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict
from datetime import datetime, timedelta
from enum import Enum
import asyncio

class ApprovalDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    ESCALATED = "escalated"
    TIMED_OUT = "timed_out"

@dataclass
class ApprovalRequest:
    request_id: str
    agent_id: str
    session_id: str
    action: dict                    # What the agent wants to do
    context: dict                   # Why (agent's reasoning)
    risk_level: str                 # "low", "medium", "high", "critical"
    timeout: timedelta = timedelta(minutes=15)
    created_at: datetime = field(default_factory=datetime.utcnow)
    escalation_chain: List[str] = field(default_factory=list)
    current_escalation_level: int = 0
    
    # For context preservation
    agent_state_snapshot: dict = field(default_factory=dict)
    working_memory: List[dict] = field(default_factory=list)

@dataclass
class ApprovalResponse:
    request_id: str
    decision: ApprovalDecision
    reviewer_id: str
    modified_action: Optional[dict] = None
    feedback: Optional[str] = None
    decided_at: datetime = field(default_factory=datetime.utcnow)

class HumanInTheLoopSystem:
    def __init__(self, queue_store, notification_service, agent_state_store):
        self.queue = queue_store
        self.notifications = notification_service
        self.state_store = agent_state_store
    
    async def request_approval(self, agent_id: str, action: dict, 
                               context: dict, agent_state: dict) -> ApprovalResponse:
        """Request human approval, preserving agent state."""
        
        # 1. Assess risk level
        risk = self.assess_risk(action)
        
        # 2. Determine timeout and escalation chain
        timeout = self.get_timeout(risk)
        escalation_chain = self.get_escalation_chain(risk, action)
        
        # 3. Create approval request
        request = ApprovalRequest(
            request_id=self.generate_id(),
            agent_id=agent_id,
            session_id=context.get("session_id"),
            action=action,
            context=context,
            risk_level=risk,
            timeout=timeout,
            escalation_chain=escalation_chain,
            agent_state_snapshot=agent_state,
            working_memory=context.get("working_memory", [])
        )
        
        # 4. Save agent state for resumption
        await self.state_store.save(request.session_id, agent_state)
        
        # 5. Enqueue and notify
        await self.queue.enqueue(request)
        await self.notify_reviewers(request)
        
        # 6. Wait for response with timeout handling
        response = await self.wait_for_decision(request)
        
        return response
    
    async def wait_for_decision(self, request: ApprovalRequest) -> ApprovalResponse:
        """Wait with escalation on timeout."""
        deadline = request.created_at + request.timeout
        
        while datetime.utcnow() < deadline:
            # Check for response
            response = await self.queue.get_response(request.request_id)
            if response:
                return response
            
            # Check if escalation needed (50% of timeout passed)
            elapsed_ratio = (datetime.utcnow() - request.created_at) / request.timeout
            if elapsed_ratio > 0.5 and request.current_escalation_level == 0:
                await self.escalate(request)
            
            await asyncio.sleep(5)  # Poll every 5 seconds
        
        # Timeout reached
        return await self.handle_timeout(request)
    
    async def handle_timeout(self, request: ApprovalRequest) -> ApprovalResponse:
        """Handle approval timeout based on risk level."""
        if request.risk_level == "low":
            # Auto-approve low-risk on timeout
            return ApprovalResponse(
                request_id=request.request_id,
                decision=ApprovalDecision.APPROVED,
                reviewer_id="system_auto_approve",
                feedback="Auto-approved on timeout (low risk)"
            )
        elif request.risk_level in ("medium", "high"):
            # Reject and let agent try alternative
            return ApprovalResponse(
                request_id=request.request_id,
                decision=ApprovalDecision.TIMED_OUT,
                reviewer_id="system",
                feedback="Timed out. Agent should try a safer alternative."
            )
        else:
            # Critical: keep waiting, escalate further
            await self.escalate(request)
            return await self.wait_for_decision(request)  # Recursive with new timeout
    
    async def escalate(self, request: ApprovalRequest):
        """Escalate to next level in chain."""
        request.current_escalation_level += 1
        if request.current_escalation_level < len(request.escalation_chain):
            next_reviewer = request.escalation_chain[request.current_escalation_level]
            await self.notifications.urgent_notify(
                next_reviewer, request,
                message=f"ESCALATED: Agent action awaiting approval for "
                       f"{(datetime.utcnow() - request.created_at).seconds}s"
            )
    
    def assess_risk(self, action: dict) -> str:
        """Assess risk level of proposed action."""
        high_risk_actions = ["deploy", "delete_data", "send_external", "modify_production"]
        medium_risk_actions = ["write_file", "execute_code", "api_call"]
        
        action_type = action.get("type", "")
        
        if action_type in high_risk_actions:
            return "high"
        elif action_type in medium_risk_actions:
            return "medium"
        elif action.get("cost_estimate", 0) > 10.0:
            return "high"
        else:
            return "low"

class AgentResumption:
    """Resume agent from saved state after approval."""
    
    async def resume_agent(self, session_id: str, approval: ApprovalResponse):
        """Resume agent execution with approval decision."""
        
        # Load saved agent state
        state = await self.state_store.load(session_id)
        
        if approval.decision == ApprovalDecision.APPROVED:
            # Continue with original action
            state["pending_action_approved"] = True
        elif approval.decision == ApprovalDecision.MODIFIED:
            # Continue with modified action
            state["pending_action"] = approval.modified_action
            state["pending_action_approved"] = True
        elif approval.decision == ApprovalDecision.REJECTED:
            # Tell agent to try different approach
            state["pending_action_approved"] = False
            state["rejection_feedback"] = approval.feedback
        
        # Resume agent loop
        await self.agent_runtime.resume(session_id, state)
```

**Timeout Policies:**

| Risk Level | Default Timeout | On Timeout | Escalation |
|-----------|----------------|------------|-----------|
| Low | 5 minutes | Auto-approve | None |
| Medium | 15 minutes | Reject (agent retries) | After 7 min |
| High | 1 hour | Reject + alert | After 15 min |
| Critical | 24 hours | Block (wait forever) | After 30 min, 2hr, 8hr |

**Production Considerations:**
- **Context richness**: Show reviewer the full chain of reasoning, not just the action
- **One-click actions**: Reviewer should be able to approve/reject in < 5 seconds (mobile-friendly)
- **Batch approvals**: If agent has 5 similar pending actions, let reviewer approve all at once
- **Learning from decisions**: Track approval patterns; auto-approve actions that are always approved
- **SLA tracking**: Monitor approval queue depth and response times; alert if queue backs up
# ML Platform Architecture (Questions 186-190)

## Q186: Design an end-to-end ML platform that supports the full lifecycle: experimentation, training, evaluation, deployment, serving, and monitoring. Include self-service capabilities for 200 ML engineers.

### Answer

**Architecture:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    End-to-End ML Platform                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Self-Service Layer (UI + CLI + SDK)                                │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌────────────────────┐  │  │
│  │  │Notebooks │ │Experiment│ │ Model      │ │ Deployment         │  │  │
│  │  │(JupyterHub│ │Tracker   │ │ Registry   │ │ Manager            │  │  │
│  │  │)         │ │          │ │            │ │                    │  │  │
│  │  └──────────┘ └──────────┘ └────────────┘ └────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Orchestration Layer                                                │  │
│  │  ┌──────────────┐  ┌────────────────┐  ┌───────────────────────┐  │  │
│  │  │Pipeline      │  │ Scheduler      │  │ Resource Manager      │  │  │
│  │  │Engine        │  │ (Airflow/Argo) │  │ (GPU/CPU Allocation)  │  │  │
│  │  │(Kubeflow/    │  │                │  │                       │  │  │
│  │  │ Metaflow)    │  │                │  │                       │  │  │
│  │  └──────────────┘  └────────────────┘  └───────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Compute Layer                                                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │  │
│  │  │ Training     │  │ Serving      │  │ Feature Computation    │  │  │
│  │  │ (Distributed)│  │ (Inference)  │  │ (Batch + Streaming)    │  │  │
│  │  └──────────────┘  └──────────────┘  └────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Data & Storage Layer                                               │  │
│  │  ┌──────────┐ ┌─────────────┐ ┌────────────┐ ┌────────────────┐  │  │
│  │  │Feature   │ │ Data Lake   │ │ Model      │ │ Vector Store   │  │  │
│  │  │Store     │ │ (Delta)     │ │ Artifacts  │ │                │  │  │
│  │  └──────────┘ └─────────────┘ └────────────┘ └────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

@dataclass
class MLProject:
    name: str
    team: str
    owner: str
    compute_quota: dict = field(default_factory=lambda: {
        "gpu_hours_monthly": 1000,
        "cpu_hours_monthly": 10000,
        "storage_gb": 500
    })

class MLPlatform:
    """Self-service ML platform for 200+ engineers."""
    
    def __init__(self, compute_manager, pipeline_engine, model_registry,
                 feature_store, experiment_tracker, serving_platform):
        self.compute = compute_manager
        self.pipelines = pipeline_engine
        self.registry = model_registry
        self.features = feature_store
        self.experiments = experiment_tracker
        self.serving = serving_platform
    
    # === Experimentation ===
    async def create_experiment(self, config: dict) -> str:
        """Self-service experiment creation."""
        # Provision notebook/compute
        env = await self.compute.provision(
            instance_type=config.get("instance", "gpu.a100.1"),
            image=config.get("image", "ml-base:latest"),
            duration_hours=config.get("duration", 8)
        )
        
        # Create experiment tracking
        experiment_id = await self.experiments.create(
            name=config["name"],
            project=config["project"],
            parameters=config.get("hyperparams", {}),
            tags=config.get("tags", [])
        )
        
        return experiment_id
    
    # === Training ===
    async def submit_training_job(self, config: dict) -> str:
        """Submit distributed training job."""
        job = await self.pipelines.submit({
            "type": "training",
            "script": config["training_script"],
            "data_config": config["data"],
            "compute": {
                "gpu_count": config.get("gpus", 1),
                "gpu_type": config.get("gpu_type", "A100"),
                "distributed": config.get("distributed", False),
                "framework": config.get("framework", "pytorch")
            },
            "hyperparameters": config.get("hyperparams", {}),
            "experiment_id": config.get("experiment_id"),
            "checkpointing": {"interval_minutes": 30},
            "max_duration_hours": config.get("max_hours", 24)
        })
        return job.id
    
    # === Evaluation ===
    async def evaluate_model(self, model_id: str, eval_config: dict) -> dict:
        """Run standardized evaluation suite."""
        model = await self.registry.get(model_id)
        
        results = {}
        for dataset_name in eval_config["datasets"]:
            dataset = await self.features.get_dataset(dataset_name)
            metrics = await self.pipelines.run_eval(
                model=model,
                dataset=dataset,
                metrics=eval_config.get("metrics", ["accuracy", "f1", "latency"])
            )
            results[dataset_name] = metrics
        
        # Store results in registry
        await self.registry.add_evaluation(model_id, results)
        
        # Auto-compare with production model
        production_model = await self.registry.get_production(model.task_type)
        if production_model:
            comparison = self.compare(results, production_model.eval_results)
            results["vs_production"] = comparison
        
        return results
    
    # === Deployment ===
    async def deploy_model(self, model_id: str, deploy_config: dict) -> str:
        """Deploy model to serving infrastructure."""
        model = await self.registry.get(model_id)
        
        # Validate model is ready for deployment
        self.validate_deployment_readiness(model)
        
        # Deploy with canary
        endpoint = await self.serving.deploy(
            model_artifact=model.artifact_uri,
            serving_config={
                "replicas": deploy_config.get("replicas", 2),
                "gpu": deploy_config.get("gpu", False),
                "autoscaling": {
                    "min_replicas": deploy_config.get("min_replicas", 1),
                    "max_replicas": deploy_config.get("max_replicas", 10),
                    "target_rps": deploy_config.get("target_rps", 100)
                },
                "canary_percent": deploy_config.get("canary", 0.05)
            }
        )
        
        # Update registry
        await self.registry.mark_deployed(model_id, endpoint.url)
        
        return endpoint.url
    
    # === Monitoring ===
    async def setup_monitoring(self, model_id: str, endpoint: str):
        """Auto-configure monitoring for deployed model."""
        await self.monitoring.configure({
            "model_id": model_id,
            "endpoint": endpoint,
            "alerts": {
                "latency_p99_ms": 200,
                "error_rate_percent": 1.0,
                "prediction_drift_threshold": 0.1,
                "data_drift_threshold": 0.15
            },
            "dashboards": ["latency", "throughput", "quality", "cost"],
            "logging": {
                "sample_rate": 0.1,  # Log 10% of predictions
                "log_inputs": True,
                "log_outputs": True
            }
        })
```

**Platform Components for 200 Engineers:**

| Component | Purpose | Technology Choice |
|-----------|---------|------------------|
| Notebooks | Interactive dev | JupyterHub on K8s |
| Pipelines | Workflow orchestration | Kubeflow Pipelines / Argo |
| Experiment tracking | Compare runs | MLflow / W&B |
| Feature store | Shared features | Feast / Tecton |
| Model registry | Model lifecycle | MLflow Model Registry |
| Serving | Inference endpoints | KServe / Triton |
| Monitoring | Drift, quality | Evidently + Prometheus |
| Data versioning | Reproducibility | DVC / LakeFS |

**Self-Service Guardrails:**

| Guardrail | Purpose | Implementation |
|-----------|---------|----------------|
| Compute quotas | Prevent cost overrun | Per-team GPU-hour budgets |
| Auto-shutdown | Reduce waste | Idle notebooks killed after 2hr |
| Deployment gates | Quality control | Must pass eval threshold to deploy |
| Resource tagging | Cost attribution | Mandatory team/project tags |
| Template library | Reduce boilerplate | Pre-built pipeline templates |

**Production Considerations:**
- **Onboarding**: New ML engineers productive in < 1 day with templates and docs
- **Cost visibility**: Real-time cost dashboards per team; weekly reports to managers
- **Multi-framework**: Support PyTorch, TensorFlow, JAX without forcing one choice
- **Reproducibility**: Every training run captures code version, data version, env hash
- **Governance**: Model approval workflow before production deployment (risk-based)

---

## Q187: Design a model registry and artifact management system. How do you track models, their lineage, associated datasets, evaluation results, and deployment history? Include reproducibility guarantees.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Model Registry & Artifact Management                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Model Registry (Metadata Store)                            │  │
│  │                                                              │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │  Model Entry                                         │   │  │
│  │  │  ├── Version 1.0.0 (staging)                         │   │  │
│  │  │  │   ├── Artifact: s3://models/v1.0.0/model.pt      │   │  │
│  │  │  │   ├── Metrics: {accuracy: 0.94, f1: 0.91}        │   │  │
│  │  │  │   ├── Training: {run_id, dataset_v, code_hash}    │   │  │
│  │  │  │   └── Dependencies: {torch==2.1, transformers==4.35}│  │  │
│  │  │  ├── Version 1.1.0 (production)                      │   │  │
│  │  │  └── Version 0.9.0 (archived)                        │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Artifact Store (Binary Storage)                            │  │
│  │  S3/GCS with content-addressable hashing                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Lineage Graph                                              │  │
│  │  Dataset → Training Run → Model → Evaluation → Deployment   │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

class ModelStage(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"

@dataclass
class ModelVersion:
    model_name: str
    version: str
    stage: ModelStage
    artifact_uri: str
    artifact_hash: str  # SHA256 of model binary
    
    # Reproducibility
    training_run_id: str
    code_commit: str
    dataset_version: str
    environment_hash: str  # Hash of pip freeze / conda env
    hyperparameters: dict = field(default_factory=dict)
    
    # Evaluation
    metrics: Dict[str, float] = field(default_factory=dict)
    eval_datasets: List[str] = field(default_factory=list)
    
    # Deployment
    deployments: List[dict] = field(default_factory=list)
    
    # Metadata
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Model card
    model_card: Optional[dict] = None

class ModelRegistry:
    def __init__(self, metadata_db, artifact_store, lineage_graph):
        self.db = metadata_db
        self.artifacts = artifact_store
        self.lineage = lineage_graph
    
    async def register_model(self, model_name: str, artifact_path: str,
                             training_context: dict) -> ModelVersion:
        """Register a new model version with full lineage."""
        
        # 1. Upload artifact to content-addressable store
        artifact_hash = self.compute_hash(artifact_path)
        artifact_uri = await self.artifacts.upload(
            source=artifact_path,
            destination=f"models/{model_name}/{artifact_hash}"
        )
        
        # 2. Capture environment for reproducibility
        env_hash = self.capture_environment()
        
        # 3. Determine version
        latest = await self.db.get_latest_version(model_name)
        new_version = self.bump_version(latest)
        
        # 4. Create model version
        model_version = ModelVersion(
            model_name=model_name,
            version=new_version,
            stage=ModelStage.DEVELOPMENT,
            artifact_uri=artifact_uri,
            artifact_hash=artifact_hash,
            training_run_id=training_context["run_id"],
            code_commit=training_context["git_commit"],
            dataset_version=training_context["dataset_version"],
            environment_hash=env_hash,
            hyperparameters=training_context.get("hyperparams", {}),
            created_by=training_context["user"]
        )
        
        await self.db.save(model_version)
        
        # 5. Record lineage
        await self.lineage.add_edge(
            source=f"dataset:{training_context['dataset_version']}",
            target=f"model:{model_name}:{new_version}",
            relation="trained_on"
        )
        await self.lineage.add_edge(
            source=f"run:{training_context['run_id']}",
            target=f"model:{model_name}:{new_version}",
            relation="produced_by"
        )
        
        return model_version
    
    async def promote(self, model_name: str, version: str, 
                      target_stage: ModelStage) -> bool:
        """Promote model through stages with validation."""
        model = await self.db.get(model_name, version)
        
        # Validate promotion rules
        if target_stage == ModelStage.STAGING:
            # Must have evaluation results
            if not model.metrics:
                raise ValueError("Cannot promote to staging without evaluation")
        
        elif target_stage == ModelStage.PRODUCTION:
            # Must pass staging checks
            if model.stage != ModelStage.STAGING:
                raise ValueError("Must be in staging before production")
            if not self.passes_production_gate(model):
                raise ValueError("Failed production gate checks")
            
            # Demote current production model
            current_prod = await self.db.get_by_stage(model_name, ModelStage.PRODUCTION)
            if current_prod:
                current_prod.stage = ModelStage.ARCHIVED
                await self.db.save(current_prod)
        
        model.stage = target_stage
        await self.db.save(model)
        return True
    
    async def reproduce(self, model_name: str, version: str) -> dict:
        """Generate reproducibility recipe for a model version."""
        model = await self.db.get(model_name, version)
        
        return {
            "code": {
                "repository": self.get_repo(model.code_commit),
                "commit": model.code_commit,
                "command": f"git checkout {model.code_commit}"
            },
            "data": {
                "dataset": model.dataset_version,
                "command": f"dvc checkout {model.dataset_version}"
            },
            "environment": {
                "hash": model.environment_hash,
                "command": f"pip install -r requirements_{model.environment_hash}.txt"
            },
            "training": {
                "hyperparameters": model.hyperparameters,
                "command": f"python train.py --config {json.dumps(model.hyperparameters)}"
            },
            "verification": {
                "expected_hash": model.artifact_hash,
                "expected_metrics": model.metrics
            }
        }
    
    def passes_production_gate(self, model: ModelVersion) -> bool:
        """Automated production readiness checks."""
        checks = [
            model.metrics.get("accuracy", 0) > 0.9,
            model.metrics.get("latency_p99_ms", float('inf')) < 200,
            model.model_card is not None,
            len(model.eval_datasets) >= 2,
            model.artifact_hash != "",  # Integrity verified
        ]
        return all(checks)
```

**Lifecycle Stages:**

| Stage | Purpose | Entry Criteria | Exit Criteria |
|-------|---------|---------------|---------------|
| Development | Experimentation | Any | Evaluation complete |
| Staging | Pre-production validation | Passes eval threshold | Passes load test + A/B test |
| Production | Serving traffic | Passes production gate | Superseded by newer version |
| Archived | Historical reference | Removed from production | Never (keep for audit) |

**Production Considerations:**
- **Immutability**: Once registered, model artifacts are immutable; new version for any change
- **Garbage collection**: Archive models > 6 months old with 0 traffic; delete artifacts after 1 year
- **Search & discovery**: Full-text search over model cards, tags, and metrics for discoverability
- **Access control**: Team-based permissions; only model owner can promote to production
- **Compliance**: Retain full lineage for regulated industries (finance, healthcare)

---

## Q188: Design an experiment tracking and comparison system for ML research teams. How do you compare 1000s of experiments across hyperparameters, architectures, and data configurations?

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Experiment Tracking & Comparison                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Logging SDK (integrated into training code)                │  │
│  │  experiment.log_param("lr", 0.001)                          │  │
│  │  experiment.log_metric("loss", 0.5, step=100)               │  │
│  │  experiment.log_artifact("model.pt")                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Storage Backend                                            │  │
│  │  ┌───────────────┐ ┌──────────────┐ ┌──────────────────┐  │  │
│  │  │ Time-Series   │ │ Metadata     │ │ Artifact Store   │  │  │
│  │  │ (Metrics)     │ │ (Params,Tags)│ │ (Models, Plots)  │  │  │
│  │  └───────────────┘ └──────────────┘ └──────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Comparison Engine                                          │  │
│  │  - Parallel coordinates                                     │  │
│  │  - Hyperparameter importance (ANOVA/fANOVA)                 │  │
│  │  - Pareto front visualization                               │  │
│  │  - Statistical significance testing                         │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np
from scipy import stats

@dataclass
class Experiment:
    id: str
    name: str
    project: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, List[float]] = field(default_factory=dict)  # metric -> [values over time]
    final_metrics: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    status: str = "running"  # running, completed, failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: float = 0

class ExperimentComparisonEngine:
    """Compare and analyze thousands of experiments."""
    
    def __init__(self, experiment_store):
        self.store = experiment_store
    
    async def compare(self, experiment_ids: List[str], 
                       metric: str = "accuracy") -> dict:
        """Compare multiple experiments."""
        experiments = [await self.store.get(eid) for eid in experiment_ids]
        
        return {
            "rankings": self.rank_by_metric(experiments, metric),
            "parameter_importance": self.compute_param_importance(experiments, metric),
            "pareto_front": self.compute_pareto(experiments, ["accuracy", "latency"]),
            "statistical_tests": self.significance_tests(experiments, metric)
        }
    
    def compute_param_importance(self, experiments: List[Experiment], 
                                  target_metric: str) -> Dict[str, float]:
        """fANOVA-style parameter importance analysis."""
        # Get all parameter names
        all_params = set()
        for exp in experiments:
            all_params.update(exp.parameters.keys())
        
        importance = {}
        for param in all_params:
            # Get experiments that have this parameter
            values = [(exp.parameters.get(param), exp.final_metrics.get(target_metric))
                     for exp in experiments 
                     if param in exp.parameters and target_metric in exp.final_metrics]
            
            if len(values) < 5:
                continue
            
            param_values, metric_values = zip(*values)
            
            # Compute correlation/importance
            if all(isinstance(v, (int, float)) for v in param_values):
                # Numerical: compute Spearman correlation
                corr, p_value = stats.spearmanr(param_values, metric_values)
                importance[param] = abs(corr) if p_value < 0.05 else 0
            else:
                # Categorical: compute ANOVA
                groups = {}
                for pv, mv in values:
                    groups.setdefault(str(pv), []).append(mv)
                if len(groups) > 1:
                    f_stat, p_value = stats.f_oneway(*groups.values())
                    importance[param] = f_stat if p_value < 0.05 else 0
        
        # Normalize
        total = sum(importance.values()) or 1
        return {k: v/total for k, v in sorted(importance.items(), 
                                               key=lambda x: x[1], reverse=True)}
    
    def compute_pareto(self, experiments: List[Experiment], 
                        objectives: List[str]) -> List[str]:
        """Find Pareto-optimal experiments (multi-objective)."""
        # For now, 2 objectives
        obj1, obj2 = objectives
        
        points = []
        for exp in experiments:
            if obj1 in exp.final_metrics and obj2 in exp.final_metrics:
                points.append((
                    exp.id,
                    exp.final_metrics[obj1],
                    -exp.final_metrics[obj2]  # Negate if lower is better
                ))
        
        # Find non-dominated solutions
        pareto = []
        for i, (id_i, x_i, y_i) in enumerate(points):
            dominated = False
            for j, (_, x_j, y_j) in enumerate(points):
                if i != j and x_j >= x_i and y_j >= y_i and (x_j > x_i or y_j > y_i):
                    dominated = True
                    break
            if not dominated:
                pareto.append(id_i)
        
        return pareto
    
    def significance_tests(self, experiments: List[Experiment], 
                           metric: str) -> dict:
        """Statistical significance between top experiments."""
        # Compare top-2 experiments
        sorted_exps = sorted(experiments, 
                            key=lambda e: e.final_metrics.get(metric, 0), 
                            reverse=True)
        
        if len(sorted_exps) < 2:
            return {}
        
        best = sorted_exps[0]
        second = sorted_exps[1]
        
        # If we have multiple evaluation runs, do paired t-test
        best_scores = best.metrics.get(f"{metric}_eval_runs", [best.final_metrics[metric]])
        second_scores = second.metrics.get(f"{metric}_eval_runs", [second.final_metrics[metric]])
        
        if len(best_scores) > 1 and len(second_scores) > 1:
            t_stat, p_value = stats.ttest_ind(best_scores, second_scores)
            return {
                "best_vs_second": {
                    "t_statistic": t_stat,
                    "p_value": p_value,
                    "significant": p_value < 0.05,
                    "effect_size": (np.mean(best_scores) - np.mean(second_scores)) / np.std(second_scores)
                }
            }
        
        return {"note": "Insufficient data for significance test"}

class HyperparameterSearch:
    """Automated hyperparameter search with experiment tracking."""
    
    async def search(self, search_space: dict, objective: str,
                     n_trials: int = 100) -> List[str]:
        """Run hyperparameter search, return experiment IDs."""
        # Use Optuna/Ray Tune for efficient search
        import optuna
        
        def objective_fn(trial):
            params = {}
            for name, config in search_space.items():
                if config["type"] == "float":
                    params[name] = trial.suggest_float(name, config["low"], config["high"], log=config.get("log", False))
                elif config["type"] == "categorical":
                    params[name] = trial.suggest_categorical(name, config["choices"])
            
            # Run training with these params (tracked as experiment)
            result = self.run_training(params)
            return result[objective]
        
        study = optuna.create_study(direction="maximize")
        study.optimize(objective_fn, n_trials=n_trials)
        
        return [t.user_attrs["experiment_id"] for t in study.trials]
```

**Comparison Features for 1000s of Experiments:**

| Feature | Purpose | Implementation |
|---------|---------|----------------|
| Parallel coordinates | Visualize param→metric relationships | D3.js / Plotly |
| Parameter importance | Which params matter most? | fANOVA / SHAP |
| Pareto frontier | Multi-objective trade-offs | Dominance analysis |
| Learning curves | Training dynamics comparison | Time-series overlay |
| Diff view | What changed between runs? | Parameter diff |
| Auto-grouping | Cluster similar experiments | DBSCAN on param space |

**Production Considerations:**
- **Scale**: Use columnar storage (ClickHouse/DuckDB) for fast aggregation over 1000s of experiments
- **Retention**: Keep metadata forever; auto-archive artifacts after 90 days (restore on demand)
- **Real-time**: Streaming metrics during training (live dashboard, no waiting for job to finish)
- **Collaboration**: Share experiment comparisons via URL; comment and discuss on specific runs
- **Automation**: Auto-tag experiments that beat production baseline; notify team

---

## Q189: Design a GPU cluster management system that efficiently allocates GPUs across training, fine-tuning, and inference workloads. Include scheduling, preemption, and utilization optimization.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              GPU Cluster Management System                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Cluster Topology                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ Node 1: 8x A100-80GB (NVLink)                       │   │  │
│  │  │ Node 2: 8x A100-80GB (NVLink)                       │   │  │
│  │  │ Node 3-10: 4x A100-40GB each                        │   │  │
│  │  │ Node 11-20: 2x L4 each (inference)                  │   │  │
│  │  │ Total: 96 GPUs, mixed types                          │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Scheduler                                                  │  │
│  │  ┌──────────┐ ┌──────────────┐ ┌─────────────────────┐   │  │
│  │  │ Gang     │ │ Topology-    │ │ Preemption          │   │  │
│  │  │ Scheduler│ │ Aware Placer │ │ Controller          │   │  │
│  │  └──────────┘ └──────────────┘ └─────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Optimization                                               │  │
│  │  - GPU sharing (MPS/MIG)                                    │  │
│  │  - Bin packing                                              │  │
│  │  - Predictive scaling                                       │  │
│  │  - Spot instance integration                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from enum import Enum

class GPUType(Enum):
    A100_80GB = "a100_80gb"
    A100_40GB = "a100_40gb"
    H100 = "h100"
    L4 = "l4"

class WorkloadType(Enum):
    TRAINING = "training"           # Long, preemptible, needs NVLink
    FINE_TUNING = "fine_tuning"     # Medium, needs some multi-GPU
    INFERENCE_REALTIME = "inference_rt"  # Always-on, latency-critical
    INFERENCE_BATCH = "inference_batch"  # Throughput-optimized
    EXPERIMENT = "experiment"       # Short, best-effort

@dataclass
class GPUNode:
    node_id: str
    gpu_type: GPUType
    gpu_count: int
    available_gpus: int
    interconnect: str  # "nvlink", "pcie"
    memory_per_gpu_gb: int
    allocations: Dict[str, int] = field(default_factory=dict)  # job_id -> gpu_count

@dataclass
class GPUJob:
    job_id: str
    workload_type: WorkloadType
    gpu_count: int
    gpu_type_preference: List[GPUType]
    priority: int  # Lower = higher priority
    requires_nvlink: bool = False
    requires_same_node: bool = False
    estimated_duration: timedelta = timedelta(hours=1)
    max_preemption_cost: float = 0  # Cost of preempting (checkpoint time)
    submitted_at: datetime = field(default_factory=datetime.utcnow)

class GPUClusterScheduler:
    """Topology-aware GPU scheduler with preemption."""
    
    def __init__(self, nodes: List[GPUNode]):
        self.nodes = {n.node_id: n for n in nodes}
        self.job_queue: List[GPUJob] = []
        self.running_jobs: Dict[str, dict] = {}
    
    def schedule(self, job: GPUJob) -> Optional[dict]:
        """Schedule job with topology awareness."""
        
        # 1. Find candidate nodes
        candidates = self.find_candidates(job)
        
        if candidates:
            # 2. Select best placement
            placement = self.select_placement(job, candidates)
            self.allocate(job, placement)
            return placement
        
        # 3. Try preemption if high priority
        if job.priority <= 1:  # Only for high-priority jobs
            preemption_plan = self.find_preemption_plan(job)
            if preemption_plan:
                return self.execute_preemption(job, preemption_plan)
        
        # 4. Queue job
        self.job_queue.append(job)
        self.job_queue.sort(key=lambda j: (j.priority, j.submitted_at))
        return None
    
    def find_candidates(self, job: GPUJob) -> List[dict]:
        """Find nodes that can satisfy the job requirements."""
        candidates = []
        
        for node in self.nodes.values():
            # Type check
            if node.gpu_type not in job.gpu_type_preference:
                continue
            
            # Capacity check
            if node.available_gpus < job.gpu_count:
                continue
            
            # NVLink requirement
            if job.requires_nvlink and node.interconnect != "nvlink":
                continue
            
            # Same-node requirement for multi-GPU
            if job.requires_same_node and node.available_gpus < job.gpu_count:
                continue
            
            candidates.append({
                "node_id": node.node_id,
                "available": node.available_gpus,
                "score": self.score_placement(job, node)
            })
        
        # Also consider multi-node placement (for distributed training)
        if not job.requires_same_node and job.gpu_count > 8:
            multi_node = self.find_multi_node_placement(job)
            candidates.extend(multi_node)
        
        return sorted(candidates, key=lambda c: c["score"], reverse=True)
    
    def score_placement(self, job: GPUJob, node: GPUNode) -> float:
        """Score placement quality (higher = better fit)."""
        score = 0.0
        
        # Prefer exact fit (minimize fragmentation)
        waste = node.available_gpus - job.gpu_count
        score -= waste * 0.1  # Penalize waste
        
        # Prefer NVLink for training
        if job.workload_type == WorkloadType.TRAINING and node.interconnect == "nvlink":
            score += 1.0
        
        # Prefer filling nodes (bin-packing)
        utilization_after = 1 - (waste / node.gpu_count)
        score += utilization_after * 0.5
        
        # Separate inference from training (reduce interference)
        existing_types = set(
            self.running_jobs[jid]["workload_type"] 
            for jid in node.allocations.keys()
            if jid in self.running_jobs
        )
        if job.workload_type == WorkloadType.INFERENCE_REALTIME:
            if WorkloadType.TRAINING in existing_types:
                score -= 2.0  # Avoid co-locating inference with training
        
        return score
    
    def find_preemption_plan(self, job: GPUJob) -> Optional[List[str]]:
        """Find lowest-cost set of jobs to preempt."""
        preemptable = []
        
        for jid, info in self.running_jobs.items():
            if info["priority"] > job.priority:  # Only preempt lower priority
                preemptable.append({
                    "job_id": jid,
                    "gpu_count": info["gpu_count"],
                    "preemption_cost": info["checkpoint_cost"],
                    "node_id": info["node_id"]
                })
        
        # Find minimum cost subset that frees enough GPUs
        preemptable.sort(key=lambda p: p["preemption_cost"] / p["gpu_count"])
        
        plan = []
        freed = 0
        for p in preemptable:
            plan.append(p["job_id"])
            freed += p["gpu_count"]
            if freed >= job.gpu_count:
                return plan
        
        return None  # Can't free enough

class UtilizationOptimizer:
    """Maximize GPU utilization across the cluster."""
    
    def __init__(self, scheduler, metrics):
        self.scheduler = scheduler
        self.metrics = metrics
    
    async def optimize(self):
        """Periodic optimization pass."""
        
        # 1. GPU sharing via MIG (Multi-Instance GPU)
        underutilized = await self.find_underutilized_gpus()
        for gpu in underutilized:
            if gpu.utilization < 0.3 and gpu.workload_type == WorkloadType.INFERENCE_REALTIME:
                # Split into MIG instances for multiple inference models
                await self.enable_mig(gpu, partitions=2)
        
        # 2. Consolidate fragmented allocations
        fragmented_nodes = self.find_fragmented_nodes()
        for node in fragmented_nodes:
            await self.defragment(node)
        
        # 3. Scale suggestions
        if self.queue_depth() > 10:
            await self.recommend_scale_up()
        elif self.overall_utilization() < 0.5:
            await self.recommend_scale_down()
```

**Scheduling Priorities:**

| Workload | Priority | Preemptible | GPU Preference | Duration |
|----------|----------|-------------|---------------|----------|
| Real-time inference | 0 (highest) | Never | L4/A10 | Always-on |
| Batch inference (SLA) | 1 | After deadline | A100-40GB | Hours |
| Fine-tuning | 2 | With checkpoint | A100-80GB | Hours-Days |
| Training | 3 | With checkpoint | H100/A100 NVLink | Days-Weeks |
| Experiments | 4 (lowest) | Immediate | Any available | Minutes-Hours |

**Production Considerations:**
- **Utilization target**: 80%+ across cluster; <60% triggers cost review
- **NVLink awareness**: Distributed training jobs MUST be co-located on NVLink nodes; PCIe is 10x slower
- **Checkpoint on preempt**: Give 5-minute grace period; job saves checkpoint before eviction
- **Spot integration**: Experiments run on spot instances (70% cheaper); auto-migrate on preemption
- **Health monitoring**: Track GPU errors (ECC), temperature; auto-drain unhealthy GPUs

---

## Q190: Design a model marketplace internal to an enterprise where teams can discover, evaluate, and deploy shared models. Include model cards, usage metrics, and deprecation policies.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Internal Model Marketplace                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Discovery Layer                                            │  │
│  │  ┌──────────┐ ┌──────────────┐ ┌─────────────────────┐   │  │
│  │  │ Catalog  │ │ Search &     │ │ Recommendations      │   │  │
│  │  │ (Browse) │ │ Filter       │ │ ("Teams like yours   │   │  │
│  │  │          │ │              │ │  also use...")        │   │  │
│  │  └──────────┘ └──────────────┘ └─────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Model Card (Per Model)                                     │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ - Description & intended use                         │   │  │
│  │  │ - Performance metrics & benchmarks                   │   │  │
│  │  │ - Limitations & known biases                         │   │  │
│  │  │ - Input/Output schema                                │   │  │
│  │  │ - Usage examples (code snippets)                     │   │  │
│  │  │ - Owner team & support channel                       │   │  │
│  │  │ - SLA (latency, availability, accuracy)              │   │  │
│  │  │ - Deprecation status & migration guide               │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Evaluation & Deployment                                    │  │
│  │  ┌────────────┐ ┌────────────────┐ ┌──────────────────┐   │  │
│  │  │Try in      │ │ One-Click      │ │ Usage Analytics  │   │  │
│  │  │Playground  │ │ Deploy         │ │ & Billing        │   │  │
│  │  └────────────┘ └────────────────┘ └──────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

class ModelStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"      # Will be removed soon
    REMOVED = "removed"

@dataclass
class ModelCard:
    # Identity
    model_id: str
    name: str
    version: str
    owner_team: str
    
    # Description
    description: str
    intended_use: List[str]
    limitations: List[str]
    known_biases: List[str]
    
    # Technical
    input_schema: dict
    output_schema: dict
    supported_languages: List[str]
    model_size_mb: float
    inference_latency_p50_ms: float
    inference_latency_p99_ms: float
    
    # Quality
    benchmark_results: Dict[str, float] = field(default_factory=dict)
    evaluation_datasets: List[str] = field(default_factory=list)
    
    # Operational
    status: ModelStatus = ModelStatus.ACTIVE
    sla: dict = field(default_factory=lambda: {
        "availability": 0.999,
        "latency_p99_ms": 200,
        "accuracy_guarantee": None
    })
    
    # Lifecycle
    published_at: datetime = field(default_factory=datetime.utcnow)
    deprecated_at: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    migration_guide: Optional[str] = None
    successor_model: Optional[str] = None

class ModelMarketplace:
    def __init__(self, catalog_db, deployment_service, analytics, notification):
        self.catalog = catalog_db
        self.deployer = deployment_service
        self.analytics = analytics
        self.notifications = notification
    
    async def publish_model(self, model_card: ModelCard) -> str:
        """Publish model to marketplace after validation."""
        
        # Validate model card completeness
        self.validate_model_card(model_card)
        
        # Run automated quality checks
        quality = await self.run_quality_checks(model_card)
        if not quality.passed:
            raise ValueError(f"Quality checks failed: {quality.issues}")
        
        # Publish to catalog
        await self.catalog.upsert(model_card)
        
        # Notify subscribers interested in this category
        await self.notifications.notify_subscribers(
            category=model_card.intended_use,
            message=f"New model published: {model_card.name} v{model_card.version}"
        )
        
        return model_card.model_id
    
    async def discover(self, query: str = None, filters: dict = None) -> List[ModelCard]:
        """Discover models in marketplace."""
        results = await self.catalog.search(
            query=query,
            filters={
                **(filters or {}),
                "status": {"$in": ["active"]},
            }
        )
        
        # Enrich with usage metrics
        for model in results:
            model.usage_metrics = await self.analytics.get_usage(model.model_id)
        
        # Sort by relevance + popularity
        results.sort(key=lambda m: (
            m.search_score * 0.6 + 
            m.usage_metrics.get("weekly_requests", 0) * 0.4
        ), reverse=True)
        
        return results
    
    async def try_model(self, model_id: str, test_input: dict) -> dict:
        """Playground: try model with sample input."""
        model = await self.catalog.get(model_id)
        
        # Validate input against schema
        self.validate_against_schema(test_input, model.input_schema)
        
        # Run inference (limited to playground quota)
        result = await self.deployer.inference(
            model_id=model_id,
            input=test_input,
            quota_type="playground"
        )
        
        return result
    
    async def deprecate_model(self, model_id: str, 
                              successor_id: Optional[str],
                              sunset_date: datetime,
                              migration_guide: str):
        """Deprecate model with migration path."""
        model = await self.catalog.get(model_id)
        model.status = ModelStatus.DEPRECATED
        model.deprecated_at = datetime.utcnow()
        model.sunset_date = sunset_date
        model.successor_model = successor_id
        model.migration_guide = migration_guide
        
        await self.catalog.upsert(model)
        
        # Notify all consumers
        consumers = await self.analytics.get_consumers(model_id)
        for consumer in consumers:
            await self.notifications.notify(
                team=consumer.team,
                severity="warning",
                message=f"Model {model.name} deprecated. "
                       f"Sunset: {sunset_date.isoformat()}. "
                       f"Migrate to: {successor_id}",
                action_url=f"/marketplace/{model_id}/migration"
            )
        
        # Schedule sunset enforcement
        await self.schedule_sunset(model_id, sunset_date)

class DeprecationPolicy:
    """Enforce model deprecation lifecycle."""
    
    LIFECYCLE = {
        "deprecation_notice": timedelta(days=90),   # 90 days warning
        "sunset_warning": timedelta(days=30),       # 30 days: aggressive notifications
        "sunset": timedelta(days=0),                # Access removed
        "data_retention": timedelta(days=30),       # 30 days after sunset: delete artifacts
    }
    
    async def enforce(self):
        """Periodic enforcement of deprecation policies."""
        deprecated = await self.catalog.get_by_status(ModelStatus.DEPRECATED)
        
        for model in deprecated:
            days_until_sunset = (model.sunset_date - datetime.utcnow()).days
            
            if days_until_sunset <= 0:
                # Sunset: redirect traffic to successor
                await self.sunset_model(model)
            elif days_until_sunset <= 30:
                # Aggressive weekly notifications
                await self.send_urgent_migration_reminder(model)
            elif days_until_sunset <= 60:
                # Monthly reminder
                await self.send_migration_reminder(model)
```

**Usage Analytics Dashboard:**

| Metric | Purpose | Visualization |
|--------|---------|---------------|
| Weekly active consumers | Model popularity | Line chart (trend) |
| Request volume | Load patterns | Time-series |
| Error rate | Reliability | Alert if > threshold |
| Latency distribution | Performance | Histogram |
| Consumer teams | Dependency mapping | Dependency graph |
| Cost per request | Economics | Per-team attribution |

**Deprecation Timeline:**

| Phase | Timing | Action |
|-------|--------|--------|
| Deprecation | T-90 days | Notice + migration guide published |
| Active migration | T-60 days | Monthly reminders to consumers |
| Urgent migration | T-30 days | Weekly reminders + team leads CC'd |
| Sunset | T-0 | Traffic routed to successor (if available) or 410 Gone |
| Cleanup | T+30 days | Artifacts deleted, catalog entry marked "removed" |

**Production Considerations:**
- **Self-service deployment**: Consumer team clicks "Deploy" and gets an endpoint in 5 minutes
- **Cost attribution**: Track inference costs per consumer team (chargeback model)
- **Quality monitoring**: Marketplace monitors all deployed models; alert owners on degradation
- **Versioning**: Semantic versioning; minor versions backward-compatible, major versions break
- **Reviews**: Models serving > 1000 consumers require security and bias review before updates
# Edge and Hybrid AI Deployment (Questions 191-195)

## Q191: Design a hybrid cloud-edge AI architecture where sensitive queries are processed on-premises and non-sensitive ones go to the cloud. Include routing logic, model synchronization, and fallback mechanisms.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              Hybrid Cloud-Edge AI Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Intelligent Router                                            │   │
│  │  Query → Classify Sensitivity → Route                          │   │
│  │                                                                 │   │
│  │  [Sensitive: PII, PHI, financial] → On-Premises                │   │
│  │  [Non-sensitive: general knowledge] → Cloud                    │   │
│  │  [Ambiguous] → On-Premises (safe default)                     │   │
│  └──────────────────────┬────────────────┬───────────────────────┘   │
│                          │                │                           │
│            ┌─────────────▼──┐    ┌───────▼──────────────┐           │
│            │  On-Premises   │    │  Cloud AI Platform    │           │
│            │                │    │                       │           │
│            │ ┌────────────┐ │    │ ┌─────────────────┐  │           │
│            │ │ Local LLM  │ │    │ │ GPT-4 / Claude  │  │           │
│            │ │ (Llama 70B)│ │    │ │ (Full power)    │  │           │
│            │ └────────────┘ │    │ └─────────────────┘  │           │
│            │ ┌────────────┐ │    │ ┌─────────────────┐  │           │
│            │ │ Local      │ │    │ │ Cloud Vector DB │  │           │
│            │ │ Vector DB  │ │    │ │ (Full corpus)   │  │           │
│            │ └────────────┘ │    │ └─────────────────┘  │           │
│            │                │    │                       │           │
│            │ Data never     │    │ Non-sensitive data    │           │
│            │ leaves premise │    │ only                  │           │
│            └────────────────┘    └───────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
import asyncio

class SensitivityLevel(Enum):
    PUBLIC = "public"           # Route to cloud (cheaper, better)
    INTERNAL = "internal"       # Route to cloud with encryption
    CONFIDENTIAL = "confidential"  # On-premises only
    RESTRICTED = "restricted"   # On-premises, enhanced audit

@dataclass
class RoutingDecision:
    target: str  # "cloud" or "on_prem"
    reason: str
    confidence: float
    fallback: str  # Where to route if primary fails

class SensitivityClassifier:
    """Classify query sensitivity for routing decisions."""
    
    def __init__(self):
        self.pii_patterns = self.load_pii_patterns()
        self.sensitive_topics = self.load_sensitive_topics()
    
    def classify(self, query: str, context: dict) -> SensitivityLevel:
        # Rule-based fast path (< 1ms)
        if self.contains_pii(query):
            return SensitivityLevel.RESTRICTED
        
        if context.get("data_classification") == "confidential":
            return SensitivityLevel.CONFIDENTIAL
        
        if context.get("department") in ["legal", "hr", "finance"]:
            return SensitivityLevel.CONFIDENTIAL
        
        # Content-based classification
        if self.matches_sensitive_topics(query):
            return SensitivityLevel.CONFIDENTIAL
        
        return SensitivityLevel.PUBLIC

class HybridAIRouter:
    """Routes queries between on-prem and cloud with fallback."""
    
    def __init__(self, classifier, on_prem_client, cloud_client, circuit_breaker):
        self.classifier = classifier
        self.on_prem = on_prem_client
        self.cloud = cloud_client
        self.cb = circuit_breaker
    
    async def route_query(self, query: str, context: dict) -> dict:
        sensitivity = self.classifier.classify(query, context)
        
        routing = self.get_routing(sensitivity)
        
        try:
            if routing.target == "on_prem":
                result = await self.execute_on_prem(query, context)
            else:
                if self.cb.is_open("cloud"):
                    # Cloud circuit breaker open, fall back to on-prem
                    result = await self.execute_on_prem(query, context)
                else:
                    result = await self.execute_cloud(query, context)
        except Exception as e:
            # Fallback
            result = await self.execute_fallback(query, context, routing, e)
        
        return result
    
    async def execute_on_prem(self, query: str, context: dict) -> dict:
        """Execute on local infrastructure."""
        return await self.on_prem.query(
            query=query,
            model="llama-3-70b",  # Local model
            index="local_vector_db",
            context=context
        )
    
    async def execute_cloud(self, query: str, context: dict) -> dict:
        """Execute on cloud with non-sensitive data only."""
        # Strip any sensitive context before sending to cloud
        safe_context = self.sanitize_for_cloud(context)
        
        return await self.cloud.query(
            query=query,
            model="gpt-4o",
            index="cloud_vector_db",
            context=safe_context
        )
    
    def get_routing(self, sensitivity: SensitivityLevel) -> RoutingDecision:
        routes = {
            SensitivityLevel.PUBLIC: RoutingDecision("cloud", "non-sensitive", 0.95, "on_prem"),
            SensitivityLevel.INTERNAL: RoutingDecision("cloud", "internal-ok", 0.9, "on_prem"),
            SensitivityLevel.CONFIDENTIAL: RoutingDecision("on_prem", "confidential", 0.99, "on_prem"),
            SensitivityLevel.RESTRICTED: RoutingDecision("on_prem", "restricted", 1.0, "reject"),
        }
        return routes[sensitivity]

class ModelSynchronizer:
    """Keep on-prem models and indices in sync with cloud."""
    
    async def sync_models(self):
        """Periodic sync of model updates to on-prem."""
        # 1. Check for new model versions in registry
        new_versions = await self.registry.get_pending_sync()
        
        for version in new_versions:
            # 2. Download model artifact
            artifact = await self.download_artifact(version.artifact_uri)
            
            # 3. Deploy to on-prem (blue-green)
            await self.on_prem_deployer.deploy(artifact, strategy="blue_green")
            
            # 4. Mark synced
            await self.registry.mark_synced(version.id)
    
    async def sync_index(self):
        """Sync non-sensitive documents to cloud index."""
        # Only sync documents classified as non-sensitive
        changes = await self.change_feed.get_since(self.last_sync)
        
        non_sensitive = [c for c in changes 
                        if c.sensitivity in (SensitivityLevel.PUBLIC, SensitivityLevel.INTERNAL)]
        
        if non_sensitive:
            await self.cloud_index.upsert_batch(non_sensitive)
        
        self.last_sync = datetime.utcnow()
```

**Routing Decision Matrix:**

| Sensitivity | Primary | Fallback | Data Sent to Cloud |
|-------------|---------|----------|--------------------|
| Public | Cloud | On-prem | Full query + context |
| Internal | Cloud | On-prem | Query only (no PII) |
| Confidential | On-prem | On-prem (degraded) | Nothing |
| Restricted | On-prem | Reject | Nothing |

**Production Considerations:**
- **Default safe**: When in doubt, route to on-prem (false positive is cheaper than data leak)
- **Latency budget**: On-prem may be slower (smaller model); set higher latency SLA for sensitive queries
- **Model gap**: On-prem Llama-70B vs cloud GPT-4; accept quality gap for sensitive queries
- **Sync security**: Model artifacts encrypted in transit; index sync only sends non-sensitive embeddings
- **Audit**: Log all routing decisions; regular audit that sensitive data never went to cloud

---

## Q192: Design a federated learning system for improving AI models using data from multiple organizations without sharing raw data. Include privacy guarantees, aggregation protocols, and model convergence.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Federated Learning System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Central Aggregation Server                                  ││
│  │  (Orchestrates rounds, never sees raw data)                  ││
│  │                                                               ││
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐    ││
│  │  │ Model    │  │ Aggregator   │  │ Convergence        │    ││
│  │  │ Registry │  │ (FedAvg/     │  │ Monitor            │    ││
│  │  │          │  │  FedProx)    │  │                    │    ││
│  │  └──────────┘  └──────────────┘  └────────────────────┘    ││
│  └─────────────────────────────────────────────────────────────┘│
│                          ▲   │                                    │
│                          │   │ Global Model                      │
│              Gradients   │   ▼                                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Org A     │  │ Org B     │  │ Org C     │  │ Org D     │  │
│  │           │  │           │  │           │  │           │  │
│  │ Local     │  │ Local     │  │ Local     │  │ Local     │  │
│  │ Training  │  │ Training  │  │ Training  │  │ Training  │  │
│  │           │  │           │  │           │  │           │  │
│  │ Data never│  │ Data never│  │ Data never│  │ Data never│  │
│  │ leaves    │  │ leaves    │  │ leaves    │  │ leaves    │  │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np

@dataclass
class FederatedConfig:
    num_rounds: int = 100
    min_participants_per_round: int = 3
    local_epochs: int = 5
    learning_rate: float = 0.01
    aggregation_strategy: str = "fedavg"  # fedavg, fedprox, scaffold
    
    # Privacy
    differential_privacy: bool = True
    dp_epsilon: float = 8.0
    dp_delta: float = 1e-5
    clip_norm: float = 1.0
    
    # Robustness
    byzantine_tolerance: int = 1  # Tolerate N malicious participants
    min_sample_size: int = 100   # Minimum local data per participant

class FederatedServer:
    """Central aggregation server."""
    
    def __init__(self, config: FederatedConfig, model_template):
        self.config = config
        self.global_model = model_template
        self.round_number = 0
        self.participants = []
        self.history = []
    
    async def run_training(self):
        """Execute federated training rounds."""
        for round_num in range(self.config.num_rounds):
            self.round_number = round_num
            
            # 1. Select participants for this round
            selected = self.select_participants()
            
            if len(selected) < self.config.min_participants_per_round:
                continue  # Not enough participants
            
            # 2. Distribute global model to participants
            global_weights = self.global_model.get_weights()
            
            # 3. Collect local updates (in parallel)
            updates = await self.collect_updates(selected, global_weights)
            
            # 4. Validate updates (Byzantine tolerance)
            valid_updates = self.filter_malicious(updates)
            
            # 5. Aggregate
            aggregated = self.aggregate(valid_updates)
            
            # 6. Apply differential privacy noise
            if self.config.differential_privacy:
                aggregated = self.add_dp_noise(aggregated)
            
            # 7. Update global model
            self.global_model.set_weights(aggregated)
            
            # 8. Evaluate convergence
            metrics = await self.evaluate_global_model()
            self.history.append(metrics)
            
            if self.has_converged():
                break
    
    def aggregate(self, updates: List[dict]) -> dict:
        """Weighted federated averaging."""
        if self.config.aggregation_strategy == "fedavg":
            # Weight by number of local samples
            total_samples = sum(u["num_samples"] for u in updates)
            
            aggregated = {}
            for key in updates[0]["weights"].keys():
                weighted_sum = sum(
                    u["weights"][key] * (u["num_samples"] / total_samples)
                    for u in updates
                )
                aggregated[key] = weighted_sum
            
            return aggregated
        
        elif self.config.aggregation_strategy == "fedprox":
            # FedProx: add proximal term to handle heterogeneity
            return self.fedprox_aggregate(updates)
    
    def add_dp_noise(self, weights: dict) -> dict:
        """Add calibrated Gaussian noise for differential privacy."""
        sensitivity = self.config.clip_norm / len(self.participants)
        sigma = sensitivity * np.sqrt(2 * np.log(1.25 / self.config.dp_delta)) / self.config.dp_epsilon
        
        noisy_weights = {}
        for key, w in weights.items():
            noise = np.random.normal(0, sigma, size=w.shape)
            noisy_weights[key] = w + noise
        
        return noisy_weights
    
    def filter_malicious(self, updates: List[dict]) -> List[dict]:
        """Detect and filter potential Byzantine/poisoning attacks."""
        # Use median-based aggregation (robust to outliers)
        if len(updates) <= 2 * self.config.byzantine_tolerance:
            return updates  # Not enough to filter
        
        # Compute pairwise distances between updates
        distances = self.compute_update_distances(updates)
        
        # Remove updates that are too far from median
        median_distance = np.median(distances)
        threshold = 3 * median_distance  # 3x median as outlier threshold
        
        valid = [u for u, d in zip(updates, distances) if d < threshold]
        return valid

class FederatedClient:
    """Runs on each participating organization."""
    
    def __init__(self, local_data, config: FederatedConfig):
        self.data = local_data
        self.config = config
    
    async def train_local(self, global_weights: dict) -> dict:
        """Local training on organization's private data."""
        # Initialize local model with global weights
        model = self.create_model()
        model.set_weights(global_weights)
        
        # Train on local data
        for epoch in range(self.config.local_epochs):
            for batch in self.data.get_batches():
                loss = model.train_step(batch)
        
        # Compute update (difference from global)
        local_weights = model.get_weights()
        update = {
            key: local_weights[key] - global_weights[key]
            for key in local_weights.keys()
        }
        
        # Clip gradients for DP
        if self.config.differential_privacy:
            update = self.clip_update(update, self.config.clip_norm)
        
        return {
            "weights": local_weights,
            "num_samples": len(self.data),
            "local_loss": loss
        }
    
    def clip_update(self, update: dict, max_norm: float) -> dict:
        """Clip update norm for differential privacy."""
        total_norm = np.sqrt(sum(
            np.sum(v ** 2) for v in update.values()
        ))
        
        if total_norm > max_norm:
            scale = max_norm / total_norm
            return {k: v * scale for k, v in update.items()}
        
        return update
```

**Privacy Guarantees:**

| Technique | Protection | Cost |
|-----------|-----------|------|
| Federated Learning | Raw data stays local | Communication overhead |
| Differential Privacy | Individual records protected | Model accuracy loss (2-5%) |
| Secure Aggregation | Server can't see individual updates | Compute overhead (2-3x) |
| Gradient Clipping | Limits per-sample influence | Slightly slower convergence |

**Production Considerations:**
- **Heterogeneity**: Organizations have different data distributions; FedProx handles this better than FedAvg
- **Communication efficiency**: Compress updates (top-k sparsification saves 90% bandwidth)
- **Stragglers**: Set timeout per round; proceed without slow participants
- **Incentive alignment**: Track each org's contribution quality; exclude free-riders
- **Convergence monitoring**: Track global model quality per round; stop when plateau

---

## Q193: Design an AI system that works in disconnected/offline environments (field operations, aircraft, submarines). Include model compression, local inference, and sync-when-connected patterns.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Disconnected AI System                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Edge Device (Offline-First)                                 ││
│  │                                                               ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  ││
│  │  │ Compressed   │  │ Local Vector │  │ Inference Engine │  ││
│  │  │ Model        │  │ Index        │  │ (ONNX Runtime/   │  ││
│  │  │ (Quantized)  │  │ (Subset)     │  │  TensorRT)       │  ││
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  ││
│  │                                                               ││
│  │  ┌──────────────┐  ┌──────────────┐                        ││
│  │  │ Query Log    │  │ Feedback     │                        ││
│  │  │ (Offline)    │  │ Queue        │                        ││
│  │  └──────────────┘  └──────────────┘                        ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│             ↕ Sync when connected (satellite/wifi)               │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Cloud Backend                                               ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐ ││
│  │  │ Full Models │  │ Full Index  │  │ Update Packager    │ ││
│  │  │             │  │             │  │ (Delta Compression)│ ││
│  │  └─────────────┘  └─────────────┘  └────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class ConnectivityState(Enum):
    CONNECTED = "connected"
    INTERMITTENT = "intermittent"
    DISCONNECTED = "disconnected"

@dataclass
class EdgeDeviceConfig:
    max_model_size_mb: int = 2048      # 2GB model budget
    max_index_size_mb: int = 1024      # 1GB vector index
    max_storage_mb: int = 8192         # 8GB total storage
    target_inference_ms: int = 500     # 500ms max latency
    sync_priority: str = "model_updates_first"

class OfflineAISystem:
    """AI system designed for disconnected environments."""
    
    def __init__(self, config: EdgeDeviceConfig):
        self.config = config
        self.model = self.load_compressed_model()
        self.index = self.load_local_index()
        self.query_log = OfflineQueryLog()
        self.sync_queue = SyncQueue()
        self.connectivity = ConnectivityState.DISCONNECTED
    
    async def query(self, question: str, context: dict = None) -> dict:
        """Process query entirely locally."""
        # 1. Local retrieval
        query_embedding = self.model.embed(question)
        results = self.index.search(query_embedding, top_k=5)
        
        # 2. Local generation
        response = self.model.generate(
            prompt=self.build_prompt(question, results),
            max_tokens=512
        )
        
        # 3. Confidence estimation
        confidence = self.estimate_confidence(results, response)
        
        # 4. Log for later sync
        self.query_log.append({
            "query": question,
            "response": response,
            "confidence": confidence,
            "timestamp": datetime.utcnow(),
            "connectivity": self.connectivity.value
        })
        
        # 5. If low confidence, mark for cloud verification later
        if confidence < 0.6:
            self.sync_queue.add_verification_request(question, response)
        
        return {
            "response": response,
            "confidence": confidence,
            "source": "local",
            "results_count": len(results)
        }

class ModelCompressor:
    """Compress models for edge deployment."""
    
    async def compress_for_edge(self, model_path: str, 
                                 target_size_mb: int) -> str:
        """Multi-technique compression pipeline."""
        
        # 1. Quantization (INT8 or INT4)
        quantized = await self.quantize(
            model_path,
            precision="int4",  # 4-bit quantization (4x size reduction)
            calibration_data=self.get_calibration_set()
        )
        
        # 2. Pruning (remove less important weights)
        pruned = await self.prune(
            quantized,
            sparsity=0.5,  # Remove 50% of weights
            method="magnitude"
        )
        
        # 3. Knowledge distillation (if still too large)
        current_size = self.get_size_mb(pruned)
        if current_size > target_size_mb:
            distilled = await self.distill(
                teacher=model_path,
                student_config=self.get_smaller_architecture(target_size_mb)
            )
            return distilled
        
        return pruned
    
    def get_compression_options(self, budget_mb: int) -> dict:
        """Recommend compression strategy based on budget."""
        if budget_mb >= 4096:
            return {"model": "llama-3-8b", "quant": "int8", "quality": "high"}
        elif budget_mb >= 2048:
            return {"model": "llama-3-8b", "quant": "int4", "quality": "medium"}
        elif budget_mb >= 512:
            return {"model": "phi-3-mini", "quant": "int4", "quality": "acceptable"}
        else:
            return {"model": "tinyllama-1b", "quant": "int4", "quality": "basic"}

class SyncWhenConnected:
    """Bidirectional sync when connectivity is available."""
    
    async def sync(self, bandwidth_kbps: float):
        """Prioritized sync based on available bandwidth."""
        
        # Priority 1: Download critical model updates
        if await self.has_critical_update():
            await self.download_model_update(bandwidth_kbps)
        
        # Priority 2: Upload query logs and feedback
        await self.upload_query_logs()
        
        # Priority 3: Download index updates (delta)
        await self.download_index_delta(bandwidth_kbps)
        
        # Priority 4: Download verification results
        await self.download_verifications()
        
        # Priority 5: Upload usage analytics
        await self.upload_analytics()
    
    async def download_model_update(self, bandwidth_kbps: float):
        """Download model update with bandwidth awareness."""
        update = await self.cloud.get_pending_model_update(self.device_id)
        
        if not update:
            return
        
        # Estimate download time
        size_kb = update.size_bytes / 1024
        estimated_seconds = size_kb / bandwidth_kbps
        
        if estimated_seconds > 3600:  # > 1 hour
            # Use delta update instead
            delta = await self.cloud.get_delta_update(
                self.device_id, self.current_model_version
            )
            await self.apply_delta(delta)
        else:
            await self.download_full(update)
    
    async def download_index_delta(self, bandwidth_kbps: float):
        """Download only changed vectors since last sync."""
        last_sync = self.get_last_index_sync_version()
        
        delta = await self.cloud.get_index_changes(
            since_version=last_sync,
            max_size_kb=bandwidth_kbps * 300  # 5 min worth of bandwidth
        )
        
        # Apply changes locally
        for change in delta.additions:
            self.index.add(change.id, change.vector, change.metadata)
        for change in delta.deletions:
            self.index.delete(change.id)
        for change in delta.updates:
            self.index.update(change.id, change.vector, change.metadata)
```

**Model Size vs Quality Tradeoffs:**

| Model | Size | Latency (CPU) | Quality vs GPT-4 |
|-------|------|---------------|-------------------|
| Llama-3-70B INT4 | 35GB | 5-10s | ~85% |
| Llama-3-8B INT4 | 4GB | 500ms | ~70% |
| Phi-3-mini INT4 | 2GB | 200ms | ~60% |
| TinyLlama-1B INT4 | 500MB | 50ms | ~40% |

**Production Considerations:**
- **Graceful degradation**: System works at reduced quality offline; clearly communicates confidence
- **Delta sync**: Only transfer changes (saves 90% bandwidth on intermittent connections)
- **Conflict resolution**: If user corrected offline responses, reconcile with cloud state on sync
- **Hardware diversity**: Support x86, ARM, GPU-less environments; ONNX for portability
- **Battery awareness**: Throttle inference on battery-powered devices; prefer cached answers

---

## Q194: Design a progressive enhancement AI architecture where the system provides increasingly better responses as more compute becomes available (edge → local GPU → cloud).

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│              Progressive Enhancement AI                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Response Quality Tiers                                      ││
│  │                                                               ││
│  │  Tier 1 (Instant, <50ms): Cached / Pattern Match             ││
│  │     ↓ If no cache hit                                        ││
│  │  Tier 2 (Fast, <500ms): Small local model (1-3B)             ││
│  │     ↓ If low confidence                                      ││
│  │  Tier 3 (Good, <2s): Local GPU model (8-13B)                 ││
│  │     ↓ If complex query                                       ││
│  │  Tier 4 (Best, <5s): Cloud model (GPT-4 / Claude)            ││
│  │                                                               ││
│  │  User sees streaming: fast draft → refined → best            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass
from typing import AsyncIterator, Optional
import asyncio

@dataclass
class TierConfig:
    name: str
    model: str
    max_latency_ms: int
    quality_score: float  # Expected quality 0-1
    cost_per_request: float
    available: bool = True

class ProgressiveEnhancementAI:
    """Provide best possible response given available compute."""
    
    def __init__(self):
        self.tiers = [
            TierConfig("cache", "semantic_cache", 10, 0.95, 0.0),
            TierConfig("tiny", "tinyllama-1b-q4", 100, 0.4, 0.0001),
            TierConfig("local", "llama-3-8b-q8", 500, 0.7, 0.001),
            TierConfig("local_gpu", "llama-3-13b", 1500, 0.8, 0.005),
            TierConfig("cloud", "gpt-4o", 3000, 0.95, 0.03),
        ]
    
    async def query_progressive(self, question: str, 
                                 context: dict) -> AsyncIterator[dict]:
        """Stream progressively better responses."""
        
        best_response = None
        best_quality = 0.0
        
        for tier in self.tiers:
            if not tier.available:
                continue
            
            try:
                response = await asyncio.wait_for(
                    self.execute_tier(tier, question, context),
                    timeout=tier.max_latency_ms / 1000
                )
                
                if response and response["quality"] > best_quality:
                    best_response = response
                    best_quality = response["quality"]
                    
                    # Yield improved response to client
                    yield {
                        "response": response["text"],
                        "tier": tier.name,
                        "quality": response["quality"],
                        "is_final": False
                    }
                
                # Stop if quality is good enough
                if best_quality >= 0.9:
                    break
                    
            except asyncio.TimeoutError:
                continue  # Skip to next tier
            except Exception:
                continue  # Graceful degradation
        
        # Final response
        if best_response:
            yield {
                "response": best_response["text"],
                "tier": best_response.get("tier", "unknown"),
                "quality": best_quality,
                "is_final": True
            }
    
    async def execute_tier(self, tier: TierConfig, question: str, 
                           context: dict) -> Optional[dict]:
        """Execute at a specific tier."""
        
        if tier.name == "cache":
            cached = await self.semantic_cache.lookup(question)
            if cached:
                return {"text": cached, "quality": 0.95, "tier": "cache"}
            return None
        
        elif tier.name == "tiny":
            # Fast draft with tiny model
            text = await self.tiny_model.generate(question, max_tokens=200)
            confidence = self.estimate_confidence(text, question)
            return {"text": text, "quality": confidence * 0.6, "tier": "tiny"}
        
        elif tier.name == "local":
            # Better model, retrieval-augmented
            results = await self.local_index.search(question, top_k=3)
            text = await self.local_model.generate(
                self.build_rag_prompt(question, results),
                max_tokens=500
            )
            return {"text": text, "quality": 0.7, "tier": "local"}
        
        elif tier.name == "cloud":
            # Best quality, full RAG
            results = await self.cloud_index.search(question, top_k=10)
            text = await self.cloud_model.generate(
                self.build_rag_prompt(question, results),
                max_tokens=1000
            )
            return {"text": text, "quality": 0.95, "tier": "cloud"}

    async def query_with_budget(self, question: str, 
                                 max_latency_ms: int,
                                 max_cost: float) -> dict:
        """Query with explicit latency and cost constraints."""
        
        # Select best tier within budget
        eligible_tiers = [
            t for t in self.tiers 
            if t.max_latency_ms <= max_latency_ms 
            and t.cost_per_request <= max_cost
            and t.available
        ]
        
        if not eligible_tiers:
            return {"error": "No tier meets constraints"}
        
        # Use highest quality eligible tier
        best_tier = max(eligible_tiers, key=lambda t: t.quality_score)
        return await self.execute_tier(best_tier, question, {})
```

**Progressive Enhancement Tiers:**

| Tier | Latency | Quality | Cost | Use Case |
|------|---------|---------|------|----------|
| Cache | <10ms | 95% (if hit) | $0 | Repeated queries |
| Tiny model (CPU) | <100ms | 40% | $0.0001 | Instant draft |
| Local 8B (GPU) | <500ms | 70% | $0.001 | Good enough for most |
| Local 13B (GPU) | <2s | 80% | $0.005 | Complex questions |
| Cloud GPT-4 | <5s | 95% | $0.03 | When quality matters |

**Production Considerations:**
- **Streaming UX**: Show fast draft immediately, then refine ("shimmer" effect like Perplexity)
- **Early termination**: If tiny model response has high confidence, skip expensive tiers
- **Compute detection**: Auto-detect available hardware (GPU? Cloud connectivity?) at startup
- **Cost-aware routing**: User/tenant config specifies max cost; stay within budget
- **Quality estimation**: Use lightweight classifier to predict if higher tier would help (avoid unnecessary cost)

---

## Q195: Design a model update distribution system for 10,000 edge devices. Include delta updates, A/B testing on edge, rollback capability, and bandwidth-efficient delivery.

### Answer

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│         Model Update Distribution System (10K devices)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Update Server                                              │  │
│  │  ┌──────────┐ ┌──────────────┐ ┌───────────────────────┐  │  │
│  │  │ Release  │ │ Delta        │ │ Rollout Controller    │  │  │
│  │  │ Manager  │ │ Generator    │ │ (Phased + A/B)        │  │  │
│  │  └──────────┘ └──────────────┘ └───────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │  CDN / Distribution Layer                                   │  │
│  │  (Geo-distributed, P2P optional)                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │  Edge Devices (10,000)                                      │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        ┌─────┐         │  │
│  │  │Dev 1│ │Dev 2│ │Dev 3│ │Dev 4│  ...   │Dev N│         │  │
│  │  │v1.2 │ │v1.2 │ │v1.3 │ │v1.2 │        │v1.3 │         │  │
│  │  │     │ │(A/B)│ │     │ │     │        │     │         │  │
│  │  └─────┘ └─────┘ └─────┘ └─────┘        └─────┘         │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import hashlib

@dataclass
class ModelRelease:
    version: str
    full_artifact_uri: str
    full_size_bytes: int
    delta_from: Dict[str, str] = field(default_factory=dict)  # prev_version -> delta_uri
    delta_sizes: Dict[str, int] = field(default_factory=dict)
    checksum: str = ""
    min_device_firmware: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class RolloutConfig:
    phases: List[dict] = field(default_factory=lambda: [
        {"name": "canary", "percent": 1, "duration_hours": 24},
        {"name": "early_adopters", "percent": 10, "duration_hours": 48},
        {"name": "general_1", "percent": 50, "duration_hours": 24},
        {"name": "general_2", "percent": 100, "duration_hours": 0},
    ])
    auto_rollback_on_error_rate: float = 0.05
    health_check_interval_minutes: int = 60

class UpdateDistributionSystem:
    """Distribute model updates to 10K edge devices efficiently."""
    
    def __init__(self, release_store, device_registry, cdn, metrics):
        self.releases = release_store
        self.devices = device_registry
        self.cdn = cdn
        self.metrics = metrics
    
    async def create_release(self, model_path: str, version: str) -> ModelRelease:
        """Create release with delta updates from previous versions."""
        
        # Upload full artifact
        full_uri = await self.cdn.upload(model_path, f"models/{version}/full")
        full_size = os.path.getsize(model_path)
        
        # Generate deltas from recent versions
        recent_versions = await self.releases.get_recent(n=3)
        deltas = {}
        delta_sizes = {}
        
        for prev in recent_versions:
            delta = await self.generate_delta(prev.full_artifact_uri, model_path)
            delta_uri = await self.cdn.upload(delta, f"models/{version}/delta_from_{prev.version}")
            deltas[prev.version] = delta_uri
            delta_sizes[prev.version] = os.path.getsize(delta)
        
        release = ModelRelease(
            version=version,
            full_artifact_uri=full_uri,
            full_size_bytes=full_size,
            delta_from=deltas,
            delta_sizes=delta_sizes,
            checksum=self.compute_checksum(model_path)
        )
        
        await self.releases.save(release)
        return release
    
    async def rollout(self, version: str, config: RolloutConfig):
        """Phased rollout to device fleet."""
        release = await self.releases.get(version)
        
        for phase in config.phases:
            # Select devices for this phase
            target_devices = await self.select_devices(
                percent=phase["percent"],
                exclude_already_updated=True
            )
            
            # Notify devices of available update
            for device_batch in self.batch(target_devices, size=100):
                await self.notify_devices(device_batch, release)
            
            # Monitor phase
            if phase["duration_hours"] > 0:
                healthy = await self.monitor_phase(
                    version, 
                    duration_hours=phase["duration_hours"],
                    error_threshold=config.auto_rollback_on_error_rate
                )
                
                if not healthy:
                    await self.rollback(version)
                    return {"status": "rolled_back", "phase": phase["name"]}
        
        return {"status": "complete", "devices_updated": len(target_devices)}
    
    async def monitor_phase(self, version: str, duration_hours: int, 
                            error_threshold: float) -> bool:
        """Monitor rollout health during a phase."""
        end_time = datetime.utcnow() + timedelta(hours=duration_hours)
        
        while datetime.utcnow() < end_time:
            # Collect metrics from updated devices
            metrics = await self.metrics.get_version_metrics(version)
            
            if metrics.error_rate > error_threshold:
                return False
            if metrics.inference_latency_p99 > metrics.baseline_latency * 2:
                return False
            if metrics.quality_score < metrics.baseline_quality * 0.95:
                return False
            
            await asyncio.sleep(3600)  # Check hourly
        
        return True

class EdgeDeviceUpdater:
    """Runs on each edge device to handle updates."""
    
    def __init__(self, device_id: str, current_version: str):
        self.device_id = device_id
        self.current_version = current_version
        self.model_slots = {"active": current_version, "standby": None}
    
    async def apply_update(self, release: ModelRelease) -> bool:
        """Apply update with A/B slot pattern."""
        
        # 1. Determine if delta or full download needed
        if self.current_version in release.delta_from:
            # Delta update (much smaller)
            uri = release.delta_from[self.current_version]
            size = release.delta_sizes[self.current_version]
            is_delta = True
        else:
            # Full download
            uri = release.full_artifact_uri
            size = release.full_size_bytes
            is_delta = False
        
        # 2. Check bandwidth/storage
        if not self.has_sufficient_resources(size):
            return False
        
        # 3. Download to standby slot
        artifact = await self.download_with_resume(uri)
        
        # 4. Verify checksum
        if self.compute_checksum(artifact) != release.checksum:
            return False  # Corrupt download
        
        # 5. Apply (delta or full)
        if is_delta:
            new_model = self.apply_delta(self.get_active_model(), artifact)
        else:
            new_model = artifact
        
        # 6. Load into standby slot
        self.model_slots["standby"] = release.version
        await self.load_model_to_slot("standby", new_model)
        
        # 7. Run local validation
        if await self.validate_model("standby"):
            # 8. Atomic swap
            self.model_slots["active"], self.model_slots["standby"] = \
                self.model_slots["standby"], self.model_slots["active"]
            self.current_version = release.version
            return True
        else:
            # Rollback: discard standby
            self.model_slots["standby"] = None
            return False
    
    async def rollback(self):
        """Instant rollback to previous version (in standby slot)."""
        if self.model_slots["standby"]:
            self.model_slots["active"], self.model_slots["standby"] = \
                self.model_slots["standby"], self.model_slots["active"]
            self.current_version = self.model_slots["active"]
```

**Bandwidth Optimization:**

| Technique | Savings | Complexity |
|-----------|---------|-----------|
| Delta updates (bsdiff) | 70-90% smaller | Medium |
| Compression (zstd) | 30-50% smaller | Low |
| P2P distribution | Reduces server load | High |
| Scheduled downloads (off-peak) | Reduces congestion | Low |
| Progressive download (layers) | Early inference | Medium |

**Production Considerations:**
- **A/B slot pattern**: Two model slots per device; atomic swap enables instant rollback
- **Resume support**: Downloads resume from where they left off after connection drops
- **Fleet segmentation**: Group devices by hardware, region, use case for targeted rollouts
- **Compliance**: Some devices in regulated environments need update approval before applying
- **Telemetry**: Track update success rate, download failures, rollback frequency per device cohort
