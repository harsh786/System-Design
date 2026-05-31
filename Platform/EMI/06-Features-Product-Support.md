# Affordability Platform - Features & Product Support

## 1. Product/Payment Mode Matrix

| Payment Mode | Channel | Card Type | Issuers | Flow Type |
|---|---|---|---|---|
| **Bank EMI (Credit Card)** | Online + Offline | Credit Card | HDFC, ICICI, SBI, Axis, Kotak, RBL, HSBC, Citi, BOB, etc. | Card-present / Card-not-present |
| **Bank EMI (Debit Card)** | Online + Offline | Debit Card | HDFC, ICICI, Axis, SBI, Kotak | OTP + Credit Limit Check |
| **Brand EMI (Credit Card)** | Online + Offline | Credit Card | All banks with brand tie-up | No-cost / Low-cost EMI |
| **Brand EMI (Debit Card)** | Online + Offline | Debit Card | Selected banks | OTP + Brand subvention |
| **Cardless EMI** | Online + Offline | None (mobile-based) | ICICI, HDFC, Kotak | OTP-based verification |
| **NBFC Lending (NTB)** | Offline (POS) | None | Bajaj Finance, HDB, HomeCredit, LiquiLoans, TVS Credit | Full loan origination |
| **BNPL (Buy Now Pay Later)** | Online | None | LazyPay, ePayLater, Flipkart Pay Later | Instant credit line |
| **EMI on UPI** | Online | UPI VPA | HDFC, ICICI, SBI | UPI mandate + EMI |
| **My EMI** | Online + Offline | Credit Card | All issuers | Standard bank rate (no subvention) |
| **Split EMI** | Online + Offline | Credit/Debit | Selected issuers | Down payment + reduced EMI |

---

## 2. Feature Catalog

### 2.1 Core EMI Features

| Feature | Description | Technical Implementation |
|---------|-------------|------------------------|
| **No-Cost EMI** | 0% interest - fully subvented by brand/merchant | `subvention_amount = interest_amount`, split via `subvention_parameters` |
| **Low-Cost EMI** | Reduced interest - partially subvented | `subvention_amount < interest_amount`, remaining paid by customer |
| **Standard EMI** | Full interest borne by customer | `program_type = MY_EMI`, no subvention |
| **Multi-Tenure** | Multiple tenure options (3/6/9/12/18/24 months) | `tenure` table + `offer_parameter_tenure_map` |
| **Down Payment** | Customer pays upfront amount, EMI on remainder | `down_payment_fixed_amount` in `offer_parameters` |
| **Advance EMI** | First N EMIs collected upfront | `advance_emi_applicable = true`, `advance_emi_months` |
| **Split EMI** | Partial amount as instant payment, rest as EMI | `split_emi_parameters` (percentage/fixed) |
| **Processing Fee** | Bank charges for EMI conversion | `processing_fee_fixed/percentage/min/max` in `issuer_emi_config` |

### 2.2 Offer & Discount Features

| Feature | Description | Technical Implementation |
|---------|-------------|------------------------|
| **Instant Discount** | Immediate price reduction at checkout | `discount_type = INSTANT`, deducted from `transaction_amount` |
| **Cashback** | Post-purchase credit to customer | `discount_type = POST_CASHBACK`, tracked separately |
| **Multi-Party Subvention** | Cost split across merchant + brand + issuer + dealer | `subvention_parameters` with sequence-based priority |
| **Multi-Party Discount** | Discount funded by multiple parties | `discount_parameters` with share calculations |
| **Offer Codes** | Bank-specific scheme codes for acquirer communication | `issuer_emi_offer_code_config` / `brand_emi_offer_code_config` |
| **Product-Level Offers** | Offers tied to specific products/SKUs | `product_offer_association` table |
| **Bundle Offers** | Offers for product combinations | `bundle` + `bundle_product_map` + `bundle_offer_map` |
| **Time-Bound Offers** | Offers active only during specific hours/days | `start_hour`, `end_hour`, `applicable_days_bitmap` |
| **Campaign Budgets** | Capped total spend per campaign | `budget` table with threshold tracking |
| **Velocity Controls** | Per-card/phone frequency limits | `velocity_rule_configuration` with type-based counting |

### 2.3 Security & Compliance Features

| Feature | Description | Technical Implementation |
|---------|-------------|------------------------|
| **IMEI Blocking** | Lock device to EMI (prevent resale during loan) | `IMEIBlockTask` → OEM API (Apple/Samsung) |
| **KFS (Key Fact Statement)** | RBI-mandated loan disclosure document | `KfsService` generates regulatory-compliant document |
| **Card Encryption (HSM)** | Hardware Security Module for PAN encryption | Thrift-based HSM integration, `encrypted_pan_number` |
| **Idempotency** | Prevent duplicate refund/void operations | `affordability_idempotent_keys` table |
| **OTP Verification** | Customer authentication for cardless/debit EMI | `SendOtpService` + `OTPValidationService` |
| **BIN Validation** | Card issuer identification from first 6-8 digits | `bin_range` sorted set lookup |
| **Transaction Expiry** | Auto-cancel stale transactions | `self_expiring_date_time` with scheduled cleanup |

### 2.4 Multi-Tenant & Channel Features

| Feature | Description | Technical Implementation |
|---------|-------------|------------------------|
| **Multi-Tenant** | White-label deployment support | `tenant_name` on all entities (PL.IN, SaaS variants) |
| **Channel Separation** | Different configs for online vs offline | `channel` field (ONLINE/OFFLINE) on configs |
| **Client Hierarchy** | Store → Merchant → Partner grouping | `client` → `client_group_map` → hierarchy |
| **Per-Client Cache TTL** | Custom cache duration per merchant | `client.offer_cache_ttl_minutes` |
| **Feature Flags** | Runtime feature toggles | `X-Feature-Flags` header (ENABLE_NBFC, ENABLE_V2_ISSUER_TYPE) |

### 2.5 Settlement & Reconciliation Features

| Feature | Description | Technical Implementation |
|---------|-------------|------------------------|
| **Auto-Settlement** | T+1 or T+2 automatic settlement | Batch processing scheduled job |
| **Partial Void** | Void part of approved amount | `action_type = PARTIAL_VOID` in ledger |
| **Partial Refund** | Refund subset of settled amount | `action_type = PARTIAL_REFUND`, cumulative tracking |
| **Fund Settlement** | Per-party payout calculation | `affordability_fund_settlement_detail` per party |
| **Settlement Instruction** | OMS integration for payout | Kafka → `auth-settlement-request` topic |
| **Bulk Settlement** | Batch settle multiple transactions | `/bulk-settle-payment` endpoint |

### 2.6 Analytics & Reporting Features

| Feature | Description | Technical Implementation |
|---------|-------------|------------------------|
| **Budget Health Dashboard** | Real-time budget consumption tracking | Healthy (<50%), Moderate (50-80%), Critical (>80%) |
| **Offer Performance** | Transaction count, amount per offer | Analytics Service → Redshift queries |
| **Excel Export** | Download offers, campaigns, budgets as Excel | S3-based streaming Excel generation |
| **Audit Trail** | Complete state change history | `offer_state_change_history`, `*_audit` tables |

---

## 3. EMI Calculation Formula

### Standard EMI (Reducing Balance)
```
EMI = P × r × (1 + r)^n / ((1 + r)^n - 1)

Where:
  P = Principal (loan amount in paisa)
  r = Monthly interest rate = (annual_roi / 12 / 100)
  n = Number of months (tenure)
```

### No-Cost EMI Calculation
```
interest_amount = total_emi_amount - loan_amount
subvention_amount = interest_amount  (fully subsidized)

Effective cost to customer = loan_amount
Monthly EMI = loan_amount / tenure_months
```

### Multi-Party Subvention Split (Sequence-Based)
```
Total subvention = interest_amount

// Apply in sequence order (1=first, 4=last)
For each party in sequence order:
  if (party.fixed_amount > 0):
    party_contribution = min(party.fixed_amount, remaining_subvention)
  elif (party.percentage > 0):
    party_contribution = min(
      loan_amount × party.percentage / 100,
      party.max_amount,
      remaining_subvention
    )
  remaining_subvention -= party_contribution

// Example: Merchant(seq=1, 40%) + Brand(seq=2, 60%)
// On Rs.50,000 @ 12 months, interest = Rs.3,300
// Merchant pays: min(50000 × 40% = 20000, 3300) = Rs.3,300? 
// Actually: Merchant: 3300 × 40% = Rs.1,320, Brand: 3300 × 60% = Rs.1,980
```

### Processing Fee Calculation
```
if (fixed_amount > 0):
  fee = fixed_amount
elif (percentage > 0):
  fee = loan_amount × percentage / 10000  // percentage in basis points
  fee = max(fee, min_amount)
  fee = min(fee, max_amount)

gst_on_fee = fee × 18 / 100  // india.tax.percentage = 18%
total_processing_cost = fee + gst_on_fee
```

### Split EMI Calculation
```
if (split_emi.enabled_on_txn_amount):
  split_amount = txn_amount × split_emi.percentage / 100
else:
  split_amount = split_emi.fixed_amount

customer_upfront_payment = split_amount
emi_principal = txn_amount - split_amount
monthly_emi = EMI(emi_principal, r, n)
```

---

## 4. Supported Issuer Types

| Issuer Type | Code | Description | Auth Method |
|---|---|---|---|
| Credit Card | `CC` | Standard credit card EMI | Card-present (chip/swipe) or CNP (online) |
| Debit Card | `DC` | Debit card with credit limit | OTP + Pre-auth hold |
| NBFC | `NBFC` | Non-Banking Financial Company | Full KYC + loan origination |
| NTB (New-to-Bank) | `NTB` | New customer with no prior relationship | Digital KYC + instant approval |
| Cardless | `CARDLESS` | Mobile number based (no physical card) | OTP-based authentication |
| UPI | `UPI` | UPI VPA based EMI | UPI mandate + autopay |

---

## 5. Integration Points (External Systems)

### 5.1 Banks/Issuers
| Bank | Integration | Capabilities |
|------|------------|--------------|
| HDFC Bank | Direct API | CC EMI, DC EMI, Cardless EMI |
| ICICI Bank | Direct API (AES encrypted) | CC EMI, DC EMI, Cardless EMI |
| SBI | Via acquirer | CC EMI, DC EMI |
| Axis Bank | Direct API | CC EMI, DC EMI |
| Kotak | Direct API | CC EMI, DC EMI, Cardless |

### 5.2 NBFCs
| Partner | Integration | Products |
|---------|------------|----------|
| Bajaj Finance | REST API | Consumer EMI, Flexi loan |
| HDB Financial | REST + JWT/JWE | Personal loan EMI |
| Home Credit | REST API | Consumer durable loan |
| LiquiLoans | REST API | Digital personal loan |
| TVS Credit | REST API | Two-wheeler, consumer EMI |

### 5.3 BNPL Providers
| Provider | Integration | Features |
|----------|------------|----------|
| ICICI Cardless | REST + AES encryption | Pre-eligibility, OTP, confirmation |
| LazyPay | REST API | Eligibility, onboarding, order, refund |
| ePayLater | Via gateway | Credit line, instant approval |

### 5.4 OEMs (Device Manufacturers)
| OEM | Integration | Purpose |
|-----|------------|---------|
| Apple | REST API | IMEI blocking, product validation, serial verification |
| Samsung | REST API | IMEI blocking |
| OnePlus | REST API | Product validation |

### 5.5 Payment Infrastructure
| System | Integration | Purpose |
|--------|------------|---------|
| Acquirers (First Data, etc.) | REST | Payment authorization, settlement |
| NXT Payment Order Service | REST + Kafka | Order lifecycle sync |
| OMS | REST + Kafka | Settlement instruction delivery |
| Customer Vault (NXT) | REST | Card tokenization |
| BIN Service | REST | Card issuer identification |
| Identity Service (Keycloak) | OAuth2 | Authentication & authorization |

---

## 6. Offer Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OFFER CONFIGURATION HIERARCHY                      │
│                                                                      │
│  Level 1: CAMPAIGN (top-level grouping)                             │
│  ├── Name, Budget cap, Date range                                    │
│  │                                                                   │
│  └── Level 2: OFFER (specific promotional offer)                    │
│      ├── Program type (BANK_EMI / BRAND_EMI / SPLIT_EMI)           │
│      ├── State (DRAFT → APPROVED → LIVE)                            │
│      ├── Date range, Hours, Days bitmap                              │
│      │                                                               │
│      └── Level 3: OFFER PARAMETERS (per-tenure configuration)       │
│          ├── Tenure(s): 3, 6, 9, 12, 18, 24 months                 │
│          ├── Amount bounds: min_amount ↔ max_amount                  │
│          ├── Subvention config (type, total amount/%)                │
│          │   └── Multi-party breakup (merchant/brand/issuer/dealer)  │
│          ├── Discount config (type, amount/%)                        │
│          │   └── Multi-party breakup (merchant/brand/issuer/dealer)  │
│          ├── Split EMI config (amount/%, min/max)                    │
│          ├── Down payment amount                                     │
│          └── Advance EMI flag                                        │
│                                                                      │
│  ASSOCIATIONS (linking offers to entities):                          │
│  ├── Client ↔ Offer (via client_issuer_offer_association)           │
│  ├── Product ↔ Offer (via product_offer_association)                │
│  ├── BIN Group ↔ Offer (via bin_group_issuer_offer + ROI override)  │
│  └── Velocity Rule ↔ Offer (via offer_velocity_rule_config_map)     │
│                                                                      │
│  BUDGET ENFORCEMENT:                                                 │
│  ├── Per-campaign budget (threshold_amount)                          │
│  ├── Per-sponsor budget (brand/merchant/issuer separate)             │
│  └── Health monitoring: HEALTHY (<50%) | MODERATE (50-80%) | CRITICAL│
│                                                                      │
│  VELOCITY ENFORCEMENT:                                               │
│  ├── Per card hash: max N discount txns per frequency                │
│  ├── Per mobile: max N subvention txns per frequency                 │
│  └── Combined cap across all types                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Deployment Environments

| Environment | Purpose | Key Differences |
|---|---|---|
| `dev` | Development/testing | Local Redis, single DB instance |
| `uat` | User acceptance testing | Shared Redis cluster, read replicas |
| `mig` | Migration testing | Schema migration validation |
| `saasUat` | SaaS tenant UAT | Multi-tenant isolation testing |
| `prod` | Production | HA Redis cluster, multi-AZ RDS, full monitoring |
| `prod.dr` | Disaster recovery | Cross-region failover |

---

## 8. Non-Functional Requirements Met

| Requirement | Implementation | Target |
|---|---|---|
| **Availability** | Multi-AZ EKS, read replicas, circuit breakers | 99.95% |
| **Latency (Discovery)** | Multi-layer cache, async parallel, GZIP | P95 < 200ms (cache hit) |
| **Latency (Transaction)** | Pipeline tasks, connection pooling | P95 < 500ms |
| **Throughput** | Horizontal scaling (K8s HPA), read replicas | 500+ TPS |
| **Data Consistency** | Idempotency keys, distributed locks, event sourcing | Exactly-once semantics |
| **Security** | HSM encryption, JWT auth, AES payloads, no PAN storage | PCI-DSS compliant |
| **Observability** | Prometheus metrics, structured logging, @LogTime | Full request tracing |
| **Scalability** | Stateless services, Redis cache, Kafka async | Linear horizontal scaling |
| **Disaster Recovery** | Multi-AZ, cross-region DR, Kafka replication | RPO < 5min, RTO < 30min |
