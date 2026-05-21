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

---


## Link To Added Deep Dive

For deeper treatment of caching, vector DB sharding, partitioning, hot/cold indexes, multi-tenant index design, ingestion scaling, and scale tests, continue with `13-enterprise-scale-deep-dives-caching-sharding-partitioning.md`.
