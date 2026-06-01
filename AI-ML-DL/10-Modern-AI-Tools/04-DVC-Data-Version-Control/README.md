# DVC - Data Version Control

## Why Version Data?

The ML reproducibility crisis: code is versioned (Git), but data and models aren't. You can't `git checkout` a 50GB dataset. DVC solves this.

```
┌─────────────────────────────────────────────────────────┐
│              DVC + Git Workflow                           │
├─────────────────────────────────────────────────────────┤
│  Git tracks:          │  DVC tracks:                     │
│  ├── Code             │  ├── Large datasets              │
│  ├── dvc.yaml         │  ├── Model weights               │
│  ├── dvc.lock         │  ├── Intermediate artifacts      │
│  ├── .dvc files       │  └── (stored in remote storage)  │
│  └── params.yaml      │                                  │
└─────────────────────────────────────────────────────────┘
```

## Setup

```bash
pip install dvc dvc-s3 dvc-gs  # Install with remote storage support
cd my-ml-project
git init
dvc init

# Configure remote storage
dvc remote add -d myremote s3://my-bucket/dvc-store
# Or: dvc remote add -d myremote gs://my-bucket/dvc-store
# Or: dvc remote add -d myremote azure://my-container/dvc-store
# Or: dvc remote add -d myremote /shared/nfs/dvc-store
```

---

## Basic Workflow: Tracking Large Files

```bash
# Track a large dataset
dvc add data/training-images/
# Creates: data/training-images.dvc (pointer file - tracked by Git)
# Adds data/training-images/ to .gitignore

# Commit the pointer
git add data/training-images.dvc data/.gitignore
git commit -m "Add training dataset v1"

# Push data to remote storage
dvc push

# On another machine (or later):
git clone <repo>
dvc pull  # Downloads data from remote

# Update data and version it
# ... modify data/training-images/ ...
dvc add data/training-images/
git add data/training-images.dvc
git commit -m "Update training data v2"
dvc push

# Go back to previous data version
git checkout HEAD~1 -- data/training-images.dvc
dvc checkout  # Restores previous data version
```

---

## DVC Pipelines

```yaml
# dvc.yaml - Define your ML pipeline
stages:
  prepare:
    cmd: python src/prepare.py
    deps:
      - src/prepare.py
      - data/raw/
    params:
      - prepare.split_ratio
      - prepare.seed
    outs:
      - data/prepared/

  featurize:
    cmd: python src/featurize.py
    deps:
      - src/featurize.py
      - data/prepared/
    params:
      - featurize.max_features
      - featurize.ngrams
    outs:
      - data/features/

  train:
    cmd: python src/train.py
    deps:
      - src/train.py
      - data/features/
    params:
      - train.learning_rate
      - train.epochs
      - train.batch_size
    outs:
      - models/model.pkl
    metrics:
      - metrics/train.json:
          cache: false
    plots:
      - plots/loss.csv:
          x: epoch
          y: loss

  evaluate:
    cmd: python src/evaluate.py
    deps:
      - src/evaluate.py
      - models/model.pkl
      - data/features/
    metrics:
      - metrics/eval.json:
          cache: false
    plots:
      - plots/confusion_matrix.csv:
          template: confusion
          x: predicted
          y: actual
```

```yaml
# params.yaml - All hyperparameters in one place
prepare:
  split_ratio: 0.2
  seed: 42

featurize:
  max_features: 5000
  ngrams: 2

train:
  learning_rate: 0.001
  epochs: 10
  batch_size: 64
```

```bash
# Run the pipeline
dvc repro  # Runs only stages with changed dependencies

# Run specific stage
dvc repro train

# Visualize pipeline DAG
dvc dag
# prepare → featurize → train → evaluate
```

---

## Experiment Tracking with DVC

```bash
# Run experiment with modified params
dvc exp run --set-param train.learning_rate=0.01

# Run multiple experiments
dvc exp run --set-param train.learning_rate=0.001
dvc exp run --set-param train.learning_rate=0.01
dvc exp run --set-param train.learning_rate=0.1

# Compare experiments
dvc exp show
# ┌──────────────────┬───────────┬──────────────────┬──────────┐
# │ Experiment       │ accuracy  │ learning_rate    │ epochs   │
# ├──────────────────┼───────────┼──────────────────┼──────────┤
# │ workspace        │ 0.92      │ 0.001            │ 10       │
# │ exp-abc123       │ 0.89      │ 0.01             │ 10       │
# │ exp-def456       │ 0.78      │ 0.1              │ 10       │
# └──────────────────┴───────────┴──────────────────┴──────────┘

# Compare specific metrics
dvc metrics diff

# Apply best experiment to workspace
dvc exp apply exp-abc123

# Push experiment to Git branch
dvc exp push origin exp-abc123

# Grid search
dvc exp run --queue --set-param train.learning_rate=0.001
dvc exp run --queue --set-param train.learning_rate=0.01
dvc exp run --queue --set-param train.learning_rate=0.1
dvc exp run --run-all --parallel 3  # Run queued experiments in parallel
```

---

## Metrics and Plots

```python
# src/train.py
import json
import csv

# Log metrics
metrics = {"accuracy": 0.92, "f1": 0.89, "loss": 0.23}
with open("metrics/train.json", "w") as f:
    json.dump(metrics, f)

# Log plots (training curves)
with open("plots/loss.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["epoch", "loss", "val_loss"])
    writer.writeheader()
    for epoch, (l, vl) in enumerate(zip(losses, val_losses)):
        writer.writerow({"epoch": epoch, "loss": l, "val_loss": vl})
```

```bash
# View metrics
dvc metrics show
dvc metrics diff  # Compare with previous commit

# Generate plots
dvc plots show  # Opens HTML plots in browser
dvc plots diff   # Compare plots across revisions
```

---

## CML (Continuous Machine Learning)

```yaml
# .github/workflows/cml.yaml
name: CML
on: [push]
jobs:
  train-and-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: iterative/setup-cml@v2
      - uses: iterative/setup-dvc@v1

      - name: Train
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          dvc pull
          dvc repro
          dvc push

      - name: Report
        env:
          REPO_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          echo "## Metrics" >> report.md
          dvc metrics diff --md >> report.md
          echo "## Plots" >> report.md
          dvc plots diff --target plots/loss.csv | cml-publish --md >> report.md
          cml comment create report.md
```

---

## Data Registries

```bash
# Create a central data registry (separate repo)
mkdir data-registry && cd data-registry
git init && dvc init
dvc remote add -d storage s3://company-data/registry

# Add datasets
dvc add datasets/imagenet-subset/
dvc add datasets/company-nlp-corpus/
git add . && git commit -m "Add datasets"
dvc push

# Use in project (import from registry)
cd my-project
dvc import https://github.com/company/data-registry datasets/imagenet-subset
# Creates .dvc file pointing to registry - always gets latest version

# Pin specific version
dvc import https://github.com/company/data-registry datasets/imagenet-subset --rev v1.0
```

---

## Complete Workflow Example

```bash
# 1. Initialize project
mkdir ml-project && cd ml-project
git init && dvc init

# 2. Configure remote
dvc remote add -d storage s3://my-bucket/ml-project

# 3. Add data
dvc add data/raw/dataset.csv
git add data/raw/dataset.csv.dvc data/raw/.gitignore
git commit -m "Add raw dataset"
dvc push

# 4. Create pipeline (dvc.yaml + params.yaml as shown above)
git add dvc.yaml params.yaml src/
git commit -m "Add ML pipeline"

# 5. Run pipeline
dvc repro
git add dvc.lock metrics/ plots/
git commit -m "Run baseline experiment"
dvc push

# 6. Iterate
dvc exp run --set-param train.learning_rate=0.005
dvc exp show
dvc exp apply <best-experiment>
git add .
git commit -m "Best experiment: lr=0.005, acc=0.95"
dvc push
```

---

## Comparison with Alternatives

| Feature | DVC | LakeFS | Delta Lake | Git LFS |
|---------|-----|--------|------------|---------|
| **Approach** | Git-like CLI | Git-like server | Table format | Git extension |
| **Pipeline** | Yes (dvc.yaml) | No | No | No |
| **Experiments** | Yes | No | No | No |
| **Branching data** | Via Git + DVC | Native branches | Time travel | Via Git |
| **Storage** | Any (S3/GCS/etc) | S3-compatible | Object store | Git server |
| **Scale** | Any size | PB-scale | PB-scale | Limited |
| **Best for** | ML projects | Data lakes | Analytics/Spark | Small binary files |

---

## Common Pitfalls

1. **Not running `dvc push`**: Data stays local - teammates can't pull
2. **Editing tracked files directly**: Always `dvc add` after modification
3. **Forgetting `dvc checkout`**: After `git checkout`, run `dvc checkout` to sync data
4. **Large `.dvc` files in Git**: Don't track the data directory AND the .dvc file
5. **Not using `params.yaml`**: Hardcoded params break experiment tracking

## Best Practices

- Keep `params.yaml` as single source of truth for hyperparameters
- Use `dvc repro` instead of running scripts manually
- Set up CML for automated experiment reports on PRs
- Use data registries for shared datasets across projects
- Pin DVC version in `requirements.txt` for reproducibility
- Use `dvc plots` for visual experiment comparison
