# Schema Design - E-Commerce & Marketplace (Problems 51-70)

## Staff Architect Level - Database Schema Design

---

## Problem 51: Design a Multi-Vendor E-Commerce Platform (Like Amazon Marketplace)

**Difficulty:** Expert | **Frequency:** Very High

**Requirements:**
- Multiple sellers can list products
- Products have variants (size, color)
- Inventory tracking per seller per variant
- Shopping cart with price locking
- Order lifecycle management

**Schema:**

```sql
-- Core Entities
CREATE TABLE sellers (
    seller_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    status ENUM('pending', 'active', 'suspended', 'banned') DEFAULT 'pending',
    commission_rate DECIMAL(5,4) DEFAULT 0.15,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_status (status)
);

CREATE TABLE categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    parent_category_id INT REFERENCES categories(category_id),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    level INT NOT NULL DEFAULT 0,
    path VARCHAR(1000),  -- Materialized path: "electronics/phones/smartphones"
    INDEX idx_parent (parent_category_id),
    INDEX idx_path (path)
);

CREATE TABLE products (
    product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES sellers(seller_id),
    category_id INT NOT NULL REFERENCES categories(category_id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    brand VARCHAR(255),
    base_price DECIMAL(10,2) NOT NULL,
    status ENUM('draft', 'active', 'inactive', 'deleted') DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW(),
    INDEX idx_seller (seller_id),
    INDEX idx_category (category_id),
    INDEX idx_status_created (status, created_at DESC),
    FULLTEXT INDEX idx_search (title, description, brand)
);

-- Product Variants (Size, Color combinations)
CREATE TABLE product_variants (
    variant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(product_id),
    sku VARCHAR(100) UNIQUE NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    compare_at_price DECIMAL(10,2),  -- Original price for showing discount
    weight_grams INT,
    attributes JSONB NOT NULL DEFAULT '{}',  -- {"size": "L", "color": "Red"}
    INDEX idx_product (product_id),
    INDEX idx_sku (sku)
);

-- Inventory (per seller, per variant, per warehouse)
CREATE TABLE inventory (
    inventory_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    variant_id UUID NOT NULL REFERENCES product_variants(variant_id),
    warehouse_id INT NOT NULL REFERENCES warehouses(warehouse_id),
    quantity_available INT NOT NULL DEFAULT 0,
    quantity_reserved INT NOT NULL DEFAULT 0,  -- In carts / pending orders
    low_stock_threshold INT DEFAULT 10,
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW(),
    UNIQUE KEY uk_variant_warehouse (variant_id, warehouse_id),
    CHECK (quantity_available >= 0),
    CHECK (quantity_reserved >= 0)
);

-- Shopping Cart
CREATE TABLE cart_items (
    cart_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id UUID NOT NULL,
    variant_id UUID NOT NULL REFERENCES product_variants(variant_id),
    quantity INT NOT NULL DEFAULT 1,
    price_at_addition DECIMAL(10,2) NOT NULL,  -- Lock price at cart time
    added_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- Cart reservation expiry
    UNIQUE KEY uk_user_variant (user_id, variant_id),
    INDEX idx_user (user_id),
    INDEX idx_expires (expires_at)
);

-- Orders
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    order_number VARCHAR(20) UNIQUE NOT NULL,  -- Human-readable: ORD-20240115-XXXX
    status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') DEFAULT 'pending',
    subtotal DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    shipping_address_id UUID NOT NULL,
    billing_address_id UUID NOT NULL,
    payment_method_id UUID,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW(),
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at DESC)
);

CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    variant_id UUID NOT NULL REFERENCES product_variants(variant_id),
    seller_id UUID NOT NULL REFERENCES sellers(seller_id),
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,  -- Price at time of order
    total_price DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded') DEFAULT 'pending',
    INDEX idx_order (order_id),
    INDEX idx_seller (seller_id)
);

-- Order Status History (Event Sourcing pattern)
CREATE TABLE order_status_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    changed_by UUID,  -- User or system
    reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_order_time (order_id, created_at)
);
```

**Key Design Decisions:**
1. **UUID vs Auto-increment:** UUIDs for distributed ID generation (no coordination needed)
2. **Price stored at order time:** Never reference current product price from orders
3. **Inventory reservation:** `quantity_reserved` prevents overselling during checkout
4. **Materialized path for categories:** Enables prefix search for all subcategories
5. **JSONB for variant attributes:** Flexible schema for different product types
6. **Event sourcing for status:** Complete audit trail, supports state machine validation

---

## Problem 52: Design Product Review & Rating System

**Difficulty:** Medium | **Frequency:** Very High

**Requirements:**
- Users rate products 1-5 stars
- Text reviews with photos
- Verified purchase reviews
- Helpful/not helpful votes
- Average rating calculation
- Filter by star rating

```sql
CREATE TABLE reviews (
    review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(product_id),
    user_id UUID NOT NULL,
    order_item_id UUID,  -- NULL = not verified purchase
    rating TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title VARCHAR(255),
    body TEXT,
    is_verified_purchase BOOLEAN GENERATED ALWAYS AS (order_item_id IS NOT NULL) STORED,
    status ENUM('pending', 'approved', 'rejected', 'flagged') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW(),
    UNIQUE KEY uk_user_product (user_id, product_id),  -- One review per user per product
    INDEX idx_product_rating (product_id, rating, created_at DESC),
    INDEX idx_status (status)
);

CREATE TABLE review_images (
    image_id UUID PRIMARY KEY,
    review_id UUID NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    display_order INT DEFAULT 0
);

CREATE TABLE review_votes (
    user_id UUID NOT NULL,
    review_id UUID NOT NULL REFERENCES reviews(review_id),
    is_helpful BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, review_id)
);

-- Denormalized aggregates (updated via trigger or async)
CREATE TABLE product_rating_summary (
    product_id UUID PRIMARY KEY REFERENCES products(product_id),
    average_rating DECIMAL(3,2) NOT NULL DEFAULT 0,
    total_reviews INT NOT NULL DEFAULT 0,
    rating_1_count INT DEFAULT 0,
    rating_2_count INT DEFAULT 0,
    rating_3_count INT DEFAULT 0,
    rating_4_count INT DEFAULT 0,
    rating_5_count INT DEFAULT 0,
    verified_review_count INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW()
);
```

**Architect Discussion:**
- **Why denormalize ratings?** AVG() over millions of reviews per product is expensive on every page load
- **Update strategy:** Trigger on review insert/update OR async event-driven update
- **Wilson Score:** For sorting reviews by quality, not just average: `(positive + 1.9208) / (total + 3.8416) - 1.96 * SQRT(positive * negative / total + 0.9604) / (total + 3.8416)`

---

## Problem 53: Design a Coupon/Discount System

**Difficulty:** Hard | **Frequency:** Very High

**Requirements:**
- Percentage and fixed-amount discounts
- Apply to specific products, categories, or entire cart
- Usage limits (total and per-user)
- Date-based validity
- Stackable vs non-stackable
- Minimum purchase requirements

```sql
CREATE TABLE coupons (
    coupon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Discount Type
    discount_type ENUM('percentage', 'fixed_amount', 'free_shipping', 'buy_x_get_y') NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL,  -- 20 for 20% or $20
    max_discount_amount DECIMAL(10,2),  -- Cap for percentage discounts
    
    -- Applicability
    applies_to ENUM('all', 'specific_products', 'specific_categories', 'specific_sellers') DEFAULT 'all',
    minimum_purchase_amount DECIMAL(10,2) DEFAULT 0,
    minimum_quantity INT DEFAULT 0,
    
    -- Limits
    total_usage_limit INT,  -- NULL = unlimited
    per_user_limit INT DEFAULT 1,
    current_usage_count INT DEFAULT 0,
    
    -- Validity
    starts_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Stacking Rules
    is_stackable BOOLEAN DEFAULT FALSE,
    priority INT DEFAULT 0,  -- Higher priority applied first
    
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_code (code),
    INDEX idx_active_dates (is_active, starts_at, expires_at)
);

-- Which products/categories a coupon applies to
CREATE TABLE coupon_applicability (
    coupon_id UUID NOT NULL REFERENCES coupons(coupon_id),
    entity_type ENUM('product', 'category', 'seller') NOT NULL,
    entity_id UUID NOT NULL,
    PRIMARY KEY (coupon_id, entity_type, entity_id)
);

-- Track coupon usage
CREATE TABLE coupon_usage (
    usage_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    coupon_id UUID NOT NULL REFERENCES coupons(coupon_id),
    user_id UUID NOT NULL,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    discount_applied DECIMAL(10,2) NOT NULL,
    used_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_coupon_user (coupon_id, user_id),
    INDEX idx_user (user_id)
);
```

**Validation Query (Can user apply this coupon?):**
```sql
SELECT c.coupon_id, c.code, c.discount_type, c.discount_value
FROM coupons c
WHERE c.code = 'SAVE20'
  AND c.is_active = TRUE
  AND NOW() BETWEEN c.starts_at AND c.expires_at
  AND (c.total_usage_limit IS NULL OR c.current_usage_count < c.total_usage_limit)
  AND (
      SELECT COUNT(*) FROM coupon_usage cu 
      WHERE cu.coupon_id = c.coupon_id AND cu.user_id = @user_id
  ) < c.per_user_limit;
```

**Race Condition Prevention:**
```sql
-- Use optimistic locking
UPDATE coupons 
SET current_usage_count = current_usage_count + 1
WHERE coupon_id = @coupon_id
  AND current_usage_count < total_usage_limit;
-- Check affected rows = 1, else coupon exhausted
```

---

## Problem 54: Design a Product Search with Faceted Filtering

**Difficulty:** Hard | **Frequency:** High

**Problem:** Design schema to support filtering products by dynamic attributes (brand, size, color, price range) with counts.

```sql
-- EAV (Entity-Attribute-Value) for dynamic product attributes
CREATE TABLE product_attributes (
    product_id UUID NOT NULL REFERENCES products(product_id),
    attribute_name VARCHAR(100) NOT NULL,  -- "brand", "color", "size"
    attribute_value VARCHAR(500) NOT NULL,  -- "Nike", "Red", "XL"
    numeric_value DECIMAL(10,2),  -- For range filtering
    PRIMARY KEY (product_id, attribute_name, attribute_value),
    INDEX idx_name_value (attribute_name, attribute_value),
    INDEX idx_numeric (attribute_name, numeric_value)
);
```

**Faceted Search Query (get counts per filter value):**
```sql
-- Products in "Shoes" category with facet counts
WITH filtered_products AS (
    SELECT p.product_id
    FROM products p
    WHERE p.category_id = 42
      AND p.status = 'active'
      -- Apply active filters
      AND EXISTS (
          SELECT 1 FROM product_attributes pa 
          WHERE pa.product_id = p.product_id 
            AND pa.attribute_name = 'brand' AND pa.attribute_value = 'Nike'
      )
)
-- Get counts for "color" facet
SELECT pa.attribute_value AS color, COUNT(DISTINCT pa.product_id) AS count
FROM product_attributes pa
JOIN filtered_products fp ON pa.product_id = fp.product_id
WHERE pa.attribute_name = 'color'
GROUP BY pa.attribute_value
ORDER BY count DESC;
```

**Architect Recommendation:**
- SQL-based faceted search works for < 1M products
- For larger catalogs: **Elasticsearch** or **Apache Solr** with SQL as source of truth
- Sync strategy: CDC (Change Data Capture) → Kafka → Elasticsearch
- Hybrid: SQL for writes + ES for search reads

---

## Problem 55: Design a Wishlist System

**Difficulty:** Easy-Medium | **Frequency:** High

```sql
CREATE TABLE wishlists (
    wishlist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL DEFAULT 'My Wishlist',
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user (user_id)
);

CREATE TABLE wishlist_items (
    wishlist_id UUID NOT NULL REFERENCES wishlists(wishlist_id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES product_variants(variant_id),
    added_at TIMESTAMP DEFAULT NOW(),
    price_at_addition DECIMAL(10,2),  -- For price drop notifications
    PRIMARY KEY (wishlist_id, variant_id),
    INDEX idx_variant (variant_id)
);

-- Price drop notification query
SELECT wi.*, pv.price AS current_price, wi.price_at_addition AS original_price,
       ROUND((wi.price_at_addition - pv.price) / wi.price_at_addition * 100, 1) AS discount_pct
FROM wishlist_items wi
JOIN product_variants pv ON wi.variant_id = pv.variant_id
WHERE pv.price < wi.price_at_addition
ORDER BY discount_pct DESC;
```

---

## Problem 56: Design a Product Recommendation Engine (Collaborative Filtering Data Model)

**Difficulty:** Expert | **Frequency:** High

```sql
-- User-Item Interactions (basis for collaborative filtering)
CREATE TABLE user_interactions (
    user_id UUID NOT NULL,
    product_id UUID NOT NULL,
    interaction_type ENUM('view', 'click', 'cart', 'purchase', 'review', 'wishlist') NOT NULL,
    interaction_weight DECIMAL(3,2) NOT NULL,  -- view=0.1, click=0.3, cart=0.5, purchase=1.0
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_product (product_id),
    INDEX idx_type (interaction_type, created_at)
);

-- Pre-computed: "Users who bought X also bought Y"
CREATE TABLE product_associations (
    product_id UUID NOT NULL,
    associated_product_id UUID NOT NULL,
    association_type ENUM('also_bought', 'also_viewed', 'frequently_together', 'similar') NOT NULL,
    score DECIMAL(5,4) NOT NULL,  -- Confidence/lift score
    sample_size INT NOT NULL,  -- How many users contributed
    computed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (product_id, associated_product_id, association_type),
    INDEX idx_product_type_score (product_id, association_type, score DESC)
);

-- Compute "also bought together" (run as batch job)
INSERT INTO product_associations (product_id, associated_product_id, association_type, score, sample_size)
SELECT oi1.product_id, oi2.product_id, 'also_bought',
       COUNT(DISTINCT oi1.order_id) * 1.0 / 
           (SELECT COUNT(DISTINCT order_id) FROM order_items WHERE product_id = oi1.product_id) AS lift,
       COUNT(DISTINCT oi1.order_id) AS sample_size
FROM order_items oi1
JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.product_id != oi2.product_id
GROUP BY oi1.product_id, oi2.product_id
HAVING sample_size >= 5  -- Minimum confidence
ORDER BY lift DESC;
```

---

## Problem 57: Design an Auction System (eBay-style)

**Difficulty:** Hard | **Frequency:** High

**Key Challenges:** Concurrency on bid placement, time-based auction ending, sniping protection

```sql
CREATE TABLE auctions (
    auction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL,
    product_id UUID NOT NULL,
    starting_price DECIMAL(10,2) NOT NULL,
    reserve_price DECIMAL(10,2),  -- Minimum to actually sell
    buy_now_price DECIMAL(10,2),  -- Instant purchase option
    current_bid DECIMAL(10,2) NOT NULL DEFAULT 0,
    current_bidder_id UUID,
    bid_count INT DEFAULT 0,
    bid_increment DECIMAL(10,2) NOT NULL DEFAULT 1.00,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    original_end_at TIMESTAMP NOT NULL,  -- Before sniping extensions
    status ENUM('scheduled', 'active', 'ended', 'sold', 'unsold', 'cancelled') DEFAULT 'scheduled',
    auto_extend_minutes INT DEFAULT 5,  -- Extend if bid in last N minutes
    created_at TIMESTAMP DEFAULT NOW(),
    version INT DEFAULT 0,  -- Optimistic locking
    INDEX idx_status_end (status, ends_at),
    INDEX idx_seller (seller_id)
);

CREATE TABLE bids (
    bid_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auction_id UUID NOT NULL REFERENCES auctions(auction_id),
    bidder_id UUID NOT NULL,
    bid_amount DECIMAL(10,2) NOT NULL,
    max_bid_amount DECIMAL(10,2),  -- Proxy bidding (auto-bid up to this)
    is_winning BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_auction_amount (auction_id, bid_amount DESC),
    INDEX idx_bidder (bidder_id)
);
```

**Place Bid (with optimistic locking + sniping protection):**
```sql
BEGIN TRANSACTION;

-- Lock and validate
SELECT auction_id, current_bid, bid_increment, ends_at, version, status
FROM auctions
WHERE auction_id = @auction_id
FOR UPDATE;

-- Validate: bid > current_bid + increment, status = 'active', not expired

-- Place bid
INSERT INTO bids (auction_id, bidder_id, bid_amount, is_winning)
VALUES (@auction_id, @bidder_id, @bid_amount, TRUE);

-- Update previous winning bid
UPDATE bids SET is_winning = FALSE
WHERE auction_id = @auction_id AND is_winning = TRUE AND bid_id != @new_bid_id;

-- Update auction with sniping protection
UPDATE auctions
SET current_bid = @bid_amount,
    current_bidder_id = @bidder_id,
    bid_count = bid_count + 1,
    ends_at = CASE 
        WHEN TIMESTAMPDIFF(MINUTE, NOW(), ends_at) < auto_extend_minutes 
        THEN ends_at + INTERVAL auto_extend_minutes MINUTE
        ELSE ends_at 
    END,
    version = version + 1
WHERE auction_id = @auction_id AND version = @expected_version;

COMMIT;
```

---

## Problem 58: Design a Flash Sale / Deal System

**Difficulty:** Hard | **Frequency:** High (Amazon Lightning Deals)

**Key Challenge:** Prevent overselling under extreme concurrency (thousands of requests/second)

```sql
CREATE TABLE flash_sales (
    sale_id UUID PRIMARY KEY,
    product_variant_id UUID NOT NULL,
    sale_price DECIMAL(10,2) NOT NULL,
    original_price DECIMAL(10,2) NOT NULL,
    total_quantity INT NOT NULL,
    sold_quantity INT NOT NULL DEFAULT 0,
    max_per_user INT DEFAULT 1,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    status ENUM('upcoming', 'active', 'sold_out', 'ended') DEFAULT 'upcoming',
    INDEX idx_status_start (status, starts_at)
);

CREATE TABLE flash_sale_claims (
    claim_id UUID PRIMARY KEY,
    sale_id UUID NOT NULL REFERENCES flash_sales(sale_id),
    user_id UUID NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    status ENUM('claimed', 'purchased', 'expired') DEFAULT 'claimed',
    claimed_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,  -- Must complete purchase within X minutes
    UNIQUE KEY uk_sale_user (sale_id, user_id),
    INDEX idx_expires (status, expires_at)
);
```

**High-Concurrency Claim (Redis + SQL hybrid):**
```
Architecture:
1. Redis: DECR atomic counter for real-time availability (fast path)
2. SQL: Source of truth for actual claims (slow path)

Flow:
1. User clicks "Claim Deal"
2. DECR redis_key:"flash_sale:{id}:remaining" → if >= 0, proceed
3. INSERT INTO flash_sale_claims (with expiry)
4. If INSERT fails (duplicate), INCR the Redis counter back
5. Background job: expire uncompleted claims, INCR counter back
```

---

## Problem 59: Design a Multi-Currency Pricing System

**Difficulty:** Hard | **Frequency:** High (International platforms)

```sql
CREATE TABLE currencies (
    currency_code CHAR(3) PRIMARY KEY,  -- ISO 4217: USD, EUR, GBP
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(5) NOT NULL,
    decimal_places INT NOT NULL DEFAULT 2,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE exchange_rates (
    from_currency CHAR(3) NOT NULL REFERENCES currencies(currency_code),
    to_currency CHAR(3) NOT NULL REFERENCES currencies(currency_code),
    rate DECIMAL(18,8) NOT NULL,
    effective_from TIMESTAMP NOT NULL,
    effective_to TIMESTAMP,  -- NULL = current
    source VARCHAR(50),  -- "ecb", "openexchange"
    PRIMARY KEY (from_currency, to_currency, effective_from),
    INDEX idx_current (from_currency, to_currency, effective_to)
);

-- Product prices in multiple currencies (seller sets explicit prices)
CREATE TABLE product_prices (
    product_id UUID NOT NULL,
    currency_code CHAR(3) NOT NULL REFERENCES currencies(currency_code),
    price DECIMAL(12,2) NOT NULL,
    is_auto_converted BOOLEAN DEFAULT FALSE,  -- TRUE if system-generated
    PRIMARY KEY (product_id, currency_code)
);
```

**Get price in user's currency (with fallback to conversion):**
```sql
SELECT COALESCE(
    -- Try explicit price first
    (SELECT price FROM product_prices 
     WHERE product_id = @pid AND currency_code = @user_currency),
    -- Fallback: convert from base currency
    (SELECT pp.price * er.rate
     FROM product_prices pp
     JOIN exchange_rates er ON er.from_currency = pp.currency_code 
                            AND er.to_currency = @user_currency
                            AND er.effective_to IS NULL
     WHERE pp.product_id = @pid AND pp.currency_code = 'USD')
) AS display_price;
```

---

## Problem 60: Design a Return/Refund Management System

**Difficulty:** Medium | **Frequency:** High

```sql
CREATE TABLE return_requests (
    return_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(order_id),
    user_id UUID NOT NULL,
    reason ENUM('defective', 'wrong_item', 'not_as_described', 'changed_mind', 'too_late', 'other') NOT NULL,
    description TEXT,
    status ENUM('requested', 'approved', 'rejected', 'shipped_back', 'received', 'refunded', 'closed') DEFAULT 'requested',
    refund_method ENUM('original_payment', 'store_credit', 'exchange') DEFAULT 'original_payment',
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    INDEX idx_order (order_id),
    INDEX idx_user (user_id),
    INDEX idx_status (status)
);

CREATE TABLE return_items (
    return_id UUID NOT NULL REFERENCES return_requests(return_id),
    order_item_id BIGINT NOT NULL REFERENCES order_items(order_item_id),
    quantity INT NOT NULL,
    condition_on_return ENUM('new', 'good', 'fair', 'poor', 'damaged'),
    refund_amount DECIMAL(10,2),
    PRIMARY KEY (return_id, order_item_id)
);

CREATE TABLE refund_transactions (
    refund_id UUID PRIMARY KEY,
    return_id UUID NOT NULL REFERENCES return_requests(return_id),
    amount DECIMAL(10,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    payment_gateway_ref VARCHAR(255),
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    processed_at TIMESTAMP,
    INDEX idx_return (return_id)
);
```

---

## Problem 61: Design an Inventory Management System with Multiple Warehouses

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE warehouses (
    warehouse_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    address_id UUID NOT NULL,
    type ENUM('fulfillment_center', 'distribution_center', 'store', 'dropship') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

CREATE TABLE inventory_levels (
    variant_id UUID NOT NULL,
    warehouse_id INT NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0,
    quantity_reserved INT NOT NULL DEFAULT 0,  -- Allocated to orders
    quantity_incoming INT NOT NULL DEFAULT 0,  -- PO in transit
    quantity_available INT GENERATED ALWAYS AS (quantity_on_hand - quantity_reserved) STORED,
    reorder_point INT DEFAULT 10,
    reorder_quantity INT DEFAULT 100,
    last_counted_at TIMESTAMP,
    PRIMARY KEY (variant_id, warehouse_id),
    CHECK (quantity_on_hand >= quantity_reserved)
);

-- Inventory movements (audit trail)
CREATE TABLE inventory_movements (
    movement_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    variant_id UUID NOT NULL,
    warehouse_id INT NOT NULL,
    movement_type ENUM('purchase_order', 'sale', 'return', 'adjustment', 'transfer_in', 'transfer_out', 'damage', 'count') NOT NULL,
    quantity INT NOT NULL,  -- Positive = increase, Negative = decrease
    reference_type VARCHAR(50),  -- 'order', 'return', 'po', 'transfer'
    reference_id UUID,
    notes TEXT,
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_variant_warehouse (variant_id, warehouse_id, created_at),
    INDEX idx_reference (reference_type, reference_id)
);
```

**Reserve inventory atomically:**
```sql
UPDATE inventory_levels
SET quantity_reserved = quantity_reserved + @qty
WHERE variant_id = @variant_id
  AND warehouse_id = @warehouse_id
  AND (quantity_on_hand - quantity_reserved) >= @qty;
-- Check affected_rows = 1; if 0, insufficient stock
```

---

## Problem 62: Design a Seller Payout System

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE seller_balances (
    seller_id UUID PRIMARY KEY REFERENCES sellers(seller_id),
    available_balance DECIMAL(12,2) NOT NULL DEFAULT 0,
    pending_balance DECIMAL(12,2) NOT NULL DEFAULT 0,  -- In settlement period
    total_earned DECIMAL(14,2) NOT NULL DEFAULT 0,
    total_paid_out DECIMAL(14,2) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE seller_transactions (
    transaction_id UUID PRIMARY KEY,
    seller_id UUID NOT NULL,
    type ENUM('sale', 'commission_fee', 'refund', 'payout', 'adjustment', 'chargeback') NOT NULL,
    amount DECIMAL(10,2) NOT NULL,  -- Positive = credit, Negative = debit
    order_id UUID,
    description VARCHAR(500),
    status ENUM('pending', 'settled', 'paid', 'cancelled') DEFAULT 'pending',
    settles_at TIMESTAMP,  -- When pending → available
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_seller_status (seller_id, status),
    INDEX idx_settles (settles_at, status)
);

CREATE TABLE payouts (
    payout_id UUID PRIMARY KEY,
    seller_id UUID NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    payment_method ENUM('bank_transfer', 'paypal', 'stripe_connect') NOT NULL,
    status ENUM('scheduled', 'processing', 'completed', 'failed') DEFAULT 'scheduled',
    scheduled_at TIMESTAMP NOT NULL,
    processed_at TIMESTAMP,
    gateway_reference VARCHAR(255),
    INDEX idx_seller (seller_id),
    INDEX idx_status_scheduled (status, scheduled_at)
);
```

---

## Problem 63: Design a Product Comparison Feature

**Difficulty:** Medium | **Frequency:** Medium

```sql
-- Comparison specifications per category
CREATE TABLE category_specs (
    spec_id INT PRIMARY KEY AUTO_INCREMENT,
    category_id INT NOT NULL REFERENCES categories(category_id),
    spec_name VARCHAR(100) NOT NULL,  -- "Screen Size", "Battery Life"
    spec_unit VARCHAR(50),  -- "inches", "mAh"
    data_type ENUM('text', 'number', 'boolean') DEFAULT 'text',
    display_order INT DEFAULT 0,
    is_key_spec BOOLEAN DEFAULT FALSE,  -- Show in comparison highlight
    UNIQUE KEY uk_cat_spec (category_id, spec_name)
);

CREATE TABLE product_specs (
    product_id UUID NOT NULL,
    spec_id INT NOT NULL REFERENCES category_specs(spec_id),
    text_value VARCHAR(500),
    numeric_value DECIMAL(10,2),
    boolean_value BOOLEAN,
    PRIMARY KEY (product_id, spec_id)
);

-- Comparison query
SELECT cs.spec_name, cs.spec_unit,
    MAX(CASE WHEN ps.product_id = @product1 THEN COALESCE(ps.text_value, CAST(ps.numeric_value AS CHAR)) END) AS product1_value,
    MAX(CASE WHEN ps.product_id = @product2 THEN COALESCE(ps.text_value, CAST(ps.numeric_value AS CHAR)) END) AS product2_value,
    MAX(CASE WHEN ps.product_id = @product3 THEN COALESCE(ps.text_value, CAST(ps.numeric_value AS CHAR)) END) AS product3_value
FROM category_specs cs
LEFT JOIN product_specs ps ON cs.spec_id = ps.spec_id 
    AND ps.product_id IN (@product1, @product2, @product3)
WHERE cs.category_id = @category_id
GROUP BY cs.spec_id, cs.spec_name, cs.spec_unit
ORDER BY cs.display_order;
```

---

## Problem 64: Design a Subscription/Recurring Order System

**Difficulty:** Hard | **Frequency:** High (SaaS, Subscribe & Save)

```sql
CREATE TABLE subscription_plans (
    plan_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    billing_interval ENUM('weekly', 'biweekly', 'monthly', 'quarterly', 'yearly') NOT NULL,
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE subscriptions (
    subscription_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL REFERENCES subscription_plans(plan_id),
    status ENUM('active', 'paused', 'cancelled', 'expired', 'past_due') DEFAULT 'active',
    current_period_start TIMESTAMP NOT NULL,
    current_period_end TIMESTAMP NOT NULL,
    next_billing_date DATE NOT NULL,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    pause_until TIMESTAMP,
    payment_method_id UUID,
    trial_ends_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user (user_id),
    INDEX idx_next_billing (status, next_billing_date),
    INDEX idx_status (status)
);

CREATE TABLE subscription_items (
    subscription_id UUID NOT NULL REFERENCES subscriptions(subscription_id),
    variant_id UUID NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (subscription_id, variant_id)
);

-- Billing job query: Find subscriptions to bill today
SELECT s.subscription_id, s.user_id, s.payment_method_id,
       SUM(si.quantity * si.unit_price * (1 - sp.discount_percentage/100)) AS amount_due
FROM subscriptions s
JOIN subscription_items si ON s.subscription_id = si.subscription_id
JOIN subscription_plans sp ON s.plan_id = sp.plan_id
WHERE s.status = 'active'
  AND s.next_billing_date <= CURRENT_DATE
  AND (s.trial_ends_at IS NULL OR s.trial_ends_at < NOW())
GROUP BY s.subscription_id, s.user_id, s.payment_method_id;
```

---

## Problem 65: Design a Gift Card / Store Credit System

**Difficulty:** Medium | **Frequency:** High

```sql
CREATE TABLE gift_cards (
    card_id UUID PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,  -- XXXX-XXXX-XXXX-XXXX
    initial_balance DECIMAL(10,2) NOT NULL,
    current_balance DECIMAL(10,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    purchaser_id UUID,
    recipient_email VARCHAR(255),
    status ENUM('active', 'depleted', 'expired', 'disabled') DEFAULT 'active',
    expires_at TIMESTAMP,
    activated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_code (code),
    CHECK (current_balance >= 0)
);

CREATE TABLE gift_card_transactions (
    transaction_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    card_id UUID NOT NULL REFERENCES gift_cards(card_id),
    type ENUM('purchase', 'redemption', 'refund', 'expiry', 'adjustment') NOT NULL,
    amount DECIMAL(10,2) NOT NULL,  -- Positive = credit, Negative = debit
    balance_after DECIMAL(10,2) NOT NULL,
    order_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_card (card_id, created_at)
);
```

**Redeem gift card (atomic):**
```sql
UPDATE gift_cards
SET current_balance = current_balance - @amount,
    status = CASE WHEN current_balance - @amount = 0 THEN 'depleted' ELSE status END
WHERE card_id = @card_id
  AND status = 'active'
  AND current_balance >= @amount
  AND (expires_at IS NULL OR expires_at > NOW());
-- Check affected_rows = 1
```

---

## Problem 66: Design a Shipping Rate Calculation System

**Difficulty:** Hard | **Frequency:** Medium

```sql
CREATE TABLE shipping_zones (
    zone_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE zone_regions (
    zone_id INT NOT NULL REFERENCES shipping_zones(zone_id),
    country_code CHAR(2) NOT NULL,
    state_code VARCHAR(10),  -- NULL = entire country
    zip_prefix VARCHAR(10),  -- For granular US zip-based zones
    PRIMARY KEY (zone_id, country_code, COALESCE(state_code, ''), COALESCE(zip_prefix, ''))
);

CREATE TABLE shipping_methods (
    method_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,  -- "Standard", "Express", "Next Day"
    carrier VARCHAR(50),  -- "UPS", "FedEx", "USPS"
    min_delivery_days INT,
    max_delivery_days INT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE shipping_rates (
    rate_id INT PRIMARY KEY AUTO_INCREMENT,
    zone_id INT NOT NULL REFERENCES shipping_zones(zone_id),
    method_id INT NOT NULL REFERENCES shipping_methods(method_id),
    rate_type ENUM('flat', 'weight_based', 'price_based', 'item_count') NOT NULL,
    min_value DECIMAL(10,2) NOT NULL DEFAULT 0,  -- Min weight/price/count
    max_value DECIMAL(10,2),  -- NULL = no upper limit
    rate DECIMAL(10,2) NOT NULL,
    per_additional_unit DECIMAL(10,2) DEFAULT 0,
    free_shipping_threshold DECIMAL(10,2),  -- Order total for free shipping
    UNIQUE KEY uk_zone_method_range (zone_id, method_id, rate_type, min_value)
);

-- Calculate shipping rate
SELECT sm.name, sm.carrier, sr.rate,
       CASE 
           WHEN sr.free_shipping_threshold IS NOT NULL AND @order_total >= sr.free_shipping_threshold THEN 0
           WHEN sr.rate_type = 'weight_based' THEN sr.rate + GREATEST(0, @weight - sr.min_value) * sr.per_additional_unit
           ELSE sr.rate
       END AS calculated_rate,
       sm.min_delivery_days, sm.max_delivery_days
FROM shipping_rates sr
JOIN shipping_methods sm ON sr.method_id = sm.method_id
JOIN shipping_zones sz ON sr.zone_id = sz.zone_id
JOIN zone_regions zr ON sz.zone_id = zr.zone_id
WHERE zr.country_code = @country
  AND (zr.state_code IS NULL OR zr.state_code = @state)
  AND @weight BETWEEN sr.min_value AND COALESCE(sr.max_value, 999999)
  AND sm.is_active = TRUE
ORDER BY calculated_rate;
```

---

## Problem 67: Design an A/B Testing Configuration System

**Difficulty:** Hard | **Frequency:** High (Product teams)

```sql
CREATE TABLE experiments (
    experiment_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    hypothesis TEXT,
    metric_primary VARCHAR(100) NOT NULL,  -- "conversion_rate", "revenue_per_user"
    metrics_secondary JSONB,
    status ENUM('draft', 'running', 'paused', 'concluded') DEFAULT 'draft',
    traffic_percentage DECIMAL(5,2) NOT NULL DEFAULT 100,  -- % of eligible users
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_by UUID NOT NULL,
    INDEX idx_status (status)
);

CREATE TABLE experiment_variants (
    variant_id UUID PRIMARY KEY,
    experiment_id UUID NOT NULL REFERENCES experiments(experiment_id),
    name VARCHAR(100) NOT NULL,  -- "control", "variant_a", "variant_b"
    traffic_weight INT NOT NULL DEFAULT 50,  -- Relative weight (50/50 = equal split)
    config JSONB NOT NULL DEFAULT '{}',  -- Feature flags / config for this variant
    is_control BOOLEAN DEFAULT FALSE,
    INDEX idx_experiment (experiment_id)
);

CREATE TABLE experiment_assignments (
    user_id UUID NOT NULL,
    experiment_id UUID NOT NULL,
    variant_id UUID NOT NULL,
    assigned_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, experiment_id),
    INDEX idx_experiment_variant (experiment_id, variant_id)
);

CREATE TABLE experiment_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id UUID NOT NULL,
    experiment_id UUID NOT NULL,
    variant_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,  -- "page_view", "click", "purchase"
    event_value DECIMAL(10,2),  -- Revenue amount, etc.
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_experiment_event (experiment_id, event_type, created_at),
    INDEX idx_user (user_id, experiment_id)
);
```

**Statistical Significance Query:**
```sql
WITH variant_stats AS (
    SELECT ev.variant_id, v.name,
           COUNT(DISTINCT ea.user_id) AS total_users,
           COUNT(DISTINCT CASE WHEN ee.event_type = 'purchase' THEN ee.user_id END) AS conversions,
           SUM(CASE WHEN ee.event_type = 'purchase' THEN ee.event_value ELSE 0 END) AS total_revenue
    FROM experiment_variants v
    JOIN experiment_assignments ea ON v.variant_id = ea.variant_id
    LEFT JOIN experiment_events ee ON ea.user_id = ee.user_id AND ea.experiment_id = ee.experiment_id
    WHERE v.experiment_id = @experiment_id
    GROUP BY ev.variant_id, v.name
)
SELECT name, total_users, conversions,
       ROUND(conversions * 100.0 / total_users, 4) AS conversion_rate,
       ROUND(total_revenue / total_users, 2) AS revenue_per_user
FROM variant_stats;
```

---

## Problem 68: Design a Tax Calculation System

**Difficulty:** Hard | **Frequency:** High (Global commerce)

```sql
CREATE TABLE tax_jurisdictions (
    jurisdiction_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    country_code CHAR(2) NOT NULL,
    state_code VARCHAR(10),
    county VARCHAR(100),
    city VARCHAR(100),
    -- Hierarchical: Country → State → County → City
    INDEX idx_location (country_code, state_code, county, city)
);

CREATE TABLE tax_rates (
    rate_id INT PRIMARY KEY AUTO_INCREMENT,
    jurisdiction_id INT NOT NULL REFERENCES tax_jurisdictions(jurisdiction_id),
    tax_category VARCHAR(100) NOT NULL,  -- "general", "food", "clothing", "digital_goods"
    rate DECIMAL(6,4) NOT NULL,  -- 0.0825 = 8.25%
    effective_from DATE NOT NULL,
    effective_to DATE,  -- NULL = current
    INDEX idx_jurisdiction_category (jurisdiction_id, tax_category, effective_from)
);

-- Tax exemptions
CREATE TABLE tax_exemptions (
    exemption_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    jurisdiction_id INT REFERENCES tax_jurisdictions(jurisdiction_id),
    exemption_type VARCHAR(100),  -- "resale", "nonprofit", "government"
    certificate_number VARCHAR(100),
    valid_from DATE NOT NULL,
    valid_to DATE,
    INDEX idx_user (user_id)
);

-- Calculate tax for an order
SELECT tj.name AS jurisdiction,
       tr.tax_category,
       tr.rate,
       @item_amount * tr.rate AS tax_amount
FROM tax_jurisdictions tj
JOIN tax_rates tr ON tj.jurisdiction_id = tr.jurisdiction_id
WHERE tj.country_code = @country
  AND (tj.state_code IS NULL OR tj.state_code = @state)
  AND tr.tax_category = @product_tax_category
  AND CURRENT_DATE BETWEEN tr.effective_from AND COALESCE(tr.effective_to, '9999-12-31')
  AND NOT EXISTS (
      SELECT 1 FROM tax_exemptions te
      WHERE te.user_id = @user_id
        AND (te.jurisdiction_id IS NULL OR te.jurisdiction_id = tj.jurisdiction_id)
        AND CURRENT_DATE BETWEEN te.valid_from AND COALESCE(te.valid_to, '9999-12-31')
  )
ORDER BY tj.state_code NULLS FIRST, tj.county NULLS FIRST, tj.city NULLS FIRST;
```

---

## Problem 69: Design a Product Bundle System

**Difficulty:** Medium | **Frequency:** Medium

```sql
CREATE TABLE bundles (
    bundle_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    bundle_type ENUM('fixed', 'mix_and_match', 'bogo') NOT NULL,
    discount_type ENUM('percentage', 'fixed_price', 'cheapest_free') NOT NULL,
    discount_value DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    starts_at TIMESTAMP,
    ends_at TIMESTAMP
);

CREATE TABLE bundle_items (
    bundle_id UUID NOT NULL REFERENCES bundles(bundle_id),
    variant_id UUID NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    is_required BOOLEAN DEFAULT TRUE,  -- For mix-and-match
    PRIMARY KEY (bundle_id, variant_id)
);

-- Calculate bundle price
SELECT b.name,
       SUM(pv.price * bi.quantity) AS original_total,
       CASE b.discount_type
           WHEN 'percentage' THEN SUM(pv.price * bi.quantity) * (1 - b.discount_value/100)
           WHEN 'fixed_price' THEN b.discount_value
           WHEN 'cheapest_free' THEN SUM(pv.price * bi.quantity) - MIN(pv.price)
       END AS bundle_price,
       SUM(pv.price * bi.quantity) - (
           CASE b.discount_type
               WHEN 'percentage' THEN SUM(pv.price * bi.quantity) * (1 - b.discount_value/100)
               WHEN 'fixed_price' THEN b.discount_value
               WHEN 'cheapest_free' THEN SUM(pv.price * bi.quantity) - MIN(pv.price)
           END
       ) AS savings
FROM bundles b
JOIN bundle_items bi ON b.bundle_id = bi.bundle_id
JOIN product_variants pv ON bi.variant_id = pv.variant_id
WHERE b.bundle_id = @bundle_id
GROUP BY b.bundle_id, b.name, b.discount_type, b.discount_value;
```

---

## Problem 70: Design an Order Fulfillment & Shipment Tracking System

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE shipments (
    shipment_id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    warehouse_id INT NOT NULL REFERENCES warehouses(warehouse_id),
    carrier VARCHAR(50) NOT NULL,
    tracking_number VARCHAR(100),
    tracking_url VARCHAR(500),
    status ENUM('pending', 'label_created', 'picked_up', 'in_transit', 'out_for_delivery', 'delivered', 'failed', 'returned') DEFAULT 'pending',
    estimated_delivery DATE,
    actual_delivery TIMESTAMP,
    shipping_cost DECIMAL(10,2),
    weight_grams INT,
    dimensions JSONB,  -- {"length": 30, "width": 20, "height": 10, "unit": "cm"}
    shipped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_order (order_id),
    INDEX idx_tracking (tracking_number),
    INDEX idx_status (status)
);

CREATE TABLE shipment_items (
    shipment_id UUID NOT NULL REFERENCES shipments(shipment_id),
    order_item_id BIGINT NOT NULL REFERENCES order_items(order_item_id),
    quantity INT NOT NULL,
    PRIMARY KEY (shipment_id, order_item_id)
);

CREATE TABLE shipment_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    shipment_id UUID NOT NULL REFERENCES shipments(shipment_id),
    status VARCHAR(50) NOT NULL,
    location VARCHAR(255),
    description TEXT,
    occurred_at TIMESTAMP NOT NULL,
    received_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_shipment_time (shipment_id, occurred_at DESC)
);

-- Fulfillment dashboard query: Orders needing attention
SELECT o.order_id, o.order_number, o.created_at,
       TIMESTAMPDIFF(HOUR, o.created_at, NOW()) AS hours_since_order,
       CASE 
           WHEN s.shipment_id IS NULL THEN 'needs_fulfillment'
           WHEN s.status = 'failed' THEN 'delivery_failed'
           WHEN s.estimated_delivery < CURRENT_DATE AND s.status != 'delivered' THEN 'delayed'
           ELSE s.status
       END AS fulfillment_status
FROM orders o
LEFT JOIN shipments s ON o.order_id = s.order_id
WHERE o.status IN ('confirmed', 'processing')
  AND (s.shipment_id IS NULL OR s.status IN ('failed', 'returned'))
ORDER BY o.created_at;
```

---

## Architecture Patterns Summary

| Pattern | Used In | Benefit |
|---------|---------|---------|
| Event Sourcing | Order status, Inventory movements | Complete audit trail, temporal queries |
| Optimistic Locking | Auctions, Flash sales | High concurrency without long locks |
| Denormalized Aggregates | Ratings, Seller balances | Read performance at scale |
| Materialized Path | Categories | Fast subtree queries |
| Temporal Tables | Pricing, Tax rates | Point-in-time queries |
| Redis + SQL Hybrid | Flash sales, Cart | Speed + Durability |
| EAV Pattern | Product attributes | Flexible schema |
| JSONB Columns | Variant attributes, Metadata | Semi-structured without schema migration |
