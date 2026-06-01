# Affordability Platform - Service Communication & Integration Patterns

## 1. Service Communication Map

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                 EXTERNAL SYSTEMS                                          │
│                                                                                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────────────────┐│
│  │NXT Order│  │NXT BIN   │  │NXT Customer  │  │Keycloak    │  │OMS (Order Management)  ││
│  │Service  │  │Service   │  │Vault         │  │Identity    │  │                        ││
│  └────┬────┘  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └──────────┬────────────┘│
│       │             │               │                 │                     │             │
└───────┼─────────────┼───────────────┼─────────────────┼─────────────────────┼─────────────┘
        │             │               │                 │                     │
        │ Kafka       │ REST          │ REST            │ OAuth2              │ REST+Kafka
        │ (order      │ (BIN→issuer)  │ (card token)    │ (client_credentials)│ (settlement)
        │  events)    │               │                 │                     │
        ▼             ▼               ▼                 ▼                     ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                           GATEWAY LAYER (Kotlin/Ktor)                                     │
│                                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐│
│  │                        Gateway Adapter (Port 8082)                                    ││
│  │  ┌─────────────────┐  ┌──────────────────────┐  ┌──────────────────────────────┐   ││
│  │  │Offer Discovery  │  │Offer Processing      │  │Order Event Consumer          │   ││
│  │  │Routing          │  │Routing               │  │(Kafka → REST sync)           │   ││
│  │  └────────┬────────┘  └──────────┬───────────┘  └──────────────────────────────┘   ││
│  └───────────┼──────────────────────┼──────────────────────────────────────────────────┘│
│              │                      │                                                    │
│  ┌───────────▼──────────┐  ┌───────▼────────────────────┐                               │
│  │Discovery Adapter     │  │Processing Adapter           │                               │
│  │(Port 8080)           │  │(Port 8081)                  │                               │
│  │                      │  │                             │                               │
│  │ Parallel Bank+Brand  │  │ RSA encryption layer        │                               │
│  │ EMI discovery        │  │ Payment lifecycle proxy     │                               │
│  │ Product name cache   │  │ Token management            │                               │
│  └───────────┬──────────┘  └───────┬────────────────────┘                               │
└──────────────┼──────────────────────┼────────────────────────────────────────────────────┘
               │                      │
               │ REST (OAuth2)        │ REST (OAuth2)
               │                      │
               ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                           CORE ENGINE LAYER (Java 17/Spring Boot)                          │
│                                                                                           │
│  ┌───────────────────────────┐        ┌─────────────────────────────────────────────────┐│
│  │     ReadServ              │        │         TransactionServ                          ││
│  │  (EMI Calculation)        │◄───────│  (Payment Orchestrator)                         ││
│  │                           │ REST   │                                                  ││
│  │  /calculate-emi           │        │  /transactions (CRUD)                            ││
│  │  /downpayment-details     │        │  /pre-payment (tasks)                            ││
│  │                           │        │  /complete-payment                               ││
│  │  ┌──────────────────────┐ │        │  /settle-payment                                 ││
│  │  │External:             │ │        │  /void-payment, /refund-payment                  ││
│  │  │• Cardless Issuer Conn│ │        │                                                  ││
│  │  │  (pre-eligibility)   │ │        │  ┌──────────────────────────────────────────────┐││
│  │  └──────────────────────┘ │        │  │External Integrations:                        │││
│  └───────────────────────────┘        │  │• ReadServ (EMI calculation)                  │││
│                                        │  │• Velocity Service (rate limiting)            │││
│  ┌───────────────────────────┐        │  │• Credit Limit Service (debit EMI)            │││
│  │   OfferMgmtServ          │        │  │• Cardless Issuer Connector (OTP flow)        │││
│  │  (Offer Administration)   │        │  │• Plural Edge Debit EMI Service               │││
│  │                           │        │  │• Product Validation (OEM - Apple)             │││
│  │  /offers (CRUD + states)  │        │  │• OMS (settlement instruction)                │││
│  │  /campaigns (management)  │        │  │• HSM (card encryption via Thrift)            │││
│  │  /budgets (tracking)      │        │  │• Kafka (settlement events)                   │││
│  │  /velocity-rules          │        │  └──────────────────────────────────────────────┘││
│  │  /clients, /issuers       │        └─────────────────────────────────────────────────┘│
│  │                           │                                                            │
│  │  ┌──────────────────────┐ │        ┌─────────────────────────────────────────────────┐│
│  │  │External:             │ │        │  CacheManagementServ                            ││
│  │  │• TransactionServ     │ │        │  (Cache Lifecycle)                              ││
│  │  │  (KFS generation)    │ │        │                                                  ││
│  │  │• S3 (bulk files)     │ │        │  Polls: offer_update_events (120s)               ││
│  │  │• Identity (auth)     │ │        │  Invalidates: Redis patterns                     ││
│  │  └──────────────────────┘ │        │  Pre-warms: Hot keys                             ││
│  └───────────────────────────┘        └─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────────────────┘
               │                                      │
               │                                      │
               ▼                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                           CONNECTOR LAYER                                                  │
│                                                                                           │
│  ┌────────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │  BNPL Connector        │  │ NBFC Connector       │  │ Debit EMI Provider Adapter  │  │
│  │  (WebFlux/Reactive)    │  │ (Strategy Pattern)   │  │ (Kotlin/Ktor)               │  │
│  │                        │  │                      │  │                             │  │
│  │  ┌─────────────────┐  │  │  ┌────────────────┐  │  │  ┌───────────────────────┐  │  │
│  │  │ICICI Cardless   │  │  │  │Bajaj Finance   │  │  │  │Standard DC EMI        │  │  │
│  │  │• Pre-eligibility│  │  │  │HDB Financial   │  │  │  │Penny Drop Auth        │  │  │
│  │  │• Eligibility    │  │  │  │Home Credit     │  │  │  │                       │  │  │
│  │  │• OTP validate   │  │  │  │LiquiLoans      │  │  │  │External:              │  │  │
│  │  │• Confirm/Cancel │  │  │  │TVS Credit      │  │  │  │• OMS (order mgmt)     │  │  │
│  │  └─────────────────┘  │  │  └────────────────┘  │  │  │• Acquirer service     │  │  │
│  │  ┌─────────────────┐  │  │                      │  │  │• Gateway adapter      │  │  │
│  │  │LazyPay          │  │  │  Interface:          │  │  └───────────────────────┘  │  │
│  │  │• Eligibility    │  │  │  checkEligibility()  │  │                             │  │
│  │  │• Order create   │  │  │  fetchSchemes()      │  │                             │  │
│  │  │• Refund         │  │  │  generateOtp()       │  │                             │  │
│  │  └─────────────────┘  │  │  submitLoan()        │  │                             │  │
│  └────────────────────────┘  │  cancelLoan()        │  └─────────────────────────────┘  │
│                               │  getStatus()         │                                    │
│                               └──────────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Communication Protocols

| Service Pair | Protocol | Auth | Timeout | Retry | Circuit Breaker |
|---|---|---|---|---|---|
| OfferAdapter → GatewayAdapter | HTTP/REST | JWT forward | 30s | 2 | Yes (200 failures, 10s reset) |
| GatewayAdapter → DiscoveryAdapter | HTTP/REST | Internal token | 15s | 2 | Yes |
| GatewayAdapter → ProcessingAdapter | HTTP/REST | Internal token | 30s | 2 | Yes |
| DiscoveryAdapter → ReadServ | HTTP/REST | OAuth2 client_credentials | 10s | 3 | No |
| ProcessingAdapter → TransactionServ | HTTP/REST | OAuth2 client_credentials | 30s | 2 | No |
| TransactionServ → ReadServ | HTTP/REST | OAuth2 | 10s | 3 | No |
| TransactionServ → Velocity Service | HTTP/REST | OAuth2 | 5s | 2 | No |
| TransactionServ → Credit Limit Service | HTTP/REST | OAuth2 | 10s | 2 | No |
| TransactionServ → Cardless Connector | HTTP/REST | OAuth2 | 10s | 3 | No |
| TransactionServ → OMS | HTTP/REST | OAuth2 | 10s | 2 | No |
| TransactionServ → Kafka | Kafka Producer | IAM (MSK) | 5s dispatch | 3 | No |
| GatewayAdapter ← Kafka | Kafka Consumer | IAM (MSK) | - | auto | No |
| BNPL Connector → ICICI | HTTP/REST | OAuth2 + AES | 30s | 2 | No |
| NBFC Connector → Bajaj/HDB | HTTP/REST | JWT/JWE | 30s | 2 | No |
| TransactionServ → HSM | Thrift RPC | Certificate | 5s | 1 | No |
| CacheManagement → Redis | RESP protocol | Password | 2s | 0 (graceful fail) | No |
| ReadServ → PostgreSQL | JDBC/HikariCP | Password | 10s | 0 | No |

---

## 3. Kafka Topics & Event Schema

### 3.1 Settlement Event Topic

**Topic**: `auth-settlement-request-{env}-v1`

**Producer**: TransactionServ (`KafkaSettlementEventDispatcher`)

**Message Schema**:
```json
{
  "transaction_id": 98765,
  "transaction_amount": 5000000,
  "settlement_amount": 5000000,
  "merchant_id": "MID_001",
  "terminal_id": "TID_001",
  "rrn": "401234567890",
  "auth_code": "123456",
  "acquirer_name": "FIRST_DATA",
  "operation_type": "SALE",
  "settlement_parties": [
    { "party_type": "MERCHANT", "amount": 4700000 },
    { "party_type": "BRAND", "amount": 200000, "type": "SUBVENTION" },
    { "party_type": "ISSUER", "amount": 100000, "type": "SUBVENTION" }
  ]
}
```

**Message Headers**:
| Header | Example Value | Purpose |
|--------|--------------|---------|
| X-source | `AFFORDABILITY` | Source system |
| X-channel | `ONLINE` | Payment channel |
| X-requestType | `SETTLEMENT` | Request type |
| X-requestId | `uuid-v4` | Correlation ID |
| X-operationType | `SALE` / `REFUND` / `VOID` | Operation |
| X-version | `v1` | Schema version |

**Key**: Idempotency key (ensures partition ordering per transaction)

**Configuration**:
```properties
kafka.settlement.enabled=true
kafka.producer.acks=all
kafka.producer.retries=3
kafka.producer.enable.idempotence=true
kafka.topic.settlement=auth-settlement-request-{env}-v1
```

### 3.2 Order Lifecycle Events (Consumer)

**Topic**: Order events from NXT Payment Order Service

**Consumer**: GatewayAdapter (`OfferOrderSyncingService`)

**Purpose**: Sync offer state with order lifecycle (e.g., order cancelled → cancel offer transaction)

---

## 4. Resilience Patterns

### 4.1 Circuit Breaker (Gateway Adapter)

```yaml
# application.yaml (GatewayAdapter)
circuitConfig:
    resetTimeout: 10              # seconds before half-open
    maxFailures: 200              # failures before opening circuit
    exponentialBackoffFactor: 1.2  # backoff multiplier
    maxResetTimeout: 60           # max reset timeout (seconds)
```

**State Machine**:
```
CLOSED → (200 failures) → OPEN → (10s) → HALF_OPEN → (success) → CLOSED
                                         → (failure) → OPEN (12s timeout)
                                                     → OPEN (14.4s timeout)
                                                     → ... (up to 60s max)
```

### 4.2 Graceful Cache Degradation

```java
// RedisCacheService.java
public <T> T get(String key, Class<T> clazz) {
    try {
        byte[] data = redis.get(key);
        return data != null ? decompress(data, clazz) : null;
    } catch (Exception e) {
        // Redis failure → treat as cache miss
        log.warn("Redis GET failed for key={}, treating as miss", key, e);
        return null;  // Fallback to DB
    }
}
```

### 4.3 Distributed Lock with Auto-Release

```java
// CacheService.java
public boolean tryAcquireLock(String lockKey, long ttlInSeconds) {
    return redis.setIfAbsent(lockKey, "LOCKED", Duration.ofSeconds(ttlInSeconds));
    // Auto-expires even if holder crashes
    // Prevents cache stampede during invalidation
}
```

### 4.4 Idempotent Operations

```java
// AffordabilityIdempotencyService.java
public boolean isAlreadyProcessed(String idempotentKey) {
    return idempotentKeyRepo.findByIdempotentKey(idempotentKey).isPresent();
}

// Before processing refund/void:
if (idempotencyService.isAlreadyProcessed(request.getIdempotentKey())) {
    return existingResult;  // Return cached result, don't re-process
}
// Process and save idempotent key atomically
```

### 4.5 Transaction Self-Expiry

```java
// On createPayment():
transaction.setSelfExpiringDateTime(
    new Date(System.currentTimeMillis() + (expirySeconds * 1000))
    // Default: 3600 seconds (1 hour)
);

// Batch job (Affordability_Batchprocessingserv) runs as CronJob:
// - Finds INITIATED transactions past self_expiring_date_time
// - Reverses all blocked resources (velocity, credit limit, IMEI)
// - Updates status to EXPIRED
```

---

## 5. Data Flow Patterns

### 5.1 CQRS (Command Query Responsibility Segregation)

```
┌─────────────────────────────────────────────────────────┐
│                  WRITE PATH (Commands)                    │
│                                                          │
│  [Create/Complete/Settle/Void/Refund Payment]            │
│              │                                           │
│              ▼                                           │
│  TransactionServ → PostgreSQL (Writer Instance)          │
│              │                                           │
│              ▼                                           │
│  offer_update_events table (async event)                 │
│              │                                           │
│              ▼                                           │
│  Kafka (settlement events)                               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  READ PATH (Queries)                      │
│                                                          │
│  [Calculate EMI / Discover Offers]                       │
│              │                                           │
│              ▼                                           │
│  ReadServ → Redis (Layer 2) → In-Memory (Layer 3)       │
│              │ MISS                                       │
│              ▼                                           │
│  CacheManagement → Redis (Layer 4)                       │
│              │ MISS                                       │
│              ▼                                           │
│  PostgreSQL (Read Replicas, round-robin)                  │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Event Sourcing (Offer Changes)

```
[Admin changes offer] 
    → OfferMgmtServ saves to DB
    → Writes OfferUpdateEvent (PENDING)
    → CacheManagementServ polls (120s)
    → Processes event → Invalidates Redis
    → Hot keys pre-warmed
    → Next ReadServ request gets fresh data
    
Eventual consistency window: 0-120 seconds (poll interval)
```

### 5.3 Saga Pattern (Transaction Lifecycle)

```
Forward Flow (createPayment → completePayment):
  Step 1: VelocityCheck → VelocityBlock
  Step 2: CreditLimitCheck → CreditLimitBlock
  Step 3: ProductValidate → ProductBlock (IMEI)
  Step 4: AcquirerAuth → CompletePayment

Compensating Flow (on failure at any step):
  Reverse Step 3: ProductUnblock (IMEI release)
  Reverse Step 2: CreditLimitUnblock
  Reverse Step 1: VelocityUnblock
  
Each task's status is tracked in affordability_transaction_task_details
with status: SUCCESS, FAILED, REVERSED
```

---

## 6. Kubernetes Service Discovery

All services communicate via K8s internal DNS:

```yaml
# Service URLs (production)
affordability-offerdiscoveryadapter.affordability-prod.svc.cluster.local:8080
affordability-offerprocessingadapter.affordability-prod.svc.cluster.local:8081
affordability-gatewayadapter.affordability-prod.svc.cluster.local:8082
readserv.affordability-prod.svc.cluster.local:8080
transaction.affordability-prod.svc.cluster.local:8080
offermgmtserv.affordability-prod.svc.cluster.local:8080

# External services
bin-service-dev.v2.pinepg.in
nxt-customer-vault-mgm-dev.v2.pinepg.in
nxt-order-history-service-dev.v2.pinepg.in
identitytest.pinelabs.com (Keycloak)
```

---

## 7. Monitoring & Observability

### Health Endpoints
```
GET /health/live   → Liveness probe (K8s restarts on failure)
GET /health/ready  → Readiness probe (K8s removes from LB on failure)
GET /metrics       → Prometheus metrics (Micrometer)
```

### Key Metrics Exported
```
# Cache metrics
cache_hit_total{service="readserv", cache="offer_response"}
cache_miss_total{service="readserv", cache="offer_response"}
cache_size_bytes{service="readserv"}

# HTTP metrics
http_server_requests_seconds{method="POST", uri="/v1/affordability/calculate-emi", status="200"}
http_client_requests_seconds{target="transaction-serv", status="200"}

# DB metrics
hikaricp_connections_active{pool="reader"}
hikaricp_connections_idle{pool="reader"}

# Custom business metrics
affordability_transactions_total{status="APPROVED", program_type="BANK_EMI"}
affordability_offers_active_total{program_type="BRAND_EMI"}
affordability_budget_consumed_ratio{campaign_id="123"}
```

### Structured Logging Format
```json
{
  "timestamp": "2024-03-15T10:30:00.000Z",
  "level": "INFO",
  "service": "affordability-readserv",
  "traceId": "abc123def456",
  "spanId": "span789",
  "method": "calculateEmi",
  "duration_ms": 45,
  "cache_hit": true,
  "client_id": "MERCHANT_001",
  "program_type": "BANK_EMI"
}
```
