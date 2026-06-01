# Plural Platform V3 — Subscription Gateway

> **Version**: 1.0 | **Service**: `nxt-subscription-gateway-service` | **Stack**: Kotlin 2.x / Ktor 2.3 / PostgreSQL / Kafka / Debezium CDC / Redis

---

## Architecture Documentation Index

| # | Document | Description |
|---|----------|-------------|
| 01 | [Architecture Overview](./01-architecture-overview.md) | High-level system design, service topology, infrastructure |
| 02 | [State Machines](./02-state-machines.md) | Subscription, billing cycle & payment lifecycle state diagrams |
| 03 | [DB Schema & Data Model](./03-db-schema-and-data-model.md) | Tables, partitioning, JSONB models, entity relationships |
| 04 | [Subscription Creation Workflow](./04-subscription-creation-workflow.md) | Plan setup, subscription onboarding, mandate registration |
| 05 | [Billing & Invoice Workflow](./05-billing-and-invoice-workflow.md) | Cycle execution, invoice generation, tax calculation |
| 06 | [Payment Execution Workflow](./06-payment-execution-workflow.md) | Auto-charge, mandate debit, payment routing |
| 07 | [Dunning & Retry Workflow](./07-dunning-and-retry-workflow.md) | Smart retry, grace period, escalation, churn prevention |
| 08 | [Lifecycle Management Workflow](./08-lifecycle-management-workflow.md) | Pause/resume/cancel/upgrade/downgrade flows |
| 09 | [Webhook & Notification Workflow](./09-webhook-and-notification-workflow.md) | Event-driven merchant & customer notifications |
| 10 | [Proration & Metering Workflow](./10-proration-and-metering-workflow.md) | Usage-based billing, mid-cycle changes, credits |
| 11 | [Mandate & Token Management](./11-mandate-and-token-management.md) | Recurring authorization, token lifecycle, multi-method |
| 12 | [Settlement & Reconciliation](./12-settlement-and-reconciliation.md) | Subscription recon pipeline, MRR tracking, revenue recognition |

---

## Platform V3 Subscription Service Map

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          MERCHANT SERVER / DASHBOARD / CHECKOUT UI                        │
└──────────────────────────────────────────────┬──────────────────────────────────────────┘
                                               │ HTTPS
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              KONG API GATEWAY (External)                                  │
└──────────────────────────────────────────────┬──────────────────────────────────────────┘
                                               │
                  ┌────────────────┬───────────┼───────────┬────────────────┐
                  ▼                ▼           ▼           ▼                ▼
      ┌───────────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────┐
      │  Subscription GW  │ │   OMS    │ │ Webhook │ │  Offer   │ │  Payment Opt   │
      │  nxt-subscription │ │  (Order  │ │ Service │ │ Service  │ │    Service     │
      │  gateway-service  │ │  Mgmt)   │ │ (Svix)  │ │          │ │                │
      └────────┬──────────┘ └────┬─────┘ └─────────┘ └──────────┘ └────────────────┘
               │                  │
   ┌───────────┼──────────────────┼───────────────────────────┐
   │           │                  │                           │
   ▼           ▼                  ▼                           ▼
┌────────┐ ┌────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐
│  Card  │ │  UPI Autopay│  │  eNACH/NACH  │  │  Customer Vault (Tokenization)   │
│Gateway │ │  (Mandate)  │  │  (Mandate)   │  │  nxt-customer-vault-mgm-service  │
└────┬───┘ └─────┬──────┘  └──────┬───────┘  └──────────────────────────────────┘
     │           │                 │
     ▼           ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              ACQUIRERS / PAYMENT NETWORKS / BANKS                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Principles

1. **Recurring-First Design** — Built from ground up for automated recurring billing, not retrofitted on one-time payments
2. **Mandate-Native** — First-class support for UPI Autopay, eNACH, card-on-file mandates with pre-debit notifications
3. **Event-Sourced State** — Every subscription mutation produces CDC events via transactional outbox
4. **Dunning Intelligence** — Smart retry with ML-driven optimal retry timing, exponential backoff, and graceful degradation
5. **Proration Engine** — Handles mid-cycle plan changes with precise time-based or usage-based proration
6. **Multi-Currency** — Native support for cross-border subscriptions with FX rate locking at billing time
7. **Merchant Control** — Configurable billing cycles, retry policies, grace periods, and lifecycle hooks
8. **Regulatory Compliant** — RBI e-mandate guidelines, pre-debit notifications (24h before), AFA compliance

---

## Key Repositories

| Repository | Purpose |
|-----------|---------|
| `nxt-subscription-gateway-service` | Core — subscription lifecycle, billing, dunning |
| `nxt-subscription-scheduler-service` | Billing cycle scheduler, retry orchestration |
| `nxt-mandate-management-service` | Mandate registration, status tracking, token rotation |
| `nxt-subscription-analytics-service` | MRR, churn, LTV metrics and reporting |
| `nxt_payment_order_service` | Payment execution (existing OMS) |
| `webhook-service` | Merchant notification delivery |
| `nxt-message-contracts` | Protobuf event contracts |
| `plural-nxt-api-contracts-internal` | Merchant-facing API contracts |

---

## Technology Decisions

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Kotlin 2.x, JVM 17 | Coroutines for async billing, type safety |
| Framework | Ktor 2.3 | Lightweight, non-blocking, Kotlin-native |
| Database | PostgreSQL (Aurora) | ACID, JSONB, partitioning, CDC-compatible |
| ORM | Exposed | Kotlin-native, type-safe SQL DSL |
| Messaging | Kafka (MSK) + Debezium | Event sourcing via outbox pattern |
| Scheduling | pg_cron + Kafka delayed topics | Reliable billing cycle triggers |
| Serialization | Protobuf + kotlinx.serialization | Proto for events, JSON for API |
| Caching | Redis (ElastiCache) | Distributed locks, plan configs, rate limits |
| Observability | OpenTelemetry + Last9 | Traces, metrics, structured logs |
| Error Handling | Arrow `Either<L, R>` | Functional error propagation |
| Mandate Integration | UPI Autopay + eNACH + Card-on-file | Full recurring payment method coverage |

---

## API Surface

### Merchant-Facing APIs (via Kong)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/subscriptions/v1/plans` | Create subscription plan |
| GET | `/api/subscriptions/v1/plans/{planId}` | Get plan details |
| PUT | `/api/subscriptions/v1/plans/{planId}` | Update plan |
| POST | `/api/subscriptions/v1/subscriptions` | Create subscription |
| GET | `/api/subscriptions/v1/subscriptions/{subId}` | Get subscription |
| PATCH | `/api/subscriptions/v1/subscriptions/{subId}` | Update subscription |
| POST | `/api/subscriptions/v1/subscriptions/{subId}/pause` | Pause subscription |
| POST | `/api/subscriptions/v1/subscriptions/{subId}/resume` | Resume subscription |
| POST | `/api/subscriptions/v1/subscriptions/{subId}/cancel` | Cancel subscription |
| POST | `/api/subscriptions/v1/subscriptions/{subId}/change-plan` | Upgrade/downgrade |
| GET | `/api/subscriptions/v1/subscriptions/{subId}/invoices` | List invoices |
| GET | `/api/subscriptions/v1/invoices/{invoiceId}` | Get invoice detail |
| POST | `/api/subscriptions/v1/subscriptions/{subId}/charge` | Manual charge |
| POST | `/api/subscriptions/v1/usage-records` | Report usage (metered) |
| GET | `/api/subscriptions/v1/subscriptions/{subId}/upcoming-invoice` | Preview next invoice |

### Internal APIs (via nginx-internal)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/internal/v1/billing/execute-cycle` | Trigger billing cycle |
| POST | `/internal/v1/dunning/retry` | Execute retry attempt |
| POST | `/internal/v1/mandates/callback` | Mandate status callback |
| POST | `/internal/v1/payments/callback` | Payment result callback |
| GET | `/internal/v1/analytics/mrr` | MRR calculation |
| POST | `/internal/v1/reconciliation/sync` | Recon sync trigger |
