# Affordability Platform - Workflows & Sequence Diagrams

## 1. EMI Offer Discovery Flow

### Sequence Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant M as Merchant/Checkout
    participant OA as OfferAdapter
    participant GA as GatewayAdapter
    participant DA as DiscoveryAdapter
    participant RS as ReadServ
    participant RC as Redis Cache
    participant DB as PostgreSQL (Replicas)

    M->>OA: POST /api/affordability/v1/offer/discovery
    OA->>OA: JWT Authentication & Validation
    OA->>GA: POST /api/affordability/v1/offer/discovery
    GA->>GA: BIN Lookup (identify issuer from card BIN)
    GA->>DA: POST /offer/discovery (with issuer context)
    
    DA->>DA: Build ReadServ request (Bank EMI + Brand EMI parallel)
    
    par Bank EMI Discovery
        DA->>RS: POST /v1/affordability/calculate-emi (BANK_EMI)
        RS->>RC: GET OFFER:{clientId}:{version}:{SHA256(request)}
        alt Cache HIT
            RC-->>RS: Compressed EMI Response
            RS->>RS: Decompress (GZIP)
            RS-->>DA: EMI Plans (cached)
        else Cache MISS
            RC-->>RS: null
            RS->>RS: Load client from cache/DB
            RS->>RC: GET CLIENT:{type}:{channel}:{id}:{tenant}
            alt Client Cache MISS
                RS->>DB: SELECT * FROM client WHERE ...
                RS->>RC: SET CLIENT:... (TTL 15min)
            end
            RS->>RS: Fetch issuer EMI configs
            RS->>RC: GET MASTER_ISSUER_EMI_CONFIG:{channel}
            alt Config Cache MISS
                RS->>DB: SELECT * FROM issuer_emi_config WHERE ...
                RS->>RC: SET MASTER_ISSUER_EMI_CONFIG:... (TTL 120min)
            end
            RS->>RS: Fetch offer details (async)
            RS->>DB: Native SQL: offer_parameters + subvention + discount
            RS->>RS: Fetch offer codes (async)
            RS->>DB: SELECT * FROM issuer_emi_offer_code_config
            RS->>RS: Calculate EMI for each tenure
            RS->>RS: Apply subvention/discount breakup
            RS->>RS: Apply velocity validation
            RS->>RC: SET OFFER:{key} = GZIP(response) TTL 60min
            RS-->>DA: EMI Plans (computed)
        end
    and Brand EMI Discovery
        DA->>RS: POST /v1/affordability/calculate-emi (BRAND_EMI)
        RS->>RC: GET OFFER:{clientId}:{version}:{SHA256(request)}
        Note over RS,DB: Same flow as Bank EMI...
        RS-->>DA: Brand EMI Plans
    end
    
    DA->>DA: Merge Bank + Brand EMI results
    DA->>DA: Cache product display names (30-day TTL)
    DA-->>GA: Combined offer response
    GA-->>OA: Offer response
    OA-->>M: Available EMI offers
```

---

## 2. EMI Transaction Lifecycle (Online Payment)

### Sequence Diagram

```mermaid
sequenceDiagram
    participant CH as Checkout/NXT
    participant GA as GatewayAdapter
    participant PA as ProcessingAdapter
    participant TS as TransactionServ
    participant RS as ReadServ
    participant VEL as Velocity Service
    participant CL as Credit Limit Service
    participant ACQ as Acquirer
    participant KF as Kafka
    participant DB as PostgreSQL

    %% Phase 1: Create Transaction
    CH->>GA: POST /offer/validate (offer selection)
    GA->>PA: POST /offer/validate
    PA->>TS: POST /v1/affordability/transactions/
    TS->>DB: INSERT affordability_transaction (status=INITIATED)
    TS->>DB: INSERT affordability_transaction_extension
    TS->>DB: INSERT affordability_transaction_product_details
    TS->>TS: Set self_expiring_date_time (now + 3600s)
    TS-->>PA: Transaction ID + Status=INITIATED
    PA-->>GA: Offer validated
    GA-->>CH: Transaction reference

    %% Phase 2: Pre-Payment
    CH->>GA: POST /offer/{txnId}/confirm
    GA->>PA: Forward to processing
    PA->>TS: POST /v1/affordability/transactions/{id}/pre-payment

    TS->>TS: Execute Task Pipeline
    
    rect rgb(240, 248, 255)
        Note over TS,CL: Task 1: Velocity Check
        TS->>VEL: POST /velocity/validate (card_hash + phone)
        VEL->>DB: Check velocity_txn_details counts
        VEL-->>TS: ALLOWED / BLOCKED
        TS->>DB: INSERT task_details (VELOCITY_CHECK, SUCCESS)
    end
    
    rect rgb(240, 255, 240)
        Note over TS,CL: Task 2: Credit Limit Block
        TS->>CL: POST /check-eligibility (BIN + amount)
        CL-->>TS: Eligible + credit_limit
        TS->>CL: POST /book-order (block amount)
        CL-->>TS: Block confirmed
        TS->>DB: INSERT task_details (CREDIT_LIMIT_BLOCK, SUCCESS)
    end
    
    rect rgb(255, 248, 240)
        Note over TS,CL: Task 3: IMEI Validation (if applicable)
        TS->>TS: Validate IMEI with OEM (Apple/Samsung)
        TS->>DB: INSERT task_details (IMEI_VALIDATE, SUCCESS)
    end

    TS-->>PA: Pre-payment SUCCESS
    PA-->>GA: Pre-payment complete
    GA-->>CH: Ready for payment

    %% Phase 3: Complete Payment (after acquirer confirmation)
    CH->>GA: POST /offer/{txnId}/confirm (with acquirer response)
    GA->>PA: Forward
    PA->>TS: POST /v1/affordability/transactions/{id}/complete-payment

    TS->>RS: POST /v1/affordability/calculate-emi (final calculation)
    RS-->>TS: EMI details (monthly_emi, interest, breakup)
    
    TS->>DB: UPDATE affordability_transaction SET status=APPROVED
    TS->>DB: INSERT affordability_online_bank_emi_txn_ledger (SALE)
    TS->>DB: UPDATE offer_json in extension
    TS->>DB: Debit budget (affordability_txn_budget_ledger)
    TS->>VEL: POST /velocity/increment (block velocity slot)
    
    TS-->>PA: Payment APPROVED
    PA-->>GA: Confirmed
    GA-->>CH: Payment successful

    %% Phase 4: Settlement
    Note over CH,KF: Settlement (async, triggered by merchant/schedule)
    CH->>GA: POST /offer/{txnId}/settle
    GA->>PA: Forward
    PA->>TS: POST /v1/affordability/transactions/{id}/settle-payment
    TS->>DB: UPDATE affordability_transaction SET status=SETTLED
    TS->>DB: INSERT settlement_instruction_audit
    TS->>KF: Publish to auth-settlement-request topic
    Note over KF: Headers: X-source, X-channel, X-requestType, X-operationType
    TS-->>PA: Settled
    PA-->>GA: Settlement confirmed
    GA-->>CH: Transaction settled
```

---

## 3. Refund Flow

### Sequence Diagram

```mermaid
sequenceDiagram
    participant M as Merchant
    participant GA as GatewayAdapter
    participant PA as ProcessingAdapter
    participant TS as TransactionServ
    participant VEL as Velocity Service
    participant CL as Credit Limit Service
    participant DB as PostgreSQL

    M->>GA: POST /offer/{txnId}/refund
    GA->>PA: Forward refund request
    PA->>TS: POST /v1/affordability/transactions/{id}/refund-payment
    
    TS->>TS: Check idempotent_key (prevent duplicate refunds)
    TS->>DB: SELECT FROM affordability_idempotent_keys
    
    alt Already processed
        TS-->>PA: Return existing refund result
    else New refund
        TS->>DB: Validate transaction_status = SETTLED or PARTIAL_REFUNDED
        TS->>DB: Validate refund_amount <= remaining_settled_amount
        
        TS->>DB: INSERT affordability_idempotent_keys
        
        %% Reverse tasks
        TS->>VEL: POST /velocity/decrement (release velocity slot)
        TS->>CL: POST /close-account (unblock credit limit)
        
        %% Update transaction
        alt Full Refund
            TS->>DB: UPDATE status = REFUNDED
        else Partial Refund
            TS->>DB: UPDATE status = PARTIAL_REFUNDED
        end
        
        TS->>DB: INSERT affordability_online_bank_emi_txn_ledger (REFUND)
        TS->>DB: CREDIT budget (reverse budget consumption)
        
        TS-->>PA: Refund SUCCESS
    end
    
    PA-->>GA: Refund confirmed
    GA-->>M: Refund processed
```

---

## 4. Offer Lifecycle (Admin Portal)

### Activity Diagram

```mermaid
stateDiagram-v2
    [*] --> CreateOffer: Brand/Merchant initiates

    state CreateOffer {
        [*] --> ValidateDates
        ValidateDates --> ValidateCampaign
        ValidateCampaign --> CheckDuplicate
        CheckDuplicate --> SaveDraft
        SaveDraft --> CreateEvent: Save OfferUpdateEvent(PENDING)
    }

    CreateOffer --> DRAFT

    DRAFT --> ConfigureParameters: Add tenures, amounts, subvention
    ConfigureParameters --> DRAFT

    DRAFT --> PENDING_FOR_APPROVAL: SUBMIT (requires edit_offers permission)
    
    PENDING_FOR_APPROVAL --> APPROVED: APPROVE (requires external_offer_approval)
    PENDING_FOR_APPROVAL --> REJECTED: REJECT (with comment)
    REJECTED --> DRAFT: Revise and resubmit

    APPROVED --> LIVE: startDate <= now <= endDate (automatic)
    APPROVED --> SCHEDULED: startDate > now (automatic)
    
    LIVE --> PAUSED: PAUSE (temporarily disable)
    PAUSED --> LIVE: RESUME

    LIVE --> INACTIVATED: INACTIVATE (permanent disable)
    SCHEDULED --> INACTIVATED: INACTIVATE
    APPROVED --> INACTIVATED: INACTIVATE

    state "After each state change" as Audit {
        [*] --> SaveAuditRecord
        SaveAuditRecord --> CreateCacheEvent
        CreateCacheEvent --> [*]
    }
```

---

## 5. Cache Invalidation Workflow

### Activity Diagram

```mermaid
flowchart TD
    A[Offer Updated in DB] --> B[AsyncOfferEventService saves OfferUpdateEvent]
    B --> C{Wait for poll cycle<br/>every 120 seconds}
    C --> D[CacheManagementServ polls<br/>offer_update_events WHERE status=PENDING]
    D --> E{Events found?}
    E -->|No| C
    E -->|Yes| F[Acquire distributed lock<br/>lock:cache:clear:request]
    F --> G{Lock acquired?}
    G -->|No| C
    G -->|Yes| H[Deduplication check<br/>10-min window]
    H --> I{Duplicate?}
    I -->|Yes| J[Skip - mark PROCESSED]
    I -->|No| K[Route to OfferCacheRefreshProcessorFactory]
    K --> L[Determine affected cache patterns]
    L --> M[SCAN Redis for matching keys]
    M --> N[Batch DELETE<br/>1000 keys/batch<br/>100 concurrent threads]
    N --> O[Read HOT_KEYS_SORTED_SET<br/>top 1000]
    O --> P{Hot keys affected?}
    P -->|Yes| Q[Pre-warm: Rebuild from DB<br/>SET with normal TTL]
    P -->|No| R[Mark events PROCESSED]
    Q --> R
    R --> S[Release distributed lock]
    S --> C
    J --> S
```

---

## 6. EMI Calculation Engine Flow

### Activity Diagram

```mermaid
flowchart TD
    A[Request: client, products, amount, issuer, tenure] --> B{Request has cardData<br/>or customerDetails?}
    B -->|Yes| C[Skip cache - personalized]
    B -->|No| D[Generate cache key:<br/>SHA256 of normalized request]
    D --> E{Redis cache hit?}
    E -->|Yes| F[Decompress GZIP response]
    F --> G[Return cached response]
    E -->|No| C
    
    C --> H[Load Client entity<br/>from cache/DB]
    H --> I[Resolve Client Group<br/>& Program Types]
    I --> J[Parallel async fetch]
    
    J --> K1[Fetch Issuer EMI Configs<br/>from cache/DB]
    J --> K2[Fetch Offer Details<br/>native SQL query]
    J --> K3[Fetch Offer Codes<br/>from cache/DB]
    J --> K4[Fetch Product Mappings<br/>Redis Hash HMGET]
    
    K1 --> L[CompletableFuture.allOf - wait]
    K2 --> L
    K3 --> L
    K4 --> L
    
    L --> M[Filter by BIN range<br/>sorted set lookup]
    M --> N[Filter by amount bounds<br/>min_amount <= txn_amount <= max_amount]
    N --> O[Filter by tenure<br/>if specific tenure requested]
    O --> P[Filter by applicability<br/>days bitmap, hours, dates]
    
    P --> Q{Program Type?}
    Q -->|BANK_EMI| R1[BankEmiCalculator]
    Q -->|BRAND_EMI| R2[BrandEmiCalculator]
    
    R1 --> S[For each eligible issuer+tenure:]
    R2 --> S
    
    S --> T[Calculate monthly EMI:<br/>P × r × (1+r)^n / ((1+r)^n - 1)]
    T --> U[Calculate total interest]
    U --> V[Apply subvention<br/>sequence-based multi-party split]
    V --> W[Apply discount<br/>merchant + brand + issuer + dealer shares]
    W --> X[Calculate processing fee:<br/>min of fixed, % of amount, max cap]
    X --> Y[Calculate net payment amount]
    Y --> Z[Apply split EMI if applicable]
    Z --> AA[Build tenure response object]
    
    AA --> AB{More tenures?}
    AB -->|Yes| S
    AB -->|No| AC[Assemble full response]
    
    AC --> AD{Cacheable request?}
    AD -->|Yes| AE[GZIP compress + Redis SET<br/>TTL: client.offerCacheTtlMinutes or 60min]
    AD -->|No| AF[Return response directly]
    AE --> AF
```

---

## 7. Cardless EMI Flow (ICICI)

### Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Customer
    participant M as Merchant POS/Online
    participant TS as TransactionServ
    participant CC as Cardless Issuer Connector
    participant ICICI as ICICI Bank API
    participant DB as PostgreSQL

    %% Step 1: Eligibility Check
    M->>TS: Create transaction (program_type=BANK_EMI, issuer_type=CARDLESS)
    TS->>DB: INSERT transaction (INITIATED)
    TS->>CC: POST /v1/cardless-issuers/pre-eligibility-check
    CC->>ICICI: POST /pre-eligibility (encrypted payload)
    ICICI-->>CC: Eligible + available_limit
    CC-->>TS: Customer eligible
    TS-->>M: Show EMI options

    %% Step 2: Send OTP
    M->>TS: POST /transactions/{id}/send-otp
    TS->>CC: POST /v1/cardless-issuers/send-otp
    CC->>ICICI: POST /eligibility (triggers OTP)
    ICICI-->>CC: OTP sent to customer mobile
    CC-->>TS: OTP dispatched
    TS->>DB: INSERT task_details (SEND_OTP, SUCCESS)
    TS-->>M: OTP sent

    %% Step 3: Customer enters OTP
    C->>M: Enter OTP
    M->>TS: POST /transactions/{id}/validate-otp
    TS->>CC: POST /v1/cardless-issuers/validate-otp
    CC->>ICICI: POST /validation (OTP + loan details)
    ICICI-->>CC: OTP valid + loan_reference
    CC-->>TS: Validated
    TS->>DB: INSERT task_details (VALIDATE_OTP, SUCCESS)
    TS-->>M: OTP validated

    %% Step 4: Confirm Transaction
    M->>TS: POST /transactions/{id}/complete-payment
    TS->>CC: POST /v1/cardless-issuers/confirmation
    CC->>ICICI: POST /confirmation (loan confirmation)
    ICICI-->>CC: Loan confirmed + reference_number
    CC-->>TS: Confirmed
    TS->>DB: UPDATE status = APPROVED
    TS->>DB: INSERT ledger (SALE)
    TS-->>M: Payment approved

    %% Cancellation (if needed)
    Note over M,ICICI: If customer wants to cancel
    M->>TS: POST /transactions/{id}/cancel-payment
    TS->>CC: POST /v1/cardless-issuers/cancellation
    CC->>ICICI: POST /cancellation
    ICICI-->>CC: Cancelled
    CC-->>TS: Cancellation confirmed
    TS->>DB: UPDATE status = CANCELLED
```

---

## 8. NBFC Lending Flow

### Sequence Diagram

```mermaid
sequenceDiagram
    participant POS as POS Terminal
    participant TXN as TxnProcessorServ
    participant NBFC as NBFC Connector
    participant BFL as Bajaj Finance/HDB
    participant DB as MSSQL (PLUTUS_HUB)

    POS->>TXN: POST /v1/paylater/transactions (integration_type=LENDING)
    TXN->>DB: INSERT PAYLATER_TXN_TBL (INITIATED)
    TXN-->>POS: Transaction ID

    POS->>TXN: POST /transactions/{id}/pre-payment
    TXN->>NBFC: POST /check-eligibility
    NBFC->>BFL: Check customer eligibility (mobile + KYC)
    BFL-->>NBFC: Eligible + schemes list
    NBFC-->>TXN: Available NBFC schemes
    
    TXN->>NBFC: POST /fetch-schemes
    NBFC->>BFL: Get detailed scheme list
    BFL-->>NBFC: EMI plans with interest rates
    NBFC-->>TXN: Scheme options
    TXN->>DB: UPDATE LENDING_SCHEME_JSON
    TXN-->>POS: Show NBFC options

    POS->>TXN: POST /transactions/{id}/complete-payment (with selected scheme)
    
    %% OTP Flow
    TXN->>NBFC: POST /generate-otp
    NBFC->>BFL: Request OTP
    BFL-->>NBFC: OTP sent
    NBFC-->>TXN: OTP dispatched
    TXN-->>POS: Waiting for OTP

    POS->>TXN: Submit OTP
    TXN->>NBFC: POST /submit-loan (with OTP + scheme)
    NBFC->>BFL: Submit loan application
    BFL-->>NBFC: Loan approved (approval_code, reference_id)
    NBFC-->>TXN: Loan granted
    
    TXN->>DB: UPDATE status=COMPLETED
    TXN->>DB: UPDATE LENDING_APPROVAL_CODE, LOAN_APPLICATION_NUMBER
    TXN->>DB: INSERT task_status (GRANT_LOAN_STATUS=SUCCESS)
    TXN-->>POS: Payment complete (print chargeslip)
```

---

## 9. Settlement & Reconciliation Flow

### Activity Diagram

```mermaid
flowchart TD
    A[Transaction APPROVED] --> B{Settlement trigger}
    B -->|Manual| C[Merchant calls settle-payment API]
    B -->|Batch| D[Bulk settle scheduled job]
    B -->|Auto| E[T+1 auto-settlement rule]
    
    C --> F[Validate transaction_status = APPROVED]
    D --> F
    E --> F
    
    F --> G[Generate settlement instruction]
    G --> H[Create AffordabilityFundSettlement record]
    H --> I[Create settlement detail records per party]
    
    I --> I1[Merchant settlement amount]
    I --> I2[Brand subvention amount]
    I --> I3[Issuer subvention amount]
    I --> I4[Dealer subvention amount]
    
    I1 --> J[Publish Kafka event]
    I2 --> J
    I3 --> J
    I4 --> J
    
    J --> K[Topic: auth-settlement-request]
    K --> L[OMS Settlement Instruction Service]
    L --> M[Generate payout instructions]
    M --> N[Bank transfer / NEFT / IMPS]
    
    N --> O[Update transaction_status = SETTLED]
    O --> P[Create SettlementInstructionAudit]
    P --> Q[Notify merchant via webhook]
```

---

## 10. Velocity Check Workflow

### Activity Diagram

```mermaid
flowchart TD
    A[Pre-payment request with card_hash + phone] --> B[Look up velocity rules]
    B --> C{Multiple rules configured?}
    C -->|Yes| D[Apply all matching rules]
    C -->|No| E[Apply default rule]
    
    D --> F[For each rule:]
    E --> F
    
    F --> G{Rule type?}
    G -->|CARD_HASH| H[Count txns by card_hash in window]
    G -->|MOBILE_NUMBER| I[Count txns by phone in window]
    G -->|CARDLESS| J[Count cardless txns in window]
    
    H --> K{Count < threshold?}
    I --> K
    J --> K
    
    K -->|Yes| L[ALLOWED - proceed]
    K -->|No| M[BLOCKED - reject transaction]
    
    L --> N{On complete-payment}
    N --> O[Increment velocity counter]
    O --> P[Insert velocity_txn_map record]
    
    M --> Q[Return error: Velocity limit exceeded]
    
    Note over L,P: On cancellation/refund
    P --> R{Transaction cancelled/refunded?}
    R -->|Yes| S[Decrement velocity counter]
    S --> T[Insert velocity_txn_map DECREMENT]
```

---

## 11. Budget Enforcement Workflow

```mermaid
flowchart TD
    A[Transaction complete-payment] --> B[Find associated budget]
    B --> C{Budget found?}
    C -->|No| D[Proceed without budget check]
    C -->|Yes| E[Calculate subvention + discount amounts]
    
    E --> F{is_threshold_breach_restricted?}
    F -->|Yes| G[Check: consumed + new_amount <= threshold]
    F -->|No| H[Allow but track consumption]
    
    G --> I{Within budget?}
    I -->|Yes| J[Debit budget ledger]
    I -->|No| K[Reject: Budget exceeded]
    
    H --> J
    
    J --> L[UPDATE budget SET total_consumed += amount]
    L --> M[INSERT affordability_txn_budget_ledger DEBIT]
    
    M --> N{Check health thresholds}
    N --> O{consumed / threshold × 100}
    O -->|< 50%| P[Status: HEALTHY]
    O -->|50-80%| Q[Status: MODERATE - alert]
    O -->|> 80%| R[Status: CRITICAL - alert]
    
    Note over J,M: On refund/void
    M --> S{Refund triggered?}
    S -->|Yes| T[Credit budget: consumed -= refund_amount]
    T --> U[INSERT budget_ledger CREDIT]
```
