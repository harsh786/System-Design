# Amazon E-Commerce Marketplace - System Design

## 1. Functional Requirements

### Core Features
- **Product Catalog**: 100M+ SKUs with hierarchical categories, variants, and rich attributes
- **Search**: Full-text search with faceted filtering, autocomplete, spell correction
- **Product Detail Page (PDP)**: Aggregated view with images, pricing, reviews, seller info
- **Seller Management**: Seller onboarding, product listing, performance metrics
- **Reviews & Ratings**: User reviews with text, images, verified purchase badges
- **Pricing Engine**: Dynamic pricing, deal pricing, lightning deals, coupons
- **Personalized Homepage**: User-specific recommendations, recently viewed, deals
- **Deals/Lightning Deals**: Time-bound offers with limited inventory allocation

### User Flows
1. **Browse**: Homepage → Category → Subcategory → Product List → PDP
2. **Search**: Query → Results (with facets) → PDP
3. **Seller**: Register → List Product → Manage Inventory → View Analytics
4. **Review**: Purchase → Write Review → Moderation → Published

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Search Latency (P99) | < 200ms |
| PDP Latency (P99) | < 150ms |
| Catalog Write Throughput | 10K updates/sec |
| Search QPS | 500K |
| PDP QPS | 1M |
| Availability | 99.99% |
| Data Durability | 99.999999999% |
| Search Index Freshness | < 30 seconds |
| Personalization Freshness | < 5 minutes |

## 3. Capacity Estimation

### Storage
- **Product Catalog**: 100M products × 50KB avg = 5 TB
- **Product Images**: 100M products × 8 images × 2MB = 1.6 PB (CDN-served)
- **Reviews**: 2B reviews × 2KB = 4 TB
- **Search Index**: ~2 TB (inverted index + metadata)
- **User Activity**: 500M users × 10KB profile + history = 5 TB
- **Seller Data**: 10M sellers × 100KB = 1 TB

### Compute
- **Search Cluster**: 500K QPS / 500 QPS per node = 1000 nodes (Elasticsearch)
- **Catalog Service**: 1M QPS / 10K QPS per node = 100 nodes
- **PDP Aggregation**: 1M QPS / 5K QPS per node = 200 nodes
- **Cache Layer**: 50TB Redis cluster (product metadata hot cache)

### Bandwidth
- **Inbound**: 10K catalog updates/sec × 50KB = 500 MB/s
- **Outbound**: 1M PDP requests/sec × 20KB response = 20 GB/s (mostly CDN)
- **Internal**: Search fanout 10x = 5M internal calls/sec

## 4. Data Modeling

### Product Schema (PostgreSQL - Partitioned by category_id)
```sql
CREATE TABLE products (
    product_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asin                VARCHAR(10) UNIQUE NOT NULL,
    title               VARCHAR(500) NOT NULL,
    brand_id            UUID REFERENCES brands(brand_id),
    category_id         UUID NOT NULL REFERENCES categories(category_id),
    product_type        VARCHAR(50) NOT NULL, -- 'STANDARD', 'VARIATION_PARENT', 'VARIATION_CHILD'
    parent_product_id   UUID REFERENCES products(product_id),
    status              VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, INACTIVE, SUPPRESSED
    listing_date        TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Denormalized for read performance
    avg_rating          DECIMAL(3,2) DEFAULT 0,
    review_count        INTEGER DEFAULT 0,
    best_seller_rank    INTEGER,
    
    -- Structured attributes (indexed)
    bullet_points       TEXT[],
    description         TEXT,
    
    -- Flexible attributes (category-specific)
    attributes          JSONB NOT NULL DEFAULT '{}',
    
    -- SEO
    slug                VARCHAR(500),
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH(category_id);

CREATE INDEX idx_products_category ON products(category_id, status, best_seller_rank);
CREATE INDEX idx_products_brand ON products(brand_id, status);
CREATE INDEX idx_products_parent ON products(parent_product_id) WHERE parent_product_id IS NOT NULL;
CREATE INDEX idx_products_asin ON products(asin);
CREATE INDEX idx_products_attributes ON products USING GIN(attributes);
CREATE INDEX idx_products_listing_date ON products(listing_date DESC);
```

### Product Variants Schema
```sql
CREATE TABLE product_variants (
    variant_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_product_id   UUID NOT NULL REFERENCES products(product_id),
    variation_theme     VARCHAR(100) NOT NULL, -- 'SIZE_COLOR', 'SIZE', 'COLOR'
    variation_values    JSONB NOT NULL, -- {"size": "XL", "color": "Red"}
    sku                 VARCHAR(50) UNIQUE NOT NULL,
    
    -- Variant-specific pricing
    base_price          DECIMAL(12,2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'USD',
    
    -- Variant-specific attributes
    weight_kg           DECIMAL(8,3),
    dimensions_cm       JSONB, -- {"length": 30, "width": 20, "height": 10}
    
    -- Images specific to this variant
    image_ids           UUID[],
    
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_variants_parent ON product_variants(parent_product_id, status);
CREATE INDEX idx_variants_sku ON product_variants(sku);
```

### Category Schema (Closure Table for hierarchy)
```sql
CREATE TABLE categories (
    category_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(200) NOT NULL,
    slug                VARCHAR(200) NOT NULL,
    parent_id           UUID REFERENCES categories(category_id),
    level               INTEGER NOT NULL DEFAULT 0,
    path                TEXT NOT NULL, -- '/electronics/phones/smartphones'
    
    -- Category-specific attribute definitions
    attribute_schema    JSONB, -- defines required/optional attributes for products
    
    is_leaf             BOOLEAN DEFAULT FALSE,
    product_count       INTEGER DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Closure table for efficient ancestor/descendant queries
CREATE TABLE category_closure (
    ancestor_id         UUID NOT NULL REFERENCES categories(category_id),
    descendant_id       UUID NOT NULL REFERENCES categories(category_id),
    depth               INTEGER NOT NULL,
    PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE INDEX idx_category_closure_desc ON category_closure(descendant_id, depth);
```

### Seller Schema
```sql
CREATE TABLE sellers (
    seller_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name       VARCHAR(300) NOT NULL,
    legal_name          VARCHAR(300),
    seller_type         VARCHAR(20) NOT NULL, -- 'FBA', 'FBM', 'VENDOR'
    
    -- Verification
    tax_id              VARCHAR(50),
    verified            BOOLEAN DEFAULT FALSE,
    verification_date   TIMESTAMP,
    
    -- Performance metrics (denormalized)
    rating              DECIMAL(3,2) DEFAULT 0,
    order_defect_rate   DECIMAL(5,4) DEFAULT 0,
    late_shipment_rate  DECIMAL(5,4) DEFAULT 0,
    cancellation_rate   DECIMAL(5,4) DEFAULT 0,
    
    -- Account
    status              VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, SUSPENDED, BANNED
    tier                VARCHAR(20) DEFAULT 'STANDARD', -- STANDARD, PROFESSIONAL
    commission_rate     DECIMAL(5,4) DEFAULT 0.15,
    
    contact_email       VARCHAR(255) NOT NULL,
    contact_phone       VARCHAR(20),
    address             JSONB,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sellers_status ON sellers(status, rating DESC);
CREATE INDEX idx_sellers_type ON sellers(seller_type, status);
```

### Seller Offers (Buy Box)
```sql
CREATE TABLE seller_offers (
    offer_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id          UUID NOT NULL REFERENCES products(product_id),
    seller_id           UUID NOT NULL REFERENCES sellers(seller_id),
    
    -- Pricing
    price               DECIMAL(12,2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'USD',
    shipping_price      DECIMAL(8,2) DEFAULT 0,
    
    -- Fulfillment
    fulfillment_type    VARCHAR(10) NOT NULL, -- 'FBA', 'FBM'
    condition           VARCHAR(20) DEFAULT 'NEW', -- NEW, USED_LIKE_NEW, USED_GOOD, etc.
    
    -- Inventory
    quantity_available  INTEGER NOT NULL DEFAULT 0,
    max_order_quantity  INTEGER DEFAULT 10,
    
    -- Buy box eligibility
    buy_box_eligible    BOOLEAN DEFAULT FALSE,
    buy_box_winner      BOOLEAN DEFAULT FALSE,
    
    -- Shipping
    ships_from          VARCHAR(100),
    delivery_days_min   INTEGER,
    delivery_days_max   INTEGER,
    
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(product_id, seller_id, condition)
);

CREATE INDEX idx_offers_product ON seller_offers(product_id, buy_box_winner, price);
CREATE INDEX idx_offers_seller ON seller_offers(seller_id, status);
CREATE INDEX idx_offers_buybox ON seller_offers(product_id, buy_box_eligible, price) WHERE status = 'ACTIVE';
```

### Reviews Schema
```sql
CREATE TABLE reviews (
    review_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id          UUID NOT NULL REFERENCES products(product_id),
    user_id             UUID NOT NULL,
    order_id            UUID, -- NULL if not verified purchase
    
    rating              SMALLINT NOT NULL CHECK(rating BETWEEN 1 AND 5),
    title               VARCHAR(200),
    body                TEXT,
    
    -- Rich content
    image_urls          TEXT[],
    video_url           TEXT,
    
    -- Metadata
    verified_purchase   BOOLEAN DEFAULT FALSE,
    helpful_votes       INTEGER DEFAULT 0,
    total_votes         INTEGER DEFAULT 0,
    
    -- Moderation
    status              VARCHAR(20) DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
    moderation_reason   TEXT,
    
    -- Variant info
    variant_attributes  JSONB, -- {"size": "XL", "color": "Red"}
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reviews_product ON reviews(product_id, status, created_at DESC);
CREATE INDEX idx_reviews_product_rating ON reviews(product_id, rating, status);
CREATE INDEX idx_reviews_user ON reviews(user_id, created_at DESC);
CREATE INDEX idx_reviews_helpful ON reviews(product_id, helpful_votes DESC) WHERE status = 'APPROVED';
```

### Pricing & Deals Schema
```sql
CREATE TABLE pricing_rules (
    rule_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id          UUID REFERENCES products(product_id),
    category_id         UUID REFERENCES categories(category_id),
    seller_id           UUID REFERENCES sellers(seller_id),
    
    rule_type           VARCHAR(30) NOT NULL, -- 'DYNAMIC', 'DEAL', 'LIGHTNING', 'COUPON'
    priority            INTEGER DEFAULT 0,
    
    -- Rule definition
    discount_type       VARCHAR(20), -- 'PERCENTAGE', 'FIXED', 'PRICE_OVERRIDE'
    discount_value      DECIMAL(12,2),
    min_price           DECIMAL(12,2), -- floor price
    max_price           DECIMAL(12,2), -- ceiling price
    
    -- Conditions
    conditions          JSONB, -- {"min_quantity": 2, "user_segment": "prime"}
    
    -- Schedule
    start_time          TIMESTAMP,
    end_time            TIMESTAMP,
    
    -- Inventory allocation (for lightning deals)
    allocated_quantity  INTEGER,
    claimed_quantity    INTEGER DEFAULT 0,
    
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pricing_product ON pricing_rules(product_id, status, priority DESC);
CREATE INDEX idx_pricing_schedule ON pricing_rules(start_time, end_time, status);
CREATE INDEX idx_pricing_type ON pricing_rules(rule_type, status);
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐                       │
│  │  Web App │  │Mobile App│  │ Seller Hub│  │ Admin Portal │                       │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘                       │
└───────┼──────────────┼──────────────┼────────────────┼───────────────────────────────┘
        │              │              │                │
┌───────┼──────────────┼──────────────┼────────────────┼───────────────────────────────┐
│       ▼              ▼              ▼                ▼          EDGE LAYER            │
│  ┌─────────────────────────────────────────────────────────┐                         │
│  │              CloudFront CDN (Static + API Cache)         │                         │
│  └────────────────────────────┬────────────────────────────┘                         │
│  ┌────────────────────────────▼────────────────────────────┐                         │
│  │              API Gateway (Rate Limit + Auth + Route)     │                         │
│  └────────────────────────────┬────────────────────────────┘                         │
└───────────────────────────────┼──────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────────────────────┐
│                               ▼          SERVICE LAYER                                │
│  ┌──────────────┐  ┌─────────────────┐  ┌───────────────┐  ┌────────────────────┐   │
│  │Search Service│  │ Catalog Service │  │  PDP Service  │  │Personalization Svc │   │
│  │              │  │                 │  │  (Aggregator) │  │                    │   │
│  └──────┬───────┘  └────────┬────────┘  └───────┬───────┘  └─────────┬──────────┘   │
│         │                   │                    │                    │               │
│  ┌──────┴───────┐  ┌───────┴────────┐  ┌───────┴───────┐  ┌────────┴──────────┐    │
│  │Seller Service│  │ Review Service │  │Pricing Service│  │ Deals Service     │    │
│  └──────┬───────┘  └───────┬────────┘  └───────┬───────┘  └────────┬──────────┘    │
└─────────┼───────────────────┼───────────────────┼───────────────────┼────────────────┘
          │                   │                   │                   │
┌─────────┼───────────────────┼───────────────────┼───────────────────┼────────────────┐
│         ▼                   ▼                   ▼                   ▼   DATA LAYER   │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐        │
│  │ PostgreSQL   │  │ Elasticsearch │  │  Redis Cluster│  │ DynamoDB        │        │
│  │ (Catalog +   │  │ (Search Index)│  │  (Cache +     │  │ (User Activity +│        │
│  │  Sellers +   │  │               │  │   Sessions)   │  │  Personalization)│        │
│  │  Reviews)    │  │               │  │               │  │                 │        │
│  └──────────────┘  └───────────────┘  └───────────────┘  └─────────────────┘        │
│                                                                                       │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐                              │
│  │    S3        │  │  Kafka        │  │ Apache Flink  │                              │
│  │ (Images +   │  │ (Events Bus)  │  │ (Stream       │                              │
│  │  Static)     │  │               │  │  Processing)  │                              │
│  └──────────────┘  └───────────────┘  └───────────────┘                              │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Search API
```
POST /api/v1/search
Request:
{
    "query": "wireless headphones",
    "filters": {
        "category": "electronics/headphones",
        "brand": ["Sony", "Bose"],
        "price_range": {"min": 50, "max": 300},
        "rating": {"min": 4},
        "prime_eligible": true,
        "condition": "NEW"
    },
    "sort": "relevance", // relevance, price_asc, price_desc, avg_rating, newest
    "page": 1,
    "page_size": 24,
    "user_id": "usr_abc123",  // for personalization
    "session_id": "sess_xyz"
}

Response:
{
    "results": [
        {
            "product_id": "prod_001",
            "asin": "B09XYZ1234",
            "title": "Sony WH-1000XM5 Wireless Noise Canceling Headphones",
            "image_url": "https://cdn.amazon.com/images/prod_001/main.jpg",
            "price": {"amount": 278.00, "currency": "USD", "was_price": 399.99},
            "rating": {"average": 4.7, "count": 45230},
            "prime_eligible": true,
            "delivery_date": "2024-01-15",
            "sponsored": false,
            "badge": "BEST_SELLER",
            "buy_box_seller": "Amazon.com"
        }
    ],
    "facets": {
        "brand": [{"value": "Sony", "count": 156}, {"value": "Bose", "count": 98}],
        "price_range": [{"min": 0, "max": 50, "count": 234}, ...],
        "rating": [{"value": 4, "count": 1203}, {"value": 3, "count": 456}],
        "features": [{"value": "Noise Canceling", "count": 890}, ...]
    },
    "total_results": 15678,
    "page": 1,
    "sponsored_products": [...],
    "query_corrections": {"original": "wirless", "corrected": "wireless"}
}
```

### Product Detail Page API
```
GET /api/v1/products/{asin}?user_id=usr_abc123

Response:
{
    "product": {
        "asin": "B09XYZ1234",
        "title": "Sony WH-1000XM5 Wireless Noise Canceling Headphones",
        "brand": {"id": "brand_sony", "name": "Sony"},
        "category_path": ["Electronics", "Headphones", "Over-Ear"],
        "bullet_points": [
            "Industry-leading noise cancellation with Auto NC Optimizer",
            "Crystal clear hands-free calling with 4 beamforming microphones",
            "Up to 30 hours battery life with quick charging"
        ],
        "description": "...",
        "images": [
            {"url": "https://cdn.amazon.com/...", "alt": "Front view", "type": "MAIN"},
            {"url": "https://cdn.amazon.com/...", "alt": "Side view", "type": "ALTERNATE"}
        ],
        "variants": {
            "theme": "COLOR",
            "options": [
                {"variant_id": "var_001", "color": "Black", "price": 278.00, "available": true},
                {"variant_id": "var_002", "color": "Silver", "price": 278.00, "available": true},
                {"variant_id": "var_003", "color": "Blue", "price": 298.00, "available": false}
            ]
        },
        "attributes": {
            "connectivity": "Bluetooth 5.2",
            "weight": "250g",
            "driver_size": "40mm"
        }
    },
    "buy_box": {
        "price": {"amount": 278.00, "currency": "USD", "savings": 121.99},
        "seller": {"id": "seller_amz", "name": "Amazon.com", "rating": 4.9},
        "fulfillment": "FBA",
        "delivery": {"date": "2024-01-15", "free_shipping": true, "prime": true},
        "in_stock": true,
        "quantity_available": 500
    },
    "other_sellers": [...],
    "reviews_summary": {
        "average": 4.7,
        "total_count": 45230,
        "distribution": {"5": 32000, "4": 8000, "3": 3000, "2": 1500, "1": 730},
        "top_positive": {...},
        "top_critical": {...}
    },
    "related_products": [...],
    "frequently_bought_together": [...],
    "deals": {"type": "LIGHTNING", "discount_pct": 30, "ends_at": "2024-01-14T23:59:59Z", "claimed_pct": 67}
}
```

### Catalog Management API (Seller)
```
POST /api/v1/seller/products
Request:
{
    "title": "Premium Bluetooth Speaker",
    "category_id": "cat_electronics_speakers",
    "product_type": "STANDARD",
    "brand": "MyBrand",
    "bullet_points": ["Waterproof IPX7", "24hr battery", "360° sound"],
    "description": "...",
    "attributes": {
        "connectivity": "Bluetooth 5.0",
        "waterproof_rating": "IPX7",
        "battery_life_hours": 24,
        "weight_grams": 680
    },
    "variants": [
        {"sku": "BT-SPK-BLK", "color": "Black", "price": 79.99, "quantity": 500},
        {"sku": "BT-SPK-BLU", "color": "Blue", "price": 79.99, "quantity": 300}
    ],
    "images": ["s3://uploads/img1.jpg", "s3://uploads/img2.jpg"],
    "fulfillment_type": "FBA",
    "shipping_weight_kg": 0.9
}

Response:
{
    "product_id": "prod_new_001",
    "asin": "B0CNEW1234",
    "status": "PENDING_REVIEW",
    "listing_quality_score": 85,
    "issues": [
        {"field": "images", "severity": "WARNING", "message": "Recommend at least 5 images for better conversion"}
    ],
    "estimated_live_date": "2024-01-16T00:00:00Z"
}
```

### Review API
```
POST /api/v1/products/{asin}/reviews
Request:
{
    "user_id": "usr_abc123",
    "order_id": "ord_xyz789",
    "rating": 5,
    "title": "Best headphones I've ever owned",
    "body": "The noise cancellation is incredible...",
    "images": ["s3://review-uploads/img1.jpg"],
    "variant_purchased": {"color": "Black"}
}

Response:
{
    "review_id": "rev_001",
    "status": "PENDING_MODERATION",
    "estimated_publish_time": "2024-01-14T12:00:00Z"
}
```

## 7. Deep Dives

### Deep Dive 1: Catalog Service - Hierarchical Categories & Variant Management

#### Hierarchical Category System
```
Electronics (L0)
├── Audio (L1)
│   ├── Headphones (L2)
│   │   ├── Over-Ear (L3) ← leaf, has attribute_schema
│   │   ├── In-Ear (L3)
│   │   └── On-Ear (L3)
│   └── Speakers (L2)
└── Phones (L1)
    └── Smartphones (L2)
```

**Attribute Inheritance**: Each category level defines attributes that are inherited by children.
```python
# Category attribute resolution algorithm
def resolve_attributes(category_id: str) -> dict:
    """Walk up the category tree, merging attribute schemas."""
    ancestors = db.query("""
        SELECT c.attribute_schema, c.level
        FROM category_closure cc
        JOIN categories c ON c.category_id = cc.ancestor_id
        WHERE cc.descendant_id = :cat_id
        ORDER BY cc.depth DESC
    """, cat_id=category_id)
    
    merged_schema = {}
    for ancestor in ancestors:
        if ancestor.attribute_schema:
            for attr_name, attr_def in ancestor.attribute_schema.items():
                if attr_name not in merged_schema:
                    merged_schema[attr_name] = attr_def
                else:
                    # Child can override parent's default but not remove required
                    merged_schema[attr_name] = {**merged_schema[attr_name], **attr_def}
    
    return merged_schema
```

**Variant Management**:
```python
# Variant creation with validation
class VariantManager:
    VALID_THEMES = {
        'SIZE': ['size'],
        'COLOR': ['color'],
        'SIZE_COLOR': ['size', 'color'],
        'STYLE': ['style'],
    }
    
    def create_variant_family(self, parent_product_id: str, theme: str, variants: list):
        """Create a variation family with parent-child relationships."""
        if theme not in self.VALID_THEMES:
            raise ValueError(f"Invalid theme: {theme}")
        
        required_dimensions = self.VALID_THEMES[theme]
        
        # Validate all variants have required dimension values
        for variant in variants:
            for dim in required_dimensions:
                if dim not in variant.get('variation_values', {}):
                    raise ValueError(f"Variant missing dimension: {dim}")
        
        # Check for duplicate dimension combinations
        combos = [tuple(sorted(v['variation_values'].items())) for v in variants]
        if len(combos) != len(set(combos)):
            raise ValueError("Duplicate variant combinations detected")
        
        # Create variants atomically
        with db.transaction():
            db.execute("""
                UPDATE products SET product_type = 'VARIATION_PARENT' 
                WHERE product_id = :pid
            """, pid=parent_product_id)
            
            for variant in variants:
                db.execute("""
                    INSERT INTO product_variants (parent_product_id, variation_theme, 
                        variation_values, sku, base_price)
                    VALUES (:parent_id, :theme, :values, :sku, :price)
                """, parent_id=parent_product_id, theme=theme,
                     values=json.dumps(variant['variation_values']),
                     sku=variant['sku'], price=variant['price'])
        
        # Trigger search reindex
        self.event_bus.publish('catalog.variant_family_created', {
            'parent_product_id': parent_product_id,
            'variant_count': len(variants)
        })
```

### Deep Dive 2: Search Ranking - Relevance + Conversion + Sponsored

#### Multi-Signal Ranking Architecture
```
Query → Query Understanding → Retrieval (ES) → Ranking Stage 1 (Lightweight) → 
Ranking Stage 2 (ML Model) → Blending (Organic + Sponsored) → Response
```

**Ranking Score Computation**:
```python
import numpy as np
from dataclasses import dataclass

@dataclass
class RankingFeatures:
    # Text relevance
    bm25_score: float          # BM25 from Elasticsearch
    title_match_score: float   # Exact match in title
    semantic_similarity: float # Embedding cosine similarity
    
    # Behavioral signals
    click_through_rate: float  # Historical CTR for this query-product pair
    conversion_rate: float     # Purchase rate after viewing
    add_to_cart_rate: float    # ATC rate
    
    # Product quality
    avg_rating: float
    review_count: int
    review_velocity: float     # Recent review growth
    return_rate: float
    
    # Seller quality
    seller_rating: float
    fulfillment_speed: float   # Days to deliver
    
    # Freshness & popularity
    sales_velocity: float      # Recent sales rank
    listing_age_days: int
    
    # Price competitiveness
    price_vs_category_avg: float
    has_deal: bool

class SearchRanker:
    def __init__(self):
        self.model = self._load_ranking_model()  # LambdaMART or Neural
    
    def compute_stage1_score(self, features: RankingFeatures) -> float:
        """Lightweight linear scoring for initial ranking (top 1000 → top 100)."""
        return (
            0.30 * features.bm25_score +
            0.15 * features.semantic_similarity +
            0.20 * features.conversion_rate +
            0.10 * features.click_through_rate +
            0.08 * min(features.avg_rating / 5.0, 1.0) +
            0.07 * np.log1p(features.review_count) / 12.0 +
            0.05 * features.sales_velocity +
            0.03 * (1.0 - features.return_rate) +
            0.02 * features.seller_rating
        )
    
    def compute_stage2_score(self, features: RankingFeatures, user_context: dict) -> float:
        """Full ML model scoring for final ranking (top 100 → page)."""
        feature_vector = self._extract_features(features, user_context)
        return self.model.predict(feature_vector)
    
    def blend_sponsored(self, organic: list, sponsored: list, page_size: int) -> list:
        """Blend sponsored products into organic results."""
        result = []
        sponsored_positions = {2, 5, 9, 14}  # Fixed positions for ads
        
        organic_idx = 0
        sponsored_idx = 0
        
        for pos in range(page_size):
            if pos in sponsored_positions and sponsored_idx < len(sponsored):
                result.append({**sponsored[sponsored_idx], 'sponsored': True})
                sponsored_idx += 1
            elif organic_idx < len(organic):
                result.append({**organic[organic_idx], 'sponsored': False})
                organic_idx += 1
        
        return result
```

**Elasticsearch Index Mapping**:
```json
{
    "settings": {
        "number_of_shards": 64,
        "number_of_replicas": 2,
        "analysis": {
            "analyzer": {
                "product_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "synonym", "stemmer", "stop"]
                },
                "autocomplete_analyzer": {
                    "type": "custom",
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"]
                }
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 15
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "title": {"type": "text", "analyzer": "product_analyzer", "fields": {"keyword": {"type": "keyword"}, "autocomplete": {"type": "text", "analyzer": "autocomplete_analyzer"}}},
            "brand": {"type": "keyword"},
            "category_path": {"type": "keyword"},
            "price": {"type": "float"},
            "rating": {"type": "float"},
            "review_count": {"type": "integer"},
            "in_stock": {"type": "boolean"},
            "prime_eligible": {"type": "boolean"},
            "sales_rank": {"type": "integer"},
            "attributes": {"type": "object", "enabled": true},
            "embedding": {"type": "dense_vector", "dims": 768, "index": true, "similarity": "cosine"}
        }
    }
}
```

### Deep Dive 3: Inventory-Aware Search (Real-Time OOS Filtering)

**Challenge**: 100M products, inventory changes every second. Search index must reflect stock status within 30 seconds.

**Architecture**:
```
Inventory DB → CDC (Debezium) → Kafka → Flink (OOS Detector) → 
    ├── ES Partial Update (in_stock field)
    └── Redis Bloom Filter (OOS set)
```

**Implementation**:
```python
# Flink job for real-time OOS detection
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment

class InventoryStockProcessor:
    """Processes inventory changes and updates search index."""
    
    def __init__(self):
        self.redis_client = redis.Redis(cluster=True)
        self.es_client = Elasticsearch(hosts=ES_CLUSTER)
        self.oos_bloom_filter_key = "oos:bloom:v1"
    
    def process_inventory_event(self, event: dict):
        """Handle inventory change event from Kafka."""
        product_id = event['product_id']
        warehouse_id = event['warehouse_id']
        new_quantity = event['available_quantity']
        
        # Calculate total available across all warehouses
        total_available = self._get_total_available(product_id)
        
        is_in_stock = total_available > 0
        
        # Update Elasticsearch (partial doc update - fast)
        self.es_client.update(
            index='products',
            id=product_id,
            body={'doc': {'in_stock': is_in_stock, 'quantity': total_available}},
            retry_on_conflict=3
        )
        
        # Update Redis bloom filter for instant OOS check during search
        if not is_in_stock:
            self.redis_client.bf().add(self.oos_bloom_filter_key, product_id)
        else:
            # Bloom filters don't support removal - rebuild periodically
            # Use a secondary Redis set for removal tracking
            self.redis_client.srem("oos:products", product_id)
    
    def _get_total_available(self, product_id: str) -> int:
        """Sum available qty across all warehouses from Redis counter."""
        pattern = f"inventory:{product_id}:*"
        total = 0
        for key in self.redis_client.scan_iter(match=pattern):
            qty = int(self.redis_client.get(key) or 0)
            total += qty
        return total

# Search service - post-filter with OOS check
class SearchService:
    def search(self, query: str, filters: dict, page_size: int = 24) -> list:
        # Primary search in Elasticsearch (already has in_stock filter)
        es_query = self._build_es_query(query, filters)
        es_query['query']['bool']['filter'].append({'term': {'in_stock': True}})
        
        # Fetch extra results to account for stale index
        results = self.es.search(index='products', body=es_query, size=page_size * 2)
        
        # Double-check OOS via Redis (handles race condition where ES index is stale)
        product_ids = [hit['_id'] for hit in results['hits']['hits']]
        oos_check = self.redis_client.smembers("oos:products")
        
        filtered = [
            hit for hit in results['hits']['hits']
            if hit['_id'] not in oos_check
        ]
        
        return filtered[:page_size]
```

**Kafka Configuration for Inventory Events**:
```yaml
# kafka-inventory-topic.yaml
topic: inventory.stock.changes
partitions: 128          # Partition by product_id for ordering
replication_factor: 3
retention_ms: 86400000   # 24 hours
min_insync_replicas: 2
compression_type: lz4

# Consumer group config
consumer:
  group_id: search-index-updater
  auto_offset_reset: latest
  max_poll_records: 500
  session_timeout_ms: 30000
  max_poll_interval_ms: 300000
```

## 8. Component Optimization

### Catalog Service Optimization
- **Read Path**: Multi-layer cache: L1 (in-process, 10K items, 30s TTL) → L2 (Redis, 10M items, 5min TTL) → L3 (PostgreSQL read replicas)
- **Write Path**: Writes go to primary DB → CDC publishes event → Invalidate cache → Update search index
- **Sharding**: Products table hash-partitioned by category_id (64 partitions) for balanced read distribution

### Search Performance
- **Index Warm-up**: Pre-warm file system cache on ES nodes after restart
- **Query Caching**: Top 10K queries cached at API gateway (5min TTL)
- **Shard Allocation**: Hot/warm/cold architecture - recent 30 days on SSD, older on HDD
- **Circuit Breaker**: If search latency > 500ms, fallback to pre-computed popular results

### PDP Aggregation Optimization
```python
# Parallel data fetching with circuit breakers
import asyncio
from circuitbreaker import circuit

class PDPAggregator:
    @circuit(failure_threshold=5, recovery_timeout=30)
    async def get_product_data(self, asin: str, user_id: str) -> dict:
        """Fetch all PDP data in parallel with graceful degradation."""
        tasks = {
            'product': self.catalog_client.get_product(asin),
            'buy_box': self.pricing_client.get_buy_box(asin),
            'reviews': self.review_client.get_summary(asin),
            'related': self.recommendation_client.get_related(asin, user_id),
            'deals': self.deals_client.get_active_deal(asin),
        }
        
        results = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True
        )
        
        response = {}
        for key, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                # Graceful degradation: PDP still renders without recommendations
                response[key] = self._get_fallback(key, asin)
            else:
                response[key] = result
        
        return response
    
    def _get_fallback(self, component: str, asin: str) -> dict:
        fallbacks = {
            'related': [],
            'deals': None,
            'reviews': {'average': 0, 'count': 0},  # Will show "No reviews yet"
        }
        return fallbacks.get(component, None)
```

### Redis Caching Strategy
```yaml
# Redis cluster configuration
cluster:
  nodes: 30
  shards: 15
  replicas_per_shard: 1
  memory_per_node: 64GB
  eviction_policy: allkeys-lfu

# Cache key patterns
patterns:
  product_metadata: "prod:{asin}" # TTL: 300s, ~20KB
  buy_box: "buybox:{asin}" # TTL: 60s, ~1KB  
  review_summary: "rev:{asin}:summary" # TTL: 600s, ~500B
  search_results: "search:{query_hash}" # TTL: 300s, ~5KB
  user_recent: "user:{uid}:recent" # TTL: 86400s, list of 50 ASINs
  oos_products: "oos:products" # Set, no TTL (managed by Flink)
```

## 9. Observability

### Key Metrics
```yaml
# Prometheus metrics
metrics:
  # Latency
  - name: search_latency_seconds
    type: histogram
    buckets: [0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0]
    labels: [query_type, result_count_bucket]
  
  - name: pdp_latency_seconds
    type: histogram
    buckets: [0.01, 0.025, 0.05, 0.1, 0.15, 0.3, 0.5]
    labels: [component]  # catalog, pricing, reviews, overall
  
  # Throughput
  - name: search_requests_total
    type: counter
    labels: [status, cache_hit]
  
  - name: catalog_writes_total
    type: counter
    labels: [operation, seller_type]
  
  # Business metrics
  - name: search_zero_results_total
    type: counter
    labels: [query_category]
  
  - name: buy_box_winner_changes_total
    type: counter
    labels: [reason]  # price_change, stock_change, seller_metric
  
  - name: oos_products_gauge
    type: gauge
    labels: [category]
  
  # Index freshness
  - name: search_index_lag_seconds
    type: gauge
    labels: [shard]
  
  - name: inventory_sync_lag_seconds
    type: gauge
```

### Distributed Tracing
```
Search Request Trace:
├── api_gateway (2ms)
├── auth_middleware (1ms)
├── query_understanding (5ms)
│   ├── spell_check (2ms)
│   └── query_expansion (3ms)
├── elasticsearch_query (45ms)
│   ├── shard_1 (40ms)
│   ├── shard_2 (35ms)
│   └── shard_3 (45ms) ← slowest shard
├── ranking_stage2 (20ms)
├── oos_filter_redis (3ms)
├── sponsored_blend (2ms)
└── response_serialization (2ms)
Total: 80ms
```

### Alerting Rules
```yaml
alerts:
  - name: SearchLatencyHigh
    expr: histogram_quantile(0.99, search_latency_seconds) > 0.3
    for: 5m
    severity: critical
    
  - name: SearchIndexStale
    expr: search_index_lag_seconds > 60
    for: 2m
    severity: warning
    
  - name: HighOOSRateInSearch
    expr: rate(search_oos_filtered_total[5m]) / rate(search_results_total[5m]) > 0.1
    for: 10m
    severity: warning
    
  - name: CatalogWriteFailures
    expr: rate(catalog_writes_total{status="error"}[5m]) > 10
    for: 3m
    severity: critical
```

## 10. Failure Scenarios & Considerations

### Search Index Corruption
- **Detection**: Compare doc count ES vs source DB, automated reconciliation job
- **Recovery**: Rebuild from snapshot + replay Kafka events from offset
- **Mitigation**: Blue-green index deployment, always keep N-1 index available

### Buy Box Race Conditions
- **Problem**: Multiple sellers update price simultaneously
- **Solution**: Optimistic locking with version field, recompute buy box asynchronously
- **Consistency**: Buy box winner cached for 60s, eventual consistency acceptable

### Hot Product Problem (Flash Sales)
- **Problem**: Single product gets 100K QPS during lightning deal
- **Solution**: 
  - CDN cache PDP with 10s TTL during deals
  - Redis hot key replication (read from replicas)
  - Request coalescing for identical concurrent requests

### Data Consistency
| Scenario | Consistency Model | Rationale |
|---|---|---|
| Product catalog updates | Eventually consistent (30s) | Search freshness SLA |
| Price changes | Strongly consistent (buy box) | Financial accuracy |
| Review counts | Eventually consistent (5min) | Non-critical display |
| Inventory OOS | Best effort (~10s) | Trade-off: speed vs oversell risk |

### Scalability Considerations
- **Search**: Horizontal scaling by adding ES data nodes, query routing by category
- **Catalog**: Read replicas scale reads, sharding by category for writes
- **Personalization**: Per-user data in DynamoDB (single-digit ms at any scale)
- **Images**: S3 + CloudFront, no scaling concern

### Multi-Region
- **Active-Active**: Search + PDP served from nearest region
- **Active-Passive**: Catalog writes go to primary region, async replicated
- **Conflict Resolution**: Last-writer-wins for seller updates, version vector for inventory

## 11. Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| Product DB | PostgreSQL (Citus) | ACID + JSON + horizontal scale |
| Search Engine | Elasticsearch | Full-text + facets + aggregations |
| Cache | Redis Cluster | Sub-ms latency, data structures |
| Event Bus | Apache Kafka | Durable, ordered, replayable events |
| Stream Processing | Apache Flink | Stateful stream processing, exactly-once |
| Object Storage | S3 | Unlimited scale for images |
| CDN | CloudFront | Global edge caching |
| User Data | DynamoDB | Key-value at scale for personalization |
| ML Models | SageMaker | Model serving for ranking |
| Monitoring | Prometheus + Grafana | Industry standard observability |
