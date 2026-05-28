# Design Notification System - Multi-Channel Notification Platform

## 1. Functional Requirements

- **Multi-channel delivery**: Push (iOS/Android), Email, SMS, In-App, WebSocket, Webhook
- **Template management**: Create/manage notification templates with variables
- **User preferences**: Per-user, per-channel, per-category notification settings
- **Scheduling**: Immediate, delayed, recurring, timezone-aware delivery
- **Priority levels**: Critical (bypass DND), High, Medium, Low
- **Rate limiting**: Per-user, per-channel throttling to prevent spam
- **Batching/Digest**: Group multiple notifications into digest (hourly/daily)
- **Delivery tracking**: Sent, delivered, opened, clicked, failed states
- **A/B testing**: Test different templates/timing for engagement
- **Segmentation**: Target notifications by user attributes/behavior
- **Unsubscribe/Opt-out**: One-click unsubscribe per category
- **Retry & DLQ**: Automatic retry with exponential backoff, dead letter handling
- **Localization**: Multi-language support based on user locale
- **Rich content**: Images, action buttons, deep links in notifications

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Delivery latency (critical) | < 1s end-to-end |
| Delivery latency (standard) | < 30s end-to-end |
| Throughput | 1M notifications/minute |
| Delivery rate | > 99% for push, > 97% for email |
| Scale | 500M users, 10B notifications/day |
| Idempotency | No duplicate delivery for same event |
| Ordering | Best-effort ordering per user (not strict) |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| Total users | 500M |
| DAU | 200M |
| Notifications/day | 10B (avg 50/user) |
| Notifications/sec (avg) | 115,000 |
| Notifications/sec (peak) | 500,000 |
| Push (APNs+FCM) | 60% = 6B/day |
| Email | 25% = 2.5B/day |
| SMS | 5% = 500M/day |
| In-App | 10% = 1B/day |
| Avg notification payload | 500 bytes |
| Storage (metadata/day) | 10B × 500B = 5 TB/day |
| Template storage | 100K templates × 10KB = 1 GB |
| User preferences | 500M × 1KB = 500 GB |

## 4. Data Modeling

### Database Technology

| Store | Technology | Reason |
|---|---|---|
| Notification metadata | Cassandra | High write, time-series, append-only |
| User preferences | PostgreSQL | Relational, complex queries, ACID |
| Templates | PostgreSQL + Redis cache | Versioned, cacheable |
| Delivery state | Cassandra | High write, per-notification tracking |
| Analytics | ClickHouse | OLAP, fast aggregations |
| Queue | Kafka | Durable, partitioned, replay |
| Rate limit counters | Redis | Atomic increments, TTL |
| Scheduled jobs | Redis (sorted set) + PostgreSQL | Time-based retrieval |
| Device tokens | PostgreSQL + Redis cache | Updated frequently, queried on send |

### Schema

```sql
-- Notification Events (Cassandra)
CREATE TABLE notifications (
    user_id UUID,
    notification_id TIMEUUID,
    category VARCHAR, -- marketing, transactional, social, system
    priority INT, -- 1=critical, 2=high, 3=medium, 4=low
    title TEXT,
    body TEXT,
    data MAP<TEXT, TEXT>, -- custom payload
    channels SET<TEXT>, -- push, email, sms, in_app, webhook
    status VARCHAR, -- pending, sent, delivered, read, failed
    created_at TIMESTAMP,
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    expires_at TIMESTAMP,
    PRIMARY KEY ((user_id), notification_id)
) WITH CLUSTERING ORDER BY (notification_id DESC);

-- Delivery Attempts (Cassandra)
CREATE TABLE delivery_attempts (
    notification_id TIMEUUID,
    channel VARCHAR,
    attempt_number INT,
    status VARCHAR, -- sent, delivered, bounced, failed
    provider VARCHAR, -- apns, fcm, ses, twilio, sendgrid
    provider_message_id VARCHAR,
    error_code VARCHAR,
    error_message TEXT,
    attempted_at TIMESTAMP,
    PRIMARY KEY ((notification_id), channel, attempt_number)
);

-- User Preferences (PostgreSQL)
CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY,
    global_enabled BOOLEAN DEFAULT TRUE,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    quiet_hours_tz VARCHAR(50),
    email_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, hourly, daily, weekly
    channels_enabled JSONB DEFAULT '{"push": true, "email": true, "sms": false, "in_app": true}',
    category_settings JSONB DEFAULT '{}', -- per-category overrides
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Templates (PostgreSQL)
CREATE TABLE notification_templates (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    category VARCHAR(50),
    channels TEXT[], -- applicable channels
    title_template TEXT, -- "Hello {{user_name}}, {{item_name}} is on sale!"
    body_template TEXT,
    html_template TEXT, -- for email
    push_template JSONB, -- APNs/FCM specific fields
    variables TEXT[], -- required variables
    version INT DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Device Tokens (PostgreSQL)
CREATE TABLE device_tokens (
    user_id UUID,
    device_id VARCHAR(100),
    platform VARCHAR(10), -- ios, android, web
    token TEXT NOT NULL,
    app_version VARCHAR(20),
    os_version VARCHAR(20),
    locale VARCHAR(10),
    active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, device_id)
);
CREATE INDEX idx_dt_token ON device_tokens(token);
```

## 5. High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EVENT SOURCES                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ User     │ │ Order    │ │ Payment  │ │ Social   │ │ Marketing        │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │ Campaign Service │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
└───────┼──────────────┼──────────────┼──────────────┼────────────┼────────────┘
        │              │              │              │            │
        ▼              ▼              ▼              ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION API GATEWAY                                   │
│  - Rate limiting  - Authentication  - Validation  - Idempotency check       │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION ENGINE                                        │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    INGESTION SERVICE                                  │    │
│  │  - Accept notification requests                                       │    │
│  │  - Validate template + variables                                      │    │
│  │  - Deduplicate (idempotency key check)                               │    │
│  │  - Enqueue to Kafka                                                   │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                  ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    ORCHESTRATOR SERVICE                               │    │
│  │  - Consume from Kafka                                                │    │
│  │  - Check user preferences & opt-outs                                 │    │
│  │  - Apply rate limits                                                  │    │
│  │  - Check quiet hours (timezone-aware)                                │    │
│  │  - Determine channels (push/email/sms/in-app)                        │    │
│  │  - Apply priority rules                                               │    │
│  │  - Route to channel-specific queues                                   │    │
│  └──────────────────────┬──────────────────────┬───────────────────────┘    │
│                          │                      │                             │
│          ┌───────────────┼──────────┬───────────┼──────────┐                │
│          ▼               ▼          ▼           ▼          ▼                │
│  ┌────────────┐  ┌────────────┐  ┌──────┐  ┌───────┐  ┌────────┐          │
│  │ PUSH       │  │ EMAIL      │  │ SMS  │  │IN-APP │  │WEBHOOK │          │
│  │ SENDER     │  │ SENDER     │  │SENDER│  │SENDER │  │ SENDER │          │
│  │            │  │            │  │      │  │       │  │        │          │
│  │ APNs pool  │  │ SES/SendGr │  │Twilio│  │ WS    │  │ HTTP   │          │
│  │ FCM pool   │  │ Mailgun    │  │Nexmo │  │ Push  │  │ POST   │          │
│  │ Web Push   │  │ Postmark   │  │      │  │       │  │        │          │
│  └────────────┘  └────────────┘  └──────┘  └───────┘  └────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                            │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Cassandra │ │PostgreSQL │ │  Redis   │ │  Kafka   │ │  ClickHouse    │  │
│  │(Notifs)  │ │(Prefs/Tpl)│ │(Rate/Tok)│ │(Queue)   │ │  (Analytics)   │  │
│  └──────────┘ └───────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design - APIs

### 6.1 Send Notification API

```
POST /api/v1/notifications/send
Idempotency-Key: "evt_order_confirmed_12345"
Request: {
  "recipients": [{"user_id": "u_123"}, {"user_id": "u_456"}],  // or segment_id
  "template_id": "order_confirmed",
  "variables": {
    "order_id": "ORD-789",
    "item_name": "iPhone 15",
    "delivery_date": "May 30, 2024"
  },
  "channels": ["push", "email"],  // override template defaults
  "priority": "high",
  "category": "transactional",
  "schedule_at": null,  // null = immediate
  "ttl_seconds": 86400,  // expire after 24h if not delivered
  "collapse_key": "order_ORD-789",  // replace previous with same key
  "data": {"deep_link": "app://orders/ORD-789"}  // custom payload
}
Response (202): {
  "request_id": "req_abc",
  "notifications": [
    {"user_id": "u_123", "notification_id": "n_001", "status": "queued"},
    {"user_id": "u_456", "notification_id": "n_002", "status": "queued"}
  ]
}
```

### 6.2 Batch/Segment Send

```
POST /api/v1/notifications/broadcast
Request: {
  "segment": {"filters": [{"field": "country", "op": "in", "values": ["US", "UK"]}, {"field": "last_active", "op": "gt", "value": "2024-05-01"}]},
  "template_id": "promo_summer_sale",
  "channels": ["push", "email"],
  "priority": "low",
  "category": "marketing",
  "schedule_at": "2024-05-28T09:00:00Z",
  "rate_limit": 10000  // max 10K/minute to spread load
}
Response (202): {
  "campaign_id": "camp_xyz",
  "estimated_recipients": 5000000,
  "status": "scheduled"
}
```

### 6.3 User Preferences API

```
GET /api/v1/users/{user_id}/notification-preferences
Response: {
  "global_enabled": true,
  "quiet_hours": {"start": "22:00", "end": "07:00", "timezone": "America/New_York"},
  "channels": {"push": true, "email": true, "sms": false, "in_app": true},
  "categories": {
    "marketing": {"push": false, "email": "weekly_digest"},
    "social": {"push": true, "email": false},
    "transactional": {"push": true, "email": true}  // cannot disable
  }
}

PUT /api/v1/users/{user_id}/notification-preferences
Request: {
  "categories": {"marketing": {"push": false, "email": "daily_digest"}}
}
Response: {"ok": true}

POST /api/v1/users/{user_id}/unsubscribe
Request: {"category": "marketing", "channel": "email", "token": "unsub_token_xyz"}
Response: {"ok": true, "message": "Unsubscribed from marketing emails"}
```

### 6.4 Notification History API

```
GET /api/v1/users/{user_id}/notifications?category=social&status=unread&limit=20&cursor=xxx
Response: {
  "notifications": [
    {
      "id": "n_001",
      "title": "John liked your post",
      "body": "Your photo got 50 likes!",
      "category": "social",
      "read": false,
      "created_at": "2024-05-25T10:00:00Z",
      "data": {"deep_link": "app://post/123"},
      "image_url": "https://cdn.../thumb.jpg"
    }
  ],
  "unread_count": 5,
  "cursor": "next_page"
}

POST /api/v1/users/{user_id}/notifications/mark-read
Request: {"notification_ids": ["n_001", "n_002"]}  // or {"all": true}
Response: {"ok": true, "unread_count": 3}
```

## 7. Deep Dive - Core Components

### 7.1 Priority Queue & Rate Limiting

```
Priority Levels:
  P1 (Critical): Account security, payment failures, 2FA
    → Bypass all limits, deliver immediately, all channels
  P2 (High): Order updates, messages, friend requests
    → Standard delivery, respect quiet hours except for time-sensitive
  P3 (Medium): Social updates, recommendations
    → Can be batched, respect all preferences
  P4 (Low): Marketing, engagement, weekly digests
    → Lowest priority, heavily rate-limited, batchable

Rate Limiting (Redis):
  Per-user: max 100 notifications/hour (across all categories)
  Per-user per-category: max 20 marketing/day
  Per-channel: max 5 push/minute per user
  Global: max 1M/minute to APNs (provider limit)
  
Implementation: Token Bucket per user in Redis
  key: ratelimit:{user_id}:{category}
  algorithm: sliding window log (precise) or token bucket (efficient)
```

### 7.2 Digest/Batching Engine

```
Scenarios:
- User gets 50 "someone liked your post" in 1 hour
- Email every message in a group chat = spam
- Daily digest of all social activity

Implementation:
┌────────────────────────────────────────────────────┐
│           DIGEST AGGREGATOR                         │
├────────────────────────────────────────────────────┤
│                                                      │
│  1. Notification arrives with category "social"     │
│  2. Check user preference: email_frequency=daily    │
│  3. Instead of sending immediately:                 │
│     → Store in digest buffer (Redis sorted set)     │
│       key: digest:{user_id}:social:email            │
│       score: timestamp                               │
│       value: notification_id                         │
│                                                      │
│  4. Scheduled job runs at user's preferred time:    │
│     - Collect all buffered notifications             │
│     - Render digest template with all items          │
│     - Send single email with summary                 │
│     - Clear buffer                                   │
│                                                      │
│  Collapsing:                                         │
│  - Same event type: "5 people liked your post"      │
│  - Same entity: "3 new messages in #general"        │
│  - collapse_key groups related notifications        │
└────────────────────────────────────────────────────┘
```

### 7.3 Provider Failover

```
Push Notification (APNs/FCM):
  Primary: Direct APNs HTTP/2 connection pool
  Fallback: FCM HTTP v1 API
  
  Error Handling:
  - Token expired (410): mark device inactive, stop sending
  - Rate limited (429): exponential backoff, retry after header
  - Server error (500): retry 3x with backoff
  - Invalid token: remove from device registry
  
Email:
  Primary: Amazon SES (cost-effective, high deliverability)
  Secondary: SendGrid (if SES fails or quota exceeded)
  Tertiary: Postmark (transactional only)
  
  Routing Logic:
  - Transactional: SES → Postmark (failover)
  - Marketing: SES → SendGrid (failover)
  - Bounce handling: webhook → mark email invalid
  - Complaint handling: auto-unsubscribe user

SMS:
  Primary: Twilio
  Secondary: Vonage/Nexmo
  Routing: by country (cheapest provider per destination)
```

## 8. Kafka & Async Processing

```
Topics:
  notifications.ingest        - 128 partitions, key=user_id
  notifications.push.pending  - 64 partitions, key=device_token_hash
  notifications.email.pending - 64 partitions, key=user_id  
  notifications.sms.pending   - 32 partitions, key=phone_hash
  notifications.inapp.pending - 32 partitions, key=user_id
  notifications.webhook       - 16 partitions, key=endpoint_hash
  notifications.dlq           - 8 partitions (dead letters)
  notifications.analytics     - 128 partitions, key=user_id

Consumer Groups:
  orchestrator-group     (ingest → preference check → route)
  push-sender-group      (push.pending → APNs/FCM delivery)
  email-sender-group     (email.pending → SES/SendGrid)
  sms-sender-group       (sms.pending → Twilio)
  analytics-group        (analytics → ClickHouse)
  dlq-processor-group    (dlq → retry or alert)

Flow:
  Producer → notifications.ingest (partitioned by user_id)
    → Orchestrator consumes, checks prefs, routes
    → Publishes to channel-specific topic
    → Channel sender consumes, delivers to provider
    → Publishes delivery event to analytics topic
```

## 9. Observability

```yaml
Metrics:
  notification_sent_total{channel, category, priority, status}
  notification_delivery_latency_seconds{channel, quantile}
  notification_provider_errors_total{provider, error_type}
  notification_rate_limited_total{user_bucket, category}
  notification_digest_size{category, quantile}
  notification_queue_depth{topic}
  notification_dlq_size{channel}
  
  # Business metrics
  notification_open_rate{category, channel}
  notification_click_rate{category, template}
  notification_unsubscribe_rate{category, channel}

Alerts:
  Critical:
  - Delivery success rate < 95% for any channel
  - Queue depth > 1M (processing falling behind)
  - Provider error rate > 10%
  
  Warning:
  - Delivery latency p99 > 60s for high priority
  - DLQ growing > 10K/hour
  - Unsubscribe rate spike (bad template?)
```

## 10. Considerations

### Key Trade-offs

| Choice | Benefit | Trade-off |
|---|---|---|
| Kafka over SQS | Replay, ordering, multiple consumers | Operational complexity |
| Cassandra for history | Write throughput, time-series | No complex queries |
| At-least-once delivery | No message loss | Need idempotency on consumer side |
| Async processing | Scalability, decoupling | Higher latency for non-critical |
| Provider abstraction | Failover, cost optimization | Additional routing complexity |

### Security
- Webhook signatures (HMAC-SHA256) for outbound webhooks
- Unsubscribe tokens (signed, one-time use)
- PII minimization in notification payloads
- Encryption in transit for all provider communication
- Audit log for who sent what notification to whom
