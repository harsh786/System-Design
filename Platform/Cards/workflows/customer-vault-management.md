# Customer Vault Management Workflow

## Overview

The Customer Vault Management Service (`nxt-customer-vault-mgm-service`) manages customer profiles, saved cards/tokens, OTP verification, addresses, and brand wallet status. It serves as the customer-facing layer that delegates token operations to the Token Management Service.

## Services Involved

| Service | Role |
|---------|------|
| Customer Vault Service | Customer CRUD, token association, OTP, addresses |
| Token Management Service | Token storage, cryptogram delegation to networks |
| SMS Service | OTP delivery via SMS |
| Network Gateway Service | Token provisioning (via Token Mgm Service) |
| Subscription Service | SBMD (Subscription-Based Merchant Debit) |
| Redis | Caching customer data and OTP sessions |

## Architecture

```mermaid
graph TB
    subgraph External["External APIs"]
        MerchantAPI["/api/v1/customers<br/>Merchant-facing"]
    end

    subgraph Internal["Internal APIs"]
        InternalAPI["/internal/api/v1/customers<br/>Service-to-service"]
    end

    subgraph CVS["Customer Vault Service"]
        CustSvc[Customer Service]
        TokenSvc[Customer Token Service]
        OTPSvc[OTP Service]
        AddrSvc[Address Service]
        GlobalCustSvc[Global Customer Service]
        BrandWallet[Brand Wallet Service]
    end

    subgraph Adapters["Service Adapters"]
        TMSAdapter[Token Mgm Adapter]
        SMSAdapter[SMS Service Adapter]
        SubAdapter[Subscription Adapter]
    end

    subgraph Storage["Storage"]
        PG[(PostgreSQL)]
        RedisCache[(Redis Cache)]
    end

    subgraph Downstream["Downstream Services"]
        TMS[Token Mgm Service]
        SMS[SMS Service]
        SubSvc[Subscription Service]
    end

    MerchantAPI --> CVS
    InternalAPI --> CVS

    CustSvc --> PG
    CustSvc --> RedisCache
    TokenSvc --> TMSAdapter
    OTPSvc --> SMSAdapter
    BrandWallet --> SubAdapter

    TMSAdapter --> TMS
    SMSAdapter --> SMS
    SubAdapter --> SubSvc
```

## Customer Creation Flow

```mermaid
sequenceDiagram
    participant Merchant
    participant CVS as Customer Vault
    participant DB as PostgreSQL
    participant Redis as Redis Cache
    participant Outbox as Outbox (Events)

    Merchant->>CVS: POST /api/v1/customers {mobile, email, name}
    
    CVS->>CVS: Validate request
    CVS->>CVS: Encrypt PII (AES-256)
    
    CVS->>DB: Check if customer exists (merchant_id + customer_id)
    
    alt Customer exists
        DB-->>CVS: Existing customer
        CVS-->>Merchant: Return existing customer
    else New customer
        CVS->>DB: Generate customer keys
        CVS->>DB: INSERT customers_details
        CVS->>DB: Check/create global_customer (by mobile)
        CVS->>Outbox: Publish CUSTOMER_CREATED event
        CVS->>Redis: Cache customer data
        CVS-->>Merchant: Customer created (id, status)
    end
```

## Save Card Token Flow

```mermaid
sequenceDiagram
    participant Merchant
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant NGS as Network Gateway
    participant Network as Card Network

    Merchant->>CVS: POST /api/v1/customers/{cust_id}/tokens
    Note over CVS: Request contains:<br/>card_number, expiry, network,<br/>card_type, issuer

    CVS->>CVS: Validate customer exists & active
    CVS->>CVS: Hash card number (SHA-256)
    CVS->>CVS: Check for duplicate (card_hash + merchant + network)

    alt Duplicate token exists
        CVS-->>Merchant: Return existing token reference
    else New token
        CVS->>TMS: POST /internal/api/v1/tokens (provision)
        TMS->>NGS: POST /api/v1/network/enroll
        NGS->>Network: Provision network token
        Network-->>NGS: DPAN + PAR + reference
        NGS-->>TMS: Enrollment success
        TMS->>TMS: Store token (ACTIVE)
        TMS-->>CVS: Token reference + details

        CVS->>CVS: Associate token with customer
        CVS-->>Merchant: Token saved (token_id, last4, network, status)
    end
```

## Fetch Saved Cards Flow

```mermaid
sequenceDiagram
    participant Merchant
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant Redis as Redis Cache

    Merchant->>CVS: GET /api/v1/customers/{cust_id}/tokens
    
    CVS->>Redis: Check cache for customer tokens
    
    alt Cache hit
        Redis-->>CVS: Cached token list
    else Cache miss
        CVS->>TMS: GET /internal/api/v1/tokens?customer_id={cust_id}
        TMS-->>CVS: All tokens for customer
        CVS->>Redis: Cache token list (TTL: 5min)
    end

    CVS->>CVS: Filter active tokens only
    CVS->>CVS: Enrich with card metadata (last4, brand, type)
    CVS-->>Merchant: Token list [{token_id, last4, network, type, issuer, status}]
```

## OTP Verification Flow (Customer Identity)

```mermaid
sequenceDiagram
    participant Merchant
    participant CVS as Customer Vault
    participant SMS as SMS Service
    participant Redis as Redis Cache

    Note over Merchant: Customer identity verification<br/>before showing saved cards

    Merchant->>CVS: POST /api/v1/customers/{cust_id}/otp/send
    
    CVS->>CVS: Fetch customer, decrypt mobile
    CVS->>CVS: Generate OTP (6-digit)
    CVS->>Redis: Store OTP session (TTL: 5min)
    CVS->>SMS: Send OTP to mobile
    SMS-->>CVS: Delivery confirmed
    CVS-->>Merchant: OTP sent (otp_id, expires_in)

    Merchant->>CVS: POST /api/v1/customers/{cust_id}/otp/{otp_id}/validate {otp}
    
    CVS->>Redis: Fetch OTP session
    
    alt OTP valid
        Redis-->>CVS: OTP matches
        CVS->>Redis: Invalidate OTP session
        CVS-->>Merchant: OTP validated (customer authenticated)
    else OTP invalid
        Redis-->>CVS: OTP mismatch
        CVS->>CVS: Increment attempt counter
        alt Max attempts exceeded
            CVS-->>Merchant: OTP expired (max retries)
        else
            CVS-->>Merchant: Invalid OTP (retry allowed)
        end
    end
```

## Delete Card Token Flow

```mermaid
sequenceDiagram
    participant Merchant
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service
    participant NGS as Network Gateway
    participant Network as Card Network

    Merchant->>CVS: POST /api/v1/customers/{cust_id}/tokens/{token_id}/delete
    
    CVS->>CVS: Validate customer owns token
    CVS->>TMS: POST /internal/api/v1/tokens/{token_id}/delete
    TMS->>NGS: POST /api/v1/network/delete
    NGS->>Network: Delete token request
    Network-->>NGS: Token deleted
    NGS-->>TMS: Deletion confirmed
    TMS->>TMS: Mark token DELETED in DB
    TMS-->>CVS: Deletion successful
    
    CVS->>CVS: Remove from customer association
    CVS->>CVS: Invalidate cache
    CVS-->>Merchant: Token deleted
```

## Activity Diagram - Customer Lifecycle

```mermaid
flowchart TB
    subgraph Creation["Customer Onboarding"]
        C1[Merchant API call] --> C2[Validate request]
        C2 --> C3[Encrypt PII with AES]
        C3 --> C4[Create customer record]
        C4 --> C5[Generate encryption keys]
        C5 --> C6[Create/link global customer]
        C6 --> C7[Publish event]
    end

    subgraph CardManagement["Card Management"]
        M1[Save card request] --> M2[Hash card for dedup]
        M2 --> M3{Duplicate?}
        M3 -->|Yes| M4[Return existing token]
        M3 -->|No| M5[Provision network token]
        M5 --> M6[Store in token service]
        M6 --> M7[Associate with customer]
        
        M8[List cards] --> M9[Fetch from token service]
        M9 --> M10[Filter active tokens]
        M10 --> M11[Return enriched card list]
        
        M12[Delete card] --> M13[Delete from network]
        M13 --> M14[Remove from token store]
        M14 --> M15[Update customer association]
    end

    subgraph Identity["Identity Verification"]
        I1[OTP send request] --> I2[Decrypt customer mobile]
        I2 --> I3[Generate 6-digit OTP]
        I3 --> I4[Store in Redis with TTL]
        I4 --> I5[Send via SMS]
        
        I6[OTP validate] --> I7[Fetch from Redis]
        I7 --> I8{Match?}
        I8 -->|Yes| I9[Customer authenticated]
        I8 -->|No| I10{Retries left?}
        I10 -->|Yes| I11[Allow retry]
        I10 -->|No| I12[Block + expire session]
    end

    subgraph Address["Address Management"]
        A1[Create address] --> A2[Validate + store]
        A3[Update address] --> A4[Validate ownership + update]
        A5[Delete address] --> A6[Soft delete]
        A7[List addresses] --> A8[Return by customer/mobile]
    end
```

## Webhook - Network Token Save

```mermaid
sequenceDiagram
    participant Network as Card Network
    participant CVS as Customer Vault
    participant TMS as Token Mgm Service

    Network->>CVS: POST /api/v1/customers/webhook/save-token
    Note over CVS: Network pushes token update<br/>after successful provisioning

    CVS->>CVS: Validate webhook signature
    CVS->>TMS: Update token details
    TMS-->>CVS: Token updated
    CVS-->>Network: 200 OK
```

## Brand Wallet Management

```mermaid
sequenceDiagram
    participant Merchant
    participant CVS as Customer Vault
    participant SubSvc as Subscription Service

    Merchant->>CVS: PATCH /api/v1/customers/{cust_id}/brand-wallet
    Note over CVS: Update brand wallet status<br/>(opt-in/opt-out for merchant wallet)
    
    CVS->>CVS: Update customer brand wallet flag
    CVS->>SubSvc: Sync wallet status for subscriptions
    SubSvc-->>CVS: Synced
    CVS-->>Merchant: Wallet status updated

    Merchant->>CVS: GET /api/v1/customers/wallet?status=ACTIVE&page=1
    CVS->>CVS: Query customers with active brand wallet
    CVS-->>Merchant: Paginated wallet customer list

    Merchant->>CVS: GET /api/v1/customers/wallet/download
    CVS->>CVS: Generate CSV of wallet customers
    CVS-->>Merchant: CSV download
```

## Global Customer Concept

```mermaid
flowchart TD
    A[Customer with mobile +91-9876543210] --> B[Global Customer<br/>Single identity across merchants]
    B --> C[Merchant A: Customer C1]
    B --> D[Merchant B: Customer C2]
    B --> E[Merchant C: Customer C3]
    
    C --> F[Token T1 - Visa card]
    C --> G[Token T2 - MC card]
    D --> H[Token T3 - Visa card<br/>same PAR as T1]
    E --> I[Token T4 - Rupay card]
    
    Note over B: Same mobile number = same global customer<br/>Tokens are merchant-scoped<br/>PAR links same card across merchants
```

## API Summary

### External APIs (Merchant-facing)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/customers` | Create customer |
| GET | `/api/v1/customers/{id}` | Get customer |
| PATCH | `/api/v1/customers/{id}` | Update customer |
| POST | `/api/v1/customers/{id}/tokens` | Save card token |
| GET | `/api/v1/customers/{id}/tokens` | List saved cards |
| POST | `/api/v1/customers/{id}/tokens/{tid}/delete` | Delete card |
| POST | `/api/v1/customers/{id}/otp/send` | Send OTP |
| POST | `/api/v1/customers/{id}/otp/{oid}/validate` | Validate OTP |
| POST | `/api/v1/customers/{id}/address` | Create address |
| PATCH | `/api/v1/customers/{id}/brand-wallet` | Update wallet status |
| GET | `/api/v1/customers/wallet` | List wallet customers |

### Internal APIs (Service-to-service)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/internal/api/v1/customers` | Create customer |
| POST | `/internal/api/v1/customers/inactive` | Create inactive customer |
| DELETE | `/internal/api/v1/customers/delete-customer` | Delete customer |
| POST | `/internal/api/v1/customers/{id}/tokens/{tid}/token-transactional-data` | Generate cryptogram |
| POST | `/internal/api/v1/customers/webhook/save-token` | Network webhook |
| POST | `/internal/api/v1/customers/delete-cards` | Bulk delete by phone |

## Security

- All PII encrypted at rest (AES-256)
- Per-customer encryption keys in `customer_keys` table
- Master key from AWS Secrets Manager
- OTP sessions with TTL (5 min default)
- Rate limiting on OTP endpoints
- Webhook signature validation
