# Plural Platform V3 — OMS (Order Management System)

> **Version**: 3.0 | **Service**: `nxt_payment_order_service` | **Stack**: Kotlin 1.9 / Ktor 2.3 / PostgreSQL / Kafka / Debezium CDC

---

## Architecture Documentation Index

| # | Document | Description |
|---|----------|-------------|
| 01 | [Architecture Overview](./01-architecture-overview.md) | High-level system design, service topology, infrastructure |
| 02 | [State Machines](./02-state-machines.md) | Order & Payment lifecycle state diagrams with all transitions |
| 03 | [DB Schema & Data Model](./03-db-schema-and-data-model.md) | Tables, partitioning strategy, JSONB models, indices |
| 04 | [Purchase Workflow](./04-purchase-workflow.md) | End-to-end payment creation flow (functional + technical) |
| 05 | [Pre-Auth & Capture](./05-pre-auth-and-capture.md) | Authorization hold, partial/full capture, void flows |
| 06 | [Cancel & Void](./06-cancel-and-void.md) | Order cancellation, payment cancellation, void mechanics |
| 07 | [Refund Mechanisms](./07-refund-mechanisms.md) | Full/partial refund, retry on decline, settlement reversal |
| 08 | [Reconciliation, Late Auth & Backposting](./08-reconciliation-late-auth-backposting.md) | Recon pipelines, late auth expiry, force close, backposting |
| 09 | [Product Workflows](./09-product-workflows.md) | DCC, MCC, Cross-Border (PA-CB), EMI, Split Payments, Brand Wallet, UPI Mandate |
| 10 | [Outbox Pattern & CDC](./10-outbox-pattern-and-cdc.md) | Transactional outbox, Debezium, Kafka event sourcing, Firehose |

---

## Platform V3 Service Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MERCHANT / CHECKOUT UI                              │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ HTTPS
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           KONG API GATEWAY (External)                            │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                    ┌──────────────────┬┴──────────────────┐
                    ▼                  ▼                    ▼
         ┌──────────────────┐ ┌────────────────┐ ┌─────────────────────┐
         │  OMS (Orders)    │ │ Payment Option │ │  Webhook Service    │
         │  nxt_payment_    │ │    Service     │ │  (Svix-based)       │
         │  order_service   │ │                │ │                     │
         └────────┬─────────┘ └────────────────┘ └─────────────────────┘
                  │
    ┌─────────────┼─────────────────────────────────────┐
    │             │                                     │
    ▼             ▼                                     ▼
┌────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐
│  Card  │  │   UPI    │  │ Netbanking │  │  Affordability GW    │
│Gateway │  │ Gateway  │  │  Gateway   │  │  (EMI/BNPL/Points)   │
└────┬───┘  └────┬─────┘  └─────┬──────┘  └──────────┬───────────┘
     │           │               │                    │
     ▼           ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│              ACQUIRERS / PAYMENT NETWORKS / BANKS                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Principles

1. **Event-Sourced State** — Every order mutation produces a CDC event via transactional outbox
2. **Single Source of Truth** — OMS PostgreSQL is the authoritative state; OHS (OpenSearch) is the read-optimized projection
3. **Idempotent Operations** — All mutations are idempotent with distributed locking (Redis)
4. **Partition-Ready** — Orders table is range-partitioned by date; payment_reference is hash-partitioned
5. **Gateway Agnostic** — OMS delegates to PaymentSDK which routes to Card/UPI/NB/Wallet/EMI gateways
6. **Reconciliation First** — Every non-terminal order is eventually reconciled via order-recon SQS pipeline

---

## Key Repositories

| Repository | Purpose |
|-----------|---------|
| `nxt_payment_order_service` | OMS core — order lifecycle, payments, refunds |
| `nxt_order_history_service` | Read projection (OpenSearch) |
| `nxt-refund-management-service` | Refund orchestration layer |
| `order-recon` | Reconciliation pipeline (Kafka + SQS) |
| `webhook-service` | Merchant notification delivery |
| `payment-option-service` | Available payment methods |
| `nxt-message-contracts` | Protobuf event contracts |
| `plural-nxt-api-contracts-internal` | Merchant-facing API contracts |

---

## Technology Decisions

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Kotlin 1.9, JVM 17 | Coroutines for async I/O, type safety |
| Framework | Ktor 2.3 | Lightweight, non-blocking, Kotlin-native |
| Database | PostgreSQL (Aurora) | ACID, JSONB, partitioning, CDC-compatible |
| ORM | Exposed | Kotlin-native, type-safe SQL DSL |
| Messaging | Kafka (MSK) + Debezium | Exactly-once semantics via outbox pattern |
| Serialization | Protobuf + kotlinx.serialization | Proto for events, JSON for API/JSONB |
| Caching | Redis (ElastiCache) | Distributed locks, payment detail cache |
| Observability | OpenTelemetry + Last9 | Distributed tracing, metrics, structured logs |
| Error Handling | Arrow `Either<L, R>` | Functional error propagation without exceptions |
