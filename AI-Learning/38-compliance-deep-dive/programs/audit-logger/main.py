"""
Compliance-Ready AI Audit Logger
=================================
Simulates tamper-evident audit logging for AI systems with:
- Full interaction logging with required metadata
- Retention policy enforcement
- Data subject access request (DSAR) handling
- Tamper-evident hash chains
- Audit trail report generation
- Compliance evidence export

Standard library only. No API keys required.
"""

import json
import hashlib
import datetime
import uuid
import os
import tempfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional
from collections import defaultdict


class EventType(Enum):
    INFERENCE = "inference"
    MODEL_DEPLOYMENT = "model_deployment"
    MODEL_ROLLBACK = "model_rollback"
    ACCESS_GRANT = "access_grant"
    ACCESS_REVOKE = "access_revoke"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"
    DATA_ACCESS = "data_access"
    DSAR_REQUEST = "dsar_request"
    DSAR_RESPONSE = "dsar_response"


class RetentionTier(Enum):
    OPERATIONAL = "operational"      # 0-90 days
    COMPLIANCE = "compliance"        # 90 days - 3 years
    ARCHIVE = "archive"             # 3-7 years
    PERMANENT = "permanent"         # Never deleted


@dataclass
class AuditRecord:
    """A single tamper-evident audit log entry."""
    record_id: str
    timestamp: str
    event_type: str
    actor_id: str
    actor_type: str  # user, service, system
    system_id: str
    model_version: str
    action: str
    input_hash: str  # SHA-256 of input (not raw input)
    output_hash: str  # SHA-256 of output
    metadata: Dict = field(default_factory=dict)
    retention_tier: str = RetentionTier.COMPLIANCE.value
    previous_hash: str = ""  # Chain to previous record
    record_hash: str = ""    # Hash of this record


@dataclass
class DSARRequest:
    """Data Subject Access Request."""
    request_id: str
    subject_id: str
    request_type: str  # access, deletion, correction, portability
    submitted_at: str
    due_date: str  # 30 days for GDPR
    status: str = "pending"  # pending, in_progress, completed, denied
    completed_at: Optional[str] = None
    response_summary: Optional[str] = None


class TamperEvidentLog:
    """Hash-chain based tamper-evident logging."""

    def __init__(self):
        self.records: List[AuditRecord] = []
        self.chain_head: str = self._genesis_hash()

    def _genesis_hash(self) -> str:
        """Create genesis block hash."""
        genesis = "AUDIT_LOG_GENESIS_" + datetime.datetime.now().isoformat()
        return hashlib.sha256(genesis.encode()).hexdigest()

    def _compute_record_hash(self, record: AuditRecord) -> str:
        """Compute hash of record including chain to previous."""
        content = (
            record.record_id +
            record.timestamp +
            record.event_type +
            record.actor_id +
            record.action +
            record.input_hash +
            record.output_hash +
            record.previous_hash
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def append(self, record: AuditRecord) -> AuditRecord:
        """Append record to tamper-evident chain."""
        record.previous_hash = self.chain_head
        record.record_hash = self._compute_record_hash(record)
        self.chain_head = record.record_hash
        self.records.append(record)
        return record

    def verify_integrity(self) -> Dict:
        """Verify the entire chain has not been tampered with."""
        if not self.records:
            return {"valid": True, "records_checked": 0}

        errors = []
        for i, record in enumerate(self.records):
            # Verify hash
            expected_hash = self._compute_record_hash(record)
            if record.record_hash != expected_hash:
                errors.append(f"Record {i} ({record.record_id}): hash mismatch")

            # Verify chain
            if i > 0 and record.previous_hash != self.records[i - 1].record_hash:
                errors.append(f"Record {i} ({record.record_id}): chain broken")

        return {
            "valid": len(errors) == 0,
            "records_checked": len(self.records),
            "errors": errors,
            "chain_head": self.chain_head,
        }


class RetentionManager:
    """Manages data retention policies for audit logs."""

    RETENTION_DAYS = {
        RetentionTier.OPERATIONAL: 90,
        RetentionTier.COMPLIANCE: 1095,   # 3 years
        RetentionTier.ARCHIVE: 2555,      # 7 years
        RetentionTier.PERMANENT: None,    # Never
    }

    def __init__(self):
        self.deletion_log: List[Dict] = []

    def classify_retention(self, event_type: EventType) -> RetentionTier:
        """Determine retention tier based on event type."""
        if event_type in (EventType.SECURITY_EVENT, EventType.ACCESS_GRANT, EventType.ACCESS_REVOKE):
            return RetentionTier.ARCHIVE
        elif event_type in (EventType.MODEL_DEPLOYMENT, EventType.MODEL_ROLLBACK):
            return RetentionTier.PERMANENT
        elif event_type == EventType.INFERENCE:
            return RetentionTier.COMPLIANCE
        else:
            return RetentionTier.COMPLIANCE

    def enforce_retention(self, records: List[AuditRecord], current_date: datetime.datetime) -> List[AuditRecord]:
        """Remove records past retention period. Returns retained records."""
        retained = []
        for record in records:
            tier = RetentionTier(record.retention_tier)
            max_days = self.RETENTION_DAYS[tier]

            if max_days is None:
                retained.append(record)
                continue

            record_date = datetime.datetime.fromisoformat(record.timestamp)
            age_days = (current_date - record_date).days

            if age_days <= max_days:
                retained.append(record)
            else:
                self.deletion_log.append({
                    "record_id": record.record_id,
                    "deleted_at": current_date.isoformat(),
                    "reason": f"Exceeded {tier.value} retention ({max_days} days)",
                    "record_hash": record.record_hash,  # Keep hash for audit
                })

        return retained

    def get_deletion_report(self) -> Dict:
        """Report on all records deleted under retention policy."""
        return {
            "total_deleted": len(self.deletion_log),
            "deletions": self.deletion_log,
        }


class DSARHandler:
    """Handle Data Subject Access Requests for AI audit logs."""

    def __init__(self):
        self.requests: List[DSARRequest] = []

    def submit_request(self, subject_id: str, request_type: str) -> DSARRequest:
        """Submit a new DSAR."""
        now = datetime.datetime.now()
        request = DSARRequest(
            request_id=str(uuid.uuid4()),
            subject_id=subject_id,
            request_type=request_type,
            submitted_at=now.isoformat(),
            due_date=(now + datetime.timedelta(days=30)).isoformat(),
            status="pending",
        )
        self.requests.append(request)
        return request

    def process_access_request(self, request: DSARRequest, records: List[AuditRecord]) -> Dict:
        """Process a data access request - find all records for subject."""
        subject_records = [
            r for r in records
            if r.actor_id == request.subject_id or
            r.metadata.get("subject_id") == request.subject_id
        ]

        request.status = "completed"
        request.completed_at = datetime.datetime.now().isoformat()
        request.response_summary = f"Found {len(subject_records)} records for subject."

        # Return sanitized records (remove internal hashes)
        sanitized = []
        for r in subject_records:
            sanitized.append({
                "timestamp": r.timestamp,
                "event_type": r.event_type,
                "action": r.action,
                "metadata": {k: v for k, v in r.metadata.items() if k != "internal"},
            })

        return {
            "request_id": request.request_id,
            "subject_id": request.subject_id,
            "records_found": len(sanitized),
            "records": sanitized,
            "completed_at": request.completed_at,
        }

    def process_deletion_request(self, request: DSARRequest, records: List[AuditRecord]) -> Dict:
        """Process right-to-deletion request."""
        # Note: Some records cannot be deleted (legal hold, regulatory requirement)
        deletable = []
        non_deletable = []

        for r in records:
            if r.actor_id == request.subject_id or r.metadata.get("subject_id") == request.subject_id:
                tier = RetentionTier(r.retention_tier)
                if tier == RetentionTier.PERMANENT:
                    non_deletable.append(r.record_id)
                else:
                    deletable.append(r.record_id)

        request.status = "completed"
        request.completed_at = datetime.datetime.now().isoformat()

        return {
            "request_id": request.request_id,
            "records_deleted": len(deletable),
            "records_retained": len(non_deletable),
            "retention_reason": "Legal/regulatory hold" if non_deletable else None,
            "deleted_record_ids": deletable,
        }

    def get_dsar_report(self) -> Dict:
        """Generate DSAR compliance report."""
        total = len(self.requests)
        completed = sum(1 for r in self.requests if r.status == "completed")
        overdue = sum(
            1 for r in self.requests
            if r.status == "pending" and
            datetime.datetime.fromisoformat(r.due_date) < datetime.datetime.now()
        )

        return {
            "total_requests": total,
            "completed": completed,
            "pending": total - completed,
            "overdue": overdue,
            "average_response_days": "N/A" if not completed else "simulated",
            "compliance_rate": f"{(completed / total * 100):.1f}%" if total > 0 else "N/A",
        }


class ComplianceAuditLogger:
    """Main audit logger combining all compliance features."""

    def __init__(self, system_id: str):
        self.system_id = system_id
        self.log = TamperEvidentLog()
        self.retention_manager = RetentionManager()
        self.dsar_handler = DSARHandler()
        self.stats = defaultdict(int)

    def log_inference(self, actor_id: str, model_version: str,
                      input_data: str, output_data: str,
                      metadata: Optional[Dict] = None) -> AuditRecord:
        """Log an AI inference event."""
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.INFERENCE.value,
            actor_id=actor_id,
            actor_type="service",
            system_id=self.system_id,
            model_version=model_version,
            action="inference_request",
            input_hash=hashlib.sha256(input_data.encode()).hexdigest(),
            output_hash=hashlib.sha256(output_data.encode()).hexdigest(),
            metadata=metadata or {},
            retention_tier=RetentionTier.COMPLIANCE.value,
        )
        self.log.append(record)
        self.stats["inferences"] += 1
        return record

    def log_security_event(self, actor_id: str, event_description: str,
                           severity: str = "medium") -> AuditRecord:
        """Log a security event (injection attempt, auth failure, etc.)."""
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.SECURITY_EVENT.value,
            actor_id=actor_id,
            actor_type="system",
            system_id=self.system_id,
            model_version="N/A",
            action=event_description,
            input_hash="",
            output_hash="",
            metadata={"severity": severity},
            retention_tier=RetentionTier.ARCHIVE.value,
        )
        self.log.append(record)
        self.stats["security_events"] += 1
        return record

    def log_model_deployment(self, actor_id: str, model_version: str,
                             details: Dict) -> AuditRecord:
        """Log a model deployment or rollback."""
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.MODEL_DEPLOYMENT.value,
            actor_id=actor_id,
            actor_type="user",
            system_id=self.system_id,
            model_version=model_version,
            action="model_deployed",
            input_hash="",
            output_hash="",
            metadata=details,
            retention_tier=RetentionTier.PERMANENT.value,
        )
        self.log.append(record)
        self.stats["deployments"] += 1
        return record

    def log_data_access(self, actor_id: str, resource: str,
                        access_type: str) -> AuditRecord:
        """Log data access for compliance."""
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.DATA_ACCESS.value,
            actor_id=actor_id,
            actor_type="user",
            system_id=self.system_id,
            model_version="N/A",
            action=f"{access_type}:{resource}",
            input_hash="",
            output_hash="",
            metadata={"resource": resource, "access_type": access_type},
            retention_tier=RetentionTier.ARCHIVE.value,
        )
        self.log.append(record)
        self.stats["data_accesses"] += 1
        return record

    def generate_audit_report(self) -> str:
        """Generate comprehensive audit trail report."""
        integrity = self.log.verify_integrity()
        lines = []
        lines.append("=" * 60)
        lines.append("COMPLIANCE AUDIT TRAIL REPORT")
        lines.append("=" * 60)
        lines.append(f"System: {self.system_id}")
        lines.append(f"Report Generated: {datetime.datetime.now().isoformat()}")
        lines.append(f"Total Records: {len(self.log.records)}")
        lines.append("")

        # Integrity verification
        lines.append("CHAIN INTEGRITY VERIFICATION:")
        lines.append(f"  Valid: {integrity['valid']}")
        lines.append(f"  Records Checked: {integrity['records_checked']}")
        if integrity['errors']:
            for error in integrity['errors']:
                lines.append(f"  ERROR: {error}")
        else:
            lines.append("  No tampering detected.")
        lines.append("")

        # Event summary
        lines.append("EVENT SUMMARY:")
        event_counts = defaultdict(int)
        for record in self.log.records:
            event_counts[record.event_type] += 1
        for event_type, count in sorted(event_counts.items()):
            lines.append(f"  {event_type}: {count}")
        lines.append("")

        # Retention status
        lines.append("RETENTION TIER DISTRIBUTION:")
        tier_counts = defaultdict(int)
        for record in self.log.records:
            tier_counts[record.retention_tier] += 1
        for tier, count in sorted(tier_counts.items()):
            lines.append(f"  {tier}: {count} records")
        lines.append("")

        # DSAR status
        dsar_report = self.dsar_handler.get_dsar_report()
        lines.append("DSAR COMPLIANCE:")
        lines.append(f"  Total Requests: {dsar_report['total_requests']}")
        lines.append(f"  Completed: {dsar_report['completed']}")
        lines.append(f"  Overdue: {dsar_report['overdue']}")
        lines.append("")

        # Recent records sample
        lines.append("RECENT RECORDS (last 5):")
        for record in self.log.records[-5:]:
            lines.append(f"  [{record.timestamp}] {record.event_type} | "
                        f"actor={record.actor_id} | action={record.action}")
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def export_compliance_evidence(self) -> Dict:
        """Export structured compliance evidence for auditors."""
        integrity = self.log.verify_integrity()

        return {
            "export_metadata": {
                "system_id": self.system_id,
                "export_date": datetime.datetime.now().isoformat(),
                "export_format": "compliance_evidence_v1",
                "total_records": len(self.log.records),
            },
            "integrity_verification": integrity,
            "event_statistics": dict(self.stats),
            "retention_compliance": {
                "policy_enforced": True,
                "deletions": self.retention_manager.get_deletion_report(),
            },
            "dsar_compliance": self.dsar_handler.get_dsar_report(),
            "chain_head_hash": self.log.chain_head,
            "sample_records": [
                asdict(r) for r in self.log.records[:3]
            ] if self.log.records else [],
        }


def demo():
    """Demonstrate the compliance audit logger."""
    print("=" * 60)
    print("COMPLIANCE-READY AI AUDIT LOGGER DEMO")
    print("=" * 60)

    # Initialize logger
    logger = ComplianceAuditLogger(system_id="ai-platform-prod-001")

    # Simulate AI interactions
    print("\n[1] Logging AI inference events...")
    for i in range(5):
        logger.log_inference(
            actor_id=f"service-api-{i % 3}",
            model_version="gpt-4-fine-tuned-v2.1",
            input_data=f"User query {i}: What is the policy for...",
            output_data=f"Response {i}: Based on our analysis...",
            metadata={"latency_ms": 150 + i * 20, "tokens": 500 + i * 50},
        )
    print(f"  Logged 5 inference events.")

    # Simulate security events
    print("\n[2] Logging security events...")
    logger.log_security_event(
        actor_id="external-ip-192.168.1.100",
        event_description="prompt_injection_attempt_detected",
        severity="high",
    )
    logger.log_security_event(
        actor_id="user-jane",
        event_description="authentication_failure",
        severity="medium",
    )
    print("  Logged 2 security events.")

    # Simulate model deployment
    print("\n[3] Logging model deployment...")
    logger.log_model_deployment(
        actor_id="ml-engineer-bob",
        model_version="gpt-4-fine-tuned-v2.2",
        details={
            "reason": "Performance improvement",
            "validation_score": 0.95,
            "approved_by": "ml-lead-alice",
        },
    )
    print("  Logged 1 model deployment.")

    # Simulate data access
    print("\n[4] Logging data access...")
    logger.log_data_access(
        actor_id="data-scientist-carol",
        resource="training_dataset_v3",
        access_type="read",
    )
    print("  Logged 1 data access event.")

    # Verify integrity
    print("\n[5] Verifying chain integrity...")
    integrity = logger.log.verify_integrity()
    print(f"  Chain valid: {integrity['valid']}")
    print(f"  Records verified: {integrity['records_checked']}")

    # Handle DSAR
    print("\n[6] Processing Data Subject Access Request...")
    dsar = logger.dsar_handler.submit_request(
        subject_id="service-api-1",
        request_type="access",
    )
    result = logger.dsar_handler.process_access_request(dsar, logger.log.records)
    print(f"  DSAR {dsar.request_id[:8]}... completed.")
    print(f"  Records found for subject: {result['records_found']}")

    # Generate audit report
    print("\n[7] Generating audit report...")
    report = logger.generate_audit_report()
    print(report)

    # Export evidence
    print("\n[8] Exporting compliance evidence...")
    evidence = logger.export_compliance_evidence()
    print(f"  Evidence exported: {evidence['export_metadata']['total_records']} records")
    print(f"  Chain integrity: {evidence['integrity_verification']['valid']}")
    print(f"  DSAR compliance rate: {evidence['dsar_compliance']['compliance_rate']}")

    # Demonstrate retention enforcement
    print("\n[9] Simulating retention enforcement (fast-forward 100 days)...")
    future_date = datetime.datetime.now() + datetime.timedelta(days=100)
    retained = logger.retention_manager.enforce_retention(logger.log.records, future_date)
    print(f"  Records retained: {len(retained)}/{len(logger.log.records)}")
    deletion_report = logger.retention_manager.get_deletion_report()
    print(f"  Records deleted: {deletion_report['total_deleted']}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    demo()
