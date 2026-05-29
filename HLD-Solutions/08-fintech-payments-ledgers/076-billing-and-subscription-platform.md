# Billing & Subscription Platform (Stripe Billing) — System Design

## 1. Functional Requirements

1. **Subscription Plans**: Flat-rate, tiered, per-unit, metered pricing models
2. **Billing Cycles**: Monthly/annual/custom cycles with proration on changes
3. **Proration**: Fair charge/credit calculation on mid-cycle plan changes
4. **Usage Metering**: Ingest and aggregate usage events for metered billing
5. **Invoice Generation**: Automated invoice creation at cycle end with line items
6. **Payment Collection**: Charge stored payment methods with retry (dunning)
7. **Revenue Recognition**: ASC 606 compliant deferred/recognized revenue tracking
8. **Tax Calculation**: Integration with tax engines (Avalara/TaxJar)
9. **Subscription Lifecycle**: Trial → active → past_due → canceled states
10. **Dunning Management**: Smart retry + escalation for failed payments

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.99% |
| Invoice Accuracy | 100% (no billing errors) |
| Metering Throughput | 1M events/sec |
| Invoice Generation Latency | < 5 min from cycle end |
| Payment Collection | Within 1 hour of invoice finalization |
| Metering Deduplication | Exactly-once event processing |
| Scalability | 50M subscriptions, 10B usage events/day |
| Compliance | ASC 606, PCI-DSS, SOC 2 |

## 3. Capacity Estimation

```
Subscriptions: 50M active
Plans: 100K distinct pricing configurations
Monthly invoices: 50M (majority monthly billing)
Usage events: 10B/day (metered subscriptions)
Peak usage ingestion: 1M events/sec

Storage:
- Subscriptions: 50M × 2KB = 100GB
- Invoices: 50M/month × 5KB = 250GB/month = 3TB/year
- Usage events: 10B/day × 200B = 2TB/day = 730TB/year (compressed: ~100TB)
- Revenue recognition: 50M × 12 months × 100B = 60GB/year

Compute:
- Invoice generation batch: 50M invoices in 4 hours = 3,500 invoices/sec
- Usage aggregation: 1M events/sec continuous
- Payment collection: 50M attempts/month = ~20 charges/sec average
  Peak (first of month): 5M charges in 1 hour = 1,400/sec
```

## 4. Data Modeling — Full Schemas

```sql
-- Products & Pricing
CREATE TABLE products (
    product_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         UUID NOT NULL,
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE prices (
    price_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id          UUID NOT NULL REFERENCES products(product_id),
    currency            CHAR(3) NOT NULL,
    pricing_model       VARCHAR(20) NOT NULL,
    -- flat, per_unit, tiered, volume, graduated, metered
    billing_period      VARCHAR(10) NOT NULL,  -- month, year, week, custom
    billing_interval    INTEGER DEFAULT 1,  -- every N periods
    unit_amount         BIGINT,  -- for flat/per_unit (in cents)
    tiers               JSONB,  -- for tiered/volume pricing
    -- [{"up_to": 100, "unit_amount": 500}, {"up_to": null, "unit_amount": 300}]
    metering_aggregate  VARCHAR(10),  -- sum, max, last (for metered)
    trial_period_days   INTEGER DEFAULT 0,
    setup_fee           BIGINT DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_prices_product ON prices(product_id);

-- Customers
CREATE TABLE customers (
    customer_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         UUID NOT NULL,
    email               VARCHAR(255) NOT NULL,
    name                VARCHAR(200),
    default_payment_method_id UUID,
    tax_id              VARCHAR(50),
    tax_exempt          BOOLEAN DEFAULT FALSE,
    billing_address     JSONB,
    currency            CHAR(3) DEFAULT 'USD',
    balance             BIGINT DEFAULT 0,  -- credit balance
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_customers_merchant ON customers(merchant_id);
CREATE INDEX idx_customers_email ON customers(merchant_id, email);

-- Subscriptions
CREATE TABLE subscriptions (
    subscription_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID NOT NULL REFERENCES customers(customer_id),
    merchant_id         UUID NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'incomplete',
    -- incomplete, trialing, active, past_due, canceled, unpaid, paused
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end  TIMESTAMPTZ NOT NULL,
    trial_start         TIMESTAMPTZ,
    trial_end           TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    canceled_at         TIMESTAMPTZ,
    cancellation_reason VARCHAR(100),
    ended_at            TIMESTAMPTZ,
    collection_method   VARCHAR(20) DEFAULT 'charge_automatically',
    -- charge_automatically, send_invoice
    days_until_due      INTEGER DEFAULT 30,  -- for send_invoice
    default_payment_method_id UUID,
    latest_invoice_id   UUID,
    pending_setup_intent_id UUID,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_subs_customer ON subscriptions(customer_id);
CREATE INDEX idx_subs_status ON subscriptions(status, current_period_end);
CREATE INDEX idx_subs_renewal ON subscriptions(current_period_end)
    WHERE status IN ('active', 'trialing');

-- Subscription Items (line items within a subscription)
CREATE TABLE subscription_items (
    item_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id     UUID NOT NULL REFERENCES subscriptions(subscription_id),
    price_id            UUID NOT NULL REFERENCES prices(price_id),
    quantity            INTEGER DEFAULT 1,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sub_items ON subscription_items(subscription_id);

-- Usage Events (append-only, high-volume)
CREATE TABLE usage_events (
    event_id            UUID NOT NULL,
    subscription_item_id UUID NOT NULL,
    customer_id         UUID NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    quantity            BIGINT NOT NULL,
    action              VARCHAR(10) DEFAULT 'increment',  -- increment, set
    idempotency_key     VARCHAR(255) NOT NULL,
    properties          JSONB DEFAULT '{}',
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id, subscription_item_id, event_id)
);
-- Partitioned by day for efficient aggregation
-- CREATE TABLE usage_events (...) PARTITION BY RANGE (timestamp);
CREATE INDEX idx_usage_item_ts ON usage_events(subscription_item_id, timestamp);
CREATE UNIQUE INDEX idx_usage_idemp ON usage_events(subscription_item_id, idempotency_key);

-- Usage Aggregates (pre-computed by Flink)
CREATE TABLE usage_aggregates (
    aggregate_id        BIGSERIAL PRIMARY KEY,
    subscription_item_id UUID NOT NULL,
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    aggregate_type      VARCHAR(10) NOT NULL,  -- hourly, daily, billing_period
    total_usage         BIGINT NOT NULL,
    max_usage           BIGINT NOT NULL,
    event_count         INTEGER NOT NULL,
    last_event_at       TIMESTAMPTZ,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(subscription_item_id, period_start, aggregate_type)
);
CREATE INDEX idx_usage_agg_lookup ON usage_aggregates(
    subscription_item_id, aggregate_type, period_start);

-- Invoices
CREATE TABLE invoices (
    invoice_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number      VARCHAR(50) NOT NULL UNIQUE,
    customer_id         UUID NOT NULL,
    subscription_id     UUID,
    merchant_id         UUID NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft, open, paid, void, uncollectible
    currency            CHAR(3) NOT NULL,
    subtotal            BIGINT NOT NULL DEFAULT 0,
    tax_amount          BIGINT NOT NULL DEFAULT 0,
    discount_amount     BIGINT NOT NULL DEFAULT 0,
    total               BIGINT NOT NULL DEFAULT 0,
    amount_due          BIGINT NOT NULL DEFAULT 0,
    amount_paid         BIGINT NOT NULL DEFAULT 0,
    amount_remaining    BIGINT NOT NULL DEFAULT 0,
    billing_reason      VARCHAR(30),
    -- subscription_cycle, subscription_create, subscription_update, manual
    period_start        TIMESTAMPTZ,
    period_end          TIMESTAMPTZ,
    due_date            DATE,
    paid_at             TIMESTAMPTZ,
    voided_at           TIMESTAMPTZ,
    payment_intent_id   UUID,
    attempt_count       SMALLINT DEFAULT 0,
    next_payment_attempt TIMESTAMPTZ,
    hosted_invoice_url  VARCHAR(500),
    pdf_url             VARCHAR(500),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at        TIMESTAMPTZ
);
CREATE INDEX idx_invoices_customer ON invoices(customer_id, created_at DESC);
CREATE INDEX idx_invoices_status ON invoices(status, next_payment_attempt)
    WHERE status IN ('open');
CREATE INDEX idx_invoices_sub ON invoices(subscription_id, created_at DESC);

-- Invoice Line Items
CREATE TABLE invoice_line_items (
    line_item_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id          UUID NOT NULL REFERENCES invoices(invoice_id),
    subscription_item_id UUID,
    price_id            UUID,
    description         TEXT NOT NULL,
    quantity            BIGINT NOT NULL,
    unit_amount         BIGINT NOT NULL,
    amount              BIGINT NOT NULL,  -- quantity × unit_amount
    currency            CHAR(3) NOT NULL,
    period_start        TIMESTAMPTZ,
    period_end          TIMESTAMPTZ,
    proration           BOOLEAN DEFAULT FALSE,
    type                VARCHAR(20) NOT NULL,  -- subscription, invoiceitem, proration
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_line_items_invoice ON invoice_line_items(invoice_id);

-- Dunning (payment retry management)
CREATE TABLE dunning_schedules (
    schedule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         UUID NOT NULL,
    name                VARCHAR(100) NOT NULL,
    retry_attempts      JSONB NOT NULL,
    -- [{"day": 1, "time": "09:00"}, {"day": 3, "time": "14:00"}, ...]
    escalation_actions  JSONB NOT NULL,
    -- [{"day": 7, "action": "email"}, {"day": 14, "action": "sms"},
    --  {"day": 30, "action": "cancel"}]
    is_default          BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE dunning_attempts (
    attempt_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id          UUID NOT NULL REFERENCES invoices(invoice_id),
    subscription_id     UUID NOT NULL,
    attempt_number      SMALLINT NOT NULL,
    scheduled_at        TIMESTAMPTZ NOT NULL,
    attempted_at        TIMESTAMPTZ,
    status              VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    -- scheduled, attempted, succeeded, failed
    payment_intent_id   UUID,
    failure_code        VARCHAR(50),
    failure_message     TEXT,
    card_type           VARCHAR(20),
    next_attempt_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_dunning_scheduled ON dunning_attempts(status, scheduled_at)
    WHERE status = 'scheduled';

-- Revenue Recognition (ASC 606)
CREATE TABLE revenue_schedules (
    schedule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_line_item_id UUID NOT NULL,
    invoice_id          UUID NOT NULL,
    customer_id         UUID NOT NULL,
    total_amount        BIGINT NOT NULL,
    recognized_amount   BIGINT NOT NULL DEFAULT 0,
    deferred_amount     BIGINT NOT NULL,
    recognition_start   DATE NOT NULL,
    recognition_end     DATE NOT NULL,
    recognition_method  VARCHAR(20) NOT NULL,  -- straight_line, usage_based
    currency            CHAR(3) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_rev_schedule_period ON revenue_schedules(recognition_start, recognition_end);

CREATE TABLE revenue_entries (
    entry_id            BIGSERIAL PRIMARY KEY,
    schedule_id         UUID NOT NULL REFERENCES revenue_schedules(schedule_id),
    period              DATE NOT NULL,  -- month
    amount              BIGINT NOT NULL,
    entry_type          VARCHAR(20) NOT NULL,  -- recognized, deferred
    journal_entry_ref   VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(schedule_id, period, entry_type)
);
CREATE INDEX idx_rev_entries_period ON revenue_entries(period);

-- Proration Events
CREATE TABLE proration_events (
    proration_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id     UUID NOT NULL,
    change_type         VARCHAR(20) NOT NULL,  -- upgrade, downgrade, quantity_change
    old_price_id        UUID,
    new_price_id        UUID,
    old_quantity        INTEGER,
    new_quantity        INTEGER,
    proration_date      TIMESTAMPTZ NOT NULL,
    credit_amount       BIGINT NOT NULL DEFAULT 0,  -- unused time on old plan
    debit_amount        BIGINT NOT NULL DEFAULT 0,  -- remaining time on new plan
    net_amount          BIGINT NOT NULL,  -- debit - credit
    applied_to_invoice  UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_proration_sub ON proration_events(subscription_id);
```

## 5. High-Level Design — ASCII Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 BILLING & SUBSCRIPTION PLATFORM                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌───────────┐
  │ Merchant │   │ Customer │   │ Usage Events │   │  Webhooks │
  │ Dashboard│   │ Portal   │   │ (SDKs/APIs)  │   │ (inbound) │
  └────┬─────┘   └────┬─────┘   └──────┬───────┘   └─────┬─────┘
       │               │                │                  │
       └───────────────┼────────────────┼──────────────────┘
                       │
                       ▼
          ┌──────────────────────────────┐
          │       API Gateway            │
          └──────────────┬───────────────┘
                         │
    ┌────────────────────┼──────────────────────────────────┐
    │                    │                                   │
    ▼                    ▼                                   ▼
┌───────────┐    ┌──────────────┐              ┌────────────────────┐
│Subscription│    │   Usage      │              │    Invoice         │
│  Service   │    │   Metering   │              │    Service         │
│            │    │   Service    │              │                    │
│ Lifecycle, │    │              │              │ Generate, Finalize │
│ Plan Change│    │ Ingest,      │              │ PDF, Send          │
│ Proration  │    │ Deduplicate  │              │                    │
└──────┬─────┘    └──────┬───────┘              └────────┬───────────┘
       │                  │                              │
       │                  ▼                              │
       │         ┌──────────────────┐                   │
       │         │      Kafka       │                   │
       │         │ (Usage Events)   │                   │
       │         └────────┬─────────┘                   │
       │                  │                              │
       │                  ▼                              │
       │         ┌──────────────────┐                   │
       │         │   Flink          │                   │
       │         │ (Aggregation +   │                   │
       │         │  Deduplication)  │                   │
       │         └────────┬─────────┘                   │
       │                  │                              │
       │                  ▼                              │
       │         ┌──────────────────┐                   │
       │         │  Usage Aggregate │                   │
       │         │  Store (PG +     │                   │
       │         │  TimescaleDB)    │                   │
       │         └──────────────────┘                   │
       │                                                │
       ▼                                                ▼
┌──────────────────────────────────────────────────────────────┐
│                    Billing Engine (Core)                       │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Clock/Scheduler│  │  Proration   │  │  Tax Calculator  │  │
│  │ (cycle end    │  │  Engine      │  │  (Avalara)       │  │
│  │  detection)   │  │              │  │                  │  │
│  └───────────────┘  └──────────────┘  └──────────────────┘  │
└────────────────────────────┬─────────────────────────────────┘
                             │
                ┌────────────┼────────────────┐
                │            │                │
                ▼            ▼                ▼
       ┌──────────────┐ ┌──────────┐ ┌──────────────────┐
       │  Payment     │ │ Dunning  │ │ Revenue          │
       │  Collection  │ │ Manager  │ │ Recognition      │
       │  (Stripe/PSP)│ │ (Retry)  │ │ (ASC 606)        │
       └──────────────┘ └──────────┘ └──────────────────┘
                │            │
                ▼            ▼
       ┌──────────────────────────┐
       │     Notification         │
       │  (Email/SMS/Webhook)     │
       └──────────────────────────┘
```

## 6. Low-Level Design — APIs

### Create Subscription
```http
POST /v1/subscriptions
Authorization: Bearer sk_live_xxx

{
  "customer": "cus_abc123",
  "items": [
    {"price": "price_pro_monthly", "quantity": 5},
    {"price": "price_metered_api_calls"}
  ],
  "default_payment_method": "pm_card_visa",
  "trial_period_days": 14,
  "proration_behavior": "create_prorations",
  "collection_method": "charge_automatically"
}
```

**Response:**
```json
{
  "id": "sub_xyz789",
  "status": "trialing",
  "current_period_start": "2024-01-15T00:00:00Z",
  "current_period_end": "2024-02-15T00:00:00Z",
  "trial_start": "2024-01-15T00:00:00Z",
  "trial_end": "2024-01-29T00:00:00Z",
  "items": {
    "data": [
      {
        "id": "si_item1",
        "price": {"id": "price_pro_monthly", "unit_amount": 4900},
        "quantity": 5
      },
      {
        "id": "si_item2",
        "price": {"id": "price_metered_api_calls", "unit_amount": 1}
      }
    ]
  },
  "latest_invoice": null
}
```

### Report Usage
```http
POST /v1/usage_records
Authorization: Bearer sk_live_xxx
Idempotency-Key: usage_20240115_hour14_cus_abc

{
  "subscription_item": "si_item2",
  "quantity": 15000,
  "timestamp": 1705312800,
  "action": "increment"
}
```

### Update Subscription (Upgrade with Proration)
```http
PATCH /v1/subscriptions/sub_xyz789
Authorization: Bearer sk_live_xxx

{
  "items": [
    {"id": "si_item1", "price": "price_enterprise_monthly", "quantity": 10}
  ],
  "proration_behavior": "create_prorations",
  "payment_behavior": "pending_if_incomplete"
}
```

**Response:**
```json
{
  "id": "sub_xyz789",
  "status": "active",
  "items": {
    "data": [{
      "id": "si_item1",
      "price": {"id": "price_enterprise_monthly", "unit_amount": 9900},
      "quantity": 10
    }]
  },
  "pending_invoice_item_interval": null,
  "proration_details": {
    "credit": -12250,
    "debit": 49500,
    "net": 37250,
    "description": "Upgrade from Pro ($49) to Enterprise ($99), 15 days remaining"
  }
}
```

### Invoice Object
```json
{
  "id": "inv_abc123",
  "invoice_number": "INV-2024-001234",
  "status": "open",
  "customer": "cus_abc123",
  "subscription": "sub_xyz789",
  "period_start": "2024-01-15T00:00:00Z",
  "period_end": "2024-02-15T00:00:00Z",
  "lines": {
    "data": [
      {
        "description": "Enterprise Plan (10 seats)",
        "quantity": 10,
        "unit_amount": 9900,
        "amount": 99000,
        "period": {"start": "2024-01-15", "end": "2024-02-15"}
      },
      {
        "description": "API Calls (142,500 calls)",
        "quantity": 142500,
        "unit_amount": 1,
        "amount": 14250,
        "period": {"start": "2024-01-15", "end": "2024-02-15"}
      }
    ]
  },
  "subtotal": 113250,
  "tax": 9060,
  "total": 122310,
  "amount_due": 122310
}
```

## 7. Deep Dives

### Deep Dive 1: Usage Metering at Scale

**Problem**: Ingest 1M events/sec, deduplicate, aggregate into billing-period buckets, handle late-arriving events.

**Architecture**:
```
┌──────────────────────────────────────────────────────────────┐
│                USAGE METERING PIPELINE                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  SDK/API ──▶ ┌──────────────┐                               │
│              │ Ingestion    │                                │
│  1M events/ │ Gateway      │                                │
│  sec        │ (validation, │                                │
│              │  rate limit) │                                │
│              └──────┬───────┘                                │
│                     │                                        │
│                     ▼                                        │
│              ┌──────────────┐                                │
│              │    Kafka     │  Partitioned by                │
│              │  (raw usage) │  subscription_item_id          │
│              │  256 parts   │  (ordering guarantee)          │
│              └──────┬───────┘                                │
│                     │                                        │
│                     ▼                                        │
│              ┌──────────────────────────────────────────┐    │
│              │         Flink Streaming Job               │    │
│              │                                          │    │
│              │  1. Deduplication (idempotency_key)      │    │
│              │     └── Bloom filter + RocksDB state     │    │
│              │                                          │    │
│              │  2. Aggregation Windows                  │    │
│              │     ├── 1-hour tumbling (billing bucket) │    │
│              │     └── Billing-period session window    │    │
│              │                                          │    │
│              │  3. Late Event Handling                  │    │
│              │     └── Allowed lateness: 24 hours       │    │
│              │         Side output for very late events │    │
│              └──────────────┬───────────────────────────┘    │
│                             │                                │
│              ┌──────────────┼──────────────┐                 │
│              │              │              │                  │
│              ▼              ▼              ▼                  │
│       ┌──────────┐  ┌──────────┐   ┌──────────────┐        │
│       │  Hourly  │  │  Daily   │   │  Billing     │        │
│       │  Buckets │  │  Rollup  │   │  Period Agg  │        │
│       │  (PG)    │  │          │   │  (for invoice)│        │
│       └──────────┘  └──────────┘   └──────────────┘        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Flink Deduplication + Aggregation**:
```python
class UsageMeteringJob:
    """
    Flink streaming job for usage event processing.
    Guarantees exactly-once semantics via Kafka transactions + Flink checkpoints.
    """

    def build(self, env):
        # Source
        usage_stream = env.add_source(
            KafkaSource.builder()
            .set_topics("usage.raw")
            .set_group_id("usage-metering")
            .build()
        ).assign_timestamps_and_watermarks(
            WatermarkStrategy
            .for_bounded_out_of_orderness(Duration.of_hours(24))
            .with_timestamp_assigner(lambda e, _: e['timestamp'])
        )

        # Step 1: Deduplicate by idempotency_key
        deduped = usage_stream \
            .key_by(lambda e: f"{e['subscription_item_id']}:{e['idempotency_key']}") \
            .process(DeduplicationFunction())

        # Step 2: Aggregate into hourly buckets
        hourly = deduped \
            .key_by(lambda e: e['subscription_item_id']) \
            .window(TumblingEventTimeWindows.of(Time.hours(1))) \
            .allowed_lateness(Time.hours(24)) \
            .aggregate(UsageAggregator())

        # Step 3: Sink to database
        hourly.add_sink(PostgresSink("usage_aggregates"))

        # Step 4: Side output for late events (> 24h)
        late_events = deduped.get_side_output(LATE_OUTPUT_TAG)
        late_events.add_sink(KafkaSink("usage.late"))


class DeduplicationFunction(KeyedProcessFunction):
    """Bloom filter + state for efficient deduplication."""

    def __init__(self):
        self.seen_keys = None  # MapState

    def open(self, config):
        self.seen_keys = self.get_runtime_context().get_map_state(
            MapStateDescriptor("seen_keys", Types.STRING(), Types.LONG())
        )

    def process_element(self, event, ctx):
        key = event['idempotency_key']
        if self.seen_keys.contains(key):
            return  # Duplicate, skip

        self.seen_keys.put(key, ctx.timestamp())
        yield event

        # Register timer to clean up old keys (memory management)
        ctx.timer_service().register_event_time_timer(
            ctx.timestamp() + 86400000  # 24h retention
        )

    def on_timer(self, timestamp, ctx):
        # Clean expired dedup keys
        to_remove = []
        for key, ts in self.seen_keys.items():
            if ts < timestamp - 86400000:
                to_remove.append(key)
        for key in to_remove:
            self.seen_keys.remove(key)


class UsageAggregator:
    """Aggregates usage within hourly window."""

    def create_accumulator(self):
        return {'sum': 0, 'max': 0, 'count': 0, 'last_value': 0}

    def add(self, acc, event):
        if event['action'] == 'increment':
            acc['sum'] += event['quantity']
        elif event['action'] == 'set':
            acc['last_value'] = event['quantity']
        acc['max'] = max(acc['max'], event['quantity'])
        acc['count'] += 1
        return acc

    def get_result(self, acc):
        return {
            'total_usage': acc['sum'],
            'max_usage': acc['max'],
            'event_count': acc['count'],
            'last_value': acc['last_value']
        }
```

### Deep Dive 2: Dunning Management — Smart Retry

**Problem**: Failed payments must be retried intelligently. Retry too early = same decline. Too late = customer churns.

**Architecture**:
```python
class DunningManager:
    """
    Smart retry engine that optimizes retry timing based on:
    - Card type (debit cards: retry on payday; credit cards: retry after statement)
    - Bank patterns (some banks have maintenance windows)
    - Historical success rates by day/hour
    - ML model for optimal retry timing
    """

    # Default retry schedule
    DEFAULT_SCHEDULE = [
        {'attempt': 1, 'delay_hours': 0},       # Immediate
        {'attempt': 2, 'delay_hours': 24},      # +1 day
        {'attempt': 3, 'delay_hours': 72},      # +3 days
        {'attempt': 4, 'delay_hours': 168},     # +7 days
        {'attempt': 5, 'delay_hours': 336},     # +14 days
    ]

    # Escalation actions
    ESCALATION_SEQUENCE = [
        {'day': 1, 'action': 'email_payment_failed'},
        {'day': 3, 'action': 'email_update_payment'},
        {'day': 7, 'action': 'sms_payment_reminder'},
        {'day': 14, 'action': 'email_final_warning'},
        {'day': 30, 'action': 'cancel_subscription'},
    ]

    async def handle_payment_failure(self, invoice_id: str, failure_code: str):
        """Called when a payment attempt fails."""
        invoice = await self.get_invoice(invoice_id)
        subscription = await self.get_subscription(invoice.subscription_id)

        # Update subscription status
        if subscription.status == 'active':
            await self.update_subscription_status(subscription.id, 'past_due')

        # Determine if retryable
        if not self._is_retryable(failure_code):
            # Hard decline (stolen card, closed account) — don't retry
            await self._escalate_immediately(invoice, subscription)
            return

        # Calculate optimal next retry time
        next_retry = await self._calculate_optimal_retry_time(
            invoice, subscription, failure_code
        )

        # Schedule retry
        await self.db.execute("""
            INSERT INTO dunning_attempts
                (invoice_id, subscription_id, attempt_number, scheduled_at, status)
            VALUES ($1, $2, $3, $4, 'scheduled')
        """, invoice_id, subscription.id,
            invoice.attempt_count + 1, next_retry)

        # Schedule escalation actions
        await self._schedule_escalations(invoice, subscription)

    async def _calculate_optimal_retry_time(self, invoice, subscription, failure_code):
        """ML-optimized retry timing."""
        # Features for retry timing model
        features = {
            'card_type': await self._get_card_type(subscription),
            'failure_code': failure_code,
            'attempt_number': invoice.attempt_count,
            'day_of_week': datetime.now().weekday(),
            'hour_of_day': datetime.now().hour,
            'amount': invoice.amount_due,
            'customer_tenure_days': await self._get_tenure(subscription.customer_id),
            'previous_success_day': await self._get_typical_success_day(subscription),
        }

        # ML model predicts optimal hour to retry
        optimal_hour = self.retry_model.predict(features)

        # Combine with schedule constraints
        base_delay = self.DEFAULT_SCHEDULE[
            min(invoice.attempt_count, len(self.DEFAULT_SCHEDULE) - 1)
        ]['delay_hours']

        next_retry = datetime.utcnow() + timedelta(hours=base_delay)

        # Adjust to optimal hour
        next_retry = next_retry.replace(hour=optimal_hour, minute=0)

        # Smart adjustments
        if features['card_type'] == 'debit':
            # Retry on typical payday (1st, 15th)
            next_retry = self._align_to_payday(next_retry)

        return next_retry

    def _is_retryable(self, failure_code: str) -> bool:
        """Determine if failure is transient (retry) or permanent (stop)."""
        non_retryable = {
            'card_stolen', 'card_lost', 'account_closed',
            'invalid_account', 'do_not_honor_permanent'
        }
        return failure_code not in non_retryable

    async def execute_retry(self, attempt_id: str):
        """Execute a scheduled retry attempt."""
        attempt = await self.get_attempt(attempt_id)
        invoice = await self.get_invoice(attempt.invoice_id)

        # Charge payment method
        result = await self.payment_service.charge(
            amount=invoice.amount_due,
            currency=invoice.currency,
            payment_method=invoice.payment_method_id,
            idempotency_key=f"dunning_{attempt_id}"
        )

        if result.success:
            # Payment succeeded!
            await self._mark_invoice_paid(invoice)
            await self._restore_subscription(invoice.subscription_id)
            await self._send_notification(invoice, 'payment_succeeded')
        else:
            await self._record_failure(attempt, result.failure_code)
            # Will trigger handle_payment_failure again
```

### Deep Dive 3: Revenue Recognition (ASC 606)

**Problem**: Revenue must be recognized when service is delivered, not when payment is received. Annual subscriptions paid upfront must spread revenue over 12 months.

```python
class RevenueRecognitionEngine:
    """
    ASC 606 compliant revenue recognition.

    5-Step Model:
    1. Identify contract (subscription)
    2. Identify performance obligations (monthly service)
    3. Determine transaction price (subscription amount)
    4. Allocate price to performance obligations (straight-line for SaaS)
    5. Recognize revenue when obligation satisfied (monthly)
    """

    async def create_recognition_schedule(self, invoice_line_item):
        """
        Create a revenue recognition schedule for an invoice line item.
        Annual subscription: spread over 12 months.
        Monthly: recognize immediately.
        """
        price = await self.get_price(invoice_line_item.price_id)
        period_months = self._get_period_months(price.billing_period, price.billing_interval)

        if period_months <= 1:
            # Monthly billing: recognize immediately
            schedule = await self.db.fetchone("""
                INSERT INTO revenue_schedules
                    (invoice_line_item_id, invoice_id, customer_id,
                     total_amount, deferred_amount, recognized_amount,
                     recognition_start, recognition_end, recognition_method, currency)
                VALUES ($1, $2, $3, $4, $4, 0, $5, $5, 'immediate', $6)
                RETURNING *
            """, invoice_line_item.id, invoice_line_item.invoice_id,
                invoice_line_item.customer_id, invoice_line_item.amount,
                invoice_line_item.period_start, invoice_line_item.currency)

            # Immediately recognize
            await self._recognize_revenue(schedule.schedule_id,
                                         invoice_line_item.period_start.date(),
                                         invoice_line_item.amount)
        else:
            # Multi-period: straight-line recognition
            monthly_amount = invoice_line_item.amount // period_months
            remainder = invoice_line_item.amount - (monthly_amount * period_months)

            schedule = await self.db.fetchone("""
                INSERT INTO revenue_schedules
                    (invoice_line_item_id, invoice_id, customer_id,
                     total_amount, deferred_amount, recognized_amount,
                     recognition_start, recognition_end, recognition_method, currency)
                VALUES ($1, $2, $3, $4, $4, 0, $5, $6, 'straight_line', $7)
                RETURNING *
            """, invoice_line_item.id, invoice_line_item.invoice_id,
                invoice_line_item.customer_id, invoice_line_item.amount,
                invoice_line_item.period_start, invoice_line_item.period_end,
                invoice_line_item.currency)

            # Create monthly entries
            current_date = invoice_line_item.period_start.date().replace(day=1)
            for month in range(period_months):
                amount = monthly_amount
                if month == period_months - 1:
                    amount += remainder  # Last month gets remainder

                await self.db.execute("""
                    INSERT INTO revenue_entries
                        (schedule_id, period, amount, entry_type)
                    VALUES ($1, $2, $3, 'recognized')
                """, schedule.schedule_id, current_date, amount)

                # Corresponding deferred entry (initially all deferred)
                if month > 0:
                    await self.db.execute("""
                        INSERT INTO revenue_entries
                            (schedule_id, period, amount, entry_type)
                        VALUES ($1, $2, $3, 'deferred')
                    """, schedule.schedule_id, current_date, -amount)

                current_date = self._add_months(current_date, 1)

    async def run_monthly_recognition(self, period: date):
        """
        Monthly batch: recognize revenue for the current period.
        Moves amounts from deferred to recognized.
        """
        schedules = await self.db.fetch("""
            SELECT rs.* FROM revenue_schedules rs
            WHERE rs.recognition_start <= $1
            AND rs.recognition_end > $1
            AND rs.deferred_amount > 0
        """, period)

        for schedule in schedules:
            entry = await self.db.fetchone("""
                SELECT amount FROM revenue_entries
                WHERE schedule_id = $1 AND period = $2 AND entry_type = 'recognized'
            """, schedule.schedule_id, period)

            if entry:
                # Update schedule totals
                await self.db.execute("""
                    UPDATE revenue_schedules
                    SET recognized_amount = recognized_amount + $2,
                        deferred_amount = deferred_amount - $2
                    WHERE schedule_id = $1
                """, schedule.schedule_id, entry.amount)

                # Create journal entries
                await self.ledger.post_journal({
                    'description': f"Revenue recognition for period {period}",
                    'entries': [
                        {'account': 'deferred_revenue', 'type': 'D', 'amount': entry.amount},
                        {'account': 'recognized_revenue', 'type': 'C', 'amount': entry.amount},
                    ]
                })

    async def handle_cancellation(self, subscription_id: str, cancel_date: date):
        """
        On cancellation, recognize remaining deferred revenue immediately
        (or write off, depending on refund policy).
        """
        pending_schedules = await self.db.fetch("""
            SELECT * FROM revenue_schedules
            WHERE customer_id = (
                SELECT customer_id FROM subscriptions WHERE subscription_id = $1
            )
            AND deferred_amount > 0
        """, subscription_id)

        for schedule in pending_schedules:
            if schedule.deferred_amount > 0:
                # If refunding: write off deferred
                # If not refunding: accelerate recognition
                await self.db.execute("""
                    UPDATE revenue_schedules
                    SET recognized_amount = total_amount,
                        deferred_amount = 0,
                        recognition_end = $2
                    WHERE schedule_id = $1
                """, schedule.schedule_id, cancel_date)
```

## 8. Component Optimization

### Kafka Configuration
```yaml
kafka:
  topics:
    usage.raw:
      partitions: 256  # high throughput, partition by subscription_item_id
      replication_factor: 3
      retention_ms: 259200000  # 3 days
      min.insync.replicas: 2
    usage.aggregated:
      partitions: 64
      replication_factor: 3
      retention_ms: 2592000000  # 30 days
    billing.events:
      partitions: 32
      replication_factor: 3
      retention_ms: 604800000  # 7 days
    subscription.lifecycle:
      partitions: 32
      replication_factor: 3
  producer:
    acks: all  # critical for billing accuracy
    enable.idempotence: true
    max.in.flight.requests.per.connection: 5
    compression.type: lz4
  consumer:
    usage_metering:
      group_id: usage-flink
      auto.offset.reset: earliest
      enable.auto.commit: false
```

### Redis Configuration
```yaml
redis:
  cluster:
    nodes: 6
    max_memory: 32GB per node
  use_cases:
    subscription_cache:
      pattern: "sub:{subscription_id}"
      ttl: 3600
    usage_counters:
      pattern: "usage:{subscription_item_id}:{period}"
      type: hash  # {total, max, count, last_event_at}
      ttl: auto (matches billing period + 7 days buffer)
    dunning_schedule:
      pattern: "dunning:{invoice_id}"
      type: sorted_set  # score=retry_timestamp
    rate_limiting:
      pattern: "rl:usage:{customer_id}"
      limit: 10000/sec per customer
    idempotency:
      pattern: "idemp:usage:{key}"
      ttl: 86400  # 1 day
```

### Flink Configuration
```yaml
flink:
  cluster:
    job_manager_memory: 8GB
    task_manager_memory: 16GB
    task_managers: 16
    slots_per_tm: 8
    total_parallelism: 128
  jobs:
    usage_metering:
      parallelism: 64
      checkpointing:
        interval: 30s
        mode: exactly_once
        min_pause: 10s
      state_backend: rocksdb
      incremental_checkpoints: true
      state_ttl: 86400s  # 1 day for dedup state
    usage_rollup:
      parallelism: 16
      trigger: processing_time (every 1 hour)
```

### Database Optimization
```sql
-- Partition usage_events by day
CREATE TABLE usage_events (...) PARTITION BY RANGE (timestamp);
-- Auto-create daily partitions
-- Drop partitions older than billing period + 30 days buffer

-- Partition invoices by month
CREATE TABLE invoices (...) PARTITION BY RANGE (created_at);

-- Materialized view for subscription renewal detection
CREATE MATERIALIZED VIEW subscriptions_due_for_renewal AS
SELECT subscription_id, customer_id, current_period_end
FROM subscriptions
WHERE status IN ('active', 'trialing')
AND current_period_end <= NOW() + INTERVAL '1 hour'
WITH DATA;
-- Refresh every 5 minutes
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  billing:
    - invoices_generated_total{billing_reason}
    - invoice_amount_total{currency}
    - payment_collection_total{status}  # succeeded, failed
    - mrr_total{currency}  # Monthly Recurring Revenue
    - arr_total{currency}  # Annual Recurring Revenue
    - churn_rate_monthly

  usage_metering:
    - usage_events_ingested_total
    - usage_events_deduplicated_total
    - usage_aggregation_latency_ms
    - late_events_total{lateness_bucket}  # 1h, 6h, 24h, >24h
    - flink_checkpoint_duration_ms

  dunning:
    - dunning_attempts_total{attempt_number,status}
    - dunning_recovery_rate  # % of past_due recovered
    - time_to_recovery_hours  # histogram
    - voluntary_churn_rate vs involuntary_churn_rate
    - subscription_status_total{status}

  revenue:
    - recognized_revenue_total{period,currency}
    - deferred_revenue_total{currency}
    - revenue_recognition_lag_hours

alerts:
  - alert: InvoiceGenerationDelay
    expr: time() - max(invoice_generated_timestamp) > 3600
    for: 15m
  - alert: HighPaymentFailureRate
    expr: rate(payment_collection_total{status="failed"}[1h]) /
          rate(payment_collection_total[1h]) > 0.15
    for: 30m
  - alert: UsagePipelineLag
    expr: flink_consumer_lag > 1000000  # 1M events behind
    for: 5m
  - alert: RevenueRecognitionMismatch
    expr: abs(recognized + deferred - total_billed) > 100
    for: 0m  # accounting must balance
```

### Trace: Invoice Generation
```
Trace: Monthly Invoice Generation for sub_xyz789
├── scheduler.detect-cycle-end (1ms)
├── subscription-service.get-details (5ms)
├── usage-service.get-period-aggregates (15ms)
│   ├── pg.query-usage-aggregates (10ms)
│   └── compute-tiered-pricing (5ms)
├── proration-service.get-pending (3ms)
├── tax-service.calculate (50ms)
│   └── avalara.api-call (45ms)
├── invoice-service.generate (20ms)
│   ├── create-line-items (5ms)
│   ├── apply-discounts (2ms)
│   ├── finalize-totals (3ms)
│   └── generate-pdf (10ms)
├── revenue-service.create-schedule (8ms)
├── payment-service.charge (1500ms)
│   └── psp.authorize (1400ms)
├── webhook-service.deliver (5ms)
└── total: ~1.6s
```

## 10. Considerations

### Proration Logic
```python
def calculate_proration(old_price, new_price, change_date,
                       period_start, period_end):
    """
    Calculate proration for mid-cycle plan change.
    Credit unused time on old plan, charge remaining time on new plan.
    """
    total_days = (period_end - period_start).days
    remaining_days = (period_end - change_date).days
    used_days = total_days - remaining_days

    # Credit for unused time on old plan
    daily_rate_old = old_price / total_days
    credit = int(daily_rate_old * remaining_days)

    # Charge for remaining time on new plan
    daily_rate_new = new_price / total_days
    debit = int(daily_rate_new * remaining_days)

    return {'credit': credit, 'debit': debit, 'net': debit - credit}
```

### Billing Clock Accuracy
- Use **database timestamps** as source of truth (not application clock)
- **Billing scheduler** runs every 5 minutes, picks up subscriptions where `current_period_end <= NOW()`
- **Idempotent**: Multiple runs for same subscription produce same invoice
- **Timezone handling**: Bill in customer's timezone for statement clarity

### Failure Modes
| Failure | Impact | Mitigation |
|---------|--------|------------|
| Usage pipeline lag | Metered billing delayed | Alert + extend billing window |
| Payment gateway down | Collection fails | Queue + retry when available |
| Tax service timeout | Invoice blocked | Fallback to estimated tax |
| Flink checkpoint failure | Duplicate events possible | Idempotency keys handle it |
| Database failover | Brief delay | Synchronous replica, < 30s RTO |

### Scaling Strategy
- **Usage ingestion**: Kafka partitioned by subscription_item_id (ordered per item)
- **Invoice generation**: Parallelized batch (shard by customer_id hash)
- **Payment collection**: Rate-limited to PSP capacity, spread over hours
- **Database**: Shard by merchant_id (multi-tenant isolation)
- **Flink**: Horizontal scaling by adding task managers
