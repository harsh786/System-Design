# Problem 77: Building a Data Contract Platform

## Problem 77: Building a Data Contract Platform

### Runnable Code
```python
"""
Data Contract Platform Implementation
=======================================
Implements producer-consumer data contracts:
- Schema contracts (structure)
- Quality contracts (SLAs)
- Semantic contracts (meaning)
- Breaking change detection

Run: python data_contracts.py
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class CompatibilityMode(Enum):
    BACKWARD = "backward"    # New schema can read old data
    FORWARD = "forward"      # Old schema can read new data
    FULL = "full"            # Both backward and forward
    NONE = "none"            # No compatibility guaranteed


class FieldType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class FieldDefinition:
    name: str
    type: FieldType
    nullable: bool = True
    description: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"min": 0, "max": 1000, "pattern": "^[A-Z]+$"}


@dataclass
class QualitySLA:
    """Quality guarantees the producer commits to"""
    freshness_minutes: int = 60      # Data no older than N minutes
    completeness_pct: float = 99.0    # % rows with no nulls in required fields
    uniqueness_fields: List[str] = field(default_factory=list)
    volume_min_rows: int = 0          # Minimum rows per batch
    volume_max_rows: int = 1000000    # Maximum rows per batch
    error_rate_max_pct: float = 1.0   # Max acceptable error rate


@dataclass
class DataContract:
    """
    A Data Contract is an agreement between data producer and consumers.
    
    It specifies:
    1. SCHEMA: What fields exist, their types, and constraints
    2. QUALITY: SLAs for freshness, completeness, uniqueness
    3. SEMANTICS: What the data means (business definitions)
    4. COMPATIBILITY: How the schema can evolve
    5. OWNERSHIP: Who is responsible
    """
    contract_id: str
    name: str
    version: str
    owner_team: str
    description: str
    fields: List[FieldDefinition]
    quality_sla: QualitySLA
    compatibility: CompatibilityMode = CompatibilityMode.BACKWARD
    consumers: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def get_schema(self) -> Dict[str, str]:
        return {f.name: f.type.value for f in self.fields}
    
    def get_required_fields(self) -> List[str]:
        return [f.name for f in self.fields if not f.nullable]


class ContractRegistry:
    """
    Central registry for all data contracts.
    
    In production: This would be backed by a database with:
    - Version history
    - Consumer subscriptions
    - Compatibility validation
    - Breaking change notifications
    """
    
    def __init__(self):
        self.contracts: Dict[str, DataContract] = {}
        self.contract_history: Dict[str, List[DataContract]] = {}
        self.violations: List[dict] = []
    
    def register(self, contract: DataContract) -> bool:
        """Register a new contract (or new version)"""
        existing = self.contracts.get(contract.name)
        
        if existing:
            # Check compatibility
            is_compatible = self._check_compatibility(existing, contract)
            if not is_compatible:
                print(f"  ERROR: Contract '{contract.name}' v{contract.version} "
                      f"is NOT compatible with v{existing.version}")
                return False
            
            # Store in history
            if contract.name not in self.contract_history:
                self.contract_history[contract.name] = []
            self.contract_history[contract.name].append(existing)
        
        self.contracts[contract.name] = contract
        print(f"  Registered contract '{contract.name}' v{contract.version}")
        return True
    
    def validate_data(self, contract_name: str, data: List[dict]) -> dict:
        """
        Validate data against its contract.
        Returns validation report.
        """
        contract = self.contracts.get(contract_name)
        if not contract:
            return {'valid': False, 'error': f'Contract {contract_name} not found'}
        
        report = {
            'contract': contract_name,
            'version': contract.version,
            'rows_checked': len(data),
            'schema_errors': [],
            'quality_errors': [],
            'is_valid': True
        }
        
        # Schema validation
        required_fields = contract.get_required_fields()
        for i, row in enumerate(data):
            for field in required_fields:
                if field not in row or row[field] is None:
                    report['schema_errors'].append(
                        f"Row {i}: Required field '{field}' is missing/null"
                    )
            
            # Type validation
            for field_def in contract.fields:
                if field_def.name in row and row[field_def.name] is not None:
                    if not self._validate_type(row[field_def.name], field_def.type):
                        report['schema_errors'].append(
                            f"Row {i}: Field '{field_def.name}' expected "
                            f"{field_def.type.value}, got {type(row[field_def.name]).__name__}"
                        )
                    
                    # Constraint validation
                    if field_def.constraints:
                        constraint_errors = self._validate_constraints(
                            row[field_def.name], field_def.constraints, field_def.name, i
                        )
                        report['schema_errors'].extend(constraint_errors)
        
        # Quality SLA validation
        sla = contract.quality_sla
        
        # Completeness check
        if required_fields:
            null_count = sum(
                1 for row in data 
                for f in required_fields 
                if f not in row or row[f] is None
            )
            completeness = (1 - null_count / max(len(data) * len(required_fields), 1)) * 100
            if completeness < sla.completeness_pct:
                report['quality_errors'].append(
                    f"Completeness {completeness:.1f}% < SLA {sla.completeness_pct}%"
                )
        
        # Volume check
        if len(data) < sla.volume_min_rows:
            report['quality_errors'].append(
                f"Volume {len(data)} < minimum {sla.volume_min_rows}"
            )
        if len(data) > sla.volume_max_rows:
            report['quality_errors'].append(
                f"Volume {len(data)} > maximum {sla.volume_max_rows}"
            )
        
        # Uniqueness check
        if sla.uniqueness_fields:
            seen_keys = set()
            duplicates = 0
            for row in data:
                key = tuple(row.get(f) for f in sla.uniqueness_fields)
                if key in seen_keys:
                    duplicates += 1
                seen_keys.add(key)
            if duplicates > 0:
                report['quality_errors'].append(
                    f"Found {duplicates} duplicate rows on {sla.uniqueness_fields}"
                )
        
        report['is_valid'] = (len(report['schema_errors']) == 0 and 
                              len(report['quality_errors']) == 0)
        
        if not report['is_valid']:
            self.violations.append({
                'contract': contract_name,
                'timestamp': datetime.now().isoformat(),
                'schema_errors': len(report['schema_errors']),
                'quality_errors': len(report['quality_errors'])
            })
        
        return report
    
    def _check_compatibility(self, old: DataContract, new: DataContract) -> bool:
        """Check if new contract version is compatible with old"""
        if old.compatibility == CompatibilityMode.NONE:
            return True
        
        old_fields = {f.name for f in old.fields}
        new_fields = {f.name for f in new.fields}
        new_required = {f.name for f in new.fields if not f.nullable}
        
        if old.compatibility in (CompatibilityMode.BACKWARD, CompatibilityMode.FULL):
            # New consumer must read old data → old fields must exist in new
            removed = old_fields - new_fields
            if removed:
                print(f"    Backward incompatible: removed fields {removed}")
                return False
        
        if old.compatibility in (CompatibilityMode.FORWARD, CompatibilityMode.FULL):
            # Old consumer must read new data → new required fields break old consumers
            new_required_added = new_required - old_fields
            if new_required_added:
                print(f"    Forward incompatible: new required fields {new_required_added}")
                return False
        
        return True
    
    def _validate_type(self, value: Any, expected: FieldType) -> bool:
        type_map = {
            FieldType.STRING: str,
            FieldType.INTEGER: int,
            FieldType.FLOAT: (int, float),
            FieldType.BOOLEAN: bool,
        }
        expected_type = type_map.get(expected)
        if expected_type:
            return isinstance(value, expected_type)
        return True
    
    def _validate_constraints(self, value: Any, constraints: dict, 
                             field_name: str, row_idx: int) -> List[str]:
        errors = []
        if 'min' in constraints and value < constraints['min']:
            errors.append(f"Row {row_idx}: {field_name}={value} < min={constraints['min']}")
        if 'max' in constraints and value > constraints['max']:
            errors.append(f"Row {row_idx}: {field_name}={value} > max={constraints['max']}")
        return errors


def run_data_contracts_demo():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       DATA CONTRACTS PLATFORM DEMONSTRATION                     ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Demonstrates:                                                   ║
║  • Contract definition (schema + quality SLAs)                   ║
║  • Contract registration with version management                 ║
║  • Data validation against contracts                             ║
║  • Compatibility checking (backward/forward)                     ║
║  • Breaking change detection                                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    registry = ContractRegistry()
    
    # Define contract v1
    print("=" * 60)
    print("STEP 1: Register Initial Contract (v1)")
    print("=" * 60)
    
    contract_v1 = DataContract(
        contract_id="orders-001",
        name="orders_stream",
        version="1.0.0",
        owner_team="order-service",
        description="Order events from checkout flow",
        fields=[
            FieldDefinition("order_id", FieldType.STRING, nullable=False,
                          description="Unique order identifier"),
            FieldDefinition("customer_id", FieldType.STRING, nullable=False),
            FieldDefinition("amount", FieldType.FLOAT, nullable=False,
                          constraints={"min": 0.01, "max": 100000}),
            FieldDefinition("currency", FieldType.STRING, nullable=False),
            FieldDefinition("status", FieldType.STRING, nullable=False),
            FieldDefinition("created_at", FieldType.TIMESTAMP, nullable=False),
            FieldDefinition("notes", FieldType.STRING, nullable=True),
        ],
        quality_sla=QualitySLA(
            freshness_minutes=5,
            completeness_pct=99.5,
            uniqueness_fields=["order_id"],
            volume_min_rows=100,
            volume_max_rows=50000,
            error_rate_max_pct=0.5
        ),
        compatibility=CompatibilityMode.BACKWARD,
        consumers=["analytics-team", "finance-team", "marketing-team"]
    )
    
    registry.register(contract_v1)
    
    # Validate good data
    print(f"\n{'=' * 60}")
    print("STEP 2: Validate GOOD Data Against Contract")
    print("=" * 60)
    
    good_data = [
        {"order_id": f"ORD-{i}", "customer_id": f"CUST-{i}", 
         "amount": 99.99, "currency": "USD", "status": "placed",
         "created_at": "2024-01-15T10:00:00Z", "notes": None}
        for i in range(500)
    ]
    
    report = registry.validate_data("orders_stream", good_data)
    print(f"  Valid: {report['is_valid']}")
    print(f"  Rows checked: {report['rows_checked']}")
    print(f"  Schema errors: {len(report['schema_errors'])}")
    print(f"  Quality errors: {len(report['quality_errors'])}")
    
    # Validate bad data
    print(f"\n{'=' * 60}")
    print("STEP 3: Validate BAD Data (Violations)")
    print("=" * 60)
    
    bad_data = [
        {"order_id": "ORD-1", "customer_id": "CUST-1", 
         "amount": 99.99, "currency": "USD", "status": "placed",
         "created_at": "2024-01-15"},
        {"order_id": "ORD-1", "amount": -50.0,  # duplicate + negative!
         "currency": "USD", "status": "placed", "created_at": "2024-01-15"},
        {"order_id": None, "customer_id": None,  # Required fields null!
         "amount": 200000, "currency": "USD", "status": "placed",
         "created_at": "2024-01-15"},
    ]
    
    report = registry.validate_data("orders_stream", bad_data)
    print(f"  Valid: {report['is_valid']}")
    print(f"  Schema errors: {len(report['schema_errors'])}")
    for err in report['schema_errors'][:5]:
        print(f"    - {err}")
    print(f"  Quality errors: {len(report['quality_errors'])}")
    for err in report['quality_errors']:
        print(f"    - {err}")
    
    # Schema evolution - compatible change
    print(f"\n{'=' * 60}")
    print("STEP 4: Compatible Schema Evolution (Add Optional Field)")
    print("=" * 60)
    
    contract_v2 = DataContract(
        contract_id="orders-002",
        name="orders_stream",
        version="2.0.0",
        owner_team="order-service",
        description="Order events with discount tracking",
        fields=[
            *contract_v1.fields,
            FieldDefinition("discount_pct", FieldType.FLOAT, nullable=True,
                          description="Applied discount percentage",
                          constraints={"min": 0, "max": 100}),
        ],
        quality_sla=contract_v1.quality_sla,
        compatibility=CompatibilityMode.BACKWARD,
        consumers=contract_v1.consumers
    )
    
    registry.register(contract_v2)  # Should succeed
    
    # Schema evolution - breaking change
    print(f"\n{'=' * 60}")
    print("STEP 5: BREAKING Schema Change (Remove Required Field)")
    print("=" * 60)
    
    contract_v3_breaking = DataContract(
        contract_id="orders-003",
        name="orders_stream",
        version="3.0.0",
        owner_team="order-service",
        description="Attempted breaking change",
        fields=[
            f for f in contract_v2.fields if f.name != "currency"  # REMOVED!
        ],
        quality_sla=contract_v2.quality_sla,
        compatibility=CompatibilityMode.BACKWARD,
        consumers=contract_v2.consumers
    )
    
    result = registry.register(contract_v3_breaking)  # Should FAIL
    print(f"  Registration {'succeeded' if result else 'REJECTED (as expected)'}")
    
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"""
  Contracts registered: {len(registry.contracts)}
  Contract violations: {len(registry.violations)}
  
  KEY INSIGHTS:
  • Contracts are agreements, not just schemas
  • Include quality SLAs (freshness, completeness, uniqueness)
  • Enforce compatibility (prevent breaking consumers)
  • Validate data at pipeline boundaries (producer side)
  • Alert on violations (before data reaches consumers)
    """)


if __name__ == '__main__':
    run_data_contracts_demo()
```

