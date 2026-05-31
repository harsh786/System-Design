"""
Event-Driven AI Processing Simulator
======================================
Simulates a Kafka-like event stream with AI consumers that classify and enrich
events, demonstrating backpressure handling, DLQ routing, exactly-once semantics,
and the saga pattern for multi-step AI processing.

Run: python3 main.py
No dependencies required (standard library only).
"""

import hashlib
import json
import random
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Event System (Kafka-like)
# =============================================================================

class EventType(Enum):
    CUSTOMER_MESSAGE = "customer_message"
    TRANSACTION = "transaction"
    SYSTEM_ALERT = "system_alert"
    USER_ACTION = "user_action"


@dataclass
class Event:
    event_id: str
    event_type: EventType
    payload: dict
    timestamp: float
    partition_key: str
    offset: int = 0
    retries: int = 0


class Topic:
    """Simulated Kafka topic with partitions."""

    def __init__(self, name: str, partitions: int = 4):
        self.name = name
        self.partitions: list = [deque() for _ in range(partitions)]
        self.offsets: dict = {}  # consumer_group -> partition -> offset
        self._next_offset = [0] * partitions
        self._lock = threading.Lock()

    def produce(self, event: Event):
        partition = hash(event.partition_key) % len(self.partitions)
        with self._lock:
            event.offset = self._next_offset[partition]
            self._next_offset[partition] += 1
            self.partitions[partition].append(event)

    def consume(self, consumer_group: str, partition: int) -> Optional[Event]:
        key = f"{consumer_group}:{partition}"
        with self._lock:
            current_offset = self.offsets.get(key, 0)
            if current_offset < len(self.partitions[partition]):
                event = self.partitions[partition][current_offset]
                return event
            return None

    def commit(self, consumer_group: str, partition: int):
        key = f"{consumer_group}:{partition}"
        with self._lock:
            self.offsets[key] = self.offsets.get(key, 0) + 1

    def lag(self, consumer_group: str) -> int:
        total_lag = 0
        for p in range(len(self.partitions)):
            key = f"{consumer_group}:{p}"
            committed = self.offsets.get(key, 0)
            total_lag += len(self.partitions[p]) - committed
        return total_lag


# =============================================================================
# Idempotency Cache (Exactly-Once Semantics)
# =============================================================================

class IdempotencyCache:
    """Caches AI processing results for exactly-once semantics."""

    def __init__(self, max_size: int = 10000):
        self.cache: dict = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get_key(self, event: Event, model_version: str) -> str:
        return hashlib.sha256(
            f"{event.event_id}:{model_version}".encode()
        ).hexdigest()[:16]

    def get(self, event: Event, model_version: str) -> Optional[dict]:
        key = self.get_key(event, model_version)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    def put(self, event: Event, model_version: str, result: dict):
        key = self.get_key(event, model_version)
        if len(self.cache) >= self.max_size:
            # Evict oldest (simplified)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[key] = result


# =============================================================================
# Dead Letter Queue
# =============================================================================

class DeadLetterQueue:
    """DLQ for failed AI processing."""

    def __init__(self):
        self.events: list = []
        self.failure_reasons: dict = {}  # reason -> count

    def send(self, event: Event, reason: str, error: str = ""):
        self.events.append({
            "event": event,
            "reason": reason,
            "error": error,
            "timestamp": time.time(),
            "retries_exhausted": event.retries
        })
        self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1

    def stats(self) -> dict:
        return {
            "total": len(self.events),
            "by_reason": dict(self.failure_reasons)
        }


# =============================================================================
# AI Processing (Simulated)
# =============================================================================

class AIClassifier:
    """Simulates LLM-based event classification."""

    MODEL_VERSION = "classifier-v2.1"

    def __init__(self, failure_rate: float = 0.05, avg_latency: float = 0.1):
        self.failure_rate = failure_rate
        self.avg_latency = avg_latency
        self.calls = 0
        self.total_latency = 0.0

    def classify(self, event: Event) -> dict:
        """Classify event with simulated AI processing."""
        self.calls += 1

        # Simulate latency
        latency = random.exponential(self.avg_latency)
        self.total_latency += latency

        # Simulate failures
        if random.random() < self.failure_rate:
            raise RuntimeError("Model returned unparseable response")

        # Simulate classification based on event type
        if event.event_type == EventType.CUSTOMER_MESSAGE:
            text = event.payload.get("text", "")
            sentiment = random.uniform(-1, 1)
            # Bias sentiment based on keywords
            if any(w in text.lower() for w in ["angry", "cancel", "terrible", "worst"]):
                sentiment = random.uniform(-1, -0.5)
            elif any(w in text.lower() for w in ["great", "love", "amazing", "thanks"]):
                sentiment = random.uniform(0.5, 1)

            intents = ["question", "complaint", "feedback", "cancellation", "upgrade"]
            intent = random.choice(intents)
            urgency = "critical" if sentiment < -0.7 else "normal"

            return {
                "intent": intent,
                "sentiment": round(sentiment, 3),
                "urgency": urgency,
                "confidence": round(random.uniform(0.75, 0.99), 3)
            }

        elif event.event_type == EventType.TRANSACTION:
            amount = event.payload.get("amount", 0)
            fraud_score = random.uniform(0, 0.3)
            if amount > 5000:
                fraud_score += random.uniform(0.2, 0.5)
            if event.payload.get("country") != event.payload.get("home_country"):
                fraud_score += random.uniform(0.1, 0.3)
            fraud_score = min(fraud_score, 1.0)

            return {
                "fraud_score": round(fraud_score, 3),
                "risk_level": "high" if fraud_score > 0.7 else "medium" if fraud_score > 0.4 else "low",
                "flags": ["unusual_amount"] if amount > 5000 else [],
                "confidence": round(random.uniform(0.80, 0.99), 3)
            }

        elif event.event_type == EventType.SYSTEM_ALERT:
            severity = event.payload.get("severity", 5)
            return {
                "category": random.choice(["performance", "error", "security", "capacity"]),
                "auto_remediation": severity < 7,
                "diagnosis": f"Likely caused by {random.choice(['traffic spike', 'memory leak', 'connection pool', 'disk full'])}",
                "confidence": round(random.uniform(0.70, 0.95), 3)
            }

        return {"category": "unknown", "confidence": 0.5}


# =============================================================================
# Saga Pattern for Multi-Step AI Processing
# =============================================================================

class SagaStep(Enum):
    CLASSIFY = "classify"
    ENRICH = "enrich"
    DECIDE = "decide"
    ACT = "act"
    COMPLETE = "complete"
    COMPENSATE = "compensate"


@dataclass
class SagaState:
    saga_id: str
    event: Event
    current_step: SagaStep
    results: dict = field(default_factory=dict)
    started_at: float = 0.0
    completed_at: float = 0.0
    failed: bool = False
    failure_reason: str = ""


class SagaOrchestrator:
    """Orchestrates multi-step AI processing with compensation."""

    def __init__(self, classifier: AIClassifier):
        self.classifier = classifier
        self.sagas: list = []
        self.completed = 0
        self.failed = 0

    def execute(self, event: Event) -> SagaState:
        saga = SagaState(
            saga_id=f"saga_{event.event_id}",
            event=event,
            current_step=SagaStep.CLASSIFY,
            started_at=time.time()
        )

        try:
            # Step 1: Classify
            saga.current_step = SagaStep.CLASSIFY
            classification = self.classifier.classify(event)
            saga.results["classification"] = classification

            # Step 2: Enrich with context
            saga.current_step = SagaStep.ENRICH
            enrichment = self._enrich(event, classification)
            saga.results["enrichment"] = enrichment

            # Step 3: Decision
            saga.current_step = SagaStep.DECIDE
            decision = self._decide(classification, enrichment)
            saga.results["decision"] = decision

            # Step 4: Act
            saga.current_step = SagaStep.ACT
            action_result = self._act(decision)
            saga.results["action"] = action_result

            # Complete
            saga.current_step = SagaStep.COMPLETE
            saga.completed_at = time.time()
            self.completed += 1

        except Exception as e:
            saga.failed = True
            saga.failure_reason = str(e)
            saga.current_step = SagaStep.COMPENSATE
            self._compensate(saga)
            self.failed += 1

        self.sagas.append(saga)
        return saga

    def _enrich(self, event: Event, classification: dict) -> dict:
        """Simulate context enrichment."""
        return {
            "user_history_length": random.randint(1, 100),
            "related_events": random.randint(0, 5),
            "user_tier": random.choice(["free", "pro", "enterprise"]),
        }

    def _decide(self, classification: dict, enrichment: dict) -> dict:
        """Simulate decision making based on classification + context."""
        confidence = classification.get("confidence", 0.5)
        if confidence < 0.6:
            return {"action": "human_review", "reason": "low_confidence"}

        urgency = classification.get("urgency", "normal")
        tier = enrichment.get("user_tier", "free")

        if urgency == "critical" and tier == "enterprise":
            return {"action": "immediate_escalation", "priority": 1}
        elif urgency == "critical":
            return {"action": "queue_escalation", "priority": 2}
        else:
            return {"action": "auto_respond", "priority": 3}

    def _act(self, decision: dict) -> dict:
        """Simulate action execution."""
        # Simulate 5% action failure
        if random.random() < 0.05:
            raise RuntimeError("Action execution failed: downstream service unavailable")
        return {"status": "executed", "action": decision["action"]}

    def _compensate(self, saga: SagaState):
        """Rollback/compensate for failed saga steps."""
        saga.results["compensation"] = {
            "rolled_back_steps": [s.value for s in SagaStep
                                  if s.value in ["act", "decide", "enrich"]
                                  and s.value in [step for step in saga.results]],
            "reason": saga.failure_reason
        }


# =============================================================================
# Backpressure Manager
# =============================================================================

class BackpressureManager:
    """Manages backpressure when AI processing can't keep up."""

    def __init__(self, high_watermark: int = 100, low_watermark: int = 20):
        self.high_watermark = high_watermark
        self.low_watermark = low_watermark
        self.current_mode = "normal"  # normal, degraded, shedding
        self.mode_changes: list = []

    def evaluate(self, lag: int, processing_rate: float, arrival_rate: float) -> str:
        """Determine processing mode based on current state."""
        previous_mode = self.current_mode

        if lag > self.high_watermark * 2:
            self.current_mode = "shedding"
        elif lag > self.high_watermark:
            self.current_mode = "degraded"
        elif lag < self.low_watermark:
            self.current_mode = "normal"

        if self.current_mode != previous_mode:
            self.mode_changes.append({
                "from": previous_mode,
                "to": self.current_mode,
                "lag": lag
            })

        return self.current_mode

    def should_process(self, event: Event) -> tuple:
        """Decide whether to process, degrade, or shed this event."""
        if self.current_mode == "normal":
            return True, "full"
        elif self.current_mode == "degraded":
            # Process all but with faster/simpler model
            return True, "fast"
        else:  # shedding
            # Only process high-priority events
            if event.event_type == EventType.TRANSACTION:
                return True, "fast"  # Always process transactions
            elif event.payload.get("priority", 5) <= 3:
                return True, "fast"
            else:
                return False, "shed"


# =============================================================================
# Event Producer (Simulated Workload)
# =============================================================================

def generate_events(topic: Topic, count: int = 200):
    """Generate a realistic stream of events."""
    event_templates = [
        (EventType.CUSTOMER_MESSAGE, [
            {"text": "I'm really angry about my order being late", "user_id": "u100"},
            {"text": "Thanks for the great service!", "user_id": "u101"},
            {"text": "I want to cancel my subscription immediately", "user_id": "u102"},
            {"text": "How do I upgrade my plan?", "user_id": "u103"},
            {"text": "This is the worst experience ever", "user_id": "u104"},
            {"text": "Can you help with my billing question?", "user_id": "u105"},
        ]),
        (EventType.TRANSACTION, [
            {"amount": 49.99, "merchant": "coffee-shop", "country": "US", "home_country": "US", "user_id": "u200"},
            {"amount": 8500, "merchant": "electronics", "country": "NG", "home_country": "US", "user_id": "u201"},
            {"amount": 12.00, "merchant": "streaming", "country": "US", "home_country": "US", "user_id": "u202"},
            {"amount": 3200, "merchant": "travel", "country": "JP", "home_country": "UK", "user_id": "u203"},
        ]),
        (EventType.SYSTEM_ALERT, [
            {"service": "payment-api", "metric": "latency_p99", "value": 5200, "severity": 8},
            {"service": "auth-service", "metric": "error_rate", "value": 0.05, "severity": 6},
            {"service": "search", "metric": "cpu_usage", "value": 92, "severity": 7},
        ]),
    ]

    for i in range(count):
        event_type, templates = random.choice(event_templates)
        payload = random.choice(templates).copy()
        user_id = payload.get("user_id", f"system_{i}")

        event = Event(
            event_id=f"evt_{i:04d}",
            event_type=event_type,
            payload=payload,
            timestamp=time.time() + i * 0.01,
            partition_key=user_id
        )
        topic.produce(event)


# =============================================================================
# Main Consumer Loop
# =============================================================================

def run_consumer(topic: Topic, output_topic: Topic, dlq: DeadLetterQueue,
                 classifier: AIClassifier, cache: IdempotencyCache,
                 backpressure: BackpressureManager, saga: SagaOrchestrator,
                 max_retries: int = 3):
    """Main event processing loop."""
    consumer_group = "ai-processor"
    processed = 0
    shed_count = 0
    saga_events = 0

    for partition in range(len(topic.partitions)):
        while True:
            event = topic.consume(consumer_group, partition)
            if event is None:
                break

            # Check backpressure
            lag = topic.lag(consumer_group)
            mode = backpressure.evaluate(lag, processed / max(1, time.time()), 100)
            should_process, quality = backpressure.should_process(event)

            if not should_process:
                # Load shedding - send to DLQ for later batch processing
                dlq.send(event, "load_shed", "Backpressure shedding active")
                topic.commit(consumer_group, partition)
                shed_count += 1
                continue

            # Check idempotency cache
            cached_result = cache.get(event, classifier.MODEL_VERSION)
            if cached_result:
                # Exactly-once: use cached result
                enriched_event = Event(
                    event_id=f"{event.event_id}_enriched",
                    event_type=event.event_type,
                    payload={**event.payload, "ai_result": cached_result},
                    timestamp=time.time(),
                    partition_key=event.partition_key
                )
                output_topic.produce(enriched_event)
                topic.commit(consumer_group, partition)
                processed += 1
                continue

            # Use saga for complex events, simple classification for others
            use_saga = (event.event_type == EventType.CUSTOMER_MESSAGE and
                        event.payload.get("text", "").lower().find("cancel") >= 0)

            try:
                if use_saga:
                    saga_state = saga.execute(event)
                    result = saga_state.results
                    saga_events += 1
                else:
                    result = classifier.classify(event)

                # Cache result for exactly-once
                cache.put(event, classifier.MODEL_VERSION, result)

                # Produce enriched event
                enriched_event = Event(
                    event_id=f"{event.event_id}_enriched",
                    event_type=event.event_type,
                    payload={**event.payload, "ai_result": result},
                    timestamp=time.time(),
                    partition_key=event.partition_key
                )
                output_topic.produce(enriched_event)
                topic.commit(consumer_group, partition)
                processed += 1

            except Exception as e:
                event.retries += 1
                if event.retries >= max_retries:
                    dlq.send(event, "max_retries_exceeded", str(e))
                    topic.commit(consumer_group, partition)
                else:
                    # In real system: put back with delay
                    # Here: just retry immediately
                    try:
                        result = classifier.classify(event)
                        cache.put(event, classifier.MODEL_VERSION, result)
                        enriched_event = Event(
                            event_id=f"{event.event_id}_enriched",
                            event_type=event.event_type,
                            payload={**event.payload, "ai_result": result},
                            timestamp=time.time(),
                            partition_key=event.partition_key
                        )
                        output_topic.produce(enriched_event)
                        topic.commit(consumer_group, partition)
                        processed += 1
                    except Exception:
                        dlq.send(event, "persistent_failure", str(e))
                        topic.commit(consumer_group, partition)

    return processed, shed_count, saga_events


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 70)
    print("EVENT-DRIVEN AI PROCESSING SIMULATOR")
    print("=" * 70)

    random.seed(42)

    # Initialize infrastructure
    input_topic = Topic("raw-events", partitions=4)
    output_topic = Topic("enriched-events", partitions=4)
    dlq = DeadLetterQueue()
    classifier = AIClassifier(failure_rate=0.08, avg_latency=0.1)
    cache = IdempotencyCache(max_size=5000)
    backpressure = BackpressureManager(high_watermark=50, low_watermark=10)
    saga = SagaOrchestrator(classifier)

    # Generate events
    event_count = 200
    print(f"\n[Producer] Generating {event_count} events...")
    generate_events(input_topic, count=event_count)

    total_in_partitions = sum(len(p) for p in input_topic.partitions)
    print(f"[Producer] Events distributed across {len(input_topic.partitions)} partitions:")
    for i, p in enumerate(input_topic.partitions):
        print(f"  Partition {i}: {len(p)} events")

    # Process events
    print(f"\n[Consumer] Starting AI processing...")
    print(f"  Model: {classifier.MODEL_VERSION}")
    print(f"  Failure rate: {classifier.failure_rate * 100:.0f}%")
    print(f"  Max retries: 3")
    print(f"  Backpressure high watermark: {backpressure.high_watermark}")

    start_time = time.time()
    processed, shed_count, saga_events = run_consumer(
        input_topic, output_topic, dlq, classifier, cache, backpressure, saga
    )
    elapsed = time.time() - start_time

    # =========================================================================
    # Results and Metrics
    # =========================================================================
    print(f"\n\n{'=' * 70}")
    print("PROCESSING RESULTS")
    print(f"{'=' * 70}")

    print(f"\n  Events produced:     {total_in_partitions}")
    print(f"  Events processed:    {processed}")
    print(f"  Events shed:         {shed_count}")
    print(f"  Events in DLQ:       {dlq.stats()['total']}")
    print(f"  Output events:       {sum(len(p) for p in output_topic.partitions)}")
    print(f"  Processing time:     {elapsed:.3f}s")
    print(f"  Throughput:          {processed / max(elapsed, 0.001):.0f} events/sec")

    # Exactly-once metrics
    print(f"\n{'─' * 40}")
    print("EXACTLY-ONCE SEMANTICS")
    print(f"{'─' * 40}")
    print(f"  Cache size:          {len(cache.cache)}")
    print(f"  Cache hits:          {cache.hits}")
    print(f"  Cache misses:        {cache.misses}")
    hit_rate = cache.hits / max(cache.hits + cache.misses, 1) * 100
    print(f"  Hit rate:            {hit_rate:.1f}%")

    # DLQ breakdown
    print(f"\n{'─' * 40}")
    print("DEAD LETTER QUEUE")
    print(f"{'─' * 40}")
    dlq_stats = dlq.stats()
    print(f"  Total DLQ events:    {dlq_stats['total']}")
    print(f"  By reason:")
    for reason, count in dlq_stats.get("by_reason", {}).items():
        print(f"    {reason:25s}: {count}")

    # Backpressure
    print(f"\n{'─' * 40}")
    print("BACKPRESSURE")
    print(f"{'─' * 40}")
    print(f"  Mode changes:        {len(backpressure.mode_changes)}")
    for change in backpressure.mode_changes[:5]:
        print(f"    {change['from']} → {change['to']} (lag: {change['lag']})")
    print(f"  Final mode:          {backpressure.current_mode}")

    # Saga pattern
    print(f"\n{'─' * 40}")
    print("SAGA PATTERN (Multi-Step AI)")
    print(f"{'─' * 40}")
    print(f"  Sagas executed:      {len(saga.sagas)}")
    print(f"  Completed:           {saga.completed}")
    print(f"  Failed (compensated):{saga.failed}")
    if saga.sagas:
        sample = saga.sagas[0]
        print(f"\n  Sample saga: {sample.saga_id}")
        print(f"    Steps completed: {list(sample.results.keys())}")
        print(f"    Failed: {sample.failed}")
        if "classification" in sample.results:
            print(f"    Classification: {json.dumps(sample.results['classification'], indent=6)}")

    # AI Model metrics
    print(f"\n{'─' * 40}")
    print("AI MODEL METRICS")
    print(f"{'─' * 40}")
    print(f"  Total AI calls:      {classifier.calls}")
    avg_latency = classifier.total_latency / max(classifier.calls, 1)
    print(f"  Avg latency:         {avg_latency * 1000:.1f}ms")
    print(f"  Failure rate:        {classifier.failure_rate * 100:.0f}% configured")

    # Sample enriched events
    print(f"\n{'─' * 40}")
    print("SAMPLE ENRICHED EVENTS")
    print(f"{'─' * 40}")
    shown = 0
    for partition in output_topic.partitions:
        for event in partition:
            if shown >= 5:
                break
            ai_result = event.payload.get("ai_result", {})
            print(f"\n  Event: {event.event_id}")
            print(f"    Type: {event.event_type.value}")
            if "sentiment" in ai_result:
                print(f"    Sentiment: {ai_result['sentiment']}, Intent: {ai_result.get('intent')}")
            elif "fraud_score" in ai_result:
                print(f"    Fraud score: {ai_result['fraud_score']}, Risk: {ai_result.get('risk_level')}")
            elif "classification" in ai_result:
                cls = ai_result["classification"]
                print(f"    [SAGA] Classification: {cls.get('intent')}, Decision: {ai_result.get('decision', {}).get('action')}")
            elif "category" in ai_result:
                print(f"    Category: {ai_result['category']}, Auto-fix: {ai_result.get('auto_remediation')}")
            shown += 1
        if shown >= 5:
            break

    print(f"\n{'=' * 70}")
    print("Event-driven AI simulation complete.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
