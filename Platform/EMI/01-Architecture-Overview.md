# Affordability (EMI) Platform - Architecture Overview

## 1. Executive Summary

The **Affordability Platform** (internally called "Paylater/EMI") is Pine Labs' enterprise-grade EMI (Equated Monthly Installment) payment infrastructure that enables merchants to offer installment-based payment options across multiple channels (POS terminals, online checkout, payment links). The platform supports Bank EMI, Brand EMI, Cardless EMI, Debit Card EMI, UPI EMI, BNPL (Buy Now Pay Later), and NBFC lending — serving millions of transactions monthly.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL CONSUMERS                                     │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────────────┐   │
│  │POS (EDC) │  │Online Gateway│  │Payment Link │  │NXT Payment Order Serv  │   │
│  │Terminal   │  │(Plural Edge) │  │(PayByLink)  │  │(Checkout)              │   │
│  └─────┬────┘  └──────┬───────┘  └──────┬──────┘  └───────────┬────────────┘   │
└────────┼───────────────┼─────────────────┼─────────────────────┼────────────────┘
         │               │                 │                     │
         ▼               ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         GATEWAY & ADAPTER LAYER (Kotlin/Ktor)                    │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                    Offer Adapter Service (Port 8083)                        │  │
│  │  - Merchant-facing V1/V2 APIs                                              │  │
│  │  - JWT Authentication & Authorization                                      │  │
│  │  - Request transformation & validation                                     │  │
│  └────────────────────────────────┬───────────────────────────────────────────┘  │
│                                   │                                               │
│  ┌────────────────────────────────▼───────────────────────────────────────────┐  │
│  │                   Gateway Adapter Service (Port 8082)                       │  │
│  │  - Central routing (Discovery vs Processing)                               │  │
│  │  - BIN service integration (card identification)                           │  │
│  │  - Order lifecycle event sync (Kafka consumer)                             │  │
│  │  - IMEI validation orchestration                                           │  │
│  │  - Circuit breaker (maxFailures=200, resetTimeout=10s)                     │  │
│  └──────────────────┬──────────────────────┬──────────────────────────────────┘  │
│                     │                      │                                      │
│  ┌──────────────────▼────────┐  ┌─────────▼───────────────────────────────────┐  │
│  │ Offer Discovery Adapter   │  │   Offer Processing Adapter (Port 8081)      │  │
│  │ (Port 8080)               │  │   - Payment lifecycle (validate/confirm/    │  │
│  │ - Parallel Bank+Brand     │  │     settle/void/refund/cancel)              │  │
│  │   EMI offer discovery     │  │   - RSA encryption for sensitive data       │  │
│  │ - Product name caching    │  │   - Token management with auth service      │  │
│  │   (30-day TTL)            │  │   - Issuer data caching                     │  │
│  └──────────────────┬────────┘  └─────────┬───────────────────────────────────┘  │
└─────────────────────┼──────────────────────┼─────────────────────────────────────┘
                      │                      │
                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CORE ENGINE LAYER (Java 17 / Spring Boot 3.x)                  │
│                                                                                   │
│  ┌───────────────────────────┐  ┌──────────────────────────────────────────────┐ │
│  │   Affordability ReadServ  │  │    Affordability TransactionServ             │ │
│  │   (EMI Calculation Engine)│  │    (Payment Orchestrator)                    │ │
│  │                           │  │                                              │ │
│  │  • EMI offer discovery    │  │  • Transaction lifecycle management          │ │
│  │  • Rate/tenure calculator │  │  • Task-based orchestration pipeline         │ │
│  │  • Multi-product support  │  │  • Velocity/budget enforcement               │ │
│  │  • BIN-based filtering    │  │  • Credit limit management                  │ │
│  │  • Subvention computation │  │  • IMEI blocking/unblocking                  │ │
│  │  • Down payment calc      │  │  • Settlement & reconciliation              │ │
│  │  • Customer validation    │  │  • Idempotent operations                    │ │
│  │  • Redis + in-memory      │  │  • Fund settlement dispatch                 │ │
│  │    multi-layer cache      │  │  • Kafka-based settlement events            │ │
│  └───────────┬───────────────┘  └──────────────────┬───────────────────────────┘ │
│              │                                      │                             │
│  ┌───────────▼───────────────┐  ┌──────────────────▼───────────────────────────┐ │
│  │  Offer Management Serv    │  │    Paylater TxnProcessor Serv (Legacy)       │ │
│  │  (Offer CRUD + Lifecycle) │  │    (MSSQL-based, POS/offline EMI)            │ │
│  │                           │  │                                              │ │
│  │  • Campaign management    │  │  • NBFC/Lending integration                  │ │
│  │  • Budget tracking        │  │  • Cardless EMI orchestration               │ │
│  │  • Velocity rules config  │  │  • PayByLink flows                          │ │
│  │  • Multi-tenant RBAC      │  │  • EMI on UPI                               │ │
│  │  • Approval workflows     │  │  • MQTT POS communication                   │ │
│  │  • Bulk operations (S3)   │  │  • Dual datasource (HUB + AUXI)            │ │
│  └───────────────────────────┘  └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                      │                      │
                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      CONNECTOR LAYER                                              │
│                                                                                   │
│  ┌─────────────────┐  ┌────────────────────┐  ┌─────────────────────────────┐   │
│  │ BNPL Connector  │  │  NBFC Connector    │  │ Debit EMI Provider Adapter  │   │
│  │                 │  │                    │  │                             │   │
│  │ • ICICI Cardless│  │ • Bajaj Finance    │  │ • Debit card EMI via        │   │
│  │ • LazyPay      │  │ • HDB Financial    │  │   acquirer integration      │   │
│  │ • ePayLater    │  │ • Home Credit      │  │ • Penny drop auth           │   │
│  │                 │  │ • LiquiLoans       │  │ • OMS integration           │   │
│  │                 │  │ • TVS Credit       │  │                             │   │
│  └─────────────────┘  └────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                      │                      │
                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SUPPORT SERVICES                                             │
│                                                                                   │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────────────────────┐  │
│  │Cache Management  │  │ Product Mgmt    │  │ Batch Processing               │  │
│  │Service           │  │ Service         │  │ Service                        │  │
│  │                  │  │                 │  │                                │  │
│  │• Event-driven    │  │• Product CRUD   │  │• IMEI unblock (orphaned txns)  │  │
│  │  invalidation    │  │• Brand mgmt     │  │• Scheduled cleanup             │  │
│  │• Hot key tracking│  │• Bundle mgmt    │  │• Async task resolution         │  │
│  │• Distributed lock│  │• Category mgmt  │  │                                │  │
│  └──────────────────┘  └─────────────────┘  └────────────────────────────────┘  │
│                                                                                   │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────────────────────┐  │
│  │Fee Engine        │  │ Catalogue Mgmt  │  │ Bulk Processor                 │  │
│  │Service           │  │ Service         │  │                                │  │
│  │                  │  │                 │  │ • Excel-based bulk ops          │  │
│  │• CCF calculation │  │• Image/asset    │  │ • Client onboarding            │  │
│  │• Tax computation │  │  metadata       │  │ • Offer configuration          │  │
│  │• Store group     │  │• CDN URL mgmt   │  │ • S3-based file processing     │  │
│  │  based pricing   │  │                 │  │                                │  │
│  └──────────────────┘  └─────────────────┘  └────────────────────────────────┘  │
│                                                                                   │
│  ┌──────────────────┐  ┌─────────────────────────────────────────────────────┐   │
│  │Analytics Service │  │ Common Utility (Rate Limiter Library)                │   │
│  │                  │  │                                                      │   │
│  │• Redshift queries│  │ • Token bucket algorithm (Redis Lua)                 │   │
│  │• Template-driven │  │ • Per-client rate limiting                           │   │
│  │• Excel export    │  │ • Configurable burst capacity                        │   │
│  └──────────────────┘  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Gateway/Adapter** | Kotlin + Ktor | Kotlin 1.9+, Ktor 2.x | High-performance async routing |
| **Core Engine** | Java + Spring Boot | Java 17, Spring Boot 3.4.x | Business logic, orchestration |
| **Legacy Processor** | Java + Spring Boot | Java 11, Spring Boot 2.7 | MSSQL-based offline EMI |
| **Database (NXT)** | PostgreSQL | 14+ | Transactional data (new platform) |
| **Database (Legacy)** | MS SQL Server | 2019 | PLUTUS_HUBDB, AUXIDB |
| **Database (Catalog)** | MongoDB | 4.4+ | EMI scheme catalog (legacy) |
| **Cache** | Redis | 6.x+ | Distributed caching, rate limiting |
| **Messaging** | Apache Kafka | MSK | Settlement events, order sync |
| **Analytics** | Amazon Redshift | - | Reporting warehouse |
| **File Storage** | AWS S3 | - | Bulk files, KFS documents |
| **Encryption** | HSM (Thrift) | - | Card data encryption |
| **Auth** | Keycloak (OIDC) | - | OAuth2 + JWT |
| **Monitoring** | Prometheus + Grafana | - | Metrics, dashboards |
| **CI/CD** | Jenkins + Helm | - | K8s deployment |

---

## 4. Microservice Inventory

### Core Services (Critical Path)
| Service | Port | Tech | Database | Role |
|---------|------|------|----------|------|
| Affordability_Readserv | 8080 | Java 17/Spring Boot 3.4 | PostgreSQL (read replicas) | EMI calculation engine |
| Affordability_Transactionserv | 8080 | Java 17/Spring Boot 3.4 | PostgreSQL | Payment orchestrator |
| Affordability_Offermgmtserv | 8080 | Java 17/Spring Boot 3.2 | PostgreSQL | Offer lifecycle management |
| Paylater_Txnprocessorserv | 8080 | Java 11/Spring Boot | MSSQL | Legacy offline EMI processor |

### Adapter Services (NXT Integration)
| Service | Port | Tech | Role |
|---------|------|------|------|
| Affordability_GatewayAdapter | 8082 | Kotlin/Ktor | Central API gateway |
| Affordability_OfferDiscoveryAdapter | 8080 | Kotlin/Ktor | Offer discovery proxy |
| Affordability_OfferProcessingAdapter | 8081 | Kotlin/Ktor | Payment processing proxy |
| Affordablity_OfferAdapter | 8083 | Kotlin/Ktor | Merchant-facing API |
| Affordability_DebitEmiProviderAdapter | - | Kotlin/Ktor | Debit EMI payments |

### Connector Services
| Service | Tech | Providers |
|---------|------|-----------|
| Affordability_BNPL_connector | Java/WebFlux | ICICI Cardless, LazyPay |
| Paylater_NBFCConnectorServ | Java/Spring Boot | Bajaj, HDB, HomeCredit, LiquiLoans, TVS |
| Paylater_CardlessIssuerConnectorServ | Java | Cardless EMI issuers |

### Support Services
| Service | Tech | Role |
|---------|------|------|
| Affordability_CacheManagementServ | Java/Spring Boot | Cache lifecycle management |
| Affordability_Productmgmtserv | Java/Spring Boot | Product/brand/bundle CRUD |
| Affordability_Cataloguemgmtserv | Java/Spring Boot 3.4 | Image/asset metadata |
| Paylater_Catalogueserv | Java/Spring Boot + MongoDB | EMI scheme catalog (legacy) |
| Paylater_FeeEngineServ | Java/Spring Boot | Customer convenience fee |
| Affordability_Batchprocessingserv | Java/Spring Boot (CronJob) | Scheduled cleanup tasks |
| Affordability_BulkProcessor | Java/Spring Boot | Excel bulk operations |
| Affordability_Analytics | Java/Spring Boot | Redshift analytics |
| Affordability_common_utility | Java (Library) | Shared rate limiter |

---

## 5. Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    AWS EKS Cluster                             │
│                                                               │
│  Namespace: affordability-prod                                │
│  ┌──────────────────────────────────────────────────────────┐│
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │ReadServ     │  │TxnServ      │  │OfferMgmtServ    │ ││
│  │  │Replicas: 3+ │  │Replicas: 3+ │  │Replicas: 2+     │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │GatewayAdptr │  │DiscoveryAdpt│  │ProcessingAdptr  │ ││
│  │  │Replicas: 3+ │  │Replicas: 3+ │  │Replicas: 3+     │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │OfferAdapter │  │DebitEMIAdptr│  │CacheMgmtServ    │ ││
│  │  │Replicas: 2+ │  │Replicas: 2+ │  │Replicas: 1      │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ Amazon ElastiCache  │  │ Amazon RDS (PostgreSQL)      │   │
│  │ Redis Cluster       │  │ Writer + N Read Replicas     │   │
│  │ • Cache storage     │  │ • Affordability DB           │   │
│  │ • Rate limiting     │  │ • Multi-AZ                   │   │
│  │ • Distributed locks │  │                              │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ Amazon MSK (Kafka)  │  │ Amazon S3                    │   │
│  │ • Settlement topic  │  │ • Bulk files                 │   │
│  │ • Order events      │  │ • KFS documents              │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Key Design Principles

1. **Strategy Pattern Everywhere** — Services are resolved at runtime based on `Channel + ProgramType + IssuerType + IntegrationType`. This enables adding new payment types without modifying existing code.

2. **Task-Based Orchestration** — Complex payment flows are broken into atomic tasks (VelocityCheck, CreditLimitBlock, ProductBlock, etc.) with individual status tracking and reversibility.

3. **Multi-Layer Caching** — Three-tier cache architecture: In-Memory (ConcurrentHashMap) → Redis (compressed) → PostgreSQL Read Replicas.

4. **Event-Driven Cache Invalidation** — DB-level event table (`offer_update_events`) polled by cache management service, ensuring eventual consistency without tight coupling.

5. **Multi-Tenant by Design** — `tenantName` on all entities supports white-label deployments (PL.IN, SaaS variants).

6. **Idempotent Operations** — All payment mutations (refund, void, settle) are idempotent using `AffordabilityIdempotentKeys`.

7. **Graceful Degradation** — Circuit breakers on all adapter services (maxFailures=200), Redis failures treated as cache miss, async task execution with fallback.

8. **Read/Write Splitting** — PostgreSQL read replicas with round-robin routing for the calculation-heavy ReadServ; MSSQL dual-datasource for legacy.

---

## 7. Data Flow Summary

```
[Merchant/POS] → [Offer Discovery] → ReadServ computes EMI plans
                                       ↓
[Customer selects plan] → [Offer Validation] → TransactionServ creates txn
                                                  ↓
[Pre-Payment] → VelocityCheck → CreditLimitBlock → ProductBlock → IMEI
                                                  ↓
[Complete Payment] → Acquirer/NBFC/BNPL confirmation → Ledger insert
                                                  ↓
[Settlement] → Kafka event → OMS settlement instruction
                                                  ↓
[Refund/Void] → Reverse tasks → Update ledger → Notify parties
```
