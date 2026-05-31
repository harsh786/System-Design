"""
Data Quality Pipeline Simulator for AI Systems
================================================
Simulates data quality validation with quality gates,
SLA monitoring, drift detection, and quality reports.

Run: python3 main.py
No dependencies required (standard library only).
"""

import random
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# DATA MODELS
# =============================================================================

class QualityAction(Enum):
    PASS = "pass"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class QualityRule:
    name: str
    description: str
    severity: Severity
    check_fn: Any  # callable
    action_on_fail: QualityAction


@dataclass
class QualityResult:
    rule_name: str
    passed: bool
    severity: Severity
    action: QualityAction
    details: str = ""


@dataclass
class Record:
    id: str
    data: Dict[str, Any]
    timestamp: datetime
    source: str


@dataclass
class QualityReport:
    total_records: int = 0
    passed: int = 0
    quarantined: int = 0
    rejected: int = 0
    rule_violations: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    processing_time_ms: float = 0.0
    freshness_p50_sec: float = 0.0
    freshness_p99_sec: float = 0.0
    completeness_pct: float = 0.0


# =============================================================================
# QUALITY RULES ENGINE
# =============================================================================

class QualityGate:
    """Applies quality rules to records and routes them accordingly."""
    
    def __init__(self, name: str):
        self.name = name
        self.rules: List[QualityRule] = []
    
    def add_rule(self, rule: QualityRule) -> None:
        self.rules.append(rule)
    
    def validate(self, record: Record) -> Tuple[QualityAction, List[QualityResult]]:
        results = []
        worst_action = QualityAction.PASS
        
        for rule in self.rules:
            try:
                passed = rule.check_fn(record)
            except Exception as e:
                passed = False
            
            result = QualityResult(
                rule_name=rule.name,
                passed=passed,
                severity=rule.severity,
                action=rule.action_on_fail if not passed else QualityAction.PASS,
            )
            results.append(result)
            
            if not passed:
                if rule.action_on_fail == QualityAction.REJECT:
                    worst_action = QualityAction.REJECT
                elif rule.action_on_fail == QualityAction.QUARANTINE and worst_action != QualityAction.REJECT:
                    worst_action = QualityAction.QUARANTINE
        
        return worst_action, results


# =============================================================================
# SLA MONITOR
# =============================================================================

class SLAMonitor:
    """Monitors data freshness, volume, and quality SLAs."""
    
    def __init__(self):
        self.freshness_observations: List[float] = []
        self.volume_per_hour: Dict[int, int] = defaultdict(int)
        self.sla_breaches: List[Dict] = []
        
        # SLA thresholds
        self.max_freshness_sec = 900  # 15 minutes
        self.min_volume_per_hour = 100
        self.max_volume_per_hour = 10000
        self.max_reject_rate = 0.05  # 5%
    
    def record_freshness(self, event_time: datetime, landing_time: datetime) -> None:
        freshness_sec = (landing_time - event_time).total_seconds()
        self.freshness_observations.append(freshness_sec)
        
        if freshness_sec > self.max_freshness_sec:
            self.sla_breaches.append({
                "type": "freshness",
                "value": freshness_sec,
                "threshold": self.max_freshness_sec,
                "timestamp": landing_time.isoformat(),
            })
    
    def record_volume(self, hour: int, count: int) -> None:
        self.volume_per_hour[hour] += count
        
        if self.volume_per_hour[hour] > self.max_volume_per_hour:
            self.sla_breaches.append({
                "type": "volume_high",
                "value": self.volume_per_hour[hour],
                "threshold": self.max_volume_per_hour,
                "hour": hour,
            })
    
    def check_reject_rate(self, rejected: int, total: int) -> None:
        if total == 0:
            return
        rate = rejected / total
        if rate > self.max_reject_rate:
            self.sla_breaches.append({
                "type": "reject_rate",
                "value": f"{rate:.2%}",
                "threshold": f"{self.max_reject_rate:.2%}",
            })
    
    def get_freshness_stats(self) -> Dict[str, float]:
        if not self.freshness_observations:
            return {"p50": 0, "p95": 0, "p99": 0, "max": 0}
        sorted_obs = sorted(self.freshness_observations)
        n = len(sorted_obs)
        return {
            "p50": sorted_obs[int(n * 0.5)],
            "p95": sorted_obs[int(n * 0.95)],
            "p99": sorted_obs[min(int(n * 0.99), n - 1)],
            "max": sorted_obs[-1],
        }


# =============================================================================
# DRIFT DETECTOR
# =============================================================================

class DriftDetector:
    """Detects statistical drift in data distributions."""
    
    def __init__(self):
        self.baseline_stats: Dict[str, Dict] = {}
        self.current_stats: Dict[str, Dict] = {}
    
    def set_baseline(self, field_name: str, values: List[Any]) -> None:
        numeric = [v for v in values if isinstance(v, (int, float))]
        if numeric:
            self.baseline_stats[field_name] = {
                "mean": sum(numeric) / len(numeric),
                "min": min(numeric),
                "max": max(numeric),
                "count": len(numeric),
                "null_rate": (len(values) - len(numeric)) / len(values),
            }
    
    def check_drift(self, field_name: str, values: List[Any]) -> Optional[Dict]:
        if field_name not in self.baseline_stats:
            return None
        
        numeric = [v for v in values if isinstance(v, (int, float))]
        if not numeric:
            return {"field": field_name, "drift": "all_null", "severity": "critical"}
        
        current_mean = sum(numeric) / len(numeric)
        baseline_mean = self.baseline_stats[field_name]["mean"]
        current_null_rate = (len(values) - len(numeric)) / len(values)
        baseline_null_rate = self.baseline_stats[field_name]["null_rate"]
        
        drift_results = []
        
        # Mean drift check (>20% change)
        if baseline_mean != 0:
            mean_drift = abs(current_mean - baseline_mean) / abs(baseline_mean)
            if mean_drift > 0.2:
                drift_results.append({
                    "field": field_name,
                    "drift_type": "mean_shift",
                    "baseline": f"{baseline_mean:.2f}",
                    "current": f"{current_mean:.2f}",
                    "change": f"{mean_drift:.1%}",
                })
        
        # Null rate drift check (>5% absolute change)
        null_drift = abs(current_null_rate - baseline_null_rate)
        if null_drift > 0.05:
            drift_results.append({
                "field": field_name,
                "drift_type": "null_rate_change",
                "baseline": f"{baseline_null_rate:.1%}",
                "current": f"{current_null_rate:.1%}",
            })
        
        return drift_results if drift_results else None


# =============================================================================
# DATA QUALITY PIPELINE
# =============================================================================

class DataQualityPipeline:
    """End-to-end data quality pipeline with gates, SLAs, and drift detection."""
    
    def __init__(self):
        self.schema_gate = QualityGate("Schema Validation")
        self.business_gate = QualityGate("Business Rules")
        self.statistical_gate = QualityGate("Statistical Checks")
        self.sla_monitor = SLAMonitor()
        self.drift_detector = DriftDetector()
        
        self.passed_records: List[Record] = []
        self.quarantined_records: List[Record] = []
        self.rejected_records: List[Record] = []
        
        self._setup_rules()
    
    def _setup_rules(self):
        # Schema validation rules
        self.schema_gate.add_rule(QualityRule(
            name="required_fields",
            description="All required fields must be present",
            severity=Severity.CRITICAL,
            check_fn=lambda r: all(k in r.data for k in ["title", "content", "author"]),
            action_on_fail=QualityAction.REJECT,
        ))
        self.schema_gate.add_rule(QualityRule(
            name="valid_types",
            description="Fields must have correct types",
            severity=Severity.CRITICAL,
            check_fn=lambda r: isinstance(r.data.get("title"), str) and isinstance(r.data.get("word_count", 0), (int, float)),
            action_on_fail=QualityAction.REJECT,
        ))
        
        # Business rules
        self.business_gate.add_rule(QualityRule(
            name="content_not_empty",
            description="Content must have meaningful text",
            severity=Severity.WARNING,
            check_fn=lambda r: len(r.data.get("content", "")) > 50,
            action_on_fail=QualityAction.QUARANTINE,
        ))
        self.business_gate.add_rule(QualityRule(
            name="not_future_dated",
            description="Timestamp must not be in the future",
            severity=Severity.WARNING,
            check_fn=lambda r: r.timestamp <= datetime.now() + timedelta(minutes=5),
            action_on_fail=QualityAction.QUARANTINE,
        ))
        self.business_gate.add_rule(QualityRule(
            name="word_count_reasonable",
            description="Word count must be between 10 and 100000",
            severity=Severity.INFO,
            check_fn=lambda r: 10 <= r.data.get("word_count", 0) <= 100000,
            action_on_fail=QualityAction.QUARANTINE,
        ))
        
        # Statistical rules
        self.statistical_gate.add_rule(QualityRule(
            name="no_duplicate_id",
            description="Record ID must be unique in batch",
            severity=Severity.WARNING,
            check_fn=lambda r: True,  # Checked at batch level
            action_on_fail=QualityAction.QUARANTINE,
        ))
    
    def process_batch(self, records: List[Record]) -> QualityReport:
        """Process a batch of records through all quality gates."""
        start_time = time.time()
        report = QualityReport(total_records=len(records))
        
        # Check for duplicates at batch level
        seen_ids = set()
        
        for record in records:
            # Track freshness
            landing_time = datetime.now()
            self.sla_monitor.record_freshness(record.timestamp, landing_time)
            
            # Gate 1: Schema
            action, results = self.schema_gate.validate(record)
            if action == QualityAction.REJECT:
                self.rejected_records.append(record)
                report.rejected += 1
                for r in results:
                    if not r.passed:
                        report.rule_violations[r.rule_name] += 1
                continue
            
            # Gate 2: Business rules
            action, results = self.business_gate.validate(record)
            if action == QualityAction.QUARANTINE:
                self.quarantined_records.append(record)
                report.quarantined += 1
                for r in results:
                    if not r.passed:
                        report.rule_violations[r.rule_name] += 1
                continue
            
            # Duplicate check
            if record.id in seen_ids:
                self.quarantined_records.append(record)
                report.quarantined += 1
                report.rule_violations["duplicate_id"] += 1
                continue
            seen_ids.add(record.id)
            
            # Passed all gates
            self.passed_records.append(record)
            report.passed += 1
        
        # Compute report stats
        report.processing_time_ms = (time.time() - start_time) * 1000
        freshness_stats = self.sla_monitor.get_freshness_stats()
        report.freshness_p50_sec = freshness_stats["p50"]
        report.freshness_p99_sec = freshness_stats["p99"]
        report.completeness_pct = (report.passed / max(report.total_records, 1)) * 100
        
        # Check SLA on reject rate
        self.sla_monitor.check_reject_rate(report.rejected, report.total_records)
        
        return report


# =============================================================================
# DATA GENERATOR
# =============================================================================

def generate_documents(count: int, include_bad_data: bool = True) -> List[Record]:
    """Generate simulated documents with some quality issues."""
    records = []
    
    authors = ["alice", "bob", "charlie", "diana", "eve"]
    
    for i in range(count):
        # Normal record
        word_count = random.randint(100, 5000)
        content = f"Document content for record {i}. " * random.randint(5, 50)
        
        data = {
            "title": f"Document {i}: Analysis of Topic {random.randint(1, 100)}",
            "content": content,
            "author": random.choice(authors),
            "word_count": word_count,
            "category": random.choice(["engineering", "product", "research", "ops"]),
            "quality_score": random.uniform(0.5, 1.0),
        }
        
        timestamp = datetime.now() - timedelta(
            hours=random.uniform(0, 48),
            minutes=random.uniform(0, 60)
        )
        
        # Inject quality issues
        if include_bad_data:
            r = random.random()
            if r < 0.05:  # 5% missing required fields
                del data["content"]
            elif r < 0.08:  # 3% empty content
                data["content"] = "short"
            elif r < 0.10:  # 2% future-dated
                timestamp = datetime.now() + timedelta(days=random.randint(1, 30))
            elif r < 0.12:  # 2% unreasonable word count
                data["word_count"] = random.choice([-1, 0, 500000])
            elif r < 0.14:  # 2% wrong types
                data["word_count"] = "not a number"
        
        # Occasional duplicates
        record_id = f"doc_{i:05d}"
        if include_bad_data and random.random() < 0.02:
            record_id = f"doc_{max(0, i-1):05d}"  # Duplicate previous ID
        
        records.append(Record(
            id=record_id,
            data=data,
            timestamp=timestamp,
            source="document_ingestion_v2",
        ))
    
    return records


# =============================================================================
# MAIN SIMULATION
# =============================================================================

def main():
    print("=" * 70)
    print("DATA QUALITY PIPELINE SIMULATOR FOR AI SYSTEMS")
    print("=" * 70)
    
    # -------------------------------------------------------------------------
    # 1. Setup Pipeline
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 1: Pipeline Configuration")
    print("-" * 70)
    
    pipeline = DataQualityPipeline()
    
    print(f"""
  Quality Gates Configured:
  ├── Gate 1: Schema Validation (REJECT on fail)
  │   ├── Required fields present (title, content, author)
  │   └── Valid field types
  ├── Gate 2: Business Rules (QUARANTINE on fail)
  │   ├── Content length > 50 chars
  │   ├── Timestamp not in future
  │   └── Word count in range [10, 100000]
  └── Gate 3: Statistical Checks
      └── No duplicate IDs in batch

  SLA Thresholds:
  ├── Max freshness: 900 seconds (15 minutes)
  ├── Min volume/hour: 100 records
  ├── Max volume/hour: 10,000 records
  └── Max reject rate: 5%
""")
    
    # -------------------------------------------------------------------------
    # 2. Generate and Process Data
    # -------------------------------------------------------------------------
    print("-" * 70)
    print("STEP 2: Processing Document Batch")
    print("-" * 70)
    
    records = generate_documents(200, include_bad_data=True)
    print(f"\n  Generated {len(records)} documents (with injected quality issues)")
    
    report = pipeline.process_batch(records)
    
    print(f"\n  Processing Results:")
    print(f"  ├── Total records: {report.total_records}")
    print(f"  ├── Passed: {report.passed} ({report.passed/report.total_records:.1%})")
    print(f"  ├── Quarantined: {report.quarantined} ({report.quarantined/report.total_records:.1%})")
    print(f"  ├── Rejected: {report.rejected} ({report.rejected/report.total_records:.1%})")
    print(f"  └── Processing time: {report.processing_time_ms:.1f}ms")
    
    if report.rule_violations:
        print(f"\n  Rule Violations:")
        for rule, count in sorted(report.rule_violations.items(), key=lambda x: -x[1]):
            print(f"    {rule}: {count} violations")
    
    # -------------------------------------------------------------------------
    # 3. SLA Monitoring
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 3: SLA Monitoring")
    print("-" * 70)
    
    freshness = pipeline.sla_monitor.get_freshness_stats()
    print(f"\n  Freshness SLA (target: < 900 seconds):")
    print(f"  ├── p50: {freshness['p50']:.0f}s")
    print(f"  ├── p95: {freshness['p95']:.0f}s")
    print(f"  ├── p99: {freshness['p99']:.0f}s")
    print(f"  └── max: {freshness['max']:.0f}s")
    
    breaches = pipeline.sla_monitor.sla_breaches
    if breaches:
        print(f"\n  SLA Breaches Detected: {len(breaches)}")
        for breach in breaches[:5]:
            print(f"    [{breach['type']}] value={breach['value']}, threshold={breach['threshold']}")
    else:
        print(f"\n  No SLA breaches detected")
    
    # -------------------------------------------------------------------------
    # 4. Drift Detection
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 4: Distribution Drift Detection")
    print("-" * 70)
    
    drift_detector = DriftDetector()
    
    # Set baseline from first batch
    baseline_word_counts = [r.data.get("word_count", 0) for r in records[:100] 
                           if isinstance(r.data.get("word_count"), (int, float))]
    baseline_quality = [r.data.get("quality_score", 0) for r in records[:100]
                       if isinstance(r.data.get("quality_score"), (int, float))]
    
    drift_detector.set_baseline("word_count", baseline_word_counts)
    drift_detector.set_baseline("quality_score", baseline_quality)
    
    print(f"\n  Baseline established from first 100 records")
    print(f"  ├── word_count: mean={drift_detector.baseline_stats['word_count']['mean']:.0f}")
    print(f"  └── quality_score: mean={drift_detector.baseline_stats['quality_score']['mean']:.2f}")
    
    # Simulate a drifted batch (word counts much higher)
    print(f"\n  Simulating a drifted batch (word counts inflated)...")
    drifted_word_counts = [wc * 2.5 for wc in baseline_word_counts]  # 150% increase
    drifted_quality = [max(0, q - 0.3) for q in baseline_quality]  # Quality dropped
    
    drift_wc = drift_detector.check_drift("word_count", drifted_word_counts)
    drift_qs = drift_detector.check_drift("quality_score", drifted_quality)
    
    if drift_wc:
        print(f"\n  DRIFT DETECTED in word_count:")
        for d in drift_wc:
            print(f"    {d['drift_type']}: baseline={d.get('baseline')}, current={d.get('current')}, change={d.get('change', 'N/A')}")
    
    if drift_qs:
        print(f"\n  DRIFT DETECTED in quality_score:")
        for d in drift_qs:
            print(f"    {d['drift_type']}: baseline={d.get('baseline')}, current={d.get('current')}, change={d.get('change', 'N/A')}")
    
    # -------------------------------------------------------------------------
    # 5. Quality Report
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 5: Quality Report Summary")
    print("-" * 70)
    
    print(f"""
  ╔══════════════════════════════════════════════════════════════════╗
  ║                    DATA QUALITY REPORT                          ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║  Pipeline: document_ingestion_v2                                ║
  ║  Batch Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                          ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║  VOLUME                                                        ║
  ║    Total Records: {report.total_records:<6}                                     ║
  ║    Pass Rate: {report.completeness_pct:.1f}%                                       ║
  ║    Reject Rate: {report.rejected/max(report.total_records,1)*100:.1f}%                                      ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║  FRESHNESS                                                     ║
  ║    p50: {freshness['p50']:.0f}s | p99: {freshness['p99']:.0f}s | SLA: 900s              ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║  ACTIONS                                                       ║
  ║    Passed → AI Pipeline: {report.passed} records                        ║
  ║    Quarantined → Review: {report.quarantined} records                         ║
  ║    Rejected → Dead Letter: {report.rejected} records                        ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║  SLA STATUS: {'BREACH' if breaches else 'HEALTHY'}                                         ║
  ║  DRIFT STATUS: {'DETECTED' if (drift_wc or drift_qs) else 'STABLE'}                                      ║
  ╚══════════════════════════════════════════════════════════════════╝
""")
    
    print("  Key Insights for Staff Architects:")
    print("  1. Quality gates BLOCK bad data before it reaches AI models")
    print("  2. SLA monitoring catches freshness and volume anomalies")
    print("  3. Drift detection finds distribution shifts before model degradation")
    print("  4. Quarantine allows human review without blocking the pipeline")
    print("  5. Dead letter queue preserves rejected records for debugging")


if __name__ == "__main__":
    random.seed(42)
    main()
