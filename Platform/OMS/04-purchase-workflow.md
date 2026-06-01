# 04 — Purchase Workflow

> End-to-end payment creation flow — from merchant API call to funds capture

---

## Functional Overview

The purchase workflow covers the standard payment lifecycle:

1. Merchant creates an order
2. Merchant (or checkout UI) initiates a payment on that order
3. Payment is processed through the appropriate gateway
4. Funds are captured (immediately or via pre-auth + capture)

---

## Flow 1: Create Order

### Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant Server
    participant OMS as OMS
    participant DB as PostgreSQL

    M->>OMS: POST /api/pay/v1/orders<br/>{amount, currency, merchantOrderRef, ...}
    activate OMS

    OMS->>OMS: Validate merchant auth (HMAC signature)
    OMS->>OMS: Validate request body<br/>(currency, amount > 0, no duplicate ref)
    OMS->>OMS: Enrich order<br/>(preAuth settings, KYC, MCC, split)
    OMS->>DB: INSERT order (status=CREATED)
    OMS->>DB: INSERT outbox (proto payload)
    OMS->>DB: INSERT merchant_ref_order_mapper
    DB-->>OMS: Committed

    OMS-->>M: 201 Created<br/>{orderId, status: CREATED, ...}
    deactivate OMS
```

### Technical Sequence (Internal Detail)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant Kong as Kong
    participant Route as OrderRoutes.kt
    participant API as OrdersAPIService
    participant OMS as OMSClient
    participant SVC as OrderService
    participant Repo as OrderRepository
    participant DB as PostgreSQL
    participant Outbox as Debezium

    M->>Kong: POST /api/pay/v1/orders
    Kong->>Route: Forward (authenticated)
    Route->>Route: validateCreateOrderRequest()
    Route->>API: createOrder(merchantId, request)

    API->>API: Validate currency (INR/MCC)
    API->>API: Validate pre-auth config
    API->>API: Validate KYC compliance
    API->>API: Validate MCC details
    API->>API: Validate split settlement

    API->>OMS: createOrder(order)
    OMS->>SVC: createOrder(order)
    SVC->>Repo: createOrder(order)

    Repo->>DB: BEGIN
    Repo->>DB: INSERT INTO orders (...)
    Repo->>DB: INSERT INTO outbox_v1 (aggregateid, payload)
    Repo->>DB: INSERT INTO merchant_ref_order_mapper
    Repo->>DB: COMMIT

    DB-->>Repo: Success
    Repo-->>SVC: OrderEntity
    SVC-->>OMS: Order
    OMS-->>API: Order
    API-->>Route: OrderResponse
    Route-->>M: 201 {orderId, status, links}

    Note over DB,Outbox: Async: Debezium reads WAL
    DB->>Outbox: CDC event captured
    Outbox->>Outbox: Publish to Kafka topic
```

---

## Flow 2: Create Payment (Standard Card — 3DS)

### Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant / Checkout
    participant OMS as OMS
    participant Gateway as Card Gateway
    participant Bank as Issuing Bank
    participant User as Cardholder

    M->>OMS: POST /api/pay/v1/orders/{orderId}/payments<br/>{method: CARD, cardData: {...}}
    activate OMS

    OMS->>OMS: Validate order can accept payment
    OMS->>OMS: Generate paymentId
    OMS->>OMS: Risk/velocity check
    OMS->>Gateway: Create payment (card details)
    Gateway->>Bank: Initiate 3DS authentication
    Bank-->>Gateway: Challenge URL (ACS redirect)
    Gateway-->>OMS: {status: PENDING, challengeUrl: "..."}

    OMS->>OMS: Mark payment AUTH_CHALLENGED
    OMS->>OMS: Mark order PENDING
    OMS-->>M: 200 {paymentId, status: PENDING, challengeUrl}
    deactivate OMS

    Note over User,Bank: User completes 3DS on bank page

    Bank->>Gateway: 3DS callback (success)
    Gateway->>OMS: POST /internal/orders/payments/{paymentId}/process<br/>{status: PROCESSED}
    activate OMS

    OMS->>OMS: Mark payment CAPTURED
    OMS->>OMS: Mark order PROCESSED
    OMS->>OMS: Persist + outbox event
    OMS-->>Gateway: 200 OK
    deactivate OMS

    Note over OMS,M: Webhook notification sent to merchant
```

### Technical Sequence (Card Payment — Full Detail)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant Route as PaymentRoutes
    participant API as PaymentsAPIService
    participant OMS as OMSClient
    participant PS as PaymentService
    participant Lock as Redis Lock
    participant Repo as OrderRepository
    participant THF as TxnHandlerFactory
    participant TH as NormalTxnHandler
    participant Risk as RiskService
    participant SDK as PaymentSDK
    participant CGW as Card Gateway
    participant DB as PostgreSQL

    M->>Route: POST /orders/{orderId}/payments
    Route->>Route: validateCreatePaymentRequest()
    Route->>API: createPayment(orderId, request)
    API->>OMS: createPayment(orderId, payment)

    OMS->>PS: createPayment(orderId, paymentRequest)
    activate PS

    PS->>Lock: acquireLock(orderId, wait=5s, lease=30s)
    Lock-->>PS: Lock acquired

    PS->>Repo: getOrderWithAuth(orderId, merchantId)
    Repo->>DB: SELECT FROM orders WHERE order_id = ?
    DB-->>Repo: OrderEntity
    Repo-->>PS: Order

    PS->>PS: Validate: order.type == CHARGE
    PS->>PS: Validate: canInitiatePayment (status ∈ {CREATED, PENDING, ATTEMPTED})
    PS->>PS: Validate: currency matches (INR or DCC/MCC)
    PS->>PS: Validate: payment attempts remaining
    PS->>PS: Validate: amount ≤ order amount

    alt Order is PENDING (non-part-payment)
        PS->>PS: Cancel existing pending payments
        PS->>SDK: cancelPayment(existingPaymentId)
    end

    PS->>PS: Validate merchant payment reference uniqueness
    PS->>PS: Generate paymentId(s)

    PS->>THF: getHandler(order, payment, merchantConfig)
    THF->>THF: Evaluate: DCC? MCC? ICB? CardlessEMI?
    THF-->>PS: NormalTxnHandler + PaymentFlow.DEFAULT

    PS->>TH: validate(order, payment)
    TH-->>PS: Validation passed

    PS->>PS: Validate convenience fee (if applicable)
    PS->>PS: Validate offers (if applicable)

    PS->>Repo: addPayments(order, paymentModels)
    Repo->>DB: UPDATE orders SET payments_list = ... WHERE order_id = ?
    DB-->>Repo: Updated

    PS->>Risk: riskCheck(order, payment)
    Risk-->>PS: APPROVED

    PS->>SDK: createPayment(paymentRequest)
    activate SDK
    SDK->>CGW: HTTP POST /create-payment
    CGW-->>SDK: {status: PENDING, challengeUrl: "https://bank.com/3ds"}
    SDK-->>PS: Right(SDKResponse)
    deactivate SDK

    PS->>PS: paymentModel.markChallengePending(challengeUrl)
    PS->>Repo: updateOrder(order.copy(status=PENDING))
    Repo->>DB: UPDATE orders ... + INSERT outbox_v1
    DB-->>Repo: Committed

    PS->>Lock: releaseLock(orderId)
    PS-->>OMS: Right(Order)
    deactivate PS

    OMS-->>API: Order
    API-->>Route: PaymentResponse
    Route-->>M: 200 {paymentId, status, challengeUrl, ...}
```

---

## Flow 3: Process Payment Callback (Async)

After the user completes authentication (3DS, OTP, UPI collect), the gateway sends a callback to OMS.

### Technical Sequence

```mermaid
sequenceDiagram
    participant GW as Gateway (Card/UPI/NB)
    participant Route as InternalRoutes
    participant OMS as OMSClient
    participant PS as PaymentService
    participant Lock as Redis Lock
    participant Repo as OrderRepository
    participant Offer as OfferService
    participant ConFee as ConvenienceFeeService
    participant Kafka as KafkaEventProducer
    participant DB as PostgreSQL

    GW->>Route: POST /internal/orders/payments/{paymentId}/process<br/>{status, providerRef, acquirerDetails}
    Route->>OMS: processPayment(paymentId, processRequest)
    OMS->>PS: processPayment(paymentId, request)
    activate PS

    PS->>Repo: getOrderByPaymentId(paymentId)
    Repo->>DB: SELECT FROM orders WHERE payments_list @> ?
    DB-->>Repo: Order
    Repo-->>PS: Order

    PS->>Lock: acquireLock(orderId, wait=5s, lease=30s)
    Lock-->>PS: Acquired

    PS->>Repo: getOrder(orderId) -- re-fetch under lock
    Repo-->>PS: Fresh Order

    PS->>PS: Check idempotency (already terminal? → return)
    PS->>PS: Check late auth expiry

    alt Late Auth Expired + Payment SUCCESS
        PS->>PS: Mark CAPTURED then initiate reversal
        PS->>SDK: refundPayment(...)
        PS->>PS: Mark order CANCEL_REQUESTED → CANCELLED
    else Late Auth NOT Expired
        alt Pre-auth order
            PS->>PS: Mark payment AUTHORIZED
            PS->>PS: Mark order AUTHORIZED
        else Non-pre-auth order
            PS->>PS: Resolve post-auth convenience fee (UPI)
            PS->>ConFee: getPostAuthConFee(payment)
            ConFee-->>PS: Fee details

            PS->>Offer: confirmOffer(order, payment)
            Offer-->>PS: APPROVED / REJECTED

            alt Offer APPROVED
                PS->>PS: Mark payment CAPTURED
                PS->>PS: Mark order PROCESSED
            else Offer REJECTED
                PS->>PS: Mark payment then reverse order
            end
        end
    end

    PS->>Repo: updateOrder(finalOrder)
    Repo->>DB: UPDATE orders + INSERT outbox_v1
    DB-->>PS: Committed

    PS->>Lock: releaseLock(orderId)
    PS-->>OMS: Right(Order)
    deactivate PS
```

---

## Flow 4: UPI Collect Payment

UPI payments have a unique async pattern — the collect request is sent to the user's UPI app, and the response arrives via callback.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant UPI as UPI Gateway
    participant PSP as UPI PSP (NPCI)
    participant User as User's UPI App

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: UPI, vpa: "user@upi"}
    OMS->>SDK: createPayment(UPI collect)
    SDK->>UPI: Initiate collect
    UPI->>PSP: Send collect request
    PSP->>User: Push notification

    UPI-->>SDK: {status: PENDING, timeout: 300s}
    SDK-->>OMS: PENDING
    OMS->>OMS: Mark AUTH_CHALLENGED + order PENDING
    OMS-->>M: 200 {status: PENDING}

    Note over User,PSP: User approves in UPI app (up to 5 min)

    User->>PSP: Approve
    PSP->>UPI: Debit success
    UPI->>OMS: POST /internal/payments/{paymentId}/process<br/>{status: PROCESSED, rrn: "..."}

    OMS->>OMS: Check late auth
    OMS->>OMS: Resolve post-auth convenience fee
    OMS->>OMS: Confirm offer
    OMS->>OMS: Mark CAPTURED + order PROCESSED
    OMS-->>UPI: 200 OK

    Note over OMS,M: Webhook → merchant notified
```

---

## Flow 5: Netbanking / Wallet Payment (Redirect)

```mermaid
sequenceDiagram
    participant M as Merchant / Checkout
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant NB as Netbanking Gateway
    participant Bank as Bank Portal

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: NETBANKING, bankCode: "HDFC"}
    OMS->>SDK: createPayment(NB)
    SDK->>NB: Initiate NB transaction
    NB-->>SDK: {redirectUrl: "https://bank.com/nb/..."}
    SDK-->>OMS: {status: PENDING, challengeUrl: redirectUrl}
    OMS->>OMS: Mark AUTH_CHALLENGED + PENDING
    OMS-->>M: 200 {challengeUrl: "https://bank.com/nb/..."}

    Note over M,Bank: User redirected to bank portal

    Bank->>NB: Payment success callback
    NB->>OMS: POST /internal/payments/{paymentId}/process<br/>{status: PROCESSED}
    OMS->>OMS: Mark CAPTURED + PROCESSED
```

---

## Flow 6: Instant (No-Redirect) Payment

Some payment methods (saved cards with no 3DS, certain wallets) can complete instantly.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Gateway

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD, savedCard: true}
    OMS->>SDK: createPayment(card)
    SDK->>GW: Process payment
    GW-->>SDK: {status: PROCESSED, rrn: "123456"}
    SDK-->>OMS: Right(PROCESSED)

    OMS->>OMS: Mark payment CAPTURED
    OMS->>OMS: Mark order PROCESSED
    OMS->>OMS: Persist + outbox
    OMS-->>M: 200 {status: PROCESSED, paymentId: "..."}
```

---

## Payment Method Routing

```mermaid
graph TD
    subgraph "PaymentSDK Router"
        SDK[PaymentSDK.createPayment]
    end

    SDK -->|CARD| CGW[Card Gateway Service<br/>Plural_CardGatewayServicev21]
    SDK -->|UPI| UGW[UPI Gateway]
    SDK -->|NETBANKING| NGW[Netbanking Gateway]
    SDK -->|WALLET| WGW[Wallet Gateway]
    SDK -->|BNPL| AGW[Affordability Gateway]
    SDK -->|CREDIT_EMI| AGW
    SDK -->|DEBIT_EMI| AGW
    SDK -->|CARDLESS_EMI| AGW
    SDK -->|POINTS| AGW
    SDK -->|BRAND_WALLET| BWGW[Brand Wallet Gateway]
    SDK -->|BANK_TRANSFER| DIRECT[Direct (no gateway call)]

    subgraph "Gateway → Acquirer"
        CGW --> HDFC[HDFC]
        CGW --> AXIS[Axis]
        CGW --> ICICI[ICICI]
        CGW --> RBL[RBL]
        UGW --> NPCI[NPCI / PSP]
        NGW --> BANKS[Bank Portals]
        AGW --> LENDERS[EMI Lenders / BNPL Providers]
    end
```

---

## Aggregator Mode Determination

```mermaid
flowchart TD
    A[Payment Method?] --> B{CARD / CREDIT_EMI / DEBIT_EMI}
    A --> C{UPI}
    A --> D{NETBANKING / WALLET / BNPL}
    A --> E{BANK_TRANSFER / BRAND_WALLET}

    B -->|Query Acquirer Service| F[acquirerService.isAggregator<br/>merchantId, paymentMethod]
    C -->|Query Merchant Service| G[merchantService.isAggregator<br/>merchantId]
    D --> H[Always aggregator = true]
    E --> I[Always aggregator = false]

    F --> J{Aggregator?}
    G --> J
    J -->|Yes| K[OMS acts as payment aggregator<br/>Uses Plural's acquiring infrastructure]
    J -->|No| L[OMS acts as gateway<br/>Routes to merchant's own acquirer]
```

---

## Error Handling Matrix

| Scenario | OMS Action | Order Status | Payment Status |
|----------|-----------|--------------|----------------|
| Gateway timeout | Return server error | PENDING (unchanged) | INITIATED (recon will resolve) |
| Gateway returns FAILED | Mark failed, check retryable | ATTEMPTED (if retriable) or FAILED | FAILED |
| Risk check DECLINED | Return error, don't call gateway | CREATED (unchanged) | Not created |
| Duplicate payment ref | Return 409 Conflict | Unchanged | Not created |
| Max attempts exceeded | Return error | Unchanged | Not created |
| Amount validation failure | Return 422 | Unchanged | Not created |
| Lock acquisition timeout | Return 423 Locked | Unchanged | Not created |
