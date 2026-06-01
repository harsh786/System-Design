# Affordability Platform - Database Schema Design

## 1. Database Architecture Overview

The platform uses a **polyglot persistence** strategy:

| Database | Engine | Purpose | Services |
|----------|--------|---------|----------|
| **Affordability DB** | PostgreSQL 14+ | NXT platform transactions, offers, configs | ReadServ, TransactionServ, OfferMgmtServ, CacheMgmtServ |
| **PLUTUS_HUBDB** | MS SQL Server | Legacy POS transactions | TxnProcessorServ |
| **AUXIDB** | MS SQL Server | Auxiliary/NBFC transactions | TxnProcessorServ |
| **paylater_catalogue** | MongoDB 4.4+ | EMI scheme catalog | Paylater_Catalogueserv |
| **Redshift** | Amazon Redshift | Analytics & reporting | Analytics Service |

---

## 2. PostgreSQL Schema (Affordability DB - NXT Platform)

### 2.1 Transaction Domain

#### `affordability_transaction` (Core Transaction Table)
```sql
CREATE TABLE affordability_transaction (
    id                      BIGSERIAL PRIMARY KEY,
    status                  VARCHAR(10) NOT NULL DEFAULT 'A',  -- A=Active, I=Inactive (soft delete)
    client_id               VARCHAR(50) NOT NULL,
    client_type             VARCHAR(30) NOT NULL,              -- MERCHANT, STORE
    issuer_id               BIGINT,
    parent_issuer_id        BIGINT,
    transaction_amount      BIGINT NOT NULL,                   -- Amount in paisa (INR cents)
    tenure_id               BIGINT,
    customer_phone_number   VARCHAR(50),
    customer_name           VARCHAR(100),
    customer_email          VARCHAR(200),
    phone_type              VARCHAR(20),                       -- PhoneTypeEnum
    txn_type                VARCHAR(30) NOT NULL,              -- TxnTypeEnum
    program_type            VARCHAR(50) NOT NULL,              -- BRAND_EMI, BANK_EMI, MY_EMI, etc.
    integration_type        VARCHAR(30) DEFAULT 'DEFAULT',
    transaction_status      VARCHAR(30) NOT NULL,              -- INITIATED, APPROVED, SETTLED, etc.
    encrypted_pan_number    BYTEA,                             -- HSM-encrypted card PAN
    invoice_number          VARCHAR(50),
    self_expiring_date_time TIMESTAMP,                         -- Auto-cancel after this time
    parent_txn_id           BIGINT,                            -- FK for refund/void parent reference
    tenant                  VARCHAR(30) NOT NULL DEFAULT 'PL.IN',
    currency                VARCHAR(10) DEFAULT 'INR',
    channel                 VARCHAR(20) NOT NULL,              -- ONLINE, OFFLINE
    emi_flow                VARCHAR(50),                       -- EmiFlowEnum variant
    created_date_time       TIMESTAMP DEFAULT NOW(),
    updated_date_time       TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_parent_txn FOREIGN KEY (parent_txn_id) REFERENCES affordability_transaction(id)
);

CREATE INDEX idx_txn_client ON affordability_transaction(client_id, client_type);
CREATE INDEX idx_txn_status ON affordability_transaction(transaction_status);
CREATE INDEX idx_txn_invoice ON affordability_transaction(invoice_number);
CREATE INDEX idx_txn_parent ON affordability_transaction(parent_txn_id);
CREATE INDEX idx_txn_expiry ON affordability_transaction(self_expiring_date_time) WHERE transaction_status = 'INITIATED';
```

#### `affordability_transaction_extension` (Extended Transaction Data)
```sql
CREATE TABLE affordability_transaction_extension (
    id                          BIGSERIAL PRIMARY KEY,
    affordability_txn_id        BIGINT NOT NULL,
    batch_id                    INTEGER,
    roc                         INTEGER,
    unique_client_txn_reference VARCHAR(100),
    acquirer_transaction_id     VARCHAR(100),
    acquirer_name               VARCHAR(50),
    auth_code                   VARCHAR(30),
    rrn                         VARCHAR(30),
    offer_json                  TEXT,                    -- Full EMI calculation response (JSON)
    card_hash_data              VARCHAR(200),            -- SHA hash of card for velocity
    cancellation_detail         TEXT,                    -- JSON cancellation metadata
    tid                         VARCHAR(30),             -- Terminal ID
    mid                         VARCHAR(30),             -- Merchant ID
    client_group_id             BIGINT,
    status                      VARCHAR(10) DEFAULT 'A',
    created_date_time           TIMESTAMP DEFAULT NOW(),
    updated_date_time           TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_txn_ext FOREIGN KEY (affordability_txn_id) 
        REFERENCES affordability_transaction(id)
);

CREATE INDEX idx_txn_ext_txn_id ON affordability_transaction_extension(affordability_txn_id);
CREATE INDEX idx_txn_ext_rrn ON affordability_transaction_extension(rrn);
CREATE INDEX idx_txn_ext_acq_txn ON affordability_transaction_extension(acquirer_transaction_id);
```

#### `affordability_transaction_product_details` (Product Line Items)
```sql
CREATE TABLE affordability_transaction_product_details (
    id                      BIGSERIAL PRIMARY KEY,
    affordability_txn_id    BIGINT NOT NULL,
    product_id              BIGINT,
    product_amount          BIGINT,                     -- Amount in paisa
    product_type            VARCHAR(50),
    ean_code                VARCHAR(50),
    serial_number           VARCHAR(100),
    imei_number             VARCHAR(50),
    quantity                INTEGER DEFAULT 1,
    status                  VARCHAR(10) DEFAULT 'A',
    created_date_time       TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_txn_product FOREIGN KEY (affordability_txn_id) 
        REFERENCES affordability_transaction(id)
);
```

#### `affordability_transaction_task_details` (Task Execution Log)
```sql
CREATE TABLE affordability_transaction_task_details (
    id                      BIGSERIAL PRIMARY KEY,
    affordability_txn_id    BIGINT NOT NULL,
    task_name               VARCHAR(100) NOT NULL,      -- e.g., VELOCITY_CHECK, CREDIT_LIMIT_BLOCK
    task_type               VARCHAR(50),
    validation_type         VARCHAR(50),
    task_status             VARCHAR(30) NOT NULL,        -- NOT_APPLICABLE, INITIATED, SUCCESS, FAILED, REVERSED
    task_input              TEXT,                        -- JSON request payload
    task_output             TEXT,                        -- JSON response payload
    url                     VARCHAR(500),                -- External service URL called
    error_code              VARCHAR(50),
    error_message           TEXT,
    status                  VARCHAR(10) DEFAULT 'A',
    created_date_time       TIMESTAMP DEFAULT NOW(),
    updated_date_time       TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_txn_task FOREIGN KEY (affordability_txn_id) 
        REFERENCES affordability_transaction(id)
);

CREATE INDEX idx_task_txn ON affordability_transaction_task_details(affordability_txn_id);
CREATE INDEX idx_task_status ON affordability_transaction_task_details(task_status);
```

#### `affordability_online_bank_emi_txn_ledger` (EMI Transaction Ledger)
```sql
CREATE TABLE affordability_online_bank_emi_txn_ledger (
    id                          BIGSERIAL PRIMARY KEY,
    affordability_txn_id        BIGINT NOT NULL,
    action_type                 VARCHAR(30) NOT NULL,    -- SALE, VOID, REFUND, PARTIAL_REFUND, PARTIAL_VOID
    
    -- Amount Fields (all in paisa)
    transaction_amount          BIGINT NOT NULL,
    loan_amount                 BIGINT,
    auth_amount                 BIGINT,
    net_payment_amount          BIGINT,
    
    -- EMI Calculation
    monthly_emi_amount          BIGINT,
    total_emi_amount            BIGINT,
    interest_amount             BIGINT,
    interest_rate_percentage    DECIMAL(10,4),
    emi_type                    VARCHAR(30),
    processing_fee_amount       BIGINT,
    processing_fee_percentage   DECIMAL(10,4),
    
    -- Discount Breakup
    discount_amount             BIGINT,
    discount_percentage         DECIMAL(10,4),
    discount_type               VARCHAR(30),
    brand_discount_amount       BIGINT,
    merchant_discount_amount    BIGINT,
    issuer_discount_amount      BIGINT,
    dealer_discount_amount      BIGINT,
    
    -- Subvention Breakup
    subvention_amount           BIGINT,
    subvention_percentage       DECIMAL(10,4),
    subvention_type             VARCHAR(30),            -- INSTANT, POST, PRE, CIB
    brand_subvention_amount     BIGINT,
    merchant_subvention_amount  BIGINT,
    issuer_subvention_amount    BIGINT,
    dealer_subvention_amount    BIGINT,
    
    -- Split EMI
    split_emi_amount            BIGINT,
    split_emi_percentage        DECIMAL(10,4),
    
    -- Down Payment
    down_payment_amount         BIGINT,
    
    -- Convenience Fee
    convenience_tax_amount          BIGINT,
    convenience_applicable_fee_amt  BIGINT,
    
    -- Coupon
    cart_coupon_discount         BIGINT,
    total_coupon_discount        BIGINT,
    
    -- Card Details (hashed/masked)
    pan_sha1                    VARCHAR(100),
    pan_sha2                    VARCHAR(100),
    masked_card_hash            VARCHAR(100),
    pan_last_four_digit         VARCHAR(4),
    card_holder_name            VARCHAR(100),
    card_issuer_name            VARCHAR(100),
    
    -- Acquirer
    acquirer_id                 BIGINT,
    acquirer_name               VARCHAR(50),
    acquirer_transaction_id     VARCHAR(100),
    rrn                         VARCHAR(30),
    auth_code                   VARCHAR(30),
    tid                         VARCHAR(30),
    mid                         VARCHAR(30),
    
    -- Tenure
    tenure_id                   BIGINT,
    tenure_type                 VARCHAR(30),
    tenure_name                 VARCHAR(50),
    tenure_uid                  VARCHAR(50),
    
    -- Offer
    offer_code                  VARCHAR(100),
    
    -- Metadata
    status                      VARCHAR(10) DEFAULT 'A',
    created_date_time           TIMESTAMP DEFAULT NOW(),
    updated_date_time           TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_ledger_txn FOREIGN KEY (affordability_txn_id) 
        REFERENCES affordability_transaction(id)
);

CREATE INDEX idx_ledger_txn ON affordability_online_bank_emi_txn_ledger(affordability_txn_id);
CREATE INDEX idx_ledger_action ON affordability_online_bank_emi_txn_ledger(action_type);
```

---

### 2.2 Offer Domain

#### `offer` (Offer Definition)
```sql
CREATE TABLE offer (
    id                      BIGSERIAL PRIMARY KEY,
    name                    VARCHAR(200) NOT NULL,
    description             TEXT,
    terms                   TEXT,
    campaign_id             BIGINT,
    start_date              TIMESTAMP NOT NULL,
    end_date                TIMESTAMP NOT NULL,
    start_hour              INTEGER,                    -- 0-23
    end_hour                INTEGER,                    -- 0-23
    applicable_days_bitmap  VARCHAR(7),                 -- '1111111' (Mon-Sun bitmap)
    program_type            VARCHAR(50) NOT NULL,       -- BRAND_EMI, BANK_EMI, etc.
    payment_type            VARCHAR(30),                -- EMI, CARD, CARDLESS
    partner_id              BIGINT,
    brand_id                BIGINT,
    state                   VARCHAR(30) NOT NULL,       -- DRAFT, PENDING_FOR_APPROVAL, APPROVED, PAUSED, REJECTED, INACTIVATED
    status                  VARCHAR(10) DEFAULT 'A',
    entity_id               VARCHAR(100),
    entity_type             VARCHAR(50),
    addon                   VARCHAR(10),                -- TopUp offer type (D=discount)
    offer_type              VARCHAR(50),
    tenant_name             VARCHAR(30) DEFAULT 'PL.IN',
    created_by              VARCHAR(100),
    updated_by              VARCHAR(100),
    created_date_time       TIMESTAMP DEFAULT NOW(),
    updated_date_time       TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_offer_campaign FOREIGN KEY (campaign_id) REFERENCES campaign(id)
);

CREATE INDEX idx_offer_state ON offer(state, status);
CREATE INDEX idx_offer_dates ON offer(start_date, end_date);
CREATE INDEX idx_offer_program ON offer(program_type);
CREATE INDEX idx_offer_brand ON offer(brand_id);
CREATE INDEX idx_offer_partner ON offer(partner_id);
CREATE INDEX idx_offer_tenant ON offer(tenant_name);
```

#### `offer_parameters` (Offer Configuration)
```sql
CREATE TABLE offer_parameters (
    id                              BIGSERIAL PRIMARY KEY,
    offer_id                        BIGINT NOT NULL,
    discount_applicable             BOOLEAN DEFAULT FALSE,
    isv_applicable                  BOOLEAN DEFAULT FALSE,
    subvention_applicable           BOOLEAN DEFAULT FALSE,
    advance_emi_applicable          BOOLEAN DEFAULT FALSE,
    split_emi_applicable            BOOLEAN DEFAULT FALSE,
    down_payment_fixed_amount       BIGINT,
    min_amount                      BIGINT,                 -- Minimum txn amount (paisa)
    max_amount                      BIGINT,                 -- Maximum txn amount (paisa)
    
    -- Discount Configuration
    discount_total_fixed_amount     BIGINT,
    discount_total_percentage       DECIMAL(10,4),
    discount_total_max_amount       BIGINT,
    discount_type                   VARCHAR(30),            -- INSTANT, deferred
    discount_deferred_duration_type VARCHAR(20),
    discount_deferred_duration_value INTEGER,
    discount_min_amount             BIGINT,
    discount_max_amount             BIGINT,
    
    -- Subvention Configuration
    subvention_type                 VARCHAR(30),            -- INSTANT, POST, PRE, CIB
    subvention_total_fixed_amount   BIGINT,
    subvention_total_percentage     DECIMAL(10,4),
    subvention_total_max_amount     BIGINT,
    
    -- Behavioral Flags
    mobile_number_mandatory         BOOLEAN DEFAULT FALSE,
    offer_auto_apply                BOOLEAN DEFAULT TRUE,
    issuer_min_amount               BIGINT,
    issuer_max_amount               BIGINT,
    
    currency_code                   VARCHAR(10) DEFAULT 'INR',
    state                           VARCHAR(30) DEFAULT 'ACTIVE',
    status                          VARCHAR(10) DEFAULT 'A',
    created_date_time               TIMESTAMP DEFAULT NOW(),
    updated_date_time               TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_offer_params FOREIGN KEY (offer_id) REFERENCES offer(id)
);

CREATE INDEX idx_offer_params_offer ON offer_parameters(offer_id);
```

#### `subvention_parameters` (Multi-Party Subvention Breakup)
```sql
CREATE TABLE subvention_parameters (
    id                              BIGSERIAL PRIMARY KEY,
    offer_parameter_id              BIGINT NOT NULL,
    
    -- Merchant Contribution
    merchant_offered_fixed_amount   BIGINT,
    merchant_offered_percentage     DECIMAL(10,4),
    merchant_offered_max_amount     BIGINT,
    merchant_offered_sequence       INTEGER,               -- Priority order
    merchant_share                  DECIMAL(10,4),         -- Actual share %
    
    -- Brand Contribution
    brand_offered_fixed_amount      BIGINT,
    brand_offered_percentage        DECIMAL(10,4),
    brand_offered_max_amount        BIGINT,
    brand_offered_sequence          INTEGER,
    brand_share                     DECIMAL(10,4),
    
    -- Issuer Contribution
    issuer_offered_fixed_amount     BIGINT,
    issuer_offered_percentage       DECIMAL(10,4),
    issuer_offered_max_amount       BIGINT,
    issuer_offered_sequence         INTEGER,
    issuer_share                    DECIMAL(10,4),
    
    -- Dealer Contribution
    dealer_offered_fixed_amount     BIGINT,
    dealer_offered_percentage       DECIMAL(10,4),
    dealer_offered_max_amount       BIGINT,
    dealer_offered_sequence         INTEGER,
    dealer_share                    DECIMAL(10,4),
    
    status                          VARCHAR(10) DEFAULT 'A',
    created_date_time               TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_subvention_param FOREIGN KEY (offer_parameter_id) 
        REFERENCES offer_parameters(id)
);
```

#### `discount_parameters` (Multi-Party Discount Breakup)
```sql
CREATE TABLE discount_parameters (
    id                              BIGSERIAL PRIMARY KEY,
    offer_parameter_id              BIGINT NOT NULL,
    
    -- Same structure as subvention_parameters
    merchant_offered_fixed_amount   BIGINT,
    merchant_offered_percentage     DECIMAL(10,4),
    merchant_offered_max_amount     BIGINT,
    merchant_offered_sequence       INTEGER,
    merchant_share                  DECIMAL(10,4),
    
    brand_offered_fixed_amount      BIGINT,
    brand_offered_percentage        DECIMAL(10,4),
    brand_offered_max_amount        BIGINT,
    brand_offered_sequence          INTEGER,
    brand_share                     DECIMAL(10,4),
    
    issuer_offered_fixed_amount     BIGINT,
    issuer_offered_percentage       DECIMAL(10,4),
    issuer_offered_max_amount       BIGINT,
    issuer_offered_sequence         INTEGER,
    issuer_share                    DECIMAL(10,4),
    
    dealer_offered_fixed_amount     BIGINT,
    dealer_offered_percentage       DECIMAL(10,4),
    dealer_offered_max_amount       BIGINT,
    dealer_offered_sequence         INTEGER,
    dealer_share                    DECIMAL(10,4),
    
    status                          VARCHAR(10) DEFAULT 'A',
    created_date_time               TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_discount_param FOREIGN KEY (offer_parameter_id) 
        REFERENCES offer_parameters(id)
);
```

#### `split_emi_parameters`
```sql
CREATE TABLE split_emi_parameters (
    id                      BIGSERIAL PRIMARY KEY,
    offer_parameter_id      BIGINT NOT NULL,
    fixed_amount            BIGINT,
    percentage              DECIMAL(10,4),
    min_amount              BIGINT,
    max_amount              BIGINT,
    enabled_on_txn_amount   BOOLEAN DEFAULT TRUE,
    status                  VARCHAR(10) DEFAULT 'A',
    created_date_time       TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_split_emi_param FOREIGN KEY (offer_parameter_id) 
        REFERENCES offer_parameters(id)
);
```

---

### 2.3 Issuer & EMI Configuration Domain

#### `issuer` (Bank/Financial Institution)
```sql
CREATE TABLE issuer (
    id                  BIGSERIAL PRIMARY KEY,
    issuer_external_id  VARCHAR(50) UNIQUE,
    name                VARCHAR(100) NOT NULL,
    display_name        VARCHAR(200),
    type                VARCHAR(30),                    -- CC, DC, NBFC, NTB, CARDLESS, UPI
    priority            INTEGER DEFAULT 0,
    offer_code_enabled  BOOLEAN DEFAULT FALSE,
    parent_issuer_id    BIGINT,
    sub_issuer_type     VARCHAR(30),
    entity_id           VARCHAR(100),
    resource_id         VARCHAR(100),
    status              VARCHAR(10) DEFAULT 'A',
    tenant_name         VARCHAR(30) DEFAULT 'PL.IN',
    created_date_time   TIMESTAMP DEFAULT NOW(),
    updated_date_time   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_issuer_external ON issuer(issuer_external_id);
CREATE INDEX idx_issuer_type ON issuer(type);
```

#### `issuer_emi_config` (EMI Rate Configuration per Issuer/Tenure)
```sql
CREATE TABLE issuer_emi_config (
    id                          BIGSERIAL PRIMARY KEY,
    issuer_id                   BIGINT NOT NULL,
    tenure_id                   BIGINT NOT NULL,
    brand_id                    BIGINT,
    program_type                VARCHAR(50) NOT NULL,
    min_amount                  BIGINT,                 -- Min eligible amount (paisa)
    max_amount                  BIGINT,                 -- Max eligible amount (paisa)
    roi                         DECIMAL(10,4),          -- Rate of Interest (annual %)
    processing_fee_fixed_amount BIGINT,
    processing_fee_percentage   DECIMAL(10,4),
    processing_fee_max_amount   BIGINT,
    processing_fee_min_amount   BIGINT,
    subvention_type             VARCHAR(30),
    subvention_borne_by         VARCHAR(50),
    channel                     VARCHAR(20),            -- ONLINE, OFFLINE
    currency_code               VARCHAR(10) DEFAULT 'INR',
    client_group_id             BIGINT,
    status                      VARCHAR(10) DEFAULT 'A',
    created_date_time           TIMESTAMP DEFAULT NOW(),
    updated_date_time           TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_emi_config_issuer FOREIGN KEY (issuer_id) REFERENCES issuer(id),
    CONSTRAINT fk_emi_config_tenure FOREIGN KEY (tenure_id) REFERENCES tenure(id)
);

CREATE INDEX idx_emi_config_issuer ON issuer_emi_config(issuer_id, program_type);
CREATE INDEX idx_emi_config_tenure ON issuer_emi_config(tenure_id);
CREATE INDEX idx_emi_config_brand ON issuer_emi_config(brand_id);
CREATE INDEX idx_emi_config_channel ON issuer_emi_config(channel);
```

#### `tenure` (EMI Tenure/Duration)
```sql
CREATE TABLE tenure (
    id              BIGSERIAL PRIMARY KEY,
    type            VARCHAR(30) NOT NULL,           -- MONTHS, DAYS, etc. (TenureTypeEnum)
    name            VARCHAR(50) NOT NULL,           -- e.g., "3 Months", "6 Months"
    value           INTEGER NOT NULL,               -- Numeric value (3, 6, 9, 12, 18, 24)
    status          VARCHAR(10) DEFAULT 'A',
    created_date_time TIMESTAMP DEFAULT NOW()
);
```

#### `offer_parameter_tenure_map`
```sql
CREATE TABLE offer_parameter_tenure_map (
    id                  BIGSERIAL PRIMARY KEY,
    offer_parameter_id  BIGINT NOT NULL,
    tenure_id           BIGINT NOT NULL,
    status              VARCHAR(10) DEFAULT 'A',
    
    CONSTRAINT fk_opt_param FOREIGN KEY (offer_parameter_id) REFERENCES offer_parameters(id),
    CONSTRAINT fk_opt_tenure FOREIGN KEY (tenure_id) REFERENCES tenure(id),
    CONSTRAINT uq_param_tenure UNIQUE (offer_parameter_id, tenure_id)
);
```

---

### 2.4 BIN Range Domain

#### `bin_range_group`
```sql
CREATE TABLE bin_range_group (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    issuer_id   BIGINT,
    status      VARCHAR(10) DEFAULT 'A',
    tenant_name VARCHAR(30) DEFAULT 'PL.IN',
    
    CONSTRAINT fk_brg_issuer FOREIGN KEY (issuer_id) REFERENCES issuer(id)
);
```

#### `bin_range`
```sql
CREATE TABLE bin_range (
    id                  BIGSERIAL PRIMARY KEY,
    bin_range_group_id  BIGINT NOT NULL,
    start_bin           VARCHAR(20) NOT NULL,
    end_bin             VARCHAR(20) NOT NULL,
    card_type           VARCHAR(20),               -- CREDIT, DEBIT, PREPAID
    status              VARCHAR(10) DEFAULT 'A',
    
    CONSTRAINT fk_bin_group FOREIGN KEY (bin_range_group_id) REFERENCES bin_range_group(id)
);

CREATE INDEX idx_bin_range ON bin_range(start_bin, end_bin);
```

#### `bin_group_issuer_offer` (BIN-level offer overrides)
```sql
CREATE TABLE bin_group_issuer_offer (
    id                  BIGSERIAL PRIMARY KEY,
    bin_range_group_id  BIGINT NOT NULL,
    issuer_id           BIGINT NOT NULL,
    offer_parameter_id  BIGINT,
    roi                 DECIMAL(10,4),              -- Override ROI for this BIN group
    start_date          TIMESTAMP,
    end_date            TIMESTAMP,
    tenant_name         VARCHAR(30),
    status              VARCHAR(10) DEFAULT 'A'
);
```

---

### 2.5 Client/Merchant Domain

#### `client`
```sql
CREATE TABLE client (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    external_id     VARCHAR(100),                  -- Merchant's external reference
    parent_id       BIGINT,                        -- Hierarchy support
    partner_id      BIGINT,
    display_name    VARCHAR(200),
    client_type     VARCHAR(30) NOT NULL,           -- MERCHANT, STORE, POS
    channel         VARCHAR(20),                    -- ONLINE, OFFLINE
    tenant_name     VARCHAR(30) DEFAULT 'PL.IN',
    brand_id        BIGINT,
    offer_cache_ttl_minutes INTEGER DEFAULT 60,    -- Per-client cache TTL override
    status          VARCHAR(10) DEFAULT 'A',
    created_date_time TIMESTAMP DEFAULT NOW(),
    updated_date_time TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_client_external ON client(external_id, client_type, channel);
CREATE INDEX idx_client_tenant ON client(tenant_name);
```

#### `client_group_map`
```sql
CREATE TABLE client_group_map (
    id              BIGSERIAL PRIMARY KEY,
    client_id       BIGINT NOT NULL,
    client_group_id BIGINT NOT NULL,
    status          VARCHAR(10) DEFAULT 'A',
    
    CONSTRAINT fk_cgm_client FOREIGN KEY (client_id) REFERENCES client(id)
);
```

#### `client_issuer_offer_association`
```sql
CREATE TABLE client_issuer_offer_association (
    id              BIGSERIAL PRIMARY KEY,
    client_group_id BIGINT NOT NULL,
    offer_id        BIGINT NOT NULL,
    start_date      TIMESTAMP,
    end_date        TIMESTAMP,
    status          VARCHAR(10) DEFAULT 'A',
    
    CONSTRAINT fk_cioa_offer FOREIGN KEY (offer_id) REFERENCES offer(id)
);

CREATE INDEX idx_cioa_client ON client_issuer_offer_association(client_group_id);
CREATE INDEX idx_cioa_offer ON client_issuer_offer_association(offer_id);
```

---

### 2.6 Product Domain

#### `product`
```sql
CREATE TABLE product (
    id                      BIGSERIAL PRIMARY KEY,
    name                    VARCHAR(200) NOT NULL,
    brand_id                BIGINT,
    product_category_id     BIGINT,
    product_family_id       BIGINT,
    sku_code                VARCHAR(100),
    brand_validation_code   VARCHAR(100),
    min_price               BIGINT,
    max_price               BIGINT,
    indicative_price        BIGINT,
    status                  VARCHAR(10) DEFAULT 'A',
    tenant_name             VARCHAR(30) DEFAULT 'PL.IN',
    created_date_time       TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_product_brand FOREIGN KEY (brand_id) REFERENCES brand(id)
);

CREATE INDEX idx_product_brand ON product(brand_id);
CREATE INDEX idx_product_sku ON product(sku_code);
```

#### `product_offer_association`
```sql
CREATE TABLE product_offer_association (
    id              BIGSERIAL PRIMARY KEY,
    product_id      BIGINT NOT NULL,
    offer_id        BIGINT NOT NULL,
    start_date      TIMESTAMP,
    end_date        TIMESTAMP,
    program_type    VARCHAR(50),
    status          VARCHAR(10) DEFAULT 'A',
    
    CONSTRAINT fk_poa_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_poa_offer FOREIGN KEY (offer_id) REFERENCES offer(id)
);

CREATE INDEX idx_poa_product ON product_offer_association(product_id);
CREATE INDEX idx_poa_offer ON product_offer_association(offer_id);
```

---

### 2.7 Budget & Campaign Domain

#### `campaign`
```sql
CREATE TABLE campaign (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    budget          BIGINT,
    max_txn_count   INTEGER,
    partner_id      BIGINT,
    currency_code   VARCHAR(10) DEFAULT 'INR',
    start_date      TIMESTAMP NOT NULL,
    end_date        TIMESTAMP NOT NULL,
    entity_id       VARCHAR(100),
    entity_type     VARCHAR(50),
    status          VARCHAR(10) DEFAULT 'A',
    tenant_name     VARCHAR(30) DEFAULT 'PL.IN',
    created_date_time TIMESTAMP DEFAULT NOW()
);
```

#### `budget`
```sql
CREATE TABLE budget (
    id                                  BIGSERIAL PRIMARY KEY,
    name                                VARCHAR(200) NOT NULL,
    display_name                        VARCHAR(200),
    fund_type                           VARCHAR(30),
    sponsor_type                        VARCHAR(30),       -- MERCHANT, BRAND, ISSUER, DEALER
    sponsor_type_id                     BIGINT,
    sponsor_type_name                   VARCHAR(200),
    threshold_amount                    BIGINT,            -- Total budget cap (paisa)
    total_amount_consumed               BIGINT DEFAULT 0,  -- Current consumption
    threshold_subvention_amount         BIGINT,
    threshold_subvention_consumed       BIGINT DEFAULT 0,
    threshold_discount_amount           BIGINT,
    threshold_discount_consumed         BIGINT DEFAULT 0,
    type                                VARCHAR(30),
    is_strict_partner_match_required    BOOLEAN DEFAULT FALSE,
    is_threshold_breach_restricted      BOOLEAN DEFAULT FALSE,
    is_global_budget_applicable         BOOLEAN DEFAULT FALSE,
    status                              VARCHAR(10) DEFAULT 'A',
    tenant_name                         VARCHAR(30) DEFAULT 'PL.IN',
    created_date_time                   TIMESTAMP DEFAULT NOW(),
    updated_date_time                   TIMESTAMP DEFAULT NOW()
);
```

#### `affordability_txn_budget_ledger` (Budget Consumption Tracking)
```sql
CREATE TABLE affordability_txn_budget_ledger (
    id                  BIGSERIAL PRIMARY KEY,
    budget_id           BIGINT NOT NULL,
    affordability_txn_id BIGINT NOT NULL,
    amount_consumed     BIGINT NOT NULL,
    action_type         VARCHAR(30),               -- DEBIT, CREDIT (reversal)
    created_date_time   TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_budget_ledger FOREIGN KEY (budget_id) REFERENCES budget(id)
);
```

---

### 2.8 Velocity (Rate Limiting) Domain

#### `velocity_rule_configuration`
```sql
CREATE TABLE velocity_rule_configuration (
    id                          BIGSERIAL PRIMARY KEY,
    name                        VARCHAR(200),
    type                        VARCHAR(30) NOT NULL,   -- CARD_HASH, MOBILE_NUMBER, CARDLESS
    frequency                   VARCHAR(30),            -- DAILY, WEEKLY, MONTHLY, CAMPAIGN
    validity_start_date         TIMESTAMP,
    validity_end_date           TIMESTAMP,
    state                       VARCHAR(30) DEFAULT 'ACTIVE',
    discount_velocity_count     INTEGER,                -- Max discount txns allowed
    subvention_velocity_count   INTEGER,                -- Max subvention txns allowed
    combined_velocity_count     INTEGER,                -- Combined cap
    source                      VARCHAR(30),
    is_default                  BOOLEAN DEFAULT FALSE,
    brand_id                    BIGINT,
    status                      VARCHAR(10) DEFAULT 'A',
    tenant_name                 VARCHAR(30) DEFAULT 'PL.IN',
    created_date_time           TIMESTAMP DEFAULT NOW()
);
```

#### `velocity_txn_details` / `velocity_txn_map`
```sql
CREATE TABLE velocity_txn_details (
    id                      BIGSERIAL PRIMARY KEY,
    velocity_rule_id        BIGINT NOT NULL,
    identifier_value        VARCHAR(200),           -- Card hash or phone number
    identifier_type         VARCHAR(30),
    txn_count               INTEGER DEFAULT 0,
    window_start            TIMESTAMP,
    window_end              TIMESTAMP,
    status                  VARCHAR(10) DEFAULT 'A'
);

CREATE TABLE velocity_txn_map (
    id                      BIGSERIAL PRIMARY KEY,
    velocity_txn_detail_id  BIGINT NOT NULL,
    affordability_txn_id    BIGINT NOT NULL,
    action_type             VARCHAR(30),            -- INCREMENT, DECREMENT
    created_date_time       TIMESTAMP DEFAULT NOW()
);
```

---

### 2.9 Settlement Domain

#### `affordability_fund_settlement`
```sql
CREATE TABLE affordability_fund_settlement (
    id                      BIGSERIAL PRIMARY KEY,
    affordability_txn_id    BIGINT NOT NULL,
    settlement_type         VARCHAR(30),
    settlement_status       VARCHAR(30),
    total_settlement_amount BIGINT,
    settlement_date         TIMESTAMP,
    status                  VARCHAR(10) DEFAULT 'A',
    created_date_time       TIMESTAMP DEFAULT NOW()
);
```

#### `affordability_fund_settlement_detail`
```sql
CREATE TABLE affordability_fund_settlement_detail (
    id                          BIGSERIAL PRIMARY KEY,
    fund_settlement_id          BIGINT NOT NULL,
    party_type                  VARCHAR(30),        -- MERCHANT, BRAND, ISSUER, DEALER
    party_id                    BIGINT,
    settlement_amount           BIGINT,
    settlement_type             VARCHAR(30),        -- SUBVENTION, DISCOUNT, EMI_INTEREST
    status                      VARCHAR(10) DEFAULT 'A',
    created_date_time           TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_settlement_detail FOREIGN KEY (fund_settlement_id) 
        REFERENCES affordability_fund_settlement(id)
);
```

---

### 2.10 Audit & Event Domain

#### `offer_state_change_history`
```sql
CREATE TABLE offer_state_change_history (
    id              BIGSERIAL PRIMARY KEY,
    offer_id        BIGINT NOT NULL,
    original_state  VARCHAR(30),
    final_state     VARCHAR(30),
    comment         TEXT,
    created_by      VARCHAR(100),
    created_date_time TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_osch_offer FOREIGN KEY (offer_id) REFERENCES offer(id)
);
```

#### `offer_update_events` (Event Sourcing for Cache)
```sql
CREATE TABLE offer_update_events (
    id                  BIGSERIAL PRIMARY KEY,
    offer_id            BIGINT,
    offer_parameter_id  BIGINT,
    update_event        VARCHAR(100) NOT NULL,      -- CREATE, UPDATE, DELETE, STATE_CHANGE
    processing_status   VARCHAR(30) DEFAULT 'PENDING',  -- PENDING, PROCESSED, FAILED
    created_date_time   TIMESTAMP DEFAULT NOW(),
    processed_date_time TIMESTAMP
);

CREATE INDEX idx_oue_status ON offer_update_events(processing_status) WHERE processing_status = 'PENDING';
```

#### `affordability_idempotent_keys`
```sql
CREATE TABLE affordability_idempotent_keys (
    id                  BIGSERIAL PRIMARY KEY,
    idempotent_key      VARCHAR(200) UNIQUE NOT NULL,
    affordability_txn_id BIGINT NOT NULL,
    operation_type      VARCHAR(30),               -- REFUND, VOID, SETTLE
    status              VARCHAR(10) DEFAULT 'A',
    created_date_time   TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_idempotent_key ON affordability_idempotent_keys(idempotent_key);
```

---

## 3. MS SQL Server Schema (Legacy - PLUTUS_HUBDB)

### `PAYLATER_TXN_TBL`
```sql
CREATE TABLE dbo.PAYLATER_TXN_TBL (
    ID                      BIGINT IDENTITY(1,1) PRIMARY KEY,
    STATUS                  VARCHAR(30),
    ISSUER_ID               INT,
    TRANSACTION_AMOUNT      BIGINT,
    TENURE_ID               INT,
    CUSTOMER_PHONE_NUMBER   VARCHAR(50),
    CUSTOMER_NAME           VARCHAR(50),
    CUSTOMER_EMAIL          VARCHAR(100),
    CLIENT_ID               BIGINT NOT NULL,
    SETTLEMENT_DATE_TIME    DATETIME,
    INTEGRATION_TYPE        VARCHAR(30) NOT NULL,     -- PAY_BY_LINK, LENDING, PL_DEFAULT, EMI_ON_UPI, PAY_BY_UPI
    TXN_TYPE                VARCHAR(30) NOT NULL,
    SUB_SYSTEM              VARCHAR(30),              -- PLUTUS_HUB, AUXI
    CLIENT_TYPE             VARCHAR(30) NOT NULL,
    ISSUER_TYPE             VARCHAR(100),
    ENCRYPTED_PAN_NUMBER    VARBINARY(300),
    INVOICE_NUMBER          VARCHAR(20),
    IS_DELETED              BIT DEFAULT 0,
    SELF_EXPIRING_DATE_TIME DATETIME,
    PARENT_TXN_ID           BIGINT,
    TENANT                  VARCHAR(30) NOT NULL,
    CANCELLATION_DATE_TIME  DATETIME,
    CANCELLATION_SOURCE     VARCHAR(20),
    CANCELLATION_REASON     VARCHAR(50),
    CANCELLATION_REFERENCE_ID VARCHAR(50),
    ROW_INSERTION_DATE_TIME DATETIME DEFAULT GETDATE(),
    ROW_UPDATION_DATE_TIME  DATETIME DEFAULT GETDATE(),
    ROW_ACTION_COUNT        INT DEFAULT 0
);
```

### `PAYLATER_TXN_EXT_TBL`
```sql
CREATE TABLE dbo.PAYLATER_TXN_EXT_TBL (
    ID                          BIGINT IDENTITY(1,1) PRIMARY KEY,
    PAYLATER_TXN_ID             BIGINT NOT NULL,
    EDC_BATCH_ID                INT,
    EDC_ROC                     INT,
    ACQUIRER_TRANSACTION_ID     BIGINT,
    PAYMENT_LINK_ID             BIGINT,
    PG_MERCHANT_ID              BIGINT,
    ACQUIRER_NAME               VARCHAR(30),
    UNIQUE_POS_REFERENCE        VARCHAR(50),
    DATABUS_JSON                VARCHAR(MAX),          -- Full task context serialized
    AUTH_CODE                   VARCHAR(20),
    RRN                         VARCHAR(20),
    LENDING_SCHEME_JSON         VARCHAR(MAX),          -- NBFC scheme details
    LENDING_APPROVAL_CODE       VARCHAR(50),
    LOAN_APPLICATION_NUMBER     VARCHAR(50),
    LENDER_UNIQUE_REFERENCE_ID  VARCHAR(50),
    LENDER_NAME                 VARCHAR(100),
    IS_DELETED                  BIT DEFAULT 0
);
```

### `PAYLATER_TXN_TASK_STATUS_TBL`
```sql
CREATE TABLE dbo.PAYLATER_TXN_TASK_STATUS_TBL (
    ID                                      BIGINT IDENTITY(1,1) PRIMARY KEY,
    PAYLATER_TXN_ID                         BIGINT NOT NULL,
    PRODUCT_CHECK_STATUS                    VARCHAR(100),
    VELOCITY_CHECK_STATUS                   VARCHAR(100),
    DEBIT_CARD_CREDIT_LIMIT_CHECK_STATUS    VARCHAR(100),
    PRODUCT_BLOCK_STATUS                    VARCHAR(100),
    VELOCITY_BLOCK_STATUS                   VARCHAR(100),
    DEBIT_CARD_CREDIT_LIMIT_BLOCK_STATUS    VARCHAR(100),
    GRANT_LOAN_STATUS                       VARCHAR(100),
    PRODUCT_UNBLOCK_STATUS                  VARCHAR(100),
    VELOCITY_UNBLOCK_STATUS                 VARCHAR(100),
    DEBIT_CARD_CREDIT_LIMIT_UNBLOCK_STATUS  VARCHAR(100),
    CANCEL_LOAN_STATUS                      VARCHAR(100),
    REFUND_LOAN_STATUS                      VARCHAR(100),
    IS_DELETED                              BIT DEFAULT 0
);
```

---

## 4. MongoDB Schema (Legacy Catalogue)

### `product_offer` Collection
```json
{
    "_id": ObjectId,
    "productCode": "PROD_001",
    "internalProductCode": "INT_PROD_001",
    "internalProductGroupId": 1234,
    "oemId": 5,
    "issuer": { "issuerId": 101, "issuerName": "HDFC" },
    "tenure": { "tenureCode": "T6", "tenureMonths": 6 },
    "schemeId": "SCH_001",
    "ruleId": "RULE_001",
    "ruleTypeId": "RT_EMI",
    "interestRatePercentage": 14.5,
    "emiMinAmount": 500000,
    "emiMaxAmount": 50000000,
    "schemeMinAmount": 300000,
    "schemeMaxAmount": 100000000,
    "productMinPrice": 100000,
    "productMaxPrice": 99999900,
    "oemDiscount": { "fixedAmount": 0, "percentage": 0 },
    "brandDiscount": { "fixedAmount": 50000, "percentage": 5.0 },
    "merchantDiscount": { "fixedAmount": 0, "percentage": 0 },
    "cashback": { "type": "INSTANT_CASHBACK", "amount": 100000 },
    "splitEmi": { "percentage": 10.0 },
    "advanceEmi": { "months": 1 },
    "processingFee": { "fixedAmount": 29900, "percentage": 0 },
    "dealerBuyDown": 0,
    "manufactureBuyDown": 200000,
    "priority": 1,
    "schemeStartDate": ISODate("2024-01-01"),
    "schemeEndDate": ISODate("2025-12-31"),
    "status": "ACTIVE",
    "tenantName": "PINELABS.IN.OFFLINE"
}
```

### `issuer_offer` Collection
```json
{
    "_id": ObjectId,
    "issuer": { "issuerId": 101, "issuerName": "HDFC", "issuerType": "CC" },
    "tenure": { "tenureCode": "T12", "tenureMonths": 12 },
    "schemeId": "BANK_SCH_001",
    "ruleId": "BANK_RULE_001",
    "ruleTypeId": "RT_BANK_EMI",
    "interestRatePercentage": 13.0,
    "emiMinAmount": 300000,
    "emiMaxAmount": 100000000,
    "schemeMinAmount": 300000,
    "schemeMaxAmount": 100000000,
    "instantDiscount": { "fixedAmount": 0, "percentage": 0 },
    "cashback": { "type": null, "amount": 0 },
    "merchantDiscount": { "fixedAmount": 0, "percentage": 0 },
    "dealerBuyDown": 0,
    "processingFee": { "fixedAmount": 19900, "percentage": 0 },
    "schemeApplicabilityHours": { "startHour": 0, "endHour": 23 },
    "daysBitmap": "1111111",
    "status": "ACTIVE"
}
```

---

## 5. Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        OFFER CONFIGURATION                               │
│                                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────────────┐ │
│  │ Campaign │───>│    Offer     │───>│     Offer Parameters           │ │
│  │          │ 1:N│              │ 1:N│                                │ │
│  └──────────┘    └──────┬───────┘    └────┬──────────┬───────────────┘ │
│                          │                 │          │                  │
│                          │           ┌─────▼─────┐ ┌─▼────────────────┐│
│                          │           │Subvention │ │ Discount         ││
│                          │           │Parameters │ │ Parameters       ││
│                          │           └───────────┘ └──────────────────┘│
│                          │                 │                            │
│                    ┌─────▼────────┐  ┌────▼──────────────────────┐     │
│                    │   Budget     │  │ Offer Parameter Tenure Map│     │
│                    │   Partner    │  └────┬──────────────────────┘     │
│                    └──────────────┘       │                            │
│                                     ┌────▼────┐                       │
│                                     │ Tenure  │                       │
│                                     └─────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    CLIENT-OFFER ASSOCIATION                               │
│                                                                          │
│  ┌────────┐    ┌──────────────────┐    ┌────────────────────────────┐   │
│  │ Client │───>│ Client Group Map │───>│ Client Issuer Offer Assoc  │   │
│  └───┬────┘    └──────────────────┘    └─────────────┬──────────────┘   │
│      │                                                │                  │
│      │    ┌─────────────────────────┐           ┌────▼────┐             │
│      └───>│ Client Product Offer    │           │  Offer  │             │
│           │ Association             │           └─────────┘             │
│           └─────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    ISSUER CONFIGURATION                                   │
│                                                                          │
│  ┌────────┐    ┌──────────────────┐    ┌────────────────────────────┐   │
│  │ Issuer │───>│ Issuer EMI Config│    │ BIN Range Group            │   │
│  └───┬────┘    │ (ROI, fees,      │    └─────────┬──────────────────┘   │
│      │         │  amount bounds)   │              │                      │
│      │         └──────────────────┘    ┌─────────▼──────────────────┐   │
│      │                                 │ BIN Range                   │   │
│      └────────────────────────────────>│ (start_bin, end_bin)        │   │
│                                        └────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────┐    ┌────────────────────────────────┐   │
│  │ BIN Group Issuer Offer     │    │ Velocity Rule Configuration    │   │
│  │ (ROI override per BIN grp) │    │ (rate limiting per card/phone) │   │
│  └────────────────────────────┘    └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    TRANSACTION LIFECYCLE                                   │
│                                                                          │
│  ┌──────────────────────┐                                                │
│  │Affordability         │──── 1:N ──→ [Extension]                        │
│  │Transaction           │──── 1:N ──→ [Product Details]                  │
│  │                      │──── 1:N ──→ [Task Details]                     │
│  │                      │──── 1:N ──→ [EMI Txn Ledger]                   │
│  │                      │──── 1:N ──→ [Fund Settlement]                  │
│  │                      │──── 1:N ──→ [Budget Ledger]                    │
│  │                      │──── 1:1 ──→ [Idempotent Keys]                  │
│  └──────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────┘
```
