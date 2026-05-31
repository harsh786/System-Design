"""
Dataset Versioner
=================
Implements dataset versioning with semantic versions, diffs, and changelogs.
Demonstrates: versioning strategies, diff computation, coverage comparison.
"""

import json
import os
import hashlib
from datetime import datetime
from collections import Counter
from copy import deepcopy


def create_v1_dataset() -> dict:
    """Create initial v1.0.0 golden dataset."""
    return {
        "metadata": {
            "name": "rag-golden",
            "version": "1.0.0",
            "schema_version": "1.0",
            "created_at": "2024-01-15T10:00:00Z",
            "created_by": "evaluation-team",
            "description": "Initial golden dataset for RAG evaluation"
        },
        "examples": [
            {"id": "g-001", "question": "What is the free tier rate limit?", "expected_answer": "100 requests per day", "category": "technical", "difficulty": "easy"},
            {"id": "g-002", "question": "What's the refund policy for standard?", "expected_answer": "Full refund within 14 days", "category": "policy", "difficulty": "easy"},
            {"id": "g-003", "question": "Is the platform HIPAA compliant?", "expected_answer": "HIPAA compliance is available on Enterprise tier only, requires BAA", "category": "security", "difficulty": "medium"},
            {"id": "g-004", "question": "How many projects on standard tier?", "expected_answer": "25 projects maximum", "category": "features", "difficulty": "easy"},
            {"id": "g-005", "question": "What encryption is used for data at rest?", "expected_answer": "AES-256 encryption at rest", "category": "security", "difficulty": "easy"},
            {"id": "g-006", "question": "Compare standard vs enterprise rate limits", "expected_answer": "Standard: 10K/day, 100/min. Enterprise: Unlimited, 1000/min", "category": "technical", "difficulty": "medium"},
            {"id": "g-007", "question": "What happens to data after account deletion on free tier?", "expected_answer": "Data retained for 30 days after account deletion", "category": "security", "difficulty": "medium"},
            {"id": "g-008", "question": "Can I get a refund after 90 days on enterprise?", "expected_answer": "After 60 days, prorated refund with 10% early termination fee", "category": "policy", "difficulty": "hard"},
            {"id": "g-009", "question": "What is the maximum payload size for enterprise?", "expected_answer": "100MB maximum payload size", "category": "technical", "difficulty": "easy"},
            {"id": "g-010", "question": "What's the SLA for enterprise support?", "expected_answer": "24/7 dedicated support, less than 1 hour for critical issues", "category": "features", "difficulty": "medium"},
        ]
    }


def create_v1_1_additions() -> list[dict]:
    """New examples to add for v1.1.0."""
    return [
        {"id": "g-011", "question": "What compliance certifications are available?", "expected_answer": "SOC 2 Type II, ISO 27001, HIPAA (Enterprise), GDPR (all tiers)", "category": "security", "difficulty": "medium"},
        {"id": "g-012", "question": "How often are API keys rotated?", "expected_answer": "Every 90 days by default, configurable on Enterprise", "category": "security", "difficulty": "medium"},
        {"id": "g-013", "question": "What models are available on free tier?", "expected_answer": "Standard models only", "category": "features", "difficulty": "easy"},
        {"id": "g-014", "question": "What is the batch endpoint limit for standard?", "expected_answer": "Up to 100 items per batch", "category": "technical", "difficulty": "medium"},
        {"id": "g-015", "question": "Is on-premise deployment available?", "expected_answer": "On-premise deployment is available on Enterprise tier only", "category": "features", "difficulty": "easy"},
        # Edge cases
        {"id": "g-016", "question": "What's the quantum computing roadmap?", "expected_answer": "This information is not available in the documentation.", "category": "unanswerable", "difficulty": "hard"},
        {"id": "g-017", "question": "Can I mix free and enterprise tiers?", "expected_answer": "This information is not available in the documentation.", "category": "unanswerable", "difficulty": "hard"},
        {"id": "g-018", "question": "If I upgrade mid-month, is the refund window reset?", "expected_answer": "This information is not available in the documentation.", "category": "policy", "difficulty": "hard"},
    ]


def create_v2_schema_migration(dataset: dict) -> dict:
    """Migrate to v2.0.0 schema: add reasoning_required and source_docs fields."""
    new_dataset = deepcopy(dataset)
    new_dataset["metadata"]["version"] = "2.0.0"
    new_dataset["metadata"]["schema_version"] = "2.0"
    new_dataset["metadata"]["description"] = "Schema v2: added reasoning_required and source_docs fields"
    
    for example in new_dataset["examples"]:
        # Add new fields
        example["reasoning_required"] = example["difficulty"] in ["medium", "hard"]
        example["source_docs"] = []
        if example["category"] == "technical":
            example["source_docs"].append("docs/api-limits.md")
        elif example["category"] == "policy":
            example["source_docs"].append("policies/refund-policy.md")
        elif example["category"] == "security":
            example["source_docs"].append("docs/security.md")
        elif example["category"] == "features":
            example["source_docs"].append("docs/features.md")
    
    return new_dataset


def compute_diff(v1: dict, v2: dict) -> dict:
    """Compute diff between two dataset versions."""
    v1_ids = {ex["id"] for ex in v1["examples"]}
    v2_ids = {ex["id"] for ex in v2["examples"]}
    
    added_ids = v2_ids - v1_ids
    removed_ids = v1_ids - v2_ids
    common_ids = v1_ids & v2_ids
    
    # Check for modifications
    modified = []
    for eid in common_ids:
        ex1 = next(e for e in v1["examples"] if e["id"] == eid)
        ex2 = next(e for e in v2["examples"] if e["id"] == eid)
        if ex1 != ex2:
            changes = {k: {"old": ex1.get(k), "new": ex2.get(k)} for k in set(list(ex1.keys()) + list(ex2.keys())) if ex1.get(k) != ex2.get(k)}
            modified.append({"id": eid, "changes": changes})
    
    # Schema diff
    v1_fields = set(v1["examples"][0].keys()) if v1["examples"] else set()
    v2_fields = set(v2["examples"][0].keys()) if v2["examples"] else set()
    new_fields = v2_fields - v1_fields
    removed_fields = v1_fields - v2_fields
    
    return {
        "added": sorted(added_ids),
        "removed": sorted(removed_ids),
        "modified": modified,
        "unchanged": len(common_ids) - len(modified),
        "new_schema_fields": sorted(new_fields),
        "removed_schema_fields": sorted(removed_fields),
        "v1_count": len(v1["examples"]),
        "v2_count": len(v2["examples"])
    }


def compute_coverage(dataset: dict) -> dict:
    """Compute coverage statistics for a dataset version."""
    examples = dataset["examples"]
    
    categories = Counter(ex["category"] for ex in examples)
    difficulties = Counter(ex["difficulty"] for ex in examples)
    total = len(examples)
    
    return {
        "total_examples": total,
        "categories": {cat: {"count": count, "pct": round(count/total*100, 1)} for cat, count in sorted(categories.items())},
        "difficulties": {diff: {"count": count, "pct": round(count/total*100, 1)} for diff, count in sorted(difficulties.items())},
        "has_edge_cases": any(ex.get("category") == "unanswerable" for ex in examples),
        "has_hard_examples": difficulties.get("hard", 0) >= max(1, total * 0.15)
    }


def generate_changelog(versions: list[dict], diffs: list[dict]) -> str:
    """Generate a CHANGELOG.md."""
    lines = ["# Golden Dataset Changelog\n"]
    
    for i, (version, diff_info) in enumerate(zip(versions[1:], diffs)):
        meta = version["metadata"]
        lines.append(f"## [{meta['version']}] - {meta.get('created_at', 'unknown')[:10]}")
        lines.append(f"")
        
        if diff_info.get("new_schema_fields"):
            lines.append("### Breaking Changes")
            for field in diff_info["new_schema_fields"]:
                lines.append(f"- Schema: added `{field}` field to all examples")
            lines.append("")
        
        if diff_info["added"]:
            lines.append("### Added")
            lines.append(f"- {len(diff_info['added'])} new examples ({', '.join(diff_info['added'][:5])}{'...' if len(diff_info['added']) > 5 else ''})")
            lines.append("")
        
        if diff_info["removed"]:
            lines.append("### Removed")
            lines.append(f"- {len(diff_info['removed'])} examples removed")
            lines.append("")
        
        if diff_info["modified"]:
            lines.append("### Modified")
            lines.append(f"- {len(diff_info['modified'])} examples modified")
            for mod in diff_info["modified"][:3]:
                changes = list(mod["changes"].keys())
                lines.append(f"  - {mod['id']}: changed {', '.join(changes)}")
            lines.append("")
        
        lines.append(f"### Statistics")
        lines.append(f"- Total examples: {diff_info['v1_count']} → {diff_info['v2_count']}")
        lines.append("")
    
    # First version
    meta = versions[0]["metadata"]
    lines.append(f"## [{meta['version']}] - {meta.get('created_at', 'unknown')[:10]}")
    lines.append("")
    lines.append("### Initial Release")
    lines.append(f"- {len(versions[0]['examples'])} initial examples")
    lines.append("")
    
    return "\n".join(lines)


def main():
    print("=" * 70)
    print("DATASET VERSIONER")
    print("=" * 70)
    
    os.makedirs("versions", exist_ok=True)
    versions = []
    diffs = []
    
    # === Version 1.0.0 ===
    print("\n[1] Creating v1.0.0 (initial dataset)...")
    v1 = create_v1_dataset()
    versions.append(v1)
    
    with open("versions/rag-golden-v1.0.0.json", "w") as f:
        json.dump(v1, f, indent=2)
    
    coverage_v1 = compute_coverage(v1)
    print(f"    Examples: {coverage_v1['total_examples']}")
    print(f"    Categories: {dict(coverage_v1['categories'])}")
    print(f"    Difficulties: {dict(coverage_v1['difficulties'])}")
    
    # === Version 1.1.0 (add examples) ===
    print("\n[2] Creating v1.1.0 (adding 8 new examples)...")
    v1_1 = deepcopy(v1)
    v1_1["metadata"]["version"] = "1.1.0"
    v1_1["metadata"]["created_at"] = "2024-02-15T10:00:00Z"
    v1_1["metadata"]["description"] = "Added 8 examples including edge cases and unanswerable queries"
    v1_1["examples"].extend(create_v1_1_additions())
    versions.append(v1_1)
    
    with open("versions/rag-golden-v1.1.0.json", "w") as f:
        json.dump(v1_1, f, indent=2)
    
    diff_1_to_1_1 = compute_diff(v1, v1_1)
    diffs.append(diff_1_to_1_1)
    
    coverage_v1_1 = compute_coverage(v1_1)
    print(f"    Examples: {coverage_v1_1['total_examples']}")
    print(f"    Added: {len(diff_1_to_1_1['added'])} examples")
    print(f"    Categories: {dict(coverage_v1_1['categories'])}")
    print(f"    Has edge cases: {coverage_v1_1['has_edge_cases']}")
    
    # === Version 2.0.0 (schema change) ===
    print("\n[3] Creating v2.0.0 (schema migration)...")
    v2 = create_v2_schema_migration(v1_1)
    v2["metadata"]["created_at"] = "2024-03-15T10:00:00Z"
    versions.append(v2)
    
    with open("versions/rag-golden-v2.0.0.json", "w") as f:
        json.dump(v2, f, indent=2)
    
    diff_1_1_to_2 = compute_diff(v1_1, v2)
    diffs.append(diff_1_1_to_2)
    
    print(f"    New schema fields: {diff_1_1_to_2['new_schema_fields']}")
    print(f"    Modified examples: {len(diff_1_1_to_2['modified'])} (all migrated)")
    
    # === Show Diffs ===
    print(f"\n{'=' * 70}")
    print("VERSION DIFFS")
    print("=" * 70)
    
    print(f"\n  v1.0.0 → v1.1.0:")
    print(f"    Added:     {len(diff_1_to_1_1['added'])} examples")
    print(f"    Removed:   {len(diff_1_to_1_1['removed'])} examples")
    print(f"    Modified:  {len(diff_1_to_1_1['modified'])} examples")
    print(f"    Unchanged: {diff_1_to_1_1['unchanged']} examples")
    print(f"    Size:      {diff_1_to_1_1['v1_count']} → {diff_1_to_1_1['v2_count']}")
    
    print(f"\n  v1.1.0 → v2.0.0:")
    print(f"    Schema changes: +{diff_1_1_to_2['new_schema_fields']}")
    print(f"    Modified:  {len(diff_1_1_to_2['modified'])} examples (schema migration)")
    print(f"    Size:      {diff_1_1_to_2['v1_count']} → {diff_1_1_to_2['v2_count']} (unchanged)")
    
    # === Coverage Comparison ===
    print(f"\n{'=' * 70}")
    print("COVERAGE COMPARISON")
    print("=" * 70)
    
    print(f"\n  {'Metric':<25s} {'v1.0.0':<15s} {'v1.1.0':<15s} {'v2.0.0':<15s}")
    print(f"  {'─' * 70}")
    print(f"  {'Total examples':<25s} {coverage_v1['total_examples']:<15d} {coverage_v1_1['total_examples']:<15d} {compute_coverage(v2)['total_examples']:<15d}")
    
    all_cats = sorted(set(list(coverage_v1["categories"].keys()) + list(coverage_v1_1["categories"].keys())))
    for cat in all_cats:
        v1_val = coverage_v1["categories"].get(cat, {"count": 0, "pct": 0})
        v1_1_val = coverage_v1_1["categories"].get(cat, {"count": 0, "pct": 0})
        v2_val = compute_coverage(v2)["categories"].get(cat, {"count": 0, "pct": 0})
        print(f"  {cat:<25s} {v1_val['count']:>2d} ({v1_val['pct']:>4.0f}%)     {v1_1_val['count']:>2d} ({v1_1_val['pct']:>4.0f}%)     {v2_val['count']:>2d} ({v2_val['pct']:>4.0f}%)")
    
    print(f"\n  {'Edge cases':<25s} {'No':<15s} {'Yes':<15s} {'Yes':<15s}")
    print(f"  {'Hard ≥ 15%':<25s} {'No':<15s} {'Yes':<15s} {'Yes':<15s}")
    
    # === Generate Changelog ===
    changelog = generate_changelog(versions, diffs)
    with open("versions/CHANGELOG.md", "w") as f:
        f.write(changelog)
    
    print(f"\n{'=' * 70}")
    print("CHANGELOG")
    print("=" * 70)
    print(changelog)
    
    # === Summary ===
    print(f"\n{'=' * 70}")
    print("OUTPUT FILES")
    print("=" * 70)
    print(f"  versions/rag-golden-v1.0.0.json  ({len(v1['examples'])} examples)")
    print(f"  versions/rag-golden-v1.1.0.json  ({len(v1_1['examples'])} examples)")
    print(f"  versions/rag-golden-v2.0.0.json  ({len(v2['examples'])} examples, new schema)")
    print(f"  versions/CHANGELOG.md")
    print("=" * 70)


if __name__ == "__main__":
    main()
