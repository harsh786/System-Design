# Payment Processing Workflows

## Overview

The Card Gateway Service orchestrates the complete payment lifecycle through six core operations: Process, Authenticate, Authorize, Capture, Refund, and Void. Each operation is exposed as a REST endpoint and follows a standardized flow through the processing pipeline.

## Core Operations

| Operation | Endpoint | Description |
|-----------|----------|-------------|
| Process | POST `/process` | Initiate payment, BIN lookup, acquirer selection, 3DS enrollment |
| Authenticate | POST `/authenticate` | Handle 3DS authentication callback |
| Authorize | POST `/authorize` | Submit authorization to acquirer |
| Capture | POST `/capture` | Capture pre-authorized amount |
| Refund | POST `/refund` | Refund captured payment |
| Void | POST `/void` | Cancel pre-authorized payment |
| Inquiry | POST `/inquiry` | Check transaction status |

---

## Process Payment Sequence

```mermaid
sequenceDiagram
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant BIN as BIN Service
    participant AQS as Acquirer Service
    participant CVS as Customer Vault
    participant NGS as Network Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer

    OMS->>CGW: POST /process (card_data, amount, merchant_id)
    
    rect rgb(240, 248, 255)
        Note over CGW: Step 1: BIN Resolution
        CGW->>BIN: Lookup card BIN
        BIN-->>CGW: {network, type, issuer, capabilities}
    end

    rect rgb(255, 248, 240)
        Note over CGW: Step 2: Acquirer Selection
        CGW->>AQS: Get merchant acquirer configs
        AQS-->>CGW: Available acquirers with MID/TID
        CGW->>CGW: Select acquirer (network + type + priority)
    end

    rect rgb(240, 255, 240)
        Note over CGW: Step 3: Token Resolution (if COFT)
        alt COFT Transaction
            CGW->>CVS: Fetch customer token
            CVS-->>CGW: Token details (DPAN, network)
            CGW->>NGS: Generate cryptogram
            NGS-->>CGW: Cryptogram + ECI
        end
    end

    rect rgb(255, 240, 255)
        Note over CGW: Step 4: 3DS Enrollment
        CGW->>CCS: Enroll (card/token, amount, acquirer)
        CCS->>ACQ: 3DS enrollment request
        ACQ-->>CCS: Enrollment response
        CCS-->>CGW: Result
    end

    alt Frictionless (ECI=05)
        CGW-->>OMS: Auth ready (no challenge needed)
    else Challenge Required
        CGW->>CGW: Cache payment data in Redis
        CGW-->>OMS: Challenge URL (ACS redirect needed)
    end
```

## Authorization Sequence

```mermaid
sequenceDiagram
    participant RL as Redirect Listener
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer
    participant Kafka as Kafka

    RL->>OMS: Auth callback (3DS complete)
    OMS->>CGW: POST /authorize (payment_id, cavv, eci)
    
    CGW->>CGW: Fetch cached payment context
    CGW->>CGW: Build authorization request

    CGW->>CCS: Authorize (amount, card/token, cavv, eci, mid, tid)
    CCS->>ACQ: Authorization API call
    
    Note over ACQ: Validate CAVV<br/>Check card limits<br/>Reserve funds

    ACQ-->>CCS: Auth response (approved/declined)
    Note over CCS: Response: auth_code, rrn,<br/>response_code, response_msg

    CCS-->>CGW: Standardized auth result

    CGW->>CGW: Update transaction status
    CGW->>Kafka: Publish PAYMENT_AUTHORIZED event

    CGW-->>OMS: Authorization response
    OMS-->>RL: Status for customer redirect
```

## Capture Sequence

```mermaid
sequenceDiagram
    participant Merchant
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer

    Merchant->>OMS: Capture request (order_id, amount)
    OMS->>CGW: POST /capture (payment_id, amount)
    
    CGW->>CGW: Validate: status=AUTHORIZED
    CGW->>CGW: Validate: amount <= authorized_amount

    CGW->>CCS: Capture (auth_code, rrn, amount, mid)
    CCS->>ACQ: Capture API call
    
    Note over ACQ: Move funds from<br/>hold to captured

    ACQ-->>CCS: Capture response
    CCS-->>CGW: Capture result

    CGW->>CGW: Update status: CAPTURED
    CGW-->>OMS: Capture successful
    OMS-->>Merchant: Capture confirmed
```

## Refund Sequence

```mermaid
sequenceDiagram
    participant Merchant
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer

    Merchant->>OMS: Refund request (order_id, amount, reason)
    OMS->>CGW: POST /refund (payment_id, amount)
    
    CGW->>CGW: Validate: status=CAPTURED
    CGW->>CGW: Validate: refund_amount <= captured_amount

    CGW->>CCS: Refund (rrn, amount, mid, original_auth)
    CCS->>ACQ: Refund API call
    
    Note over ACQ: Process refund<br/>Credit to cardholder

    ACQ-->>CCS: Refund response (rrn, status)
    CCS-->>CGW: Refund result

    alt Full refund
        CGW->>CGW: Update status: REFUNDED
    else Partial refund
        CGW->>CGW: Update status: PARTIALLY_REFUNDED
        CGW->>CGW: Track refunded_amount
    end

    CGW-->>OMS: Refund successful
    OMS-->>Merchant: Refund confirmed
```

## Void Sequence

```mermaid
sequenceDiagram
    participant Merchant
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer

    Merchant->>OMS: Void request (order_id)
    OMS->>CGW: POST /void (payment_id)
    
    CGW->>CGW: Validate: status=AUTHORIZED (not captured)

    CGW->>CCS: Void (auth_code, rrn, mid)
    CCS->>ACQ: Void/Reversal API call
    
    Note over ACQ: Release hold on funds

    ACQ-->>CCS: Void response
    CCS-->>CGW: Void result

    CGW->>CGW: Update status: VOIDED
    CGW-->>OMS: Void successful
    OMS-->>Merchant: Void confirmed
```

## Transaction State Machine

```mermaid
stateDiagram-v2
    [*] --> INITIATED: POST /process
    
    INITIATED --> ENROLLED: 3DS enrollment success
    INITIATED --> FAILED: BIN/acquirer error

    ENROLLED --> AUTHENTICATION_PENDING: Challenge required
    ENROLLED --> AUTHORIZED: Frictionless + auto-auth

    AUTHENTICATION_PENDING --> AUTHENTICATED: 3DS complete
    AUTHENTICATION_PENDING --> FAILED: Auth timeout/failure

    AUTHENTICATED --> AUTHORIZED: POST /authorize success
    AUTHENTICATED --> FAILED: Auth declined

    AUTHORIZED --> CAPTURED: POST /capture
    AUTHORIZED --> VOIDED: POST /void
    AUTHORIZED --> FAILED: Late decline

    CAPTURED --> REFUNDED: Full POST /refund
    CAPTURED --> PARTIALLY_REFUNDED: Partial refund
    PARTIALLY_REFUNDED --> REFUNDED: Remaining refund

    FAILED --> [*]
    VOIDED --> [*]
    REFUNDED --> [*]
```

## Activity Diagram - Full Payment Flow

```mermaid
flowchart TB
    subgraph Process["Process Phase"]
        P1[Receive payment request] --> P2[BIN lookup]
        P2 --> P3[Acquirer selection]
        P3 --> P4{COFT?}
        P4 -->|Yes| P5[Fetch token + cryptogram]
        P4 -->|No| P6[Use card data directly]
        P5 --> P7[3DS Enrollment]
        P6 --> P7
        P7 --> P8{Enrollment result}
        P8 -->|Frictionless| P9[Direct to authorize]
        P8 -->|Challenge| P10[Cache + redirect to ACS]
        P8 -->|Failed| P11[Return failure]
    end

    subgraph Authenticate["Authentication Phase"]
        A1[Customer at ACS page] --> A2{Auth method}
        A2 -->|OTP| A3[Native OTP / ACS OTP]
        A2 -->|Passkey| A4[Biometric authentication]
        A2 -->|3DS Challenge| A5[Bank challenge page]
        A3 --> A6[Callback to Redirect Listener]
        A4 --> A6
        A5 --> A6
        A6 --> A7[Extract auth data]
    end

    subgraph Authorize["Authorization Phase"]
        AU1[Receive auth data CAVV+ECI] --> AU2[Build auth request]
        AU2 --> AU3[Send to acquirer via connector]
        AU3 --> AU4{Approved?}
        AU4 -->|Yes| AU5[AUTHORIZED]
        AU4 -->|No| AU6[DECLINED]
    end

    subgraph PostAuth["Post-Authorization"]
        PA1[AUTHORIZED] --> PA2{Merchant action}
        PA2 -->|Capture| PA3[Send capture to acquirer]
        PA2 -->|Void| PA4[Send void to acquirer]
        PA3 --> PA5[CAPTURED]
        PA4 --> PA6[VOIDED]
        PA5 --> PA7{Refund?}
        PA7 -->|Full| PA8[REFUNDED]
        PA7 -->|Partial| PA9[PARTIALLY_REFUNDED]
    end
```

## Inquiry Flow

```mermaid
sequenceDiagram
    participant Merchant
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer

    Merchant->>OMS: Inquiry (order_id)
    OMS->>CGW: POST /inquiry (payment_id)
    
    alt Local status available
        CGW->>CGW: Fetch from DB/cache
        CGW-->>OMS: Current status + details
    else Need acquirer confirmation
        CGW->>CCS: Inquiry (rrn, mid, tid)
        CCS->>ACQ: Status inquiry
        ACQ-->>CCS: Transaction status
        CCS-->>CGW: Acquirer-confirmed status
        CGW->>CGW: Reconcile local vs acquirer status
        CGW-->>OMS: Reconciled status
    end
```

## Response Code Mapping

| Acquirer Code | Plural Status | Description |
|---------------|--------------|-------------|
| 00 | AUTHORIZED | Approved |
| 05 | DECLINED | Do not honor |
| 12 | DECLINED | Invalid transaction |
| 14 | DECLINED | Invalid card number |
| 41 | DECLINED | Card reported lost |
| 43 | DECLINED | Card reported stolen |
| 51 | DECLINED | Insufficient funds |
| 54 | DECLINED | Card expired |
| 55 | DECLINED | Incorrect PIN |
| 61 | DECLINED | Exceeds withdrawal limit |
| 91 | TIMEOUT | Issuer unavailable |

## Error Recovery Patterns

| Scenario | Pattern |
|----------|---------|
| Auth timeout | Inquiry after 30s, if no response -> reversal |
| Capture timeout | Inquiry to confirm, retry if not processed |
| Duplicate auth attempt | Idempotency via payment_id |
| Partial capture | Track remaining authorized amount |
| Multiple partial refunds | Track cumulative refund vs captured |
| Network partition | Circuit breaker + fallback to inquiry |
