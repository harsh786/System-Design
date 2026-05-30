"""
Unified Vector DB Client - Production Implementation
Supports: Qdrant, Pinecone, pgvector, Elasticsearch, FAISS
"""

import abc
import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────────────────────────────

class DistanceMetric(Enum):
    COSINE = "cosine"
    DOT_PRODUCT = "dot_product"
    EUCLIDEAN = "euclidean"


@dataclass
class VectorRecord:
    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    sparse_vector: Optional[dict[str, Any]] = None  # For hybrid search


@dataclass
class SearchResult:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    vector: Optional[list[float]] = None


@dataclass
class SearchRequest:
    vector: list[float]
    top_k: int = 10
    filter: Optional[dict[str, Any]] = None
    include_metadata: bool = True
    include_vectors: bool = False
    # Hybrid search
    query_text: Optional[str] = None
    alpha: float = 0.7  # Weight for vector vs keyword (1.0 = pure vector)


@dataclass
class CollectionConfig:
    name: str
    dimension: int
    metric: DistanceMetric = DistanceMetric.COSINE
    # HNSW params
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    # Quantization
    quantization: Optional[str] = None  # "scalar", "product", "binary"
    # Replication
    replication_factor: int = 1
    shard_count: int = 1


@dataclass
class HealthStatus:
    healthy: bool
    latency_ms: float
    details: dict[str, Any] = field(default_factory=dict)


# ─── Abstract Interface ────────────────────────────────────────────────────────

class VectorDBClient(abc.ABC):
    """Abstract interface for vector database operations."""

    @abc.abstractmethod
    async def create_collection(self, config: CollectionConfig) -> bool:
        """Create a collection/index with specified configuration."""
        ...

    @abc.abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """Delete a collection/index."""
        ...

    @abc.abstractmethod
    async def list_collections(self) -> list[str]:
        """List all collections."""
        ...

    @abc.abstractmethod
    async def insert(self, collection: str, records: list[VectorRecord]) -> int:
        """Insert/upsert records. Returns count of inserted records."""
        ...

    @abc.abstractmethod
    async def search(self, collection: str, request: SearchRequest) -> list[SearchResult]:
        """Search for similar vectors."""
        ...

    @abc.abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> int:
        """Delete records by IDs. Returns count deleted."""
        ...

    @abc.abstractmethod
    async def get(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        """Get records by IDs."""
        ...

    @abc.abstractmethod
    async def count(self, collection: str) -> int:
        """Count records in collection."""
        ...

    @abc.abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check database health."""
        ...

    # ─── Batch Operations ──────────────────────────────────────────────────

    async def batch_insert(
        self, collection: str, records: list[VectorRecord], batch_size: int = 100
    ) -> int:
        """Insert records in batches."""
        total = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            total += await self.insert(collection, batch)
        return total

    async def batch_search(
        self, collection: str, requests: list[SearchRequest]
    ) -> list[list[SearchResult]]:
        """Execute multiple searches (override for native batch support)."""
        results = []
        for req in requests:
            results.append(await self.search(collection, req))
        return results


# ─── Qdrant Implementation ─────────────────────────────────────────────────────

class QdrantClient(VectorDBClient):
    """Qdrant vector database client."""

    def __init__(self, url: str = "http://localhost:6333", api_key: Optional[str] = None):
        from qdrant_client import AsyncQdrantClient as _QdrantClient
        from qdrant_client.models import Distance

        self._client = _QdrantClient(url=url, api_key=api_key)
        self._distance_map = {
            DistanceMetric.COSINE: Distance.COSINE,
            DistanceMetric.DOT_PRODUCT: Distance.DOT,
            DistanceMetric.EUCLIDEAN: Distance.EUCLID,
        }

    async def create_collection(self, config: CollectionConfig) -> bool:
        from qdrant_client.models import (
            VectorParams,
            HnswConfigDiff,
            ScalarQuantization,
            ScalarQuantizationConfig,
            ScalarType,
            ProductQuantization,
            ProductQuantizationConfig,
            CompressionRatio,
        )

        hnsw_config = HnswConfigDiff(m=config.hnsw_m, ef_construct=config.hnsw_ef_construction)

        quantization_config = None
        if config.quantization == "scalar":
            quantization_config = ScalarQuantization(
                scalar=ScalarQuantizationConfig(type=ScalarType.INT8, always_ram=True)
            )
        elif config.quantization == "product":
            quantization_config = ProductQuantization(
                product=ProductQuantizationConfig(compression=CompressionRatio.X16, always_ram=True)
            )

        await self._client.create_collection(
            collection_name=config.name,
            vectors_config=VectorParams(
                size=config.dimension,
                distance=self._distance_map[config.metric],
            ),
            hnsw_config=hnsw_config,
            quantization_config=quantization_config,
            replication_factor=config.replication_factor,
            shard_number=config.shard_count,
        )
        return True

    async def delete_collection(self, name: str) -> bool:
        await self._client.delete_collection(name)
        return True

    async def list_collections(self) -> list[str]:
        collections = await self._client.get_collections()
        return [c.name for c in collections.collections]

    async def insert(self, collection: str, records: list[VectorRecord]) -> int:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(id=r.id, vector=r.vector, payload=r.metadata) for r in records
        ]
        await self._client.upsert(collection_name=collection, points=points)
        return len(points)

    async def search(self, collection: str, request: SearchRequest) -> list[SearchResult]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        query_filter = None
        if request.filter:
            conditions = []
            for key, value in request.filter.items():
                if isinstance(value, dict):
                    # Range filter: {"price": {"gte": 10, "lte": 100}}
                    conditions.append(FieldCondition(key=key, range=Range(**value)))
                else:
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            query_filter = Filter(must=conditions)

        results = await self._client.search(
            collection_name=collection,
            query_vector=request.vector,
            limit=request.top_k,
            query_filter=query_filter,
            with_payload=request.include_metadata,
            with_vectors=request.include_vectors,
        )

        return [
            SearchResult(
                id=str(r.id),
                score=r.score,
                metadata=r.payload or {},
                vector=r.vector if request.include_vectors else None,
            )
            for r in results
        ]

    async def delete(self, collection: str, ids: list[str]) -> int:
        from qdrant_client.models import PointIdsList

        await self._client.delete(
            collection_name=collection, points_selector=PointIdsList(points=ids)
        )
        return len(ids)

    async def get(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        points = await self._client.retrieve(collection_name=collection, ids=ids, with_vectors=True)
        return [
            VectorRecord(id=str(p.id), vector=p.vector, metadata=p.payload or {})
            for p in points
        ]

    async def count(self, collection: str) -> int:
        info = await self._client.get_collection(collection)
        return info.points_count or 0

    async def health_check(self) -> HealthStatus:
        start = time.time()
        try:
            await self._client.get_collections()
            return HealthStatus(healthy=True, latency_ms=(time.time() - start) * 1000)
        except Exception as e:
            return HealthStatus(healthy=False, latency_ms=(time.time() - start) * 1000, details={"error": str(e)})

    # ─── Qdrant-specific: Payload Index ────────────────────────────────────

    async def create_payload_index(self, collection: str, field: str, field_type: str = "keyword"):
        from qdrant_client.models import PayloadSchemaType

        schema_map = {
            "keyword": PayloadSchemaType.KEYWORD,
            "integer": PayloadSchemaType.INTEGER,
            "float": PayloadSchemaType.FLOAT,
            "geo": PayloadSchemaType.GEO,
            "datetime": PayloadSchemaType.DATETIME,
            "text": PayloadSchemaType.TEXT,
        }
        await self._client.create_payload_index(
            collection_name=collection,
            field_name=field,
            field_schema=schema_map[field_type],
        )


# ─── Pinecone Implementation ──────────────────────────────────────────────────

class PineconeClient(VectorDBClient):
    """Pinecone vector database client."""

    def __init__(self, api_key: str, environment: str = "us-east-1"):
        from pinecone import Pinecone

        self._pc = Pinecone(api_key=api_key)
        self._environment = environment
        self._indexes: dict[str, Any] = {}

    def _get_index(self, name: str):
        if name not in self._indexes:
            self._indexes[name] = self._pc.Index(name)
        return self._indexes[name]

    async def create_collection(self, config: CollectionConfig) -> bool:
        from pinecone import ServerlessSpec

        metric_map = {
            DistanceMetric.COSINE: "cosine",
            DistanceMetric.DOT_PRODUCT: "dotproduct",
            DistanceMetric.EUCLIDEAN: "euclidean",
        }
        self._pc.create_index(
            name=config.name,
            dimension=config.dimension,
            metric=metric_map[config.metric],
            spec=ServerlessSpec(cloud="aws", region=self._environment),
        )
        return True

    async def delete_collection(self, name: str) -> bool:
        self._pc.delete_index(name)
        self._indexes.pop(name, None)
        return True

    async def list_collections(self) -> list[str]:
        return [idx.name for idx in self._pc.list_indexes()]

    async def insert(self, collection: str, records: list[VectorRecord]) -> int:
        index = self._get_index(collection)
        vectors = [
            {
                "id": r.id,
                "values": r.vector,
                "metadata": r.metadata,
                **({"sparse_values": r.sparse_vector} if r.sparse_vector else {}),
            }
            for r in records
        ]
        index.upsert(vectors=vectors)
        return len(vectors)

    async def search(self, collection: str, request: SearchRequest) -> list[SearchResult]:
        index = self._get_index(collection)
        results = index.query(
            vector=request.vector,
            top_k=request.top_k,
            filter=request.filter,
            include_metadata=request.include_metadata,
            include_values=request.include_vectors,
        )
        return [
            SearchResult(
                id=m.id,
                score=m.score,
                metadata=m.metadata or {},
                vector=m.values if request.include_vectors else None,
            )
            for m in results.matches
        ]

    async def delete(self, collection: str, ids: list[str]) -> int:
        index = self._get_index(collection)
        index.delete(ids=ids)
        return len(ids)

    async def get(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        index = self._get_index(collection)
        result = index.fetch(ids=ids)
        return [
            VectorRecord(id=vid, vector=v.values, metadata=v.metadata or {})
            for vid, v in result.vectors.items()
        ]

    async def count(self, collection: str) -> int:
        index = self._get_index(collection)
        stats = index.describe_index_stats()
        return stats.total_vector_count

    async def health_check(self) -> HealthStatus:
        start = time.time()
        try:
            self._pc.list_indexes()
            return HealthStatus(healthy=True, latency_ms=(time.time() - start) * 1000)
        except Exception as e:
            return HealthStatus(healthy=False, latency_ms=(time.time() - start) * 1000, details={"error": str(e)})


# ─── pgvector Implementation ──────────────────────────────────────────────────

class PgvectorClient(VectorDBClient):
    """PostgreSQL + pgvector client."""

    def __init__(self, connection_string: str):
        self._conn_str = connection_string
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._conn_str, min_size=2, max_size=10)
            async with self._pool.acquire() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        return self._pool

    async def create_collection(self, config: CollectionConfig) -> bool:
        pool = await self._get_pool()
        metric_ops = {
            DistanceMetric.COSINE: "vector_cosine_ops",
            DistanceMetric.EUCLIDEAN: "vector_l2_ops",
            DistanceMetric.DOT_PRODUCT: "vector_ip_ops",
        }
        async with pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS "{config.name}" (
                    id TEXT PRIMARY KEY,
                    embedding vector({config.dimension}),
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Create HNSW index
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS "{config.name}_hnsw_idx"
                ON "{config.name}"
                USING hnsw (embedding {metric_ops[config.metric]})
                WITH (m = {config.hnsw_m}, ef_construction = {config.hnsw_ef_construction})
            """)
            # GIN index on metadata for filtering
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS "{config.name}_metadata_idx"
                ON "{config.name}" USING GIN (metadata)
            """)
        return True

    async def delete_collection(self, name: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f'DROP TABLE IF EXISTS "{name}" CASCADE')
        return True

    async def list_collections(self) -> list[str]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name NOT LIKE 'pg_%'
            """)
            return [r["table_name"] for r in rows]

    async def insert(self, collection: str, records: list[VectorRecord]) -> int:
        import json

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                f'INSERT INTO "{collection}" (id, embedding, metadata) VALUES ($1, $2, $3) '
                f"ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata",
                [(r.id, str(r.vector), json.dumps(r.metadata)) for r in records],
            )
        return len(records)

    async def search(self, collection: str, request: SearchRequest) -> list[SearchResult]:
        import json

        pool = await self._get_pool()
        # Build WHERE clause from filters
        where_clauses = []
        params = [str(request.vector), request.top_k]
        param_idx = 3

        if request.filter:
            for key, value in request.filter.items():
                if isinstance(value, dict):
                    for op, val in value.items():
                        sql_op = {"gte": ">=", "lte": "<=", "gt": ">", "lt": "<"}[op]
                        where_clauses.append(f"(metadata->>'{key}')::numeric {sql_op} ${param_idx}")
                        params.append(val)
                        param_idx += 1
                else:
                    where_clauses.append(f"metadata->>'{key}' = ${param_idx}")
                    params.append(str(value))
                    param_idx += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        async with pool.acquire() as conn:
            # Set ef_search for this query
            await conn.execute("SET hnsw.ef_search = 100")
            rows = await conn.fetch(
                f"""
                SELECT id, metadata, 1 - (embedding <=> $1::vector) AS score
                FROM "{collection}"
                {where_sql}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                *params,
            )
        return [
            SearchResult(id=r["id"], score=float(r["score"]), metadata=json.loads(r["metadata"]) if r["metadata"] else {})
            for r in rows
        ]

    async def delete(self, collection: str, ids: list[str]) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f'DELETE FROM "{collection}" WHERE id = ANY($1)', ids
            )
            return int(result.split()[-1])

    async def get(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        import json

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT id, embedding::text, metadata FROM "{collection}" WHERE id = ANY($1)', ids
            )
        return [
            VectorRecord(
                id=r["id"],
                vector=json.loads(r["embedding"]) if r["embedding"] else [],
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    async def count(self, collection: str) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f'SELECT COUNT(*) as cnt FROM "{collection}"')
            return row["cnt"]

    async def health_check(self) -> HealthStatus:
        start = time.time()
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.fetchrow("SELECT 1")
            return HealthStatus(healthy=True, latency_ms=(time.time() - start) * 1000)
        except Exception as e:
            return HealthStatus(healthy=False, latency_ms=(time.time() - start) * 1000, details={"error": str(e)})


# ─── Elasticsearch Implementation ─────────────────────────────────────────────

class ElasticsearchVectorClient(VectorDBClient):
    """Elasticsearch/OpenSearch vector client with hybrid search."""

    def __init__(self, hosts: list[str], api_key: Optional[str] = None):
        from elasticsearch import AsyncElasticsearch

        kwargs = {"hosts": hosts}
        if api_key:
            kwargs["api_key"] = api_key
        self._client = AsyncElasticsearch(**kwargs)

    async def create_collection(self, config: CollectionConfig) -> bool:
        metric_map = {
            DistanceMetric.COSINE: "cosine",
            DistanceMetric.DOT_PRODUCT: "dot_product",
            DistanceMetric.EUCLIDEAN: "l2_norm",
        }
        body = {
            "settings": {"number_of_shards": config.shard_count, "number_of_replicas": config.replication_factor - 1},
            "mappings": {
                "properties": {
                    "embedding": {
                        "type": "dense_vector",
                        "dims": config.dimension,
                        "index": True,
                        "similarity": metric_map[config.metric],
                        "index_options": {
                            "type": "hnsw",
                            "m": config.hnsw_m,
                            "ef_construction": config.hnsw_ef_construction,
                        },
                    },
                    "content": {"type": "text", "analyzer": "standard"},
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        }
        await self._client.indices.create(index=config.name, body=body)
        return True

    async def delete_collection(self, name: str) -> bool:
        await self._client.indices.delete(index=name, ignore=[404])
        return True

    async def list_collections(self) -> list[str]:
        indices = await self._client.indices.get(index="*")
        return [name for name in indices.keys() if not name.startswith(".")]

    async def insert(self, collection: str, records: list[VectorRecord]) -> int:
        actions = []
        for r in records:
            actions.append({"index": {"_index": collection, "_id": r.id}})
            doc = {"embedding": r.vector, "metadata": r.metadata}
            if "content" in r.metadata:
                doc["content"] = r.metadata["content"]
            actions.append(doc)

        from elasticsearch.helpers import async_bulk

        success, _ = await async_bulk(self._client, self._gen_actions(collection, records))
        return success

    @staticmethod
    def _gen_actions(collection: str, records: list[VectorRecord]):
        for r in records:
            doc = {"_index": collection, "_id": r.id, "embedding": r.vector, "metadata": r.metadata}
            if "content" in r.metadata:
                doc["content"] = r.metadata["content"]
            yield doc

    async def search(self, collection: str, request: SearchRequest) -> list[SearchResult]:
        # Build hybrid query if query_text provided
        if request.query_text and request.alpha < 1.0:
            # RRF (Reciprocal Rank Fusion) hybrid search
            body = {
                "size": request.top_k,
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"content": {"query": request.query_text, "boost": 1 - request.alpha}}},
                        ]
                    }
                },
                "knn": {
                    "field": "embedding",
                    "query_vector": request.vector,
                    "k": request.top_k,
                    "num_candidates": request.top_k * 10,
                    "boost": request.alpha,
                },
            }
        else:
            body = {
                "size": request.top_k,
                "knn": {
                    "field": "embedding",
                    "query_vector": request.vector,
                    "k": request.top_k,
                    "num_candidates": request.top_k * 10,
                },
            }

        # Add filters
        if request.filter:
            filter_clauses = []
            for key, value in request.filter.items():
                if isinstance(value, dict):
                    filter_clauses.append({"range": {f"metadata.{key}": value}})
                else:
                    filter_clauses.append({"term": {f"metadata.{key}": value}})
            if "knn" in body:
                body["knn"]["filter"] = {"bool": {"must": filter_clauses}}

        result = await self._client.search(index=collection, body=body)
        return [
            SearchResult(
                id=hit["_id"],
                score=hit["_score"],
                metadata=hit["_source"].get("metadata", {}),
            )
            for hit in result["hits"]["hits"]
        ]

    async def delete(self, collection: str, ids: list[str]) -> int:
        body = {"query": {"ids": {"values": ids}}}
        result = await self._client.delete_by_query(index=collection, body=body)
        return result.get("deleted", 0)

    async def get(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        result = await self._client.mget(index=collection, body={"ids": ids})
        records = []
        for doc in result["docs"]:
            if doc.get("found"):
                src = doc["_source"]
                records.append(VectorRecord(
                    id=doc["_id"],
                    vector=src.get("embedding", []),
                    metadata=src.get("metadata", {}),
                ))
        return records

    async def count(self, collection: str) -> int:
        result = await self._client.count(index=collection)
        return result["count"]

    async def health_check(self) -> HealthStatus:
        start = time.time()
        try:
            info = await self._client.cluster.health()
            return HealthStatus(
                healthy=info["status"] in ("green", "yellow"),
                latency_ms=(time.time() - start) * 1000,
                details={"status": info["status"], "nodes": info["number_of_nodes"]},
            )
        except Exception as e:
            return HealthStatus(healthy=False, latency_ms=(time.time() - start) * 1000, details={"error": str(e)})


# ─── FAISS Implementation ─────────────────────────────────────────────────────

class FAISSClient(VectorDBClient):
    """Local FAISS vector store (in-memory, no persistence by default)."""

    def __init__(self, persist_dir: Optional[str] = None):
        import faiss

        self._faiss = faiss
        self._persist_dir = persist_dir
        self._indexes: dict[str, faiss.Index] = {}
        self._metadata: dict[str, dict[str, dict]] = {}  # collection -> id -> metadata
        self._id_map: dict[str, list[str]] = {}  # collection -> [id_at_position]
        self._configs: dict[str, CollectionConfig] = {}

    async def create_collection(self, config: CollectionConfig) -> bool:
        if config.quantization == "product":
            # IVF + PQ
            nlist = max(1, int(np.sqrt(1000)))  # Will be rebuilt when data arrives
            quantizer = self._faiss.IndexFlatL2(config.dimension)
            m_sub = min(config.dimension, 96)  # Sub-quantizers
            index = self._faiss.IndexIVFPQ(quantizer, config.dimension, nlist, m_sub, 8)
        else:
            # HNSW
            index = self._faiss.IndexHNSWFlat(config.dimension, config.hnsw_m)
            index.hnsw.efConstruction = config.hnsw_ef_construction
            index.hnsw.efSearch = 128

        self._indexes[config.name] = index
        self._metadata[config.name] = {}
        self._id_map[config.name] = []
        self._configs[config.name] = config
        return True

    async def delete_collection(self, name: str) -> bool:
        self._indexes.pop(name, None)
        self._metadata.pop(name, None)
        self._id_map.pop(name, None)
        self._configs.pop(name, None)
        return True

    async def list_collections(self) -> list[str]:
        return list(self._indexes.keys())

    async def insert(self, collection: str, records: list[VectorRecord]) -> int:
        index = self._indexes[collection]
        vectors = np.array([r.vector for r in records], dtype=np.float32)

        # Train IVF if needed and not yet trained
        if hasattr(index, "is_trained") and not index.is_trained:
            index.train(vectors)

        start_pos = index.ntotal
        index.add(vectors)

        for i, r in enumerate(records):
            pos = start_pos + i
            self._id_map[collection].append(r.id)
            self._metadata[collection][r.id] = r.metadata

        return len(records)

    async def search(self, collection: str, request: SearchRequest) -> list[SearchResult]:
        index = self._indexes[collection]
        query = np.array([request.vector], dtype=np.float32)

        # Over-fetch if filtering (since FAISS doesn't support native filters)
        fetch_k = request.top_k * 10 if request.filter else request.top_k

        distances, indices = index.search(query, min(fetch_k, index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            record_id = self._id_map[collection][idx]
            metadata = self._metadata[collection].get(record_id, {})

            # Apply filter
            if request.filter:
                match = all(
                    metadata.get(k) == v for k, v in request.filter.items() if not isinstance(v, dict)
                )
                if not match:
                    continue

            results.append(SearchResult(id=record_id, score=float(1 / (1 + dist)), metadata=metadata))
            if len(results) >= request.top_k:
                break

        return results

    async def delete(self, collection: str, ids: list[str]) -> int:
        # FAISS doesn't support deletion natively - mark as deleted
        # In production, rebuild index periodically
        deleted = 0
        for id_ in ids:
            if id_ in self._metadata[collection]:
                del self._metadata[collection][id_]
                deleted += 1
        return deleted

    async def get(self, collection: str, ids: list[str]) -> list[VectorRecord]:
        results = []
        for id_ in ids:
            if id_ in self._metadata[collection]:
                idx = self._id_map[collection].index(id_)
                vector = self._indexes[collection].reconstruct(idx)
                results.append(VectorRecord(id=id_, vector=vector.tolist(), metadata=self._metadata[collection][id_]))
        return results

    async def count(self, collection: str) -> int:
        return self._indexes[collection].ntotal

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            healthy=True,
            latency_ms=0.0,
            details={"collections": len(self._indexes), "backend": "faiss_local"},
        )

    def save(self, collection: str, path: str):
        """Persist FAISS index to disk."""
        import json
        import os

        os.makedirs(path, exist_ok=True)
        self._faiss.write_index(self._indexes[collection], os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump({"metadata": self._metadata[collection], "id_map": self._id_map[collection]}, f)

    def load(self, collection: str, path: str):
        """Load FAISS index from disk."""
        import json
        import os

        self._indexes[collection] = self._faiss.read_index(os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "metadata.json")) as f:
            data = json.load(f)
            self._metadata[collection] = data["metadata"]
            self._id_map[collection] = data["id_map"]


# ─── Factory ───────────────────────────────────────────────────────────────────

class VectorDBFactory:
    """Factory to create vector DB clients from configuration."""

    @staticmethod
    def create(provider: str, **kwargs) -> VectorDBClient:
        providers = {
            "qdrant": QdrantClient,
            "pinecone": PineconeClient,
            "pgvector": PgvectorClient,
            "elasticsearch": ElasticsearchVectorClient,
            "faiss": FAISSClient,
        }
        if provider not in providers:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(providers.keys())}")
        return providers[provider](**kwargs)


# ─── Usage Example ─────────────────────────────────────────────────────────────

async def example_usage():
    """Demonstrates unified client usage."""
    # Create client
    client = VectorDBFactory.create("qdrant", url="http://localhost:6333")

    # Create collection
    config = CollectionConfig(
        name="documents",
        dimension=1536,
        metric=DistanceMetric.COSINE,
        hnsw_m=16,
        hnsw_ef_construction=200,
        quantization="scalar",
    )
    await client.create_collection(config)

    # Insert vectors
    records = [
        VectorRecord(
            id=f"doc_{i}",
            vector=[float(x) for x in np.random.randn(1536)],
            metadata={"category": "tech", "source": "arxiv", "year": 2024},
        )
        for i in range(100)
    ]
    await client.batch_insert("documents", records, batch_size=50)

    # Search with filter
    query_vector = [float(x) for x in np.random.randn(1536)]
    results = await client.search(
        "documents",
        SearchRequest(
            vector=query_vector,
            top_k=5,
            filter={"category": "tech", "year": {"gte": 2023}},
        ),
    )

    for r in results:
        print(f"  {r.id}: score={r.score:.4f}")

    # Health check
    health = await client.health_check()
    print(f"Health: {health.healthy}, latency: {health.latency_ms:.1f}ms")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
