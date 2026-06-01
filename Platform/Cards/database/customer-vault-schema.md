# Customer Vault Database Schema

## Entity-Relationship Diagram

```mermaid
erDiagram
    CUSTOMERS_DETAILS {
        uuid id PK
        varchar merchant_id "Merchant identifier"
        varchar customer_id "Merchant-scoped customer ID"
        varchar mobile_number "Encrypted"
        varchar country_code
        varchar email "Encrypted"
        varchar first_name "Encrypted"
        varchar last_name "Encrypted"
        varchar status "ACTIVE/INACTIVE/DELETED"
        timestamp created_at
        timestamp updated_at
    }

    GLOBAL_CUSTOMERS {
        uuid id PK
        varchar mobile_number "Encrypted - unique global identity"
        varchar country_code
        varchar status
        timestamp created_at
        timestamp updated_at
    }

    CUSTOMER_KEYS {
        uuid id PK
        uuid customer_id FK
        varchar key_type "ENCRYPTION/SIGNING"
        text encrypted_key
        varchar key_version
        boolean is_active
        timestamp created_at
    }

    CUSTOMER_BNPL_DETAILS {
        uuid id PK
        uuid customer_id FK
        varchar provider "SIMPL/LAZYPAY/ZESTMONEY"
        varchar provider_customer_id
        varchar status
        decimal credit_limit
        timestamp created_at
        timestamp updated_at
    }

    CUSTOMER_ADDRESS {
        uuid id PK
        uuid customer_id FK
        varchar address_type "BILLING/SHIPPING"
        varchar line1
        varchar line2
        varchar city
        varchar state
        varchar country
        varchar postal_code
        boolean is_default
        timestamp created_at
    }

    OUTBOX {
        uuid id PK
        varchar aggregate_type
        varchar aggregate_id
        varchar event_type
        jsonb payload
        varchar status "PENDING/PUBLISHED/FAILED"
        timestamp created_at
        timestamp published_at
    }

    GLOBAL_CUSTOMERS ||--o{ CUSTOMERS_DETAILS : "global identity"
    CUSTOMERS_DETAILS ||--o{ CUSTOMER_KEYS : "encryption keys"
    CUSTOMERS_DETAILS ||--o{ CUSTOMER_BNPL_DETAILS : "BNPL providers"
    CUSTOMERS_DETAILS ||--o{ CUSTOMER_ADDRESS : "addresses"
```

## DDL Statements

### customers_details

```sql
CREATE TABLE customers_details (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id     VARCHAR(50) NOT NULL,
    customer_id     VARCHAR(100) NOT NULL,
    mobile_number   VARCHAR(500),          -- AES encrypted
    country_code    VARCHAR(10) DEFAULT '+91',
    email           VARCHAR(500),          -- AES encrypted
    first_name      VARCHAR(500),          -- AES encrypted
    last_name       VARCHAR(500),          -- AES encrypted
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_merchant_customer UNIQUE (merchant_id, customer_id)
);

CREATE INDEX idx_customers_merchant_id ON customers_details(merchant_id);
CREATE INDEX idx_customers_mobile ON customers_details(mobile_number);
CREATE INDEX idx_customers_status ON customers_details(status);
```

### global_customers

```sql
CREATE TABLE global_customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile_number   VARCHAR(500) NOT NULL,  -- AES encrypted, unique global identity
    country_code    VARCHAR(10) NOT NULL DEFAULT '+91',
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_global_mobile UNIQUE (mobile_number, country_code)
);

-- V8: Mobile number is required
ALTER TABLE global_customers ALTER COLUMN mobile_number SET NOT NULL;
```

### customer_keys

```sql
CREATE TABLE customer_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers_details(id),
    key_type        VARCHAR(20) NOT NULL,   -- ENCRYPTION, SIGNING
    encrypted_key   TEXT NOT NULL,          -- Encrypted with master key
    key_version     VARCHAR(10) NOT NULL DEFAULT 'v1',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_customer_keys_cust_id (customer_id)
);
```

### customer_bnpl_details

```sql
CREATE TABLE customer_bnpl_details (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id             UUID NOT NULL REFERENCES customers_details(id),
    provider                VARCHAR(50) NOT NULL,    -- SIMPL, LAZYPAY, ZESTMONEY
    provider_customer_id    VARCHAR(200),
    status                  VARCHAR(20) DEFAULT 'ACTIVE',
    credit_limit            DECIMAL(18,2),
    eligibility_status      VARCHAR(20),
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uk_customer_provider UNIQUE (customer_id, provider)
);
```

### outbox (Event Sourcing)

```sql
CREATE TABLE outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  VARCHAR(100) NOT NULL,  -- CUSTOMER, TOKEN, OTP
    aggregate_id    VARCHAR(200) NOT NULL,  -- Changed from UUID to VARCHAR in V4
    event_type      VARCHAR(100) NOT NULL,  -- CUSTOMER_CREATED, TOKEN_SAVED, etc.
    payload         JSONB NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at    TIMESTAMP WITH TIME ZONE,
    retry_count     INT DEFAULT 0,
    error_message   TEXT,
    
    INDEX idx_outbox_status (status),
    INDEX idx_outbox_created (created_at)
);

-- V3: Performance indexes
CREATE INDEX idx_outbox_aggregate ON outbox(aggregate_type, aggregate_id);
```

## Data Flow

```mermaid
flowchart TD
    A[API Request] --> B{Customer Exists?}
    B -->|No| C[Create Customer]
    C --> D[Generate Customer Keys]
    D --> E[Encrypt PII with AES]
    E --> F[Store in customers_details]
    F --> G[Publish CUSTOMER_CREATED via Outbox]
    
    B -->|Yes| H[Fetch Customer]
    H --> I[Decrypt PII]
    I --> J[Return Customer Data]
    
    K[Save Token Request] --> L[Validate Customer]
    L --> M[Delegate to Token Mgm Service]
    M --> N[Store Token Reference]
    N --> O[Publish TOKEN_SAVED via Outbox]
```

## Encryption at Rest

All PII fields are encrypted using AES-256 before storage:
- `mobile_number` - AES encrypted
- `email` - AES encrypted
- `first_name` / `last_name` - AES encrypted
- Customer-specific keys stored in `customer_keys` table
- Master encryption key managed via AWS Secrets Manager
