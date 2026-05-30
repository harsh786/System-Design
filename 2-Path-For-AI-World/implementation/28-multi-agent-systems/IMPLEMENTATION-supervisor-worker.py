"""
Multi-Agent Systems: Supervisor-Worker Pattern
==============================================

Production implementation of the supervisor-worker pattern where a supervisor
agent decomposes tasks, assigns them to specialized workers, monitors execution,
and aggregates results with quality verification.
"""

import asyncio
import uuid
import time
import json
from enum import Enum
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


# =============================================================================
# Core Types
# =============================================================================

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REASSIGNED = "reassigned"
    TIMED_OUT = "timed_out"


class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class SubTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    type: str = ""  # research, code, analysis, writing
    input_data: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: float = 30.0
    cost: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class WorkerMetrics:
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_cost: float = 0.0
    total_latency: float = 0.0
    consecutive_failures: int = 0


@dataclass
class SupervisorResult:
    task_id: str
    status: str
    subtasks: list[SubTask] = field(default_factory=list)
    final_result: Optional[dict] = None
    total_cost: float = 0.0
    total_time: float = 0.0
    worker_metrics: dict = field(default_factory=dict)


# =============================================================================
# Worker Base Class
# =============================================================================

class Worker(ABC):
    """Base class for specialized worker agents."""

    def __init__(self, worker_id: str, capabilities: list[str], 
                 max_concurrent: int = 3):
        self.worker_id = worker_id
        self.capabilities = capabilities
        self.max_concurrent = max_concurrent
        self.status = WorkerStatus.IDLE
        self.metrics = WorkerMetrics()
        self.current_tasks: int = 0
        self.circuit_breaker_threshold = 3
        self.circuit_breaker_reset_time = 60.0
        self.circuit_opened_at: Optional[float] = None

    @abstractmethod
    async def execute(self, task: SubTask) -> dict:
        """Execute a subtask and return result."""
        pass

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.capabilities

    def is_available(self) -> bool:
        if self.status == WorkerStatus.CIRCUIT_OPEN:
            # Check if circuit breaker should reset
            if (self.circuit_opened_at and 
                time.time() - self.circuit_opened_at > self.circuit_breaker_reset_time):
                self.status = WorkerStatus.IDLE
                self.metrics.consecutive_failures = 0
                return True
            return False
        return self.current_tasks < self.max_concurrent

    def record_success(self, cost: float, latency: float):
        self.metrics.tasks_completed += 1
        self.metrics.total_cost += cost
        self.metrics.total_latency += latency
        self.metrics.consecutive_failures = 0
        self.current_tasks -= 1
        if self.current_tasks == 0:
            self.status = WorkerStatus.IDLE

    def record_failure(self):
        self.metrics.tasks_failed += 1
        self.metrics.consecutive_failures += 1
        self.current_tasks -= 1
        if self.metrics.consecutive_failures >= self.circuit_breaker_threshold:
            self.status = WorkerStatus.CIRCUIT_OPEN
            self.circuit_opened_at = time.time()
            print(f"  ⚠️  Circuit breaker OPEN for worker {self.worker_id}")
        elif self.current_tasks == 0:
            self.status = WorkerStatus.IDLE


# =============================================================================
# Specialized Workers
# =============================================================================

class ResearchWorker(Worker):
    """Worker specialized in research and information gathering."""

    def __init__(self, worker_id: str = "research-worker"):
        super().__init__(worker_id, capabilities=["research", "search", "summarize"])

    async def execute(self, task: SubTask) -> dict:
        """Simulate research task execution."""
        # In production: call search APIs, scrape, summarize with LLM
        await asyncio.sleep(0.5)  # Simulate work
        
        query = task.input_data.get("query", task.description)
        
        # Simulated research result
        return {
            "findings": [
                f"Finding 1 for: {query}",
                f"Finding 2 for: {query}",
                f"Finding 3 for: {query}",
            ],
            "sources": ["source_a.com", "source_b.com"],
            "confidence": 0.85,
            "tokens_used": 1500,
            "cost": 0.003,
        }


class CodeWorker(Worker):
    """Worker specialized in code generation and modification."""

    def __init__(self, worker_id: str = "code-worker"):
        super().__init__(worker_id, capabilities=["code", "implement", "refactor"])

    async def execute(self, task: SubTask) -> dict:
        """Simulate code generation."""
        await asyncio.sleep(0.8)  # Simulate work
        
        spec = task.input_data.get("spec", task.description)
        
        return {
            "code": f"# Implementation for: {spec}\ndef solution():\n    pass\n",
            "language": "python",
            "tests_passed": True,
            "tokens_used": 2000,
            "cost": 0.005,
        }


class AnalysisWorker(Worker):
    """Worker specialized in data analysis and evaluation."""

    def __init__(self, worker_id: str = "analysis-worker"):
        super().__init__(worker_id, capabilities=["analysis", "evaluate", "compare"])

    async def execute(self, task: SubTask) -> dict:
        """Simulate analysis task."""
        await asyncio.sleep(0.6)  # Simulate work
        
        data = task.input_data.get("data", {})
        
        return {
            "analysis": f"Analysis of: {task.description}",
            "metrics": {"quality": 0.88, "completeness": 0.92},
            "recommendations": ["Recommendation 1", "Recommendation 2"],
            "tokens_used": 1800,
            "cost": 0.004,
        }


class WritingWorker(Worker):
    """Worker specialized in content writing and documentation."""

    def __init__(self, worker_id: str = "writing-worker"):
        super().__init__(worker_id, capabilities=["writing", "document", "explain"])

    async def execute(self, task: SubTask) -> dict:
        """Simulate writing task."""
        await asyncio.sleep(0.7)  # Simulate work
        
        topic = task.input_data.get("topic", task.description)
        
        return {
            "content": f"Comprehensive document about: {topic}\n\n"
                      f"Section 1: Overview\nSection 2: Details\nSection 3: Conclusion",
            "word_count": 500,
            "tokens_used": 2500,
            "cost": 0.006,
        }


# =============================================================================
# Supervisor Agent
# =============================================================================

class SupervisorAgent:
    """
    Supervisor agent that decomposes tasks, assigns to workers,
    monitors execution, and aggregates results.
    """

    def __init__(self, 
                 workers: list[Worker],
                 max_cost: float = 1.0,
                 max_time: float = 120.0,
                 max_iterations: int = 50,
                 quality_threshold: float = 0.7):
        self.workers = {w.worker_id: w for w in workers}
        self.max_cost = max_cost
        self.max_time = max_time
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.total_cost = 0.0
        self.start_time: Optional[float] = None
        self.task_log: list[dict] = []

    # -------------------------------------------------------------------------
    # Task Decomposition
    # -------------------------------------------------------------------------

    async def decompose_task(self, goal: str, context: dict = None) -> list[SubTask]:
        """
        Decompose a high-level goal into subtasks.
        In production: use LLM to analyze goal and create plan.
        """
        # Simulated decomposition — in production this would be an LLM call
        # that analyzes the goal and produces structured subtasks
        
        subtasks = []
        
        # Example decomposition for a typical complex task
        if "research" in goal.lower() or "analyze" in goal.lower():
            subtasks.append(SubTask(
                description=f"Research background for: {goal}",
                type="research",
                input_data={"query": goal},
                timeout_seconds=30.0,
            ))
        
        if "implement" in goal.lower() or "build" in goal.lower() or "code" in goal.lower():
            research_ids = [t.id for t in subtasks if t.type == "research"]
            subtasks.append(SubTask(
                description=f"Implement solution for: {goal}",
                type="code",
                input_data={"spec": goal},
                dependencies=research_ids,
                timeout_seconds=45.0,
            ))
        
        if "analyze" in goal.lower() or "evaluate" in goal.lower():
            prior_ids = [t.id for t in subtasks]
            subtasks.append(SubTask(
                description=f"Analyze results for: {goal}",
                type="analysis",
                input_data={"data": {}},
                dependencies=prior_ids,
                timeout_seconds=30.0,
            ))
        
        # Always add a writing/summary task at the end
        all_ids = [t.id for t in subtasks]
        subtasks.append(SubTask(
            description=f"Write summary report for: {goal}",
            type="writing",
            input_data={"topic": goal},
            dependencies=all_ids,
            timeout_seconds=30.0,
        ))
        
        # If no specific tasks matched, create a generic research + writing flow
        if len(subtasks) == 1:
            research_task = SubTask(
                description=f"Research: {goal}",
                type="research",
                input_data={"query": goal},
                timeout_seconds=30.0,
            )
            subtasks.insert(0, research_task)
            subtasks[-1].dependencies = [research_task.id]
        
        self._log("decompose", f"Decomposed into {len(subtasks)} subtasks")
        return subtasks

    # -------------------------------------------------------------------------
    # Worker Selection and Assignment
    # -------------------------------------------------------------------------

    def select_worker(self, task: SubTask) -> Optional[Worker]:
        """Select best available worker for a task using capability matching + load balancing."""
        candidates = []
        
        for worker in self.workers.values():
            if worker.can_handle(task.type) and worker.is_available():
                # Score based on: capability match + past performance + current load
                success_rate = (
                    worker.metrics.tasks_completed / 
                    max(1, worker.metrics.tasks_completed + worker.metrics.tasks_failed)
                )
                load_factor = 1.0 - (worker.current_tasks / worker.max_concurrent)
                score = success_rate * 0.6 + load_factor * 0.4
                candidates.append((worker, score))
        
        if not candidates:
            return None
        
        # Select highest scoring candidate
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    # -------------------------------------------------------------------------
    # Task Execution
    # -------------------------------------------------------------------------

    async def execute_subtask(self, task: SubTask, worker: Worker) -> bool:
        """Execute a single subtask with timeout and error handling."""
        task.status = TaskStatus.IN_PROGRESS
        task.assigned_worker = worker.worker_id
        task.started_at = time.time()
        task.attempts += 1
        worker.current_tasks += 1
        worker.status = WorkerStatus.BUSY

        self._log("assign", f"Task {task.id} ({task.type}) → {worker.worker_id}")

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                worker.execute(task),
                timeout=task.timeout_seconds
            )
            
            # Track cost
            task_cost = result.get("cost", 0.0)
            task.cost = task_cost
            self.total_cost += task_cost
            
            # Check global budget
            if self.total_cost > self.max_cost:
                task.status = TaskStatus.FAILED
                task.error = "Global cost budget exceeded"
                worker.record_failure()
                return False
            
            # Quality verification
            if await self.verify_quality(task, result):
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                latency = task.completed_at - task.started_at
                worker.record_success(task_cost, latency)
                self._log("complete", f"Task {task.id} completed (cost: ${task_cost:.4f})")
                return True
            else:
                task.status = TaskStatus.FAILED
                task.error = "Quality verification failed"
                worker.record_failure()
                return False

        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMED_OUT
            task.error = f"Timed out after {task.timeout_seconds}s"
            worker.record_failure()
            self._log("timeout", f"Task {task.id} timed out")
            return False

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            worker.record_failure()
            self._log("error", f"Task {task.id} failed: {e}")
            return False

    async def verify_quality(self, task: SubTask, result: dict) -> bool:
        """
        Verify the quality of a worker's output.
        In production: use LLM to evaluate result against task description.
        """
        # Check that result has expected fields
        if not result:
            return False
        
        # Check confidence if available
        confidence = result.get("confidence", 0.8)
        if confidence < self.quality_threshold:
            self._log("quality_fail", 
                     f"Task {task.id} below quality threshold: {confidence} < {self.quality_threshold}")
            return False
        
        return True

    # -------------------------------------------------------------------------
    # Main Orchestration Loop
    # -------------------------------------------------------------------------

    async def run(self, goal: str, context: dict = None) -> SupervisorResult:
        """
        Main supervisor loop: decompose → assign → execute → aggregate.
        """
        task_id = str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.total_cost = 0.0
        self.task_log = []
        
        self._log("start", f"Supervisor starting task: {goal}")
        
        # Step 1: Decompose
        subtasks = await self.decompose_task(goal, context)
        
        # Step 2: Execute with dependency resolution
        completed_ids: set[str] = set()
        iterations = 0
        
        while True:
            iterations += 1
            
            # Termination checks
            if iterations > self.max_iterations:
                self._log("terminate", "Max iterations reached")
                break
            
            if time.time() - self.start_time > self.max_time:
                self._log("terminate", "Max time exceeded")
                break
            
            if self.total_cost > self.max_cost:
                self._log("terminate", "Cost budget exceeded")
                break
            
            # Find tasks ready to execute (dependencies met, not completed/failed permanently)
            ready_tasks = [
                t for t in subtasks
                if t.status in (TaskStatus.PENDING, TaskStatus.TIMED_OUT, TaskStatus.FAILED)
                and t.attempts < t.max_attempts
                and all(dep in completed_ids for dep in t.dependencies)
            ]
            
            if not ready_tasks:
                # Check if all done or permanently failed
                all_terminal = all(
                    t.status == TaskStatus.COMPLETED or t.attempts >= t.max_attempts
                    for t in subtasks
                )
                if all_terminal:
                    break
                # Some tasks waiting for dependencies — wait a bit
                await asyncio.sleep(0.1)
                continue
            
            # Execute ready tasks (potentially in parallel)
            execution_tasks = []
            for task in ready_tasks:
                worker = self.select_worker(task)
                if worker:
                    task.status = TaskStatus.ASSIGNED
                    execution_tasks.append(self.execute_subtask(task, worker))
                else:
                    self._log("no_worker", 
                             f"No available worker for task {task.id} ({task.type})")
            
            if execution_tasks:
                results = await asyncio.gather(*execution_tasks, return_exceptions=True)
                
                # Update completed set
                for task in subtasks:
                    if task.status == TaskStatus.COMPLETED:
                        completed_ids.add(task.id)
            else:
                await asyncio.sleep(0.2)  # Wait for workers to become available
        
        # Step 3: Aggregate results
        final_result = await self.aggregate_results(subtasks)
        
        # Build result
        elapsed = time.time() - self.start_time
        worker_metrics = {
            wid: {
                "completed": w.metrics.tasks_completed,
                "failed": w.metrics.tasks_failed,
                "cost": w.metrics.total_cost,
                "avg_latency": (w.metrics.total_latency / max(1, w.metrics.tasks_completed)),
            }
            for wid, w in self.workers.items()
        }
        
        result = SupervisorResult(
            task_id=task_id,
            status="completed" if all(t.status == TaskStatus.COMPLETED for t in subtasks) else "partial",
            subtasks=subtasks,
            final_result=final_result,
            total_cost=self.total_cost,
            total_time=elapsed,
            worker_metrics=worker_metrics,
        )
        
        self._log("finish", f"Task {task_id} finished: status={result.status}, "
                           f"cost=${self.total_cost:.4f}, time={elapsed:.1f}s")
        
        return result

    async def aggregate_results(self, subtasks: list[SubTask]) -> dict:
        """Aggregate results from all completed subtasks."""
        completed = [t for t in subtasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in subtasks if t.status != TaskStatus.COMPLETED]
        
        return {
            "completed_count": len(completed),
            "failed_count": len(failed),
            "results": {t.id: t.result for t in completed},
            "errors": {t.id: t.error for t in failed if t.error},
        }

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _log(self, event: str, message: str):
        entry = {
            "timestamp": time.time(),
            "event": event,
            "message": message,
            "cost_so_far": self.total_cost,
        }
        self.task_log.append(entry)
        elapsed = time.time() - (self.start_time or time.time())
        print(f"  [{elapsed:6.2f}s] [{event:12s}] {message}")


# =============================================================================
# Demo
# =============================================================================

async def main():
    """Demonstrate the supervisor-worker pattern."""
    print("=" * 70)
    print("SUPERVISOR-WORKER PATTERN DEMO")
    print("=" * 70)
    
    # Create specialized workers
    workers = [
        ResearchWorker("research-1"),
        ResearchWorker("research-2"),  # Multiple research workers for parallelism
        CodeWorker("code-1"),
        AnalysisWorker("analysis-1"),
        WritingWorker("writing-1"),
    ]
    
    # Create supervisor
    supervisor = SupervisorAgent(
        workers=workers,
        max_cost=0.50,
        max_time=60.0,
        quality_threshold=0.6,
    )
    
    # Run a complex task
    print("\n--- Task 1: Research and Implement ---\n")
    result = await supervisor.run(
        goal="Research best practices for rate limiting and implement a token bucket algorithm",
        context={"language": "python", "priority": "high"}
    )
    
    print(f"\n--- Result ---")
    print(f"  Status: {result.status}")
    print(f"  Subtasks: {len(result.subtasks)} "
          f"({sum(1 for t in result.subtasks if t.status == TaskStatus.COMPLETED)} completed)")
    print(f"  Total cost: ${result.total_cost:.4f}")
    print(f"  Total time: {result.total_time:.2f}s")
    print(f"  Worker metrics:")
    for wid, metrics in result.worker_metrics.items():
        if metrics["completed"] > 0:
            print(f"    {wid}: {metrics['completed']} tasks, "
                  f"${metrics['cost']:.4f}, avg {metrics['avg_latency']:.2f}s")
    
    print("\n" + "=" * 70)
    print("\n--- Task 2: Analysis Task ---\n")
    
    # Reset supervisor for new task
    supervisor2 = SupervisorAgent(
        workers=workers,
        max_cost=0.50,
        max_time=60.0,
    )
    
    result2 = await supervisor2.run(
        goal="Analyze and evaluate the performance characteristics of our caching layer"
    )
    
    print(f"\n--- Result ---")
    print(f"  Status: {result2.status}")
    print(f"  Total cost: ${result2.total_cost:.4f}")
    print(f"  Total time: {result2.total_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
