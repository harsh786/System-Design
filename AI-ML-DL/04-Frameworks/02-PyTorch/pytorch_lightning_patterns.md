# PyTorch Lightning Patterns

## Table of Contents
- [Why Lightning](#why-lightning)
- [LightningModule Structure](#lightningmodule-structure)
- [LightningDataModule](#lightningdatamodule)
- [Callbacks](#callbacks)
- [Logging](#logging)
- [Multi-GPU Training](#multi-gpu-training)
- [Profiling and Reproducibility](#profiling-and-reproducibility)
- [Hyperparameter Tuning with Optuna](#hyperparameter-tuning-with-optuna)
- [Production Export](#production-export)
- [Complete Example](#complete-example)
- [Migration Guide from Raw PyTorch](#migration-guide-from-raw-pytorch)

---

## Why Lightning

PyTorch Lightning separates **research code** (model, loss, optimizer) from **engineering code** (training loop, distributed, mixed precision, logging, checkpointing):

```
Raw PyTorch:
┌──────────────────────────────────────────────────┐
│  Research Code + Engineering Code                 │
│  (tangled together, hard to maintain)            │
│                                                  │
│  - Model definition                              │
│  - Training loop boilerplate                     │
│  - Distributed setup                             │
│  - Mixed precision handling                      │
│  - Checkpointing logic                           │
│  - Logging integration                           │
│  - GPU/CPU device management                     │
│  - Gradient accumulation                         │
└──────────────────────────────────────────────────┘

Lightning:
┌──────────────────────┐  ┌────────────────────────┐
│  LightningModule     │  │  Trainer               │
│  (YOUR code)         │  │  (Lightning handles)   │
│                      │  │                        │
│  - Model             │  │  - Training loop       │
│  - Forward           │  │  - Distributed         │
│  - Loss computation  │  │  - Mixed precision     │
│  - Optimizer config  │  │  - Checkpointing       │
│                      │  │  - Logging             │
└──────────────────────┘  │  - Device management   │
                          └────────────────────────┘
```

**Key benefits:**
1. No `.to(device)` calls — Lightning handles device placement
2. Multi-GPU with zero code change — just change Trainer flag
3. Built-in best practices (gradient clipping, early stopping, etc.)
4. Reproducibility guarantees
5. Same code runs on CPU, GPU, TPU, IPU

---

## LightningModule Structure

```python
import pytorch_lightning as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchmetrics import Accuracy

class ImageClassifier(pl.LightningModule):
    """
    LightningModule organizes code into these key methods:
    - __init__: Define model architecture and metrics
    - forward: Inference only (used for predict/export)
    - training_step: What happens for each training batch
    - validation_step: What happens for each validation batch
    - configure_optimizers: Define optimizer(s) and scheduler(s)
    """
    
    def __init__(self, num_classes=10, learning_rate=1e-3, weight_decay=1e-4):
        super().__init__()
        
        # save_hyperparameters() stores all __init__ args in self.hparams
        # and logs them automatically. Enables easy checkpoint restoration.
        self.save_hyperparameters()
        
        # Model architecture
        self.model = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Flatten(),
            nn.Linear(64 * 7 * 7, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )
        
        # Metrics (torchmetrics handles distributed aggregation automatically)
        self.train_acc = Accuracy(task="multiclass", num_classes=num_classes)
        self.val_acc = Accuracy(task="multiclass", num_classes=num_classes)
        self.test_acc = Accuracy(task="multiclass", num_classes=num_classes)
    
    def forward(self, x):
        """
        Forward is for INFERENCE only.
        Don't put loss computation here.
        Used when you call model(x) or for export.
        """
        return self.model(x)
    
    def training_step(self, batch, batch_idx):
        """
        Called for each training batch.
        Must return loss (or dict with 'loss' key).
        Lightning handles backward(), optimizer.step(), zero_grad().
        """
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        
        # Logging (automatically aggregated across batches and GPUs)
        preds = logits.argmax(dim=1)
        self.train_acc(preds, y)
        self.log('train_loss', loss, prog_bar=True)
        self.log('train_acc', self.train_acc, on_step=False, on_epoch=True, prog_bar=True)
        
        return loss
    
    def validation_step(self, batch, batch_idx):
        """Called for each validation batch. No need to handle torch.no_grad() — Lightning does it."""
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        
        preds = logits.argmax(dim=1)
        self.val_acc(preds, y)
        self.log('val_loss', loss, prog_bar=True)
        self.log('val_acc', self.val_acc, on_step=False, on_epoch=True, prog_bar=True)
    
    def test_step(self, batch, batch_idx):
        """Called during trainer.test()."""
        x, y = batch
        logits = self(x)
        preds = logits.argmax(dim=1)
        self.test_acc(preds, y)
        self.log('test_acc', self.test_acc, on_step=False, on_epoch=True)
    
    def configure_optimizers(self):
        """
        Define optimizer and LR scheduler.
        Lightning supports complex scheduling configs.
        """
        optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.hparams.learning_rate,
            weight_decay=self.hparams.weight_decay,
        )
        
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=self.trainer.max_epochs
        )
        
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "interval": "epoch",  # "step" for per-batch scheduling
                "frequency": 1,
                "monitor": "val_loss",  # For ReduceLROnPlateau
            },
        }
```

---

## LightningDataModule

Encapsulates all data-related logic in one reusable class:

```python
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader, random_split
import torchvision
import torchvision.transforms as transforms

class FashionMNISTDataModule(LightningDataModule):
    """
    Encapsulates:
    - Download/preprocessing
    - Train/val/test splits
    - DataLoader configuration
    
    Benefits:
    - Reusable across experiments
    - Consistent splits
    - Easy to share with team
    """
    
    def __init__(self, data_dir="./data", batch_size=64, num_workers=4):
        super().__init__()
        self.save_hyperparameters()
        self.data_dir = data_dir
        self.batch_size = batch_size
        self.num_workers = num_workers
        
        self.transform_train = transforms.Compose([
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ToTensor(),
            transforms.Normalize((0.2860,), (0.3530,)),
        ])
        self.transform_test = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.2860,), (0.3530,)),
        ])
    
    def prepare_data(self):
        """
        Download data. Called only on ONE process in distributed.
        Do NOT assign state here (no self.x = ...).
        """
        torchvision.datasets.FashionMNIST(self.data_dir, train=True, download=True)
        torchvision.datasets.FashionMNIST(self.data_dir, train=False, download=True)
    
    def setup(self, stage=None):
        """
        Assign datasets. Called on EVERY process.
        stage: 'fit', 'validate', 'test', or 'predict'
        """
        if stage == "fit" or stage is None:
            full_train = torchvision.datasets.FashionMNIST(
                self.data_dir, train=True, transform=self.transform_train
            )
            self.train_dataset, self.val_dataset = random_split(
                full_train, [54000, 6000],
                generator=torch.Generator().manual_seed(42)
            )
        
        if stage == "test" or stage is None:
            self.test_dataset = torchvision.datasets.FashionMNIST(
                self.data_dir, train=False, transform=self.transform_test
            )
    
    def train_dataloader(self):
        return DataLoader(
            self.train_dataset, batch_size=self.batch_size,
            shuffle=True, num_workers=self.num_workers, pin_memory=True
        )
    
    def val_dataloader(self):
        return DataLoader(
            self.val_dataset, batch_size=self.batch_size * 2,
            shuffle=False, num_workers=self.num_workers, pin_memory=True
        )
    
    def test_dataloader(self):
        return DataLoader(
            self.test_dataset, batch_size=self.batch_size * 2,
            shuffle=False, num_workers=self.num_workers, pin_memory=True
        )
```

---

## Callbacks

### Built-in Callbacks

```python
from pytorch_lightning.callbacks import (
    ModelCheckpoint,
    EarlyStopping,
    LearningRateMonitor,
    RichProgressBar,
    StochasticWeightAveraging,
)

callbacks = [
    # Save best model by validation accuracy
    ModelCheckpoint(
        monitor="val_acc",
        mode="max",
        dirpath="checkpoints/",
        filename="best-{epoch:02d}-{val_acc:.4f}",
        save_top_k=3,       # Keep top 3 models
        save_last=True,     # Always save last checkpoint
    ),
    
    # Stop if val_loss doesn't improve for 5 epochs
    EarlyStopping(
        monitor="val_loss",
        mode="min",
        patience=5,
        verbose=True,
    ),
    
    # Log LR to tensorboard
    LearningRateMonitor(logging_interval="step"),
    
    # Stochastic Weight Averaging (better generalization)
    StochasticWeightAveraging(swa_lrs=1e-4, swa_epoch_start=10),
]
```

### Custom Callbacks

```python
from pytorch_lightning.callbacks import Callback

class GradientNormLogger(Callback):
    """Log gradient norms to detect exploding/vanishing gradients."""
    
    def on_before_optimizer_step(self, trainer, pl_module, optimizer):
        total_norm = 0.0
        for p in pl_module.parameters():
            if p.grad is not None:
                total_norm += p.grad.data.norm(2).item() ** 2
        total_norm = total_norm ** 0.5
        pl_module.log("grad_norm", total_norm)


class FreezeUnfreezeCallback(Callback):
    """Freeze backbone for N epochs, then unfreeze (transfer learning)."""
    
    def __init__(self, unfreeze_epoch=5):
        self.unfreeze_epoch = unfreeze_epoch
    
    def on_train_epoch_start(self, trainer, pl_module):
        if trainer.current_epoch == 0:
            # Freeze backbone
            for param in pl_module.model.backbone.parameters():
                param.requires_grad = False
            print("Backbone frozen")
        
        elif trainer.current_epoch == self.unfreeze_epoch:
            # Unfreeze backbone
            for param in pl_module.model.backbone.parameters():
                param.requires_grad = True
            print("Backbone unfrozen")
```

---

## Logging

```python
from pytorch_lightning.loggers import TensorBoardLogger, CSVLogger, WandbLogger

# Multiple loggers simultaneously
trainer = pl.Trainer(
    logger=[
        TensorBoardLogger("logs/", name="experiment1"),
        CSVLogger("logs/", name="csv_logs"),
        # WandbLogger(project="my-project", name="run-1"),  # Weights & Biases
    ],
)

# Inside LightningModule, log anything:
class MyModel(pl.LightningModule):
    def training_step(self, batch, batch_idx):
        # Scalars
        self.log("train_loss", loss)
        
        # Multiple metrics at once
        self.log_dict({"loss": loss, "acc": acc}, prog_bar=True)
        
        # Images, histograms (via tensorboard logger)
        if batch_idx == 0:
            tensorboard = self.logger.experiment
            tensorboard.add_images("input_images", x[:8], self.global_step)
            tensorboard.add_histogram("fc_weights", self.fc.weight, self.global_step)
        
        return loss
```

---

## Multi-GPU Training

The key advantage — zero code change to go from 1 GPU to N GPUs/nodes:

```python
# Single GPU
trainer = pl.Trainer(accelerator="gpu", devices=1)

# Multi-GPU (DDP - recommended)
trainer = pl.Trainer(accelerator="gpu", devices=4, strategy="ddp")

# Multi-node
trainer = pl.Trainer(
    accelerator="gpu",
    devices=4,
    num_nodes=2,
    strategy="ddp",
)

# FSDP for very large models
trainer = pl.Trainer(
    accelerator="gpu",
    devices=4,
    strategy="fsdp",
    precision="16-mixed",
)

# DeepSpeed integration
trainer = pl.Trainer(
    accelerator="gpu",
    devices=4,
    strategy="deepspeed_stage_2",
    precision="16-mixed",
)
```

**No changes needed in your LightningModule!** Lightning handles:
- Process spawning
- Distributed sampler
- Gradient synchronization
- Metric aggregation across GPUs

---

## Profiling and Reproducibility

### Profiling

```python
from pytorch_lightning.profilers import PyTorchProfiler, SimpleProfiler

# Simple profiler (timing of each hook)
trainer = pl.Trainer(profiler="simple")

# Advanced PyTorch profiler (GPU kernels, memory)
profiler = PyTorchProfiler(
    dirpath="profiler_logs/",
    filename="perf",
    activities=[
        torch.profiler.ProfilerActivity.CPU,
        torch.profiler.ProfilerActivity.CUDA,
    ],
    schedule=torch.profiler.schedule(wait=1, warmup=1, active=3),
    on_trace_ready=torch.profiler.tensorboard_trace_handler("profiler_logs/"),
    record_shapes=True,
    profile_memory=True,
)
trainer = pl.Trainer(profiler=profiler, max_epochs=1)
```

### Reproducibility

```python
import pytorch_lightning as pl

# Seed everything (torch, numpy, python random)
pl.seed_everything(42, workers=True)

trainer = pl.Trainer(
    deterministic=True,  # Force deterministic algorithms (slower but reproducible)
)
```

---

## Hyperparameter Tuning with Optuna

```python
import optuna
from optuna.integration import PyTorchLightningPruningCallback

def objective(trial):
    # Suggest hyperparameters
    lr = trial.suggest_float("lr", 1e-5, 1e-2, log=True)
    weight_decay = trial.suggest_float("weight_decay", 1e-6, 1e-3, log=True)
    dropout = trial.suggest_float("dropout", 0.1, 0.5)
    hidden_dim = trial.suggest_categorical("hidden_dim", [128, 256, 512])
    
    # Create model with suggested params
    model = ImageClassifier(
        learning_rate=lr,
        weight_decay=weight_decay,
        dropout=dropout,
        hidden_dim=hidden_dim,
    )
    
    datamodule = FashionMNISTDataModule(batch_size=64)
    
    # Pruning callback: stop unpromising trials early
    pruning_callback = PyTorchLightningPruningCallback(trial, monitor="val_acc")
    
    trainer = pl.Trainer(
        max_epochs=20,
        accelerator="gpu",
        devices=1,
        callbacks=[pruning_callback],
        enable_progress_bar=False,
        logger=False,  # Disable logging for speed
    )
    
    trainer.fit(model, datamodule=datamodule)
    
    return trainer.callback_metrics["val_acc"].item()

# Run study
study = optuna.create_study(direction="maximize", pruner=optuna.pruners.MedianPruner())
study.optimize(objective, n_trials=50, timeout=3600)

print(f"Best trial: {study.best_trial.params}")
print(f"Best accuracy: {study.best_value:.4f}")
```

---

## Production Export

```python
# Method 1: TorchScript export from Lightning
model = ImageClassifier.load_from_checkpoint("checkpoints/best.ckpt")
model.eval()

script = model.to_torchscript(method="trace", example_inputs=torch.randn(1, 1, 28, 28))
torch.jit.save(script, "production_model.pt")

# Method 2: ONNX export
model.to_onnx(
    "production_model.onnx",
    input_sample=torch.randn(1, 1, 28, 28),
    export_params=True,
    opset_version=11,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
)

# Method 3: Load for inference (stays in PyTorch)
model = ImageClassifier.load_from_checkpoint(
    "checkpoints/best.ckpt",
    map_location="cpu",
)
model.eval()
model.freeze()  # Disables gradient computation permanently

with torch.inference_mode():
    predictions = model(input_batch)
```

---

## Complete Example

Putting it all together:

```python
"""Complete Lightning training script."""
import pytorch_lightning as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping, LearningRateMonitor
from pytorch_lightning.loggers import TensorBoardLogger
from torchmetrics import Accuracy

class LitClassifier(pl.LightningModule):
    def __init__(self, num_classes=10, lr=1e-3):
        super().__init__()
        self.save_hyperparameters()
        
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(4),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )
        
        self.train_acc = Accuracy(task="multiclass", num_classes=num_classes)
        self.val_acc = Accuracy(task="multiclass", num_classes=num_classes)
    
    def forward(self, x):
        return self.classifier(self.features(x))
    
    def training_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        self.train_acc(logits.argmax(1), y)
        self.log_dict({"train_loss": loss, "train_acc": self.train_acc}, prog_bar=True)
        return loss
    
    def validation_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        self.val_acc(logits.argmax(1), y)
        self.log_dict({"val_loss": loss, "val_acc": self.val_acc}, prog_bar=True)
    
    def configure_optimizers(self):
        opt = torch.optim.AdamW(self.parameters(), lr=self.hparams.lr, weight_decay=1e-4)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=self.trainer.max_epochs)
        return [opt], [sch]


def main():
    pl.seed_everything(42)
    
    # Data
    dm = FashionMNISTDataModule(batch_size=128, num_workers=4)
    
    # Model
    model = LitClassifier(num_classes=10, lr=1e-3)
    
    # Trainer
    trainer = pl.Trainer(
        max_epochs=30,
        accelerator="auto",  # Automatically detect GPU/CPU
        devices="auto",
        precision="16-mixed",  # Mixed precision
        gradient_clip_val=1.0,
        accumulate_grad_batches=1,
        callbacks=[
            ModelCheckpoint(monitor="val_acc", mode="max", save_top_k=1),
            EarlyStopping(monitor="val_loss", patience=5),
            LearningRateMonitor(),
        ],
        logger=TensorBoardLogger("lightning_logs/"),
        log_every_n_steps=50,
    )
    
    # Train
    trainer.fit(model, datamodule=dm)
    
    # Test
    trainer.test(model, datamodule=dm, ckpt_path="best")


if __name__ == "__main__":
    main()
```

---

## Migration Guide from Raw PyTorch

### Before (Raw PyTorch)

```python
# ~100 lines of boilerplate
model = Model().to(device)
optimizer = optim.Adam(model.parameters(), lr=1e-3)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10)
scaler = GradScaler()

for epoch in range(num_epochs):
    model.train()
    for batch in train_loader:
        inputs, targets = batch[0].to(device), batch[1].to(device)
        optimizer.zero_grad()
        with autocast():
            outputs = model(inputs)
            loss = criterion(outputs, targets)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
    
    scheduler.step()
    
    model.eval()
    with torch.no_grad():
        for batch in val_loader:
            # ... validation logic ...
            pass
    
    # Manual checkpointing
    if val_acc > best_acc:
        torch.save(model.state_dict(), "best.pt")
        best_acc = val_acc
```

### After (Lightning)

```python
# Model only contains research logic
class LitModel(pl.LightningModule):
    def __init__(self):
        super().__init__()
        self.model = Model()
    
    def training_step(self, batch, batch_idx):
        x, y = batch
        loss = F.cross_entropy(self(x), y)
        self.log("train_loss", loss)
        return loss
    
    def validation_step(self, batch, batch_idx):
        x, y = batch
        loss = F.cross_entropy(self(x), y)
        self.log("val_loss", loss)
    
    def configure_optimizers(self):
        opt = optim.Adam(self.parameters(), lr=1e-3)
        return [opt], [optim.lr_scheduler.StepLR(opt, step_size=10)]

# All engineering handled by Trainer
trainer = pl.Trainer(
    max_epochs=num_epochs,
    precision="16-mixed",              # Replaces manual AMP
    gradient_clip_val=1.0,             # Replaces manual clipping
    callbacks=[ModelCheckpoint(monitor="val_loss")],  # Replaces manual checkpointing
    accelerator="gpu", devices=4,      # Replaces manual DDP setup
)
trainer.fit(LitModel(), train_loader, val_loader)
```

### Migration Checklist

| Raw PyTorch | Lightning Equivalent |
|-------------|---------------------|
| `model.to(device)` | Automatic |
| `optimizer.zero_grad()` | Automatic |
| `loss.backward()` | Automatic |
| `optimizer.step()` | Automatic |
| `torch.no_grad()` for eval | Automatic |
| `model.train()/eval()` | Automatic |
| Manual device placement | Automatic |
| DistributedDataParallel setup | `strategy="ddp"` |
| GradScaler + autocast | `precision="16-mixed"` |
| Manual checkpointing | `ModelCheckpoint` callback |
| Early stopping logic | `EarlyStopping` callback |
| TensorBoard writer | `TensorBoardLogger` |
| Gradient clipping | `gradient_clip_val=1.0` |
| Gradient accumulation | `accumulate_grad_batches=4` |
