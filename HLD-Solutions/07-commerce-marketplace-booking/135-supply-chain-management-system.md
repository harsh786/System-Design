# Supply Chain Management System

## 1. Functional Requirements

| # | Requirement | Details |
|---|-------------|---------|
| FR-1 | Demand Forecasting | Per SKU/location forecasting with seasonal decomposition, promotion effects, external signals |
| FR-2 | Inventory Optimization | Safety stock, reorder points, EOQ calculation, multi-echelon optimization |
| FR-3 | Purchase Order Management | Full PO lifecycle: draft → approved → sent → acknowledged → shipped → received → invoiced |
| FR-4 | Supplier Management | Supplier scoring (quality, delivery, cost), risk assessment, diversification tracking |
| FR-5 | Warehouse Management (WMS) | Slotting optimization, pick path routing, packing station assignment, wave planning |
| FR-6 | Shipment Tracking & Logistics | Multi-carrier integration, real-time tracking, ETA prediction, exception handling |
| FR-7 | Supply Chain Visibility | End-to-end dashboard: supplier → factory → DC → store with real-time status |
| FR-8 | Disruption Detection | Anomaly detection on lead times, quality, and supply signals; automated alerting |
| FR-9 | Returns & Reverse Logistics | Return authorization, inspection, restocking, disposal workflows |
| FR-10 | Demand Sensing | Near-real-time demand signals from POS, web traffic, social media for short-horizon adjustment |

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.99% |
| Forecast Refresh | < 1 hour (batch); < 5 min (demand sensing) |
| Inventory Updates | Real-time (< 1 second propagation) |
| SKU Scale | 10M+ SKUs |
| Warehouse Scale | 1000+ warehouses globally |
| PO Throughput | 100K+ POs/day |
| Shipment Tracking | 50M+ active shipments |
| Decision Latency | < 100ms for replenishment triggers |

## 3. Capacity Estimation

```
Inventory:
  - 10M SKUs × 1000 locations = 10B inventory positions
  - Each position: ~200 bytes → 2 TB
  - Updates: 50M inventory movements/day → 580/sec average, 5K/sec peak

Demand Forecasting:
  - 10M SKUs × 1000 locations × 90 days = 900B forecast points
  - Stored as time-series: 10M active series × 365 days × 50 bytes = 182 TB/year
  - Forecast compute: 10M models refreshed hourly = 2,800 models/sec

Purchase Orders:
  - 100K POs/day × avg 20 line items = 2M line items/day
  - Active POs: 500K → 5 GB
  - Historical: 36M POs/year → 50 GB/year

Shipments:
  - 50M active shipments
  - Location updates: 50M × 4 updates/day = 200M events/day → 2,300/sec
  - Each event: 500 bytes → 100 GB/day

Warehouse Operations:
  - 1000 warehouses × avg 50K picks/day = 50M picks/day → 580/sec
  - Wave planning: 1000 × 24 waves/day = 24K optimizations/day

Total Storage:
  - Hot data: 5 TB (active inventory + forecasts + POs)
  - Warm data: 50 TB (historical)
  - Cold data: 200+ TB (full history)
```

## 4. Data Modeling

### 4.1 Products & Inventory

```sql
CREATE TABLE products (
    sku_id              VARCHAR(50) PRIMARY KEY,
    product_name        VARCHAR(500) NOT NULL,
    category_id         UUID NOT NULL,
    subcategory_id      UUID,
    brand               VARCHAR(200),
    unit_of_measure     VARCHAR(20) NOT NULL,
    weight_kg           DECIMAL(10,3),
    volume_cm3          DECIMAL(12,2),
    shelf_life_days     INTEGER,
    abc_class           CHAR(1),       -- 'A', 'B', 'C' (value classification)
    xyz_class           CHAR(1),       -- 'X', 'Y', 'Z' (variability classification)
    lead_time_days      INTEGER NOT NULL,
    lead_time_stddev    DECIMAL(5,2),
    min_order_qty       INTEGER DEFAULT 1,
    pack_size           INTEGER DEFAULT 1,
    unit_cost           DECIMAL(12,4),
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_products_category ON products(category_id, subcategory_id);
CREATE INDEX idx_products_abc_xyz ON products(abc_class, xyz_class);

CREATE TABLE inventory_positions (
    position_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku_id              VARCHAR(50) NOT NULL REFERENCES products(sku_id),
    location_id         UUID NOT NULL,
    location_type       VARCHAR(20) NOT NULL,  -- 'warehouse', 'dc', 'store', 'in_transit'
    quantity_on_hand    INTEGER NOT NULL DEFAULT 0,
    quantity_allocated  INTEGER NOT NULL DEFAULT 0,
    quantity_available  INTEGER GENERATED ALWAYS AS (quantity_on_hand - quantity_allocated) STORED,
    quantity_on_order   INTEGER NOT NULL DEFAULT 0,
    quantity_in_transit INTEGER NOT NULL DEFAULT 0,
    reorder_point       INTEGER,
    safety_stock        INTEGER,
    max_stock_level     INTEGER,
    last_counted_at     TIMESTAMPTZ,
    last_movement_at    TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(sku_id, location_id)
);

CREATE INDEX idx_inventory_sku ON inventory_positions(sku_id);
CREATE INDEX idx_inventory_location ON inventory_positions(location_id);
CREATE INDEX idx_inventory_reorder ON inventory_positions(sku_id, location_id) 
    WHERE quantity_available <= reorder_point;
CREATE INDEX idx_inventory_low_stock ON inventory_positions(location_id) 
    WHERE quantity_available < safety_stock;

CREATE TABLE inventory_movements (
    movement_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku_id              VARCHAR(50) NOT NULL,
    location_id         UUID NOT NULL,
    movement_type       VARCHAR(30) NOT NULL,  -- 'receipt', 'sale', 'transfer_in', 'transfer_out', 'adjustment', 'return', 'damage'
    quantity            INTEGER NOT NULL,      -- positive = in, negative = out
    reference_type      VARCHAR(30),           -- 'purchase_order', 'sales_order', 'transfer', 'count'
    reference_id        UUID,
    balance_after       INTEGER NOT NULL,
    cost_per_unit       DECIMAL(12,4),
    moved_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by         VARCHAR(100)
);

CREATE INDEX idx_movements_sku_loc ON inventory_movements(sku_id, location_id, moved_at DESC);
CREATE INDEX idx_movements_time ON inventory_movements(moved_at DESC);
CREATE INDEX idx_movements_reference ON inventory_movements(reference_type, reference_id);
```

### 4.2 Purchase Orders & Suppliers

```sql
CREATE TABLE suppliers (
    supplier_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_name       VARCHAR(300) NOT NULL,
    country             VARCHAR(3) NOT NULL,
    lead_time_days      INTEGER NOT NULL,
    lead_time_variability DECIMAL(5,2),
    quality_score       DECIMAL(3,2),  -- 0.00 to 1.00
    delivery_score      DECIMAL(3,2),
    cost_score          DECIMAL(3,2),
    overall_score       DECIMAL(3,2),
    risk_level          VARCHAR(10),   -- 'low', 'medium', 'high', 'critical'
    payment_terms_days  INTEGER DEFAULT 30,
    min_order_value     DECIMAL(12,2),
    status              VARCHAR(20) DEFAULT 'active',
    last_evaluated_at   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE purchase_orders (
    po_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_number           VARCHAR(50) NOT NULL UNIQUE,
    supplier_id         UUID NOT NULL REFERENCES suppliers(supplier_id),
    destination_id      UUID NOT NULL,        -- warehouse/DC
    status              VARCHAR(30) NOT NULL DEFAULT 'draft',
    -- States: draft → approved → sent → acknowledged → partially_shipped → shipped → 
    --         partially_received → received → invoiced → paid → closed
    order_date          DATE,
    expected_delivery   DATE,
    actual_delivery     DATE,
    total_value         DECIMAL(14,2),
    currency            VARCHAR(3) DEFAULT 'USD',
    payment_terms       VARCHAR(50),
    shipping_method     VARCHAR(50),
    priority            VARCHAR(10) DEFAULT 'normal',
    auto_generated      BOOLEAN DEFAULT FALSE,
    created_by          VARCHAR(100),
    approved_by         VARCHAR(100),
    approved_at         TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id, status);
CREATE INDEX idx_po_status ON purchase_orders(status, expected_delivery);
CREATE INDEX idx_po_destination ON purchase_orders(destination_id, status);
CREATE INDEX idx_po_delivery ON purchase_orders(expected_delivery) WHERE status IN ('sent', 'acknowledged', 'shipped');

CREATE TABLE po_line_items (
    line_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_id               UUID NOT NULL REFERENCES purchase_orders(po_id),
    sku_id              VARCHAR(50) NOT NULL,
    quantity_ordered    INTEGER NOT NULL,
    quantity_received   INTEGER DEFAULT 0,
    unit_cost           DECIMAL(12,4) NOT NULL,
    line_total          DECIMAL(14,2) GENERATED ALWAYS AS (quantity_ordered * unit_cost) STORED,
    status              VARCHAR(20) DEFAULT 'pending',
    expected_date       DATE,
    received_date       DATE
);

CREATE INDEX idx_po_lines_po ON po_line_items(po_id);
CREATE INDEX idx_po_lines_sku ON po_line_items(sku_id, status);
```

### 4.3 Demand Forecasts & Warehouse

```sql
CREATE TABLE demand_forecasts (
    forecast_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku_id              VARCHAR(50) NOT NULL,
    location_id         UUID NOT NULL,
    forecast_date       DATE NOT NULL,
    forecast_horizon    VARCHAR(10) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    predicted_demand    DECIMAL(12,2) NOT NULL,
    lower_bound_95      DECIMAL(12,2),
    upper_bound_95      DECIMAL(12,2),
    model_type          VARCHAR(30) NOT NULL,  -- 'arima', 'prophet', 'deepar', 'ensemble'
    confidence          DECIMAL(5,4),
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(sku_id, location_id, forecast_date, forecast_horizon)
);

CREATE INDEX idx_forecast_sku_loc ON demand_forecasts(sku_id, location_id, forecast_date);
CREATE INDEX idx_forecast_date ON demand_forecasts(forecast_date, forecast_horizon);

-- TimescaleDB hypertable for time-series demand data
CREATE TABLE demand_actuals (
    sku_id              VARCHAR(50) NOT NULL,
    location_id         UUID NOT NULL,
    time_bucket         TIMESTAMPTZ NOT NULL,
    quantity_sold       INTEGER NOT NULL,
    revenue             DECIMAL(12,2),
    promotion_active    BOOLEAN DEFAULT FALSE,
    promotion_id        UUID,
    PRIMARY KEY (sku_id, location_id, time_bucket)
);

-- Convert to hypertable (TimescaleDB)
-- SELECT create_hypertable('demand_actuals', 'time_bucket');

CREATE TABLE warehouse_locations (
    wh_location_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warehouse_id        UUID NOT NULL,
    zone                VARCHAR(20) NOT NULL,  -- 'receiving', 'bulk', 'pick', 'pack', 'ship'
    aisle               VARCHAR(10),
    rack                VARCHAR(10),
    shelf               VARCHAR(10),
    bin                 VARCHAR(10),
    location_code       VARCHAR(50) NOT NULL UNIQUE,  -- "A-01-03-02" (aisle-rack-shelf-bin)
    sku_id              VARCHAR(50),
    max_quantity        INTEGER,
    current_quantity    INTEGER DEFAULT 0,
    pick_priority       INTEGER DEFAULT 0,
    slot_type           VARCHAR(20),  -- 'forward_pick', 'reserve', 'overflow'
    last_picked_at      TIMESTAMPTZ,
    velocity_class      CHAR(1)       -- 'A', 'B', 'C' (pick frequency)
);

CREATE INDEX idx_wh_loc_warehouse ON warehouse_locations(warehouse_id, zone);
CREATE INDEX idx_wh_loc_sku ON warehouse_locations(sku_id) WHERE sku_id IS NOT NULL;
CREATE INDEX idx_wh_loc_velocity ON warehouse_locations(warehouse_id, velocity_class);
```

### 4.4 Shipments

```sql
CREATE TABLE shipments (
    shipment_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_number     VARCHAR(100) UNIQUE,
    carrier             VARCHAR(50) NOT NULL,
    service_level       VARCHAR(50),
    origin_id           UUID NOT NULL,
    destination_id      UUID NOT NULL,
    status              VARCHAR(30) NOT NULL DEFAULT 'created',
    -- created → picked_up → in_transit → out_for_delivery → delivered | exception
    estimated_departure TIMESTAMPTZ,
    actual_departure    TIMESTAMPTZ,
    estimated_arrival   TIMESTAMPTZ,
    actual_arrival      TIMESTAMPTZ,
    weight_kg           DECIMAL(10,3),
    dimensions_cm       JSONB,
    reference_type      VARCHAR(20),  -- 'purchase_order', 'transfer', 'customer_order'
    reference_id        UUID,
    last_location       JSONB,        -- {"lat": x, "lon": y, "city": "...", "timestamp": "..."}
    exception_reason    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shipments_tracking ON shipments(tracking_number);
CREATE INDEX idx_shipments_status ON shipments(status, estimated_arrival);
CREATE INDEX idx_shipments_reference ON shipments(reference_type, reference_id);
CREATE INDEX idx_shipments_carrier ON shipments(carrier, status);
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          SUPPLY CHAIN MANAGEMENT SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Planning │  │Operations│  │Warehouse │  │ Supplier │  │Dashboard │               │
│  │  Console │  │  Console │  │  Console │  │  Portal  │  │  / BI    │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │              │              │              │              │                     │
│  ┌────▼──────────────▼──────────────▼──────────────▼──────────────▼─────────────────┐  │
│  │                         API GATEWAY (AuthZ + Rate Limiting)                       │  │
│  └────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────────────┘  │
│       │              │              │              │              │                     │
│  ┌────▼─────┐  ┌─────▼────┐  ┌─────▼────┐  ┌─────▼────┐  ┌─────▼──────┐            │
│  │ Demand   │  │Inventory │  │   PO     │  │   WMS    │  │ Logistics  │            │
│  │Forecaster│  │Optimizer │  │ Service  │  │ Service  │  │  Service   │            │
│  └────┬─────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬──────┘            │
│       │              │              │              │              │                     │
│  ┌────▼─────┐  ┌─────▼────┐  ┌─────▼────┐  ┌─────▼────┐  ┌─────▼──────┐            │
│  │  ML      │  │ Redis    │  │Supplier  │  │  Pick/   │  │  Carrier   │            │
│  │ Platform │  │Inventory │  │  API     │  │Pack/Ship │  │Integration │            │
│  │(Spark/   │  │  Cache   │  │ Gateway  │  │  Engine  │  │  (50+)     │            │
│  │ SageMaker)│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬──────┘            │
│  └────┬─────┘        │              │              │              │                     │
│       │              │              │              │              │                     │
│  ┌────▼──────────────▼──────────────▼──────────────▼──────────────▼─────────────────┐  │
│  │                         KAFKA EVENT STREAMING                                     │  │
│  │  Topics: inventory.movements │ demand.actuals │ po.events │ shipment.tracking    │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│       │              │              │              │              │                     │
│  ┌────▼──────────────▼──────────────▼──────────────▼──────────────▼─────────────────┐  │
│  │                         DATA LAYER                                                │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐     │  │
│  │  │PostgreSQL │  │TimescaleDB│  │   Redis   │  │    S3     │  │Elasticsearch│     │  │
│  │  │(Orders/   │  │(Demand    │  │(Inventory │  │(Documents/│  │(Search/    │     │  │
│  │  │ Suppliers)│  │ Time-Ser) │  │  Cache)   │  │ Reports)  │  │ Analytics) │     │  │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘     │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                     DIGITAL TWIN SIMULATION ENGINE                                │  │
│  │        Discrete Event Simulation │ Monte Carlo │ What-If Scenarios               │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) – APIs

### 6.1 Inventory APIs

```
GET /api/v1/inventory/{sku_id}?location_id={loc}
Response (200):
{
    "sku_id": "SKU-12345",
    "location_id": "wh-uuid-001",
    "location_name": "Chicago DC",
    "quantity_on_hand": 5000,
    "quantity_allocated": 1200,
    "quantity_available": 3800,
    "quantity_on_order": 2000,
    "quantity_in_transit": 500,
    "reorder_point": 2000,
    "safety_stock": 800,
    "days_of_supply": 12.5,
    "last_movement_at": "2024-01-15T14:30:00Z",
    "stock_status": "healthy"  // healthy, low, critical, stockout
}

POST /api/v1/inventory/movements
Request:
{
    "sku_id": "SKU-12345",
    "location_id": "wh-uuid-001",
    "movement_type": "receipt",
    "quantity": 500,
    "reference_type": "purchase_order",
    "reference_id": "po-uuid-789",
    "cost_per_unit": 12.50
}
Response (201):
{
    "movement_id": "mov-uuid-101",
    "balance_after": 5500,
    "recorded_at": "2024-01-15T15:00:00Z",
    "alerts": []  // or ["OVERSTOCK: exceeds max level"]
}
```

### 6.2 Purchase Order APIs

```
POST /api/v1/purchase-orders
Request:
{
    "supplier_id": "sup-uuid-001",
    "destination_id": "wh-uuid-001",
    "priority": "normal",
    "line_items": [
        {"sku_id": "SKU-12345", "quantity": 2000, "unit_cost": 12.50},
        {"sku_id": "SKU-67890", "quantity": 500, "unit_cost": 45.00}
    ],
    "requested_delivery": "2024-02-15",
    "notes": "Auto-generated by replenishment engine"
}
Response (201):
{
    "po_id": "po-uuid-123",
    "po_number": "PO-2024-001234",
    "status": "draft",
    "total_value": 47500.00,
    "expected_delivery": "2024-02-15",
    "supplier_lead_time_days": 14
}

POST /api/v1/purchase-orders/{po_id}/approve
Response (200):
{
    "po_id": "po-uuid-123",
    "status": "approved",
    "approved_at": "2024-01-15T16:00:00Z",
    "next_action": "send_to_supplier"
}
```

### 6.3 Forecast APIs

```
GET /api/v1/forecasts/{sku_id}/{location_id}?horizon=30d
Response (200):
{
    "sku_id": "SKU-12345",
    "location_id": "wh-uuid-001",
    "model_type": "ensemble",
    "generated_at": "2024-01-15T06:00:00Z",
    "forecast": [
        {"date": "2024-01-16", "predicted": 150, "lower_95": 120, "upper_95": 185},
        {"date": "2024-01-17", "predicted": 145, "lower_95": 110, "upper_95": 180},
        // ... 30 days
    ],
    "metrics": {
        "mape": 0.082,
        "bias": -0.01,
        "model_accuracy_30d": 0.91
    },
    "signals": {
        "trend": "stable",
        "seasonality": "weekly_peak_friday",
        "upcoming_promotion": "2024-01-20"
    }
}
```

## 7. Deep Dives

### 7.1 Demand Forecasting

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DEMAND FORECASTING ENGINE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ENSEMBLE APPROACH:                                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                                                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │  │
│  │  │   ARIMA     │  │   Prophet   │  │   DeepAR (LSTM)     │ │  │
│  │  │ Trend +     │  │ Holidays +  │  │ Complex patterns +  │ │  │
│  │  │ Seasonality │  │ Changepoints│  │ Cross-series learn  │ │  │
│  │  │ Weight: 0.3 │  │ Weight: 0.3 │  │ Weight: 0.4         │ │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │  │
│  │         │                │                     │            │  │
│  │  ┌──────▼────────────────▼─────────────────────▼──────────┐ │  │
│  │  │              ENSEMBLE COMBINER                          │ │  │
│  │  │    Weighted average with dynamic weight adjustment      │ │  │
│  │  │    based on recent forecast accuracy per model          │ │  │
│  │  └───────────────────────┬────────────────────────────────┘ │  │
│  │                          │                                   │  │
│  │  ┌───────────────────────▼────────────────────────────────┐ │  │
│  │  │         HIERARCHICAL RECONCILIATION                     │ │  │
│  │  │   SKU forecasts constrained to category/region totals   │ │  │
│  │  │   Bottom-up: sum(SKU) ≤ Category forecast              │ │  │
│  │  │   Top-down:  category total distributed proportionally  │ │  │
│  │  │   Middle-out: reconcile both directions iteratively     │ │  │
│  │  └────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  FEATURE ENGINEERING:                                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  - Promotions calendar (start/end/discount %)               │  │
│  │  - Weather data (temperature, precipitation by location)     │  │
│  │  - Competitor pricing (web scraping signals)                 │  │
│  │  - Social media trends (brand mentions, viral products)      │  │
│  │  - Economic indicators (CPI, unemployment, consumer conf.)  │  │
│  │  - Calendar effects (day-of-week, holidays, events)         │  │
│  │  - Price elasticity (own-price + cross-price effects)       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

```python
class DemandForecaster:
    def __init__(self, spark_session, model_registry):
        self.spark = spark_session
        self.models = model_registry
    
    def generate_forecast(self, sku_id: str, location_id: str, horizon_days: int = 90):
        # Load historical demand
        history = self._load_demand_history(sku_id, location_id, lookback_days=730)
        features = self._engineer_features(sku_id, location_id, horizon_days)
        
        # Run individual models
        arima_forecast = self._run_arima(history, horizon_days)
        prophet_forecast = self._run_prophet(history, features, horizon_days)
        deepar_forecast = self._run_deepar(sku_id, location_id, features, horizon_days)
        
        # Dynamic weight calculation based on recent accuracy
        weights = self._calculate_dynamic_weights(sku_id, location_id)
        
        # Ensemble combination
        ensemble = (
            weights["arima"] * arima_forecast +
            weights["prophet"] * prophet_forecast +
            weights["deepar"] * deepar_forecast
        )
        
        # Hierarchical reconciliation
        reconciled = self._hierarchical_reconcile(sku_id, location_id, ensemble)
        
        # Confidence intervals (quantile regression from DeepAR)
        confidence = self._compute_confidence_intervals(deepar_forecast, reconciled)
        
        return ForecastResult(
            predictions=reconciled,
            lower_95=confidence["p2.5"],
            upper_95=confidence["p97.5"],
            model_weights=weights,
            accuracy_metrics=self._backtest_metrics(sku_id, location_id)
        )
    
    def _run_arima(self, history, horizon):
        """SARIMA: captures trend + seasonality"""
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        model = SARIMAX(history, order=(1,1,1), seasonal_order=(1,1,1,7))
        fitted = model.fit(disp=False)
        return fitted.forecast(steps=horizon)
    
    def _run_prophet(self, history, features, horizon):
        """Prophet: handles holidays, changepoints, regressors"""
        from prophet import Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            changepoint_prior_scale=0.05
        )
        # Add external regressors
        model.add_regressor('promotion_discount')
        model.add_regressor('temperature')
        model.add_regressor('competitor_price_index')
        
        model.fit(history)
        future = model.make_future_dataframe(periods=horizon)
        future = future.merge(features, on='ds', how='left')
        return model.predict(future)['yhat'].values[-horizon:]
    
    def _hierarchical_reconcile(self, sku_id, location_id, sku_forecast):
        """Ensure SKU forecasts sum to category constraints"""
        category = self._get_category(sku_id)
        category_forecast = self._get_category_forecast(category, location_id)
        
        # Get all SKU forecasts in this category
        all_sku_forecasts = self._get_all_sku_forecasts(category, location_id)
        total_bottom_up = sum(all_sku_forecasts.values())
        
        # Proportional reconciliation
        if total_bottom_up > 0:
            scaling_factor = category_forecast / total_bottom_up
            reconciled = sku_forecast * scaling_factor
        else:
            reconciled = sku_forecast
        
        return reconciled
```

### 7.2 Inventory Optimization

```python
class InventoryOptimizer:
    """Multi-echelon inventory optimization"""
    
    # Service level Z-scores
    Z_SCORES = {0.90: 1.28, 0.95: 1.645, 0.97: 1.88, 0.99: 2.33, 0.999: 3.09}
    
    def calculate_safety_stock(self, sku_id: str, location_id: str) -> int:
        """
        Safety Stock = Z × σ_demand × √(lead_time)
        
        With demand AND lead time variability:
        SS = Z × √(LT × σ²_demand + D² × σ²_lead_time)
        """
        params = self._get_parameters(sku_id, location_id)
        
        z = self.Z_SCORES[params.service_level]
        avg_demand = params.avg_daily_demand
        demand_stddev = params.demand_stddev
        lead_time = params.lead_time_days
        lt_stddev = params.lead_time_stddev
        
        # Combined safety stock formula
        ss = z * math.sqrt(
            lead_time * demand_stddev**2 + 
            avg_demand**2 * lt_stddev**2
        )
        
        return math.ceil(ss)
    
    def calculate_reorder_point(self, sku_id: str, location_id: str) -> int:
        """ROP = Avg_Daily_Demand × Lead_Time + Safety_Stock"""
        params = self._get_parameters(sku_id, location_id)
        safety_stock = self.calculate_safety_stock(sku_id, location_id)
        
        rop = params.avg_daily_demand * params.lead_time_days + safety_stock
        return math.ceil(rop)
    
    def calculate_eoq(self, sku_id: str, location_id: str) -> int:
        """
        Economic Order Quantity = √(2 × D × S / H)
        D = annual demand
        S = ordering cost per order
        H = holding cost per unit per year
        """
        params = self._get_parameters(sku_id, location_id)
        
        annual_demand = params.avg_daily_demand * 365
        ordering_cost = params.ordering_cost  # $/order
        holding_cost = params.unit_cost * params.holding_cost_rate  # $/unit/year
        
        eoq = math.sqrt(2 * annual_demand * ordering_cost / holding_cost)
        
        # Round up to pack size
        pack_size = params.pack_size
        eoq_rounded = math.ceil(eoq / pack_size) * pack_size
        
        # Respect MOQ
        return max(eoq_rounded, params.min_order_qty)
    
    def multi_echelon_optimize(self, sku_id: str, network: SupplyNetwork):
        """
        Optimize inventory across: Supplier → DC → Regional Warehouse → Store
        Objective: minimize total cost (holding + ordering + stockout)
        Subject to: service level constraints at each echelon
        """
        echelons = network.get_echelons(sku_id)
        
        # Base stock policy per echelon
        for echelon in reversed(echelons):  # bottom-up
            downstream_demand = self._aggregate_downstream_demand(echelon)
            lead_time = echelon.replenishment_lead_time
            
            # Install base-stock level
            echelon.base_stock = (
                downstream_demand.mean * lead_time +
                self.Z_SCORES[echelon.service_level] * 
                downstream_demand.stddev * math.sqrt(lead_time)
            )
        
        # Iterate to find global optimum (cost minimization)
        total_cost = self._compute_total_cost(echelons)
        
        return OptimizationResult(
            echelon_params=[{
                "location": e.location_id,
                "safety_stock": e.safety_stock,
                "reorder_point": e.reorder_point,
                "order_quantity": e.order_qty,
                "expected_fill_rate": e.fill_rate
            } for e in echelons],
            total_annual_cost=total_cost
        )
    
    def abc_xyz_classify(self, sku_id: str) -> tuple:
        """
        ABC: by revenue contribution (A=80%, B=15%, C=5%)
        XYZ: by demand variability (X: CV<0.5, Y: 0.5-1.0, Z: >1.0)
        
        AX: high value, predictable → lean/JIT
        AZ: high value, unpredictable → higher safety stock
        CX: low value, predictable → automate replenishment
        CZ: low value, unpredictable → consider discontinuing
        """
        revenue_rank = self._get_revenue_percentile(sku_id)
        cv = self._get_demand_cv(sku_id)  # coefficient of variation
        
        abc = 'A' if revenue_rank >= 0.80 else 'B' if revenue_rank >= 0.65 else 'C'
        xyz = 'X' if cv < 0.5 else 'Y' if cv < 1.0 else 'Z'
        
        return abc, xyz
```

### 7.3 Supply Chain Digital Twin

```python
class SupplyChainDigitalTwin:
    """Discrete event simulation of the supply chain network"""
    
    def __init__(self, network_config: NetworkConfig):
        self.network = network_config
        self.rng = np.random.default_rng(seed=42)
    
    def simulate(self, scenario: Scenario, days: int = 365, runs: int = 1000) -> SimulationResult:
        """Monte Carlo simulation with stochastic parameters"""
        results = []
        
        for run in range(runs):
            state = self._initialize_state()
            daily_metrics = []
            
            for day in range(days):
                # Apply scenario disruptions
                disruptions = scenario.get_disruptions(day)
                self._apply_disruptions(state, disruptions)
                
                # Simulate each node
                for node in self.network.nodes:
                    # Generate stochastic demand
                    demand = self._sample_demand(node, day)
                    
                    # Process fulfillment
                    fulfilled, stockout = self._fulfill_demand(state, node, demand)
                    
                    # Check reorder points and generate orders
                    orders = self._check_replenishment(state, node, day)
                    
                    # Process in-transit shipments (stochastic lead time)
                    arrivals = self._process_arrivals(state, node, day)
                    
                    daily_metrics.append({
                        "day": day, "node": node.id,
                        "demand": demand, "fulfilled": fulfilled,
                        "stockout": stockout, "inventory": state.inventory[node.id]
                    })
            
            results.append(self._aggregate_metrics(daily_metrics))
        
        return SimulationResult(
            service_level_distribution=self._compute_distribution(results, "service_level"),
            total_cost_distribution=self._compute_distribution(results, "total_cost"),
            stockout_risk=self._compute_risk(results, "stockout_days"),
            recommendations=self._generate_recommendations(results, scenario)
        )
    
    def what_if_analysis(self, scenarios: list) -> ComparisonReport:
        """Compare multiple scenarios"""
        # Example scenarios:
        # 1. "What if supplier X fails for 30 days?"
        # 2. "What if demand increases 50% for holiday?"
        # 3. "What if we add a new DC in region Y?"
        
        baseline = self.simulate(Scenario.baseline())
        comparisons = []
        
        for scenario in scenarios:
            result = self.simulate(scenario)
            comparison = {
                "scenario": scenario.name,
                "service_level_delta": result.avg_service_level - baseline.avg_service_level,
                "cost_delta": result.avg_total_cost - baseline.avg_total_cost,
                "stockout_risk_delta": result.stockout_risk - baseline.stockout_risk,
                "recommendation": self._recommend(baseline, result, scenario)
            }
            comparisons.append(comparison)
        
        return ComparisonReport(baseline=baseline, scenarios=comparisons)
    
    def _sample_demand(self, node, day):
        """Stochastic demand with seasonality + noise"""
        base = node.avg_daily_demand
        seasonal = base * node.seasonal_factors[day % 365]
        noise = self.rng.normal(0, node.demand_stddev)
        return max(0, int(seasonal + noise))
    
    def _fulfill_demand(self, state, node, demand):
        """FIFO fulfillment from available inventory"""
        available = state.inventory[node.id]
        fulfilled = min(available, demand)
        stockout = demand - fulfilled
        state.inventory[node.id] -= fulfilled
        return fulfilled, stockout
```

## 8. Component Optimization

### Spark Configuration (Batch Forecasting)

```yaml
spark:
  job: demand_forecast_refresh
  schedule: "0 * * * *"  # hourly
  config:
    spark.executor.memory: 16g
    spark.executor.cores: 4
    spark.executor.instances: 50
    spark.sql.shuffle.partitions: 200
    spark.dynamicAllocation.enabled: true
    spark.dynamicAllocation.maxExecutors: 100
  
  # 10M SKU-location combinations / 50 executors = 200K per executor
  # Each forecast: ~100ms → 200K × 100ms = 20,000 sec with 4 cores = 5,000 sec ≈ 83 min
  # Need parallelism optimization to meet <60 min target
  
  optimization:
    - partition_by: [category_id, location_region]  # balanced partitions
    - broadcast_join: feature tables (small)
    - cache: historical demand (reused across models)
```

### Kafka Configuration

```yaml
kafka:
  cluster: 5 brokers
  topics:
    inventory_movements:
      partitions: 64
      replication: 3
      retention: 30d
      key: "sku_id:location_id"
    
    demand_actuals:
      partitions: 32
      replication: 3
      retention: 365d
      # POS transactions aggregated per minute
    
    po_events:
      partitions: 16
      replication: 3
      retention: 90d
    
    shipment_tracking:
      partitions: 32
      replication: 3
      retention: 7d
      # High volume: 200M events/day
    
    replenishment_triggers:
      partitions: 32
      replication: 3
      retention: 7d
      # Real-time: inventory drops below ROP
```

### Redis Configuration

```yaml
redis:
  cluster: true
  nodes: 6 (3 primary + 3 replica)
  memory: 64GB per node
  
  data_patterns:
    # Real-time inventory (hot path)
    inventory:
      key: "inv:{sku_id}:{location_id}"
      type: hash
      fields: [on_hand, allocated, available, on_order, in_transit]
      ttl: none  # always fresh, updated on every movement
    
    # Reorder alerts
    reorder_set:
      key: "reorder:{location_id}"
      type: sorted_set
      score: "available_quantity / reorder_point"  # ratio < 1.0 = needs reorder
    
    # Forecast cache
    forecast:
      key: "forecast:{sku_id}:{location_id}:{date}"
      type: string (JSON)
      ttl: 3600  # refresh hourly
  
  # Memory: 10M SKU-location pairs × 200 bytes = 2 GB for inventory
  # Forecast cache: 1M hot items × 5KB = 5 GB
```

### TimescaleDB Configuration

```yaml
timescaledb:
  hypertables:
    demand_actuals:
      time_column: time_bucket
      chunk_interval: 7 days
      compression:
        enabled: true
        after: 30 days
        segment_by: [sku_id, location_id]
        order_by: time_bucket DESC
      retention:
        drop_after: 3 years
      continuous_aggregates:
        - name: demand_daily
          interval: 1 day
          refresh: 1 hour
        - name: demand_weekly
          interval: 7 days
          refresh: 1 day
```

## 9. Observability

### Metrics

```yaml
metrics:
  forecasting:
    - forecast_mape{sku_class, model_type}
    - forecast_bias{sku_class, model_type}
    - forecast_refresh_latency_ms
    - forecast_model_training_time_sec
    - demand_sensing_lag_ms
  
  inventory:
    - inventory_service_level{location, category}
    - stockout_rate{location, sku_class}
    - inventory_turns{location, category}
    - days_of_supply{location, sku_class}
    - overstock_value_usd{location}
    - fill_rate{location}
  
  purchase_orders:
    - po_lead_time_days{supplier}
    - po_on_time_delivery_rate{supplier}
    - po_value_total{status}
    - supplier_score{supplier}
  
  warehouse:
    - picks_per_hour{warehouse, zone}
    - order_cycle_time_minutes{warehouse}
    - warehouse_utilization_percent{warehouse}
    - mispick_rate{warehouse}
  
  logistics:
    - shipment_on_time_rate{carrier}
    - shipment_damage_rate{carrier}
    - tracking_update_latency_ms{carrier}
    - transportation_cost_per_unit{lane}

alerts:
  - name: CriticalStockout
    condition: inventory_available == 0 AND abc_class == 'A'
    severity: critical
  
  - name: ForecastAccuracyDegraded
    condition: forecast_mape > 0.25
    severity: warning
  
  - name: SupplierDeliveryLate
    condition: days_past_expected_delivery > 7
    severity: warning
  
  - name: WarehouseCapacityCritical
    condition: warehouse_utilization_percent > 95
    severity: critical
```

### Supply Chain Control Tower Dashboard

```
┌──────────────────────────────────────────────────────────────────┐
│  SUPPLY CHAIN CONTROL TOWER                                      │
├──────────────────────────────────────────────────────────────────┤
│  Service Level: 98.7% │ Stockouts: 23 SKUs │ Fill Rate: 99.1%  │
│  Active POs: 12,450 │ In-Transit: 3.2M units │ At-Risk: 47    │
│  Forecast Accuracy (MAPE): 8.2% │ Inventory Turns: 12.4x      │
│  Supplier On-Time: 94.3% │ Avg Lead Time: 12.3 days           │
│  Disruptions Active: 2 (supplier fire, port congestion)         │
└──────────────────────────────────────────────────────────────────┘
```

## 10. Failure Analysis & Considerations

### Failure Scenarios

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Forecast model drift | Over/under ordering | Continuous accuracy monitoring; automatic retraining triggers |
| Supplier failure | Stockout for dependent SKUs | Multi-sourcing strategy; safety stock buffers; digital twin scenario planning |
| Warehouse system outage | Picking/shipping halted | Local cache for active waves; manual fallback procedures |
| Kafka lag on inventory events | Stale inventory reads from Redis | Health check on consumer lag; direct DB fallback |
| Redis cache failure | Increased DB load; slower inventory checks | Read replicas; local application cache |
| Demand spike (viral product) | Stockout, allocation needed | Demand sensing (real-time POS); allocation rules (fair share) |
| Network partition between DCs | Inconsistent inventory views | Eventual consistency with conflict resolution; regional autonomy |

### Considerations

1. **Bullwhip Effect**: Small demand variability amplifies upstream; use demand visibility sharing with suppliers
2. **Seasonality Cold Start**: New products have no history; use analogous product forecasting
3. **Multi-Currency**: PO costs in supplier currency; inventory valued in local currency; FX exposure
4. **Perishability**: FEFO (First Expired First Out) for perishable goods; separate optimization
5. **Batch/Lot Tracking**: Regulatory requirement for food/pharma; track lot through entire chain
6. **Channel Conflict**: Same inventory sold online + retail; allocation policies needed
7. **Returns Impact**: High return rate SKUs need adjusted forecasting and separate inventory pools
8. **Sustainability**: Carbon footprint per shipment; optimize for cost AND emissions (multi-objective)
9. **Global Trade Compliance**: Customs, tariffs, restricted items, trade agreements affect routing
10. **Data Quality**: Bad master data (wrong lead times, costs) cascades through all calculations

## 11. References

- SCOR Model (Supply Chain Operations Reference)
- APICS/ASCM Body of Knowledge
- Silver-Meal & Wagner-Whitin algorithms for lot sizing
- AWS Supply Chain solutions architecture
