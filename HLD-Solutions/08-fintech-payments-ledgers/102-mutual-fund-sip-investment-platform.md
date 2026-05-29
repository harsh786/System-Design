# Mutual Fund SIP Investment Platform

## 1. Functional Requirements

### Core Features
- **Fund Catalog**: NAV history, returns (1Y/3Y/5Y), risk metrics (Sharpe, Sortino, std dev), category filtering
- **SIP Creation**: Amount, frequency (daily/weekly/monthly), start date, step-up percentage
- **SIP Execution**: Auto-debit via mandate (NACH/UPI autopay) + order placement to AMC/RTA
- **Portfolio Tracking**: Holdings with current value, returns (absolute/XIRR), asset allocation
- **Goal-Based Investing**: Map SIPs to goals (retirement, education), track progress
- **Redemption**: Full/partial, SWP (Systematic Withdrawal Plan), instant redemption (liquid funds)
- **Switch/STP**: Switch between funds, Systematic Transfer Plan
- **Tax Harvesting**: LTCG/STCG tracking, tax-loss harvesting suggestions
- **Statements**: Consolidated Account Statement (CAS equivalent), transaction history, capital gains report

### Participants
- **Investor** → Platform → **BSE StAR MF / MFU** → **AMC/RTA (CAMS/KFintech)**
- **Payment**: Investor's bank → NACH mandate → Clearing → AMC collection account

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| SIP execution success rate | > 99.5% |
| Order placement latency | < 2 seconds |
| NAV update freshness | Within 30 min of AMC publication |
| Portfolio value accuracy | Real-time (within current NAV) |
| Platform availability | 99.95% |
| Peak concurrent users | 500K (during market hours) |
| SIP execution window | Complete all SIPs by 1:30 PM (cut-off) |

## 3. Capacity Estimation

### Assumptions
- 10M investors, 30M SIPs active
- Average 5 SIPs per investor
- SIP execution: 30M/month ÷ 30 days = 1M SIPs/day (concentrated on specific dates: 1st, 5th, 10th, 15th)
- Peak: 40% of SIPs on 1st of month = 12M on single day
- Fund catalog: 5000 schemes, 15000 plans (direct/regular × growth/dividend)

### Storage
- Portfolio holdings: 10M investors × 5 funds × 200B = 10GB
- Transaction history: 30M SIPs × 12 months × 300B = 108GB/year
- NAV history: 5000 funds × 365 days × 50B = 91MB/year
- Fund metadata: 5000 × 5KB = 25MB
- Total: ~200GB/year growing

### Compute
- SIP execution on 1st: 12M orders in ~4 hours (before cutoff) = 833 orders/sec
- Portfolio valuation: 500K concurrent × refresh = high read load
- NAV import: 5000 funds × daily = trivial

## 4. Data Modeling

### Full Database Schemas

```sql
-- Fund schemes (master data)
CREATE TABLE fund_schemes (
    scheme_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code VARCHAR(20) NOT NULL UNIQUE, -- AMFI code
    isin VARCHAR(12) UNIQUE,
    scheme_name VARCHAR(300) NOT NULL,
    amc_id UUID NOT NULL REFERENCES amcs(amc_id),
    category VARCHAR(50), -- EQUITY_LARGE_CAP, DEBT_SHORT_TERM, HYBRID_BALANCED, etc.
    sub_category VARCHAR(50),
    scheme_type VARCHAR(20), -- OPEN_ENDED, CLOSE_ENDED, INTERVAL
    plan_type VARCHAR(10), -- DIRECT, REGULAR
    option_type VARCHAR(10), -- GROWTH, IDCW (dividend)
    risk_level VARCHAR(10), -- LOW, MODERATE, HIGH, VERY_HIGH
    benchmark_index VARCHAR(100),
    fund_manager VARCHAR(200),
    expense_ratio DECIMAL(5, 4),
    aum_crores DECIMAL(12, 2),
    min_sip_amount DECIMAL(10, 2) DEFAULT 500,
    min_lumpsum_amount DECIMAL(10, 2) DEFAULT 5000,
    min_redemption_units DECIMAL(10, 4),
    exit_load_rules JSONB, -- [{within_days: 365, load_pct: 1.0}, ...]
    sip_dates_allowed INT[], -- [1, 5, 10, 15, 20, 25]
    lock_in_days INT DEFAULT 0, -- ELSS = 1095
    launch_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_schemes_category ON fund_schemes(category, plan_type, is_active);
CREATE INDEX idx_schemes_amc ON fund_schemes(amc_id);

-- NAV history
CREATE TABLE nav_history (
    nav_id BIGSERIAL PRIMARY KEY,
    scheme_id UUID NOT NULL REFERENCES fund_schemes(scheme_id),
    nav_date DATE NOT NULL,
    nav DECIMAL(12, 4) NOT NULL,
    adjusted_nav DECIMAL(12, 4), -- Post-dividend adjustment
    source VARCHAR(20) DEFAULT 'AMFI', -- AMFI, AMC_DIRECT
    imported_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(scheme_id, nav_date)
);

CREATE INDEX idx_nav_scheme_date ON nav_history(scheme_id, nav_date DESC);

-- Investor accounts
CREATE TABLE investors (
    investor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pan VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(15) NOT NULL,
    kyc_status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, VERIFIED, REJECTED
    kyc_reference VARCHAR(50),
    risk_profile VARCHAR(20), -- CONSERVATIVE, MODERATE, AGGRESSIVE
    tax_status VARCHAR(20) DEFAULT 'INDIVIDUAL', -- INDIVIDUAL, HUF, NRI
    bank_accounts JSONB, -- [{bank, account, ifsc, primary: true}]
    nominee_details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- SIP registrations
CREATE TABLE sips (
    sip_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID NOT NULL REFERENCES investors(investor_id),
    scheme_id UUID NOT NULL REFERENCES fund_schemes(scheme_id),
    folio_number VARCHAR(20),
    mandate_id UUID REFERENCES mandates(mandate_id),
    amount DECIMAL(10, 2) NOT NULL,
    frequency VARCHAR(10) NOT NULL DEFAULT 'MONTHLY', -- DAILY, WEEKLY, MONTHLY, QUARTERLY
    sip_date INT NOT NULL, -- Day of month (1-28)
    start_date DATE NOT NULL,
    end_date DATE, -- NULL = perpetual
    step_up_percentage DECIMAL(5, 2) DEFAULT 0, -- Annual increase %
    step_up_month INT, -- Month when step-up applies (1-12)
    installments_total INT, -- NULL = perpetual
    installments_completed INT DEFAULT 0,
    next_execution_date DATE,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    -- ACTIVE, PAUSED, COMPLETED, CANCELLED, FAILED_MANDATE
    goal_id UUID REFERENCES goals(goal_id),
    external_sip_id VARCHAR(50), -- BSE/MFU registration ID
    registered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sips_investor ON sips(investor_id, status);
CREATE INDEX idx_sips_next_exec ON sips(next_execution_date, status) WHERE status = 'ACTIVE';
CREATE INDEX idx_sips_scheme ON sips(scheme_id);

-- Mandates (auto-debit authorization)
CREATE TABLE mandates (
    mandate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID NOT NULL REFERENCES investors(investor_id),
    mandate_type VARCHAR(10) NOT NULL, -- NACH, UPI_AUTOPAY, NETBANKING
    bank_account_number_enc BYTEA,
    bank_ifsc VARCHAR(11),
    bank_name VARCHAR(100),
    upi_id VARCHAR(50),
    max_amount DECIMAL(10, 2) NOT NULL,
    frequency VARCHAR(10), -- AS_PRESENTED, MONTHLY
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    -- PENDING, APPROVED, ACTIVE, EXPIRED, CANCELLED, REJECTED
    umrn VARCHAR(20), -- Unique Mandate Reference Number
    external_ref VARCHAR(50),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mandates_investor ON mandates(investor_id, status);

-- Orders (buy/sell/switch)
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID NOT NULL,
    scheme_id UUID NOT NULL,
    sip_id UUID REFERENCES sips(sip_id),
    order_type VARCHAR(10) NOT NULL, -- PURCHASE, REDEMPTION, SWITCH_IN, SWITCH_OUT, STP
    amount DECIMAL(12, 2), -- For purchases
    units DECIMAL(12, 4), -- For redemptions
    folio_number VARCHAR(20),
    allotment_nav DECIMAL(12, 4),
    allotment_date DATE,
    allotment_units DECIMAL(12, 4),
    allotment_amount DECIMAL(12, 2),
    stamp_duty DECIMAL(8, 2) DEFAULT 0,
    exit_load DECIMAL(8, 2) DEFAULT 0,
    stt DECIMAL(8, 2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'INITIATED',
    -- INITIATED, PAYMENT_PENDING, PAYMENT_SUCCESS, SUBMITTED_TO_RTA, 
    -- ALLOTTED, REJECTED, CANCELLED
    payment_ref VARCHAR(50),
    bse_order_id VARCHAR(20),
    rta_reference VARCHAR(50),
    rejection_reason TEXT,
    submitted_at TIMESTAMP,
    allotted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orders_investor ON orders(investor_id, created_at DESC);
CREATE INDEX idx_orders_sip ON orders(sip_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status, created_at);
CREATE INDEX idx_orders_allotment ON orders(status, scheme_id) WHERE status = 'SUBMITTED_TO_RTA';

-- Portfolio holdings
CREATE TABLE holdings (
    holding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID NOT NULL,
    scheme_id UUID NOT NULL,
    folio_number VARCHAR(20) NOT NULL,
    units DECIMAL(14, 4) NOT NULL,
    invested_amount DECIMAL(14, 2) NOT NULL,
    current_nav DECIMAL(12, 4),
    current_value DECIMAL(14, 2),
    avg_cost_per_unit DECIMAL(12, 4),
    unrealized_gain DECIMAL(14, 2),
    xirr DECIMAL(8, 4),
    last_updated_at TIMESTAMP,
    UNIQUE(investor_id, scheme_id, folio_number)
);

CREATE INDEX idx_holdings_investor ON holdings(investor_id);

-- Transaction lots (for tax computation - FIFO)
CREATE TABLE transaction_lots (
    lot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    holding_id UUID NOT NULL REFERENCES holdings(holding_id),
    order_id UUID NOT NULL REFERENCES orders(order_id),
    purchase_date DATE NOT NULL,
    purchase_nav DECIMAL(12, 4) NOT NULL,
    original_units DECIMAL(12, 4) NOT NULL,
    remaining_units DECIMAL(12, 4) NOT NULL,
    cost_per_unit DECIMAL(12, 4) NOT NULL,
    is_fully_redeemed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_lots_holding ON transaction_lots(holding_id, purchase_date) WHERE NOT is_fully_redeemed;

-- Goals
CREATE TABLE goals (
    goal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID NOT NULL,
    goal_name VARCHAR(100) NOT NULL,
    target_amount DECIMAL(14, 2) NOT NULL,
    target_date DATE NOT NULL,
    current_amount DECIMAL(14, 2) DEFAULT 0,
    monthly_required DECIMAL(10, 2),
    risk_profile VARCHAR(20),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW()
);

-- SIP execution log
CREATE TABLE sip_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sip_id UUID NOT NULL REFERENCES sips(sip_id),
    execution_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    order_id UUID REFERENCES orders(order_id),
    mandate_debit_status VARCHAR(20),
    debit_reference VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    -- SUCCESS, MANDATE_FAILED, INSUFFICIENT_FUNDS, HOLIDAY_SKIPPED, CUTOFF_MISSED
    failure_reason TEXT,
    retry_count INT DEFAULT 0,
    next_retry_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sip_exec_sip ON sip_executions(sip_id, execution_date DESC);
CREATE INDEX idx_sip_exec_date ON sip_executions(execution_date, status);
```

## 5. High-Level Design (HLD)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         MUTUAL FUND SIP PLATFORM                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌──────────┐  ┌──────────┐                                                      │
│  │  Mobile  │  │   Web    │  [Investor Clients]                                  │
│  │   App    │  │  Portal  │                                                       │
│  └────┬─────┘  └────┬─────┘                                                      │
│       └──────────────┘                                                             │
│              │                                                                     │
│    ┌─────────▼──────────┐                                                         │
│    │    API Gateway     │                                                         │
│    └─────────┬──────────┘                                                         │
│              │                                                                     │
│  ┌───────────┼─────────────────────────────────────────┐                          │
│  │           │                                          │                          │
│  │  ┌────────▼──────┐  ┌──────────┐  ┌─────────────┐  │                          │
│  │  │   Portfolio   │  │   SIP    │  │   Order     │  │                          │
│  │  │   Service     │  │  Service │  │   Service   │  │                          │
│  │  └───────────────┘  └────┬─────┘  └──────┬──────┘  │                          │
│  │                           │               │          │                          │
│  │  ┌───────────────┐  ┌────▼─────┐  ┌──────▼──────┐  │                          │
│  │  │    Fund       │  │   SIP    │  │  Payment    │  │                          │
│  │  │   Catalog     │  │Scheduler │  │  Service    │  │                          │
│  │  └───────────────┘  └────┬─────┘  └──────┬──────┘  │                          │
│  │                           │               │          │                          │
│  └───────────────────────────┼───────────────┼──────────┘                          │
│                              │               │                                     │
│              ┌───────────────▼───────────────▼─────────────┐                      │
│              │            Kafka Event Bus                    │                      │
│              │  [sip.execute] [order.placed] [nav.updated]  │                      │
│              └───────────────┬──────────────────────────────┘                      │
│                              │                                                     │
│       ┌──────────────────────┼──────────────────────┐                             │
│       │                      │                      │                             │
│  ┌────▼────────┐  ┌─────────▼──────┐  ┌───────────▼──────┐                      │
│  │ BSE StAR MF │  │   NACH/UPI     │  │   AMFI NAV       │                      │
│  │ / MFU       │  │   Mandate      │  │   Feed           │                      │
│  │ (Order RTG) │  │   (Payment)    │  │   (Daily Import) │                      │
│  └─────────────┘  └────────────────┘  └──────────────────┘                      │
│                                                                                    │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐                    │
│  │ PostgreSQL  │  │  Redis   │  │TimescaleDB│  │    S3     │                    │
│  │(Orders/SIPs)│  │(NAV Cache│  │(NAV Hist) │  │(Statements)│                   │
│  │             │  │+Sessions)│  │           │  │           │                    │
│  └─────────────┘  └──────────┘  └──────────┘  └───────────┘                    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Create SIP
```http
POST /api/v1/sips
Authorization: Bearer <investor_token>

{
  "scheme_code": "INF123A01234",
  "amount": 5000.00,
  "frequency": "MONTHLY",
  "sip_date": 5,
  "mandate_id": "mandate-uuid-001",
  "start_date": "2024-02-05",
  "step_up_percentage": 10,
  "goal_id": "goal-uuid-retirement"
}

Response 201:
{
  "sip_id": "sip-uuid-001",
  "status": "ACTIVE",
  "scheme_name": "Axis Bluechip Fund - Direct Growth",
  "amount": 5000.00,
  "next_execution_date": "2024-02-05",
  "mandate_status": "ACTIVE",
  "external_sip_id": "BSE-SIP-12345",
  "projected_value_10y": 1158000,
  "message": "SIP registered successfully. First installment on 5-Feb-2024."
}
```

### Get Portfolio
```http
GET /api/v1/portfolio?include_lots=true
Authorization: Bearer <investor_token>

Response 200:
{
  "investor_id": "inv-uuid-001",
  "total_invested": 1250000.00,
  "current_value": 1485000.00,
  "total_returns": 235000.00,
  "overall_xirr": 0.1542,
  "day_change": 3200.00,
  "day_change_pct": 0.22,
  "asset_allocation": {
    "equity": {"value": 1100000, "pct": 74.1},
    "debt": {"value": 300000, "pct": 20.2},
    "hybrid": {"value": 85000, "pct": 5.7}
  },
  "holdings": [
    {
      "scheme_name": "Axis Bluechip Fund - Direct Growth",
      "scheme_code": "INF123A01234",
      "category": "EQUITY_LARGE_CAP",
      "units": 2345.678,
      "avg_nav": 42.35,
      "current_nav": 48.92,
      "invested": 99320.00,
      "current_value": 114755.12,
      "returns_pct": 15.54,
      "xirr": 18.2,
      "day_change": 245.60,
      "lots": [
        {"purchase_date": "2023-01-05", "units": 118.23, "nav": 40.12, "gain_type": "LTCG"},
        {"purchase_date": "2023-02-05", "units": 115.45, "nav": 41.05, "gain_type": "LTCG"}
      ]
    }
  ]
}
```

## 7. Deep Dives

### Deep Dive 1: SIP Execution Pipeline

```
┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌───────────┐
│  Cron   │───▶│ Mandate  │───▶│ Debit   │───▶│  Order   │───▶│Allocation │
│ Trigger │    │  Check   │    │ Execute │    │ Placement│    │(Post-NAV) │
└─────────┘    └──────────┘    └─────────┘    └──────────┘    └───────────┘
```

```python
import asyncio
from datetime import date, time, datetime, timedelta
from decimal import Decimal

class SIPExecutionPipeline:
    """Executes SIPs: trigger → mandate check → debit → order → allocation."""
    
    # Market cutoff: Orders before 3 PM get same-day NAV (equity)
    EQUITY_CUTOFF = time(15, 0)
    # Debt cutoff: 1:30 PM for liquid/overnight, 3 PM for others
    DEBT_CUTOFF = time(13, 30)
    
    async def execute_daily_sips(self, execution_date: date):
        """Main entry: execute all SIPs scheduled for today."""
        
        # Check if market is open (skip holidays/weekends)
        if not await self.market_calendar.is_trading_day(execution_date):
            # Shift to next trading day
            next_day = await self.market_calendar.next_trading_day(execution_date)
            await self._reschedule_sips(execution_date, next_day)
            return
        
        # Fetch all SIPs due today
        sips = await self.db.fetch_all("""
            SELECT s.*, m.mandate_id, m.status as mandate_status, m.umrn,
                   m.max_amount, fs.category
            FROM sips s
            JOIN mandates m ON s.mandate_id = m.mandate_id
            JOIN fund_schemes fs ON s.scheme_id = fs.scheme_id
            WHERE s.next_execution_date = $1
            AND s.status = 'ACTIVE'
            ORDER BY s.amount DESC  -- Process larger SIPs first
        """, execution_date)
        
        # Process in batches (avoid overwhelming payment gateway)
        batch_size = 1000
        for i in range(0, len(sips), batch_size):
            batch = sips[i:i + batch_size]
            await self._process_batch(batch, execution_date)
            await asyncio.sleep(1)  # Rate limiting
    
    async def _process_batch(self, sips: list, execution_date: date):
        """Process a batch of SIPs."""
        
        tasks = []
        for sip in sips:
            # Step 1: Validate mandate
            if sip.mandate_status != 'ACTIVE':
                await self._handle_mandate_inactive(sip)
                continue
            
            if sip.amount > sip.max_amount:
                await self._handle_mandate_limit_exceeded(sip)
                continue
            
            # Step 2: Check step-up
            amount = self._calculate_amount_with_stepup(sip, execution_date)
            
            tasks.append(self._execute_single_sip(sip, amount, execution_date))
        
        # Execute in parallel with concurrency limit
        semaphore = asyncio.Semaphore(100)
        async def limited(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(*[limited(t) for t in tasks], return_exceptions=True)
        
        # Log results
        success = sum(1 for r in results if not isinstance(r, Exception) and r['status'] == 'SUCCESS')
        failed = len(results) - success
        await self.metrics.record('sip_batch_execution', success=success, failed=failed)
    
    async def _execute_single_sip(self, sip, amount: Decimal, execution_date: date) -> dict:
        """Execute single SIP: debit → order placement."""
        
        execution = await self.db.fetch_one("""
            INSERT INTO sip_executions (sip_id, execution_date, amount, status)
            VALUES ($1, $2, $3, 'INITIATED')
            RETURNING execution_id
        """, sip.sip_id, execution_date, amount)
        
        try:
            # Step 3: Initiate debit via mandate
            debit_result = await self.payment_service.debit_mandate(
                umrn=sip.umrn,
                amount=amount,
                reference=f"SIP-{sip.sip_id}-{execution_date}",
                execution_date=execution_date
            )
            
            if debit_result.status != 'SUCCESS':
                await self._handle_debit_failure(execution.execution_id, sip, debit_result)
                return {'status': 'DEBIT_FAILED', 'reason': debit_result.reason}
            
            # Step 4: Place order to BSE/AMC
            order = await self.order_service.place_purchase_order(
                investor_id=sip.investor_id,
                scheme_id=sip.scheme_id,
                amount=amount,
                sip_id=sip.sip_id,
                folio=sip.folio_number,
                payment_ref=debit_result.reference
            )
            
            # Update execution record
            await self.db.execute("""
                UPDATE sip_executions 
                SET status = 'SUCCESS', order_id = $1, mandate_debit_status = 'SUCCESS',
                    debit_reference = $2
                WHERE execution_id = $3
            """, order.order_id, debit_result.reference, execution.execution_id)
            
            # Update SIP metadata
            await self.db.execute("""
                UPDATE sips 
                SET installments_completed = installments_completed + 1,
                    next_execution_date = $1,
                    updated_at = NOW()
                WHERE sip_id = $2
            """, self._calculate_next_date(sip, execution_date), sip.sip_id)
            
            return {'status': 'SUCCESS', 'order_id': order.order_id}
            
        except Exception as e:
            await self.db.execute("""
                UPDATE sip_executions SET status = 'FAILED', failure_reason = $1
                WHERE execution_id = $2
            """, str(e), execution.execution_id)
            raise
    
    def _calculate_amount_with_stepup(self, sip, execution_date: date) -> Decimal:
        """Apply annual step-up to SIP amount."""
        if sip.step_up_percentage <= 0:
            return sip.amount
        
        years_elapsed = (execution_date.year - sip.start_date.year)
        if execution_date.month < sip.step_up_month:
            years_elapsed -= 1
        
        if years_elapsed <= 0:
            return sip.amount
        
        step_up_factor = (1 + sip.step_up_percentage / 100) ** years_elapsed
        return (sip.amount * Decimal(str(step_up_factor))).quantize(Decimal('1'))
    
    def _calculate_next_date(self, sip, current_date: date) -> date:
        """Calculate next SIP execution date."""
        if sip.frequency == 'MONTHLY':
            if current_date.month == 12:
                return date(current_date.year + 1, 1, sip.sip_date)
            return date(current_date.year, current_date.month + 1, sip.sip_date)
        elif sip.frequency == 'WEEKLY':
            return current_date + timedelta(weeks=1)
        elif sip.frequency == 'DAILY':
            return current_date + timedelta(days=1)  # Will be adjusted for holidays
```

### Deep Dive 2: NAV Computation and Unit Allocation

```python
class NAVAllocationService:
    """Handles NAV declaration, cutoff times, and unit allocation."""
    
    async def process_nav_declaration(self, scheme_id: str, nav_date: date, nav: Decimal):
        """When AMC declares NAV, allocate units to all pending orders."""
        
        # Store NAV
        await self.db.execute("""
            INSERT INTO nav_history (scheme_id, nav_date, nav) 
            VALUES ($1, $2, $3)
            ON CONFLICT (scheme_id, nav_date) DO UPDATE SET nav = $3
        """, scheme_id, nav_date, nav)
        
        # Update Redis cache
        await self.redis.hset(f"nav:current", scheme_id, str(nav))
        
        # Find all orders awaiting allocation for this scheme + date
        pending_orders = await self.db.fetch_all("""
            SELECT * FROM orders
            WHERE scheme_id = $1 
            AND status = 'SUBMITTED_TO_RTA'
            AND created_at::date <= $2
            AND order_type = 'PURCHASE'
        """, scheme_id, nav_date)
        
        for order in pending_orders:
            await self._allocate_units(order, nav, nav_date)
    
    async def _allocate_units(self, order, nav: Decimal, nav_date: date):
        """Allocate units to an order based on declared NAV."""
        
        # Calculate stamp duty (0.005% for MF purchases)
        stamp_duty = (order.amount * Decimal('0.00005')).quantize(Decimal('0.01'))
        investable_amount = order.amount - stamp_duty
        
        # Calculate units (up to 4 decimal places)
        units = (investable_amount / nav).quantize(Decimal('0.0001'))
        allotment_amount = (units * nav).quantize(Decimal('0.01'))
        
        async with self.db.transaction() as txn:
            # Update order
            await txn.execute("""
                UPDATE orders 
                SET status = 'ALLOTTED', allotment_nav = $1, allotment_date = $2,
                    allotment_units = $3, allotment_amount = $4, stamp_duty = $5,
                    allotted_at = NOW()
                WHERE order_id = $6
            """, nav, nav_date, units, allotment_amount, stamp_duty, order.order_id)
            
            # Update holdings
            await txn.execute("""
                INSERT INTO holdings (investor_id, scheme_id, folio_number, units, invested_amount, avg_cost_per_unit)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (investor_id, scheme_id, folio_number) 
                DO UPDATE SET 
                    units = holdings.units + $4,
                    invested_amount = holdings.invested_amount + $5,
                    avg_cost_per_unit = (holdings.invested_amount + $5) / (holdings.units + $4),
                    last_updated_at = NOW()
            """, order.investor_id, order.scheme_id, order.folio_number or 'NEW',
                units, investable_amount, nav)
            
            # Create transaction lot (for FIFO tax computation)
            await txn.execute("""
                INSERT INTO transaction_lots (holding_id, order_id, purchase_date, purchase_nav, 
                    original_units, remaining_units, cost_per_unit)
                VALUES (
                    (SELECT holding_id FROM holdings WHERE investor_id = $1 AND scheme_id = $2 LIMIT 1),
                    $3, $4, $5, $6, $6, $7
                )
            """, order.investor_id, order.scheme_id, order.order_id, nav_date, nav, units, nav)
        
        # Emit event for portfolio update
        await self.kafka.produce('order.allotted', {
            'order_id': order.order_id,
            'investor_id': order.investor_id,
            'units': str(units),
            'nav': str(nav)
        })
```

### Deep Dive 3: Portfolio Analytics (XIRR Calculation)

```python
from scipy.optimize import brentq
from datetime import date
from decimal import Decimal
from typing import List, Tuple

class PortfolioAnalytics:
    """XIRR calculation, benchmark comparison, asset allocation drift."""
    
    def calculate_xirr(self, cashflows: List[Tuple[date, float]]) -> float:
        """
        Calculate XIRR (Extended Internal Rate of Return).
        cashflows: List of (date, amount) where negative = investment, positive = redemption/current_value
        """
        if len(cashflows) < 2:
            return 0.0
        
        # Sort by date
        cashflows = sorted(cashflows, key=lambda x: x[0])
        first_date = cashflows[0][0]
        
        def npv(rate):
            """Net Present Value at given rate."""
            total = 0.0
            for cf_date, amount in cashflows:
                years = (cf_date - first_date).days / 365.25
                total += amount / ((1 + rate) ** years)
            return total
        
        try:
            # Use Brent's method to find rate where NPV = 0
            result = brentq(npv, -0.99, 10.0, xtol=1e-6, maxiter=100)
            return round(result * 100, 2)  # Return as percentage
        except (ValueError, RuntimeError):
            # If no solution found, return simple CAGR
            return self._simple_cagr(cashflows)
    
    def _simple_cagr(self, cashflows: List[Tuple[date, float]]) -> float:
        """Fallback: simple CAGR based on total invested vs current value."""
        invested = sum(-cf[1] for cf in cashflows if cf[1] < 0)
        current = sum(cf[1] for cf in cashflows if cf[1] > 0)
        if invested <= 0:
            return 0.0
        years = (cashflows[-1][0] - cashflows[0][0]).days / 365.25
        if years <= 0:
            return 0.0
        return ((current / invested) ** (1 / years) - 1) * 100
    
    async def calculate_portfolio_xirr(self, investor_id: str) -> dict:
        """Calculate XIRR for entire portfolio."""
        
        # Get all transactions
        transactions = await self.db.fetch_all("""
            SELECT o.allotment_date as txn_date, 
                   CASE WHEN o.order_type = 'PURCHASE' THEN -o.allotment_amount
                        ELSE o.allotment_amount END as amount
            FROM orders o
            WHERE o.investor_id = $1 AND o.status = 'ALLOTTED'
            ORDER BY o.allotment_date
        """, investor_id)
        
        # Add current portfolio value as final positive cashflow
        current_value = await self._get_portfolio_value(investor_id)
        
        cashflows = [(t.txn_date, float(t.amount)) for t in transactions]
        cashflows.append((date.today(), float(current_value)))
        
        return {
            'xirr': self.calculate_xirr(cashflows),
            'total_invested': sum(-cf[1] for cf in cashflows if cf[1] < 0),
            'current_value': float(current_value),
            'absolute_return_pct': ((float(current_value) / sum(-cf[1] for cf in cashflows if cf[1] < 0)) - 1) * 100
        }
    
    async def check_asset_allocation_drift(self, investor_id: str, target_allocation: dict) -> dict:
        """Check if portfolio has drifted from target allocation."""
        
        holdings = await self.db.fetch_all("""
            SELECT h.current_value, fs.category
            FROM holdings h
            JOIN fund_schemes fs ON h.scheme_id = fs.scheme_id
            WHERE h.investor_id = $1 AND h.units > 0
        """, investor_id)
        
        total_value = sum(h.current_value for h in holdings)
        if total_value == 0:
            return {'drift': False}
        
        # Calculate current allocation
        current = {}
        for h in holdings:
            asset_class = self._map_category_to_asset_class(h.category)
            current[asset_class] = current.get(asset_class, 0) + float(h.current_value)
        
        current_pct = {k: v / float(total_value) * 100 for k, v in current.items()}
        
        # Calculate drift
        drifts = {}
        needs_rebalance = False
        for asset_class, target_pct in target_allocation.items():
            actual_pct = current_pct.get(asset_class, 0)
            drift = actual_pct - target_pct
            drifts[asset_class] = {'target': target_pct, 'actual': round(actual_pct, 1), 'drift': round(drift, 1)}
            if abs(drift) > 5:  # 5% tolerance band
                needs_rebalance = True
        
        return {
            'needs_rebalance': needs_rebalance,
            'total_value': float(total_value),
            'allocation': drifts
        }
```

## 8. Component Optimization

### Kafka Configuration
```yaml
sip.execute:
  partitions: 32
  replication-factor: 3
  retention.ms: 604800000  # 7 days
  partition-key: investor_id

order.placed:
  partitions: 16
  replication-factor: 3
  
nav.updated:
  partitions: 4  # Low volume (5000 schemes/day)
  replication-factor: 3
  retention.ms: 2592000000  # 30 days
```

### Redis Configuration
```yaml
redis:
  cluster: 6 nodes
  
  # Current NAV (hot data)
  nav-current:
    key: "nav:current"  # Hash: scheme_id → nav
    type: hash
    ttl: none  # Updated on NAV declaration
  
  # Portfolio cache
  portfolio:
    key: "portfolio:{investor_id}"
    ttl: 300  # 5 min (invalidated on order allotment)
  
  # SIP execution lock (prevent double execution)
  sip-lock:
    key: "siplock:{sip_id}:{date}"
    ttl: 86400
    type: string (SET NX)
```

## 9. Observability

### Metrics
```yaml
metrics:
  - name: sip_execution_success_rate
    type: gauge
    labels: [frequency, failure_reason]
    alert_threshold: 0.995  # < 99.5% = alert
  
  - name: sip_execution_latency_seconds
    type: histogram
    labels: [stage]  # mandate_check, debit, order_placement
  
  - name: nav_import_lag_minutes
    type: gauge
    labels: [source]
    alert_threshold: 60
  
  - name: order_allotment_pending_count
    type: gauge
    alert_threshold: 10000  # Orders stuck
  
  - name: portfolio_value_computation_ms
    type: histogram

alerts:
  - name: SIPExecutionFailureSpike
    expr: sip_execution_success_rate < 0.99
    severity: critical
    
  - name: NAVImportDelayed
    expr: nav_import_lag_minutes > 120
    severity: warning
    
  - name: CutoffTimeApproaching
    expr: pending_sips_count > 0 AND hour() >= 14
    severity: critical
```

## 10. Failure Modes & Considerations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Mandate debit fails | SIP missed | Retry next 3 business days, notify investor |
| BSE StAR MF down | Orders can't be placed | Queue orders, submit when available (before cutoff) |
| NAV not declared | Units not allocated | Wait (NAV declared by 11 PM typically), no data loss |
| Market holiday on SIP date | Execution skipped | Auto-shift to next trading day |
| Double execution | Duplicate investment | Idempotency key per SIP+date, distributed lock |

### Regulatory Compliance
- SEBI guidelines: SIP cancellation requires 30-day notice
- Stamp duty: 0.005% on all MF purchases (effective July 2020)
- KYC mandatory before any transaction
- FATCA compliance for NRIs
- Nomination mandatory (SEBI circular 2023)

## 11. Trade-offs & Alternatives

| Decision | Choice | Alternative | Why |
|----------|--------|-------------|-----|
| Order routing | BSE StAR MF | Direct AMC API | Single integration for all AMCs |
| Payment | NACH mandate | UPI Autopay | Higher limits, bulk processing |
| NAV source | AMFI daily file | AMC direct feed | Standardized, all schemes in one feed |
| XIRR calculation | Server-side (scipy) | Client-side (JS) | Accuracy, large portfolios |
| Portfolio storage | Materialized holdings table | Event-sourced (recompute from orders) | Read performance for 500K concurrent |
