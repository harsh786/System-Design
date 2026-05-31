# Issuer Tokenization Workflow

## Overview

Issuer Tokenization is the process where the card issuer (bank) provisions tokens for card-on-file storage, as opposed to network tokenization where the card network (Visa/MC/RuPay) issues the token. Issuer tokens are managed directly by the issuing bank and are used for recurring payments, subscriptions, and merchant-specific card-on-file scenarios.

## Key Differences: Network vs Issuer Tokenization

| Aspect | Network Tokenization | Issuer Tokenization |
|--------|---------------------|---------------------|
| Token Issuer | Card Network (Visa/MC/RuPay) | Issuing Bank |
| Token Format | DPAN (looks like card number) | Bank-specific reference |
| Cryptogram | Required per transaction | May not be required |
| PAR | Assigned by network | Not applicable |
| Lifecycle | Network manages | Issuer manages |
| Use Case | All e-commerce | Recurring, subscriptions, merchant-specific |
| RBI Compliance | Fully compliant (CoF guidelines) | Compliant via issuer agreement |

## Services Involved

| Service | Role |
|---------|------|
| Card Gateway | Detects issuer token type, routes accordingly |
| Customer Vault Service | Stores issuer token reference |
| Token Management Service | Manages issuer token lifecycle |
| Acquirer Connector (HDFC/CYBS) | Some acquirers support issuer token provisioning |
| BIN Service | Identifies if issuer supports tokenization |

## Issuer Token Provisioning Sequence

```mermaid
sequenceDiagram
    participant Customer
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant BIN as BIN Service
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant CCS as Card Connector
    participant ACQ as Acquirer/Issuer

    Customer->>OMS: Save card for future use
    OMS->>CGW: Tokenization request
    
    CGW->>BIN: Lookup BIN metadata
    BIN-->>CGW: Issuer info, token support flags
    
    Note over CGW: Check if issuer supports<br/>issuer-level tokenization

    CGW->>CCS: Validate card + request token
    CCS->>ACQ: Card validation + token request
    
    Note over ACQ: Issuer validates card<br/>Provisions issuer token<br/>Returns token reference

    ACQ-->>CCS: Issuer token reference + expiry
    CCS-->>CGW: Token provisioning response

    CGW->>CVS: Save issuer token for customer
    CVS->>TMS: POST /tokens (type=ISSUER)
    TMS-->>CVS: Token stored
    CVS-->>CGW: Token saved
    CGW-->>OMS: Tokenization complete
    OMS-->>Customer: Card saved successfully
```

## Issuer Token Payment Flow

```mermaid
sequenceDiagram
    participant Customer
    participant OMS as Order Management
    participant CGW as Card Gateway
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant CCS as Card Connector
    participant ACQ as Acquirer
    participant Issuer as Issuer Bank

    Customer->>OMS: Pay with saved card (issuer token)
    OMS->>CGW: POST /process (token reference)
    
    CGW->>CVS: Fetch token details
    CVS->>TMS: GET token by reference
    TMS-->>CVS: Token (type=ISSUER, reference, status)
    CVS-->>CGW: Issuer token data

    Note over CGW: Token type = ISSUER<br/>No network cryptogram needed<br/>Use issuer token directly

    CGW->>CCS: Authorize with issuer token
    CCS->>ACQ: Authorization (issuer_token_reference)
    ACQ->>Issuer: Route with issuer token
    
    Note over Issuer: Resolve token to PAN<br/>Validate + Authorize

    Issuer-->>ACQ: Authorization response
    ACQ-->>CCS: Auth result
    CCS-->>CGW: Authorization complete
    CGW-->>OMS: Payment response
    OMS-->>Customer: Payment successful
```

## Activity Diagram - Issuer Token Decision Flow

```mermaid
flowchart TD
    A[Payment with saved card] --> B{Token type?}
    B -->|NETWORK| C[Network Token Flow<br/>Generate cryptogram]
    B -->|ISSUER| D[Issuer Token Flow]
    B -->|NONE/LEGACY| E[PAN-based flow<br/>Direct card data]
    
    D --> F{Issuer token valid?}
    F -->|Active| G[Proceed with issuer token]
    F -->|Expired| H[Re-tokenize with issuer]
    F -->|Suspended| I[Return error to merchant]
    
    G --> J[3DS Enrollment]
    J --> K{Challenge required?}
    K -->|Yes| L[3DS Challenge/OTP]
    K -->|No| M[Frictionless auth]
    L --> N[Authorization with issuer token]
    M --> N
    N --> O[Issuer resolves token to PAN]
    O --> P[Issuer authorizes]
    
    H --> Q{Re-tokenization successful?}
    Q -->|Yes| R[Update token in store]
    R --> G
    Q -->|No| S[Fall back to new card entry]
```

## Issuer Token Lifecycle

```mermaid
stateDiagram-v2
    [*] --> REQUESTED: Card validation + token request
    REQUESTED --> ACTIVE: Issuer provisions token
    REQUESTED --> FAILED: Issuer rejects

    ACTIVE --> EXPIRED: Token expiry reached
    ACTIVE --> SUSPENDED: Issuer suspends (fraud/dispute)
    ACTIVE --> REVOKED: Customer/merchant revokes

    EXPIRED --> RENEWED: Auto-renewal by issuer
    RENEWED --> ACTIVE: New token active

    SUSPENDED --> ACTIVE: Issuer reactivates
    SUSPENDED --> REVOKED: Permanent block

    REVOKED --> [*]
    FAILED --> [*]
```

## Issuer Token Types by Acquirer

| Acquirer | Token Type | Mechanism |
|----------|-----------|-----------|
| HDFC | SI Token (Standing Instruction) | Recurring mandate token |
| Cybersource | TMS Token | Cybersource Token Management |
| MPGS | Session Token | MPGS tokenization framework |
| RBL | Issuer Reference | Bank-specific token |
| Axis | Network Token (MPGS) | Routes via MDES |

## Configuration

Issuer tokenization eligibility is determined by:
1. `ADDON_ISSUER_ID_MASTER_TBL.IS_NATIVE_OTP_ENABLED` - Indicates issuer support
2. BIN metadata - Card type and issuer capabilities
3. Acquirer configuration - Whether acquirer supports issuer token for that merchant

## Error Scenarios

| Error | Handling |
|-------|----------|
| Issuer doesn't support tokenization | Fall back to network tokenization |
| Token expired during payment | Attempt re-tokenization, fail gracefully |
| Issuer token format mismatch | Log error, return generic failure |
| Recurring mandate expired | Notify merchant, request new mandate |
| Card replaced by issuer | Token invalidated, customer re-enrollment needed |
