"""
Architecture Fitness Function Evaluator
========================================
Defines and evaluates fitness functions for an AI platform,
tracking architecture evolution over time and identifying
gaps between current state and target architecture.

Demonstrates how Staff Architects measure progress toward
their architecture vision quantitatively.

Usage: python3 main.py

No external dependencies required.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta
import random


class Status(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class FitnessFunction:
    """
    An architecture fitness function - a measurable indicator
    of whether the architecture is moving toward or away from
    its target state.
    """
    name: str
    description: str
    category: str  # performance, cost, reliability, quality, developer_experience
    current_value: float
    target_value: float
    threshold_warning: float
    threshold_critical: float
    unit: str
    higher_is_better: bool
    trend: List[float] = field(default_factory=list)  # last 6 months
    
    @property
    def status(self) -> Status:
        if self.higher_is_better:
            if self.current_value >= self.target_value:
                return Status.HEALTHY
            elif self.current_value >= self.threshold_warning:
                return Status.WARNING
            else:
                return Status.CRITICAL
        else:
            if self.current_value <= self.target_value:
                return Status.HEALTHY
            elif self.current_value <= self.threshold_warning:
                return Status.WARNING
            else:
                return Status.CRITICAL
    
    @property
    def gap_percent(self) -> float:
        if self.target_value == 0:
            return 0
        return abs(self.current_value - self.target_value) / abs(self.target_value) * 100
    
    @property
    def trend_direction(self) -> str:
        if len(self.trend) < 2:
            return "UNKNOWN"
        recent = self.trend[-2:]
        if self.higher_is_better:
            return "IMPROVING" if recent[-1] > recent[-2] else "DEGRADING"
        else:
            return "IMPROVING" if recent[-1] < recent[-2] else "DEGRADING"


def create_fitness_functions() -> List[FitnessFunction]:
    """
    Define fitness functions for an AI platform.
    
    TEACHING POINT: Fitness functions should cover multiple dimensions.
    An architecture that's fast but expensive, or cheap but unreliable,
    isn't fit. You need a balanced scorecard.
    """
    return [
        # Performance
        FitnessFunction(
            name="Inference Latency (p99)",
            description="99th percentile latency for model inference requests",
            category="performance",
            current_value=8100,
            target_value=3000,
            threshold_warning=5000,
            threshold_critical=10000,
            unit="ms",
            higher_is_better=False,
            trend=[9500, 9200, 8800, 8500, 8300, 8100],
        ),
        FitnessFunction(
            name="Cache Hit Rate",
            description="Percentage of requests served from semantic cache",
            category="performance",
            current_value=12,
            target_value=35,
            threshold_warning=20,
            threshold_critical=5,
            unit="%",
            higher_is_better=True,
            trend=[0, 2, 5, 8, 10, 12],
        ),
        
        # Cost
        FitnessFunction(
            name="Cost Per Query",
            description="Average cost per inference request including all infrastructure",
            category="cost",
            current_value=0.0070,
            target_value=0.0040,
            threshold_warning=0.0080,
            threshold_critical=0.0100,
            unit="USD",
            higher_is_better=False,
            trend=[0.0065, 0.0068, 0.0070, 0.0072, 0.0071, 0.0070],
        ),
        FitnessFunction(
            name="Cost Growth Rate (QoQ)",
            description="Quarter-over-quarter cost growth normalized by traffic",
            category="cost",
            current_value=40,
            target_value=10,
            threshold_warning=25,
            threshold_critical=50,
            unit="% QoQ",
            higher_is_better=False,
            trend=[35, 38, 42, 45, 42, 40],
        ),
        
        # Reliability
        FitnessFunction(
            name="Platform Availability",
            description="Percentage uptime excluding planned maintenance",
            category="reliability",
            current_value=99.5,
            target_value=99.95,
            threshold_warning=99.9,
            threshold_critical=99.0,
            unit="%",
            higher_is_better=True,
            trend=[99.2, 99.3, 99.4, 99.5, 99.5, 99.5],
        ),
        FitnessFunction(
            name="Mean Time to Recovery",
            description="Average time to recover from incidents",
            category="reliability",
            current_value=240,
            target_value=30,
            threshold_warning=60,
            threshold_critical=300,
            unit="minutes",
            higher_is_better=False,
            trend=[360, 320, 280, 260, 250, 240],
        ),
        FitnessFunction(
            name="Provider Independence",
            description="Can survive any single provider outage without user impact",
            category="reliability",
            current_value=0,
            target_value=100,
            threshold_warning=50,
            threshold_critical=0,
            unit="% traffic with failover",
            higher_is_better=True,
            trend=[0, 0, 0, 0, 0, 0],
        ),
        
        # Quality
        FitnessFunction(
            name="Evaluation Coverage",
            description="Percentage of production use cases with automated quality evaluation",
            category="quality",
            current_value=35,
            target_value=95,
            threshold_warning=60,
            threshold_critical=30,
            unit="%",
            higher_is_better=True,
            trend=[20, 22, 25, 28, 32, 35],
        ),
        FitnessFunction(
            name="Quality Regressions Detected Pre-Production",
            description="Percentage of quality issues caught before reaching users",
            category="quality",
            current_value=20,
            target_value=90,
            threshold_warning=50,
            threshold_critical=20,
            unit="%",
            higher_is_better=True,
            trend=[10, 12, 14, 16, 18, 20],
        ),
        
        # Developer Experience
        FitnessFunction(
            name="Time to First AI Feature",
            description="Days from project start to first production AI feature for a new team",
            category="developer_experience",
            current_value=21,
            target_value=2,
            threshold_warning=7,
            threshold_critical=30,
            unit="days",
            higher_is_better=False,
            trend=[28, 26, 24, 23, 22, 21],
        ),
        FitnessFunction(
            name="Platform Adoption",
            description="Percentage of teams using the centralized AI platform",
            category="developer_experience",
            current_value=17,
            target_value=100,
            threshold_warning=50,
            threshold_critical=10,
            unit="% of teams",
            higher_is_better=True,
            trend=[0, 0, 8, 8, 17, 17],
        ),
    ]


def evaluate_fitness(functions: List[FitnessFunction]) -> Dict[str, any]:
    """Evaluate overall architecture fitness."""
    results = {
        "total": len(functions),
        "healthy": sum(1 for f in functions if f.status == Status.HEALTHY),
        "warning": sum(1 for f in functions if f.status == Status.WARNING),
        "critical": sum(1 for f in functions if f.status == Status.CRITICAL),
        "improving": sum(1 for f in functions if f.trend_direction == "IMPROVING"),
        "degrading": sum(1 for f in functions if f.trend_direction == "DEGRADING"),
    }
    results["fitness_score"] = results["healthy"] / results["total"] * 100
    return results


def print_dashboard(functions: List[FitnessFunction]) -> None:
    """Print a fitness function dashboard."""
    print()
    print("=" * 70)
    print("  ARCHITECTURE FITNESS DASHBOARD")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    # Group by category
    categories = {}
    for f in functions:
        categories.setdefault(f.category, []).append(f)
    
    status_icons = {
        Status.HEALTHY: "●",
        Status.WARNING: "◐",
        Status.CRITICAL: "○",
        Status.UNKNOWN: "?",
    }
    
    for category, fns in categories.items():
        print()
        print(f"  ┌─ {category.upper().replace('_', ' ')} {'─' * (50 - len(category))}")
        for f in fns:
            icon = status_icons[f.status]
            trend = "↑" if f.trend_direction == "IMPROVING" else "↓" if f.trend_direction == "DEGRADING" else "→"
            
            print(f"  │ {icon} {f.name}")
            print(f"  │   Current: {f.current_value}{f.unit}  Target: {f.target_value}{f.unit}  {trend} {f.trend_direction}")
            
            if f.status == Status.CRITICAL:
                print(f"  │   ⚠ GAP: {f.gap_percent:.0f}% from target")
        print(f"  └{'─' * 65}")


def print_recommendations(functions: List[FitnessFunction]) -> None:
    """Generate recommendations based on fitness evaluation."""
    print()
    print("=" * 70)
    print("  RECOMMENDATIONS")
    print("=" * 70)
    
    critical = [f for f in functions if f.status == Status.CRITICAL]
    degrading = [f for f in functions if f.trend_direction == "DEGRADING"]
    
    if critical:
        print()
        print("  🔴 CRITICAL - Immediate Action Required:")
        for f in critical:
            print(f"    • {f.name}: {f.current_value}{f.unit} → target {f.target_value}{f.unit}")
            print(f"      Gap: {f.gap_percent:.0f}%. ", end="")
            # Contextual recommendation
            if "Provider" in f.name:
                print("Implement multi-provider failover as highest priority.")
            elif "Cost Growth" in f.name:
                print("Implement caching and model routing to bend the cost curve.")
            elif "Evaluation" in f.name:
                print("Ship eval framework and mandate for new features.")
            elif "Recovery" in f.name:
                print("Build automated runbooks and reduce manual intervention.")
            else:
                print("Requires architecture intervention.")
            print()
    
    if degrading:
        print()
        print("  🟡 DEGRADING TRENDS - Investigate:")
        for f in degrading:
            recent_change = f.trend[-1] - f.trend[-2] if len(f.trend) >= 2 else 0
            print(f"    • {f.name}: trending {'up' if recent_change > 0 else 'down'} "
                  f"({recent_change:+.4f}{f.unit} last period)")
    
    # Overall health
    results = evaluate_fitness(functions)
    print()
    print("  📊 OVERALL ARCHITECTURE HEALTH:")
    print(f"    Fitness Score: {results['fitness_score']:.0f}% ({results['healthy']}/{results['total']} targets met)")
    print(f"    Improving: {results['improving']}/{results['total']} metrics trending in right direction")
    print()
    
    if results['fitness_score'] < 30:
        print("    ASSESSMENT: Architecture is significantly behind target state.")
        print("    The vision needs either accelerated investment or revised targets.")
    elif results['fitness_score'] < 60:
        print("    ASSESSMENT: Making progress but significant gaps remain.")
        print("    Focus on critical items; don't spread effort too thin.")
    elif results['fitness_score'] < 90:
        print("    ASSESSMENT: Good progress. Focus on remaining gaps and")
        print("    preventing regressions in healthy metrics.")
    else:
        print("    ASSESSMENT: Architecture is largely aligned with vision.")
        print("    Consider setting more ambitious targets for next phase.")


def print_evolution_timeline(functions: List[FitnessFunction]) -> None:
    """Show how fitness has evolved over time."""
    print()
    print("=" * 70)
    print("  FITNESS EVOLUTION (Last 6 Months)")
    print("=" * 70)
    print()
    
    months = ["Month -5", "Month -4", "Month -3", "Month -2", "Month -1", "Current"]
    
    # Show a few key metrics over time
    key_metrics = [f for f in functions if f.name in [
        "Cost Per Query", "Platform Availability", "Evaluation Coverage", "Platform Adoption"
    ]]
    
    for f in key_metrics:
        print(f"  {f.name} ({f.unit}):")
        print(f"    Target: {f.target_value}")
        bar_width = 40
        for i, (month, value) in enumerate(zip(months, f.trend)):
            # Normalize for display
            if f.higher_is_better:
                fill = int(value / f.target_value * bar_width) if f.target_value else 0
            else:
                fill = int((1 - value / (f.threshold_critical * 1.5)) * bar_width)
            fill = max(0, min(bar_width, fill))
            bar = "█" * fill + "░" * (bar_width - fill)
            marker = " ← NOW" if i == len(months) - 1 else ""
            print(f"    {month:>8}: [{bar}] {value}{f.unit}{marker}")
        print()


def main():
    """Main execution demonstrating architecture fitness evaluation."""
    print("=" * 70)
    print("  ARCHITECTURE FITNESS FUNCTION EVALUATOR")
    print("=" * 70)
    print()
    print("  Fitness functions are quantitative measures of whether your")
    print("  architecture is evolving toward its target state. They answer:")
    print("  'Are we getting closer to our vision, or drifting away?'")
    print()
    print("  💡 TEACHING POINT: Without fitness functions, architecture visions")
    print("     become aspirational documents that gather dust. With them,")
    print("     you can have data-driven conversations about progress.")
    print()
    
    # Create and evaluate
    functions = create_fitness_functions()
    
    # Print dashboard
    print_dashboard(functions)
    
    # Print evolution
    print_evolution_timeline(functions)
    
    # Print recommendations
    print_recommendations(functions)
    
    # Teaching summary
    print()
    print("=" * 70)
    print("  HOW TO USE FITNESS FUNCTIONS")
    print("=" * 70)
    print("""
  1. DEFINE at architecture vision time (not after)
     - Each dimension of your vision gets a fitness function
     - Include current value, target, and thresholds

  2. MEASURE regularly (monthly or quarterly)
     - Automate collection where possible
     - Track trends, not just point-in-time values

  3. ACT on degradation
     - Warning = investigate
     - Critical = immediate action
     - Degrading trend = systemic issue

  4. COMMUNICATE with stakeholders
     - This dashboard goes to leadership quarterly
     - It justifies continued investment in architecture
     - It shows ROI of platform work

  5. EVOLVE the functions themselves
     - As architecture matures, targets get more ambitious
     - Add new functions as new dimensions matter
     - Retire functions when permanently green

  The Staff Architect's job: define these, track them, and use them
  to drive architectural decisions. Without measurement, you're just
  hoping the vision comes true.
""")


if __name__ == "__main__":
    main()
