# Fraud Detection Pipeline Monitoring

## Problem Statement

Real-time fraud detection at Stripe/Visa scale processes **100,000+ transactions per second** with a hard latency SLA of **sub-100ms** for scoring decisions. The pipeline must maintain **99.99% availability** — even 1 minute of downtime allows thousands of fraudulent transactions through.

**The cost of monitoring failures:**
- Stale ML model → fraud patterns evolve undetected → millions in losses per hour
- Feature store lag → scoring with stale data → wrong approve/decline decisions
- Silent pipeline failure → no scoring at all → all transactions auto-approved
- False positive spike → legitimate customers blocked → revenue loss + churn

Unlike most data pipelines where minutes of delay are acceptable, fraud detection operates in a world where **every millisecond of latency is a decision window for attackers**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     REAL-TIME FRAUD DETECTION PIPELINE                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │  Card    │   │  ACH/    │   │  Crypto  │   │  Wire    │
  │  Present │   │  Bank    │   │  Txn     │   │  Transfer│
  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
       └───────────────┴───────┬──────┴───────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER                                                                     │
│  ┌─────────────────────────────────────┐                                            │
│  │  Kafka: transactions (256 partitions)│  ← 100K+ msg/sec                          │
│  │  Partitioned by: merchant_id         │                                            │
│  └───────────────────┬─────────────────┘                                            │
│                [MON-1]● throughput, schema validation                                 │
└───────────────────────┼─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  FEATURE ENRICHMENT LAYER (< 20ms budget)                                            │
│                                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ User Profile│  │ Merchant    │  │ Device      │  │ Velocity    │              │
│  │ Features    │  │ Risk Score  │  │ Fingerprint │  │ Counters    │              │
│  │ (DynamoDB)  │  │ (Redis)     │  │ (Redis)     │  │ (Redis)     │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                │                        │
│   [MON-2]● latency [MON-3]● freshness [MON-4]● hit rate [MON-5]● accuracy        │
│         └────────────────┴────────────────┴────────────────┘                        │
│                                    │                                                 │
│                          Feature Vector (50+ features)                               │
└────────────────────────────────────┼────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  ML SCORING LAYER (< 30ms budget)                                                    │
│                                                                                       │
│  ┌──────────────────────────────────────────────────────────┐                       │
│  │  Model Ensemble (served via Triton/TensorRT)             │                       │
│  │                                                           │                       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │                       │
│  │  │ XGBoost  │  │  Neural  │  │  Rules   │              │                       │
│  │  │ v3.2.1   │  │  Net v2  │  │  Engine  │              │                       │
│  │  │ (fast)   │  │  (deep)  │  │  (hard)  │              │                       │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │                       │
│  │       └──────────────┴──────────────┘                    │                       │
│  │                      │                                    │                       │
│  │              Ensemble Score [0.0 - 1.0]                  │                       │
│  └──────────────────────┼───────────────────────────────────┘                       │
│                   [MON-6]● latency, score distribution, model version                │
└──────────────────────────┼──────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  DECISION LAYER                                                                      │
│                                                                                       │
│  ┌──────────────────────────────────────────────────────────┐                       │
│  │              Decision Engine                               │                       │
│  │  Score < 0.3  →  APPROVE (85%)                            │                       │
│  │  Score 0.3-0.7 → REVIEW  (10%)                            │                       │
│  │  Score > 0.7  →  DECLINE (5%)                             │                       │
│  └──────────────────────┬───────────────────────────────────┘                       │
│                   [MON-7]● decision distribution, override rates                     │
└──────────────────────────┼──────────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
      ┌────────────┐ ┌──────────┐ ┌──────────────┐
      │  Approve   │ │  Queue   │ │   Decline    │
      │  (sync)    │ │  Review  │ │  + Alert     │
      └────────────┘ └──────────┘ └──────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│  BATCH RETRAINING PIPELINE (monitored separately)                                    │
│                                                                                       │
│  Fraud Labels ──► Feature ──► Model ──► Validation ──► Champion/ ──► Deploy         │
│  (7-30 day lag)   Rebuild     Train     (offline)     Challenger    (canary)         │
│       │              │          │           │              │            │             │
│ [MON-8]●       [MON-9]●  [MON-10]●  [MON-11]●      [MON-12]●   [MON-13]●          │
│ label rate    feature   training    AUC/precision  A/B test    rollout              │
│ completeness  drift     convergence threshold     significance health              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Why Monitoring is Critical for Fraud

### The Concept Drift Problem

```
Fraud Pattern Lifecycle:
═══════════════════════════════════════════════════════════════════

Week 1-4:    Model trained on pattern A (card-not-present BIN attacks)
             Detection rate: 97%

Week 5-6:    Attackers shift to pattern B (synthetic identity + ACH)
             Model sees pattern B as normal → Detection drops to 40%
             ┌─────────────────────────────────────────────────┐
             │  WITHOUT MONITORING: $2.3M lost before noticed  │
             │  WITH MONITORING: Alert fires in 15 minutes     │
             └─────────────────────────────────────────────────┘

Week 7:      Retrained model deployed, detection recovers to 95%

═══════════════════════════════════════════════════════════════════
```

### Silent Failure Cascade

```
Root Cause: Redis cluster node fails
     │
     ▼
Feature enrichment returns stale/default values (no error!)
     │
     ▼
Model scores with incomplete features → scores shift toward 0.5 (uncertain)
     │
     ▼
Review queue overwhelmed (10% → 40% review rate)
     │
     ▼
Analysts can't keep up → auto-approve kicks in after timeout
     │
     ▼
Fraud passes through undetected
     │
     ▼
$500K loss before anyone notices

MONITORING DETECTION POINT: Feature freshness alert fires at step 2
```

---

## Key Monitoring Dimensions

### 1. Model Performance (Sliding Window)

| Metric | Description | Threshold | Window |
|---|---|---|---|
| `fraud_model_precision` | TP / (TP + FP) | > 0.85 | 1 hour |
| `fraud_model_recall` | TP / (TP + FN) | > 0.70 | 1 hour |
| `fraud_model_f1_score` | Harmonic mean | > 0.75 | 1 hour |
| `fraud_model_auc_roc` | Area under ROC | > 0.95 | 6 hours |
| `fraud_model_score_distribution` | Histogram of scores | KS < 0.05 vs baseline | 15 min |
| `fraud_model_calibration_error` | Expected calibration error | < 0.05 | 1 hour |

### 2. Feature Freshness

| Feature Category | Freshness SLA | Monitoring Metric |
|---|---|---|
| Velocity counters (txn count/hr) | < 1 second | `feature_freshness_seconds{category="velocity"}` |
| Device fingerprint | < 5 seconds | `feature_freshness_seconds{category="device"}` |
| User profile | < 30 seconds | `feature_freshness_seconds{category="profile"}` |
| Merchant risk score | < 5 minutes | `feature_freshness_seconds{category="merchant"}` |
| Network graph features | < 1 hour | `feature_freshness_seconds{category="graph"}` |

### 3. Scoring Latency

```
Latency Budget Breakdown (total: 100ms):
═══════════════════════════════════════════
 Kafka consume:        5ms  ███░░░░░░░░░░░░░░░░░
 Feature lookup:      20ms  ██████░░░░░░░░░░░░░░
 Model inference:     30ms  █████████░░░░░░░░░░░
 Rules engine:        10ms  ███░░░░░░░░░░░░░░░░░
 Decision + respond:   5ms  ██░░░░░░░░░░░░░░░░░░
 Buffer/headroom:     30ms  █████████░░░░░░░░░░░
═══════════════════════════════════════════
 Total budget:       100ms

 Metrics:
 - scoring_latency_seconds{quantile="0.50"} target: < 50ms
 - scoring_latency_seconds{quantile="0.95"} target: < 80ms
 - scoring_latency_seconds{quantile="0.99"} target: < 100ms
```

### 4. Decision Distribution

```
Normal Decision Distribution:
  APPROVE ████████████████████████████████████████████  85%
  REVIEW  █████                                         10%
  DECLINE ███                                            5%

Anomalous Distribution (feature store outage):
  APPROVE ████████████████████                          40%
  REVIEW  ████████████████████████████                  55%  ← ALERT!
  DECLINE ███                                            5%
```

### 5. Feedback Loop Metrics

| Metric | Description | Target |
|---|---|---|
| `fraud_label_delay_hours` | Time from txn to confirmed fraud/legit label | < 168h (7 days) |
| `fraud_label_rate` | Percentage of transactions with final labels | > 95% at 30 days |
| `model_retrain_frequency_hours` | Hours since last model update | < 168h (weekly) |
| `champion_challenger_gap` | AUC difference between prod model and candidate | < 0.02 |

---

## Real-time Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│              MONITORING SYSTEM ARCHITECTURE                               │
│                                                                           │
│  Transaction      Kafka Streams         Storage          Alerting        │
│  Events           (Metric Computation)  Layer            Layer           │
│                                                                           │
│  ┌──────┐        ┌──────────────┐      ┌──────────┐   ┌──────────┐    │
│  │Score │───────►│ Sliding Win  │─────►│ Redis    │──►│ Alert    │    │
│  │Events│        │ Aggregation  │      │ (real-   │   │ Evaluator│    │
│  └──────┘        │              │      │  time)   │   └─────┬────┘    │
│                   │ - p50/p95/p99│      └──────────┘         │         │
│  ┌──────┐        │ - count/rate │                            │         │
│  │Featu-│───────►│ - distribution│     ┌──────────┐         │         │
│  │re    │        │ - drift tests│────►│ClickHouse│         │         │
│  │Reads │        └──────────────┘      │ (history)│         │         │
│  └──────┘                              └──────────┘         │         │
│                                                              ▼         │
│  ┌──────┐        ┌──────────────┐      ┌──────────┐   ┌──────────┐  │
│  │Decis-│───────►│ Anomaly      │─────►│Prometheus│──►│PagerDuty │  │
│  │ions  │        │ Detection    │      │ (metrics)│   │ Slack    │  │
│  └──────┘        │ (ADWIN/DDM)  │      └──────────┘   │ Grafana  │  │
│                   └──────────────┘                      └──────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Alert Rules

### Critical (Page Immediately — P1)

```yaml
groups:
  - name: fraud_pipeline_critical
    rules:
      # Scoring latency breach
      - alert: FraudScoringLatencyP99Critical
        expr: |
          histogram_quantile(0.99,
            rate(scoring_latency_seconds_bucket{service="fraud-scorer"}[2m])
          ) > 0.1
        for: 1m
        labels:
          severity: critical
          team: fraud-platform
        annotations:
          summary: "Fraud scoring p99 latency > 100ms"
          description: |
            Scoring latency p99 is {{ $value }}s (target: 0.1s).
            Transactions may timeout and auto-approve.
          impact: "Fraud transactions may pass through unscored"
          runbook_url: "https://runbooks.internal/fraud-latency-critical"

      # Decision distribution anomaly
      - alert: FraudDeclineRateSpike
        expr: |
          (
            rate(fraud_decisions_total{decision="decline"}[5m])
            /
            rate(fraud_decisions_total[5m])
          ) > 2 * (
            rate(fraud_decisions_total{decision="decline"}[5m] offset 1h)
            /
            rate(fraud_decisions_total[5m] offset 1h)
          )
        for: 5m
        labels:
          severity: critical
          team: fraud-platform
        annotations:
          summary: "Decline rate doubled vs 1 hour ago"
          description: |
            Current decline rate is 2x the rate from 1 hour ago.
            Possible causes: model issue, feature store problem, or actual fraud wave.
          impact: "Legitimate customers may be incorrectly declined"

      # Transaction volume drop (ingestion failure)
      - alert: TransactionVolumeDropCritical
        expr: |
          rate(transactions_ingested_total[5m])
          < 0.8 * rate(transactions_ingested_total[5m] offset 1h)
          and
          hour() >= 8 and hour() <= 23  # Only during business hours
        for: 3m
        labels:
          severity: critical
          team: fraud-platform
        annotations:
          summary: "Transaction volume dropped > 20%"
          description: |
            Ingestion rate {{ $value }}/sec vs expected.
            Possible upstream failure — transactions may be unscored.

      # Feature freshness critical
      - alert: FeatureFreshnessCritical
        expr: |
          feature_freshness_seconds{category=~"velocity|device"} > 30
        for: 2m
        labels:
          severity: critical
          team: fraud-platform
        annotations:
          summary: "Critical features stale > 30s: {{ $labels.category }}"
          description: |
            Feature category {{ $labels.category }} last updated {{ $value }}s ago.
            Scoring with stale features produces unreliable decisions.
```

### Warning (Slack + Ticket — P3)

```yaml
      # Model score distribution shift
      - alert: ModelScoreDistributionShift
        expr: |
          fraud_model_ks_statistic > 0.05
        for: 15m
        labels:
          severity: warning
          team: fraud-ml
        annotations:
          summary: "Model score distribution shift detected (KS={{ $value }})"
          description: |
            Kolmogorov-Smirnov statistic between current score distribution
            and reference distribution exceeds threshold.
            May indicate concept drift or feature pipeline issue.

      # Model performance degradation
      - alert: ModelPrecisionDegraded
        expr: |
          fraud_model_precision{window="1h"} < 0.80
        for: 30m
        labels:
          severity: warning
          team: fraud-ml
        annotations:
          summary: "Model precision dropped below 80%"
          description: |
            Precision is {{ $value }}. May indicate increased false positives
            or shift in transaction patterns.

      # Feedback loop delay
      - alert: FraudLabelDelayHigh
        expr: |
          fraud_label_delay_hours > 336  # 14 days
        for: 1h
        labels:
          severity: warning
          team: fraud-ops
        annotations:
          summary: "Fraud labels delayed > 14 days"
```

---

## Production Code Examples

### 1. Real-time Model Performance Tracker

```python
"""
Tracks fraud model performance in real-time using sliding windows.
Computes precision, recall, F1 as labels arrive (delayed feedback loop).
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict
from prometheus_client import Gauge, Histogram
import numpy as np


@dataclass
class ScoredTransaction:
    transaction_id: str
    score: float
    decision: str  # approve, review, decline
    timestamp: float
    actual_fraud: bool = None  # Filled when label arrives
    label_timestamp: float = None


class RealTimeModelPerformanceTracker:
    """
    Maintains sliding windows of scored + labeled transactions.
    Computes live model metrics as labels arrive.
    """

    def __init__(self, window_seconds: int = 3600):
        self.window_seconds = window_seconds
        self.scored_txns: Dict[str, ScoredTransaction] = {}
        self.labeled_window: Deque[ScoredTransaction] = deque()
        self.decision_threshold = 0.5

        # Prometheus metrics
        self.precision_gauge = Gauge(
            'fraud_model_precision',
            'Model precision over sliding window',
            ['window']
        )
        self.recall_gauge = Gauge(
            'fraud_model_recall',
            'Model recall over sliding window',
            ['window']
        )
        self.f1_gauge = Gauge(
            'fraud_model_f1_score',
            'Model F1 score over sliding window',
            ['window']
        )
        self.ks_statistic = Gauge(
            'fraud_model_ks_statistic',
            'KS statistic vs reference distribution'
        )
        self.score_histogram = Histogram(
            'fraud_model_score_distribution',
            'Distribution of model scores',
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )

        # Reference distribution (from training set)
        self.reference_scores: np.ndarray = None

    def record_score(self, txn_id: str, score: float, decision: str):
        """Called for every scored transaction."""
        self.scored_txns[txn_id] = ScoredTransaction(
            transaction_id=txn_id,
            score=score,
            decision=decision,
            timestamp=time.time()
        )
        self.score_histogram.observe(score)

        # Evict old unmatched scores (> 30 days)
        self._evict_old_scores()

    def record_label(self, txn_id: str, is_fraud: bool):
        """Called when a fraud/legit label arrives (delayed by days/weeks)."""
        if txn_id not in self.scored_txns:
            return  # Score already evicted

        txn = self.scored_txns.pop(txn_id)
        txn.actual_fraud = is_fraud
        txn.label_timestamp = time.time()
        self.labeled_window.append(txn)

        # Evict old labels outside window
        cutoff = time.time() - self.window_seconds
        while self.labeled_window and self.labeled_window[0].label_timestamp < cutoff:
            self.labeled_window.popleft()

        # Recompute metrics
        self._compute_metrics()

    def _compute_metrics(self):
        """Compute precision, recall, F1 from labeled window."""
        if len(self.labeled_window) < 100:
            return  # Not enough data for reliable metrics

        tp = fp = fn = tn = 0
        scores = []

        for txn in self.labeled_window:
            predicted_fraud = txn.score >= self.decision_threshold
            scores.append(txn.score)

            if predicted_fraud and txn.actual_fraud:
                tp += 1
            elif predicted_fraud and not txn.actual_fraud:
                fp += 1
            elif not predicted_fraud and txn.actual_fraud:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        window_label = f"{self.window_seconds // 3600}h"
        self.precision_gauge.labels(window=window_label).set(precision)
        self.recall_gauge.labels(window=window_label).set(recall)
        self.f1_gauge.labels(window=window_label).set(f1)

        # KS test against reference
        if self.reference_scores is not None and len(scores) > 50:
            ks_stat = self._ks_test(np.array(scores), self.reference_scores)
            self.ks_statistic.set(ks_stat)

    def _ks_test(self, sample: np.ndarray, reference: np.ndarray) -> float:
        """Kolmogorov-Smirnov two-sample test statistic."""
        from scipy import stats
        statistic, _ = stats.ks_2samp(sample, reference)
        return statistic

    def _evict_old_scores(self):
        """Remove scores older than 30 days without labels."""
        cutoff = time.time() - (30 * 86400)
        to_remove = [
            k for k, v in self.scored_txns.items()
            if v.timestamp < cutoff
        ]
        for k in to_remove:
            del self.scored_txns[k]
```

### 2. Feature Freshness Monitor

```python
"""
Monitors freshness of features in the feature store.
Tracks per-feature and per-entity freshness with tiered alerting.
"""

import asyncio
import time
from typing import Dict, List, Tuple
import redis.asyncio as redis
from prometheus_client import Gauge, Counter, Histogram


FEATURE_FRESHNESS = Gauge(
    'feature_freshness_seconds',
    'Seconds since feature was last updated',
    ['feature_name', 'category', 'entity_type']
)
FEATURE_STALE_TOTAL = Counter(
    'feature_stale_events_total',
    'Number of feature lookups that returned stale data',
    ['feature_name', 'category']
)
FEATURE_MISS_TOTAL = Counter(
    'feature_miss_total',
    'Feature store cache misses',
    ['feature_name']
)
FEATURE_LOOKUP_LATENCY = Histogram(
    'feature_lookup_latency_seconds',
    'Feature store lookup latency',
    ['feature_name', 'store_type'],
    buckets=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1]
)


# Feature freshness SLAs (in seconds)
FRESHNESS_SLAS = {
    'velocity': {
        'txn_count_1h': 1,
        'txn_amount_1h': 1,
        'unique_merchants_1h': 5,
        'avg_amount_7d': 300,
    },
    'device': {
        'device_fingerprint': 5,
        'device_trust_score': 30,
        'device_first_seen': 86400,
    },
    'profile': {
        'account_age_days': 3600,
        'historical_fraud_rate': 3600,
        'avg_transaction_amount': 300,
    },
    'merchant': {
        'merchant_risk_score': 300,
        'merchant_category': 86400,
        'merchant_fraud_rate_30d': 3600,
    },
}


class FeatureFreshnessMonitor:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.check_interval = 5  # seconds

    async def check_freshness(self):
        """Periodically check freshness of all feature categories."""
        while True:
            for category, features in FRESHNESS_SLAS.items():
                for feature_name, sla_seconds in features.items():
                    freshness = await self._get_feature_freshness(
                        category, feature_name
                    )

                    FEATURE_FRESHNESS.labels(
                        feature_name=feature_name,
                        category=category,
                        entity_type='aggregate'
                    ).set(freshness)

                    if freshness > sla_seconds:
                        FEATURE_STALE_TOTAL.labels(
                            feature_name=feature_name,
                            category=category
                        ).inc()

            await asyncio.sleep(self.check_interval)

    async def _get_feature_freshness(self, category: str, feature: str) -> float:
        """Get time since last update for a feature."""
        key = f"feature:last_update:{category}:{feature}"
        last_update = await self.redis.get(key)

        if last_update is None:
            return float('inf')

        return time.time() - float(last_update)

    async def record_feature_update(self, category: str, feature: str):
        """Called when a feature is updated in the store."""
        key = f"feature:last_update:{category}:{feature}"
        await self.redis.set(key, str(time.time()))

    async def check_entity_freshness(
        self, entity_id: str, required_features: List[str]
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Check if all features for an entity are fresh enough for scoring.
        Returns (all_fresh, {feature: staleness_seconds}).
        Used as a circuit breaker before scoring.
        """
        staleness = {}
        all_fresh = True

        pipeline = self.redis.pipeline()
        for feature in required_features:
            pipeline.get(f"feature:entity:{entity_id}:{feature}:updated_at")

        results = await pipeline.execute()

        for feature, last_update in zip(required_features, results):
            if last_update is None:
                staleness[feature] = float('inf')
                all_fresh = False
                FEATURE_MISS_TOTAL.labels(feature_name=feature).inc()
            else:
                age = time.time() - float(last_update)
                staleness[feature] = age
                # Look up SLA for this feature
                for cat, feats in FRESHNESS_SLAS.items():
                    if feature in feats and age > feats[feature]:
                        all_fresh = False
                        FEATURE_STALE_TOTAL.labels(
                            feature_name=feature, category=cat
                        ).inc()

        return all_fresh, staleness
```

### 3. Anomaly Detection on Decision Distributions

```python
"""
Detects anomalies in fraud decision distributions using ADWIN
(Adaptive Windowing) algorithm. Alerts when the distribution of
approve/decline/review decisions shifts significantly.
"""

import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional
from prometheus_client import Gauge, Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class DistributionSnapshot:
    timestamp: float
    approve_rate: float
    decline_rate: float
    review_rate: float
    total_count: int


class DecisionDistributionMonitor:
    """
    Monitors the distribution of fraud decisions for anomalies.
    Uses a combination of:
    1. Simple threshold checks (rate > 2x baseline)
    2. CUSUM (Cumulative Sum) change detection
    3. Chi-squared test against reference distribution
    """

    def __init__(self, window_size: int = 300, sensitivity: float = 3.0):
        self.window_size = window_size  # seconds
        self.sensitivity = sensitivity
        self.decisions: deque = deque()

        # Reference distribution (updated periodically from stable periods)
        self.reference = {
            'approve': 0.85,
            'review': 0.10,
            'decline': 0.05,
        }

        # CUSUM state
        self.cusum_high = 0.0
        self.cusum_low = 0.0
        self.cusum_threshold = 5.0

        # Metrics
        self.anomaly_score = Gauge(
            'fraud_decision_anomaly_score',
            'Anomaly score for decision distribution (0=normal, 1=anomalous)'
        )
        self.distribution_gauge = Gauge(
            'fraud_decision_rate',
            'Current rate for each decision type',
            ['decision']
        )
        self.anomaly_detected = Counter(
            'fraud_decision_anomaly_detected_total',
            'Number of distribution anomalies detected',
            ['detection_method']
        )

    def record_decision(self, decision: str, timestamp: float):
        """Record a single fraud decision."""
        self.decisions.append((timestamp, decision))

        # Evict old decisions
        cutoff = timestamp - self.window_size
        while self.decisions and self.decisions[0][0] < cutoff:
            self.decisions.popleft()

        # Compute current distribution
        if len(self.decisions) < 100:
            return  # Not enough data

        counts = {'approve': 0, 'review': 0, 'decline': 0}
        for _, d in self.decisions:
            if d in counts:
                counts[d] += 1

        total = sum(counts.values())
        current_dist = {k: v / total for k, v in counts.items()}

        # Update gauges
        for decision_type, rate in current_dist.items():
            self.distribution_gauge.labels(decision=decision_type).set(rate)

        # Run anomaly detection
        anomaly_score = self._detect_anomaly(current_dist, total)
        self.anomaly_score.set(anomaly_score)

    def _detect_anomaly(self, current: Dict[str, float], n: int) -> float:
        """
        Multi-method anomaly detection.
        Returns score 0.0 (normal) to 1.0 (highly anomalous).
        """
        scores = []

        # Method 1: Threshold check
        for decision, rate in current.items():
            ref_rate = self.reference[decision]
            if rate > 2.0 * ref_rate or rate < 0.5 * ref_rate:
                scores.append(1.0)
                self.anomaly_detected.labels(detection_method='threshold').inc()
                logger.warning(
                    f"Threshold breach: {decision} rate={rate:.3f} "
                    f"(reference={ref_rate:.3f})"
                )

        # Method 2: Chi-squared test
        chi2 = self._chi_squared(current, self.reference, n)
        # With 2 degrees of freedom, chi2 > 9.21 is p < 0.01
        if chi2 > 9.21:
            chi2_score = min(1.0, chi2 / 20.0)
            scores.append(chi2_score)
            self.anomaly_detected.labels(detection_method='chi_squared').inc()

        # Method 3: CUSUM on decline rate
        decline_drift = current['decline'] - self.reference['decline']
        self.cusum_high = max(0, self.cusum_high + decline_drift - 0.005)
        self.cusum_low = min(0, self.cusum_low + decline_drift + 0.005)

        if self.cusum_high > self.cusum_threshold or abs(self.cusum_low) > self.cusum_threshold:
            scores.append(0.8)
            self.anomaly_detected.labels(detection_method='cusum').inc()
            # Reset after detection
            self.cusum_high = 0
            self.cusum_low = 0

        return max(scores) if scores else 0.0

    def _chi_squared(
        self, observed: Dict[str, float],
        expected: Dict[str, float],
        n: int
    ) -> float:
        """Compute chi-squared statistic."""
        chi2 = 0.0
        for key in expected:
            o = observed.get(key, 0) * n
            e = expected[key] * n
            if e > 0:
                chi2 += (o - e) ** 2 / e
        return chi2

    def update_reference(self, new_reference: Dict[str, float]):
        """Update reference distribution from a known-good period."""
        self.reference = new_reference
        logger.info(f"Reference distribution updated: {new_reference}")
```

### 4. Kafka Streams Topology for Metric Computation

```java
/**
 * Kafka Streams application that computes real-time fraud metrics.
 * Consumes scored transactions and produces aggregated metrics
 * for Prometheus scraping and ClickHouse insertion.
 */
public class FraudMetricsTopology {

    public static Topology buildTopology() {
        StreamsBuilder builder = new StreamsBuilder();

        // Source: scored transactions
        KStream<String, ScoredTransaction> transactions = builder.stream(
            "fraud-scored-transactions",
            Consumed.with(Serdes.String(), new ScoredTransactionSerde())
        );

        // Branch by decision
        Map<String, KStream<String, ScoredTransaction>> branches = transactions
            .split(Named.as("decision-"))
            .branch((k, v) -> v.getDecision() == Decision.APPROVE, Branched.as("approve"))
            .branch((k, v) -> v.getDecision() == Decision.DECLINE, Branched.as("decline"))
            .branch((k, v) -> v.getDecision() == Decision.REVIEW, Branched.as("review"))
            .defaultBranch(Branched.as("unknown"));

        // Compute per-minute decision counts (tumbling window)
        transactions
            .groupBy((k, v) -> v.getDecision().name(),
                     Grouped.with(Serdes.String(), new ScoredTransactionSerde()))
            .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(1)))
            .count(Materialized.as("decision-counts-1min"))
            .toStream()
            .mapValues((windowedKey, count) -> new MetricEvent(
                "fraud_decisions_total",
                Map.of("decision", windowedKey.key()),
                count.doubleValue(),
                windowedKey.window().endTime().toEpochMilli()
            ))
            .to("fraud-metrics", Produced.with(
                new TimeWindowedSerdes.TimeWindowedSerde<>(Serdes.String()),
                new MetricEventSerde()
            ));

        // Compute latency percentiles (sliding window)
        transactions
            .groupByKey()
            .windowedBy(SlidingWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(5)))
            .aggregate(
                TDigestAccumulator::new,
                (key, txn, digest) -> {
                    digest.add(txn.getScoringLatencyMs());
                    return digest;
                },
                Materialized.with(Serdes.String(), new TDigestSerde())
            )
            .toStream()
            .mapValues((windowedKey, digest) -> new LatencyMetric(
                digest.quantile(0.50),
                digest.quantile(0.95),
                digest.quantile(0.99),
                windowedKey.window().endTime().toEpochMilli()
            ))
            .to("fraud-latency-metrics");

        // Score distribution tracking
        transactions
            .mapValues(txn -> {
                // Bucket the score into deciles
                int bucket = Math.min(9, (int)(txn.getScore() * 10));
                return new ScoreBucket(bucket, txn.getScore());
            })
            .groupBy((k, v) -> String.valueOf(v.getBucket()),
                     Grouped.with(Serdes.String(), new ScoreBucketSerde()))
            .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5)))
            .count(Materialized.as("score-distribution-5min"))
            .toStream()
            .to("fraud-score-distribution");

        return builder.build();
    }

    public static Properties getConfig() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "fraud-metrics-streams");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
        props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, "exactly_once_v2");
        props.put(StreamsConfig.NUM_STREAM_THREADS_CONFIG, 4);
        props.put(StreamsConfig.METRICS_RECORDING_LEVEL_CONFIG, "DEBUG");
        props.put(StreamsConfig.STATE_DIR_CONFIG, "/data/kafka-streams-state");
        // Ensure low latency
        props.put(StreamsConfig.COMMIT_INTERVAL_MS_CONFIG, 100);
        props.put(StreamsConfig.producerPrefix(ProducerConfig.LINGER_MS_CONFIG), 10);
        return props;
    }
}
```

---

## Grafana Dashboard Design

### Fraud Scoring Operations Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ROW 1: Real-time Scoring Health                                         │
│                                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Txn/sec │  │  p99     │  │  Decline │  │  Model   │  │  Feature │ │
│  │  Score   │  │  Latency │  │  Rate    │  │  Version │  │  Fresh?  │ │
│  │  98,432  │  │  78ms    │  │  4.8%    │  │  v3.2.1  │  │  ✓ YES   │ │
│  │  ✓ OK    │  │  ✓ OK    │  │  ✓ OK    │  │          │  │          │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 2: Latency & Throughput                                             │
│                                                                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  Scoring Latency (p50/p95/p99)  │  │  Score Distribution (heatmap)   ││
│  │     100ms ─ ─ ─ ─ ─ ─ ─ SLA    │  │  0.0 ░░░░░░░░░░████████████    ││
│  │  ___     ___                     │  │  0.3 ░░░░████░░░░░░░░░░░░░░    ││
│  │ /   \___/   \____  p99          │  │  0.5 ░░██░░░░░░░░░░░░░░░░░░    ││
│  │ ─────────────────── p50          │  │  0.7 ░█░░░░░░░░░░░░░░░░░░░░    ││
│  └─────────────────────────────────┘  │  1.0 █░░░░░░░░░░░░░░░░░░░░░    ││
│                                        └─────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 3: Model Performance (delayed - labels arrive in days)              │
│                                                                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  Precision / Recall / F1        │  │  Decision Distribution Pie      ││
│  │  ────── Precision (0.89)        │  │                                  ││
│  │  - - -  Recall (0.73)           │  │      ┌──── Approve: 85.2%       ││
│  │  ······ F1 (0.80)               │  │      │  ┌─ Review:  10.1%       ││
│  │                                  │  │      │  │  Decline:  4.7%       ││
│  └─────────────────────────────────┘  └─────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 4: Feature Store Health                                             │
│                                                                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  Feature Freshness by Category  │  │  Feature Lookup Latency         ││
│  │  velocity:  ████░░░ 2s (SLA:1s) │  │  Redis:    ██░░ 3ms             ││
│  │  device:    ██░░░░░ 3s (SLA:5s) │  │  DynamoDB: ████░ 8ms            ││
│  │  profile:   █░░░░░░ 12s(SLA:30s)│  │  Graph:    ████████░ 18ms       ││
│  │  merchant:  █░░░░░░ 45s(SLA:5m) │  │                                 ││
│  └─────────────────────────────────┘  └─────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Incident Response Playbook

### Scenario: Scoring Latency Spike

```
┌─────────────────────────────────────────────────────────────┐
│  DECISION TREE: Scoring Latency > 100ms                      │
│                                                               │
│  1. Check feature store latency                              │
│     ├─ High? → Redis/DynamoDB issue                          │
│     │   ├─ Check Redis cluster health                        │
│     │   ├─ Check network between scoring + feature store     │
│     │   └─ Failover to replica / enable feature cache        │
│     │                                                        │
│     └─ Normal? → Continue to step 2                          │
│                                                               │
│  2. Check model inference latency                            │
│     ├─ High? → Model serving issue                           │
│     │   ├─ Check GPU utilization                             │
│     │   ├─ Check batch size configuration                    │
│     │   └─ Scale model serving pods                          │
│     │                                                        │
│     └─ Normal? → Continue to step 3                          │
│                                                               │
│  3. Check Kafka consumer lag                                 │
│     ├─ Growing? → Backpressure from downstream              │
│     │   ├─ Scale consumer instances                          │
│     │   └─ Check if partition count is sufficient            │
│     │                                                        │
│     └─ Stable? → Check GC pauses, network, host health     │
│                                                               │
│  ESCALATION:                                                 │
│  - If not resolved in 5 min: Activate fallback rules engine  │
│  - If not resolved in 15 min: Page fraud-platform-lead       │
│  - If scoring fully down: Auto-approve with amount limits    │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Ingestion | Kafka (256 partitions) | Transaction event streaming |
| Feature Store | Redis Cluster + DynamoDB | Online feature serving |
| Model Serving | Triton Inference Server | GPU-accelerated scoring |
| Metric Aggregation | Kafka Streams | Real-time metric computation |
| Time-series | Prometheus + Cortex | Metric storage and alerting |
| Analytics | ClickHouse | Historical fraud analysis |
| ML Platform | SageMaker + MLflow | Model training and registry |
| Orchestration | Kubernetes (EKS) | Service deployment |
| Alerting | PagerDuty + Slack | Incident management |
| Dashboards | Grafana | Visualization |

---

## Key Takeaways

1. **Latency is the primary SLA** — unlike batch pipelines, fraud scoring must complete in < 100ms or transactions timeout
2. **Monitor the model, not just the infrastructure** — precision/recall degradation is invisible to traditional monitoring
3. **Feature freshness is as critical as feature correctness** — stale features produce confidently wrong decisions
4. **Decision distribution is a powerful signal** — sudden shifts indicate systemic issues before individual metrics do
5. **Plan for silent failures** — systems that return defaults instead of errors are the most dangerous
6. **Feedback loops are delayed** — fraud labels arrive days/weeks later, requiring specialized monitoring approaches
7. **Circuit breakers for degraded scoring** — better to use simpler rules than score with broken features
