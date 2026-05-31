# 01 — Architecture Overview

## System Context

The Order Reconciliation Service sits between **Order History Service** (the read-optimized OpenSearch store) and the **transactional services** (OMS, RMS). Its primary role is to detect orders/payments in intermediate states and drive them to terminal states through configurable retry pipelines.

```mermaid
C4Context
    title Order Recon — System Context

    Person(ops, "Platform Ops", "Monitors recon health, manages rules")

    System(recon, "Order Recon Service", "Discovers stuck orders, routes through SQS pipeline, reconciles via OMS/RMS/Kafka")

    System_Ext(ohs, "Order History Service", "OpenSearch-backed read store")
    System_Ext(oms, "OMS (nxt-payments-service)", "Order state machine, payment orchestration")
    System_Ext(rms, "Refund Management Service", "Refund orchestration")
    System_Ext(kafka, "Kafka MSK", "Event streaming (6 recon topics)")
    System_Ext(sqs, "AWS SQS", "Delay queues (10 queues + DLQs)")
    System_Ext(redis, "Redis ElastiCache", "Dedup + circuit state")

    Rel(recon, ohs, "Queries pending orders", "HTTP/Protobuf")
    Rel(recon, oms, "Reconcile/Terminate", "HTTP")
    Rel(recon, rms, "Reconcile refunds", "HTTP")
    Rel(recon, kafka, "Publishes events", "Protobuf/ByteArray")
    Rel(recon, sqs, "Enqueue/Poll", "AWS SDK")
    Rel(recon, redis, "Dedup check/set", "Jedis")
    Rel(ops, recon, "Configure rules, trigger manual recon", "HTTP API")
```

## Component Architecture

```mermaid
graph TB
    subgraph "Order Recon Service"
        subgraph "Ingestion Layer"
            CRON[CronJob Scheduler<br/>Ktor scheduled tasks]
            API[HTTP API<br/>Manual triggers]
        end

        subgraph "Discovery Layer"
            SRB[SearchRequestBuilder<br/>OHS query construction]
            OHS_CLIENT[OrderHistoryClient<br/>HTTP + Circuit Breaker]
        end

        subgraph "Classification Layer"
            PIPELINE[ReconPipelineConfig<br/>Rule matching engine]
            DEDUP[Redis Dedup<br/>24h TTL keys]
        end

        subgraph "Routing Layer"
            SQS_PROD[SqsProducer<br/>Queue message dispatch]
            KAFKA_PROD[KafkaEventProducer<br/>Topic publishing]
            DELAY[DelayComputation<br/>Kafka lag compensation]
        end

        subgraph "Processing Layer"
            POLLER_MGR[SqsPollerManager<br/>Lifecycle orchestrator]
            RECON_POLLER[SqsPollerWorker<br/>Standard recon processing]
            ACTION_POLLER[ActionQueuePollerWorker<br/>Native OTP lifecycle]
            S3_POLLER[S3EventLoggerPollerWorker<br/>Cross-border docs]
            RISK_HANDLER[RiskDecisionHandler<br/>CyberSource decisions]
        end

        subgraph "Execution Layer"
            OMS_CLIENT2[OMSClient<br/>Reconcile/Terminate/Close]
            RMS_CLIENT[RMSClient<br/>Refund reconciliation]
            WEBHOOK_CLIENT[WebhookClient<br/>Retry delivery]
            SETTLEMENT_CLIENT[SettlementClient<br/>Retry settlement]
            NOTP_CLIENT[NativeOtpProcessorClient<br/>OTP status]
            CYBS_CLIENT[CybsCardConnectorClient<br/>Risk decisions]
        end
    end

    CRON --> SRB
    API --> SRB
    SRB --> OHS_CLIENT
    OHS_CLIENT --> PIPELINE
    PIPELINE --> DEDUP
    DEDUP --> SQS_PROD
    DEDUP --> KAFKA_PROD
    DELAY --> SQS_PROD

    POLLER_MGR --> RECON_POLLER
    POLLER_MGR --> ACTION_POLLER
    POLLER_MGR --> S3_POLLER

    RECON_POLLER --> OMS_CLIENT2
    RECON_POLLER --> RMS_CLIENT
    RECON_POLLER --> RISK_HANDLER
    RECON_POLLER --> KAFKA_PROD

    ACTION_POLLER --> NOTP_CLIENT
    ACTION_POLLER --> OMS_CLIENT2

    S3_POLLER --> OMS_CLIENT2

    RISK_HANDLER --> CYBS_CLIENT
```

## Layered Architecture

| Layer | Responsibility | Key Classes |
|-------|---------------|-------------|
| **Ingestion** | Trigger recon runs via cron or API | `OrderReconService`, `OrderReconRoutes` |
| **Discovery** | Build & execute OHS queries | `SearchRequestBuilder`, `OrderHistoryClient` |
| **Classification** | Match orders to pipeline rules | `ReconPipelineConfig`, `ReconPipelineRule` |
| **Routing** | Decide SQS vs Kafka, compute delays | `SqsProducer`, `KafkaEventProducer`, `DelayComputation` |
| **Processing** | Poll SQS, execute recon logic | `SqsPollerWorker`, `ActionQueuePollerWorker`, `S3EventLoggerPollerWorker` |
| **Execution** | Call downstream services | All `*Client` classes |

## Deployment Topology

```mermaid
graph TB
    subgraph "EKS Cluster (ap-south-1)"
        subgraph "Namespace: order-recon"
            POD1[order-recon Pod 1<br/>8080]
            POD2[order-recon Pod 2<br/>8080]
            POD3[order-recon Pod 3<br/>8080]
            SVC[K8s Service<br/>:80 → :8080]
            ING[Ingress<br/>nginx-internal]
        end
    end

    subgraph "AWS Managed Services"
        SQS[SQS<br/>10 queues + DLQs<br/>ap-south-1]
        MSK[MSK Kafka<br/>3 brokers<br/>IAM auth]
        REDIS[ElastiCache Redis<br/>6379]
        S3[S3<br/>Cross-border uploads]
    end

    subgraph "Internal Services (K8s)"
        OMS[nxt-payments-service]
        OHS[nxt-order-history-service]
        RMS[nxt-refund-management-service]
        NOTP[native-otp-processor]
    end

    ING --> SVC --> POD1 & POD2 & POD3
    POD1 & POD2 & POD3 --> SQS
    POD1 & POD2 & POD3 --> MSK
    POD1 & POD2 & POD3 --> REDIS
    POD1 & POD2 & POD3 --> OMS & OHS & RMS & NOTP
    S3 -->|Event notification| SQS
```

### HPA Configuration

| Parameter | Value |
|-----------|-------|
| Min replicas | 2 |
| Max replicas | 3 |
| CPU target | 80% |
| Memory target | 80% |
| Resources | 500m CPU / 1000Mi memory |

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Delay mechanism** | AWS SQS | Native DelaySeconds (≤900s) + visibility-timeout trick (>900s) eliminates need for custom delay infrastructure |
| **Message format** | JSON (SQS), Protobuf (Kafka) | SQS messages are small routing metadata; Kafka carries full order payloads for downstream |
| **Query engine** | OpenSearch via OHS | Millisecond queries over millions of orders; real-time index from Debezium CDC |
| **Circuit breaking** | Arrow Resilience | Functional, composable, Kotlin-native; avoids Spring dependency |
| **Deduplication** | Redis with TTL | Simple, fast, auto-expiring keys prevent re-processing within 24h window |
| **Config management** | Hoplite + ConfigMap | Hot-reloadable pipeline rules via K8s ConfigMap mount without service restart |
| **Concurrency** | Kotlin Coroutines (Dispatchers.IO) | Lightweight async processing; each SQS queue gets independent coroutine scope |
| **HTTP client** | OkHttp + CIO engines | OkHttp for connection pooling (600 max); CIO for async/non-blocking |

## Health & Observability

### Probes

| Probe | Endpoint | Port |
|-------|----------|------|
| Liveness | `/health/live` | 8080 |
| Readiness | `/health/ready` | 8080 |

### Metrics & Tracing

- **OpenTelemetry** instrumentation on Kafka producer (TracingProducerInterceptor)
- **Structured logging** via logback with JSON encoder
- **Custom metrics** (exposed via OTLP):
  - `recon.orders.discovered` — orders found per scenario per cron run
  - `recon.sqs.messages.processed` — messages processed per queue
  - `recon.direct.reconcile.duration` — latency of direct recon calls
  - `recon.dedup.hits` — deduplicated (skipped) orders

### Alerting Signals

| Signal | Condition | Action |
|--------|-----------|--------|
| DLQ depth > 0 | Messages failing all retries | Investigate stuck orders |
| Circuit breaker OPEN | Downstream service unhealthy | Check OMS/RMS/OHS health |
| Cron run 0 orders | OHS query returning empty | Verify OpenSearch index health |
| Redis connection failures | Pool exhausted | Scale Redis / check network |

## Request Flow Summary

```mermaid
sequenceDiagram
    participant Cron as Cron Scheduler
    participant Recon as OrderReconService
    participant OHS as Order History (OpenSearch)
    participant Redis as Redis (Dedup)
    participant SQS as SQS Queues
    participant Poller as SqsPollerWorker
    participant OMS as OMS / RMS

    Note over Cron: Every N minutes per scenario
    Cron->>Recon: triggerScenario(AUTHZ)
    Recon->>OHS: POST /orders/filter/scroll<br/>{status=AUTHENTICATED, age>5min}
    OHS-->>Recon: Order[] (batch of 1000)

    loop For each order
        Recon->>Redis: EXISTS dedup:{orderId}:{ruleId}
        alt Not deduplicated
            Redis-->>Recon: 0 (new)
            Recon->>Redis: SETEX dedup:{orderId}:{ruleId} 86460
            Recon->>SQS: SendMessage(queue=sqs-authz, delay=step[0].delay)
        else Already processed
            Redis-->>Recon: 1 (exists)
            Note over Recon: Skip
        end
    end

    Note over Poller: Continuous polling
    Poller->>SQS: ReceiveMessage(queue=sqs-authz)
    SQS-->>Poller: SqsMessagePayload

    alt Direct Recon (directPercent)
        Poller->>OMS: POST /reconcile-payments/{orderId}
        OMS-->>Poller: 200 OK (reconciled)
    else Kafka Path (kafkaPercent)
        Poller->>Poller: Publish to recon-orders topic
    end

    alt More steps remaining
        Poller->>SQS: SendMessage(delay=step[n+1].delay)
    else All steps exhausted
        Poller->>SQS: SendMessage(DLQ)
    end
```
