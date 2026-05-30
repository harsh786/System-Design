# Production Deployment for AI Systems

## Overview

Deploying AI systems to production is fundamentally different from deploying traditional software. AI systems have non-deterministic outputs, depend on external model providers, require specialized hardware (GPUs), need continuous evaluation, and must handle graceful degradation when models fail or produce harmful content. This module covers the complete production deployment strategy for agentic AI systems.

---

## 1. Deployment Options Comparison

### Serverless (AWS Lambda, Cloud Functions, Azure Functions)

| Aspect | Details |
|--------|---------|
| **Best for** | Low-traffic AI endpoints, event-driven pipelines, embedding generation |
| **Pros** | Zero ops, auto-scale to zero, pay-per-invocation |
| **Cons** | Cold starts (10-30s for ML models), 15min timeout, no GPU, memory limits |
| **Pattern** | API Gateway -> Lambda -> External LLM API |

```
Use when:
- Traffic is bursty and unpredictable
- You're calling managed LLM APIs (OpenAI, Anthropic)
- No local model inference needed
- Cost optimization for low-traffic services
```

### Kubernetes (EKS, GKE, AKS)

| Aspect | Details |
|--------|---------|
| **Best for** | Production agentic systems, multi-service architectures |
| **Pros** | Full control, GPU scheduling, service mesh, autoscaling |
| **Cons** | Operational complexity, requires platform team |
| **Pattern** | Ingress -> Services -> Pods (with GPU node pools) |

```
Use when:
- Running multiple AI services (orchestrator, retriever, guardrails)
- Need GPU inference (self-hosted models)
- Require fine-grained traffic control (canary, blue/green)
- Need service mesh for inter-service communication
```

### Managed LLM APIs (OpenAI, Anthropic, Google, Azure OpenAI)

| Aspect | Details |
|--------|---------|
| **Best for** | Most production deployments initially |
| **Pros** | No infra, best models, managed scaling |
| **Cons** | Vendor lock-in, rate limits, cost at scale, data privacy |
| **Pattern** | Your Service -> AI Gateway -> Provider API |

```
Use when:
- Starting production deployment
- Need best-in-class model quality
- Don't want to manage GPU infrastructure
- Can tolerate vendor dependency
```

### Self-Hosted vLLM

| Aspect | Details |
|--------|---------|
| **Best for** | High-throughput inference with open models |
| **Pros** | Full data control, no rate limits, cost-effective at scale |
| **Cons** | GPU management, model updates, optimization complexity |
| **Pattern** | Load Balancer -> vLLM Instances (GPU) -> Model Weights (S3) |

```
Use when:
- Processing >1M tokens/day
- Data sovereignty requirements
- Need custom/fine-tuned models
- Want predictable costs at scale
```

### Ray Serve

| Aspect | Details |
|--------|---------|
| **Best for** | Complex ML pipelines, multi-model serving |
| **Pros** | Dynamic batching, multi-model, Python-native |
| **Cons** | Ray cluster management, learning curve |
| **Pattern** | Ray Cluster -> Serve Deployments -> Model Replicas |

### KServe (formerly KFServing)

| Aspect | Details |
|--------|---------|
| **Best for** | Kubernetes-native model serving with auto-scaling |
| **Pros** | Scale to zero, canary rollouts, model explainability |
| **Cons** | Heavy Kubernetes dependency, Knative requirement |
| **Pattern** | InferenceService -> Predictor -> Transformer -> Explainer |

### NVIDIA Triton Inference Server

| Aspect | Details |
|--------|---------|
| **Best for** | High-performance multi-framework inference |
| **Pros** | Dynamic batching, concurrent models, model analyzer |
| **Cons** | NVIDIA ecosystem lock-in, complexity |
| **Pattern** | Triton Server -> Model Repository -> Ensemble Pipelines |

### Hybrid Architecture (Recommended for Production)

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID DEPLOYMENT                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Managed APIs (OpenAI/Anthropic)                            │
│  └── Primary LLM inference (GPT-4, Claude)                  │
│  └── Fallback chain across providers                        │
│                                                              │
│  Kubernetes                                                  │
│  └── Agent orchestrator (CPU)                               │
│  └── Retrieval service (CPU)                                │
│  └── Guardrail service (CPU or GPU)                         │
│  └── Vector DB (StatefulSet)                                │
│  └── AI Gateway (CPU)                                       │
│                                                              │
│  Self-Hosted vLLM (GPU nodes)                               │
│  └── Embedding models                                       │
│  └── Small classification models                            │
│  └── Fine-tuned domain models                               │
│                                                              │
│  Serverless                                                  │
│  └── Document processing pipeline                           │
│  └── Async evaluation jobs                                  │
│  └── Webhook handlers                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Production System Components

### Complete Architecture

```
User Request
    │
    ▼
┌──────────────┐     ┌──────────────┐
│  API Gateway │────▶│   Auth/Rate  │
│  (Kong/AWS)  │     │   Limiter    │
└──────────────┘     └──────────────┘
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  AI Gateway  │────▶│   Model      │────▶│  Guardrail   │
│  (routing)   │     │   Providers  │     │   Service    │
└──────────────┘     └──────────────┘     └──────────────┘
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Agent     │────▶│  Retrieval   │────▶│  Vector DB   │
│ Orchestrator │     │   Service    │     │  (Qdrant)    │
└──────────────┘     └──────────────┘     └──────────────┘
    │                                          │
    ▼                                          ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Tool      │     │  Metadata    │     │  Document    │
│   Service    │     │     DB       │     │   Storage    │
└──────────────┘     └──────────────┘     └──────────────┘
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ MCP Servers  │     │  Eval        │     │ Observability│
│              │     │  Service     │     │  Pipeline    │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Component Details

#### API Gateway
- **Purpose**: Single entry point, TLS termination, rate limiting, request routing
- **Technology**: Kong, AWS API Gateway, Envoy, Traefik
- **Responsibilities**:
  - TLS termination
  - Rate limiting (per-user, per-tier)
  - Request/response transformation
  - API versioning
  - Request ID injection for tracing

#### Authentication & Authorization
- **Purpose**: Verify identity, enforce permissions
- **Technology**: Auth0, Keycloak, AWS Cognito
- **AI-Specific Concerns**:
  - Per-model access control (who can use GPT-4 vs GPT-3.5)
  - Token budget enforcement per user/org
  - Tool access control (which tools an agent can use)
  - Data access scoping for RAG

#### AI Gateway
- **Purpose**: Intelligent routing to model providers with fallback, caching, and cost control
- **Technology**: LiteLLM, Portkey, custom
- **Responsibilities**:
  - Provider routing (OpenAI -> Anthropic -> Azure OpenAI)
  - Automatic failover on provider outage
  - Response caching (semantic dedup)
  - Cost tracking per request
  - Token counting and budget enforcement
  - Model version pinning
  - Request/response logging

#### Agent Orchestrator
- **Purpose**: Manages agent execution loops, tool calls, memory
- **Technology**: LangGraph, custom orchestrator
- **Responsibilities**:
  - Agent state management
  - Tool call dispatching
  - Conversation memory (short-term)
  - Execution timeout enforcement
  - Max iterations guard
  - Streaming response assembly

#### Retrieval Service
- **Purpose**: Manages RAG pipeline - query processing, retrieval, reranking
- **Technology**: Custom service with embedding models
- **Responsibilities**:
  - Query understanding and expansion
  - Hybrid search (dense + sparse)
  - Reranking retrieved documents
  - Citation extraction
  - Context window optimization
  - Document freshness management

#### Vector Database
- **Purpose**: Store and retrieve document embeddings
- **Technology**: Qdrant, Pinecone, Weaviate, Milvus, pgvector
- **Deployment**: StatefulSet with persistent volumes
- **Concerns**:
  - Replication for HA
  - Backup and restore
  - Index optimization
  - Collection management

#### Metadata Database
- **Purpose**: Store conversations, user preferences, eval results, audit logs
- **Technology**: PostgreSQL, MongoDB
- **Stores**:
  - Conversation history
  - User preferences and context
  - Eval results and metrics
  - Prompt versions and A/B test configs
  - Feedback data

#### Tool Service
- **Purpose**: Secure execution of agent tools
- **Technology**: Custom service with sandboxing
- **Responsibilities**:
  - Tool registration and discovery
  - Input validation and sanitization
  - Execution sandboxing
  - Output formatting
  - Timeout enforcement
  - Audit logging

#### MCP Servers
- **Purpose**: Standardized tool interface for agents
- **Technology**: Model Context Protocol servers
- **Deployment**: Sidecar or standalone services
- **Concerns**:
  - Server lifecycle management
  - Connection pooling
  - Schema validation
  - Error handling

#### Guardrail Service
- **Purpose**: Input/output safety filtering
- **Technology**: Custom classifiers, LlamaGuard, OpenAI Moderation
- **Checks**:
  - PII detection and redaction
  - Toxicity/harmful content filtering
  - Prompt injection detection
  - Output hallucination detection
  - Policy compliance verification
  - Topic boundary enforcement

#### Eval Service
- **Purpose**: Continuous evaluation of system quality
- **Technology**: Custom eval framework
- **Responsibilities**:
  - Golden dataset evaluation on deploy
  - Online evaluation (LLM-as-judge)
  - Drift detection
  - A/B test analysis
  - Regression detection

#### Observability Pipeline
- **Purpose**: Full visibility into AI system behavior
- **Technology**: OpenTelemetry, Langfuse, LangSmith
- **Collects**:
  - Traces (full request lifecycle)
  - Metrics (latency, tokens, cost, quality scores)
  - Logs (structured, with trace correlation)
  - AI-specific: prompt/response pairs, tool calls, retrieval results

#### Feedback System
- **Purpose**: Collect user signals for improvement
- **Technology**: Custom service
- **Signals**:
  - Explicit feedback (thumbs up/down, ratings)
  - Implicit feedback (copy, share, regenerate)
  - Correction data
  - Escalation to human

#### Human Review Queue
- **Purpose**: Route uncertain/high-risk responses for human review
- **Technology**: Custom UI + queue (SQS/Redis)
- **Triggers**:
  - Low confidence scores
  - High-risk domains (medical, legal, financial)
  - Guardrail edge cases
  - User escalation requests

---

## 3. Kubernetes Patterns for AI

### StatefulSets for Vector Databases

Vector databases require stable network identities and persistent storage:

```yaml
# Pattern: StatefulSet with anti-affinity and topology spread
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
spec:
  serviceName: qdrant-headless
  replicas: 3
  template:
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                app: qdrant
            topologyKey: kubernetes.io/hostname
      containers:
      - name: qdrant
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
  volumeClaimTemplates:
  - metadata:
      name: qdrant-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: gp3
      resources:
        requests:
          storage: 100Gi
```

### HPA for API Services

```yaml
# Pattern: HPA with custom metrics (requests per second + latency)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-orchestrator-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-orchestrator
  minReplicas: 3
  maxReplicas: 50
  metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"
  - type: Pods
    pods:
      metric:
        name: p95_latency_ms
      target:
        type: AverageValue
        averageValue: "2000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### GPU Node Pools

```yaml
# Pattern: GPU node pool with taints for AI inference
apiVersion: v1
kind: Node
metadata:
  labels:
    node-type: gpu-inference
    gpu-type: a100
spec:
  taints:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule

---
# Pod that tolerates GPU taint
apiVersion: v1
kind: Pod
spec:
  tolerations:
  - key: nvidia.com/gpu
    operator: Equal
    value: "true"
    effect: NoSchedule
  nodeSelector:
    gpu-type: a100
  containers:
  - name: vllm
    resources:
      limits:
        nvidia.com/gpu: 1
```

---

## 4. Container Design for AI Services

### Multi-Stage Build Pattern

```dockerfile
# Stage 1: Dependencies
FROM python:3.11-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Application
FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY src/ ./src/
COPY prompts/ ./prompts/

# Non-root user
RUN useradd -m -r appuser && chown -R appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Key Principles for AI Containers

1. **Separate model weights from code** - Mount models via PVC or download at startup
2. **Layer caching** - Put rarely-changing deps first (torch, transformers)
3. **Slim images** - Use distroless or slim base images
4. **No secrets in images** - Use Kubernetes secrets or Vault
5. **Prompt versioning** - Mount prompts via ConfigMap for hot-reload
6. **GPU drivers** - Use NVIDIA base images for GPU workloads

---

## 5. Blue/Green and Canary Deployment Strategies

### Blue/Green for AI Systems

```
┌─────────────────────────────────────────────┐
│              Load Balancer                    │
│         (100% -> Blue OR Green)              │
└─────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│   BLUE (v1.2)   │    │  GREEN (v1.3)   │
│                  │    │                  │
│ - Orchestrator   │    │ - Orchestrator   │
│ - Prompt v5      │    │ - Prompt v6      │
│ - Retriever v2   │    │ - Retriever v2   │
│ - Model: GPT-4   │    │ - Model: GPT-4o  │
└─────────────────┘    └─────────────────┘
```

**When to use**: Major model changes, prompt rewrites, retriever upgrades

### Canary Deployment for AI

```
Phase 1: 1% traffic  → Monitor quality metrics for 1 hour
Phase 2: 5% traffic  → Monitor for 2 hours
Phase 3: 25% traffic → Monitor for 4 hours  
Phase 4: 100% traffic → Full rollout

Rollback trigger:
- Quality score drops >5% from baseline
- Latency p95 increases >50%
- Error rate increases >1%
- Guardrail trigger rate increases >2x
- User feedback score drops >10%
```

### Shadow Deployment (Dark Launch)

```
All traffic → Production (serves response)
           → Shadow (discards response, logs for comparison)

Use for:
- Testing new models without user impact
- Comparing prompt versions
- Validating retriever changes
```

---

## 6. Rollback Strategies for AI

### Prompt Rollback

```python
# Prompts are versioned in ConfigMap or database
# Rollback = update ConfigMap to previous version

# Prompt version history:
# v6 (current) - "You are a helpful assistant..."  [REGRESSION DETECTED]
# v5 (previous) - "You are an AI assistant..."     [ROLLBACK TARGET]
# v4 - "You are a knowledgeable..."

# Rollback command:
# kubectl set configmap prompts --from-file=system_prompt=prompts/v5/system.txt
# Pods pick up new ConfigMap via volume mount (no restart needed with inotify)
```

### Model Rollback

```python
# AI Gateway maintains model routing config
# Rollback = change routing weight back to previous model

# Before: {"model": "gpt-4o-2024-08-06", "fallback": "gpt-4-0613"}
# After:  {"model": "gpt-4-0613", "fallback": "claude-3-sonnet"}  # Rolled back
```

### Retriever Rollback

```python
# Vector DB collections are versioned
# Rollback = point retrieval service to previous collection

# Before: retriever.collection = "docs_v3_2024_01"
# After:  retriever.collection = "docs_v2_2023_12"  # Rolled back

# Keep previous collection alive for 7 days after new deployment
```

### Composite Rollback

AI systems often need coordinated rollback across multiple components:

```
Deployment Bundle v2.3:
  - Prompt: v6
  - Model: gpt-4o
  - Retriever collection: docs_v3
  - Guardrails config: v4
  
Rollback to Bundle v2.2:
  - Prompt: v5
  - Model: gpt-4
  - Retriever collection: docs_v2
  - Guardrails config: v3
```

---

## 7. Infrastructure as Code Patterns

### Module Structure

```
terraform/
├── modules/
│   ├── networking/        # VPC, subnets, security groups
│   ├── eks-cluster/       # EKS with GPU node groups
│   ├── vector-db/         # Qdrant/Pinecone provisioning
│   ├── cache/             # Redis/ElastiCache
│   ├── storage/           # S3 for documents
│   ├── secrets/           # AWS Secrets Manager / Vault
│   ├── monitoring/        # CloudWatch, Prometheus, Grafana
│   └── ai-gateway/        # API Gateway + WAF
├── environments/
│   ├── dev/
│   │   └── main.tf
│   ├── staging/
│   │   └── main.tf
│   └── prod/
│       └── main.tf
└── shared/
    └── backend.tf         # Remote state config
```

### Key Principles

1. **Environment parity** - Dev/staging/prod use same modules, different vars
2. **State isolation** - Separate state per environment
3. **Least privilege** - IAM roles scoped to service needs
4. **Immutable infrastructure** - Replace, don't mutate
5. **GitOps** - All infra changes via PR

---

## 8. Secret Management for AI Keys

### Secrets Hierarchy

```
┌─────────────────────────────────────────────┐
│           Secret Categories                  │
├─────────────────────────────────────────────┤
│                                              │
│  Model Provider Keys (CRITICAL)             │
│  ├── OPENAI_API_KEY                         │
│  ├── ANTHROPIC_API_KEY                      │
│  ├── AZURE_OPENAI_KEY                       │
│  └── GOOGLE_AI_KEY                          │
│                                              │
│  Infrastructure Secrets                      │
│  ├── DB_CONNECTION_STRING                   │
│  ├── REDIS_PASSWORD                         │
│  ├── VECTOR_DB_API_KEY                      │
│  └── S3_ACCESS_CREDENTIALS                  │
│                                              │
│  Service Secrets                             │
│  ├── JWT_SIGNING_KEY                        │
│  ├── WEBHOOK_SECRETS                        │
│  └── INTER_SERVICE_AUTH_TOKEN               │
│                                              │
│  Tool/MCP Secrets                            │
│  ├── GITHUB_TOKEN                           │
│  ├── JIRA_API_KEY                           │
│  ├── SLACK_BOT_TOKEN                        │
│  └── BROWSER_API_KEY                        │
│                                              │
└─────────────────────────────────────────────┘
```

### Best Practices

1. **External Secrets Operator** - Sync from Vault/AWS SM to K8s secrets
2. **Rotation** - Automate key rotation (especially LLM keys)
3. **Scoped access** - Each service only gets keys it needs
4. **Audit trail** - Log all secret access
5. **No secrets in Git** - Use sealed-secrets or external-secrets
6. **Environment-specific keys** - Different keys per environment

---

## 9. Multi-Environment Strategy

### Environment Purposes

| Environment | Purpose | Model Provider | Data |
|-------------|---------|---------------|------|
| **Dev** | Developer testing, rapid iteration | GPT-3.5 / local models | Synthetic data |
| **Staging** | Integration testing, eval runs | Same as prod (lower rate limit) | Anonymized prod data |
| **Prod** | Live traffic | GPT-4o / Claude | Real data |

### Environment Differences

```yaml
# dev.yaml
replicas: 1
model: "gpt-3.5-turbo"
vector_db: "in-memory"
eval_on_deploy: false
guardrails: "warn-only"

# staging.yaml  
replicas: 2
model: "gpt-4o"
vector_db: "qdrant-single-node"
eval_on_deploy: true
guardrails: "enforce"

# prod.yaml
replicas: 5
model: "gpt-4o"
vector_db: "qdrant-cluster-3"
eval_on_deploy: true
guardrails: "enforce"
canary_enabled: true
```

### Promotion Flow

```
Dev → (PR merge) → Staging → (eval pass + approval) → Prod
                                                         │
                                                    Canary (1%)
                                                         │
                                                    Monitor 1hr
                                                         │
                                                    Promote/Rollback
```

---

## 10. CI/CD Pipeline Design for AI Systems

### AI-Specific Pipeline Stages

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Build   │──▶│  Test    │──▶│  Eval    │──▶│  Safety  │
│  & Lint  │   │  (Unit)  │   │  (AI)    │   │  (Guard) │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                    │
┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  Deploy  │◀──│  Integ   │◀──│Container │◀───────┘
│  (Prod)  │   │  Tests   │   │  Build   │
└──────────┘   └──────────┘   └──────────┘
```

### What Makes AI CI/CD Different

1. **Eval stage** - Run golden dataset through system, check quality scores
2. **Safety stage** - Run adversarial prompts, check guardrails hold
3. **Cost estimation** - Estimate token cost of changes
4. **Prompt diff** - Show prompt changes in PR review
5. **Non-deterministic tests** - Need statistical assertions (>90% pass rate)
6. **Longer pipelines** - Eval can take 10-30 minutes
7. **Model pinning** - Ensure exact model version in deployment

### Pipeline Triggers

| Trigger | Actions |
|---------|---------|
| PR opened | Lint, unit test, eval subset (fast) |
| PR merged to main | Full eval, safety eval, deploy staging |
| Manual approval | Deploy prod (canary) |
| Prompt change | Eval only (skip build) |
| Retriever update | Retrieval eval + integration test |
| Scheduled (daily) | Full eval suite, drift detection |

---

## Summary: Production Readiness Checklist

- [ ] All services containerized with health checks
- [ ] Kubernetes manifests with resource limits
- [ ] HPA configured with AI-relevant metrics
- [ ] Canary deployment with automatic rollback
- [ ] Secrets managed externally (not in Git)
- [ ] CI/CD pipeline with eval gates
- [ ] Multi-environment parity
- [ ] Observability (traces, metrics, logs) for all AI calls
- [ ] Guardrails enforced in production
- [ ] Rollback procedures documented and tested
- [ ] Disaster recovery plan for vector DB
- [ ] Cost alerting and budget controls
- [ ] Rate limiting per user/tier
- [ ] PII handling and data retention policies
