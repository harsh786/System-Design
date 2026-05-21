# Vector and Data Scale Track: Vector Databases, Embeddings, and Index Design

**Learning level:** Core to advanced infrastructure  
**Outcome:** You can choose embedding models and vector databases based on measured retrieval quality, latency, filtering, update behavior, multi-tenancy, compliance, and operations.

---

# 5. Vector Databases and Embedding Models

## Vector Database Categories

| Category | Examples | Best For |
|---|---|---|
| managed vector DB | Pinecone | fast managed production |
| open-source vector DB | Qdrant, Weaviate, Milvus | control and self-hosting |
| relational vector search | pgvector, AlloyDB | existing relational apps |
| search engine with vectors | Elasticsearch, OpenSearch, Azure AI Search | hybrid enterprise search |
| local/embedded vector stores | FAISS, Chroma, LanceDB | prototypes and local apps |
| lakehouse vector layer | LanceDB-style patterns | large offline corpora |

## Vector Database Capability Matrix

Evaluate vector databases like production data systems, not just embedding stores.

| Capability | Why It Matters |
|---|---|
| ANN index support | HNSW, IVF, disk-based ANN, quantization tradeoffs |
| hybrid search | BM25/sparse + dense search in one retrieval plan |
| metadata filtering | tenant, ACL, freshness, region, document type, sensitivity |
| payload indexing | fast filters on high-cardinality metadata |
| multi-tenancy | namespaces, collections, partitions, dedicated indexes |
| update/delete behavior | freshness, right-to-delete, document versioning |
| consistency model | read-after-write expectations and ingestion correctness |
| backup/restore | recovery from index corruption or poisoning |
| replication | read scale, failover, regional resilience |
| sharding/rebalancing | large corpora and hot tenant management |
| observability | index health, recall proxy, latency, QPS, filter selectivity |
| security | encryption, IAM, network isolation, audit logs |
| ecosystem fit | connectors, SDKs, cloud, Kubernetes, data lake integration |

## Selection Criteria

- latency
- recall
- filtering performance
- hybrid search
- metadata scale
- indexing algorithm
- multi-tenancy
- update/delete speed
- backup/restore
- compliance
- cloud availability
- cost
- operational complexity

Selection questions:

- Is this a prototype, product feature, internal platform, or regulated enterprise system?
- Do you need hybrid search in the vector DB or in a separate search engine?
- Are tenants isolated by metadata, namespace, index, cluster, or region?
- What are p95/p99 latency and recall targets?
- How fast must updates, deletes, and permission revocations propagate?
- Can it restore a poisoned or corrupted index within the recovery objective?
- How will you run blue-green embedding/index migrations?
- How will you measure recall after sharding, quantization, and caching?

## Index Concepts

- HNSW
- IVFFlat
- PQ/product quantization
- scalar quantization
- vector dimensions
- cosine similarity
- dot product
- L2 distance
- recall vs latency
- sharding
- replication
- ef_search
- ef_construction
- probes

Additional index and storage concepts:

- disk-based ANN
- payload indexes
- filter pushdown
- segment compaction
- tombstones and delete propagation
- snapshotting
- hot/warm/cold storage
- namespace vs collection vs partition
- blue-green indexes
- read replicas
- shard rebalancing
- consistency and freshness watermarks

## Embedding Model Types

| Type | Use Case |
|---|---|
| general text embeddings | semantic search |
| multilingual embeddings | cross-language search |
| code embeddings | code search |
| domain embeddings | legal, medical, finance |
| multimodal embeddings | text and image retrieval |
| sparse embeddings | hybrid lexical/semantic retrieval |
| late-interaction embeddings | high-recall search |
| small embeddings | fast and cheap |
| large embeddings | higher quality and cost |

Embedding architecture choices:

| Choice | Architect Question |
|---|---|
| dense vs sparse | Do queries need semantic meaning, exact terms, or both? |
| single-vector vs late interaction | Is high recall worth more storage and reranking complexity? |
| small vs large dimension | Does quality improvement justify memory and latency cost? |
| general vs domain model | Does domain terminology fail with general embeddings? |
| multilingual model | Are queries and documents cross-language? |
| multimodal model | Are images, diagrams, screenshots, tables, or video part of retrieval? |
| normalized vectors | Does the chosen distance metric expect normalization? |
| embedding versioning | Can old and new embeddings coexist during migration? |

## Choosing Embeddings

Evaluate on your own data:

1. Create 200-1000 real queries.
2. Label relevant documents.
3. Test multiple embedding models.
4. Measure recall@k, MRR, nDCG.
5. Test multilingual and domain-specific queries.
6. Test metadata filtering.
7. Test latency and cost.
8. Test adversarial queries.

Benchmark slices:

- exact policy IDs, product codes, dates, and names
- paraphrased natural-language questions
- multi-hop questions
- no-answer questions
- stale document versions
- permission-sensitive queries
- multilingual queries
- table-heavy and scanned-document queries
- short vague queries
- adversarial or poisoned-source queries

Embedding migration rule:

> Treat an embedding model change like a schema migration. Track model, dimension, preprocessing, chunking version, distance metric, index version, and eval score; then run blue-green reindexing before switching traffic.

---


## Link To Added Deep Dive

For deeper treatment of caching, vector DB sharding, partitioning, hot/cold indexes, multi-tenant index design, ingestion scaling, and scale tests, continue with `13-enterprise-scale-deep-dives-caching-sharding-partitioning.md`.
