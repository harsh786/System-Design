# Weights & Biases (W&B)

## Overview

W&B is the MLOps platform for experiment tracking, hyperparameter optimization, model versioning, and collaboration.

```
┌─────────────────────────────────────────────────────────┐
│                 W&B Platform                              │
├──────────────┬──────────────┬───────────────────────────┤
│ Experiments  │ Sweeps       │ Artifacts                  │
│ (tracking)   │ (HPO)        │ (versioning)              │
├──────────────┼──────────────┼───────────────────────────┤
│ Tables       │ Reports      │ Alerts                    │
│ (data viz)   │ (collab)     │ (monitoring)              │
└──────────────┴──────────────┴───────────────────────────┘
```

## Setup

```bash
pip install wandb
wandb login  # Enter API key from wandb.ai/authorize
```

---

## Basic Experiment Tracking

```python
import wandb
import torch
import torch.nn as nn

# Initialize run
run = wandb.init(
    project="my-project",
    name="experiment-001",
    config={
        "learning_rate": 1e-4,
        "epochs": 10,
        "batch_size": 32,
        "architecture": "ResNet50",
        "dataset": "CIFAR-10",
        "optimizer": "AdamW",
        "weight_decay": 0.01,
    },
    tags=["baseline", "resnet"],
    notes="First baseline experiment with ResNet50",
)

config = wandb.config  # Access config anywhere

# Training loop with logging
model = build_model(config.architecture)
optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

for epoch in range(config.epochs):
    for batch_idx, (data, target) in enumerate(train_loader):
        optimizer.zero_grad()
        output = model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()

        # Log metrics
        wandb.log({
            "train/loss": loss.item(),
            "train/epoch": epoch,
            "train/step": batch_idx + epoch * len(train_loader),
        })

    # Validation
    val_loss, val_acc = evaluate(model, val_loader)
    wandb.log({
        "val/loss": val_loss,
        "val/accuracy": val_acc,
        "epoch": epoch,
    })

    # Log model checkpoint as artifact
    if val_acc > best_acc:
        best_acc = val_acc
        artifact = wandb.Artifact(f"model-best", type="model")
        torch.save(model.state_dict(), "best_model.pt")
        artifact.add_file("best_model.pt")
        run.log_artifact(artifact)

# Log summary metrics
wandb.summary["best_val_accuracy"] = best_acc
wandb.finish()
```

---

## Advanced Logging

```python
# Log images
wandb.log({"examples": [wandb.Image(img, caption=f"Pred: {pred}") for img, pred in zip(images, preds)]})

# Log histograms
wandb.log({"gradients": wandb.Histogram(model.fc.weight.grad.numpy())})

# Log confusion matrix
wandb.log({"conf_mat": wandb.plot.confusion_matrix(
    probs=None, y_true=labels, preds=predictions, class_names=class_names
)})

# Log tables (structured data)
table = wandb.Table(columns=["input", "prediction", "ground_truth", "correct"])
for inp, pred, gt in zip(inputs, predictions, ground_truths):
    table.add_data(inp, pred, gt, pred == gt)
wandb.log({"predictions": table})

# Watch model (log gradients and parameters)
wandb.watch(model, log="all", log_freq=100)

# Log custom charts
data = [[x, y] for x, y in zip(x_values, y_values)]
table = wandb.Table(data=data, columns=["x", "y"])
wandb.log({"custom_chart": wandb.plot.line(table, "x", "y", title="Custom Plot")})
```

---

## Hyperparameter Sweeps

```python
# sweep_config.yaml equivalent in Python
sweep_config = {
    "method": "bayes",  # grid, random, bayes
    "metric": {"name": "val/accuracy", "goal": "maximize"},
    "parameters": {
        "learning_rate": {"distribution": "log_uniform_values", "min": 1e-5, "max": 1e-2},
        "batch_size": {"values": [16, 32, 64, 128]},
        "epochs": {"value": 10},
        "optimizer": {"values": ["adam", "sgd", "adamw"]},
        "dropout": {"distribution": "uniform", "min": 0.1, "max": 0.5},
        "hidden_size": {"values": [128, 256, 512]},
    },
    "early_terminate": {
        "type": "hyperband",
        "min_iter": 3,
        "eta": 2,
    },
}

# Create sweep
sweep_id = wandb.sweep(sweep_config, project="my-project")

# Define training function
def train():
    run = wandb.init()
    config = wandb.config

    model = build_model(hidden_size=config.hidden_size, dropout=config.dropout)
    optimizer = get_optimizer(config.optimizer, model.parameters(), config.learning_rate)

    for epoch in range(config.epochs):
        train_loss = train_epoch(model, optimizer, train_loader)
        val_loss, val_acc = evaluate(model, val_loader)
        wandb.log({"train/loss": train_loss, "val/loss": val_loss, "val/accuracy": val_acc})

    wandb.finish()

# Run sweep agent
wandb.agent(sweep_id, function=train, count=50)  # Run 50 trials
```

---

## Artifacts (Model & Data Versioning)

```python
# Log a dataset artifact
run = wandb.init(project="my-project", job_type="data-prep")
artifact = wandb.Artifact("training-data", type="dataset", description="Cleaned training data v2")
artifact.add_dir("./data/processed/")
artifact.add_file("./data/metadata.json")
run.log_artifact(artifact)

# Use artifact in training
run = wandb.init(project="my-project", job_type="training")
artifact = run.use_artifact("training-data:latest")
data_dir = artifact.download()  # Downloads to local cache

# Model artifact with metadata
model_artifact = wandb.Artifact(
    "trained-model", type="model",
    metadata={"accuracy": 0.95, "architecture": "bert-base", "dataset_version": "v2"},
)
model_artifact.add_file("model.pt")
run.log_artifact(model_artifact)

# Link to model registry
run.link_artifact(model_artifact, "my-team/model-registry/production-classifier")
```

---

## Integration with HuggingFace

```python
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./results",
    report_to="wandb",              # Just add this!
    run_name="bert-finetune-v1",
    # ... other args
)
# W&B automatically logs all metrics, hyperparams, and model
```

## Integration with PyTorch Lightning

```python
from pytorch_lightning.loggers import WandbLogger

wandb_logger = WandbLogger(project="my-project", name="lightning-run")
trainer = pl.Trainer(logger=wandb_logger, max_epochs=10)
trainer.fit(model, datamodule)
```

---

## Alerts

```python
# Set up alerts for training anomalies
if val_loss > 2.0:
    wandb.alert(
        title="High Validation Loss",
        text=f"Val loss is {val_loss:.4f} at epoch {epoch}",
        level=wandb.AlertLevel.WARN,
    )
```

---

## Comparison with Alternatives

| Feature | W&B | MLflow | Neptune | Comet |
|---------|-----|--------|---------|-------|
| **Hosted option** | Yes (free tier) | Self-host or Databricks | Yes | Yes |
| **UI quality** | Excellent | Basic | Good | Good |
| **Sweeps** | Built-in (Bayesian) | Basic | Via Optuna | Built-in |
| **Artifacts** | Excellent | Good | Basic | Basic |
| **Collaboration** | Reports, Teams | Basic | Good | Good |
| **Free tier** | Generous (100GB) | Unlimited (self-host) | Limited | Limited |
| **LLM tracking** | Traces, Prompts | MLflow Tracing | Basic | Good |
| **Best for** | Research teams | MLOps pipelines | Small teams | Quick setup |

---

## Production Monitoring

```python
# Log inference predictions for monitoring
run = wandb.init(project="production-monitoring", job_type="inference")

# Log prediction distribution over time
for batch in production_data_stream:
    predictions = model.predict(batch)
    wandb.log({
        "inference/prediction_distribution": wandb.Histogram(predictions),
        "inference/avg_confidence": predictions.max(axis=1).mean(),
        "inference/batch_size": len(batch),
        "inference/latency_ms": latency,
    })
```

---

## Common Pitfalls

1. **Not using `wandb.finish()`**: Causes data loss in scripts (notebooks auto-finish)
2. **Logging too frequently**: Log every N steps, not every step (slows training)
3. **Not setting `WANDB_MODE=offline`**: For air-gapped environments
4. **Ignoring config**: Always log ALL hyperparameters for reproducibility
5. **Large artifacts without deduplication**: Use references for large datasets

## Best Practices

- Log config at init, metrics during training, summary at end
- Use `wandb.watch(model)` sparingly - it's expensive
- Group related runs with `group` parameter
- Use tags for filtering (e.g., "production", "baseline", "experiment")
- Create Reports for sharing results with stakeholders
- Use Artifacts for full lineage tracking (data → model → deployment)
