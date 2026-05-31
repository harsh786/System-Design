# Affordability Platform - API Reference & State Machine

## 1. API Gateway Hierarchy

```
External Clients (Merchants, NXT Checkout, POS)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Offer Adapter (/api/affordability/v1 & /v2)        │  ← Merchant-facing
│  Port 8083 | Auth: JWT Bearer Token                 │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  Gateway Adapter (/api/affordability/v1)            │  ← Central router
│  Port 8082 | Internal service-to-service            │
└───────────┬─────────────────────┬───────────────────┘
            │                     │
            ▼                     ▼
┌───────────────────┐   ┌────────────────────────────┐
│ Discovery Adapter │   │ Processing Adapter          │
│ Port 8080         │   │ Port 8081                   │
└─────────┬─────────┘   └──────────────┬─────────────┘
          │                            │
          ▼                            ▼
┌───────────────────┐   ┌────────────────────────────┐
│ ReadServ          │   │ TransactionServ             │
│ Port 8080         │   │ Port 8080                   │
└───────────────────┘   └────────────────────────────┘
```

---

## 2. Complete API Endpoint Reference

### 2.1 Offer Discovery & Calculation APIs

#### POST `/api/affordability/v1/offer/discovery`
**Purpose**: Discover all available EMI offers for a given cart/product

**Request:**
```json
{
  "client": {
    "id": "MERCHANT_001",
    "type": "MERCHANT",
    "channel": "ONLINE"
  },
  "program_type": "BANK_EMI",
  "product_details": [
    {
      "id": "PROD_001",
      "amount": 5000000,
      "type": "PRODUCT",
      "ean_code": "8901234567890"
    }
  ],
  "txn_amount": 5000000,
  "issuer": {
    "issuer_id": 101,
    "bin": "411111",
    "issuer_type": "CC"
  },
  "tenure": {
    "tenure_id": 6,
    "tenure_type": "MONTHS"
  },
  "customer_details": {
    "mobile_number": "9876543210"
  },
  "card_data": {
    "card_hash": "sha256_hash_of_card"
  },
  "convenience": {
    "applicable": true
  }
}
```

**Response:**
```json
{
  "status": "SUCCESS",
  "data": {
    "issuers": [
      {
        "issuer_id": 101,
        "issuer_name": "HDFC Bank",
        "issuer_type": "CC",
        "tenures": [
          {
            "tenure_id": 3,
            "tenure_name": "3 Months",
            "tenure_value": 3,
            "transaction_amount": 5000000,
            "loan_amount": 5000000,
            "auth_amount": 5000000,
            "monthly_emi_amount": 1700000,
            "total_emi_amount": 5100000,
            "interest_amount": 100000,
            "interest_rate_percentage": 12.0,
            "processing_fee_amount": 29900,
            "net_payment_amount": 5000000,
            "emi_type": "NO_COST_EMI",
            "total_discount_amount": 100000,
            "total_subvention_amount": 100000,
            "total_down_payment_amount": 0,
            "offer_code": "OFFER_HDFC_3M",
            "split_emi_amount": 0,
            "split_emi_percentage": 0,
            "convenience": {
              "fee_amount": 0,
              "tax_amount": 0
            },
            "discount_breakup": {
              "brand_amount": 50000,
              "merchant_amount": 30000,
              "issuer_amount": 20000,
              "dealer_amount": 0
            },
            "subvention_breakup": {
              "brand_amount": 50000,
              "merchant_amount": 30000,
              "issuer_amount": 20000,
              "dealer_amount": 0
            }
          },
          {
            "tenure_id": 6,
            "tenure_name": "6 Months",
            "tenure_value": 6,
            "monthly_emi_amount": 870000,
            "total_emi_amount": 5220000,
            "interest_amount": 220000,
            "interest_rate_percentage": 14.0
          }
        ]
      }
    ]
  }
}
```

---

#### POST `/v1/affordability/calculate-emi` (Internal - ReadServ)
**Purpose**: Core EMI calculation engine (called by adapters)

**Request:**
```json
{
  "client": { "id": "12345", "type": "MERCHANT", "channel": "ONLINE" },
  "program_type": "BRAND_EMI",
  "product_details": [
    { "id": "101", "amount": 7500000, "type": "PRODUCT", "ean_code": "EAN123" }
  ],
  "txn_amount": 7500000,
  "margin_amount": 0,
  "issuer": { "issuer_id": 5, "bin": "524321", "issuer_type": "CC" },
  "tenure": { "tenure_id": null, "tenure_type": null },
  "customer_details": { "mobile_number": "9876543210" },
  "card_data": null,
  "exclusions": [],
  "convenience": { "applicable": false },
  "supplementary_data": {}
}
```

---

#### POST `/v1/affordability/downpayment-details` (ReadServ)
**Purpose**: Calculate down payment options for offers

---

### 2.2 Transaction Lifecycle APIs

#### POST `/v1/affordability/transactions/` (Create Payment)
**Purpose**: Initialize a new EMI transaction
**Auth Scope**: `affordability.transactions.create-payment.POST`

**Request:**
```json
{
  "client_id": "MERCHANT_001",
  "client_type": "STORE",
  "channel": "OFFLINE",
  "transaction_amount": 5000000,
  "tenure_id": 6,
  "issuer_id": 101,
  "program_type": "BANK_EMI",
  "txn_type": "SALE",
  "customer": {
    "phone_number": "9876543210",
    "name": "John Doe",
    "email": "john@example.com"
  },
  "product_details": [
    {
      "product_id": 1001,
      "amount": 5000000,
      "ean_code": "8901234567890",
      "serial_number": "SN12345"
    }
  ],
  "invoice_number": "INV-2024-001",
  "card_data": {
    "encrypted_pan": "base64_encrypted_data"
  }
}
```

**Response:**
```json
{
  "status": "SUCCESS",
  "data": {
    "transaction_id": 98765,
    "transaction_status": "INITIATED",
    "self_expiring_date_time": "2024-03-15T11:00:00Z",
    "created_date_time": "2024-03-15T10:00:00Z"
  }
}
```

---

#### POST `/v1/affordability/transactions/{id}/pre-payment`
**Purpose**: Run pre-payment validations (velocity, credit limit, IMEI)
**Auth Scope**: `affordability.transactions.pre-payment.POST`

**Request:**
```json
{
  "tasks": ["VELOCITY_CHECK", "CREDIT_LIMIT_BLOCK", "IMEI_VALIDATE"],
  "card_data": {
    "card_hash": "sha256_hash"
  },
  "imei_data": {
    "imei_number": "352099001761481",
    "serial_number": "C39NKDEVHG7J"
  }
}
```

**Response:**
```json
{
  "status": "SUCCESS",
  "data": {
    "transaction_id": 98765,
    "tasks": [
      { "task_name": "VELOCITY_CHECK", "status": "SUCCESS" },
      { "task_name": "CREDIT_LIMIT_BLOCK", "status": "SUCCESS", "blocked_amount": 5000000 },
      { "task_name": "IMEI_VALIDATE", "status": "SUCCESS" }
    ]
  }
}
```

---

#### POST `/v1/affordability/transactions/{id}/complete-payment`
**Purpose**: Finalize the payment after acquirer/issuer confirmation
**Auth Scope**: `affordability.transactions.complete-payment.POST`

**Request:**
```json
{
  "acquirer_transaction_id": "ACQ_TXN_001",
  "acquirer_name": "FIRST_DATA",
  "auth_code": "123456",
  "rrn": "401234567890",
  "emi_details": {
    "monthly_emi_amount": 870000,
    "total_emi_amount": 5220000,
    "interest_amount": 220000,
    "interest_rate_percentage": 14.0,
    "processing_fee_amount": 29900
  }
}
```

**Response:**
```json
{
  "status": "SUCCESS",
  "data": {
    "transaction_id": 98765,
    "transaction_status": "APPROVED",
    "rrn": "401234567890",
    "auth_code": "123456"
  }
}
```

---

#### POST `/v1/affordability/transactions/{id}/settle-payment`
**Purpose**: Mark transaction as settled
**Auth Scope**: `affordability.transactions.settle-payment.POST`

---

#### POST `/v1/affordability/transactions/{id}/void-payment`
**Purpose**: Void an approved (unsettled) transaction
**Auth Scope**: `affordability.transactions.void-payment.POST`

**Request:**
```json
{
  "void_amount": 5000000,
  "void_type": "FULL",
  "reason": "Customer request",
  "idempotent_key": "VOID_98765_20240315"
}
```

---

#### POST `/v1/affordability/transactions/{id}/refund-payment`
**Purpose**: Refund a settled transaction (full or partial)
**Auth Scope**: `affordability.transactions.refund-payment.POST`

**Request:**
```json
{
  "refund_amount": 2500000,
  "refund_type": "PARTIAL",
  "reason": "Product return",
  "idempotent_key": "REFUND_98765_20240320"
}
```

---

#### POST `/v1/affordability/transactions/{id}/cancel-payment`
**Purpose**: Cancel an initiated (not yet approved) transaction

---

#### POST `/v1/affordability/transactions/{id}/kfs-details`
**Purpose**: Get Key Fact Statement (RBI regulatory compliance)

---

#### POST `/v1/affordability/transactions/{id}/send-otp`
**Purpose**: Send OTP for cardless EMI verification

---

#### POST `/v1/affordability/transactions/{id}/validate-otp`
**Purpose**: Validate OTP response

---

#### POST `/v1/affordability/transactions/{id}/perform-imei`
**Purpose**: Perform IMEI blocking on device

---

#### POST `/v1/affordability/transactions/{id}/settlement-instruction`
**Purpose**: Generate settlement instruction for OMS

---

#### POST `/v1/affordability/transactions/bulk-settle-payment`
**Purpose**: Bulk settle multiple transactions

---

### 2.3 Offer Management APIs (Admin/Portal)

#### Offer CRUD
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/affordability/offers` | Create new offer |
| GET | `/v1/affordability/offers` | List offers (paginated, filterable) |
| GET | `/v1/affordability/offers/download` | Export offers as Excel |
| PATCH | `/v1/affordability/offers/{id}` | Update offer details |
| DELETE | `/v1/affordability/offers/{id}` | Soft-delete offer |
| POST | `/v1/affordability/offers/{id}/{state}` | Change offer state (SUBMIT/APPROVE/REJECT/PAUSE/RESUME/INACTIVATE) |

#### Offer Parameters
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/affordability/offers/{id}/parameters` | Add offer parameters |
| GET | `/v1/affordability/offers/{id}/parameters` | Get offer parameters |
| PATCH | `/v1/affordability/offers/{id}/parameters/{paramId}` | Update parameters |
| DELETE | `/v1/affordability/offers/{id}/parameters/{paramId}` | Remove parameters |

#### Campaign & Budget
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/affordability/campaigns` | Create campaign |
| GET | `/v1/affordability/campaigns` | List campaigns |
| POST | `/v1/affordability/budgets` | Create budget |
| GET | `/v1/affordability/budgets/summary` | Budget consumption summary |
| GET | `/v1/affordability/budgets/summary/growth` | Budget growth analytics |

#### Configuration APIs
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/affordability/clients` | Create client/merchant |
| POST | `/v1/affordability/issuers` | Create issuer |
| POST | `/v1/affordability/issuer-emi-configs` | Create EMI config |
| POST | `/v1/affordability/bin-groups` | Create BIN group |
| POST | `/v1/affordability/tenures` | Create tenure |
| GET | `/v1/affordability/velocity-rules` | List velocity rules |

---

### 2.4 Velocity & Rate Limiting APIs

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/affordability/velocity/validate` | Check velocity limits |
| POST | `/v1/affordability/velocity/increment` | Increment velocity counter |
| POST | `/v1/affordability/velocity/decrement` | Decrement velocity counter (reversal) |

---

### 2.5 Cache Management APIs

| Method | Endpoint | Purpose |
|--------|----------|---------|
| DELETE | `/v1/affordability/cache` | Clear cache (by pattern/client/tenant) |
| POST | `/v1/affordability/cache` | Trigger cache refresh |
| DELETE | `/readserv/v1/affordability/clear-cache` | Clear ReadServ Redis cache |

---

### 2.6 Legacy POS APIs (TxnProcessorServ)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/paylater/transactions` | Create POS payment |
| GET | `/v1/paylater/transactions/{id}` | Get transaction |
| POST | `/v1/paylater/transactions/{id}/pre-payment` | Pre-payment checks |
| POST | `/v1/paylater/transactions/{id}/complete-payment` | Complete payment |
| POST | `/v1/paylater/transactions/{id}/cancel-payment` | Cancel |
| POST | `/v1/paylater/transactions/{id}/reverse-payment` | Reverse |
| POST | `/v1/paylater/transactions/{id}/void-payment` | Void |
| POST | `/v1/paylater/transactions/{id}/sync-payment` | Sync status |
| POST | `/v1/paylater/transactions/{id}/send-payment-link` | Payment link |
| POST | `/v1/paylater/transactions/{id}/emi-upi/offers` | EMI on UPI offers |
| POST | `/v1/paylater/cardless-eligibility` | Cardless EMI check |
| POST | `/v1/paylater/product-validate` | Product validation |
| GET | `/v1/paylater/transactions/chargeslip` | Charge slip |

---

## 3. Transaction State Machine

### 3.1 NXT Platform (Affordability_Transactionserv)

```
                    ┌──────────────────────────────────────────────────────────┐
                    │                                                          │
                    │             TRANSACTION STATE MACHINE                     │
                    │                                                          │
                    │                                                          │
    createPayment() │              ┌─────────┐                                 │
   ─────────────────┼─────────────>│INITIATED│                                 │
                    │              └────┬─────┘                                 │
                    │                   │                                       │
                    │         ┌─────────┼──────────┐                           │
                    │         │         │          │                            │
                    │  cancelPayment() │   selfExpiry (timeout)                │
                    │         │         │          │                            │
                    │         ▼         │          ▼                            │
                    │   ┌──────────┐   │    ┌─────────┐                        │
                    │   │CANCELLED │   │    │ EXPIRED │                         │
                    │   └──────────┘   │    └─────────┘                        │
                    │                   │                                       │
                    │         completePayment()                                 │
                    │                   │                                       │
                    │                   ▼                                       │
                    │              ┌─────────┐                                  │
                    │              │APPROVED │                                  │
                    │              └────┬────┘                                  │
                    │                   │                                       │
                    │      ┌────────────┼────────────┐                         │
                    │      │            │            │                          │
                    │  voidPayment() settlePayment()│                          │
                    │      │(full)      │       voidPayment()                  │
                    │      │            │       (partial)                       │
                    │      ▼            ▼            ▼                          │
                    │  ┌────────┐  ┌─────────┐  ┌───────────────┐              │
                    │  │ VOIDED │  │ SETTLED │  │PARTIAL_VOIDED │              │
                    │  └────────┘  └────┬────┘  └───────────────┘              │
                    │                   │                                       │
                    │      ┌────────────┼────────────┐                         │
                    │      │            │            │                          │
                    │  refundPayment() │     refundPayment()                   │
                    │      (full)      │        (partial)                       │
                    │      │            │            │                          │
                    │      ▼            │            ▼                          │
                    │  ┌──────────┐    │    ┌──────────────────┐               │
                    │  │ REFUNDED │    │    │PARTIAL_REFUNDED  │               │
                    │  └──────────┘    │    └────────┬─────────┘               │
                    │                  │             │                          │
                    │                  │     refundPayment(full)                │
                    │                  │             │                          │
                    │                  │             ▼                          │
                    │                  │     ┌──────────┐                       │
                    │                  │     │ REFUNDED │                       │
                    │                  │     └──────────┘                       │
                    │                  │                                        │
                    │                  │  (special)                             │
                    │                  │                                        │
                    │                  ▼                                        │
                    │           ┌──────────┐                                   │
                    │           │ REVERSED │ (system-initiated reversal)        │
                    │           └──────────┘                                   │
                    │                                                           │
                    └──────────────────────────────────────────────────────────┘
```

### 3.2 State Transition Rules

| Current State | Action | Next State | Conditions |
|---------------|--------|------------|------------|
| (none) | `createPayment()` | INITIATED | Valid client, amount, program type |
| INITIATED | `completePayment()` | APPROVED | Acquirer confirms, all pre-payment tasks SUCCESS |
| INITIATED | `cancelPayment()` | CANCELLED | Reverses all blocked resources |
| INITIATED | (timeout) | EXPIRED | `self_expiring_date_time` reached (default: 3600s) |
| APPROVED | `settlePayment()` | SETTLED | Settlement instruction generated |
| APPROVED | `voidPayment(full)` | VOIDED | Full amount void |
| APPROVED | `voidPayment(partial)` | PARTIAL_VOIDED | Partial amount void |
| SETTLED | `refundPayment(full)` | REFUNDED | Full refund of settled amount |
| SETTLED | `refundPayment(partial)` | PARTIAL_REFUNDED | Partial refund |
| PARTIAL_REFUNDED | `refundPayment(remaining)` | REFUNDED | Refund remaining amount |
| PARTIAL_REFUNDED | `refundPayment(partial)` | PARTIAL_REFUNDED | Another partial refund |

### 3.3 Task Status Machine (Per Task)

```
    ┌────────────────┐
    │ NOT_APPLICABLE │ (task not required for this flow)
    └────────────────┘

    ┌───────────┐     ┌─────────┐     ┌───────────────┐
    │ INITIATED │────>│ SUCCESS │     │PARTIAL_SUCCESS│
    └─────┬─────┘     └─────────┘     └───────────────┘
          │
          │           ┌────────┐
          └──────────>│ FAILED │
          │           └────────┘
          │
          │           ┌───────────┐
          └──────────>│ EXCEPTION │ (timeout/connectivity)
                      └───────────┘

    ┌─────────┐
    │REVERSED │ (task result undone during cancellation)
    └─────────┘
```

---

### 3.4 Offer State Machine (OfferMgmtServ)

```
    ┌───────────────────────────────────────────────────────────────┐
    │                                                               │
    │                  OFFER LIFECYCLE STATES                        │
    │                                                               │
    │                                                               │
    │  Create Offer                                                 │
    │       │                                                       │
    │       ▼                                                       │
    │   ┌───────┐         SUBMIT          ┌──────────────────────┐ │
    │   │ DRAFT │ ───────────────────────> │PENDING_FOR_APPROVAL  │ │
    │   └───┬───┘                          └──────────┬───────────┘ │
    │       ▲                                    │         │        │
    │       │                                    │         │        │
    │       │                             APPROVE│   REJECT│        │
    │       │                                    │         │        │
    │       │                                    ▼         ▼        │
    │       │                              ┌──────────┐ ┌────────┐ │
    │       │                              │ APPROVED │ │REJECTED│ │
    │       │                              └────┬─────┘ └───┬────┘ │
    │       │                                   │           │      │
    │       │         (if start_date > now)     │     DRAFT │      │
    │       │◄──────────────────────────────────┤           │      │
    │       │◄──────────────────────────────────────────────┘      │
    │       │                                   │                   │
    │       │                          PAUSE    │    INACTIVATE     │
    │       │                      (if live)    │         │         │
    │       │                           │       │         │         │
    │       │                           ▼       │         ▼         │
    │       │                     ┌────────┐    │   ┌────────────┐  │
    │       │                     │ PAUSED │    │   │INACTIVATED │  │
    │       │                     └───┬────┘    │   └────────────┘  │
    │       │                         │         │         ▲         │
    │       │                  RESUME  │         │         │         │
    │       │                         │         │  INACTIVATE       │
    │       │                         ▼         │    (from any)     │
    │       │                   ┌──────────┐    │                   │
    │       │                   │ APPROVED │◄───┘                   │
    │       │                   └──────────┘                        │
    │                                                               │
    └───────────────────────────────────────────────────────────────┘

    OFFER STATUS (derived from state + dates):
    ┌────────────────────────────────────────────────────────┐
    │ LIVE      = APPROVED + startDate <= now <= endDate      │
    │ SCHEDULED = APPROVED + startDate > now                  │
    │ DRAFT     = DRAFT or PENDING_FOR_APPROVAL state        │
    │ ARCHIVE   = APPROVED + endDate < now (auto-expired)    │
    └────────────────────────────────────────────────────────┘
```

---

## 4. Integration Type Strategy Resolution

The platform uses runtime strategy resolution to handle different payment flows:

### 4.1 NXT Platform (TransactionServ)
```
Bean Resolution: {IntegrationType}{Channel}{ProgramType}{IssuerType} + ServiceSuffix

Examples:
  DEFAULT + ONLINE + BANK_EMI + CC    → DEFAULTOnlineBankEmiCCCompletePaymentService
  DEFAULT + ONLINE + BRAND_EMI + DC   → DEFAULTOnlineBrandEmiDCCompletePaymentService
  DEFAULT + OFFLINE + BANK_EMI + CC   → DEFAULTOfflineBankEmiCCCompletePaymentService
  DEFAULT + ONLINE + BANK_EMI + CARDLESS → DEFAULTOnlineCardlessBankEmiCompletePaymentService
  DEFAULT + ONLINE + BANK_EMI + UPI   → DEFAULTOnlineUpiBankEmiCompletePaymentService
```

### 4.2 Legacy Platform (TxnProcessorServ)
```
Bean Resolution: {IntegrationType} + ServiceSuffix

Integration Types:
  PL_DEFAULT    → Standard POS EMI (bank/brand/cardless)
  LENDING       → NBFC loan origination
  PAY_BY_LINK   → Payment gateway link
  EMI_ON_UPI    → UPI-based EMI
  PAY_BY_UPI    → Direct UPI payment

Examples:
  PL_DEFAULT + CREATE_PAYMENT  → PL_DEFAULT_CREATE_PAYMENT_SERVICE
  LENDING + COMPLETE_PAYMENT   → LENDING_COMPLETE_PAYMENT_SERVICE
  PAY_BY_LINK + PRE_PAYMENT    → PAY_BY_LINK_PRE_PAYMENT_SERVICE
```

---

## 5. Authentication & Authorization

### 5.1 JWT Token Structure
```json
{
  "sub": "user_id",
  "realm_access": { "roles": ["OPERATIONS", "ADMIN"] },
  "tenant_name": "PL.IN",
  "user_type": "INTERNAL",
  "client_id": "affordability-portal",
  "permissions": ["edit_offers", "external_offer_approval", "view_reports"]
}
```

### 5.2 Auth Policy Annotation
```java
@PLAuthPolicy(
    scope = "affordability.transactions.create-payment.POST",
    userType = {"INTERNAL", "MERCHANT"},
    permission = "create_payment"
)
@PostMapping("/transactions/")
public ResponseEntity<?> createPayment(@RequestBody CreatePaymentRequest request) { }
```

### 5.3 User Types & Access Matrix

| User Type | Offer Create | Offer Approve | View All | Budget Manage | Settlement |
|-----------|:---:|:---:|:---:|:---:|:---:|
| INTERNAL | Yes | Yes | Yes | Yes | Yes |
| MERCHANT | Limited* | No | Own only | No | Own only |
| BRAND | Limited* | No | Own brand | No | No |
| ISSUER | No | No | Own issuer | No | No |
| OPERATIONS | Yes | Yes | Yes | Yes | Yes |

*Merchants can only create MERCHANT_BANK_DISCOUNT type offers.

---

## 6. Error Handling

### Standard Error Response
```json
{
  "status": "FAILED",
  "error": {
    "code": "AFF_TXN_001",
    "message": "Transaction not found",
    "details": "No transaction exists with id 98765"
  },
  "request_id": "req_abc123"
}
```

### Error Code Categories
| Prefix | Domain | Examples |
|--------|--------|---------|
| `AFF_TXN_` | Transaction | 001=Not Found, 002=Invalid State, 003=Expired |
| `AFF_OFR_` | Offer | 001=Not Found, 002=Invalid Dates, 003=State Conflict |
| `AFF_VEL_` | Velocity | 001=Limit Exceeded, 002=Rule Not Found |
| `AFF_BDG_` | Budget | 001=Exceeded, 002=Not Found |
| `AFF_EMI_` | EMI Calc | 001=No Offers, 002=Amount Below Min, 003=Config Missing |
| `AFF_INT_` | Integration | 001=Acquirer Error, 002=NBFC Error, 003=Timeout |
