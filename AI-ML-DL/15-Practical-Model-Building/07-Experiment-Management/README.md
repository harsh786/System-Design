# Experiment Management: Track, Compare, and Reproduce ML Experiments

## 1. Why Experiment Management Matters

### The Horror Story Every ML Engineer Knows

```
"I got 95% accuracy last week but can't reproduce it."

- Was it learning rate 0.001 or 0.0001?
- Did I use dropout 0.3 or 0.5?
- Which version of the data did I use?
- Was it before or after I fixed that preprocessing bug?
- Which notebook was it in? experiment_v3_final_FINAL2.ipynb?
```

### The Typical Chaos

```
project/
├── train.py
├── train_v2.py
├── train_v2_fixed.py
├── train_final.py
├── train_FINAL_USE_THIS.py          # <- Nobody knows which is best
├── notebook_experiments.ipynb        # <- 200 cells, half commented out
├── model_good.pt
├── model_better.pt
├── model_best_maybe.pt
└── results_somewhere.txt             # <- "accuracy was like 94%?"
```

### The Professional Approach

Every experiment is:
- **Tracked** - all parameters, metrics, and artifacts logged automatically
- **Reproducible** - can re-run any past experiment and get the same result
- **Comparable** - easy to see which approach works best and why
- **Searchable** - find that great result from 3 months ago instantly

---

## 2. What to Track for EVERY Experiment

```
MUST LOG:
├── Code version (git commit hash)
├── Data version (hash or DVC pointer)
├── Hyperparameters (ALL of them)
│   ├── Learning rate, batch size, epochs
│   ├── Model architecture choices
│   ├── Preprocessing parameters
│   └── Random seeds
├── Metrics (training AND validation)
│   ├── Loss curve (every epoch)
│   ├── Primary metric (accuracy, F1, etc.)
│   ├── Secondary metrics
│   └── Training time
├── Artifacts
│   ├── Model checkpoint (best)
│   ├── Config file
│   ├── Sample predictions
│   └── Confusion matrix / plots
└── Environment
    ├── Python version
    ├── Package versions (pip freeze)
    ├── Hardware (GPU type, memory)
    └── Random seeds (all of them!)
```

### Why Each Category Matters

| Category | Without It | With It |
|----------|-----------|---------|
| Code version | "Which version of train.py?" | `git checkout abc123` and re-run |
| Data version | "Was this before the data fix?" | Exact dataset hash verified |
| Hyperparameters | "Maybe lr was 0.001?" | All params in config.yaml |
| Metrics per epoch | "It was around 94%" | Full learning curve available |
| Artifacts | "The model file got overwritten" | Checkpoint safely stored |
| Environment | "Works on my machine" | Exact package versions frozen |

### Minimum Viable Experiment Log

```python
experiment_log = {
    "experiment_id": "exp_2024_01_15_001",
    "timestamp": "2024-01-15T14:30:00",
    "git_commit": "a1b2c3d",
    "description": "ResNet50 with higher learning rate",
    
    "data": {
        "dataset": "cifar10",
        "version": "v2.1",
        "train_size": 45000,
        "val_size": 5000,
        "test_size": 10000,
        "preprocessing": "normalize_imagenet"
    },
    
    "hyperparameters": {
        "model": "resnet50",
        "learning_rate": 0.01,
        "batch_size": 128,
        "epochs": 100,
        "optimizer": "adam",
        "weight_decay": 1e-4,
        "scheduler": "cosine",
        "dropout": 0.3,
        "seed": 42
    },
    
    "results": {
        "best_val_accuracy": 0.943,
        "best_val_loss": 0.187,
        "test_accuracy": 0.938,
        "training_time_hours": 2.3,
        "best_epoch": 67
    },
    
    "environment": {
        "python": "3.10.12",
        "pytorch": "2.1.0",
        "cuda": "12.1",
        "gpu": "NVIDIA A100 40GB"
    }
}
```

---

## 3. Experiment Tracking Tools Comparison

| Tool | Free? | Self-hosted? | Best for | Learning Curve |
|------|-------|-------------|----------|---------------|
| **MLflow** | Yes (OSS) | Yes | Teams, production pipelines | Medium |
| **W&B** | Free tier (personal) | No (cloud) | Research, visualization | Low |
| **TensorBoard** | Yes | Yes | Quick loss/metric viz | Low |
| **Neptune** | Free tier | No (cloud) | Collaboration, enterprise | Low |
| **Comet** | Free tier | No (cloud) | Enterprise, comparison | Medium |
| **Sacred** | Yes (OSS) | Yes | Academic research | Medium |
| **DVC** | Yes (OSS) | Yes | Data/model versioning | Medium |
| **Simple CSV/JSON** | Yes | Yes | Solo projects, learning | None |

### Decision Framework

```
Solo researcher, < 50 experiments?
  → Simple JSON/YAML tracking (Section 6)

Solo researcher, want great visualizations?
  → W&B free tier

Team, need self-hosted?
  → MLflow

Team, want zero setup?
  → W&B or Neptune

Production ML pipeline?
  → MLflow + DVC

Academic paper reproducibility?
  → Sacred or MLflow + Git tags
```

---

## 4. MLflow Complete Workflow

### Setup

```bash
pip install mlflow
mlflow server --backend-store-uri sqlite:///mlflow.db \
              --default-artifact-root ./mlflow-artifacts \
              --host 0.0.0.0 --port 5000
```

### Complete Training Script with MLflow

```python
import mlflow
import mlflow.pytorch
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import time
import subprocess

# Get git commit hash
def get_git_hash():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD']
        ).decode('utf-8').strip()[:8]
    except:
        return "unknown"

# Configuration
config = {
    "model_name": "resnet50",
    "learning_rate": 0.001,
    "batch_size": 128,
    "epochs": 50,
    "optimizer": "adam",
    "weight_decay": 1e-4,
    "dropout": 0.3,
    "seed": 42,
}

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("image-classification")

with mlflow.start_run(run_name=f"{config['model_name']}_lr{config['learning_rate']}"):
    # Log ALL parameters
    mlflow.log_params(config)
    mlflow.log_param("git_commit", get_git_hash())
    mlflow.log_param("python_version", "3.10.12")
    
    # Tag for easy filtering
    mlflow.set_tag("stage", "development")
    mlflow.set_tag("model_family", "resnet")
    
    # Training loop
    best_val_acc = 0
    start_time = time.time()
    
    for epoch in range(config["epochs"]):
        train_loss = train_one_epoch(model, train_loader, optimizer)
        val_loss, val_acc = evaluate(model, val_loader)
        
        # Log metrics EVERY epoch
        mlflow.log_metrics({
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_accuracy": val_acc,
            "learning_rate": optimizer.param_groups[0]['lr'],
        }, step=epoch)
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            mlflow.pytorch.log_model(model, "best_model")
            mlflow.log_metric("best_val_accuracy", best_val_acc)
            mlflow.log_metric("best_epoch", epoch)
    
    # Log final results
    training_time = time.time() - start_time
    mlflow.log_metric("training_time_seconds", training_time)
    
    # Log artifacts (plots, configs, etc.)
    mlflow.log_artifact("confusion_matrix.png")
    mlflow.log_artifact("config.yaml")

# Compare runs programmatically
from mlflow.tracking import MlflowClient
client = MlflowClient()
experiment = client.get_experiment_by_name("image-classification")
runs = client.search_runs(
    experiment_ids=[experiment.experiment_id],
    order_by=["metrics.best_val_accuracy DESC"],
    max_results=10
)

print("\nTop 10 Experiments:")
print(f"{'Run Name':<30} {'Val Acc':<10} {'LR':<10} {'Epochs':<8}")
print("-" * 58)
for run in runs:
    print(f"{run.info.run_name:<30} "
          f"{run.data.metrics.get('best_val_accuracy', 0):<10.4f} "
          f"{run.data.params.get('learning_rate', 'N/A'):<10} "
          f"{run.data.params.get('epochs', 'N/A'):<8}")
```

### MLflow Model Registry

```python
# Register best model
model_uri = f"runs:/{best_run.info.run_id}/best_model"
mlflow.register_model(model_uri, "image-classifier")

# Transition to production
client.transition_model_version_stage(
    name="image-classifier",
    version=3,
    stage="Production"
)

# Load production model
model = mlflow.pytorch.load_model("models:/image-classifier/Production")
```

---

## 5. Weights & Biases Complete Workflow

### Setup

```bash
pip install wandb
wandb login  # Enter API key from wandb.ai/authorize
```

### Complete Training Script with W&B

```python
import wandb
import torch
import numpy as np

# Initialize
config = {
    "model": "resnet50",
    "learning_rate": 0.001,
    "batch_size": 128,
    "epochs": 50,
    "optimizer": "adam",
    "dropout": 0.3,
    "dataset": "cifar10",
    "seed": 42,
}

run = wandb.init(
    project="image-classification",
    name="resnet50-lr001-drop03",
    config=config,
    tags=["resnet", "baseline"],
    notes="Testing higher dropout with cosine schedule"
)

# W&B automatically logs git commit, OS, hardware info!

# Watch model gradients and parameters
wandb.watch(model, log="all", log_freq=100)

# Training loop
for epoch in range(config["epochs"]):
    train_loss = train_one_epoch(model, train_loader, optimizer)
    val_loss, val_acc, val_f1 = evaluate(model, val_loader)
    
    # Log metrics
    wandb.log({
        "epoch": epoch,
        "train/loss": train_loss,
        "val/loss": val_loss,
        "val/accuracy": val_acc,
        "val/f1": val_f1,
        "lr": optimizer.param_groups[0]['lr'],
    })
    
    # Log sample predictions as images
    if epoch % 10 == 0:
        images, preds, labels = get_sample_predictions(model, val_loader)
        wandb.log({
            "predictions": [
                wandb.Image(img, caption=f"Pred: {p}, True: {l}")
                for img, p, l in zip(images[:16], preds[:16], labels[:16])
            ]
        })

# Log confusion matrix
wandb.log({
    "confusion_matrix": wandb.plot.confusion_matrix(
        y_true=all_labels, preds=all_preds, class_names=class_names
    )
})

# Save model as artifact
artifact = wandb.Artifact("trained-model", type="model")
artifact.add_file("model_best.pt")
run.log_artifact(artifact)

wandb.finish()
```

### W&B Sweeps (Hyperparameter Search)

```python
# sweep_config.yaml
sweep_config = {
    "method": "bayes",  # bayes, grid, random
    "metric": {"name": "val/accuracy", "goal": "maximize"},
    "parameters": {
        "learning_rate": {
            "distribution": "log_uniform_values",
            "min": 1e-5,
            "max": 1e-1,
        },
        "batch_size": {"values": [32, 64, 128, 256]},
        "dropout": {"distribution": "uniform", "min": 0.1, "max": 0.5},
        "optimizer": {"values": ["adam", "sgd", "adamw"]},
    },
    "early_terminate": {
        "type": "hyperband",
        "min_iter": 5,
        "eta": 3,
    },
}

# Launch sweep
sweep_id = wandb.sweep(sweep_config, project="image-classification")

def train_sweep():
    run = wandb.init()
    config = wandb.config  # Automatically set by sweep agent
    
    model = build_model(dropout=config.dropout)
    optimizer = get_optimizer(config.optimizer, config.learning_rate)
    
    for epoch in range(50):
        train_loss = train_one_epoch(model, train_loader, optimizer)
        val_loss, val_acc = evaluate(model, val_loader)
        wandb.log({"val/accuracy": val_acc, "val/loss": val_loss})

# Run 50 trials
wandb.agent(sweep_id, function=train_sweep, count=50)
```

---

## 6. DIY Experiment Tracking (No External Tools)

### Directory Structure

```
experiments/
├── registry.json                     # Index of all experiments
├── 2024-01-15_resnet50_lr001/
│   ├── config.yaml                   # ALL hyperparameters
│   ├── metrics.json                  # Per-epoch metrics
│   ├── results.json                  # Final summary
│   ├── model_best.pt                 # Best checkpoint
│   ├── training.log                  # Stdout/stderr
│   └── plots/
│       ├── loss_curve.png
│       └── confusion_matrix.png
├── 2024-01-16_resnet50_lr0001/
│   ├── config.yaml
│   ├── metrics.json
│   ├── results.json
│   └── ...
└── compare_experiments.py            # Script to compare results
```

### Complete DIY Implementation

```python
"""Minimal experiment tracker - no external dependencies beyond stdlib."""
import json
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path

class ExperimentTracker:
    def __init__(self, base_dir="experiments"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.current_experiment = None
        self.metrics_history = []
    
    def start_experiment(self, name, config):
        """Start a new experiment."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        exp_name = f"{timestamp}_{name}"
        exp_dir = self.base_dir / exp_name
        exp_dir.mkdir(parents=True)
        
        self.current_experiment = {
            "name": exp_name,
            "dir": exp_dir,
            "config": config,
            "start_time": time.time(),
            "metrics_history": [],
        }
        
        # Save config immediately
        with open(exp_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"Started experiment: {exp_name}")
        return exp_name
    
    def log_metrics(self, metrics, step=None):
        """Log metrics for current step/epoch."""
        entry = {"step": step, "timestamp": time.time(), **metrics}
        self.current_experiment["metrics_history"].append(entry)
        
        # Append to file incrementally (crash-safe)
        with open(self.current_experiment["dir"] / "metrics.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def end_experiment(self, final_results=None):
        """Finalize and save experiment results."""
        duration = time.time() - self.current_experiment["start_time"]
        
        summary = {
            "name": self.current_experiment["name"],
            "config": self.current_experiment["config"],
            "duration_seconds": duration,
            "final_results": final_results or {},
            "num_steps": len(self.current_experiment["metrics_history"]),
        }
        
        with open(self.current_experiment["dir"] / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        # Update registry
        self._update_registry(summary)
        print(f"Experiment complete: {duration:.1f}s")
    
    def _update_registry(self, summary):
        registry_path = self.base_dir / "registry.json"
        registry = []
        if registry_path.exists():
            with open(registry_path) as f:
                registry = json.load(f)
        registry.append({
            "name": summary["name"],
            "results": summary["final_results"],
            "config": summary["config"],
        })
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)
    
    @staticmethod
    def compare(base_dir="experiments"):
        """Compare all experiments."""
        registry_path = Path(base_dir) / "registry.json"
        if not registry_path.exists():
            print("No experiments found.")
            return
        
        with open(registry_path) as f:
            registry = json.load(f)
        
        # Print comparison table
        print(f"\n{'Experiment':<40} {'Accuracy':<10} {'Loss':<10} {'LR':<10}")
        print("-" * 70)
        for exp in sorted(registry, 
                         key=lambda x: x['results'].get('val_accuracy', 0),
                         reverse=True):
            print(f"{exp['name']:<40} "
                  f"{exp['results'].get('val_accuracy', 'N/A'):<10.4f} "
                  f"{exp['results'].get('val_loss', 'N/A'):<10.4f} "
                  f"{exp['config'].get('learning_rate', 'N/A'):<10}")
```

See `simple_experiment_tracker.py` for the complete runnable version.

---

## 7. Hyperparameter Search Strategies

### Strategy Comparison

| Method | Pros | Cons | When to Use |
|--------|------|------|-------------|
| Grid Search | Exhaustive, simple | Exponentially expensive | ≤3 params, few values each |
| Random Search | Better coverage, cheap | No learning between trials | First exploration |
| Bayesian (Optuna) | Smart, efficient | Overhead, sequential | Main optimization phase |
| Population-Based | Adapts schedule | Complex, needs resources | Large-scale training |

### Why Random Search Beats Grid Search

```
Grid search with 3 params × 10 values = 1,000 experiments
But only explores 10 unique values per dimension!

Random search with 100 experiments:
Explores 100 unique values per dimension!
Often finds better results with 10x fewer experiments.
```

### Optuna Example (Bayesian Optimization)

```python
import optuna
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.datasets import load_digits

def objective(trial):
    """Optuna objective function."""
    # Suggest hyperparameters
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 50, 500),
        "max_depth": trial.suggest_int("max_depth", 3, 30),
        "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
        "max_features": trial.suggest_categorical(
            "max_features", ["sqrt", "log2", None]
        ),
    }
    
    # Train and evaluate
    X, y = load_digits(return_X_y=True)
    clf = RandomForestClassifier(**params, random_state=42, n_jobs=-1)
    scores = cross_val_score(clf, X, y, cv=5, scoring="accuracy")
    
    # Report intermediate results for pruning
    accuracy = scores.mean()
    return accuracy

# Run optimization
study = optuna.create_study(
    direction="maximize",
    study_name="rf-optimization",
    pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
)
study.optimize(objective, n_trials=100, show_progress_bar=True)

# Results
print(f"\nBest accuracy: {study.best_value:.4f}")
print(f"Best params: {study.best_params}")

# Visualization
optuna.visualization.plot_optimization_history(study)
optuna.visualization.plot_param_importances(study)
optuna.visualization.plot_parallel_coordinate(study)
```

### Budget Allocation Strategy

```
Total budget: 100 GPU-hours

Phase 1 - Broad exploration (20% budget):
  Random search, 20 trials, short training (5 epochs)
  Goal: Identify promising regions

Phase 2 - Focused search (50% budget):
  Bayesian optimization, 30 trials, medium training (20 epochs)
  Goal: Find best hyperparameters in promising region

Phase 3 - Final training (30% budget):
  Top 3 configs, full training (100 epochs), 3 seeds each
  Goal: Get reliable final numbers with confidence intervals
```

---

## 8. Comparing Experiments and Picking Winners

### Don't Just Compare Single Numbers

```
BAD:
  Model A accuracy: 0.943
  Model B accuracy: 0.941
  "Model A wins!"

GOOD:
  Model A: 0.943 ± 0.008 (5 seeds, 5 folds)
  Model B: 0.941 ± 0.005 (5 seeds, 5 folds)
  p-value: 0.42 → NOT statistically significant
  Model B has lower variance → might be more reliable
```

### Statistical Comparison Framework

```python
import numpy as np
from scipy import stats

def compare_models(scores_a, scores_b, model_a_name="A", model_b_name="B"):
    """Statistically compare two models using paired t-test."""
    assert len(scores_a) == len(scores_b), "Need paired observations"
    
    mean_a, std_a = np.mean(scores_a), np.std(scores_a)
    mean_b, std_b = np.mean(scores_b), np.std(scores_b)
    
    # Paired t-test (same CV folds)
    t_stat, p_value = stats.ttest_rel(scores_a, scores_b)
    
    print(f"\n{'Model Comparison':=^50}")
    print(f"{model_a_name}: {mean_a:.4f} ± {std_a:.4f}")
    print(f"{model_b_name}: {mean_b:.4f} ± {std_b:.4f}")
    print(f"Difference: {mean_a - mean_b:+.4f}")
    print(f"P-value: {p_value:.4f}")
    
    if p_value < 0.05:
        winner = model_a_name if mean_a > mean_b else model_b_name
        print(f"Result: {winner} is significantly better (p < 0.05)")
    else:
        print("Result: No significant difference")
    
    return {"p_value": p_value, "significant": p_value < 0.05}

# Example: 5-fold CV scores for two models
scores_a = [0.943, 0.938, 0.951, 0.940, 0.945]
scores_b = [0.941, 0.940, 0.944, 0.939, 0.942]
compare_models(scores_a, scores_b, "ResNet50", "ResNet34")
```

### Ablation Studies

```python
"""What contributes to performance?"""
ablation_results = {
    "full_model": 0.943,
    "no_augmentation": 0.921,       # -0.022 → augmentation helps a lot
    "no_scheduler": 0.935,          # -0.008 → scheduler helps some
    "no_dropout": 0.938,            # -0.005 → dropout helps a little
    "no_pretrained": 0.891,         # -0.052 → pretraining is critical
    "smaller_batch": 0.940,         # -0.003 → batch size barely matters
}

# Sort by impact
sorted_ablations = sorted(
    [(k, v) for k, v in ablation_results.items() if k != "full_model"],
    key=lambda x: x[1]
)

print("\nAblation Study (what hurts most when removed):")
print(f"{'Ablation':<25} {'Accuracy':<10} {'Impact':<10}")
print("-" * 45)
for name, acc in sorted_ablations:
    impact = acc - ablation_results["full_model"]
    print(f"{name:<25} {acc:<10.3f} {impact:<+10.3f}")
```

### Pareto-Optimal Selection (Multi-Objective)

```python
def find_pareto_optimal(experiments):
    """Find Pareto-optimal models (accuracy vs latency)."""
    pareto_front = []
    
    for i, exp in enumerate(experiments):
        dominated = False
        for j, other in enumerate(experiments):
            if i == j:
                continue
            # other dominates exp if better on ALL objectives
            if (other["accuracy"] >= exp["accuracy"] and 
                other["latency_ms"] <= exp["latency_ms"] and
                (other["accuracy"] > exp["accuracy"] or 
                 other["latency_ms"] < exp["latency_ms"])):
                dominated = True
                break
        if not dominated:
            pareto_front.append(exp)
    
    return pareto_front

experiments = [
    {"name": "ResNet152", "accuracy": 0.961, "latency_ms": 45},
    {"name": "ResNet50", "accuracy": 0.943, "latency_ms": 22},
    {"name": "MobileNet", "accuracy": 0.912, "latency_ms": 5},
    {"name": "EfficientNet-B0", "accuracy": 0.935, "latency_ms": 12},
    {"name": "ResNet18", "accuracy": 0.928, "latency_ms": 8},
]

pareto = find_pareto_optimal(experiments)
print("Pareto-optimal models (no model is better on BOTH metrics):")
for p in pareto:
    print(f"  {p['name']}: acc={p['accuracy']:.3f}, latency={p['latency_ms']}ms")
```

---

## 9. Reproducibility Checklist

### The Complete Checklist

```
□ Fixed all random seeds
    □ Python: random.seed(42)
    □ NumPy: np.random.seed(42)
    □ PyTorch: torch.manual_seed(42)
    □ CUDA: torch.cuda.manual_seed_all(42)
    □ Set PYTHONHASHSEED=42
    □ torch.backends.cudnn.deterministic = True
    □ torch.backends.cudnn.benchmark = False

□ Recorded exact package versions
    □ pip freeze > requirements.txt
    □ OR conda env export > environment.yml
    □ OR Dockerfile committed

□ Recorded git commit hash
    □ Logged automatically at experiment start
    □ No uncommitted changes (git status clean)

□ Data is versioned
    □ DVC tracks data files
    □ OR data hash recorded in experiment log
    □ OR data stored in versioned bucket

□ Config file captures ALL parameters
    □ No hardcoded values in training script
    □ Everything comes from config
    □ Config is saved with results

□ Training script can re-run from config alone
    □ python train.py --config experiments/exp_001/config.yaml
    □ Produces same results (within floating point tolerance)

□ Results match when re-run
    □ Verified on same hardware → exact match
    □ Verified on different hardware → within ±0.001
    □ Documented any non-determinism sources

□ Docker/conda environment is captured
    □ Can spin up identical environment from scratch
    □ Tested on clean machine
```

### Setting All Seeds

```python
import random
import os
import numpy as np
import torch

def set_all_seeds(seed=42):
    """Set ALL random seeds for reproducibility."""
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)  # multi-GPU
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    
    # For DataLoader workers
    def seed_worker(worker_id):
        worker_seed = torch.initial_seed() % 2**32
        np.random.seed(worker_seed)
        random.seed(worker_seed)
    
    return seed_worker

# Usage
seed_worker = set_all_seeds(42)
train_loader = DataLoader(
    dataset, 
    batch_size=32,
    worker_init_fn=seed_worker,
    generator=torch.Generator().manual_seed(42),
)
```

---

## 10. From Experiment to Production

### Promotion Pipeline

```
Development → Staging → Production
     │            │          │
     │            │          └── Monitored, A/B tested
     │            └── Shadow mode, validated on prod data
     └── Tracked experiments, best model selected
```

### Model Promotion Criteria

```python
promotion_criteria = {
    "minimum_accuracy": 0.93,
    "maximum_latency_p99_ms": 50,
    "minimum_test_samples": 10000,
    "reproducibility_verified": True,
    "statistical_significance_vs_current": 0.05,
    "no_regression_on_slices": True,  # No subgroup gets worse
    "reviewed_by": "senior_engineer",
}
```

### A/B Testing in Production

```
Traffic Split:
  - 95% → Current model (control)
  - 5%  → New model (treatment)

Monitor for 1-2 weeks:
  - Primary metric (accuracy, CTR, revenue)
  - Latency (p50, p95, p99)
  - Error rate
  - Subgroup performance (fairness)

Decision:
  - Treatment significantly better → Ramp to 100%
  - No significant difference → Keep current (simpler)
  - Treatment worse on any metric → Rollback
```

### When to Retrain

```
Trigger retraining when:
├── Scheduled: Every 2 weeks / monthly
├── Performance drop: Accuracy below threshold for 3 days
├── Data drift: Feature distributions shift significantly
├── New data: Enough new labeled data accumulated
└── Business change: New categories, new requirements

Monitor continuously:
├── Prediction confidence distribution
├── Feature value distributions (vs training)
├── Actual vs predicted (when labels arrive)
├── Latency and throughput
└── Business metrics (revenue, engagement)
```

---

## Quick Reference: Experiment Management Commands

```bash
# MLflow
mlflow ui                                    # Launch UI
mlflow run . -P lr=0.01 -P epochs=50        # Run with params
mlflow models serve -m models:/my-model/1   # Serve model

# W&B
wandb init                                   # Initialize project
wandb sweep sweep.yaml                       # Create sweep
wandb agent <sweep-id>                       # Run sweep agent
wandb sync --sync-all                        # Sync offline runs

# DVC (data versioning)
dvc init                                     # Initialize
dvc add data/training.csv                    # Track data file
dvc push                                     # Push to remote storage
dvc pull                                     # Pull data

# Optuna
optuna-dashboard sqlite:///optuna.db         # Launch dashboard
```

---

## Summary: The Professional Workflow

```
1. BEFORE training:
   - Create config file with ALL parameters
   - Ensure git is clean (commit or stash)
   - Set all random seeds
   - Verify data version

2. DURING training:
   - Log metrics every epoch
   - Save best checkpoint
   - Log to tracking tool (MLflow/W&B/JSON)

3. AFTER training:
   - Save final results summary
   - Generate plots and artifacts
   - Compare against baselines
   - Document what you learned

4. BEFORE claiming "this model is better":
   - Run multiple seeds (≥3, ideally 5)
   - Statistical significance test
   - Check for regressions on subgroups
   - Verify reproducibility
```

The investment in experiment tracking pays for itself after about 10 experiments. After 100 experiments, you'll wonder how anyone works without it.
