# Problem 127: Design a Vector Database (like Pinecone/Milvus/Weaviate)

## Problem Statement

Design a purpose-built Vector Database that efficiently stores, indexes, and queries high-dimensional vector embeddings for AI/ML applications such as semantic search, recommendation systems, and RAG pipelines.

## Key Challenges

### Approximate Nearest Neighbor (ANN) Search
- HNSW (Hierarchical Navigable Small World) graphs
- IVF (Inverted File Index) with product quantization
- Trade-offs between recall, latency, and memory usage
- Supporting multiple distance metrics (cosine, L2, dot product)

### Real-Time Index Updates
- Inserting vectors without full index rebuild
- Maintaining search quality during concurrent writes
- Handling deletions efficiently (tombstones vs compaction)
- Balancing freshness vs query performance

### Hybrid Search
- Combining vector similarity with metadata filtering
- Pre-filtering vs post-filtering trade-offs
- Integrated filtering during ANN traversal
- Supporting complex filter expressions (AND/OR/NOT)

### Sharding Strategies
- Partitioning high-dimensional data effectively
- Avoiding hot spots with uniform query distribution
- Cross-shard query aggregation and result merging
- Rebalancing shards as data grows

### Consistency for Concurrent Writes
- Read-after-write consistency for vector updates
- Handling concurrent upserts to the same vector ID
- Index consistency during compaction/rebuild

### Multi-Tenancy
- Namespace/collection isolation per tenant
- Preventing noisy neighbor effects on query latency
- Per-tenant resource limits and billing

### Quantization for Memory Efficiency
- Scalar quantization (FP32 → INT8)
- Product quantization (PQ) for compression
- Binary quantization for ultra-fast distance computation
- Rescoring with full precision vectors

## Scale Requirements

- 1 billion+ vectors stored
- Vector dimensions: 128 to 4096
- Query latency: <10ms at p99
- Query throughput: 100,000+ QPS
- Write throughput: 50,000+ vectors/second
- 99.99% availability

## Expected Output

Provide a complete system design covering index structures, distributed architecture, hybrid search implementation, and memory optimization strategies.
