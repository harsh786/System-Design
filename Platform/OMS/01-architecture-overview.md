# 01 — Architecture Overview

> High-level system design of the Plural Platform V3 Order Management System

---

## System Context Diagram

```mermaid
graph TB
    subgraph External Actors
        MERCHANT[Merchant Server]
        CHECKOUT[Checkout UI / SDK]
        ADMIN[Admin Dashboard]
        SCHEDULER[Cron Scheduler]
    end

    subgraph API Gateway Layer
        KONG[Kong API Gateway<br/>External Traffic]
        NGINX[nginx-internal<br/>Service-to-Service]
    end

    subgraph OMS Platform Core
        OMS[nxt_payment_order_service<br/>Order Management System]
        RMS[nxt-refund-management-service<br/>Refund Management]
        RECON[order-recon<br/>Reconciliation Engine]
        OHS[nxt_order_history_service<br/>Read Projection]
        WEBHOOK[webhook-service<br/>Merchant Notifications]
        POS[payment-option-service<br/>Available Methods]
    end

    subgraph Payment Gateways
        CARD_GW[Card Gateway<br/>Plural_CardGatewayServicev21]
        UPI_GW[UPI Gateway]
        NB_GW[Netbanking Gateway]
        AFFORD_GW[Affordability Gateway<br/>EMI / BNPL / Points]
        WALLET_GW[Wallet Gateway]
    end

    subgraph Supporting Services
        MERCHANT_SVC[Merchant Service]
        BIN_SVC[Bin Service]
        ACQUIRER_SVC[Acquirer Service]
        TDS[Transaction Data Service]
        RISK_SVC[Risk Service]
        VAULT[Customer Vault MGM<br/>Tokenization]
        CONFEE[Convenience Fee Service]
        OFFER[Offer Service]
        FX[FX Rate Service]
    end

    subgraph Data Infrastructure
        PG[(PostgreSQL<br/>OMS Database)]
        REDIS[(Redis<br/>Locks + Cache)]
        KAFKA[Apache Kafka<br/>MSK]
        DEBEZIUM[Debezium CDC<br/>Connector]
        OPENSEARCH[(OpenSearch<br/>OHS Store)]
        SQS[AWS SQS<br/>Recon Pipeline]
    end

    MERCHANT --> KONG
    CHECKOUT --> KONG
    ADMIN --> KONG
    KONG --> OMS
    KONG --> RMS
    KONG --> POS
    KONG --> WEBHOOK

    SCHEDULER --> NGINX --> RECON

    OMS --> PG
    OMS --> REDIS
    OMS --> CARD_GW
    OMS --> UPI_GW
    OMS --> NB_GW
    OMS --> AFFORD_GW
    OMS --> WALLET_GW
    OMS --> MERCHANT_SVC
    OMS --> BIN_SVC
    OMS --> ACQUIRER_SVC
    OMS --> RISK_SVC
    OMS --> VAULT
    OMS --> CONFEE
    OMS --> OFFER
    OMS --> FX

    RMS --> OMS
    RMS --> OHS
    RMS --> REDIS
    RECON --> OHS
    RECON --> OMS
    RECON --> RMS
    RECON --> KAFKA
    RECON --> SQS

    PG --> DEBEZIUM
    DEBEZIUM --> KAFKA
    KAFKA --> OHS
    KAFKA --> WEBHOOK
    KAFKA --> TDS

    OHS --> OPENSEARCH
```

---

## Layered Architecture (OMS Internal)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (Ktor Routing)                        │
│  OrderRoutes │ PaymentRoutes │ InternalRoutes │ OTP │ Invoice │ AWB     │
├─────────────────────────────────────────────────────────────────────────┤
│                        API SERVICE LAYER                                 │
│  OrdersAPIService │ PaymentsAPIService │ CrossBorderService             │
├─────────────────────────────────────────────────────────────────────────┤
│                        OMS CLIENT (Facade)                               │
│  OMSClient — orchestrates OrderService, PaymentService, RefundService   │
├─────────────────────────────────────────────────────────────────────────┤
│                        DOMAIN SERVICE LAYER                              │
│  OrderService │ PaymentService │ RefundService │ OfferService            │
│  LockService │ DowntimeService │ SettlementReversalService              │
├─────────────────────────────────────────────────────────────────────────┤
│                   TRANSACTION HANDLER LAYER (Strategy)                    │
│  NormalTxnHandler │ DccTxnHandler │ ICBTxnHandler │ MccTxnHandler       │
│  CardLessEMIHandler │ MccWalletTxnHandler                               │
├─────────────────────────────────────────────────────────────────────────┤
│                        PAYMENT SDK LAYER                                  │
│  PaymentSDK → routes to Card/UPI/NB/Wallet/EMI/BNPL connectors          │
├─────────────────────────────────────────────────────────────────────────┤
│                        REPOSITORY LAYER                                   │
│  OrderRepository │ OutboxRepository │ PaymentReferenceRepository        │
│  DowntimeRepository │ MerchantRefOrderMapperRepository                  │
├─────────────────────────────────────────────────────────────────────────┤
│                        INFRASTRUCTURE                                     │
│  PostgreSQL (Exposed ORM) │ Redis │ Kafka Producer │ HTTP Clients        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant M as Merchant
    participant Kong as Kong Gateway
    participant OMS as OMS Service
    participant PG as PostgreSQL
    participant DBZ as Debezium CDC
    participant Kafka as Kafka (MSK)
    participant FH as Firehose Consumer
    participant OHS as Order History Service
    participant WH as Webhook Service
    participant TDS as Transaction Data Service

    M->>Kong: API Request
    Kong->>OMS: Route to OMS

    OMS->>PG: BEGIN Transaction
    OMS->>PG: INSERT/UPDATE orders table
    OMS->>PG: INSERT outbox record (proto payload)
    OMS->>PG: COMMIT Transaction

    Note over PG,DBZ: Debezium reads WAL (logical replication)

    DBZ->>Kafka: Publish to orders.public.outbox
    
    par Parallel Consumers
        Kafka->>FH: Firehose (generic consumer)
        FH->>OHS: Persist to OpenSearch
    and
        Kafka->>WH: Webhook Service
        WH->>M: POST merchant callback URL
    and
        Kafka->>TDS: Transaction Data Service
        TDS->>TDS: Update transaction records
    end
```

---

## Infrastructure Topology

### Kubernetes Deployment

```
EKS Cluster (ap-south-1)
├── Namespace: nxt-services
│   ├── nxt-payment-order-service (3 replicas, 2 CPU / 4GB)
│   ├── nxt-order-history-service (3 replicas)
│   ├── nxt-refund-management-service (2 replicas)
│   ├── order-recon (2 replicas)
│   ├── webhook-service (3 replicas)
│   └── payment-option-service (2 replicas)
├── Namespace: debezium
│   ├── oms-debezium-server (outbox CDC)
│   └── oms-debezium-server-v1 (outbox_v1 CDC)
└── Namespace: data
    ├── Redis (ElastiCache cluster)
    └── Kafka Connect (MSK Connect)
```

### Database Architecture

```
Aurora PostgreSQL (Multi-AZ)
├── nxt_payment_orders_db
│   ├── orders (RANGE partitioned by partition_date — monthly)
│   ├── outbox (Debezium CDC source)
│   ├── outbox_v1 (Debezium CDC source v1)
│   ├── payment_reference (RANGE partitioned by created_at)
│   ├── merchant_ref_order_mapper (HASH partitioned, 8 buckets)
│   ├── downtimes (downtime tracking)
│   ├── order_update_audit (admin audit trail)
│   ├── mcc_currency_codes (lookup)
│   ├── pa_cb_invoices (cross-border, partitioned)
│   └── pa_cb_awb_mappings (cross-border, partitioned)
└── Extensions: pg_cron, pgcrypto
```

### Kafka Topics

| Topic | Producer | Consumers | Format |
|-------|----------|-----------|--------|
| `orders.public.outbox` | Debezium (outbox) | Firehose, OHS, Webhook, TDS | Protobuf |
| `orders.public.outbox_v1` | Debezium (outbox_v1) | Firehose v2 | Protobuf |
| `update.event.orders` | OMS (direct) | OHS, Webhook | Protobuf |
| `order-recon` | order-recon | OMS | Protobuf |
| `refund-recon` | order-recon | RMS → OMS | Protobuf |
| `long-pending` | order-recon | SQS pipeline | Protobuf |
| `long-pending-refund` | order-recon | SQS pipeline | Protobuf |
| `emi-recon` | order-recon | OMS | Protobuf |
| `sync-payments` | order-recon | OMS | Protobuf |

---

## Cross-Cutting Concerns

### Security
- Merchant authentication via signed headers (HMAC)
- PII encryption at rest (AES-256 on card numbers, customer data)
- Field-level encryption in JSONB via `encryptOrder()` pipeline
- TLS 1.3 for all inter-service communication

### Observability
- **Traces**: OpenTelemetry → OTLP → Last9 (trace context propagated via outbox `traceparent`)
- **Metrics**: Custom counters per merchant/acquirer/payment-method (MetricsInfo)
- **Logs**: Structured JSON via logstash-logback-encoder → Loki
- **Health**: `/health/live` (liveness) + `/health/ready` (readiness) on port 8081

### Resilience
- Distributed locks (Redis) prevent concurrent mutations on same order
- Circuit breakers on all downstream HTTP clients
- Exponential backoff in SQS recon pipeline (30s → 60s → 120s → 240s → 480s)
- Bounded retries with DLQ for exhausted messages
- Feature toggles for graceful degradation

### Performance
- Table partitioning (monthly range, hash) for query performance at scale
- JSONB for flexible payment model storage (avoids schema migrations)
- Coroutine-based async I/O (Ktor + kotlinx.coroutines)
- Connection pooling via HikariCP
- Redis caching for merchant configs, DCC details, feature toggles
