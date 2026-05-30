"""
Privacy Engine for AI Systems
==============================
Comprehensive privacy management: classification, PII detection, consent,
purpose tracking, anonymization, and privacy-safe logging.
"""

import re
import hashlib
import hmac
import json
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

# =============================================================================
# DATA CLASSIFICATION
# =============================================================================

class DataSensitivity(Enum):
    PUBLIC = 0        # Marketing content, public docs
    INTERNAL = 1     # Internal business data
    CONFIDENTIAL = 2 # Customer data, PII
    RESTRICTED = 3   # SSN, health records, payment cards


class DataCategory(Enum):
    DIRECT_IDENTIFIER = "direct_identifier"      # Name, email, SSN
    QUASI_IDENTIFIER = "quasi_identifier"        # Age, zip, job title
    SENSITIVE_ATTRIBUTE = "sensitive_attribute"   # Health, politics
    BEHAVIORAL = "behavioral"                    # Browsing, purchases
    BUSINESS = "business"                        # Revenue, strategy
    TECHNICAL = "technical"                      # Logs, metrics
    PUBLIC = "public"                            # Published content


@dataclass
class ClassificationResult:
    sensitivity: DataSensitivity
    categories: list[DataCategory]
    pii_detected: list[dict]
    confidence: float
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DataClassificationEngine:
    """Classifies data by sensitivity level and category."""

    def __init__(self):
        self._rules: list[dict] = []
        self._custom_patterns: dict[str, re.Pattern] = {}
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default classification rules."""
        self._rules = [
            {
                "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
                "sensitivity": DataSensitivity.RESTRICTED,
                "category": DataCategory.DIRECT_IDENTIFIER,
                "label": "SSN",
            },
            {
                "pattern": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                "sensitivity": DataSensitivity.RESTRICTED,
                "category": DataCategory.DIRECT_IDENTIFIER,
                "label": "credit_card",
            },
            {
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "sensitivity": DataSensitivity.CONFIDENTIAL,
                "category": DataCategory.DIRECT_IDENTIFIER,
                "label": "email",
            },
            {
                "pattern": r"\b(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
                "sensitivity": DataSensitivity.CONFIDENTIAL,
                "category": DataCategory.DIRECT_IDENTIFIER,
                "label": "phone",
            },
            {
                "pattern": r"\b\d{5}(-\d{4})?\b",
                "sensitivity": DataSensitivity.INTERNAL,
                "category": DataCategory.QUASI_IDENTIFIER,
                "label": "zip_code",
            },
        ]

    def classify(self, text: str, context: Optional[dict] = None) -> ClassificationResult:
        """Classify a piece of text for sensitivity."""
        pii_found = []
        max_sensitivity = DataSensitivity.PUBLIC
        categories = set()

        for rule in self._rules:
            matches = re.finditer(rule["pattern"], text)
            for match in matches:
                pii_found.append({
                    "type": rule["label"],
                    "value_hash": hashlib.sha256(match.group().encode()).hexdigest()[:16],
                    "position": {"start": match.start(), "end": match.end()},
                    "sensitivity": rule["sensitivity"].name,
                })
                if rule["sensitivity"].value > max_sensitivity.value:
                    max_sensitivity = rule["sensitivity"]
                categories.add(rule["category"])

        # Check custom patterns
        for label, pattern in self._custom_patterns.items():
            matches = pattern.finditer(text)
            for match in matches:
                pii_found.append({
                    "type": label,
                    "value_hash": hashlib.sha256(match.group().encode()).hexdigest()[:16],
                    "position": {"start": match.start(), "end": match.end()},
                    "sensitivity": DataSensitivity.CONFIDENTIAL.name,
                })
                if DataSensitivity.CONFIDENTIAL.value > max_sensitivity.value:
                    max_sensitivity = DataSensitivity.CONFIDENTIAL
                categories.add(DataCategory.DIRECT_IDENTIFIER)

        confidence = 0.95 if pii_found else 0.7
        reasoning = (
            f"Found {len(pii_found)} PII instances. Max sensitivity: {max_sensitivity.name}"
            if pii_found else "No PII detected via pattern matching."
        )

        return ClassificationResult(
            sensitivity=max_sensitivity,
            categories=list(categories) or [DataCategory.PUBLIC],
            pii_detected=pii_found,
            confidence=confidence,
            reasoning=reasoning,
        )

    def add_custom_pattern(self, label: str, pattern: str):
        """Add organization-specific PII pattern."""
        self._custom_patterns[label] = re.compile(pattern)


# =============================================================================
# PII DETECTION AND REDACTION
# =============================================================================

@dataclass
class PIIEntity:
    entity_type: str
    value: str
    start: int
    end: int
    confidence: float
    detection_method: str  # "regex" or "ner"


class PIIDetector:
    """Detects PII using regex patterns and optionally NER models."""

    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone_us": r"\b(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "date_of_birth": r"\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b",
        "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
        "drivers_license": r"\b[A-Z]\d{7,8}\b",
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b",
        "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
        "api_key": r"\b(?:sk|pk)[-_][a-zA-Z0-9]{32,}\b",
    }

    NAME_INDICATORS = [
        r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b",
        r"\bmy name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        r"\bI am\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
    ]

    ADDRESS_PATTERN = (
        r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s?){1,3}"
        r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Way|Ct|Court)"
        r"\.?(?:\s*,?\s*(?:Apt|Suite|Unit|#)\s*\d+)?\b"
    )

    def __init__(self, custom_patterns: Optional[dict[str, str]] = None):
        self._patterns = {**self.PATTERNS}
        if custom_patterns:
            self._patterns.update(custom_patterns)

    def detect(self, text: str) -> list[PIIEntity]:
        """Detect all PII entities in text."""
        entities = []

        # Regex-based detection
        for pii_type, pattern in self._patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(PIIEntity(
                    entity_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    detection_method="regex",
                ))

        # Name detection
        for pattern in self.NAME_INDICATORS:
            for match in re.finditer(pattern, text):
                entities.append(PIIEntity(
                    entity_type="person_name",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,
                    detection_method="regex",
                ))

        # Address detection
        for match in re.finditer(self.ADDRESS_PATTERN, text, re.IGNORECASE):
            entities.append(PIIEntity(
                entity_type="address",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.75,
                detection_method="regex",
            ))

        return sorted(entities, key=lambda e: e.start)

    def detect_with_context(self, text: str, context: dict) -> list[PIIEntity]:
        """Detect PII with additional context (e.g., known user fields)."""
        entities = self.detect(text)

        # Check if known user data appears in text
        known_values = context.get("known_pii_values", {})
        for field_name, value in known_values.items():
            if value and value in text:
                start = text.index(value)
                entities.append(PIIEntity(
                    entity_type=f"known_{field_name}",
                    value=value,
                    start=start,
                    end=start + len(value),
                    confidence=1.0,
                    detection_method="context_match",
                ))

        return sorted(entities, key=lambda e: e.start)


class PIIRedactor:
    """Redacts PII from text using various strategies."""

    class Strategy(Enum):
        FULL = "full"                  # [REDACTED]
        TYPE_PRESERVING = "type"       # [EMAIL], [PHONE]
        PARTIAL = "partial"            # ***-**-1234
        TOKENIZED = "tokenized"        # {token_abc123}
        HASH = "hash"                  # SHA256 prefix

    def __init__(
        self,
        strategy: "PIIRedactor.Strategy" = None,
        token_secret: Optional[str] = None,
    ):
        self.strategy = strategy or self.Strategy.TYPE_PRESERVING
        self._token_secret = token_secret or "default-secret-change-me"
        self._token_map: dict[str, str] = {}

    def redact(self, text: str, entities: list[PIIEntity]) -> str:
        """Redact PII entities from text."""
        if not entities:
            return text

        # Process from end to start to preserve positions
        result = text
        for entity in sorted(entities, key=lambda e: e.start, reverse=True):
            replacement = self._get_replacement(entity)
            result = result[:entity.start] + replacement + result[entity.end:]

        return result

    def _get_replacement(self, entity: PIIEntity) -> str:
        match self.strategy:
            case self.Strategy.FULL:
                return "[REDACTED]"
            case self.Strategy.TYPE_PRESERVING:
                return f"[{entity.entity_type.upper()}]"
            case self.Strategy.PARTIAL:
                return self._partial_redact(entity)
            case self.Strategy.TOKENIZED:
                return self._tokenize(entity)
            case self.Strategy.HASH:
                h = hashlib.sha256(entity.value.encode()).hexdigest()[:12]
                return f"[HASH:{h}]"
            case _:
                return "[REDACTED]"

    def _partial_redact(self, entity: PIIEntity) -> str:
        value = entity.value
        if entity.entity_type == "ssn":
            return f"***-**-{value[-4:]}"
        elif entity.entity_type == "credit_card":
            digits = re.sub(r"\D", "", value)
            return f"****-****-****-{digits[-4:]}"
        elif entity.entity_type == "email":
            local, domain = value.split("@")
            return f"{local[0]}***@{domain}"
        elif entity.entity_type == "phone_us":
            digits = re.sub(r"\D", "", value)
            return f"(***) ***-{digits[-4:]}"
        else:
            if len(value) > 4:
                return "*" * (len(value) - 4) + value[-4:]
            return "[REDACTED]"

    def _tokenize(self, entity: PIIEntity) -> str:
        if entity.value not in self._token_map:
            token = hmac.new(
                self._token_secret.encode(),
                entity.value.encode(),
                hashlib.sha256,
            ).hexdigest()[:16]
            self._token_map[entity.value] = f"{{tok_{token}}}"
        return self._token_map[entity.value]


# =============================================================================
# PURPOSE TRACKING
# =============================================================================

class DataPurpose(Enum):
    CONVERSATION = "active_conversation"
    PERSONALIZATION = "user_personalization"
    ANALYTICS = "aggregate_analytics"
    MODEL_TRAINING = "model_improvement"
    EVALUATION = "system_evaluation"
    DEBUGGING = "incident_investigation"
    COMPLIANCE = "regulatory_compliance"
    BILLING = "billing_and_metering"


@dataclass
class PurposeRecord:
    data_id: str
    purposes: list[DataPurpose]
    collected_at: datetime
    collected_by: str  # system/component that collected it
    consent_ref: Optional[str] = None  # reference to consent record
    retention_until: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


class PurposeTracker:
    """Tracks why data was collected and what it can be used for."""

    def __init__(self, storage_backend=None):
        self._records: dict[str, PurposeRecord] = {}
        self._access_log: list[dict] = []

    def register_data(
        self,
        data_id: str,
        purposes: list[DataPurpose],
        collected_by: str,
        consent_ref: Optional[str] = None,
        retention_days: Optional[int] = None,
    ) -> PurposeRecord:
        """Register data with its allowed purposes."""
        record = PurposeRecord(
            data_id=data_id,
            purposes=purposes,
            collected_at=datetime.utcnow(),
            collected_by=collected_by,
            consent_ref=consent_ref,
            retention_until=(
                datetime.utcnow() + timedelta(days=retention_days)
                if retention_days else None
            ),
        )
        self._records[data_id] = record
        return record

    def check_purpose(self, data_id: str, intended_purpose: DataPurpose) -> bool:
        """Check if data can be used for a given purpose."""
        record = self._records.get(data_id)
        if not record:
            return False

        # Check retention
        if record.retention_until and datetime.utcnow() > record.retention_until:
            return False

        allowed = intended_purpose in record.purposes
        self._access_log.append({
            "data_id": data_id,
            "intended_purpose": intended_purpose.value,
            "allowed": allowed,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return allowed

    def revoke_purpose(self, data_id: str, purpose: DataPurpose):
        """Revoke a purpose for specific data."""
        record = self._records.get(data_id)
        if record and purpose in record.purposes:
            record.purposes.remove(purpose)

    def get_data_by_purpose(self, purpose: DataPurpose) -> list[str]:
        """Find all data registered for a specific purpose."""
        return [
            data_id for data_id, record in self._records.items()
            if purpose in record.purposes
        ]

    def get_expired_data(self) -> list[str]:
        """Find data past its retention period."""
        now = datetime.utcnow()
        return [
            data_id for data_id, record in self._records.items()
            if record.retention_until and now > record.retention_until
        ]


# =============================================================================
# CONSENT MANAGEMENT
# =============================================================================

class ConsentStatus(Enum):
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"


@dataclass
class ConsentRecord:
    consent_id: str
    user_id: str
    purpose: DataPurpose
    data_types: list[str]  # What types of data this consent covers
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    source: str = ""  # How consent was obtained (UI, API, form)
    version: str = ""  # Version of privacy policy at time of consent


class ConsentManager:
    """Manages user consent for data processing purposes."""

    def __init__(self):
        self._consents: dict[str, list[ConsentRecord]] = {}  # user_id -> records
        self._history: list[dict] = []

    def grant_consent(
        self,
        user_id: str,
        purpose: DataPurpose,
        data_types: list[str],
        source: str = "user_action",
        policy_version: str = "1.0",
        expires_in_days: Optional[int] = None,
    ) -> ConsentRecord:
        """Record user granting consent."""
        record = ConsentRecord(
            consent_id=str(uuid.uuid4()),
            user_id=user_id,
            purpose=purpose,
            data_types=data_types,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.utcnow(),
            expires_at=(
                datetime.utcnow() + timedelta(days=expires_in_days)
                if expires_in_days else None
            ),
            source=source,
            version=policy_version,
        )

        if user_id not in self._consents:
            self._consents[user_id] = []
        self._consents[user_id].append(record)

        self._history.append({
            "action": "grant",
            "consent_id": record.consent_id,
            "user_id": user_id,
            "purpose": purpose.value,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return record

    def withdraw_consent(self, user_id: str, purpose: DataPurpose) -> list[ConsentRecord]:
        """Withdraw consent for a specific purpose. Returns affected records."""
        affected = []
        for record in self._consents.get(user_id, []):
            if record.purpose == purpose and record.status == ConsentStatus.GRANTED:
                record.status = ConsentStatus.WITHDRAWN
                record.withdrawn_at = datetime.utcnow()
                affected.append(record)

        self._history.append({
            "action": "withdraw",
            "user_id": user_id,
            "purpose": purpose.value,
            "affected_count": len(affected),
            "timestamp": datetime.utcnow().isoformat(),
        })

        return affected

    def check_consent(
        self,
        user_id: str,
        purpose: DataPurpose,
        data_type: Optional[str] = None,
    ) -> bool:
        """Check if user has active consent for a purpose."""
        for record in self._consents.get(user_id, []):
            if record.purpose != purpose:
                continue
            if record.status != ConsentStatus.GRANTED:
                continue
            if record.expires_at and datetime.utcnow() > record.expires_at:
                record.status = ConsentStatus.EXPIRED
                continue
            if data_type and data_type not in record.data_types:
                continue
            return True
        return False

    def get_user_consents(self, user_id: str) -> list[ConsentRecord]:
        """Get all consent records for a user."""
        return self._consents.get(user_id, [])

    def get_users_with_consent(self, purpose: DataPurpose) -> list[str]:
        """Get all users who have active consent for a purpose."""
        users = []
        for user_id, records in self._consents.items():
            for record in records:
                if (record.purpose == purpose and
                    record.status == ConsentStatus.GRANTED and
                    (not record.expires_at or datetime.utcnow() <= record.expires_at)):
                    users.append(user_id)
                    break
        return users


# =============================================================================
# PRIVACY IMPACT ASSESSMENT
# =============================================================================

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PIAQuestion:
    category: str
    question: str
    risk_if_yes: RiskLevel
    mitigation_suggestion: str


@dataclass
class PIAResult:
    assessment_id: str
    feature_name: str
    assessed_by: str
    assessed_at: datetime
    overall_risk: RiskLevel
    answers: list[dict]
    mitigations: list[str]
    decision: str  # "proceed", "modify", "reject"
    notes: str = ""


class PrivacyImpactAssessment:
    """Automated privacy impact assessment tool."""

    QUESTIONS = [
        PIAQuestion(
            "data_collection",
            "Does this feature collect new personal data?",
            RiskLevel.MEDIUM,
            "Apply data minimization. Document what's collected and why.",
        ),
        PIAQuestion(
            "data_collection",
            "Does this feature process sensitive/restricted data (health, financial, biometric)?",
            RiskLevel.CRITICAL,
            "Require explicit consent. Apply encryption at rest and in transit. Limit access.",
        ),
        PIAQuestion(
            "data_sharing",
            "Does data leave our infrastructure (sent to vendor APIs)?",
            RiskLevel.HIGH,
            "Review vendor DPA. Minimize data sent. Consider on-premise alternatives.",
        ),
        PIAQuestion(
            "data_sharing",
            "Is data shared across tenant boundaries?",
            RiskLevel.CRITICAL,
            "Implement strict tenant isolation. Never share raw data across tenants.",
        ),
        PIAQuestion(
            "data_retention",
            "Is data stored beyond the immediate transaction?",
            RiskLevel.MEDIUM,
            "Define retention period. Implement automated cleanup. Document justification.",
        ),
        PIAQuestion(
            "data_retention",
            "Does this create data that's difficult to delete (embeddings, model weights)?",
            RiskLevel.HIGH,
            "Design deletion strategy before launch. Consider re-indexing/retraining procedures.",
        ),
        PIAQuestion(
            "purpose",
            "Could this data be used for purposes beyond the stated one?",
            RiskLevel.HIGH,
            "Implement purpose limitation controls. Log all access with declared purpose.",
        ),
        PIAQuestion(
            "ai_specific",
            "Does user data enter LLM prompts?",
            RiskLevel.MEDIUM,
            "Implement prompt redaction. Minimize context. Review what's sent to vendors.",
        ),
        PIAQuestion(
            "ai_specific",
            "Does this feature create persistent memory about users?",
            RiskLevel.HIGH,
            "Implement memory deletion. Track memory provenance. Honor deletion requests.",
        ),
        PIAQuestion(
            "ai_specific",
            "Could model outputs leak training/context data?",
            RiskLevel.HIGH,
            "Test for data leakage. Implement output filtering. Monitor for PII in responses.",
        ),
        PIAQuestion(
            "logging",
            "Are prompts or responses logged with PII?",
            RiskLevel.MEDIUM,
            "Implement log redaction. Set short retention. Restrict access to logs.",
        ),
        PIAQuestion(
            "deletion",
            "Can all user data be fully deleted upon request?",
            RiskLevel.HIGH,
            "Map all data locations. Implement cascading deletion. Verify with tests.",
        ),
    ]

    def conduct_assessment(
        self,
        feature_name: str,
        assessed_by: str,
        answers: dict[int, bool],
        notes: str = "",
    ) -> PIAResult:
        """Conduct a privacy impact assessment."""
        results = []
        mitigations = []
        max_risk = RiskLevel.LOW

        for i, question in enumerate(self.QUESTIONS):
            answer = answers.get(i, False)
            results.append({
                "category": question.category,
                "question": question.question,
                "answer": answer,
                "risk_level": question.risk_if_yes.value if answer else "none",
                "mitigation": question.mitigation_suggestion if answer else None,
            })
            if answer:
                if question.risk_if_yes.value > max_risk.value:
                    max_risk = question.risk_if_yes
                mitigations.append(question.mitigation_suggestion)

        # Determine decision based on risk
        if max_risk == RiskLevel.CRITICAL:
            decision = "reject"
        elif max_risk == RiskLevel.HIGH:
            decision = "modify"
        else:
            decision = "proceed"

        return PIAResult(
            assessment_id=str(uuid.uuid4()),
            feature_name=feature_name,
            assessed_by=assessed_by,
            assessed_at=datetime.utcnow(),
            overall_risk=max_risk,
            answers=results,
            mitigations=mitigations,
            decision=decision,
            notes=notes,
        )


# =============================================================================
# DATA LINEAGE TRACKING
# =============================================================================

@dataclass
class DataFlowEdge:
    source_system: str
    destination_system: str
    data_types: list[str]
    purpose: DataPurpose
    transformation: str  # "raw", "redacted", "anonymized", "aggregated"
    created_at: datetime = field(default_factory=datetime.utcnow)


class DataLineageTracker:
    """Tracks where data flows across systems."""

    def __init__(self):
        self._flows: list[DataFlowEdge] = []
        self._data_locations: dict[str, list[str]] = {}  # data_id -> [systems]

    def record_flow(
        self,
        source: str,
        destination: str,
        data_types: list[str],
        purpose: DataPurpose,
        transformation: str = "raw",
    ) -> DataFlowEdge:
        """Record a data flow between systems."""
        edge = DataFlowEdge(
            source_system=source,
            destination_system=destination,
            data_types=data_types,
            purpose=purpose,
            transformation=transformation,
        )
        self._flows.append(edge)
        return edge

    def record_data_location(self, data_id: str, system: str):
        """Record that a specific data item exists in a system."""
        if data_id not in self._data_locations:
            self._data_locations[data_id] = []
        if system not in self._data_locations[data_id]:
            self._data_locations[data_id].append(system)

    def find_data_locations(self, data_id: str) -> list[str]:
        """Find all systems where a data item exists."""
        return self._data_locations.get(data_id, [])

    def find_downstream_systems(self, source_system: str) -> list[str]:
        """Find all systems that receive data from a source."""
        downstream = set()
        visited = set()
        queue = [source_system]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            for flow in self._flows:
                if flow.source_system == current:
                    downstream.add(flow.destination_system)
                    queue.append(flow.destination_system)

        return list(downstream)

    def get_flow_map(self) -> dict:
        """Get complete data flow map for visualization."""
        return {
            "nodes": list({f.source_system for f in self._flows} |
                         {f.destination_system for f in self._flows}),
            "edges": [
                {
                    "source": f.source_system,
                    "destination": f.destination_system,
                    "data_types": f.data_types,
                    "purpose": f.purpose.value,
                    "transformation": f.transformation,
                }
                for f in self._flows
            ],
        }


# =============================================================================
# ANONYMIZATION AND PSEUDONYMIZATION
# =============================================================================

class Anonymizer:
    """Irreversible data anonymization."""

    def __init__(self):
        self._generalizations = {
            "age": lambda v: f"{(int(v) // 10) * 10}-{(int(v) // 10) * 10 + 9}",
            "zip": lambda v: v[:3] + "**",
            "date": lambda v: v[:4],  # Keep only year
        }

    def anonymize_record(self, record: dict, config: dict) -> dict:
        """
        Anonymize a record based on config.
        
        Config example:
        {
            "remove": ["name", "email", "ssn"],
            "generalize": {"age": "age", "zip_code": "zip"},
            "noise": {"salary": 5000},
            "keep": ["department", "role"]
        }
        """
        result = {}

        for field, value in record.items():
            if field in config.get("remove", []):
                continue
            elif field in config.get("generalize", {}):
                gen_type = config["generalize"][field]
                if gen_type in self._generalizations:
                    result[field] = self._generalizations[gen_type](str(value))
                else:
                    result[field] = "[GENERALIZED]"
            elif field in config.get("noise", {}):
                import random
                noise_range = config["noise"][field]
                result[field] = value + random.uniform(-noise_range, noise_range)
            elif field in config.get("keep", []):
                result[field] = value
            # Fields not in any category are removed (safe default)

        return result

    def k_anonymity_check(self, records: list[dict], quasi_identifiers: list[str], k: int) -> bool:
        """Check if dataset satisfies k-anonymity."""
        from collections import Counter
        groups = Counter()
        for record in records:
            key = tuple(record.get(qi) for qi in quasi_identifiers)
            groups[key] += 1
        return all(count >= k for count in groups.values())


class Pseudonymizer:
    """Reversible pseudonymization with consistent tokens."""

    def __init__(self, secret_key: str):
        self._secret = secret_key.encode()
        self._forward_map: dict[str, str] = {}
        self._reverse_map: dict[str, str] = {}

    def pseudonymize(self, value: str, domain: str = "default") -> str:
        """Replace value with consistent pseudonym."""
        key = f"{domain}:{value}"
        if key not in self._forward_map:
            token = hmac.new(
                self._secret,
                key.encode(),
                hashlib.sha256,
            ).hexdigest()[:16]
            pseudonym = f"pseudo_{domain}_{token}"
            self._forward_map[key] = pseudonym
            self._reverse_map[pseudonym] = value
        return self._forward_map[key]

    def de_pseudonymize(self, pseudonym: str) -> Optional[str]:
        """Reverse pseudonymization (requires access to mapping)."""
        return self._reverse_map.get(pseudonym)

    def pseudonymize_record(self, record: dict, fields_to_pseudonymize: list[str]) -> dict:
        """Pseudonymize specific fields in a record."""
        result = dict(record)
        for field in fields_to_pseudonymize:
            if field in result and result[field]:
                result[field] = self.pseudonymize(str(result[field]), domain=field)
        return result


# =============================================================================
# PRIVACY-SAFE LOGGING
# =============================================================================

class PrivacySafeLogger:
    """Logger that automatically redacts PII from log messages."""

    def __init__(
        self,
        name: str,
        redaction_strategy: PIIRedactor.Strategy = PIIRedactor.Strategy.TYPE_PRESERVING,
        log_level: int = logging.INFO,
    ):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(log_level)
        self._detector = PIIDetector()
        self._redactor = PIIRedactor(strategy=redaction_strategy)
        self._redaction_count = 0

    def _safe_message(self, message: str) -> str:
        """Redact PII from a log message."""
        entities = self._detector.detect(message)
        if entities:
            self._redaction_count += len(entities)
            return self._redactor.redact(message, entities)
        return message

    def _safe_kwargs(self, kwargs: dict) -> dict:
        """Redact PII from structured log data."""
        safe = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                entities = self._detector.detect(value)
                if entities:
                    self._redaction_count += len(entities)
                    safe[key] = self._redactor.redact(value, entities)
                else:
                    safe[key] = value
            else:
                safe[key] = value
        return safe

    def info(self, message: str, **kwargs):
        safe_msg = self._safe_message(message)
        safe_kwargs = self._safe_kwargs(kwargs)
        self._logger.info(safe_msg, extra={"structured": safe_kwargs})

    def warning(self, message: str, **kwargs):
        safe_msg = self._safe_message(message)
        safe_kwargs = self._safe_kwargs(kwargs)
        self._logger.warning(safe_msg, extra={"structured": safe_kwargs})

    def error(self, message: str, **kwargs):
        safe_msg = self._safe_message(message)
        safe_kwargs = self._safe_kwargs(kwargs)
        self._logger.error(safe_msg, extra={"structured": safe_kwargs})

    def debug(self, message: str, **kwargs):
        safe_msg = self._safe_message(message)
        safe_kwargs = self._safe_kwargs(kwargs)
        self._logger.debug(safe_msg, extra={"structured": safe_kwargs})

    @property
    def redaction_stats(self) -> dict:
        return {"total_redactions": self._redaction_count}


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main():
    """Demonstrate privacy engine capabilities."""
    
    # 1. Data Classification
    print("=" * 60)
    print("DATA CLASSIFICATION")
    print("=" * 60)
    classifier = DataClassificationEngine()
    
    sample_text = "Please contact John at john.doe@example.com or 555-123-4567. His SSN is 123-45-6789."
    result = classifier.classify(sample_text)
    print(f"Sensitivity: {result.sensitivity.name}")
    print(f"PII found: {len(result.pii_detected)} instances")
    for pii in result.pii_detected:
        print(f"  - {pii['type']} (hash: {pii['value_hash']})")

    # 2. PII Detection and Redaction
    print("\n" + "=" * 60)
    print("PII DETECTION AND REDACTION")
    print("=" * 60)
    detector = PIIDetector()
    redactor = PIIRedactor(strategy=PIIRedactor.Strategy.TYPE_PRESERVING)
    
    entities = detector.detect(sample_text)
    redacted = redactor.redact(sample_text, entities)
    print(f"Original: {sample_text}")
    print(f"Redacted: {redacted}")

    # 3. Consent Management
    print("\n" + "=" * 60)
    print("CONSENT MANAGEMENT")
    print("=" * 60)
    consent_mgr = ConsentManager()
    
    consent_mgr.grant_consent(
        user_id="user-123",
        purpose=DataPurpose.PERSONALIZATION,
        data_types=["conversation_history", "preferences"],
        source="settings_page",
    )
    
    has_consent = consent_mgr.check_consent("user-123", DataPurpose.PERSONALIZATION)
    print(f"Has personalization consent: {has_consent}")
    
    no_consent = consent_mgr.check_consent("user-123", DataPurpose.MODEL_TRAINING)
    print(f"Has training consent: {no_consent}")

    # 4. Purpose Tracking
    print("\n" + "=" * 60)
    print("PURPOSE TRACKING")
    print("=" * 60)
    tracker = PurposeTracker()
    
    tracker.register_data(
        data_id="conv-abc-123",
        purposes=[DataPurpose.CONVERSATION, DataPurpose.PERSONALIZATION],
        collected_by="chat_service",
        retention_days=30,
    )
    
    can_use = tracker.check_purpose("conv-abc-123", DataPurpose.CONVERSATION)
    print(f"Can use for conversation: {can_use}")
    
    cannot_use = tracker.check_purpose("conv-abc-123", DataPurpose.MODEL_TRAINING)
    print(f"Can use for training: {cannot_use}")

    # 5. Privacy Impact Assessment
    print("\n" + "=" * 60)
    print("PRIVACY IMPACT ASSESSMENT")
    print("=" * 60)
    pia = PrivacyImpactAssessment()
    
    result = pia.conduct_assessment(
        feature_name="User Memory System",
        assessed_by="privacy-team",
        answers={0: True, 2: True, 5: True, 8: True, 11: True},
        notes="Agent memory for personalization",
    )
    print(f"Feature: {result.feature_name}")
    print(f"Overall Risk: {result.overall_risk.value}")
    print(f"Decision: {result.decision}")
    print(f"Mitigations needed: {len(result.mitigations)}")

    # 6. Privacy-Safe Logging
    print("\n" + "=" * 60)
    print("PRIVACY-SAFE LOGGING")
    print("=" * 60)
    logger = PrivacySafeLogger("ai_service")
    
    logger.info(f"User query from john.doe@example.com: what is my balance?")
    logger.info(f"Processing request for SSN 123-45-6789")
    print(f"Redactions performed: {logger.redaction_stats}")


if __name__ == "__main__":
    main()
