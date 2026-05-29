# Multi-Tenant SaaS Platform

## 1. Requirements

### Functional Requirements
- **Tenant Provisioning**: Self-service signup with automated resource setup
- **Isolation Models**: Support shared DB, shared schema, and dedicated instance models
- **Tenant-Aware Routing**: Route requests to correct tenant context based on domain/header/JWT
- **Per-Tenant Configuration**: Custom branding, feature toggles, limits per tenant
- **Usage Metering + Billing**: Track resource consumption, enforce quotas, generate invoices
- **Data Residency**: Store tenant data in specified geographic regions
- **Tenant Lifecycle**: Trial → Paid → Suspended → Deleted with grace periods
- **Noisy Neighbor Prevention**: Isolate workloads so one tenant can't degrade others

### Non-Functional Requirements
- **Availability**: 99.99% per-tenant SLA (tier-dependent)
- **Latency**: <100ms p99 for tenant context resolution
- **Scale**: 100K tenants, 10M users across tenants, 500K QPS aggregate
- **Isolation**: Complete data isolation (no cross-tenant data leakage)
- **Elasticity**: Scale per-tenant from 0 to millions of requests
- **Compliance**: SOC2, GDPR, HIPAA (for enterprise tenants)

## 2. Capacity Estimation

### Traffic
- Total QPS: 500K aggregate across all tenants
- Top 1% tenants: 50% of traffic (power law distribution)
- Tenant provisioning: 1000 new tenants/day
- Authentication: 50K logins/day

### Storage
- Shared database: 10TB (80% of tenants on shared model)
- Dedicated databases: 200 × 50GB = 10TB (enterprise tenants)
- Configuration store: 100K tenants × 10KB = 1GB
- Usage metering: 500K QPS × 200 bytes × 86400s = 8.6TB/day (pre-aggregation)
- After aggregation: ~100GB/day retained

### Compute
- Shared compute pool: 2000 pods serving shared-model tenants
- Dedicated compute: 200 enterprise tenants × 3 pods = 600 pods
- Metering pipeline: 50 consumers processing 500K events/s

## 3. Data Modeling

### Database Schemas

```sql
-- Tenant Registry (Control Plane)
CREATE TABLE tenants (
    tenant_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    slug                VARCHAR(100) NOT NULL UNIQUE,  -- URL-safe identifier
    custom_domain       VARCHAR(255),
    status              VARCHAR(20) NOT NULL DEFAULT 'TRIAL',
    tier                VARCHAR(20) NOT NULL DEFAULT 'FREE',
    isolation_model     VARCHAR(20) NOT NULL DEFAULT 'POOL',  -- POOL, BRIDGE, SILO
    data_region         VARCHAR(20) NOT NULL DEFAULT 'us-east-1',
    billing_plan_id     UUID,
    trial_ends_at       TIMESTAMPTZ,
    suspended_at        TIMESTAMPTZ,
    deletion_scheduled  TIMESTAMPTZ,
    owner_user_id       UUID NOT NULL,
    settings            JSONB DEFAULT '{}',
    feature_flags       JSONB DEFAULT '{}',
    resource_quotas     JSONB NOT NULL DEFAULT '{
        "max_users": 5,
        "max_storage_gb": 1,
        "max_api_calls_per_month": 10000
    }',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('TRIAL','ACTIVE','SUSPENDED','PENDING_DELETION','DELETED')),
    CHECK (tier IN ('FREE','STARTER','PROFESSIONAL','ENTERPRISE')),
    CHECK (isolation_model IN ('POOL','BRIDGE','SILO'))
);

CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_domain ON tenants(custom_domain) WHERE custom_domain IS NOT NULL;
CREATE INDEX idx_tenants_status ON tenants(status, tier);
CREATE INDEX idx_tenants_region ON tenants(data_region);
CREATE INDEX idx_tenants_deletion ON tenants(deletion_scheduled) WHERE deletion_scheduled IS NOT NULL;

-- Tenant Resource Registry (tracks provisioned resources)
CREATE TABLE tenant_resources (
    resource_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id),
    resource_type       VARCHAR(50) NOT NULL,    -- DATABASE, CACHE, QUEUE, COMPUTE, STORAGE
    resource_identifier VARCHAR(500) NOT NULL,   -- Connection string, ARN, etc.
    region              VARCHAR(20) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'PROVISIONING',
    config              JSONB DEFAULT '{}',
    provisioned_at      TIMESTAMPTZ,
    last_health_check   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_resources_tenant ON tenant_resources(tenant_id, resource_type);
CREATE INDEX idx_resources_status ON tenant_resources(status);

-- Tenant Users
CREATE TABLE tenant_users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id),
    email               VARCHAR(255) NOT NULL,
    display_name        VARCHAR(255),
    role                VARCHAR(50) NOT NULL DEFAULT 'MEMBER',
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

CREATE INDEX idx_tusers_tenant ON tenant_users(tenant_id, status);
CREATE INDEX idx_tusers_email ON tenant_users(email);

-- Usage Metering (time-series, partitioned)
CREATE TABLE usage_events (
    event_id            UUID DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    event_type          VARCHAR(50) NOT NULL,    -- API_CALL, STORAGE, COMPUTE_SECONDS, etc.
    quantity            DECIMAL(20,6) NOT NULL,
    unit                VARCHAR(20) NOT NULL,
    resource_id         VARCHAR(200),
    metadata            JSONB DEFAULT '{}',
    event_time          TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (event_time);

CREATE INDEX idx_usage_tenant_time ON usage_events(tenant_id, event_time DESC);
CREATE INDEX idx_usage_type ON usage_events(event_type, event_time DESC);

-- Usage Aggregations (hourly rollups)
CREATE TABLE usage_aggregations (
    tenant_id           UUID NOT NULL,
    event_type          VARCHAR(50) NOT NULL,
    period_start        TIMESTAMPTZ NOT NULL,
    period_type         VARCHAR(10) NOT NULL,    -- HOURLY, DAILY, MONTHLY
    total_quantity      DECIMAL(20,6) NOT NULL,
    count               BIGINT NOT NULL,
    metadata            JSONB DEFAULT '{}',
    PRIMARY KEY (tenant_id, event_type, period_start, period_type)
);

CREATE INDEX idx_agg_period ON usage_aggregations(period_start, period_type);

-- Billing
CREATE TABLE billing_subscriptions (
    subscription_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id),
    plan_id             UUID NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end  TIMESTAMPTZ NOT NULL,
    stripe_subscription_id VARCHAR(100),
    monthly_base_amount DECIMAL(10,2),
    currency            VARCHAR(3) DEFAULT 'USD',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_billing_tenant ON billing_subscriptions(tenant_id, status);

-- Invoices
CREATE TABLE invoices (
    invoice_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    subscription_id     UUID REFERENCES billing_subscriptions(subscription_id),
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    base_amount         DECIMAL(10,2) NOT NULL,
    usage_amount        DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount        DECIMAL(10,2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'USD',
    status              VARCHAR(20) DEFAULT 'DRAFT',
    line_items          JSONB NOT NULL DEFAULT '[]',
    stripe_invoice_id   VARCHAR(100),
    paid_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invoices_tenant ON invoices(tenant_id, period_start DESC);

-- Row-Level Security Policies (for shared database model)
-- Applied on application tables:

-- Example: shared 'documents' table
CREATE TABLE documents (
    document_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,           -- TENANT DISCRIMINATOR
    title               VARCHAR(500) NOT NULL,
    content             TEXT,
    created_by          UUID NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Policy: tenants can only see their own rows
CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Force RLS for all users except superuser
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

CREATE INDEX idx_documents_tenant ON documents(tenant_id, created_at DESC);
```

### Kafka Topics

```yaml
topics:
  tenant-provisioning-events:
    partitions: 16
    replication-factor: 3
    retention.ms: 604800000

  tenant-usage-events:
    partitions: 128                # High throughput
    replication-factor: 3
    retention.ms: 86400000
    max.message.bytes: 1048576

  tenant-lifecycle-events:
    partitions: 16
    replication-factor: 3
    retention.ms: -1              # Infinite
    cleanup.policy: compact

  tenant-billing-events:
    partitions: 32
    replication-factor: 3
    retention.ms: 2592000000     # 30 days
```

### Redis Configuration

```yaml
redis:
  tenant-context:
    cluster: true
    nodes: 6
    maxmemory: 8gb
    maxmemory-policy: allkeys-lru
    data-structures:
      - hash: "tenant:{tenant_id}:config"
      - hash: "tenant:{tenant_id}:quotas"
      - string: "tenant:domain:{domain}"       # domain → tenant_id
      - string: "tenant:slug:{slug}"           # slug → tenant_id

  rate-limiting:
    cluster: true
    nodes: 6
    maxmemory: 4gb
    maxmemory-policy: volatile-ttl
    data-structures:
      - sorted-set: "rate:{tenant_id}:{resource}"  # Sliding window
      - hash: "quota:{tenant_id}:usage"             # Current period usage
```

## 4. High-Level Design

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          MULTI-TENANT SaaS PLATFORM                                    │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  Tenant Access Points:                                                                │
│  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐                         │
│  │ tenant1.app  │  │ custom.domain.com │  │ api.app/v1      │                         │
│  │ (subdomain)  │  │ (custom domain)   │  │ (X-Tenant-ID)   │                         │
│  └──────┬───────┘  └────────┬──────────┘  └────────┬────────┘                         │
│         └────────────────────┴──────────────────────┘                                  │
│                              │                                                          │
│                              ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                        Edge / Ingress Layer                                       │  │
│  │  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  ┌───────────────┐  │  │
│  │  │ CDN/WAF      │  │ Tenant Resolver │  │ Rate Limiter    │  │ Auth Gateway  │  │  │
│  │  │ (CloudFront) │  │ (domain→tenant) │  │ (per-tenant)    │  │               │  │  │
│  │  └──────────────┘  └────────────────┘  └─────────────────┘  └───────────────┘  │  │
│  └───────────────────────────────────────────┬─────────────────────────────────────┘  │
│                                              │                                          │
│                    ┌─────────────────────────┼──────────────────────────┐               │
│                    ▼                         ▼                          ▼               │
│  ┌────────────────────┐   ┌────────────────────────┐   ┌────────────────────────┐     │
│  │  Pool Model (80%)   │   │  Bridge Model (15%)    │   │  Silo Model (5%)       │     │
│  │  (Shared everything)│   │  (Shared compute,     │   │  (Dedicated everything)│     │
│  │                     │   │   dedicated data)      │   │                        │     │
│  │  ┌───────────────┐ │   │  ┌───────────────┐    │   │  ┌───────────────┐     │     │
│  │  │Shared Compute │ │   │  │Shared Compute │    │   │  │Dedicated Pods │     │     │
│  │  │(K8s Pods)     │ │   │  │(K8s Pods)     │    │   │  │(Namespace)    │     │     │
│  │  └───────┬───────┘ │   │  └───────┬───────┘    │   │  └───────┬───────┘     │     │
│  │          │          │   │          │            │   │          │              │     │
│  │  ┌───────▼───────┐ │   │  ┌───────▼───────┐    │   │  ┌───────▼───────┐     │     │
│  │  │Shared DB      │ │   │  │Dedicated DB   │    │   │  │Dedicated DB   │     │     │
│  │  │(tenant_id col)│ │   │  │(per-tenant)   │    │   │  │(dedicated RDS)│     │     │
│  │  │+ RLS          │ │   │  │               │    │   │  │               │     │     │
│  │  └───────────────┘ │   │  └───────────────┘    │   │  └───────────────┘     │     │
│  └────────────────────┘   └────────────────────────┘   └────────────────────────┘     │
│                                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Control Plane                                             │  │
│  │  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────────┐  │  │
│  │  │ Provisioning │  │ Billing &     │  │ Lifecycle    │  │ Quota             │  │  │
│  │  │ Service      │  │ Metering      │  │ Manager      │  │ Enforcement       │  │  │
│  │  └──────────────┘  └───────────────┘  └──────────────┘  └───────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Observability (per-tenant metrics)                        │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 5. Low-Level Design (APIs)

### Tenant Management APIs

```yaml
# Create Tenant (Self-Service Signup)
POST /api/v1/tenants
Request:
  {
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "owner_email": "admin@acme.com",
    "tier": "STARTER",
    "data_region": "eu-west-1",
    "settings": {
      "branding": { "logo_url": "...", "primary_color": "#2563eb" },
      "features": { "sso_enabled": false, "api_access": true }
    }
  }
Response: 201
  {
    "tenant_id": "tnt_a1b2c3d4",
    "slug": "acme-corp",
    "status": "PROVISIONING",
    "access_url": "https://acme-corp.app.example.com",
    "trial_ends_at": "2024-02-15T00:00:00Z",
    "provisioning_status": {
      "database": "CREATING",
      "cache": "PENDING",
      "dns": "PENDING"
    }
  }

# Get Tenant Context (internal, called by services)
GET /internal/v1/tenants/resolve?domain=acme-corp.app.example.com
Response: 200
  {
    "tenant_id": "tnt_a1b2c3d4",
    "isolation_model": "POOL",
    "data_region": "eu-west-1",
    "tier": "STARTER",
    "status": "ACTIVE",
    "db_connection": "pool://shared-eu-west-1",
    "feature_flags": { "new_dashboard": true },
    "rate_limits": { "api_rpm": 1000, "burst": 100 },
    "quotas": { "max_users": 50, "max_storage_gb": 10 }
  }

# Usage Report
GET /api/v1/tenants/{tenant_id}/usage?period=2024-01
Response: 200
  {
    "tenant_id": "tnt_a1b2c3d4",
    "period": "2024-01",
    "usage": {
      "api_calls": { "total": 45231, "quota": 100000, "percent": 45.2 },
      "storage_gb": { "total": 3.7, "quota": 10, "percent": 37.0 },
      "users": { "total": 12, "quota": 50, "percent": 24.0 },
      "compute_hours": { "total": 156.3, "included": 200, "overage": 0 }
    },
    "estimated_bill": {
      "base": 49.00,
      "usage_charges": 0.00,
      "total": 49.00,
      "currency": "USD"
    }
  }

# Tenant Lifecycle Transition
POST /api/v1/tenants/{tenant_id}/lifecycle
Request:
  {
    "action": "SUSPEND",
    "reason": "Payment failure after 3 retries",
    "grace_period_days": 14
  }
Response: 200
  {
    "tenant_id": "tnt_a1b2c3d4",
    "previous_status": "ACTIVE",
    "new_status": "SUSPENDED",
    "suspended_at": "2024-01-15T10:00:00Z",
    "deletion_scheduled": "2024-01-29T10:00:00Z",
    "access_restricted": true,
    "data_retained": true
  }
```

## 6. Deep Dive: Isolation Strategies

### Isolation Models Comparison

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    ISOLATION MODELS TRADE-OFF MATRIX                         │
├────────────┬──────────────────┬──────────────────┬─────────────────────────┤
│ Dimension  │ Pool Model       │ Bridge Model     │ Silo Model              │
├────────────┼──────────────────┼──────────────────┼─────────────────────────┤
│ Compute    │ Shared pods      │ Shared pods      │ Dedicated pods/NS       │
│ Database   │ Shared DB+Schema │ Dedicated DB     │ Dedicated DB instance   │
│ Cache      │ Shared Redis     │ Shared Redis     │ Dedicated Redis         │
│ Network    │ Shared VPC       │ Shared VPC       │ Dedicated VPC/Subnet    │
│ Cost/Tenant│ $0.50-5/mo       │ $20-100/mo       │ $500-5000/mo            │
│ Isolation  │ Logical (RLS)    │ Physical (data)  │ Full physical           │
│ Compliance │ SOC2             │ SOC2, HIPAA      │ SOC2, HIPAA, FedRAMP    │
│ Scale Limit│ 100K tenants     │ 10K tenants      │ 500 tenants             │
│ Noisy Nbr  │ High risk        │ Medium (data OK) │ None                    │
│ Migration  │ Easy up          │ Moderate         │ N/A (already max)       │
│ Onboarding │ <1 second        │ 2-5 minutes      │ 15-60 minutes           │
│ Data Region│ Shared region    │ Per-tenant region│ Per-tenant anything     │
└────────────┴──────────────────┴──────────────────┴─────────────────────────┘
```

### Pool Model Implementation (Shared DB with RLS)

```python
from contextvars import ContextVar
from sqlalchemy import event
from sqlalchemy.orm import Session

# Thread-safe tenant context
_current_tenant: ContextVar[str] = ContextVar('current_tenant')

class TenantContext:
    """
    Manages tenant context propagation across the request lifecycle.
    Sets PostgreSQL session variable for RLS enforcement.
    """
    
    @staticmethod
    def set_tenant(tenant_id: str):
        _current_tenant.set(tenant_id)
    
    @staticmethod
    def get_tenant() -> str:
        try:
            return _current_tenant.get()
        except LookupError:
            raise TenantContextMissing("No tenant context set")
    
    @staticmethod
    def clear():
        _current_tenant.set(None)


class TenantAwareSessionFactory:
    """SQLAlchemy session that automatically sets tenant context."""
    
    def __init__(self, engine):
        self.engine = engine
        
        # Set tenant_id on every connection checkout
        @event.listens_for(engine, "checkout")
        def set_tenant_on_checkout(dbapi_conn, connection_record, connection_proxy):
            pass  # Connection pool event
        
    def create_session(self) -> Session:
        session = Session(bind=self.engine)
        tenant_id = TenantContext.get_tenant()
        
        # Set PostgreSQL session variable for RLS
        session.execute(
            f"SET app.current_tenant_id = '{tenant_id}'"
        )
        return session


class TenantMiddleware:
    """
    ASGI middleware that resolves tenant from request and sets context.
    Must be early in the middleware chain.
    """
    
    def __init__(self, app, tenant_resolver):
        self.app = app
        self.resolver = tenant_resolver
    
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            tenant_id = await self._resolve_tenant(scope)
            
            if not tenant_id:
                await self._send_error(send, 404, "Tenant not found")
                return
            
            # Validate tenant is active
            tenant = await self.resolver.get_tenant(tenant_id)
            if tenant.status == 'SUSPENDED':
                await self._send_error(send, 403, "Tenant suspended")
                return
            
            # Set context for downstream
            TenantContext.set_tenant(tenant_id)
            scope['state']['tenant'] = tenant
            
            try:
                await self.app(scope, receive, send)
            finally:
                TenantContext.clear()
    
    async def _resolve_tenant(self, scope) -> Optional[str]:
        """
        Resolution order:
        1. Custom domain → tenant mapping
        2. Subdomain extraction (tenant.app.example.com)
        3. X-Tenant-ID header (API clients)
        4. JWT claim (authenticated requests)
        """
        headers = dict(scope.get('headers', []))
        host = headers.get(b'host', b'').decode()
        
        # 1. Custom domain
        tenant_id = await self.resolver.resolve_by_domain(host)
        if tenant_id:
            return tenant_id
        
        # 2. Subdomain
        if host.endswith('.app.example.com'):
            slug = host.split('.')[0]
            return await self.resolver.resolve_by_slug(slug)
        
        # 3. Header
        tenant_header = headers.get(b'x-tenant-id')
        if tenant_header:
            return tenant_header.decode()
        
        return None
```

### Cross-Service Tenant Propagation

```python
class TenantPropagationInterceptor:
    """
    gRPC/HTTP interceptor that propagates tenant context
    across service boundaries via headers.
    """
    
    TENANT_HEADER = "x-tenant-id"
    TENANT_TIER_HEADER = "x-tenant-tier"
    TENANT_REGION_HEADER = "x-tenant-region"
    
    def intercept_outgoing(self, request):
        """Add tenant context to outgoing requests."""
        tenant_id = TenantContext.get_tenant()
        request.headers[self.TENANT_HEADER] = tenant_id
        
        # Propagate tier for downstream priority decisions
        tenant = TenantContext.get_tenant_metadata()
        if tenant:
            request.headers[self.TENANT_TIER_HEADER] = tenant.tier
            request.headers[self.TENANT_REGION_HEADER] = tenant.data_region
        
        return request
    
    def intercept_incoming(self, request):
        """Extract tenant context from incoming requests."""
        tenant_id = request.headers.get(self.TENANT_HEADER)
        if tenant_id:
            TenantContext.set_tenant(tenant_id)
        return request
```

## 7. Deep Dive: Request Routing and Context Propagation

### Tenant-Aware Load Balancer

```python
class TenantAwareRouter:
    """
    Routes requests to appropriate backend based on tenant isolation model.
    - Pool tenants → shared service fleet
    - Bridge tenants → shared compute, dedicated DB endpoint
    - Silo tenants → dedicated namespace/cluster
    """
    
    def __init__(self, tenant_registry, service_discovery):
        self.registry = tenant_registry
        self.discovery = service_discovery
    
    async def route(self, request) -> RoutingDecision:
        tenant = request.state.tenant
        
        if tenant.isolation_model == 'SILO':
            # Route to dedicated namespace
            endpoints = await self.discovery.get_endpoints(
                service='api',
                namespace=f"tenant-{tenant.tenant_id}"
            )
            return RoutingDecision(
                endpoints=endpoints,
                db_connection=tenant.dedicated_db_url,
                cache_prefix=f"silo:{tenant.tenant_id}:"
            )
        
        elif tenant.isolation_model == 'BRIDGE':
            # Shared compute, dedicated DB
            endpoints = await self.discovery.get_endpoints(
                service='api',
                namespace='shared',
                region=tenant.data_region
            )
            db_url = await self.registry.get_dedicated_db(tenant.tenant_id)
            return RoutingDecision(
                endpoints=endpoints,
                db_connection=db_url,
                cache_prefix=f"bridge:{tenant.tenant_id}:"
            )
        
        else:  # POOL
            # Everything shared
            endpoints = await self.discovery.get_endpoints(
                service='api',
                namespace='shared',
                region=tenant.data_region
            )
            return RoutingDecision(
                endpoints=endpoints,
                db_connection=f"pool://{tenant.data_region}",
                cache_prefix=f"pool:{tenant.tenant_id}:",
                rls_tenant_id=tenant.tenant_id
            )
```

### Data Region Routing

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Data Residency Routing                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Request → Resolve Tenant → Get data_region → Route to regional DB   │
│                                                                       │
│  ┌──────────────┐                                                    │
│  │ Global Edge  │                                                    │
│  │ (CloudFront) │                                                    │
│  └──────┬───────┘                                                    │
│         │                                                             │
│    ┌────┴─────────────────────────────────┐                          │
│    ▼                ▼                     ▼                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐                      │
│  │us-east-1 │  │eu-west-1 │  │ap-southeast-1│                      │
│  │          │  │          │  │              │                        │
│  │ Compute  │  │ Compute  │  │  Compute     │                      │
│  │ Database │  │ Database │  │  Database    │                      │
│  │ Cache    │  │ Cache    │  │  Cache       │                      │
│  │          │  │          │  │              │                        │
│  │ Tenants: │  │ Tenants: │  │  Tenants:   │                      │
│  │ US-based │  │ EU-based │  │  APAC-based │                      │
│  └──────────┘  └──────────┘  └──────────────┘                      │
│                                                                       │
│  Cross-region ops: Metadata only (tenant registry replicated)        │
│  Data never leaves designated region                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## 8. Deep Dive: Resource Fairness (Noisy Neighbor Prevention)

### Per-Tenant Rate Limiting

```python
import time
import math

class TenantRateLimiter:
    """
    Multi-level rate limiting with tier-based quotas.
    Uses sliding window log algorithm for precision.
    """
    
    TIER_LIMITS = {
        'FREE':          {'rpm': 60,     'burst': 10,   'daily': 10000},
        'STARTER':       {'rpm': 1000,   'burst': 100,  'daily': 100000},
        'PROFESSIONAL':  {'rpm': 10000,  'burst': 1000, 'daily': 1000000},
        'ENTERPRISE':    {'rpm': 100000, 'burst': 10000,'daily': 10000000},
    }
    
    def __init__(self, redis):
        self.redis = redis
    
    async def check_rate_limit(self, tenant_id: str, tier: str) -> RateLimitResult:
        """
        Check rate limit using sliding window.
        Returns: allowed (bool), remaining, retry_after_ms
        """
        limits = self.TIER_LIMITS[tier]
        now = time.time()
        window_start = now - 60  # 1 minute window
        
        key = f"rate:{tenant_id}:rpm"
        
        # Sliding window log with Redis sorted set
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
        pipe.zcard(key)                                # Count in window
        pipe.zadd(key, {f"{now}:{id}": now})          # Add current request
        pipe.expire(key, 120)                          # Cleanup
        
        results = await pipe.execute()
        current_count = results[1]
        
        if current_count >= limits['rpm']:
            # Calculate retry-after
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            retry_after = int((oldest[0][1] + 60 - now) * 1000) if oldest else 1000
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=limits['rpm'],
                retry_after_ms=retry_after
            )
        
        return RateLimitResult(
            allowed=True,
            remaining=limits['rpm'] - current_count - 1,
            limit=limits['rpm'],
            retry_after_ms=0
        )
    
    async def check_quota(self, tenant_id: str, resource: str, tier: str) -> QuotaResult:
        """Check monthly quota for a resource."""
        period_key = time.strftime('%Y-%m')
        quota_key = f"quota:{tenant_id}:{resource}:{period_key}"
        
        current = await self.redis.incr(quota_key)
        if current == 1:
            # First request this period, set expiry
            await self.redis.expire(quota_key, 86400 * 32)  # ~1 month
        
        limit = self.TIER_LIMITS[tier].get(f'{resource}_limit', float('inf'))
        
        if current > limit:
            return QuotaResult(allowed=False, used=current, limit=limit)
        
        return QuotaResult(allowed=True, used=current, limit=limit)


class ResourceQuotaEnforcer:
    """Enforce hard quotas on tenant resources."""
    
    async def enforce_storage_quota(self, tenant_id: str, additional_bytes: int) -> bool:
        """Check if tenant can store additional data."""
        tenant = await self.tenant_store.get(tenant_id)
        quota_gb = tenant.resource_quotas['max_storage_gb']
        
        current_usage = await self.metering.get_current_storage(tenant_id)
        
        if (current_usage + additional_bytes) > (quota_gb * 1024 * 1024 * 1024):
            await self._notify_quota_exceeded(tenant_id, 'storage')
            return False
        
        return True


class PriorityQueueManager:
    """
    Tenant-tier-based priority queuing.
    Enterprise tenants get priority over free tenants for shared resources.
    """
    
    TIER_PRIORITIES = {
        'ENTERPRISE': 1,      # Highest priority
        'PROFESSIONAL': 3,
        'STARTER': 5,
        'FREE': 10            # Lowest priority
    }
    
    async def enqueue_with_priority(self, tenant_id: str, tier: str, job: dict):
        """Enqueue work item with tenant-tier-based priority."""
        priority = self.TIER_PRIORITIES[tier]
        score = time.time() + (priority * 0.001)  # Lower score = higher priority
        
        await self.redis.zadd(
            "work_queue:prioritized",
            {json.dumps({**job, 'tenant_id': tenant_id}): score}
        )
    
    async def dequeue_fair(self) -> Optional[dict]:
        """Dequeue with weighted fair queuing across tenants."""
        # Pop lowest score (highest priority + oldest)
        result = await self.redis.zpopmin("work_queue:prioritized")
        if result:
            return json.loads(result[0][0])
        return None
```

### Compute Isolation with Kubernetes

```yaml
# Per-tenant resource quotas in shared namespace
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-tnt-a1b2c3d4-quota
  namespace: shared-workloads
  labels:
    tenant: tnt-a1b2c3d4
    tier: professional
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"

---
# Network policy for tenant isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-tnt-enterprise-001
spec:
  podSelector:
    matchLabels:
      tenant: tnt-enterprise-001
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-controllers
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: tenant-tnt-enterprise-001
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0  # Allow internet egress
```

## 9. Component Optimization

### Tenant Provisioning Pipeline

```python
class TenantProvisioningOrchestrator:
    """
    Orchestrates tenant onboarding with step-by-step resource creation.
    Uses saga pattern for rollback on failure.
    """
    
    async def provision_tenant(self, request: CreateTenantRequest) -> Tenant:
        saga = ProvisioningSaga()
        
        try:
            # Step 1: Create tenant record
            tenant = await saga.step(
                action=lambda: self.create_tenant_record(request),
                compensate=lambda t: self.delete_tenant_record(t.tenant_id)
            )
            
            # Step 2: Provision database (model-dependent)
            if request.tier in ('ENTERPRISE',):
                db_resource = await saga.step(
                    action=lambda: self.provision_dedicated_db(tenant),
                    compensate=lambda r: self.destroy_database(r)
                )
            else:
                db_resource = await saga.step(
                    action=lambda: self.configure_shared_db(tenant),
                    compensate=lambda r: self.remove_shared_config(r)
                )
            
            # Step 3: Setup DNS
            await saga.step(
                action=lambda: self.configure_dns(tenant),
                compensate=lambda: self.remove_dns(tenant)
            )
            
            # Step 4: Initialize cache
            await saga.step(
                action=lambda: self.setup_cache_namespace(tenant),
                compensate=lambda: self.teardown_cache(tenant)
            )
            
            # Step 5: Create admin user
            await saga.step(
                action=lambda: self.create_owner_account(tenant, request.owner_email),
                compensate=lambda u: self.delete_user(u)
            )
            
            # Step 6: Apply default configuration
            await self.apply_tier_defaults(tenant)
            
            # Mark as active
            tenant.status = 'ACTIVE' if request.tier != 'FREE' else 'TRIAL'
            await self.tenant_store.update(tenant)
            
            # Emit event
            await self.events.publish('tenant-provisioning-events', {
                'type': 'TENANT_PROVISIONED',
                'tenant_id': tenant.tenant_id,
                'tier': tenant.tier,
                'region': tenant.data_region
            })
            
            return tenant
            
        except Exception as e:
            await saga.rollback()
            raise ProvisioningError(f"Failed to provision tenant: {e}")
```

## 10. Observability

### Metrics

```yaml
metrics:
  - tenant.requests.total:           Counter (tags: tenant_id, tier, endpoint)
  - tenant.requests.latency_ms:      Histogram (tags: tenant_id, tier)
  - tenant.rate_limit.exceeded:      Counter (tags: tenant_id, tier)
  - tenant.quota.usage_percent:      Gauge (tags: tenant_id, resource)
  - tenant.provisioning.duration_ms: Histogram (tags: tier, isolation_model)
  - tenant.provisioning.failures:    Counter (tags: step, error_type)
  - tenant.lifecycle.transitions:    Counter (tags: from_status, to_status)
  - tenant.billing.mrr:              Gauge (tags: tier)
  - tenant.storage.bytes:            Gauge (tags: tenant_id, tier)
  - tenant.active_users:             Gauge (tags: tenant_id)
  - tenant.noisy_neighbor.score:     Gauge (tags: tenant_id)  # 0-100

alerts:
  - name: TenantQuotaExceeded
    condition: tenant.quota.usage_percent > 95
    severity: warning
  - name: NoisyNeighborDetected
    condition: tenant.noisy_neighbor.score > 80 for 5m
    severity: critical
  - name: ProvisioningStuck
    condition: tenant status=PROVISIONING for >10m
    severity: warning
```

## 11. Considerations

### Trade-offs
| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Default isolation | Pool with RLS | Schema-per-tenant | Cost efficiency for 80% of tenants (small workloads) |
| Tenant resolution | Redis cache + DB | DNS-based routing | Flexibility (header/domain/subdomain), <1ms lookup |
| Rate limiting | Sliding window log | Token bucket | Precision, no burst beyond limit |
| Metering | Kafka + hourly rollups | Real-time counting | Cost, supports high-volume events without read pressure |
| Provisioning | Async saga | Synchronous | Long operations (DB creation), compensating transactions |

### Data Isolation Guarantees
- Pool: RLS enforced at DB level (not just application) + periodic audit queries
- All SQL queries include WHERE tenant_id = ? (ORM middleware enforces)
- Cross-tenant query detection: query analyzer rejects queries missing tenant filter
- Penetration testing: automated cross-tenant access tests in CI

### Tenant Migration (Pool → Bridge → Silo)
1. Snapshot tenant data from shared DB
2. Provision dedicated resources
3. Restore data to dedicated DB
4. Update routing table (atomic switch)
5. Verify data integrity
6. Remove from shared DB (after confirmation period)

### Failure Handling
- Tenant DB unavailable: Return 503 with retry-after (don't cascade to other tenants)
- Rate limiter Redis down: Fall back to local in-memory approximation (permissive)
- Provisioning failure: Saga rollback + alert ops + tenant stays in PROVISIONING
- Noisy neighbor: Auto-throttle to tier limits, alert, offer upgrade path
