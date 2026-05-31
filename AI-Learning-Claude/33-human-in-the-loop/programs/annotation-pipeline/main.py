"""
Annotation Pipeline Simulator
==============================
Simulates a complete annotation pipeline with task creation, assignment,
quality control (gold items, agreement checks), LLM-assisted pre-labeling,
and consensus aggregation.

Run: python3 main.py
"""

import random
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import statistics


@dataclass
class AnnotationItem:
    id: int
    text: str
    true_label: str
    is_gold: bool = False
    pre_label: str = ""  # LLM pre-label
    annotations: list = field(default_factory=list)
    final_label: str = ""
    consensus: bool = False


@dataclass
class Annotation:
    annotator_id: str
    label: str
    time_seconds: float
    is_gold_correct: Optional[bool] = None


@dataclass
class Annotator:
    id: str
    accuracy: float
    speed_items_per_hour: float
    items_completed: int = 0
    gold_correct: int = 0
    gold_total: int = 0
    total_time: float = 0.0


@dataclass
class QualityReport:
    total_items: int = 0
    gold_items: int = 0
    avg_annotator_accuracy: float = 0.0
    inter_annotator_agreement: float = 0.0
    consensus_rate: float = 0.0
    items_needing_adjudication: int = 0
    llm_pre_label_accuracy: float = 0.0
    estimated_final_accuracy: float = 0.0


class AnnotationPipeline:
    """Complete annotation pipeline with quality control."""

    def __init__(self, num_annotators=5, annotations_per_item=3, gold_rate=0.08):
        self.annotations_per_item = annotations_per_item
        self.gold_rate = gold_rate
        self.annotators = self._create_annotators(num_annotators)
        self.items = []
        self.quality_report = QualityReport()

    def _create_annotators(self, n):
        """Create annotators with varying skill levels."""
        annotators = []
        for i in range(n):
            # Simulate different skill levels
            accuracy = random.uniform(0.75, 0.96)
            speed = random.uniform(30, 80)  # items per hour
            annotators.append(Annotator(
                id=f"annotator_{i+1}",
                accuracy=accuracy,
                speed_items_per_hour=speed,
            ))
        return annotators

    def create_tasks(self, n_items=200):
        """Create annotation tasks from simulated production data."""
        categories = ["positive", "negative", "neutral", "mixed"]
        items = []

        for i in range(n_items):
            true_label = random.choice(categories)
            is_gold = random.random() < self.gold_rate

            # Generate synthetic text
            text_templates = {
                "positive": "Great product, really enjoyed using it. #{0}",
                "negative": "Terrible experience, would not recommend. #{0}",
                "neutral": "The product arrived on time and works as described. #{0}",
                "mixed": "Good quality but the shipping was slow. #{0}",
            }
            text = text_templates[true_label].format(i)

            items.append(AnnotationItem(
                id=i,
                text=text,
                true_label=true_label,
                is_gold=is_gold,
            ))

        self.items = items
        return items

    def llm_pre_label(self):
        """Simulate LLM pre-labeling (AI labels first, human verifies)."""
        llm_accuracy = 0.82  # Simulated LLM accuracy
        categories = ["positive", "negative", "neutral", "mixed"]

        correct_count = 0
        for item in self.items:
            if random.random() < llm_accuracy:
                item.pre_label = item.true_label
                correct_count += 1
            else:
                # LLM makes mistake
                wrong_labels = [l for l in categories if l != item.true_label]
                item.pre_label = random.choice(wrong_labels)

        self.quality_report.llm_pre_label_accuracy = correct_count / len(self.items)
        return correct_count, len(self.items)

    def assign_and_annotate(self):
        """Assign items to annotators and simulate annotation."""
        for item in self.items:
            # Assign to N annotators
            selected_annotators = random.sample(
                self.annotators,
                min(self.annotations_per_item, len(self.annotators))
            )

            for annotator in selected_annotators:
                # Simulate annotation decision
                # With pre-label, annotator is faster and slightly more accurate
                has_pre_label = item.pre_label != ""

                if has_pre_label:
                    # Annotator verifies pre-label (faster)
                    time_seconds = 3600 / annotator.speed_items_per_hour * 0.4
                    # Slight accuracy boost from anchoring (can be positive or negative)
                    effective_accuracy = min(0.98, annotator.accuracy + 0.05)
                else:
                    time_seconds = 3600 / annotator.speed_items_per_hour
                    effective_accuracy = annotator.accuracy

                # Determine annotator's label
                if random.random() < effective_accuracy:
                    label = item.true_label
                else:
                    categories = ["positive", "negative", "neutral", "mixed"]
                    wrong_labels = [l for l in categories if l != item.true_label]
                    label = random.choice(wrong_labels)

                # Gold item check
                is_gold_correct = None
                if item.is_gold:
                    is_gold_correct = (label == item.true_label)
                    annotator.gold_total += 1
                    if is_gold_correct:
                        annotator.gold_correct += 1

                annotation = Annotation(
                    annotator_id=annotator.id,
                    label=label,
                    time_seconds=time_seconds,
                    is_gold_correct=is_gold_correct,
                )
                item.annotations.append(annotation)

                annotator.items_completed += 1
                annotator.total_time += time_seconds

    def aggregate_labels(self):
        """Aggregate annotations using majority vote with quality weighting."""
        consensus_count = 0
        adjudication_needed = 0

        for item in self.items:
            if not item.annotations:
                continue

            # Count votes
            vote_counts = defaultdict(int)
            for ann in item.annotations:
                vote_counts[ann.label] += 1

            # Find majority
            max_votes = max(vote_counts.values())
            total_votes = len(item.annotations)
            majority_labels = [l for l, c in vote_counts.items() if c == max_votes]

            if len(majority_labels) == 1 and max_votes > total_votes / 2:
                # Clear consensus
                item.final_label = majority_labels[0]
                item.consensus = True
                consensus_count += 1
            else:
                # No clear consensus - would go to adjudication
                # For simulation, pick the most common (tie-break random)
                item.final_label = random.choice(majority_labels)
                item.consensus = False
                adjudication_needed += 1

        self.quality_report.consensus_rate = consensus_count / len(self.items)
        self.quality_report.items_needing_adjudication = adjudication_needed

    def compute_inter_annotator_agreement(self):
        """Compute pairwise agreement between annotators."""
        pair_agreements = []

        for item in self.items:
            annotations = item.annotations
            if len(annotations) < 2:
                continue
            # Pairwise agreement
            for i in range(len(annotations)):
                for j in range(i + 1, len(annotations)):
                    pair_agreements.append(
                        1 if annotations[i].label == annotations[j].label else 0
                    )

        if pair_agreements:
            raw_agreement = statistics.mean(pair_agreements)
            # Simplified Cohen's Kappa approximation
            # Kappa = (observed - expected) / (1 - expected)
            # For 4 categories, chance agreement ≈ 0.25
            chance_agreement = 0.25
            kappa = (raw_agreement - chance_agreement) / (1 - chance_agreement)
            self.quality_report.inter_annotator_agreement = kappa
            return raw_agreement, kappa
        return 0.0, 0.0

    def check_annotator_quality(self):
        """Flag annotators with poor gold item performance."""
        flagged = []
        for annotator in self.annotators:
            if annotator.gold_total >= 3:
                gold_accuracy = annotator.gold_correct / annotator.gold_total
                if gold_accuracy < 0.70:
                    flagged.append((annotator.id, gold_accuracy))
        return flagged

    def compute_final_accuracy(self):
        """Compute accuracy of final aggregated labels."""
        correct = sum(1 for item in self.items if item.final_label == item.true_label)
        accuracy = correct / len(self.items)
        self.quality_report.estimated_final_accuracy = accuracy
        return accuracy

    def generate_quality_report(self):
        """Generate comprehensive quality report."""
        self.quality_report.total_items = len(self.items)
        self.quality_report.gold_items = sum(1 for item in self.items if item.is_gold)

        accuracies = []
        for a in self.annotators:
            if a.items_completed > 0 and a.gold_total > 0:
                accuracies.append(a.gold_correct / a.gold_total)
        if accuracies:
            self.quality_report.avg_annotator_accuracy = statistics.mean(accuracies)

        return self.quality_report

    def print_report(self):
        """Print formatted quality report."""
        r = self.quality_report
        print("\n" + "=" * 65)
        print("          ANNOTATION PIPELINE - QUALITY REPORT")
        print("=" * 65)

        print(f"\n{'PIPELINE OVERVIEW':^65}")
        print("-" * 65)
        print(f"  Total Items Annotated:    {r.total_items}")
        print(f"  Gold Standard Items:      {r.gold_items} ({r.gold_items/r.total_items*100:.1f}%)")
        print(f"  Annotations per Item:     {self.annotations_per_item}")
        print(f"  Total Annotations:        {r.total_items * self.annotations_per_item}")

        print(f"\n{'LLM PRE-LABELING':^65}")
        print("-" * 65)
        print(f"  LLM Pre-label Accuracy:   {r.llm_pre_label_accuracy*100:.1f}%")
        print(f"  Items Pre-labeled:        {r.total_items}")
        time_saved = (1 - 0.4) * 100  # 60% time saved per item
        print(f"  Time Saved (vs no pre-label): ~{time_saved:.0f}% per item")

        print(f"\n{'QUALITY METRICS':^65}")
        print("-" * 65)
        print(f"  Inter-Annotator Agreement (Kappa): {r.inter_annotator_agreement:.3f}")
        print(f"  Consensus Rate:           {r.consensus_rate*100:.1f}%")
        print(f"  Items Needing Adjudication: {r.items_needing_adjudication}")
        print(f"  Avg Annotator Gold Accuracy: {r.avg_annotator_accuracy*100:.1f}%")
        print(f"  Final Label Accuracy:     {r.estimated_final_accuracy*100:.1f}%")

        # Interpret Kappa
        kappa = r.inter_annotator_agreement
        if kappa > 0.8:
            interpretation = "Almost perfect agreement"
        elif kappa > 0.6:
            interpretation = "Substantial agreement"
        elif kappa > 0.4:
            interpretation = "Moderate agreement"
        else:
            interpretation = "Fair/poor agreement - review guidelines"
        print(f"  Agreement Interpretation: {interpretation}")

        print(f"\n{'ANNOTATOR PERFORMANCE':^65}")
        print("-" * 65)
        print(f"  {'Annotator':<14} {'Items':<8} {'Gold Acc':<10} {'Avg Time':<10} {'Status'}")
        print(f"  {'-'*14} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
        for a in self.annotators:
            gold_acc = a.gold_correct / a.gold_total * 100 if a.gold_total > 0 else 0
            avg_time = a.total_time / a.items_completed if a.items_completed > 0 else 0
            status = "OK" if gold_acc >= 70 else "FLAGGED"
            print(f"  {a.id:<14} {a.items_completed:<8} {gold_acc:<10.1f}% {avg_time:<10.1f}s {status}")

        # Cost analysis
        print(f"\n{'COST ANALYSIS':^65}")
        print("-" * 65)
        cost_per_annotation = 0.10  # $0.10 per annotation
        total_cost = r.total_items * self.annotations_per_item * cost_per_annotation
        cost_per_final_label = total_cost / r.total_items
        print(f"  Cost per annotation:      ${cost_per_annotation:.2f}")
        print(f"  Total annotations:        {r.total_items * self.annotations_per_item}")
        print(f"  Total cost:               ${total_cost:.2f}")
        print(f"  Cost per final label:     ${cost_per_final_label:.2f}")
        print(f"  (With 3-way redundancy + gold items for QC)")

        # Comparison: with vs without LLM assist
        print(f"\n{'LLM-ASSISTED vs TRADITIONAL':^65}")
        print("-" * 65)
        trad_time = sum(3600 / a.speed_items_per_hour for a in self.annotators) / len(self.annotators)
        llm_time = trad_time * 0.4
        print(f"  Traditional avg time/item:  {trad_time:.1f}s")
        print(f"  LLM-assisted avg time/item: {llm_time:.1f}s")
        print(f"  Speedup:                    {trad_time/llm_time:.1f}x")
        traditional_cost = r.total_items * self.annotations_per_item * cost_per_annotation * (trad_time / llm_time)
        print(f"  Traditional cost (same items): ${traditional_cost:.2f}")
        print(f"  Savings with LLM assist:    ${traditional_cost - total_cost:.2f} ({(1 - total_cost/traditional_cost)*100:.0f}%)")


def main():
    print("=" * 65)
    print("         ANNOTATION PIPELINE SIMULATOR")
    print("         Task Creation → Labeling → QC → Aggregation")
    print("=" * 65)

    random.seed(42)

    pipeline = AnnotationPipeline(
        num_annotators=5,
        annotations_per_item=3,
        gold_rate=0.08,
    )

    # Step 1: Create tasks
    print("\n  Step 1: Creating annotation tasks from production data...")
    items = pipeline.create_tasks(n_items=300)
    print(f"  Created {len(items)} items ({sum(1 for i in items if i.is_gold)} gold standards)")

    # Step 2: LLM pre-labeling
    print("\n  Step 2: LLM pre-labeling (AI labels first, human verifies)...")
    correct, total = pipeline.llm_pre_label()
    print(f"  LLM pre-labeled {total} items (accuracy: {correct/total*100:.1f}%)")

    # Step 3: Human annotation
    print("\n  Step 3: Distributing to annotators and collecting labels...")
    pipeline.assign_and_annotate()
    total_annotations = sum(a.items_completed for a in pipeline.annotators)
    print(f"  Collected {total_annotations} annotations from {len(pipeline.annotators)} annotators")

    # Step 4: Quality checks
    print("\n  Step 4: Running quality checks...")
    raw_agreement, kappa = pipeline.compute_inter_annotator_agreement()
    print(f"  Raw pairwise agreement: {raw_agreement*100:.1f}%")
    print(f"  Cohen's Kappa: {kappa:.3f}")

    flagged = pipeline.check_annotator_quality()
    if flagged:
        print(f"  Flagged annotators (gold accuracy < 70%):")
        for name, acc in flagged:
            print(f"    - {name}: {acc*100:.1f}% gold accuracy")
    else:
        print(f"  All annotators passed gold standard checks")

    # Step 5: Aggregate labels
    print("\n  Step 5: Aggregating labels (majority vote)...")
    pipeline.aggregate_labels()
    accuracy = pipeline.compute_final_accuracy()
    print(f"  Final label accuracy: {accuracy*100:.1f}%")

    # Step 6: Quality report
    pipeline.generate_quality_report()
    pipeline.print_report()

    # Summary
    print("\n" + "=" * 65)
    print("      KEY TAKEAWAYS")
    print("=" * 65)
    print("""
  1. Gold standard items catch low-quality annotators early
  2. LLM pre-labeling gives 2-3x speedup with minimal accuracy loss
  3. Multi-annotator consensus improves beyond individual accuracy
  4. Inter-annotator agreement (Kappa) measures task clarity
  5. Cost scales linearly - plan budget for redundancy + QC overhead
  6. Flagging poor annotators prevents training data corruption
    """)


if __name__ == "__main__":
    main()
