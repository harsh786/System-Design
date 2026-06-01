# 01 — Architecture Overview

> High-level system design of the Plural Platform V3 Subscription Gateway

---

## System Context Diagram

```mermaid
graph TB
    subgraph External Actors
        MERCHANT[Merchant Server]
        CHECKOUT[Checkout UI / SDK]
        ADMIN[Admin Dashboard]
        CUSTOMER[End Customer]
        SCHEDULER[Billing Scheduler<br/>pg_cron + K8s CronJob]
    end

    subgraph API Gateway Layer
        KONG[Kong API Gateway<br/>External Traffic]
        NGINX[nginx-internal<br/>Service-to-Service]
    end

    subgraph Subscription Platform Core
        SUB_GW[nxt-subscription-gateway-service<br/>Subscription Core]
        SUB_SCHED[nxt-subscription-scheduler-service<br/>Billing & Retry Orchestrator]
        MANDATE_SVC[nxt-mandate-management-service<br/>Mandate Lifecycle]
        SUB_ANALYTICS[nxt-subscription-analytics-service<br/>MRR & Churn Metrics]
    end

    subgraph Existing Platform Services
        OMS[nxt_payment_order_service<br/>Order Management System]
        OHS[nxt_order_history_service<br/>Read Projection]
        WEBHOOK[webhook-service<br/>Merchant Notifications]
        POS[payment-option-service<br/>Available Methods]
        OFFER[nxt-offer-service<br/>Offer Evaluation]
        FX[repo-fx-rate-service<br/>FX Rates]
        MERCH_SVC[Plural_MerchantServicev21<br/>Merchant Config]
        SETTLE[nxt-settlement<br/>Settlement Engine]
    end

    subgraph Payment Gateways
        CARD_GW[Card Gateway<br/>Plural_CardGatewayServicev21]
        UPI_GW[UPI Gateway<br/>UPI Autopay Mandates]
        NACH_GW[eNACH Gateway<br/>NACH Mandates]
        WALLET_GW[Wallet Gateway]
    end

    subgraph Customer Vault
        VAULT[nxt-customer-vault-mgm-service<br/>Tokenization & Card Storage]
    end

    subgraph Data Infrastructure
        PG[(PostgreSQL Aurora<br/>Subscription DB)]
        REDIS[(Redis ElastiCache<br/>Locks + Cache + Rate Limit)]
        KAFKA[Apache Kafka<br/>MSK]
        DEBEZIUM[Debezium CDC<br/>Connector]
        OPENSEARCH[(OpenSearch<br/>Subscription History)]
        SQS[AWS SQS<br/>Dunning Pipeline]
        S3[(AWS S3<br/>Invoice Storage)]
    end

    MERCHANT --> KONG
    CHECKOUT --> KONG
    ADMIN --> KONG
    CUSTOMER --> CHECKOUT
    KONG --> SUB_GW
    KONG --> SUB_ANALYTICS

    SCHEDULER --> NGINX --> SUB_SCHED

    SUB_GW --> PG
    SUB_GW --> REDIS
    SUB_GW --> MANDATE_SVC
    SUB_GW --> OMS
    SUB_GW --> MERCH_SVC
    SUB_GW --> OFFER
    SUB_GW --> FX
    SUB_GW --> VAULT
    SUB_GW --> POS

    SUB_SCHED --> SUB_GW
    SUB_SCHED --> SQS
    SUB_SCHED --> KAFKA
    SUB_SCHED --> REDIS

    MANDATE_SVC --> UPI_GW
    MANDATE_SVC --> NACH_GW
    MANDATE_SVC --> CARD_GW
    MANDATE_SVC --> VAULT

    SUB_GW --> OMS
    OMS --> CARD_GW
    OMS --> UPI_GW
    OMS --> WALLET_GW

    SUB_ANALYTICS --> OPENSEARCH
    SUB_ANALYTICS --> PG

    PG --> DEBEZIUM
    DEBEZIUM --> KAFKA
    KAFKA --> OHS
    KAFKA --> WEBHOOK
    KAFKA --> SUB_ANALYTICS
    KAFKA --> SETTLE

    SUB_GW --> S3
```

---

## Layered Architecture (Subscription Gateway Internal)

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (Ktor Routing)                                    │
│  PlanRoutes │ SubscriptionRoutes │ InvoiceRoutes │ UsageRoutes │ InternalRoutes     │
├────────────────────────────────────────────────────────────────────────────────────┤
│                        API SERVICE LAYER                                             │
│  PlanAPIService │ SubscriptionAPIService │ InvoiceAPIService │ UsageAPIService      │
│  MandateAPIService │ AnalyticsAPIService │ WebhookEventService                     │
├────────────────────────────────────────────────────────────────────────────────────┤
│                    SUBSCRIPTION CLIENT (Facade / Orchestrator)                       │
│  SubscriptionClient — orchestrates Plan, Subscription, Billing, Dunning services   │
├────────────────────────────────────────────────────────────────────────────────────┤
│                        DOMAIN SERVICE LAYER                                          │
│  PlanService │ SubscriptionService │ BillingService │ InvoiceService               │
│  DunningService │ ProrationService │ MeteringService │ LifecycleService            │
│  MandateService │ TaxService │ DiscountService │ CouponService                     │
├────────────────────────────────────────────────────────────────────────────────────┤
│                    BILLING ENGINE LAYER (Strategy Pattern)                           │
│  FixedRecurringEngine │ UsageBasedEngine │ TieredEngine │ HybridEngine             │
│  PerSeatEngine │ VolumeTieredEngine │ StaircaseEngine                              │
├────────────────────────────────────────────────────────────────────────────────────┤
│                        PAYMENT EXECUTION LAYER                                       │
│  PaymentExecutor → OMS integration for actual charge execution                      │
│  MandateExecutor → UPI Autopay / eNACH / Card-on-file debit                       │
│  RetryStrategyEngine → Smart retry with backoff + ML scoring                       │
├────────────────────────────────────────────────────────────────────────────────────┤
│                        REPOSITORY LAYER                                              │
│  PlanRepository │ SubscriptionRepository │ InvoiceRepository │ BillingCycleRepo    │
│  MandateRepository │ UsageRecordRepository │ DunningAttemptRepository              │
│  OutboxRepository │ ScheduleRepository │ CouponRepository                          │
├────────────────────────────────────────────────────────────────────────────────────┤
│                        INFRASTRUCTURE                                                │
│  PostgreSQL (Exposed ORM) │ Redis │ Kafka Producer │ SQS Client │ S3 Client        │
│  HTTP Clients (OMS, Merchant, Vault, FX) │ pg_cron │ OpenTelemetry                 │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant M as Merchant
    participant Kong as Kong Gateway
    participant SubGW as Subscription Gateway
    participant PG as PostgreSQL
    participant DBZ as Debezium CDC
    participant Kafka as Kafka (MSK)
    participant Sched as Scheduler Service
    participant OMS as OMS (Payment)
    participant Mandate as Mandate Service
    participant WH as Webhook Service
    participant Analytics as Analytics Service

    Note over M,Analytics: === SUBSCRIPTION CREATION ===
    M->>Kong: POST /api/subscriptions/v1/subscriptions
    Kong->>SubGW: Route to Subscription GW
    SubGW->>PG: BEGIN Transaction
    SubGW->>PG: INSERT subscription (status=CREATED)
    SubGW->>PG: INSERT billing_schedule (next cycles)
    SubGW->>PG: INSERT outbox (proto payload)
    SubGW->>PG: COMMIT
    SubGW-->>M: 201 Created {subscriptionId, mandateUrl}

    Note over PG,DBZ: Debezium reads WAL
    DBZ->>Kafka: Publish subscription.created event

    par Parallel Consumers
        Kafka->>WH: Webhook Service
        WH->>M: POST merchant callback (subscription.created)
    and
        Kafka->>Analytics: Update MRR metrics
    end

    Note over M,Analytics: === MANDATE REGISTRATION ===
    M->>Kong: Customer completes mandate setup
    Kong->>SubGW: Mandate callback
    SubGW->>Mandate: Register mandate (UPI/eNACH/Card)
    Mandate-->>SubGW: Mandate active
    SubGW->>PG: UPDATE subscription (status=ACTIVE, mandate_id)
    SubGW->>PG: INSERT outbox (subscription.activated)

    Note over M,Analytics: === BILLING CYCLE EXECUTION ===
    Sched->>SubGW: Execute billing cycle (cron trigger)
    SubGW->>PG: SELECT due subscriptions
    SubGW->>SubGW: Calculate invoice (plan + usage + tax)
    SubGW->>PG: INSERT invoice (status=PENDING)
    SubGW->>OMS: Create order + payment (mandate debit)
    OMS->>Mandate: Execute mandate debit
    Mandate-->>OMS: Payment success
    OMS-->>SubGW: Payment confirmed
    SubGW->>PG: UPDATE invoice (status=PAID)
    SubGW->>PG: INSERT outbox (invoice.paid)

    par Notifications
        Kafka->>WH: Notify merchant (invoice.paid)
    and
        Kafka->>Analytics: Update revenue metrics
    end
```

---

## Infrastructure Topology

### Kubernetes Deployment

```
EKS Cluster (ap-south-1)
├── Namespace: nxt-subscriptions
│   ├── nxt-subscription-gateway-service (3 replicas, 2 CPU / 4GB)
│   ├── nxt-subscription-scheduler-service (2 replicas, 1 CPU / 2GB)
│   ├── nxt-mandate-management-service (3 replicas, 1 CPU / 2GB)
│   ├── nxt-subscription-analytics-service (2 replicas, 1 CPU / 2GB)
│   └── subscription-debezium-server (1 replica, outbox CDC)
├── Namespace: nxt-services (existing)
│   ├── nxt-payment-order-service (OMS — payment execution)
│   ├── webhook-service (notification delivery)
│   └── payment-option-service (payment methods)
└── Namespace: data
    ├── Redis (ElastiCache — subscription locks, plan cache)
    ├── Kafka Connect (MSK Connect — Debezium)
    └── SQS (dunning retry queues)
```

### Database Architecture

```
Aurora PostgreSQL (Multi-AZ) — nxt_subscriptions_db
├── plans (subscription plan definitions)
├── plan_prices (multi-currency pricing per plan)
├── subscriptions (RANGE partitioned by created_date — monthly)
├── subscription_items (line items per subscription)
├── billing_schedules (next billing dates, computed)
├── invoices (RANGE partitioned by billing_date — monthly)
├── invoice_line_items (breakdown per invoice)
├── payments (RANGE partitioned by created_at)
├── mandates (mandate lifecycle tracking)
├── dunning_attempts (retry history)
├── usage_records (metered usage, RANGE partitioned)
├── coupons (discount definitions)
├── subscription_coupons (applied coupons)
├── proration_credits (mid-cycle credits)
├── outbox (Debezium CDC source)
├── subscription_events (audit trail)
└── Extensions: pg_cron, pgcrypto, pg_partman
```

### Kafka Topics

| Topic | Producer | Consumers | Format |
|-------|----------|-----------|--------|
| `subscriptions.public.outbox` | Debezium | Firehose, Webhook, Analytics | Protobuf |
| `subscription.lifecycle` | Sub GW | Analytics, Webhook, Settlement | Protobuf |
| `subscription.billing` | Scheduler | Sub GW, Analytics | Protobuf |
| `subscription.dunning` | Scheduler | Sub GW (retry) | Protobuf |
| `subscription.mandate` | Mandate Svc | Sub GW, Analytics | Protobuf |
| `subscription.invoice` | Sub GW | Webhook, Settlement, Analytics | Protobuf |
| `subscription.usage` | Sub GW | Analytics, Metering | Protobuf |
| `subscription.recon` | Recon Pipeline | Sub GW | Protobuf |

### SQS Queues (Dunning Pipeline)

| Queue | Delay | Purpose |
|-------|-------|---------|
| `subscription-retry-immediate` | 0s | Soft-decline immediate retry |
| `subscription-retry-4h` | 4h | First retry after cooling |
| `subscription-retry-24h` | 24h | Second retry next day |
| `subscription-retry-48h` | 48h | Third retry |
| `subscription-retry-72h` | 72h | Final retry before cancellation |
| `subscription-dunning-dlq` | — | Dead letter after all retries exhausted |

---

## Cross-Cutting Concerns

### Security
- Merchant authentication via HMAC-signed headers (same as OMS)
- Mandate tokens encrypted at rest (AES-256-GCM)
- Customer PII encrypted in JSONB (card last-4, email, phone)
- TLS 1.3 for all inter-service communication
- API rate limiting per merchant (Redis sliding window)
- PCI DSS compliance for stored card mandates (delegated to Vault)

### Observability
- **Traces**: OpenTelemetry → OTLP → Last9 (full distributed trace from billing trigger to payment completion)
- **Metrics**: Custom counters — billing_cycles_executed, dunning_attempts, churn_rate, mrr_delta
- **Logs**: Structured JSON via logstash-logback-encoder → Loki
- **Alerts**: PagerDuty integration for billing failures > threshold
- **Health**: `/health/live` + `/health/ready` on port 8081
- **Dashboards**: Grafana — MRR, churn, ARPU, billing success rate, dunning recovery

### Resilience
- Distributed locks (Redis) prevent duplicate billing for same subscription
- Circuit breakers on all downstream payment gateways
- Exponential backoff in SQS dunning pipeline
- Idempotency keys on all billing and payment operations
- Graceful degradation: if mandate service is down, queue billing for later
- Feature toggles for new billing engine rollout

### Performance
- Table partitioning (monthly range) for invoices and usage records
- JSONB for flexible subscription metadata
- Coroutine-based async I/O (batch billing cycles in parallel)
- Connection pooling via HikariCP (max 50 per pod)
- Redis caching for plan configs (5-min TTL), merchant settings
- Pre-computed billing schedules (avoid runtime calculation)
- Batch invoice generation (process 1000 subscriptions per scheduler tick)

### Regulatory Compliance (RBI)
- **Pre-debit notification**: 24 hours before recurring charge (mandatory for UPI/eNACH)
- **Amount ceiling**: eNACH mandates capped at registered max amount
- **Customer opt-out**: One-click cancellation without merchant intervention
- **Transaction limits**: Per-transaction and periodic limits enforced
- **AFA (Additional Factor of Authentication)**: First transaction requires 2FA; subsequent charges auto-debited within mandate limits
