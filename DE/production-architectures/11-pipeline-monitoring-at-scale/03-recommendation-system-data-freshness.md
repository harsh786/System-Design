# Recommendation System Data Freshness Monitoring

## Problem Statement

At Netflix/Spotify/YouTube scale, recommendation systems serve **billions of predictions daily** across hundreds of millions of users. The quality of recommendations directly correlates with data freshness:

- **Stale user features** → recommendations don't reflect recent behavior → poor engagement
- **Outdated embeddings** → new content never surfaces → catalog coverage drops
- **Delayed A/B test logging** → incorrect experiment decisions → shipping losing variants
- **Cold start failures** → new users/items get generic recommendations → first-session churn

**Business impact:**
- 1% drop in recommendation relevance = ~$50M annual revenue loss (for Netflix-scale)
- Stale features for 1 hour during peak = measurable engagement dip for days (user trust erosion)
- Bad A/B test decision based on incomplete data = months of lost optimization

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION SYSTEM DATA PIPELINE                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

  USER INTERACTIONS
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  Clicks  │  │  Views   │  │  Plays   │  │  Skips   │  │Purchases │
  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
       └───────────────┴───────┬───────┴───────────────┴───────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  EVENT INGESTION (Kafka)                                                             │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐            │
│  │ user-interactions   │  │ content-metadata   │  │ ab-test-exposures  │            │
│  │ (512 partitions)    │  │ (64 partitions)    │  │ (128 partitions)   │            │
│  └─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘            │
│      [MON-1]●                [MON-2]●                 [MON-3]●                       │
└─────────────┼────────────────────────┼──────────────────────┼───────────────────────┘
              │                        │                      │
              ▼                        │                      │
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  REAL-TIME FEATURE COMPUTATION (Flink)                                               │
│                                                                                       │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐               │
│  │ User Session       │  │ Trending Content  │  │ Real-time         │               │
│  │ Features           │  │ Aggregations      │  │ Collaborative     │               │
│  │ (clicks, time,     │  │ (popularity,      │  │ Signals           │               │
│  │  scroll depth)     │  │  velocity)        │  │ (user-item co-    │               │
│  └────────┬──────────┘  └────────┬──────────┘  │  occurrence)      │               │
│     [MON-4]●                [MON-5]●            └────────┬──────────┘               │
│           │                      │                 [MON-6]●                           │
└───────────┼──────────────────────┼───────────────────────┼──────────────────────────┘
            │                      │                       │
            ▼                      ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  FEATURE STORE                                                                       │
│                                                                                       │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐                 │
│  │  ONLINE STORE               │    │  OFFLINE STORE               │                 │
│  │  (serving: < 5ms latency)   │    │  (training: batch access)    │                 │
│  │                              │    │                              │                 │
│  │  ┌────────┐  ┌───────────┐ │    │  ┌─────────┐  ┌──────────┐ │                 │
│  │  │ Redis  │  │ DynamoDB  │ │    │  │  S3     │  │ Iceberg  │ │                 │
│  │  │Cluster │  │ (backup)  │ │    │  │(Parquet)│  │ (tables) │ │                 │
│  │  └────┬───┘  └─────┬─────┘ │    │  └────┬────┘  └────┬─────┘ │                 │
│  │  [MON-7]●     [MON-8]●     │    │  [MON-9]●     [MON-10]●    │                 │
│  └─────────────────────────────┘    └─────────────────────────────┘                 │
│                    │                                    │                             │
└────────────────────┼────────────────────────────────────┼────────────────────────────┘
                     │                                    │
                     ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  MODEL SERVING LAYER                                                                 │
│                                                                                       │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │                    Model Serving (TensorFlow Serving / Triton)     │              │
│  │                                                                    │              │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │              │
│  │  │Candidate │  │  Ranking │  │ Re-rank  │  │  Diversity│        │              │
│  │  │Generation│─►│  Model   │─►│  (rules) │─►│  Filter  │        │              │
│  │  │(ANN/HNSW)│  │  (DNN)   │  │          │  │          │        │              │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │              │
│  └───────────────────────────────────────────┬───────────────────────┘              │
│                                        [MON-11]●                                     │
└────────────────────────────────────────────────┼────────────────────────────────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │   RECOMMENDATIONS       │
                                    │   (personalized feed)   │
                                    └────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│  BATCH RETRAINING LOOP (Daily/Weekly)                                                │
│                                                                                       │
│  Offline      ──►  Feature    ──►  Model    ──►  Validation ──► Deploy              │
│  Features           Engineering     Training      (offline)      (canary)            │
│  (Spark)            (Spark)         (GPU cluster)  (metrics)     (gradual)           │
│     │                  │               │              │              │                │
│  [MON-12]●        [MON-13]●      [MON-14]●      [MON-15]●     [MON-16]●            │
│  freshness        correctness    convergence    AUC/NDCG      serving              │
│  completeness     feature drift  loss curves    thresholds    latency              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Monitoring Challenges Unique to Recommendations

### Feature Freshness Tiers

```
┌────────────────────────────────────────────────────────────────────┐
│  FEATURE FRESHNESS SLA TIERS                                        │
│                                                                      │
│  TIER 1: Real-time (< 1 minute)                                    │
│  ├── Current session features (clicks in last 5 min)               │
│  ├── Trending scores (what's popular right now)                    │
│  ├── Real-time collaborative signals                               │
│  └── User's last-watched/played item                               │
│                                                                      │
│  TIER 2: Near-real-time (< 15 minutes)                             │
│  ├── User taste profile (rolling 7-day preferences)                │
│  ├── Item popularity scores                                        │
│  ├── Social signals (friends' activity)                            │
│  └── Content freshness scores                                      │
│                                                                      │
│  TIER 3: Batch (< 6 hours)                                         │
│  ├── User embeddings (trained daily)                               │
│  ├── Item embeddings (trained daily)                               │
│  ├── Collaborative filtering matrix                                │
│  └── Content-based similarity scores                               │
│                                                                      │
│  TIER 4: Slow-moving (< 24 hours)                                  │
│  ├── User demographic features                                     │
│  ├── Content metadata (genre, cast, etc.)                          │
│  ├── Historical engagement aggregates                              │
│  └── A/B test segment assignments                                  │
└────────────────────────────────────────────────────────────────────┘
```

### Cold Start Problem Monitoring

```
New User Journey:
═══════════════════════════════════════════════════════════════

Event 0     Event 1-5         Event 6-20        Event 20+
(signup)    (first interactions) (learning)     (personalized)
   │            │                   │               │
   ▼            ▼                   ▼               ▼
┌────────┐  ┌──────────┐      ┌──────────┐    ┌──────────┐
│Popular │  │Explore + │      │Partially │    │Fully     │
│Items   │  │ Popular  │      │Personal  │    │Personal  │
│(generic)│  │(diverse) │      │          │    │          │
└────────┘  └──────────┘      └──────────┘    └──────────┘

MONITOR:
- % users in each stage
- Time to transition between stages
- Engagement rate at each stage vs mature users
- Feature coverage: what % of new users have enough features
```

### Embedding Staleness

```
Day 1: New item "Movie X" released
Day 1: No embedding exists → item NEVER recommended
Day 2: Batch training runs → embedding computed from metadata only
Day 3: Some users watch → sparse interaction data
Day 7: Sufficient interactions → quality embedding
       ▲
       │
       └── THIS GAP = "cold item" period
           Monitor: items_without_embedding / total_active_items
```

---

## Multi-Layer Monitoring Framework

### Layer 1: Event Ingestion

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: Are we receiving all user events?                      │
│                                                                   │
│  Metrics:                                                        │
│  ├── events_ingested_total{type="click|view|play|skip|purchase"}│
│  ├── event_ingestion_lag_seconds (event_time vs ingest_time)    │
│  ├── events_dropped_total{reason="schema|size|rate_limit"}      │
│  ├── event_dedup_rate (% duplicate events)                      │
│  └── client_coverage_ratio (active users sending events / MAU)  │
│                                                                   │
│  Alerts:                                                         │
│  ├── Event volume drops > 20% vs same hour yesterday            │
│  ├── Any event type goes to zero for > 1 minute                 │
│  ├── Ingestion lag > 30 seconds                                 │
│  └── Client coverage drops below 95%                            │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 2: Feature Computation

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: Are features being computed correctly?                 │
│                                                                   │
│  Metrics:                                                        │
│  ├── feature_computation_latency_seconds{feature_group}         │
│  ├── feature_computation_errors_total{feature, error_type}      │
│  ├── feature_null_rate{feature} (% null/default values)         │
│  ├── feature_distribution_drift{feature} (PSI or KS stat)      │
│  └── feature_computation_throughput_events_per_sec              │
│                                                                   │
│  Alerts:                                                         │
│  ├── Feature null rate > 5% (usually indicates upstream issue)  │
│  ├── Feature distribution drift PSI > 0.2                       │
│  ├── Computation latency p99 > SLA for tier                     │
│  └── Flink job restart / checkpoint failure                     │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 3: Feature Serving

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: Is the feature store serving fresh data?               │
│                                                                   │
│  Metrics:                                                        │
│  ├── feature_serving_latency_seconds{store="redis|dynamodb"}    │
│  ├── feature_serving_freshness_seconds{feature_group}           │
│  ├── feature_store_hit_rate{store} (cache hit ratio)            │
│  ├── feature_store_stale_serves_total (served data older than SLA)│
│  └── feature_store_size_bytes{store}                            │
│                                                                   │
│  Alerts:                                                         │
│  ├── Serving latency p99 > 10ms                                 │
│  ├── Freshness > tier SLA for any feature group                 │
│  ├── Hit rate drops below 90%                                   │
│  └── Stale serve rate > 1%                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 4: Model Serving

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 4: Are predictions reasonable?                            │
│                                                                   │
│  Metrics:                                                        │
│  ├── model_serving_latency_seconds{model, version}              │
│  ├── model_prediction_score_distribution{model} (histogram)     │
│  ├── model_candidate_set_size (how many items considered)       │
│  ├── model_diversity_score (entropy of recommended categories)  │
│  ├── model_coverage_ratio (unique items recommended / catalog)  │
│  └── model_cold_start_fallback_rate (% using fallback logic)    │
│                                                                   │
│  Alerts:                                                         │
│  ├── Prediction score distribution shift (KL divergence > 0.1)  │
│  ├── Coverage drops below 30% of catalog                        │
│  ├── Serving latency p99 > 50ms                                 │
│  └── Cold start fallback rate > 15%                             │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 5: Business Metrics

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 5: Business outcome correlation                           │
│                                                                   │
│  Metrics (computed hourly):                                      │
│  ├── recommendation_ctr (click-through rate)                    │
│  ├── recommendation_engagement_time_seconds                     │
│  ├── recommendation_conversion_rate                             │
│  ├── recommendation_revenue_per_impression                      │
│  ├── user_satisfaction_score (implicit signals)                 │
│  └── session_depth (items interacted before leaving)            │
│                                                                   │
│  Correlation Monitoring:                                         │
│  ├── Feature freshness vs CTR (should be inversely correlated)  │
│  ├── Model version vs engagement (new model should improve)     │
│  └── Coverage vs discovery rate (diverse recs → more discovery) │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Freshness Monitoring Framework

### Per-Feature Freshness Tracking

```python
"""
Feature Freshness Monitoring Framework.
Tracks the freshness of every feature in the feature store
and triggers circuit breakers when features become stale.
"""

import time
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from prometheus_client import Gauge, Counter, Histogram, Summary
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)


class FreshnessTier(Enum):
    REALTIME = ("realtime", 60)          # < 1 minute
    NEAR_REALTIME = ("near_realtime", 900)  # < 15 minutes
    BATCH = ("batch", 21600)             # < 6 hours
    SLOW = ("slow", 86400)               # < 24 hours

    def __init__(self, label: str, sla_seconds: int):
        self.label = label
        self.sla_seconds = sla_seconds


@dataclass
class FeatureConfig:
    name: str
    tier: FreshnessTier
    critical: bool = False  # If True, stale feature triggers circuit breaker
    fallback_strategy: str = "last_known"  # last_known, default, skip


# Feature registry
FEATURE_REGISTRY: Dict[str, FeatureConfig] = {
    # Tier 1: Real-time
    "session_click_count": FeatureConfig("session_click_count", FreshnessTier.REALTIME, critical=True),
    "session_duration_sec": FeatureConfig("session_duration_sec", FreshnessTier.REALTIME, critical=True),
    "last_interaction_item": FeatureConfig("last_interaction_item", FreshnessTier.REALTIME, critical=True),
    "trending_score": FeatureConfig("trending_score", FreshnessTier.REALTIME, critical=False),

    # Tier 2: Near-real-time
    "user_taste_vector": FeatureConfig("user_taste_vector", FreshnessTier.NEAR_REALTIME, critical=True),
    "item_popularity_7d": FeatureConfig("item_popularity_7d", FreshnessTier.NEAR_REALTIME, critical=False),
    "social_signals": FeatureConfig("social_signals", FreshnessTier.NEAR_REALTIME, critical=False),

    # Tier 3: Batch
    "user_embedding_v2": FeatureConfig("user_embedding_v2", FreshnessTier.BATCH, critical=True),
    "item_embedding_v2": FeatureConfig("item_embedding_v2", FreshnessTier.BATCH, critical=False),
    "cf_scores": FeatureConfig("cf_scores", FreshnessTier.BATCH, critical=False),

    # Tier 4: Slow
    "user_demographics": FeatureConfig("user_demographics", FreshnessTier.SLOW, critical=False),
    "content_metadata": FeatureConfig("content_metadata", FreshnessTier.SLOW, critical=False),
}


# Prometheus metrics
FEATURE_FRESHNESS = Gauge(
    'recommendation_feature_freshness_seconds',
    'Age of feature data in seconds',
    ['feature_name', 'tier']
)
FEATURE_SLA_BREACH = Counter(
    'recommendation_feature_sla_breach_total',
    'Number of times a feature exceeded its freshness SLA',
    ['feature_name', 'tier']
)
FEATURE_CIRCUIT_BREAKER = Gauge(
    'recommendation_feature_circuit_breaker_open',
    'Whether the circuit breaker is open (1) or closed (0)',
    ['feature_name']
)
FRESHNESS_CHECK_DURATION = Histogram(
    'recommendation_freshness_check_duration_seconds',
    'Time to run freshness check cycle'
)
STALE_SERVE_RATE = Gauge(
    'recommendation_stale_serve_rate',
    'Percentage of requests served with at least one stale feature',
    ['tier']
)


class FeatureFreshnessMonitor:
    """
    Continuously monitors feature freshness and manages circuit breakers.
    """

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.circuit_breakers: Dict[str, bool] = {}  # feature -> is_open

    async def check_all_features(self):
        """Run a complete freshness check across all registered features."""
        now = time.time()
        stale_by_tier = {tier: 0 for tier in FreshnessTier}
        total_by_tier = {tier: 0 for tier in FreshnessTier}

        pipeline = self.redis.pipeline()
        for feature_name in FEATURE_REGISTRY:
            pipeline.get(f"feature:freshness:{feature_name}:last_update")

        results = await pipeline.execute()

        for (feature_name, config), last_update_str in zip(
            FEATURE_REGISTRY.items(), results
        ):
            total_by_tier[config.tier] += 1

            if last_update_str is None:
                freshness = float('inf')
            else:
                freshness = now - float(last_update_str)

            FEATURE_FRESHNESS.labels(
                feature_name=feature_name,
                tier=config.tier.label
            ).set(freshness)

            # Check SLA breach
            if freshness > config.tier.sla_seconds:
                FEATURE_SLA_BREACH.labels(
                    feature_name=feature_name,
                    tier=config.tier.label
                ).inc()
                stale_by_tier[config.tier] += 1

                # Circuit breaker logic
                if config.critical and freshness > config.tier.sla_seconds * 2:
                    self._open_circuit_breaker(feature_name)
                    logger.error(
                        f"Circuit breaker OPEN for {feature_name}: "
                        f"freshness={freshness:.0f}s, SLA={config.tier.sla_seconds}s"
                    )
            else:
                self._close_circuit_breaker(feature_name)

        # Report stale serve rates by tier
        for tier in FreshnessTier:
            if total_by_tier[tier] > 0:
                rate = stale_by_tier[tier] / total_by_tier[tier]
                STALE_SERVE_RATE.labels(tier=tier.label).set(rate)

    def _open_circuit_breaker(self, feature_name: str):
        self.circuit_breakers[feature_name] = True
        FEATURE_CIRCUIT_BREAKER.labels(feature_name=feature_name).set(1)

    def _close_circuit_breaker(self, feature_name: str):
        if self.circuit_breakers.get(feature_name, False):
            logger.info(f"Circuit breaker CLOSED for {feature_name}")
        self.circuit_breakers[feature_name] = False
        FEATURE_CIRCUIT_BREAKER.labels(feature_name=feature_name).set(0)

    def get_serving_decision(self, feature_name: str) -> Tuple[bool, str]:
        """
        Called at serving time to decide if a feature should be used.
        Returns (should_use, strategy).
        """
        config = FEATURE_REGISTRY.get(feature_name)
        if config is None:
            return True, "unknown_feature"

        if self.circuit_breakers.get(feature_name, False):
            return False, config.fallback_strategy

        return True, "fresh"

    async def run(self, check_interval: int = 10):
        """Main monitoring loop."""
        while True:
            with FRESHNESS_CHECK_DURATION.time():
                await self.check_all_features()
            await asyncio.sleep(check_interval)
```

### Watermark-Based Freshness Detection

```python
"""
Watermark-based freshness: compares event time watermarks
across pipeline stages to detect processing delays.
"""

from dataclasses import dataclass
from typing import Dict
import time
from prometheus_client import Gauge


WATERMARK_LAG = Gauge(
    'recommendation_watermark_lag_seconds',
    'Lag between event time watermark and wall clock',
    ['stage', 'pipeline']
)
STAGE_TO_STAGE_LAG = Gauge(
    'recommendation_stage_lag_seconds',
    'Lag between two adjacent pipeline stages',
    ['from_stage', 'to_stage', 'pipeline']
)


@dataclass
class StageWatermark:
    stage: str
    watermark_epoch: float  # Event-time watermark
    wall_clock: float       # When this watermark was observed
    events_processed: int


class WatermarkFreshnessTracker:
    """
    Tracks event-time watermarks across pipeline stages.
    Detects when processing falls behind real-time.

    Pipeline stages:
    ingestion → feature_compute → feature_store → model_serving
    """

    STAGES = ['ingestion', 'feature_compute', 'feature_store_write', 'model_serving']

    def __init__(self):
        self.watermarks: Dict[str, StageWatermark] = {}

    def update_watermark(self, stage: str, event_time_watermark: float,
                         events_processed: int):
        """Called by each pipeline stage to report its current watermark."""
        now = time.time()
        self.watermarks[stage] = StageWatermark(
            stage=stage,
            watermark_epoch=event_time_watermark,
            wall_clock=now,
            events_processed=events_processed
        )

        # Report lag from wall clock
        lag = now - event_time_watermark
        WATERMARK_LAG.labels(stage=stage, pipeline='recommendations').set(lag)

        # Report stage-to-stage lag
        stage_idx = self.STAGES.index(stage) if stage in self.STAGES else -1
        if stage_idx > 0:
            prev_stage = self.STAGES[stage_idx - 1]
            if prev_stage in self.watermarks:
                prev_watermark = self.watermarks[prev_stage].watermark_epoch
                stage_lag = prev_watermark - event_time_watermark
                STAGE_TO_STAGE_LAG.labels(
                    from_stage=prev_stage,
                    to_stage=stage,
                    pipeline='recommendations'
                ).set(max(0, stage_lag))

    def get_end_to_end_freshness(self) -> float:
        """
        Returns seconds between the last stage's watermark and wall clock.
        This represents total pipeline freshness.
        """
        if 'model_serving' in self.watermarks:
            return time.time() - self.watermarks['model_serving'].watermark_epoch
        return float('inf')

    def is_pipeline_healthy(self, max_lag_seconds: float = 120) -> bool:
        """Quick health check: is any stage more than max_lag behind?"""
        now = time.time()
        for stage, wm in self.watermarks.items():
            if now - wm.watermark_epoch > max_lag_seconds:
                return False
        return True
```

### A/B Test Exposure Logger with Completeness Monitoring

```python
"""
A/B Test exposure logging with completeness monitoring.
Ensures every recommendation served is properly logged for experiment analysis.
Missing exposure logs = biased experiment results = bad product decisions.
"""

import time
import uuid
from typing import Dict, Optional, List
from dataclasses import dataclass
from prometheus_client import Counter, Gauge, Histogram
from confluent_kafka import Producer
import json
import logging

logger = logging.getLogger(__name__)


EXPOSURE_LOGGED = Counter(
    'ab_test_exposure_logged_total',
    'Total exposure events logged',
    ['experiment_id', 'variant']
)
EXPOSURE_LOG_FAILURES = Counter(
    'ab_test_exposure_log_failures_total',
    'Failed exposure log attempts',
    ['experiment_id', 'failure_reason']
)
EXPOSURE_COMPLETENESS = Gauge(
    'ab_test_exposure_completeness_ratio',
    'Ratio of logged exposures to served recommendations',
    ['experiment_id']
)
EXPOSURE_LOG_LATENCY = Histogram(
    'ab_test_exposure_log_latency_seconds',
    'Latency to log an exposure event',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
)


@dataclass
class ExposureEvent:
    experiment_id: str
    variant: str
    user_id: str
    session_id: str
    timestamp: float
    items_shown: List[str]
    position: int
    context: Dict


class ABTestExposureLogger:
    """
    Logs every recommendation serving event as an A/B test exposure.
    Monitors completeness by comparing served count vs logged count.
    """

    def __init__(self, kafka_config: Dict):
        self.producer = Producer(kafka_config)
        self.topic = 'ab-test-exposures'

        # Counters for completeness tracking
        self.served_counts: Dict[str, int] = {}   # experiment -> served
        self.logged_counts: Dict[str, int] = {}   # experiment -> logged

    def log_exposure(self, event: ExposureEvent) -> bool:
        """
        Log an exposure event. Returns True if successfully queued.
        """
        start = time.time()
        try:
            payload = {
                'event_id': str(uuid.uuid4()),
                'experiment_id': event.experiment_id,
                'variant': event.variant,
                'user_id': event.user_id,
                'session_id': event.session_id,
                'timestamp': event.timestamp,
                'items_shown': event.items_shown,
                'position': event.position,
                'context': event.context,
                'logged_at': time.time(),
            }

            self.producer.produce(
                self.topic,
                key=event.user_id.encode(),
                value=json.dumps(payload).encode(),
                callback=self._delivery_callback
            )
            self.producer.poll(0)  # Trigger callbacks

            # Track counts
            exp_id = event.experiment_id
            self.logged_counts[exp_id] = self.logged_counts.get(exp_id, 0) + 1
            EXPOSURE_LOGGED.labels(
                experiment_id=exp_id, variant=event.variant
            ).inc()

            duration = time.time() - start
            EXPOSURE_LOG_LATENCY.observe(duration)
            return True

        except Exception as e:
            EXPOSURE_LOG_FAILURES.labels(
                experiment_id=event.experiment_id,
                failure_reason=type(e).__name__
            ).inc()
            logger.error(f"Failed to log exposure: {e}")
            return False

    def record_serving(self, experiment_id: str):
        """Called every time a recommendation is served (regardless of logging)."""
        self.served_counts[experiment_id] = \
            self.served_counts.get(experiment_id, 0) + 1

    def compute_completeness(self):
        """Compute and report exposure completeness ratios."""
        for exp_id in self.served_counts:
            served = self.served_counts.get(exp_id, 0)
            logged = self.logged_counts.get(exp_id, 0)

            if served > 0:
                completeness = logged / served
                EXPOSURE_COMPLETENESS.labels(experiment_id=exp_id).set(completeness)

                if completeness < 0.99:
                    logger.warning(
                        f"Exposure completeness for {exp_id}: {completeness:.4f} "
                        f"({served - logged} missing logs)"
                    )

    def _delivery_callback(self, err, msg):
        if err:
            logger.error(f"Exposure delivery failed: {err}")
            EXPOSURE_LOG_FAILURES.labels(
                experiment_id='unknown',
                failure_reason='delivery_failed'
            ).inc()
```

### Recommendation Diversity Scorer

```python
"""
Monitors diversity and coverage of recommendations.
Detects popularity bias drift and ensures catalog coverage.
"""

import math
from collections import Counter, defaultdict
from typing import Dict, List, Set
from prometheus_client import Gauge, Histogram
import numpy as np


DIVERSITY_SCORE = Gauge(
    'recommendation_diversity_score',
    'Shannon entropy of recommended item categories',
    ['model_version', 'user_segment']
)
CATALOG_COVERAGE = Gauge(
    'recommendation_catalog_coverage_ratio',
    'Fraction of catalog items recommended in time window',
    ['model_version', 'time_window']
)
POPULARITY_BIAS = Gauge(
    'recommendation_popularity_bias_gini',
    'Gini coefficient of recommendation frequency (1=all same item, 0=uniform)',
    ['model_version']
)
NOVELTY_SCORE = Gauge(
    'recommendation_novelty_score',
    'Average self-information of recommended items',
    ['model_version']
)


class RecommendationDiversityMonitor:
    """
    Tracks diversity, coverage, and popularity bias of recommendations.
    High-quality systems balance relevance with diversity.
    """

    def __init__(self, total_catalog_size: int):
        self.total_catalog_size = total_catalog_size
        self.recommended_items: Counter = Counter()  # item_id -> count
        self.category_distribution: Counter = Counter()  # category -> count
        self.unique_items_recommended: Set[str] = set()
        self.item_popularity: Dict[str, float] = {}  # item_id -> historical pop

    def record_recommendation(self, items: List[str], categories: List[str],
                              model_version: str, user_segment: str):
        """Called for each recommendation list served."""
        for item, category in zip(items, categories):
            self.recommended_items[item] += 1
            self.category_distribution[category] += 1
            self.unique_items_recommended.add(item)

        # Compute and report metrics
        diversity = self._shannon_entropy(categories)
        DIVERSITY_SCORE.labels(
            model_version=model_version,
            user_segment=user_segment
        ).set(diversity)

    def compute_periodic_metrics(self, model_version: str, window: str = "1h"):
        """Compute metrics over a time window (called periodically)."""

        # Catalog coverage
        coverage = len(self.unique_items_recommended) / self.total_catalog_size
        CATALOG_COVERAGE.labels(
            model_version=model_version,
            time_window=window
        ).set(coverage)

        # Popularity bias (Gini coefficient)
        if self.recommended_items:
            counts = np.array(list(self.recommended_items.values()), dtype=float)
            gini = self._gini_coefficient(counts)
            POPULARITY_BIAS.labels(model_version=model_version).set(gini)

        # Novelty (average self-information)
        if self.item_popularity and self.recommended_items:
            novelty = self._compute_novelty()
            NOVELTY_SCORE.labels(model_version=model_version).set(novelty)

    def _shannon_entropy(self, categories: List[str]) -> float:
        """Compute Shannon entropy (higher = more diverse)."""
        if not categories:
            return 0.0
        counts = Counter(categories)
        total = len(categories)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def _gini_coefficient(self, values: np.ndarray) -> float:
        """Compute Gini coefficient (0=equal, 1=concentrated)."""
        sorted_values = np.sort(values)
        n = len(sorted_values)
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * sorted_values) / (n * np.sum(sorted_values))) - (n + 1) / n

    def _compute_novelty(self) -> float:
        """Average self-information: -log2(popularity) of recommended items."""
        total_interactions = sum(self.item_popularity.values())
        novelty_sum = 0.0
        count = 0
        for item, rec_count in self.recommended_items.items():
            pop = self.item_popularity.get(item, 1) / total_interactions
            if pop > 0:
                novelty_sum += -math.log2(pop) * rec_count
                count += rec_count
        return novelty_sum / count if count > 0 else 0.0

    def reset_window(self):
        """Reset counters for new time window."""
        self.recommended_items.clear()
        self.category_distribution.clear()
        self.unique_items_recommended.clear()
```

### Airflow DAG for Batch Feature Pipeline SLA Monitoring

```python
"""
Airflow DAG that monitors batch feature pipeline freshness.
Alerts if daily/weekly batch features are not updated within SLA.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
import boto3
import time


default_args = {
    'owner': 'ml-platform',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'recommendation_feature_freshness_sla',
    default_args=default_args,
    description='Monitor batch feature pipeline freshness SLAs',
    schedule_interval='*/30 * * * *',  # Every 30 minutes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['monitoring', 'recommendations', 'sla'],
)


# Feature pipeline SLAs
BATCH_FEATURE_SLAS = {
    'user_embeddings': {
        'table': 's3://feature-store/batch/user_embeddings/',
        'max_age_hours': 26,  # Must refresh daily + 2hr buffer
        'owner': 'ml-team',
        'severity': 'critical',
    },
    'item_embeddings': {
        'table': 's3://feature-store/batch/item_embeddings/',
        'max_age_hours': 26,
        'owner': 'ml-team',
        'severity': 'critical',
    },
    'collaborative_filtering': {
        'table': 's3://feature-store/batch/cf_scores/',
        'max_age_hours': 26,
        'owner': 'ml-team',
        'severity': 'warning',
    },
    'content_similarity': {
        'table': 's3://feature-store/batch/content_sim/',
        'max_age_hours': 50,  # Updates every 2 days
        'owner': 'content-team',
        'severity': 'warning',
    },
    'user_segments': {
        'table': 's3://feature-store/batch/user_segments/',
        'max_age_hours': 170,  # Weekly
        'owner': 'data-science',
        'severity': 'info',
    },
}


def check_feature_freshness(**context):
    """Check freshness of all batch features and return violations."""
    s3 = boto3.client('s3')
    violations = []

    for feature_name, config in BATCH_FEATURE_SLAS.items():
        # Parse S3 path
        bucket = config['table'].split('/')[2]
        prefix = '/'.join(config['table'].split('/')[3:])

        # Find most recent partition
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter='/'
        )

        if 'CommonPrefixes' not in response:
            violations.append({
                'feature': feature_name,
                'issue': 'no_data_found',
                'severity': config['severity'],
                'owner': config['owner'],
            })
            continue

        # Get latest partition timestamp
        partitions = [p['Prefix'] for p in response['CommonPrefixes']]
        latest_partition = sorted(partitions)[-1]

        # Check the actual file modification time
        objects = s3.list_objects_v2(
            Bucket=bucket, Prefix=latest_partition, MaxKeys=1
        )
        if 'Contents' not in objects:
            violations.append({
                'feature': feature_name,
                'issue': 'empty_partition',
                'severity': config['severity'],
                'owner': config['owner'],
            })
            continue

        last_modified = objects['Contents'][0]['LastModified']
        age_hours = (datetime.utcnow() - last_modified.replace(tzinfo=None)).total_seconds() / 3600

        if age_hours > config['max_age_hours']:
            violations.append({
                'feature': feature_name,
                'issue': 'stale',
                'age_hours': round(age_hours, 1),
                'sla_hours': config['max_age_hours'],
                'severity': config['severity'],
                'owner': config['owner'],
            })

    context['task_instance'].xcom_push(key='violations', value=violations)
    return violations


def decide_alert_path(**context):
    """Branch based on violation severity."""
    violations = context['task_instance'].xcom_pull(
        task_ids='check_freshness', key='violations'
    )

    if not violations:
        return 'no_violations'

    severities = [v['severity'] for v in violations]
    if 'critical' in severities:
        return 'alert_critical'
    elif 'warning' in severities:
        return 'alert_warning'
    return 'no_violations'


def format_slack_message(**context):
    """Format violation details for Slack alert."""
    violations = context['task_instance'].xcom_pull(
        task_ids='check_freshness', key='violations'
    )

    blocks = [":rotating_light: *Feature Freshness SLA Violations*\n"]
    for v in violations:
        if v['issue'] == 'stale':
            blocks.append(
                f"• *{v['feature']}* [{v['severity'].upper()}]: "
                f"Age {v['age_hours']}h (SLA: {v['sla_hours']}h) "
                f"Owner: @{v['owner']}"
            )
        else:
            blocks.append(
                f"• *{v['feature']}* [{v['severity'].upper()}]: "
                f"{v['issue']} - Owner: @{v['owner']}"
            )

    return '\n'.join(blocks)


# DAG tasks
check_freshness = PythonOperator(
    task_id='check_freshness',
    python_callable=check_feature_freshness,
    dag=dag,
)

branch = BranchPythonOperator(
    task_id='decide_alert',
    python_callable=decide_alert_path,
    dag=dag,
)

no_violations = EmptyOperator(task_id='no_violations', dag=dag)

alert_warning = SlackWebhookOperator(
    task_id='alert_warning',
    slack_webhook_conn_id='slack_ml_alerts',
    message="{{ task_instance.xcom_pull(task_ids='format_message') }}",
    channel='#ml-alerts',
    dag=dag,
)

alert_critical = SlackWebhookOperator(
    task_id='alert_critical',
    slack_webhook_conn_id='slack_ml_oncall',
    message="{{ task_instance.xcom_pull(task_ids='format_message') }}",
    channel='#ml-oncall',
    dag=dag,
)

format_message = PythonOperator(
    task_id='format_message',
    python_callable=format_slack_message,
    dag=dag,
    trigger_rule='none_failed_min_one_success',
)

check_freshness >> branch >> [no_violations, alert_warning, alert_critical]
[alert_warning, alert_critical] << format_message
```

---

## Grafana Dashboard Design

### Feature Freshness Heatmap

```
┌─────────────────────────────────────────────────────────────────────────┐
│  RECOMMENDATION SYSTEM MONITORING DASHBOARD                              │
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 1: Feature Freshness Heatmap (all features, last 24 hours)         │
│                                                                           │
│  Feature               00:00  04:00  08:00  12:00  16:00  20:00  NOW    │
│  ─────────────────────────────────────────────────────────────────────   │
│  session_clicks        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  trending_score        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  user_taste_vector     ░░░░░░░░░░░░░░░░▒▒▒▒░░░░░░░░░░░░░░░░░░░░░░░░   │
│  item_popularity       ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  user_embedding        ░░░░░░░░████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  item_embedding        ░░░░░░░░████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  cf_scores             ░░░░░░░░░░██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  content_metadata      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│                                                                           │
│  Legend: ░ Fresh  ▒ Warning  █ SLA Breach  ▓ Critical                    │
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 2: Model Performance Over Time                                      │
│                                                                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  CTR by Model Version           │  │  Catalog Coverage (7 days)      ││
│  │                   v3.1 deployed  │  │                                  ││
│  │          ___      │              │  │  ───────────────────── 42%       ││
│  │  _______/   \─────┘──────────   │  │  Target: 30% ─ ─ ─ ─ ─ ─       ││
│  │  CTR: 12.3%                      │  │                                  ││
│  └─────────────────────────────────┘  └─────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 3: A/B Test Data Completeness                                       │
│                                                                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  Exposure Logging Completeness  │  │  Experiment Sample Sizes         ││
│  │                                  │  │                                  ││
│  │  exp-ranking-v3:  ████████ 99.7% │  │  exp-ranking-v3:               ││
│  │  exp-diversity:   ████████ 99.4% │  │    Control:  1,234,567          ││
│  │  exp-cold-start:  ██████░░ 94.2% │  │    Variant:  1,235,012          ││
│  │                   ▲               │  │    Balance:  ✓ 50.0%/50.0%     ││
│  │                   └─ INVESTIGATE  │  │                                  ││
│  └─────────────────────────────────┘  └─────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 4: Diversity & Coverage Metrics                                     │
│                                                                           │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  Popularity Bias (Gini Coeff)   │  │  Diversity Score (Entropy)       ││
│  │  ────────────────── 0.72         │  │  ────────────────── 3.2 bits     ││
│  │  Target: < 0.80 ─ ─ ─ ─ ─       │  │  Target: > 2.5 ─ ─ ─ ─ ─       ││
│  │  (lower = more fair distribution)│  │  (higher = more diverse)         ││
│  └─────────────────────────────────┘  └─────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Grafana Queries

```promql
# Feature freshness heatmap (all features)
recommendation_feature_freshness_seconds

# SLA breach rate per tier
sum(rate(recommendation_feature_sla_breach_total[1h])) by (tier)

# Circuit breaker status
recommendation_feature_circuit_breaker_open

# Catalog coverage trend
recommendation_catalog_coverage_ratio

# A/B test completeness
ab_test_exposure_completeness_ratio

# End-to-end pipeline freshness
recommendation_watermark_lag_seconds{stage="model_serving"}

# Diversity trend
recommendation_diversity_score
```

---

## Alert Rules

```yaml
groups:
  - name: recommendation_freshness
    rules:
      # Critical: real-time features stale
      - alert: RealtimeFeatureStale
        expr: |
          recommendation_feature_freshness_seconds{tier="realtime"} > 120
        for: 2m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "Real-time feature {{ $labels.feature_name }} stale > 2 minutes"
          impact: "Recommendations not reflecting user's current session behavior"

      # Critical: circuit breaker open
      - alert: FeatureCircuitBreakerOpen
        expr: recommendation_feature_circuit_breaker_open == 1
        for: 1m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "Circuit breaker open for {{ $labels.feature_name }}"
          description: "Model serving is using fallback values for this feature"

      # Warning: batch features behind SLA
      - alert: BatchFeatureSLABreach
        expr: |
          recommendation_feature_freshness_seconds{tier="batch"} > 21600
        for: 30m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Batch feature {{ $labels.feature_name }} > 6 hours old"

      # Warning: catalog coverage dropping
      - alert: CatalogCoverageDropping
        expr: |
          recommendation_catalog_coverage_ratio < 0.25
        for: 1h
        labels:
          severity: warning
          team: recommendations
        annotations:
          summary: "Catalog coverage dropped below 25%"
          description: "Possible popularity bias — most catalog items never recommended"

      # Warning: A/B test exposure completeness
      - alert: ABTestExposureIncomplete
        expr: |
          ab_test_exposure_completeness_ratio < 0.98
        for: 15m
        labels:
          severity: warning
          team: experimentation
        annotations:
          summary: "A/B test {{ $labels.experiment_id }} exposure logging < 98%"
          description: "Experiment analysis may be biased due to missing exposure logs"

      # Info: pipeline end-to-end freshness
      - alert: PipelineFreshnessWarning
        expr: |
          recommendation_watermark_lag_seconds{stage="model_serving"} > 300
        for: 10m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Recommendation pipeline > 5 minutes behind real-time"
```

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Event Streaming | Apache Kafka | User interaction events |
| Stream Processing | Apache Flink | Real-time feature computation |
| Batch Processing | Apache Spark | Daily embedding & batch features |
| Feature Store (Online) | Redis Cluster + DynamoDB | Low-latency feature serving |
| Feature Store (Offline) | Iceberg on S3 | Training data & historical features |
| Feature Store Platform | Feast / Tecton | Feature management & serving |
| Model Training | GPU cluster + Ray | Embedding & ranking model training |
| Model Registry | MLflow | Model versioning & deployment |
| Model Serving | TensorFlow Serving / Triton | Online inference |
| Orchestration | Apache Airflow | Batch pipeline scheduling |
| Metrics | Prometheus + Thanos | Time-series monitoring |
| Dashboards | Grafana | Visualization & alerting |
| Experimentation | Internal platform | A/B test management |

---

## Key Takeaways

1. **Freshness has tiers** — not all features need the same SLA; tier them to focus monitoring effort
2. **Circuit breakers prevent cascading failures** — better to use stale-but-known features than missing features
3. **A/B test data integrity is often overlooked** — incomplete exposure logs silently corrupt experiment decisions
4. **Coverage and diversity are first-class metrics** — pure relevance optimization leads to filter bubbles and catalog waste
5. **Watermark-based monitoring reveals true pipeline health** — wall clock delays compound across stages
6. **Cold start is a monitoring problem** — track the percentage of users/items without adequate features
7. **Business metric correlation closes the loop** — connect technical freshness metrics to engagement outcomes
