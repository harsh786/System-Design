"""
IMPLEMENTATION: Workflow / State Machine Agent
==============================================
A production-grade state machine agent demonstrating:
- Explicit state definitions with valid transitions
- Conditional routing based on LLM classification
- Human approval checkpoints
- Parallel state execution
- State persistence (checkpoint/resume)
- Timeout and circuit breaker per state
- Full audit trail of transitions
- Rollback on failure
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ============================================================
# CORE TYPES
# ============================================================

class StateStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"
    TIMED_OUT = "timed_out"
    ROLLED_BACK = "rolled_back"


@dataclass
class TransitionRecord:
    """Immutable record of a state transition for audit trail."""
    timestamp: float
    from_state: str
    to_state: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    actor: str = "system"  # "system", "llm", "human"


@dataclass
class StateContext:
    """Shared context passed between states. Mutable accumulator."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_data: dict[str, Any] = field(default_factory=dict)
    state_outputs: dict[str, Any] = field(default_factory=dict)  # state_name -> output
    variables: dict[str, Any] = field(default_factory=dict)  # shared variables
    errors: list[dict[str, Any]] = field(default_factory=list)
    transitions: list[TransitionRecord] = field(default_factory=list)
    current_state: str = ""
    started_at: float = field(default_factory=time.time)

    def set_output(self, state_name: str, output: Any) -> None:
        self.state_outputs[state_name] = output

    def get_output(self, state_name: str) -> Any:
        return self.state_outputs.get(state_name)

    def record_transition(self, from_state: str, to_state: str, reason: str, actor: str = "system") -> None:
        self.transitions.append(TransitionRecord(
            timestamp=time.time(),
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            actor=actor,
        ))

    def to_checkpoint(self) -> dict[str, Any]:
        """Serialize context for persistence."""
        return {
            "workflow_id": self.workflow_id,
            "input_data": self.input_data,
            "state_outputs": self.state_outputs,
            "variables": self.variables,
            "errors": self.errors,
            "current_state": self.current_state,
            "started_at": self.started_at,
            "transitions": [
                {
                    "timestamp": t.timestamp,
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "reason": t.reason,
                    "actor": t.actor,
                }
                for t in self.transitions
            ],
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "StateContext":
        """Restore context from checkpoint."""
        ctx = cls(
            workflow_id=data["workflow_id"],
            input_data=data["input_data"],
            state_outputs=data["state_outputs"],
            variables=data["variables"],
            errors=data["errors"],
            current_state=data["current_state"],
            started_at=data["started_at"],
        )
        ctx.transitions = [
            TransitionRecord(**t) for t in data.get("transitions", [])
        ]
        return ctx


# ============================================================
# CIRCUIT BREAKER
# ============================================================

class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject immediately
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """Per-state circuit breaker to prevent repeated failures."""
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds
    _failure_count: int = 0
    _state: CircuitBreakerState = CircuitBreakerState.CLOSED
    _last_failure_time: float = 0.0

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN

    def can_execute(self) -> bool:
        if self._state == CircuitBreakerState.CLOSED:
            return True
        if self._state == CircuitBreakerState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one attempt
        return True

    @property
    def state(self) -> CircuitBreakerState:
        return self._state


# ============================================================
# STATE DEFINITION
# ============================================================

class StateNode(ABC):
    """Base class for all state nodes in the workflow."""

    def __init__(
        self,
        name: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        requires_approval: bool = False,
        rollback_handler: Callable[[StateContext], None] | None = None,
    ):
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.requires_approval = requires_approval
        self.rollback_handler = rollback_handler
        self.circuit_breaker = CircuitBreaker()
        self.status = StateStatus.PENDING

    @abstractmethod
    async def execute(self, context: StateContext) -> Any:
        """Execute this state's logic. Return output to store in context."""
        ...

    @abstractmethod
    def get_next_state(self, context: StateContext) -> str | None:
        """Determine the next state based on execution result. None = terminal."""
        ...

    async def run_with_timeout(self, context: StateContext) -> Any:
        """Execute with timeout enforcement."""
        try:
            return await asyncio.wait_for(
                self.execute(context),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.status = StateStatus.TIMED_OUT
            raise StateTimeoutError(f"State '{self.name}' timed out after {self.timeout_seconds}s")

    def rollback(self, context: StateContext) -> None:
        """Rollback this state's effects."""
        if self.rollback_handler:
            self.rollback_handler(context)
            self.status = StateStatus.ROLLED_BACK


# ============================================================
# CONCRETE STATE TYPES
# ============================================================

class LLMClassifierState(StateNode):
    """State that uses an LLM to classify input and route to next state."""

    def __init__(
        self,
        name: str,
        classify_prompt: str,
        routes: dict[str, str],  # classification_label -> next_state_name
        default_route: str,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.classify_prompt = classify_prompt
        self.routes = routes
        self.default_route = default_route

    async def execute(self, context: StateContext) -> Any:
        """Classify input using LLM (simulated)."""
        # In production: call LLM with classify_prompt + context
        input_text = json.dumps(context.input_data)
        # Simulated classification
        classification = "standard"  # Would come from LLM
        context.variables["classification"] = classification
        return {"classification": classification}

    def get_next_state(self, context: StateContext) -> str | None:
        classification = context.variables.get("classification", "")
        return self.routes.get(classification, self.default_route)


class FunctionState(StateNode):
    """State that executes a deterministic function."""

    def __init__(self, name: str, handler: Callable[[StateContext], Any], next_state: str | None = None, **kwargs):
        super().__init__(name, **kwargs)
        self.handler = handler
        self.next_state = next_state

    async def execute(self, context: StateContext) -> Any:
        return self.handler(context)

    def get_next_state(self, context: StateContext) -> str | None:
        return self.next_state


class ConditionalState(StateNode):
    """State that routes based on a condition function."""

    def __init__(
        self,
        name: str,
        condition: Callable[[StateContext], str],
        routes: dict[str, str],
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.condition = condition
        self.routes = routes

    async def execute(self, context: StateContext) -> Any:
        result = self.condition(context)
        context.variables[f"{self.name}_condition"] = result
        return {"condition_result": result}

    def get_next_state(self, context: StateContext) -> str | None:
        result = context.variables.get(f"{self.name}_condition", "")
        return self.routes.get(result)


class ParallelState(StateNode):
    """State that executes multiple sub-states in parallel."""

    def __init__(self, name: str, sub_states: list[StateNode], next_state: str | None = None, **kwargs):
        super().__init__(name, **kwargs)
        self.sub_states = sub_states
        self.next_state = next_state

    async def execute(self, context: StateContext) -> Any:
        tasks = [sub.run_with_timeout(context) for sub in self.sub_states]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = {}
        for sub_state, result in zip(self.sub_states, results):
            if isinstance(result, Exception):
                outputs[sub_state.name] = {"error": str(result)}
                context.errors.append({
                    "state": sub_state.name,
                    "error": str(result),
                    "timestamp": time.time(),
                })
            else:
                outputs[sub_state.name] = result
                context.set_output(sub_state.name, result)

        return outputs

    def get_next_state(self, context: StateContext) -> str | None:
        return self.next_state


class HumanApprovalState(StateNode):
    """State that pauses execution and waits for human approval."""

    def __init__(
        self,
        name: str,
        approval_prompt: str,
        approved_next: str,
        rejected_next: str,
        approval_handler: Callable[..., bool] | None = None,
        **kwargs,
    ):
        super().__init__(name, requires_approval=True, **kwargs)
        self.approval_prompt = approval_prompt
        self.approved_next = approved_next
        self.rejected_next = rejected_next
        self.approval_handler = approval_handler

    async def execute(self, context: StateContext) -> Any:
        """Request approval. In production, this would pause and await external signal."""
        print(f"\n🔔 APPROVAL REQUIRED: {self.approval_prompt}")
        print(f"   Context: {json.dumps(context.variables, indent=2)[:200]}")

        if self.approval_handler:
            approved = self.approval_handler(context)
        else:
            # Simulate approval (in production: webhook, queue, UI)
            approved = True

        context.variables[f"{self.name}_approved"] = approved
        return {"approved": approved}

    def get_next_state(self, context: StateContext) -> str | None:
        approved = context.variables.get(f"{self.name}_approved", False)
        return self.approved_next if approved else self.rejected_next


class TerminalState(StateNode):
    """Terminal state — workflow ends here."""

    def __init__(self, name: str, handler: Callable[[StateContext], Any] | None = None, **kwargs):
        super().__init__(name, **kwargs)
        self.handler = handler

    async def execute(self, context: StateContext) -> Any:
        if self.handler:
            return self.handler(context)
        return {"status": "completed", "outputs": context.state_outputs}

    def get_next_state(self, context: StateContext) -> str | None:
        return None  # Terminal


# ============================================================
# EXCEPTIONS
# ============================================================

class WorkflowError(Exception):
    pass

class StateTimeoutError(WorkflowError):
    pass

class InvalidTransitionError(WorkflowError):
    pass

class CircuitBreakerOpenError(WorkflowError):
    pass

class RollbackError(WorkflowError):
    pass


# ============================================================
# CHECKPOINT STORE (Interface + In-Memory Implementation)
# ============================================================

class CheckpointStore(ABC):
    @abstractmethod
    async def save(self, workflow_id: str, checkpoint: dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def load(self, workflow_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def delete(self, workflow_id: str) -> None:
        ...


class InMemoryCheckpointStore(CheckpointStore):
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    async def save(self, workflow_id: str, checkpoint: dict[str, Any]) -> None:
        self._store[workflow_id] = checkpoint

    async def load(self, workflow_id: str) -> dict[str, Any] | None:
        return self._store.get(workflow_id)

    async def delete(self, workflow_id: str) -> None:
        self._store.pop(workflow_id, None)


# ============================================================
# WORKFLOW ENGINE
# ============================================================

class WorkflowEngine:
    """
    Orchestrates state machine execution with:
    - State transition validation
    - Checkpoint/resume
    - Circuit breakers per state
    - Rollback on failure
    - Full audit trail
    """

    def __init__(
        self,
        states: dict[str, StateNode],
        initial_state: str,
        checkpoint_store: CheckpointStore | None = None,
        max_transitions: int = 50,
    ):
        self.states = states
        self.initial_state = initial_state
        self.checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
        self.max_transitions = max_transitions

        # Validate that initial state exists
        if initial_state not in states:
            raise ValueError(f"Initial state '{initial_state}' not found in states")

    async def run(self, input_data: dict[str, Any], resume_workflow_id: str | None = None) -> StateContext:
        """Execute the workflow from start or resume from checkpoint."""

        # Initialize or resume context
        if resume_workflow_id:
            checkpoint = await self.checkpoint_store.load(resume_workflow_id)
            if checkpoint is None:
                raise WorkflowError(f"No checkpoint found for workflow '{resume_workflow_id}'")
            context = StateContext.from_checkpoint(checkpoint)
            current_state_name = context.current_state
        else:
            context = StateContext(input_data=input_data)
            current_state_name = self.initial_state

        transition_count = 0
        completed_states: list[str] = []  # For rollback tracking

        while current_state_name is not None and transition_count < self.max_transitions:
            state_node = self.states.get(current_state_name)
            if state_node is None:
                raise InvalidTransitionError(f"State '{current_state_name}' not found")

            # Update context
            previous_state = context.current_state
            context.current_state = current_state_name

            # Check circuit breaker
            if not state_node.circuit_breaker.can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker OPEN for state '{current_state_name}'"
                )

            # Checkpoint before execution
            await self.checkpoint_store.save(context.workflow_id, context.to_checkpoint())

            # Execute state with retries
            success = False
            last_error: Exception | None = None

            for attempt in range(state_node.max_retries + 1):
                try:
                    state_node.status = StateStatus.RUNNING
                    output = await state_node.run_with_timeout(context)
                    context.set_output(current_state_name, output)
                    state_node.status = StateStatus.COMPLETED
                    state_node.circuit_breaker.record_success()
                    success = True
                    break
                except Exception as e:
                    last_error = e
                    state_node.circuit_breaker.record_failure()
                    if attempt < state_node.max_retries:
                        await asyncio.sleep(1.0 * (attempt + 1))

            if not success:
                state_node.status = StateStatus.FAILED
                context.errors.append({
                    "state": current_state_name,
                    "error": str(last_error),
                    "timestamp": time.time(),
                })
                # Rollback completed states in reverse order
                await self._rollback(completed_states, context)
                raise WorkflowError(
                    f"State '{current_state_name}' failed after {state_node.max_retries + 1} attempts: {last_error}"
                )

            completed_states.append(current_state_name)

            # Determine next state
            next_state = state_node.get_next_state(context)

            # Record transition
            context.record_transition(
                from_state=current_state_name,
                to_state=next_state or "__END__",
                reason=f"State '{current_state_name}' completed successfully",
                actor="system",
            )

            current_state_name = next_state
            transition_count += 1

        # Cleanup checkpoint on successful completion
        await self.checkpoint_store.delete(context.workflow_id)

        return context

    async def _rollback(self, completed_states: list[str], context: StateContext) -> None:
        """Rollback completed states in reverse order."""
        for state_name in reversed(completed_states):
            state_node = self.states.get(state_name)
            if state_node and state_node.rollback_handler:
                try:
                    state_node.rollback(context)
                    context.record_transition(
                        from_state=state_name,
                        to_state=f"{state_name}__ROLLED_BACK",
                        reason="Rollback due to downstream failure",
                        actor="system",
                    )
                except Exception as e:
                    context.errors.append({
                        "state": state_name,
                        "error": f"Rollback failed: {e}",
                        "timestamp": time.time(),
                    })


# ============================================================
# EXAMPLE: Order Processing Workflow
# ============================================================

def validate_order(context: StateContext) -> Any:
    """Validate order data."""
    order = context.input_data.get("order", {})
    if not order.get("items"):
        raise ValueError("Order has no items")
    total = sum(item.get("price", 0) * item.get("quantity", 0) for item in order["items"])
    context.variables["order_total"] = total
    return {"valid": True, "total": total}


def check_order_value(context: StateContext) -> str:
    """Route based on order value."""
    total = context.variables.get("order_total", 0)
    if total > 1000:
        return "high_value"
    elif total > 100:
        return "medium_value"
    return "low_value"


def process_payment(context: StateContext) -> Any:
    """Process payment (simulated)."""
    total = context.variables.get("order_total", 0)
    context.variables["payment_id"] = f"PAY-{uuid.uuid4().hex[:8]}"
    return {"payment_id": context.variables["payment_id"], "amount": total}


def rollback_payment(context: StateContext) -> None:
    """Rollback payment (refund)."""
    payment_id = context.variables.get("payment_id")
    if payment_id:
        print(f"  ↩️ Refunding payment {payment_id}")
        context.variables["payment_refunded"] = True


def fulfill_order(context: StateContext) -> Any:
    """Create fulfillment record."""
    return {
        "fulfillment_id": f"FUL-{uuid.uuid4().hex[:8]}",
        "status": "shipped",
    }


def send_confirmation(context: StateContext) -> Any:
    """Send order confirmation."""
    return {"email_sent": True, "to": context.input_data.get("customer_email", "unknown")}


def build_order_workflow() -> WorkflowEngine:
    """Build the complete order processing workflow."""

    states: dict[str, StateNode] = {
        # 1. Validate incoming order
        "validate": FunctionState(
            name="validate",
            handler=validate_order,
            next_state="route_by_value",
            timeout_seconds=5.0,
        ),

        # 2. Route based on order value
        "route_by_value": ConditionalState(
            name="route_by_value",
            condition=check_order_value,
            routes={
                "high_value": "human_approval",
                "medium_value": "process_payment",
                "low_value": "process_payment",
            },
        ),

        # 3. Human approval for high-value orders
        "human_approval": HumanApprovalState(
            name="human_approval",
            approval_prompt="High-value order requires manager approval",
            approved_next="process_payment",
            rejected_next="order_rejected",
            timeout_seconds=3600.0,  # 1 hour timeout for human
        ),

        # 4. Process payment
        "process_payment": FunctionState(
            name="process_payment",
            handler=process_payment,
            next_state="fulfill",
            timeout_seconds=30.0,
            rollback_handler=rollback_payment,
        ),

        # 5. Fulfill order
        "fulfill": FunctionState(
            name="fulfill",
            handler=fulfill_order,
            next_state="confirm",
            timeout_seconds=15.0,
        ),

        # 6. Send confirmation
        "confirm": FunctionState(
            name="confirm",
            handler=send_confirmation,
            next_state="completed",
            timeout_seconds=10.0,
        ),

        # Terminal states
        "completed": TerminalState(name="completed"),
        "order_rejected": TerminalState(
            name="order_rejected",
            handler=lambda ctx: {"status": "rejected", "reason": "Manager disapproved"},
        ),
    }

    return WorkflowEngine(states=states, initial_state="validate")


# ============================================================
# MAIN
# ============================================================

async def main():
    """Demonstrate the workflow agent."""
    engine = build_order_workflow()

    # Simulate an order
    order_data = {
        "order": {
            "items": [
                {"name": "Laptop", "price": 1200.00, "quantity": 1},
                {"name": "Mouse", "price": 25.00, "quantity": 2},
            ]
        },
        "customer_email": "customer@example.com",
    }

    print("=" * 60)
    print("ORDER PROCESSING WORKFLOW")
    print("=" * 60)

    context = await engine.run(input_data=order_data)

    print(f"\n{'='*60}")
    print(f"Workflow ID: {context.workflow_id}")
    print(f"Final State: {context.current_state}")
    print(f"Variables: {json.dumps(context.variables, indent=2)}")
    print(f"\nTransition Audit Trail:")
    for t in context.transitions:
        print(f"  [{t.actor}] {t.from_state} → {t.to_state} ({t.reason})")
    print(f"\nState Outputs:")
    for state_name, output in context.state_outputs.items():
        print(f"  {state_name}: {output}")
    if context.errors:
        print(f"\nErrors:")
        for err in context.errors:
            print(f"  {err['state']}: {err['error']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
