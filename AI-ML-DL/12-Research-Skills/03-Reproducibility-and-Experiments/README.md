# Reproducibility and Experiments

## The Reproducibility Crisis in ML

Machine learning faces a significant reproducibility problem:

- **Only ~50%** of ML papers can be reproduced even with original code
- Small implementation details (not mentioned in papers) dramatically affect results
- Hardware differences cause non-deterministic behavior
- Cherry-picking of results is pervasive

### Why Reproducibility Matters

1. **Scientific validity** - Results that can't be reproduced may be artifacts
2. **Engineering confidence** - Production systems need predictable behavior
3. **Collaboration** - Teams need to build on each other's work
4. **Debugging** - Non-reproducible training makes debugging impossible
5. **Compliance** - Regulated industries require audit trails

---

## Random Seeds and Determinism

### Sources of Non-Determinism

```python
# Common sources of randomness in ML
sources = {
    "weight_initialization": "Random starting weights",
    "data_shuffling": "Order of training examples",
    "dropout": "Which neurons are dropped",
    "data_augmentation": "Random transforms applied",
    "cuda_operations": "Non-deterministic GPU kernels",
    "parallel_reduction": "Floating point ordering in multi-threaded ops",
    "hash_randomization": "Python dict ordering (PYTHONHASHSEED)",
}
```

### Setting Seeds Properly

```python
import random
import numpy as np
import torch

def set_seed(seed: int = 42):
    """Set all random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    
    # For full determinism (may reduce performance)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    
    # Python hash seed
    import os
    os.environ['PYTHONHASHSEED'] = str(seed)

# TensorFlow equivalent
import tensorflow as tf
tf.random.set_seed(42)
```

### Important Caveats

- **Deterministic != Reproducible across hardware**: Same seed on different GPUs may give different results
- **Performance trade-off**: Full determinism disables cuDNN autotuning (10-20% slower)
- **Multi-GPU**: Additional non-determinism from communication patterns
- **Library versions**: Different PyTorch versions may initialize differently

### Best Practice: Report Variance

```python
# Run experiment with multiple seeds and report mean ± std
results = []
for seed in [42, 123, 456, 789, 1024]:
    set_seed(seed)
    result = train_and_evaluate(config)
    results.append(result)

print(f"Accuracy: {np.mean(results):.2f} ± {np.std(results):.2f}")
```

---

## Hardware-Dependent Results

### Why Hardware Matters

| Factor | Impact |
|--------|--------|
| GPU architecture | Different numerical precision implementations |
| Number of GPUs | Different batch sizes, gradient averaging |
| CPU vs GPU | Different floating-point behavior |
| CUDA version | Kernel implementation changes |
| Memory | May force different batch sizes |

### Mitigation Strategies

1. **Document hardware exactly**: GPU model, count, CUDA version, driver version
2. **Use containers**: Docker ensures consistent software environment
3. **Report hardware**: Include in paper/report
4. **Test on multiple hardware**: Ensure results are robust

---

## Experiment Management

### What to Track

Every experiment should record:

```yaml
experiment:
  # Code
  git_commit: "abc123"
  git_branch: "feature/new-loss"
  git_diff: "..." # Uncommitted changes
  
  # Data
  dataset_version: "v2.3"
  dataset_hash: "sha256:..."
  preprocessing: "tokenizer_v2"
  train_split_size: 80000
  val_split_size: 10000
  test_split_size: 10000
  
  # Environment
  python_version: "3.10.12"
  pytorch_version: "2.1.0"
  cuda_version: "12.1"
  gpu: "A100-80GB"
  num_gpus: 4
  docker_image: "training:v1.2"
  
  # Hyperparameters
  learning_rate: 0.0001
  batch_size: 256
  epochs: 100
  optimizer: "adamw"
  weight_decay: 0.01
  scheduler: "cosine"
  warmup_steps: 1000
  seed: 42
  
  # Results
  best_val_loss: 0.234
  test_accuracy: 0.891
  training_time_hours: 4.5
  
  # Artifacts
  model_checkpoint: "s3://models/exp_001/best.pt"
  training_logs: "s3://logs/exp_001/"
```

### Environment Management

#### Docker (Recommended for Production)

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

# Pin versions in requirements.txt
# numpy==1.24.3
# scikit-learn==1.3.0
# transformers==4.35.0
```

#### Conda (Good for Research)

```yaml
# environment.yml
name: ml-research
channels:
  - pytorch
  - nvidia
  - conda-forge
dependencies:
  - python=3.10.12
  - pytorch=2.1.0
  - torchvision=0.16.0
  - cudatoolkit=12.1
  - numpy=1.24.3
  - pip:
    - transformers==4.35.0
    - wandb==0.16.0
```

---

## Statistical Significance in ML

### The Problem

- ML results are random variables (depend on seed, data split, initialization)
- A 0.5% improvement may be noise, not real progress
- Most papers don't report confidence intervals

### Methods for Statistical Testing

#### Bootstrap Confidence Intervals

```python
from scipy import stats
import numpy as np

def bootstrap_ci(scores, n_bootstrap=10000, ci=0.95):
    """Compute bootstrap confidence interval for mean."""
    bootstrapped_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(scores, size=len(scores), replace=True)
        bootstrapped_means.append(np.mean(sample))
    
    lower = np.percentile(bootstrapped_means, (1-ci)/2 * 100)
    upper = np.percentile(bootstrapped_means, (1+ci)/2 * 100)
    return lower, upper

# Example
model_a_scores = [0.85, 0.87, 0.84, 0.86, 0.88]
model_b_scores = [0.86, 0.88, 0.87, 0.89, 0.87]

ci_a = bootstrap_ci(model_a_scores)
ci_b = bootstrap_ci(model_b_scores)
print(f"Model A: {np.mean(model_a_scores):.3f} [{ci_a[0]:.3f}, {ci_a[1]:.3f}]")
print(f"Model B: {np.mean(model_b_scores):.3f} [{ci_b[0]:.3f}, {ci_b[1]:.3f}]")
```

#### Paired Tests (When Comparing Models)

```python
from scipy.stats import wilcoxon, ttest_rel

# Paired samples: same test examples, different models
model_a_per_example = [...]  # Score per test example
model_b_per_example = [...]

# Wilcoxon signed-rank test (non-parametric, preferred)
stat, p_value = wilcoxon(model_a_per_example, model_b_per_example)
print(f"p-value: {p_value:.4f}")
if p_value < 0.05:
    print("Difference is statistically significant")
```

### How Many Seeds?

| Scenario | Minimum Seeds | Recommended |
|----------|--------------|-------------|
| Quick exploration | 1 | 3 |
| Paper submission | 3 | 5 |
| Production decision | 5 | 10 |
| High-stakes deployment | 10 | 20+ |

---

## Ablation Studies

### What is an Ablation?

Systematically removing or modifying components to understand their contribution.

### Design Principles

```
Full Model:          Component A + B + C + D → 92.3%
Remove A:            Component B + C + D     → 91.1%  (A contributes +1.2%)
Remove B:            Component A + C + D     → 89.5%  (B contributes +2.8%)
Remove C:            Component A + B + D     → 91.9%  (C contributes +0.4%)
Remove D:            Component A + B + C     → 90.7%  (D contributes +1.6%)
Baseline (none):     No components           → 85.2%

Note: Contributions may not be additive due to interactions!
```

### Ablation Table Template

| Model Variant | Accuracy | Δ from Full | Notes |
|---------------|----------|-------------|-------|
| Full model | 92.3 | - | All components |
| - attention pooling | 91.1 | -1.2 | Use mean pooling instead |
| - data augmentation | 89.5 | -2.8 | Most impactful component |
| - label smoothing | 91.9 | -0.4 | Minor contribution |
| - learning rate warmup | 90.7 | -1.6 | Important for stability |
| Baseline | 85.2 | -7.1 | Standard architecture |

### Common Ablation Mistakes

1. **Not controlling for compute**: Removing a component makes training faster; is the improvement from the component or from longer effective training?
2. **Confounding variables**: Changing two things at once
3. **Missing error bars**: Is the ablation within noise?

---

## Confidence Intervals and Error Bars

### What to Report

```
GOOD:  "Our model achieves 92.3% ± 0.4% accuracy (mean ± std over 5 seeds)"
GOOD:  "Our model achieves 92.3% [91.8%, 92.7%] (95% CI, bootstrap)"
BAD:   "Our model achieves 92.3% accuracy"
BAD:   "Our model achieves 92.3% (best of 5 runs)"
```

### Visualization

```python
import matplotlib.pyplot as plt
import numpy as np

models = ['Baseline', 'Model A', 'Model B', 'Our Model']
means = [85.2, 89.1, 91.5, 92.3]
stds = [0.8, 0.6, 0.5, 0.4]

plt.figure(figsize=(8, 5))
plt.bar(models, means, yerr=stds, capsize=5, color=['gray', 'blue', 'blue', 'green'])
plt.ylabel('Accuracy (%)')
plt.title('Model Comparison with Error Bars')
plt.ylim(80, 95)
plt.tight_layout()
plt.savefig('comparison.png', dpi=150)
```

---

## Checklist for Reproducible Research

### Before Starting

```markdown
□ Version control setup (git)
□ Environment specification (Docker/conda)
□ Data versioning (DVC, git-lfs, or manual hashing)
□ Experiment tracker configured (W&B, MLflow)
□ Random seed strategy defined
□ Compute budget estimated
```

### During Experiments

```markdown
□ All hyperparameters logged automatically
□ Code version tracked with each run
□ Data splits fixed and documented
□ Intermediate checkpoints saved
□ Training curves logged (loss, metrics per epoch)
□ Hardware and software versions recorded
□ Wall-clock time recorded
```

### Before Publishing/Reporting

```markdown
□ Results reported with error bars (multiple seeds)
□ Ablation study completed
□ Statistical significance tested
□ Negative results documented
□ Compute cost reported (GPU hours, cost)
□ Code cleaned and documented
□ README with reproduction instructions
□ Requirements/environment files included
□ Data access instructions provided
□ Pre-trained model checkpoints available
```

---

## Tools for Experiment Management

### MLflow

```python
import mlflow

mlflow.set_experiment("my_project")

with mlflow.start_run(run_name="experiment_001"):
    # Log parameters
    mlflow.log_params({
        "learning_rate": 0.001,
        "batch_size": 64,
        "model": "resnet50",
    })
    
    # Train...
    for epoch in range(100):
        train_loss = train_one_epoch()
        val_acc = evaluate()
        mlflow.log_metrics({
            "train_loss": train_loss,
            "val_accuracy": val_acc,
        }, step=epoch)
    
    # Log artifacts
    mlflow.log_artifact("model.pt")
    mlflow.log_artifact("config.yaml")
```

### Weights & Biases (W&B)

```python
import wandb

wandb.init(
    project="my_project",
    config={
        "learning_rate": 0.001,
        "batch_size": 64,
        "architecture": "resnet50",
    }
)

for epoch in range(100):
    train_loss = train_one_epoch()
    val_acc = evaluate()
    wandb.log({"train_loss": train_loss, "val_accuracy": val_acc})

wandb.finish()
```

### DVC (Data Version Control)

```bash
# Track large data files
dvc init
dvc add data/training_set.parquet
git add data/training_set.parquet.dvc .gitignore
git commit -m "Add training data v1"

# Reproduce pipeline
dvc repro  # Reruns pipeline if inputs changed
```

### Comparison

| Tool | Best For | Cost | Self-hosted |
|------|----------|------|-------------|
| MLflow | Full lifecycle, enterprise | Free (OSS) | Yes |
| W&B | Experiment tracking, collaboration | Free tier / paid | Cloud + self-host |
| Sacred | Academic research | Free (OSS) | Yes |
| Guild AI | CLI-focused, lightweight | Free (OSS) | Yes |
| DVC | Data versioning, pipelines | Free (OSS) | Yes |
| Neptune | Team collaboration | Paid | Cloud |
| ClearML | End-to-end MLOps | Free tier / paid | Yes |

---

## Summary

Reproducibility isn't just academic virtue - it's engineering discipline. A result you can't reproduce is a result you can't deploy with confidence.

**Key principles**:
1. Track everything automatically (don't rely on memory)
2. Report variance, not just best runs
3. Use containers for environment consistency
4. Version data alongside code
5. Design ablations to isolate contributions
6. Apply statistical rigor before claiming improvements
