# Shopping Cart Service - System Design

## 1. Functional Requirements

### Core Features
- **Add/Remove/Update Items**: CRUD operations on cart line items with quantity management
- **Persistent Cart (Logged-in)**: Cart survives sessions, accessible from any device
- **Session Cart (Guest)**: Anonymous cart tied to browser session/cookie
- **Cart Merge on Login**: Merge guest cart into user's persistent cart on authentication
- **Price/Availability Validation**: Real-time price and stock checks on cart view
- **Saved for Later**: Move items from cart to wishlist-like "save for later" list
- **Cart Abandonment Recovery**: Track abandoned carts, trigger recovery emails/notifications
- **Multi-Currency**: Display and calculate prices in user's local currency
- **Promotional Pricing/Coupons**: Apply discount codes, automatic promotions, stacking rules

### User Flows
1. **Guest adds item** → Session cart created → Cookie stored → Item added
2. **Guest logs in** → Merge session cart into persistent cart → Conflict resolution
3. **Apply coupon** → Validate code → Check eligibility → Calculate discount → Update total
4. **Checkout** → Validate all items → Hold inventory → Calculate final total → Redirect to payment

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Add to Cart Latency (P99) | < 100ms |
| Cart Read Latency (P99) | < 50ms |
| Cart Write QPS | 200K |
| Cart Read QPS | 500K |
| Availability | 99.99% |
| Data Durability | 99.999% (no lost carts) |
| Session Cart TTL | 30 days |
| Max Items per Cart | 100 |
| Concurrent Cart Updates | Handle without data loss |
| Recovery Email Timing | Within 1 hour of abandonment |

## 3. Capacity Estimation

### Storage
- **Active Carts**: 50M active carts × 2KB avg = 100 GB (fits in Redis)
- **Persistent Carts (DB)**: 500M users × 2KB = 1 TB
- **Session Carts**: 200M sessions × 1KB = 200 GB
- **Cart History (analytics)**: 1B events/day × 500B = 500 GB/day = 180 TB/year
- **Saved for Later**: 200M lists × 1KB = 200 GB

### Compute
- **Cart Service Instances**: 700K QPS / 10K per instance = 70 instances
- **Redis Cluster**: 300 GB data, 700K ops/sec → 20 nodes (64GB each)
- **Event Processing**: 1B events/day = ~12K events/sec → 10 Flink task managers

### Bandwidth
- **Inbound**: 200K writes/sec × 1KB = 200 MB/s
- **Outbound**: 500K reads/sec × 2KB = 1 GB/s
- **Event Stream**: 12K events/sec × 500B = 6 MB/s

## 4. Data Modeling

### Cart Schema (DynamoDB - Primary Store)
```
Table: carts
Partition Key: cart_id (UUID)
Sort Key: -

{
    "cart_id": "cart_uuid_001",
    "user_id": "usr_abc123",          // NULL for guest carts
    "session_id": "sess_xyz789",      // Always present
    "status": "ACTIVE",               // ACTIVE, MERGED, CONVERTED, ABANDONED
    "currency": "USD",
    "items": [...],                    // Denormalized for single-read access
    "item_count": 3,
    "subtotal": 299.97,
    "applied_coupons": ["SAVE10"],
    "discount_total": 29.99,
    "created_at": "2024-01-10T10:00:00Z",
    "updated_at": "2024-01-14T15:30:00Z",
    "last_activity_at": "2024-01-14T15:30:00Z",
    "ttl": 1707868200                 // DynamoDB TTL for session carts (30 days)
}
```

### Cart Items Schema (Redis Hash for hot path)
```
Key: cart:{cart_id}
Type: Hash

Fields:
  meta:user_id → "usr_abc123"
  meta:currency → "USD"
  meta:updated_at → "1705245000"
  meta:version → "15"
  item:{item_id}:product_id → "prod_001"
  item:{item_id}:variant_id → "var_001"
  item:{item_id}:quantity → "2"
  item:{item_id}:unit_price → "99.99"
  item:{item_id}:added_at → "1705240000"
  item:{item_id}:seller_id → "seller_001"
  coupon:SAVE10 → '{"type":"PERCENTAGE","value":10,"applied_at":"..."}'
```

### Cart Relational Schema (PostgreSQL - Durable Store)
```sql
CREATE TABLE carts (
    cart_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(user_id),
    session_id          VARCHAR(64) NOT NULL,
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    currency            VARCHAR(3) NOT NULL DEFAULT 'USD',
    
    -- Computed totals (denormalized)
    item_count          INTEGER DEFAULT 0,
    subtotal            DECIMAL(12,2) DEFAULT 0,
    discount_total      DECIMAL(12,2) DEFAULT 0,
    tax_total           DECIMAL(12,2) DEFAULT 0,
    
    -- Cart-level metadata
    shipping_address_id UUID,
    notes               TEXT,
    
    -- Tracking
    version             INTEGER DEFAULT 1,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    last_activity_at    TIMESTAMP DEFAULT NOW(),
    abandoned_at        TIMESTAMP, -- Set when no activity for X hours
    converted_at        TIMESTAMP, -- Set when checkout completes
    
    CONSTRAINT ck_cart_status CHECK (status IN ('ACTIVE','MERGED','CONVERTED','ABANDONED','EXPIRED'))
);

CREATE INDEX idx_carts_user ON carts(user_id, status) WHERE user_id IS NOT NULL;
CREATE INDEX idx_carts_session ON carts(session_id, status);
CREATE INDEX idx_carts_abandoned ON carts(last_activity_at, status) WHERE status = 'ACTIVE';
CREATE INDEX idx_carts_updated ON carts(updated_at);

CREATE TABLE cart_items (
    item_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id             UUID NOT NULL REFERENCES carts(cart_id) ON DELETE CASCADE,
    product_id          UUID NOT NULL,
    variant_id          UUID,
    seller_id           UUID NOT NULL,
    
    quantity            INTEGER NOT NULL CHECK(quantity > 0 AND quantity <= 99),
    
    -- Price snapshot at time of add (for stale detection)
    unit_price_at_add   DECIMAL(12,2) NOT NULL,
    currency_at_add     VARCHAR(3) NOT NULL,
    
    -- Current validated price
    current_unit_price  DECIMAL(12,2),
    price_changed       BOOLEAN DEFAULT FALSE,
    
    -- Item metadata
    gift_wrap           BOOLEAN DEFAULT FALSE,
    gift_message        TEXT,
    
    added_at            TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(cart_id, product_id, variant_id, seller_id)
);

CREATE INDEX idx_cart_items_cart ON cart_items(cart_id);
CREATE INDEX idx_cart_items_product ON cart_items(product_id);

CREATE TABLE cart_coupons (
    cart_id             UUID NOT NULL REFERENCES carts(cart_id) ON DELETE CASCADE,
    coupon_code         VARCHAR(50) NOT NULL,
    discount_type       VARCHAR(20) NOT NULL, -- PERCENTAGE, FIXED_AMOUNT, FREE_SHIPPING
    discount_value      DECIMAL(12,2) NOT NULL,
    applied_discount    DECIMAL(12,2) NOT NULL, -- actual savings
    min_order_value     DECIMAL(12,2),
    max_discount        DECIMAL(12,2),
    applied_at          TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (cart_id, coupon_code)
);

CREATE TABLE saved_for_later (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    product_id          UUID NOT NULL,
    variant_id          UUID,
    seller_id           UUID,
    price_at_save       DECIMAL(12,2),
    saved_at            TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, product_id, variant_id)
);

CREATE INDEX idx_saved_user ON saved_for_later(user_id, saved_at DESC);
```

### Cart Events Schema (Kafka + Flink)
```sql
-- Event store for cart analytics
CREATE TABLE cart_events (
    event_id            UUID PRIMARY KEY,
    cart_id             UUID NOT NULL,
    user_id             UUID,
    session_id          VARCHAR(64) NOT NULL,
    
    event_type          VARCHAR(50) NOT NULL,
    -- ITEM_ADDED, ITEM_REMOVED, ITEM_QUANTITY_CHANGED,
    -- COUPON_APPLIED, COUPON_REMOVED, CART_VIEWED,
    -- CART_MERGED, CART_ABANDONED, CHECKOUT_STARTED, CART_CONVERTED
    
    event_data          JSONB NOT NULL,
    -- {"product_id": "...", "quantity": 2, "price": 99.99}
    
    device_type         VARCHAR(20), -- MOBILE, DESKTOP, TABLET
    geo_country         VARCHAR(2),
    
    created_at          TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partition per day for efficient retention
CREATE TABLE cart_events_20240114 PARTITION OF cart_events
    FOR VALUES FROM ('2024-01-14') TO ('2024-01-15');
```

## 5. High-Level Design (HLD)

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                           │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐                                       │
│  │  Web App │  │Mobile App│  │  PWA      │                                       │
│  │ (React)  │  │ (Native) │  │           │                                       │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘                                       │
│       │  Local cart state (optimistic UI)  │                                       │
└───────┼──────────────┼──────────────┼──────────────────────────────────────────────┘
        │              │              │
┌───────┼──────────────┼──────────────┼──────────────────────────────────────────────┐
│       ▼              ▼              ▼            API LAYER                          │
│  ┌─────────────────────────────────────────────────────────┐                       │
│  │         API Gateway (Auth + Rate Limiting)              │                       │
│  └────────────────────────────┬────────────────────────────┘                       │
│                               │                                                     │
│  ┌────────────────────────────▼────────────────────────────┐                       │
│  │              Cart BFF (Backend for Frontend)             │                       │
│  │  - Cart enrichment (product names, images, prices)      │                       │
│  │  - Response formatting per client type                   │                       │
│  └────────────────────────────┬────────────────────────────┘                       │
└───────────────────────────────┼────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼────────────────────────────────────────────────────┐
│                               ▼         SERVICE LAYER                               │
│                                                                                     │
│  ┌──────────────────────────────────────────┐   ┌──────────────────────────────┐   │
│  │           Cart Core Service              │   │    Pricing Service           │   │
│  │  - Add/Remove/Update items               │   │    - Real-time pricing       │   │
│  │  - Optimistic locking (version)          │   │    - Coupon validation       │   │
│  │  - Cart merge logic                      │   │    - Multi-currency          │   │
│  │  - Inventory pre-check                   │   │    - Tax calculation         │   │
│  └──────────┬───────────────────────────────┘   └──────────────┬───────────────┘   │
│             │                                                    │                   │
│  ┌──────────▼──────────────────────────────────────────────────▼───────────────┐   │
│  │                    Cart Validation Service                                   │   │
│  │  - Price freshness check (stale price detection)                            │   │
│  │  - Stock availability verification                                           │   │
│  │  - Seller status check                                                       │   │
│  │  - Coupon eligibility re-validation                                          │   │
│  └──────────┬──────────────────────────────────────────────────────────────────┘   │
│             │                                                                       │
│  ┌──────────▼───────────────────┐   ┌──────────────────────────────────────────┐   │
│  │ Cart Abandonment Service     │   │ Cart Event Publisher                     │   │
│  │ - Detect idle carts          │   │ - Emit events for all cart mutations     │   │
│  │ - Schedule recovery emails   │   │ - Feed analytics pipeline               │   │
│  │ - A/B test recovery offers   │   │ - Trigger ML predictions                │   │
│  └──────────────────────────────┘   └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────────────┐
│                               ▼         DATA LAYER                                   │
│                                                                                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │ Redis Cluster │  │  DynamoDB     │  │  PostgreSQL   │  │  Kafka              │  │
│  │ (Hot carts +  │  │ (Persistent   │  │ (Analytics +  │  │ (Cart events +      │  │
│  │  sessions)    │  │  cart store)  │  │  reporting)   │  │  abandonment)       │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └─────────────────────┘  │
│                                                                                      │
│  ┌───────────────┐  ┌───────────────┐                                               │
│  │ Apache Flink  │  │ ElastiCache   │                                               │
│  │ (Abandonment  │  │ (Session      │                                               │
│  │  detection)   │  │  storage)     │                                               │
│  └───────────────┘  └───────────────┘                                               │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Add Item to Cart
```
POST /api/v1/cart/items
Headers: 
  Authorization: Bearer <token>  (optional for guest)
  X-Session-Id: sess_xyz789
  X-Currency: USD

Request:
{
    "product_id": "prod_001",
    "variant_id": "var_001",
    "seller_id": "seller_001",
    "quantity": 2,
    "metadata": {
        "gift_wrap": false,
        "source": "PDP"  // where user added from (for analytics)
    }
}

Response (200 OK):
{
    "cart_id": "cart_uuid_001",
    "item": {
        "item_id": "item_uuid_001",
        "product_id": "prod_001",
        "variant_id": "var_001",
        "title": "Sony WH-1000XM5 - Black",
        "image_url": "https://cdn.example.com/prod_001/thumb.jpg",
        "quantity": 2,
        "unit_price": 278.00,
        "line_total": 556.00,
        "in_stock": true,
        "delivery_estimate": "Jan 16-18"
    },
    "cart_summary": {
        "item_count": 5,
        "subtotal": 856.00,
        "discount": 0,
        "estimated_tax": 68.48,
        "estimated_total": 924.48
    },
    "version": 16,
    "notifications": []  // price changes, low stock warnings
}

Error Response (409 Conflict):
{
    "error": "CART_VERSION_CONFLICT",
    "message": "Cart was modified. Please retry.",
    "current_version": 17,
    "your_version": 15
}
```

### Get Cart
```
GET /api/v1/cart
Headers:
  Authorization: Bearer <token>
  X-Session-Id: sess_xyz789

Response (200 OK):
{
    "cart_id": "cart_uuid_001",
    "status": "ACTIVE",
    "currency": "USD",
    "items": [
        {
            "item_id": "item_001",
            "product_id": "prod_001",
            "variant_id": "var_001",
            "seller_id": "seller_001",
            "title": "Sony WH-1000XM5 Wireless Headphones - Black",
            "image_url": "https://cdn.example.com/...",
            "quantity": 2,
            "unit_price": 278.00,
            "original_price": 399.99,
            "line_total": 556.00,
            "in_stock": true,
            "available_quantity": 50,
            "delivery_estimate": "Jan 16-18",
            "price_alert": null,
            "seller_name": "Amazon.com",
            "fulfillment": "FBA"
        },
        {
            "item_id": "item_002",
            "product_id": "prod_045",
            "variant_id": null,
            "seller_id": "seller_003",
            "title": "USB-C Charging Cable 6ft",
            "image_url": "https://cdn.example.com/...",
            "quantity": 1,
            "unit_price": 12.99,
            "original_price": 12.99,
            "line_total": 12.99,
            "in_stock": true,
            "available_quantity": 1200,
            "delivery_estimate": "Jan 15",
            "price_alert": {
                "type": "PRICE_DROP",
                "message": "Price dropped $2 since you added this",
                "previous_price": 14.99
            },
            "seller_name": "TechAccessories",
            "fulfillment": "FBM"
        }
    ],
    "applied_coupons": [
        {
            "code": "NEWYEAR10",
            "description": "10% off electronics",
            "discount_amount": 55.60,
            "eligible_items": ["item_001"]
        }
    ],
    "summary": {
        "item_count": 3,
        "subtotal": 568.99,
        "discount_total": 55.60,
        "shipping": 0.00,
        "estimated_tax": 41.07,
        "estimated_total": 554.46,
        "savings_total": 177.59
    },
    "saved_for_later": [
        {
            "product_id": "prod_078",
            "title": "Kindle Paperwhite",
            "price": 139.99,
            "in_stock": true,
            "saved_at": "2024-01-10T08:00:00Z"
        }
    ],
    "recommendations": [...],
    "version": 16,
    "last_updated": "2024-01-14T15:30:00Z"
}
```

### Merge Carts on Login
```
POST /api/v1/cart/merge
Headers:
  Authorization: Bearer <token>
  X-Session-Id: sess_xyz789

Request:
{
    "session_cart_id": "cart_guest_001",
    "merge_strategy": "KEEP_HIGHER_QUANTITY"  // KEEP_HIGHER_QUANTITY, KEEP_GUEST, KEEP_PERSISTENT, SUM
}

Response (200 OK):
{
    "merged_cart_id": "cart_uuid_001",
    "merge_result": {
        "items_kept_from_persistent": 2,
        "items_added_from_guest": 3,
        "items_quantity_updated": 1,
        "conflicts_resolved": [
            {
                "product_id": "prod_001",
                "persistent_qty": 1,
                "guest_qty": 2,
                "resolved_qty": 2,
                "strategy_applied": "KEEP_HIGHER_QUANTITY"
            }
        ]
    },
    "cart": {...}  // Full cart response
}
```

### Apply Coupon
```
POST /api/v1/cart/coupons
Request:
{
    "coupon_code": "SAVE20",
    "cart_id": "cart_uuid_001"
}

Response (200 OK):
{
    "applied": true,
    "coupon": {
        "code": "SAVE20",
        "description": "Save $20 on orders over $100",
        "discount_type": "FIXED_AMOUNT",
        "discount_value": 20.00,
        "applied_discount": 20.00,
        "eligible_items": ["item_001", "item_002"],
        "expires_at": "2024-01-31T23:59:59Z"
    },
    "updated_summary": {
        "subtotal": 568.99,
        "discount_total": 75.60,
        "estimated_total": 534.46
    }
}

Error (422):
{
    "error": "COUPON_INVALID",
    "reason": "MIN_ORDER_NOT_MET",
    "message": "This coupon requires a minimum order of $200. Your subtotal is $168.99.",
    "min_order_value": 200.00
}
```

## 7. Deep Dives

### Deep Dive 1: Cart Consistency - Optimistic Locking & Stale Price Detection

**Problem**: Multiple devices/tabs updating same cart simultaneously; prices change between add-to-cart and checkout.

**Optimistic Locking Implementation**:
```python
import redis
import json
from typing import Optional

class CartService:
    def __init__(self):
        self.redis = redis.Redis(cluster=True)
        self.dynamo = boto3.resource('dynamodb')
        self.cart_table = self.dynamo.Table('carts')
    
    def add_item(self, cart_id: str, item: dict, expected_version: int) -> dict:
        """Add item with optimistic concurrency control."""
        
        # Lua script for atomic check-and-update in Redis
        lua_script = """
        local cart_key = KEYS[1]
        local expected_version = tonumber(ARGV[1])
        local item_data = ARGV[2]
        local item_key = ARGV[3]
        
        -- Check version
        local current_version = tonumber(redis.call('HGET', cart_key, 'meta:version') or '0')
        if current_version ~= expected_version then
            return {err = 'VERSION_CONFLICT:' .. current_version}
        end
        
        -- Check max items
        local item_count = tonumber(redis.call('HGET', cart_key, 'meta:item_count') or '0')
        if item_count >= 100 then
            return {err = 'MAX_ITEMS_REACHED'}
        end
        
        -- Add item and increment version atomically
        redis.call('HSET', cart_key, item_key .. ':product_id', cjson.decode(item_data).product_id)
        redis.call('HSET', cart_key, item_key .. ':quantity', cjson.decode(item_data).quantity)
        redis.call('HSET', cart_key, item_key .. ':unit_price', cjson.decode(item_data).unit_price)
        redis.call('HSET', cart_key, item_key .. ':added_at', cjson.decode(item_data).added_at)
        redis.call('HINCRBY', cart_key, 'meta:version', 1)
        redis.call('HINCRBY', cart_key, 'meta:item_count', 1)
        redis.call('HSET', cart_key, 'meta:updated_at', ARGV[4])
        
        -- Set TTL (30 days for session carts)
        redis.call('EXPIRE', cart_key, 2592000)
        
        return redis.call('HGET', cart_key, 'meta:version')
        """
        
        item_id = str(uuid.uuid4())
        item_key = f"item:{item_id}"
        now = str(int(time.time()))
        
        try:
            new_version = self.redis.eval(
                lua_script, 1, f"cart:{cart_id}",
                str(expected_version), json.dumps(item), item_key, now
            )
        except redis.ResponseError as e:
            error_msg = str(e)
            if 'VERSION_CONFLICT' in error_msg:
                current = int(error_msg.split(':')[1])
                raise VersionConflictError(expected_version, current)
            elif 'MAX_ITEMS_REACHED' in error_msg:
                raise MaxItemsError()
            raise
        
        # Async persist to DynamoDB (write-behind)
        self._async_persist(cart_id, item_id, item)
        
        # Publish event
        self._publish_event('ITEM_ADDED', cart_id, {
            'item_id': item_id, **item
        })
        
        return {'item_id': item_id, 'version': int(new_version)}
    
    def validate_cart_prices(self, cart_id: str) -> list:
        """Check all items for stale prices before checkout."""
        cart_data = self._get_cart_from_redis(cart_id)
        items = self._extract_items(cart_data)
        
        # Batch fetch current prices from pricing service
        product_ids = [item['product_id'] for item in items]
        current_prices = self.pricing_service.batch_get_prices(product_ids)
        
        alerts = []
        for item in items:
            current_price = current_prices.get(item['product_id'])
            if current_price is None:
                alerts.append({
                    'item_id': item['item_id'],
                    'type': 'UNAVAILABLE',
                    'message': 'This item is no longer available'
                })
            elif abs(current_price - item['unit_price']) > 0.01:
                alerts.append({
                    'item_id': item['item_id'],
                    'type': 'PRICE_CHANGED',
                    'old_price': item['unit_price'],
                    'new_price': current_price,
                    'direction': 'UP' if current_price > item['unit_price'] else 'DOWN'
                })
                # Auto-update price in cart
                self._update_item_price(cart_id, item['item_id'], current_price)
        
        return alerts
```

**Inventory Hold Strategy**:
```python
class InventoryHoldStrategy:
    """
    Two strategies:
    1. Check-at-checkout: Don't hold inventory when adding to cart. Check at checkout.
       - Pros: Simple, no reservation overhead
       - Cons: "Sorry, item sold out" at checkout = bad UX
    
    2. Soft-hold with TTL: Reserve inventory for 15min during checkout flow.
       - Pros: Better UX during checkout
       - Cons: Can reduce effective inventory for other buyers
    """
    
    def check_at_add_to_cart(self, product_id: str, quantity: int) -> bool:
        """Lightweight stock check - no reservation."""
        available = self.inventory_service.get_available_quantity(product_id)
        return available >= quantity
    
    def soft_hold_at_checkout(self, cart_id: str, items: list) -> dict:
        """Reserve inventory when user initiates checkout. TTL = 15 min."""
        holds = {}
        failed = []
        
        for item in items:
            success = self.inventory_service.create_soft_hold(
                product_id=item['product_id'],
                quantity=item['quantity'],
                hold_id=f"{cart_id}:{item['item_id']}",
                ttl_seconds=900  # 15 minutes
            )
            if success:
                holds[item['item_id']] = True
            else:
                failed.append(item)
                # Rollback previous holds
                for held_item_id in holds:
                    self.inventory_service.release_hold(
                        f"{cart_id}:{held_item_id}"
                    )
                break
        
        if failed:
            return {'success': False, 'unavailable_items': failed}
        return {'success': True, 'hold_expires_at': time.time() + 900}
```

### Deep Dive 2: Distributed Session Management

**Architecture**: Guest carts need to be accessible without authentication, tied to a session identifier.

```python
class SessionCartManager:
    """
    Session management for guest carts:
    - Session ID generated client-side (UUID in cookie)
    - Redis stores session → cart mapping
    - DynamoDB for persistence beyond Redis TTL
    - Fingerprinting for session hijack protection
    """
    
    def __init__(self):
        self.redis = redis.Redis(cluster=True)
        self.session_ttl = 30 * 86400  # 30 days
    
    def get_or_create_session(self, session_id: Optional[str], 
                              fingerprint: dict) -> tuple:
        """Get existing session or create new one."""
        if session_id:
            # Validate session exists and fingerprint matches
            session_data = self.redis.hgetall(f"session:{session_id}")
            if session_data:
                stored_fp = session_data.get(b'fingerprint', b'').decode()
                if self._validate_fingerprint(stored_fp, fingerprint):
                    cart_id = session_data.get(b'cart_id', b'').decode()
                    return session_id, cart_id
                else:
                    # Potential session hijack - create new session
                    pass
        
        # Create new session
        new_session_id = str(uuid.uuid4())
        new_cart_id = str(uuid.uuid4())
        
        self.redis.hset(f"session:{new_session_id}", mapping={
            'cart_id': new_cart_id,
            'fingerprint': self._hash_fingerprint(fingerprint),
            'created_at': str(int(time.time())),
            'device_type': fingerprint.get('device_type', 'unknown')
        })
        self.redis.expire(f"session:{new_session_id}", self.session_ttl)
        
        # Initialize empty cart
        self.redis.hset(f"cart:{new_cart_id}", mapping={
            'meta:session_id': new_session_id,
            'meta:version': '0',
            'meta:item_count': '0',
            'meta:created_at': str(int(time.time()))
        })
        self.redis.expire(f"cart:{new_cart_id}", self.session_ttl)
        
        return new_session_id, new_cart_id
    
    def merge_on_login(self, user_id: str, session_id: str, 
                       strategy: str = 'KEEP_HIGHER_QUANTITY') -> dict:
        """Merge guest session cart into user's persistent cart."""
        
        # Get session cart
        session_data = self.redis.hgetall(f"session:{session_id}")
        guest_cart_id = session_data.get(b'cart_id', b'').decode()
        guest_items = self._get_cart_items(guest_cart_id)
        
        # Get or create persistent cart
        persistent_cart_id = self._get_user_cart(user_id)
        if not persistent_cart_id:
            persistent_cart_id = self._create_persistent_cart(user_id)
        
        persistent_items = self._get_cart_items(persistent_cart_id)
        
        # Merge logic
        merged_items, conflicts = self._merge_items(
            persistent_items, guest_items, strategy
        )
        
        # Atomic update of persistent cart
        pipe = self.redis.pipeline(transaction=True)
        
        # Clear persistent cart items
        for key in self.redis.hscan_iter(f"cart:{persistent_cart_id}", match="item:*"):
            pipe.hdel(f"cart:{persistent_cart_id}", key[0])
        
        # Write merged items
        for item in merged_items:
            item_key = f"item:{item['item_id']}"
            pipe.hset(f"cart:{persistent_cart_id}", f"{item_key}:product_id", item['product_id'])
            pipe.hset(f"cart:{persistent_cart_id}", f"{item_key}:quantity", str(item['quantity']))
            pipe.hset(f"cart:{persistent_cart_id}", f"{item_key}:unit_price", str(item['unit_price']))
        
        # Update metadata
        pipe.hset(f"cart:{persistent_cart_id}", 'meta:item_count', str(len(merged_items)))
        pipe.hincrby(f"cart:{persistent_cart_id}", 'meta:version', 1)
        
        # Mark guest cart as merged
        pipe.hset(f"cart:{guest_cart_id}", 'meta:status', 'MERGED')
        pipe.expire(f"cart:{guest_cart_id}", 86400)  # Keep 1 day for audit
        
        # Link session to persistent cart
        pipe.hset(f"session:{session_id}", 'cart_id', persistent_cart_id)
        pipe.hset(f"session:{session_id}", 'user_id', user_id)
        
        pipe.execute()
        
        return {
            'merged_cart_id': persistent_cart_id,
            'conflicts': conflicts,
            'total_items': len(merged_items)
        }
    
    def _merge_items(self, persistent: list, guest: list, strategy: str) -> tuple:
        """Merge two item lists with conflict resolution."""
        conflicts = []
        merged = {(i['product_id'], i.get('variant_id')): i for i in persistent}
        
        for guest_item in guest:
            key = (guest_item['product_id'], guest_item.get('variant_id'))
            if key in merged:
                existing = merged[key]
                conflict = {
                    'product_id': guest_item['product_id'],
                    'persistent_qty': existing['quantity'],
                    'guest_qty': guest_item['quantity']
                }
                
                if strategy == 'KEEP_HIGHER_QUANTITY':
                    merged[key]['quantity'] = max(existing['quantity'], guest_item['quantity'])
                elif strategy == 'SUM':
                    merged[key]['quantity'] = min(existing['quantity'] + guest_item['quantity'], 99)
                elif strategy == 'KEEP_GUEST':
                    merged[key] = guest_item
                # KEEP_PERSISTENT: do nothing
                
                conflict['resolved_qty'] = merged[key]['quantity']
                conflicts.append(conflict)
            else:
                merged[key] = guest_item
        
        return list(merged.values()), conflicts
```

### Deep Dive 3: Cart Event Streaming for Analytics/ML

**Kafka Topic Configuration**:
```yaml
topic: cart.events
partitions: 64
replication_factor: 3
retention_ms: 604800000  # 7 days
cleanup_policy: delete
compression_type: snappy
min_insync_replicas: 2

# Partition by user_id for ordering guarantee per user
key_serializer: StringSerializer  # user_id or session_id
value_serializer: JsonSerializer
```

**Event Publisher**:
```python
from confluent_kafka import Producer
import json

class CartEventPublisher:
    def __init__(self):
        self.producer = Producer({
            'bootstrap.servers': 'kafka-cluster:9092',
            'acks': 'all',
            'enable.idempotence': True,
            'max.in.flight.requests.per.connection': 5,
            'retries': 10,
            'linger.ms': 5,  # Small batch window for low latency
            'batch.size': 65536,
            'compression.type': 'snappy'
        })
    
    def publish_cart_event(self, event_type: str, cart_id: str, 
                           user_id: str, data: dict):
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'cart_id': cart_id,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        # Partition by user_id for per-user ordering
        key = user_id or data.get('session_id', cart_id)
        
        self.producer.produce(
            topic='cart.events',
            key=key.encode(),
            value=json.dumps(event).encode(),
            callback=self._delivery_callback
        )
        self.producer.poll(0)  # Non-blocking
    
    def _delivery_callback(self, err, msg):
        if err:
            logger.error(f"Cart event delivery failed: {err}")
            # Write to dead letter queue
            self._write_to_dlq(msg)
```

**Flink Abandonment Detection Job**:
```python
# Apache Flink - Cart Abandonment Detection
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.window import TumblingEventTimeWindows
from pyflink.common.time import Time

class CartAbandonmentDetector:
    """
    Detects abandoned carts using event-time session windows.
    A cart is considered abandoned if:
    1. Has items (item_count > 0)
    2. No activity for 1 hour
    3. Not converted to order
    """
    
    ABANDONMENT_THRESHOLD = 3600  # 1 hour
    
    def build_pipeline(self, env: StreamExecutionEnvironment):
        # Read from Kafka
        cart_events = env.from_source(
            KafkaSource.builder()
            .set_topics("cart.events")
            .set_group_id("abandonment-detector")
            .set_starting_offsets(KafkaOffsetsInitializer.latest())
            .build()
        )
        
        # Key by cart_id, use session window with 1hr gap
        abandoned = (
            cart_events
            .key_by(lambda e: e['cart_id'])
            .window(EventTimeSessionWindows.with_gap(Time.hours(1)))
            .process(AbandonmentWindowFunction())
        )
        
        # Filter to only abandoned (no CHECKOUT_STARTED or CART_CONVERTED in window)
        truly_abandoned = abandoned.filter(
            lambda result: result['is_abandoned'] and result['item_count'] > 0
        )
        
        # Sink to abandonment topic for email service
        truly_abandoned.sink_to(
            KafkaSink.builder()
            .set_bootstrap_servers("kafka-cluster:9092")
            .set_record_serializer(JsonSerializer("cart.abandoned"))
            .build()
        )
        
        # Also sink to analytics
        truly_abandoned.sink_to(analytics_sink)

class AbandonmentWindowFunction:
    def process(self, key, context, elements):
        events = list(elements)
        event_types = {e['event_type'] for e in events}
        
        # Not abandoned if checkout happened
        if 'CHECKOUT_STARTED' in event_types or 'CART_CONVERTED' in event_types:
            return
        
        # Get latest cart state
        latest = max(events, key=lambda e: e['timestamp'])
        
        yield {
            'cart_id': key,
            'user_id': latest.get('user_id'),
            'session_id': latest.get('data', {}).get('session_id'),
            'item_count': latest.get('data', {}).get('item_count', 0),
            'cart_value': latest.get('data', {}).get('subtotal', 0),
            'is_abandoned': True,
            'last_activity': latest['timestamp'],
            'abandon_detected_at': datetime.utcnow().isoformat(),
            'items': latest.get('data', {}).get('items', [])
        }
```

**ML Pipeline for Cart Recovery Optimization**:
```python
class CartRecoveryMLPipeline:
    """
    ML model to predict:
    1. Likelihood of recovery (should we send email?)
    2. Optimal timing for recovery email
    3. Best offer to include (discount amount)
    """
    
    def extract_features(self, abandoned_cart: dict) -> dict:
        user_id = abandoned_cart['user_id']
        
        return {
            # Cart features
            'cart_value': abandoned_cart['cart_value'],
            'item_count': abandoned_cart['item_count'],
            'has_deal_items': self._has_deals(abandoned_cart['items']),
            'price_sensitivity': self._avg_discount_seeking(user_id),
            
            # User features
            'previous_purchases': self._get_purchase_count(user_id),
            'previous_abandons': self._get_abandon_count(user_id),
            'previous_recoveries': self._get_recovery_count(user_id),
            'days_since_last_purchase': self._days_since_purchase(user_id),
            'is_prime': self._is_prime(user_id),
            
            # Temporal features
            'hour_of_day': abandoned_cart['hour'],
            'day_of_week': abandoned_cart['day_of_week'],
            'time_since_last_activity_min': abandoned_cart['inactivity_minutes'],
            
            # Product features
            'avg_item_rating': self._avg_rating(abandoned_cart['items']),
            'items_still_in_stock': self._stock_check(abandoned_cart['items']),
        }
    
    def predict_recovery_action(self, features: dict) -> dict:
        recovery_prob = self.model.predict_proba(features)
        
        if recovery_prob < 0.1:
            return {'action': 'SKIP', 'reason': 'Low recovery probability'}
        
        # Determine optimal offer
        if features['cart_value'] > 100 and features['previous_purchases'] > 5:
            offer = {'type': 'FREE_SHIPPING', 'code': 'COMEBACK_SHIP'}
        elif recovery_prob < 0.3:
            offer = {'type': 'PERCENTAGE', 'value': 15, 'code': 'COMEBACK15'}
        else:
            offer = {'type': 'NONE'}  # High-probability recovery, no discount needed
        
        # Determine timing
        if features['hour_of_day'] < 8 or features['hour_of_day'] > 22:
            send_at = 'NEXT_MORNING_9AM'
        else:
            send_at = 'IMMEDIATE'
        
        return {
            'action': 'SEND_RECOVERY',
            'offer': offer,
            'send_at': send_at,
            'channel': 'EMAIL' if features['is_prime'] else 'PUSH',
            'predicted_recovery_rate': recovery_prob
        }
```

## 8. Component Optimization

### Redis Cart Performance
```yaml
# Redis Cluster Configuration
cluster:
  nodes: 20
  memory_per_node: 64GB
  maxmemory_policy: volatile-lru
  
# Connection pooling
pool:
  max_connections: 1000
  min_idle: 50
  connection_timeout_ms: 100
  socket_timeout_ms: 50

# Pipeline batching for cart reads
optimization:
  use_pipeline: true  # Batch HGETALL into single round-trip
  use_lua_scripts: true  # Atomic operations
  compression: false  # Cart data is small, compression overhead not worth it
```

### Write-Behind Persistence
```python
class CartPersistenceWorker:
    """
    Async worker that persists Redis cart state to DynamoDB.
    Uses debouncing: only persist after 5s of no updates (or max 30s).
    """
    
    def __init__(self):
        self.pending_writes = {}  # cart_id → (timestamp, data)
        self.max_delay = 30  # seconds
        self.debounce_delay = 5  # seconds
    
    async def process_cart_update(self, cart_id: str, version: int):
        """Called on every cart mutation."""
        now = time.time()
        
        if cart_id in self.pending_writes:
            first_seen = self.pending_writes[cart_id][0]
            if now - first_seen > self.max_delay:
                # Force flush - been waiting too long
                await self._persist(cart_id)
                return
        
        self.pending_writes[cart_id] = (now, version)
        
        # Schedule debounced write
        await asyncio.sleep(self.debounce_delay)
        
        # Check if this is still the latest
        if self.pending_writes.get(cart_id, (0, 0))[1] == version:
            await self._persist(cart_id)
            del self.pending_writes[cart_id]
    
    async def _persist(self, cart_id: str):
        """Write current Redis state to DynamoDB."""
        cart_data = self.redis.hgetall(f"cart:{cart_id}")
        
        self.dynamo_table.put_item(
            Item=self._redis_to_dynamo(cart_id, cart_data),
            ConditionExpression='attribute_not_exists(version) OR version < :v',
            ExpressionAttributeValues={':v': int(cart_data.get(b'meta:version', 0))}
        )
```

### Cart Read Optimization
```python
class CartReadOptimizer:
    """Optimize cart reads with product data enrichment."""
    
    async def get_enriched_cart(self, cart_id: str) -> dict:
        """Single optimized read path."""
        
        # 1. Get cart from Redis (single HGETALL)
        raw_cart = await self.redis.hgetall(f"cart:{cart_id}")
        items = self._parse_items(raw_cart)
        
        if not items:
            return self._empty_cart_response(cart_id)
        
        # 2. Batch fetch product data (single multi-get from product cache)
        product_ids = [item['product_id'] for item in items]
        products = await self.product_cache.mget(product_ids)
        
        # 3. Batch fetch current prices (single call to pricing service)
        prices = await self.pricing_service.batch_get(product_ids)
        
        # 4. Batch check availability (single call)
        availability = await self.inventory_service.batch_check(product_ids)
        
        # 5. Merge all data
        enriched_items = []
        for item in items:
            pid = item['product_id']
            enriched_items.append({
                **item,
                'title': products[pid]['title'],
                'image_url': products[pid]['image_url'],
                'current_price': prices[pid],
                'in_stock': availability[pid]['available'],
                'available_quantity': availability[pid]['quantity'],
                'price_changed': abs(prices[pid] - item['unit_price']) > 0.01
            })
        
        return self._build_response(cart_id, enriched_items, raw_cart)
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  # Performance
  - name: cart_operation_latency_ms
    type: histogram
    labels: [operation, cache_hit]  # add_item, remove_item, get_cart, merge
    buckets: [5, 10, 25, 50, 100, 250, 500]
  
  - name: cart_redis_operations_total
    type: counter
    labels: [operation, status]
  
  # Business
  - name: cart_items_added_total
    type: counter
    labels: [source, device_type]  # PDP, search, recommendation
  
  - name: cart_abandonment_total
    type: counter
    labels: [cart_value_bucket, item_count_bucket]
  
  - name: cart_recovery_sent_total
    type: counter
    labels: [channel, offer_type]
  
  - name: cart_recovery_converted_total
    type: counter
    labels: [channel, offer_type]
  
  - name: cart_merge_total
    type: counter
    labels: [strategy, conflict_count_bucket]
  
  - name: cart_value_gauge
    type: histogram
    labels: [currency]
    buckets: [10, 25, 50, 100, 200, 500, 1000, 5000]
  
  # Consistency
  - name: cart_version_conflicts_total
    type: counter
    labels: [operation]
  
  - name: cart_stale_price_detections_total
    type: counter
    labels: [direction]  # UP, DOWN
  
  - name: cart_oos_detections_total
    type: counter
    labels: [stage]  # at_add, at_view, at_checkout
  
  # Infrastructure
  - name: redis_cart_memory_bytes
    type: gauge
  
  - name: dynamo_persist_lag_seconds
    type: histogram
    buckets: [1, 5, 10, 30, 60]
```

### Alerting
```yaml
alerts:
  - name: CartAddLatencyHigh
    expr: histogram_quantile(0.99, cart_operation_latency_ms{operation="add_item"}) > 200
    for: 3m
    severity: critical

  - name: CartRedisFailover
    expr: redis_cart_master_changes_total > 0
    for: 0m
    severity: critical
    
  - name: AbandonmentRateSpike
    expr: rate(cart_abandonment_total[1h]) / rate(cart_items_added_total[1h]) > 0.8
    for: 30m
    severity: warning
    
  - name: CartPersistenceLag
    expr: histogram_quantile(0.99, dynamo_persist_lag_seconds) > 60
    for: 5m
    severity: warning
```

## 10. Failure Scenarios & Considerations

### Redis Cluster Node Failure
- **Impact**: Carts on failed shard temporarily unavailable
- **Mitigation**: Redis Cluster auto-failover (< 15s), read from replica during failover
- **Fallback**: Read from DynamoDB if Redis misses (stale by debounce window)

### Cart-Inventory Desync
- **Problem**: Item shows in cart but went OOS between add and checkout
- **Solution**: Validate at 3 points: add (soft check), cart view (informational), checkout (hard block)
- **UX**: Show warning badge on cart icon, "Low stock" labels

### Merge Conflicts at Scale
- **Problem**: User has 50 items in persistent cart, 30 in guest → exceeds 100-item limit
- **Solution**: Priority-based merge (recently added first), push overflow to "Saved for Later"

### DynamoDB Throttling
- **Problem**: Burst writes during peak (flash sale)
- **Mitigation**: Write-behind buffer absorbs spikes, DynamoDB auto-scaling with provisioned burst
- **Fallback**: Redis is source of truth; DynamoDB write retries with exponential backoff

### Multi-Currency Consistency
- **Problem**: Exchange rates change between add-to-cart and checkout
- **Solution**: Store price in seller's currency + user's currency at time of add; recalculate on cart view with latest rate; show difference if significant (>1%)

## 11. Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| Hot Cart Store | Redis Cluster | Sub-ms reads, atomic Lua scripts |
| Persistent Store | DynamoDB | Serverless, auto-scaling, TTL support |
| Analytics DB | PostgreSQL (TimescaleDB) | Time-series cart events |
| Event Bus | Apache Kafka | Durable event stream for analytics |
| Stream Processing | Apache Flink | Session windows for abandonment |
| Session Store | Redis | TTL-based expiry, fast lookup |
| Cart BFF | Node.js | High concurrency for I/O-bound enrichment |
| Cart Core | Go | Performance-critical cart mutations |
| ML Pipeline | SageMaker | Recovery prediction model serving |
| Monitoring | Prometheus + Grafana | Real-time operational metrics |
