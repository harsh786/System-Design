"""
AI Compliance Checker
Automated policy checking for AI system configurations.
Defines 10 compliance policies and validates systems against them.
"""

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class PolicyResult:
    policy_id: str
    policy_name: str
    compliant: bool
    message: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    recommendation: str = ""


# ─────────────────────────────────────────────────────
# 10 COMPLIANCE POLICIES
# ─────────────────────────────────────────────────────

def policy_pii_protection(config: dict) -> PolicyResult:
    """POL-001: Customer-facing AI must have PII filtering enabled."""
    if config.get("deployment_type") != "customer_facing":
        return PolicyResult("POL-001", "PII Protection", True,
                          "Not customer-facing, policy not applicable", "HIGH")
    guardrails = config.get("guardrails", {})
    pii = guardrails.get("pii_filter", {})
    if not pii.get("enabled"):
        return PolicyResult("POL-001", "PII Protection", False,
                          "PII filter not enabled for customer-facing system",
                          "CRITICAL",
                          "Enable PII detection with action='redact' in guardrails config")
    return PolicyResult("POL-001", "PII Protection", True,
                       "PII filter enabled and configured", "CRITICAL")


def policy_cost_controls(config: dict) -> PolicyResult:
    """POL-002: Max cost per request must not exceed $0.10."""
    max_cost = config.get("max_cost_per_request")
    if max_cost is None:
        return PolicyResult("POL-002", "Cost Controls", False,
                          "No max_cost_per_request defined",
                          "HIGH",
                          "Set max_cost_per_request <= 0.10 in config")
    if max_cost > 0.10:
        return PolicyResult("POL-002", "Cost Controls", False,
                          f"Max cost ${max_cost} exceeds $0.10 limit",
                          "HIGH",
                          "Reduce max cost or get finance approval for higher limit")
    return PolicyResult("POL-002", "Cost Controls", True,
                       f"Cost limit ${max_cost} within bounds", "HIGH")


def policy_evaluation_exists(config: dict) -> PolicyResult:
    """POL-003: Production systems must have evaluation pipeline."""
    if config.get("environment") != "production":
        return PolicyResult("POL-003", "Evaluation Pipeline", True,
                          "Non-production, policy not applicable", "HIGH")
    eval_config = config.get("evaluation", {})
    if not eval_config:
        return PolicyResult("POL-003", "Evaluation Pipeline", False,
                          "No evaluation configuration for production system",
                          "HIGH",
                          "Add evaluation config with golden dataset (min 50 examples)")
    dataset_size = eval_config.get("golden_dataset_size", 0)
    if dataset_size < 50:
        return PolicyResult("POL-003", "Evaluation Pipeline", False,
                          f"Golden dataset too small ({dataset_size} < 50 required)",
                          "HIGH",
                          "Expand golden dataset to at least 50 examples")
    return PolicyResult("POL-003", "Evaluation Pipeline", True,
                       f"Evaluation configured with {dataset_size} examples", "HIGH")


def policy_model_approved(config: dict) -> PolicyResult:
    """POL-004: Only approved models may be used in production."""
    approved_models = [
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
        "claude-sonnet-4-20250514", "claude-haiku-3-5",
        "gemini-1.5-pro", "gemini-1.5-flash",
    ]
    model = config.get("model", "")
    if not model:
        return PolicyResult("POL-004", "Approved Model", False,
                          "No model specified in configuration",
                          "CRITICAL",
                          "Specify model from approved list")
    if model not in approved_models:
        return PolicyResult("POL-004", "Approved Model", False,
                          f"Model '{model}' not in approved model list",
                          "CRITICAL",
                          f"Use an approved model: {', '.join(approved_models[:4])}...")
    return PolicyResult("POL-004", "Approved Model", True,
                       f"Model '{model}' is approved", "CRITICAL")


def policy_data_residency(config: dict) -> PolicyResult:
    """POL-005: EU user data must be processed in EU region."""
    if not config.get("serves_eu_users"):
        return PolicyResult("POL-005", "Data Residency", True,
                          "Does not serve EU users, policy not applicable", "CRITICAL")
    endpoint_region = config.get("endpoint_region", "")
    if not endpoint_region.startswith("eu"):
        return PolicyResult("POL-005", "Data Residency", False,
                          f"EU users served from non-EU region: {endpoint_region}",
                          "CRITICAL",
                          "Route EU traffic to EU endpoint (eu-west-1, eu-central-1)")
    return PolicyResult("POL-005", "Data Residency", True,
                       f"EU data processed in {endpoint_region}", "CRITICAL")


def policy_content_safety(config: dict) -> PolicyResult:
    """POL-006: All outputs must pass content safety check."""
    guardrails = config.get("guardrails", {})
    if not guardrails.get("content_safety", {}).get("enabled"):
        return PolicyResult("POL-006", "Content Safety", False,
                          "Content safety filter not enabled",
                          "HIGH",
                          "Enable content safety guardrail for output filtering")
    return PolicyResult("POL-006", "Content Safety", True,
                       "Content safety filter enabled", "HIGH")


def policy_logging_enabled(config: dict) -> PolicyResult:
    """POL-007: All AI interactions must be logged for audit."""
    logging = config.get("logging", {})
    if not logging.get("enabled"):
        return PolicyResult("POL-007", "Audit Logging", False,
                          "Interaction logging not enabled",
                          "HIGH",
                          "Enable logging with appropriate retention (min 90 days)")
    retention = logging.get("retention_days", 0)
    if retention < 90:
        return PolicyResult("POL-007", "Audit Logging", False,
                          f"Log retention {retention} days < 90 day minimum",
                          "MEDIUM",
                          "Increase log retention to at least 90 days")
    return PolicyResult("POL-007", "Audit Logging", True,
                       f"Logging enabled with {retention}-day retention", "HIGH")


def policy_rate_limiting(config: dict) -> PolicyResult:
    """POL-008: Rate limiting must be configured."""
    rate_limit = config.get("rate_limit", {})
    if not rate_limit.get("enabled"):
        return PolicyResult("POL-008", "Rate Limiting", False,
                          "No rate limiting configured",
                          "MEDIUM",
                          "Enable rate limiting (recommended: 60 req/min per user)")
    return PolicyResult("POL-008", "Rate Limiting", True,
                       f"Rate limit: {rate_limit.get('requests_per_minute', '?')} req/min",
                       "MEDIUM")


def policy_fallback_configured(config: dict) -> PolicyResult:
    """POL-009: Production systems must have fallback mechanism."""
    if config.get("environment") != "production":
        return PolicyResult("POL-009", "Fallback Mechanism", True,
                          "Non-production, policy not applicable", "MEDIUM")
    if not config.get("fallback", {}).get("enabled"):
        return PolicyResult("POL-009", "Fallback Mechanism", False,
                          "No fallback configured for production system",
                          "MEDIUM",
                          "Configure fallback (cached response, simpler model, or graceful error)")
    return PolicyResult("POL-009", "Fallback Mechanism", True,
                       f"Fallback: {config['fallback'].get('type', 'configured')}", "MEDIUM")


def policy_arb_approval(config: dict) -> PolicyResult:
    """POL-010: High-risk systems require ARB approval."""
    risk_level = config.get("risk_level", "LOW")
    if risk_level not in ("HIGH", "CRITICAL"):
        return PolicyResult("POL-010", "ARB Approval", True,
                          f"Risk level '{risk_level}' does not require ARB approval", "HIGH")
    approval = config.get("arb_approval", {})
    if not approval.get("approved"):
        return PolicyResult("POL-010", "ARB Approval", False,
                          "High-risk system without ARB approval",
                          "CRITICAL",
                          "Submit architecture review request to ARB before deployment")
    # Check approval freshness (< 180 days)
    approval_date = approval.get("date", "2020-01-01")
    try:
        days_old = (date.today() - date.fromisoformat(approval_date)).days
        if days_old > 180:
            return PolicyResult("POL-010", "ARB Approval", False,
                              f"ARB approval expired ({days_old} days old, max 180)",
                              "HIGH",
                              "Re-submit for ARB review (approval > 6 months old)")
    except ValueError:
        pass
    return PolicyResult("POL-010", "ARB Approval", True,
                       "ARB approval current and valid", "CRITICAL")


ALL_POLICIES = [
    policy_pii_protection,
    policy_cost_controls,
    policy_evaluation_exists,
    policy_model_approved,
    policy_data_residency,
    policy_content_safety,
    policy_logging_enabled,
    policy_rate_limiting,
    policy_fallback_configured,
    policy_arb_approval,
]


# ─────────────────────────────────────────────────────
# EXAMPLE CONFIGURATIONS
# ─────────────────────────────────────────────────────

EXAMPLE_CONFIGS = {
    "compliant_system": {
        "name": "CustomerBot v3 (Well-configured)",
        "deployment_type": "customer_facing",
        "environment": "production",
        "model": "gpt-4o-mini",
        "risk_level": "MEDIUM",
        "serves_eu_users": False,
        "endpoint_region": "us-east-1",
        "max_cost_per_request": 0.05,
        "guardrails": {
            "pii_filter": {"enabled": True, "action": "redact"},
            "content_safety": {"enabled": True},
        },
        "evaluation": {"golden_dataset_size": 100, "frequency": "daily"},
        "logging": {"enabled": True, "retention_days": 180},
        "rate_limit": {"enabled": True, "requests_per_minute": 60},
        "fallback": {"enabled": True, "type": "cached_response"},
        "arb_approval": {"approved": True, "date": "2024-06-01"},
    },
    "non_compliant_system": {
        "name": "QuickBot (Rushed to production)",
        "deployment_type": "customer_facing",
        "environment": "production",
        "model": "llama-3-70b-custom",
        "risk_level": "HIGH",
        "serves_eu_users": True,
        "endpoint_region": "us-west-2",
        "max_cost_per_request": 0.25,
        "guardrails": {
            "pii_filter": {"enabled": False},
            "content_safety": {"enabled": False},
        },
        "evaluation": {"golden_dataset_size": 10},
        "logging": {"enabled": True, "retention_days": 30},
        "rate_limit": {"enabled": False},
        "fallback": {"enabled": False},
        "arb_approval": {"approved": False},
    },
    "internal_tool": {
        "name": "InternalSearch (Low risk)",
        "deployment_type": "internal",
        "environment": "production",
        "model": "gpt-4o-mini",
        "risk_level": "LOW",
        "serves_eu_users": False,
        "endpoint_region": "us-east-1",
        "max_cost_per_request": 0.03,
        "guardrails": {
            "pii_filter": {"enabled": False},
            "content_safety": {"enabled": True},
        },
        "evaluation": {"golden_dataset_size": 75, "frequency": "weekly"},
        "logging": {"enabled": True, "retention_days": 90},
        "rate_limit": {"enabled": True, "requests_per_minute": 120},
        "fallback": {"enabled": True, "type": "error_message"},
        "arb_approval": {},
    },
}


def run_compliance_check(config: dict) -> list[PolicyResult]:
    """Run all policies against a configuration."""
    results = []
    for policy_fn in ALL_POLICIES:
        result = policy_fn(config)
        results.append(result)
    return results


def print_report(config: dict, results: list[PolicyResult]):
    """Print formatted compliance report."""
    name = config.get("name", "Unknown System")
    passed = sum(1 for r in results if r.compliant)
    failed = sum(1 for r in results if not r.compliant)
    total = len(results)

    print("\n" + "=" * 65)
    print(f"  COMPLIANCE REPORT: {name}")
    print(f"  Date: {date.today()}")
    print("=" * 65)

    # Summary
    status = "✓ COMPLIANT" if failed == 0 else "✗ NON-COMPLIANT"
    print(f"\n  Status: {status}")
    print(f"  Passed: {passed}/{total} | Failed: {failed}/{total}")

    # Progress bar
    pct = int(passed / total * 100)
    filled = int(passed / total * 30)
    bar = "█" * filled + "░" * (30 - filled)
    print(f"  [{bar}] {pct}%")

    # Details
    if failed > 0:
        print(f"\n  {'─' * 60}")
        print("  FAILURES:")
        print(f"  {'─' * 60}")
        for r in results:
            if not r.compliant:
                sev_marker = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(r.severity, "⚪")
                print(f"\n  {sev_marker} [{r.severity}] {r.policy_id}: {r.policy_name}")
                print(f"     Issue: {r.message}")
                if r.recommendation:
                    print(f"     Fix: {r.recommendation}")

    print(f"\n  {'─' * 60}")
    print("  ALL CHECKS:")
    print(f"  {'─' * 60}")
    for r in results:
        icon = "✓" if r.compliant else "✗"
        print(f"  {icon} {r.policy_id} {r.policy_name:<25} [{r.severity}]")

    # Recommendations summary
    recommendations = [r for r in results if not r.compliant and r.recommendation]
    if recommendations:
        print(f"\n  {'─' * 60}")
        print("  ACTION ITEMS (prioritized by severity):")
        print(f"  {'─' * 60}")
        sorted_recs = sorted(recommendations,
                           key=lambda r: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[r.severity])
        for i, r in enumerate(sorted_recs, 1):
            print(f"  {i}. [{r.severity}] {r.recommendation}")

    print("\n" + "=" * 65)


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║        AI COMPLIANCE CHECKER                     ║")
    print("║  Automated policy checking for AI systems        ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  10 policies checked against system config       ║")
    print("╚══════════════════════════════════════════════════╝")

    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx + 1 < len(sys.argv):
            with open(sys.argv[idx + 1]) as f:
                config = json.load(f)
            results = run_compliance_check(config)
            print_report(config, results)
            return

    # Demo mode: check all example configs
    print("\n  Running compliance checks on 3 example systems...\n")

    for key, config in EXAMPLE_CONFIGS.items():
        results = run_compliance_check(config)
        print_report(config, results)

    # Summary across all systems
    print("\n" + "═" * 65)
    print("  ORGANIZATION COMPLIANCE SUMMARY")
    print("═" * 65)
    total_checks = 0
    total_passed = 0
    for key, config in EXAMPLE_CONFIGS.items():
        results = run_compliance_check(config)
        passed = sum(1 for r in results if r.compliant)
        total = len(results)
        total_checks += total
        total_passed += passed
        status = "✓" if passed == total else "✗"
        print(f"  {status} {config['name']:<40} {passed}/{total} policies")

    print(f"\n  Overall: {total_passed}/{total_checks} checks passing ({int(total_passed/total_checks*100)}%)")
    print("═" * 65)


if __name__ == "__main__":
    main()
