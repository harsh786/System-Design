# Ads Serving Platform (Google Ads / Facebook Ads) System Design

## 1. Functional Requirements

### Core Features
- **Campaign Management**: Create/manage ad campaigns with objectives, budgets, schedules
- **Targeting**: Demographics, interests, contextual, retargeting, lookalike audiences
- **Real-Time Bidding (RTB)**: Participate in ad auctions at page load time
- **Auction Mechanism**: Second-price / VCG auction with quality adjustments
- **Ad Ranking**: bid × quality_score × predicted_CTR for final ranking
- **Frequency Capping**: Limit impressions per user per time window
- **Budget Pacing**: Even delivery throughout day, prevent early budget exhaustion
- **Attribution & Conversion Tracking**: Multi-touch attribution, conversion pixels
- **Creative Optimization**: A/B testing, dynamic creative assembly, auto-rotation

### Out of Scope
- Ad creative design tools
- Payment/billing system details
- Publisher SDK implementation

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Auction Latency (p99) | <100ms end-to-end |
| Availability | 99.99% (revenue-critical) |
| Throughput | 1M+ ad requests/sec |
| CTR Prediction Accuracy | AUC > 0.80 |
| Budget Accuracy | Within 5% of daily budget |
| Freshness (targeting data) | <5 min for behavioral signals |
| Impression Counting | <1% discrepancy vs third-party |
| Scale | 10M advertisers, 100M ad creatives, 5B users |

## 3. Capacity Estimation

### Traffic
- Ad requests: 1M QPS (peak 3M during prime time)
- Each request evaluates: ~1000 candidate ads → rank top 10 → serve 1-5
- CTR prediction model inference: 1M × 1000 = 1B predictions/sec (batched)
- Click events: 50K/sec (avg CTR ~5%)
- Conversion events: 5K/sec

### Storage
- Campaign metadata: 10M campaigns × 10KB = 100GB
- Ad creatives metadata: 100M × 5KB = 500GB
- User profiles (targeting): 5B × 2KB = 10TB
- Click/impression logs: 1M/sec × 500B × 86400 = 43TB/day
- Feature store: 50TB (user features, context features)

### Compute
- CTR model serving: 1000 GPU instances (batch inference)
- Auction servers: 5000 CPU instances
- Real-time feature computation: 500 instances (Flink)

### Bandwidth
- Ad request (incoming): 1M × 2KB = 2GB/s
- Ad response (creative URLs + metadata): 1M × 5KB = 5GB/s
- Event streaming (clicks/impressions): 1M × 200B = 200MB/s

## 4. Data Modeling

### Primary Database: PostgreSQL (campaigns) + Cassandra (events) + Redis (real-time)

```sql
-- Advertisers
CREATE TABLE advertisers (
    advertiser_id   UUID PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    billing_type    VARCHAR(20) NOT NULL, -- prepaid, postpaid
    daily_budget    DECIMAL(12,2),
    total_budget    DECIMAL(12,2),
    status          VARCHAR(20) DEFAULT 'active',
    industry        VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Campaigns
CREATE TABLE campaigns (
    campaign_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advertiser_id   UUID NOT NULL,
    name            VARCHAR(255) NOT NULL,
    objective       VARCHAR(50) NOT NULL, -- awareness, traffic, conversions, app_install
    status          VARCHAR(20) DEFAULT 'draft', -- draft, active, paused, completed
    daily_budget    DECIMAL(12,2) NOT NULL,
    total_budget    DECIMAL(12,2),
    bid_strategy    VARCHAR(50) NOT NULL, -- manual_cpc, target_cpa, maximize_conversions, target_roas
    bid_amount      DECIMAL(8,4), -- NULL for auto-bid
    start_date      DATE NOT NULL,
    end_date        DATE,
    schedule        JSONB, -- dayparting schedule
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_advertiser FOREIGN KEY (advertiser_id) REFERENCES advertisers(advertiser_id)
);

CREATE INDEX idx_campaigns_advertiser ON campaigns(advertiser_id, status);
CREATE INDEX idx_campaigns_active ON campaigns(status, start_date, end_date) WHERE status = 'active';

-- Ad Groups (targeting groups within campaign)
CREATE TABLE ad_groups (
    ad_group_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID NOT NULL,
    name            VARCHAR(255) NOT NULL,
    status          VARCHAR(20) DEFAULT 'active',
    bid_modifier    DECIMAL(4,2) DEFAULT 1.0, -- multiplier on campaign bid
    -- Targeting
    targeting       JSONB NOT NULL,
    /*
    targeting format:
    {
      "demographics": {"age_min": 25, "age_max": 55, "gender": ["M","F"], "income": ["high"]},
      "interests": ["technology", "sports", "travel"],
      "keywords": ["running shoes", "marathon training"],
      "placements": ["youtube.com", "news.google.com"],
      "audiences": ["audience_id_1", "audience_id_2"],  -- custom/lookalike
      "geo": {"countries": ["US"], "cities": ["San Francisco"], "radius_km": 50},
      "devices": ["mobile", "desktop"],
      "languages": ["en", "es"],
      "retargeting": {"pixel_id": "px_123", "lookback_days": 30}
    }
    */
    frequency_cap   JSONB, -- {"impressions": 3, "period_hours": 24}
    CONSTRAINT fk_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE INDEX idx_ad_groups_campaign ON ad_groups(campaign_id, status);

-- Ad Creatives
CREATE TABLE ads (
    ad_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_group_id     UUID NOT NULL,
    format          VARCHAR(50) NOT NULL, -- text, image, video, carousel, native
    status          VARCHAR(20) DEFAULT 'pending_review', -- pending_review, approved, rejected, active
    -- Creative content
    headline        VARCHAR(150),
    description     VARCHAR(500),
    display_url     VARCHAR(500),
    landing_url     VARCHAR(2000) NOT NULL,
    media_url       VARCHAR(2000),
    call_to_action  VARCHAR(50),
    -- Performance
    quality_score   FLOAT DEFAULT 0.5,
    historical_ctr  FLOAT DEFAULT 0.0,
    relevance_score FLOAT DEFAULT 0.5,
    -- Review
    review_status   VARCHAR(20),
    rejection_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ad_group FOREIGN KEY (ad_group_id) REFERENCES ad_groups(ad_group_id)
);

CREATE INDEX idx_ads_group ON ads(ad_group_id, status);
CREATE INDEX idx_ads_quality ON ads(quality_score DESC) WHERE status = 'active';

-- Conversion tracking pixels
CREATE TABLE conversion_pixels (
    pixel_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advertiser_id   UUID NOT NULL,
    name            VARCHAR(255) NOT NULL,
    event_type      VARCHAR(50) NOT NULL, -- purchase, signup, add_to_cart, page_view
    attribution_window_days INTEGER DEFAULT 30,
    attribution_model VARCHAR(50) DEFAULT 'last_click', -- last_click, first_click, linear, time_decay
    pixel_code      TEXT NOT NULL,
    CONSTRAINT fk_advertiser FOREIGN KEY (advertiser_id) REFERENCES advertisers(advertiser_id)
);

-- User targeting profiles (stored in Cassandra/BigTable for scale)
-- Schema representation:
CREATE TABLE user_profiles (
    user_id         UUID PRIMARY KEY,
    demographics    JSONB, -- {age_bucket, gender, income_level, education}
    interests       TEXT[], -- inferred interest categories
    behavior        JSONB, -- {purchase_history, app_usage, search_history}
    segments        TEXT[], -- audience segment memberships
    frequency_caps  JSONB, -- {ad_group_id: {count, last_reset}}
    device_ids      TEXT[], -- cross-device graph
    last_updated    TIMESTAMPTZ
);

-- Impression/Click event log (Cassandra, time-series)
CREATE TABLE ad_events (
    event_id        UUID,
    event_type      VARCHAR(20), -- impression, click, conversion, viewable
    timestamp       TIMESTAMPTZ,
    user_id         UUID,
    ad_id           UUID,
    campaign_id     UUID,
    advertiser_id   UUID,
    placement       VARCHAR(500),
    bid_amount      DECIMAL(8,6),
    cost            DECIMAL(8,6), -- actual cost (second price)
    position        INTEGER,
    device_type     VARCHAR(20),
    geo_country     VARCHAR(2),
    PRIMARY KEY ((advertiser_id, event_type), timestamp, event_id)
) WITH CLUSTERING ORDER BY (timestamp DESC);

-- Budget tracking (real-time in Redis, persisted hourly)
CREATE TABLE budget_ledger (
    campaign_id     UUID,
    date            DATE,
    hour            INTEGER,
    impressions     BIGINT DEFAULT 0,
    clicks          BIGINT DEFAULT 0,
    spend           DECIMAL(12,4) DEFAULT 0,
    conversions     INTEGER DEFAULT 0,
    PRIMARY KEY (campaign_id, date, hour)
);
```

### Redis Schemas

```redis
# Real-time budget tracking
HSET budget:{campaign_id}:{date} spent {amount} remaining {amount} impressions {count}

# Frequency capping per user per ad_group
SET freqcap:{user_id}:{ad_group_id} {count} EX {period_seconds}

# Real-time CTR features
HSET user_features:{user_id} last_click_ts {ts} clicks_1h {count} impressions_1h {count}

# Campaign status cache (avoid DB lookups during auction)
HSET campaign_cache:{campaign_id} status active budget_remaining 150.50 bid 2.50

# Pacing controller state
HSET pacing:{campaign_id}:{date} target_hourly_spend {amount} actual_hourly_spend {amount} bid_multiplier {float}

# Ad candidate index (inverted index for targeting match)
SADD targeting:interest:technology {ad_group_id_1} {ad_group_id_2} ...
SADD targeting:geo:US {ad_group_id_1} {ad_group_id_3} ...
SADD targeting:age:25-34 {ad_group_id_1} ...
```

### Kafka Topics

```yaml
topics:
  ads.requests:
    partitions: 512
    replication: 3
    retention: 6h
    key: request_id
  ads.impressions:
    partitions: 256
    replication: 3
    retention: 30d
    key: campaign_id
  ads.clicks:
    partitions: 128
    replication: 3
    retention: 30d
    key: campaign_id
  ads.conversions:
    partitions: 64
    replication: 3
    retention: 90d
    key: advertiser_id
  ads.budget.updates:
    partitions: 64
    replication: 3
    retention: 7d
    key: campaign_id
  ads.features.realtime:
    partitions: 256
    replication: 3
    retention: 24h
    key: user_id
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              AD REQUEST FLOW (< 100ms total)                             │
│                                                                                         │
│  ┌────────────┐     ┌─────────────────┐     ┌────────────────┐     ┌───────────────┐   │
│  │ Publisher  │     │  Ad Exchange /  │     │  Candidate     │     │   CTR         │   │
│  │ (webpage/ │────▶│  Ad Server      │────▶│  Selection     │────▶│   Prediction  │   │
│  │  app)     │     │                 │     │  (Targeting)   │     │   (ML Model)  │   │
│  └────────────┘     │  - Parse req    │     │                │     │               │   │
│                     │  - User lookup  │     │  - Inverted    │     │  - Feature    │   │
│                     │  - Context      │     │    index       │     │    extract    │   │
│                     │    extract      │     │  - Budget      │     │  - Wide&Deep  │   │
│                     └─────────────────┘     │    filter      │     │  - Batch GPU  │   │
│                                             │  - Freq cap    │     │  - Score      │   │
│                                             └────────────────┘     └───────┬───────┘   │
│                                                                            │           │
│  ┌────────────┐     ┌─────────────────┐     ┌────────────────┐            │           │
│  │ Ad        │     │  Auction        │     │  Ad Ranking    │◀───────────┘           │
│  │ Rendered  │◀────│  Winner         │◀────│                │                        │
│  │ to User   │     │  Selection      │     │  rank_score =  │                        │
│  └─────┬──────┘     │                 │     │  bid × CTR ×   │                        │
│        │            │  - 2nd price    │     │  quality_score │                        │
│        │            │  - VCG for      │     │                │                        │
│        │            │    multi-slot   │     │  Top-K select  │                        │
│        │            └─────────────────┘     └────────────────┘                        │
│        │                                                                              │
└────────┼──────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              EVENT TRACKING & FEEDBACK LOOP                              │
│                                                                                         │
│  ┌────────────────┐     ┌──────────────────┐     ┌────────────────────────────────┐    │
│  │ Impression/    │     │  Event           │     │  Real-Time Aggregation         │    │
│  │ Click/Conv     │────▶│  Stream          │────▶│  (Flink)                       │    │
│  │ Pixels         │     │  (Kafka)         │     │                                │    │
│  └────────────────┘     └──────────────────┘     │  - Budget spend tracking       │    │
│                                                  │  - Pacing adjustments          │    │
│                                                  │  - CTR model feature updates   │    │
│                                                  │  - Attribution / conversions   │    │
│                                                  └────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              OFFLINE / BATCH SYSTEMS                                     │
│                                                                                         │
│  ┌────────────────┐     ┌──────────────────┐     ┌────────────────────────────────┐    │
│  │ Model Training │     │  Audience        │     │  Reporting &                   │    │
│  │ Pipeline       │     │  Builder         │     │  Analytics                     │    │
│  │                │     │                  │     │                                │    │
│  │ - Daily retrain│     │ - Lookalike      │     │ - Campaign dashboards          │    │
│  │ - A/B test     │     │ - Segment build  │     │ - Attribution reports          │    │
│  │ - Feature eng  │     │ - Profile update │     │ - Budget forecasting           │    │
│  └────────────────┘     └──────────────────┘     └────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Ad Request API (Publisher → Ad Server)

```http
POST /api/v1/ads/request
Content-Type: application/json

{
  "requestId": "req_abc123",
  "publisherId": "pub_xyz",
  "placement": {
    "id": "slot_header_728x90",
    "format": ["banner", "native"],
    "size": {"width": 728, "height": 90},
    "position": "above_fold",
    "pageUrl": "https://news.example.com/article/123",
    "pageCategory": "technology"
  },
  "user": {
    "id": "user_hashed_id",
    "cookieId": "cookie_abc",
    "deviceType": "desktop",
    "browser": "chrome",
    "os": "macos",
    "geo": {"country": "US", "region": "CA", "city": "San Francisco"},
    "language": "en"
  },
  "context": {
    "keywords": ["AI", "machine learning", "startups"],
    "contentCategory": "technology",
    "referrer": "https://google.com/search?q=ai+news"
  },
  "restrictions": {
    "blockedCategories": ["adult", "gambling"],
    "blockedAdvertisers": ["competitor_brand"]
  },
  "maxAds": 3,
  "timeout": 80
}
```

**Response:**
```json
{
  "requestId": "req_abc123",
  "ads": [
    {
      "adId": "ad_001",
      "campaignId": "camp_xyz",
      "format": "banner",
      "creative": {
        "headline": "Try Our AI Platform Free",
        "imageUrl": "https://cdn.ads.com/creative/ad_001_728x90.webp",
        "landingUrl": "https://platform.ai/signup?utm_source=display",
        "displayUrl": "platform.ai",
        "cta": "Start Free Trial"
      },
      "tracking": {
        "impressionUrl": "https://track.ads.com/imp?id=imp_123&sig=hmac_abc",
        "clickUrl": "https://track.ads.com/click?id=clk_123&sig=hmac_def",
        "viewableUrl": "https://track.ads.com/viewable?id=vw_123"
      },
      "position": 1,
      "auctionPrice": 2.35
    }
  ],
  "processingTimeMs": 45
}
```

### Campaign Creation API

```http
POST /api/v1/campaigns
Content-Type: application/json
Authorization: Bearer {advertiser_token}

{
  "name": "Q1 Product Launch",
  "objective": "conversions",
  "dailyBudget": 5000.00,
  "totalBudget": 100000.00,
  "bidStrategy": "target_cpa",
  "targetCpa": 25.00,
  "startDate": "2024-03-18",
  "endDate": "2024-06-18",
  "schedule": {
    "timezone": "America/New_York",
    "hours": {"weekday": [8, 22], "weekend": [10, 20]}
  },
  "adGroups": [
    {
      "name": "Tech Enthusiasts",
      "targeting": {
        "demographics": {"age_min": 25, "age_max": 45},
        "interests": ["technology", "software"],
        "geo": {"countries": ["US", "CA", "UK"]},
        "devices": ["desktop", "mobile"]
      },
      "frequencyCap": {"impressions": 5, "periodHours": 24},
      "ads": [
        {
          "format": "image",
          "headline": "Revolutionary AI Platform",
          "description": "Build smarter applications with our AI tools.",
          "landingUrl": "https://platform.ai/product",
          "mediaUrl": "https://assets.advertiser.com/banner_v1.png"
        }
      ]
    }
  ]
}
```

## 7. Deep Dives

### Deep Dive 1: Real-Time Auction (< 100ms)

```
Timeline breakdown for a single ad request:

0ms   - Request arrives at ad server
5ms   - User profile lookup (Redis, pre-cached)
10ms  - Context feature extraction (page content, keywords)
15ms  - Candidate selection from inverted targeting index
25ms  - Budget + frequency cap filtering
30ms  - Feature vector assembly for CTR model
55ms  - CTR prediction (GPU batch, ~25ms)
65ms  - Ranking: score = bid × pCTR × quality_score
70ms  - Auction: second-price computation
75ms  - Winner creative assembly
80ms  - Response serialization + send
```

#### Candidate Selection (Inverted Index)

```python
class AdCandidateSelector:
    """
    Selects relevant ad candidates using inverted targeting index.
    Target: narrow 100M active ads → ~1000 candidates in <15ms.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def select_candidates(self, request: dict) -> List[str]:
        """
        Multi-criteria targeting match using Redis set intersections.
        Returns ad_group_ids that match the user's profile.
        """
        user = request['user']
        context = request['context']
        
        # Build targeting keys to intersect
        targeting_sets = []
        
        # Geographic targeting
        targeting_sets.append(f"targeting:geo:{user['geo']['country']}")
        
        # Device targeting
        targeting_sets.append(f"targeting:device:{user['device_type']}")
        
        # Interest targeting (union of user interests)
        interest_keys = [f"targeting:interest:{i}" for i in user.get('interests', [])]
        
        # Get candidates matching geo + device (mandatory)
        geo_device_candidates = await self.redis.sinter(*targeting_sets)
        
        # Filter by interest (at least one interest must match)
        if interest_keys:
            interest_candidates = await self.redis.sunion(*interest_keys)
            candidates = geo_device_candidates & interest_candidates
        else:
            candidates = geo_device_candidates
        
        # Filter by active campaigns with remaining budget
        active_candidates = []
        pipe = self.redis.pipeline()
        for cand_id in candidates:
            pipe.hget(f"campaign_cache:{cand_id}", "budget_remaining")
        
        budgets = await pipe.execute()
        for cand_id, budget in zip(candidates, budgets):
            if budget and float(budget) > 0:
                active_candidates.append(cand_id)
        
        return active_candidates[:1000]  # Cap at 1000 for latency


class AuctionEngine:
    """
    Implements Generalized Second-Price (GSP) auction.
    Winner pays minimum bid needed to maintain position.
    """
    
    def run_auction(self, ranked_ads: List[dict], slots: int) -> List[dict]:
        """
        Input: ads sorted by rank_score = bid × pCTR × quality
        Output: winners with actual cost (second-price)
        
        Second-price: winner pays (next_ad_score / winner_CTR) + 0.01
        This ensures truthful bidding is optimal strategy.
        """
        winners = []
        
        for i in range(min(slots, len(ranked_ads))):
            ad = ranked_ads[i]
            
            if i + 1 < len(ranked_ads):
                next_ad = ranked_ads[i + 1]
                # Second price: pay just enough to beat next ad
                # next_score / my_quality = minimum bid I need
                min_bid = next_ad['rank_score'] / (ad['pCTR'] * ad['quality_score'])
                actual_cost = min_bid + 0.01  # Minimum increment
            else:
                # Last position: pay reserve price
                actual_cost = ad.get('reserve_price', 0.01)
            
            # Apply pacing bid modifier
            actual_cost *= ad.get('pacing_multiplier', 1.0)
            
            # Cap at original bid
            actual_cost = min(actual_cost, ad['bid'])
            
            winners.append({
                'ad_id': ad['ad_id'],
                'position': i + 1,
                'bid': ad['bid'],
                'actual_cost': round(actual_cost, 6),
                'pCTR': ad['pCTR'],
                'rank_score': ad['rank_score']
            })
        
        return winners
```

### Deep Dive 2: CTR Prediction Model

```python
import tensorflow as tf
import numpy as np
from typing import Dict, List

class WideAndDeepCTRModel:
    """
    Wide & Deep model architecture for CTR prediction.
    
    Wide component: Memorization of feature interactions (cross-product)
    Deep component: Generalization through embeddings + DNN
    
    Features:
    - Sparse: user_id, ad_id, advertiser, publisher, keywords (hashed)
    - Dense: historical CTR, position bias, time features, user engagement score
    - Cross: user_interest × ad_category, geo × time_of_day
    """
    
    EMBEDDING_DIM = 64
    HASH_BUCKETS = 1_000_000  # Feature hashing for sparse features
    
    def build_model(self):
        # === WIDE COMPONENT (Linear model with crossed features) ===
        # Cross features for memorization
        crossed_features = tf.feature_column.crossed_column(
            ['user_interest_bucket', 'ad_category'], hash_bucket_size=100000
        )
        geo_time_cross = tf.feature_column.crossed_column(
            ['geo_region', 'hour_of_day'], hash_bucket_size=5000
        )
        
        wide_columns = [crossed_features, geo_time_cross]
        
        # === DEEP COMPONENT (DNN with embeddings) ===
        # Sparse features → embeddings
        user_embedding = tf.feature_column.embedding_column(
            tf.feature_column.categorical_column_with_hash_bucket(
                'user_id', self.HASH_BUCKETS
            ), dimension=self.EMBEDDING_DIM
        )
        ad_embedding = tf.feature_column.embedding_column(
            tf.feature_column.categorical_column_with_hash_bucket(
                'ad_id', self.HASH_BUCKETS
            ), dimension=self.EMBEDDING_DIM
        )
        advertiser_embedding = tf.feature_column.embedding_column(
            tf.feature_column.categorical_column_with_hash_bucket(
                'advertiser_id', 100000
            ), dimension=32
        )
        
        # Dense features
        dense_features = [
            tf.feature_column.numeric_column('historical_ctr'),
            tf.feature_column.numeric_column('ad_quality_score'),
            tf.feature_column.numeric_column('user_engagement_score'),
            tf.feature_column.numeric_column('position_bias'),
            tf.feature_column.numeric_column('time_decay_factor'),
            tf.feature_column.numeric_column('ad_freshness_days'),
            tf.feature_column.numeric_column('user_session_depth'),
        ]
        
        deep_columns = [user_embedding, ad_embedding, advertiser_embedding] + dense_features
        
        # Build Wide & Deep model
        model = tf.estimator.DNNLinearCombinedClassifier(
            linear_feature_columns=wide_columns,
            dnn_feature_columns=deep_columns,
            dnn_hidden_units=[512, 256, 128, 64],
            dnn_activation_fn=tf.nn.relu,
            dnn_dropout=0.1,
            n_classes=2,  # click / no-click
            linear_optimizer=tf.optimizers.FTRL(learning_rate=0.1),
            dnn_optimizer=tf.optimizers.Adam(learning_rate=0.001)
        )
        
        return model


class CTRModelServer:
    """
    TensorFlow Serving wrapper for real-time CTR prediction.
    Handles batching for GPU efficiency.
    """
    
    BATCH_SIZE = 256
    MAX_BATCH_WAIT_MS = 5
    
    async def predict_batch(self, candidates: List[dict], 
                           user_features: dict, 
                           context_features: dict) -> List[float]:
        """
        Predict CTR for a batch of ad candidates.
        Batches requests for GPU throughput optimization.
        
        Input: ~1000 candidates
        Output: CTR probabilities [0, 1] for each candidate
        Processing: Batched inference on GPU, ~25ms for 1000 predictions
        """
        # Feature extraction
        feature_vectors = []
        for candidate in candidates:
            features = self._extract_features(candidate, user_features, context_features)
            feature_vectors.append(features)
        
        # Batch predict via TF Serving gRPC
        predictions = await self.tf_serving_client.predict(
            model_name="ctr_wide_deep",
            inputs={"features": np.array(feature_vectors)},
            timeout_ms=30
        )
        
        return predictions['probabilities'][:, 1].tolist()  # P(click)
    
    def _extract_features(self, candidate: dict, user: dict, context: dict) -> dict:
        """Assemble feature vector for one (user, ad, context) triple."""
        return {
            # User features (from feature store)
            'user_id': hash(user['user_id']) % self.HASH_BUCKETS,
            'user_engagement_score': user.get('engagement_score', 0.5),
            'user_interest_bucket': user.get('primary_interest', 'unknown'),
            
            # Ad features
            'ad_id': hash(candidate['ad_id']) % self.HASH_BUCKETS,
            'advertiser_id': candidate['advertiser_id'],
            'ad_category': candidate.get('category', 'unknown'),
            'historical_ctr': candidate.get('historical_ctr', 0.01),
            'ad_quality_score': candidate.get('quality_score', 0.5),
            'ad_freshness_days': candidate.get('age_days', 0),
            
            # Context features
            'geo_region': context.get('geo_region', 'unknown'),
            'hour_of_day': context.get('hour', 12),
            'position_bias': context.get('position', 1) ** (-0.3),  # Power-law decay
            'time_decay_factor': context.get('time_since_last_interaction', 0),
            'user_session_depth': context.get('session_pageviews', 1),
        }
```

### Deep Dive 3: Budget Pacing (PID Controller)

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

@dataclass
class PacingState:
    campaign_id: str
    daily_budget: float
    spent_today: float
    hours_elapsed: float
    hours_remaining: float
    bid_multiplier: float
    impressions_today: int
    target_spend_rate: float  # $/hour

class BudgetPacer:
    """
    Budget pacing using PID controller.
    
    Goal: Spend budget evenly throughout the day.
    Challenge: Traffic is not uniform (peaks at certain hours).
    
    Approach:
    - Target spend curve (can be uniform or traffic-weighted)
    - PID controller adjusts bid multiplier based on actual vs target spend
    - Bid multiplier affects auction bid: effective_bid = base_bid × multiplier
    
    PID terms:
    - P (Proportional): Current deviation from target
    - I (Integral): Accumulated under/overspend
    - D (Derivative): Rate of change of deviation
    """
    
    # PID gains (tuned empirically)
    KP = 0.5   # Proportional gain
    KI = 0.1   # Integral gain
    KD = 0.2   # Derivative gain
    
    MIN_MULTIPLIER = 0.1
    MAX_MULTIPLIER = 3.0
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self._integral_error = {}  # Accumulated error
        self._prev_error = {}     # Previous error for derivative
    
    async def compute_bid_multiplier(self, campaign_id: str) -> float:
        """
        Compute bid multiplier for a campaign using PID control.
        Called on every ad request for this campaign.
        
        Returns multiplier in [0.1, 3.0]
        """
        state = await self._get_pacing_state(campaign_id)
        
        if state.hours_remaining <= 0:
            return 0.0  # Day is over, stop spending
        
        # Target spend rate (uniform pacing)
        budget_remaining = state.daily_budget - state.spent_today
        target_spend_rate = budget_remaining / state.hours_remaining
        
        # Actual spend rate (last hour)
        actual_spend_rate = await self._get_hourly_spend_rate(campaign_id)
        
        # Error: positive = underspending, negative = overspending
        error = (target_spend_rate - actual_spend_rate) / target_spend_rate
        
        # PID computation
        # Proportional term
        p_term = self.KP * error
        
        # Integral term (accumulated error)
        self._integral_error[campaign_id] = self._integral_error.get(campaign_id, 0) + error
        # Anti-windup: clamp integral
        self._integral_error[campaign_id] = max(-5, min(5, self._integral_error[campaign_id]))
        i_term = self.KI * self._integral_error[campaign_id]
        
        # Derivative term (rate of change)
        prev_error = self._prev_error.get(campaign_id, 0)
        d_term = self.KD * (error - prev_error)
        self._prev_error[campaign_id] = error
        
        # Compute multiplier
        adjustment = p_term + i_term + d_term
        multiplier = state.bid_multiplier * (1 + adjustment)
        
        # Clamp to bounds
        multiplier = max(self.MIN_MULTIPLIER, min(self.MAX_MULTIPLIER, multiplier))
        
        # Store updated state
        await self.redis.hset(
            f"pacing:{campaign_id}:{datetime.utcnow().strftime('%Y%m%d')}",
            mapping={
                'bid_multiplier': multiplier,
                'target_spend_rate': target_spend_rate,
                'actual_spend_rate': actual_spend_rate,
                'error': error
            }
        )
        
        return multiplier
    
    async def _get_pacing_state(self, campaign_id: str) -> PacingState:
        """Fetch current pacing state from Redis."""
        data = await self.redis.hgetall(f"budget:{campaign_id}:{datetime.utcnow().strftime('%Y%m%d')}")
        
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0)
        hours_elapsed = (now - day_start).total_seconds() / 3600
        hours_remaining = 24 - hours_elapsed
        
        return PacingState(
            campaign_id=campaign_id,
            daily_budget=float(data.get('daily_budget', 0)),
            spent_today=float(data.get('spent', 0)),
            hours_elapsed=hours_elapsed,
            hours_remaining=hours_remaining,
            bid_multiplier=float(data.get('bid_multiplier', 1.0)),
            impressions_today=int(data.get('impressions', 0)),
            target_spend_rate=float(data.get('target_spend_rate', 0))
        )


class TrafficWeightedPacer(BudgetPacer):
    """
    Enhanced pacer that accounts for traffic patterns.
    Allocates more budget during high-traffic hours for maximum reach.
    """
    
    # Historical traffic distribution by hour (0-23)
    TRAFFIC_WEIGHTS = [
        0.02, 0.01, 0.01, 0.01, 0.02, 0.03,  # 0-5 AM
        0.04, 0.06, 0.07, 0.07, 0.07, 0.07,  # 6-11 AM
        0.06, 0.06, 0.06, 0.06, 0.06, 0.05,  # 12-5 PM
        0.05, 0.05, 0.04, 0.04, 0.03, 0.02,  # 6-11 PM
    ]
    
    def _get_target_hourly_budget(self, daily_budget: float, hour: int) -> float:
        """Get target spend for specific hour based on traffic pattern."""
        remaining_weight = sum(self.TRAFFIC_WEIGHTS[hour:])
        return daily_budget * (self.TRAFFIC_WEIGHTS[hour] / remaining_weight)
```

## 8. Component Optimization

### Auction Server Optimization

```
Target: 1M QPS with <100ms latency

Architecture:
- Stateless auction servers behind L4 load balancer
- Co-located with Redis for targeting index (same rack)
- CPU-optimized instances (no disk I/O in hot path)
- Pre-computed candidate sets refreshed every 5 seconds

Hot path optimizations:
1. Feature store pre-warmed: top 100M user profiles in Redis cluster
2. Model inference batched: group requests in 5ms windows
3. Candidate pre-filtering: bloom filter for budget exhausted campaigns
4. Zero-copy serialization: flatbuffers for internal communication
5. Connection pooling: persistent gRPC to model servers
```

### CTR Model Serving

```yaml
tensorflow_serving:
  model_name: ctr_wide_deep
  model_version_policy: latest
  batching:
    max_batch_size: 512
    batch_timeout_micros: 5000
    num_batch_threads: 8
    max_enqueued_batches: 100
  gpu:
    per_process_gpu_memory_fraction: 0.8
    allow_growth: true
  
  # A/B testing: shadow mode for new model versions
  model_config:
    - name: ctr_v2_prod
      base_path: /models/ctr_v2
      model_platform: tensorflow
    - name: ctr_v3_shadow
      base_path: /models/ctr_v3
      model_platform: tensorflow
```

### Real-Time Feature Updates (Flink)

```java
// Flink job: real-time user feature computation from click stream
public class UserFeatureAggregator extends KeyedProcessFunction<String, ClickEvent, UserFeatures> {
    
    private ValueState<UserFeatures> featureState;
    
    @Override
    public void processElement(ClickEvent event, Context ctx, Collector<UserFeatures> out) {
        UserFeatures features = featureState.value();
        if (features == null) features = new UserFeatures();
        
        // Update rolling stats
        features.clicksLastHour = updateRollingCount(features.clicksLastHour, event.timestamp);
        features.impressionsLastHour = features.impressionsLastHour + 1;
        features.lastClickTimestamp = event.timestamp;
        features.engagementScore = computeEngagement(features);
        
        featureState.update(features);
        
        // Emit to Redis sink
        out.collect(features);
    }
}
```

## 9. Observability

### Metrics

```yaml
metrics:
  # Auction performance
  - name: auction_latency_ms
    type: histogram
    labels: [stage] # candidate_selection, ctr_prediction, ranking, total
    buckets: [5, 10, 20, 30, 50, 75, 100, 150]
  
  - name: auction_candidates_count
    type: histogram
    labels: [publisher_tier]
    buckets: [10, 50, 100, 500, 1000, 5000]
  
  # Revenue
  - name: ad_revenue_dollars
    type: counter
    labels: [campaign_objective, ad_format]
  
  - name: effective_cpm
    type: gauge
    labels: [publisher_id, ad_format]
  
  # Model performance
  - name: ctr_prediction_accuracy_auc
    type: gauge
    labels: [model_version]
  
  - name: model_inference_latency_ms
    type: histogram
    labels: [model_name, batch_size_bucket]
  
  # Budget pacing
  - name: campaign_pacing_deviation
    type: gauge
    labels: [campaign_id_bucket, direction] # over, under
  
  - name: budget_exhausted_campaigns
    type: gauge
  
  # Quality
  - name: click_through_rate
    type: gauge
    labels: [ad_format, position]
  
  - name: conversion_rate
    type: gauge
    labels: [campaign_objective]
```

### Alerting

```yaml
alerts:
  - name: AuctionLatencyP99High
    expr: histogram_quantile(0.99, auction_latency_ms{stage="total"}) > 100
    severity: critical
    
  - name: RevenueDropSudden
    expr: rate(ad_revenue_dollars[10m]) < rate(ad_revenue_dollars[10m] offset 1h) * 0.7
    severity: critical
    description: "Revenue dropped >30% compared to same time last hour"
    
  - name: CTRModelDegradation
    expr: ctr_prediction_accuracy_auc < 0.75
    severity: warning
    
  - name: BudgetPacingDeviation
    expr: abs(campaign_pacing_deviation) > 0.3
    for: 30m
    severity: warning
```

## 10. Considerations

### Fraud Detection

```
Click fraud patterns:
- Bot traffic: anomalous click patterns, no conversion follow-through
- Click farms: high CTR from specific geo/IP ranges
- Competitor clicking: repeated clicks from same user/IP on competitor ads

Countermeasures:
- Invalid click detection model (real-time)
- IP/device fingerprint reputation scoring
- Click-to-conversion time analysis
- Automatic refunds for detected invalid clicks
```

### Privacy & Compliance

```
- GDPR/CCPA: User consent for behavioral targeting
- No cross-site tracking without consent (cookie deprecation)
- Privacy Sandbox / Topics API for interest-based targeting
- Differential privacy for aggregated reporting
- Data retention: 90 days for raw events, aggregated indefinitely
- Right to opt-out: immediate removal from targeting pools
```

### Multi-Touch Attribution

```
Models:
- Last click: 100% credit to last touchpoint (simple, biased)
- First click: 100% credit to first touchpoint
- Linear: Equal credit across all touchpoints
- Time decay: Exponential weight toward conversion
- Data-driven (Shapley value): ML-based credit assignment

Implementation:
- Cookie/device graph tracks user journey
- Attribution window: 30 days (configurable per advertiser)
- Cross-device: probabilistic matching via device graph
- View-through: credit impressions that led to conversion (lower weight)
```

## 11. Failure Scenarios & Recovery

| Failure | Impact | Mitigation |
|---------|--------|------------|
| CTR model server down | Cannot rank ads | Fallback to historical CTR, rule-based ranking |
| Budget tracker failure | Overspend risk | Pessimistic estimation, pause on uncertainty |
| Kafka partition loss | Delayed attribution | Replay from checkpoint, at-least-once processing |
| Targeting index stale | Serving to wrong audience | Background refresh every 5s, serve stale with logging |
| Auction timeout (>100ms) | No ad served (lost revenue) | Cached best-guess response, progressive timeout |
| Feature store unavailable | Degraded CTR accuracy | Default feature values, model trained to handle missing |

---
