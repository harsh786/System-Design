"""
Embedding Model Migration Simulator

Demonstrates zero-downtime blue-green migration from one embedding model
to another, including dual-write, background re-embedding, quality
comparison, and atomic switch.
"""

import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# --- Data Models ---

@dataclass
class Document:
    id: str
    text: str
    created_at: float = field(default_factory=time.time)


@dataclass
class VectorRecord:
    doc_id: str
    vector: np.ndarray
    model_version: str


@dataclass
class Collection:
    name: str
    model_version: str
    dimensions: int
    records: Dict[str, VectorRecord] = field(default_factory=dict)
    
    def upsert(self, doc_id: str, vector: np.ndarray):
        self.records[doc_id] = VectorRecord(doc_id, vector, self.model_version)
    
    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        scores = []
        for doc_id, record in self.records.items():
            sim = float(np.dot(query_vec, record.vector) / 
                       (np.linalg.norm(query_vec) * np.linalg.norm(record.vector) + 1e-10))
            scores.append((doc_id, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def count(self) -> int:
        return len(self.records)


# --- Simulated Embedding Models ---

class EmbeddingModelV1:
    """Simulates 'old' embedding model (e.g., text-embedding-ada-002)."""
    name = "text-embedding-ada-002"
    version = "v1"
    dimensions = 1536
    
    def embed(self, text: str) -> np.ndarray:
        np.random.seed(hash(text + "v1") % 2**31)
        vec = np.random.randn(self.dimensions)
        # Add semantic signal based on keywords
        words = text.lower().split()
        for i, word in enumerate(words[:20]):
            dim = hash(word) % self.dimensions
            vec[dim] += 1.0
        vec = vec / np.linalg.norm(vec)
        return vec


class EmbeddingModelV2:
    """Simulates 'new' embedding model (e.g., text-embedding-3-small) - slightly better."""
    name = "text-embedding-3-small"
    version = "v2"
    dimensions = 1536
    
    def embed(self, text: str) -> np.ndarray:
        np.random.seed(hash(text + "v2") % 2**31)
        vec = np.random.randn(self.dimensions)
        # Better semantic signal (more dimensions affected per word)
        words = text.lower().split()
        for i, word in enumerate(words[:20]):
            for offset in range(3):  # Richer representation
                dim = (hash(word) + offset * 7) % self.dimensions
                vec[dim] += 1.5
        vec = vec / np.linalg.norm(vec)
        return vec


# --- Migration Engine ---

class MigrationEngine:
    def __init__(self):
        self.model_v1 = EmbeddingModelV1()
        self.model_v2 = EmbeddingModelV2()
        self.old_collection = Collection("documents_v1", "v1", 1536)
        self.new_collection = Collection("documents_v2", "v2", 1536)
        self.active_collection = "documents_v1"
        self.documents: Dict[str, Document] = {}
        self.dual_write_enabled = False
        self.migration_progress = 0.0
        self.migrated_ids: set = set()
        self.events: List[str] = []
    
    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{timestamp}] {msg}")
        print(f"  [{timestamp}] {msg}")
    
    # --- Phase 1: Initial State ---
    
    def populate_initial_corpus(self, documents: List[Document]):
        """Populate the old collection with existing documents."""
        self.log(f"Populating old collection with {len(documents)} documents...")
        for doc in documents:
            self.documents[doc.id] = doc
            vec = self.model_v1.embed(doc.text)
            self.old_collection.upsert(doc.id, vec)
        self.log(f"Old collection ready: {self.old_collection.count()} documents")
    
    # --- Phase 2: Enable Dual-Write ---
    
    def enable_dual_write(self):
        """New documents get written to both collections."""
        self.dual_write_enabled = True
        self.log("Dual-write ENABLED - new documents go to both collections")
    
    def index_new_document(self, doc: Document):
        """Index a new document (respects dual-write setting)."""
        self.documents[doc.id] = doc
        
        # Always write to old collection
        vec_v1 = self.model_v1.embed(doc.text)
        self.old_collection.upsert(doc.id, vec_v1)
        
        # If dual-write, also write to new collection
        if self.dual_write_enabled:
            vec_v2 = self.model_v2.embed(doc.text)
            self.new_collection.upsert(doc.id, vec_v2)
            self.migrated_ids.add(doc.id)
    
    # --- Phase 3: Background Migration ---
    
    def run_background_migration(self, batch_size: int = 10):
        """Re-embed old documents into new collection."""
        unmigrated = [doc_id for doc_id in self.documents if doc_id not in self.migrated_ids]
        total = len(unmigrated)
        
        if total == 0:
            self.log("Migration complete - all documents in new collection")
            return
        
        self.log(f"Starting background migration: {total} documents remaining")
        
        batches = [unmigrated[i:i+batch_size] for i in range(0, total, batch_size)]
        
        for batch_num, batch in enumerate(batches):
            for doc_id in batch:
                doc = self.documents[doc_id]
                vec_v2 = self.model_v2.embed(doc.text)
                self.new_collection.upsert(doc_id, vec_v2)
                self.migrated_ids.add(doc_id)
            
            self.migration_progress = len(self.migrated_ids) / len(self.documents)
            
            if (batch_num + 1) % 5 == 0 or batch_num == len(batches) - 1:
                self.log(f"  Progress: {self.migration_progress*100:.0f}% "
                        f"({len(self.migrated_ids)}/{len(self.documents)})")
        
        self.log(f"Background migration complete: {self.new_collection.count()} documents")
    
    # --- Phase 4: Quality Comparison ---
    
    def compare_quality(self, test_queries: List[Tuple[str, List[str]]]) -> Dict:
        """Compare search quality between old and new collections."""
        self.log("Running quality comparison...")
        
        old_recalls = []
        new_recalls = []
        
        for query_text, relevant_ids in test_queries:
            # Search old collection
            q_v1 = self.model_v1.embed(query_text)
            old_results = self.old_collection.search(q_v1, top_k=5)
            old_retrieved = set(doc_id for doc_id, _ in old_results)
            old_recall = len(old_retrieved & set(relevant_ids)) / len(relevant_ids)
            old_recalls.append(old_recall)
            
            # Search new collection
            q_v2 = self.model_v2.embed(query_text)
            new_results = self.new_collection.search(q_v2, top_k=5)
            new_retrieved = set(doc_id for doc_id, _ in new_results)
            new_recall = len(new_retrieved & set(relevant_ids)) / len(relevant_ids)
            new_recalls.append(new_recall)
        
        results = {
            "old_recall": np.mean(old_recalls),
            "new_recall": np.mean(new_recalls),
            "improvement": np.mean(new_recalls) - np.mean(old_recalls),
            "new_is_better": np.mean(new_recalls) >= np.mean(old_recalls),
        }
        
        self.log(f"  Old model recall@5: {results['old_recall']:.3f}")
        self.log(f"  New model recall@5: {results['new_recall']:.3f}")
        self.log(f"  Improvement: {results['improvement']:+.3f}")
        
        return results
    
    # --- Phase 5: Switch ---
    
    def switch_to_new(self):
        """Atomic switch to new collection."""
        self.active_collection = "documents_v2"
        self.log("SWITCH: Traffic now served by new collection (documents_v2)")
    
    def rollback(self):
        """Rollback to old collection."""
        self.active_collection = "documents_v1"
        self.log("ROLLBACK: Traffic reverted to old collection (documents_v1)")
    
    # --- Search (respects active collection) ---
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Search using the currently active collection."""
        if self.active_collection == "documents_v1":
            q_vec = self.model_v1.embed(query)
            return self.old_collection.search(q_vec, top_k)
        else:
            q_vec = self.model_v2.embed(query)
            return self.new_collection.search(q_vec, top_k)
    
    # --- Status Report ---
    
    def print_status(self):
        print(f"\n  ┌{'─'*50}┐")
        print(f"  │ {'Migration Status':<48} │")
        print(f"  ├{'─'*50}┤")
        print(f"  │ {'Active collection:':<25} {self.active_collection:<23} │")
        print(f"  │ {'Old collection docs:':<25} {self.old_collection.count():<23} │")
        print(f"  │ {'New collection docs:':<25} {self.new_collection.count():<23} │")
        print(f"  │ {'Migration progress:':<25} {self.migration_progress*100:.0f}%{'':<20} │")
        print(f"  │ {'Dual-write:':<25} {'ON' if self.dual_write_enabled else 'OFF':<23} │")
        print(f"  └{'─'*50}┘")


# --- Main Demo ---

def main():
    print("=" * 70)
    print("Embedding Model Migration: Zero-Downtime Blue-Green Demo")
    print("=" * 70)
    
    engine = MigrationEngine()
    
    # --- Create initial corpus ---
    print("\n" + "─" * 70)
    print("PHASE 1: Initial State (Old model serving traffic)")
    print("─" * 70)
    
    initial_docs = [
        Document("doc_01", "machine learning algorithms for classification"),
        Document("doc_02", "deep neural network architectures overview"),
        Document("doc_03", "kubernetes deployment and scaling strategies"),
        Document("doc_04", "python data science libraries pandas numpy"),
        Document("doc_05", "natural language processing with transformers"),
        Document("doc_06", "sql database query optimization techniques"),
        Document("doc_07", "reinforcement learning reward function design"),
        Document("doc_08", "docker containerization best practices"),
        Document("doc_09", "cloud computing aws azure infrastructure"),
        Document("doc_10", "microservices communication patterns grpc rest"),
        Document("doc_11", "gradient descent optimization neural networks"),
        Document("doc_12", "transfer learning pretrained models fine tuning"),
        Document("doc_13", "graph neural networks for recommendation systems"),
        Document("doc_14", "devops ci cd pipeline automation"),
        Document("doc_15", "attention mechanism self attention cross attention"),
        Document("doc_16", "embedding models vector search similarity"),
        Document("doc_17", "distributed computing mapreduce spark"),
        Document("doc_18", "api gateway rate limiting authentication"),
        Document("doc_19", "message queue kafka rabbitmq event streaming"),
        Document("doc_20", "monitoring observability metrics logging tracing"),
    ]
    
    engine.populate_initial_corpus(initial_docs)
    engine.print_status()
    
    # Demonstrate search works
    print("\n  Search test (query: 'neural network training'):")
    results = engine.search("neural network training", top_k=3)
    for doc_id, score in results:
        print(f"    {doc_id}: score={score:.3f} - {engine.documents[doc_id].text[:50]}")
    
    # --- Enable dual-write ---
    print("\n" + "─" * 70)
    print("PHASE 2: Enable Dual-Write")
    print("─" * 70)
    
    engine.enable_dual_write()
    
    # Simulate new documents arriving
    new_docs = [
        Document("doc_21", "large language models gpt claude scaling laws"),
        Document("doc_22", "vector databases pinecone weaviate qdrant"),
        Document("doc_23", "rag retrieval augmented generation pipeline"),
    ]
    
    for doc in new_docs:
        engine.index_new_document(doc)
        engine.log(f"Indexed new doc: {doc.id} (dual-write to both collections)")
    
    engine.print_status()
    
    # --- Background migration ---
    print("\n" + "─" * 70)
    print("PHASE 3: Background Re-Embedding")
    print("─" * 70)
    
    engine.run_background_migration(batch_size=5)
    engine.print_status()
    
    # --- Quality comparison ---
    print("\n" + "─" * 70)
    print("PHASE 4: Quality Comparison")
    print("─" * 70)
    
    test_queries = [
        ("neural network deep learning", ["doc_02", "doc_11", "doc_15"]),
        ("kubernetes docker deployment", ["doc_03", "doc_08", "doc_14"]),
        ("natural language processing", ["doc_05", "doc_15", "doc_12"]),
        ("database optimization query", ["doc_06", "doc_17"]),
        ("machine learning model training", ["doc_01", "doc_12", "doc_07"]),
    ]
    
    quality = engine.compare_quality(test_queries)
    
    # --- Switch decision ---
    print("\n" + "─" * 70)
    print("PHASE 5: Switch Decision")
    print("─" * 70)
    
    if quality["new_is_better"]:
        engine.log("Quality check PASSED - new model is equal or better")
        engine.switch_to_new()
    else:
        engine.log("Quality check FAILED - keeping old model")
        engine.log("Investigation needed before migration")
    
    engine.print_status()
    
    # Demonstrate search still works after switch
    print("\n  Search test after switch (query: 'neural network training'):")
    results = engine.search("neural network training", top_k=3)
    for doc_id, score in results:
        print(f"    {doc_id}: score={score:.3f} - {engine.documents[doc_id].text[:50]}")
    
    # --- Cost summary ---
    print("\n" + "─" * 70)
    print("PHASE 6: Migration Report")
    print("─" * 70)
    
    num_docs = len(engine.documents)
    avg_tokens = 8  # Simulated average
    
    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │ MIGRATION REPORT                                    │
  ├─────────────────────────────────────────────────────┤
  │ Documents migrated:  {num_docs:<30}│
  │ Old model:           {engine.model_v1.name:<30}│
  │ New model:           {engine.model_v2.name:<30}│
  │ Dimensions:          {engine.model_v2.dimensions:<30}│
  ├─────────────────────────────────────────────────────┤
  │ QUALITY                                             │
  │ Old recall@5:        {quality['old_recall']:<30.3f}│
  │ New recall@5:        {quality['new_recall']:<30.3f}│
  │ Improvement:         {quality['improvement']:<+30.3f}│
  ├─────────────────────────────────────────────────────┤
  │ COST ESTIMATE (at production scale)                 │
  │                                                     │
  │ If 10M documents:                                   │
  │   Embedding cost:    $100 (at $0.02/1M tokens)      │
  │   Time:             ~56 min (at 3000/sec)           │
  │   Extra storage:     60GB during transition         │
  │   Storage cost:      $6 (for ~1 week)               │
  │   Total:            ~$106 + engineering time         │
  ├─────────────────────────────────────────────────────┤
  │ STATUS: {'COMPLETE - Using new model' if engine.active_collection == 'documents_v2' else 'PENDING - Still on old model':<38}│
  │ ROLLBACK: Available (old collection retained)       │
  └─────────────────────────────────────────────────────┘
""")
    
    print("  Timeline of events:")
    for event in engine.events:
        print(f"    {event}")


if __name__ == "__main__":
    main()
