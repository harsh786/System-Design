"""
Simple Experiment Tracker - No external dependencies needed.
Tracks parameters, metrics per epoch, final results, and timing.
Run this file directly to see a demo with 3 experiments compared.

Requirements: numpy, scikit-learn (for demo), json, os, time (stdlib)
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path


class ExperimentTracker:
    """Lightweight experiment tracker using JSON files."""

    def __init__(self, base_dir="experiments"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.experiment = None

    def start(self, name, config, description=""):
        """Start tracking a new experiment."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_id = f"{timestamp}_{name}"
        exp_dir = self.base_dir / exp_id
        exp_dir.mkdir(parents=True)

        self.experiment = {
            "id": exp_id,
            "name": name,
            "dir": str(exp_dir),
            "description": description,
            "config": config,
            "start_time": time.time(),
            "metrics_history": [],
            "best_metric": None,
            "best_metric_value": float("-inf"),
        }

        # Save config
        with open(exp_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)

        print(f"[START] Experiment: {exp_id}")
        return self

    def log_metrics(self, metrics, step):
        """Log metrics for a given step/epoch."""
        entry = {"step": step, **metrics}
        self.experiment["metrics_history"].append(entry)

        # Track best (assumes first metric is primary, higher=better)
        primary_key = list(metrics.keys())[0]
        if metrics[primary_key] > self.experiment["best_metric_value"]:
            self.experiment["best_metric_value"] = metrics[primary_key]
            self.experiment["best_metric"] = {
                "step": step,
                "value": metrics[primary_key],
                "metric": primary_key,
            }

    def end(self, final_results=None):
        """End experiment and save all results."""
        duration = time.time() - self.experiment["start_time"]
        exp_dir = Path(self.experiment["dir"])

        summary = {
            "id": self.experiment["id"],
            "name": self.experiment["name"],
            "description": self.experiment["description"],
            "config": self.experiment["config"],
            "duration_seconds": round(duration, 2),
            "best": self.experiment["best_metric"],
            "final_results": final_results or {},
            "metrics_history": self.experiment["metrics_history"],
        }

        # Save full results
        with open(exp_dir / "results.json", "w") as f:
            json.dump(summary, f, indent=2)

        # Append to registry
        self._update_registry(summary)

        print(f"[DONE]  {self.experiment['id']} | "
              f"Best {self.experiment['best_metric']['metric']}: "
              f"{self.experiment['best_metric']['value']:.4f} | "
              f"Time: {duration:.1f}s")

        return summary

    def _update_registry(self, summary):
        registry_path = self.base_dir / "registry.json"
        registry = []
        if registry_path.exists():
            with open(registry_path) as f:
                registry = json.load(f)
        registry.append({
            "id": summary["id"],
            "config": summary["config"],
            "best": summary["best"],
            "final_results": summary["final_results"],
            "duration_seconds": summary["duration_seconds"],
        })
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    @classmethod
    def compare(cls, base_dir="experiments"):
        """Load registry and print comparison table."""
        registry_path = Path(base_dir) / "registry.json"
        if not registry_path.exists():
            print("No experiments found.")
            return

        with open(registry_path) as f:
            registry = json.load(f)

        # Sort by best metric value descending
        registry.sort(key=lambda x: x["best"]["value"] if x["best"] else 0,
                      reverse=True)

        print("\n" + "=" * 75)
        print(f"{'EXPERIMENT COMPARISON':^75}")
        print("=" * 75)
        print(f"{'#':<3} {'Name':<28} {'Best Score':<12} "
              f"{'Test Acc':<10} {'Time(s)':<8} {'LR':<10}")
        print("-" * 75)

        for i, exp in enumerate(registry, 1):
            test_acc = exp["final_results"].get("test_accuracy", "N/A")
            test_str = f"{test_acc:.4f}" if isinstance(test_acc, float) else test_acc
            lr = exp["config"].get("learning_rate", "N/A")
            lr_str = f"{lr}" if lr is not None else "N/A"
            best_val = exp["best"]["value"] if exp["best"] else 0

            print(f"{i:<3} {exp['id']:<28} {best_val:<12.4f} "
                  f"{test_str:<10} {exp['duration_seconds']:<8.1f} {lr_str:<10}")

        print("=" * 75)
        print(f"Winner: {registry[0]['id']}")
        print()


# =============================================================================
# DEMO: Run 3 experiments with different hyperparameters and compare
# =============================================================================

def run_demo():
    """Run 3 sklearn experiments with different params and compare."""
    import numpy as np
    from sklearn.datasets import load_digits
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, cross_val_score

    print("\n" + "=" * 60)
    print(" EXPERIMENT TRACKER DEMO ")
    print("=" * 60)

    # Load data
    X, y = load_digits(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Clean up any previous demo runs
    demo_dir = "/tmp/experiment_tracker_demo"
    if os.path.exists(demo_dir):
        import shutil
        shutil.rmtree(demo_dir)

    # Define 3 experiments with different hyperparameters
    experiments = [
        {
            "name": "rf_shallow",
            "description": "Random Forest with shallow trees",
            "config": {
                "model": "RandomForest",
                "n_estimators": 50,
                "max_depth": 5,
                "min_samples_split": 5,
                "learning_rate": None,
                "seed": 42,
            },
        },
        {
            "name": "rf_deep",
            "description": "Random Forest with deep trees",
            "config": {
                "model": "RandomForest",
                "n_estimators": 100,
                "max_depth": 20,
                "min_samples_split": 2,
                "learning_rate": None,
                "seed": 42,
            },
        },
        {
            "name": "rf_large",
            "description": "Large Random Forest, no depth limit",
            "config": {
                "model": "RandomForest",
                "n_estimators": 200,
                "max_depth": None,
                "min_samples_split": 2,
                "learning_rate": None,
                "seed": 42,
            },
        },
    ]

    tracker = ExperimentTracker(base_dir=demo_dir)

    for exp_def in experiments:
        config = exp_def["config"]
        tracker.start(exp_def["name"], config, exp_def["description"])

        # Simulate epoch-like iterations using incremental n_estimators
        clf = None
        n_est = config["n_estimators"]
        steps = 5  # simulate 5 "epochs" by increasing trees

        for step in range(1, steps + 1):
            partial_n = max(10, n_est * step // steps)
            clf = RandomForestClassifier(
                n_estimators=partial_n,
                max_depth=config["max_depth"],
                min_samples_split=config["min_samples_split"],
                random_state=config["seed"],
                n_jobs=-1,
            )
            clf.fit(X_train, y_train)
            train_acc = clf.score(X_train, y_train)
            val_scores = cross_val_score(clf, X_train, y_train, cv=3)
            val_acc = val_scores.mean()

            tracker.log_metrics({
                "val_accuracy": val_acc,
                "train_accuracy": train_acc,
                "n_trees": partial_n,
            }, step=step)

        # Final evaluation on test set
        test_acc = clf.score(X_test, y_test)
        tracker.end(final_results={
            "test_accuracy": test_acc,
            "val_accuracy_final": val_acc,
            "train_accuracy_final": train_acc,
        })

    # Compare all experiments
    ExperimentTracker.compare(base_dir=demo_dir)

    # Show what files were created
    print("Files created:")
    for root, dirs, files in os.walk(demo_dir):
        level = root.replace(demo_dir, "").count(os.sep)
        indent = "  " * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = "  " * (level + 1)
        for f in files:
            print(f"{sub_indent}{f}")


if __name__ == "__main__":
    run_demo()
