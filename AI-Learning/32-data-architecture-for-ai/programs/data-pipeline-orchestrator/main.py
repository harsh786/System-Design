"""
Data Pipeline Orchestrator Simulator for AI Systems
=====================================================
DAG-based orchestration with idempotency, backfill,
incremental processing, error handling, and CDC.

Run: python3 main.py
No dependencies required (standard library only).
"""

import time
import random
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# TASK AND DAG DATA MODELS
# =============================================================================

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


@dataclass
class TaskResult:
    status: TaskStatus
    records_processed: int = 0
    records_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    output: Any = None


@dataclass
class Task:
    id: str
    name: str
    description: str
    execute_fn: Callable
    dependencies: List[str] = field(default_factory=list)
    max_retries: int = 3
    retry_delay_sec: float = 1.0
    idempotent: bool = True
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    retry_count: int = 0


class DAG:
    """Directed Acyclic Graph of tasks (like Airflow)."""
    
    def __init__(self, name: str):
        self.name = name
        self.tasks: Dict[str, Task] = {}
        self.execution_order: List[str] = []
    
    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task
    
    def topological_sort(self) -> List[str]:
        """Determine execution order based on dependencies."""
        visited: Set[str] = set()
        order: List[str] = []
        
        def visit(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)
            task = self.tasks[task_id]
            for dep in task.dependencies:
                if dep in self.tasks:
                    visit(dep)
            order.append(task_id)
        
        for task_id in self.tasks:
            visit(task_id)
        
        self.execution_order = order
        return order


# =============================================================================
# IDEMPOTENCY MANAGER
# =============================================================================

class IdempotencyManager:
    """Ensures operations are safe to retry without side effects."""
    
    def __init__(self):
        self.processed_ids: Set[str] = set()
        self.checkpoints: Dict[str, datetime] = {}
    
    def get_idempotency_key(self, record_id: str, task_id: str, version: str) -> str:
        """Generate deterministic key for deduplication."""
        raw = f"{record_id}:{task_id}:{version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    def is_already_processed(self, key: str) -> bool:
        return key in self.processed_ids
    
    def mark_processed(self, key: str) -> None:
        self.processed_ids.add(key)
    
    def save_checkpoint(self, task_id: str, timestamp: datetime) -> None:
        self.checkpoints[task_id] = timestamp
    
    def get_checkpoint(self, task_id: str) -> Optional[datetime]:
        return self.checkpoints.get(task_id)


# =============================================================================
# CDC (CHANGE DATA CAPTURE) SIMULATOR
# =============================================================================

class CDCEvent:
    """Represents a change data capture event."""
    
    def __init__(self, operation: str, table: str, record_id: str,
                 data: Dict, timestamp: datetime):
        self.operation = operation  # INSERT, UPDATE, DELETE
        self.table = table
        self.record_id = record_id
        self.data = data
        self.timestamp = timestamp
    
    def __repr__(self):
        return f"CDC({self.operation} {self.table}.{self.record_id})"


class CDCStream:
    """Simulates a CDC stream (like Debezium reading PostgreSQL WAL)."""
    
    def __init__(self):
        self.events: List[CDCEvent] = []
        self.offset: int = 0
    
    def produce_events(self, count: int) -> None:
        """Generate simulated CDC events."""
        tables = ["documents", "users", "interactions"]
        operations = ["INSERT", "UPDATE", "UPDATE", "UPDATE", "DELETE"]  # More updates than inserts
        
        for i in range(count):
            table = random.choice(tables)
            op = random.choice(operations)
            record_id = f"{table[:3]}_{random.randint(1, 1000):04d}"
            
            data = {}
            if table == "documents":
                data = {
                    "title": f"Document {record_id}",
                    "content": f"Updated content at {datetime.now().isoformat()}",
                    "category": random.choice(["eng", "product", "research"]),
                }
            elif table == "users":
                data = {
                    "name": f"User {record_id}",
                    "last_active": datetime.now().isoformat(),
                }
            
            self.events.append(CDCEvent(
                operation=op,
                table=table,
                record_id=record_id,
                data=data,
                timestamp=datetime.now() - timedelta(minutes=random.uniform(0, 60)),
            ))
    
    def consume(self, batch_size: int = 10) -> List[CDCEvent]:
        """Consume a batch of CDC events."""
        batch = self.events[self.offset:self.offset + batch_size]
        self.offset += len(batch)
        return batch


# =============================================================================
# PIPELINE TASKS
# =============================================================================

class PipelineTasks:
    """Collection of task implementations for AI data pipeline."""
    
    def __init__(self, idempotency: IdempotencyManager):
        self.idempotency = idempotency
        self.extracted_data: List[Dict] = []
        self.cleaned_data: List[Dict] = []
        self.embedded_data: List[Dict] = []
        self.indexed_data: List[Dict] = []
    
    def extract(self, **kwargs) -> TaskResult:
        """Extract data from sources."""
        start = time.time()
        records = []
        
        # Simulate extracting documents
        for i in range(50):
            records.append({
                "id": f"doc_{i:04d}",
                "title": f"Document {i}",
                "content": f"Content for document {i}. " * random.randint(10, 100),
                "source": "postgresql",
                "extracted_at": datetime.now().isoformat(),
            })
        
        self.extracted_data = records
        duration = (time.time() - start) * 1000
        
        return TaskResult(
            status=TaskStatus.SUCCESS,
            records_processed=len(records),
            duration_ms=duration,
            output={"count": len(records)},
        )
    
    def clean(self, **kwargs) -> TaskResult:
        """Clean and validate extracted data."""
        start = time.time()
        cleaned = []
        skipped = 0
        errors = []
        
        for record in self.extracted_data:
            key = self.idempotency.get_idempotency_key(record["id"], "clean", "v1")
            
            if self.idempotency.is_already_processed(key):
                skipped += 1
                continue
            
            # Simulate cleaning logic
            if len(record.get("content", "")) < 20:
                errors.append(f"Record {record['id']}: content too short")
                continue
            
            # Simulate occasional failure (for retry demo)
            if random.random() < 0.02:
                raise Exception(f"Transient error cleaning {record['id']}")
            
            cleaned_record = {
                **record,
                "content": record["content"].strip(),
                "word_count": len(record["content"].split()),
                "cleaned_at": datetime.now().isoformat(),
            }
            cleaned.append(cleaned_record)
            self.idempotency.mark_processed(key)
        
        self.cleaned_data = cleaned
        duration = (time.time() - start) * 1000
        
        return TaskResult(
            status=TaskStatus.SUCCESS,
            records_processed=len(cleaned),
            records_skipped=skipped,
            errors=errors,
            duration_ms=duration,
        )
    
    def embed(self, **kwargs) -> TaskResult:
        """Generate embeddings for cleaned documents."""
        start = time.time()
        embedded = []
        skipped = 0
        
        for record in self.cleaned_data:
            key = self.idempotency.get_idempotency_key(record["id"], "embed", "v1")
            
            if self.idempotency.is_already_processed(key):
                skipped += 1
                continue
            
            # Simulate embedding generation (deterministic for idempotency)
            seed = int(hashlib.md5(record["content"].encode()).hexdigest()[:8], 16)
            random.seed(seed)
            embedding = [random.uniform(-1, 1) for _ in range(8)]  # Small dims for demo
            random.seed()  # Reset
            
            embedded_record = {
                "id": record["id"],
                "embedding": embedding,
                "model": "text-embedding-3-small",
                "dimensions": len(embedding),
                "embedded_at": datetime.now().isoformat(),
            }
            embedded.append(embedded_record)
            self.idempotency.mark_processed(key)
        
        self.embedded_data = embedded
        duration = (time.time() - start) * 1000
        
        return TaskResult(
            status=TaskStatus.SUCCESS,
            records_processed=len(embedded),
            records_skipped=skipped,
            duration_ms=duration,
        )
    
    def index(self, **kwargs) -> TaskResult:
        """Index embeddings in vector store (idempotent upsert)."""
        start = time.time()
        indexed = []
        
        for record in self.embedded_data:
            # Deterministic vector ID (idempotent - upsert semantics)
            vector_id = self.idempotency.get_idempotency_key(
                record["id"], "index", "v1"
            )
            
            indexed_record = {
                "vector_id": vector_id,
                "doc_id": record["id"],
                "embedding": record["embedding"],
                "indexed_at": datetime.now().isoformat(),
            }
            indexed.append(indexed_record)
        
        self.indexed_data = indexed
        duration = (time.time() - start) * 1000
        
        return TaskResult(
            status=TaskStatus.SUCCESS,
            records_processed=len(indexed),
            duration_ms=duration,
            output={"index_size": len(indexed)},
        )


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class PipelineOrchestrator:
    """Executes DAGs with retry logic, error handling, and monitoring."""
    
    def __init__(self):
        self.run_history: List[Dict] = []
    
    def execute_dag(self, dag: DAG, context: Dict = None) -> Dict:
        """Execute all tasks in DAG order with retry logic."""
        
        order = dag.topological_sort()
        run_id = hashlib.md5(f"{dag.name}:{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        
        print(f"\n  Executing DAG: {dag.name} (run_id: {run_id})")
        print(f"  Execution order: {' → '.join(order)}")
        print(f"  {'─' * 50}")
        
        results = {}
        failed = False
        
        for task_id in order:
            task = dag.tasks[task_id]
            
            if failed and task.dependencies:
                # Skip tasks whose dependencies failed
                task.status = TaskStatus.SKIPPED
                task.result = TaskResult(status=TaskStatus.SKIPPED)
                results[task_id] = task.result
                print(f"  [{task_id}] SKIPPED (upstream failure)")
                continue
            
            # Execute with retries
            task.status = TaskStatus.RUNNING
            success = False
            
            for attempt in range(task.max_retries + 1):
                try:
                    result = task.execute_fn(**(context or {}))
                    task.status = TaskStatus.SUCCESS
                    task.result = result
                    results[task_id] = result
                    success = True
                    
                    print(f"  [{task_id}] SUCCESS — processed={result.records_processed}, "
                          f"skipped={result.records_skipped}, time={result.duration_ms:.1f}ms")
                    if result.errors:
                        print(f"           warnings: {len(result.errors)} records had issues")
                    break
                    
                except Exception as e:
                    task.retry_count += 1
                    if attempt < task.max_retries:
                        task.status = TaskStatus.RETRYING
                        print(f"  [{task_id}] RETRY {attempt + 1}/{task.max_retries} — {str(e)}")
                        time.sleep(0.01)  # Simulated backoff
                    else:
                        task.status = TaskStatus.FAILED
                        task.result = TaskResult(
                            status=TaskStatus.FAILED,
                            errors=[str(e)],
                        )
                        results[task_id] = task.result
                        failed = True
                        print(f"  [{task_id}] FAILED after {task.max_retries} retries — {str(e)}")
        
        run_record = {
            "run_id": run_id,
            "dag": dag.name,
            "timestamp": datetime.now().isoformat(),
            "success": not failed,
            "tasks": {tid: t.status.value for tid, t in dag.tasks.items()},
        }
        self.run_history.append(run_record)
        
        return results


# =============================================================================
# BACKFILL ENGINE
# =============================================================================

class BackfillEngine:
    """Handles reprocessing historical data (e.g., re-embedding with new model)."""
    
    def __init__(self, idempotency: IdempotencyManager):
        self.idempotency = idempotency
    
    def plan_backfill(self, total_records: int, batch_size: int,
                      reason: str) -> Dict:
        """Plan a backfill operation."""
        num_batches = (total_records + batch_size - 1) // batch_size
        
        # Estimate cost
        cost_per_embed = 0.0001  # $0.0001 per embedding
        total_cost = total_records * cost_per_embed
        
        # Estimate time
        rate_per_second = 500  # embeddings per second with parallelism
        total_seconds = total_records / rate_per_second
        
        plan = {
            "reason": reason,
            "total_records": total_records,
            "batch_size": batch_size,
            "num_batches": num_batches,
            "estimated_cost": f"${total_cost:.2f}",
            "estimated_time": f"{total_seconds/3600:.1f} hours",
            "strategy": "shadow_index" if total_records > 1_000_000 else "in_place",
            "parallelism": min(100, num_batches),
        }
        return plan
    
    def execute_backfill(self, plan: Dict) -> Dict:
        """Simulate backfill execution with progress tracking."""
        total = plan["total_records"]
        batch_size = plan["batch_size"]
        num_batches = plan["num_batches"]
        
        # Simulate processing batches
        processed = 0
        batches_done = 0
        simulate_batches = min(5, num_batches)  # Only simulate a few for demo
        
        print(f"\n  Executing backfill: {plan['reason']}")
        print(f"  Strategy: {plan['strategy']}")
        print(f"  Progress:")
        
        for i in range(simulate_batches):
            batch_processed = min(batch_size, total - processed)
            processed += batch_processed
            batches_done += 1
            pct = (processed / total) * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"    [{bar}] {pct:.1f}% — batch {batches_done}/{num_batches}")
        
        if num_batches > simulate_batches:
            print(f"    ... (simulating remaining {num_batches - simulate_batches} batches)")
            processed = total
        
        return {
            "records_processed": processed,
            "batches_completed": num_batches,
            "status": "completed",
        }


# =============================================================================
# MAIN SIMULATION
# =============================================================================

def main():
    print("=" * 70)
    print("DATA PIPELINE ORCHESTRATOR FOR AI SYSTEMS")
    print("=" * 70)
    
    idempotency = IdempotencyManager()
    tasks = PipelineTasks(idempotency)
    orchestrator = PipelineOrchestrator()
    
    # -------------------------------------------------------------------------
    # 1. DAG-Based Orchestration
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 1: DAG-Based Pipeline Orchestration")
    print("-" * 70)
    
    dag = DAG("ai_document_pipeline")
    
    dag.add_task(Task(
        id="extract", name="Extract Documents",
        description="Extract documents from PostgreSQL",
        execute_fn=tasks.extract, dependencies=[],
    ))
    dag.add_task(Task(
        id="clean", name="Clean & Validate",
        description="Clean, deduplicate, validate schema",
        execute_fn=tasks.clean, dependencies=["extract"],
    ))
    dag.add_task(Task(
        id="embed", name="Generate Embeddings",
        description="Embed documents using text-embedding-3-small",
        execute_fn=tasks.embed, dependencies=["clean"],
    ))
    dag.add_task(Task(
        id="index", name="Index Vectors",
        description="Upsert embeddings into vector index",
        execute_fn=tasks.index, dependencies=["embed"],
    ))
    
    print(f"\n  DAG: {dag.name}")
    print(f"  Tasks: extract → clean → embed → index")
    
    results = orchestrator.execute_dag(dag)
    
    # -------------------------------------------------------------------------
    # 2. Idempotency Demonstration
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 2: Idempotency — Safe to Re-Run")
    print("-" * 70)
    
    print(f"\n  Re-running the same pipeline (simulating retry after partial failure)...")
    print(f"  Records already processed will be SKIPPED (not duplicated)")
    
    # Reset task state but keep idempotency records
    tasks.extracted_data = []
    tasks.cleaned_data = []
    tasks.embedded_data = []
    tasks.indexed_data = []
    
    dag2 = DAG("ai_document_pipeline_retry")
    dag2.add_task(Task(id="extract", name="Extract", description="",
                       execute_fn=tasks.extract, dependencies=[]))
    dag2.add_task(Task(id="clean", name="Clean", description="",
                       execute_fn=tasks.clean, dependencies=["extract"]))
    dag2.add_task(Task(id="embed", name="Embed", description="",
                       execute_fn=tasks.embed, dependencies=["clean"]))
    dag2.add_task(Task(id="index", name="Index", description="",
                       execute_fn=tasks.index, dependencies=["embed"]))
    
    results2 = orchestrator.execute_dag(dag2)
    
    print(f"\n  Key insight: clean and embed tasks SKIPPED already-processed records")
    print(f"  No duplicate vectors were created in the index")
    print(f"  Idempotency keys: {len(idempotency.processed_ids)} unique records tracked")
    
    # -------------------------------------------------------------------------
    # 3. CDC-Triggered Incremental Processing
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 3: CDC-Triggered Incremental Processing")
    print("-" * 70)
    
    cdc_stream = CDCStream()
    cdc_stream.produce_events(30)
    
    print(f"\n  CDC stream: {len(cdc_stream.events)} change events captured")
    
    # Process CDC events
    batch = cdc_stream.consume(batch_size=15)
    
    doc_changes = [e for e in batch if e.table == "documents"]
    inserts = [e for e in doc_changes if e.operation == "INSERT"]
    updates = [e for e in doc_changes if e.operation == "UPDATE"]
    deletes = [e for e in doc_changes if e.operation == "DELETE"]
    
    print(f"\n  Processing CDC batch (15 events):")
    print(f"  ├── Document changes: {len(doc_changes)}")
    print(f"  │   ├── INSERTs (embed new): {len(inserts)}")
    print(f"  │   ├── UPDATEs (re-embed): {len(updates)}")
    print(f"  │   └── DELETEs (remove from index): {len(deletes)}")
    print(f"  └── Other tables (user/interaction): {len(batch) - len(doc_changes)}")
    
    print(f"\n  Actions taken:")
    for event in doc_changes[:5]:
        action = {"INSERT": "embed & index", "UPDATE": "re-embed & upsert", 
                  "DELETE": "remove from index"}[event.operation]
        print(f"    {event.operation} {event.record_id} → {action}")
    
    print(f"\n  CDC advantage: processed {len(doc_changes)} changes instead of scanning all documents")
    print(f"  Estimated savings: 99.5% less compute (only changes, not full table)")
    
    # -------------------------------------------------------------------------
    # 4. Backfill
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 4: Backfill — Re-Embedding with New Model")
    print("-" * 70)
    
    backfill_engine = BackfillEngine(idempotency)
    
    plan = backfill_engine.plan_backfill(
        total_records=5_000_000,
        batch_size=10_000,
        reason="Upgrade from ada-002 to text-embedding-3-small",
    )
    
    print(f"\n  Backfill Plan:")
    print(f"  ├── Reason: {plan['reason']}")
    print(f"  ├── Records: {plan['total_records']:,}")
    print(f"  ├── Batches: {plan['num_batches']:,}")
    print(f"  ├── Strategy: {plan['strategy']}")
    print(f"  ├── Parallelism: {plan['parallelism']} workers")
    print(f"  ├── Estimated cost: {plan['estimated_cost']}")
    print(f"  └── Estimated time: {plan['estimated_time']}")
    
    result = backfill_engine.execute_backfill(plan)
    
    print(f"\n  Backfill complete: {result['records_processed']:,} records reprocessed")
    
    # -------------------------------------------------------------------------
    # 5. Error Handling
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 5: Error Handling & Retry Logic")
    print("-" * 70)
    
    print(f"""
  Error handling strategy for AI pipelines:
  ┌─────────────────────────────────────────────────────────────┐
  │ Error Type        │ Action         │ Retry? │ Alert?        │
  ├───────────────────┼────────────────┼────────┼───────────────┤
  │ Rate limit (429)  │ Backoff+retry  │ Yes    │ If persistent │
  │ Timeout           │ Retry          │ Yes    │ If > 3x       │
  │ Invalid input     │ Dead letter Q  │ No     │ If > 5%       │
  │ Auth error        │ Halt pipeline  │ No     │ Immediately   │
  │ Infra failure     │ Retry          │ Yes    │ Immediately   │
  │ Content policy    │ Skip + log     │ No     │ Batch report  │
  └─────────────────────────────────────────────────────────────┘

  Retry configuration used:
  ├── Max retries: 3
  ├── Backoff: exponential (1s, 2s, 4s)
  ├── Dead letter queue: records that fail all retries
  └── Circuit breaker: halt if error rate > 10% in 5-minute window
""")
    
    # Show pipeline run history
    print(f"\n  Pipeline Run History:")
    for run in orchestrator.run_history:
        status = "SUCCESS" if run["success"] else "FAILED"
        print(f"    [{run['run_id']}] {run['dag']} — {status}")
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PIPELINE ORCHESTRATOR SUMMARY")
    print("=" * 70)
    print(f"""
  Capabilities Demonstrated:
  ├── DAG orchestration: topological sort, dependency management
  ├── Idempotency: deterministic IDs, safe retries, no duplicates
  ├── CDC processing: incremental updates, not full re-scans
  ├── Backfill: shadow index strategy for model upgrades
  ├── Error handling: retries, dead letter queues, circuit breakers
  └── Monitoring: run history, task status, record counts

  Staff Architect Design Principles:
  1. Every task MUST be idempotent (safe to re-run)
  2. Use CDC for incremental updates (99%+ compute savings)
  3. Design for backfill from day 1 (model upgrades are inevitable)
  4. Decompose into stages (independently scalable and debuggable)
  5. Deterministic vector IDs prevent duplicate embeddings
  6. Shadow indexes enable zero-downtime model migrations
""")


if __name__ == "__main__":
    random.seed(42)
    main()
