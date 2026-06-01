# Network Token Management Service Workflow

## Overview

The Network Token Management Service (`nxt-token-mgm-service`) is responsible for persistent storage and lifecycle management of network tokens. It coordinates with the Network Gateway Service for cryptogram generation and handles network webhooks for token status updates.

## Services Involved

| Service | Role |
|---------|------|
| Token Management Service | Token CRUD, lifecycle, cryptogram delegation |
| Network Gateway Service | Cryptogram generation, token enrollment |
| Customer Vault Service | Upstream caller for customer-token operations |
| Card Networks (via webhooks) | Token lifecycle notifications |

## Architecture

```mermaid
graph TB
    subgraph Consumers["Consumers"]
        CVS[Customer Vault Service]
        CGW[Card Gateway]
    end

    subgraph TMS["Token Management Service"]
        InternalAPI["Internal API<br/>/internal/api/v1/tokens"]
        ExternalAPI["External API<br/>/api/v1/tokens"]
        
        TokenCRUD[Token CRUD Operations]
        CryptogramSvc[Cryptogram Service]
        WebhookHandler[Webhook Handler]
        LifecycleMgr[Lifecycle Manager]
        CleanupJob[Expiry Cleanup Job]
    end

    subgraph Adapters["Adapters"]
        NGSAdapter[Network Gateway Adapter]
    end

    subgraph Storage["Storage"]
        DB[(PostgreSQL<br/>tokens, audit_log, outbox)]
    end

    subgraph External["External"]
        NGS[Network Gateway Service]
        Networks[Card Networks<br/>Webhooks]
    end

    CVS --> InternalAPI
    CGW --> InternalAPI
    ExternalAPI --> TokenCRUD

    InternalAPI --> TokenCRUD
    InternalAPI --> CryptogramSvc
    InternalAPI --> WebhookHandler
    InternalAPI --> LifecycleMgr

    TokenCRUD --> DB
    CryptogramSvc --> NGSAdapter
    WebhookHandler --> DB
    LifecycleMgr --> DB
    CleanupJob --> DB & NGSAdapter

    NGSAdapter --> NGS
    Networks --> WebhookHandler
```

## Token Provisioning Sequence

```mermaid
sequenceDiagram
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL
    participant NGS as Network Gateway
    participant Network as Card Network

    CVS->>TMS: POST /internal/api/v1/tokens
    Note over TMS: Request: customer_id, merchant_id,<br/>card_number, expiry, network, card_type

    TMS->>TMS: Hash card number (SHA-256)
    TMS->>DB: Check for duplicate (customer_id + merchant_id + card_hash + network)
    
    alt Duplicate exists
        DB-->>TMS: Existing token
        TMS-->>CVS: Return existing token (dedup)
    else New token
        TMS->>NGS: POST /api/v1/network/enroll
        NGS->>Network: Provision request (encrypted PAN)
        Network-->>NGS: DPAN, PAR, reference_id, expiry
        NGS-->>TMS: Enrollment success

        TMS->>DB: INSERT token (status=ACTIVE)
        TMS->>DB: INSERT audit_log (action=CREATED)
        TMS->>DB: INSERT outbox (event=TOKEN_PROVISIONED)
        TMS-->>CVS: Token created {token_id, last4, network, status}
    end
```

## Cryptogram Generation Sequence

```mermaid
sequenceDiagram
    participant CGW as Card Gateway
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL
    participant NGS as Network Gateway
    participant Network as Card Network

    CGW->>TMS: POST /internal/api/v1/tokens/{token_id}/customer/{cust_id}/token-transactional-data
    Note over TMS: Request: amount, currency,<br/>transaction_type

    TMS->>DB: Fetch token by ID + customer
    DB-->>TMS: Token (network_token, network, status)

    alt Token not ACTIVE
        TMS-->>CGW: Error: Token not active
    else Token ACTIVE
        TMS->>NGS: POST /api/v1/network/cryptogram
        Note over NGS: Request includes:<br/>network_token, TRID, amount

        NGS->>Network: Generate cryptogram
        
        Note over Network: Generate transaction-specific<br/>cryptogram (TAVV/DTVV/TAV)

        Network-->>NGS: Cryptogram + ECI + type
        NGS-->>TMS: Cryptogram response
        TMS->>DB: INSERT audit_log (action=CRYPTOGRAM_GENERATED)
        TMS-->>CGW: {cryptogram, eci, cryptogram_type}
    end
```

## Token Lifecycle - Update from Network

```mermaid
sequenceDiagram
    participant Network as Card Network
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL

    Network->>TMS: POST /internal/api/v1/webhook/update-token-by-network
    Note over TMS: Webhook payload contains:<br/>token_reference, new_status,<br/>new_expiry, reason

    TMS->>TMS: Validate webhook signature/source

    TMS->>DB: Fetch token by network_reference_id
    DB-->>TMS: Current token state

    alt Token Status Update
        TMS->>DB: UPDATE token status
        TMS->>DB: INSERT audit_log (source=NETWORK_WEBHOOK)
        TMS->>DB: INSERT outbox (event=TOKEN_STATUS_UPDATED)
    else Token Expiry Update
        TMS->>DB: UPDATE token expiry
        TMS->>DB: INSERT audit_log
    else Card Metadata Update
        TMS->>DB: UPDATE card details (suffix, issuer)
        TMS->>DB: INSERT audit_log
    end

    TMS-->>Network: 200 OK (acknowledged)
```

## Token Deletion Flow

```mermaid
sequenceDiagram
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL
    participant NGS as Network Gateway
    participant Network as Card Network

    CVS->>TMS: POST /internal/api/v1/tokens/{token_id}/customer/{cust_id}/delete
    
    TMS->>DB: Fetch token
    DB-->>TMS: Token details

    TMS->>NGS: POST /api/v1/network/delete
    NGS->>Network: Delete token request
    Network-->>NGS: Deletion confirmed
    NGS-->>TMS: Success

    TMS->>DB: UPDATE token SET status = 'DELETED'
    TMS->>DB: INSERT audit_log (action=DELETED, source=MERCHANT)
    TMS->>DB: INSERT outbox (event=TOKEN_DELETED)
    TMS-->>CVS: Token deleted
```

## Batch Operations

### Fetch All Tokens by Customer

```mermaid
sequenceDiagram
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL

    CVS->>TMS: GET /internal/api/v1/tokens/{customer_id}
    TMS->>DB: SELECT * FROM tokens WHERE customer_id = ? AND status = 'ACTIVE'
    DB-->>TMS: Token list
    TMS-->>CVS: [{token_id, last4, network, type, status, expires_at}]
```

### Fetch Tokens by PAR

```mermaid
sequenceDiagram
    participant Service as Internal Service
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL

    Service->>TMS: GET /internal/api/v1/tokens/{par}
    Note over TMS: PAR links same card<br/>across different merchants
    TMS->>DB: SELECT * FROM tokens WHERE par = ?
    DB-->>TMS: All tokens for this card (across merchants)
    TMS-->>Service: Token list (multi-merchant)
```

### Expired Token Cleanup

```mermaid
sequenceDiagram
    participant Scheduler as Cleanup Job
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL
    participant NGS as Network Gateway

    Note over Scheduler: Scheduled job (daily)
    
    Scheduler->>TMS: POST /internal/api/v1/tokens/delete-deactivate-expired
    TMS->>DB: SELECT tokens WHERE expires_at < NOW() AND status = 'ACTIVE'
    DB-->>TMS: Expired tokens list
    
    loop For each expired token
        TMS->>NGS: Delete token from network
        NGS-->>TMS: Confirmed
        TMS->>DB: UPDATE status = 'EXPIRED' -> 'DELETED'
        TMS->>DB: INSERT audit_log (action=EXPIRED, source=SYSTEM)
    end
    
    TMS-->>Scheduler: Cleanup complete ({count} tokens processed)
```

## Offline Token Generation

```mermaid
sequenceDiagram
    participant Service as Internal Service
    participant TMS as Token Mgm Service
    participant DB as PostgreSQL

    Service->>TMS: POST /internal/api/v1/tokens/offline
    Note over TMS: Generate token without<br/>network provisioning<br/>(for offline/batch scenarios)

    TMS->>TMS: Generate internal token reference
    TMS->>DB: INSERT token (status=PENDING_PROVISIONING)
    TMS->>DB: INSERT outbox (event=OFFLINE_TOKEN_CREATED)
    TMS-->>Service: Token reference (pending network sync)
    
    Note over TMS: Background job will<br/>provision with network later
```

## Activity Diagram - Token Management Operations

```mermaid
flowchart TB
    subgraph CRUD["Token CRUD"]
        direction LR
        Create[Create/Provision] --> Store[Store with ACTIVE status]
        Read[Fetch by ID/Customer/PAR] --> Return[Return token details]
        Update[Update status/expiry] --> Audit[Log in audit_log]
        Delete[Delete token] --> Network_Del[Delete from network]
        Network_Del --> Mark_Del[Mark DELETED]
    end

    subgraph Cryptogram["Cryptogram Generation"]
        direction LR
        CReq[Cryptogram request] --> Validate[Validate token ACTIVE]
        Validate --> Delegate[Delegate to Network Gateway]
        Delegate --> Gen[Network generates cryptogram]
        Gen --> CResp[Return cryptogram + ECI]
    end

    subgraph Webhook["Webhook Processing"]
        direction LR
        WH[Network webhook] --> WValidate[Validate signature]
        WValidate --> WProcess[Process event type]
        WProcess --> WUpdate[Update token in DB]
        WUpdate --> WAudit[Audit log + outbox event]
    end

    subgraph Lifecycle["Lifecycle Jobs"]
        direction LR
        Expire[Expiry scanner] --> EFind[Find expired tokens]
        EFind --> EClean[Cleanup + notify network]
        Dedup[Dedup scanner] --> DFind[Find duplicates]
        DFind --> DMerge[Merge/cleanup duplicates]
    end
```

## API Reference

### Internal APIs (`/internal/api/v1/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tokens` | Provision new token |
| GET | `/tokens/{token_id}/customer/{customer_id}` | Fetch token by ID |
| PATCH | `/tokens/{token_id}/customer/{customer_id}` | Update token |
| POST | `/tokens/{token_id}/customer/{customer_id}/token-transactional-data` | Generate cryptogram |
| POST | `/tokens/{token_id}/customer/{customer_id}/delete` | Delete token |
| GET | `/tokens` | Fetch tokens (query params) |
| GET | `/tokens/{customer_id}` | Fetch all by customer |
| GET | `/tokens/{par}` | Fetch by PAR |
| POST | `/tokens/delete-deactivate-expired` | Cleanup expired |
| POST | `/tokens/delete` | Batch delete |
| POST | `/tokens/offline` | Generate offline token |
| POST | `/webhook/update-token-by-network` | Network webhook |

### External APIs (`/api/v1/tokens`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tokens` | Provision token (merchant-facing) |
| GET | `/tokens/{token_id}` | Fetch token |
| POST | `/tokens/{token_id}/delete` | Delete token |
| POST | `/tokens/{token_id}/cryptogram` | Generate cryptogram |

## Event Types (Outbox)

| Event | Trigger | Payload |
|-------|---------|---------|
| TOKEN_PROVISIONED | New token created | token_id, customer_id, network, status |
| TOKEN_STATUS_UPDATED | Status change | token_id, old_status, new_status, source |
| TOKEN_DELETED | Token removed | token_id, customer_id, reason |
| CRYPTOGRAM_GENERATED | Cryptogram created | token_id, transaction_ref |
| TOKEN_EXPIRED | Auto-expiry | token_id, expired_at |
| OFFLINE_TOKEN_CREATED | Offline provision | token_id, pending_network_sync |
