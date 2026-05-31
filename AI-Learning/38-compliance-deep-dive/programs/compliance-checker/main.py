"""
AI System Compliance Checker
============================
Simulates compliance assessment against EU AI Act, SOC 2, HIPAA, and financial regulations.
Takes AI system characteristics and identifies compliance gaps with prioritized remediation.

Standard library only. No API keys required.
"""

import json
import hashlib
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class Framework(Enum):
    EU_AI_ACT = "EU AI Act"
    SOC2 = "SOC 2"
    HIPAA = "HIPAA"
    FINANCIAL = "Financial Services (SR 11-7)"


class EUAIRiskTier(Enum):
    UNACCEPTABLE = "unacceptable"
    HIGH = "high_risk"
    LIMITED = "limited_risk"
    MINIMAL = "minimal_risk"


@dataclass
class AISystemProfile:
    """Characteristics of an AI system to assess."""
    name: str
    description: str
    sector: str  # healthcare, finance, general, hr, law_enforcement
    use_case: str
    processes_pii: bool = False
    processes_phi: bool = False
    processes_financial_data: bool = False
    makes_consumer_decisions: bool = False
    uses_biometric_data: bool = False
    is_autonomous: bool = False
    has_human_oversight: bool = False
    has_audit_logging: bool = False
    has_model_documentation: bool = False
    has_bias_testing: bool = False
    has_drift_monitoring: bool = False
    has_explainability: bool = False
    has_data_governance: bool = False
    has_incident_response: bool = False
    has_vendor_assessment: bool = False
    uses_third_party_model: bool = False
    has_encryption: bool = False
    has_access_controls: bool = False
    has_retention_policy: bool = False
    has_model_validation: bool = False
    has_change_management: bool = False
    training_data_documented: bool = False
    deployed_in_eu: bool = False
    deployed_in_us: bool = False


@dataclass
class ComplianceGap:
    """A single compliance gap identified."""
    framework: Framework
    requirement: str
    description: str
    risk_level: RiskLevel
    remediation: str
    effort_hours: int
    article_reference: str = ""


@dataclass
class ComplianceReport:
    """Full compliance assessment report."""
    system: AISystemProfile
    assessment_date: str
    gaps: List[ComplianceGap] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    applicable_frameworks: List[Framework] = field(default_factory=list)


class EUAIActChecker:
    """Check compliance against EU AI Act requirements."""

    def classify_risk(self, system: AISystemProfile) -> EUAIRiskTier:
        """Classify system under EU AI Act risk tiers."""
        # Unacceptable: social scoring, real-time biometric surveillance
        if system.use_case in ("social_scoring", "real_time_biometric_surveillance"):
            return EUAIRiskTier.UNACCEPTABLE

        # High risk categories
        high_risk_sectors = {"healthcare", "finance", "hr", "law_enforcement", "education"}
        high_risk_uses = {
            "credit_scoring", "hiring", "medical_diagnosis",
            "criminal_justice", "border_control", "critical_infrastructure"
        }

        if system.sector in high_risk_sectors or system.use_case in high_risk_uses:
            return EUAIRiskTier.HIGH

        # Limited risk: chatbots, emotion recognition, deepfakes
        if system.use_case in ("chatbot", "emotion_recognition", "content_generation"):
            return EUAIRiskTier.LIMITED

        return EUAIRiskTier.MINIMAL

    def check(self, system: AISystemProfile) -> List[ComplianceGap]:
        """Run EU AI Act compliance checks."""
        gaps = []
        risk_tier = self.classify_risk(system)

        if risk_tier == EUAIRiskTier.UNACCEPTABLE:
            gaps.append(ComplianceGap(
                framework=Framework.EU_AI_ACT,
                requirement="Prohibited AI Practice",
                description=f"System use case '{system.use_case}' is prohibited under EU AI Act.",
                risk_level=RiskLevel.CRITICAL,
                remediation="Cease operation of this AI system in the EU immediately.",
                effort_hours=0,
                article_reference="Article 5"
            ))
            return gaps

        if risk_tier == EUAIRiskTier.HIGH:
            # Article 9: Risk Management
            if not system.has_incident_response:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Risk Management System",
                    description="No documented risk management system for continuous risk identification.",
                    risk_level=RiskLevel.HIGH,
                    remediation="Implement risk management system covering intended use and foreseeable misuse.",
                    effort_hours=160,
                    article_reference="Article 9"
                ))

            # Article 10: Data Governance
            if not system.has_data_governance or not system.training_data_documented:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Data Governance",
                    description="Training data not documented with quality, representativeness, and bias analysis.",
                    risk_level=RiskLevel.HIGH,
                    remediation="Document all training data: origin, quality metrics, bias analysis, gaps.",
                    effort_hours=120,
                    article_reference="Article 10"
                ))

            # Article 11: Technical Documentation
            if not system.has_model_documentation:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Technical Documentation",
                    description="Missing comprehensive technical documentation of AI system.",
                    risk_level=RiskLevel.HIGH,
                    remediation="Create full technical documentation: architecture, design choices, performance.",
                    effort_hours=80,
                    article_reference="Article 11"
                ))

            # Article 12: Record-Keeping
            if not system.has_audit_logging:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Automatic Logging",
                    description="No automatic recording of events during system operation.",
                    risk_level=RiskLevel.HIGH,
                    remediation="Implement comprehensive audit logging for all AI operations.",
                    effort_hours=120,
                    article_reference="Article 12"
                ))

            # Article 14: Human Oversight
            if not system.has_human_oversight:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Human Oversight",
                    description="No human oversight mechanism to understand, monitor, and override AI decisions.",
                    risk_level=RiskLevel.CRITICAL,
                    remediation="Design human oversight: ability to interpret, intervene, and override.",
                    effort_hours=200,
                    article_reference="Article 14"
                ))

            # Article 15: Accuracy/Robustness
            if not system.has_model_validation or not system.has_drift_monitoring:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Accuracy and Robustness",
                    description="No ongoing validation of accuracy or robustness against errors.",
                    risk_level=RiskLevel.MEDIUM,
                    remediation="Implement continuous model validation and drift monitoring.",
                    effort_hours=100,
                    article_reference="Article 15"
                ))

            # Bias testing
            if not system.has_bias_testing:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Non-Discrimination",
                    description="No bias testing across protected characteristics.",
                    risk_level=RiskLevel.HIGH,
                    remediation="Implement fairness testing across demographic groups.",
                    effort_hours=80,
                    article_reference="Article 10(2)(f)"
                ))

        elif risk_tier == EUAIRiskTier.LIMITED:
            # Transparency obligations
            if not system.has_explainability:
                gaps.append(ComplianceGap(
                    framework=Framework.EU_AI_ACT,
                    requirement="Transparency",
                    description="Users not informed they are interacting with an AI system.",
                    risk_level=RiskLevel.MEDIUM,
                    remediation="Implement clear disclosure that users are interacting with AI.",
                    effort_hours=20,
                    article_reference="Article 50"
                ))

        return gaps


class HIPAAChecker:
    """Check compliance against HIPAA for AI systems processing PHI."""

    def check(self, system: AISystemProfile) -> List[ComplianceGap]:
        gaps = []
        if not system.processes_phi:
            return gaps

        if not system.has_encryption:
            gaps.append(ComplianceGap(
                framework=Framework.HIPAA,
                requirement="Encryption of PHI",
                description="PHI not encrypted at rest and in transit in AI system.",
                risk_level=RiskLevel.CRITICAL,
                remediation="Implement AES-256 encryption at rest and TLS 1.3 in transit for all PHI.",
                effort_hours=80,
                article_reference="45 CFR 164.312(a)(2)(iv)"
            ))

        if not system.has_access_controls:
            gaps.append(ComplianceGap(
                framework=Framework.HIPAA,
                requirement="Access Controls",
                description="No role-based access controls for PHI in AI system.",
                risk_level=RiskLevel.CRITICAL,
                remediation="Implement RBAC with minimum necessary access for all PHI touchpoints.",
                effort_hours=60,
                article_reference="45 CFR 164.312(a)(1)"
            ))

        if not system.has_audit_logging:
            gaps.append(ComplianceGap(
                framework=Framework.HIPAA,
                requirement="Audit Controls",
                description="No audit trail for PHI access within AI system.",
                risk_level=RiskLevel.HIGH,
                remediation="Log all PHI access: who, what, when, why for every AI interaction.",
                effort_hours=100,
                article_reference="45 CFR 164.312(b)"
            ))

        if not system.has_retention_policy:
            gaps.append(ComplianceGap(
                framework=Framework.HIPAA,
                requirement="Data Retention",
                description="No retention/disposal policy for PHI in AI logs and training data.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Define retention periods, implement auto-deletion for PHI in AI artifacts.",
                effort_hours=40,
                article_reference="45 CFR 164.530(j)"
            ))

        if system.uses_third_party_model and not system.has_vendor_assessment:
            gaps.append(ComplianceGap(
                framework=Framework.HIPAA,
                requirement="Business Associate Agreement",
                description="Third-party AI model used with PHI but no BAA in place.",
                risk_level=RiskLevel.CRITICAL,
                remediation="Execute BAA with model provider or move to on-premises inference.",
                effort_hours=20,
                article_reference="45 CFR 164.502(e)"
            ))

        if not system.training_data_documented:
            gaps.append(ComplianceGap(
                framework=Framework.HIPAA,
                requirement="De-identification",
                description="Training data may contain PHI without proper de-identification.",
                risk_level=RiskLevel.HIGH,
                remediation="Apply Safe Harbor or Expert Determination de-identification to all training data.",
                effort_hours=120,
                article_reference="45 CFR 164.514"
            ))

        return gaps


class FinancialChecker:
    """Check compliance against financial services regulations (SR 11-7, ECOA)."""

    def check(self, system: AISystemProfile) -> List[ComplianceGap]:
        gaps = []
        if system.sector != "finance" and not system.processes_financial_data:
            return gaps

        # SR 11-7: Model Risk Management
        if not system.has_model_validation:
            gaps.append(ComplianceGap(
                framework=Framework.FINANCIAL,
                requirement="Independent Model Validation",
                description="No independent validation of AI model (SR 11-7 Pillar 2).",
                risk_level=RiskLevel.CRITICAL,
                remediation="Commission independent model validation by team not involved in development.",
                effort_hours=200,
                article_reference="SR 11-7 Section V"
            ))

        if not system.has_model_documentation:
            gaps.append(ComplianceGap(
                framework=Framework.FINANCIAL,
                requirement="Model Documentation",
                description="No model development document per SR 11-7 requirements.",
                risk_level=RiskLevel.HIGH,
                remediation="Create full model development doc: methodology, data, assumptions, limitations.",
                effort_hours=80,
                article_reference="SR 11-7 Section IV"
            ))

        if not system.has_drift_monitoring:
            gaps.append(ComplianceGap(
                framework=Framework.FINANCIAL,
                requirement="Ongoing Monitoring",
                description="No ongoing model performance monitoring.",
                risk_level=RiskLevel.HIGH,
                remediation="Implement continuous monitoring with drift detection and escalation.",
                effort_hours=100,
                article_reference="SR 11-7 Section V.C"
            ))

        # Fair Lending (ECOA)
        if system.makes_consumer_decisions:
            if not system.has_bias_testing:
                gaps.append(ComplianceGap(
                    framework=Framework.FINANCIAL,
                    requirement="Fair Lending Testing",
                    description="No disparate impact analysis for consumer credit decisions.",
                    risk_level=RiskLevel.CRITICAL,
                    remediation="Conduct four-fifths rule analysis across all protected classes.",
                    effort_hours=120,
                    article_reference="ECOA / Reg B"
                ))

            if not system.has_explainability:
                gaps.append(ComplianceGap(
                    framework=Framework.FINANCIAL,
                    requirement="Adverse Action Notices",
                    description="Cannot generate specific reasons for adverse credit decisions.",
                    risk_level=RiskLevel.CRITICAL,
                    remediation="Implement SHAP/LIME explainability mapped to consumer reason codes.",
                    effort_hours=160,
                    article_reference="ECOA 15 USC 1691(d)"
                ))

        if not system.has_change_management:
            gaps.append(ComplianceGap(
                framework=Framework.FINANCIAL,
                requirement="Model Change Management",
                description="No formal change management process for model updates.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Implement model change log with approval workflow and re-validation triggers.",
                effort_hours=60,
                article_reference="SR 11-7 Section VI"
            ))

        if system.uses_third_party_model and not system.has_vendor_assessment:
            gaps.append(ComplianceGap(
                framework=Framework.FINANCIAL,
                requirement="Third-Party Model Risk",
                description="Using third-party model without proper vendor risk assessment.",
                risk_level=RiskLevel.HIGH,
                remediation="Conduct third-party model risk assessment per OCC 2013-29 guidance.",
                effort_hours=80,
                article_reference="OCC 2013-29"
            ))

        return gaps


class SOC2Checker:
    """Check compliance against SOC 2 Trust Service Criteria for AI."""

    def check(self, system: AISystemProfile) -> List[ComplianceGap]:
        gaps = []

        # Security
        if not system.has_access_controls:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Logical Access Controls",
                description="No tiered access control for AI model and data assets.",
                risk_level=RiskLevel.HIGH,
                remediation="Implement tiered access model: inference, monitoring, deployment, development, admin.",
                effort_hours=80,
                article_reference="CC6.1"
            ))

        if not system.has_encryption:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Data Protection",
                description="Model weights, training data, or API communications not encrypted.",
                risk_level=RiskLevel.HIGH,
                remediation="Encrypt all AI assets at rest (AES-256) and in transit (TLS 1.3).",
                effort_hours=60,
                article_reference="CC6.1"
            ))

        # Processing Integrity
        if not system.has_model_validation:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Processing Integrity - Validation",
                description="No pre-deployment validation that AI outputs are accurate.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Implement model validation gates before production deployment.",
                effort_hours=80,
                article_reference="PI1.1"
            ))

        if not system.has_drift_monitoring:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Processing Integrity - Monitoring",
                description="No ongoing monitoring of AI output quality and accuracy.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Deploy drift detection and output quality monitoring.",
                effort_hours=60,
                article_reference="PI1.3"
            ))

        # Audit Logging
        if not system.has_audit_logging:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Monitoring Activities",
                description="No comprehensive audit logging of AI interactions.",
                risk_level=RiskLevel.HIGH,
                remediation="Log all inferences: timestamp, caller, model version, input/output hash, status.",
                effort_hours=80,
                article_reference="CC7.2"
            ))

        # Change Management
        if not system.has_change_management:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Change Management",
                description="No formal change management for model deployments.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Implement model deployment approval workflow with rollback capability.",
                effort_hours=60,
                article_reference="CC8.1"
            ))

        # Vendor Management
        if system.uses_third_party_model and not system.has_vendor_assessment:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Vendor Management",
                description="Third-party AI model provider not assessed per vendor management policy.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Conduct vendor risk assessment: SOC 2 report, data handling, SLA review.",
                effort_hours=40,
                article_reference="CC9.2"
            ))

        # Confidentiality
        if system.processes_pii and not system.has_retention_policy:
            gaps.append(ComplianceGap(
                framework=Framework.SOC2,
                requirement="Data Retention",
                description="No retention policy for AI inference logs containing confidential data.",
                risk_level=RiskLevel.MEDIUM,
                remediation="Define and implement retention schedules for all AI data tiers.",
                effort_hours=40,
                article_reference="C1.2"
            ))

        return gaps


class ComplianceAssessor:
    """Main compliance assessment engine."""

    def __init__(self):
        self.checkers = {
            Framework.EU_AI_ACT: EUAIActChecker(),
            Framework.HIPAA: HIPAAChecker(),
            Framework.FINANCIAL: FinancialChecker(),
            Framework.SOC2: SOC2Checker(),
        }

    def determine_applicable_frameworks(self, system: AISystemProfile) -> List[Framework]:
        """Determine which frameworks apply to this system."""
        frameworks = [Framework.SOC2]  # SOC 2 applies to nearly all enterprise AI

        if system.deployed_in_eu:
            frameworks.append(Framework.EU_AI_ACT)
        if system.processes_phi:
            frameworks.append(Framework.HIPAA)
        if system.sector == "finance" or system.processes_financial_data:
            frameworks.append(Framework.FINANCIAL)

        return frameworks

    def assess(self, system: AISystemProfile) -> ComplianceReport:
        """Run full compliance assessment."""
        report = ComplianceReport(
            system=system,
            assessment_date=datetime.datetime.now().isoformat(),
        )

        report.applicable_frameworks = self.determine_applicable_frameworks(system)

        for framework in report.applicable_frameworks:
            checker = self.checkers[framework]
            gaps = checker.check(system)
            report.gaps.extend(gaps)

        # Calculate scores per framework
        for framework in report.applicable_frameworks:
            framework_gaps = [g for g in report.gaps if g.framework == framework]
            critical = sum(1 for g in framework_gaps if g.risk_level == RiskLevel.CRITICAL)
            high = sum(1 for g in framework_gaps if g.risk_level == RiskLevel.HIGH)
            medium = sum(1 for g in framework_gaps if g.risk_level == RiskLevel.MEDIUM)

            # Score: 100 = fully compliant, deduct for gaps
            score = max(0, 100 - (critical * 25) - (high * 15) - (medium * 5))
            report.scores[framework.value] = score

        return report

    def prioritize_remediation(self, report: ComplianceReport) -> List[ComplianceGap]:
        """Return gaps sorted by priority."""
        priority_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.MINIMAL: 4,
        }
        return sorted(report.gaps, key=lambda g: (priority_order[g.risk_level], g.effort_hours))

    def generate_text_report(self, report: ComplianceReport) -> str:
        """Generate human-readable compliance report."""
        lines = []
        lines.append("=" * 70)
        lines.append("AI SYSTEM COMPLIANCE ASSESSMENT REPORT")
        lines.append("=" * 70)
        lines.append(f"System: {report.system.name}")
        lines.append(f"Description: {report.system.description}")
        lines.append(f"Sector: {report.system.sector}")
        lines.append(f"Assessment Date: {report.assessment_date}")
        lines.append("")

        # Applicable frameworks
        lines.append("APPLICABLE FRAMEWORKS:")
        for fw in report.applicable_frameworks:
            score = report.scores.get(fw.value, 0)
            status = "PASS" if score >= 70 else "NEEDS WORK" if score >= 40 else "FAIL"
            lines.append(f"  [{status}] {fw.value}: {score:.0f}/100")
        lines.append("")

        # Overall score
        if report.scores:
            avg_score = sum(report.scores.values()) / len(report.scores)
            lines.append(f"OVERALL COMPLIANCE SCORE: {avg_score:.0f}/100")
        lines.append("")

        # Gaps by priority
        prioritized = self.prioritize_remediation(report)
        lines.append(f"COMPLIANCE GAPS IDENTIFIED: {len(prioritized)}")
        lines.append("-" * 70)

        for i, gap in enumerate(prioritized, 1):
            lines.append(f"\n#{i} [{gap.risk_level.value.upper()}] {gap.requirement}")
            lines.append(f"   Framework: {gap.framework.value}")
            if gap.article_reference:
                lines.append(f"   Reference: {gap.article_reference}")
            lines.append(f"   Issue: {gap.description}")
            lines.append(f"   Remediation: {gap.remediation}")
            lines.append(f"   Estimated Effort: {gap.effort_hours} hours")

        # Summary
        lines.append("\n" + "=" * 70)
        lines.append("REMEDIATION SUMMARY")
        lines.append("=" * 70)
        total_hours = sum(g.effort_hours for g in prioritized)
        critical_count = sum(1 for g in prioritized if g.risk_level == RiskLevel.CRITICAL)
        high_count = sum(1 for g in prioritized if g.risk_level == RiskLevel.HIGH)
        lines.append(f"Total gaps: {len(prioritized)}")
        lines.append(f"Critical: {critical_count}")
        lines.append(f"High: {high_count}")
        lines.append(f"Total remediation effort: ~{total_hours} hours")
        lines.append(f"Estimated timeline: {total_hours // 160 + 1} months (1 FTE)")

        return "\n".join(lines)


def demo():
    """Demonstrate compliance checker with sample AI systems."""

    # Example 1: Healthcare AI with gaps
    healthcare_system = AISystemProfile(
        name="RadiologyAssist AI",
        description="AI-powered chest X-ray analysis for pneumonia detection",
        sector="healthcare",
        use_case="medical_diagnosis",
        processes_pii=True,
        processes_phi=True,
        makes_consumer_decisions=False,
        has_human_oversight=True,
        has_audit_logging=False,
        has_model_documentation=True,
        has_bias_testing=False,
        has_drift_monitoring=False,
        has_explainability=True,
        has_data_governance=True,
        has_encryption=True,
        has_access_controls=True,
        has_retention_policy=False,
        has_model_validation=True,
        has_change_management=True,
        training_data_documented=True,
        uses_third_party_model=False,
        has_vendor_assessment=False,
        has_incident_response=True,
        deployed_in_eu=True,
        deployed_in_us=True,
    )

    # Example 2: Financial AI with many gaps
    finance_system = AISystemProfile(
        name="CreditScore ML",
        description="Machine learning credit scoring model for consumer loans",
        sector="finance",
        use_case="credit_scoring",
        processes_pii=True,
        processes_financial_data=True,
        makes_consumer_decisions=True,
        has_human_oversight=False,
        has_audit_logging=False,
        has_model_documentation=False,
        has_bias_testing=False,
        has_drift_monitoring=False,
        has_explainability=False,
        has_data_governance=False,
        has_encryption=True,
        has_access_controls=True,
        has_retention_policy=False,
        has_model_validation=False,
        has_change_management=False,
        training_data_documented=False,
        uses_third_party_model=True,
        has_vendor_assessment=False,
        has_incident_response=False,
        deployed_in_eu=True,
        deployed_in_us=True,
    )

    assessor = ComplianceAssessor()

    print("\n" + "=" * 70)
    print("COMPLIANCE CHECKER DEMO")
    print("=" * 70)

    for system in [healthcare_system, finance_system]:
        report = assessor.assess(system)
        print(assessor.generate_text_report(report))
        print("\n\n")


if __name__ == "__main__":
    demo()
