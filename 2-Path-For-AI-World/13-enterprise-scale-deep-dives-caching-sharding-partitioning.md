# Enterprise Scale Deep Dives: Caching, Sharding, Partitioning, and Retrieval Infrastructure

**Learning level:** Advanced to enterprise  
**Why this exists:** The source roadmap already mentions prompt cache, semantic cache, retrieval cache, vector DB sharding, replication, tenant isolation, and hot indexes. This file expands those ideas into architect-level design patterns you should know before discussing each concept in depth.

---

# 1. Caching Architecture for AI Systems

AI systems need multiple cache layers because one user request may touch auth, retrieval, reranking, tools, model calls, guardrails, traces, and eval sampling.

## Cache Types

| Cache | What It Stores | Primary Benefit | Main Risk |
|---|---|---|---|
| prompt/prefix cache | repeated prompt prefixes and static instructions | lower latency and model cost | stale prompt or policy version |
| semantic response cache | answers for semantically similar questions | lower model calls | wrong reuse across tenant, permission, or freshness boundary |
| retrieval result cache | query -> document IDs/chunks | lower vector/search QPS | stale documents or ACL changes |
| reranker cache | candidate set -> reranked order | lower reranker cost | stale ranking after model/index changes |
| embedding cache | text/chunk -> vector | lower embedding cost | wrong embedding model/version |
| tool-result cache | API/tool responses | lower tool latency and rate-limit pressure | stale business data or side-effect confusion |
| document parse cache | raw document -> extracted text/tables/layout | faster reindexing | parser version mismatch |
| authorization decision cache | user/scope/resource decision | lower policy latency | permission revocation delay |
| eval cache | repeated judge/eval outputs | lower eval cost | invalid comparisons after rubric changes |

## Cache Key Design

Never cache only by natural-language query. A production AI cache key usually includes:

- tenant ID
- user or role scope
- permission hash
- risk tier
- language and locale
- model name/version
- prompt version
- tool schema version
- retrieval configuration version
- embedding model and index version
- source corpus version or freshness timestamp
- safety policy version
- response format/schema version

Bad key:

```text
hash(user_question)
```

Better key:

```text
hash(
  tenant_id,
  permission_fingerprint,
  normalized_query,
  prompt_version,
  model_version,
  retriever_version,
  index_version,
  source_freshness_watermark,
  safety_policy_version
)
```

## Cache Invalidation Rules

Invalidate or bypass cache when:

- document permissions change
- source document version changes
- user role/scope changes
- embedding model changes
- chunking strategy changes
- reranker changes
- prompt or system instructions change
- model/provider changes behavior
- safety policy changes
- legal/compliance retention window expires
- user requests fresh/live data

## Interview-Grade Caching Answer

> I use caching at prompt, semantic response, retrieval, embedding, reranker, tool-result, and eval layers, but every cache is scoped by tenant, permissions, freshness, model/prompt/index versions, and risk tier. I never let semantic cache bypass authorization or freshness rules.

---

# 2. Billion-Request AI Caching Strategy

Prompt caching alone does not handle billions of users or billions of requests. It is one layer in a larger AI scale architecture.

Billion-scale AI needs:

- routing
- batching
- queues
- regional cells
- semantic cache
- retrieval cache
- model fallback
- vector DB sharding
- rate limits
- backpressure
- budget controls
- degraded modes

Architect principle:

> Prompt/prefix caching reduces repeated prompt-processing cost. It does not solve authorization, retrieval QPS, vector DB scale, tool latency, model provider limits, tenant isolation, freshness, or regional failover.

## Billion-Request Capacity Model

Use request volume and workflow shape to estimate every downstream bottleneck.

```text
daily_active_users
x requests_per_user_per_day
x agent_steps_per_request
x model_calls_per_step
x average_input_tokens
x average_output_tokens
= daily model token demand

daily_active_users
x requests_per_user_per_day
x retrieval_calls_per_request
= daily retrieval demand

daily_active_users
x requests_per_user_per_day
x tool_calls_per_request
= daily tool demand

peak_multiplier
x daily average QPS
= peak QPS target
```

Capacity dimensions:

| Dimension | Estimate |
|---|---|
| model QPS | requests x model calls per request |
| token throughput | input tokens/sec + output tokens/sec |
| retrieval QPS | requests x retrieval calls per request |
| reranker QPS | retrieved candidate sets x reranker calls |
| embedding QPS | ingestion chunks + live query embeddings |
| tool QPS | requests x tool calls per request |
| queue depth | long-running jobs, retries, evals, ingestion |
| trace write QPS | spans per request x requests/sec |
| cache QPS | reads/writes across prompt, semantic, retrieval, and tool caches |
| approval workload | high-risk actions x review rate |

## Cache Layers For Billion-Scale AI

| Cache Layer | What It Caches | Key Design | Invalidation |
|---|---|---|---|
| prompt/prefix cache | static system prompts, developer instructions, common tool schemas, fixed policy text | prompt version, model, tenant policy, safety policy | prompt/model/policy/tool schema change |
| semantic response cache | final answers or answer drafts for semantically similar questions | tenant, permission hash, query embedding, risk tier, model, prompt version, freshness watermark | source update, permission change, policy change, high-risk query |
| retrieval cache | query -> candidate document/chunk IDs | tenant, ACL hash, retriever config, index version, source freshness | document update/delete, ACL change, index migration |
| embedding cache | text/chunk/query -> embedding vector | text hash, embedding model, preprocessing version, dimension | embedding model/preprocessing/chunking change |
| reranker cache | candidate set -> reranked list | candidate IDs, reranker model, reranker prompt/config, query hash | reranker change, candidate content/version change |
| tool-result cache | read-only API/tool output | user/tenant scope, tool name/version, params, data freshness SLA | source update, permission change, TTL expiry |
| authorization cache | policy decisions and resource access checks | user, tenant, roles, groups, resource, policy version | role/group/policy/resource ACL change |
| document parse cache | raw doc -> parsed text/table/layout | document version, parser version, OCR model version | doc/parser/OCR change |

## Regional Cache Hierarchy

Billion-scale systems need caches close to traffic, but cache safety matters more than cache hit rate.

```text
Client / edge
  -> regional API gateway cache
  -> regional AI gateway cache
  -> regional semantic cache
  -> regional retrieval cache
  -> regional vector/search replicas
  -> global source-of-truth metadata and policy systems
```

Regional design rules:

- keep tenant traffic pinned to a home region or cell when data residency requires it
- replicate only data that is allowed to cross regions
- prefer regional semantic caches for low latency, but include source freshness and policy version in keys
- use regional retrieval caches only when ACL sync and freshness watermarks are reliable
- keep global invalidation events for prompt, policy, source, and permission changes
- define degraded mode per region when model provider, vector DB, or tool APIs fail

## Tenant-Aware Cache Keys

Never cache AI outputs only by prompt text or user question. Every AI cache that can affect an answer must include security, freshness, and version context.

Minimum safe key fields:

- tenant ID
- user ID, role, or permission fingerprint
- policy version
- model name/version
- prompt version
- tool schema version
- retriever version
- embedding model/version
- vector index version
- source freshness watermark
- region/cell
- risk tier
- output schema version

Example:

```text
cache_key = hash(
  tenant_id,
  permission_fingerprint,
  normalized_query,
  region_or_cell,
  risk_tier,
  model_version,
  prompt_version,
  retriever_version,
  embedding_version,
  index_version,
  source_freshness_watermark,
  policy_version,
  output_schema_version
)
```

Unsafe key:

```text
cache_key = hash(user_question)
```

## Cache Invalidation

Invalidate or bypass AI caches when:

- prompt instructions change
- model/provider changes
- tool schema changes
- safety policy changes
- document content changes
- source freshness watermark changes
- ACLs or group membership changes
- tenant policy changes
- embedding model changes
- vector index changes
- reranker changes
- answer depends on live data
- request is high-risk and requires fresh verification

Invalidation patterns:

| Pattern | Use When |
|---|---|
| TTL | low-risk data can be briefly stale |
| versioned keys | prompt, model, tool, index, and policy changes |
| event-driven invalidation | document, ACL, or source-system change events are available |
| freshness watermark | retrieval depends on source corpus version |
| write-through invalidation | tool writes change data that can be read later |
| cache bypass | high-risk, live-data, permission-sensitive, or low-confidence cases |

## Cache Stampede Protection

At high traffic, popular cache keys expiring at the same time can overload model providers, vector DBs, or tools.

Use:

- request coalescing / single-flight per key
- TTL jitter
- stale-while-revalidate
- background refresh
- cache warming for known hot prompts and docs
- per-key concurrency limits
- fallback to stale low-risk answer with freshness label
- circuit breakers around model, retrieval, and tool dependencies

Stampede pattern:

```text
many requests miss same key
  -> one request recomputes
  -> others wait, receive stale value, or get queued
  -> cache is refreshed once
```

## Hot-Key Protection

Hot tenants, common prompts, viral questions, common documents, or popular tools can create uneven load.

Controls:

- detect top keys by QPS and latency contribution
- shard hot keys with read replicas
- precompute common responses when safe
- replicate hot retrieval indexes
- isolate hot tenants in dedicated cells
- enforce tenant budgets and per-key rate limits
- degrade expensive flows before they affect the whole platform
- split read-only and side-effecting tool paths

## Stale-Answer Policy

Some stale answers are acceptable. Some are dangerous. Define policy by risk tier.

| Risk Tier | Stale Cache Policy |
|---|---|
| low-risk FAQ | stale-while-revalidate allowed with source timestamp |
| internal productivity | short TTL allowed if no policy/security change |
| customer support | stale allowed only for generic docs, not account/order state |
| finance/legal/HR | require fresh retrieval and citations for policy-sensitive answers |
| transactional actions | no stale tool data for side effects |
| safety/security incident | bypass semantic cache and require current evidence |

Answer UX rule:

> If freshness matters, show source timestamp, confidence, and whether the answer used cached evidence.

## Cache Safety For Auth And Permissions

Cache safety rules:

- never share semantic response cache across tenants unless the answer uses only public/global data
- never reuse cached retrieval results across different permission fingerprints
- never cache tool results from write or side-effect operations as reusable truth
- never let prompt cache preserve old policy after a policy version change
- never return cached answer if required source documents were deleted or access was revoked
- run negative access tests against semantic, retrieval, and tool-result caches
- log cache hits/misses with redaction and tenant isolation
- include permission revocation latency in SLOs

Permission-safe retrieval flow:

```text
request
  -> authenticate user
  -> compute tenant and permission fingerprint
  -> check policy version
  -> lookup permission-scoped cache
  -> verify current ACL before context assembly
  -> generate or return answer
  -> log cache decision
```

## Routing, Batching, Queues, And Backpressure

Caching reduces work, but billion-scale AI also needs traffic shaping.

| Mechanism | Purpose |
|---|---|
| model routing | simple tasks use small/cheap models; hard/risky tasks use stronger models |
| provider routing | spread load across approved providers or self-hosted models |
| batching | group embeddings, reranking, evals, and some model calls for throughput |
| async queues | isolate long-running agent jobs, ingestion, evals, and retries |
| priority queues | protect high-priority tenants/workflows |
| backpressure | reject, delay, or degrade before dependencies collapse |
| rate limits | control tenant, user, workflow, model, and tool usage |
| budget controls | stop runaway cost before it becomes an incident |
| degraded modes | answer with smaller model, fewer tools, stale low-risk cache, or human escalation |

## Billion-Scale AI Request Path

```text
User request
  -> DNS / edge / WAF
  -> API gateway rate limit
  -> auth and tenant policy
  -> AI gateway budget and routing
  -> prompt/prefix cache check
  -> semantic cache check
  -> retrieval cache check
  -> vector/search shard routing
  -> reranker cache check
  -> model routing / batching / fallback
  -> tool-result cache or queued tool execution
  -> guardrails and confidence scoring
  -> response streaming
  -> trace, metrics, eval sampling
```

## Billion-Scale Readiness Checklist

- [ ] prompt/prefix caching for stable prompt prefixes and tool schemas
- [ ] semantic response caching scoped by tenant, permission, freshness, and risk
- [ ] retrieval cache scoped by ACL hash, index version, and source freshness
- [ ] embedding cache with embedding model and preprocessing version
- [ ] reranker cache with reranker model/config and candidate version
- [ ] read-only tool-result cache with source freshness and scoped permissions
- [ ] regional cache hierarchy with data-residency rules
- [ ] tenant-aware cache keys
- [ ] cache invalidation for prompt, model, source, index, ACL, and policy changes
- [ ] cache stampede protection
- [ ] hot-key and hot-tenant protection
- [ ] stale-answer policy by risk tier
- [ ] cache safety tests for auth and permissions
- [ ] model routing and provider fallback
- [ ] batching for embeddings, reranking, evals, and compatible model calls
- [ ] async queues for long-running agents, ingestion, evals, and retries
- [ ] vector DB sharding and hot-index replication
- [ ] rate limits by user, tenant, workflow, model, and tool
- [ ] backpressure and circuit breakers
- [ ] budget controls and cost anomaly alerts
- [ ] degraded modes for model, vector DB, tool, and region failures
- [ ] full-path load test including cache hit/miss ratios

Interview-grade answer:

> Prompt caching is useful, but it is not a billion-user architecture. Billion-scale AI needs a cache hierarchy across prompt, semantic response, retrieval, embedding, reranker, and tool-result layers, all scoped by tenant, permissions, freshness, and versions. It also needs routing, batching, queues, regional cells, model fallback, vector DB sharding, rate limits, backpressure, budget controls, degraded modes, and full-path load testing.

## AWS Mapping For Billion-Request GenAI Platforms

Use this when explaining how the generic billion-scale AI caching architecture maps onto AWS.

| Need | AWS Mapping | Architect Notes |
|---|---|---|
| prompt/prefix caching | model/provider prompt cache where available, AI gateway cache, application cache | Cache stable system prompts, policy blocks, and tool schemas by model, prompt version, tenant policy, and safety policy. |
| semantic response caching | ElastiCache Redis/Valkey, DynamoDB, OpenSearch/vector similarity cache | Scope by tenant, permission fingerprint, query embedding, freshness watermark, risk tier, model, and prompt version. |
| retrieval cache | ElastiCache, DynamoDB, OpenSearch query/result cache where appropriate | Cache query-to-candidate document IDs only when ACL and source freshness are part of the key. |
| embedding cache | DynamoDB or ElastiCache keyed by text hash and embedding version | Include embedding model, dimension, preprocessing version, and chunking version. |
| reranker cache | ElastiCache or DynamoDB keyed by query and candidate set | Invalidate when reranker model/config or candidate content changes. |
| tool-result cache | ElastiCache, DynamoDB, API Gateway cache for safe read-only APIs | Never reuse side-effecting tool results as source of truth. |
| regional cache hierarchy | Route 53, CloudFront, regional API Gateway/ALB, regional ElastiCache, regional OpenSearch/vector stores | Keep tenant data in allowed regions and define cross-region invalidation. |
| tenant-aware cache keys | Cognito/IAM Identity Center identity, tenant ID, IAM/ABAC policy version, app permission hash | Never cache AI answers by user question alone. |
| cache invalidation | EventBridge, DynamoDB Streams, S3 events, SNS/SQS, Lambda workers | Invalidate on prompt, model, tool schema, source data, index, ACL, and policy changes. |
| cache stampede protection | ElastiCache locks, single-flight in application, SQS buffering, stale-while-revalidate | Prevent many workers from recomputing the same expensive model/retrieval result. |
| hot-key protection | ElastiCache cluster mode, read replicas, dedicated tenant cells, precomputed safe answers | Detect hot tenants/prompts/docs and isolate or replicate them. |
| stale-answer policy | risk-tier policy in AI gateway/app layer | Low-risk FAQ may use stale-while-revalidate; finance, legal, HR, and actions require fresh evidence. |
| cache safety for auth/permissions | IAM, Cognito, ABAC/RBAC/ReBAC app policy, Verified Permissions where adopted | Recheck current permissions before assembling context or executing tools. |
| billion-request capacity model | CloudWatch metrics, X-Ray traces, Cost Explorer, Budgets, load tests | Estimate model QPS, token throughput, retrieval QPS, reranker QPS, tool QPS, queue depth, trace volume, and cache QPS. |

AWS billion-scale AI request path:

```text
User
  -> Route 53 / CloudFront / WAF
  -> API Gateway or ALB throttling
  -> auth through Cognito, IAM Identity Center, or enterprise OIDC
  -> AI gateway service on ECS/EKS/Lambda
  -> prompt/prefix cache check
  -> semantic response cache check
  -> retrieval cache check
  -> Bedrock Knowledge Bases / OpenSearch vector search / custom vector DB
  -> reranker cache check
  -> Bedrock, SageMaker endpoint, or external model provider
  -> read-only tool-result cache or queued tool execution
  -> Step Functions/SQS for long-running work
  -> CloudWatch/X-Ray/CloudTrail tracing and audit
```

AWS cache safety rules:

- Do not cache dynamic Bedrock Agent or MCP gateway traffic at CloudFront unless the cache key and TTL are explicitly safe; dynamic API proxy paths often need caching disabled.
- Do not share semantic response cache across tenants unless the content is public and policy allows it.
- Do not reuse retrieval cache across different permission fingerprints.
- Do not return cached answers after source deletion, right-to-delete, ACL revocation, prompt policy change, or index migration.
- Do not use prompt caching as a substitute for API Gateway throttling, queues, vector DB sharding, model fallback, or budget controls.
- Use private networking patterns, VPC endpoints, IAM roles, KMS encryption, Secrets Manager, CloudTrail, and CloudWatch alarms for sensitive workloads.

AWS readiness checklist:

- [ ] prompt/prefix caching for stable prompt prefixes and tool schemas
- [ ] semantic response caching scoped by tenant, permission, freshness, and risk
- [ ] retrieval cache scoped by ACL hash, index version, and source freshness
- [ ] embedding cache with embedding model and preprocessing version
- [ ] reranker cache with reranker model/config and candidate version
- [ ] read-only tool-result cache with source freshness and scoped permissions
- [ ] regional cache hierarchy with Route 53, CloudFront, regional API entry, ElastiCache, and vector/search replicas
- [ ] tenant-aware cache keys
- [ ] cache invalidation through EventBridge/SNS/SQS/Lambda or stream-based change events
- [ ] cache stampede protection
- [ ] hot-key and hot-tenant protection
- [ ] stale-answer policy by risk tier
- [ ] cache safety tests for auth and permissions
- [ ] model routing and provider fallback across Bedrock, SageMaker, approved external providers, or self-hosted models
- [ ] batching for embeddings, reranking, evals, and compatible model calls
- [ ] async queues for long-running agents, ingestion, evals, and retries
- [ ] vector DB sharding and hot-index replication
- [ ] API Gateway/service/tenant/model/tool rate limits
- [ ] backpressure and circuit breakers
- [ ] budget controls and cost anomaly alerts
- [ ] degraded modes for model, vector DB, tool, and region failures
- [ ] full-path load test including cache hit/miss ratios

AWS interview phrase:

> On AWS, I would not claim prompt caching handles billion-scale AI. I would use a layered cache strategy across prompt, semantic response, retrieval, embedding, reranking, and tools; scope every cache by tenant, permissions, freshness, and version; then combine it with API Gateway throttling, SQS/Step Functions queues, regional cells, vector DB sharding, model routing/fallback, backpressure, budget controls, degraded modes, and full-path observability.

AWS reference anchors:

- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html
- Amazon Bedrock Knowledge Bases: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
- Amazon OpenSearch Service: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html
- Amazon ElastiCache: https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/WhatIs.html
- Amazon SQS: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html
- Amazon CloudFront: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html

---

# 3. Vector Database Partitioning and Sharding

Partitioning decides how data is logically divided. Sharding decides how partitions are physically distributed across nodes or indexes. In practice, vector systems use both.

## Partitioning Strategies

| Strategy | Use When | Tradeoff |
|---|---|---|
| tenant partitioning | SaaS and enterprise multi-tenancy | strong isolation, but small tenants may waste capacity |
| domain partitioning | HR, finance, support, engineering corpora | better relevance and ownership, but cross-domain queries need fanout |
| time partitioning | news, tickets, logs, fast-changing knowledge | easy freshness and archival, but historical queries need multiple partitions |
| geography partitioning | data residency or latency requirements | compliance and latency benefits, but replication complexity |
| risk/sensitivity partitioning | PII, legal, finance, confidential docs | better policy enforcement, but more routing complexity |
| embedding-version partitioning | blue-green reindexing | safer migrations, but temporary storage duplication |
| modality partitioning | text, image, audio, video vectors | model-specific indexes, but query planner must route by modality |
| hot/cold partitioning | frequently accessed vs archival docs | lower cost, but recall can drop if planner ignores cold data |

## Sharding Strategies

| Strategy | How It Works | Best For |
|---|---|---|
| hash sharding | hash document/chunk ID across shards | even distribution, simple routing |
| tenant sharding | map tenants to shards/cells | tenant isolation and quotas |
| range/time sharding | route by date/version range | time-series knowledge, logs, tickets |
| semantic/domain sharding | route by topic/domain | strong relevance and ownership |
| hybrid sharding | tenant/domain first, hash inside partition | large enterprise multi-tenant systems |

## Query Routing Patterns

| Pattern | Description |
|---|---|
| single-shard lookup | route query to one tenant/domain shard |
| fanout query | search multiple shards then merge results |
| two-stage routing | classify intent/domain first, then query selected shards |
| hierarchical retrieval | retrieve from metadata/catalog first, then search child shards |
| federated retrieval | combine vector DB, keyword engine, SQL, graph DB, and external APIs |

## Sharding Risks

- uneven tenant size causes hot shards
- fanout increases p95/p99 latency
- local top-k per shard can miss globally relevant documents
- metadata filters may become slow if not indexed per shard
- rebalancing can reduce recall during migration
- duplicated replicas increase cost
- cross-shard consistency is hard during incremental ingestion
- backup and restore must preserve tenant/index/version metadata

## Architect Pattern for Vector Scale

```text
Query
  -> authenticate user
  -> compute tenant and permission scope
  -> classify domain/risk/freshness need
  -> select index partitions/shards
  -> check permission-aware retrieval cache
  -> run vector + keyword retrieval
  -> merge and deduplicate candidates
  -> rerank globally
  -> verify ACLs again before context assembly
  -> cite only permitted sources
```

## Interview-Grade Sharding Answer

> I shard vector search by tenant, domain, or time depending on isolation and query patterns. For large SaaS systems I prefer tenant/cell routing with replicas for hot tenants and fanout only when needed. I measure recall after sharding because local top-k per shard can reduce global recall.

---

# 4. Multi-Tenant Vector Index Design

| Pattern | Description | Best For | Risk |
|---|---|---|---|
| shared index + tenant filter | all tenants share one index with tenant metadata filter | small tenants, low ops overhead | filter bug can leak data |
| namespace per tenant | one logical namespace per tenant | medium SaaS isolation | many namespaces can be operationally heavy |
| index per tenant | separate index per tenant | regulated or large tenants | high cost and lifecycle complexity |
| cluster/cell per tenant group | groups of tenants assigned to isolated cells | large SaaS platforms | routing and migration complexity |
| dedicated deployment | separate stack for one customer | strict compliance or data residency | highest cost |

Enterprise default:

- small tenants: shared index with mandatory tenant filter and negative tests
- medium tenants: namespace or logical partition
- large/high-risk tenants: dedicated index or cell
- regulated customers: dedicated region/deployment when required

---

# 5. Vector Index Lifecycle

## Blue-Green Reindexing

Use blue-green index migration when changing:

- embedding model
- vector dimensions
- chunking strategy
- parser/OCR pipeline
- metadata schema
- distance metric
- ANN algorithm or parameters

Flow:

```text
current index: blue
new index: green
  -> backfill green from source of truth
  -> run retrieval regression evals
  -> compare recall, latency, cost, and citation quality
  -> shadow traffic to green
  -> canary tenants to green
  -> promote green
  -> retain blue for rollback window
```

## Index Version Metadata

Track:

- index ID
- owner/team
- source corpus
- embedding model/version/dimension
- chunking version
- parser version
- metadata schema version
- ANN algorithm and parameters
- creation date
- freshness watermark
- eval score
- rollback index

---

# 6. HNSW, IVF, and Partitioning Gotchas

## HNSW at Scale

- HNSW gives strong recall but uses memory heavily.
- Each shard has its own graph; global recall depends on routing and merge strategy.
- Increasing `ef_search` improves recall but increases latency.
- Increasing `ef_construction` improves graph quality but slows indexing.
- Replicas improve read throughput but not write throughput.

## IVF at Scale

- IVF partitions vector space into coarse clusters.
- `nlist` controls number of clusters; `nprobe` controls how many clusters are searched.
- Too few probes reduces recall; too many probes increases latency.
- IVF can be efficient for very large indexes but needs tuning on real queries.

## Quantization

- Product/scalar quantization reduces memory and cost.
- It can reduce recall, especially for subtle semantic differences.
- Always compare quantized vs unquantized recall on golden retrieval data.

---

# 7. Ingestion Scaling and Partitioned Pipelines

Production RAG fails if ingestion cannot keep knowledge fresh.

## Scalable Ingestion Flow

```text
source connector
  -> change event / CDC / scheduled sync
  -> idempotent ingestion job
  -> parse/OCR/table extraction
  -> clean and normalize
  -> metadata and ACL enrichment
  -> PII/sensitivity classification
  -> chunk
  -> embedding batch
  -> write to partitioned vector index
  -> write to keyword index
  -> update metadata DB
  -> emit freshness/eval event
```

## Pipeline Design Rules

- use idempotency keys per document version
- separate parse, chunk, embed, and index jobs
- use queues and backpressure for bursty syncs
- batch embeddings for throughput and cost
- use dead-letter queues for broken documents
- preserve source document lineage
- propagate deletes and permission changes quickly
- monitor source freshness SLAs
- run retrieval regression after major index updates

---

# 8. Metadata Partitioning and Filtering

Vector similarity is not enough. Enterprise retrieval usually depends on metadata filters.

Important metadata fields:

- tenant ID
- document ID and version
- source system
- source URL
- owner/team
- created/updated time
- freshness watermark
- region/data residency
- language
- document type
- sensitivity level
- ACL or permission groups
- embedding model version
- chunking version
- parent section/page
- deletion status

Filter design rules:

- apply hard ACL filters before context assembly
- index high-cardinality fields carefully
- avoid relying on prompt instructions for authorization
- test negative access cases continuously
- keep metadata in sync with source systems
- design for permission revocation latency

---

# 9. Scale Testing Checklist

Test the whole retrieval path, not only raw vector QPS.

- [ ] auth and tenant routing latency
- [ ] policy/ACL filter latency
- [ ] prompt/prefix cache hit rate
- [ ] semantic response cache hit rate
- [ ] retrieval cache hit rate
- [ ] embedding cache hit rate
- [ ] reranker cache hit rate
- [ ] tool-result cache hit rate
- [ ] vector search p50/p95/p99
- [ ] keyword search p50/p95/p99
- [ ] hybrid merge latency
- [ ] reranker latency and cost
- [ ] cache hit rate under realistic traffic
- [ ] cache stampede behavior
- [ ] hot-key behavior
- [ ] stale-answer policy behavior
- [ ] fanout query latency across shards
- [ ] hot tenant behavior
- [ ] index update throughput
- [ ] delete propagation latency
- [ ] permission revocation latency
- [ ] recall@k before and after sharding
- [ ] citation precision after partitioning
- [ ] failover to replicas
- [ ] backup and restore drill
- [ ] cross-tenant leakage negative tests

---

# 10. Design Decision Guide

| Problem | Prefer |
|---|---|
| many small tenants | shared index with mandatory tenant filter or namespaces |
| few large tenants | dedicated indexes or tenant cells |
| strict data residency | region-based partitions or dedicated deployments |
| fast-changing knowledge | time/version partitions and incremental sync |
| high read QPS | read replicas, retrieval cache, semantic cache |
| high write/update rate | async ingestion, batch embeddings, index partitioning |
| hot tenants | cell isolation, dedicated replicas, tenant-specific budgets |
| compliance-sensitive data | sensitivity partitions, strict ACLs, audit logs |
| expensive model calls | prompt cache, semantic cache, routing, smaller models |
| stale answers | freshness-aware retrieval and cache invalidation |

## Final Architect Statement

> At enterprise scale, retrieval architecture is a distributed systems problem. I design partitioning, sharding, caching, ingestion, ACLs, freshness, observability, and evals together, then validate that scale optimizations did not reduce recall, citation quality, tenant isolation, or safety.
