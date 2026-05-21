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

# 2. Vector Database Partitioning and Sharding

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

# 3. Multi-Tenant Vector Index Design

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

# 4. Vector Index Lifecycle

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

# 5. HNSW, IVF, and Partitioning Gotchas

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

# 6. Ingestion Scaling and Partitioned Pipelines

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

# 7. Metadata Partitioning and Filtering

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

# 8. Scale Testing Checklist

Test the whole retrieval path, not only raw vector QPS.

- [ ] auth and tenant routing latency
- [ ] policy/ACL filter latency
- [ ] vector search p50/p95/p99
- [ ] keyword search p50/p95/p99
- [ ] hybrid merge latency
- [ ] reranker latency and cost
- [ ] cache hit rate under realistic traffic
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

# 9. Design Decision Guide

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
