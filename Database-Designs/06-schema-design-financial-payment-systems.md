# Schema Design - Financial & Payment Systems (Problems 111-130)

## Staff Architect Level - Banking, Payments, Ledgers

---

## Problem 111: Design a Double-Entry Accounting Ledger

**Difficulty:** Expert | **Frequency:** Very High (Fintech, Any payment system)

**The Golden Rule:** Every financial transaction MUST have equal debits and credits. The system should make it IMPOSSIBLE to create an unbalanced entry.

```sql
-- Chart of Accounts
CREATE TABLE accounts (
    account_id UUID PRIMARY KEY,
    account_code VARCHAR(20) UNIQUE NOT NULL,  -- "1000", "2000"
    name VARCHAR(255) NOT NULL,
    type ENUM('asset', 'liability', 'equity', 'revenue', 'expense') NOT NULL,
    normal_balance ENUM('debit', 'credit') NOT NULL,  -- Which side increases this account
    parent_account_id UUID REFERENCES accounts(account_id),
    is_active BOOLEAN DEFAULT TRUE,
    currency CHAR(3) DEFAULT 'USD'
);

-- Journal Entries (the transaction header)
CREATE TABLE journal_entries (
    entry_id UUID PRIMARY KEY,
    entry_date DATE NOT NULL,
    description VARCHAR(500) NOT NULL,
    reference_type VARCHAR(50),  -- 'invoice', 'payment', 'transfer'
    reference_id UUID,
    status ENUM('draft', 'posted', 'reversed') DEFAULT 'draft',
    posted_at TIMESTAMP,
    posted_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_date (entry_date),
    INDEX idx_reference (reference_type, reference_id)
);

-- Journal Lines (individual debits and credits)
CREATE TABLE journal_lines (
    line_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    entry_id UUID NOT NULL REFERENCES journal_entries(entry_id),
    account_id UUID NOT NULL REFERENCES accounts(account_id),
    debit_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    credit_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    description VARCHAR(255),
    
    -- Ensure each line is either debit OR credit, not both
    CHECK (
        (debit_amount > 0 AND credit_amount = 0) OR 
        (credit_amount > 0 AND debit_amount = 0)
    ),
    
    INDEX idx_entry (entry_id),
    INDEX idx_account_date (account_id)
);

-- CRITICAL: Trigger/constraint to ensure balanced entries
-- PostgreSQL approach using a constraint trigger:
CREATE OR REPLACE FUNCTION check_balanced_entry() RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT SUM(debit_amount) - SUM(credit_amount) 
        FROM journal_lines WHERE entry_id = NEW.entry_id) != 0 
    THEN
        RAISE EXCEPTION 'Journal entry is not balanced';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Alternatively, enforce at posting time:
CREATE OR REPLACE FUNCTION post_journal_entry(p_entry_id UUID) RETURNS VOID AS $$
DECLARE
    v_balance DECIMAL(15,2);
BEGIN
    SELECT SUM(debit_amount) - SUM(credit_amount) INTO v_balance
    FROM journal_lines WHERE entry_id = p_entry_id;
    
    IF v_balance != 0 THEN
        RAISE EXCEPTION 'Cannot post unbalanced entry. Difference: %', v_balance;
    END IF;
    
    UPDATE journal_entries SET status = 'posted', posted_at = NOW()
    WHERE entry_id = p_entry_id;
END;
$$ LANGUAGE plpgsql;
```

**Account Balance Query:**
```sql
-- Current balance for any account
SELECT a.account_code, a.name, a.type,
       SUM(jl.debit_amount) AS total_debits,
       SUM(jl.credit_amount) AS total_credits,
       CASE a.normal_balance
           WHEN 'debit' THEN SUM(jl.debit_amount) - SUM(jl.credit_amount)
           WHEN 'credit' THEN SUM(jl.credit_amount) - SUM(jl.debit_amount)
       END AS balance
FROM accounts a
LEFT JOIN journal_lines jl ON a.account_id = jl.account_id
LEFT JOIN journal_entries je ON jl.entry_id = je.entry_id AND je.status = 'posted'
GROUP BY a.account_id, a.account_code, a.name, a.type, a.normal_balance;
```

**Trial Balance (must sum to zero):**
```sql
SELECT 
    SUM(jl.debit_amount) AS total_debits,
    SUM(jl.credit_amount) AS total_credits,
    SUM(jl.debit_amount) - SUM(jl.credit_amount) AS difference  -- MUST be 0
FROM journal_lines jl
JOIN journal_entries je ON jl.entry_id = je.entry_id
WHERE je.status = 'posted';
```

---

## Problem 112: Design a Digital Wallet System

**Difficulty:** Hard | **Frequency:** Very High

```sql
CREATE TABLE wallets (
    wallet_id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    balance DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    status ENUM('active', 'frozen', 'closed') DEFAULT 'active',
    daily_limit DECIMAL(12,2) DEFAULT 10000,
    created_at TIMESTAMP DEFAULT NOW(),
    version INT DEFAULT 0,  -- Optimistic locking
    CHECK (balance >= 0)  -- No negative balance (no overdraft)
);

CREATE TABLE wallet_transactions (
    transaction_id UUID PRIMARY KEY,
    wallet_id UUID NOT NULL REFERENCES wallets(wallet_id),
    type ENUM('credit', 'debit', 'hold', 'release', 'transfer_in', 'transfer_out') NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    balance_before DECIMAL(12,2) NOT NULL,
    balance_after DECIMAL(12,2) NOT NULL,
    reference_type VARCHAR(50),  -- 'payment', 'refund', 'deposit', 'withdrawal'
    reference_id UUID,
    description VARCHAR(500),
    status ENUM('pending', 'completed', 'failed', 'reversed') DEFAULT 'completed',
    idempotency_key VARCHAR(100) UNIQUE,  -- Prevent duplicate processing
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_wallet_time (wallet_id, created_at DESC),
    INDEX idx_reference (reference_type, reference_id),
    INDEX idx_idempotency (idempotency_key)
);
```

**Transfer Between Wallets (Atomic):**
```sql
-- Transfer $100 from wallet A to wallet B
BEGIN TRANSACTION;

-- Always lock in consistent order (lower ID first) to prevent deadlocks
-- Debit sender
UPDATE wallets 
SET balance = balance - 100, version = version + 1
WHERE wallet_id = @sender_wallet_id 
  AND balance >= 100 
  AND status = 'active'
  AND version = @expected_version;

IF @@ROW_COUNT = 0 THEN
    ROLLBACK;  -- Insufficient balance or stale version
END IF;

-- Credit receiver
UPDATE wallets 
SET balance = balance + 100, version = version + 1
WHERE wallet_id = @receiver_wallet_id 
  AND status = 'active';

-- Record both transactions
INSERT INTO wallet_transactions (wallet_id, type, amount, balance_before, balance_after, reference_type, reference_id)
VALUES 
    (@sender_wallet_id, 'transfer_out', 100, @sender_balance_before, @sender_balance_before - 100, 'transfer', @transfer_id),
    (@receiver_wallet_id, 'transfer_in', 100, @receiver_balance_before, @receiver_balance_before + 100, 'transfer', @transfer_id);

COMMIT;
```

**Idempotency Pattern:**
```sql
-- Before processing any transaction, check idempotency key
INSERT INTO wallet_transactions (transaction_id, wallet_id, type, amount, ..., idempotency_key)
VALUES (@txn_id, @wallet_id, 'credit', @amount, ..., @idempotency_key)
ON CONFLICT (idempotency_key) DO NOTHING;

-- If affected_rows = 0, this was a duplicate → return original result
```

---

## Problem 113: Design a Payment Processing System (Stripe-like)

**Difficulty:** Expert | **Frequency:** Very High

```sql
CREATE TABLE payment_methods (
    payment_method_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    type ENUM('card', 'bank_account', 'wallet', 'upi') NOT NULL,
    -- Card details (tokenized - NEVER store raw card numbers)
    card_last_four VARCHAR(4),
    card_brand VARCHAR(20),  -- 'visa', 'mastercard'
    card_exp_month INT,
    card_exp_year INT,
    card_fingerprint VARCHAR(64),  -- Hash for detecting duplicates
    -- Bank details
    bank_name VARCHAR(255),
    account_last_four VARCHAR(4),
    -- Tokenization
    gateway_token VARCHAR(255) NOT NULL,  -- Token from payment gateway
    gateway VARCHAR(50) NOT NULL,  -- 'stripe', 'adyen', 'braintree'
    is_default BOOLEAN DEFAULT FALSE,
    status ENUM('active', 'expired', 'failed', 'removed') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user (user_id, is_default DESC)
);

CREATE TABLE payments (
    payment_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    payment_method_id UUID REFERENCES payment_methods(payment_method_id),
    amount DECIMAL(12,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    
    -- Status machine
    status ENUM('created', 'processing', 'requires_action', 'succeeded', 'failed', 'cancelled', 'refunded', 'partially_refunded') DEFAULT 'created',
    
    -- Gateway response
    gateway VARCHAR(50) NOT NULL,
    gateway_payment_id VARCHAR(255),  -- Stripe's pi_xxxxx
    gateway_status VARCHAR(50),
    failure_code VARCHAR(50),
    failure_message TEXT,
    
    -- 3D Secure / SCA
    requires_action BOOLEAN DEFAULT FALSE,
    action_url VARCHAR(500),
    
    -- Metadata
    description VARCHAR(500),
    metadata JSONB,
    idempotency_key VARCHAR(100) UNIQUE,
    
    -- Refund tracking
    amount_refunded DECIMAL(12,2) DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user (user_id, created_at DESC),
    INDEX idx_gateway (gateway, gateway_payment_id),
    INDEX idx_status (status, created_at)
);

CREATE TABLE payment_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_id UUID NOT NULL REFERENCES payments(payment_id),
    event_type VARCHAR(50) NOT NULL,  -- 'created', 'processing', 'succeeded', 'failed'
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    gateway_event_id VARCHAR(255),
    raw_response JSONB,  -- Full gateway webhook payload
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_payment (payment_id, created_at)
);

CREATE TABLE refunds (
    refund_id UUID PRIMARY KEY,
    payment_id UUID NOT NULL REFERENCES payments(payment_id),
    amount DECIMAL(12,2) NOT NULL,
    reason ENUM('requested_by_customer', 'duplicate', 'fraudulent', 'order_cancelled') NOT NULL,
    status ENUM('pending', 'processing', 'succeeded', 'failed') DEFAULT 'pending',
    gateway_refund_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_payment (payment_id)
);
```

---

## Problem 114: Design a Fraud Detection Data Model

**Difficulty:** Expert | **Frequency:** High

```sql
-- Transaction risk signals
CREATE TABLE transaction_risk_scores (
    transaction_id UUID PRIMARY KEY,
    payment_id UUID NOT NULL,
    risk_score DECIMAL(5,4) NOT NULL,  -- 0.0000 to 1.0000
    risk_level ENUM('low', 'medium', 'high', 'critical') NOT NULL,
    decision ENUM('approve', 'review', 'decline', 'challenge') NOT NULL,
    
    -- Individual risk signals
    signals JSONB NOT NULL,
    /*
    {
        "velocity_score": 0.8,  -- Too many transactions in short time
        "amount_anomaly": 0.3,  -- Unusual amount for this user
        "geo_anomaly": 0.9,     -- Transaction from unusual location
        "device_score": 0.1,    -- Known device
        "behavioral_score": 0.4 -- Pattern deviation
    }
    */
    
    -- Context
    ip_address INET,
    device_fingerprint VARCHAR(64),
    geo_country CHAR(2),
    geo_city VARCHAR(100),
    
    evaluated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_risk (risk_level, evaluated_at DESC),
    INDEX idx_payment (payment_id)
);

-- Fraud rules engine
CREATE TABLE fraud_rules (
    rule_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_type ENUM('velocity', 'amount', 'geo', 'device', 'pattern', 'blocklist') NOT NULL,
    conditions JSONB NOT NULL,
    /*
    Example conditions:
    {
        "field": "transaction_count_1h",
        "operator": ">",
        "value": 5,
        "action": "decline"
    }
    */
    action ENUM('flag', 'review', 'decline', 'challenge') NOT NULL,
    score_impact DECIMAL(3,2) NOT NULL DEFAULT 0.1,
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 0
);

-- Velocity tracking (sliding window counters)
CREATE TABLE user_velocity (
    user_id UUID NOT NULL,
    window_type VARCHAR(20) NOT NULL,  -- '1min', '1hour', '24hour'
    window_key VARCHAR(50) NOT NULL,   -- Timestamp bucket
    transaction_count INT DEFAULT 0,
    total_amount DECIMAL(12,2) DEFAULT 0,
    distinct_merchants INT DEFAULT 0,
    distinct_countries INT DEFAULT 0,
    PRIMARY KEY (user_id, window_type, window_key)
);
```

---

## Problem 115: Design an Invoice & Billing System

**Difficulty:** Hard | **Frequency:** Very High

```sql
CREATE TABLE invoices (
    invoice_id UUID PRIMARY KEY,
    invoice_number VARCHAR(20) UNIQUE NOT NULL,  -- "INV-2024-0001"
    customer_id UUID NOT NULL,
    
    -- Status
    status ENUM('draft', 'sent', 'viewed', 'partial', 'paid', 'overdue', 'void', 'written_off') DEFAULT 'draft',
    
    -- Dates
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    paid_date DATE,
    
    -- Amounts
    subtotal DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    amount_paid DECIMAL(12,2) DEFAULT 0,
    amount_due DECIMAL(12,2) GENERATED ALWAYS AS (total_amount - amount_paid) STORED,
    
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    
    -- Payment terms
    payment_terms VARCHAR(50),  -- "Net 30", "Due on receipt"
    late_fee_percentage DECIMAL(5,2) DEFAULT 0,
    
    notes TEXT,
    footer TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_customer (customer_id, status),
    INDEX idx_due_date (status, due_date),
    INDEX idx_number (invoice_number)
);

CREATE TABLE invoice_line_items (
    line_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    invoice_id UUID NOT NULL REFERENCES invoices(invoice_id),
    description VARCHAR(500) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    line_total DECIMAL(10,2) NOT NULL,
    sort_order INT DEFAULT 0,
    INDEX idx_invoice (invoice_id)
);

-- Payment applications (which payments applied to which invoices)
CREATE TABLE payment_applications (
    application_id UUID PRIMARY KEY,
    payment_id UUID NOT NULL,
    invoice_id UUID NOT NULL REFERENCES invoices(invoice_id),
    amount_applied DECIMAL(12,2) NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_invoice (invoice_id),
    INDEX idx_payment (payment_id)
);
```

**Aging Report (Accounts Receivable):**
```sql
SELECT 
    c.name AS customer,
    SUM(CASE WHEN i.due_date >= CURRENT_DATE THEN i.amount_due ELSE 0 END) AS current,
    SUM(CASE WHEN i.due_date BETWEEN CURRENT_DATE - 30 AND CURRENT_DATE - 1 THEN i.amount_due ELSE 0 END) AS "1_30_days",
    SUM(CASE WHEN i.due_date BETWEEN CURRENT_DATE - 60 AND CURRENT_DATE - 31 THEN i.amount_due ELSE 0 END) AS "31_60_days",
    SUM(CASE WHEN i.due_date BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE - 61 THEN i.amount_due ELSE 0 END) AS "61_90_days",
    SUM(CASE WHEN i.due_date < CURRENT_DATE - 90 THEN i.amount_due ELSE 0 END) AS "over_90_days",
    SUM(i.amount_due) AS total_outstanding
FROM invoices i
JOIN customers c ON i.customer_id = c.customer_id
WHERE i.status IN ('sent', 'viewed', 'partial', 'overdue')
  AND i.amount_due > 0
GROUP BY c.customer_id, c.name
ORDER BY total_outstanding DESC;
```

---

## Problem 116: Design a Stock Trading System (Order Book)

**Difficulty:** Expert | **Frequency:** High (Fintech interviews)

```sql
CREATE TABLE instruments (
    symbol VARCHAR(10) PRIMARY KEY,  -- "AAPL", "GOOGL"
    name VARCHAR(255) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    lot_size INT DEFAULT 1,
    tick_size DECIMAL(10,6) NOT NULL,  -- Minimum price increment
    status ENUM('active', 'halted', 'delisted') DEFAULT 'active'
);

-- Order Book
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    symbol VARCHAR(10) NOT NULL REFERENCES instruments(symbol),
    side ENUM('buy', 'sell') NOT NULL,
    order_type ENUM('market', 'limit', 'stop', 'stop_limit') NOT NULL,
    time_in_force ENUM('day', 'gtc', 'ioc', 'fok') NOT NULL DEFAULT 'day',
    
    -- Pricing
    quantity INT NOT NULL,
    filled_quantity INT NOT NULL DEFAULT 0,
    remaining_quantity INT GENERATED ALWAYS AS (quantity - filled_quantity) STORED,
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    average_fill_price DECIMAL(12,4),
    
    -- Status
    status ENUM('new', 'partially_filled', 'filled', 'cancelled', 'rejected', 'expired') DEFAULT 'new',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    INDEX idx_book (symbol, side, limit_price, created_at),  -- Order book lookup
    INDEX idx_user (user_id, created_at DESC),
    INDEX idx_status (status, symbol)
);

-- Trade executions (fills)
CREATE TABLE trades (
    trade_id UUID PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    buy_order_id UUID NOT NULL REFERENCES orders(order_id),
    sell_order_id UUID NOT NULL REFERENCES orders(order_id),
    buyer_id UUID NOT NULL,
    seller_id UUID NOT NULL,
    price DECIMAL(12,4) NOT NULL,
    quantity INT NOT NULL,
    executed_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_symbol_time (symbol, executed_at DESC),
    INDEX idx_buyer (buyer_id, executed_at DESC),
    INDEX idx_seller (seller_id, executed_at DESC)
);

-- Portfolio positions
CREATE TABLE positions (
    user_id UUID NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,  -- Positive = long, Negative = short
    average_cost DECIMAL(12,4) NOT NULL DEFAULT 0,
    realized_pnl DECIMAL(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, symbol)
);
```

**Order Matching Engine Query (Price-Time Priority):**
```sql
-- Find best matching sell orders for a buy order
SELECT order_id, user_id, limit_price, remaining_quantity, created_at
FROM orders
WHERE symbol = @symbol
  AND side = 'sell'
  AND status IN ('new', 'partially_filled')
  AND (limit_price <= @buy_limit_price OR order_type = 'market')
ORDER BY limit_price ASC, created_at ASC  -- Best price first, then earliest
LIMIT 10;
```

**Architect Note:** In production, order books are NEVER queried from SQL. They use:
- In-memory matching engines (LMAX Disruptor pattern)
- Lock-free data structures
- SQL is only for persistence/recovery and post-trade processing

---

## Problem 117: Design a Cryptocurrency Exchange

**Difficulty:** Expert | **Frequency:** High

```sql
-- Similar to stock trading but with:
-- 1. 24/7 trading (no market hours)
-- 2. Higher decimal precision
-- 3. Blockchain deposit/withdrawal tracking

CREATE TABLE crypto_wallets (
    wallet_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    currency VARCHAR(10) NOT NULL,  -- "BTC", "ETH", "USDT"
    available_balance DECIMAL(20,8) NOT NULL DEFAULT 0,
    locked_balance DECIMAL(20,8) NOT NULL DEFAULT 0,  -- In open orders
    total_balance DECIMAL(20,8) GENERATED ALWAYS AS (available_balance + locked_balance) STORED,
    deposit_address VARCHAR(100),
    PRIMARY KEY (user_id, currency),
    CHECK (available_balance >= 0),
    CHECK (locked_balance >= 0)
);

CREATE TABLE blockchain_transactions (
    tx_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    currency VARCHAR(10) NOT NULL,
    tx_type ENUM('deposit', 'withdrawal') NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    fee DECIMAL(20,8) DEFAULT 0,
    blockchain_tx_hash VARCHAR(100) UNIQUE,
    from_address VARCHAR(100),
    to_address VARCHAR(100),
    confirmations INT DEFAULT 0,
    required_confirmations INT NOT NULL,
    status ENUM('pending', 'confirming', 'completed', 'failed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    INDEX idx_user (user_id, currency),
    INDEX idx_hash (blockchain_tx_hash),
    INDEX idx_status (status)
);
```

---

## Problem 118: Design a Loan Management System

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE loans (
    loan_id UUID PRIMARY KEY,
    borrower_id UUID NOT NULL,
    loan_type ENUM('personal', 'mortgage', 'auto', 'business', 'student') NOT NULL,
    principal_amount DECIMAL(14,2) NOT NULL,
    interest_rate DECIMAL(6,4) NOT NULL,  -- Annual rate: 0.0750 = 7.5%
    term_months INT NOT NULL,
    
    -- Calculated at origination
    monthly_payment DECIMAL(10,2) NOT NULL,
    total_interest DECIMAL(14,2) NOT NULL,
    total_amount DECIMAL(14,2) NOT NULL,
    
    -- Current state
    outstanding_principal DECIMAL(14,2) NOT NULL,
    status ENUM('application', 'approved', 'active', 'paid_off', 'defaulted', 'written_off') DEFAULT 'application',
    
    disbursement_date DATE,
    first_payment_date DATE,
    maturity_date DATE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_borrower (borrower_id),
    INDEX idx_status (status)
);

-- Amortization schedule
CREATE TABLE loan_schedule (
    schedule_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    loan_id UUID NOT NULL REFERENCES loans(loan_id),
    payment_number INT NOT NULL,
    due_date DATE NOT NULL,
    principal_amount DECIMAL(10,2) NOT NULL,
    interest_amount DECIMAL(10,2) NOT NULL,
    total_payment DECIMAL(10,2) NOT NULL,
    remaining_balance DECIMAL(14,2) NOT NULL,
    status ENUM('scheduled', 'paid', 'partial', 'overdue', 'waived') DEFAULT 'scheduled',
    paid_date DATE,
    paid_amount DECIMAL(10,2),
    late_fee DECIMAL(8,2) DEFAULT 0,
    UNIQUE KEY uk_loan_payment (loan_id, payment_number),
    INDEX idx_due (status, due_date)
);

-- Generate amortization schedule
WITH RECURSIVE schedule AS (
    SELECT 
        1 AS payment_number,
        @first_payment_date AS due_date,
        @monthly_payment - (@principal * @rate / 12) AS principal_portion,
        @principal * @rate / 12 AS interest_portion,
        @monthly_payment AS total_payment,
        @principal - (@monthly_payment - @principal * @rate / 12) AS remaining_balance
    UNION ALL
    SELECT
        payment_number + 1,
        due_date + INTERVAL '1 month',
        @monthly_payment - (remaining_balance * @rate / 12),
        remaining_balance * @rate / 12,
        @monthly_payment,
        remaining_balance - (@monthly_payment - remaining_balance * @rate / 12)
    FROM schedule
    WHERE payment_number < @term_months
)
SELECT * FROM schedule;
```

---

## Problem 119: Design a Split Payment / Bill Splitting System

**Difficulty:** Medium | **Frequency:** High (Splitwise, Venmo)

```sql
CREATE TABLE expense_groups (
    group_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE group_members (
    group_id UUID NOT NULL REFERENCES expense_groups(group_id),
    user_id UUID NOT NULL,
    joined_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE expenses (
    expense_id UUID PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES expense_groups(group_id),
    paid_by UUID NOT NULL,  -- Who paid the full amount
    description VARCHAR(500) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    currency CHAR(3) DEFAULT 'USD',
    split_type ENUM('equal', 'exact', 'percentage', 'shares') NOT NULL DEFAULT 'equal',
    expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_group (group_id, expense_date DESC)
);

CREATE TABLE expense_splits (
    expense_id UUID NOT NULL REFERENCES expenses(expense_id),
    user_id UUID NOT NULL,
    owed_amount DECIMAL(10,2) NOT NULL,  -- How much this person owes
    is_settled BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (expense_id, user_id)
);

-- Settlements (actual payments between users)
CREATE TABLE settlements (
    settlement_id UUID PRIMARY KEY,
    group_id UUID NOT NULL,
    from_user_id UUID NOT NULL,
    to_user_id UUID NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'completed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Calculate Net Balances (Who Owes Whom):**
```sql
WITH debts AS (
    -- Amount each person owes to payer for each expense
    SELECT e.paid_by AS creditor, es.user_id AS debtor, SUM(es.owed_amount) AS amount
    FROM expenses e
    JOIN expense_splits es ON e.expense_id = es.expense_id
    WHERE e.group_id = @group_id
      AND es.user_id != e.paid_by  -- Don't count self
      AND es.is_settled = FALSE
    GROUP BY e.paid_by, es.user_id
),
settlements_made AS (
    SELECT from_user_id AS debtor, to_user_id AS creditor, SUM(amount) AS settled
    FROM settlements
    WHERE group_id = @group_id AND status = 'completed'
    GROUP BY from_user_id, to_user_id
),
net_debts AS (
    SELECT d.creditor, d.debtor,
           d.amount - COALESCE(s.settled, 0) AS net_owed
    FROM debts d
    LEFT JOIN settlements_made s ON d.creditor = s.creditor AND d.debtor = s.debtor
    WHERE d.amount - COALESCE(s.settled, 0) > 0
)
-- Simplify debts (minimize transactions)
SELECT creditor, debtor, net_owed
FROM net_debts
ORDER BY net_owed DESC;
```

---

## Problem 120: Design a Multi-Tenant SaaS Billing System

**Difficulty:** Expert | **Frequency:** Very High

```sql
CREATE TABLE billing_plans (
    plan_id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,  -- "Starter", "Pro", "Enterprise"
    billing_period ENUM('monthly', 'yearly') NOT NULL,
    base_price DECIMAL(10,2) NOT NULL,
    currency CHAR(3) DEFAULT 'USD',
    features JSONB,  -- {"max_users": 10, "storage_gb": 100, "api_calls": 10000}
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE plan_usage_tiers (
    tier_id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES billing_plans(plan_id),
    metric VARCHAR(50) NOT NULL,  -- "api_calls", "storage_gb", "compute_hours"
    tier_start INT NOT NULL,  -- From this usage level
    tier_end INT,  -- NULL = unlimited
    unit_price DECIMAL(10,6) NOT NULL,  -- Price per unit in this tier
    PRIMARY KEY (plan_id, metric, tier_start)
);

CREATE TABLE subscriptions (
    subscription_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    plan_id UUID NOT NULL REFERENCES billing_plans(plan_id),
    status ENUM('trialing', 'active', 'past_due', 'cancelled', 'paused') DEFAULT 'active',
    quantity INT DEFAULT 1,  -- Number of seats/units
    current_period_start TIMESTAMP NOT NULL,
    current_period_end TIMESTAMP NOT NULL,
    trial_ends_at TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    INDEX idx_tenant (tenant_id),
    INDEX idx_renewal (status, current_period_end)
);

-- Usage-based billing metering
CREATE TABLE usage_records (
    record_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    subscription_id UUID NOT NULL,
    metric VARCHAR(50) NOT NULL,
    quantity DECIMAL(14,4) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    idempotency_key VARCHAR(100) UNIQUE,
    INDEX idx_subscription_metric (subscription_id, metric, timestamp)
);

-- Monthly usage aggregation for billing
CREATE TABLE usage_summaries (
    subscription_id UUID NOT NULL,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    metric VARCHAR(50) NOT NULL,
    total_usage DECIMAL(14,4) NOT NULL,
    billable_amount DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (subscription_id, billing_period_start, metric)
);
```

**Calculate Monthly Bill with Tiered Pricing:**
```sql
WITH monthly_usage AS (
    SELECT subscription_id, metric, SUM(quantity) AS total_usage
    FROM usage_records
    WHERE subscription_id = @sub_id
      AND timestamp >= @period_start AND timestamp < @period_end
    GROUP BY subscription_id, metric
),
tiered_cost AS (
    SELECT mu.metric, mu.total_usage,
           SUM(
               put.unit_price * LEAST(
                   GREATEST(mu.total_usage - put.tier_start, 0),
                   COALESCE(put.tier_end - put.tier_start, mu.total_usage - put.tier_start)
               )
           ) AS cost
    FROM monthly_usage mu
    JOIN plan_usage_tiers put ON put.plan_id = @plan_id AND put.metric = mu.metric
    GROUP BY mu.metric, mu.total_usage
)
SELECT bp.base_price + COALESCE(SUM(tc.cost), 0) AS total_bill,
       bp.base_price,
       SUM(tc.cost) AS usage_charges
FROM billing_plans bp
LEFT JOIN tiered_cost tc ON TRUE
WHERE bp.plan_id = @plan_id
GROUP BY bp.base_price;
```

---

## Problem 121: Design a Revenue Recognition System

**Difficulty:** Expert | **Frequency:** High (Enterprise, ASC 606 compliance)

```sql
CREATE TABLE revenue_contracts (
    contract_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    total_value DECIMAL(14,2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status ENUM('active', 'completed', 'terminated') DEFAULT 'active'
);

CREATE TABLE performance_obligations (
    obligation_id UUID PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES revenue_contracts(contract_id),
    description VARCHAR(500),
    type ENUM('point_in_time', 'over_time') NOT NULL,
    standalone_selling_price DECIMAL(12,2) NOT NULL,
    allocated_transaction_price DECIMAL(12,2) NOT NULL,
    recognition_start DATE,
    recognition_end DATE,
    percent_complete DECIMAL(5,2) DEFAULT 0
);

-- Monthly revenue recognition schedule
CREATE TABLE revenue_schedule (
    schedule_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    obligation_id UUID NOT NULL,
    recognition_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    is_recognized BOOLEAN DEFAULT FALSE,
    recognized_at TIMESTAMP,
    journal_entry_id UUID,
    INDEX idx_date (recognition_date, is_recognized),
    INDEX idx_obligation (obligation_id)
);
```

---

## Problems 122-130: Additional Financial System Designs

### Problem 122: Design an Escrow System
- Hold funds until conditions met
- Multi-party dispute resolution
- Automatic release on milestones

### Problem 123: Design a Loyalty Points System
- Earn points on purchases
- Points expiration
- Tier-based multipliers
- Redemption rules

### Problem 124: Design a Tax Withholding System
- Support 1099/W-2 reporting
- Country-specific tax rules
- Threshold-based withholding

### Problem 125: Design an Insurance Claims System
- Claim lifecycle management
- Document attachment
- Adjuster assignment
- Coverage verification

### Problem 126: Design a Payroll System
- Salary, hourly, commission
- Tax calculation per jurisdiction
- Benefits deductions
- Pay period management

### Problem 127: Design a Budget/Expense Tracking System
- Category-based budgets
- Recurring vs one-time
- Multi-currency consolidation
- Alerts on threshold breach

### Problem 128: Design a Commission Calculation System
- Tiered commission rates
- Override commissions (manager gets % of team)
- Clawback on cancellations
- Split commissions

### Problem 129: Design an Accounts Payable System
- Purchase orders
- 3-way matching (PO ↔ Receipt ↔ Invoice)
- Approval workflows
- Payment batch processing

### Problem 130: Design a Financial Reconciliation System
- Match bank transactions to internal records
- Auto-match rules (amount + date + reference)
- Exception handling for unmatched items
- Balance verification

---

## Key Financial Database Principles

| Principle | Why | Implementation |
|-----------|-----|----------------|
| Double-entry | Mathematically provable correctness | Every transaction has equal debits & credits |
| Immutability | Audit trail, regulatory compliance | Never UPDATE/DELETE; only INSERT + reversal entries |
| Idempotency | Handle retries safely | Unique idempotency_key per transaction |
| Eventual balance | Performance at scale | Async balance computation, periodic reconciliation |
| Decimal precision | Avoid floating-point errors | DECIMAL(12,2) for fiat, DECIMAL(20,8) for crypto |
| Temporal tracking | Point-in-time queries for audit | Valid-from/valid-to on all reference data |
| Ordered locking | Prevent deadlocks | Always lock accounts in consistent order (by ID) |
| Saga pattern | Distributed transactions | Compensating transactions instead of 2PC |
