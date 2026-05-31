# Acquirer Services & Connector Architecture

## Overview

The acquirer layer handles routing payments to the correct banking partner (acquirer) and communicating with them via their specific APIs. It consists of the Acquirer Service (configuration/routing data) and the Card Connector Service (request dispatch to per-acquirer connectors).

## Services Involved

| Service | Role |
|---------|------|
| Acquirer Service (`Plural_AcquirerServicev21`) | Merchant-acquirer config, MID/TID data, routing rules |
| Card Connector Service (`Plural_CardConnectorService`) | Dispatch hub routing to per-acquirer connectors |
| HDFC Card Connector | HDFC bank integration |
| Cybersource Card Connector | CYBS (HDFC/Axis) integration |
| MPGS Connector | Mastercard Payment Gateway Services (Axis/Amex) |
| RBL Card Connector | RBL bank integration |
| Fiserv Connector | Fiserv bank integration |
| Lyra Connector | Lyra/ICICI integration |
| Wibmo Connector | Wibmo/Axis integration |

## Architecture

```mermaid
graph TB
    subgraph Orchestration["Card Gateway (Orchestrator)"]
        CGW[Card Gateway Service]
    end

    subgraph Config["Configuration Layer"]
        AQS[Acquirer Service<br/>Merchant-Acquirer Config]
        AQS_DB[(Acquirer DB<br/>SQL Server + PostgreSQL)]
    end

    subgraph Dispatch["Dispatch Layer"]
        CCS[Card Connector Service<br/>ConnectorRoute Factory]
    end

    subgraph Connectors["Per-Acquirer Connectors"]
        HDFC[HDFC Connector]
        CYBS[Cybersource Connector<br/>HDFC-CYBS / Axis-CYBS]
        MPGS[MPGS Connector<br/>Axis / Amex]
        RBL[RBL Connector]
        Fiserv[Fiserv Connector]
        Lyra[Lyra Connector<br/>ICICI]
        WibmoAcq[Wibmo Connector<br/>Axis]
        PayGlocal[PayGlocal Connector<br/>Kotak]
    end

    subgraph Banks["Acquirer Banks"]
        HDFC_Bank[HDFC Bank]
        Axis_Bank[Axis Bank]
        RBL_Bank[RBL Bank]
        ICICI_Bank[ICICI Bank]
        Amex_Bank[American Express]
        Kotak_Bank[Kotak Bank]
    end

    CGW --> AQS
    CGW --> CCS
    AQS --> AQS_DB
    
    CCS --> HDFC & CYBS & MPGS & RBL & Fiserv & Lyra & WibmoAcq & PayGlocal
    
    HDFC --> HDFC_Bank
    CYBS --> HDFC_Bank & Axis_Bank
    MPGS --> Axis_Bank & Amex_Bank
    RBL --> RBL_Bank
    Fiserv --> HDFC_Bank
    Lyra --> ICICI_Bank
    WibmoAcq --> Axis_Bank
    PayGlocal --> Kotak_Bank
```

## Acquirer Selection Sequence

```mermaid
sequenceDiagram
    participant CGW as Card Gateway
    participant BIN as BIN Service
    participant AQS as Acquirer Service
    participant Cache as Redis Cache

    CGW->>BIN: Lookup BIN metadata
    BIN-->>CGW: {network: VISA, type: CREDIT, issuer: HDFC}

    CGW->>AQS: GET /merchant/{merchantId}/cards
    
    AQS->>Cache: Check acquirer config cache
    alt Cache hit
        Cache-->>AQS: Cached config
    else Cache miss
        AQS->>AQS: Query DB (SQL Server or PostgreSQL)
        AQS->>Cache: Cache result
    end
    
    AQS-->>CGW: Acquirer configs [{acquirer_id, mid, tid, priority, network, card_type}]

    Note over CGW: Select acquirer based on:<br/>1. Card network match<br/>2. Card type match<br/>3. Priority order<br/>4. Load balancing<br/>5. Acquirer availability

    CGW->>CGW: Selected: HDFC (acquirer_id=CYBER_SOURCE_HDFC)
```

## Card Connector Routing Sequence

```mermaid
sequenceDiagram
    participant CGW as Card Gateway
    participant CCS as Card Connector Service
    participant Factory as ConnectorRoute Factory
    participant CYBS as Cybersource Connector
    participant Bank as HDFC Bank (via CYBS)

    CGW->>CCS: POST /authorize {acquirer_id: CYBER_SOURCE_HDFC, ...}
    
    CCS->>Factory: Route by acquirer_id
    Note over Factory: ConnectorRoute enum:<br/>CYBER_SOURCE_HDFC -> "cybs"<br/>HDFC -> "hdfc"<br/>AXIS -> "mpgs"<br/>RBL -> "rbl"

    Factory-->>CCS: CybsCardConnector (base_url)
    
    CCS->>CYBS: Forward authorize request
    CYBS->>CYBS: Transform to CYBS API format
    CYBS->>Bank: CYBS Authorization API call
    Bank-->>CYBS: Auth response
    CYBS->>CYBS: Map to standard response
    CYBS-->>CCS: Standardized auth result
    CCS-->>CGW: Authorization response
```

## Connector Operations Interface

```mermaid
flowchart LR
    subgraph Interface["CardConnectorService Interface"]
        Setup[setup]
        Enroll[enroll<br/>3DS enrollment]
        Auth[authorize]
        AuthDecoupled[authorizeDecoupled]
        Capture[capture]
        Refund[refund]
        Void[voidTransaction]
        Inquiry[inquiry]
        Validate[validate]
        Risk[risk]
    end
```

### Operations by Acquirer Support

| Operation | HDFC | CYBS | MPGS | RBL | Fiserv | Lyra |
|-----------|------|------|------|-----|--------|------|
| Setup | - | - | - | - | - | - |
| Enroll (3DS) | Y | Y | Y | Y | Y | Y |
| Authorize | Y | Y | Y | Y | Y | Y |
| Capture | Y | Y | Y | Y | Y | Y |
| Refund | Y | Y | Y | Y | Y | Y |
| Void | Y | Y | Y | Y | Y | Y |
| Inquiry | Y | Y | Y | Y | Y | Y |
| Validate | Y | Y | - | - | - | - |
| Risk | - | Y | - | - | - | - |

## Acquirer Routing Table

| Acquirer ID | Connector Route | Connector Service | Bank |
|-------------|----------------|-------------------|------|
| `HDFC` | `hdfc` | HDFC Card Connector | HDFC Bank |
| `CYBER_SOURCE_HDFC` | `cybs` | Cybersource Connector | HDFC Bank (via CYBS) |
| `CYBER_SOURCE_AXIS` | `cybs` | Cybersource Connector | Axis Bank (via CYBS) |
| `AXIS` | `mpgs` | MPGS Connector | Axis Bank |
| `AMEX` | `mpgs` | MPGS Connector | American Express |
| `RBL` | `rbl` | RBL Card Connector | RBL Bank |
| `HDFC_FSS_IN_HOUSE` | `hdfc` | HDFC Card Connector | HDFC FSS |
| `PAYGLOCAL_KOTAK` | `payglocal` | PayGlocal Connector | Kotak Bank |
| `LYRA_ICICI` | `lyra` | Lyra Connector | ICICI Bank |
| `WIBMO_AXIS` | `wibmo` | Wibmo Connector | Axis Bank |

## 3DS Enrollment Flow (Per Acquirer)

```mermaid
sequenceDiagram
    participant CGW as Card Gateway
    participant CCS as Card Connector
    participant ACQ as Acquirer Connector
    participant DS as Directory Server
    participant ACS as Issuer ACS

    CGW->>CCS: Enroll request (card, amount, merchant)
    CCS->>ACQ: Forward enrollment

    Note over ACQ: Build acquirer-specific<br/>enrollment payload

    ACQ->>DS: 3DS2 Authentication Request (AReq)
    DS->>ACS: Route to issuer ACS
    ACS-->>DS: Authentication Response (ARes)
    DS-->>ACQ: ARes (frictionless or challenge)

    alt Frictionless (ECI=05)
        ACQ-->>CCS: CAVV + ECI + status=AUTHENTICATED
        CCS-->>CGW: Frictionless auth complete
    else Challenge Required
        ACQ-->>CCS: ACS URL + CReq + transaction_id
        CCS-->>CGW: Challenge required (redirect needed)
        Note over CGW: Return ACS URL to browser<br/>via Redirect Listener
    end
```

## Activity Diagram - Acquirer Configuration Management

```mermaid
flowchart TB
    subgraph MerchantOnboarding["Merchant Acquirer Onboarding"]
        O1[New merchant registered] --> O2[Assign acquirer based on:<br/>- MCC code<br/>- Volume<br/>- Network support]
        O2 --> O3[Generate MID with acquirer]
        O3 --> O4[Store comm params<br/>MID, TID, keys]
        O4 --> O5[Configure network support<br/>3DS version, COFT, Passkey]
    end

    subgraph Routing["Runtime Routing"]
        R1[Payment request] --> R2[BIN lookup: network + type]
        R2 --> R3[Fetch merchant acquirer configs]
        R3 --> R4[Filter by network + card type]
        R4 --> R5{Multiple acquirers?}
        R5 -->|Yes| R6[Select by priority + availability]
        R5 -->|No| R7[Use single match]
        R6 --> R8[Route to connector]
        R7 --> R8
    end

    subgraph CacheStrategy["Caching"]
        C1[Acquirer config fetched] --> C2[Cache in Redis]
        C2 --> C3[TTL-based invalidation]
        C3 --> C4[Force refresh endpoint<br/>GET /merchant/{id}/cards/refresh]
    end
```

## Acquirer Service API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/acquirers` | List all acquirers |
| GET | `/merchant/{merchantId}/acquirer/{acquirerId}` | Merchant-acquirer comm params |
| GET | `/merchant/{merchantId}/acquirer/{acquirerId}/client/{clientId}` | Client-specific params |
| GET | `/merchant/{merchantId}/cards` | All acquirer configs for merchant |
| GET | `/merchant/{merchantId}/cards/refresh` | Force cache refresh |
| GET | `/merchant/{merchantId}/client/{clientId}/cards` | Client-specific cards |
| GET | `/merchant/{merchantId}/client/{clientId}/pos` | POS acquirer config |
| GET | `/pfid` | Payment Facilitator IDs |
| GET | `/pbp/{acquirerId}` | Acquirer-level config |
| GET | `/cache/clear/{id}` | Clear cache entry |

## Acquirer Service Data Model

```mermaid
erDiagram
    ACQUIRER_MASTER {
        varchar acquirer_id PK
        varchar acquirer_name
        varchar acquirer_type
        bit is_active
    }

    ACQUIRER_MERCHANT_MAPPING {
        bigint id PK
        varchar merchant_id
        varchar acquirer_id FK
        varchar mid
        varchar tid
        int priority
        varchar card_network
        varchar card_type
        bit is_active
    }

    ACQUIRER_COMM_PARAMS {
        bigint id PK
        varchar merchant_id
        varchar acquirer_id
        varchar mid
        varchar encryption_key
        varchar api_key
        varchar api_secret
        varchar three_ds_key
    }

    ACQUIRER_NETWORK_CONFIG {
        bigint id PK
        varchar acquirer_id
        varchar network_type
        varchar ds_url
        varchar trid
        bit is_network_token
        bit is_native_otp
    }

    ACQUIRER_MASTER ||--o{ ACQUIRER_MERCHANT_MAPPING : "merchants"
    ACQUIRER_MASTER ||--o{ ACQUIRER_NETWORK_CONFIG : "network configs"
    ACQUIRER_MERCHANT_MAPPING ||--o{ ACQUIRER_COMM_PARAMS : "comm params"
```

## Dual-DB Architecture

```mermaid
flowchart TD
    A[Acquirer Service] --> B[RepositoryFactory]
    B --> C{DB Source Config}
    C -->|Legacy| D[SQL Server Repository<br/>R2DBC MSSQL Driver]
    C -->|Migration| E[PostgreSQL Repository<br/>R2DBC PostgreSQL Driver]
    C -->|Dual Read| F[Read from both<br/>Compare results]
    
    D --> G[(SQL Server<br/>Legacy DB)]
    E --> H[(PostgreSQL<br/>Target DB)]
```

## Connector Communication Patterns

| Acquirer | Protocol | Auth | Format |
|----------|----------|------|--------|
| HDFC | HTTPS REST | API Key + HMAC | JSON |
| Cybersource | HTTPS REST | JWT + Shared Secret | JSON |
| MPGS | HTTPS REST | API Key + Certificate | JSON |
| RBL | HTTPS REST | API Key | JSON |
| Fiserv | HTTPS REST | OAuth 2.0 | JSON |
| Lyra | HTTPS REST | HMAC SHA-256 | JSON |
| PayGlocal | HTTPS REST | RSA Signature | JSON |

## Error Handling

| Error | Connector Behavior | Gateway Behavior |
|-------|-------------------|------------------|
| Acquirer timeout | Retry once (idempotent ops) | Return timeout to merchant |
| Auth declined | Return decline reason | Map to merchant error code |
| Acquirer down | Circuit breaker opens | Route to backup acquirer if available |
| Invalid MID/TID | Return config error | Alert operations, block merchant |
| Network error | Retry with backoff | Inquiry after timeout |
| Duplicate transaction | Idempotency check | Return original result |
