# Real-World Examples: AI Architect Orientation

## 1. How a Senior AI Architect Operates at Top Companies

### Stripe: AI Architect for Fraud Detection Platform

At Stripe, the AI Architect for Radar (fraud detection) operates across three planes:

**Strategic plane (weekly):**
- Meets with product leadership to align ML roadmap with Stripe's revenue goals
- Decides whether to build custom fraud models or leverage foundation models
- Sets latency budgets: fraud scoring must complete in <100ms at p99 for payment flow

**Technical plane (daily):**
- Reviews architecture proposals for new model serving infrastructure
- Defines contracts between the feature store (built on Apache Flink) and model inference layer
- Makes build-vs-buy decisions: Stripe built their own feature store because no vendor met their latency + consistency requirements

**Organizational plane (ongoing):**
- Maintains the ML platform RFC process (any change affecting >2 teams needs an RFC)
- Runs architecture review board for ML services
- Mentors senior engineers transitioning into architect-adjacent roles

**Key decision example:** In 2022, Stripe's AI architect decided to move from batch fraud scoring to real-time streaming inference. This required:
- Migrating from hourly batch predictions to sub-100ms online inference
- Building a custom feature store that could serve 1000+ features in <10ms
- Redesigning the model training pipeline to support continuous learning
- Result: 40% improvement in fraud detection with same false positive rate

---

### Netflix: AI Architect for Recommendations Platform

Netflix's recommendation system serves 230M+ subscribers. The AI architect role here involves:

**Architecture scope:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Netflix AI Platform                        │
├──────────────┬──────────────┬───────────────┬───────────────┤
│  Metaflow    │  Feature     │   Model       │  A/B Testing  │
│  (Workflow)  │  Store       │   Registry    │  Platform     │
├──────────────┼──────────────┼───────────────┼───────────────┤
│  Data Lake   │  Spark/Flink │   KubeFlow    │  Experimentation│
│  (S3/Iceberg)│  Processing  │   Serving     │  Framework     │
└──────────────┴──────────────┴───────────────┴───────────────┘
```

**Real decisions made:**
1. Built Metaflow (open-sourced) rather than adopting Airflow - reason: data scientists needed Python-native workflow tooling, not DAG configuration
2. Chose to run separate model serving clusters per use-case rather than a shared inference platform - reason: recommendations (high throughput, relaxed latency) vs. content safety (lower throughput, strict latency) have incompatible SLO requirements
3. Invested in a custom A/B testing framework that supports interleaving experiments for ranking models

---

### Google DeepMind: Research-to-Production Architect

The bridge between research and production at Google requires a specific architect profile:

**Responsibilities:**
- Translates research breakthroughs (e.g., Gemini architecture improvements) into scalable production systems
- Defines the "productionization contract": what a research team must deliver for a model to be production-ready
- Manages the TPU allocation strategy across research training and production inference

**Productionization contract example:**
```
Research team must provide:
├── Model checkpoint + training config (reproducible)
├── Evaluation suite with regression benchmarks
├── Latency/memory profile at target batch sizes
├── Known failure modes + mitigation strategies
├── Data pipeline specification (training data lineage)
└── Responsible AI evaluation results
```

---

## 2. Real Organizational Structures for AI Teams

### Pattern A: Centralized AI Platform (Used by: Uber, Airbnb, LinkedIn)

```
CTO
├── VP of AI/ML Platform
│   ├── ML Infrastructure Team (12-20 engineers)
│   │   ├── Model Serving (Kubernetes, Triton, TensorRT)
│   │   ├── Feature Store (online + offline)
│   │   ├── Training Infrastructure (GPU clusters)
│   │   └── ML Observability (drift detection, monitoring)
│   ├── ML Tools Team (6-10 engineers)
│   │   ├── Experiment tracking
│   │   ├── Model registry
│   │   └── Developer experience (SDKs, CLI tools)
│   └── Applied ML Team (8-15 scientists)
│       ├── Shared models (embeddings, NLP)
│       └── Consulting for product teams
├── VP of Product Engineering
│   ├── Search Team (has 2-3 ML engineers embedded)
│   ├── Recommendations Team (has 3-4 ML engineers embedded)
│   └── Trust & Safety Team (has 2-3 ML engineers embedded)
```

**Advantages:** Consistent infrastructure, no duplicated effort, career growth for ML engineers
**Disadvantages:** Platform team becomes bottleneck, product teams feel underserved

### Pattern B: Federated AI (Used by: Google, Meta, Amazon)

```
CEO
├── Division A (Search)
│   ├── Own ML infra team
│   ├── Own research team
│   └── Own production ML team
├── Division B (Ads)
│   ├── Own ML infra team
│   ├── Own research team
│   └── Own production ML team
├── Central AI Research Lab (DeepMind / FAIR / Alexa AI)
│   └── Provides foundation models, breakthroughs
└── Shared Infrastructure (TPUs/GPUs, storage, networking)
```

**Advantages:** Teams move fast independently, deep domain expertise
**Disadvantages:** Massive duplication, inconsistent practices, hard to share learnings

### Pattern C: Hub-and-Spoke (Used by: Spotify, Stripe, DoorDash)

```
CTO
├── AI Platform Team (Hub) - 15-25 engineers
│   ├── Provides: serving infra, feature store, experiment platform
│   ├── Provides: SDKs and abstractions
│   └── Sets: standards, best practices, review process
├── Product Team A (Spoke) - has 3-5 ML engineers
│   └── Uses platform, builds domain-specific models
├── Product Team B (Spoke) - has 2-4 ML engineers
│   └── Uses platform, builds domain-specific models
└── Research Team (Small, focused)
    └── Evaluates new approaches, prototypes
```

---

## 3. Case Study: How Spotify Built Their AI Platform Organization

### Timeline: 2015-2023

**Phase 1 (2015-2017): Ad-hoc ML**
- Individual teams built their own ML pipelines
- Recommendations team had custom TensorFlow serving
- Search team used separate Elasticsearch ML features
- NLP team had their own text classification pipeline
- Problem: 5 different teams maintained 5 different model serving solutions

**Phase 2 (2018-2019): Platform consolidation**
- Created "ML Platform" team (initially 6 engineers, grew to 20)
- Built internal platform called "ML Hub" (later influenced their open-source contributions)
- Standardized on:
  - Luigi → migrated to Cloud Dataflow for pipeline orchestration
  - TFX for model validation
  - Custom feature store built on BigTable + Scio (Scala data processing)
- Key architectural decision: Event-driven architecture for feature computation
  - Every user action → Pub/Sub → Feature computation → BigTable (online) + GCS (offline)

**Phase 3 (2020-2022): Self-service ML**
- Goal: Any engineer at Spotify can train and deploy a model in <1 day
- Built "Hendrix" - internal ML platform providing:
  - One-click model deployment (abstracted Kubernetes complexity)
  - Automated A/B testing integration
  - Feature store with <10ms online serving latency
  - Model monitoring with automatic rollback

**Phase 4 (2023+): LLM integration**
- Added LLM gateway layer on top of existing platform
- "DJ" feature (AI-powered personalized playlists with voice) built by:
  - 2 ML engineers (personalization model)
  - 3 backend engineers (serving infrastructure)
  - 1 AI architect (system design, vendor selection for voice synthesis)
- Key decision: Use OpenAI for generation, own models for personalization/ranking

**Organizational lessons learned:**
1. Don't build platform too early (they wasted effort in 2016 on premature abstraction)
2. Platform team needs embedded "customer" engineers who rotate in from product teams
3. AI architect role emerged organically from senior engineers who kept making cross-team decisions

---

## 4. Case Study: Fintech Startup Scaling from 1 to Full AI Platform Team

### Company: "LendAI" (composite of real patterns from Plaid, Brex, Ramp)

**Stage 1: Solo AI Engineer (Months 1-6, $2M seed)**
- One ML engineer building credit risk scoring model
- Architecture: Python script → scikit-learn model → Flask API → single EC2 instance
- Model retrained weekly by running a Jupyter notebook manually
- Database: Single Postgres instance for everything

**Stage 2: Small Team (Months 7-18, $15M Series A)**
- Hired 2 more ML engineers + 1 data engineer
- Pain points that triggered hires:
  - Model serving went down on weekends (nobody monitoring)
  - Feature computation took 4 hours, blocking daily retraining
  - No experiment tracking (engineers overwriting each other's models)
- Architecture evolution:
  - Moved to Docker + ECS for model serving
  - Added MLflow for experiment tracking
  - Built simple feature pipeline on Airflow + Redshift
  - Added PagerDuty alerts for model service health

**Stage 3: Dedicated AI Platform (Months 18-36, $50M Series B)**
- Team grew to: 4 ML engineers, 2 ML platform engineers, 1 data engineer, 1 AI architect (hired)
- AI architect's first 90 days:
  - Week 1-2: Mapped all ML systems, identified 7 critical gaps
  - Week 3-4: Wrote architecture vision document (18 pages)
  - Week 5-8: Led migration from ECS to Kubernetes for model serving
  - Week 9-12: Implemented feature store, model registry, and CI/CD for models
- Key decisions by architect:
  - Chose SageMaker for training (don't manage GPU infrastructure at this stage)
  - Built lightweight feature store on Redis + Postgres (not Feast/Tecton - too heavy)
  - Implemented shadow deployment pattern for safe model rollouts
  - Set up model monitoring: PSI (Population Stability Index) drift detection

**Stage 4: Scaling (Months 36+, $200M Series C)**
- Team: 12 ML engineers, 5 platform engineers, 2 architects, 1 Head of AI
- Now processing 50M credit decisions/month
- Architecture matured to:
  - Multi-model ensemble (gradient boosted trees + neural network + rule engine)
  - Real-time feature computation (<50ms) via Kafka Streams
  - Automated retraining triggered by drift detection
  - Full model governance: audit trail, explainability, bias monitoring

---

## 5. Day-in-the-Life: AI Architect at Different Company Sizes

### Startup (50 people, 5 engineers, 1 AI architect)

```
8:30  - Review overnight model performance dashboards
9:00  - Standup with engineering team (AI architect IS the tech lead)
9:30  - Hands-on coding: implementing new embedding model for search
11:00 - Call with potential vendor (evaluating Pinecone vs self-hosted Qdrant)
12:00 - Lunch + reading latest papers on RAG optimization
13:00 - Architecture design for new feature (writes the RFC AND implements it)
15:00 - Pair programming with junior ML engineer on data pipeline
16:30 - Meeting with CEO about AI product roadmap
17:30 - Deploy new model version to production (they do their own deploys)
```

**Key difference:** AI architect is 60% hands-on coding, 40% design/strategy

### Mid-size (500 people, 50 engineers, 2-3 AI architects)

```
8:30  - Review PRs from ML platform team (architectural consistency)
9:00  - Architecture review meeting: evaluating proposal for new RAG system
10:00 - Write technical design document for LLM gateway
11:00 - 1:1 with senior ML engineer (mentoring on system design)
11:30 - Cross-team sync: aligning ML platform with data platform roadmap
12:30 - Lunch
13:00 - Deep work: designing evaluation framework for LLM outputs
15:00 - Meeting with VP of Engineering: quarterly ML infrastructure budget
16:00 - Review vendor proposals (Databricks vs Snowflake for feature engineering)
17:00 - Update architecture decision records (ADRs)
```

**Key difference:** AI architect is 20% coding, 50% design/review, 30% communication

### Large Enterprise (10,000+ people, 500+ engineers, 8-12 AI architects)

```
8:30  - Review architecture governance dashboard (compliance, cost, drift)
9:00  - AI Architecture Board meeting (reviewing 3 proposals from different divisions)
10:30 - Executive briefing: presenting AI infrastructure 3-year roadmap to CTO
11:30 - Working session: defining organization-wide LLM usage policies
12:30 - Lunch with external partner (cloud provider architecture review)
13:30 - Cross-division alignment: standardizing model deployment patterns
15:00 - Write position paper: "Build vs Buy for Foundation Models"
16:00 - Mentoring session with principal engineers aspiring to architect role
17:00 - Industry research: reviewing competitor architectures, conference papers
```

**Key difference:** AI architect is 5% coding, 30% design, 65% strategy/communication

---

## 6. Real Architecture Review Examples

### Example 1: APPROVED - Real-time Fraud Detection Redesign (Fintech)

**Proposal:** Migrate from batch fraud scoring (hourly) to real-time streaming inference

**Architecture submitted:**
```
User Transaction → API Gateway → Kafka → Feature Enrichment (Flink)
    → Model Inference (Triton on K8s, p99 < 50ms)
    → Decision Engine → Response to Payment Service
    
Fallback: If inference fails, use rule-based system (never block a payment due to ML failure)
```

**Review board assessment:**
- Latency budget: 50ms for inference is achievable with their model size (approved)
- Fault tolerance: Fallback to rules is correct - ML should enhance, not gate payments (approved)
- Cost analysis: $45K/month for GPU inference cluster - justified by $2M/month fraud prevention (approved)
- Data freshness: Flink features computed in <5s from event - adequate for fraud patterns (approved)
- Rollback plan: Shadow mode for 2 weeks before taking live traffic (approved)

**Result: APPROVED with condition** - must add circuit breaker between Flink and Triton

---

### Example 2: REJECTED - "Let's Fine-tune GPT-4 for Everything" (E-commerce)

**Proposal:** Fine-tune GPT-4 for product categorization, review summarization, search query understanding, and customer support

**Architecture submitted:**
```
All text tasks → Single fine-tuned GPT-4 endpoint → All downstream services
```

**Review board rejection reasons:**
1. **Cost:** GPT-4 fine-tuning + inference for 500M daily product categorizations = $800K/month. A BERT classifier does this for $2K/month with 98% accuracy.
2. **Latency:** GPT-4 inference at ~2s per request is unacceptable for search query understanding (budget: 50ms)
3. **Single point of failure:** One model for all tasks means one failure affects everything
4. **No evaluation framework:** No benchmarks comparing GPT-4 vs simpler models per task
5. **Data governance:** Product catalog data cannot be sent to external API (regulatory requirement)

**Counter-proposal approved:**
```
Product categorization → Fine-tuned BERT (on-premise, <10ms)
Review summarization → GPT-3.5-turbo via API (acceptable latency for async task)
Search query understanding → Custom bi-encoder model (on-premise, <20ms)
Customer support → GPT-4 with RAG (acceptable latency for chat)
```

---

### Example 3: APPROVED WITH MAJOR REVISIONS - Vector Search Platform

**Original proposal:** Deploy Pinecone for all embedding search across 6 product teams

**Issues identified:**
- No cost modeling (Pinecone at their scale = $180K/month)
- No latency testing at production load
- Single vendor lock-in for critical path
- No backup/disaster recovery plan

**Revised and approved:**
- Use pgvector for teams with <1M vectors (3 teams) - $0 additional cost
- Use Qdrant self-hosted for teams with 1M-100M vectors (2 teams) - $15K/month
- Use Pinecone only for the one team needing 500M+ vectors with managed scaling - $40K/month
- Total savings: $125K/month vs original proposal

---

## 7. Anti-Pattern War Stories

### War Story 1: "The AI Platform Nobody Used"

**Company type:** Series C fintech, 200 engineers

**What happened:** The AI platform team spent 18 months building a comprehensive ML platform with:
- Custom feature store
- Model registry with full lineage tracking
- Automated hyperparameter tuning
- Custom notebook environment

**The problem:** They never talked to their users (the product ML engineers). When launched:
- Feature store required a 40-step onboarding process
- Model registry had a different abstraction than what teams used (TensorFlow-centric, but teams used PyTorch)
- Notebook environment didn't support the IDE extensions engineers relied on
- Adoption: 2 out of 8 teams used it after 6 months

**Root cause:** Platform team optimized for "correctness" and "completeness" instead of developer experience. No architect was asking "what's the minimum viable platform that solves today's pain?"

**Lesson:** Build platform features in response to demonstrated pain, not anticipated need.

---

### War Story 2: "The $2M Monthly GPU Bill Surprise"

**Company type:** Large e-commerce, moved aggressively to LLMs

**What happened:**
- 12 teams independently deployed LLM-powered features
- Each team provisioned their own GPU inference clusters
- No shared gateway or caching layer
- Many requests were semantically identical (same product descriptions summarized repeatedly)

**The numbers:**
- 12 separate GPU clusters: $2.1M/month
- Average GPU utilization: 12% (massive over-provisioning)
- 40% of LLM calls were cache-able (same inputs seen within 24 hours)

**Fix (led by newly hired AI architect):**
1. Centralized LLM gateway with semantic caching (saved 40% of calls)
2. Shared GPU pool with autoscaling (utilization went to 65%)
3. Model right-sizing (moved 6 use-cases from GPT-4 to GPT-3.5-turbo)
4. New monthly cost: $340K (84% reduction)

**Lesson:** Without an architect enforcing shared infrastructure patterns, teams will independently optimize locally while the organization burns money globally.

---

### War Story 3: "The Model That Worked in Testing But Failed in Production"

**Company type:** Healthcare AI startup

**What happened:** Built a diagnostic assistance model that achieved 94% accuracy in offline evaluation. Deployed to production. Within 2 weeks:
- Accuracy dropped to 71%
- Clinicians stopped trusting the system
- Three incorrect suggestions led to patient complaints

**Root causes identified (post-mortem):**
1. **Training/serving skew:** Training data was clean hospital records. Production input was messy, abbreviated clinical notes with typos.
2. **Population shift:** Training data was from urban academic hospitals. Deployed to rural clinics with different patient demographics.
3. **No monitoring:** No drift detection, no accuracy tracking in production.
4. **No graceful degradation:** Model always returned a confident prediction, even on out-of-distribution inputs.

**Architecture fix:**
```
Clinical Note → Input Quality Check (reject if confidence < threshold)
    → Ensemble of 3 models (only predict if 2/3 agree)
    → Confidence calibration layer
    → Output with uncertainty estimate
    → Clinician sees: prediction + confidence + similar training examples
    
Monitoring: Daily accuracy sampling, weekly distribution shift analysis
Fallback: If model uncertainty > threshold, show "insufficient confidence" instead of prediction
```

**Lesson:** Production ML systems need uncertainty quantification, input validation, monitoring, and graceful degradation. A model is not a product.

---

### War Story 4: "The Infinite Retry Loop"

**Company type:** SaaS company using LLM for document processing

**What happened:** Production system called OpenAI API for contract analysis. During an OpenAI rate-limiting event:
- Service hit rate limit (429 response)
- Retry logic kicked in (exponential backoff)
- But: the retry was inside a Kubernetes pod with a 30-second liveness probe timeout
- Pod got killed during backoff wait → Kubernetes restarted it → immediately retried → got rate limited again
- 400 pods in an infinite restart loop
- Cascading failure: exhausted Kubernetes cluster resources, took down unrelated services

**Architecture failure points:**
1. No circuit breaker (should have stopped retrying after N failures)
2. Liveness probe timeout shorter than retry backoff (pod killed before retry completes)
3. No bulkhead isolation (LLM service failure affected other services)
4. No queue-based architecture (should have queued requests and processed when API recovered)

**Fix:**
```
Request → Queue (SQS) → Worker with circuit breaker
    → If open: return cached/fallback response
    → If closed: call API with proper timeout
    → Dead letter queue for persistent failures
    
Kubernetes: Separate node pool for LLM workloads (blast radius containment)
Liveness probe: 120s timeout, separate from readiness probe
Circuit breaker: Opens after 5 consecutive failures, half-open after 60s
```

---

### War Story 5: "The Feature Store That Caused a Data Breach"

**Company type:** Financial services

**What happened:** ML team built a feature store that cached user financial data for fast model inference. The feature store:
- Stored raw financial data (account balances, transaction history) in Redis
- Redis cluster had no encryption at rest
- No access controls beyond network-level security
- Feature store was accessible from the development environment (for debugging convenience)

**Discovery:** During a security audit, a penetration tester accessed the Redis cluster from a compromised development machine and extracted 2M customer financial records.

**Regulatory impact:** GDPR fine, mandatory disclosure, 6-month remediation program

**Architecture fix (mandated by AI architect post-incident):**
```
Feature Store Architecture (compliant):
├── Online Store (Redis)
│   ├── Encryption at rest (AES-256)
│   ├── Encryption in transit (TLS 1.3)
│   ├── Feature-level access controls (RBAC)
│   ├── PII features: tokenized, not raw values
│   └── Audit logging on all reads
├── Offline Store (S3 + Parquet)
│   ├── Column-level encryption for PII
│   ├── Access requires data classification approval
│   └── Automatic expiry per retention policy
└── Access Layer
    ├── Service-to-service auth (mTLS)
    ├── Feature access requires explicit grant per model
    └── No development environment access to production data
```

**Lesson:** AI architects must own security architecture for ML systems. Feature stores, model registries, and training pipelines all handle sensitive data and need the same security rigor as any production database.
