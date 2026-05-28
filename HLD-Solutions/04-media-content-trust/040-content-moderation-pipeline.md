# Content Moderation Pipeline - System Design

## 1. Requirements

### 1.1 Functional Requirements
- Multi-modal moderation: text, image, video, audio
- ML classifiers for: toxicity, nudity/sexual content, violence/gore, hate speech, spam, misinformation, self-harm, child safety (CSAM)
- Human review workflow with configurable SLAs per category
- Appeals process (user-initiated, with escalation tiers)
- Configurable policy engine (rules DSL, per-market/jurisdiction)
- False positive handling with feedback loop
- Model retraining pipeline with active learning
- Audit trail for all moderation decisions (legal compliance)
- Real-time abuse pattern detection (coordinated attacks, brigading)

### 1.2 Non-Functional Requirements
- 99.99% availability (critical safety system)
- Auto-moderation latency: <100ms for text, <500ms for images, <2s for video (first frame)
- Human review SLA: P50 <10min, P95 <30min, P99 <2h
- Throughput: 1B+ items/day (11.5K items/sec sustained, 50K/sec peak)
- False positive rate <1% for auto-actions
- False negative rate <0.1% for critical categories (CSAM, terrorism)
- Decision consistency >95% (inter-rater reliability)

---

## 2. Capacity Estimation

### 2.1 Traffic
- 1B items/day = ~11,574 items/sec average
- Peak: 50K items/sec (events, viral content)
- Distribution: 70% text, 20% image, 8% video, 2% audio
- Text: 8.1K/sec, Image: 2.3K/sec, Video: 925/sec, Audio: 231/sec

### 2.2 Compute
- Text inference (BERT-based): ~5ms/item on GPU → 8.1K/sec ÷ 200 items/sec/GPU = 41 GPUs
- Image inference (ResNet+CLIP): ~50ms/item → 2.3K/sec ÷ 20 items/sec/GPU = 115 GPUs
- Video (per-frame sampling at 1fps, 10s preview): ~500ms → 925/sec ÷ 2/sec/GPU = 463 GPUs
- Audio (Whisper transcribe + text classify): ~200ms → 231/sec ÷ 5/sec/GPU = 47 GPUs
- Total GPU fleet: ~670 GPUs (with 2x headroom for peak: ~1,340 GPUs)

### 2.3 Human Review
- ~2% of items escalated = 20M items/day for human review
- Average review time: 30 seconds
- Required reviewer hours: 20M × 30s / 3600 = 166,667 reviewer-hours/day
- With 8-hour shifts: ~20,800 concurrent reviewers
- With AI-assisted review (pre-scored, pre-highlighted): 15s avg → 10,400 reviewers

### 2.4 Storage
- Moderation decisions: 1B/day × 500 bytes = 500 GB/day in Cassandra
- Decision history (90 days): 45 TB
- Training data (curated): 50M labeled examples × 100KB avg = 5 TB
- Audit logs: 1B/day × 200 bytes = 200 GB/day (365-day retention = 73 TB)

### 2.5 Queue Sizes
- Human review queue steady state: 20M/day ÷ 86400 × 30min SLA window = ~417K items in queue
- Appeals queue: 1% of actioned × 500M actioned = 5M/day → ~35K in queue

---

## 3. Data Modeling

### 3.1 PostgreSQL - Core Decisions & Configuration

```sql
-- Moderation decisions (partitioned by date)
CREATE TABLE moderation_decisions (
    decision_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id      VARCHAR(256) NOT NULL,
    content_type    VARCHAR(20) NOT NULL, -- text, image, video, audio
    platform_id     VARCHAR(100) NOT NULL, -- which product/platform submitted
    
    -- ML scores
    ml_scores       JSONB NOT NULL,
    -- {"toxicity": 0.92, "nudity": 0.05, "violence": 0.12, "hate_speech": 0.88, ...}
    ml_model_versions JSONB NOT NULL,
    -- {"toxicity": "v3.2.1", "nudity": "v2.1.0", ...}
    
    -- Decision
    auto_decision   VARCHAR(20), -- allow, remove, reduce_visibility, escalate
    final_decision  VARCHAR(20), -- allow, remove, reduce_visibility, warn
    decision_source VARCHAR(20) NOT NULL, -- auto, human, appeal
    confidence      DECIMAL(4,3),
    
    -- Policy
    policy_id       UUID,
    policy_version  INTEGER,
    violated_rules  JSONB DEFAULT '[]',
    jurisdiction    VARCHAR(10), -- US, EU, IN, etc.
    
    -- Timing
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    auto_decided_at TIMESTAMPTZ,
    human_decided_at TIMESTAMPTZ,
    
    -- Audit
    reviewer_id     UUID,
    review_notes    TEXT,
    appeal_id       UUID
) PARTITION BY RANGE (submitted_at);

-- Create monthly partitions
CREATE TABLE moderation_decisions_2024_01 PARTITION OF moderation_decisions
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_decisions_content ON moderation_decisions(content_id);
CREATE INDEX idx_decisions_platform ON moderation_decisions(platform_id, submitted_at DESC);
CREATE INDEX idx_decisions_escalated ON moderation_decisions(auto_decision, submitted_at)
    WHERE auto_decision = 'escalate';

-- Human review queue
CREATE TABLE review_queue (
    queue_item_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID NOT NULL,
    content_id      VARCHAR(256) NOT NULL,
    content_type    VARCHAR(20) NOT NULL,
    
    -- Priority scoring
    priority_score  DECIMAL(6,2) NOT NULL, -- higher = more urgent
    category        VARCHAR(50) NOT NULL, -- primary violation category
    severity        VARCHAR(10) NOT NULL, -- critical, high, medium, low
    
    -- Assignment
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, assigned, in_review, decided, expired
    assigned_to     UUID,
    assigned_at     TIMESTAMPTZ,
    sla_deadline    TIMESTAMPTZ NOT NULL,
    
    -- Routing
    required_expertise VARCHAR(50)[], -- language, content_type specialization
    required_market VARCHAR(10)[], -- jurisdiction expertise
    queue_name      VARCHAR(100) NOT NULL DEFAULT 'general',
    
    -- Context
    ml_scores       JSONB NOT NULL,
    content_preview TEXT, -- truncated/blurred preview
    context         JSONB DEFAULT '{}', -- reporter info, user history, etc.
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_queue_pending ON review_queue(priority_score DESC, created_at)
    WHERE status = 'pending';
CREATE INDEX idx_queue_assigned ON review_queue(assigned_to, status)
    WHERE status IN ('assigned', 'in_review');
CREATE INDEX idx_queue_sla ON review_queue(sla_deadline)
    WHERE status IN ('pending', 'assigned');
CREATE INDEX idx_queue_expertise ON review_queue USING GIN (required_expertise)
    WHERE status = 'pending';

-- Appeals
CREATE TABLE appeals (
    appeal_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID NOT NULL,
    content_id      VARCHAR(256) NOT NULL,
    appellant_id    UUID NOT NULL, -- user who appealed
    
    reason          TEXT NOT NULL,
    evidence        JSONB DEFAULT '[]', -- attached evidence
    
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, in_review, upheld, overturned, partial
    tier            SMALLINT NOT NULL DEFAULT 1, -- 1=first review, 2=senior, 3=legal
    
    assigned_to     UUID,
    decision        VARCHAR(20),
    decision_notes  TEXT,
    
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    sla_deadline    TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_appeals_status ON appeals(status, tier, submitted_at);

-- Policy engine
CREATE TABLE policies (
    policy_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft', -- draft, active, deprecated
    jurisdiction    VARCHAR(10)[], -- applicable jurisdictions
    content_types   VARCHAR(20)[], -- applicable content types
    rules           JSONB NOT NULL, -- policy rules DSL
    thresholds      JSONB NOT NULL, -- per-category thresholds
    actions         JSONB NOT NULL, -- action mappings
    created_by      UUID NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at    TIMESTAMPTZ,
    UNIQUE(name, version)
);

CREATE INDEX idx_policies_active ON policies(status, jurisdiction)
    WHERE status = 'active';

-- Reviewer performance tracking
CREATE TABLE reviewer_metrics (
    reviewer_id     UUID NOT NULL,
    date            DATE NOT NULL,
    category        VARCHAR(50) NOT NULL,
    
    items_reviewed  INTEGER DEFAULT 0,
    avg_review_time_s DECIMAL(6,1),
    accuracy_score  DECIMAL(4,3), -- measured against golden sets
    agreement_rate  DECIMAL(4,3), -- inter-rater agreement
    overturn_rate   DECIMAL(4,3), -- decisions overturned on appeal
    
    fatigue_score   DECIMAL(4,3), -- quality degradation over shift
    break_compliance BOOLEAN,
    
    PRIMARY KEY (reviewer_id, date, category)
);

-- Golden set items for QA
CREATE TABLE golden_sets (
    golden_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id      VARCHAR(256) NOT NULL,
    content_type    VARCHAR(20) NOT NULL,
    category        VARCHAR(50) NOT NULL,
    correct_decision VARCHAR(20) NOT NULL,
    difficulty      VARCHAR(10) NOT NULL, -- easy, medium, hard
    explanation     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    retired_at      TIMESTAMPTZ -- rotated out to prevent memorization
);
```

### 3.2 Cassandra - High-Volume ML Predictions

```cql
-- Store every ML prediction for audit and retraining
CREATE TABLE ml_predictions (
    content_id      TEXT,
    submitted_at    TIMESTAMP,
    content_type    TEXT,
    model_id        TEXT,
    model_version   TEXT,
    category        TEXT,
    score           DOUBLE,
    latency_ms      INT,
    features_hash   TEXT, -- hash of input features for reproducibility
    PRIMARY KEY ((content_id), submitted_at, model_id)
) WITH CLUSTERING ORDER BY (submitted_at DESC)
  AND default_time_to_live = 7776000  -- 90 days
  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_size': 1, 'compaction_window_unit': 'DAYS'};

-- Abuse patterns (time-series)
CREATE TABLE abuse_signals (
    entity_id       TEXT, -- user_id, ip, content_hash
    entity_type     TEXT,
    signal_time     TIMESTAMP,
    signal_type     TEXT, -- rapid_posting, duplicate_content, coordinated_action
    signal_value    DOUBLE,
    metadata        TEXT, -- JSON
    PRIMARY KEY ((entity_id, entity_type), signal_time)
) WITH CLUSTERING ORDER BY (signal_time DESC)
  AND default_time_to_live = 604800; -- 7 days

-- Training data labels
CREATE TABLE training_labels (
    content_id      TEXT,
    category        TEXT,
    label           TEXT, -- positive, negative, borderline
    labeler_type    TEXT, -- human, auto, consensus
    labeler_id      TEXT,
    confidence      DOUBLE,
    labeled_at      TIMESTAMP,
    PRIMARY KEY ((category), content_id, labeled_at)
) WITH CLUSTERING ORDER BY (content_id ASC, labeled_at DESC);
```

### 3.3 Redis - Real-time State

```redis
# Review queue sorted by priority (hot queue for assignment)
ZADD review_queue:general {priority_score} {queue_item_id}
ZADD review_queue:csam {priority_score} {queue_item_id}
ZADD review_queue:hate_speech {priority_score} {queue_item_id}

# Reviewer state
HSET reviewer:{id} status "available" current_item "" shift_start {ts} items_today 45
SADD reviewers:available:general {reviewer_id_1} {reviewer_id_2}
SADD reviewers:available:csam {reviewer_id_3}

# Rate limiting / abuse detection
INCR abuse:user:{user_id}:posts:{minute_bucket}
EXPIRE abuse:user:{user_id}:posts:{minute_bucket} 120

# Content hash dedup (prevent re-moderation of same content)
SET content_hash:{sha256} {decision_id} EX 86400

# Circuit breaker for ML models
HSET model:toxicity:v3 status "healthy" error_rate 0.001 p99_latency_ms 8
```

---

## 4. High-Level Design

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         CONTENT PRODUCERS                                         │
│              Posts │ Comments │ Images │ Videos │ Messages │ Profiles             │
└──────────┬──────────────────────────────────────────────────────────────────┬────┘
           │ Submit content                                                    │ Get decision
           ▼                                                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          INGESTION GATEWAY                                        │
│   Rate Limit │ Dedup (content hash) │ Format Normalize │ Priority Classify       │
└──────────┬───────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       KAFKA (Ingestion Stream)                                    │
│  Topics: content.text, content.image, content.video, content.audio               │
│  Partitions: 512 per topic, keyed by content_id                                  │
└────┬─────────────┬──────────────┬──────────────────┬─────────────────────────────┘
     │             │              │                  │
     ▼             ▼              ▼                  ▼
┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
│ TEXT ML  │ │ IMAGE ML │ │ VIDEO ML   │ │ AUDIO ML     │
│ CLUSTER  │ │ CLUSTER  │ │ CLUSTER    │ │ CLUSTER      │
│          │ │          │ │            │ │              │
│-Toxicity │ │-Nudity   │ │-Frame      │ │-Whisper STT  │
│-Hate     │ │-Violence │ │ sampling   │ │-Then text    │
│-Spam     │ │-CSAM     │ │-Nudity     │ │ pipeline     │
│-Misinfo  │ │-Text/OCR │ │-Violence   │ │-Audio class  │
│          │ │-Context  │ │-Scene      │ │              │
└─────┬────┘ └─────┬────┘ └─────┬──────┘ └──────┬───────┘
      │            │             │               │
      └────────────┴─────────────┴───────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        DECISION ENGINE                                            │
│                                                                                  │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────────────┐         │
│  │ Score        │──▶│ Policy Engine    │──▶│ Action Resolver         │         │
│  │ Aggregator   │   │ (Rules DSL)      │   │                         │         │
│  │              │   │                  │   │ - auto_allow            │         │
│  │ Combine      │   │ - Jurisdiction   │   │ - auto_remove           │         │
│  │ multi-model  │   │ - Content type   │   │ - reduce_visibility     │         │
│  │ scores       │   │ - User context   │   │ - escalate_to_human     │         │
│  │              │   │ - Thresholds     │   │ - warn_user             │         │
│  └──────────────┘   └──────────────────┘   └──────────┬──────────────┘         │
│                                                         │                        │
└─────────────────────────────────────────────────────────┼────────────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼──────────────────┐
                    │                                     │                  │
                    ▼                                     ▼                  ▼
          ┌──────────────────┐              ┌──────────────────┐  ┌──────────────┐
          │ AUTO-ACTION      │              │ HUMAN REVIEW     │  │ NOTIFICATION │
          │                  │              │ SYSTEM           │  │ SERVICE      │
          │ Execute action   │              │                  │  │              │
          │ immediately      │              │ - Priority queue │  │ - User notify│
          │                  │              │ - Skill routing  │  │ - Webhook    │
          └──────────────────┘              │ - QA sampling    │  │ - Platform   │
                                            │ - Fatigue mgmt  │  │   callback   │
                                            └────────┬─────────┘  └──────────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │ APPEALS SYSTEM   │
                                            │                  │
                                            │ - User submits   │
                                            │ - Tier escalation│
                                            │ - Fresh review   │
                                            └────────┬─────────┘
                                                     │
                                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    FEEDBACK & RETRAINING LOOP                                     │
│                                                                                  │
│  Human decisions + Appeals outcomes + User reports → Training Data Pipeline      │
│  → Active Learning Selection → Model Retraining → A/B Evaluation → Deploy       │
└──────────────────────────────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    FLINK (Real-time Pattern Detection)                            │
│                                                                                  │
│  - Coordinated inauthentic behavior (same content from N accounts in M minutes)  │
│  - Brigading detection (sudden spike in reports on single target)                │
│  - Bot patterns (posting velocity, timing regularity)                            │
│  - Evasion detection (adversarial text mutations, image perturbations)           │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Low-Level Design - APIs

### 5.1 Submit Content for Moderation

```
POST /v1/moderation/submit
Authorization: Bearer {platform_token}
Content-Type: application/json

{
  "content_id": "post-12345-abc",
  "content_type": "image",
  "content": {
    "url": "https://cdn.platform.com/uploads/img_abc.jpg",
    "text": "Check out this amazing view! #travel",
    "language": "en"
  },
  "context": {
    "author_id": "user-789",
    "author_account_age_days": 3,
    "author_previous_violations": 2,
    "author_trust_score": 0.4,
    "platform": "social_feed",
    "reporting_user_ids": ["user-111", "user-222"],
    "report_reasons": ["nudity", "spam"]
  },
  "priority": "high",
  "jurisdiction": "EU",
  "callback_url": "https://platform.com/webhooks/moderation"
}

Response 202:
{
  "decision_id": "dec_550e8400-...",
  "status": "processing",
  "estimated_latency_ms": 450
}

-- For synchronous decisions (text-only, low latency):
POST /v1/moderation/submit?sync=true

Response 200:
{
  "decision_id": "dec_550e8400-...",
  "decision": "allow",
  "scores": {
    "toxicity": 0.12,
    "hate_speech": 0.03,
    "spam": 0.08,
    "nudity": 0.01
  },
  "latency_ms": 45
}
```

### 5.2 Get Moderation Decision

```
GET /v1/moderation/decisions/{decision_id}
Authorization: Bearer {platform_token}

Response 200:
{
  "decision_id": "dec_550e8400-...",
  "content_id": "post-12345-abc",
  "status": "decided",
  "decision": "remove",
  "decision_source": "auto",
  "scores": {
    "nudity": {"score": 0.96, "model": "nudity-v2.3", "subcategory": "explicit"},
    "violence": {"score": 0.02, "model": "violence-v1.8"},
    "toxicity": {"score": 0.15, "model": "toxicity-v3.2"}
  },
  "violated_policies": [
    {"policy": "community_guidelines_v4", "rule": "no_explicit_nudity", "section": "3.2.1"}
  ],
  "action_taken": "content_removed",
  "decided_at": "2024-01-15T10:00:00.450Z",
  "appealable": true,
  "appeal_deadline": "2024-01-22T10:00:00Z"
}
```

### 5.3 Appeal a Decision

```
POST /v1/moderation/decisions/{decision_id}/appeal
Authorization: Bearer {user_token}

{
  "reason": "This is a classical art painting, not explicit content",
  "evidence": [
    {"type": "text", "content": "This is Botticelli's Birth of Venus, a famous Renaissance painting"},
    {"type": "url", "content": "https://en.wikipedia.org/wiki/The_Birth_of_Venus"}
  ]
}

Response 202:
{
  "appeal_id": "apl_660f9500-...",
  "status": "pending",
  "tier": 1,
  "estimated_review_time": "24 hours",
  "sla_deadline": "2024-01-16T10:00:00Z"
}
```

### 5.4 Reviewer Actions

```
POST /v1/moderation/review/{queue_item_id}/decide
Authorization: Bearer {reviewer_token}

{
  "decision": "remove",
  "category": "nudity",
  "subcategory": "explicit",
  "confidence": "high",
  "notes": "Clear policy violation, not artistic exemption",
  "applies_to_similar": true  -- flag similar content for auto-action
}

Response 200:
{
  "queue_item_id": "qi_abc123",
  "decision_recorded": true,
  "next_item": {
    "queue_item_id": "qi_def456",
    "content_type": "image",
    "preview_url": "https://review.internal.com/preview/...",
    "ml_scores": {...},
    "context": {...}
  }
}
```

---

## 6. Deep Dive: ML Model Ensemble Architecture

### 6.1 Cascading Classifier Pipeline

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import asyncio
import time

class ModelTier(Enum):
    FAST = "fast"        # <5ms, lower accuracy
    STANDARD = "standard" # <50ms, good accuracy
    ACCURATE = "accurate" # <200ms, highest accuracy

@dataclass
class ModelPrediction:
    category: str
    score: float
    model_id: str
    model_version: str
    tier: ModelTier
    latency_ms: float
    features: Optional[Dict] = None

@dataclass
class EnsembleResult:
    scores: Dict[str, float]  # category → final score
    predictions: List[ModelPrediction] = field(default_factory=list)
    total_latency_ms: float = 0
    models_invoked: int = 0

class CascadingClassifier:
    """
    Multi-tier cascading ML classifier.
    
    Strategy:
    1. Fast tier (lightweight model): classify obvious cases immediately
       - Clear allow (all scores < low_threshold) → ALLOW
       - Clear violation (any score > high_threshold) → ACTION
    2. Standard tier: for uncertain cases from fast tier
       - More accurate model with richer features
    3. Accurate tier: for borderline cases or high-stakes categories
       - Most expensive model, only invoked when necessary
    
    This reduces average inference cost by 60-70% while maintaining accuracy.
    """
    
    # Thresholds for cascade decisions
    FAST_ALLOW_THRESHOLD = 0.15   # Below this → definitely safe
    FAST_ACTION_THRESHOLD = 0.92  # Above this → definitely violating
    STANDARD_ALLOW_THRESHOLD = 0.25
    STANDARD_ACTION_THRESHOLD = 0.85
    UNCERTAINTY_BAND = 0.15  # Width of "uncertain" zone
    
    # Categories requiring highest accuracy (always go to accurate tier)
    HIGH_STAKES_CATEGORIES = {'csam', 'terrorism', 'self_harm'}
    
    def __init__(self, model_registry):
        self.registry = model_registry
        self.models = {
            ModelTier.FAST: {
                'text': 'distilbert-toxicity-v2',
                'image': 'mobilenet-nsfw-v3',
            },
            ModelTier.STANDARD: {
                'text': 'roberta-moderation-v4',
                'image': 'resnet50-moderation-v3',
            },
            ModelTier.ACCURATE: {
                'text': 'deberta-xl-moderation-v2',
                'image': 'clip-vit-l14-moderation-v2',
            }
        }
    
    async def classify(self, content: dict, content_type: str,
                       context: dict = None) -> EnsembleResult:
        """Run cascading classification on content."""
        result = EnsembleResult(scores={})
        start_time = time.time()
        
        # ─── TIER 1: Fast Model ───
        fast_predictions = await self._run_tier(
            ModelTier.FAST, content, content_type
        )
        result.predictions.extend(fast_predictions)
        result.models_invoked += 1
        
        # Check if fast tier is conclusive
        fast_decision = self._evaluate_tier(fast_predictions, ModelTier.FAST)
        
        if fast_decision == 'allow':
            result.scores = {p.category: p.score for p in fast_predictions}
            result.total_latency_ms = (time.time() - start_time) * 1000
            return result
        
        if fast_decision == 'action' and not self._needs_escalation(fast_predictions):
            result.scores = {p.category: p.score for p in fast_predictions}
            result.total_latency_ms = (time.time() - start_time) * 1000
            return result
        
        # ─── TIER 2: Standard Model (only for uncertain categories) ───
        uncertain_categories = self._get_uncertain_categories(fast_predictions, ModelTier.FAST)
        
        standard_predictions = await self._run_tier(
            ModelTier.STANDARD, content, content_type,
            categories=uncertain_categories
        )
        result.predictions.extend(standard_predictions)
        result.models_invoked += 1
        
        # Merge predictions (standard tier overrides fast for uncertain categories)
        merged = self._merge_predictions(fast_predictions, standard_predictions)
        
        standard_decision = self._evaluate_tier(merged, ModelTier.STANDARD)
        
        if standard_decision in ('allow', 'action') and not self._needs_escalation(merged):
            result.scores = {p.category: p.score for p in merged}
            result.total_latency_ms = (time.time() - start_time) * 1000
            return result
        
        # ─── TIER 3: Accurate Model (borderline or high-stakes) ───
        still_uncertain = self._get_uncertain_categories(merged, ModelTier.STANDARD)
        high_stakes = [p.category for p in merged 
                      if p.category in self.HIGH_STAKES_CATEGORIES and p.score > 0.3]
        categories_for_accurate = list(set(still_uncertain + high_stakes))
        
        if categories_for_accurate:
            accurate_predictions = await self._run_tier(
                ModelTier.ACCURATE, content, content_type,
                categories=categories_for_accurate,
                context=context  # Accurate model uses full context
            )
            result.predictions.extend(accurate_predictions)
            result.models_invoked += 1
            merged = self._merge_predictions(merged, accurate_predictions)
        
        result.scores = {p.category: p.score for p in merged}
        result.total_latency_ms = (time.time() - start_time) * 1000
        return result
    
    async def _run_tier(self, tier: ModelTier, content: dict,
                       content_type: str, categories: List[str] = None,
                       context: dict = None) -> List[ModelPrediction]:
        """Run inference for a specific tier."""
        model_id = self.models[tier][content_type]
        model = self.registry.get_model(model_id)
        
        start = time.time()
        raw_scores = await model.predict(content, categories=categories, context=context)
        latency = (time.time() - start) * 1000
        
        predictions = []
        for category, score in raw_scores.items():
            predictions.append(ModelPrediction(
                category=category,
                score=score,
                model_id=model_id,
                model_version=model.version,
                tier=tier,
                latency_ms=latency
            ))
        
        return predictions
    
    def _evaluate_tier(self, predictions: List[ModelPrediction], 
                       tier: ModelTier) -> str:
        """Evaluate whether tier result is conclusive."""
        if tier == ModelTier.FAST:
            low, high = self.FAST_ALLOW_THRESHOLD, self.FAST_ACTION_THRESHOLD
        else:
            low, high = self.STANDARD_ALLOW_THRESHOLD, self.STANDARD_ACTION_THRESHOLD
        
        max_score = max(p.score for p in predictions) if predictions else 0
        
        if max_score < low:
            return 'allow'
        elif max_score > high:
            return 'action'
        return 'uncertain'
    
    def _get_uncertain_categories(self, predictions: List[ModelPrediction],
                                   tier: ModelTier) -> List[str]:
        """Get categories that need further evaluation."""
        if tier == ModelTier.FAST:
            low, high = self.FAST_ALLOW_THRESHOLD, self.FAST_ACTION_THRESHOLD
        else:
            low, high = self.STANDARD_ALLOW_THRESHOLD, self.STANDARD_ACTION_THRESHOLD
        
        return [p.category for p in predictions if low <= p.score <= high]
    
    def _needs_escalation(self, predictions: List[ModelPrediction]) -> bool:
        """Check if any high-stakes category has concerning scores."""
        for p in predictions:
            if p.category in self.HIGH_STAKES_CATEGORIES and p.score > 0.3:
                return True
        return False
    
    def _merge_predictions(self, base: List[ModelPrediction],
                          override: List[ModelPrediction]) -> List[ModelPrediction]:
        """Merge predictions, higher tier overrides lower for same category."""
        merged = {p.category: p for p in base}
        for p in override:
            merged[p.category] = p  # Override with more accurate prediction
        return list(merged.values())


class ConfidenceCalibrator:
    """
    Calibrate model confidence scores using Platt scaling.
    Raw model scores are often poorly calibrated (overconfident or underconfident).
    """
    
    def __init__(self):
        self.calibration_params = {}  # {model_id: {category: (A, B)}}
    
    def calibrate(self, raw_score: float, model_id: str, category: str) -> float:
        """Apply Platt scaling: P(y=1|score) = 1 / (1 + exp(A*score + B))"""
        if model_id not in self.calibration_params:
            return raw_score  # No calibration available
        
        params = self.calibration_params[model_id].get(category)
        if not params:
            return raw_score
        
        A, B = params
        calibrated = 1.0 / (1.0 + np.exp(A * raw_score + B))
        return float(calibrated)
    
    def fit(self, model_id: str, category: str, 
            scores: np.ndarray, labels: np.ndarray):
        """Fit calibration parameters from validation set."""
        from sklearn.linear_model import LogisticRegression
        
        lr = LogisticRegression()
        lr.fit(scores.reshape(-1, 1), labels)
        
        A = float(lr.coef_[0][0])
        B = float(lr.intercept_[0])
        
        if model_id not in self.calibration_params:
            self.calibration_params[model_id] = {}
        self.calibration_params[model_id][category] = (A, B)


class ActiveLearningSelector:
    """Select the most informative samples for human labeling."""
    
    def __init__(self, budget_per_day: int = 10000):
        self.budget = budget_per_day
    
    def select_samples(self, predictions: List[dict]) -> List[str]:
        """
        Select samples using uncertainty sampling + diversity.
        
        Strategy:
        1. Uncertainty: items where model is least confident (near decision boundary)
        2. Diversity: ensure coverage across categories and content types
        3. Disagreement: items where fast and accurate models disagree
        """
        scored_items = []
        
        for pred in predictions:
            uncertainty = self._compute_uncertainty(pred['scores'])
            disagreement = self._compute_model_disagreement(pred['predictions'])
            
            # Combined informativeness score
            info_score = 0.6 * uncertainty + 0.4 * disagreement
            scored_items.append((pred['content_id'], info_score, pred))
        
        # Sort by informativeness
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        # Apply diversity filter (don't over-sample one category)
        selected = self._diversity_filter(scored_items, self.budget)
        
        return [item[0] for item in selected]
    
    def _compute_uncertainty(self, scores: Dict[str, float]) -> float:
        """Entropy-based uncertainty."""
        values = list(scores.values())
        # Higher entropy = more uncertain
        entropy = -sum(s * np.log(s + 1e-10) + (1-s) * np.log(1-s + 1e-10) 
                      for s in values)
        return entropy / len(values)
    
    def _compute_model_disagreement(self, predictions: List[ModelPrediction]) -> float:
        """Measure disagreement between model tiers."""
        by_category = {}
        for p in predictions:
            if p.category not in by_category:
                by_category[p.category] = []
            by_category[p.category].append(p.score)
        
        disagreements = [max(scores) - min(scores) 
                        for scores in by_category.values() if len(scores) > 1]
        return np.mean(disagreements) if disagreements else 0
```

---

## 7. Deep Dive: Human Review Queue Optimization

### 7.1 Priority Scoring & Reviewer Matching

```python
import math
from datetime import datetime, timedelta

class ReviewQueueManager:
    """
    Optimized human review queue with:
    - Dynamic priority scoring
    - Expertise-based routing
    - Fatigue management
    - QA via golden sets
    """
    
    # Priority weights
    SEVERITY_WEIGHTS = {'critical': 100, 'high': 50, 'medium': 20, 'low': 5}
    CATEGORY_URGENCY = {
        'csam': 200, 'terrorism': 150, 'self_harm': 120,
        'hate_speech': 60, 'nudity': 40, 'violence': 40,
        'spam': 10, 'misinformation': 30
    }
    
    def compute_priority_score(self, item: dict) -> float:
        """
        Priority score = f(severity, category urgency, time in queue, 
                          report count, user trust, content visibility)
        
        Higher score = reviewed first.
        """
        score = 0.0
        
        # Base severity
        score += self.SEVERITY_WEIGHTS.get(item['severity'], 10)
        
        # Category urgency
        score += self.CATEGORY_URGENCY.get(item['category'], 20)
        
        # ML confidence (less confident = needs human more urgently)
        ml_score = item.get('ml_confidence', 0.5)
        uncertainty_bonus = (1 - abs(ml_score - 0.5) * 2) * 30  # Max 30 for 0.5 confidence
        score += uncertainty_bonus
        
        # Time decay: urgency increases as SLA approaches
        time_to_sla = (item['sla_deadline'] - datetime.utcnow()).total_seconds()
        if time_to_sla > 0:
            sla_urgency = max(0, 50 * (1 - time_to_sla / 1800))  # Ramps up in last 30min
            score += sla_urgency
        else:
            score += 200  # SLA breached - highest priority
        
        # Report count (more reports = more likely violating)
        report_count = item.get('report_count', 0)
        score += min(30, report_count * 5)
        
        # Content visibility amplifier (viral content = more urgent)
        views = item.get('content_views', 0)
        if views > 10000:
            score += 40
        elif views > 1000:
            score += 20
        
        # Author risk factor
        author_trust = item.get('author_trust_score', 0.5)
        score += (1 - author_trust) * 20
        
        return round(score, 2)
    
    def assign_to_reviewer(self, queue_item: dict, 
                           available_reviewers: List[dict]) -> Optional[str]:
        """
        Match queue item to best available reviewer.
        
        Criteria:
        1. Required expertise match (language, category)
        2. Reviewer accuracy for this category
        3. Current workload balance
        4. Fatigue score (avoid assigning traumatic content to fatigued reviewers)
        """
        candidates = []
        
        for reviewer in available_reviewers:
            # Must-have: expertise match
            if not self._expertise_match(queue_item, reviewer):
                continue
            
            # Must-have: not fatigued for traumatic content
            if queue_item['category'] in ('csam', 'violence', 'self_harm'):
                if reviewer.get('fatigue_score', 0) > 0.7:
                    continue
                if reviewer.get('traumatic_items_today', 0) >= reviewer.get('traumatic_limit', 20):
                    continue
            
            # Scoring
            fit_score = 0.0
            
            # Category accuracy
            category_accuracy = reviewer.get('accuracy', {}).get(queue_item['category'], 0.8)
            fit_score += category_accuracy * 40
            
            # Workload balance (prefer less loaded reviewers)
            current_load = reviewer.get('items_in_progress', 0)
            fit_score += max(0, 20 - current_load * 5)
            
            # Freshness (avoid consecutive same-category items)
            if reviewer.get('last_category') != queue_item['category']:
                fit_score += 10
            
            candidates.append((reviewer['reviewer_id'], fit_score))
        
        if not candidates:
            return None
        
        # Select best candidate
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _expertise_match(self, item: dict, reviewer: dict) -> bool:
        """Check if reviewer has required expertise."""
        required_expertise = item.get('required_expertise', [])
        reviewer_expertise = set(reviewer.get('expertise', []))
        
        # All required expertise must be met
        for req in required_expertise:
            if req not in reviewer_expertise:
                return False
        
        # Market/jurisdiction match
        required_markets = item.get('required_market', [])
        if required_markets:
            reviewer_markets = set(reviewer.get('markets', []))
            if not reviewer_markets.intersection(set(required_markets)):
                return False
        
        return True


class FatigueManager:
    """
    Monitor and manage reviewer fatigue, especially for traumatic content.
    
    Implements:
    - Mandatory breaks after N traumatic items
    - Quality degradation detection
    - Shift time limits
    - Content variety rotation
    """
    
    TRAUMATIC_CATEGORIES = {'csam', 'violence', 'gore', 'self_harm'}
    MAX_TRAUMATIC_CONSECUTIVE = 5
    MANDATORY_BREAK_AFTER_TRAUMATIC = 10  # minutes
    MAX_SHIFT_HOURS = 6
    QUALITY_WINDOW = 20  # items to compute rolling accuracy
    
    def check_fatigue(self, reviewer_id: str, metrics: dict) -> dict:
        """Evaluate reviewer fatigue level and recommend actions."""
        fatigue_score = 0.0
        recommendations = []
        
        # Time-based fatigue
        shift_duration_hours = metrics.get('shift_duration_hours', 0)
        if shift_duration_hours > self.MAX_SHIFT_HOURS:
            fatigue_score = 1.0
            recommendations.append('end_shift')
        elif shift_duration_hours > 4:
            fatigue_score += 0.3
            recommendations.append('suggest_break')
        
        # Traumatic content exposure
        traumatic_consecutive = metrics.get('traumatic_consecutive', 0)
        if traumatic_consecutive >= self.MAX_TRAUMATIC_CONSECUTIVE:
            fatigue_score += 0.4
            recommendations.append('mandatory_break')
            recommendations.append('rotate_content_type')
        
        # Quality degradation detection
        recent_accuracy = metrics.get('rolling_accuracy', 1.0)
        baseline_accuracy = metrics.get('baseline_accuracy', 0.9)
        if recent_accuracy < baseline_accuracy - 0.1:
            fatigue_score += 0.3
            recommendations.append('quality_warning')
        
        # Speed anomaly (too fast = not reviewing carefully)
        avg_review_time = metrics.get('avg_review_time_last_10', 30)
        if avg_review_time < 10:  # Less than 10 seconds average
            fatigue_score += 0.2
            recommendations.append('slow_down_warning')
        
        return {
            'fatigue_score': min(1.0, fatigue_score),
            'recommendations': recommendations,
            'can_review_traumatic': fatigue_score < 0.5
        }


class GoldenSetQA:
    """
    Quality assurance via golden set items injected into review queue.
    
    - 5% of items are pre-labeled golden set items
    - Reviewer doesn't know which items are golden
    - Track accuracy per reviewer per category
    - Flag reviewers falling below threshold
    """
    
    INJECTION_RATE = 0.05  # 5% of items are golden
    MIN_ACCURACY_THRESHOLD = 0.85
    
    def should_inject_golden(self, items_since_last_golden: int) -> bool:
        """Probabilistic injection of golden items."""
        expected_interval = int(1 / self.INJECTION_RATE)
        if items_since_last_golden >= expected_interval:
            return True
        # Randomized to prevent gaming
        return random.random() < self.INJECTION_RATE
    
    def select_golden_item(self, reviewer_id: str, category: str,
                          recent_accuracy: float) -> dict:
        """Select appropriate golden item based on reviewer performance."""
        # If accuracy is dropping, use easier items to confirm
        if recent_accuracy < 0.9:
            difficulty = 'easy'
        else:
            # Challenge with harder items
            difficulty = random.choice(['medium', 'hard'])
        
        # Query golden set DB
        golden = self._get_random_golden(category, difficulty)
        return golden
    
    def evaluate_golden_response(self, reviewer_id: str, golden_id: str,
                                 reviewer_decision: str) -> dict:
        """Check reviewer's answer against golden truth."""
        golden = self._get_golden(golden_id)
        correct = reviewer_decision == golden['correct_decision']
        
        # Update rolling accuracy
        self._update_accuracy(reviewer_id, golden['category'], correct)
        
        # Check if reviewer needs intervention
        rolling_accuracy = self._get_rolling_accuracy(reviewer_id, golden['category'])
        
        result = {'correct': correct, 'accuracy': rolling_accuracy}
        
        if rolling_accuracy < self.MIN_ACCURACY_THRESHOLD:
            result['action'] = 'pause_and_retrain'
            result['message'] = f"Accuracy {rolling_accuracy:.0%} below {self.MIN_ACCURACY_THRESHOLD:.0%} threshold"
        
        return result
```

---

## 8. Deep Dive: Policy Engine

### 8.1 Rules DSL and Execution

```python
from typing import Any, Callable
import json

class PolicyRule:
    """A single rule in the policy engine."""
    
    def __init__(self, rule_def: dict):
        self.id = rule_def['id']
        self.name = rule_def['name']
        self.condition = rule_def['condition']  # DSL expression
        self.action = rule_def['action']
        self.priority = rule_def.get('priority', 0)
        self.enabled = rule_def.get('enabled', True)

class PolicyEngine:
    """
    Configurable policy engine with rules DSL.
    
    Rules DSL supports:
    - Threshold comparisons: score.toxicity > 0.9
    - Compound conditions: score.nudity > 0.8 AND context.author_age < 18
    - Context-aware rules: jurisdiction == "DE" AND score.hate_speech > 0.7
    - Time-based rules: content.posted_time BETWEEN "22:00" AND "06:00"
    - User-based rules: context.author_violations > 3
    
    Example policy:
    {
      "name": "EU Digital Services Act Compliance",
      "version": 3,
      "jurisdiction": ["EU"],
      "rules": [
        {
          "id": "eu-csam-1",
          "name": "CSAM auto-remove",
          "condition": "score.csam > 0.7",
          "action": {"type": "remove", "report_to": "NCMEC", "priority": "immediate"}
        },
        {
          "id": "eu-hate-1",
          "name": "Hate speech high confidence",
          "condition": "score.hate_speech > 0.9 AND jurisdiction IN ['DE', 'FR']",
          "action": {"type": "remove", "notify_user": true, "within_hours": 24}
        }
      ]
    }
    """
    
    def __init__(self):
        self.policies = {}  # {policy_id: Policy}
        self.compiled_rules = []  # Pre-compiled for fast evaluation
    
    def load_policy(self, policy_def: dict):
        """Load and compile a policy definition."""
        policy_id = policy_def['policy_id']
        rules = []
        
        for rule_def in policy_def['rules']:
            rule = PolicyRule(rule_def)
            rule._compiled_condition = self._compile_condition(rule.condition)
            rules.append(rule)
        
        # Sort by priority (higher priority rules evaluated first)
        rules.sort(key=lambda r: r.priority, reverse=True)
        self.policies[policy_id] = {
            'definition': policy_def,
            'rules': rules
        }
        self._rebuild_evaluation_order()
    
    def evaluate(self, scores: Dict[str, float], context: dict,
                jurisdiction: str = None) -> dict:
        """
        Evaluate all applicable policies against scores and context.
        Returns the action to take.
        
        Evaluation order:
        1. Filter policies by jurisdiction and content type
        2. Evaluate rules in priority order
        3. First matching rule determines action (short-circuit)
        4. If no rules match → default action (allow)
        """
        evaluation_context = {
            'score': scores,
            'context': context,
            'jurisdiction': jurisdiction,
        }
        
        matched_rules = []
        
        for policy_id, policy in self.policies.items():
            # Check if policy applies to this jurisdiction
            policy_jurisdictions = policy['definition'].get('jurisdiction', [])
            if policy_jurisdictions and jurisdiction not in policy_jurisdictions:
                continue
            
            for rule in policy['rules']:
                if not rule.enabled:
                    continue
                
                try:
                    if rule._compiled_condition(evaluation_context):
                        matched_rules.append({
                            'policy_id': policy_id,
                            'rule_id': rule.id,
                            'rule_name': rule.name,
                            'action': rule.action,
                            'priority': rule.priority
                        })
                except Exception as e:
                    # Rule evaluation error - log and continue
                    pass
        
        if not matched_rules:
            return {'action': 'allow', 'matched_rules': []}
        
        # Highest priority matched rule wins
        matched_rules.sort(key=lambda r: r['priority'], reverse=True)
        winning_rule = matched_rules[0]
        
        return {
            'action': winning_rule['action']['type'],
            'action_config': winning_rule['action'],
            'matched_rules': matched_rules,
            'policy_id': winning_rule['policy_id']
        }
    
    def _compile_condition(self, condition_str: str) -> Callable:
        """
        Compile DSL condition string to executable function.
        
        Supported operators: >, <, >=, <=, ==, !=, IN, AND, OR, NOT, BETWEEN
        Supported paths: score.{category}, context.{field}, jurisdiction
        """
        # Simple recursive descent parser for the DSL
        tokens = self._tokenize(condition_str)
        ast = self._parse_expression(tokens)
        return self._compile_ast(ast)
    
    def _tokenize(self, expr: str) -> list:
        """Tokenize condition expression."""
        import re
        pattern = r'(\w+\.\w+|\w+|[><=!]+|"[^"]*"|\[.*?\]|\(|\))'
        return re.findall(pattern, expr)
    
    def _compile_ast(self, ast) -> Callable:
        """Compile AST node to callable."""
        if ast['type'] == 'comparison':
            return self._make_comparison(ast)
        elif ast['type'] == 'and':
            left = self._compile_ast(ast['left'])
            right = self._compile_ast(ast['right'])
            return lambda ctx: left(ctx) and right(ctx)
        elif ast['type'] == 'or':
            left = self._compile_ast(ast['left'])
            right = self._compile_ast(ast['right'])
            return lambda ctx: left(ctx) or right(ctx)
        return lambda ctx: False
    
    def _make_comparison(self, ast) -> Callable:
        """Create comparison function."""
        field_path = ast['left']
        op = ast['op']
        value = ast['right']
        
        def resolve_path(ctx, path):
            parts = path.split('.')
            obj = ctx
            for part in parts:
                if isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    return None
            return obj
        
        if op == '>':
            return lambda ctx: (resolve_path(ctx, field_path) or 0) > value
        elif op == '<':
            return lambda ctx: (resolve_path(ctx, field_path) or 0) < value
        elif op == '>=':
            return lambda ctx: (resolve_path(ctx, field_path) or 0) >= value
        elif op == '==':
            return lambda ctx: resolve_path(ctx, field_path) == value
        elif op == 'IN':
            return lambda ctx: resolve_path(ctx, field_path) in value
        return lambda ctx: False


class PolicyABTester:
    """A/B test policy changes before full rollout."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def create_experiment(self, experiment_id: str, 
                         control_policy_version: int,
                         treatment_policy_version: int,
                         traffic_percent: float = 5.0):
        """Create a policy A/B test."""
        self.redis.hset(f'policy_experiment:{experiment_id}', mapping={
            'control_version': control_policy_version,
            'treatment_version': treatment_policy_version,
            'traffic_percent': traffic_percent,
            'status': 'active',
            'started_at': datetime.utcnow().isoformat()
        })
    
    def get_policy_version(self, experiment_id: str, content_id: str) -> int:
        """Deterministic assignment based on content_id hash."""
        experiment = self.redis.hgetall(f'policy_experiment:{experiment_id}')
        if not experiment or experiment.get('status') != 'active':
            return int(experiment.get('control_version', 1))
        
        # Deterministic hash-based assignment
        hash_val = int(hashlib.md5(content_id.encode()).hexdigest()[:8], 16)
        bucket = hash_val % 1000
        threshold = float(experiment['traffic_percent']) * 10
        
        if bucket < threshold:
            return int(experiment['treatment_version'])
        return int(experiment['control_version'])
```

---

## 9. Component Optimization

### 9.1 Kafka Configuration for Moderation Pipeline

```properties
# High-throughput ingestion topics
topic.content.text.partitions=512
topic.content.text.replication.factor=3
topic.content.text.retention.ms=3600000  # 1 hour (processed quickly)
topic.content.text.min.insync.replicas=2

topic.content.image.partitions=256
topic.content.image.replication.factor=3
topic.content.image.retention.ms=7200000  # 2 hours

topic.content.video.partitions=128
topic.content.video.replication.factor=3

# Decision output topics
topic.decisions.partitions=256
topic.decisions.replication.factor=3
topic.decisions.retention.ms=604800000  # 7 days

# Consumer configs for ML workers
group.text-ml.max.poll.records=64
group.text-ml.max.poll.interval.ms=30000
group.text-ml.session.timeout.ms=15000

group.image-ml.max.poll.records=8
group.image-ml.max.poll.interval.ms=60000

group.video-ml.max.poll.records=2
group.video-ml.max.poll.interval.ms=300000

# Producer configs (low latency)
producer.linger.ms=5
producer.batch.size=32768
producer.compression.type=lz4
producer.acks=1  # Trade durability for latency (decisions are reconstructible)
```

### 9.2 GPU Inference Cluster

```python
class InferenceCluster:
    """Manages GPU inference fleet with model versioning and canary deploys."""
    
    def __init__(self):
        self.model_servers = {}  # {model_id: [endpoints]}
        self.canary_config = {}
    
    async def predict(self, model_id: str, inputs: list, 
                      timeout_ms: int = 100) -> list:
        """Route prediction to model server with load balancing."""
        endpoints = self.model_servers.get(model_id, [])
        if not endpoints:
            raise ModelUnavailableError(model_id)
        
        # Canary routing: send small % to new model version
        endpoint = self._select_endpoint(model_id, endpoints)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{endpoint}/predict",
                    json={"inputs": inputs},
                    timeout=aiohttp.ClientTimeout(total=timeout_ms/1000)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    raise InferenceError(f"Model returned {resp.status}")
        except asyncio.TimeoutError:
            # Fallback to fast model if accurate model times out
            raise InferenceTimeoutError(model_id, timeout_ms)
    
    def _select_endpoint(self, model_id: str, endpoints: list) -> str:
        """Weighted random selection with canary support."""
        canary = self.canary_config.get(model_id)
        if canary and random.random() < canary['traffic_percent'] / 100:
            return canary['endpoint']
        
        # Round-robin among stable endpoints
        return random.choice(endpoints)
```

### 9.3 Flink Real-Time Pattern Detection

```python
# Flink SQL for coordinated abuse detection (conceptual)
COORDINATED_ABUSE_QUERY = """
-- Detect same content hash posted by multiple accounts within 5 minutes
CREATE TABLE coordinated_posts AS
SELECT 
    content_hash,
    TUMBLE_START(event_time, INTERVAL '5' MINUTE) as window_start,
    COUNT(DISTINCT author_id) as unique_authors,
    COUNT(*) as post_count,
    COLLECT(author_id) as author_ids
FROM content_submissions
GROUP BY 
    content_hash,
    TUMBLE(event_time, INTERVAL '5' MINUTE)
HAVING COUNT(DISTINCT author_id) >= 5;

-- Detect brigading (sudden spike in reports against single target)
CREATE TABLE brigading_signals AS
SELECT
    target_content_id,
    HOP_START(event_time, INTERVAL '1' MINUTE, INTERVAL '10' MINUTE) as window_start,
    COUNT(*) as report_count,
    COUNT(DISTINCT reporter_id) as unique_reporters,
    -- Check if reporters are connected (same creation date, similar names)
    COUNT(DISTINCT reporter_creation_date) as reporter_cohorts
FROM user_reports
GROUP BY
    target_content_id,
    HOP(event_time, INTERVAL '1' MINUTE, INTERVAL '10' MINUTE)
HAVING COUNT(*) >= 10 AND COUNT(DISTINCT reporter_creation_date) <= 3;
"""

class AbusePatternDetector:
    """Real-time abuse pattern detection using sliding windows."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_posting_velocity(self, author_id: str) -> dict:
        """Detect abnormal posting velocity (bot indicator)."""
        minute_key = f"velocity:{author_id}:{int(time.time()) // 60}"
        hour_key = f"velocity:{author_id}:{int(time.time()) // 3600}"
        
        pipe = self.redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 7200)
        results = pipe.execute()
        
        per_minute = results[0]
        per_hour = results[2]
        
        signals = {}
        if per_minute > 10:
            signals['rapid_posting'] = {'rate': per_minute, 'window': '1min'}
        if per_hour > 100:
            signals['high_volume'] = {'rate': per_hour, 'window': '1hour'}
        
        return signals
    
    async def check_content_duplication(self, content_hash: str) -> dict:
        """Detect same content posted by multiple accounts."""
        key = f"content_hash:{content_hash}"
        
        pipe = self.redis.pipeline()
        pipe.sadd(key, f"{author_id}:{int(time.time())}")
        pipe.expire(key, 300)  # 5-min window
        pipe.scard(key)
        results = pipe.execute()
        
        unique_posters = results[2]
        if unique_posters >= 5:
            return {'coordinated_spam': {'unique_posters': unique_posters}}
        return {}
```

---

## 10. Observability

### 10.1 Key Metrics

```yaml
metrics:
  # Throughput
  - name: moderation_items_submitted_total
    type: counter
    labels: [content_type, platform_id]
  
  - name: moderation_decisions_total
    type: counter
    labels: [content_type, decision, decision_source, category]
  
  # Latency
  - name: moderation_auto_latency_ms
    type: histogram
    labels: [content_type, models_invoked]
    buckets: [10, 25, 50, 100, 200, 500, 1000, 2000]
  
  - name: moderation_human_review_time_seconds
    type: histogram
    labels: [category, severity]
    buckets: [10, 30, 60, 300, 600, 1800, 3600]
  
  # Quality
  - name: moderation_false_positive_rate
    type: gauge
    labels: [category, model_version]
  
  - name: moderation_false_negative_rate
    type: gauge
    labels: [category, model_version]
  
  - name: moderation_model_accuracy
    type: gauge
    labels: [model_id, model_version, category]
  
  - name: moderation_reviewer_accuracy
    type: gauge
    labels: [reviewer_id, category]
  
  # Queue health
  - name: moderation_queue_depth
    type: gauge
    labels: [queue_name, severity]
  
  - name: moderation_sla_breach_total
    type: counter
    labels: [queue_name, severity]
  
  # Appeals
  - name: moderation_appeals_total
    type: counter
    labels: [category, outcome]  # upheld, overturned
  
  - name: moderation_overturn_rate
    type: gauge
    labels: [category, decision_source]

alerts:
  - name: SLABreachRateHigh
    expr: rate(moderation_sla_breach_total[5m]) > 10
    for: 2m
    severity: critical
  
  - name: FalseNegativeSpike
    expr: moderation_false_negative_rate{category="csam"} > 0.001
    for: 1m
    severity: critical
    # CSAM false negatives are a legal liability
  
  - name: ModelLatencyDegraded
    expr: histogram_quantile(0.99, moderation_auto_latency_ms{content_type="text"}) > 200
    for: 5m
    severity: warning
  
  - name: QueueDepthCritical
    expr: moderation_queue_depth{severity="critical"} > 1000
    for: 5m
    severity: critical
  
  - name: ReviewerAccuracyDrop
    expr: moderation_reviewer_accuracy < 0.80
    for: 30m
    severity: warning
  
  - name: OverturnRateHigh
    expr: moderation_overturn_rate > 0.15
    for: 1h
    severity: warning
    # High overturn rate suggests policy or model issues
```

### 10.2 Dashboards

```
1. Real-time Operations:
   - Items/sec by content type
   - Auto-decision distribution (allow/remove/escalate)
   - ML inference latency P50/P95/P99
   - Queue depth by severity
   - Active reviewers count

2. Quality & Accuracy:
   - Model accuracy by category (trending)
   - False positive/negative rates
   - Golden set performance by reviewer
   - Appeal overturn rates
   - Inter-rater agreement

3. Policy Effectiveness:
   - Rules triggered frequency
   - A/B test results
   - Jurisdiction-specific metrics
   - Time-to-action for high-severity items

4. Abuse Detection:
   - Coordinated attack alerts
   - Bot detection rates
   - Evasion technique frequency
   - New abuse pattern discoveries
```

---

## 11. Considerations & Trade-offs

| Decision | Choice | Trade-off |
|----------|--------|-----------|
| Cascade vs parallel models | Cascade (fast→accurate) | 60% cost reduction but adds latency for borderline cases |
| Sync vs async moderation | Async default, sync for text | Better UX (instant post) but violating content visible briefly |
| Human review platform | In-house built | Higher initial cost but full control over reviewer experience |
| Policy engine | Custom DSL over general rules engine | Simpler for policy team but limited expressiveness |
| Training data storage | Cassandra over data lake | Fast access for active learning but higher storage cost |
| Vector dedup | Content hash + perceptual hash | Fast but misses semantic duplicates |
| Queue prioritization | Dynamic scoring | More complex but better SLA adherence |
| Golden sets | 5% injection rate | 5% reviewer capacity spent on QA but catches quality issues early |

### Failure Modes & Mitigations
- **ML cluster down**: Circuit breaker → escalate all to human review (temporarily lower throughput)
- **Queue SLA breach**: Auto-scale reviewers; temporarily lower threshold for auto-actions
- **Model accuracy regression**: Canary deploy catches; auto-rollback if accuracy drops >2%
- **Coordinated attack**: Flink detects pattern → auto-throttle suspicious accounts → elevate to trust & safety team
- **Reviewer fatigue**: Auto-detect quality drop → force break → reassign items
- **Policy misconfiguration**: A/B test all changes; shadow mode first; instant rollback capability

### Legal & Compliance
- CSAM: Mandatory NCMEC reporting (US), hash matching with PhotoDNA
- EU DSA: 24h removal for illegal content, transparency reporting
- NetzDG (Germany): 7-day removal for most violations, 24h for "obviously illegal"
- Audit trail: All decisions retained for 5+ years for legal discovery
- Reviewer welfare: Mandatory counseling access, limited exposure hours
