# Real-World Examples: Engineering Foundations for AI Systems

## 1. How Netflix Builds Their AI Microservices

### Service Architecture Overview

Netflix runs 700+ microservices. Their ML/AI services follow specific patterns:

**Service Mesh: Zuul + Eureka + Custom Sidecar**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Netflix AI Service Mesh                        │
│                                                                   │
│  ┌──────────┐     ┌──────────────┐     ┌────────────────────┐  │
│  │  Zuul    │────▶│  Eureka      │────▶│  ML Service A      │  │
│  │  Gateway │     │  (Discovery) │     │  (Recommendations) │  │
│  └──────────┘     └──────────────┘     └────────────────────┘  │
│       │                                          │               │
│       │           ┌──────────────┐     ┌────────────────────┐  │
│       └──────────▶│  Ribbon      │────▶│  ML Service B      │  │
│                   │  (Load Bal.) │     │  (Artwork Select)  │  │
│                   └──────────────┘     └────────────────────┘  │
│                                                                   │
│  Observability: Atlas (metrics) + Mantis (streaming analytics)   │
└─────────────────────────────────────────────────────────────────┘
```

### gRPC for Internal ML Communication

Netflix uses gRPC between ML services for:
- Model ensemble coordination (ranking service calls multiple scoring models)
- Feature retrieval from their online feature store
- A/B test assignment propagation

**Real gRPC service definition (simplified from their architecture):**

```protobuf
syntax = "proto3";

service RecommendationService {
  // Synchronous: Get personalized recommendations for homepage
  rpc GetRecommendations(RecommendationRequest) returns (RecommendationResponse);
  
  // Server streaming: Stream artwork selections as models complete
  rpc StreamArtworkSelections(ArtworkRequest) returns (stream ArtworkResponse);
  
  // Bidirectional: Real-time session personalization
  rpc PersonalizeSession(stream UserEvent) returns (stream PersonalizationUpdate);
}

message RecommendationRequest {
  string member_id = 1;
  string device_type = 2;  // Affects model selection (TV vs mobile)
  int32 num_rows = 3;
  int32 items_per_row = 4;
  map<string, string> context = 5;  // Time of day, recent watches, etc.
  string experiment_allocation = 6;  // A/B test bucket
}

message RecommendationResponse {
  repeated Row rows = 1;
  string model_version = 2;
  int64 latency_ms = 3;
  string experiment_id = 4;
}
```

### Async Patterns: Event-Driven ML Pipeline

Netflix's recommendation system uses async patterns extensively:

```
User watches show → Kafka event
    → Consumer 1: Update user embedding (async, <5min SLA)
    → Consumer 2: Update "trending" features (async, <1min SLA)
    → Consumer 3: Trigger re-ranking for active sessions (near real-time, <10s SLA)
    → Consumer 4: Update training data store (async, <1hr SLA)
```

**Key design decisions:**
- Kafka topic per event type (not per service) - allows independent consumer evolution
- Schema registry (Avro) enforces contract between producers and consumers
- Dead letter queues for ML pipeline failures (don't lose training data)
- Exactly-once semantics for feature computation (prevents feature store corruption)

### Real Latency Budgets at Netflix

```
Total page load budget: 400ms

Breakdown:
├── CDN/Network: 80ms
├── API Gateway (Zuul): 10ms
├── A/B Test Assignment: 5ms
├── Feature Retrieval: 30ms (p99)
│   ├── User features from Cassandra: 15ms
│   ├── Item features from EVCache: 5ms
│   └── Context features computed: 10ms
├── Model Inference: 50ms (p99)
│   ├── Candidate generation (ANN): 15ms
│   ├── Ranking model: 25ms
│   └── Business rules post-processing: 10ms
├── Response serialization: 5ms
└── Buffer: 220ms (for tail latency, retries, etc.)
```

---

## 2. How Uber Handles API Gateway for ML Services

### Michelangelo Gateway Architecture

Uber's ML platform (Michelangelo) serves 4000+ models across ride pricing, ETA prediction, fraud detection, and driver matching.

**API Gateway Design:**

```
┌─────────────────────────────────────────────────────────────┐
│                  Uber ML API Gateway                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Protocol Translation                               │
│  ├── REST → gRPC conversion for legacy clients              │
│  ├── GraphQL federation for mobile clients                   │
│  └── Raw gRPC for internal high-performance paths           │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Traffic Management                                 │
│  ├── Rate limiting (per-model, per-client, per-region)      │
│  ├── Request prioritization (ride pricing > analytics)      │
│  ├── Load shedding under pressure (drop low-priority first) │
│  └── Canary routing (send 1% to new model version)          │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: ML-Specific Logic                                  │
│  ├── Feature hydration (attach features to bare requests)   │
│  ├── Model routing (A/B test → correct model version)       │
│  ├── Ensemble orchestration (fan-out to multiple models)    │
│  ├── Response caching (same features → same prediction)     │
│  └── Fallback logic (if model fails → use last prediction)  │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Observability                                      │
│  ├── Prediction logging (for retraining)                    │
│  ├── Latency tracking (per-model percentiles)               │
│  ├── Feature drift monitoring                                │
│  └── Business metric correlation                             │
└─────────────────────────────────────────────────────────────┘
```

**Key patterns from Uber's gateway:**

1. **Request prioritization:** During surge, ride pricing predictions (safety-critical) get priority over food delivery ETA (best-effort). Implemented via weighted queues.

2. **Prediction caching:** For ETA models, same (origin, destination, time_bucket) returns cached prediction. Cache hit rate: ~35%, saving millions of inference calls daily.

3. **Shadow traffic:** New model versions receive shadow traffic (real requests, responses discarded) for 48 hours before receiving live traffic. Gateway handles duplication.

4. **Circuit breaker per model:**
```python
# Uber's per-model circuit breaker configuration
circuit_breaker_config = {
    "ride_pricing_v3": {
        "failure_threshold": 5,        # 5 failures in window
        "window_seconds": 30,          # 30 second window  
        "recovery_timeout": 60,        # Try again after 60s
        "fallback": "ride_pricing_v2", # Fall back to previous version
    },
    "eta_prediction_v7": {
        "failure_threshold": 10,       # More lenient (not safety-critical)
        "window_seconds": 60,
        "recovery_timeout": 30,
        "fallback": "historical_average",  # Simple heuristic fallback
    }
}
```

---

## 3. Docker/Kubernetes Patterns for AI Workloads at Scale

### Pattern 1: GPU Scheduling at Scale (Used by: Anyscale, Modal, RunPod)

**The challenge:** GPUs are expensive ($3/hr for A100). You can't let them sit idle, but ML workloads are bursty.

**Solution architecture (based on patterns from Anyscale/Ray):**

```yaml
# Kubernetes node pools for ML workloads
apiVersion: v1
kind: NodePool
metadata:
  name: gpu-inference-pool
spec:
  machineType: a2-highgpu-1g  # 1x A100 40GB
  autoscaling:
    minNodes: 2      # Always-on for latency-sensitive models
    maxNodes: 20     # Scale up for batch inference
  taints:
    - key: nvidia.com/gpu
      effect: NoSchedule  # Only GPU workloads land here
  labels:
    workload-type: inference
---
apiVersion: v1
kind: NodePool
metadata:
  name: gpu-training-pool
spec:
  machineType: a2-ultragpu-8g  # 8x A100 80GB
  autoscaling:
    minNodes: 0      # Scale to zero when no training jobs
    maxNodes: 10     # Max for parallel training
  taints:
    - key: nvidia.com/gpu
      effect: NoSchedule
  labels:
    workload-type: training
    preemptible: "true"  # Use spot instances for training (70% cheaper)
```

### Pattern 2: Model Serving with Sidecar Pattern (Production pattern from LinkedIn)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recommendation-model-v3
spec:
  replicas: 6
  template:
    spec:
      containers:
        # Main container: Model inference
        - name: model-server
          image: tritonserver:23.10
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: "16Gi"
            requests:
              nvidia.com/gpu: 1
              memory: "12Gi"
          ports:
            - containerPort: 8001  # gRPC
            - containerPort: 8002  # Metrics
          readinessProbe:
            httpGet:
              path: /v2/health/ready
              port: 8000
            initialDelaySeconds: 30  # Model loading takes time
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /v2/health/live
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 30
            failureThreshold: 3
            
        # Sidecar 1: Feature retrieval
        - name: feature-fetcher
          image: internal/feature-client:1.2
          resources:
            limits:
              memory: "2Gi"
              cpu: "1"
          env:
            - name: FEATURE_STORE_ENDPOINT
              value: "feature-store.ml-platform.svc.cluster.local:6379"
            - name: CACHE_TTL_SECONDS
              value: "300"
              
        # Sidecar 2: Prediction logger (async, non-blocking)
        - name: prediction-logger
          image: internal/pred-logger:2.0
          resources:
            limits:
              memory: "512Mi"
              cpu: "0.5"
          env:
            - name: KAFKA_BROKERS
              value: "kafka.data-platform.svc.cluster.local:9092"
            - name: TOPIC
              value: "ml.predictions.recommendations"
              
      # Model artifacts from S3/GCS
      initContainers:
        - name: model-downloader
          image: internal/model-fetcher:1.0
          env:
            - name: MODEL_URI
              value: "s3://ml-models/recommendations/v3/model.plan"
            - name: DEST_PATH
              value: "/models/recommendations/1/"
          volumeMounts:
            - name: model-store
              mountPath: /models
```

### Pattern 3: Autoscaling ML Services Based on Queue Depth (DoorDash pattern)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: document-processor-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: document-processor
  minReplicas: 2
  maxReplicas: 50
  metrics:
    # Scale based on SQS queue depth (not CPU!)
    - type: External
      external:
        metric:
          name: sqs_queue_messages_visible
          selector:
            matchLabels:
              queue: document-processing
        target:
          type: AverageValue
          averageValue: "5"  # 5 messages per pod
    # Also consider GPU utilization
    - type: Pods
      pods:
        metric:
          name: gpu_utilization
        target:
          type: AverageValue
          averageValue: "70"  # Scale up if GPUs > 70% utilized
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60   # React fast to queue buildup
      policies:
        - type: Pods
          value: 10
          periodSeconds: 60  # Add up to 10 pods per minute
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min before scaling down (GPU startup is slow)
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60  # Remove max 2 pods per minute
```

---

## 4. Case Study: Production-Ready AI Service with Proper Resilience

### Scenario: Building a Document Analysis Service (Insurance Company)

This service processes insurance claims documents using LLMs. Requirements:
- Process 10,000 documents/day
- Extract: claim amount, incident date, policy number, damage description
- SLA: 95% of documents processed within 5 minutes
- Accuracy: 98%+ on structured field extraction

**Full production architecture:**

```python
import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx
from circuitbreaker import circuit
from prometheus_client import Counter, Histogram, Gauge
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
import structlog

logger = structlog.get_logger()

# --- Metrics ---
REQUESTS_TOTAL = Counter('doc_analysis_requests_total', 'Total requests', ['status'])
LATENCY = Histogram('doc_analysis_latency_seconds', 'Processing latency',
                    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120])
LLM_CALLS = Counter('llm_api_calls_total', 'LLM API calls', ['provider', 'model', 'status'])
QUEUE_DEPTH = Gauge('doc_analysis_queue_depth', 'Current queue depth')
CIRCUIT_STATE = Gauge('circuit_breaker_state', 'Circuit breaker state', ['service'])


class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_PERMANENT = "failed_permanent"


@dataclass
class DocumentResult:
    document_id: str
    claim_amount: Optional[float]
    incident_date: Optional[str]
    policy_number: Optional[str]
    damage_description: Optional[str]
    confidence_scores: dict
    processing_time_ms: int
    model_used: str
    status: ProcessingStatus


class LLMClient:
    """Production LLM client with circuit breaker, retries, and fallback."""
    
    def __init__(self):
        self.primary_client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        self.fallback_client = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10)
        )
        self.cache = {}  # In production: Redis
    
    def _cache_key(self, prompt: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()
    
    @circuit(failure_threshold=5, recovery_timeout=60, expected_exception=httpx.HTTPStatusError)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, "warning")
    )
    async def call_primary(self, prompt: str, model: str = "gpt-4o") -> dict:
        """Call OpenAI with circuit breaker and retries."""
        # Check cache first
        cache_key = self._cache_key(prompt, model)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        response = await self.primary_client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,  # Deterministic for extraction
                "response_format": {"type": "json_object"}
            },
            headers={"Authorization": f"Bearer {self._get_api_key()}"}
        )
        response.raise_for_status()
        
        result = response.json()
        LLM_CALLS.labels(provider="openai", model=model, status="success").inc()
        
        # Cache successful results
        self.cache[cache_key] = result
        return result
    
    async def call_with_fallback(self, prompt: str) -> dict:
        """Try primary, fall back to secondary provider."""
        try:
            return await self.call_primary(prompt)
        except Exception as primary_error:
            logger.warning("primary_llm_failed", error=str(primary_error))
            LLM_CALLS.labels(provider="openai", model="gpt-4o", status="circuit_open").inc()
            
            # Fallback to Anthropic
            try:
                return await self._call_fallback(prompt)
            except Exception as fallback_error:
                logger.error("all_llm_providers_failed",
                           primary_error=str(primary_error),
                           fallback_error=str(fallback_error))
                raise
    
    async def _call_fallback(self, prompt: str) -> dict:
        """Fallback to Anthropic Claude."""
        response = await self.fallback_client.post(
            "/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            },
            headers={
                "x-api-key": self._get_fallback_key(),
                "anthropic-version": "2023-06-01"
            }
        )
        response.raise_for_status()
        LLM_CALLS.labels(provider="anthropic", model="claude-sonnet", status="success").inc()
        return response.json()


class DocumentProcessor:
    """Main processing pipeline with timeout, validation, and graceful degradation."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.max_document_size = 100_000  # 100KB max
        self.processing_timeout = 120  # 2 minutes max per document
    
    async def process_document(self, document_id: str, content: str) -> DocumentResult:
        """Process a single document with full production error handling."""
        start_time = time.time()
        
        # Input validation
        if len(content) > self.max_document_size:
            logger.warning("document_too_large", doc_id=document_id, size=len(content))
            content = content[:self.max_document_size]  # Truncate, don't fail
        
        if not content.strip():
            return DocumentResult(
                document_id=document_id,
                claim_amount=None, incident_date=None,
                policy_number=None, damage_description=None,
                confidence_scores={}, processing_time_ms=0,
                model_used="none", status=ProcessingStatus.FAILED_PERMANENT
            )
        
        try:
            # Timeout wrapper for entire processing
            result = await asyncio.wait_for(
                self._extract_fields(document_id, content),
                timeout=self.processing_timeout
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            LATENCY.observe(elapsed_ms / 1000)
            REQUESTS_TOTAL.labels(status="success").inc()
            
            result.processing_time_ms = elapsed_ms
            return result
            
        except asyncio.TimeoutError:
            logger.error("processing_timeout", doc_id=document_id)
            REQUESTS_TOTAL.labels(status="timeout").inc()
            return DocumentResult(
                document_id=document_id,
                claim_amount=None, incident_date=None,
                policy_number=None, damage_description=None,
                confidence_scores={},
                processing_time_ms=int((time.time() - start_time) * 1000),
                model_used="timeout", status=ProcessingStatus.FAILED
            )
        except Exception as e:
            logger.error("processing_failed", doc_id=document_id, error=str(e))
            REQUESTS_TOTAL.labels(status="error").inc()
            return DocumentResult(
                document_id=document_id,
                claim_amount=None, incident_date=None,
                policy_number=None, damage_description=None,
                confidence_scores={},
                processing_time_ms=int((time.time() - start_time) * 1000),
                model_used="error", status=ProcessingStatus.FAILED
            )
    
    async def _extract_fields(self, document_id: str, content: str) -> DocumentResult:
        """Core extraction logic with structured output validation."""
        prompt = f"""Extract the following fields from this insurance claim document.
Return a JSON object with these exact keys:
- claim_amount: number or null
- incident_date: ISO date string or null  
- policy_number: string or null
- damage_description: brief summary string or null
- confidence: object with confidence score 0-1 for each field

Document:
{content}"""
        
        response = await self.llm.call_with_fallback(prompt)
        
        # Parse and validate response
        try:
            extracted = json.loads(response["choices"][0]["message"]["content"])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("invalid_llm_response", doc_id=document_id, error=str(e))
            # Retry with simpler prompt (graceful degradation)
            extracted = await self._simple_extraction_fallback(content)
        
        # Validate extracted fields
        claim_amount = self._validate_amount(extracted.get("claim_amount"))
        incident_date = self._validate_date(extracted.get("incident_date"))
        
        return DocumentResult(
            document_id=document_id,
            claim_amount=claim_amount,
            incident_date=incident_date,
            policy_number=extracted.get("policy_number"),
            damage_description=extracted.get("damage_description"),
            confidence_scores=extracted.get("confidence", {}),
            processing_time_ms=0,
            model_used="gpt-4o",
            status=ProcessingStatus.COMPLETED
        )
```

---

## 5. Database Patterns for AI Metadata

### The Standard Stack: Postgres + Redis + S3

Used by: Weights & Biases, MLflow, Determined AI, most ML platforms

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI Metadata Storage Pattern                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  PostgreSQL (Source of Truth)                                    │
│  ├── experiments table (id, name, created_at, config_json)      │
│  ├── runs table (id, experiment_id, status, metrics_summary)    │
│  ├── model_registry (id, name, version, stage, metadata)        │
│  ├── deployments (id, model_id, endpoint, status, traffic_pct)  │
│  └── audit_log (who changed what, when, why)                    │
│                                                                   │
│  Redis (Hot Path Cache + Real-time)                              │
│  ├── Feature store online serving (hash maps per entity)        │
│  ├── Rate limiting counters (per-model, per-client)             │
│  ├── Active experiment allocations (user → bucket mapping)      │
│  ├── Model prediction cache (input_hash → prediction)           │
│  └── Real-time metrics (sliding window counters)                │
│                                                                   │
│  S3/GCS (Large Objects)                                          │
│  ├── Model artifacts (weights, configs, tokenizers)             │
│  ├── Training datasets (Parquet files, sharded)                 │
│  ├── Prediction logs (for retraining, auditing)                 │
│  ├── Evaluation results (plots, reports, detailed metrics)      │
│  └── Feature store offline (historical feature values)          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Real schema example (based on MLflow + custom extensions):**

```sql
-- Model Registry (used by companies like Databricks, Uber)
CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    stage VARCHAR(50) DEFAULT 'development',  -- development/staging/production/archived
    
    -- Artifact location
    artifact_uri TEXT NOT NULL,  -- s3://ml-models/fraud-detector/v23/
    artifact_size_bytes BIGINT,
    
    -- Lineage
    training_run_id UUID REFERENCES runs(id),
    training_dataset_hash VARCHAR(64),  -- SHA256 of training data manifest
    parent_model_version_id UUID REFERENCES model_versions(id),
    
    -- Performance
    metrics JSONB,  -- {"accuracy": 0.94, "f1": 0.91, "latency_p99_ms": 45}
    
    -- Governance
    created_by VARCHAR(255) NOT NULL,
    approved_by VARCHAR(255),
    approved_at TIMESTAMP,
    description TEXT,
    tags JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(model_name, version)
);

-- Deployment tracking
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id UUID REFERENCES model_versions(id),
    endpoint_name VARCHAR(255) NOT NULL,
    
    -- Traffic management
    traffic_percentage INTEGER DEFAULT 0 CHECK (traffic_percentage BETWEEN 0 AND 100),
    is_shadow BOOLEAN DEFAULT false,  -- Shadow deployment (no live traffic)
    
    -- Infrastructure
    cluster VARCHAR(100),
    replicas INTEGER,
    gpu_type VARCHAR(50),
    
    -- Status
    status VARCHAR(50) DEFAULT 'deploying',
    health_check_url TEXT,
    last_health_check_at TIMESTAMP,
    
    -- Rollback
    previous_deployment_id UUID REFERENCES deployments(id),
    rollback_reason TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Prediction audit log (for regulated industries)
CREATE TABLE prediction_audit (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(255),
    model_version INTEGER,
    
    -- Request (hashed/tokenized for PII)
    input_hash VARCHAR(64),
    input_features_snapshot JSONB,  -- Feature values at prediction time
    
    -- Response
    prediction JSONB,
    confidence FLOAT,
    
    -- Context
    request_id UUID,
    user_id_hash VARCHAR(64),  -- Hashed for privacy
    timestamp TIMESTAMP DEFAULT NOW(),
    latency_ms INTEGER,
    
    -- For explainability
    feature_importances JSONB,
    explanation TEXT
) PARTITION BY RANGE (timestamp);  -- Partition monthly for performance

-- Create monthly partitions
CREATE TABLE prediction_audit_2024_01 PARTITION OF prediction_audit
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Redis patterns for AI workloads:**

```python
# Pattern 1: Feature Store Online Serving (used by Feast, Tecton)
# Store features as Redis hashes - O(1) lookup per entity

async def get_user_features(user_id: str, feature_names: list[str]) -> dict:
    """Retrieve user features from Redis. <5ms p99."""
    key = f"features:user:{user_id}"
    
    # HMGET: get multiple fields in single round-trip
    values = await redis.hmget(key, *feature_names)
    
    return {name: json.loads(val) if val else None 
            for name, val in zip(feature_names, values)}

# Pattern 2: Semantic Cache for LLM responses
# Saves 30-40% of LLM API costs at companies like Notion

async def get_cached_completion(prompt_embedding: list[float], threshold: float = 0.95):
    """Check if a semantically similar prompt was recently answered."""
    # Use Redis vector search (RediSearch module)
    results = await redis.ft("llm_cache_idx").search(
        Query(f"*=>[KNN 1 @embedding $vec AS score]")
        .return_fields("response", "score")
        .dialect(2),
        query_params={"vec": np.array(prompt_embedding).tobytes()}
    )
    
    if results.docs and float(results.docs[0].score) > threshold:
        return json.loads(results.docs[0].response)
    return None

# Pattern 3: Rate Limiting with Token Bucket (per-model)
async def check_rate_limit(client_id: str, model: str, tokens_requested: int) -> bool:
    """Token bucket rate limiter. Used by AI API providers."""
    key = f"ratelimit:{client_id}:{model}"
    
    # Lua script for atomic token bucket
    lua_script = """
    local tokens = tonumber(redis.call('get', KEYS[1]) or ARGV[1])
    local last_refill = tonumber(redis.call('get', KEYS[2]) or ARGV[3])
    local now = tonumber(ARGV[3])
    
    -- Refill tokens based on elapsed time
    local elapsed = now - last_refill
    local refill_rate = tonumber(ARGV[4])  -- tokens per second
    tokens = math.min(tonumber(ARGV[1]), tokens + elapsed * refill_rate)
    
    -- Try to consume
    local requested = tonumber(ARGV[2])
    if tokens >= requested then
        tokens = tokens - requested
        redis.call('set', KEYS[1], tokens)
        redis.call('set', KEYS[2], now)
        return 1
    end
    return 0
    """
    
    result = await redis.eval(lua_script, 2,
        f"{key}:tokens", f"{key}:last_refill",
        100000,  # max bucket size (100K tokens)
        tokens_requested,
        time.time(),
        1000  # refill rate: 1000 tokens/second
    )
    return bool(result)
```

---

## 6. Testing Patterns at AI-First Companies

### How OpenAI Tests Their API Services

Based on public information from OpenAI engineering blog posts and conference talks:

**Testing pyramid for AI services:**

```
                    ┌──────────────┐
                    │  E2E Tests   │  (5% - expensive, slow)
                    │  Real models │
                   ─┼──────────────┼─
                  │  Integration    │  (20% - mock expensive parts)
                  │  Tests          │
                 ─┼─────────────────┼─
                │  Unit Tests        │  (40% - pure logic)
                │  (no model calls)  │
               ─┼────────────────────┼─
              │  Contract Tests       │  (20% - API contracts)
              │  (schema validation)  │
             ─┼───────────────────────┼─
            │  Evaluation Suites        │  (15% - model quality)
            │  (offline benchmarks)     │
            └───────────────────────────┘
```

**Concrete testing examples:**

```python
# 1. Unit test: Token counting logic (no API calls)
def test_token_counting_with_tool_definitions():
    """Verify token counting matches tiktoken for complex messages."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather?"},
    ]
    tools = [
        {"type": "function", "function": {"name": "get_weather", "parameters": {...}}}
    ]
    
    counted = count_tokens(messages, tools, model="gpt-4o")
    expected = tiktoken_count(messages, tools, model="gpt-4o")  # Ground truth
    
    assert counted == expected, f"Token count mismatch: {counted} vs {expected}"


# 2. Contract test: Structured output schema validation
def test_structured_output_matches_schema():
    """Ensure model output conforms to declared JSON schema."""
    schema = {
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "topics": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["sentiment", "confidence", "topics"]
    }
    
    # Test with 100 diverse inputs
    for input_text in load_test_corpus("sentiment_diverse_100"):
        response = call_model_with_schema(input_text, schema)
        
        # Validate against JSON schema
        validate(instance=response, schema=schema)
        
        # Validate business rules
        assert 0 <= response["confidence"] <= 1
        assert len(response["topics"]) <= 10  # Reasonable upper bound


# 3. Integration test: Rate limiting + retry behavior
@pytest.mark.integration
async def test_rate_limit_handling():
    """Verify service handles 429s gracefully with proper backoff."""
    # Configure mock to return 429 for first 2 calls, then 200
    mock_openai.configure_responses([
        (429, {"error": "rate_limited"}, {"retry-after": "2"}),
        (429, {"error": "rate_limited"}, {"retry-after": "4"}),
        (200, {"choices": [{"message": {"content": "hello"}}]}),
    ])
    
    start = time.time()
    result = await service.complete("test prompt")
    elapsed = time.time() - start
    
    assert result.content == "hello"
    assert elapsed >= 6  # Respected retry-after headers
    assert mock_openai.call_count == 3


# 4. Evaluation suite: Model quality regression
@pytest.mark.evaluation
def test_extraction_accuracy_regression():
    """Ensure new prompt doesn't degrade extraction quality."""
    dataset = load_golden_dataset("insurance_claims_500")
    
    results = []
    for sample in dataset:
        prediction = extract_fields(sample.document)
        results.append(evaluate_extraction(prediction, sample.ground_truth))
    
    accuracy = sum(r.correct for r in results) / len(results)
    f1_score = compute_f1(results)
    
    # These thresholds are set based on previous best model
    assert accuracy >= 0.94, f"Accuracy regression: {accuracy} < 0.94"
    assert f1_score >= 0.91, f"F1 regression: {f1_score} < 0.91"
    
    # Also check per-field accuracy (catch targeted regressions)
    for field in ["claim_amount", "incident_date", "policy_number"]:
        field_acc = compute_field_accuracy(results, field)
        assert field_acc >= 0.90, f"Field {field} regression: {field_acc}"


# 5. Load test: Concurrent request handling
@pytest.mark.load
async def test_concurrent_throughput():
    """Verify service handles expected production load."""
    NUM_CONCURRENT = 100
    TOTAL_REQUESTS = 1000
    
    semaphore = asyncio.Semaphore(NUM_CONCURRENT)
    latencies = []
    errors = 0
    
    async def make_request():
        nonlocal errors
        async with semaphore:
            start = time.time()
            try:
                await service.process_document(generate_test_document())
                latencies.append(time.time() - start)
            except Exception:
                errors += 1
    
    await asyncio.gather(*[make_request() for _ in range(TOTAL_REQUESTS)])
    
    p50 = np.percentile(latencies, 50)
    p99 = np.percentile(latencies, 99)
    error_rate = errors / TOTAL_REQUESTS
    
    assert p50 < 2.0, f"p50 latency too high: {p50}s"
    assert p99 < 10.0, f"p99 latency too high: {p99}s"
    assert error_rate < 0.01, f"Error rate too high: {error_rate}"
```

---

## 7. Real CI/CD Pipeline Examples for AI Services

### GitHub Actions Pipeline (Used by: Hugging Face, LangChain, many AI startups)

```yaml
# .github/workflows/ai-service-deploy.yml
name: AI Service CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  MODEL_REGISTRY: s3://company-ml-models
  SERVICE_NAME: document-processor
  
jobs:
  # Stage 1: Fast checks (< 2 min)
  lint-and-type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff mypy
      - run: ruff check .
      - run: mypy src/ --strict

  # Stage 2: Unit tests (< 5 min)
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[test]"
      - run: pytest tests/unit/ -v --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3

  # Stage 3: Integration tests with mocked LLM (< 10 min)
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[test]"
      - run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379
          LLM_PROVIDER: mock  # Use recorded responses, not real API

  # Stage 4: Model evaluation (< 30 min, only on main)
  model-evaluation:
    if: github.ref == 'refs/heads/main'
    needs: [unit-tests, integration-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[eval]"
      - name: Run evaluation suite
        run: python -m eval.run_evaluation --dataset golden_set_v3 --output results/
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY_EVAL }}
      - name: Check quality gates
        run: python -m eval.check_gates --results results/ --thresholds config/quality_gates.yaml
      - uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: results/

  # Stage 5: Build and push container
  build:
    needs: [lint-and-type-check, unit-tests, integration-tests]
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}/${{ env.SERVICE_NAME }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # Stage 6: Deploy to staging with shadow traffic
  deploy-staging:
    if: github.ref == 'refs/heads/main'
    needs: [build, model-evaluation]
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: |
          kubectl set image deployment/$SERVICE_NAME \
            $SERVICE_NAME=ghcr.io/${{ github.repository }}/$SERVICE_NAME:${{ github.sha }} \
            --namespace=staging
      - name: Wait for rollout
        run: kubectl rollout status deployment/$SERVICE_NAME --namespace=staging --timeout=300s
      - name: Run smoke tests
        run: pytest tests/smoke/ --base-url=https://staging.api.company.com
      - name: Enable shadow traffic (10% of production traffic mirrored)
        run: |
          kubectl patch virtualservice $SERVICE_NAME --namespace=staging \
            --type=json -p='[{"op":"replace","path":"/spec/http/0/mirror","value":{"host":"'$SERVICE_NAME'-canary"}}]'

  # Stage 7: Deploy to production (manual approval + canary)
  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: [deploy-staging]
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval in GitHub
    steps:
      - uses: actions/checkout@v4
      - name: Canary deployment (5% traffic)
        run: |
          helm upgrade $SERVICE_NAME ./helm/ \
            --set image.tag=${{ github.sha }} \
            --set canary.enabled=true \
            --set canary.weight=5 \
            --namespace=production
      - name: Monitor canary (10 minutes)
        run: |
          python scripts/monitor_canary.py \
            --service=$SERVICE_NAME \
            --duration=600 \
            --error-threshold=0.01 \
            --latency-threshold-p99=5000
      - name: Promote to full traffic
        run: |
          helm upgrade $SERVICE_NAME ./helm/ \
            --set image.tag=${{ github.sha }} \
            --set canary.enabled=false \
            --namespace=production
```

### Key CI/CD Patterns Specific to AI Services

**1. Evaluation as a Gate (not just tests):**
Unlike traditional services where tests are pass/fail, AI services need statistical evaluation:
```yaml
# config/quality_gates.yaml
gates:
  - metric: extraction_accuracy
    threshold: 0.94
    comparison: gte
    dataset: golden_set_v3
  - metric: latency_p99_ms
    threshold: 5000
    comparison: lte
  - metric: cost_per_1000_requests_usd
    threshold: 12.50
    comparison: lte
  - metric: hallucination_rate
    threshold: 0.02
    comparison: lte
    dataset: hallucination_test_set
```

**2. Model artifact versioning (separate from code versioning):**
```
Code version: git SHA (deployed via container)
Model version: semantic version in model registry (deployed via model pull)
Prompt version: stored in database, hot-reloadable without redeploy

This means:
- Code deploys: standard CI/CD (container build + deploy)
- Model updates: model registry promotion (no code change needed)
- Prompt updates: database update + cache invalidation (no deploy needed)
```

**3. Rollback strategy differs from traditional services:**
```
Traditional service rollback: Deploy previous container image

AI service rollback options:
├── Code rollback: Previous container (same as traditional)
├── Model rollback: Point serving to previous model version in registry
├── Prompt rollback: Revert prompt version in database
└── Full rollback: All three simultaneously (nuclear option)

Each has different blast radius and recovery time:
- Code rollback: 2-5 minutes (container restart)
- Model rollback: 30 seconds (update model pointer)
- Prompt rollback: <5 seconds (cache invalidation)
```
