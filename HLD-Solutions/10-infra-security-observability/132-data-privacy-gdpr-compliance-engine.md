# Data Privacy / GDPR Compliance Engine

## 1. Functional Requirements

| # | Requirement | Details |
|---|-------------|---------|
| FR-1 | Consent Management | Purpose-based granular consent (marketing, analytics, personalization, third-party sharing) with versioned consent receipts |
| FR-2 | Data Subject Access Requests (DSAR) | Right-to-erasure, right-to-portability (machine-readable export), right-to-rectification, right-to-restrict-processing |
| FR-3 | PII Discovery & Classification | Automated scanning across all data stores (RDBMS, NoSQL, object storage, logs, analytics), tagging with sensitivity levels |
| FR-4 | Data Retention Policy Enforcement | Per-purpose retention schedules, automated purge workflows, legal hold override |
| FR-5 | Breach Notification Workflow | Detection → Impact Assessment → 72-hour DPA notification → affected user notification |
| FR-6 | Privacy Impact Assessments (DPIA) | Template-driven assessments, risk scoring, DPO approval workflow |
| FR-7 | Cross-Border Transfer Compliance | SCCs, BCRs, adequacy decision tracking, transfer impact assessments |
| FR-8 | Consent Audit Trail | Immutable log of all consent changes with timestamp, source, version |
| FR-9 | Data Inventory / Record of Processing | Article 30 compliant records of processing activities |
| FR-10 | Privacy-by-Design Enforcement | Pre-deployment privacy checks in CI/CD pipelines |

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.99% (consent serving path) |
| DSAR Fulfillment | < 72 hours automated (regulatory max 30 days) |
| Data Store Coverage | Scan 1000+ heterogeneous data stores |
| User Scale | 500M+ data subjects |
| Consent Lookup Latency | < 10ms P99 |
| PII Scan Throughput | 10 TB/hour |
| Audit Log Retention | 7 years immutable |
| Encryption | AES-256 at rest, TLS 1.3 in transit |
| Compliance Frameworks | GDPR, CCPA, LGPD, PIPA, PIPEDA |

## 3. Capacity Estimation

```
Users: 500M data subjects
Consent records: 500M users × 8 purposes = 4B consent records
  - Each record ~500 bytes → 2 TB consent store
  - Consent changes: 1% daily = 40M events/day → ~460 events/sec

DSAR Requests:
  - 0.01% users/month = 50K DSARs/month → ~1700/day → ~1.2/sec
  - Each DSAR touches avg 50 systems → 85K system queries/day

PII Discovery:
  - 1000 data stores, avg 1TB each = 1 PB total
  - Full scan cycle: 30 days → ~33 TB/day scanning throughput
  - Incremental scan (CDC): ~5% change/day = 50 TB incremental/day

Consent Lookups:
  - Every API call checks consent: 100K RPS at peak
  - Cache hit ratio target: 99%+ → 1K RPS to consent store

Storage:
  - Consent store: 2 TB
  - Data inventory: 500 GB (metadata across all stores)
  - Audit logs: 10 TB/year
  - DSAR artifacts: 5 TB/year (exports)
  - Total: ~20 TB/year growing
```

## 4. Data Modeling

### 4.1 Consent Records

```sql
CREATE TABLE consent_records (
    consent_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    purpose             VARCHAR(50) NOT NULL,  -- 'marketing', 'analytics', 'personalization', 'third_party'
    legal_basis         VARCHAR(30) NOT NULL,  -- 'consent', 'legitimate_interest', 'contract', 'legal_obligation'
    status              VARCHAR(20) NOT NULL,  -- 'granted', 'withdrawn', 'expired'
    granted_at          TIMESTAMPTZ NOT NULL,
    withdrawn_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    consent_version     INTEGER NOT NULL DEFAULT 1,
    policy_version      VARCHAR(20) NOT NULL,  -- links to privacy policy version
    collection_method   VARCHAR(30) NOT NULL,  -- 'web_form', 'api', 'sdk', 'verbal', 'paper'
    source_ip           INET,
    user_agent          TEXT,
    third_party_id      UUID,                  -- if consent is for specific third party
    data_categories     JSONB NOT NULL,        -- ["email", "location", "browsing_history"]
    processing_activities JSONB NOT NULL,      -- ["email_campaigns", "ad_targeting"]
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consent_user_purpose ON consent_records(user_id, purpose, status);
CREATE INDEX idx_consent_user_active ON consent_records(user_id) WHERE status = 'granted';
CREATE INDEX idx_consent_expiry ON consent_records(expires_at) WHERE status = 'granted';
CREATE INDEX idx_consent_purpose_status ON consent_records(purpose, status);
CREATE INDEX idx_consent_created ON consent_records(created_at);

-- Consent change audit log (append-only)
CREATE TABLE consent_audit_log (
    log_id              BIGSERIAL PRIMARY KEY,
    consent_id          UUID NOT NULL REFERENCES consent_records(consent_id),
    user_id             UUID NOT NULL,
    action              VARCHAR(20) NOT NULL,  -- 'grant', 'withdraw', 'expire', 'update'
    previous_status     VARCHAR(20),
    new_status          VARCHAR(20) NOT NULL,
    changed_by          VARCHAR(50) NOT NULL,  -- 'user', 'system', 'dpo', 'api'
    change_reason       TEXT,
    event_timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_metadata      JSONB DEFAULT '{}'
);

CREATE INDEX idx_audit_user ON consent_audit_log(user_id, event_timestamp DESC);
CREATE INDEX idx_audit_consent ON consent_audit_log(consent_id, event_timestamp DESC);
```

### 4.2 Data Inventory

```sql
CREATE TABLE data_stores (
    store_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_name          VARCHAR(200) NOT NULL,
    store_type          VARCHAR(50) NOT NULL,  -- 'postgresql', 'mongodb', 'elasticsearch', 's3', 'redis', 'kafka'
    connection_config   JSONB NOT NULL,        -- encrypted connection details
    owner_team          VARCHAR(100) NOT NULL,
    data_controller     VARCHAR(200) NOT NULL,
    processing_purposes JSONB NOT NULL,
    legal_basis         JSONB NOT NULL,
    cross_border        BOOLEAN DEFAULT FALSE,
    transfer_mechanism  VARCHAR(50),           -- 'scc', 'bcr', 'adequacy', 'derogation'
    last_scan_at        TIMESTAMPTZ,
    scan_status         VARCHAR(20) DEFAULT 'pending',
    classification      VARCHAR(20) DEFAULT 'unclassified',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE pii_findings (
    finding_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id            UUID NOT NULL REFERENCES data_stores(store_id),
    table_or_collection VARCHAR(200) NOT NULL,
    column_or_field     VARCHAR(200) NOT NULL,
    pii_type            VARCHAR(50) NOT NULL,  -- 'email', 'ssn', 'phone', 'name', 'address', 'dob', 'ip', 'biometric'
    sensitivity_level   VARCHAR(20) NOT NULL,  -- 'low', 'medium', 'high', 'critical'
    detection_method    VARCHAR(30) NOT NULL,  -- 'regex', 'ner_model', 'fingerprint', 'manual'
    confidence_score    DECIMAL(5,4) NOT NULL, -- 0.0000 to 1.0000
    sample_count        INTEGER,
    total_records       BIGINT,
    is_encrypted        BOOLEAN DEFAULT FALSE,
    is_pseudonymized    BOOLEAN DEFAULT FALSE,
    encryption_key_id   UUID,
    discovered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by         VARCHAR(100),
    verified_at         TIMESTAMPTZ,
    status              VARCHAR(20) DEFAULT 'active'  -- 'active', 'remediated', 'false_positive'
);

CREATE INDEX idx_findings_store ON pii_findings(store_id, pii_type);
CREATE INDEX idx_findings_type ON pii_findings(pii_type, sensitivity_level);
CREATE INDEX idx_findings_unverified ON pii_findings(status) WHERE verified_at IS NULL;
```

### 4.3 DSAR State Machine

```sql
CREATE TABLE dsar_requests (
    request_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    request_type        VARCHAR(30) NOT NULL,  -- 'access', 'erasure', 'portability', 'rectification', 'restriction'
    status              VARCHAR(30) NOT NULL DEFAULT 'received',
    -- States: received → identity_verified → processing → systems_queried → 
    --         review → completed | rejected | partially_completed
    identity_verified   BOOLEAN DEFAULT FALSE,
    verification_method VARCHAR(30),
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at         TIMESTAMPTZ,
    processing_started  TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    deadline_at         TIMESTAMPTZ NOT NULL,  -- regulatory deadline (30 days)
    extended_deadline   TIMESTAMPTZ,           -- extension allowed (60 more days)
    extension_reason    TEXT,
    assigned_to         UUID,
    priority            VARCHAR(10) DEFAULT 'normal',
    systems_total       INTEGER DEFAULT 0,
    systems_completed   INTEGER DEFAULT 0,
    systems_failed      INTEGER DEFAULT 0,
    result_location     TEXT,                  -- S3 path for export artifacts
    rejection_reason    TEXT,
    notes               TEXT,
    metadata            JSONB DEFAULT '{}'
);

CREATE INDEX idx_dsar_user ON dsar_requests(user_id, submitted_at DESC);
CREATE INDEX idx_dsar_status ON dsar_requests(status, deadline_at);
CREATE INDEX idx_dsar_deadline ON dsar_requests(deadline_at) WHERE status NOT IN ('completed', 'rejected');
CREATE INDEX idx_dsar_assigned ON dsar_requests(assigned_to, status);

CREATE TABLE dsar_system_tasks (
    task_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          UUID NOT NULL REFERENCES dsar_requests(request_id),
    store_id            UUID NOT NULL REFERENCES data_stores(store_id),
    task_type           VARCHAR(30) NOT NULL,  -- 'extract', 'delete', 'rectify', 'restrict'
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- States: pending → in_progress → completed | failed | skipped
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    retry_count         INTEGER DEFAULT 0,
    max_retries         INTEGER DEFAULT 3,
    error_message       TEXT,
    records_processed   BIGINT DEFAULT 0,
    verification_hash   TEXT,                  -- hash proving deletion/modification
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_request ON dsar_system_tasks(request_id, status);
CREATE INDEX idx_task_store ON dsar_system_tasks(store_id, status);
CREATE INDEX idx_task_pending ON dsar_system_tasks(status, created_at) WHERE status = 'pending';
```

### 4.4 Retention Policies

```sql
CREATE TABLE retention_policies (
    policy_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name         VARCHAR(200) NOT NULL,
    data_category       VARCHAR(100) NOT NULL,
    purpose             VARCHAR(100) NOT NULL,
    retention_days      INTEGER NOT NULL,
    legal_basis         VARCHAR(50) NOT NULL,
    applicable_stores   JSONB NOT NULL,        -- list of store_ids
    purge_method        VARCHAR(30) NOT NULL,  -- 'hard_delete', 'crypto_shred', 'anonymize', 'pseudonymize'
    legal_hold_exempt   BOOLEAN DEFAULT FALSE,
    active              BOOLEAN DEFAULT TRUE,
    approved_by         UUID NOT NULL,
    approved_at         TIMESTAMPTZ NOT NULL,
    effective_from      DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE retention_executions (
    execution_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id           UUID NOT NULL REFERENCES retention_policies(policy_id),
    store_id            UUID NOT NULL,
    execution_date      DATE NOT NULL,
    records_evaluated   BIGINT NOT NULL,
    records_purged      BIGINT NOT NULL,
    records_held        BIGINT DEFAULT 0,     -- legal hold
    execution_time_ms   INTEGER NOT NULL,
    status              VARCHAR(20) NOT NULL,
    error_details       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_retention_exec_policy ON retention_executions(policy_id, execution_date DESC);
CREATE INDEX idx_retention_exec_date ON retention_executions(execution_date, status);
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA PRIVACY / GDPR COMPLIANCE ENGINE                           │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌───────────────────┐ │
│  │  User/Data   │    │  DPO/Privacy     │    │  Engineering     │    │  Regulatory       │ │
│  │  Subject     │    │  Team Console    │    │  Teams           │    │  Authorities      │ │
│  └──────┬───────┘    └────────┬─────────┘    └────────┬─────────┘    └────────┬──────────┘ │
│         │                     │                       │                       │            │
│  ┌──────▼─────────────────────▼───────────────────────▼───────────────────────▼──────────┐ │
│  │                            API GATEWAY (OAuth2 + mTLS)                                 │ │
│  │                    Rate Limiting │ Audit Logging │ Request Validation                  │ │
│  └───────┬──────────────┬───────────────┬────────────────┬──────────────┬────────────────┘ │
│          │              │               │                │              │                   │
│  ┌───────▼────┐  ┌──────▼──────┐  ┌────▼─────┐  ┌──────▼──────┐  ┌───▼──────────┐       │
│  │  Consent   │  │   DSAR      │  │   PII    │  │  Retention  │  │   Breach     │       │
│  │  Service   │  │Orchestrator │  │ Scanner  │  │  Enforcer   │  │  Notifier    │       │
│  └───────┬────┘  └──────┬──────┘  └────┬─────┘  └──────┬──────┘  └───┬──────────┘       │
│          │              │               │                │              │                   │
│  ┌───────▼────┐  ┌──────▼──────┐  ┌────▼─────┐  ┌──────▼──────┐  ┌───▼──────────┐       │
│  │  Consent   │  │  Per-System │  │   Data   │  │   Purge     │  │  Notification│       │
│  │  Store     │  │  Adapters   │  │Inventory │  │  Scheduler  │  │  Queue       │       │
│  │ (Postgres) │  │(50+ types)  │  │  (ES)    │  │  (Cron)     │  │  (SES/SNS)   │       │
│  └───────┬────┘  └──────┬──────┘  └────┬─────┘  └──────┬──────┘  └──────────────┘       │
│          │              │               │                │                                  │
│  ┌───────▼──────────────▼───────────────▼────────────────▼──────────────────────────────┐  │
│  │                              KAFKA EVENT BUS                                          │  │
│  │  Topics: consent.changes │ dsar.events │ pii.discoveries │ retention.executions      │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│          │              │               │                │                                  │
│  ┌───────▼──────────────▼───────────────▼────────────────▼──────────────────────────────┐  │
│  │                        DOWNSTREAM SYSTEM ADAPTERS                                     │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │  │
│  │  │PostgreSQL│ │MongoDB  │ │  S3/    │ │Elastic- │ │  Redis  │ │Analytics│          │  │
│  │  │ Adapter │ │ Adapter │ │  GCS   │ │ search  │ │ Adapter │ │ Adapter │          │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                          CRYPTO KEY MANAGEMENT (HSM-backed)                           │  │
│  │           Per-User Encryption Keys │ Key Rotation │ Crypto-Shredding                 │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              AUDIT & COMPLIANCE STORE                                 │  │
│  │        Immutable Append-Only Log │ Tamper Detection │ 7-Year Retention               │  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) – APIs

### 6.1 Consent Management APIs

```
POST /api/v1/consent
Request:
{
    "user_id": "uuid-123",
    "consents": [
        {
            "purpose": "marketing",
            "status": "granted",
            "data_categories": ["email", "name", "preferences"],
            "processing_activities": ["email_campaigns", "push_notifications"],
            "third_party_id": null,
            "expires_at": "2025-12-31T23:59:59Z"
        },
        {
            "purpose": "analytics",
            "status": "granted",
            "data_categories": ["browsing_history", "location"],
            "processing_activities": ["usage_analytics", "product_improvement"]
        }
    ],
    "policy_version": "v2.3",
    "collection_method": "web_form"
}
Response (201):
{
    "consent_receipt_id": "receipt-uuid-456",
    "consents": [
        {"consent_id": "uuid-c1", "purpose": "marketing", "status": "granted", "recorded_at": "2024-01-15T10:30:00Z"},
        {"consent_id": "uuid-c2", "purpose": "analytics", "status": "granted", "recorded_at": "2024-01-15T10:30:00Z"}
    ],
    "receipt_hash": "sha256:abc123..."
}

GET /api/v1/consent/{user_id}?purpose=marketing&active_only=true
Response (200):
{
    "user_id": "uuid-123",
    "consents": [
        {
            "consent_id": "uuid-c1",
            "purpose": "marketing",
            "status": "granted",
            "granted_at": "2024-01-15T10:30:00Z",
            "expires_at": "2025-12-31T23:59:59Z",
            "data_categories": ["email", "name", "preferences"],
            "policy_version": "v2.3"
        }
    ]
}

DELETE /api/v1/consent/{user_id}/{purpose}
Request:
{
    "withdrawal_reason": "no_longer_interested",
    "effective_immediately": true
}
Response (200):
{
    "consent_id": "uuid-c1",
    "status": "withdrawn",
    "withdrawn_at": "2024-03-01T14:00:00Z",
    "propagation_status": "in_progress",
    "affected_systems": ["email_service", "analytics_pipeline", "ad_platform"]
}
```

### 6.2 DSAR APIs

```
POST /api/v1/dsar
Request:
{
    "user_id": "uuid-123",
    "request_type": "erasure",
    "identity_proof": {
        "method": "email_otp",
        "verification_token": "verified-token-xyz"
    },
    "scope": {
        "include_backups": true,
        "include_third_parties": true,
        "exclude_legal_obligations": true
    },
    "preferred_format": "json"  // for portability
}
Response (202):
{
    "request_id": "dsar-uuid-789",
    "status": "identity_verified",
    "estimated_completion": "2024-01-17T10:30:00Z",
    "deadline": "2024-02-14T10:30:00Z",
    "systems_to_process": 47,
    "tracking_url": "https://privacy.example.com/track/dsar-uuid-789"
}

GET /api/v1/dsar/{request_id}/status
Response (200):
{
    "request_id": "dsar-uuid-789",
    "status": "processing",
    "progress": {
        "systems_total": 47,
        "systems_completed": 32,
        "systems_in_progress": 8,
        "systems_failed": 2,
        "systems_pending": 5
    },
    "failures": [
        {"store": "legacy-crm", "error": "connection_timeout", "retry_scheduled": "2024-01-16T02:00:00Z"}
    ],
    "estimated_completion": "2024-01-17T10:30:00Z"
}
```

### 6.3 PII Discovery APIs

```
POST /api/v1/scan/trigger
Request:
{
    "store_ids": ["store-uuid-1", "store-uuid-2"],
    "scan_type": "incremental",  // or "full"
    "pii_types": ["email", "ssn", "phone", "name", "address"],
    "min_confidence": 0.85,
    "sample_size": 10000
}
Response (202):
{
    "scan_id": "scan-uuid-101",
    "status": "queued",
    "estimated_duration_minutes": 45
}

GET /api/v1/inventory/findings?store_id={id}&pii_type=email&min_confidence=0.9
Response (200):
{
    "findings": [
        {
            "finding_id": "find-uuid-1",
            "store_name": "user_service_db",
            "table": "users",
            "column": "contact_email",
            "pii_type": "email",
            "confidence": 0.9987,
            "detection_method": "regex",
            "total_records": 15000000,
            "is_encrypted": true,
            "encryption_key_id": "key-uuid-45"
        }
    ],
    "total_count": 234,
    "page": 1
}
```

## 7. Deep Dives

### 7.1 PII Discovery Engine

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PII DISCOVERY ENGINE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │   Schema    │    │   Content    │    │    ML/NER            │   │
│  │  Analysis   │    │   Scanning   │    │    Classification    │   │
│  │  (metadata) │    │  (sampling)  │    │    (context)         │   │
│  └──────┬──────┘    └──────┬───────┘    └──────────┬───────────┘   │
│         │                  │                       │               │
│  ┌──────▼──────────────────▼───────────────────────▼───────────┐   │
│  │                  CONFIDENCE SCORER                            │   │
│  │   Schema Match (0.3) + Regex Match (0.4) + NER (0.3)       │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │              BLOOM FILTER (known PII locations)              │   │
│  │         Quick lookup: "Is this column already known PII?"   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Regex Pattern Library:**

```python
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "ssn": r"\b\d{3}-?\d{2}-?\d{4}\b",
    "phone_us": r"\b(\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b",
    "phone_intl": r"\b\+\d{1,3}[-.]?\d{4,14}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "date_of_birth": r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b",
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b",
}

class PIIScanner:
    def __init__(self, ner_model, bloom_filter):
        self.ner_model = ner_model  # spaCy/Presidio NER
        self.bloom_filter = bloom_filter  # ~1% FPR, stores "store:table:column" keys
        self.confidence_weights = {"schema": 0.3, "regex": 0.4, "ner": 0.3}
    
    def scan_column(self, store_id, table, column, sample_values):
        # Quick check: already known?
        key = f"{store_id}:{table}:{column}"
        if self.bloom_filter.contains(key):
            return self._get_cached_finding(key)
        
        scores = {}
        
        # 1. Schema/metadata analysis
        schema_score = self._analyze_column_name(column)  # "email" → 0.95, "col_7" → 0.0
        
        # 2. Regex pattern matching on sample
        regex_matches = {}
        for pii_type, pattern in PII_PATTERNS.items():
            match_rate = sum(1 for v in sample_values if re.search(pattern, str(v))) / len(sample_values)
            if match_rate > 0.1:
                regex_matches[pii_type] = match_rate
        
        # 3. NER/ML classification
        ner_results = self.ner_model.analyze_batch(sample_values)
        
        # Combine scores
        for pii_type in set(list(regex_matches.keys()) + list(ner_results.keys())):
            score = (
                self.confidence_weights["schema"] * schema_score.get(pii_type, 0) +
                self.confidence_weights["regex"] * regex_matches.get(pii_type, 0) +
                self.confidence_weights["ner"] * ner_results.get(pii_type, 0)
            )
            if score >= 0.7:  # threshold
                scores[pii_type] = score
        
        # Add to bloom filter for future quick lookups
        if scores:
            self.bloom_filter.add(key)
        
        return scores

    def incremental_scan(self, store_id, cdc_events):
        """Process CDC events for new/modified columns"""
        new_findings = []
        for event in cdc_events:
            if event.type in ('CREATE_TABLE', 'ADD_COLUMN', 'ALTER_COLUMN'):
                sample = self._get_sample(store_id, event.table, event.column)
                findings = self.scan_column(store_id, event.table, event.column, sample)
                new_findings.extend(findings)
        return new_findings
```

**Bloom Filter Configuration:**

```python
# Bloom filter for known PII locations
# Expected items: 10M (columns across all stores)
# Target FPR: 1%
# Optimal: m = -n*ln(p) / (ln2)^2 ≈ 96M bits ≈ 12MB
# Optimal k (hash functions): (m/n) * ln2 ≈ 7

bloom_config = {
    "expected_items": 10_000_000,
    "false_positive_rate": 0.01,
    "bit_array_size": 96_000_000,
    "hash_functions": 7,
    "hash_algorithm": "murmur3"
}
```

### 7.2 Cryptographic Erasure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CRYPTOGRAPHIC ERASURE FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  WRITE PATH (data ingestion):                                       │
│  ┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐ │
│  │ User PII │───▶│ Fetch/Gen │───▶│ Encrypt PII │───▶│  Store   │ │
│  │  Data    │    │ User Key  │    │  with Key   │    │Ciphertext│ │
│  └──────────┘    └───────────┘    └─────────────┘    └──────────┘ │
│                        │                                            │
│                  ┌─────▼─────┐                                     │
│                  │    HSM    │  Per-user AES-256-GCM key           │
│                  │ Key Store │  Key hierarchy: Master → User       │
│                  └───────────┘                                     │
│                                                                     │
│  ERASURE PATH (right-to-erasure):                                  │
│  ┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐ │
│  │  DSAR    │───▶│  Destroy  │───▶│ Ciphertext  │───▶│Verify All│ │
│  │ Erasure  │    │  User Key │    │  Now Unread │    │ Systems  │ │
│  │ Request  │    │  in HSM   │    │   -able     │    │  Clear   │ │
│  └──────────┘    └───────────┘    └─────────────┘    └──────────┘ │
│                                                                     │
│  BACKUP HANDLING:                                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Backups contain encrypted PII → key destruction renders     │  │
│  │  backup PII unrecoverable without re-encryption overhead     │  │
│  │                                                              │  │
│  │  Verification: attempt decrypt with destroyed key → must fail│  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

```python
class CryptoErasureService:
    def __init__(self, hsm_client, key_store):
        self.hsm = hsm_client
        self.key_store = key_store  # Maps user_id → key_id in HSM
    
    def encrypt_pii(self, user_id: str, plaintext: bytes) -> tuple[bytes, str]:
        """Encrypt PII with user-specific key"""
        key_id = self._get_or_create_user_key(user_id)
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
        ciphertext = self.hsm.encrypt(
            key_id=key_id,
            plaintext=plaintext,
            nonce=nonce,
            aad=user_id.encode()  # additional authenticated data
        )
        return nonce + ciphertext, key_id
    
    def execute_erasure(self, user_id: str) -> ErasureResult:
        """Crypto-shred: destroy user's encryption key"""
        key_id = self.key_store.get_key_id(user_id)
        if not key_id:
            return ErasureResult(status="no_key_found")
        
        # 1. Schedule key destruction (with 24hr grace period for rollback)
        destruction_ticket = self.hsm.schedule_key_destruction(
            key_id=key_id,
            grace_period_hours=24
        )
        
        # 2. Immediately revoke key access (no new encrypts/decrypts)
        self.hsm.disable_key(key_id)
        
        # 3. Record in audit log
        self._audit_log(user_id, key_id, "erasure_initiated")
        
        # 4. Trigger verification pipeline
        verification_job = self._schedule_verification(user_id, key_id)
        
        return ErasureResult(
            status="initiated",
            key_id=key_id,
            destruction_ticket=destruction_ticket,
            verification_job_id=verification_job.id,
            grace_period_ends="2024-01-16T10:30:00Z"
        )
    
    def verify_erasure(self, user_id: str, key_id: str) -> VerificationResult:
        """Verify PII is unrecoverable across all systems"""
        results = []
        
        # Check all known PII locations for this user
        pii_locations = self.data_inventory.get_user_pii_locations(user_id)
        
        for location in pii_locations:
            # Attempt to read and decrypt — must fail
            try:
                encrypted_data = location.adapter.read(user_id)
                if encrypted_data:
                    # Try decrypt with destroyed key — should fail
                    try:
                        self.hsm.decrypt(key_id, encrypted_data)
                        results.append(VerificationFailure(location, "decrypt_succeeded"))
                    except HSMKeyDestroyedError:
                        results.append(VerificationSuccess(location))
                else:
                    results.append(VerificationSuccess(location, "data_not_found"))
            except Exception as e:
                results.append(VerificationSuccess(location, f"read_failed: {e}"))
        
        # Check caches (Redis, CDN, etc.)
        cache_results = self._verify_cache_cleared(user_id)
        results.extend(cache_results)
        
        # Check logs (verify PII not in plaintext logs)
        log_results = self._verify_logs_clean(user_id)
        results.extend(log_results)
        
        return VerificationResult(
            user_id=user_id,
            locations_checked=len(results),
            all_verified=all(r.success for r in results),
            failures=[r for r in results if not r.success]
        )
```

### 7.3 Consent Propagation

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONSENT PROPAGATION FLOW                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐    ┌──────────┐    ┌─────────────────────────────┐   │
│  │  User   │───▶│ Consent  │───▶│  Kafka: consent.changes     │   │
│  │withdraws│    │ Service  │    │  Key: user_id               │   │
│  │ consent │    │          │    │  Partition: hash(user_id)    │   │
│  └─────────┘    └──────────┘    └──────────────┬──────────────┘   │
│                                                 │                   │
│                    ┌────────────────────────────┼────────────┐      │
│                    │                            │            │      │
│            ┌───────▼──────┐  ┌─────────▼─────┐  ┌──▼───────┐     │
│            │  Email       │  │  Analytics    │  │  Ad      │     │
│            │  Service     │  │  Pipeline     │  │ Platform │     │
│            │  Consumer    │  │  Consumer     │  │ Consumer │     │
│            └───────┬──────┘  └─────────┬─────┘  └──┬───────┘     │
│                    │                   │            │              │
│            ┌───────▼──────┐  ┌─────────▼─────┐  ┌──▼───────┐     │
│            │   ACK back   │  │   ACK back    │  │ ACK back │     │
│            │  to consent  │  │  to consent   │  │to consent│     │
│            │   service    │  │   service     │  │ service  │     │
│            └──────────────┘  └───────────────┘  └──────────┘     │
│                                                                     │
│  CONSENT-AWARE QUERY LAYER:                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  SELECT * FROM user_data                                      │  │
│  │  WHERE user_id = ?                                            │  │
│  │  AND has_active_consent(user_id, 'analytics') = TRUE         │  │
│  │                                                               │  │
│  │  → Interceptor checks Redis consent cache before returning    │  │
│  │  → If consent withdrawn, filter out data / return empty      │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**Kafka Configuration for Consent Events:**

```yaml
# consent.changes topic
topic:
  name: consent.changes
  partitions: 64              # partition by user_id for ordering
  replication_factor: 3
  retention_ms: 604800000     # 7 days
  cleanup_policy: delete
  min_insync_replicas: 2
  compression: lz4
  
# Consumer group settings
consumer:
  group_id: consent-propagation-{service_name}
  auto_offset_reset: earliest
  enable_auto_commit: false   # manual commit after processing
  max_poll_records: 100
  session_timeout_ms: 30000
```

```python
class ConsentPropagationService:
    def __init__(self, kafka_producer, redis_client, downstream_registry):
        self.producer = kafka_producer
        self.redis = redis_client
        self.downstream = downstream_registry
    
    def propagate_consent_change(self, user_id: str, purpose: str, new_status: str):
        """Propagate consent change to all downstream systems"""
        event = {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "purpose": purpose,
            "new_status": new_status,
            "timestamp": datetime.utcnow().isoformat(),
            "affected_systems": self.downstream.get_systems_for_purpose(purpose),
            "requires_ack": True,
            "deadline": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }
        
        # Publish to Kafka (ordered by user_id via partition key)
        self.producer.send(
            topic="consent.changes",
            key=user_id.encode(),
            value=json.dumps(event).encode(),
            headers=[("event_type", b"consent_change")]
        )
        
        # Update Redis consent cache immediately
        cache_key = f"consent:{user_id}:{purpose}"
        if new_status == "granted":
            self.redis.set(cache_key, "1", ex=86400)  # 24hr TTL, refreshed on read
        else:
            self.redis.delete(cache_key)
        
        # Track acknowledgments needed
        ack_key = f"consent_ack:{event['event_id']}"
        self.redis.sadd(ack_key, *event["affected_systems"])
        self.redis.expire(ack_key, 86400)
    
    def check_consent(self, user_id: str, purpose: str) -> bool:
        """Fast consent check via Redis cache"""
        cache_key = f"consent:{user_id}:{purpose}"
        cached = self.redis.get(cache_key)
        
        if cached is not None:
            return cached == "1"
        
        # Cache miss: check database
        consent = self.db.get_active_consent(user_id, purpose)
        result = consent is not None and consent.status == "granted"
        
        # Populate cache
        if result:
            self.redis.set(cache_key, "1", ex=86400)
        else:
            self.redis.set(cache_key, "0", ex=3600)  # shorter TTL for negatives
        
        return result
    
    def process_acknowledgment(self, event_id: str, system_name: str, success: bool):
        """Track downstream system acknowledgment"""
        ack_key = f"consent_ack:{event_id}"
        
        if success:
            self.redis.srem(ack_key, system_name)
            remaining = self.redis.scard(ack_key)
            if remaining == 0:
                self._mark_propagation_complete(event_id)
        else:
            # Schedule retry
            self._schedule_retry(event_id, system_name)
```

## 8. Component Optimization

### Kafka Configuration

```yaml
# Consent event streaming
kafka:
  brokers: ["kafka-1:9092", "kafka-2:9092", "kafka-3:9092"]
  topics:
    consent_changes:
      partitions: 64
      replication: 3
      retention: 7d
      compaction: false
    dsar_events:
      partitions: 32
      replication: 3
      retention: 30d
    pii_discoveries:
      partitions: 16
      replication: 3
      retention: 90d
  producer:
    acks: all
    retries: 5
    linger_ms: 10
    batch_size: 16384
    compression: lz4
    idempotence: true
```

### Redis Configuration

```yaml
# Consent cache cluster
redis:
  cluster_mode: true
  nodes: 6  # 3 primary + 3 replica
  memory_per_node: 32GB
  eviction_policy: volatile-lru
  maxmemory: 28GB
  
  # Key patterns and TTLs
  key_patterns:
    consent_cache: "consent:{user_id}:{purpose}" # TTL: 24h
    consent_ack: "consent_ack:{event_id}"         # TTL: 24h
    dsar_progress: "dsar:{request_id}:progress"   # TTL: 72h
    scan_state: "scan:{scan_id}:state"            # TTL: 48h
  
  # Memory estimation
  # 500M users × 8 purposes × ~100 bytes = 400GB (too large for full cache)
  # Strategy: cache active/recently-checked consents only (~5% = 25GB)
```

### Elasticsearch Configuration

```yaml
# Data inventory index
elasticsearch:
  cluster:
    nodes: 5
    heap_size: 16GB
  index:
    pii_inventory:
      shards: 10
      replicas: 1
      refresh_interval: 30s
      mapping:
        store_id: keyword
        table_name: keyword
        column_name: keyword
        pii_type: keyword
        sensitivity_level: keyword
        confidence_score: float
        discovered_at: date
        full_path: text  # for search: "db.schema.table.column"
```

### Flink Configuration

```yaml
# Real-time consent enforcement
flink:
  job:
    name: consent-enforcement
    parallelism: 32
    checkpointing:
      interval: 60000
      mode: exactly_once
      timeout: 120000
    state_backend: rocksdb
    state_ttl: 86400000  # 24h
  
  # Consent filter operator
  # Every data processing event passes through this
  # Checks consent state before allowing data usage
```

## 9. Observability

### Metrics

```yaml
metrics:
  consent:
    - consent_grants_total{purpose, method}
    - consent_withdrawals_total{purpose, reason}
    - consent_lookup_latency_ms{cache_hit}
    - consent_propagation_lag_ms{system}
    - consent_ack_pending_count{system}
  
  dsar:
    - dsar_requests_total{type, status}
    - dsar_fulfillment_time_hours{type}
    - dsar_systems_processing_time_ms{system}
    - dsar_deadline_breach_risk  # countdown alert
    - dsar_backlog_count{priority}
  
  pii_scanner:
    - pii_scan_throughput_bytes_per_sec
    - pii_findings_total{type, sensitivity, method}
    - pii_false_positive_rate{type}
    - pii_stores_scanned_total
    - pii_scan_coverage_percent
  
  crypto_erasure:
    - keys_destroyed_total
    - erasure_verification_success_rate
    - erasure_verification_failures{system}

alerts:
  - name: DSARDeadlineApproaching
    condition: dsar_deadline_hours_remaining < 72
    severity: warning
  
  - name: DSARDeadlineCritical
    condition: dsar_deadline_hours_remaining < 24
    severity: critical
  
  - name: ConsentPropagationLag
    condition: consent_propagation_lag_ms > 60000
    severity: warning
  
  - name: ErasureVerificationFailure
    condition: erasure_verification_failures > 0
    severity: critical
  
  - name: PIIScanCoverageDropped
    condition: pii_scan_coverage_percent < 95
    severity: warning
```

### Distributed Tracing

```
Consent Change Trace:
User Request → API Gateway → Consent Service → DB Write → Kafka Publish
  → [Fan-out] Email Service ACK (200ms)
  → [Fan-out] Analytics Pipeline ACK (500ms)
  → [Fan-out] Ad Platform ACK (300ms)
  → Propagation Complete Event

DSAR Trace:
Submit → Verify Identity → Create Tasks (fan-out to 47 systems)
  → Per-system: Connect → Query → Process → Verify → ACK
  → Aggregate Results → Generate Export → Notify User
```

### Audit Dashboard

```
┌─────────────────────────────────────────────────────────┐
│  GDPR COMPLIANCE DASHBOARD                              │
├─────────────────────────────────────────────────────────┤
│  DSARs: 1,247 active │ 98.7% on-time │ Avg: 18hrs     │
│  Consent: 4.2B records │ 99.99% cache hit             │
│  PII Coverage: 97.3% stores scanned                    │
│  Erasure Verification: 100% success (last 30d)         │
│  Cross-border Transfers: 127 active │ All compliant    │
│  Retention Purges: 2.1M records/day                    │
│  Breach Notifications: 0 pending                       │
└─────────────────────────────────────────────────────────┘
```

## 10. Failure Analysis & Considerations

### Failure Scenarios

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Consent cache failure | Falls back to DB; higher latency | Multi-region Redis cluster with local fallback cache |
| DSAR adapter timeout | Delayed fulfillment | Retry with exponential backoff; escalation after 3 failures |
| HSM unavailability | Cannot encrypt/decrypt PII | HSM cluster with cross-region failover; circuit breaker |
| Kafka partition leader failure | Consent propagation delay | ISR with min.insync.replicas=2; automatic leader election |
| PII scanner false positives | Alert fatigue | Human-in-the-loop verification; confidence threshold tuning |
| Key destruction before verification | Premature data loss | 24-hour grace period; DPO approval for destruction |

### Considerations

1. **Legal Conflicts**: Right-to-erasure vs. legal retention obligations (e.g., financial records 7 years) — implement legal hold overlay
2. **Backup Consistency**: Crypto-shredding handles backups without needing to rewrite them, but restore testing must account for destroyed keys
3. **Third-Party Data Sharing**: Track all recipients of shared data; trigger cascading deletion requests per GDPR Article 17(2)
4. **Performance vs. Compliance**: Consent checks on every API call add latency — Redis cache with eventual consistency (max 1min lag)
5. **Multi-Tenancy**: Different jurisdictions have different requirements — configurable policy engine per region
6. **Right to Portability Format**: GDPR requires "structured, commonly used, machine-readable format" — support JSON, CSV, XML exports
7. **Data Minimization**: Scanner should also flag over-collection — data stored without clear purpose
8. **Consent Fatigue**: UX consideration — granular consent without overwhelming users
9. **Legacy Systems**: Some systems cannot be modified — proxy/wrapper approach for consent enforcement
10. **Audit Immutability**: Use append-only stores with cryptographic chaining (blockchain-like) for tamper evidence

## 11. References & Standards

- GDPR Articles 6, 7, 12-23, 25, 30, 32-34
- ISO 27701 (Privacy Information Management)
- NIST Privacy Framework
- WP29 Guidelines on Consent, Transparency, DSAR
