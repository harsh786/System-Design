# Production Deployment — Real-World Examples

## Case Study: From "Works on My Laptop" to Production AI in 6 Weeks

### Company: MedScribe (Series A, 12 engineers)
**Product:** AI-powered medical note summarization from doctor-patient conversations.

#### Week 1-2: The Starting Point
The prototype was a Python script running on a developer's M2 MacBook:
```python
# What "production" looked like on day 0
import openai
client = openai.OpenAI(api_key="sk-hardcoded-key-lol")

def summarize_note(transcript: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": open("prompt.txt").read()},
                  {"role": "user", "content": transcript}],
        temperature=0.3
    )
    return response.choices[0].message.content
```

Problems:
- API key hardcoded in source
- No retry logic, no timeout
- No observability — if quality degraded, nobody knew
- Prompt stored as local file, no versioning
- No input validation (HIPAA-sensitive data flowing freely)

#### Week 2-3: Architecture Decisions

They chose this stack after evaluating tradeoffs:

| Decision | Choice | Why | Rejected Alternative |
|----------|--------|-----|---------------------|
| Orchestration | EKS (Kubernetes) | Team had K8s experience, needed GPU later | ECS (simpler but less flexible) |
| LLM Gateway | LiteLLM proxy | Multi-provider failover, cost tracking | Direct SDK calls |
| Secrets | AWS Secrets Manager + External Secrets Operator | K8s-native, auto-rotation | Vault (overkill for team size) |
| Observability | Datadog + LangSmith | LangSmith for LLM-specific tracing | OpenTelemetry (too much setup) |
| CI/CD | GitHub Actions + ArgoCD | GitOps, easy rollback | Jenkins (nobody wanted to maintain) |
| Vector DB | Pinecone | Managed, no ops burden | Self-hosted Qdrant (ops overhead) |

#### Week 3-4: Core Infrastructure

```yaml
# ArgoCD Application manifest
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: medscribe-ai
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/medscribe/platform
    targetRevision: main
    path: k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: medscribe-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

#### Week 4-5: Quality Gates & Eval Pipeline

Before any deployment, an eval suite ran against 200 golden examples:
```python
# eval/run_eval.py — runs in CI before promotion
import json
from medscribe.client import MedScribeClient
from eval.metrics import compute_medical_accuracy, compute_hallucination_rate

GOLDEN_SET = json.load(open("eval/golden_200.json"))
THRESHOLDS = {
    "medical_accuracy": 0.92,      # Must correctly capture diagnoses, meds
    "hallucination_rate": 0.02,    # Max 2% hallucinated facts
    "format_compliance": 0.95,     # Follows SOAP note structure
    "latency_p95_seconds": 8.0,   # Under 8s for 95th percentile
}

def run_evaluation(endpoint: str) -> dict:
    results = []
    for example in GOLDEN_SET:
        response = client.summarize(example["transcript"], endpoint=endpoint)
        results.append({
            "medical_accuracy": compute_medical_accuracy(response, example["expected"]),
            "hallucination_rate": compute_hallucination_rate(response, example["transcript"]),
            "format_compliance": check_soap_format(response),
            "latency": response.latency_seconds,
        })
    
    aggregated = aggregate_metrics(results)
    for metric, threshold in THRESHOLDS.items():
        if metric == "hallucination_rate":
            assert aggregated[metric] <= threshold, f"{metric}: {aggregated[metric]} > {threshold}"
        else:
            assert aggregated[metric] >= threshold, f"{metric}: {aggregated[metric]} < {threshold}"
    
    return aggregated
```

#### Week 5-6: Production Hardening

Final architecture after 6 weeks:
- **3 environments**: dev (shared, relaxed limits), staging (production-mirror), prod
- **Canary deploys**: 5% traffic → eval check → 25% → eval check → 100%
- **Circuit breaker**: Falls back to GPT-3.5-turbo summary if GPT-4 latency exceeds 15s
- **PII detection**: Pre-processing layer strips SSNs, redacts names before LLM call
- **Cost controls**: Hard cap at $500/day LLM spend, alerts at $300

**Total cost of infrastructure (month 1):** ~$4,200/month
- EKS cluster: $800
- LLM API calls: $2,500
- Pinecone: $350
- Datadog + LangSmith: $400
- Secrets Manager, S3, misc: $150

---

## Case Study: Shopify's AI Canary Releases

### Context
Shopify deploys AI-powered features (product descriptions, customer support suggestions, Sidekick) across millions of merchants. A bad deployment could generate harmful product descriptions or incorrect financial advice.

### Their Canary Strategy

```yaml
# Simplified representation of Shopify's AI canary config
canary:
  stages:
    - name: shadow
      traffic_percent: 0
      duration: 2h
      description: "Run new model in shadow mode, compare outputs"
      gates:
        - type: output_similarity
          threshold: 0.85  # New outputs should be ≥85% similar to current
          metric: semantic_similarity_score
        - type: toxicity
          threshold: 0.001  # Less than 0.1% toxic outputs
        - type: latency_regression
          max_increase_percent: 20

    - name: internal
      traffic_percent: 1
      audience: "shopify_employees_only"
      duration: 4h
      gates:
        - type: human_review
          sample_size: 50
          min_approval: 0.95
        - type: merchant_category_coverage
          min_categories: 20  # Must work across diverse merchant types

    - name: canary_small
      traffic_percent: 5
      duration: 24h
      gates:
        - type: merchant_satisfaction
          metric: thumbs_up_ratio
          min_value: 0.78
        - type: edit_rate
          description: "How often merchants edit AI output"
          max_increase_percent: 10
        - type: error_rate
          max_value: 0.005
        - type: revenue_impact
          description: "Products with AI descriptions conversion rate"
          min_change: -0.5  # No more than 0.5% conversion drop

    - name: canary_large
      traffic_percent: 25
      duration: 48h
      gates:
        - type: all_previous
        - type: cost_per_request
          max_increase_percent: 15
        - type: long_tail_quality
          description: "Quality on rare languages and edge cases"
          min_score: 0.70

    - name: full_rollout
      traffic_percent: 100
      monitoring_period: 7d
      rollback_triggers:
        - merchant_complaints_spike: 3x_baseline
        - error_rate: "> 1%"
        - cost_anomaly: "> 2x daily budget"
```

### Key Insight: AI-Specific Quality Gates

Traditional canaries check error rates and latency. Shopify's AI canaries additionally check:

1. **Output semantic drift** — Are outputs meaningfully different from before?
2. **Edit rate** — Are merchants editing AI suggestions more than before?
3. **Category fairness** — Does quality hold across merchant types (fashion, electronics, food)?
4. **Revenue proxy** — Do AI-generated descriptions still convert?

### The Rollback Decision Tree
```
Quality gate fails at any stage?
├── Shadow stage failure → Block deployment, no user impact
├── Internal stage failure → Auto-rollback, alert on-call
├── Canary small failure → Auto-rollback within 5 min, page on-call
└── Canary large failure → Auto-rollback within 2 min, page on-call + engineering lead
```

---

## Kubernetes for AI Services: GPU Scheduling & Spot Instances

### GPU Pod with Preemption Priority

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: inference-server
  labels:
    app: llm-inference
    tier: realtime
spec:
  # High priority — won't be preempted by batch jobs
  priorityClassName: realtime-inference
  
  # Tolerate GPU node taints
  tolerations:
    - key: "nvidia.com/gpu"
      operator: "Exists"
      effect: "NoSchedule"
    - key: "dedicated"
      value: "gpu-inference"
      effect: "NoSchedule"
  
  # Prefer nodes with already-cached model weights
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          preference:
            matchExpressions:
              - key: cached-model
                operator: In
                values: ["llama-3-70b"]
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: node.kubernetes.io/instance-type
                operator: In
                values: ["g5.12xlarge", "g5.48xlarge", "p4d.24xlarge"]
  
  containers:
    - name: vllm-server
      image: registry.internal/vllm-server:v0.4.2-custom
      resources:
        requests:
          cpu: "8"
          memory: "64Gi"
          nvidia.com/gpu: "4"
        limits:
          cpu: "16"
          memory: "96Gi"
          nvidia.com/gpu: "4"
      env:
        - name: MODEL_PATH
          value: "/models/llama-3-70b-instruct"
        - name: TENSOR_PARALLEL_SIZE
          value: "4"
        - name: MAX_MODEL_LEN
          value: "8192"
        - name: GPU_MEMORY_UTILIZATION
          value: "0.92"
      volumeMounts:
        - name: model-cache
          mountPath: /models
        - name: shm
          mountPath: /dev/shm
      
      # Startup takes 3-5 min for large model loading
      startupProbe:
        httpGet:
          path: /health
          port: 8000
        initialDelaySeconds: 60
        periodSeconds: 10
        failureThreshold: 30  # Allow up to 5 min startup
      
      readinessProbe:
        httpGet:
          path: /health
          port: 8000
        periodSeconds: 5
        failureThreshold: 3
      
      livenessProbe:
        httpGet:
          path: /health
          port: 8000
        periodSeconds: 15
        failureThreshold: 5
  
  volumes:
    - name: model-cache
      hostPath:
        path: /mnt/models  # EBS volume pre-populated via DaemonSet
        type: Directory
    - name: shm
      emptyDir:
        medium: Memory
        sizeLimit: "16Gi"  # Required for tensor parallelism IPC

---
# Priority classes for GPU workload tiering
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: realtime-inference
value: 1000000
globalDefault: false
description: "Real-time user-facing inference — never preempted"

---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: batch-inference
value: 100000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
description: "Batch jobs — can preempt spot workloads, preempted by realtime"

---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: spot-batch
value: 10000
globalDefault: false
preemptionPolicy: Never
description: "Spot instance batch — cheapest, can be interrupted anytime"
```

### Spot Instance Node Pool for Batch Inference (EKS)

```yaml
# Karpenter provisioner for spot GPU nodes
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
  name: gpu-spot-batch
spec:
  requirements:
    - key: karpenter.sh/capacity-type
      operator: In
      values: ["spot"]
    - key: node.kubernetes.io/instance-type
      operator: In
      values: ["g5.xlarge", "g5.2xlarge", "g5.4xlarge"]
    - key: topology.kubernetes.io/zone
      operator: In
      values: ["us-east-1a", "us-east-1b", "us-east-1c"]
  
  limits:
    resources:
      nvidia.com/gpu: "32"  # Max 32 spot GPUs at any time
  
  # Consolidation: pack batch jobs tight, release nodes fast
  consolidation:
    enabled: true
  
  # Time-to-live: don't keep idle GPU nodes
  ttlSecondsAfterEmpty: 60
  
  # Expire nodes after 24h to pick up new spot pricing
  ttlSecondsUntilExpired: 86400
  
  taints:
    - key: dedicated
      value: gpu-batch-spot
      effect: NoSchedule
  
  labels:
    workload-type: batch-inference
    cost-tier: spot
```

---

## CI/CD Pipeline: Complete GitHub Actions for AI Service

```yaml
# .github/workflows/ai-service-deploy.yml
name: AI Service Deploy Pipeline

on:
  push:
    branches: [main]
    paths:
      - 'services/ai-inference/**'
      - 'prompts/**'
      - 'eval/**'

env:
  SERVICE: ai-inference
  AWS_REGION: us-east-1
  ECR_REPO: 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-inference
  CLUSTER: prod-ai-cluster
  EVAL_ENDPOINT: https://eval.internal.company.com

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
        working-directory: services/ai-inference
      - name: Ruff lint
        run: ruff check services/ai-inference/
      - name: Mypy typecheck
        run: mypy services/ai-inference/ --strict
      - name: Prompt lint (check for injection vulnerabilities)
        run: python scripts/lint_prompts.py prompts/

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
        working-directory: services/ai-inference
      - name: Run unit tests (mocked LLM calls)
        run: pytest tests/unit/ -v --cov=src --cov-report=xml
        working-directory: services/ai-inference
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    needs: [lint-and-typecheck, unit-tests]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
        working-directory: services/ai-inference
      - name: Start dependencies (Redis, mock vector DB)
        run: docker compose -f docker-compose.test.yml up -d
      - name: Run integration tests (real LLM calls, test budget)
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY_TEST }}
          LLM_TEST_BUDGET: "5.00"  # Max $5 spend per CI run
        run: pytest tests/integration/ -v --timeout=120
        working-directory: services/ai-inference

  eval-suite:
    runs-on: ubuntu-latest
    needs: [integration-tests]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
        working-directory: services/ai-inference
      - name: Run AI evaluation suite
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY_EVAL }}
          EVAL_DATASET: eval/golden_500.jsonl
        run: |
          python eval/run_eval.py \
            --dataset $EVAL_DATASET \
            --output eval-results.json \
            --parallel 10
        working-directory: services/ai-inference
      
      - name: Check quality gates
        run: |
          python eval/check_gates.py eval-results.json \
            --min-accuracy 0.91 \
            --max-hallucination 0.03 \
            --max-latency-p95 6.0 \
            --max-cost-per-request 0.08
        working-directory: services/ai-inference
      
      - name: Compare with baseline (regression detection)
        run: |
          python eval/compare_baseline.py \
            --current eval-results.json \
            --baseline eval/baseline-main.json \
            --max-regression 0.02
        working-directory: services/ai-inference
      
      - name: Upload eval results as artifact
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: services/ai-inference/eval-results.json

  build-and-push:
    runs-on: ubuntu-latest
    needs: [eval-suite]
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}
      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2
      - name: Docker meta
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.ECR_REPO }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: services/ai-inference/
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  canary-deploy:
    runs-on: ubuntu-latest
    needs: [build-and-push]
    environment: production-canary
    steps:
      - uses: actions/checkout@v4
      - name: Deploy canary (5% traffic)
        run: |
          kubectl set image deployment/ai-inference-canary \
            ai-inference=${{ env.ECR_REPO }}:${{ github.sha }} \
            --namespace=prod
          kubectl rollout status deployment/ai-inference-canary --timeout=300s
      
      - name: Wait and monitor canary (15 minutes)
        run: |
          python scripts/monitor_canary.py \
            --duration 900 \
            --max-error-rate 0.01 \
            --max-latency-p99 10.0 \
            --min-quality-score 0.88 \
            --datadog-api-key ${{ secrets.DATADOG_API_KEY }}

  promote-to-production:
    runs-on: ubuntu-latest
    needs: [canary-deploy]
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Promote to full production
        run: |
          kubectl set image deployment/ai-inference \
            ai-inference=${{ env.ECR_REPO }}:${{ github.sha }} \
            --namespace=prod
          kubectl rollout status deployment/ai-inference --timeout=600s
      
      - name: Update baseline eval results
        run: |
          aws s3 cp s3://ml-artifacts/eval-results/${{ github.sha }}.json \
            s3://ml-artifacts/eval-baseline/current.json
      
      - name: Notify Slack
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "✓ AI Inference deployed: ${{ github.sha }}\nEval score: passed all gates\nCanary: 15min clean"
            }
```

---

## Blue/Green War Story: The 20% Quality Drop

### What Happened

**Company:** FinBot (AI financial advisor chatbot)  
**Date:** March 2024  
**Root cause:** Updated from GPT-4-0613 to GPT-4-turbo-preview without adequate eval coverage.

### Timeline

```
14:00 — Engineer updates model config: gpt-4-0613 → gpt-4-turbo-preview
14:05 — CI passes (unit tests mock LLM, integration tests have only 20 examples)
14:12 — Blue/green switch: green environment now serving 100% traffic
14:15 — Latency drops 40% (good! turbo is faster)
14:30 — No alerts firing — error rate is 0%, latency is better
15:45 — Customer support tickets start arriving: "Bot gave me wrong tax advice"
16:00 — 12 tickets in 45 minutes (normally 2/day)
16:15 — Engineer investigates, finds GPT-4-turbo is:
         - Less precise on numerical calculations
         - More likely to hedge instead of giving specific advice
         - Occasionally hallucinating tax brackets
16:20 — Manual rollback to blue environment (old model)
16:22 — Traffic back on gpt-4-0613
17:00 — Post-mortem begins
```

### What Went Wrong

1. **Eval suite was too small** — 20 golden examples didn't cover financial calculation edge cases
2. **No AI-specific quality monitoring** — Only checked error rates and latency, not output quality
3. **Blue/green was all-or-nothing** — 100% switch instead of gradual canary
4. **No automated quality scoring in production** — Relied on customer complaints as the feedback signal

### What They Built After

```python
# Real-time quality monitor deployed post-incident
class ProductionQualityMonitor:
    """Samples 5% of production traffic and runs quality checks."""
    
    def __init__(self):
        self.judge_model = "gpt-4o"  # Use a different model as judge
        self.alert_threshold = 0.85
        self.rollback_threshold = 0.80
        self.window_size = 100  # Rolling window of last 100 samples
        self.scores = deque(maxlen=self.window_size)
    
    async def evaluate_sample(self, request: dict, response: str):
        """Run on 5% of production traffic."""
        score = await self.judge_quality(request, response)
        self.scores.append(score)
        
        avg_score = sum(self.scores) / len(self.scores)
        
        if avg_score < self.rollback_threshold and len(self.scores) >= 50:
            await self.trigger_automatic_rollback(avg_score)
        elif avg_score < self.alert_threshold:
            await self.alert_oncall(avg_score)
    
    async def judge_quality(self, request: dict, response: str) -> float:
        """Use LLM-as-judge for real-time quality scoring."""
        judgment = await self.llm.complete(
            model=self.judge_model,
            messages=[{
                "role": "system",
                "content": """Rate this financial advice response 0-1:
                - 1.0: Accurate, specific, actionable
                - 0.7: Mostly correct but vague
                - 0.4: Contains errors or misleading info
                - 0.0: Dangerous misinformation"""
            }, {
                "role": "user",
                "content": f"User asked: {request['query']}\nBot replied: {response}"
            }]
        )
        return float(judgment)
```

### Outcome
After implementing automated quality monitoring, their next model upgrade (to GPT-4o) was caught by the quality gate during canary (score dropped from 0.91 to 0.84 on financial precision). They tuned the system prompt, re-ran eval, and deployed safely 3 days later.

---

## Container Patterns: Multi-Stage Docker Builds for AI

```dockerfile
# Dockerfile for AI inference service with model weight caching
# Strategy: Separate model weights into their own layer for fast rebuilds

# ============================================================
# Stage 1: Base dependencies (changes rarely)
# ============================================================
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached unless requirements change)
COPY requirements.lock requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

# ============================================================
# Stage 2: Model weights (changes only on model updates)
# ============================================================
FROM base AS model-fetcher

# Download model weights — this layer is ~4GB but cached independently
ARG MODEL_VERSION=v2.3
ARG MODEL_REGISTRY=s3://company-models/production

RUN pip install awscli
# Using build-time secrets for AWS credentials
RUN --mount=type=secret,id=aws_credentials,target=/root/.aws/credentials \
    aws s3 cp ${MODEL_REGISTRY}/${MODEL_VERSION}/adapter_weights.safetensors /models/ && \
    aws s3 cp ${MODEL_REGISTRY}/${MODEL_VERSION}/tokenizer/ /models/tokenizer/ --recursive

# ============================================================
# Stage 3: Application code (changes most frequently)
# ============================================================
FROM base AS production

# Copy model weights from fetcher stage
COPY --from=model-fetcher /models /models

# Copy application code (this layer rebuilds on every code change — fast!)
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY config/ /app/config/

# Non-root user for security
RUN useradd -m -u 1000 appuser
USER appuser

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENV MODEL_PATH=/models
ENV PROMPT_DIR=/app/prompts
ENV PORT=8080

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

**Layer caching strategy:**
```
Layer 1: OS + system deps     (~200MB, changes monthly)
Layer 2: Python dependencies  (~800MB, changes weekly)
Layer 3: Model weights        (~4GB, changes per model update)
Layer 4: Application code     (~5MB, changes per commit)
```

Result: Most deployments rebuild only Layer 4 → **build time drops from 12 min to 45 seconds**.

---

## Infrastructure as Code: Terraform for RAG System on AWS

```hcl
# modules/rag-platform/main.tf
# Deploys: EKS + Qdrant (self-hosted) + S3 (documents) + ElastiCache (Redis) + OpenSearch

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
    helm = { source = "hashicorp/helm", version = "~> 2.12" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.25" }
  }
}

# --- VPC ---
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.4.0"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}

# --- EKS Cluster ---
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.21.0"

  cluster_name    = "${var.project_name}-${var.environment}"
  cluster_version = "1.28"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  cluster_endpoint_public_access = var.environment != "production"

  eks_managed_node_groups = {
    # General workloads (API servers, Redis clients, etc.)
    general = {
      instance_types = ["m6i.xlarge"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3
      labels = { workload = "general" }
    }

    # Qdrant vector database nodes (memory-optimized)
    vectordb = {
      instance_types = ["r6i.2xlarge"]  # 64GB RAM for vector indices
      min_size       = 3
      max_size       = 6
      desired_size   = 3
      labels = { workload = "vectordb" }
      taints = [{
        key    = "dedicated"
        value  = "vectordb"
        effect = "NO_SCHEDULE"
      }]
    }

    # GPU nodes for embedding generation
    gpu = {
      instance_types = ["g5.xlarge"]
      min_size       = 0
      max_size       = 4
      desired_size   = 1
      ami_type       = "AL2_x86_64_GPU"
      labels = { workload = "gpu", "nvidia.com/gpu" = "true" }
      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }
}

# --- S3: Document Storage ---
resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-documents-${var.environment}"
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    id     = "archive-old-versions"
    status = "Enabled"
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }
  }
}

# --- ElastiCache (Redis): Caching layer ---
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.project_name}-cache"
  description          = "RAG caching layer — semantic cache + session state"
  
  node_type            = var.environment == "production" ? "cache.r6g.xlarge" : "cache.t4g.medium"
  num_cache_clusters   = var.environment == "production" ? 3 : 1
  
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  
  # For semantic cache: store embedding+response pairs
  # Average entry: 1536-dim embedding (6KB) + response (2KB) = 8KB
  # 1M cached entries ≈ 8GB
  parameter_group_name = aws_elasticache_parameter_group.redis.name
}

resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.project_name}-redis-params"
  family = "redis7"
  
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"  # Evict least recently used when full
  }
}

# --- Qdrant Vector DB (Helm) ---
resource "helm_release" "qdrant" {
  name       = "qdrant"
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  version    = "0.7.6"
  namespace  = "vectordb"
  create_namespace = true

  values = [<<-EOT
    replicaCount: 3
    
    resources:
      requests:
        memory: "32Gi"
        cpu: "4"
      limits:
        memory: "48Gi"
        cpu: "8"
    
    persistence:
      size: 100Gi
      storageClassName: gp3-encrypted
    
    tolerations:
      - key: "dedicated"
        value: "vectordb"
        effect: "NoSchedule"
    
    nodeSelector:
      workload: vectordb
    
    config:
      storage:
        performance:
          max_search_threads: 4
          max_optimization_threads: 2
      service:
        grpc_port: 6334
        enable_tls: true
    
    # Snapshot backups every 6 hours
    snapshot:
      enabled: true
      schedule: "0 */6 * * *"
      s3:
        bucket: ${aws_s3_bucket.qdrant_backups.id}
        region: ${var.region}
  EOT
  ]
}

# --- Outputs ---
output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "document_bucket" {
  value = aws_s3_bucket.documents.id
}
```

**Monthly cost estimate (production):**
| Component | Configuration | Cost/month |
|-----------|--------------|------------|
| EKS Control Plane | 1 cluster | $73 |
| General nodes | 3x m6i.xlarge | $432 |
| Vector DB nodes | 3x r6i.2xlarge | $1,440 |
| GPU nodes | 1x g5.xlarge (on-demand) | $1,210 |
| ElastiCache | 3x cache.r6g.xlarge | $1,080 |
| S3 + transfers | ~500GB stored | $50 |
| NAT Gateway | 3 AZs | $97 |
| **Total** | | **~$4,382** |

---

## Secret Management: Handling 15+ API Keys in Kubernetes

### The Problem
A typical production AI system needs:
- 3 LLM provider keys (OpenAI, Anthropic, Cohere — for failover)
- Vector DB credentials (Qdrant API key or connection string)
- Redis AUTH token
- 4 tool API keys (Serper for search, Tavily, GitHub, Jira)
- Database credentials (PostgreSQL for metadata)
- Monitoring (Datadog, LangSmith)
- Cloud provider (AWS credentials for S3 model access)
- Webhook secrets (Slack, PagerDuty)

### Solution: External Secrets Operator + AWS Secrets Manager

```yaml
# 1. Install External Secrets Operator
# helm install external-secrets external-secrets/external-secrets -n external-secrets

# 2. ClusterSecretStore pointing to AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets

---
# 3. ExternalSecret that syncs all AI service secrets
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ai-service-secrets
  namespace: prod
spec:
  refreshInterval: 5m  # Re-sync every 5 minutes (catches rotations)
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  
  target:
    name: ai-service-secrets
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        # Template allows combining multiple AWS secrets into one K8s secret
        config.yaml: |
          llm:
            openai_key: "{{ .openai_key }}"
            anthropic_key: "{{ .anthropic_key }}"
            cohere_key: "{{ .cohere_key }}"
          vectordb:
            qdrant_api_key: "{{ .qdrant_key }}"
            qdrant_url: "{{ .qdrant_url }}"
          cache:
            redis_url: "redis://:{{ .redis_auth }}@{{ .redis_host }}:6379"
          tools:
            serper_key: "{{ .serper_key }}"
            tavily_key: "{{ .tavily_key }}"
            github_token: "{{ .github_token }}"
            jira_token: "{{ .jira_token }}"
          monitoring:
            datadog_api_key: "{{ .datadog_key }}"
            langsmith_api_key: "{{ .langsmith_key }}"
          webhooks:
            slack_webhook: "{{ .slack_webhook }}"
            pagerduty_key: "{{ .pagerduty_key }}"
  
  data:
    - secretKey: openai_key
      remoteRef:
        key: prod/ai-service/llm-providers
        property: openai_api_key
    - secretKey: anthropic_key
      remoteRef:
        key: prod/ai-service/llm-providers
        property: anthropic_api_key
    - secretKey: cohere_key
      remoteRef:
        key: prod/ai-service/llm-providers
        property: cohere_api_key
    - secretKey: qdrant_key
      remoteRef:
        key: prod/ai-service/vectordb
        property: api_key
    - secretKey: qdrant_url
      remoteRef:
        key: prod/ai-service/vectordb
        property: url
    - secretKey: redis_auth
      remoteRef:
        key: prod/ai-service/redis
        property: auth_token
    - secretKey: redis_host
      remoteRef:
        key: prod/ai-service/redis
        property: host
    - secretKey: serper_key
      remoteRef:
        key: prod/ai-service/tool-keys
        property: serper
    - secretKey: tavily_key
      remoteRef:
        key: prod/ai-service/tool-keys
        property: tavily
    - secretKey: github_token
      remoteRef:
        key: prod/ai-service/tool-keys
        property: github
    - secretKey: jira_token
      remoteRef:
        key: prod/ai-service/tool-keys
        property: jira
    - secretKey: datadog_key
      remoteRef:
        key: prod/ai-service/monitoring
        property: datadog_api_key
    - secretKey: langsmith_key
      remoteRef:
        key: prod/ai-service/monitoring
        property: langsmith_api_key
    - secretKey: slack_webhook
      remoteRef:
        key: prod/ai-service/webhooks
        property: slack
    - secretKey: pagerduty_key
      remoteRef:
        key: prod/ai-service/webhooks
        property: pagerduty
```

### Key Rotation Without Downtime
```python
# Application code: watch for secret file changes (K8s updates mounted secrets)
import hashlib, time, threading, yaml

class SecretWatcher:
    def __init__(self, secret_path="/etc/secrets/config.yaml"):
        self.path = secret_path
        self.current_hash = self._hash()
        self.config = self._load()
        self._start_watcher()
    
    def _hash(self):
        return hashlib.md5(open(self.path, 'rb').read()).hexdigest()
    
    def _load(self):
        return yaml.safe_load(open(self.path))
    
    def _start_watcher(self):
        def watch():
            while True:
                time.sleep(30)
                new_hash = self._hash()
                if new_hash != self.current_hash:
                    logger.info("Secrets rotated, reloading configuration")
                    self.config = self._load()
                    self.current_hash = new_hash
                    self._reinitialize_clients()
        threading.Thread(target=watch, daemon=True).start()
```

---

## Multi-Environment Strategy

### Real Config Differences

```yaml
# config/environments/dev.yaml
environment: development
llm:
  provider: openai
  model: gpt-4o-mini          # Cheaper model for dev
  max_tokens: 1000            # Lower limits to save cost
  daily_budget: 20.00         # $20/day cap
  rate_limit: 100             # req/min across all devs

vectordb:
  provider: qdrant
  url: http://qdrant-dev.internal:6333
  collection_suffix: "_dev"   # Separate collections
  replicas: 1                 # No replication in dev

cache:
  enabled: false              # No caching — see real LLM behavior

observability:
  tracing: enabled
  log_level: DEBUG
  log_prompts: true           # Log full prompts in dev (NEVER in prod)
  sample_rate: 1.0            # Trace everything

guardrails:
  pii_detection: warn         # Warn but don't block
  toxicity_filter: disabled   # Don't want false positives blocking dev

---
# config/environments/staging.yaml
environment: staging
llm:
  provider: openai
  model: gpt-4o               # Same model as prod
  max_tokens: 4096
  daily_budget: 200.00
  rate_limit: 500

vectordb:
  provider: qdrant
  url: http://qdrant-staging.internal:6333
  collection_suffix: "_staging"
  replicas: 2                 # Some replication to catch issues

cache:
  enabled: true
  ttl_seconds: 300            # Shorter TTL for faster iteration
  semantic_threshold: 0.98    # Very strict matching

observability:
  tracing: enabled
  log_level: INFO
  log_prompts: false
  sample_rate: 0.5

guardrails:
  pii_detection: block
  toxicity_filter: enabled

---
# config/environments/production.yaml
environment: production
llm:
  provider: litellm_proxy     # Multi-provider with failover
  primary_model: gpt-4o
  fallback_models:
    - anthropic/claude-3-5-sonnet
    - cohere/command-r-plus
  max_tokens: 4096
  daily_budget: 2000.00
  rate_limit: 5000
  timeout_seconds: 30
  retry:
    max_attempts: 3
    backoff_base: 2

vectordb:
  provider: qdrant
  url: grpcs://qdrant-prod.internal:6334
  collection_suffix: ""
  replicas: 3
  read_consistency: majority

cache:
  enabled: true
  ttl_seconds: 3600
  semantic_threshold: 0.95
  max_memory_gb: 8

observability:
  tracing: enabled
  log_level: WARN
  log_prompts: false          # NEVER log prompts in prod (PII risk)
  sample_rate: 0.05           # 5% trace sampling
  metrics:
    - request_latency
    - token_usage
    - cache_hit_rate
    - quality_score
    - cost_per_request

guardrails:
  pii_detection: block
  toxicity_filter: enabled
  hallucination_check: enabled  # Only in prod (expensive)
  max_output_length: 8000
```

---

## Disaster Recovery: Vector DB Corruption Recovery

### Incident Report: Qdrant Corruption at DataLens AI

**Date:** November 2024  
**Impact:** 4 hours of degraded RAG quality, 45 minutes of full outage  
**Root cause:** A failed schema migration corrupted the HNSW index on 2 of 3 Qdrant replicas

### Their Backup Strategy (Before the Incident)

```yaml
# Backup configuration
backups:
  vector_db:
    type: qdrant_snapshot
    schedule: "0 */4 * * *"       # Every 4 hours
    retention: 72h                 # Keep 3 days of snapshots
    storage: s3://datalens-backups/qdrant/
    
    # Also maintain a WAL-based continuous backup
    wal_backup:
      enabled: true
      destination: s3://datalens-backups/qdrant-wal/
      lag_alert_threshold: 5m
  
  metadata_db:
    type: pg_dump
    schedule: "0 * * * *"          # Hourly
    retention: 7d

  document_store:
    type: s3_versioning           # S3 versioning handles this
    
rto_rpo_targets:
  vector_db:
    rpo: 4h   # Max 4 hours of data loss (snapshot interval)
    rto: 30m  # Must recover within 30 minutes
  metadata_db:
    rpo: 1h
    rto: 15m
```

### The Recovery Timeline

```
09:00 — Engineer runs schema migration on Qdrant (adding new payload index)
09:02 — Migration fails midway due to OOM on 2 replicas
09:03 — Qdrant replicas restart, HNSW index reports corruption on affected shards
09:05 — Health check fails → pods marked NotReady → traffic routed to 1 healthy replica
09:07 — Alert fires: "Qdrant cluster degraded — 1/3 replicas serving"
09:10 — On-call acknowledges, starts investigation
09:15 — Decision: single replica can't handle production load (latency spiking to 5s)
09:18 — Activate recovery runbook
```

### Recovery Procedure (Executed)

```bash
#!/bin/bash
# runbooks/qdrant-recovery.sh

echo "=== Qdrant Disaster Recovery ==="
echo "Step 1: Scale up healthy replica to handle load"
kubectl scale statefulset qdrant --replicas=1 -n vectordb
# Keep only the healthy replica, remove corrupted ones

echo "Step 2: Enable degraded mode in application"
kubectl set env deployment/rag-service \
  VECTORDB_MODE=degraded \
  VECTORDB_TIMEOUT=10s \
  CACHE_FALLBACK=true  # Serve from semantic cache when possible

echo "Step 3: Find latest clean snapshot"
LATEST_SNAPSHOT=$(aws s3 ls s3://datalens-backups/qdrant/ \
  --recursive | sort | tail -5 | head -1 | awk '{print $4}')
echo "Latest snapshot: $LATEST_SNAPSHOT"
# Found: qdrant/2024-11-15-0400-snapshot.tar.gz (5 hours old)

echo "Step 4: Provision fresh Qdrant nodes"
kubectl apply -f k8s/qdrant-recovery-statefulset.yaml
# Fresh StatefulSet with 2 new replicas

echo "Step 5: Restore snapshot to new nodes"
kubectl exec qdrant-recovery-0 -- \
  qdrant-restore --snapshot s3://datalens-backups/qdrant/$LATEST_SNAPSHOT

echo "Step 6: Re-index documents uploaded in last 5 hours"
python scripts/reindex_recent.py \
  --since "2024-11-15T04:00:00Z" \
  --source s3://datalens-documents/ \
  --target qdrant-recovery-0:6333

echo "Step 7: Validate recovery"
python scripts/validate_vectordb.py \
  --endpoint qdrant-recovery-0:6333 \
  --test-queries eval/vectordb_validation_queries.json \
  --expected-recall 0.95

echo "Step 8: Switch traffic to recovered cluster"
kubectl patch service qdrant -n vectordb \
  -p '{"spec":{"selector":{"app":"qdrant-recovery"}}}'

echo "Step 9: Disable degraded mode"
kubectl set env deployment/rag-service VECTORDB_MODE=normal CACHE_FALLBACK=false
```

### Final Statistics
- **Actual RPO achieved:** 5 hours (snapshot was from 04:00, incident at 09:00) + 20 min re-indexing
- **Actual RTO achieved:** 52 minutes (target was 30 min — triggered post-mortem action item)
- **Data loss:** 847 documents uploaded between 04:00-09:00 were re-indexed from S3 source → **zero permanent data loss**

### Post-Incident Improvements
1. Reduced snapshot frequency to every 1 hour (RPO improved to 1h)
2. Added pre-migration snapshot: auto-snapshot before any schema change
3. Implemented WAL-based continuous replication to standby cluster
4. Added canary migration: test schema changes on 1 replica first

---

## Cost of Deployment Choices: Real Comparison

### Scenario: RAG-based customer support bot

| Traffic Level | Queries/day | Avg tokens/query | Concurrent users |
|---------------|-------------|-------------------|------------------|
| Low | 1,000 | 2,000 | 5 |
| Medium | 50,000 | 2,500 | 100 |
| High | 500,000 | 3,000 | 1,000 |

### Option A: Serverless (AWS Lambda + Bedrock)

```
Low traffic:
  Lambda invocations: 1,000/day × $0.0000002 = $0.006/month
  Lambda compute: 1,000 × 10s × 1GB = 10,000 GB-s × $0.0000167 = $5/month
  Bedrock (Claude Sonnet): 2M tokens/day × 30 × $0.003/1K = $180/month
  API Gateway: $3.50/month
  Total: ~$189/month ← WINNER for low traffic

Medium traffic:
  Lambda: 50K/day × 30 = 1.5M invocations + compute = $450/month
  Bedrock: 125M tokens/month × $0.003/1K = $375/month
  API Gateway: $175/month
  Cold starts become painful (2-5s on first request)
  Total: ~$1,000/month

High traffic:
  Lambda: Concurrency limits hit (1000 default), need reserved = $3,500/month
  Bedrock: Provisioned throughput needed = $5,000/month
  Cold starts unacceptable at scale
  Total: ~$8,500/month + poor UX from cold starts
```

### Option B: Kubernetes (EKS)

```
Low traffic:
  EKS cluster: $73/month
  2x t3.medium nodes: $60/month
  ALB: $25/month
  Over-provisioned for low traffic
  Total: ~$158/month + LLM API costs ($180) = $338/month

Medium traffic:
  EKS cluster: $73/month
  4x m6i.large nodes: $280/month
  ALB: $50/month
  Stable latency, no cold starts
  Total: ~$403/month + LLM API ($375) = $778/month ← WINNER

High traffic:
  EKS cluster: $73/month
  12x m6i.xlarge nodes (auto-scaled): $1,680/month
  ALB + WAF: $200/month
  Consistent performance under load
  Total: ~$1,953/month + LLM API (negotiated rate ~$3,000) = $4,953/month ← WINNER
```

### Option C: Dedicated GPU (Self-hosted inference with open-source model)

```
Low traffic:
  1x g5.xlarge (on-demand): $1,210/month
  Massive overkill — GPU sits 99% idle
  Total: ~$1,400/month (absurd for 1K queries/day)

Medium traffic:
  1x g5.2xlarge: $1,825/month
  No per-token API costs!
  Good utilization at 50K queries/day
  Total: ~$2,100/month (competitive only if avoiding API costs matters)

High traffic:
  4x g5.12xlarge (spot mix): $8,000/month
  Zero marginal cost per token
  Full control over model, no rate limits
  Total: ~$9,500/month BUT unlimited throughput
  Break-even vs API: if API would cost >$9,500 in tokens
```

### Decision Matrix

| Factor | Serverless | Kubernetes | Dedicated GPU |
|--------|-----------|------------|---------------|
| Best at | < 5K req/day | 5K-500K req/day | > 500K + cost-sensitive |
| Worst at | High concurrency | Low traffic (over-provisioned) | Low traffic (waste) |
| Cold start | 2-5s | None | None |
| Ops burden | Minimal | Medium | High |
| Scaling speed | Instant | 2-5 min (node provision) | 5-10 min |
| Vendor lock-in | High | Medium | Low |
| Data privacy | Data leaves your VPC | Stays in cluster | Full control |

**The real-world answer:** Most teams at medium scale use Kubernetes for the application layer + API-based LLM providers, then add self-hosted GPU nodes only for embedding generation (high volume, predictable workload) while keeping reasoning on APIs (variable, harder to self-host).
