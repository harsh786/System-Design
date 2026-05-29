# UPI Real-Time Bank Transfer System

## 1. Functional Requirements

### Core Features
- **VPA Management**: Create/link/delink Virtual Payment Addresses (user@bank)
- **Collect Requests**: Payee initiates payment request to payer
- **Pay Requests**: Payer initiates push payment to payee
- **Multi-Bank Integration**: Connect to all banks via NPCI switch
- **Transaction Routing**: Route through NPCI switch between PSPs and banks
- **Mandate/Autopay**: Recurring payment authorization (UPI Autopay)
- **QR Code Payments**: Static and dynamic QR generation and scanning
- **Dispute Resolution**: Complaint filing, chargeback, resolution within TAT
- **Transaction Limits**: Per-transaction, daily, monthly limits
- **PSP Integration**: Payment Service Provider onboarding and management

### Transaction Types
1. **P2P (Person to Person)**: Send money to another UPI ID
2. **P2M (Person to Merchant)**: Pay merchant via QR/VPA
3. **Collect**: Merchant/person requests money
4. **Mandate**: Recurring auto-debit (SIP, bills, subscriptions)

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Transaction latency (end-to-end) | < 3 seconds |
| Switch throughput | 1 Billion transactions/day (peak) |
| Success rate | > 99.5% |
| Availability | 99.99% (24×7) |
| Timeout handling | 30s per leg, auto-reversal |
| Concurrent transactions | 10,000 TPS (Transaction Per Second) |
| Data consistency | Zero fund loss (exactly-once) |
| Dispute resolution TAT | < 5 business days |

## 3. Capacity Estimation

### Assumptions
- 300M active UPI users
- Peak: 1B transactions/day = ~11,500 TPS average, ~40,000 TPS peak
- Average transaction: ₹1,500 (~$18)
- Daily value: 1B × ₹1,500 = ₹1.5 Trillion/day
- 50+ banks connected, 20+ PSPs

### Storage
- Transactions: 1B/day × 1KB = 1TB/day = 365TB/year
- VPA mappings: 300M × 200B = 60GB
- Mandates: 100M × 500B = 50GB
- Disputes: 1M/day × 2KB = 2GB/day

### Network
- Each transaction = 4 network hops (payer PSP → switch → payee PSP → payee bank)
- Messages per transaction: ~8 (request + response at each hop)
- Network throughput: 40K TPS × 8 messages × 2KB = 640MB/sec

## 4. Data Modeling

### Full Database Schemas

```sql
-- VPA (Virtual Payment Address) registry
CREATE TABLE vpa_registry (
    vpa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vpa_address VARCHAR(50) NOT NULL UNIQUE, -- user@psp
    customer_id UUID NOT NULL,
    psp_id VARCHAR(20) NOT NULL, -- PSP handle (e.g., 'paytm', 'gpay', 'phonepe')
    linked_account_id UUID NOT NULL REFERENCES bank_accounts(account_id),
    is_primary BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, BLOCKED, DEACTIVATED
    device_fingerprint VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_vpa_customer ON vpa_registry(customer_id);
CREATE INDEX idx_vpa_psp ON vpa_registry(psp_id);

-- Bank accounts linked to UPI
CREATE TABLE bank_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    bank_code VARCHAR(10) NOT NULL, -- IFSC first 4 chars
    account_number_enc BYTEA NOT NULL,
    account_holder_name VARCHAR(200),
    account_type VARCHAR(20), -- SAVINGS, CURRENT
    ifsc_code VARCHAR(11) NOT NULL,
    bank_name VARCHAR(100),
    is_verified BOOLEAN DEFAULT FALSE,
    balance_check_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bank_accounts_customer ON bank_accounts(customer_id);

-- Transactions (core payment records)
CREATE TABLE transactions (
    txn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rrn VARCHAR(12) NOT NULL UNIQUE, -- Retrieval Reference Number (NPCI assigned)
    umn VARCHAR(36), -- Unique Mandate Number (for mandates)
    txn_type VARCHAR(10) NOT NULL, -- PAY, COLLECT, MANDATE_EXEC
    flow_type VARCHAR(10) NOT NULL, -- DEBIT, CREDIT, REVERSAL
    
    -- Payer details
    payer_vpa VARCHAR(50) NOT NULL,
    payer_psp_id VARCHAR(20) NOT NULL,
    payer_bank_code VARCHAR(10) NOT NULL,
    payer_account_ref VARCHAR(50), -- Encrypted reference
    payer_name VARCHAR(200),
    
    -- Payee details
    payee_vpa VARCHAR(50) NOT NULL,
    payee_psp_id VARCHAR(20) NOT NULL,
    payee_bank_code VARCHAR(10) NOT NULL,
    payee_account_ref VARCHAR(50),
    payee_name VARCHAR(200),
    payee_mcc VARCHAR(4), -- Merchant Category Code (P2M)
    
    -- Amount
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'INITIATED',
    -- INITIATED, PAYER_APPROVED, DEBIT_SUCCESS, CREDIT_SUCCESS, 
    -- COMPLETED, FAILED, TIMEOUT, REVERSED, DEEMED_APPROVED
    sub_status VARCHAR(30),
    failure_reason VARCHAR(100),
    response_code VARCHAR(5), -- NPCI response code
    
    -- Timing
    initiated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    payer_approved_at TIMESTAMP,
    debit_at TIMESTAMP,
    credit_at TIMESTAMP,
    completed_at TIMESTAMP,
    timeout_at TIMESTAMP,
    
    -- Metadata
    remarks TEXT, -- Payment note
    ref_id VARCHAR(50), -- Merchant reference
    ref_url TEXT, -- Collect request URL
    device_info JSONB,
    risk_score DECIMAL(3, 2),
    
    -- Settlement
    settlement_batch_id UUID,
    settled_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_txn_rrn ON transactions(rrn);
CREATE INDEX idx_txn_payer ON transactions(payer_vpa, created_at DESC);
CREATE INDEX idx_txn_payee ON transactions(payee_vpa, created_at DESC);
CREATE INDEX idx_txn_status ON transactions(status, created_at);
CREATE INDEX idx_txn_timeout ON transactions(status, initiated_at) WHERE status IN ('INITIATED', 'PAYER_APPROVED', 'DEBIT_SUCCESS');

-- Transaction state machine (audit trail)
CREATE TABLE transaction_states (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    txn_id UUID NOT NULL,
    from_state VARCHAR(20),
    to_state VARCHAR(20) NOT NULL,
    actor VARCHAR(20), -- PAYER_PSP, NPCI_SWITCH, PAYEE_PSP, PAYEE_BANK, SYSTEM
    response_code VARCHAR(5),
    response_message TEXT,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_txn_states_txn ON transaction_states(txn_id, created_at);

-- Mandates (recurring payments)
CREATE TABLE mandates (
    mandate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    umn VARCHAR(36) NOT NULL UNIQUE, -- Unique Mandate Number
    payer_vpa VARCHAR(50) NOT NULL,
    payee_vpa VARCHAR(50) NOT NULL,
    payer_bank_code VARCHAR(10),
    
    mandate_type VARCHAR(20), -- CREATE, MODIFY, REVOKE
    recurrence_pattern VARCHAR(20), -- DAILY, WEEKLY, FORTNIGHTLY, MONTHLY, YEARLY, AS_PRESENTED
    recurrence_rule JSONB, -- {day_of_month: 5, start_date, end_date}
    
    amount DECIMAL(12, 2) NOT NULL, -- Max amount per debit
    amount_rule VARCHAR(10) DEFAULT 'MAX', -- MAX, EXACT
    
    validity_start DATE NOT NULL,
    validity_end DATE NOT NULL,
    
    status VARCHAR(20) DEFAULT 'PENDING',
    -- PENDING, APPROVED, ACTIVE, PAUSED, REVOKED, EXPIRED
    
    purpose VARCHAR(100), -- Description shown to payer
    
    last_executed_at TIMESTAMP,
    next_execution_date DATE,
    execution_count INT DEFAULT 0,
    
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mandates_payer ON mandates(payer_vpa, status);
CREATE INDEX idx_mandates_next_exec ON mandates(next_execution_date, status) WHERE status = 'ACTIVE';

-- PSP (Payment Service Provider) registry
CREATE TABLE psp_registry (
    psp_id VARCHAR(20) PRIMARY KEY,
    psp_name VARCHAR(100) NOT NULL,
    psp_type VARCHAR(20), -- BANK_PSP, THIRD_PARTY_PSP
    handle VARCHAR(20) NOT NULL UNIQUE, -- @paytm, @ybl, @okhdfcbank
    api_endpoint TEXT NOT NULL,
    certificate_thumbprint VARCHAR(64),
    daily_limit DECIMAL(14, 2),
    per_txn_limit DECIMAL(12, 2),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    onboarded_at TIMESTAMP
);

-- Disputes
CREATE TABLE disputes (
    dispute_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    txn_id UUID NOT NULL REFERENCES transactions(txn_id),
    rrn VARCHAR(12) NOT NULL,
    complainant_vpa VARCHAR(50) NOT NULL,
    complainant_type VARCHAR(10), -- PAYER, PAYEE
    dispute_type VARCHAR(30), -- UNAUTHORIZED, GOODS_NOT_RECEIVED, DUPLICATE, AMOUNT_MISMATCH
    dispute_reason TEXT,
    amount DECIMAL(12, 2) NOT NULL,
    
    status VARCHAR(20) DEFAULT 'FILED',
    -- FILED, ACKNOWLEDGED, UNDER_REVIEW, RESOLVED, REJECTED, ESCALATED
    resolution VARCHAR(20), -- REFUNDED, NO_ACTION, PARTIAL_REFUND
    resolution_amount DECIMAL(12, 2),
    resolution_notes TEXT,
    
    sla_deadline TIMESTAMP, -- 5 business days from filing
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_disputes_txn ON disputes(txn_id);
CREATE INDEX idx_disputes_status ON disputes(status, sla_deadline);

-- Settlement batches (net settlement between banks)
CREATE TABLE settlement_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    settlement_cycle VARCHAR(10), -- HOURLY, DAILY
    cycle_date DATE NOT NULL,
    cycle_number INT, -- Intra-day cycle number
    total_transactions INT,
    total_amount DECIMAL(16, 2),
    status VARCHAR(20) DEFAULT 'COMPUTING',
    -- COMPUTING, READY, SUBMITTED_TO_RBI, SETTLED
    net_positions JSONB, -- {bank_code: net_amount} per bank
    submitted_at TIMESTAMP,
    settled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 5. High-Level Design (HLD)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          UPI REAL-TIME PAYMENT SYSTEM                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│   PAYER SIDE                           PAYEE SIDE                                 │
│  ┌──────────┐                         ┌──────────┐                               │
│  │  Payer   │                         │  Payee   │                               │
│  │  App     │                         │  App     │                               │
│  └────┬─────┘                         └────┬─────┘                               │
│       │                                    │                                      │
│  ┌────▼─────┐                         ┌────▼─────┐                               │
│  │  Payer   │                         │  Payee   │                               │
│  │   PSP    │                         │   PSP    │                               │
│  │(PhonePe/ │                         │(Merchant/│                               │
│  │ GPay)    │                         │ Bank App)│                               │
│  └────┬─────┘                         └────┬─────┘                               │
│       │                                    │                                      │
│       │         ┌──────────────────┐       │                                      │
│       └────────▶│                  │◀──────┘                                      │
│                 │   NPCI SWITCH    │                                              │
│                 │                  │                                              │
│                 │  ┌────────────┐  │                                              │
│                 │  │Transaction │  │                                              │
│                 │  │  Router    │  │                                              │
│                 │  └─────┬──────┘  │                                              │
│                 │        │         │                                              │
│                 │  ┌─────▼──────┐  │                                              │
│                 │  │ Participant│  │                                              │
│                 │  │  Manager   │  │                                              │
│                 │  └─────┬──────┘  │                                              │
│                 │        │         │                                              │
│                 │  ┌─────▼──────┐  │                                              │
│                 │  │ VPA        │  │                                              │
│                 │  │ Directory  │  │                                              │
│                 │  └─────┬──────┘  │                                              │
│                 │        │         │                                              │
│                 │  ┌─────▼──────┐  │                                              │
│                 │  │ Settlement │  │                                              │
│                 │  │  Engine    │  │                                              │
│                 │  └────────────┘  │                                              │
│                 └────────┬─────────┘                                              │
│                          │                                                         │
│         ┌────────────────┼────────────────┐                                       │
│         │                │                │                                       │
│    ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐                                 │
│    │  Payer   │    │  Payee   │    │  Other   │  [ISSUER BANKS]                  │
│    │  Bank    │    │  Bank    │    │  Banks   │                                  │
│    │(CBS+UPI) │    │(CBS+UPI) │    │          │                                  │
│    └──────────┘    └──────────┘    └──────────┘                                  │
│                                                                                    │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐                 │
│  │ PostgreSQL  │  │  Redis   │  │  Kafka   │  │   HSM (Keys)  │                 │
│  │(Transactions)│  │(VPA Cache│  │(Events)  │  │   (Crypto)    │                 │
│  │             │  │+Sessions)│  │          │  │               │                 │
│  └─────────────┘  └──────────┘  └──────────┘  └───────────────┘                 │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Initiate Pay Request (Payer PSP → Switch)
```xml
<!-- UPI XML message format (simplified) -->
POST /upi/ReqPay
Content-Type: application/xml
X-Signature: <digital_signature>

<upi:ReqPay xmlns:upi="http://npci.org/upi/schema/v2">
  <Head ver="2.0" ts="2024-01-15T10:30:00+05:30" orgId="PHONEPE" msgId="PHE-MSG-001"/>
  <Meta>
    <Tag name="ORIGDEVICE" value="APP"/>
  </Meta>
  <Txn id="PHE-TXN-UUID-001" type="PAY" ts="2024-01-15T10:30:00+05:30" 
       refId="PHE-REF-001" note="Lunch payment">
    <RiskScores>
      <Score provider="PHONEPE" type="PAY" value="LOW"/>
    </RiskScores>
  </Txn>
  <Payer addr="user@ybl" name="John Doe" type="PERSON">
    <Ac addrType="ACCOUNT">
      <Detail name="IFSC" value="HDFC0001234"/>
      <Detail name="ACNUM" value="XXXXX789"/>
    </Ac>
    <Amount value="500.00" curr="INR"/>
  </Payer>
  <Payees>
    <Payee addr="merchant@paytm" name="Coffee Shop" type="ENTITY">
      <Amount value="500.00" curr="INR"/>
    </Payee>
  </Payees>
</upi:ReqPay>

<!-- Response from Switch -->
<upi:RespPay>
  <Head ver="2.0" ts="2024-01-15T10:30:01+05:30" orgId="NPCI" msgId="NPCI-RSP-001"/>
  <Resp reqMsgId="PHE-MSG-001" result="SUCCESS" errCode="" approvalNum="123456">
    <Ref type="PAYER" seqNum="1" addr="user@ybl" settAmount="500.00" 
         approvalNum="123456" respCode="00"/>
    <Ref type="PAYEE" seqNum="1" addr="merchant@paytm" settAmount="500.00"
         approvalNum="654321" respCode="00"/>
  </Resp>
  <Txn id="PHE-TXN-UUID-001" type="PAY" rrn="401512345678"/>
</upi:RespPay>
```

### REST API (PSP to Customer App)
```http
POST /api/v1/payments/pay
Authorization: Bearer <user_token>
X-Device-Fingerprint: <fingerprint>

{
  "payer_vpa": "user@ybl",
  "payee_vpa": "merchant@paytm",
  "amount": 500.00,
  "currency": "INR",
  "remarks": "Lunch payment",
  "upi_pin_encrypted": "<encrypted_pin>",
  "device_info": {"os": "android", "app_version": "4.5.0"}
}

Response 200:
{
  "txn_id": "txn-uuid-001",
  "rrn": "401512345678",
  "status": "COMPLETED",
  "amount": 500.00,
  "payee_name": "Coffee Shop",
  "completed_at": "2024-01-15T10:30:01.500+05:30",
  "approval_number": "123456"
}
```

## 7. Deep Dives

### Deep Dive 1: Transaction Flow (Pay Request)

```
┌───────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────┐
│ Payer │    │ Payer   │    │  NPCI    │    │ Payee   │    │ Payee   │
│  App  │    │  PSP    │    │  Switch  │    │  PSP    │    │  Bank   │
└───┬───┘    └────┬────┘    └────┬─────┘    └────┬────┘    └────┬────┘
    │              │              │               │              │
    │─── Pay ─────▶│              │               │              │
    │  (VPA+PIN)   │              │               │              │
    │              │── ReqPay ───▶│               │              │
    │              │   (signed)   │               │              │
    │              │              │── Resolve VPA─▶│              │
    │              │              │   (payee@psp)  │              │
    │              │              │◀─ VPA Found ──│              │
    │              │              │               │              │
    │              │              │── ReqDebit ──▶│─── Debit ──▶│
    │              │              │   (payer bank) │  (CBS call) │
    │              │              │◀─ Debit OK ──│◀── OK ──────│
    │              │              │               │              │
    │              │              │── ReqCredit ─▶│              │
    │              │              │   (payee bank) │              │
    │              │              │               │── Credit ──▶│
    │              │              │               │   (CBS call) │
    │              │              │◀─ Credit OK ─│◀── OK ──────│
    │              │              │               │              │
    │              │◀─ RespPay ──│               │              │
    │◀── Success ──│  (completed) │               │              │
    │              │              │               │              │
```

#### Timeout Handling at Each Hop
```python
class TransactionOrchestrator:
    """Manages UPI transaction flow with timeout handling at each hop."""
    
    TIMEOUTS = {
        'payer_psp_to_switch': 10,  # seconds
        'switch_to_payer_bank': 10,
        'payer_bank_debit': 10,
        'switch_to_payee_bank': 10,
        'payee_bank_credit': 10,
        'total_transaction': 30,
    }
    
    async def execute_pay(self, request: dict) -> dict:
        """Execute full pay flow with timeout management."""
        
        txn = await self._create_transaction(request)
        
        try:
            # Step 1: Validate payer (PIN verification at payer bank)
            async with timeout(self.TIMEOUTS['switch_to_payer_bank']):
                validation = await self.payer_bank_connector.validate_pin(
                    txn.payer_bank_code, txn.payer_account_ref, request['encrypted_pin']
                )
            if not validation.success:
                return await self._fail_transaction(txn, 'PIN_INVALID', validation.code)
            
            # Step 2: Debit payer account
            async with timeout(self.TIMEOUTS['payer_bank_debit']):
                debit_result = await self.payer_bank_connector.debit(
                    bank_code=txn.payer_bank_code,
                    account_ref=txn.payer_account_ref,
                    amount=txn.amount,
                    rrn=txn.rrn
                )
            
            if not debit_result.success:
                return await self._fail_transaction(txn, 'DEBIT_FAILED', debit_result.code)
            
            await self._update_state(txn, 'DEBIT_SUCCESS')
            
            # Step 3: Credit payee account
            try:
                async with timeout(self.TIMEOUTS['payee_bank_credit']):
                    credit_result = await self.payee_bank_connector.credit(
                        bank_code=txn.payee_bank_code,
                        account_ref=txn.payee_account_ref,
                        amount=txn.amount,
                        rrn=txn.rrn
                    )
                
                if credit_result.success:
                    await self._update_state(txn, 'COMPLETED')
                    return {'status': 'COMPLETED', 'rrn': txn.rrn}
                else:
                    # Credit failed - MUST reverse debit
                    await self._reverse_debit(txn)
                    return await self._fail_transaction(txn, 'CREDIT_FAILED', credit_result.code)
                    
            except asyncio.TimeoutError:
                # Credit timed out - initiate reversal
                await self._handle_credit_timeout(txn)
                return {'status': 'PENDING', 'rrn': txn.rrn, 'message': 'Transaction pending verification'}
        
        except asyncio.TimeoutError:
            # Overall timeout
            await self._handle_timeout(txn)
            return {'status': 'TIMEOUT', 'rrn': txn.rrn}
    
    async def _handle_credit_timeout(self, txn):
        """Handle credit leg timeout - deemed approved or reversal."""
        
        await self._update_state(txn, 'CREDIT_TIMEOUT')
        
        # As per NPCI rules: if credit doesn't respond within timeout,
        # it's "deemed approved" - payee bank must credit within T+1
        # If payee bank later rejects, they must return funds
        
        # Schedule status check after 30 seconds
        await self.scheduler.schedule(
            task='check_credit_status',
            txn_id=txn.txn_id,
            run_at=datetime.now() + timedelta(seconds=30)
        )
        
        # Mark as deemed approved for settlement
        await self._update_state(txn, 'DEEMED_APPROVED')
    
    async def _reverse_debit(self, txn):
        """Reverse a successful debit (credit failed/timed out and rejected)."""
        
        reversal_rrn = self._generate_rrn()
        
        reversal = await self.payer_bank_connector.credit(
            bank_code=txn.payer_bank_code,
            account_ref=txn.payer_account_ref,
            amount=txn.amount,
            rrn=reversal_rrn,
            original_rrn=txn.rrn,
            reason='CREDIT_REVERSAL'
        )
        
        if reversal.success:
            await self._update_state(txn, 'REVERSED')
        else:
            # Reversal failed - critical alert, manual intervention
            await self.alert_service.critical(
                'REVERSAL_FAILED', 
                f"TXN {txn.txn_id} debit reversal failed. Amount: {txn.amount}"
            )
            await self._update_state(txn, 'REVERSAL_PENDING')
```

### Deep Dive 2: Switch Architecture

```python
class NPCISwitch:
    """High-throughput transaction routing switch."""
    
    def __init__(self):
        self.participant_registry = {}  # PSP/Bank connection pool
        self.vpa_directory = VPADirectory()  # VPA → PSP/Bank mapping
        self.rate_limiter = TokenBucketRateLimiter()
    
    async def route_transaction(self, message: dict) -> dict:
        """Route transaction to appropriate participant."""
        
        # Step 1: Parse and validate message signature
        if not self._verify_signature(message):
            return {'error': 'SIGNATURE_INVALID'}
        
        # Step 2: Rate limiting per PSP
        psp_id = message['header']['org_id']
        if not await self.rate_limiter.allow(psp_id):
            return {'error': 'RATE_LIMITED', 'code': 'RP'}
        
        # Step 3: Resolve payee VPA to PSP/Bank
        payee_vpa = message['payee']['addr']
        payee_info = await self.vpa_directory.resolve(payee_vpa)
        
        if not payee_info:
            return {'error': 'VPA_NOT_FOUND', 'code': 'U16'}
        
        # Step 4: Route to payee PSP
        payee_psp = self.participant_registry[payee_info.psp_id]
        
        # Step 5: Forward with timeout
        try:
            response = await asyncio.wait_for(
                payee_psp.send(message),
                timeout=10.0
            )
            return response
        except asyncio.TimeoutError:
            return {'error': 'PAYEE_TIMEOUT', 'code': 'U68'}
    
    async def generate_settlement_file(self, cycle_date: date, cycle_number: int):
        """Generate net settlement positions between banks."""
        
        # Aggregate all completed transactions in this cycle
        transactions = await self.db.fetch_all("""
            SELECT payer_bank_code, payee_bank_code, SUM(amount) as total_amount,
                   COUNT(*) as txn_count
            FROM transactions
            WHERE status = 'COMPLETED'
            AND settled_at IS NULL
            AND completed_at BETWEEN $1 AND $2
            GROUP BY payer_bank_code, payee_bank_code
        """, cycle_start, cycle_end)
        
        # Calculate net positions
        net_positions = {}
        for txn in transactions:
            payer = txn.payer_bank_code
            payee = txn.payee_bank_code
            
            net_positions[payer] = net_positions.get(payer, Decimal('0')) - txn.total_amount
            net_positions[payee] = net_positions.get(payee, Decimal('0')) + txn.total_amount
        
        # Validate: net positions must sum to zero
        assert sum(net_positions.values()) == Decimal('0'), "Settlement imbalance!"
        
        # Create settlement batch
        batch = await self.db.execute("""
            INSERT INTO settlement_batches 
            (cycle_date, cycle_number, total_transactions, total_amount, net_positions, status)
            VALUES ($1, $2, $3, $4, $5, 'READY')
            RETURNING batch_id
        """, cycle_date, cycle_number, sum(t.txn_count for t in transactions),
            sum(t.total_amount for t in transactions), net_positions)
        
        # Submit to RBI settlement system
        await self.rbi_connector.submit_settlement(batch.batch_id, net_positions)
        
        return batch
```

### Deep Dive 3: Dispute Lifecycle

```python
class DisputeManager:
    """Handle UPI dispute resolution within NPCI TAT."""
    
    SLA_DAYS = 5  # Business days
    
    async def file_dispute(self, txn_id: str, complainant_vpa: str, 
                          dispute_type: str, reason: str) -> dict:
        """File a new dispute."""
        
        txn = await self.db.fetch_one("SELECT * FROM transactions WHERE txn_id = $1", txn_id)
        
        # Validate dispute eligibility
        if txn.status != 'COMPLETED':
            return {'error': 'Transaction not completed, cannot dispute'}
        
        days_since = (date.today() - txn.completed_at.date()).days
        if days_since > 30:
            return {'error': 'Dispute window expired (30 days)'}
        
        # Create dispute
        sla_deadline = self._calculate_sla_deadline(date.today(), self.SLA_DAYS)
        
        dispute = await self.db.execute("""
            INSERT INTO disputes (txn_id, rrn, complainant_vpa, complainant_type,
                dispute_type, dispute_reason, amount, status, sla_deadline)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'FILED', $8)
            RETURNING dispute_id
        """, txn_id, txn.rrn, complainant_vpa,
            'PAYER' if complainant_vpa == txn.payer_vpa else 'PAYEE',
            dispute_type, reason, txn.amount, sla_deadline)
        
        # Route to respondent bank/PSP
        respondent_psp = txn.payee_psp_id if complainant_vpa == txn.payer_vpa else txn.payer_psp_id
        
        await self.kafka.produce('dispute.filed', {
            'dispute_id': dispute.dispute_id,
            'txn_id': txn_id,
            'respondent_psp': respondent_psp,
            'sla_deadline': sla_deadline.isoformat()
        })
        
        return {'dispute_id': dispute.dispute_id, 'sla_deadline': sla_deadline}
    
    async def process_chargeback(self, dispute_id: str):
        """Execute chargeback: reverse funds from payee to payer."""
        
        dispute = await self.db.fetch_one("SELECT * FROM disputes WHERE dispute_id = $1", dispute_id)
        txn = await self.db.fetch_one("SELECT * FROM transactions WHERE txn_id = $1", dispute.txn_id)
        
        # Initiate reversal transaction
        reversal_txn = await self.transaction_orchestrator.execute_reversal(
            original_txn=txn,
            amount=dispute.resolution_amount or txn.amount,
            reason=f"CHARGEBACK-{dispute.dispute_type}"
        )
        
        if reversal_txn.status == 'COMPLETED':
            await self.db.execute("""
                UPDATE disputes SET status = 'RESOLVED', resolution = 'REFUNDED',
                    resolution_amount = $1, resolved_at = NOW()
                WHERE dispute_id = $2
            """, reversal_txn.amount, dispute_id)
        
        return reversal_txn
```

## 8. Component Optimization

### Kafka Configuration
```yaml
upi.transactions:
  partitions: 128  # High throughput (40K TPS)
  replication-factor: 3
  min.insync.replicas: 2
  acks: all
  retention.ms: 604800000  # 7 days
  partition-key: rrn  # Ensures ordering per transaction

upi.settlements:
  partitions: 16
  replication-factor: 3
  retention.ms: 2592000000  # 30 days

upi.disputes:
  partitions: 8
  replication-factor: 3
```

### Redis Configuration
```yaml
redis:
  cluster: 12 nodes
  
  # VPA resolution cache
  vpa-cache:
    key: "vpa:{vpa_address}"
    type: hash  # {psp_id, bank_code, account_ref, customer_name}
    ttl: 3600  # 1 hour
    
  # Transaction dedup (prevent double processing)
  txn-dedup:
    key: "txn:{rrn}"
    ttl: 86400  # 24h
    type: string (SET NX)
    
  # Rate limiting per PSP
  rate-limit:
    key: "rl:{psp_id}:{second}"
    type: counter
    ttl: 2  # 2 second window
    limit: 5000  # per second per PSP
    
  # Session (PIN verification state)
  session:
    key: "session:{device_id}"
    ttl: 300  # 5 min
```

## 9. Observability

### Metrics
```yaml
metrics:
  - name: upi_transaction_latency_ms
    type: histogram
    labels: [txn_type, status, payer_psp, payee_psp]
    buckets: [500, 1000, 1500, 2000, 3000, 5000, 10000, 30000]
  
  - name: upi_success_rate
    type: gauge
    labels: [psp_id, bank_code]
    alert_threshold: 0.995
  
  - name: upi_tps
    type: gauge
    labels: [direction]
  
  - name: upi_timeout_rate
    type: gauge
    labels: [leg]  # debit_leg, credit_leg
    
  - name: settlement_discrepancy
    type: gauge
    alert_threshold: 0

alerts:
  - name: HighTimeoutRate
    expr: upi_timeout_rate > 0.01
    severity: critical
    
  - name: BankConnectivityDown
    expr: bank_heartbeat_age_seconds{bank_code=~".+"} > 30
    severity: critical
    
  - name: SettlementImbalance
    expr: settlement_discrepancy != 0
    severity: critical
```

## 10. Failure Modes & Considerations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Payer bank timeout after debit | Money debited, not credited | Auto-reversal after timeout + deemed approval |
| Switch outage | All UPI payments fail | Active-active across 2 data centers |
| VPA resolution failure | Can't find payee | Cache + retry + graceful error |
| Double credit | Payee gets money twice | Idempotency on RRN at bank level |
| Mandate executed twice | Double debit | UMN + date based idempotency |

### Security
- End-to-end encryption of UPI PIN (device to bank HSM)
- Digital signatures on all inter-participant messages (PKI)
- Device binding (SIM + device fingerprint)
- Transaction velocity checks (fraud detection)
- Multi-factor: PIN + device + SIM

## 11. Trade-offs & Alternatives

| Decision | Choice | Alternative | Why |
|----------|--------|-------------|-----|
| Message format | XML (NPCI spec) | JSON/Protobuf | Regulatory requirement (NPCI standard) |
| Settlement | Net multilateral | Real-time gross (RTGS) | Efficiency at scale (netting reduces flows) |
| VPA directory | Centralized (NPCI) | Distributed (each PSP) | Single source of truth, instant resolution |
| Timeout strategy | Deemed approval | Immediate reversal | Prevents stuck transactions, payee bank liability |
| Dispute model | Chargeback-based | Escrow | Similar to card networks, proven model |
