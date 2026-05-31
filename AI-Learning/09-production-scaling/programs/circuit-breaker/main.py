"""
Circuit Breaker for AI Model Endpoints
=======================================
Implements the circuit breaker pattern:
- CLOSED: Normal operation, requests pass through
- OPEN: Failing fast, all requests use fallback
- HALF-OPEN: Testing recovery with single request

Simulates: healthy endpoint → failure → circuit opens → recovery
"""

import asyncio
import time
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable


# --- Circuit Breaker States ---

class State(Enum):
    CLOSED = "CLOSED"       # Normal - requests pass through
    OPEN = "OPEN"           # Failing - reject immediately, use fallback
    HALF_OPEN = "HALF_OPEN" # Testing - allow one request to test recovery


# --- Circuit Breaker Implementation ---

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3      # Failures before opening
    success_threshold: int = 2      # Successes in half-open before closing
    recovery_timeout: float = 10.0  # Seconds before trying half-open
    name: str = "default"


class CircuitBreaker:
    """
    Circuit Breaker Pattern.
    
    Like an electrical circuit breaker:
    - Normal current (requests succeed) → breaker stays CLOSED
    - Overcurrent (too many failures) → breaker OPENS (cuts the circuit)
    - After cooling period → breaker goes HALF-OPEN (test with one request)
    - Test succeeds → breaker CLOSES (normal operation resumes)
    - Test fails → breaker stays OPEN (wait more)
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = State.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.state_change_log: list[dict] = []

    def _log_state_change(self, from_state: State, to_state: State, reason: str):
        entry = {
            "time": time.time(),
            "from": from_state.value,
            "to": to_state.value,
            "reason": reason,
            "breaker": self.config.name,
        }
        self.state_change_log.append(entry)
        timestamp = time.strftime("%H:%M:%S")
        print(f"  [{timestamp}] Circuit '{self.config.name}': {from_state.value} → {to_state.value} ({reason})")

    def can_execute(self) -> bool:
        """Check if a request should be allowed through."""
        if self.state == State.CLOSED:
            return True
        
        if self.state == State.OPEN:
            # Check if recovery timeout has elapsed
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self._log_state_change(State.OPEN, State.HALF_OPEN, "recovery timeout elapsed")
                self.state = State.HALF_OPEN
                self.success_count = 0
                return True
            return False
        
        if self.state == State.HALF_OPEN:
            return True  # Allow test requests
        
        return False

    def record_success(self):
        """Record a successful request."""
        if self.state == State.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._log_state_change(State.HALF_OPEN, State.CLOSED, f"{self.success_count} consecutive successes")
                self.state = State.CLOSED
                self.failure_count = 0
        elif self.state == State.CLOSED:
            self.failure_count = 0  # Reset on success

    def record_failure(self):
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == State.HALF_OPEN:
            self._log_state_change(State.HALF_OPEN, State.OPEN, "test request failed")
            self.state = State.OPEN
        elif self.state == State.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._log_state_change(State.CLOSED, State.OPEN, f"{self.failure_count} failures exceeded threshold")
                self.state = State.OPEN


# --- Simulated Model Endpoints ---

class SimulatedModelEndpoint:
    """Simulates an AI model endpoint that can be healthy or failing."""

    def __init__(self, name: str, latency_range: tuple = (0.1, 0.5)):
        self.name = name
        self.latency_range = latency_range
        self.is_healthy = True

    async def call(self, prompt: str) -> str:
        """Simulate a model API call."""
        latency = random.uniform(*self.latency_range)
        await asyncio.sleep(latency)
        
        if not self.is_healthy:
            raise Exception(f"Model '{self.name}' unavailable: 503 Service Unavailable")
        
        return f"[{self.name}] Response to: {prompt[:30]}"


# --- Resilient Model Client ---

class ResilientModelClient:
    """
    Model client with circuit breaker and automatic fallback.
    
    Primary model → (if failing) → Secondary model → (if failing) → Error
    """

    def __init__(self):
        self.primary = SimulatedModelEndpoint("GPT-4", latency_range=(0.2, 0.8))
        self.secondary = SimulatedModelEndpoint("GPT-3.5-Fallback", latency_range=(0.1, 0.3))
        
        self.primary_breaker = CircuitBreaker(CircuitBreakerConfig(
            name="primary-gpt4",
            failure_threshold=3,
            recovery_timeout=10.0,
            success_threshold=2,
        ))
        
        self.stats = {"primary": 0, "fallback": 0, "failed": 0}

    async def call(self, prompt: str) -> tuple[str, str]:
        """
        Call model with circuit breaker protection.
        Returns (response, model_used).
        """
        # Try primary (if circuit allows)
        if self.primary_breaker.can_execute():
            try:
                response = await self.primary.call(prompt)
                self.primary_breaker.record_success()
                self.stats["primary"] += 1
                return response, "primary"
            except Exception:
                self.primary_breaker.record_failure()
        
        # Fallback to secondary
        try:
            response = await self.secondary.call(prompt)
            self.stats["fallback"] += 1
            return response, "fallback"
        except Exception:
            self.stats["failed"] += 1
            return "Error: All models unavailable", "none"


# --- Demo Simulation ---

async def main():
    print("=" * 60)
    print("     CIRCUIT BREAKER DEMO")
    print("=" * 60)
    print()
    print("Scenario: Primary model (GPT-4) fails, circuit opens,")
    print("          traffic routes to fallback (GPT-3.5),")
    print("          primary recovers, circuit closes.")
    print()
    print("Configuration:")
    print("  Failure threshold: 3 (opens after 3 failures)")
    print("  Recovery timeout:  10s (tests recovery after 10s)")
    print("  Success threshold: 2 (closes after 2 successes)")
    print()
    print("-" * 60)
    print("SIMULATION TIMELINE:")
    print("-" * 60)
    print()

    client = ResilientModelClient()
    
    # Phase 1: Normal operation (0-5 seconds)
    print("Phase 1: Normal operation (primary model healthy)")
    print()
    for i in range(5):
        response, model_used = await client.call(f"Question {i+1}")
        status = "✓" if model_used == "primary" else "⚡"
        print(f"  {status} Request {i+1}: {model_used:<10} | {response[:40]}")
        await asyncio.sleep(0.3)

    # Phase 2: Primary starts failing
    print(f"\n{'─' * 60}")
    print("Phase 2: Primary model FAILS (simulating outage)")
    print(f"{'─' * 60}\n")
    client.primary.is_healthy = False

    for i in range(6):
        response, model_used = await client.call(f"Question {i+6}")
        status = "✓" if model_used == "primary" else "⚡" if model_used == "fallback" else "✗"
        breaker_state = client.primary_breaker.state.value
        print(f"  {status} Request {i+6}: {model_used:<10} | Circuit: {breaker_state:<10} | {response[:35]}")
        await asyncio.sleep(0.5)

    # Phase 3: Wait for recovery timeout
    print(f"\n{'─' * 60}")
    print(f"Phase 3: Waiting for recovery timeout (10 seconds)...")
    print(f"{'─' * 60}\n")
    
    # Wait in increments showing time passing
    for sec in range(10):
        await asyncio.sleep(1)
        print(f"  ... {sec+1}s elapsed (circuit still OPEN, using fallback)")

    # Phase 4: Primary recovers
    print(f"\n{'─' * 60}")
    print("Phase 4: Primary model RECOVERS")
    print(f"{'─' * 60}\n")
    client.primary.is_healthy = True

    for i in range(5):
        response, model_used = await client.call(f"Question {i+12}")
        status = "✓" if model_used == "primary" else "⚡"
        breaker_state = client.primary_breaker.state.value
        print(f"  {status} Request {i+12}: {model_used:<10} | Circuit: {breaker_state:<10} | {response[:35]}")
        await asyncio.sleep(0.5)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Requests via primary model:  {client.stats['primary']}")
    print(f"  Requests via fallback model: {client.stats['fallback']}")
    print(f"  Total failures:              {client.stats['failed']}")
    print(f"\n  State transitions:")
    for log in client.primary_breaker.state_change_log:
        print(f"    {log['from']} → {log['to']} ({log['reason']})")
    
    print(f"\n  Result: Circuit breaker protected the system!")
    print(f"  Users experienced degraded service (fallback model)")
    print(f"  instead of errors during the outage.")


if __name__ == "__main__":
    asyncio.run(main())
