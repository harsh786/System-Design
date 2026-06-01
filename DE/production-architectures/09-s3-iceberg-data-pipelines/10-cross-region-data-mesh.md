# Cross-Region Data Mesh with Iceberg Catalog Federation

## The Production Problem

A global financial services company operates across 5 regions (us-east-1, us-west-2, eu-west-1, eu-central-1, ap-southeast-1) with 50+ autonomous teams. Each team produces data products consumed by other teams globally. The current state:

- **Monolithic catalog** in us-east-1 creates 200-400ms latency for APAC queries
- **GDPR/data residency** violations because EU PII data metadata is accessible globally without controls
- **No ownership model** — shared Hive metastore means anyone can ALTER any table
- **Vendor lock-in** — Glue Catalog ties them to AWS; the APAC team runs on GCP
- **No data contracts** — downstream pipelines break weekly from unannounced schema changes
- **Discovery is impossible** — 100K+ tables with no documentation, ownership, or quality signals

They need a **federated data mesh** where each team owns their data as products, but any authorized consumer can discover and query across regions with low latency and full compliance.

---

## Why Iceberg Solves This

| Data Mesh Requirement | Iceberg Capability |
|---|---|
| Domain ownership | Namespace hierarchy maps to team ownership |
| Data as a product | Iceberg tables ARE the product (self-describing, versioned) |
| Self-serve platform | REST Catalog standard = any engine can connect |
| Federated governance | Multi-catalog routing + column-level access via views |
| Multi-cloud | Open format on object storage (S3/GCS/ADLS) — no proprietary lock-in |
| Cross-region | Metadata is small (JSON/Avro) — replicate catalogs, not data |
| Schema contracts | Schema evolution rules enforced at catalog level |
| Time travel | Consumers can pin to snapshots for reproducibility |

The key insight: **Iceberg's REST Catalog specification** provides a standard API that allows catalog federation — a routing layer can dispatch requests to regional catalogs transparently. The open table format means data stays in-region while metadata is federated.

---

## Global Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          GLOBAL FEDERATION LAYER                                 │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    Catalog Federation Router (Global)                     │   │
│  │         catalog.global.company.com (GeoDNS → nearest region)            │   │
│  │                                                                          │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐   │   │
│  │  │ Namespace│  │Access Control│  │ Data Contract│  │  Audit Log    │   │   │
│  │  │ Router   │  │  Enforcer    │  │  Validator   │  │  (Global)     │   │   │
│  │  └──────────┘  └──────────────┘  └─────────────┘  └───────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│         ┌──────────────┬──────────────┬──────────────┬──────────────┐          │
│         │              │              │              │              │          │
│         ▼              ▼              ▼              ▼              ▼          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │ US-EAST    │ │ US-WEST    │ │ EU-WEST    │ │ EU-CENTRAL │ │ APAC       │  │
│  │ Catalog    │ │ Catalog    │ │ Catalog    │ │ Catalog    │ │ Catalog    │  │
│  │ (Polaris)  │ │ (Polaris)  │ │ (Polaris)  │ │ (Nessie)   │ │ (Custom)   │  │
│  │            │ │            │ │            │ │            │ │ on GCP     │  │
│  │ 15 teams   │ │ 8 teams    │ │ 12 teams   │ │ 10 teams   │ │ 7 teams    │  │
│  │ 30K tables │ │ 15K tables │ │ 25K tables │ │ 20K tables │ │ 12K tables │  │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘  │
│        │              │              │              │              │          │
│        ▼              ▼              ▼              ▼              ▼          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │ S3         │ │ S3         │ │ S3         │ │ S3         │ │ GCS        │  │
│  │ us-east-1  │ │ us-west-2  │ │ eu-west-1  │ │ eu-central │ │ asia-se1   │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         QUERY ENGINES                                    │   │
│  │                                                                          │   │
│  │  Trino (federated)    Spark (batch)    Flink (streaming)    DuckDB (ad-hoc)│
│  │  - Multi-catalog      - Per-region     - Per-region         - Local dev   │   │
│  │  - Cross-region JOIN  - Heavy ETL      - CDC ingestion      - Notebooks   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      GOVERNANCE & DISCOVERY                              │   │
│  │                                                                          │   │
│  │  DataHub (global metadata graph)     OpenMetadata (data quality)         │   │
│  │  dbt (contracts + lineage)           Terraform (IaC for catalog)         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Namespace Convention

Namespaces encode ownership and data residency:

```
<region>.<domain>.<team>.<product>.<layer>

Examples:
  eu_west.payments.checkout_team.transactions.gold
  us_east.risk.fraud_detection.alerts.silver
  apac.trading.equities_team.market_data.bronze
```

| Level | Purpose | Example |
|---|---|---|
| Region | Data residency boundary | `eu_west` |
| Domain | Business domain | `payments` |
| Team | Owning team | `checkout_team` |
| Product | Data product name | `transactions` |
| Layer | Medallion layer | `gold` |

This convention is **enforced by the federation router** — you cannot create a table outside your assigned namespace.

---

## REST Catalog Federation Router

### Architecture

The federation router is a stateless service that:
1. Authenticates the caller (JWT from corporate IdP)
2. Resolves namespace to regional catalog
3. Enforces access policies
4. Proxies the REST Catalog API call to the correct regional catalog
5. Logs the access for audit

### Implementation (Java - Spring Boot)

```java
@RestController
@RequestMapping("/v1")
public class CatalogFederationRouter {

    private final NamespaceRouter namespaceRouter;
    private final AccessControlEnforcer accessControl;
    private final AuditLogger auditLogger;
    private final Map<String, RestCatalogClient> regionalCatalogs;

    @PostMapping("/namespaces/{namespace}/tables")
    public ResponseEntity<LoadTableResponse> loadTable(
            @PathVariable String namespace,
            @RequestParam String table,
            @RequestHeader("Authorization") String authToken,
            HttpServletRequest request) {

        // 1. Authenticate and extract identity
        CallerIdentity caller = authService.authenticate(authToken);

        // 2. Resolve which regional catalog owns this namespace
        RegionalCatalog target = namespaceRouter.resolve(namespace);

        // 3. Check access control
        AccessDecision decision = accessControl.evaluate(
            caller, target, namespace, table, Action.READ
        );
        if (decision.isDenied()) {
            auditLogger.logDenied(caller, namespace, table, decision.getReason());
            throw new ForbiddenException(decision.getReason());
        }

        // 4. Check data residency constraints
        if (decision.requiresResidencyCheck()) {
            DataResidencyPolicy policy = residencyService.getPolicy(namespace);
            if (!policy.allowsCrossRegionMetadataAccess(caller.getRegion())) {
                throw new DataResidencyViolationException(
                    "Metadata for " + namespace + " cannot leave " + target.getRegion()
                );
            }
        }

        // 5. Proxy to regional catalog
        RestCatalogClient client = regionalCatalogs.get(target.getRegion());
        LoadTableResponse response = client.loadTable(
            TableIdentifier.of(Namespace.of(namespace.split("\\.")), table)
        );

        // 6. Apply column-level masking if needed
        if (decision.hasColumnRestrictions()) {
            response = applyColumnMasking(response, decision.getColumnPolicy());
        }

        // 7. Audit log
        auditLogger.logAccess(caller, namespace, table, target.getRegion());

        return ResponseEntity.ok(response);
    }

    @PostMapping("/namespaces/{namespace}/tables/{table}/metrics")
    public ResponseEntity<Void> reportMetrics(
            @PathVariable String namespace,
            @PathVariable String table,
            @RequestBody ReportMetricsRequest metricsRequest,
            @RequestHeader("Authorization") String authToken) {

        CallerIdentity caller = authService.authenticate(authToken);
        RegionalCatalog target = namespaceRouter.resolve(namespace);

        // Forward scan metrics to regional catalog
        RestCatalogClient client = regionalCatalogs.get(target.getRegion());
        client.reportMetrics(
            TableIdentifier.of(Namespace.of(namespace.split("\\.")), table),
            metricsRequest
        );

        // Also publish to global metrics aggregator
        globalMetrics.publish(namespace, table, metricsRequest, caller);

        return ResponseEntity.noContent().build();
    }

    private LoadTableResponse applyColumnMasking(
            LoadTableResponse response, ColumnPolicy policy) {
        // Modify metadata to inject masking view layer
        Schema originalSchema = response.tableMetadata().schema();
        Schema maskedSchema = policy.applyMasking(originalSchema);

        // Return metadata that points to a masking view instead of raw table
        return LoadTableResponse.builder()
            .withTableMetadata(
                TableMetadata.buildFrom(response.tableMetadata())
                    .setCurrentSchema(maskedSchema)
                    .build()
            )
            .build();
    }
}
```

### Namespace Router

```java
@Component
public class NamespaceRouter {

    // Loaded from configuration / Consul / etcd
    private final Map<String, RegionalCatalogConfig> routingTable;

    public RegionalCatalog resolve(String namespace) {
        // First token is the region prefix
        String regionPrefix = namespace.split("\\.")[0];

        RegionalCatalogConfig config = routingTable.get(regionPrefix);
        if (config == null) {
            throw new UnknownNamespaceException(
                "No catalog registered for region prefix: " + regionPrefix
            );
        }

        return RegionalCatalog.builder()
            .region(config.getRegion())
            .endpoint(config.getEndpoint())
            .failoverEndpoint(config.getFailoverEndpoint())
            .build();
    }
}
```

### Routing Configuration

```yaml
# catalog-routing.yaml
routing:
  namespaces:
    us_east:
      region: us-east-1
      catalog_type: polaris
      endpoint: https://polaris.us-east-1.internal.company.com
      failover: https://polaris.us-west-2.internal.company.com
      cloud: aws

    us_west:
      region: us-west-2
      catalog_type: polaris
      endpoint: https://polaris.us-west-2.internal.company.com
      failover: https://polaris.us-east-1.internal.company.com
      cloud: aws

    eu_west:
      region: eu-west-1
      catalog_type: polaris
      endpoint: https://polaris.eu-west-1.internal.company.com
      failover: https://polaris.eu-central-1.internal.company.com
      cloud: aws
      residency_policy: eu_strict  # metadata cannot leave EU

    eu_central:
      region: eu-central-1
      catalog_type: nessie
      endpoint: https://nessie.eu-central-1.internal.company.com
      failover: https://nessie.eu-west-1.internal.company.com
      cloud: aws
      residency_policy: eu_strict

    apac:
      region: asia-southeast1
      catalog_type: custom_rest
      endpoint: https://iceberg-catalog.apac.internal.company.com
      failover: https://iceberg-catalog-dr.apac.internal.company.com
      cloud: gcp
```

---

## Python REST Catalog Client for Federation

```python
"""
Custom Iceberg REST Catalog client that connects through the federation router.
Used by data teams to interact with the global catalog from Python/Spark/dbt.
"""

from pyiceberg.catalog import Catalog, PropertiesUpdateSummary
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.table import Table
from pyiceberg.typedef import Identifier
import httpx
import time


class FederatedCatalog(Catalog):
    """
    Wraps the Iceberg REST catalog to route through our federation layer.
    Handles:
      - Token refresh (corporate OIDC)
      - Region-aware routing
      - Automatic failover
      - Request tracing
    """

    def __init__(self, name: str, **properties):
        super().__init__(name, **properties)
        self.federation_url = properties["uri"]  # Global federation endpoint
        self.token_endpoint = properties["oauth2-server-uri"]
        self.client_id = properties["credential"].split(":")[0]
        self.client_secret = properties["credential"].split(":")[1]
        self._token = None
        self._token_expiry = 0

        self._client = httpx.Client(
            base_url=self.federation_url,
            timeout=30.0,
            headers={"X-Trace-Id": self._generate_trace_id()},
        )

    def _get_token(self) -> str:
        if time.time() < self._token_expiry - 60:
            return self._token

        resp = httpx.post(
            self.token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "catalog:read catalog:write",
            },
        )
        resp.raise_for_status()
        token_data = resp.json()
        self._token = token_data["access_token"]
        self._token_expiry = time.time() + token_data["expires_in"]
        return self._token

    def load_table(self, identifier: Identifier) -> Table:
        """Load table through federation - router handles region resolution."""
        namespace = ".".join(identifier[:-1])
        table_name = identifier[-1]

        response = self._client.get(
            f"/v1/namespaces/{namespace}/tables/{table_name}",
            headers={"Authorization": f"Bearer {self._get_token()}"},
        )

        if response.status_code == 403:
            raise PermissionError(
                f"Access denied to {namespace}.{table_name}: "
                f"{response.json().get('message')}"
            )
        if response.status_code == 451:  # Unavailable for Legal Reasons
            raise DataResidencyError(
                f"Data residency policy prevents access: {response.json()}"
            )

        response.raise_for_status()
        return self._parse_table_response(response.json())

    def list_tables(self, namespace: Identifier) -> list[Identifier]:
        """List tables - respects access control (only shows permitted tables)."""
        ns_str = ".".join(namespace)
        response = self._client.get(
            f"/v1/namespaces/{ns_str}/tables",
            headers={"Authorization": f"Bearer {self._get_token()}"},
        )
        response.raise_for_status()
        return [
            tuple(t["namespace"] + [t["name"]])
            for t in response.json()["identifiers"]
        ]


# Usage in Spark
spark_config = {
    "spark.sql.catalog.global": "org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.global.type": "rest",
    "spark.sql.catalog.global.uri": "https://catalog.global.company.com",
    "spark.sql.catalog.global.oauth2-server-uri": "https://auth.company.com/oauth/token",
    "spark.sql.catalog.global.credential": "spark-svc:secret123",
    "spark.sql.catalog.global.scope": "catalog:read",
}
```

---

## Multi-Catalog Trino Configuration

Trino connects to multiple regional catalogs simultaneously, enabling cross-region JOINs:

```properties
# etc/catalog/us_east.properties
connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=https://polaris.us-east-1.internal.company.com
iceberg.rest-catalog.security=OAUTH2
iceberg.rest-catalog.oauth2.token=https://auth.company.com/oauth/token
iceberg.rest-catalog.oauth2.credential=trino-us-east:${ENV:TRINO_US_EAST_SECRET}

# etc/catalog/eu_west.properties
connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=https://polaris.eu-west-1.internal.company.com
iceberg.rest-catalog.security=OAUTH2
iceberg.rest-catalog.oauth2.token=https://auth.company.com/oauth/token
iceberg.rest-catalog.oauth2.credential=trino-eu-west:${ENV:TRINO_EU_WEST_SECRET}

# etc/catalog/apac.properties
connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=https://iceberg-catalog.apac.internal.company.com
iceberg.rest-catalog.security=OAUTH2
iceberg.rest-catalog.oauth2.token=https://auth.company.com/oauth/token
iceberg.rest-catalog.oauth2.credential=trino-apac:${ENV:TRINO_APAC_SECRET}
```

### Cross-Region Query Example

```sql
-- Federated query: Join US transactions with EU customer data
-- Trino pushes predicates down to each regional catalog independently
SELECT
    t.transaction_id,
    t.amount_usd,
    t.transaction_time,
    c.customer_segment,        -- EU data stays in EU
    c.country_code
FROM us_east.us_east.payments.checkout_team.transactions.gold AS t
JOIN eu_west.eu_west.customers.identity_team.profiles.gold AS c
    ON t.customer_id = c.customer_id
WHERE t.transaction_date >= DATE '2024-01-01'
  AND c.country_code = 'DE'
  AND t.amount_usd > 10000;

-- Note: The EU catalog will mask PII columns (email, phone) based on
-- the Trino service account's access level. The query sees only
-- customer_segment and country_code because those are non-PII.
```

---

## Access Control Model

### Hierarchy

```
┌─────────────────────────────────────────────────┐
│              GLOBAL POLICIES                      │
│  - Data residency rules (EU data stays in EU)   │
│  - Cross-region access requires approval        │
│  - PII access requires DPO sign-off             │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        ▼            ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ DOMAIN POLICY│ │ DOMAIN POLICY│ │ DOMAIN POLICY│
│ (payments)   │ │ (risk)       │ │ (trading)    │
│              │ │              │ │              │
│ Owner: Pay   │ │ Owner: Risk  │ │ Owner: Trade │
│ team lead    │ │ team lead    │ │ team lead    │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ TABLE-LEVEL ACCESS                        │
│                                          │
│ transactions.gold:                       │
│   - Owner: checkout_team (FULL)          │
│   - risk_team: READ (all columns)        │
│   - analytics_team: READ (masked PII)    │
│   - external_auditor: READ (aggregates)  │
└──────────────────────────────────────────┘
```

### Policy Definition (OPA/Rego)

```rego
package iceberg.access

import future.keywords.in

# Default deny
default allow := false

# Table owners have full access
allow {
    input.action in ["READ", "WRITE", "ALTER", "DROP"]
    input.caller.team == data.table_ownership[input.namespace][input.table].owner
}

# Cross-team read access requires explicit grant
allow {
    input.action == "READ"
    grant := data.access_grants[input.namespace][input.table][_]
    grant.grantee == input.caller.team
    grant.permission == "READ"
    not grant.expired
}

# Data residency: EU tables cannot be read from outside EU
deny[msg] {
    startswith(input.namespace, "eu_")
    not input.caller.region in ["eu-west-1", "eu-central-1"]
    not data.residency_exceptions[input.caller.team][input.namespace]
    msg := sprintf("Data residency violation: %s cannot access %s from %s",
        [input.caller.team, input.namespace, input.caller.region])
}

# Column-level masking policy
column_mask[col] := "HASH" {
    col := data.pii_columns[input.namespace][input.table][_]
    not input.caller.team == data.table_ownership[input.namespace][input.table].owner
    not data.pii_access_approved[input.caller.team][input.namespace]
}

column_mask[col] := "NULL" {
    col := data.restricted_columns[input.namespace][input.table][_]
    input.caller.clearance_level < data.column_clearance[input.namespace][input.table][col]
}
```

### Column-Level Masking via Iceberg Views

```sql
-- The federation router returns this view definition instead of raw table
-- when caller doesn't have PII access

CREATE VIEW eu_west.customers.identity_team.profiles.gold_masked AS
SELECT
    customer_id,
    customer_segment,
    country_code,
    registration_date,
    -- Masked columns
    SHA256(CAST(email AS VARBINARY))     AS email,
    CONCAT(SUBSTR(phone, 1, 4), '****') AS phone,
    NULL                                  AS address_line_1,
    NULL                                  AS address_line_2,
    postal_code,  -- kept for geo-analytics
    lifetime_value_bucket  -- bucketed, not exact value
FROM eu_west.customers.identity_team.profiles.gold_raw;
```

---

## Data Contracts

### Contract Definition (YAML)

```yaml
# contracts/eu_west.payments.checkout_team.transactions.gold.yaml
apiVersion: datacontract/v1
kind: DataContract
metadata:
  name: transactions-gold
  owner: checkout_team
  domain: payments
  region: eu-west
  version: "3.2.0"
  deprecation: null  # or date when deprecated

spec:
  schema:
    type: iceberg
    fields:
      - name: transaction_id
        type: string
        required: true
        unique: true
        description: "UUID v4 identifier"

      - name: customer_id
        type: string
        required: true
        pii: false  # anonymized reference

      - name: amount_usd
        type: decimal(18,2)
        required: true
        constraints:
          minimum: 0.01
          maximum: 10000000.00

      - name: transaction_time
        type: timestamp_tz
        required: true
        constraints:
          not_future: true

      - name: payment_method
        type: string
        required: true
        constraints:
          allowed_values: ["card", "bank_transfer", "crypto", "wallet"]

      - name: status
        type: string
        required: true
        constraints:
          allowed_values: ["pending", "completed", "failed", "refunded"]

  quality:
    freshness:
      max_delay: "15 minutes"
      measured_at: "transaction_time"
    completeness:
      required_fields_null_rate: "<0.1%"
    accuracy:
      duplicate_rate: "<0.001%"
    volume:
      min_daily_records: 100000
      max_daily_records: 50000000

  sla:
    availability: "99.9%"
    query_latency_p99: "30s"
    support_channel: "#payments-data-support"
    incident_response: "15 minutes (business hours)"

  compatibility:
    breaking_change_policy: "2 weeks notice + migration guide"
    schema_evolution: "additive only (new columns nullable)"
    deprecation_notice: "90 days minimum"

  consumers:
    - team: risk_team
      use_case: "Fraud detection model features"
      sla_tier: critical
    - team: analytics_team
      use_case: "Revenue dashboards"
      sla_tier: standard
    - team: finance_team
      use_case: "Month-end reconciliation"
      sla_tier: critical
```

### Contract Enforcement (dbt + Python)

```python
"""
Contract enforcement runs as a pre-commit hook on the catalog.
When a producer attempts to ALTER a table, this validates the change
against the registered contract.
"""

import yaml
from dataclasses import dataclass
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField, StringType, DecimalType, TimestamptzType
)


@dataclass
class ContractViolation:
    severity: str  # "error" | "warning"
    field: str
    message: str


class ContractEnforcer:

    def __init__(self, contract_path: str):
        with open(contract_path) as f:
            self.contract = yaml.safe_load(f)

    def validate_schema_evolution(
        self, current_schema: Schema, proposed_schema: Schema
    ) -> list[ContractViolation]:
        """Validate that schema changes don't violate the contract."""
        violations = []

        # Check for removed required fields (breaking change)
        current_fields = {f.name: f for f in current_schema.fields}
        proposed_fields = {f.name: f for f in proposed_schema.fields}

        contract_fields = {
            f["name"]: f for f in self.contract["spec"]["schema"]["fields"]
        }

        for field_name, contract_field in contract_fields.items():
            if field_name not in proposed_fields:
                violations.append(ContractViolation(
                    severity="error",
                    field=field_name,
                    message=f"Contract-required field '{field_name}' was removed"
                ))
                continue

            # Check type compatibility
            proposed = proposed_fields[field_name]
            if not self._types_compatible(
                contract_field["type"], proposed.field_type
            ):
                violations.append(ContractViolation(
                    severity="error",
                    field=field_name,
                    message=(
                        f"Type changed from {contract_field['type']} to "
                        f"{proposed.field_type} — violates contract"
                    )
                ))

        # Check compatibility policy
        compat = self.contract["spec"]["compatibility"]
        if compat["schema_evolution"] == "additive only (new columns nullable)":
            for name, field in proposed_fields.items():
                if name not in current_fields and field.required:
                    violations.append(ContractViolation(
                        severity="error",
                        field=name,
                        message="New fields must be nullable per contract policy"
                    ))

        return violations

    def validate_data_quality(
        self, scan_metrics: dict
    ) -> list[ContractViolation]:
        """Validate post-write data quality against contract SLAs."""
        violations = []
        quality = self.contract["spec"]["quality"]

        # Freshness check
        if "freshness" in quality:
            max_delay = self._parse_duration(quality["freshness"]["max_delay"])
            if scan_metrics.get("max_event_lag_seconds", 0) > max_delay:
                violations.append(ContractViolation(
                    severity="error",
                    field="freshness",
                    message=(
                        f"Data is {scan_metrics['max_event_lag_seconds']}s stale, "
                        f"contract requires <{max_delay}s"
                    )
                ))

        # Volume check
        if "volume" in quality:
            daily_count = scan_metrics.get("daily_record_count", 0)
            min_vol = quality["volume"]["min_daily_records"]
            if daily_count < min_vol:
                violations.append(ContractViolation(
                    severity="warning",
                    field="volume",
                    message=f"Daily volume {daily_count} below minimum {min_vol}"
                ))

        return violations

    def _types_compatible(self, contract_type: str, iceberg_type) -> bool:
        type_map = {
            "string": StringType,
            "timestamp_tz": TimestamptzType,
        }
        if contract_type.startswith("decimal"):
            return isinstance(iceberg_type, DecimalType)
        return isinstance(iceberg_type, type_map.get(contract_type, type(None)))

    def _parse_duration(self, duration_str: str) -> int:
        """Parse '15 minutes' to seconds."""
        parts = duration_str.split()
        value = int(parts[0])
        unit = parts[1]
        multipliers = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}
        return value * multipliers.get(unit, 1)
```

---

## Data Product Registration (Terraform)

```hcl
# terraform/modules/data-product/main.tf

variable "product_name" {}
variable "owner_team" {}
variable "domain" {}
variable "region" {}
variable "schema_fields" { type = list(object({ name = string, type = string, required = bool })) }
variable "consumers" { type = list(object({ team = string, access_level = string })) }

locals {
  namespace = "${var.region}.${var.domain}.${var.owner_team}.${var.product_name}"
}

# Create namespace in regional catalog
resource "iceberg_namespace" "product" {
  catalog  = var.region
  name     = local.namespace

  properties = {
    "owner"              = var.owner_team
    "domain"             = var.domain
    "data-product.name"  = var.product_name
    "data-product.tier"  = "gold"
    "data-product.sla"   = "99.9"
    "compliance.residency" = var.region
  }
}

# Create the table
resource "iceberg_table" "product_table" {
  catalog   = var.region
  namespace = iceberg_namespace.product.name
  name      = "gold"

  schema {
    dynamic "column" {
      for_each = var.schema_fields
      content {
        name     = column.value.name
        type     = column.value.type
        required = column.value.required
      }
    }
  }

  properties = {
    "write.metadata.metrics.default" = "full"
    "write.parquet.compression-codec" = "zstd"
    "commit.retry.num-retries"        = "10"
  }
}

# Register access grants
resource "iceberg_access_grant" "consumer" {
  for_each = { for c in var.consumers : c.team => c }

  catalog   = var.region
  namespace = local.namespace
  table     = iceberg_table.product_table.name
  grantee   = each.value.team
  permission = each.value.access_level  # "READ", "READ_MASKED", "READ_AGGREGATED"
}

# Register in DataHub for discovery
resource "datahub_dataset" "product" {
  urn      = "urn:li:dataset:(urn:li:dataPlatform:iceberg,${local.namespace}.gold,PROD)"
  platform = "iceberg"

  ownership {
    owner = var.owner_team
    type  = "DATAOWNER"
  }

  tags = ["data-product", var.domain, var.region]

  properties = {
    "contract_url" = "s3://data-contracts/${local.namespace}/contract.yaml"
    "quality_dashboard" = "https://dataquality.internal/${local.namespace}"
  }
}

# Create contract file in S3
resource "aws_s3_object" "contract" {
  bucket  = "data-contracts-${var.region}"
  key     = "${local.namespace}/contract.yaml"
  content = templatefile("${path.module}/templates/contract.yaml.tpl", {
    product_name = var.product_name
    owner_team   = var.owner_team
    domain       = var.domain
    region       = var.region
    fields       = var.schema_fields
    consumers    = var.consumers
  })
}

# Monitoring alerts
resource "datadog_monitor" "freshness" {
  name    = "Data Product Freshness: ${local.namespace}"
  type    = "metric alert"
  query   = "max(last_15m):max:iceberg.table.last_commit_age{namespace:${local.namespace}} > 900"
  message = "Data product ${var.product_name} is stale. Owner: @${var.owner_team}"

  monitor_thresholds {
    critical = 900   # 15 min
    warning  = 600   # 10 min
  }
}
```

### Usage

```hcl
# terraform/products/transactions.tf

module "transactions_product" {
  source = "../modules/data-product"

  product_name = "transactions"
  owner_team   = "checkout_team"
  domain       = "payments"
  region       = "eu_west"

  schema_fields = [
    { name = "transaction_id",   type = "string",         required = true },
    { name = "customer_id",      type = "string",         required = true },
    { name = "amount_usd",       type = "decimal(18,2)",  required = true },
    { name = "transaction_time", type = "timestamp_tz",   required = true },
    { name = "payment_method",   type = "string",         required = true },
    { name = "status",           type = "string",         required = true },
  ]

  consumers = [
    { team = "risk_team",      access_level = "READ" },
    { team = "analytics_team", access_level = "READ_MASKED" },
    { team = "finance_team",   access_level = "READ" },
  ]
}
```

---

## Cross-Region Consistency

### Metadata Replication Strategy

Data files stay in their region. Only metadata is replicated for discovery:

```
┌─────────────────────────────────────────────────────────┐
│                  Metadata Replication                     │
│                                                          │
│  Producer (EU-WEST)          Consumer (US-EAST)          │
│  ┌──────────────┐           ┌──────────────────┐        │
│  │ Polaris      │──CRR──▶   │ Metadata Cache    │        │
│  │ (source of   │  (S3)     │ (read replica)    │        │
│  │  truth)      │           │                    │        │
│  └──────────────┘           └──────────────────┘        │
│         │                            │                   │
│         ▼                            ▼                   │
│  s3://eu-west-iceberg/      s3://us-east-meta-cache/     │
│  metadata/                  eu-west-replicas/            │
│  snap-001.avro              snap-001.avro (replica)      │
│  v3.metadata.json           v3.metadata.json (replica)   │
│                                                          │
│  DATA FILES NEVER LEAVE EU                               │
│  s3://eu-west-iceberg/data/ ← queried directly via      │
│                                S3 cross-region access    │
└─────────────────────────────────────────────────────────┘
```

### Consistency Model

```python
class CrossRegionConsistencyManager:
    """
    Manages eventual consistency for cross-region catalog access.
    Uses version vectors to detect stale reads.
    """

    def __init__(self, region: str, catalog_clients: dict):
        self.local_region = region
        self.catalogs = catalog_clients
        self.version_cache = {}  # namespace.table -> (version, timestamp)

    async def load_table_consistent(
        self, namespace: str, table: str, consistency: str = "eventual"
    ):
        """
        Load table with configurable consistency:
        - "eventual": use local cache/replica (fast, may be stale)
        - "strong": always read from source region (slow, always fresh)
        - "bounded": accept staleness up to N seconds
        """
        source_region = self._get_source_region(namespace)

        if consistency == "eventual":
            # Try local replica first
            local = await self._load_local_replica(namespace, table)
            if local:
                return local
            # Fallback to source
            return await self._load_from_source(source_region, namespace, table)

        elif consistency == "strong":
            return await self._load_from_source(source_region, namespace, table)

        elif consistency.startswith("bounded:"):
            max_staleness = int(consistency.split(":")[1])
            cached = self.version_cache.get(f"{namespace}.{table}")
            if cached and (time.time() - cached[1]) < max_staleness:
                return await self._load_local_replica(namespace, table)
            return await self._load_from_source(source_region, namespace, table)

    async def _load_from_source(self, region: str, namespace: str, table: str):
        """Direct read from source region catalog."""
        client = self.catalogs[region]
        result = await client.load_table(namespace, table)
        # Update version cache
        self.version_cache[f"{namespace}.{table}"] = (
            result.metadata.current_snapshot_id,
            time.time()
        )
        return result
```

---

## Catalog Failover

```yaml
# Kubernetes deployment for federation router with failover
apiVersion: apps/v1
kind: Deployment
metadata:
  name: catalog-federation-router
  namespace: data-platform
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: router
          image: company/catalog-federation:3.2.1
          env:
            - name: FAILOVER_ENABLED
              value: "true"
            - name: HEALTH_CHECK_INTERVAL_MS
              value: "5000"
            - name: FAILOVER_THRESHOLD
              value: "3"  # 3 consecutive failures trigger failover
            - name: CIRCUIT_BREAKER_TIMEOUT_MS
              value: "30000"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            periodSeconds: 5
---
# Global DNS with health checks
apiVersion: externaldns.k8s.io/v1alpha1
kind: DNSEndpoint
metadata:
  name: catalog-global
spec:
  endpoints:
    - dnsName: catalog.global.company.com
      recordType: A
      targets:
        - 10.0.1.100  # us-east
        - 10.0.2.100  # eu-west
        - 10.0.3.100  # apac
      setIdentifier: geo-routing
      providerSpecific:
        - name: geo-routing-policy
          value: latency
```

---

## Nessie for Git-Like Governance (EU-Central Region)

The EU-Central team uses Nessie for branch-based governance:

```python
"""
Nessie enables Git-like workflows for data:
- Propose schema changes on a branch
- Review via PR (data PR, not code PR)
- Merge atomically when approved
- Rollback instantly if issues found
"""

from pynessie import init as nessie_init

nessie = nessie_init(
    endpoint="https://nessie.eu-central-1.internal.company.com/api/v2"
)

# Create branch for schema evolution
branch = nessie.create_branch(
    branch_name="feature/add-risk-score-column",
    from_ref="main"
)

# Make changes on branch (not affecting production)
# ... ALTER TABLE on branch ...

# List changes (like git diff)
diff = nessie.get_diff(
    from_ref="main",
    to_ref="feature/add-risk-score-column"
)
for entry in diff.entries:
    print(f"  {entry.change_type}: {entry.key}")

# Merge when reviewed (atomic, all-or-nothing)
nessie.merge(
    from_branch="feature/add-risk-score-column",
    to_branch="main",
    message="Add risk_score column - approved by @risk-lead"
)
```

---

## Monitoring & Observability

### Key Metrics

| Metric | Source | Alert Threshold |
|---|---|---|
| `catalog.request.latency.p99` | Federation router | > 500ms |
| `catalog.request.error_rate` | Federation router | > 1% |
| `catalog.cross_region.latency` | Router → regional catalog | > 200ms |
| `catalog.failover.count` | Circuit breaker | > 0 (page) |
| `data_product.freshness.lag_seconds` | Commit timestamps | Per contract SLA |
| `data_product.quality.null_rate` | dbt tests | Per contract |
| `access.denied.count` | OPA decisions | Spike detection |
| `residency.violation.attempted` | Router | > 0 (page + legal) |
| `catalog.tables.total` | Per-region catalogs | Capacity planning |
| `replication.lag.seconds` | S3 CRR metrics | > 60s |

### Audit Log Schema

```json
{
  "timestamp": "2024-03-15T14:22:01.332Z",
  "trace_id": "abc-123-def",
  "caller": {
    "team": "analytics_team",
    "service_account": "analytics-trino-prod",
    "region": "us-east-1",
    "ip": "10.0.5.42"
  },
  "action": "LOAD_TABLE",
  "target": {
    "namespace": "eu_west.payments.checkout_team.transactions.gold",
    "table": "gold",
    "source_region": "eu-west-1"
  },
  "decision": "ALLOWED_WITH_MASKING",
  "masked_columns": ["customer_email", "customer_phone"],
  "latency_ms": 142,
  "metadata_version": "v3.metadata.json",
  "snapshot_id": 7284619283746
}
```

### Grafana Dashboard Query (PromQL)

```promql
# Cross-region p99 latency by source region
histogram_quantile(0.99,
  sum(rate(catalog_request_duration_seconds_bucket{
    type="cross_region"
  }[5m])) by (le, source_region, target_region)
)

# Data product SLA compliance (% of products meeting freshness target)
(
  count(iceberg_table_last_commit_age_seconds < on(namespace) group_left
    data_contract_freshness_threshold_seconds)
  /
  count(iceberg_table_last_commit_age_seconds)
) * 100
```

---

## Data Product Governance

### Quality Scoring

Each data product gets a composite score (0-100):

| Dimension | Weight | Measurement |
|---|---|---|
| Freshness | 25% | Time since last commit vs SLA |
| Completeness | 20% | Null rate in required fields |
| Schema stability | 15% | Breaking changes in last 90 days |
| Documentation | 15% | Description coverage in contract |
| Consumer satisfaction | 15% | Survey + incident count |
| Availability | 10% | Uptime over 30-day window |

```sql
-- Quality score materialized view (runs hourly)
CREATE OR REPLACE VIEW governance.data_product_scores AS
SELECT
    namespace,
    owner_team,
    -- Freshness score (25%)
    CASE
        WHEN freshness_lag_seconds <= contract_freshness_sla THEN 25
        WHEN freshness_lag_seconds <= contract_freshness_sla * 2 THEN 15
        ELSE 0
    END AS freshness_score,
    -- Completeness score (20%)
    GREATEST(0, 20 - (null_rate_pct * 200)) AS completeness_score,
    -- Combined
    freshness_score + completeness_score + schema_score +
    doc_score + satisfaction_score + availability_score AS total_score,
    -- Tier based on score
    CASE
        WHEN total_score >= 90 THEN 'platinum'
        WHEN total_score >= 70 THEN 'gold'
        WHEN total_score >= 50 THEN 'silver'
        ELSE 'bronze'
    END AS quality_tier
FROM governance.product_metrics;
```

### Deprecation Policy

```yaml
# Deprecation lifecycle
stages:
  - name: announcement
    duration: "90 days"
    actions:
      - Add "deprecated" tag in DataHub
      - Notify all registered consumers
      - Add deprecation warning to catalog properties
      - Log warning on every access

  - name: migration_support
    duration: "60 days (overlaps with announcement)"
    actions:
      - Publish migration guide
      - Provide replacement table reference
      - Offer migration office hours

  - name: read_only
    duration: "30 days after announcement ends"
    actions:
      - Revoke write access (table becomes immutable)
      - Consumers still have read access
      - Automated weekly reminder to consumers

  - name: removal
    actions:
      - Soft delete (metadata retained 1 year for audit)
      - Data retained per retention policy (7 years for financial)
      - Namespace reclaimed after 30 days
```

---

## Scale Considerations

### At 100K+ Tables

| Challenge | Solution |
|---|---|
| Catalog listing is slow | Pagination + server-side filtering in REST API |
| Metadata storage grows | Metadata cleanup job (expire old snapshots) |
| Discovery is noisy | DataHub with quality tier filtering |
| Too many access grants | Role-based access (team roles, not individual grants) |
| Terraform state too large | Split state per domain (payments/, risk/, trading/) |
| Cross-region queries slow | Materialized aggregates in consumer region |

### Performance Targets

```
Catalog Operations:
  - loadTable:         p50 < 50ms,  p99 < 200ms  (same region)
  - loadTable:         p50 < 120ms, p99 < 500ms  (cross region)
  - listTables:        p50 < 100ms, p99 < 400ms  (up to 1000 tables)
  - commitTable:       p50 < 200ms, p99 < 1000ms (with contract validation)

Federation Router:
  - Routing overhead:  < 10ms (namespace lookup + auth)
  - Access control:    < 20ms (OPA evaluation cached)
  - Failover switch:   < 5s (circuit breaker open → route to backup)

Data Operations:
  - Cross-region JOIN: < 30s for 1M row result (predicate pushdown critical)
  - Metadata sync:     < 60s replication lag (S3 CRR)
  - Contract validation: < 500ms per commit
```

---

## Deployment Checklist

```markdown
## New Region Onboarding

- [ ] Deploy regional catalog (Polaris/Nessie/Custom)
- [ ] Configure S3/GCS bucket with encryption + versioning
- [ ] Add region to federation router routing table
- [ ] Configure S3 CRR for metadata replication
- [ ] Set up Trino catalog connector
- [ ] Deploy OPA policies for region
- [ ] Configure DataHub ingestion from new catalog
- [ ] Set up monitoring dashboards and alerts
- [ ] Load test: 10K concurrent metadata requests
- [ ] Failover test: kill primary, verify backup serves
- [ ] Residency test: verify cross-region blocks work
- [ ] Onboard first team with sample data product

## New Team Onboarding

- [ ] Assign namespace prefix
- [ ] Create IAM role / service account
- [ ] Register team in access control system
- [ ] Provide Terraform module + examples
- [ ] Create first data product (guided)
- [ ] Verify contract enforcement works
- [ ] Add team to DataHub ownership graph
- [ ] Schedule data mesh onboarding session
```

---

## Key Takeaways

1. **Iceberg's REST Catalog spec is the linchpin** — it provides a standard API that enables federation without engine-specific hacks.

2. **Separate metadata from data** — metadata is small, replicate it freely. Data stays in-region for residency compliance.

3. **Namespace conventions are governance** — encode ownership, region, and domain into the namespace structure and enforce it at the router level.

4. **Data contracts turn tables into products** — without contracts, a table is just a table. With contracts, consumers can depend on it.

5. **Column-level masking via views** — Iceberg views let you expose different "shapes" of the same table to different consumers without data duplication.

6. **Nessie for high-governance domains** — when you need auditable, reviewable schema changes (finance, compliance), Git-like branching is invaluable.

7. **Federation router is thin** — it's auth + routing + policy. Keep it stateless and fast. The heavy lifting stays in regional catalogs.

8. **Multi-cloud is achievable** — because Iceberg is just files + metadata, the catalog implementation can differ per region (Polaris on AWS, custom on GCP) as long as they speak REST Catalog protocol.
