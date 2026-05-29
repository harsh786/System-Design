# Payment Gateway (Stripe-like) — System Design

## 1. Functional Requirements

1. **Merchant Onboarding**: KYC/KYB verification, API key issuance, webhook configuration
2. **Payment Intent Creation**: Create payment intents with amount, currency, metadata
3. **Multi-PSP Routing**: Intelligent routing across Visa/Mastercard/Amex processors
4. **Card Tokenization**: PCI-DSS Level 1 compliant vault for card data
5. **3DS Authentication**: SCA/3D Secure flows for strong authentication
6. **Webhook Notifications**: Event-driven notifications for payment lifecycle events
7. **Idempotency**: Exactly-once payment processing with idempotency keys
8. **Retry with Exponential Backoff**: Automatic retries on transient PSP failures
9. **Refunds**: Full/partial refunds with reason tracking
10. **Disputes/Chargebacks**: Dispute lifecycle management, evidence submission
11. **Multi-Currency**: 135+ currencies with real-time FX rates
12. **Settlement**: Batch settlement with merchant payout scheduling

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.999% (5 nines) — financial SLA |
| Latency (p99) | < 2s end-to-end payment, < 100ms API response |
| Throughput | 50,000 TPS peak (Black Friday) |
| Durability | Zero payment loss — exactly-once semantics |
| Compliance | PCI-DSS Level 1, SOC 2 Type II, GDPR |
| RPO/RTO | RPO=0 (synchronous replication), RTO < 30s |
| Idempotency Window | 48 hours |
| Webhook Delivery | At-least-once with 72hr retry window |

## 3. Capacity Estimation

```
Daily transactions: 100M
Average payload: 2KB per transaction
Daily data ingestion: 100M × 2KB = 200GB/day
Storage (1 year): 200GB × 365 = 73TB (raw)
Peak TPS: 50,000 (3x average during peaks)
Average TPS: ~1,150

Tokenization vault:
- 500M unique cards stored
- 256-byte token record → 128GB
- HSM operations: 50K/sec encrypt/decrypt

Webhook delivery:
- 3 events per payment average → 300M events/day
- Average payload: 1KB → 300GB/day outbound

Settlement batches:
- 10M merchants, daily settlement
- Average 10 transactions per merchant per batch
```

## 4. Data Modeling — Full Schemas

```sql
-- Core Payment Schema
CREATE TABLE merchants (
    merchant_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name       VARCHAR(255) NOT NULL,
    legal_entity_name   VARCHAR(255) NOT NULL,
    tax_id              VARCHAR(50),
    country_code        CHAR(2) NOT NULL,
    mcc_code            CHAR(4) NOT NULL,  -- Merchant Category Code
    kyb_status          VARCHAR(20) DEFAULT 'pending', -- pending/verified/rejected
    risk_tier           VARCHAR(10) DEFAULT 'standard', -- low/standard/high
    settlement_currency CHAR(3) NOT NULL DEFAULT 'USD',
    settlement_schedule VARCHAR(20) DEFAULT 'T+2',
    webhook_url         TEXT,
    webhook_secret      VARCHAR(64),
    api_key_hash        VARCHAR(128) NOT NULL,
    api_key_prefix      VARCHAR(8) NOT NULL,  -- pk_live_xxxx
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_merchants_api_prefix ON merchants(api_key_prefix);
CREATE INDEX idx_merchants_country ON merchants(country_code);

CREATE TABLE payment_intents (
    payment_intent_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         UUID NOT NULL REFERENCES merchants(merchant_id),
    idempotency_key     VARCHAR(255),
    amount              BIGINT NOT NULL,          -- in smallest currency unit (cents)
    currency            CHAR(3) NOT NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'requires_payment_method',
    -- statuses: requires_payment_method, requires_confirmation, requires_action,
    --           processing, requires_capture, succeeded, canceled, failed
    capture_method      VARCHAR(10) DEFAULT 'automatic', -- automatic/manual
    payment_method_id   UUID,
    customer_id         UUID,
    description         TEXT,
    statement_descriptor VARCHAR(22),
    metadata            JSONB DEFAULT '{}',
    client_secret       VARCHAR(64) NOT NULL,
    cancellation_reason VARCHAR(50),
    last_payment_error  JSONB,
    next_action         JSONB,  -- 3DS redirect, etc.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ,
    UNIQUE(merchant_id, idempotency_key)
);
CREATE INDEX idx_pi_merchant_status ON payment_intents(merchant_id, status);
CREATE INDEX idx_pi_created ON payment_intents(created_at);
CREATE INDEX idx_pi_customer ON payment_intents(customer_id);

CREATE TABLE payment_methods (
    payment_method_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID,
    type                VARCHAR(20) NOT NULL,  -- card, bank_transfer, wallet
    card_token_id       UUID,                  -- reference to tokenization vault
    card_brand          VARCHAR(20),           -- visa, mastercard, amex
    card_last4          CHAR(4),
    card_exp_month      SMALLINT,
    card_exp_year       SMALLINT,
    card_fingerprint    VARCHAR(64),           -- for dedup across merchants
    billing_address     JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pm_customer ON payment_methods(customer_id);
CREATE INDEX idx_pm_fingerprint ON payment_methods(card_fingerprint);

CREATE TABLE charges (
    charge_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_intent_id   UUID NOT NULL REFERENCES payment_intents(payment_intent_id),
    merchant_id         UUID NOT NULL,
    amount              BIGINT NOT NULL,
    currency            CHAR(3) NOT NULL,
    status              VARCHAR(20) NOT NULL,  -- pending, succeeded, failed
    psp_id              VARCHAR(50) NOT NULL,  -- which PSP processed this
    psp_reference       VARCHAR(255),          -- PSP's transaction ID
    psp_response_code   VARCHAR(10),
    auth_code           VARCHAR(20),
    risk_score          DECIMAL(5,4),
    three_ds_result     VARCHAR(20),           -- authenticated, attempted, failed
    failure_code        VARCHAR(50),
    failure_message     TEXT,
    captured            BOOLEAN DEFAULT FALSE,
    captured_at         TIMESTAMPTZ,
    refunded_amount     BIGINT DEFAULT 0,
    disputed            BOOLEAN DEFAULT FALSE,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_charges_pi ON charges(payment_intent_id);
CREATE INDEX idx_charges_psp_ref ON charges(psp_id, psp_reference);
CREATE INDEX idx_charges_merchant_created ON charges(merchant_id, created_at);

CREATE TABLE refunds (
    refund_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    charge_id           UUID NOT NULL REFERENCES charges(charge_id),
    payment_intent_id   UUID NOT NULL,
    merchant_id         UUID NOT NULL,
    amount              BIGINT NOT NULL,
    currency            CHAR(3) NOT NULL,
    status              VARCHAR(20) NOT NULL,  -- pending, succeeded, failed
    reason              VARCHAR(50),           -- duplicate, fraudulent, requested_by_customer
    psp_refund_ref      VARCHAR(255),
    failure_reason      VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refunds_charge ON refunds(charge_id);

CREATE TABLE disputes (
    dispute_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    charge_id           UUID NOT NULL REFERENCES charges(charge_id),
    merchant_id         UUID NOT NULL,
    amount              BIGINT NOT NULL,
    currency            CHAR(3) NOT NULL,
    reason              VARCHAR(50) NOT NULL,  -- fraudulent, product_not_received, etc.
    status              VARCHAR(30) NOT NULL,  -- needs_response, under_review, won, lost
    evidence_due_by     TIMESTAMPTZ,
    network_reason_code VARCHAR(10),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_disputes_merchant_status ON disputes(merchant_id, status);

-- Double-Entry Ledger
CREATE TABLE ledger_entries (
    entry_id            BIGSERIAL PRIMARY KEY,
    journal_id          UUID NOT NULL,
    account_id          UUID NOT NULL,
    entry_type          CHAR(1) NOT NULL,  -- 'D' debit, 'C' credit
    amount              BIGINT NOT NULL,
    currency            CHAR(3) NOT NULL,
    reference_type      VARCHAR(30) NOT NULL,  -- charge, refund, settlement, fee
    reference_id        UUID NOT NULL,
    description         TEXT,
    posted_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ledger_account ON ledger_entries(account_id, posted_at);
CREATE INDEX idx_ledger_journal ON ledger_entries(journal_id);
CREATE INDEX idx_ledger_reference ON ledger_entries(reference_type, reference_id);

CREATE TABLE ledger_accounts (
    account_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_type        VARCHAR(20) NOT NULL,  -- asset, liability, revenue, expense
    account_name        VARCHAR(100) NOT NULL,
    currency            CHAR(3) NOT NULL,
    balance             BIGINT NOT NULL DEFAULT 0,
    merchant_id         UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tokenization Vault (separate PCI-scoped database)
CREATE TABLE card_tokens (
    token_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    encrypted_pan       BYTEA NOT NULL,        -- AES-256-GCM encrypted
    key_id              VARCHAR(36) NOT NULL,   -- HSM key reference
    pan_hash            VARCHAR(64) NOT NULL,   -- SHA-256 for dedup
    exp_month           SMALLINT NOT NULL,
    exp_year            SMALLINT NOT NULL,
    card_brand          VARCHAR(20) NOT NULL,
    last4               CHAR(4) NOT NULL,
    issuer_country      CHAR(2),
    bin                 CHAR(6),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tokens_pan_hash ON card_tokens(pan_hash);

-- Webhook Events
CREATE TABLE webhook_events (
    event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id         UUID NOT NULL,
    event_type          VARCHAR(50) NOT NULL,
    payload             JSONB NOT NULL,
    delivery_status     VARCHAR(20) DEFAULT 'pending',
    attempts            SMALLINT DEFAULT 0,
    next_retry_at       TIMESTAMPTZ,
    last_response_code  SMALLINT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_webhooks_pending ON webhook_events(delivery_status, next_retry_at)
    WHERE delivery_status = 'pending';

-- PSP Routing Configuration
CREATE TABLE psp_configurations (
    psp_id              VARCHAR(50) PRIMARY KEY,
    psp_name            VARCHAR(100) NOT NULL,
    supported_currencies CHAR(3)[] NOT NULL,
    supported_card_brands VARCHAR(20)[] NOT NULL,
    supported_countries CHAR(2)[],
    base_fee_bps        DECIMAL(5,2) NOT NULL,  -- basis points
    per_txn_fee_cents   INTEGER NOT NULL,
    success_rate_30d    DECIMAL(5,4) DEFAULT 0.95,
    avg_latency_ms      INTEGER DEFAULT 500,
    circuit_state       VARCHAR(10) DEFAULT 'closed', -- closed, open, half_open
    circuit_opened_at   TIMESTAMPTZ,
    weight              INTEGER DEFAULT 100,
    is_active           BOOLEAN DEFAULT TRUE
);

-- Idempotency Store
CREATE TABLE idempotency_keys (
    key_hash            VARCHAR(64) PRIMARY KEY,
    merchant_id         UUID NOT NULL,
    request_path        VARCHAR(255) NOT NULL,
    request_body_hash   VARCHAR(64) NOT NULL,
    response_code       SMALLINT,
    response_body       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '48 hours'
);
CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);
```

## 5. High-Level Design — ASCII Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PAYMENT GATEWAY ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────────┐
    │ Merchant │     │ Mobile   │     │ Checkout.js  │
    │ Backend  │     │ SDK      │     │ (PCI iframe) │
    └────┬─────┘     └────┬─────┘     └──────┬───────┘
         │                 │                   │
         └────────────┬────┴───────────────────┘
                      │ HTTPS/TLS 1.3
                      ▼
         ┌────────────────────────────┐
         │      CloudFlare / WAF      │
         │   (DDoS, Rate Limiting)    │
         └─────────────┬──────────────┘
                       │
                       ▼
         ┌────────────────────────────┐
         │     API Gateway (Kong)     │
         │  Auth │ Rate Limit │ Route │
         └─────────────┬──────────────┘
                       │
         ┌─────────────┼──────────────────────────────┐
         │             │                              │
         ▼             ▼                              ▼
┌─────────────┐ ┌──────────────┐           ┌─────────────────┐
│  Payment    │ │  Merchant    │           │  Webhook        │
│  Service    │ │  Service     │           │  Delivery Svc   │
│             │ │  (Onboard)   │           │  (async)        │
└──────┬──────┘ └──────────────┘           └────────┬────────┘
       │                                            │
       ├──────────────┬────────────────┐            │
       │              │                │            │
       ▼              ▼                ▼            ▼
┌────────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────┐
│ Idempotency│ │ Tokenize   │ │ 3DS Service │ │  Kafka   │
│ Service    │ │ Service    │ │ (SCA)       │ │ (Events) │
│ (Redis+PG) │ │ (PCI Vault)│ │             │ │          │
└────────────┘ └─────┬──────┘ └─────────────┘ └──────────┘
                     │                              │
                     ▼                              │
              ┌────────────┐                        │
              │    HSM      │                       │
              │ (Thales/AWS │                       │
              │  CloudHSM)  │                       │
              └────────────┘                        │
       │                                            │
       ▼                                            │
┌──────────────────────────────┐                    │
│     Payment Orchestrator     │◄───────────────────┘
│  (Routing + Retry + Circuit) │
└──────────────┬───────────────┘
               │
    ┌──────────┼──────────┬───────────┐
    │          │          │           │
    ▼          ▼          ▼           ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌──────────┐
│ Visa  │ │Master │ │ Adyen │ │Checkout  │
│Direct │ │card   │ │       │ │.com      │
│(PSP 1)│ │(PSP 2)│ │(PSP 3)│ │(PSP 4)  │
└───────┘ └───────┘ └───────┘ └──────────┘

       │
       ▼
┌──────────────────────────────┐
│    Double-Entry Ledger       │
│  (PostgreSQL + TimescaleDB)  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│    Settlement Engine         │
│  (Daily batch + Payouts)     │
└──────────────────────────────┘
```

## 6. Low-Level Design — APIs

### Payment Intent API

```http
POST /v1/payment_intents
Authorization: Bearer sk_live_xxxxxxxxxxxx
Idempotency-Key: pi_unique_key_12345
Content-Type: application/json

{
  "amount": 5000,
  "currency": "usd",
  "payment_method_types": ["card"],
  "capture_method": "automatic",
  "metadata": {
    "order_id": "ord_123456"
  },
  "statement_descriptor": "ACME CORP"
}
```

**Response (201 Created):**
```json
{
  "id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
  "object": "payment_intent",
  "amount": 5000,
  "currency": "usd",
  "status": "requires_payment_method",
  "client_secret": "pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_YrKJUKribcBjcG8HVhfZluoGH",
  "created": 1680000000,
  "livemode": true,
  "metadata": {"order_id": "ord_123456"}
}
```

### Confirm Payment Intent

```http
POST /v1/payment_intents/pi_3MtwBwLkdIwHu7ix28a3tqPa/confirm
Authorization: Bearer sk_live_xxxxxxxxxxxx

{
  "payment_method": "pm_card_visa",
  "return_url": "https://merchant.com/return"
}
```

**Response (200 - Requires 3DS):**
```json
{
  "id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
  "status": "requires_action",
  "next_action": {
    "type": "redirect_to_url",
    "redirect_to_url": {
      "url": "https://hooks.stripe.com/3d_secure_2/authenticate/...",
      "return_url": "https://merchant.com/return"
    }
  }
}
```

### Refund API

```http
POST /v1/refunds
Authorization: Bearer sk_live_xxxxxxxxxxxx
Idempotency-Key: refund_unique_key_789

{
  "payment_intent": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
  "amount": 2500,
  "reason": "requested_by_customer"
}
```

### Webhook Event Payload

```json
{
  "id": "evt_1NB8fMLkdIwHu7ixEpTBGy0B",
  "object": "event",
  "type": "payment_intent.succeeded",
  "created": 1680000300,
  "data": {
    "object": {
      "id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
      "amount": 5000,
      "currency": "usd",
      "status": "succeeded",
      "charges": {
        "data": [{
          "id": "ch_3MtwBwLkdIwHu7ix0Dv23oIi",
          "amount": 5000,
          "paid": true
        }]
      }
    }
  }
}
```

### PSP Routing Algorithm (Code)

```python
import random
from dataclasses import dataclass
from typing import List, Optional
import time

@dataclass
class PSPConfig:
    psp_id: str
    success_rate: float      # 30-day rolling
    avg_latency_ms: int
    cost_bps: float          # basis points
    supported_currencies: set
    supported_brands: set
    supported_countries: set
    circuit_state: str       # closed, open, half_open
    circuit_opened_at: float
    weight: int

class PaymentOrchestrator:
    CIRCUIT_OPEN_DURATION = 30  # seconds
    HALF_OPEN_TRIAL_RATE = 0.1  # 10% traffic in half-open

    def __init__(self, psps: List[PSPConfig]):
        self.psps = {p.psp_id: p for p in psps}
        self.failure_counts = {}  # psp_id -> consecutive failures
        self.FAILURE_THRESHOLD = 5

    def select_psp(self, currency: str, card_brand: str,
                   country: str, amount: int) -> Optional[PSPConfig]:
        """Intelligent PSP routing based on multi-factor scoring."""
        candidates = []
        for psp in self.psps.values():
            # Filter by capability
            if currency not in psp.supported_currencies:
                continue
            if card_brand not in psp.supported_brands:
                continue
            if country and psp.supported_countries and country not in psp.supported_countries:
                continue
            # Circuit breaker check
            if not self._is_psp_available(psp):
                continue
            candidates.append(psp)

        if not candidates:
            return None

        # Score each PSP (higher is better)
        scored = []
        for psp in candidates:
            score = self._calculate_score(psp, amount)
            scored.append((score, psp))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Weighted random selection from top 3 (avoids thundering herd)
        top_n = scored[:3]
        total_score = sum(s for s, _ in top_n)
        r = random.uniform(0, total_score)
        cumulative = 0
        for score, psp in top_n:
            cumulative += score
            if r <= cumulative:
                return psp
        return top_n[0][1]

    def _calculate_score(self, psp: PSPConfig, amount: int) -> float:
        """Multi-factor score: success_rate (60%) + cost (25%) + latency (15%)."""
        success_score = psp.success_rate * 60
        # Normalize cost: lower is better (invert)
        cost_score = (1 - psp.cost_bps / 300) * 25  # 300bps as max
        # Normalize latency: lower is better (invert)
        latency_score = (1 - psp.avg_latency_ms / 3000) * 15
        return success_score + cost_score + latency_score

    def _is_psp_available(self, psp: PSPConfig) -> bool:
        if psp.circuit_state == 'closed':
            return True
        if psp.circuit_state == 'open':
            if time.time() - psp.circuit_opened_at > self.CIRCUIT_OPEN_DURATION:
                psp.circuit_state = 'half_open'
                return random.random() < self.HALF_OPEN_TRIAL_RATE
            return False
        if psp.circuit_state == 'half_open':
            return random.random() < self.HALF_OPEN_TRIAL_RATE
        return False

    def record_outcome(self, psp_id: str, success: bool):
        """Update circuit breaker state based on outcome."""
        psp = self.psps[psp_id]
        if success:
            self.failure_counts[psp_id] = 0
            if psp.circuit_state == 'half_open':
                psp.circuit_state = 'closed'
        else:
            count = self.failure_counts.get(psp_id, 0) + 1
            self.failure_counts[psp_id] = count
            if count >= self.FAILURE_THRESHOLD:
                psp.circuit_state = 'open'
                psp.circuit_opened_at = time.time()
```

### Idempotency Implementation

```python
import hashlib
import json
from redis import Redis
from datetime import timedelta

class IdempotencyService:
    LOCK_TTL = timedelta(seconds=30)
    KEY_TTL = timedelta(hours=48)

    def __init__(self, redis: Redis, db_session):
        self.redis = redis
        self.db = db_session

    async def check_or_lock(self, merchant_id: str, idempotency_key: str,
                            request_body: dict) -> tuple:
        """
        Returns (is_duplicate, cached_response_or_None).
        If not duplicate, acquires a lock for processing.
        """
        key_hash = self._hash_key(merchant_id, idempotency_key)
        body_hash = hashlib.sha256(
            json.dumps(request_body, sort_keys=True).encode()
        ).hexdigest()

        # Phase 1: Redis fast-path check
        cached = self.redis.get(f"idemp:{key_hash}")
        if cached:
            cached_data = json.loads(cached)
            # Verify request body matches (detect misuse)
            if cached_data['body_hash'] != body_hash:
                raise IdempotencyKeyReusedError(
                    "Idempotency key reused with different request body"
                )
            if cached_data.get('response'):
                return True, cached_data['response']
            # Still processing — return 409
            raise RequestInProgressError()

        # Phase 2: Acquire distributed lock
        lock_key = f"idemp_lock:{key_hash}"
        acquired = self.redis.set(lock_key, "1", nx=True,
                                   ex=int(self.LOCK_TTL.total_seconds()))
        if not acquired:
            raise RequestInProgressError()

        # Phase 3: Store placeholder in Redis + DB
        placeholder = {'body_hash': body_hash, 'response': None}
        self.redis.setex(f"idemp:{key_hash}",
                        int(self.KEY_TTL.total_seconds()),
                        json.dumps(placeholder))

        return False, None

    async def store_response(self, merchant_id: str, idempotency_key: str,
                            response_code: int, response_body: dict):
        """Store the completed response for future duplicate requests."""
        key_hash = self._hash_key(merchant_id, idempotency_key)
        data = {
            'body_hash': self.redis.get(f"idemp:{key_hash}"),
            'response': {'code': response_code, 'body': response_body}
        }
        # Update Redis
        self.redis.setex(f"idemp:{key_hash}",
                        int(self.KEY_TTL.total_seconds()),
                        json.dumps(data))
        # Persist to DB for durability
        await self.db.execute("""
            INSERT INTO idempotency_keys (key_hash, merchant_id, response_code, response_body)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (key_hash) DO UPDATE SET response_code=$3, response_body=$4
        """, key_hash, merchant_id, response_code, json.dumps(response_body))

        # Release lock
        self.redis.delete(f"idemp_lock:{key_hash}")

    def _hash_key(self, merchant_id: str, key: str) -> str:
        return hashlib.sha256(f"{merchant_id}:{key}".encode()).hexdigest()
```

## 7. Deep Dives

### Deep Dive 1: Payment Orchestration — Intelligent Routing

**Problem**: Different PSPs have varying success rates, costs, and geographic strengths. Static routing leaves money on the table.

**Architecture**:
```
┌─────────────────────────────────────────────┐
│           Payment Orchestrator              │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────┐    ┌──────────────────┐   │
│  │ Eligibility │───▶│  Scoring Engine   │   │
│  │   Filter    │    │                  │   │
│  └─────────────┘    │ success_rate×0.6 │   │
│                      │ cost×0.25       │   │
│                      │ latency×0.15    │   │
│                      └────────┬─────────┘   │
│                               │             │
│  ┌────────────────────────────▼──────────┐  │
│  │         Weighted Selection            │  │
│  │  (top-3 with proportional sampling)   │  │
│  └────────────────────────────┬──────────┘  │
│                               │             │
│  ┌────────────────────────────▼──────────┐  │
│  │         Circuit Breaker               │  │
│  │  closed ──▶ open (5 fails) ──▶ half   │  │
│  │  half_open ──▶ closed (1 success)     │  │
│  └────────────────────────────┬──────────┘  │
│                               │             │
│  ┌────────────────────────────▼──────────┐  │
│  │         Retry Manager                 │  │
│  │  Attempt 1: Primary PSP              │  │
│  │  Attempt 2: Secondary PSP (failover) │  │
│  │  Attempt 3: Tertiary PSP             │  │
│  │  Backoff: 100ms, 500ms, 2000ms       │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**Failover Logic**:
```python
async def process_payment_with_retry(self, payment_intent, max_attempts=3):
    attempted_psps = set()
    last_error = None

    for attempt in range(max_attempts):
        psp = self.select_psp(
            currency=payment_intent.currency,
            card_brand=payment_intent.card_brand,
            country=payment_intent.country,
            amount=payment_intent.amount,
            exclude=attempted_psps
        )
        if not psp:
            break

        attempted_psps.add(psp.psp_id)
        try:
            result = await self._call_psp(psp, payment_intent, timeout=5.0)
            self.record_outcome(psp.psp_id, success=True)
            return result
        except (PSPTimeoutError, PSPUnavailableError) as e:
            last_error = e
            self.record_outcome(psp.psp_id, success=False)
            # Exponential backoff before next attempt
            await asyncio.sleep(0.1 * (2 ** attempt))
        except PSPDeclinedError as e:
            # Hard decline — don't retry
            self.record_outcome(psp.psp_id, success=True)  # PSP worked, card declined
            raise e

    raise PaymentProcessingError(f"All PSPs failed: {last_error}")
```

**Success Rate Tracking** (Sliding window with Redis):
```python
def update_success_rate(self, psp_id: str, success: bool):
    """Maintain 30-day rolling success rate using Redis sorted sets."""
    now = time.time()
    key = f"psp_metrics:{psp_id}"
    # Add outcome (1=success, 0=failure) with timestamp as score
    self.redis.zadd(key, {f"{now}:{1 if success else 0}": now})
    # Remove entries older than 30 days
    cutoff = now - 86400 * 30
    self.redis.zremrangebyscore(key, 0, cutoff)
    # Calculate rate
    all_entries = self.redis.zrange(key, 0, -1)
    successes = sum(1 for e in all_entries if e.decode().endswith(':1'))
    total = len(all_entries)
    rate = successes / total if total > 0 else 0.95
    # Update PSP config
    self.redis.hset(f"psp_config:{psp_id}", "success_rate_30d", rate)
```

### Deep Dive 2: Idempotency and Exactly-Once Semantics

**Problem**: Network timeouts create ambiguity — did the payment succeed or not?

**Multi-Layer Idempotency Architecture**:

```
Request Flow:
─────────────

Client ──▶ [Idempotency-Key header]
              │
              ▼
    ┌─────────────────────────┐
    │  Layer 1: Redis Dedup   │  ◀── Fast path (sub-ms)
    │  Key: hash(merchant+key)│      TTL: 48h
    │  Value: {state, response}│
    └────────────┬────────────┘
                 │ Miss
                 ▼
    ┌─────────────────────────┐
    │  Layer 2: DB Constraint │  ◀── Durable (UNIQUE constraint)
    │  UNIQUE(merchant_id,    │      Prevents race conditions
    │         idempotency_key)│
    └────────────┬────────────┘
                 │ New request
                 ▼
    ┌─────────────────────────┐
    │  Layer 3: Distributed   │  ◀── Prevents concurrent
    │  Lock (Redis SETNX)     │      duplicate processing
    │  TTL: 30s               │
    └────────────┬────────────┘
                 │ Lock acquired
                 ▼
    ┌─────────────────────────┐
    │  Process Payment        │
    │  Store result atomically│
    └─────────────────────────┘
```

**Timeout Ambiguity Resolution** (Reconciliation):
```python
class ReconciliationWorker:
    """
    Handles payments stuck in 'processing' state due to timeouts.
    Runs every 5 minutes.
    """
    async def reconcile_stuck_payments(self):
        stuck = await self.db.fetch("""
            SELECT * FROM charges
            WHERE status = 'pending'
            AND created_at < NOW() - INTERVAL '5 minutes'
        """)
        for charge in stuck:
            # Query PSP for actual status
            psp_status = await self.query_psp_status(
                charge.psp_id, charge.psp_reference
            )
            if psp_status == 'succeeded':
                await self.mark_succeeded(charge)
            elif psp_status == 'failed':
                await self.mark_failed(charge)
            elif psp_status == 'not_found':
                # Payment never reached PSP — safe to retry or fail
                await self.mark_failed(charge)
            # else: still processing at PSP, check again later
```

### Deep Dive 3: Double-Entry Ledger for Fund Flow

**Principle**: Every money movement creates exactly two entries (debit + credit) that sum to zero.

**Account Structure**:
```
Chart of Accounts:
├── ASSETS
│   ├── psp_receivable_{psp_id}     (money owed by PSP to us)
│   ├── merchant_reserve_{merchant}  (held funds)
│   └── bank_account                 (our bank)
├── LIABILITIES
│   ├── merchant_payable_{merchant}  (money owed to merchant)
│   └── refund_payable               (pending refunds)
└── REVENUE
    ├── processing_fees              (our revenue)
    └── fx_markup                    (FX spread revenue)
```

**Payment Lifecycle Journal Entries**:
```
Event: Customer pays $100 to merchant (2.9% + $0.30 fee)
─────────────────────────────────────────────────────────
Journal 1 (Payment Captured):
  DR  psp_receivable_visa       $100.00    (PSP owes us)
  CR  merchant_payable_acme      $96.80    (we owe merchant)
  CR  processing_fees             $3.20    (our revenue)

Journal 2 (PSP Settlement - money arrives):
  DR  bank_account              $100.00    (cash in)
  CR  psp_receivable_visa       $100.00    (PSP debt cleared)

Journal 3 (Merchant Payout):
  DR  merchant_payable_acme      $96.80    (debt cleared)
  CR  bank_account               $96.80    (cash out)

Event: Partial refund of $50
─────────────────────────────────
Journal 4 (Refund Issued):
  DR  merchant_payable_acme      $50.00    (reduce what we owe)
  CR  refund_payable             $50.00    (we owe customer)

Journal 5 (Refund Settled):
  DR  refund_payable             $50.00
  CR  bank_account               $50.00    (cash out to customer)
```

```python
class LedgerService:
    async def record_payment(self, charge):
        fee = self.calculate_fee(charge.amount, charge.merchant.fee_rate)
        net = charge.amount - fee

        journal_id = uuid4()
        entries = [
            LedgerEntry(
                journal_id=journal_id,
                account_id=f"psp_receivable_{charge.psp_id}",
                entry_type='D', amount=charge.amount,
                currency=charge.currency,
                reference_type='charge', reference_id=charge.charge_id
            ),
            LedgerEntry(
                journal_id=journal_id,
                account_id=f"merchant_payable_{charge.merchant_id}",
                entry_type='C', amount=net,
                currency=charge.currency,
                reference_type='charge', reference_id=charge.charge_id
            ),
            LedgerEntry(
                journal_id=journal_id,
                account_id="processing_fees",
                entry_type='C', amount=fee,
                currency=charge.currency,
                reference_type='charge', reference_id=charge.charge_id
            ),
        ]
        # Atomic insert — all entries or none
        await self.db.execute_batch(
            "INSERT INTO ledger_entries (...) VALUES (...)", entries
        )
        # Invariant check: sum of debits == sum of credits
        assert sum(e.amount for e in entries if e.entry_type == 'D') == \
               sum(e.amount for e in entries if e.entry_type == 'C')
```

## 8. Component Optimization

### Redis Configuration
```yaml
# Redis Cluster for Idempotency + Rate Limiting
redis:
  cluster:
    nodes: 6 (3 masters + 3 replicas)
    slots_per_node: ~5461
  maxmemory: 64GB per node
  maxmemory-policy: volatile-ttl
  persistence: AOF (appendfsync everysec)
  tcp-keepalive: 60
  timeout: 300
```

### Kafka Configuration
```yaml
# Payment Events Topic
kafka:
  topics:
    payment.events:
      partitions: 64
      replication_factor: 3
      retention_ms: 604800000  # 7 days
      min.insync.replicas: 2
      cleanup.policy: delete
    payment.deadletter:
      partitions: 8
      retention_ms: 2592000000  # 30 days
  producer:
    acks: all
    retries: 3
    enable.idempotence: true
    max.in.flight.requests.per.connection: 5
  consumer:
    group_id: webhook-delivery-group
    auto.offset.reset: earliest
    enable.auto.commit: false
    max.poll.records: 100
```

### Database Optimization
```sql
-- Partition charges table by month
CREATE TABLE charges (
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE charges_2024_01 PARTITION OF charges
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Connection pooling: PgBouncer
-- Pool mode: transaction
-- Default pool size: 100
-- Max client connections: 10000
```

## 9. Observability

### Key Metrics (Prometheus)
```yaml
metrics:
  - payment_intent_created_total{merchant, currency}
  - payment_processed_total{psp, status, card_brand}
  - payment_processing_duration_seconds{psp, outcome}  # histogram
  - psp_success_rate{psp_id}  # gauge, 30-day rolling
  - psp_circuit_state{psp_id}  # 0=closed, 1=open, 2=half_open
  - idempotency_hit_total{type}  # cache_hit, db_hit, miss
  - webhook_delivery_total{status}
  - webhook_delivery_latency_seconds  # histogram
  - refund_total{reason, status}
  - dispute_total{reason, outcome}
  - settlement_batch_amount{currency}
  - tokenization_operations_total{operation}  # encrypt, decrypt

alerts:
  - alert: PSPSuccessRateLow
    expr: psp_success_rate < 0.90
    for: 5m
  - alert: PaymentLatencyHigh
    expr: histogram_quantile(0.99, payment_processing_duration_seconds) > 5
    for: 2m
  - alert: CircuitBreakerOpen
    expr: psp_circuit_state == 1
    for: 0m  # immediate
```

### Distributed Tracing
```
Trace: Payment Intent Confirmation
├── api-gateway (2ms)
├── auth-service.validate-api-key (1ms)
├── idempotency-service.check (3ms)
│   └── redis.get (0.5ms)
├── payment-service.confirm (1800ms)
│   ├── tokenize-service.detokenize (15ms)
│   │   └── hsm.decrypt (8ms)
│   ├── risk-service.score (50ms)
│   ├── orchestrator.route (1ms)
│   ├── psp-adapter.authorize (1500ms)  ◀── PSP network call
│   ├── ledger-service.record (20ms)
│   └── db.update-status (5ms)
├── kafka.produce-event (3ms)
└── idempotency-service.store-response (2ms)
```

## 10. Considerations

### PCI-DSS Compliance
- Card data never touches application servers — collected via iframe/SDK
- Tokenization vault in isolated network segment (CDE)
- HSM for all encryption key operations
- Quarterly vulnerability scans, annual penetration testing
- 90-day log retention for all CDE access

### Failure Modes
| Failure | Impact | Mitigation |
|---------|--------|------------|
| PSP timeout | Payment stuck | Reconciliation worker + failover PSP |
| Redis down | Idempotency degraded | Fall through to DB constraint |
| Kafka down | Webhooks delayed | Write-ahead to DB, process from DB |
| DB failover | Brief unavailability | Synchronous replica promotion < 30s |
| HSM failure | Can't tokenize | HSM cluster with N+1 redundancy |

### Multi-Currency Settlement
```python
# FX rate locked at payment time, settled in merchant's currency
class FXService:
    def convert(self, amount: int, from_ccy: str, to_ccy: str) -> int:
        rate = self.get_rate(from_ccy, to_ccy)  # from ECB/Reuters
        markup = 0.01  # 1% spread (revenue)
        effective_rate = rate * (1 + markup) if from_ccy != to_ccy else 1
        return int(amount * effective_rate)
```

### Scalability Path
- **Horizontal**: Stateless services behind load balancer
- **Database**: Sharding by merchant_id (Citus/Vitess)
- **Read replicas**: For reporting/analytics queries
- **Event sourcing**: Payment events as source of truth, projections for read models
- **Geographic**: Multi-region active-active with conflict-free payment IDs (UUIDv7)
