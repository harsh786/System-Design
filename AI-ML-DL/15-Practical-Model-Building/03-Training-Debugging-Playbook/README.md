# Training Debugging Playbook

> A decision tree for when things go wrong. Every diagnostic has runnable code.

---

## The Master Debugging Flowchart

```
Model not learning?
├── Loss not decreasing at all
│   ├── Check: Is data loaded correctly? (print a batch, verify labels)
│   ├── Check: Is learning rate too high? (try 10x smaller)
│   ├── Check: Is loss function correct for the task?
│   ├── Check: Are gradients flowing? (print grad norms)
│   └── Check: Is model too simple for the data?
│
├── Loss decreasing but validation not improving
│   ├── → Overfitting!
│   ├── Fix: Add dropout, reduce model size
│   ├── Fix: More data augmentation
│   ├── Fix: Early stopping
│   └── Fix: Regularization (weight decay)
│
├── Loss is NaN or Inf
│   ├── Check: Learning rate too high
│   ├── Check: Division by zero in loss
│   ├── Check: Log of zero or negative
│   └── Check: Gradient explosion → clip gradients
│
├── Training is extremely slow
│   ├── Check: Data loading bottleneck (num_workers)
│   ├── Check: Batch size too small
│   ├── Check: Unnecessary CPU-GPU transfers
│   └── Check: Not using mixed precision
│
└── Good training but bad real-world performance
    ├── Check: Training-serving skew
    ├── Check: Distribution mismatch
    └── Check: Label leakage in training
```

---

## Step 0: Sanity Checks (Run These FIRST)

```python
# 1. Verify data is loaded correctly
batch = next(iter(train_loader))
inputs, labels = batch
print(f"Input shape: {inputs.shape}, dtype: {inputs.dtype}")
print(f"Labels shape: {labels.shape}, unique: {labels.unique()}")
print(f"Input range: [{inputs.min():.3f}, {inputs.max():.3f}]")

# 2. Visualize a sample (images)
import matplotlib.pyplot as plt
img = inputs[0].permute(1, 2, 0).numpy()
# Unnormalize if needed
img = img * np.array([0.229, 0.224, 0.225]) + np.array([0.485, 0.456, 0.406])
plt.imshow(img.clip(0, 1))
plt.title(f"Label: {labels[0].item()}")
plt.savefig('sanity_check.png')

# 3. Overfit on one batch (MUST succeed)
model.train()
for i in range(100):
    optimizer.zero_grad()
    out = model(inputs.cuda())
    loss = criterion(out, labels.cuda())
    loss.backward()
    optimizer.step()
    if i % 10 == 0:
        print(f"Step {i}: loss={loss.item():.4f}")
# If loss doesn't go to ~0, something is fundamentally broken
```

---

## Learning Rate Finder

### Implementation

```python
import torch
import numpy as np
import matplotlib.pyplot as plt

def lr_finder(model, train_loader, criterion, optimizer, start_lr=1e-7, end_lr=10, num_steps=100):
    """Find optimal learning rate by gradually increasing it."""
    lrs, losses = [], []
    lr_mult = (end_lr / start_lr) ** (1 / num_steps)

    # Save model state
    model_state = model.state_dict()
    optimizer_state = optimizer.state_dict()

    # Set initial LR
    for pg in optimizer.param_groups:
        pg['lr'] = start_lr

    model.train()
    smooth_loss = 0
    best_loss = float('inf')

    data_iter = iter(train_loader)
    for step in range(num_steps):
        try:
            inputs, labels = next(data_iter)
        except StopIteration:
            data_iter = iter(train_loader)
            inputs, labels = next(data_iter)

        inputs, labels = inputs.cuda(), labels.cuda()
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        # Smooth loss
        smooth_loss = 0.98 * smooth_loss + 0.02 * loss.item()
        corrected_loss = smooth_loss / (1 - 0.98 ** (step + 1))

        lrs.append(optimizer.param_groups[0]['lr'])
        losses.append(corrected_loss)

        # Stop if loss explodes
        if corrected_loss > 4 * best_loss and step > 10:
            break
        best_loss = min(best_loss, corrected_loss)

        # Increase LR
        for pg in optimizer.param_groups:
            pg['lr'] *= lr_mult

    # Restore model
    model.load_state_dict(model_state)
    optimizer.load_state_dict(optimizer_state)

    # Plot
    plt.figure(figsize=(10, 4))
    plt.semilogx(lrs, losses)
    plt.xlabel('Learning Rate')
    plt.ylabel('Loss')
    plt.title('LR Finder')
    plt.savefig('lr_finder.png')
    plt.show()

    # Suggested LR: where loss is steepest descent (1/10 of min loss point)
    min_idx = np.argmin(losses)
    suggested_lr = lrs[min_idx] / 10
    print(f"Suggested LR: {suggested_lr:.2e}")
    return suggested_lr
```

### How to Read the LR Plot

```
Good plot:
- Loss decreases smoothly then spikes up
- Pick LR at the steepest downward slope (or 1/10 of minimum)

Bad plot (flat then spike):
- Model/data issue, not LR issue
- Try: verify data, check model architecture

Bad plot (immediately spikes):
- Start_lr too high, try start_lr=1e-8
```

---

## Gradient Debugging

### Check Gradient Flow

```python
def plot_grad_flow(model):
    """Plot gradient magnitudes for each layer."""
    layers, avg_grads, max_grads = [], [], []

    for name, param in model.named_parameters():
        if param.requires_grad and param.grad is not None:
            layers.append(name)
            avg_grads.append(param.grad.abs().mean().item())
            max_grads.append(param.grad.abs().max().item())

    plt.figure(figsize=(15, 5))
    plt.bar(range(len(layers)), avg_grads, alpha=0.5, label='avg')
    plt.bar(range(len(layers)), max_grads, alpha=0.5, label='max')
    plt.xticks(range(len(layers)), layers, rotation=90, fontsize=6)
    plt.xlabel('Layers')
    plt.ylabel('Gradient magnitude')
    plt.legend()
    plt.tight_layout()
    plt.savefig('grad_flow.png')

# Usage: call after loss.backward(), before optimizer.step()
loss.backward()
plot_grad_flow(model)
```

### Gradient Norm Monitoring

```python
def get_grad_norm(model):
    """Get total gradient norm."""
    total_norm = 0
    for p in model.parameters():
        if p.grad is not None:
            total_norm += p.grad.data.norm(2).item() ** 2
    return total_norm ** 0.5

# Track during training
grad_norms = []
for batch in train_loader:
    optimizer.zero_grad()
    loss = criterion(model(batch[0].cuda()), batch[1].cuda())
    loss.backward()
    grad_norms.append(get_grad_norm(model))
    optimizer.step()

# Plot — look for spikes (explosion) or flatlines (vanishing)
plt.plot(grad_norms)
plt.ylabel('Gradient Norm')
plt.xlabel('Step')
plt.savefig('grad_norms.png')
```

### Dead Neurons Detection

```python
def check_dead_neurons(model, train_loader, num_batches=10):
    """Check for ReLU layers with neurons that never activate."""
    activations = {}

    def hook_fn(name):
        def hook(module, input, output):
            if name not in activations:
                activations[name] = []
            activations[name].append((output > 0).float().mean(dim=0))
        return hook

    hooks = []
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.ReLU):
            hooks.append(module.register_forward_hook(hook_fn(name)))

    model.eval()
    with torch.no_grad():
        for i, (inputs, _) in enumerate(train_loader):
            if i >= num_batches:
                break
            model(inputs.cuda())

    for h in hooks:
        h.remove()

    for name, acts in activations.items():
        mean_activation = torch.stack(acts).mean(dim=0)
        dead = (mean_activation < 0.01).sum().item()
        total = mean_activation.numel()
        if dead > 0:
            print(f"{name}: {dead}/{total} dead neurons ({100*dead/total:.1f}%)")
```

### Gradient Clipping

```python
# If gradient norms spike, clip them
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
optimizer.step()
```

---

## Overfitting Diagnosis & Solutions

### Diagnosis

```python
# Clear sign: train loss keeps dropping, val loss increases
# Plot both curves:
plt.plot(train_losses, label='train')
plt.plot(val_losses, label='val')
plt.legend()
plt.savefig('loss_curves.png')

# Gap > 0.1 between train and val accuracy = likely overfitting
```

### Solutions Checklist

```python
# 1. Data Augmentation (most effective for images)
train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(0.3, 0.3, 0.3),
    transforms.RandomRotation(15),
    transforms.RandomErasing(p=0.2),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# 2. Dropout
model = nn.Sequential(
    nn.Linear(512, 256),
    nn.ReLU(),
    nn.Dropout(0.5),  # Start with 0.3-0.5
    nn.Linear(256, num_classes),
)

# 3. Weight Decay (L2 regularization)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

# 4. Reduce model capacity
# Use fewer layers, smaller hidden dimensions, smaller pretrained model

# 5. Early stopping (see training loop in Recipe 1)

# 6. Label smoothing
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

# 7. Mixup / CutMix
def mixup_data(x, y, alpha=0.2):
    lam = np.random.beta(alpha, alpha)
    idx = torch.randperm(x.size(0))
    mixed_x = lam * x + (1 - lam) * x[idx]
    return mixed_x, y, y[idx], lam
```

---

## Underfitting Diagnosis & Solutions

### Diagnosis

```python
# Signs: both train AND val loss are high / not decreasing
# Or: can't even overfit a single batch
```

### Solutions

```python
# 1. Increase model capacity
# More layers, wider layers, larger pretrained model

# 2. Train longer
# Increase epochs, reduce LR for more gradual convergence

# 3. Reduce regularization
# Remove dropout, reduce weight_decay, remove augmentation temporarily

# 4. Better features (tabular)
# More feature engineering, polynomial features, interactions

# 5. Check the problem isn't just too hard / noisy
# What's the Bayes error rate? Human-level performance?

# 6. Learning rate too low
# Try 10x higher, or use LR finder
```

---

## Common Bugs: Top 20

### 1. Forgot model.eval() during inference

```python
# BUG: BatchNorm and Dropout behave differently in train vs eval
model.eval()  # ALWAYS before inference
with torch.no_grad():  # saves memory, not strictly needed for correctness
    predictions = model(inputs)
```

### 2. Forgot optimizer.zero_grad()

```python
# BUG: Gradients accumulate across batches!
for batch in loader:
    optimizer.zero_grad()  # MUST be before forward pass
    loss = criterion(model(batch[0]), batch[1])
    loss.backward()
    optimizer.step()
```

### 3. Wrong input dimensions

```python
# PyTorch: (batch, channels, height, width) — channels FIRST
# TensorFlow: (batch, height, width, channels) — channels LAST
# NumPy/PIL images: (height, width, channels)

# Fix: img.permute(2, 0, 1) or img.transpose(2, 0, 1)
```

### 4. Not normalizing inputs same as training

```python
# If you trained with ImageNet normalization, you MUST use it at inference
# mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
```

### 5. Data leakage from preprocessing before split

```python
# BUG: fitting scaler on ALL data before splitting
# scaler.fit(X_all)  ← WRONG

# FIX: fit on train only
scaler.fit(X_train)
X_train = scaler.transform(X_train)
X_val = scaler.transform(X_val)
```

### 6. Using accuracy for imbalanced datasets

```python
# 95% class A, 5% class B → predicting all A gives 95% accuracy!
# Use: F1, precision, recall, AUC-ROC, balanced accuracy
from sklearn.metrics import f1_score, balanced_accuracy_score
```

### 7. Wrong loss function for the task

```python
# Binary classification → BCEWithLogitsLoss (NOT CrossEntropy with 2 classes)
# Multi-class → CrossEntropyLoss (includes softmax internally!)
# Multi-label → BCEWithLogitsLoss per label
# Regression → MSELoss or L1Loss

# COMMON BUG: applying softmax before CrossEntropyLoss (double softmax!)
# CrossEntropyLoss = LogSoftmax + NLLLoss internally
```

### 8. Shuffling time series data

```python
# NEVER shuffle time series for train/test split
# Use temporal split: train on past, test on future
```

### 9. Not setting random seeds

```python
import random, numpy as np, torch

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_seed(42)
```

### 10. Mismatched tensor devices

```python
# BUG: model on GPU, data on CPU (or vice versa)
# RuntimeError: Expected all tensors to be on the same device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = model.to(device)
inputs = inputs.to(device)
labels = labels.to(device)
```

### 11. Integer division in Python 3 for indices

```python
# Not really a bug in Python 3 (// is integer division)
# But watch out for: split_idx = len(data) * 0.8  ← float!
split_idx = int(len(data) * 0.8)
```

### 12. Not detaching tensors before numpy conversion

```python
# BUG: can't call .numpy() on tensor that requires grad
# predictions.numpy()  ← RuntimeError

# FIX:
predictions.detach().cpu().numpy()
```

### 13. In-place operations breaking autograd

```python
# BUG: in-place ops can break gradient computation
# x += 1  ← might cause issues
# x[:, 0] = something  ← definitely breaks gradients

# FIX: use out-of-place operations
x = x + 1
x = torch.cat([something, x[:, 1:]], dim=1)
```

### 14. BatchNorm with batch_size=1

```python
# BatchNorm needs batch_size > 1 (can't compute variance of 1 sample)
# Use GroupNorm or InstanceNorm if batch_size=1 is needed
```

### 15. Loading model weights with mismatched architecture

```python
# FIX: use strict=False to skip mismatched keys
model.load_state_dict(torch.load('weights.pth'), strict=False)
```

### 16. Tokenizer/model mismatch in NLP

```python
# ALWAYS use the tokenizer that matches the model
# BUG: bert-base tokenizer with distilbert model
tokenizer = AutoTokenizer.from_pretrained("same-model-name-as-model")
```

### 17. Not handling variable-length sequences properly

```python
# Use padding + attention_mask in transformers
encodings = tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
# The attention_mask tells the model to ignore padding tokens
```

### 18. Forgetting to move scheduler.step()

```python
# Per-epoch schedulers: call after validation
scheduler.step(val_loss)  # ReduceLROnPlateau

# Per-batch schedulers: call after optimizer.step()
optimizer.step()
scheduler.step()  # OneCycleLR, CosineAnnealingWarmRestarts
```

### 19. Using model output directly as probabilities

```python
# Model outputs are logits, NOT probabilities!
logits = model(inputs)
probabilities = torch.softmax(logits, dim=1)  # for multi-class
probabilities = torch.sigmoid(logits)          # for binary/multi-label
```

### 20. Memory leak from storing tensors in lists

```python
# BUG: storing tensors with grad history fills GPU memory
all_losses = []
for batch in loader:
    loss = criterion(model(batch[0].cuda()), batch[1].cuda())
    all_losses.append(loss)  # ← keeps entire computation graph!

# FIX: detach or use .item()
all_losses.append(loss.item())  # scalar only
```

---

## Hardware & Speed Debugging

### GPU Utilization Monitoring

```python
import subprocess

def gpu_stats():
    """Print GPU utilization and memory."""
    result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total',
                           '--format=csv,nounits,noheader'], capture_output=True, text=True)
    for i, line in enumerate(result.stdout.strip().split('\n')):
        util, used, total = line.split(', ')
        print(f"GPU {i}: {util}% util, {used}/{total} MB memory")

# Call periodically during training
# If utilization < 80%, you have a bottleneck elsewhere (likely data loading)
```

### Data Loading Bottleneck

```python
import time

# Test data loading speed independently
start = time.time()
for i, batch in enumerate(train_loader):
    if i >= 100:
        break
elapsed = time.time() - start
print(f"100 batches loaded in {elapsed:.1f}s ({elapsed/100*1000:.0f}ms per batch)")

# Fix: increase num_workers (try 4, 8, or cpu_count)
# Fix: use pin_memory=True
# Fix: preprocess/resize images offline instead of on-the-fly
# Fix: use faster storage (SSD vs HDD)

# Quick test for optimal num_workers:
for nw in [0, 2, 4, 8, 16]:
    loader = DataLoader(dataset, batch_size=32, num_workers=nw, pin_memory=True)
    start = time.time()
    for i, _ in enumerate(loader):
        if i >= 50: break
    print(f"num_workers={nw}: {time.time()-start:.2f}s")
```

### Memory Profiling

```python
# Check GPU memory usage
print(f"Allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
print(f"Cached: {torch.cuda.memory_reserved() / 1e9:.2f} GB")

# Find memory hogs
torch.cuda.memory_summary()

# Reduce memory:
# 1. Mixed precision training
from torch.cuda.amp import autocast, GradScaler
scaler = GradScaler()

for batch in loader:
    optimizer.zero_grad()
    with autocast():
        outputs = model(inputs.cuda())
        loss = criterion(outputs, labels.cuda())
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()

# 2. Gradient accumulation (simulate larger batch with less memory)
accumulation_steps = 4
for i, (inputs, labels) in enumerate(loader):
    with autocast():
        loss = criterion(model(inputs.cuda()), labels.cuda())
        loss = loss / accumulation_steps
    scaler.scale(loss).backward()
    if (i + 1) % accumulation_steps == 0:
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()

# 3. Gradient checkpointing (trade compute for memory)
from torch.utils.checkpoint import checkpoint
# In model forward:
# out = checkpoint(self.heavy_layer, x)  # recomputes during backward
```

### Training Speed Optimization Checklist

```
□ GPU utilization > 80%? (if not, data loading is bottleneck)
□ Using mixed precision (fp16)? (2x speedup for free)
□ Batch size maximized for GPU memory?
□ num_workers optimized? (usually 4-8)
□ pin_memory=True?
□ Using compiled model? (torch.compile for PyTorch 2.0+)
□ cuDNN benchmark enabled for fixed input sizes?
    torch.backends.cudnn.benchmark = True
□ Unnecessary logging/metrics removed from training loop?
□ Not moving tensors CPU↔GPU unnecessarily?
```

---

## Quick Decision Matrix

| Symptom | Most Likely Cause | First Fix |
|---------|------------------|-----------|
| Loss = NaN | LR too high or log(0) | Reduce LR by 10x |
| Loss not moving | LR too low or broken pipeline | Overfit one batch test |
| Train good, val bad | Overfitting | More augmentation + dropout |
| Both train & val bad | Underfitting | Bigger model or more features |
| Very slow training | Data loading bottleneck | Increase num_workers |
| OOM errors | Batch too large | Reduce batch, use fp16 |
| Accuracy stuck at 50% (binary) | Random guessing | Check labels, loss function |
| Accuracy stuck at 1/N (N classes) | Random guessing | Sanity check everything |
| Val loss oscillating | LR too high | Reduce LR or add warmup |
| Good offline, bad in prod | Train-serve skew | Check preprocessing parity |

---

## The 5-Minute Debugging Protocol

When something goes wrong, run through this exact sequence:

```python
# 1. Can you overfit ONE batch? (30 seconds)
# If NO → model/loss/optimizer is broken

# 2. Print input shapes and ranges
print(inputs.shape, inputs.min(), inputs.max())
print(labels.shape, labels.unique())

# 3. Check gradients exist and are reasonable
loss.backward()
for name, p in model.named_parameters():
    if p.grad is not None:
        print(f"{name}: grad_mean={p.grad.mean():.6f}, grad_std={p.grad.std():.6f}")
    else:
        print(f"{name}: NO GRADIENT")  # ← problem!

# 4. Verify loss function matches task
# Multi-class: CrossEntropyLoss expects (N, C) logits and (N,) integer labels
# Binary: BCEWithLogitsLoss expects (N, 1) logits and (N, 1) float labels

# 5. Try a known-good configuration
# Reset to: lr=1e-3, batch_size=32, Adam, no augmentation
# If this works, add complexity back one thing at a time
```
