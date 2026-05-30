"""
Embedding Model Migration - Blue-green reindexing workflow.

Features:
- Blue-green reindexing (zero-downtime migration)
- Parallel embedding generation (old + new model)
- Recall comparison (old vs new on same queries)
- Gradual traffic migration
- Rollback capability
- Version metadata tracking
- Migration monitoring
- Post-migration validation
- Cost estimation
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Types & Configuration
# =============================================================================

class MigrationState(Enum):
    PLANNED = "planned"
    EMBEDDING_IN_PROGRESS = "embedding_in_progress"
    EVALUATION = "evaluation"
    SHADOW_TRAFFIC = "shadow_traffic"
    GRADUAL_ROLLOUT = "gradual_rollout"
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"


@dataclass
class EmbeddingModelVersion:
    version_id: str
    model_name: str
    provider: str
    dimensions: int
    config: dict
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "inactive"
    eval_metrics: dict = field(default_factory=dict)
    document_count: int = 0
    index_name: str = ""

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "model_name": self.model_name,
            "provider": self.provider,
            "dimensions": self.dimensions,
            "config": self.config,
            "created_at": self.created_at,
            "status": self.status,
            "eval_metrics": self.eval_metrics,
            "document_count": self.document_count,
            "index_name": self.index_name,
        }


@dataclass
class MigrationPlan:
    migration_id: str
    source_version: EmbeddingModelVersion
    target_version: EmbeddingModelVersion
    state: MigrationState = MigrationState.PLANNED
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    rollback_deadline: Optional[str] = None
    traffic_percentage: float = 0.0  # % traffic going to new model
    batch_size: int = 1000
    parallel_workers: int = 4
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    documents_processed: int = 0
    total_documents: int = 0
    errors: list = field(default_factory=list)


# =============================================================================
# Vector Store Interface (Abstract)
# =============================================================================

class VectorStoreInterface:
    """Abstract interface for vector databases (Pinecone, Qdrant, Weaviate, etc.)."""

    async def create_collection(self, name: str, dimensions: int, **kwargs):
        raise NotImplementedError

    async def insert_batch(self, collection: str, ids: list[str], vectors: list[list[float]], metadata: list[dict]):
        raise NotImplementedError

    async def search(self, collection: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
        raise NotImplementedError

    async def delete_collection(self, name: str):
        raise NotImplementedError

    async def collection_info(self, name: str) -> dict:
        raise NotImplementedError

    async def count(self, name: str) -> int:
        raise NotImplementedError


class MockVectorStore(VectorStoreInterface):
    """In-memory mock for demonstration."""

    def __init__(self):
        self._collections: dict[str, dict] = {}

    async def create_collection(self, name: str, dimensions: int, **kwargs):
        self._collections[name] = {"dimensions": dimensions, "vectors": {}, "metadata": {}}

    async def insert_batch(self, collection: str, ids: list[str], vectors: list[list[float]], metadata: list[dict]):
        col = self._collections[collection]
        for id_, vec, meta in zip(ids, vectors, metadata):
            col["vectors"][id_] = np.array(vec)
            col["metadata"][id_] = meta

    async def search(self, collection: str, query_vector: list[float], top_k: int = 10) -> list[dict]:
        col = self._collections[collection]
        q = np.array(query_vector)
        scores = []
        for id_, vec in col["vectors"].items():
            score = np.dot(q, vec)
            scores.append({"id": id_, "score": float(score), "metadata": col["metadata"][id_]})
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    async def delete_collection(self, name: str):
        self._collections.pop(name, None)

    async def collection_info(self, name: str) -> dict:
        col = self._collections.get(name, {})
        return {"name": name, "count": len(col.get("vectors", {})), "dimensions": col.get("dimensions")}

    async def count(self, name: str) -> int:
        return len(self._collections.get(name, {}).get("vectors", {}))


# =============================================================================
# Cost Estimator
# =============================================================================

class MigrationCostEstimator:
    """Estimate costs for embedding migration."""

    # Cost per 1M tokens by provider/model
    COST_TABLE = {
        "text-embedding-3-large": 0.13,
        "text-embedding-3-small": 0.02,
        "embed-english-v3.0": 0.10,
        "embed-multilingual-v3.0": 0.10,
        "voyage-large-2": 0.12,
        "voyage-code-2": 0.12,
    }

    @classmethod
    def estimate(
        cls,
        model_name: str,
        total_documents: int,
        avg_tokens_per_doc: int = 200,
    ) -> dict:
        cost_per_million = cls.COST_TABLE.get(model_name, 0.0)
        total_tokens = total_documents * avg_tokens_per_doc
        embedding_cost = (total_tokens / 1_000_000) * cost_per_million

        # Estimate time based on rate limits (~5000 RPM for most providers)
        batches = total_documents / 100  # batch size 100
        minutes_at_rate_limit = batches / 3000  # conservative RPM
        hours = minutes_at_rate_limit / 60

        return {
            "model": model_name,
            "total_documents": total_documents,
            "total_tokens_estimate": total_tokens,
            "embedding_cost_usd": round(embedding_cost, 2),
            "estimated_hours": round(hours, 2),
            "cost_per_million_tokens": cost_per_million,
            "note": "Self-hosted models have $0 API cost but require GPU compute.",
        }


# =============================================================================
# Migration Engine
# =============================================================================

class EmbeddingMigrationEngine:
    """
    Orchestrates blue-green embedding migration.

    Workflow:
    1. Create new collection (green)
    2. Generate embeddings with new model in batches
    3. Run evaluation comparing old vs new
    4. If new is better: gradual traffic shift
    5. If new is worse: rollback
    6. After rollback window: delete old collection
    """

    def __init__(
        self,
        vector_store: VectorStoreInterface,
        embed_fn_old,  # async fn(texts) -> embeddings
        embed_fn_new,  # async fn(texts) -> embeddings
        document_source,  # async iterator yielding (doc_id, text, metadata)
    ):
        self._store = vector_store
        self._embed_old = embed_fn_old
        self._embed_new = embed_fn_new
        self._doc_source = document_source
        self._plan: Optional[MigrationPlan] = None
        self._state_file = "migration_state.json"

    async def plan_migration(
        self,
        source_version: EmbeddingModelVersion,
        target_version: EmbeddingModelVersion,
        total_documents: int,
    ) -> MigrationPlan:
        """Create a migration plan with cost estimation."""
        cost_estimate = MigrationCostEstimator.estimate(
            target_version.model_name, total_documents
        )

        self._plan = MigrationPlan(
            migration_id=f"mig_{int(time.time())}",
            source_version=source_version,
            target_version=target_version,
            total_documents=total_documents,
            estimated_cost_usd=cost_estimate["embedding_cost_usd"],
            rollback_deadline=(datetime.utcnow() + timedelta(days=14)).isoformat(),
        )

        logger.info(f"Migration plan created: {self._plan.migration_id}")
        logger.info(f"  Source: {source_version.model_name} ({source_version.index_name})")
        logger.info(f"  Target: {target_version.model_name}")
        logger.info(f"  Documents: {total_documents:,}")
        logger.info(f"  Estimated cost: ${cost_estimate['embedding_cost_usd']:.2f}")
        logger.info(f"  Estimated time: {cost_estimate['estimated_hours']:.1f} hours")

        self._save_state()
        return self._plan

    async def execute_migration(self):
        """Execute the full migration workflow."""
        if not self._plan:
            raise ValueError("No migration plan. Call plan_migration() first.")

        try:
            # Phase 1: Create new collection
            await self._phase_create_collection()

            # Phase 2: Generate embeddings
            await self._phase_generate_embeddings()

            # Phase 3: Evaluate
            await self._phase_evaluate()

            # Phase 4: Gradual traffic shift
            await self._phase_gradual_rollout()

            # Phase 5: Complete
            await self._phase_complete()

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self._plan.errors.append(str(e))
            await self.rollback()
            raise

    async def _phase_create_collection(self):
        """Create the target (green) collection."""
        self._plan.state = MigrationState.EMBEDDING_IN_PROGRESS
        self._plan.started_at = datetime.utcnow().isoformat()

        target = self._plan.target_version
        target.index_name = f"docs_v{target.version_id}_{target.model_name.replace('-', '_')}"

        logger.info(f"Creating collection: {target.index_name}")
        await self._store.create_collection(
            name=target.index_name,
            dimensions=target.dimensions,
        )
        self._save_state()

    async def _phase_generate_embeddings(self):
        """Generate embeddings with new model for all documents."""
        logger.info("Phase 2: Generating embeddings with new model...")

        batch_ids = []
        batch_texts = []
        batch_metadata = []
        processed = 0

        async for doc_id, text, metadata in self._doc_source:
            batch_ids.append(doc_id)
            batch_texts.append(text)
            batch_metadata.append(metadata)

            if len(batch_ids) >= self._plan.batch_size:
                await self._embed_and_insert_batch(batch_ids, batch_texts, batch_metadata)
                processed += len(batch_ids)
                self._plan.documents_processed = processed

                if processed % 10000 == 0:
                    logger.info(f"  Progress: {processed:,}/{self._plan.total_documents:,}")
                    self._save_state()

                batch_ids, batch_texts, batch_metadata = [], [], []

        # Final batch
        if batch_ids:
            await self._embed_and_insert_batch(batch_ids, batch_texts, batch_metadata)
            self._plan.documents_processed += len(batch_ids)

        logger.info(f"Embedding complete: {self._plan.documents_processed:,} documents")
        self._save_state()

    async def _embed_and_insert_batch(self, ids: list[str], texts: list[str], metadata: list[dict]):
        """Embed a batch and insert into target collection."""
        embeddings = await self._embed_new(texts)
        await self._store.insert_batch(
            collection=self._plan.target_version.index_name,
            ids=ids,
            vectors=embeddings,
            metadata=metadata,
        )

    async def _phase_evaluate(self):
        """Compare retrieval quality: old model vs new model."""
        self._plan.state = MigrationState.EVALUATION
        logger.info("Phase 3: Evaluating new model vs old model...")

        # Use a set of evaluation queries
        eval_queries = await self._get_eval_queries()

        old_scores = []
        new_scores = []

        for query_text, relevant_docs in eval_queries:
            # Embed query with both models
            old_query_emb = (await self._embed_old([query_text]))[0]
            new_query_emb = (await self._embed_new([query_text]))[0]

            # Search both collections
            old_results = await self._store.search(
                self._plan.source_version.index_name, old_query_emb, top_k=10
            )
            new_results = await self._store.search(
                self._plan.target_version.index_name, new_query_emb, top_k=10
            )

            # Compute recall@10
            old_retrieved = set(r["id"] for r in old_results)
            new_retrieved = set(r["id"] for r in new_results)
            relevant_set = set(relevant_docs)

            old_recall = len(old_retrieved & relevant_set) / max(len(relevant_set), 1)
            new_recall = len(new_retrieved & relevant_set) / max(len(relevant_set), 1)

            old_scores.append(old_recall)
            new_scores.append(new_recall)

        # Compare
        old_mean = np.mean(old_scores)
        new_mean = np.mean(new_scores)
        improvement = (new_mean - old_mean) / max(old_mean, 0.001)

        self._plan.target_version.eval_metrics = {
            "recall_at_10": float(new_mean),
            "old_recall_at_10": float(old_mean),
            "improvement_pct": float(improvement * 100),
            "num_eval_queries": len(eval_queries),
        }

        logger.info(f"  Old model recall@10: {old_mean:.4f}")
        logger.info(f"  New model recall@10: {new_mean:.4f}")
        logger.info(f"  Improvement: {improvement*100:.1f}%")

        # Gate: only proceed if new model is better or within tolerance
        if new_mean < old_mean * 0.95:  # More than 5% regression
            raise ValueError(
                f"New model is significantly worse: {new_mean:.4f} vs {old_mean:.4f}. "
                f"Aborting migration."
            )

        self._save_state()

    async def _phase_gradual_rollout(self):
        """Gradually shift traffic from old to new model."""
        self._plan.state = MigrationState.GRADUAL_ROLLOUT
        logger.info("Phase 4: Gradual traffic rollout...")

        traffic_steps = [10, 25, 50, 75, 100]
        for pct in traffic_steps:
            self._plan.traffic_percentage = pct
            logger.info(f"  Traffic to new model: {pct}%")
            self._save_state()

            # In production, you'd wait and monitor here
            # Simulate monitoring period
            await asyncio.sleep(0.1)  # In reality: hours/days

            # Check for anomalies (latency spike, error rate, user complaints)
            if await self._check_health():
                continue
            else:
                logger.warning(f"Health check failed at {pct}% traffic. Rolling back.")
                await self.rollback()
                return

        logger.info("Gradual rollout complete: 100% traffic on new model")

    async def _phase_complete(self):
        """Finalize migration."""
        self._plan.state = MigrationState.COMPLETED
        self._plan.completed_at = datetime.utcnow().isoformat()
        self._plan.target_version.status = "active"
        self._plan.source_version.status = "deprecated"

        logger.info(f"Migration {self._plan.migration_id} COMPLETED")
        logger.info(f"  New active index: {self._plan.target_version.index_name}")
        logger.info(f"  Rollback available until: {self._plan.rollback_deadline}")
        self._save_state()

    async def rollback(self):
        """Rollback to old model."""
        logger.warning("ROLLING BACK migration...")
        self._plan.state = MigrationState.ROLLED_BACK
        self._plan.traffic_percentage = 0

        # Delete the new collection
        try:
            await self._store.delete_collection(self._plan.target_version.index_name)
        except Exception as e:
            logger.error(f"Failed to delete new collection during rollback: {e}")

        self._plan.source_version.status = "active"
        self._plan.target_version.status = "rolled_back"
        self._save_state()
        logger.info("Rollback complete. Old model is serving all traffic.")

    async def _get_eval_queries(self) -> list[tuple[str, list[str]]]:
        """Load evaluation queries. Override for real implementation."""
        # Placeholder - in production, load from eval dataset file
        return [
            ("example query", ["doc_1", "doc_2"]),
        ]

    async def _check_health(self) -> bool:
        """Check system health during rollout. Override for real monitoring."""
        return True

    def _save_state(self):
        """Persist migration state for recovery."""
        state = {
            "migration_id": self._plan.migration_id,
            "state": self._plan.state.value,
            "source_version": self._plan.source_version.to_dict(),
            "target_version": self._plan.target_version.to_dict(),
            "traffic_percentage": self._plan.traffic_percentage,
            "documents_processed": self._plan.documents_processed,
            "total_documents": self._plan.total_documents,
            "started_at": self._plan.started_at,
            "errors": self._plan.errors,
        }
        Path(self._state_file).write_text(json.dumps(state, indent=2))


# =============================================================================
# Traffic Router
# =============================================================================

class EmbeddingTrafficRouter:
    """Routes queries between old and new embedding models during migration."""

    def __init__(self, store: VectorStoreInterface, embed_old, embed_new):
        self._store = store
        self._embed_old = embed_old
        self._embed_new = embed_new
        self._new_percentage = 0
        self._old_collection = ""
        self._new_collection = ""

    def configure(self, old_collection: str, new_collection: str, new_percentage: float):
        self._old_collection = old_collection
        self._new_collection = new_collection
        self._new_percentage = new_percentage

    async def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Route search to old or new model based on traffic percentage."""
        import random

        use_new = random.random() * 100 < self._new_percentage

        if use_new and self._new_collection:
            embedding = (await self._embed_new([query]))[0]
            results = await self._store.search(self._new_collection, embedding, top_k)
            for r in results:
                r["_model_version"] = "new"
        else:
            embedding = (await self._embed_old([query]))[0]
            results = await self._store.search(self._old_collection, embedding, top_k)
            for r in results:
                r["_model_version"] = "old"

        return results


# =============================================================================
# Migration Monitor
# =============================================================================

class MigrationMonitor:
    """Monitor migration health and generate dashboard data."""

    def __init__(self, state_file: str = "migration_state.json"):
        self._state_file = state_file

    def get_status(self) -> dict:
        """Get current migration status."""
        try:
            state = json.loads(Path(self._state_file).read_text())
        except FileNotFoundError:
            return {"status": "no_active_migration"}

        progress = 0
        if state["total_documents"] > 0:
            progress = state["documents_processed"] / state["total_documents"] * 100

        return {
            "migration_id": state["migration_id"],
            "state": state["state"],
            "progress_pct": round(progress, 1),
            "documents_processed": state["documents_processed"],
            "total_documents": state["total_documents"],
            "traffic_percentage_new": state["traffic_percentage"],
            "source_model": state["source_version"]["model_name"],
            "target_model": state["target_version"]["model_name"],
            "started_at": state.get("started_at"),
            "errors": state.get("errors", []),
        }

    def dashboard_summary(self) -> str:
        """Generate text dashboard."""
        status = self.get_status()
        if status.get("status") == "no_active_migration":
            return "No active migration."

        lines = [
            "=" * 60,
            "EMBEDDING MIGRATION DASHBOARD",
            "=" * 60,
            f"Migration ID: {status['migration_id']}",
            f"State:        {status['state']}",
            f"Source:       {status['source_model']}",
            f"Target:       {status['target_model']}",
            f"Progress:     {status['progress_pct']}% ({status['documents_processed']:,}/{status['total_documents']:,})",
            f"Traffic New:  {status['traffic_percentage_new']}%",
            f"Started:      {status['started_at']}",
            f"Errors:       {len(status['errors'])}",
            "=" * 60,
        ]
        return "\n".join(lines)


# =============================================================================
# Example Usage
# =============================================================================

async def example_migration():
    """Demonstrate embedding migration workflow."""

    # Setup
    store = MockVectorStore()

    # Create old collection with some data
    await store.create_collection("docs_v1_ada002", dimensions=1536)
    for i in range(100):
        vec = np.random.randn(1536).tolist()
        await store.insert_batch("docs_v1_ada002", [f"doc_{i}"], [vec], [{"text": f"doc {i}"}])

    # Define versions
    source = EmbeddingModelVersion(
        version_id="1",
        model_name="text-embedding-ada-002",
        provider="openai",
        dimensions=1536,
        config={},
        status="active",
        index_name="docs_v1_ada002",
    )
    target = EmbeddingModelVersion(
        version_id="2",
        model_name="text-embedding-3-large",
        provider="openai",
        dimensions=3072,
        config={"truncate_dim": 1024},
    )

    # Mock embedding functions
    async def embed_old(texts):
        return [np.random.randn(1536).tolist() for _ in texts]

    async def embed_new(texts):
        return [np.random.randn(1024).tolist() for _ in texts]

    # Mock document source
    async def doc_source():
        for i in range(100):
            yield f"doc_{i}", f"Document {i} with content", {"source": "test"}

    # Run migration
    engine = EmbeddingMigrationEngine(store, embed_old, embed_new, doc_source())

    plan = await engine.plan_migration(source, target, total_documents=100)
    print(f"Plan created: {plan.migration_id}")
    print(f"Estimated cost: ${plan.estimated_cost_usd:.2f}")

    # Cost estimation standalone
    cost = MigrationCostEstimator.estimate("text-embedding-3-large", 1_000_000)
    print(f"\nCost for 1M docs: ${cost['embedding_cost_usd']:.2f}")
    print(f"Estimated time: {cost['estimated_hours']:.1f} hours")

    # Monitor
    monitor = MigrationMonitor()
    print(monitor.dashboard_summary())


if __name__ == "__main__":
    asyncio.run(example_migration())
