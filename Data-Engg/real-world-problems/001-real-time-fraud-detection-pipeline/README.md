# Problem 1: Real-Time Fraud Detection Pipeline

## Problem 1: Real-Time Fraud Detection Pipeline

### Business Context
A fintech company processes 50,000 transactions/second. They need to detect fraudulent
transactions in <100ms to block them before settlement.

### Why This Architecture?

```
REQUIREMENTS:
- Latency: <100ms (must block before settlement)
- Throughput: 50K txn/sec (peak 200K during flash sales)
- Accuracy: <0.1% false positive rate
- Availability: 99.99% (4 minutes downtime/month max)

WHY STREAM PROCESSING (not batch)?
→ Batch: Even 1-minute delay = $millions in fraud goes through
→ Must evaluate EACH transaction before approving

WHY KAFKA + FLINK (not Spark Streaming)?
→ Kafka: Exactly-once, replay capability, 50K msg/s easily
→ Flink: True event-time processing, ms latency, stateful
→ Spark Streaming: Micro-batch (100ms minimum) too slow

WHY FEATURE STORE (not inline computation)?
→ Features like "avg spend last 30 days" can't be computed inline
→ Pre-computed features: O(1) lookup vs O(n) computation
→ Shared between real-time and batch ML training
```

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              REAL-TIME FRAUD DETECTION ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  TRANSACTION SOURCES                                            │         │
│  │  [POS Terminals] [Online Checkout] [Mobile App] [Wire Transfer] │         │
│  └──────────────────────────────┬─────────────────────────────────┘         │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────┐       │
│  │  API GATEWAY (Rate Limiting + Initial Validation)                 │       │
│  │  • Schema validation                                              │       │
│  │  • Rate limiting per merchant                                     │       │
│  │  • TLS termination                                                │       │
│  └───────────────────────────────┬──────────────────────────────────┘       │
│                                   │                                          │
│  ┌────────────────────────────────▼─────────────────────────────────┐       │
│  │  KAFKA CLUSTER (Event Backbone)                                    │       │
│  │  Topic: transactions.raw (32 partitions, RF=3)                     │       │
│  │  Throughput: 50K msgs/sec × 1KB = 50 MB/s                         │       │
│  │  Retention: 7 days (for replay/investigation)                      │       │
│  └────────┬──────────────────────────────────────┬──────────────────┘       │
│           │                                       │                          │
│  ┌────────▼──────────────────────────┐  ┌────────▼──────────────────┐       │
│  │  FLINK JOB: Feature Enrichment    │  │  FLINK JOB: Rule Engine   │       │
│  │                                    │  │                           │        │
│  │  For each transaction:             │  │  Hard rules (instant):    │        │
│  │  1. Lookup user features           │  │  • Amount > $10K → review│        │
│  │  2. Lookup merchant features       │  │  • Country blacklist      │        │
│  │  3. Compute real-time features:    │  │  • Velocity (>5 in 1min) │        │
│  │     • Txn count last 5 min         │  │  • Card testing pattern  │        │
│  │     • Geo-velocity (miles/hour)    │  │                           │        │
│  │     • Amount deviation from avg    │  │  Produces: BLOCK/ALLOW    │        │
│  │  4. Emit enriched transaction      │  │  Latency: <5ms           │        │
│  │                                    │  │                           │        │
│  │  State: RocksDB (per-user stats)   │  └───────────┬───────────────┘       │
│  │  Latency: <20ms                    │              │                       │
│  └────────┬───────────────────────────┘              │                       │
│           │                                          │                       │
│  ┌────────▼──────────────────────────┐              │                       │
│  │  ML SCORING SERVICE               │              │                       │
│  │  (Real-time inference)            │              │                        │
│  │                                    │              │                       │
│  │  Model: XGBoost / Neural Network  │              │                        │
│  │  Features: 200+ dimensions        │              │                        │
│  │  Latency: <30ms (P99)            │              │                        │
│  │  Output: fraud_score [0.0 - 1.0]  │              │                        │
│  │                                    │              │                       │
│  │  WHY XGBoost:                      │              │                       │
│  │  • Fast inference (<1ms)           │              │                       │
│  │  • Good with tabular features      │              │                       │
│  │  • Interpretable (SHAP values)     │              │                       │
│  └────────┬───────────────────────────┘              │                       │
│           │                                          │                       │
│  ┌────────▼──────────────────────────────────────────▼───────────────┐      │
│  │  DECISION ENGINE (Combine rules + ML score)                        │      │
│  │                                                                    │      │
│  │  Logic:                                                            │      │
│  │  if rule_result == BLOCK: → BLOCK (hard rule override)             │      │
│  │  elif ml_score > 0.9: → BLOCK                                     │      │
│  │  elif ml_score > 0.7: → REVIEW (manual queue)                     │      │
│  │  else: → ALLOW                                                    │      │
│  │                                                                    │      │
│  │  Total latency budget: <100ms                                      │      │
│  │  ┌──────────────────────────────────────────┐                     │      │
│  │  │ Kafka(5ms) + Enrich(20ms) + ML(30ms)     │                     │      │
│  │  │ + Decision(5ms) + Response(10ms) = 70ms  │                     │      │
│  │  │ Buffer: 30ms for network/retry            │                     │      │
│  │  └──────────────────────────────────────────┘                     │      │
│  └────────┬──────────────────────────────────────────────────────────┘      │
│           │                                                                  │
│  ┌────────▼──────────────────────────────────────────────────────────┐      │
│  │  FEEDBACK LOOP                                                     │      │
│  │                                                                    │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │      │
│  │  │ Decision Log │  │ Model Retrain│  │ Feature Store│             │      │
│  │  │ (S3/Iceberg) │  │ (Daily batch)│  │ Update       │             │      │
│  │  │              │  │              │  │ (Streaming)  │             │      │
│  │  │ For audit    │  │ Spark + MLflow│ │ Redis + Flink│            │      │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │      │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Scalability Design
```
HORIZONTAL SCALING:
───────────────────
Kafka: 32 partitions → 32 parallel consumers
Flink: 32 TaskManager slots (1:1 with Kafka partitions)
ML Service: 20 pods behind load balancer (GPU instances)
Feature Store (Redis): 6-node cluster, 100GB RAM total

CAPACITY PLANNING:
──────────────────
Normal: 50K txn/s × 1KB = 50 MB/s
Peak (Black Friday): 200K txn/s × 1KB = 200 MB/s
Kafka can handle: 500 MB/s per cluster (headroom: 2.5x)
Flink can handle: 1M events/s with enrichment (headroom: 5x)

FAILURE SCENARIOS:
──────────────────
• Flink failure: Checkpoint recovery (<3 min), rules still block
• ML service down: Fall back to rules-only (higher false positives)
• Redis down: Use stale features from backup, flag for review
• Kafka broker loss: ISR replication, automatic failover
```

### Runnable Code
```python
"""
Real-Time Fraud Detection Pipeline
====================================
Simulates the complete fraud detection flow:
- Transaction generation
- Feature enrichment
- Rule engine
- ML scoring
- Decision engine

Run: python fraud_detection.py
"""

import time
import random
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import threading
import json
import math


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Transaction:
    txn_id: str
    user_id: str
    merchant_id: str
    amount: float
    currency: str
    country: str
    card_type: str
    timestamp: float
    ip_address: str
    device_id: str


@dataclass
class EnrichedTransaction:
    """Transaction + computed features for ML scoring"""
    transaction: Transaction
    # User features (from feature store)
    user_avg_amount_30d: float = 0.0
    user_txn_count_30d: int = 0
    user_distinct_merchants_30d: int = 0
    user_distinct_countries_30d: int = 0
    # Real-time features (computed by Flink)
    txn_count_last_5min: int = 0
    txn_count_last_1hr: int = 0
    amount_deviation: float = 0.0  # Std devs from mean
    geo_velocity_mph: float = 0.0  # Miles/hour between txns
    time_since_last_txn_sec: float = 0.0
    is_new_merchant: bool = False
    is_new_country: bool = False
    # Card testing indicators
    rapid_small_amounts: bool = False
    incrementing_amounts: bool = False


@dataclass
class FraudDecision:
    txn_id: str
    decision: str  # ALLOW, BLOCK, REVIEW
    rule_result: Optional[str] = None
    ml_score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    latency_ms: float = 0.0


# ============================================================================
# FEATURE STORE (Simulates Redis-backed feature store)
# ============================================================================

class FeatureStore:
    """
    Pre-computed user features for real-time lookup.
    
    In production:
    - Redis Cluster for <1ms lookups
    - Updated by Flink streaming job
    - Batch features refreshed daily by Spark
    - Feast/Tecton as feature platform
    """
    
    def __init__(self):
        self.user_features: Dict[str, dict] = {}
        self.merchant_features: Dict[str, dict] = {}
        self._populate_features()
    
    def _populate_features(self):
        """Pre-populate with historical features"""
        for i in range(1000):
            user_id = f"user_{i:04d}"
            self.user_features[user_id] = {
                'avg_amount_30d': random.uniform(20, 500),
                'std_amount_30d': random.uniform(10, 200),
                'txn_count_30d': random.randint(5, 100),
                'distinct_merchants_30d': random.randint(3, 30),
                'distinct_countries_30d': random.randint(1, 5),
                'account_age_days': random.randint(30, 3650),
                'previous_fraud_count': random.choices([0, 0, 0, 1, 2], k=1)[0],
                'last_country': random.choice(['US', 'UK', 'DE', 'FR', 'JP']),
                'last_txn_timestamp': time.time() - random.uniform(60, 86400),
            }
    
    def get_user_features(self, user_id: str) -> dict:
        return self.user_features.get(user_id, {
            'avg_amount_30d': 100,
            'std_amount_30d': 50,
            'txn_count_30d': 10,
            'distinct_merchants_30d': 5,
            'distinct_countries_30d': 1,
            'account_age_days': 365,
            'previous_fraud_count': 0,
            'last_country': 'US',
            'last_txn_timestamp': time.time() - 3600,
        })


# ============================================================================
# REAL-TIME FEATURE COMPUTATION (Simulates Flink Stateful Processing)
# ============================================================================

class RealTimeFeatureEngine:
    """
    Computes features that require recent event history.
    
    In production: Flink with RocksDB state backend
    - Sliding windows for counts
    - Session windows for patterns
    - Keyed state per user
    """
    
    def __init__(self):
        # Per-user recent transaction windows
        self.user_recent_txns: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )
    
    def compute_features(self, txn: Transaction, 
                        historical_features: dict) -> EnrichedTransaction:
        """Compute real-time features for a transaction"""
        user_txns = self.user_recent_txns[txn.user_id]
        now = txn.timestamp
        
        # Transactions in last 5 minutes
        txns_5min = [t for t in user_txns if now - t['timestamp'] < 300]
        txns_1hr = [t for t in user_txns if now - t['timestamp'] < 3600]
        
        # Amount deviation
        avg = historical_features.get('avg_amount_30d', 100)
        std = historical_features.get('std_amount_30d', 50)
        amount_deviation = (txn.amount - avg) / max(std, 1)
        
        # Geo-velocity (distance between last txn location and current)
        last_country = historical_features.get('last_country', txn.country)
        geo_velocity = 0.0
        if last_country != txn.country:
            last_time = historical_features.get('last_txn_timestamp', now)
            hours_elapsed = max((now - last_time) / 3600, 0.01)
            # Rough distance between countries (simplified)
            geo_velocity = 3000 / hours_elapsed  # Assume 3000 miles between countries
        
        # Time since last transaction
        time_since_last = now - historical_features.get('last_txn_timestamp', now - 3600)
        
        # Card testing detection
        rapid_small = (len(txns_5min) > 3 and 
                      all(t['amount'] < 5 for t in txns_5min[-3:]))
        
        incrementing = False
        if len(txns_5min) >= 3:
            amounts = [t['amount'] for t in txns_5min[-3:]]
            incrementing = all(amounts[i] < amounts[i+1] for i in range(len(amounts)-1))
        
        enriched = EnrichedTransaction(
            transaction=txn,
            user_avg_amount_30d=avg,
            user_txn_count_30d=historical_features.get('txn_count_30d', 10),
            user_distinct_merchants_30d=historical_features.get('distinct_merchants_30d', 5),
            user_distinct_countries_30d=historical_features.get('distinct_countries_30d', 1),
            txn_count_last_5min=len(txns_5min),
            txn_count_last_1hr=len(txns_1hr),
            amount_deviation=amount_deviation,
            geo_velocity_mph=geo_velocity,
            time_since_last_txn_sec=time_since_last,
            is_new_merchant=True,  # Simplified
            is_new_country=(txn.country != last_country),
            rapid_small_amounts=rapid_small,
            incrementing_amounts=incrementing,
        )
        
        # Update state
        user_txns.append({
            'timestamp': now,
            'amount': txn.amount,
            'country': txn.country,
            'merchant': txn.merchant_id
        })
        
        return enriched


# ============================================================================
# RULE ENGINE (Hard rules - instant decisions)
# ============================================================================

class RuleEngine:
    """
    Deterministic rules for obvious fraud.
    Rules are evaluated BEFORE ML for speed.
    
    WHY RULES + ML:
    - Rules: Fast, explainable, handle known patterns
    - ML: Catches novel patterns, better at subtle fraud
    - Together: Best of both worlds
    """
    
    BLOCKED_COUNTRIES = {'NK', 'IR', 'SY'}  # Sanctioned
    
    def evaluate(self, enriched: EnrichedTransaction) -> Tuple[str, List[str]]:
        """
        Returns: (decision, reasons)
        decision: BLOCK, REVIEW, PASS (pass to ML)
        """
        reasons = []
        txn = enriched.transaction
        
        # Rule 1: Sanctioned country
        if txn.country in self.BLOCKED_COUNTRIES:
            reasons.append(f"Sanctioned country: {txn.country}")
            return 'BLOCK', reasons
        
        # Rule 2: Extreme amount
        if txn.amount > 10000:
            reasons.append(f"Amount ${txn.amount} exceeds $10K threshold")
            return 'REVIEW', reasons
        
        # Rule 3: Velocity (too many transactions too fast)
        if enriched.txn_count_last_5min > 5:
            reasons.append(f"Velocity: {enriched.txn_count_last_5min} txns in 5 min")
            return 'BLOCK', reasons
        
        # Rule 4: Impossible travel (geo-velocity)
        if enriched.geo_velocity_mph > 600:  # Faster than commercial flight
            reasons.append(f"Impossible travel: {enriched.geo_velocity_mph:.0f} mph")
            return 'BLOCK', reasons
        
        # Rule 5: Card testing pattern
        if enriched.rapid_small_amounts:
            reasons.append("Card testing pattern detected")
            return 'BLOCK', reasons
        
        # Rule 6: Huge deviation from normal
        if enriched.amount_deviation > 5:
            reasons.append(f"Amount {enriched.amount_deviation:.1f} std devs above mean")
            return 'REVIEW', reasons
        
        return 'PASS', reasons  # Let ML decide


# ============================================================================
# ML SCORING (Simulates real-time model inference)
# ============================================================================

class MLScoringService:
    """
    Simulates ML model inference for fraud scoring.
    
    In production:
    - Model: XGBoost or LightGBM (fast inference)
    - Serving: TensorFlow Serving / Triton / SageMaker
    - Latency budget: <30ms P99
    - Features: 200+ dimensions
    - Retrained daily on labeled data
    """
    
    def score(self, enriched: EnrichedTransaction) -> float:
        """
        Returns fraud probability [0.0, 1.0]
        Higher = more likely fraud
        """
        # Simulated scoring based on features
        score = 0.0
        
        # High amount deviation → suspicious
        score += min(enriched.amount_deviation * 0.1, 0.3)
        
        # New country → suspicious
        if enriched.is_new_country:
            score += 0.2
        
        # High velocity → suspicious
        score += min(enriched.txn_count_last_5min * 0.05, 0.2)
        
        # Very fast geo-velocity
        if enriched.geo_velocity_mph > 300:
            score += 0.3
        
        # Incrementing amounts (card testing)
        if enriched.incrementing_amounts:
            score += 0.25
        
        # New account (less history = riskier)
        if enriched.user_txn_count_30d < 5:
            score += 0.1
        
        # Add some noise (real models aren't perfect)
        score += random.uniform(-0.05, 0.05)
        
        return max(0.0, min(1.0, score))


# ============================================================================
# DECISION ENGINE (Combines rules + ML)
# ============================================================================

class DecisionEngine:
    """Combines rule engine and ML scoring for final decision"""
    
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.ml_service = MLScoringService()
        self.decisions_log: List[FraudDecision] = []
    
    def decide(self, enriched: EnrichedTransaction) -> FraudDecision:
        start_time = time.time()
        
        # Step 1: Rules (fast path)
        rule_result, rule_reasons = self.rule_engine.evaluate(enriched)
        
        if rule_result == 'BLOCK':
            decision = FraudDecision(
                txn_id=enriched.transaction.txn_id,
                decision='BLOCK',
                rule_result='BLOCK',
                ml_score=0.0,
                reasons=rule_reasons,
                latency_ms=(time.time() - start_time) * 1000
            )
            self.decisions_log.append(decision)
            return decision
        
        # Step 2: ML scoring
        ml_score = self.ml_service.score(enriched)
        
        # Step 3: Combine
        all_reasons = rule_reasons[:]
        
        if rule_result == 'REVIEW' or ml_score > 0.7:
            if ml_score > 0.9:
                final = 'BLOCK'
                all_reasons.append(f"ML score: {ml_score:.3f} (high confidence fraud)")
            elif ml_score > 0.7:
                final = 'REVIEW'
                all_reasons.append(f"ML score: {ml_score:.3f} (moderate risk)")
            else:
                final = 'REVIEW'
        else:
            final = 'ALLOW'
        
        decision = FraudDecision(
            txn_id=enriched.transaction.txn_id,
            decision=final,
            rule_result=rule_result,
            ml_score=ml_score,
            reasons=all_reasons,
            latency_ms=(time.time() - start_time) * 1000
        )
        self.decisions_log.append(decision)
        return decision


# ============================================================================
# PIPELINE ORCHESTRATOR
# ============================================================================

def generate_transaction(is_fraud: bool = False) -> Transaction:
    """Generate a realistic transaction (optionally fraudulent)"""
    user_id = f"user_{random.randint(0, 999):04d}"
    
    if is_fraud:
        # Fraud patterns
        pattern = random.choice(['high_amount', 'foreign', 'velocity', 'card_test'])
        if pattern == 'high_amount':
            amount = random.uniform(2000, 15000)
            country = 'US'
        elif pattern == 'foreign':
            amount = random.uniform(100, 1000)
            country = random.choice(['NK', 'IR', 'NG', 'RU'])
        elif pattern == 'velocity':
            amount = random.uniform(50, 200)
            country = 'US'
        else:  # card_test
            amount = random.uniform(1, 5)
            country = 'US'
    else:
        amount = random.uniform(5, 500)
        country = random.choice(['US', 'US', 'US', 'UK', 'DE', 'FR', 'JP'])
    
    return Transaction(
        txn_id=hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:12],
        user_id=user_id,
        merchant_id=f"merch_{random.randint(1, 500):04d}",
        amount=round(amount, 2),
        currency='USD',
        country=country,
        card_type=random.choice(['visa', 'mastercard', 'amex']),
        timestamp=time.time(),
        ip_address=f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        device_id=f"device_{random.randint(1, 10000)}"
    )


def run_fraud_detection_pipeline():
    """Run the complete fraud detection pipeline"""
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       REAL-TIME FRAUD DETECTION PIPELINE                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Processing 1000 transactions:                                   ║
║  • 90% legitimate, 10% fraudulent                                ║
║  • Rule engine + ML scoring                                      ║
║  • Target: <100ms latency per decision                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize components
    feature_store = FeatureStore()
    rt_features = RealTimeFeatureEngine()
    decision_engine = DecisionEngine()
    
    # Process transactions
    results = {'ALLOW': 0, 'BLOCK': 0, 'REVIEW': 0}
    fraud_caught = 0
    fraud_missed = 0
    legitimate_blocked = 0
    total_latency = 0
    
    num_transactions = 1000
    fraud_rate = 0.10  # 10% fraud
    
    print(f"Processing {num_transactions} transactions...\n")
    
    for i in range(num_transactions):
        is_fraud = random.random() < fraud_rate
        txn = generate_transaction(is_fraud=is_fraud)
        
        # Feature enrichment
        user_features = feature_store.get_user_features(txn.user_id)
        enriched = rt_features.compute_features(txn, user_features)
        
        # Decision
        decision = decision_engine.decide(enriched)
        results[decision.decision] += 1
        total_latency += decision.latency_ms
        
        # Track accuracy
        if is_fraud and decision.decision in ('BLOCK', 'REVIEW'):
            fraud_caught += 1
        elif is_fraud and decision.decision == 'ALLOW':
            fraud_missed += 1
        elif not is_fraud and decision.decision == 'BLOCK':
            legitimate_blocked += 1
    
    # Print results
    total_fraud = int(num_transactions * fraud_rate)
    
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\n  Transactions Processed: {num_transactions}")
    print(f"  Fraud Rate: {fraud_rate*100:.1f}%")
    print(f"\n  Decisions:")
    print(f"    ALLOW:  {results['ALLOW']:>5} ({results['ALLOW']/num_transactions*100:.1f}%)")
    print(f"    BLOCK:  {results['BLOCK']:>5} ({results['BLOCK']/num_transactions*100:.1f}%)")
    print(f"    REVIEW: {results['REVIEW']:>5} ({results['REVIEW']/num_transactions*100:.1f}%)")
    print(f"\n  Accuracy:")
    print(f"    Fraud caught (blocked/reviewed): {fraud_caught}/{total_fraud} "
          f"({fraud_caught/max(total_fraud,1)*100:.1f}%)")
    print(f"    Fraud missed (allowed): {fraud_missed}/{total_fraud} "
          f"({fraud_missed/max(total_fraud,1)*100:.1f}%)")
    print(f"    False positives (legit blocked): {legitimate_blocked} "
          f"({legitimate_blocked/max(num_transactions-total_fraud,1)*100:.2f}%)")
    print(f"\n  Performance:")
    print(f"    Avg latency: {total_latency/num_transactions:.3f}ms")
    print(f"    Throughput: {num_transactions/(total_latency/1000):.0f} txn/sec")
    
    # Show some blocked transactions
    print(f"\n  Sample BLOCKED transactions:")
    blocked = [d for d in decision_engine.decisions_log if d.decision == 'BLOCK'][:5]
    for d in blocked:
        print(f"    {d.txn_id}: ML={d.ml_score:.3f} | {'; '.join(d.reasons[:2])}")


if __name__ == '__main__':
    run_fraud_detection_pipeline()
```

