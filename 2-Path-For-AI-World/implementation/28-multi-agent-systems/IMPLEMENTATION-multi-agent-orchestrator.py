"""
Multi-Agent Systems: Production Orchestrator
=============================================

Complete production orchestrator for multi-agent systems with:
- Agent registry and discovery
- Dynamic agent composition
- Message routing
- Shared state management
- Global budget/timeout enforcement
- Circular delegation detection
- Communication logging
- Performance monitoring
- Graceful shutdown
"""

import asyncio
import uuid
import time
import json
from enum import Enum
from typing import Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict


# =============================================================================
# Core Types
# =============================================================================

class AgentStatus(Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    BUSY = "busy"
    PAUSED = "paused"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    DELEGATE = "delegate"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MessageType = MessageType.REQUEST
    from_agent: str = ""
    to_agent: str = ""
    content: dict = field(default_factory=dict)
    correlation_id: Optional[str] = None  # Links request/response
    timestamp: float = field(default_factory=time.time)
    ttl: float = 30.0  # Time-to-live in seconds


@dataclass
class AgentCapability:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    estimated_cost: float = 0.0
    estimated_latency: float = 0.0


@dataclass
class AgentRegistration:
    agent_id: str
    name: str
    capabilities: list[AgentCapability] = field(default_factory=list)
    status: AgentStatus = AgentStatus.REGISTERED
    max_concurrent: int = 5
    current_load: int = 0
    metrics: dict = field(default_factory=lambda: {
        "requests_handled": 0,
        "requests_failed": 0,
        "total_cost": 0.0,
        "total_latency": 0.0,
        "avg_latency": 0.0,
    })
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class SharedState:
    """Global shared state accessible by all agents through the orchestrator."""
    data: dict = field(default_factory=dict)
    locks: dict = field(default_factory=dict)  # key → lock holder agent_id
    version: int = 0
    history: list[dict] = field(default_factory=list)


@dataclass
class BudgetConfig:
    max_total_cost: float = 1.0
    max_total_time: float = 120.0
    max_agent_invocations: int = 50
    max_messages: int = 200
    cost_alert_threshold: float = 0.8  # Alert at 80% budget


@dataclass
class OrchestratorMetrics:
    total_messages: int = 0
    total_cost: float = 0.0
    total_invocations: int = 0
    start_time: float = field(default_factory=time.time)
    messages_per_agent: dict = field(default_factory=lambda: defaultdict(int))
    delegation_graph: list = field(default_factory=list)  # (from, to, task) tuples
    circular_delegations_detected: int = 0
    budget_alerts: list = field(default_factory=list)


# =============================================================================
# Agent Interface
# =============================================================================

class ManagedAgent:
    """Base class for agents managed by the orchestrator."""

    def __init__(self, agent_id: str, name: str, capabilities: list[AgentCapability]):
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities
        self._orchestrator: Optional['MultiAgentOrchestrator'] = None

    def set_orchestrator(self, orchestrator: 'MultiAgentOrchestrator'):
        self._orchestrator = orchestrator

    async def handle_message(self, message: AgentMessage) -> dict:
        """Handle an incoming message. Override in subclasses."""
        raise NotImplementedError

    async def delegate(self, to_agent: str, task: dict) -> dict:
        """Delegate a task to another agent through the orchestrator."""
        if not self._orchestrator:
            raise RuntimeError("Agent not connected to orchestrator")
        return await self._orchestrator.route_message(AgentMessage(
            type=MessageType.DELEGATE,
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=task,
        ))

    async def read_state(self, key: str) -> Any:
        """Read from shared state."""
        if self._orchestrator:
            return self._orchestrator.shared_state.data.get(key)
        return None

    async def write_state(self, key: str, value: Any):
        """Write to shared state through orchestrator."""
        if self._orchestrator:
            await self._orchestrator.update_shared_state(self.agent_id, key, value)


# =============================================================================
# Example Managed Agents
# =============================================================================

class ResearchAgent(ManagedAgent):
    def __init__(self):
        super().__init__(
            agent_id="research-agent",
            name="Research Agent",
            capabilities=[
                AgentCapability("research", "Web research and information gathering",
                              estimated_cost=0.01, estimated_latency=2.0),
            ]
        )

    async def handle_message(self, message: AgentMessage) -> dict:
        await asyncio.sleep(0.3)
        query = message.content.get("query", "")
        return {
            "findings": [f"Research result for: {query}"],
            "cost": 0.005,
            "confidence": 0.85,
        }


class CodeAgent(ManagedAgent):
    def __init__(self):
        super().__init__(
            agent_id="code-agent",
            name="Code Agent",
            capabilities=[
                AgentCapability("code_generation", "Generate and modify code",
                              estimated_cost=0.02, estimated_latency=3.0),
            ]
        )

    async def handle_message(self, message: AgentMessage) -> dict:
        await asyncio.sleep(0.5)
        spec = message.content.get("spec", "")
        return {
            "code": f"# Generated code for: {spec}\ndef solution(): pass",
            "cost": 0.01,
            "tests_passing": True,
        }


class ReviewAgent(ManagedAgent):
    def __init__(self):
        super().__init__(
            agent_id="review-agent",
            name="Review Agent",
            capabilities=[
                AgentCapability("code_review", "Review code for quality and issues",
                              estimated_cost=0.01, estimated_latency=2.0),
            ]
        )

    async def handle_message(self, message: AgentMessage) -> dict:
        await asyncio.sleep(0.3)
        code = message.content.get("code", "")
        return {
            "approved": True,
            "issues": [],
            "suggestions": ["Consider adding error handling"],
            "cost": 0.005,
        }


# =============================================================================
# Multi-Agent Orchestrator
# =============================================================================

class MultiAgentOrchestrator:
    """
    Production orchestrator managing multiple agents with full lifecycle support.
    """

    def __init__(self, budget: BudgetConfig = None):
        self.budget = budget or BudgetConfig()
        self.registry: dict[str, AgentRegistration] = {}
        self.agents: dict[str, ManagedAgent] = {}
        self.shared_state = SharedState()
        self.metrics = OrchestratorMetrics()
        self.message_log: list[AgentMessage] = []
        self._shutdown_event = asyncio.Event()
        self._running = False

    # -------------------------------------------------------------------------
    # Agent Registry
    # -------------------------------------------------------------------------

    def register_agent(self, agent: ManagedAgent) -> bool:
        """Register an agent with the orchestrator."""
        if agent.agent_id in self.registry:
            print(f"  [Registry] Agent {agent.agent_id} already registered")
            return False
        
        registration = AgentRegistration(
            agent_id=agent.agent_id,
            name=agent.name,
            capabilities=agent.capabilities,
            status=AgentStatus.ACTIVE,
        )
        
        self.registry[agent.agent_id] = registration
        self.agents[agent.agent_id] = agent
        agent.set_orchestrator(self)
        
        print(f"  [Registry] Registered: {agent.name} ({agent.agent_id})")
        return True

    def deregister_agent(self, agent_id: str):
        """Remove agent from registry."""
        if agent_id in self.registry:
            self.registry[agent_id].status = AgentStatus.SHUTDOWN
            del self.agents[agent_id]
            print(f"  [Registry] Deregistered: {agent_id}")

    def discover_agents(self, capability: str) -> list[AgentRegistration]:
        """Find agents that can handle a specific capability."""
        matches = []
        for reg in self.registry.values():
            if reg.status == AgentStatus.ACTIVE:
                for cap in reg.capabilities:
                    if capability in cap.name or capability in cap.description.lower():
                        matches.append(reg)
                        break
        return matches

    # -------------------------------------------------------------------------
    # Message Routing
    # -------------------------------------------------------------------------

    async def route_message(self, message: AgentMessage) -> dict:
        """Route a message to the target agent with all safeguards."""
        # Check budget
        if not self._check_budget():
            return {"error": "Budget exceeded", "budget_status": self._budget_status()}
        
        # Check shutdown
        if self._shutdown_event.is_set():
            return {"error": "Orchestrator shutting down"}
        
        # Check TTL
        if time.time() - message.timestamp > message.ttl:
            return {"error": "Message TTL expired"}
        
        # Circular delegation detection
        if message.type == MessageType.DELEGATE:
            if self._detect_circular_delegation(message.from_agent, message.to_agent):
                self.metrics.circular_delegations_detected += 1
                print(f"  ⚠️  [CIRCULAR] {message.from_agent} → {message.to_agent} blocked!")
                return {"error": "Circular delegation detected"}
        
        # Log message
        self.message_log.append(message)
        self.metrics.total_messages += 1
        self.metrics.messages_per_agent[message.from_agent] += 1
        
        # Track delegation graph
        if message.type == MessageType.DELEGATE:
            self.metrics.delegation_graph.append(
                (message.from_agent, message.to_agent, message.content.get("task", ""))
            )
        
        # Route to target agent
        target = self.agents.get(message.to_agent)
        if not target:
            # Try capability-based routing
            capability = message.content.get("capability", "")
            candidates = self.discover_agents(capability)
            if candidates:
                target = self.agents.get(candidates[0].agent_id)
                message.to_agent = candidates[0].agent_id
            else:
                return {"error": f"Agent {message.to_agent} not found"}
        
        # Check agent health
        reg = self.registry[message.to_agent]
        if reg.status != AgentStatus.ACTIVE:
            return {"error": f"Agent {message.to_agent} not active (status: {reg.status.value})"}
        if reg.current_load >= reg.max_concurrent:
            return {"error": f"Agent {message.to_agent} at capacity"}
        
        # Execute
        reg.current_load += 1
        reg.status = AgentStatus.BUSY
        self.metrics.total_invocations += 1
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                target.handle_message(message),
                timeout=30.0
            )
            
            latency = time.time() - start_time
            cost = result.get("cost", 0)
            
            # Update metrics
            self.metrics.total_cost += cost
            reg.metrics["requests_handled"] += 1
            reg.metrics["total_cost"] += cost
            reg.metrics["total_latency"] += latency
            reg.metrics["avg_latency"] = (
                reg.metrics["total_latency"] / reg.metrics["requests_handled"]
            )
            
            # Budget alert
            if self.metrics.total_cost > self.budget.max_total_cost * self.budget.cost_alert_threshold:
                alert = f"Budget alert: ${self.metrics.total_cost:.4f} / ${self.budget.max_total_cost:.2f}"
                self.metrics.budget_alerts.append(alert)
                print(f"  ⚠️  {alert}")
            
            return result
            
        except asyncio.TimeoutError:
            reg.metrics["requests_failed"] += 1
            return {"error": f"Agent {message.to_agent} timed out"}
        except Exception as e:
            reg.metrics["requests_failed"] += 1
            return {"error": str(e)}
        finally:
            reg.current_load -= 1
            if reg.current_load == 0:
                reg.status = AgentStatus.ACTIVE

    # -------------------------------------------------------------------------
    # Circular Delegation Detection
    # -------------------------------------------------------------------------

    def _detect_circular_delegation(self, from_agent: str, to_agent: str) -> bool:
        """Detect if this delegation would create a cycle."""
        # Build current delegation graph
        graph = defaultdict(set)
        for src, dst, _ in self.metrics.delegation_graph[-20:]:  # Check recent
            graph[src].add(dst)
        
        # Check if to_agent can reach from_agent (would create cycle)
        visited = set()
        queue = [to_agent]
        while queue:
            current = queue.pop(0)
            if current == from_agent:
                return True
            if current in visited:
                continue
            visited.add(current)
            queue.extend(graph.get(current, set()))
        
        return False

    # -------------------------------------------------------------------------
    # Shared State Management
    # -------------------------------------------------------------------------

    async def update_shared_state(self, agent_id: str, key: str, value: Any):
        """Update shared state with versioning and history."""
        # Simple lock check
        if key in self.shared_state.locks and self.shared_state.locks[key] != agent_id:
            raise RuntimeError(f"Key '{key}' locked by {self.shared_state.locks[key]}")
        
        old_value = self.shared_state.data.get(key)
        self.shared_state.data[key] = value
        self.shared_state.version += 1
        self.shared_state.history.append({
            "version": self.shared_state.version,
            "agent_id": agent_id,
            "key": key,
            "old_value": str(old_value)[:100] if old_value else None,
            "new_value": str(value)[:100],
            "timestamp": time.time(),
        })

    async def lock_state_key(self, agent_id: str, key: str) -> bool:
        """Lock a state key for exclusive access."""
        if key in self.shared_state.locks:
            return False
        self.shared_state.locks[key] = agent_id
        return True

    async def unlock_state_key(self, agent_id: str, key: str):
        """Release a state lock."""
        if self.shared_state.locks.get(key) == agent_id:
            del self.shared_state.locks[key]

    # -------------------------------------------------------------------------
    # Budget Enforcement
    # -------------------------------------------------------------------------

    def _check_budget(self) -> bool:
        """Check if we're within budget."""
        if self.metrics.total_cost >= self.budget.max_total_cost:
            return False
        if self.metrics.total_invocations >= self.budget.max_agent_invocations:
            return False
        if self.metrics.total_messages >= self.budget.max_messages:
            return False
        elapsed = time.time() - self.metrics.start_time
        if elapsed >= self.budget.max_total_time:
            return False
        return True

    def _budget_status(self) -> dict:
        elapsed = time.time() - self.metrics.start_time
        return {
            "cost": f"${self.metrics.total_cost:.4f} / ${self.budget.max_total_cost:.2f}",
            "invocations": f"{self.metrics.total_invocations} / {self.budget.max_agent_invocations}",
            "messages": f"{self.metrics.total_messages} / {self.budget.max_messages}",
            "time": f"{elapsed:.1f}s / {self.budget.max_total_time:.0f}s",
        }

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    async def shutdown(self, graceful: bool = True):
        """Shutdown the orchestrator and all agents."""
        print(f"\n  [Orchestrator] {'Graceful' if graceful else 'Immediate'} shutdown initiated")
        self._shutdown_event.set()
        
        if graceful:
            # Wait for active tasks to complete (with timeout)
            for _ in range(10):
                busy_agents = [r for r in self.registry.values() if r.current_load > 0]
                if not busy_agents:
                    break
                await asyncio.sleep(0.5)
        
        # Deregister all agents
        for agent_id in list(self.agents.keys()):
            self.deregister_agent(agent_id)
        
        print(f"  [Orchestrator] Shutdown complete")

    # -------------------------------------------------------------------------
    # Monitoring and Reporting
    # -------------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get full orchestrator status."""
        elapsed = time.time() - self.metrics.start_time
        return {
            "running": not self._shutdown_event.is_set(),
            "elapsed": f"{elapsed:.1f}s",
            "budget": self._budget_status(),
            "agents": {
                agent_id: {
                    "name": reg.name,
                    "status": reg.status.value,
                    "load": f"{reg.current_load}/{reg.max_concurrent}",
                    "handled": reg.metrics["requests_handled"],
                    "failed": reg.metrics["requests_failed"],
                    "cost": f"${reg.metrics['total_cost']:.4f}",
                    "avg_latency": f"{reg.metrics['avg_latency']:.2f}s",
                }
                for agent_id, reg in self.registry.items()
            },
            "metrics": {
                "total_messages": self.metrics.total_messages,
                "total_cost": f"${self.metrics.total_cost:.4f}",
                "total_invocations": self.metrics.total_invocations,
                "circular_delegations_blocked": self.metrics.circular_delegations_detected,
            },
            "shared_state_version": self.shared_state.version,
        }

    def get_communication_log(self, last_n: int = 20) -> list[dict]:
        """Get recent communication log."""
        return [
            {
                "id": m.id,
                "type": m.type.value,
                "from": m.from_agent,
                "to": m.to_agent,
                "content_preview": str(m.content)[:80],
                "timestamp": m.timestamp,
            }
            for m in self.message_log[-last_n:]
        ]


# =============================================================================
# High-Level Task Runner
# =============================================================================

class TaskRunner:
    """High-level interface for running multi-agent tasks through the orchestrator."""

    def __init__(self, orchestrator: MultiAgentOrchestrator):
        self.orchestrator = orchestrator

    async def run_task(self, task: str, pipeline: list[str] = None) -> dict:
        """
        Run a task through a pipeline of agents.
        If no pipeline specified, auto-discovers capable agents.
        """
        results = {}
        context = {"original_task": task}
        
        if not pipeline:
            # Auto-discover: research → code → review
            pipeline = ["research-agent", "code-agent", "review-agent"]
        
        for agent_id in pipeline:
            message = AgentMessage(
                type=MessageType.REQUEST,
                from_agent="task-runner",
                to_agent=agent_id,
                content={"task": task, "context": context, "prior_results": results},
            )
            
            result = await self.orchestrator.route_message(message)
            
            if "error" in result:
                print(f"  [TaskRunner] Pipeline failed at {agent_id}: {result['error']}")
                return {"status": "failed", "failed_at": agent_id, "error": result["error"],
                       "partial_results": results}
            
            results[agent_id] = result
            context[f"{agent_id}_result"] = result
        
        return {"status": "completed", "results": results}


# =============================================================================
# Demo
# =============================================================================

async def main():
    print("=" * 70)
    print("MULTI-AGENT ORCHESTRATOR DEMO")
    print("=" * 70)
    
    # Create orchestrator with budget
    budget = BudgetConfig(
        max_total_cost=0.50,
        max_total_time=60.0,
        max_agent_invocations=20,
        max_messages=100,
    )
    orchestrator = MultiAgentOrchestrator(budget=budget)
    
    # Register agents
    print("\n--- Registering Agents ---")
    orchestrator.register_agent(ResearchAgent())
    orchestrator.register_agent(CodeAgent())
    orchestrator.register_agent(ReviewAgent())
    
    # Run a task through the pipeline
    print("\n--- Running Task Pipeline ---")
    runner = TaskRunner(orchestrator)
    result = await runner.run_task(
        task="Implement a thread-safe LRU cache with TTL support",
        pipeline=["research-agent", "code-agent", "review-agent"]
    )
    
    print(f"\n  Pipeline result: {result['status']}")
    for agent_id, agent_result in result.get("results", {}).items():
        print(f"    {agent_id}: {json.dumps(agent_result, indent=2)[:100]}...")
    
    # Direct message routing
    print("\n--- Direct Message Routing ---")
    response = await orchestrator.route_message(AgentMessage(
        type=MessageType.REQUEST,
        from_agent="user",
        to_agent="code-agent",
        content={"spec": "fibonacci with memoization", "capability": "code_generation"},
    ))
    print(f"  Direct response: {response}")
    
    # Shared state demo
    print("\n--- Shared State ---")
    research_agent = orchestrator.agents["research-agent"]
    await research_agent.write_state("project_context", {"language": "python", "framework": "fastapi"})
    
    code_agent = orchestrator.agents["code-agent"]
    ctx = await code_agent.read_state("project_context")
    print(f"  Code agent read shared state: {ctx}")
    
    # Circular delegation detection demo
    print("\n--- Circular Delegation Detection ---")
    # Simulate: research → code → research (circular)
    orchestrator.metrics.delegation_graph.append(("research-agent", "code-agent", "task1"))
    result = await orchestrator.route_message(AgentMessage(
        type=MessageType.DELEGATE,
        from_agent="code-agent",
        to_agent="research-agent",
        content={"task": "re-research"},
    ))
    if "error" in result and "Circular" in result["error"]:
        print(f"  Correctly blocked: {result['error']}")
    else:
        print(f"  Delegation allowed (no cycle in this case): {result}")
    
    # Print final status
    print(f"\n{'=' * 70}")
    print("ORCHESTRATOR STATUS")
    print(f"{'=' * 70}")
    status = orchestrator.get_status()
    print(f"  Budget: {json.dumps(status['budget'], indent=4)}")
    print(f"  Metrics: {json.dumps(status['metrics'], indent=4)}")
    print(f"  Agents:")
    for aid, info in status["agents"].items():
        print(f"    {aid}: status={info['status']}, handled={info['handled']}, cost={info['cost']}")
    
    # Graceful shutdown
    await orchestrator.shutdown(graceful=True)


if __name__ == "__main__":
    asyncio.run(main())
