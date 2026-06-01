# Data Contract Enforcement Pipeline

## Problem Statement

In large organizations with 100+ data producers and consumers, schema changes in upstream systems cascade into downstream failures: broken dashboards, failed ML pipelines, incorrect reports. Without formal data contracts, a simple column rename can break 50 downstream jobs. At scale, we need automated contract testing, breaking change detection before deployment, consumer notification, and schema evolution rules that prevent incompatible changes while still allowing innovation.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Producer (CI/CD)"
        DEV[Developer<br/>Schema Change]
        PR[Pull Request]
        CI[CI Pipeline<br/>Contract Tests]
        DEPLOY[Deploy to Prod]
    end

    subgraph "Contract Registry"
        SR[Schema Registry<br/>Confluent/Apicurio]
        CR[Contract Store<br/>Git Repository]
        COMPAT[Compatibility<br/>Checker]
        CATALOG[Data Catalog<br/>+ Lineage]
    end

    subgraph "Enforcement Layer"
        GATE[Schema Gate<br/>(Pre-production)]
        RUNTIME[Runtime Validator<br/>(In Kafka)]
        INTERCEPT[Interceptor<br/>(Connect SMT)]
    end

    subgraph "Notification"
        IMPACT[Impact Analyzer<br/>Affected Consumers]
        NOTIFY[Notification Service<br/>Slack/Email/PagerDuty]
        APPROVAL[Approval Workflow<br/>Breaking Changes]
    end

    subgraph "Testing"
        CONTRACT_TEST[Contract Test<br/>Suite]
        CONSUMER_TEST[Consumer<br/>Compatibility Test]
        SYNTHETIC[Synthetic Data<br/>Generator]
    end

    subgraph "Monitoring"
        VIOLATIONS[Violation<br/>Dashboard]
        METRICS[Schema Evolution<br/>Metrics]
        LINEAGE[Data Lineage<br/>Graph]
    end

    DEV --> PR --> CI
    CI --> CONTRACT_TEST
    CI --> CONSUMER_TEST
    CI --> COMPAT

    COMPAT --> GATE
    GATE -->|Pass| DEPLOY
    GATE -->|Fail| IMPACT
    IMPACT --> NOTIFY
    NOTIFY --> APPROVAL

    DEPLOY --> SR
    SR --> RUNTIME
    RUNTIME --> INTERCEPT

    CONTRACT_TEST --> SYNTHETIC
    COMPAT --> CATALOG
    CATALOG --> LINEAGE

    RUNTIME --> VIOLATIONS
    COMPAT --> METRICS
```

## Component Breakdown

### Schema Evolution Rules (Avro)

```
Compatibility Modes:
┌─────────────────┬──────────────────────────────────────────────┐
│ Mode            │ Allowed Changes                              │
├─────────────────┼──────────────────────────────────────────────┤
│ BACKWARD        │ Delete fields, add optional fields           │
│                 │ (new schema can read old data)               │
├─────────────────┼──────────────────────────────────────────────┤
│ FORWARD         │ Add fields, delete optional fields           │
│                 │ (old schema can read new data)               │
├─────────────────┼──────────────────────────────────────────────┤
│ FULL            │ Add/delete optional fields only              │
│                 │ (both directions compatible)                 │
├─────────────────┼──────────────────────────────────────────────┤
│ BACKWARD_TRANS  │ BACKWARD across all registered versions      │
├─────────────────┼──────────────────────────────────────────────┤
│ FULL_TRANSITIVE │ FULL across all versions (safest)            │
└─────────────────┴──────────────────────────────────────────────┘
```

### Protobuf Evolution Rules

```protobuf
// SAFE changes (backward compatible):
// 1. Add new optional field
// 2. Add new oneof member
// 3. Rename field (wire format uses numbers)
// 4. Add new enum value

// BREAKING changes:
// 1. Remove/rename field number
// 2. Change field type
// 3. Change field from optional to required
// 4. Remove enum value
// 5. Change field number

// Example: Safe evolution
syntax = "proto3";

message OrderEvent {
  string order_id = 1;
  string customer_id = 2;
  double amount = 3;
  string status = 4;
  int64 created_at_ms = 5;
  
  // v2: Added fields (safe - backward compatible)
  string currency = 6;           // New optional field
  repeated Item items = 7;       // New repeated field
  string shipping_method = 8;    // New optional field
  
  // NEVER reuse field numbers 1-8 if removed
  reserved 9, 10;               // Reserve for future removal
  reserved "deprecated_field";   // Reserve removed field names
}

message Item {
  string product_id = 1;
  int32 quantity = 2;
  double unit_price = 3;
}
```

### Contract Definition and Testing

```yaml
# data-contract.yaml - lives in producer's repository
apiVersion: datacontract.com/v1.0.0
id: orders-placed-contract
info:
  title: Order Placed Events
  version: 2.1.0
  owner: order-team
  contact:
    email: order-team@company.com
    slack: "#order-team-data"

servers:
  production:
    type: kafka
    host: kafka-prod.internal:9092
    topic: orders.public.placed
    format: avro
    schemaRegistryUrl: http://schema-registry:8081

models:
  OrderPlaced:
    description: "Emitted when a customer successfully places an order"
    type: object
    fields:
      order_id:
        type: string
        format: uuid
        required: true
        unique: true
        description: "Globally unique order identifier"
      customer_id:
        type: string
        required: true
        pii: true
        classification: confidential
      total_amount:
        type: number
        minimum: 0.01
        maximum: 999999.99
        required: true
      currency:
        type: string
        enum: [USD, EUR, GBP, JPY, CAD, AUD]
        required: true
      status:
        type: string
        enum: [placed, confirmed, processing]
        required: true
      items:
        type: array
        minItems: 1
        required: true
        items:
          type: object
          fields:
            product_id:
              type: string
              required: true
            quantity:
              type: integer
              minimum: 1
            unit_price:
              type: number
              minimum: 0.01
      placed_at:
        type: timestamp
        required: true

quality:
  type: SodaCL
  specification:
    checks:
      - freshness(placed_at) < 5m
      - row_count > 0 for last 1h
      - duplicate_count(order_id) = 0
      - invalid_count(total_amount) = 0:
          valid min: 0.01
      - invalid_count(currency) = 0:
          valid values: [USD, EUR, GBP, JPY, CAD, AUD]

servicelevels:
  availability:
    percentage: 99.9%
  freshness:
    threshold: 5 minutes
    percentile: p99
  throughput:
    threshold: 50000
    unit: events/second
  latency:
    p50: 500ms
    p99: 2000ms
```

### CI Pipeline Contract Validation

```python
class ContractValidator:
    """
    Runs in CI pipeline on every schema change PR.
    Blocks merge if breaking changes detected without approval.
    """
    
    def __init__(self, schema_registry_url: str, contract_store: str):
        self.registry = SchemaRegistryClient(schema_registry_url)
        self.contracts = ContractStore(contract_store)
    
    def validate_pr(self, changed_files: list) -> ValidationResult:
        results = []
        
        for file in changed_files:
            if file.endswith('.avsc') or file.endswith('.proto'):
                result = self._validate_schema_change(file)
                results.append(result)
            elif file.endswith('contract.yaml'):
                result = self._validate_contract_change(file)
                results.append(result)
        
        return ValidationResult(results)
    
    def _validate_schema_change(self, schema_file: str) -> dict:
        new_schema = self._load_schema(schema_file)
        subject = self._get_subject(schema_file)
        
        # Check compatibility with Schema Registry
        is_compatible = self.registry.test_compatibility(subject, new_schema)
        
        if not is_compatible:
            # Identify what broke
            breaking_changes = self._identify_breaking_changes(subject, new_schema)
            affected_consumers = self._find_affected_consumers(subject)
            
            return {
                'status': 'BREAKING',
                'file': schema_file,
                'breaking_changes': breaking_changes,
                'affected_consumers': affected_consumers,
                'action_required': 'Requires approval from affected consumer teams',
                'alternatives': self._suggest_compatible_alternatives(breaking_changes)
            }
        
        return {'status': 'COMPATIBLE', 'file': schema_file}
    
    def _identify_breaking_changes(self, subject: str, new_schema) -> list:
        current = self.registry.get_latest_version(subject)
        changes = []
        
        # Compare fields
        current_fields = {f['name']: f for f in current.get('fields', [])}
        new_fields = {f['name']: f for f in new_schema.get('fields', [])}
        
        # Removed required fields
        for name, field in current_fields.items():
            if name not in new_fields and not field.get('default'):
                changes.append({
                    'type': 'FIELD_REMOVED',
                    'field': name,
                    'severity': 'BREAKING',
                    'impact': 'Consumers reading this field will get null/error'
                })
        
        # Type changes
        for name in set(current_fields) & set(new_fields):
            if current_fields[name]['type'] != new_fields[name]['type']:
                changes.append({
                    'type': 'TYPE_CHANGED',
                    'field': name,
                    'from': current_fields[name]['type'],
                    'to': new_fields[name]['type'],
                    'severity': 'BREAKING'
                })
        
        return changes
    
    def _find_affected_consumers(self, subject: str) -> list:
        """Query data lineage to find all consumers of this schema"""
        return self.contracts.get_consumers_of(subject)
    
    def _suggest_compatible_alternatives(self, breaking_changes: list) -> list:
        suggestions = []
        for change in breaking_changes:
            if change['type'] == 'FIELD_REMOVED':
                suggestions.append(
                    f"Instead of removing '{change['field']}', "
                    f"deprecate it (add @deprecated annotation) and add new field"
                )
            elif change['type'] == 'TYPE_CHANGED':
                suggestions.append(
                    f"Instead of changing type of '{change['field']}', "
                    f"add a new field with the new type and deprecate the old one"
                )
        return suggestions
```

### Breaking Change Approval Workflow

```python
class BreakingChangeWorkflow:
    """
    When a breaking change is detected:
    1. Identify affected consumers
    2. Notify consumer teams
    3. Require explicit approval from all affected teams
    4. Provide migration timeline
    5. Only then allow deployment
    """
    
    async def initiate_breaking_change(self, change: dict):
        # Create approval request
        approval = {
            'id': str(uuid.uuid4()),
            'producer': change['producer_team'],
            'schema_subject': change['subject'],
            'breaking_changes': change['changes'],
            'affected_consumers': change['consumers'],
            'proposed_migration_date': datetime.utcnow() + timedelta(days=30),
            'status': 'pending_approval',
            'approvals_needed': len(change['consumers']),
            'approvals_received': []
        }
        
        # Notify each affected team
        for consumer in change['consumers']:
            await self.notify(consumer['team'], {
                'type': 'breaking_schema_change',
                'message': f"Schema change in {change['subject']} will break your consumer",
                'details': change['changes'],
                'action': f"Approve or request extension: {approval['id']}",
                'deadline': approval['proposed_migration_date']
            })
        
        # Block PR until all approvals received
        await self.github.add_check(
            change['pr_url'],
            status='pending',
            description=f"Waiting for {len(change['consumers'])} consumer team approvals"
        )
```

### Runtime Contract Enforcement

```python
class RuntimeContractEnforcer:
    """
    Kafka interceptor that validates messages against contracts in real-time.
    Can operate in: ENFORCE (reject), WARN (log + pass), AUDIT (log only) modes.
    """
    
    def __init__(self, mode: str = 'WARN'):
        self.mode = mode  # ENFORCE, WARN, AUDIT
        self.metrics = MetricsCollector()
    
    def on_produce(self, topic: str, message: bytes, headers: dict) -> bool:
        contract = self.get_contract(topic)
        if not contract:
            return True  # No contract, allow
        
        violations = self._validate(message, contract)
        
        if violations:
            self.metrics.increment(f'contract.violation.{topic}', tags={
                'violation_type': violations[0]['type']
            })
            
            if self.mode == 'ENFORCE':
                raise ContractViolationError(f"Message violates contract: {violations}")
            elif self.mode == 'WARN':
                log.warning(f"Contract violation on {topic}: {violations}")
                return True  # Allow but log
            else:  # AUDIT
                self._audit_log(topic, violations)
                return True
        
        return True
    
    def _validate(self, message: bytes, contract: dict) -> list:
        violations = []
        data = self._deserialize(message)
        
        # Required fields
        for field in contract.get('required_fields', []):
            if field not in data or data[field] is None:
                violations.append({'type': 'missing_required', 'field': field})
        
        # Type validation
        for field, spec in contract.get('fields', {}).items():
            if field in data:
                if not self._type_matches(data[field], spec['type']):
                    violations.append({'type': 'type_mismatch', 'field': field,
                                     'expected': spec['type'], 'actual': type(data[field]).__name__})
                if 'enum' in spec and data[field] not in spec['enum']:
                    violations.append({'type': 'invalid_enum', 'field': field, 
                                     'value': data[field]})
        
        return violations
```

## Data Flow

```
Schema Change Lifecycle:

1. Developer modifies schema (.avsc/.proto) in PR
2. CI pipeline triggers contract validation
3. Compatibility check against Schema Registry
4. If compatible → auto-merge allowed
5. If breaking:
   a. Impact analysis identifies affected consumers
   b. Notifications sent to consumer teams
   c. Approval workflow initiated
   d. PR blocked until approvals received
   e. Migration timeline agreed
6. On deploy: new schema version registered
7. Runtime: messages validated against contract
8. Monitoring: violations tracked, SLAs measured
```

## Scaling Strategies

| Component | Scaling Approach |
|-----------|-----------------|
| Schema Registry | Single leader + read replicas (low write volume) |
| Contract validation | Stateless, run in CI (scales with PRs) |
| Runtime enforcement | Kafka interceptor (per broker, low overhead) |
| Notification | Queue-based (Slack/email API limits) |
| Impact analysis | Pre-computed lineage graph (updated on schema change) |

## Failure Handling

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Schema Registry down | Can't serialize/deserialize | Local schema cache (stale ok) |
| Contract test flaky | Blocks legitimate PRs | Retry + manual override option |
| False positive breaking | Delays deployments | Review process, escalation path |
| Consumer doesn't update | Will break on deprecation | Hard deadline + auto-disable |
| Runtime validator crash | No enforcement | Fail-open (allow messages) |

## Cost Optimization

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Schema Registry | ~$400 | Single instance + standby |
| CI contract tests | ~$100 | Part of existing CI |
| Impact analysis service | ~$200 | Small compute |
| Notification service | ~$50 | Low volume |
| Monitoring | ~$200 | Prometheus + Grafana |
| **Total** | **~$950/month** | Prevents $100K+ incident costs |

### ROI
```
Cost of a breaking change incident:
- 4 hours engineer time × 5 engineers = 20 engineer-hours = $5,000
- Dashboard downtime = $10,000 business impact
- ML pipeline retraining = $2,000 compute
- Total per incident: ~$17,000

With contract enforcement:
- Incidents reduced from 4/month to 0.2/month
- Monthly savings: ~$64,000
- Monthly cost: ~$950
- ROI: 67x
```

## Real-World Companies

| Company | Approach | Tool |
|---------|----------|------|
| **Confluent** | Schema Registry + compatibility modes | Native product |
| **Netflix** | Schema evolution governance | Custom tooling |
| **Uber** | Schema-on-read with contract validation | Custom (Schemaless) |
| **Airbnb** | Data quality + schema contracts | Custom + Great Expectations |
| **Spotify** | Protobuf contracts + CI validation | Custom pipeline |
| **GoCardless** | Contract-first API design | Pact + Schema Registry |
| **Thoughtworks** | Data contracts advocacy | Open source tooling |
| **PayPal** | Schema governance platform | Custom enterprise |
