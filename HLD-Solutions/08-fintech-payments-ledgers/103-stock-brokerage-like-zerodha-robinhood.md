# Stock Brokerage System (Zerodha/Robinhood)

## 1. Functional Requirements

### Core Features
- **Market Data Streaming**: Real-time quotes (LTP, bid/ask, depth), tick-by-tick for subscribed instruments
- **Order Placement**: Market, Limit, Stop-Loss, Stop-Loss Market, Bracket, Cover orders
- **Order Routing**: Smart order routing to multiple exchanges (NSE/BSE, NYSE/NASDAQ)
- **Portfolio/Holdings**: Current holdings, average cost, P&L, day's change
- **P&L Tracking**: Real-time unrealized P&L, realized P&L, day's P&L
- **Margin Management**: Available margin, used margin, margin requirement per order
- **IPO Applications**: ASBA-based IPO application, status tracking
- **Corporate Actions**: Splits, dividends, bonuses, rights issues, mergers
- **Contract Notes**: Daily trade confirmations, monthly statements
- **Regulatory Compliance**: SEBI/SEC reporting, client fund segregation

### Order Lifecycle
```
Place → Validate → Risk Check → Route → Exchange ACK → Partial Fill → Full Fill
                                                    → Reject
                                         → Cancel → Cancelled
```

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Order placement latency | < 10ms (internal) |
| Market data tick latency | < 5ms from exchange |
| Order throughput | 100K orders/second peak |
| Position update | Real-time (< 100ms) |
| Market data subscribers | 2M concurrent WebSocket |
| Availability (trading hours) | 99.99% |
| Data consistency | Zero discrepancy (funds/securities) |
| Market data throughput | 500K ticks/second |

## 3. Capacity Estimation

### Assumptions
- 10M registered users, 2M active during market hours
- Average 20 orders/active user/day = 40M orders/day
- Trading hours: 6.5 hours = 23,400 seconds
- Average order rate: 40M/23400 ≈ 1700 orders/sec, peak 10x = 17K/sec
- Market data: 5000 instruments × 100 ticks/sec = 500K ticks/sec
- WebSocket connections: 2M concurrent

### Storage
- Order book: 40M/day × 500B = 20GB/day = 7.3TB/year
- Trade executions: 80M/day × 300B = 24GB/day
- Market data (tick): 500K/sec × 100B × 23400sec = 1.1TB/day (time-series)
- Holdings: 10M users × 10 positions × 200B = 20GB
- Total: ~500TB/year (market data dominates)

### Network
- Market data broadcast: 2M users × 10 instruments × 10B/tick × 10 ticks/sec = 2TB/sec (needs fan-out optimization)
- WebSocket: 2M connections × 2KB memory = 4GB RAM for connections alone

## 4. Data Modeling

### Full Database Schemas

```sql
-- Instruments (tradeable securities)
CREATE TABLE instruments (
    instrument_id BIGINT PRIMARY KEY,
    exchange VARCHAR(10) NOT NULL, -- NSE, BSE, NYSE, NASDAQ
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    isin VARCHAR(12),
    instrument_type VARCHAR(20), -- EQ, FUT, OPT, ETF, BOND
    segment VARCHAR(20), -- CASH, FNO, CDS, COMMODITY
    lot_size INT DEFAULT 1,
    tick_size DECIMAL(8, 4) DEFAULT 0.05,
    circuit_limit_upper DECIMAL(12, 2),
    circuit_limit_lower DECIMAL(12, 2),
    expiry_date DATE, -- For derivatives
    strike_price DECIMAL(12, 2), -- For options
    option_type VARCHAR(2), -- CE, PE
    underlying_id BIGINT,
    is_tradeable BOOLEAN DEFAULT TRUE,
    last_price DECIMAL(12, 2),
    open_price DECIMAL(12, 2),
    high_price DECIMAL(12, 2),
    low_price DECIMAL(12, 2),
    close_price DECIMAL(12, 2),
    volume BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(exchange, symbol)
);

CREATE INDEX idx_instruments_symbol ON instruments(symbol);
CREATE INDEX idx_instruments_type ON instruments(instrument_type, segment);

-- Orders
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    instrument_id BIGINT NOT NULL REFERENCES instruments(instrument_id),
    exchange VARCHAR(10) NOT NULL,
    order_type VARCHAR(10) NOT NULL, -- MARKET, LIMIT, SL, SLM
    transaction_type VARCHAR(4) NOT NULL, -- BUY, SELL
    product_type VARCHAR(10) NOT NULL, -- CNC (delivery), MIS (intraday), NRML (F&O)
    quantity INT NOT NULL,
    price DECIMAL(12, 2), -- For LIMIT/SL orders
    trigger_price DECIMAL(12, 2), -- For SL orders
    disclosed_quantity INT DEFAULT 0,
    validity VARCHAR(10) DEFAULT 'DAY', -- DAY, IOC, GTT
    filled_quantity INT DEFAULT 0,
    pending_quantity INT,
    average_price DECIMAL(12, 2) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'PLACED',
    -- PLACED, VALIDATED, SENT, OPEN, PARTIAL_FILL, FILLED, CANCELLED, REJECTED
    status_message TEXT,
    exchange_order_id VARCHAR(50),
    exchange_timestamp TIMESTAMP,
    parent_order_id UUID, -- For bracket/cover orders
    tag VARCHAR(20), -- User-defined tag
    is_amo BOOLEAN DEFAULT FALSE, -- After-market order
    placed_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orders_client ON orders(client_id, placed_at DESC);
CREATE INDEX idx_orders_status ON orders(status, instrument_id);
CREATE INDEX idx_orders_exchange ON orders(exchange_order_id);
PARTITION BY RANGE (placed_at); -- Daily partitions

-- Trades (filled orders / executions)
CREATE TABLE trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(order_id),
    client_id UUID NOT NULL,
    instrument_id BIGINT NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    exchange_trade_id VARCHAR(50),
    transaction_type VARCHAR(4) NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    trade_value DECIMAL(14, 2) NOT NULL,
    brokerage DECIMAL(10, 2) DEFAULT 0,
    stt DECIMAL(10, 2) DEFAULT 0, -- Securities Transaction Tax
    exchange_charges DECIMAL(10, 2) DEFAULT 0,
    gst DECIMAL(10, 2) DEFAULT 0,
    stamp_duty DECIMAL(10, 2) DEFAULT 0,
    total_charges DECIMAL(10, 2) DEFAULT 0,
    net_amount DECIMAL(14, 2) NOT NULL, -- Buy: -(value+charges), Sell: +(value-charges)
    traded_at TIMESTAMP NOT NULL,
    settlement_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_client ON trades(client_id, traded_at DESC);
CREATE INDEX idx_trades_order ON trades(order_id);
CREATE INDEX idx_trades_settlement ON trades(settlement_date, client_id);

-- Positions (intraday + carry-forward)
CREATE TABLE positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    instrument_id BIGINT NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    product_type VARCHAR(10) NOT NULL,
    quantity INT NOT NULL DEFAULT 0, -- Net quantity (positive=long, negative=short)
    buy_quantity INT DEFAULT 0,
    sell_quantity INT DEFAULT 0,
    buy_value DECIMAL(14, 2) DEFAULT 0,
    sell_value DECIMAL(14, 2) DEFAULT 0,
    average_buy_price DECIMAL(12, 2) DEFAULT 0,
    average_sell_price DECIMAL(12, 2) DEFAULT 0,
    realized_pnl DECIMAL(14, 2) DEFAULT 0,
    unrealized_pnl DECIMAL(14, 2) DEFAULT 0,
    day_buy_quantity INT DEFAULT 0,
    day_sell_quantity INT DEFAULT 0,
    overnight_quantity INT DEFAULT 0, -- Carried from previous day
    last_price DECIMAL(12, 2),
    close_price DECIMAL(12, 2), -- Previous close for day's P&L
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(client_id, instrument_id, product_type)
);

CREATE INDEX idx_positions_client ON positions(client_id) WHERE quantity != 0;

-- Holdings (delivery positions - T+1 settled)
CREATE TABLE holdings (
    holding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    instrument_id BIGINT NOT NULL,
    isin VARCHAR(12),
    quantity INT NOT NULL,
    average_price DECIMAL(12, 2) NOT NULL,
    invested_value DECIMAL(14, 2) NOT NULL,
    pledged_quantity INT DEFAULT 0,
    collateral_quantity INT DEFAULT 0,
    t1_quantity INT DEFAULT 0, -- Bought today, not yet settled
    authorized_quantity INT DEFAULT 0, -- Authorized for selling
    last_price DECIMAL(12, 2),
    current_value DECIMAL(14, 2),
    pnl DECIMAL(14, 2),
    pnl_percentage DECIMAL(8, 4),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(client_id, instrument_id)
);

CREATE INDEX idx_holdings_client ON holdings(client_id);

-- Margin/Funds
CREATE TABLE client_margins (
    client_id UUID PRIMARY KEY,
    available_cash DECIMAL(14, 2) NOT NULL DEFAULT 0,
    used_margin DECIMAL(14, 2) NOT NULL DEFAULT 0,
    available_margin DECIMAL(14, 2) NOT NULL DEFAULT 0,
    collateral_margin DECIMAL(14, 2) DEFAULT 0,
    -- Breakup
    span_margin DECIMAL(14, 2) DEFAULT 0,
    exposure_margin DECIMAL(14, 2) DEFAULT 0,
    option_premium DECIMAL(14, 2) DEFAULT 0,
    -- Intraday
    intraday_payin DECIMAL(14, 2) DEFAULT 0,
    intraday_payout DECIMAL(14, 2) DEFAULT 0,
    -- Limits
    delivery_margin_utilized DECIMAL(14, 2) DEFAULT 0,
    day_pnl DECIMAL(14, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    version BIGINT DEFAULT 0
);

-- Margin requirements per instrument
CREATE TABLE margin_requirements (
    instrument_id BIGINT PRIMARY KEY,
    var_margin DECIMAL(8, 4), -- Value at Risk margin %
    elm_margin DECIMAL(8, 4), -- Extreme Loss Margin %
    span_margin DECIMAL(14, 2), -- For F&O
    exposure_margin DECIMAL(14, 2),
    delivery_margin DECIMAL(8, 4), -- Peak margin for delivery
    total_margin_pct DECIMAL(8, 4),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- GTT (Good Till Triggered) orders
CREATE TABLE gtt_orders (
    gtt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    instrument_id BIGINT NOT NULL,
    trigger_type VARCHAR(20), -- SINGLE, OCO (one-cancels-other)
    trigger_conditions JSONB NOT NULL,
    -- [{price_type: 'LTP', operator: 'GTE', value: 500.00}]
    order_params JSONB NOT NULL,
    -- {transaction_type, quantity, price, order_type}
    status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, TRIGGERED, CANCELLED, EXPIRED
    triggered_at TIMESTAMP,
    result_order_id UUID,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_gtt_active ON gtt_orders(instrument_id, status) WHERE status = 'ACTIVE';
```

## 5. High-Level Design (HLD)

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                          STOCK BROKERAGE SYSTEM                                     │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                                         │
│  │  Mobile  │  │   Web    │  │   API    │  [Clients - 2M concurrent]              │
│  │   App    │  │ Terminal │  │  (Algo)  │                                          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                                          │
│       └──────────────┴──────────────┘                                                │
│                      │                                                               │
│         ┌────────────┼────────────┐                                                 │
│         │ WebSocket  │   REST     │                                                 │
│         │ Gateway    │  Gateway   │                                                 │
│         │(Market Data)│ (Orders)  │                                                 │
│         └─────┬──────┘  └────┬────┘                                                 │
│               │              │                                                       │
│  ┌────────────┼──────────────┼─────────────────────────────────┐                    │
│  │            │              │                                  │                    │
│  │  ┌────────▼──────┐  ┌────▼──────────┐  ┌────────────────┐  │                    │
│  │  │  Market Data  │  │    Order      │  │   Position     │  │                    │
│  │  │  Distributor  │  │   Management  │  │   Service      │  │                    │
│  │  │  (Fan-out)    │  │    System     │  │                │  │                    │
│  │  └───────────────┘  └───────┬───────┘  └────────────────┘  │                    │
│  │                             │                                │                    │
│  │            ┌────────────────┼────────────────┐               │                    │
│  │            │                │                │               │                    │
│  │     ┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼──────┐       │                    │
│  │     │   Risk     │  │   Smart    │  │   Margin    │       │                    │
│  │     │   Engine   │  │   Order    │  │   Engine    │       │                    │
│  │     │            │  │   Router   │  │   (SPAN)    │       │                    │
│  │     └────────────┘  └──────┬─────┘  └─────────────┘       │                    │
│  │                            │                                │                    │
│  └────────────────────────────┼────────────────────────────────┘                    │
│                               │                                                      │
│              ┌────────────────┼────────────────┐                                    │
│              │                │                │                                    │
│       ┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼─────┐                              │
│       │    NSE     │  │    BSE     │  │  NASDAQ    │  [Exchange Connectivity]      │
│       │  (FIX/OUCH)│  │  (BOLT)   │  │  (FIX)    │                              │
│       └──────┬─────┘  └──────┬─────┘  └──────┬─────┘                              │
│              │               │               │                                      │
│              └───────────────┴───────────────┘                                      │
│                              │                                                       │
│              ┌───────────────▼───────────────┐                                      │
│              │   Exchange Response Handler    │                                      │
│              │   (Fills, Rejects, Cancels)    │                                      │
│              └───────────────┬───────────────┘                                      │
│                              │                                                       │
│  ┌─────────────┐  ┌─────────▼──┐  ┌──────────┐  ┌───────────┐  ┌──────────┐     │
│  │  PostgreSQL │  │   Redis    │  │  Kafka   │  │TimescaleDB│  │  Aerospike│     │
│  │  (Orders/   │  │ (Positions │  │ (Events) │  │(Tick Data)│  │ (Sessions)│     │
│  │   Trades)   │  │  +Margins) │  │          │  │           │  │           │     │
│  └─────────────┘  └────────────┘  └──────────┘  └───────────┘  └──────────┘     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Place Order
```http
POST /api/v1/orders
Authorization: Bearer <client_token>

{
  "instrument_id": 256265,
  "exchange": "NSE",
  "transaction_type": "BUY",
  "order_type": "LIMIT",
  "product_type": "CNC",
  "quantity": 100,
  "price": 2450.50,
  "trigger_price": null,
  "validity": "DAY",
  "disclosed_quantity": 0,
  "tag": "algo-momentum-1"
}

Response 200:
{
  "order_id": "ord-uuid-001",
  "status": "SENT",
  "exchange_order_id": "1100000012345",
  "placed_at": "2024-01-15T10:30:00.005Z",
  "message": "Order sent to exchange"
}
```

### WebSocket Market Data
```javascript
// Subscribe
{"action": "subscribe", "instruments": [256265, 260105, 738561]}

// Tick message (binary for efficiency, shown as JSON)
{
  "instrument_id": 256265,
  "ltp": 2451.25,
  "ltq": 50,
  "volume": 12450000,
  "bid": 2451.00, "bid_qty": 500,
  "ask": 2451.50, "ask_qty": 300,
  "open": 2445.00, "high": 2460.00, "low": 2440.50, "close": 2448.00,
  "change": 3.25, "change_pct": 0.13,
  "oi": 5000000,  // Open Interest (for F&O)
  "timestamp": 1705312200005
}

// Market depth (Level 2)
{
  "instrument_id": 256265,
  "depth": {
    "buy": [
      {"price": 2451.00, "quantity": 500, "orders": 12},
      {"price": 2450.95, "quantity": 1200, "orders": 8},
      {"price": 2450.90, "quantity": 800, "orders": 15},
      {"price": 2450.85, "quantity": 2000, "orders": 22},
      {"price": 2450.80, "quantity": 3500, "orders": 45}
    ],
    "sell": [
      {"price": 2451.50, "quantity": 300, "orders": 5},
      {"price": 2451.55, "quantity": 750, "orders": 10},
      {"price": 2451.60, "quantity": 1100, "orders": 18},
      {"price": 2451.65, "quantity": 900, "orders": 12},
      {"price": 2451.70, "quantity": 2200, "orders": 30}
    ]
  }
}
```

### Get Positions
```http
GET /api/v1/positions
Authorization: Bearer <client_token>

Response 200:
{
  "net": [
    {
      "instrument_id": 256265,
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "product_type": "MIS",
      "quantity": 100,
      "average_price": 2450.50,
      "last_price": 2465.00,
      "close_price": 2448.00,
      "pnl": 1450.00,
      "day_pnl": 1700.00,
      "m2m": 1450.00,
      "value": 246500.00,
      "buy_quantity": 100,
      "sell_quantity": 0
    }
  ],
  "day": [...],
  "total_pnl": 3200.00,
  "total_m2m": 3200.00
}
```

## 7. Deep Dives

### Deep Dive 1: Order Management System (OMS)

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time

class OrderState(Enum):
    PLACED = "PLACED"
    VALIDATED = "VALIDATED"
    RISK_CHECKED = "RISK_CHECKED"
    SENT = "SENT"
    OPEN = "OPEN"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

# State machine transitions
VALID_TRANSITIONS = {
    OrderState.PLACED: [OrderState.VALIDATED, OrderState.REJECTED],
    OrderState.VALIDATED: [OrderState.RISK_CHECKED, OrderState.REJECTED],
    OrderState.RISK_CHECKED: [OrderState.SENT, OrderState.REJECTED],
    OrderState.SENT: [OrderState.OPEN, OrderState.FILLED, OrderState.REJECTED],
    OrderState.OPEN: [OrderState.PARTIAL_FILL, OrderState.FILLED, OrderState.CANCELLED],
    OrderState.PARTIAL_FILL: [OrderState.PARTIAL_FILL, OrderState.FILLED, OrderState.CANCELLED],
}

class OrderManagementSystem:
    """Core OMS with order state machine and smart routing."""
    
    async def place_order(self, order_request: dict) -> dict:
        """Full order pipeline: validate → risk → route → exchange."""
        
        start_time = time.monotonic_ns()
        
        # Step 1: Create order record
        order = await self._create_order(order_request)
        
        # Step 2: Validate order parameters
        validation = await self._validate_order(order)
        if not validation.passed:
            await self._transition(order, OrderState.REJECTED, validation.reason)
            return {"status": "REJECTED", "reason": validation.reason}
        await self._transition(order, OrderState.VALIDATED)
        
        # Step 3: Risk check (margin, position limits, circuit limits)
        risk_result = await self.risk_engine.check(order)
        if not risk_result.approved:
            await self._transition(order, OrderState.REJECTED, risk_result.reason)
            return {"status": "REJECTED", "reason": risk_result.reason}
        
        # Block margin
        await self.margin_engine.block_margin(order.client_id, risk_result.required_margin)
        await self._transition(order, OrderState.RISK_CHECKED)
        
        # Step 4: Smart Order Routing
        target_exchange = await self.smart_router.route(order)
        
        # Step 5: Send to exchange
        exchange_ack = await self.exchange_gateway.send_order(order, target_exchange)
        
        if exchange_ack.accepted:
            await self._transition(order, OrderState.SENT)
            order.exchange_order_id = exchange_ack.exchange_order_id
        else:
            await self.margin_engine.release_margin(order.client_id, risk_result.required_margin)
            await self._transition(order, OrderState.REJECTED, exchange_ack.reason)
        
        latency_us = (time.monotonic_ns() - start_time) / 1000
        self.metrics.record_latency('order_placement', latency_us)
        
        return {"order_id": order.order_id, "status": order.status.value}
    
    async def handle_exchange_message(self, message: dict):
        """Process exchange responses: fills, rejects, cancels."""
        
        msg_type = message['type']
        order = await self._find_order(message['exchange_order_id'])
        
        if msg_type == 'FILL' or msg_type == 'PARTIAL_FILL':
            trade = await self._record_trade(order, message)
            
            order.filled_quantity += message['quantity']
            order.average_price = self._calc_avg_price(order, message)
            
            if order.filled_quantity >= order.quantity:
                await self._transition(order, OrderState.FILLED)
                # Release excess margin
                await self.margin_engine.settle_order(order)
            else:
                await self._transition(order, OrderState.PARTIAL_FILL)
            
            # Update position
            await self.position_service.update_on_trade(trade)
            
            # Notify client via WebSocket
            await self.ws_notifier.send(order.client_id, 'order_update', order.to_dict())
    
    async def _validate_order(self, order) -> 'ValidationResult':
        """Validate order parameters."""
        # Check instrument is tradeable
        instrument = await self.instruments.get(order.instrument_id)
        if not instrument.is_tradeable:
            return ValidationResult(False, "Instrument not tradeable")
        
        # Check market hours
        if not self.market_hours.is_open(order.exchange) and not order.is_amo:
            return ValidationResult(False, "Market closed")
        
        # Check circuit limits
        if order.price:
            if order.price > instrument.circuit_limit_upper:
                return ValidationResult(False, "Price exceeds upper circuit limit")
            if order.price < instrument.circuit_limit_lower:
                return ValidationResult(False, "Price below lower circuit limit")
        
        # Check lot size (for F&O)
        if order.quantity % instrument.lot_size != 0:
            return ValidationResult(False, f"Quantity must be multiple of lot size {instrument.lot_size}")
        
        # Check tick size
        if order.price and (order.price * 100) % (instrument.tick_size * 100) != 0:
            return ValidationResult(False, f"Price must be multiple of tick size {instrument.tick_size}")
        
        return ValidationResult(True)

class SmartOrderRouter:
    """Route orders to best exchange based on liquidity and spread."""
    
    async def route(self, order) -> str:
        """Determine best exchange for execution."""
        if order.exchange:  # User specified exchange
            return order.exchange
        
        # Get order book depth from both exchanges
        nse_depth = await self.market_data.get_depth(order.instrument_id, 'NSE')
        bse_depth = await self.market_data.get_depth(order.instrument_id, 'BSE')
        
        if order.transaction_type == 'BUY':
            # Best ask (lowest sell price with sufficient quantity)
            nse_score = self._score_execution(nse_depth.asks, order.quantity)
            bse_score = self._score_execution(bse_depth.asks, order.quantity)
        else:
            nse_score = self._score_execution(nse_depth.bids, order.quantity)
            bse_score = self._score_execution(bse_depth.bids, order.quantity)
        
        return 'NSE' if nse_score >= bse_score else 'BSE'
    
    def _score_execution(self, levels: list, quantity: int) -> float:
        """Score based on available liquidity and price impact."""
        available_qty = sum(l.quantity for l in levels[:3])
        if available_qty == 0:
            return -float('inf')
        
        # Weighted average price for our quantity
        remaining = quantity
        cost = 0
        for level in levels:
            fill_qty = min(remaining, level.quantity)
            cost += fill_qty * level.price
            remaining -= fill_qty
            if remaining <= 0:
                break
        
        if remaining > 0:
            return -float('inf')  # Insufficient liquidity
        
        vwap = cost / quantity
        spread_impact = abs(levels[0].price - vwap) / levels[0].price
        
        return -spread_impact  # Lower impact = better score
```

### Deep Dive 2: Real-Time P&L

```python
class RealTimePnLEngine:
    """Streaming P&L computation: market data × positions."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def on_tick(self, instrument_id: int, ltp: float, close_price: float):
        """Called on every market tick - update P&L for all affected positions."""
        
        # Get all clients holding this instrument (from Redis set)
        clients = await self.redis.smembers(f"position_holders:{instrument_id}")
        
        if not clients:
            return
        
        # Pipeline Redis updates for efficiency
        pipe = self.redis.pipeline()
        
        for client_id in clients:
            position_key = f"position:{client_id}:{instrument_id}"
            position = await self.redis.hgetall(position_key)
            
            if not position:
                continue
            
            qty = int(position['quantity'])
            avg_price = float(position['average_price'])
            
            # Unrealized P&L = (LTP - Avg Price) × Quantity
            unrealized_pnl = (ltp - avg_price) * qty
            
            # Day's P&L = (LTP - Previous Close) × Quantity
            day_pnl = (ltp - close_price) * qty
            
            # M2M (Mark-to-Market) for F&O
            m2m = unrealized_pnl  # Simplified
            
            # Update position in Redis
            pipe.hset(position_key, mapping={
                'last_price': str(ltp),
                'unrealized_pnl': str(round(unrealized_pnl, 2)),
                'day_pnl': str(round(day_pnl, 2)),
                'm2m': str(round(m2m, 2)),
                'current_value': str(round(ltp * abs(qty), 2))
            })
            
            # Update client's total P&L
            pipe.hincrbyfloat(f"client_pnl:{client_id}", 'unrealized', 
                             round(unrealized_pnl - float(position.get('unrealized_pnl', 0)), 2))
        
        await pipe.execute()
    
    async def get_client_pnl(self, client_id: str) -> dict:
        """Get real-time P&L for a client (FIFO/average cost)."""
        
        positions = await self.redis.keys(f"position:{client_id}:*")
        total_unrealized = 0
        total_realized = 0
        total_day_pnl = 0
        
        position_details = []
        for pos_key in positions:
            pos = await self.redis.hgetall(pos_key)
            if int(pos.get('quantity', 0)) == 0:
                continue
            
            unrealized = float(pos.get('unrealized_pnl', 0))
            realized = float(pos.get('realized_pnl', 0))
            day = float(pos.get('day_pnl', 0))
            
            total_unrealized += unrealized
            total_realized += realized
            total_day_pnl += day
            
            position_details.append(pos)
        
        return {
            'unrealized_pnl': round(total_unrealized, 2),
            'realized_pnl': round(total_realized, 2),
            'total_pnl': round(total_unrealized + total_realized, 2),
            'day_pnl': round(total_day_pnl, 2),
            'positions': position_details
        }
```

### Deep Dive 3: Margin Engine

```python
class MarginEngine:
    """SPAN-based margin calculation with real-time utilization tracking."""
    
    async def calculate_margin_required(self, order) -> dict:
        """Calculate margin requirement for an order."""
        
        instrument = await self.instruments.get(order.instrument_id)
        
        if order.product_type == 'CNC':  # Delivery
            # Full value for buy, check holdings for sell
            if order.transaction_type == 'BUY':
                margin = order.quantity * (order.price or instrument.last_price)
                # Apply delivery margin (peak margin rule)
                delivery_pct = await self._get_delivery_margin_pct(instrument)
                margin *= delivery_pct
            else:
                margin = 0  # Selling from holdings
            
            return {'total': margin, 'type': 'DELIVERY', 'var': 0, 'elm': 0}
        
        elif order.product_type == 'MIS':  # Intraday
            # Reduced margin (leverage)
            base_value = order.quantity * (order.price or instrument.last_price)
            var_margin = base_value * float(instrument.var_margin or 0.10)
            elm_margin = base_value * float(instrument.elm_margin or 0.035)
            
            # MIS gets additional leverage (e.g., 5x)
            mis_multiplier = await self._get_mis_multiplier(instrument)
            total = (var_margin + elm_margin) * mis_multiplier
            
            return {'total': total, 'type': 'INTRADAY', 'var': var_margin, 'elm': elm_margin}
        
        elif order.product_type == 'NRML':  # F&O
            # SPAN margin (from exchange)
            span = await self._calculate_span_margin(order, instrument)
            exposure = await self._calculate_exposure_margin(order, instrument)
            
            # Portfolio-level margin (SPAN considers hedges)
            portfolio_benefit = await self._calculate_portfolio_benefit(
                order.client_id, order
            )
            
            total = span + exposure - portfolio_benefit
            return {'total': total, 'type': 'FNO', 'span': span, 'exposure': exposure, 
                    'portfolio_benefit': portfolio_benefit}
    
    async def check_margin_call(self, client_id: str):
        """Check if client's margin utilization triggers a margin call."""
        
        margin = await self.redis.hgetall(f"margin:{client_id}")
        
        available = float(margin.get('available_margin', 0))
        used = float(margin.get('used_margin', 0))
        
        if available <= 0:
            return
        
        utilization = used / (available + used) if (available + used) > 0 else 0
        
        if utilization > 0.90:  # 90% utilization
            # Trigger margin call
            await self.notification_service.send_margin_call(
                client_id=client_id,
                shortfall=used - available * 0.8,
                deadline_minutes=60
            )
            
            # If > 100%, auto-square-off positions
            if utilization > 1.0:
                await self._auto_square_off(client_id, shortfall=used - available)
    
    async def _auto_square_off(self, client_id: str, shortfall: float):
        """Square off positions to recover margin shortfall (most losing first)."""
        
        positions = await self.position_service.get_open_positions(client_id, product_type='MIS')
        
        # Sort by P&L (square off most losing first)
        positions.sort(key=lambda p: p.unrealized_pnl)
        
        recovered = 0
        for position in positions:
            if recovered >= shortfall:
                break
            
            # Place market order to close position
            close_order = {
                'client_id': client_id,
                'instrument_id': position.instrument_id,
                'transaction_type': 'SELL' if position.quantity > 0 else 'BUY',
                'quantity': abs(position.quantity),
                'order_type': 'MARKET',
                'product_type': 'MIS',
                'tag': 'AUTO_SQUARE_OFF'
            }
            
            await self.oms.place_order(close_order)
            recovered += abs(position.unrealized_pnl) + position.margin_used
```

## 8. Component Optimization

### Kafka Configuration
```yaml
# Order events (ultra-low latency)
order.events:
  partitions: 64
  replication-factor: 3
  min.insync.replicas: 2
  acks: all
  linger.ms: 0  # No batching for orders
  batch.size: 1  # Single message
  compression: none  # Speed over size

# Market data ticks
market.ticks:
  partitions: 128  # High parallelism
  replication-factor: 2  # Can tolerate loss (re-fetch from exchange)
  retention.ms: 3600000  # 1 hour
  compression: lz4
  batch.size: 65536
  linger.ms: 1

# Trade executions
trade.executions:
  partitions: 32
  replication-factor: 3
  min.insync.replicas: 2
```

### Redis Configuration
```yaml
redis:
  cluster: 12 nodes (6 master + 6 replica)
  maxmemory: 128GB total
  
  # Positions (hot data, updated on every trade)
  positions:
    key: "position:{client_id}:{instrument_id}"
    type: hash
    ttl: none
    
  # Margins (updated real-time)
  margins:
    key: "margin:{client_id}"
    type: hash
    update: atomic (MULTI/EXEC)
    
  # Position holders per instrument (for P&L fan-out)
  position_holders:
    key: "position_holders:{instrument_id}"
    type: set
    
  # Market data cache (latest tick)
  market:
    key: "tick:{instrument_id}"
    type: hash
    ttl: none
```

### WebSocket Optimization
```yaml
websocket:
  # Fan-out architecture
  tier-1-gateways: 50  # Accept client connections
  tier-2-distributors: 10  # Receive from exchange, fan out to gateways
  
  # Binary protocol (not JSON) for market data
  format: protocol-buffers
  compression: none  # Already minimal
  
  # Connection management
  max-connections-per-node: 50000
  heartbeat-interval: 30s
  idle-timeout: 300s
  
  # Subscription management
  max-instruments-per-client: 100
  batch-tick-interval: 100ms  # Batch ticks for non-professional feeds
```

## 9. Observability

### Metrics
```yaml
metrics:
  - name: order_latency_microseconds
    type: histogram
    labels: [stage, exchange, order_type]
    buckets: [100, 500, 1000, 5000, 10000, 50000]
  
  - name: orders_per_second
    type: gauge
    labels: [exchange, transaction_type]
  
  - name: market_data_latency_us
    type: histogram
    labels: [exchange]
    buckets: [100, 500, 1000, 2000, 5000]
  
  - name: websocket_connections
    type: gauge
    labels: [gateway_node]
  
  - name: margin_utilization_pct
    type: histogram
    labels: [product_type]
    buckets: [0.5, 0.7, 0.8, 0.9, 0.95, 1.0]
  
  - name: order_rejection_rate
    type: gauge
    labels: [reason]

alerts:
  - name: ExchangeConnectivityDown
    expr: exchange_heartbeat_age_seconds > 5
    severity: critical  # Trading halted
    
  - name: OrderLatencySpike  
    expr: histogram_quantile(0.99, order_latency_microseconds) > 50000
    severity: warning
    
  - name: MarginCallsHigh
    expr: rate(margin_calls_total[5m]) > 100
    severity: warning
```

## 10. Failure Modes & Considerations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Exchange connectivity loss | Can't place/cancel orders | Redundant lines (2 co-lo connections), DR site |
| Order stuck in SENT state | Client can't cancel | Timeout → query exchange → reconcile |
| Market data feed gap | Stale prices, wrong P&L | Gap detection → re-request, mark stale |
| Redis failure | Positions unavailable | Multi-AZ, reconstruct from trades |
| Double order execution | Financial loss | Idempotent order IDs at exchange level |

### Regulatory Requirements
- **Margin reporting**: Report peak margin utilization to exchange daily
- **Client fund segregation**: Client money in separate bank accounts
- **Best execution**: Prove orders routed for best price (audit trail)
- **Risk limits**: Position limits per client, per instrument
- **Surveillance**: Report suspicious trading patterns to exchange

## 11. Trade-offs & Alternatives

| Decision | Choice | Alternative | Why |
|----------|--------|-------------|-----|
| Market data transport | Binary WebSocket | REST polling | 1000x less bandwidth, real-time |
| Position store | Redis (in-memory) | PostgreSQL | Sub-ms P&L updates, 500K ticks/sec |
| Order matching | Exchange-side | Internal dark pool | Regulatory compliance, price discovery |
| Exchange protocol | FIX 4.2 / OUCH | Proprietary binary | Industry standard, multi-exchange |
| Time-series (ticks) | TimescaleDB | InfluxDB/QuestDB | SQL compatibility, good compression |
| WebSocket gateway | Custom (Rust/C++) | Socket.IO | Performance for 2M connections |
