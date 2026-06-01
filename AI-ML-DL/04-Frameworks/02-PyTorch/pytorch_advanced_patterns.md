# PyTorch Advanced Patterns

## Table of Contents
- [Custom Datasets and DataLoaders](#custom-datasets-and-dataloaders)
- [Custom Layers and Modules](#custom-layers-and-modules)
- [Advanced Training Patterns](#advanced-training-patterns)
- [Distributed Training Deep Dive](#distributed-training-deep-dive)
- [Model Export and Deployment](#model-export-and-deployment)

---

## Custom Datasets and DataLoaders

### `__getitem__` and `__len__` Pattern

The map-style dataset is the most common pattern:

```python
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import os

class CustomImageDataset(Dataset):
    """
    Map-style dataset: supports random access via index.
    Must implement __getitem__ and __len__.
    """
    
    def __init__(self, image_dir, labels_file, transform=None):
        self.image_dir = image_dir
        self.transform = transform
        
        # Load labels (e.g., from CSV)
        self.labels = []
        self.image_paths = []
        with open(labels_file, 'r') as f:
            for line in f:
                path, label = line.strip().split(',')
                self.image_paths.append(path)
                self.labels.append(int(label))
    
    def __len__(self):
        """Must return the total number of samples."""
        return len(self.labels)
    
    def __getitem__(self, idx):
        """
        Must return a single sample given an index.
        Called by DataLoader to build batches.
        """
        img_path = os.path.join(self.image_dir, self.image_paths[idx])
        image = Image.open(img_path).convert('RGB')
        label = self.labels[idx]
        
        if self.transform:
            image = self.transform(image)
        
        return image, label
```

### `collate_fn` for Variable-Length Sequences

When samples have different sizes, the default collation (stacking into a tensor) fails. Custom `collate_fn` solves this:

```python
def collate_variable_length(batch):
    """
    Custom collate for variable-length sequences.
    batch: list of (sequence_tensor, label) tuples
    """
    # Sort by length (descending) for pack_padded_sequence efficiency
    batch.sort(key=lambda x: len(x[0]), reverse=True)
    
    sequences = [item[0] for item in batch]
    labels = torch.tensor([item[1] for item in batch])
    lengths = torch.tensor([len(seq) for seq in sequences])
    
    # Pad sequences to max length in this batch
    padded = torch.nn.utils.rnn.pad_sequence(sequences, batch_first=True)
    
    return padded, labels, lengths

# Usage
loader = DataLoader(
    dataset,
    batch_size=32,
    collate_fn=collate_variable_length
)
```

**Another common pattern — handling None/failed samples:**

```python
def collate_skip_none(batch):
    """Skip samples that returned None (e.g., corrupted images)."""
    batch = [b for b in batch if b is not None]
    if len(batch) == 0:
        return None
    return torch.utils.data.dataloader.default_collate(batch)
```

### Multi-Worker Data Loading (Pitfalls)

```python
loader = DataLoader(
    dataset,
    batch_size=32,
    num_workers=4,      # 4 separate processes for data loading
    prefetch_factor=2,  # Each worker prefetches 2 batches
    persistent_workers=True,  # Don't respawn workers each epoch
    pin_memory=True,    # For faster GPU transfer
)
```

**Critical pitfalls:**

1. **Fork vs Spawn**: On Linux, workers are forked. Shared state (file handles, RNG) can cause issues:
```python
# BAD: Opening file in __init__ — file handle shared across forked workers
class BadDataset(Dataset):
    def __init__(self, path):
        self.file = open(path)  # Shared across workers!

# GOOD: Open file in __getitem__ or use worker_init_fn
class GoodDataset(Dataset):
    def __init__(self, path):
        self.path = path
    
    def __getitem__(self, idx):
        with open(self.path) as f:  # Each worker opens independently
            ...
```

2. **Random seed per worker**: Without this, all workers generate same augmentations:
```python
def worker_init_fn(worker_id):
    """Ensure each worker has unique random seed."""
    import numpy as np
    np.random.seed(np.random.get_state()[1][0] + worker_id)

loader = DataLoader(dataset, num_workers=4, worker_init_fn=worker_init_fn)
```

3. **Memory growth**: Each worker loads data independently. With `num_workers=8` and large datasets, RAM usage = 8x single worker.

### IterableDataset for Streaming Data

For data too large to index or coming from a stream:

```python
from torch.utils.data import IterableDataset

class StreamingDataset(IterableDataset):
    """
    For data that can't be randomly accessed:
    - Reading from database cursors
    - Streaming from network
    - Processing files too large to index
    """
    
    def __init__(self, file_paths):
        self.file_paths = file_paths
    
    def __iter__(self):
        # Handle multi-worker splitting
        worker_info = torch.utils.data.get_worker_info()
        if worker_info is None:
            # Single worker - process all files
            files = self.file_paths
        else:
            # Split files across workers
            per_worker = len(self.file_paths) // worker_info.num_workers
            worker_id = worker_info.id
            start = worker_id * per_worker
            end = start + per_worker if worker_id < worker_info.num_workers - 1 else len(self.file_paths)
            files = self.file_paths[start:end]
        
        for file_path in files:
            with open(file_path, 'r') as f:
                for line in f:
                    yield self.process_line(line)
    
    def process_line(self, line):
        # Parse and return tensor
        values = [float(x) for x in line.strip().split(',')]
        return torch.tensor(values[:-1]), torch.tensor(values[-1])
```

### Sampler Patterns

```python
from torch.utils.data import WeightedRandomSampler, DistributedSampler

# Weighted sampling for imbalanced datasets
class_counts = [1000, 100, 50]  # Highly imbalanced
weights = 1.0 / torch.tensor(class_counts, dtype=torch.float)
sample_weights = weights[labels]  # Weight per sample

sampler = WeightedRandomSampler(
    weights=sample_weights,
    num_samples=len(sample_weights),
    replacement=True
)

loader = DataLoader(dataset, batch_size=32, sampler=sampler)
# Note: Cannot use shuffle=True with a sampler

# Distributed sampler (for multi-GPU)
sampler = DistributedSampler(
    dataset,
    num_replicas=world_size,
    rank=rank,
    shuffle=True
)
loader = DataLoader(dataset, batch_size=32, sampler=sampler)
# Must call sampler.set_epoch(epoch) each epoch for proper shuffling
```

---

## Custom Layers and Modules

### Building Custom Layers with `nn.Module`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class SEBlock(nn.Module):
    """
    Squeeze-and-Excitation block — channel attention mechanism.
    Shows proper nn.Module patterns.
    """
    
    def __init__(self, channels, reduction=16):
        super().__init__()
        # All sub-modules must be assigned as attributes
        # so they're registered and appear in .parameters()
        self.squeeze = nn.AdaptiveAvgPool2d(1)
        self.excitation = nn.Sequential(
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        batch, channels, _, _ = x.shape
        # Squeeze: Global average pooling
        y = self.squeeze(x).view(batch, channels)
        # Excitation: FC → ReLU → FC → Sigmoid
        y = self.excitation(y).view(batch, channels, 1, 1)
        # Scale: channel-wise multiplication
        return x * y


class ConditionalBatchNorm(nn.Module):
    """
    Conditional Batch Normalization (used in GANs like BigGAN).
    BN parameters are predicted from a conditioning vector.
    """
    
    def __init__(self, num_features, condition_dim):
        super().__init__()
        self.bn = nn.BatchNorm2d(num_features, affine=False)  # No learnable affine
        # Predict gamma and beta from condition
        self.gain = nn.Linear(condition_dim, num_features)
        self.bias = nn.Linear(condition_dim, num_features)
    
    def forward(self, x, condition):
        normalized = self.bn(x)
        gamma = self.gain(condition).unsqueeze(-1).unsqueeze(-1)
        beta = self.bias(condition).unsqueeze(-1).unsqueeze(-1)
        return gamma * normalized + beta
```

### Custom Loss Functions

```python
class FocalLoss(nn.Module):
    """
    Focal Loss for addressing class imbalance.
    Down-weights easy examples, focuses on hard ones.
    FL(p) = -alpha * (1-p)^gamma * log(p)
    """
    
    def __init__(self, alpha=1.0, gamma=2.0, reduction='mean'):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
    
    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction='none')
        pt = torch.exp(-ce_loss)  # probability of correct class
        focal_loss = self.alpha * (1 - pt) ** self.gamma * ce_loss
        
        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        return focal_loss


class ContrastiveLoss(nn.Module):
    """Contrastive loss for siamese networks."""
    
    def __init__(self, margin=1.0):
        super().__init__()
        self.margin = margin
    
    def forward(self, embedding1, embedding2, label):
        # label: 1 = same class, 0 = different class
        distance = F.pairwise_distance(embedding1, embedding2)
        loss = label * distance.pow(2) + \
               (1 - label) * F.relu(self.margin - distance).pow(2)
        return loss.mean()
```

### Hooks (`register_forward_hook`, `register_backward_hook`)

Hooks allow inspecting/modifying activations and gradients without changing model code:

```python
class HookManager:
    """Utility for managing hooks and extracting intermediate features."""
    
    def __init__(self):
        self.activations = {}
        self.gradients = {}
        self.handles = []
    
    def register_forward_hook(self, model, layer_name):
        """Capture output of a layer during forward pass."""
        layer = dict(model.named_modules())[layer_name]
        
        def hook_fn(module, input, output):
            self.activations[layer_name] = output.detach()
        
        handle = layer.register_forward_hook(hook_fn)
        self.handles.append(handle)
    
    def register_backward_hook(self, model, layer_name):
        """Capture gradients flowing through a layer during backward pass."""
        layer = dict(model.named_modules())[layer_name]
        
        def hook_fn(module, grad_input, grad_output):
            self.gradients[layer_name] = grad_output[0].detach()
        
        handle = layer.register_full_backward_hook(hook_fn)
        self.handles.append(handle)
    
    def remove_all(self):
        for handle in self.handles:
            handle.remove()
        self.handles.clear()

# Usage: Feature extraction without modifying model
hook_mgr = HookManager()
hook_mgr.register_forward_hook(model, 'layer4')  # Get features from layer4

output = model(input_tensor)
features = hook_mgr.activations['layer4']  # Intermediate features!

# Usage: Gradient-based visualization (GradCAM)
hook_mgr.register_backward_hook(model, 'layer4')
output = model(input_tensor)
output[0, target_class].backward()
gradients = hook_mgr.gradients['layer4']
```

**Modifying gradients with hooks (gradient clipping per layer):**

```python
def clip_gradient_hook(module, grad_input, grad_output):
    """Clip gradients at a specific layer."""
    return tuple(g.clamp(-1.0, 1.0) if g is not None else g for g in grad_input)

model.layer3.register_full_backward_hook(clip_gradient_hook)
```

### Parameter vs Buffer (`register_buffer`)

```python
class LayerNormCustom(nn.Module):
    """
    Demonstrates the difference between Parameter and Buffer.
    
    Parameter: learnable, updated by optimizer, saved in state_dict
    Buffer: NOT learnable, NOT updated by optimizer, but saved in state_dict
            and moved with .to(device)
    """
    
    def __init__(self, features):
        super().__init__()
        # Parameters — these are trained
        self.weight = nn.Parameter(torch.ones(features))
        self.bias = nn.Parameter(torch.zeros(features))
        
        # Buffer — not trained, but part of model state
        # Example: running mean/var in BatchNorm, positional encodings
        self.register_buffer('running_mean', torch.zeros(features))
        self.register_buffer('num_batches_tracked', torch.tensor(0, dtype=torch.long))
        
        # Regular attribute — NOT in state_dict, NOT moved with .to()
        self.epsilon = 1e-5  # Just a Python float
    
    def forward(self, x):
        mean = x.mean(-1, keepdim=True)
        std = x.std(-1, keepdim=True)
        
        # Update buffer (not tracked by autograd)
        if self.training:
            self.running_mean = 0.9 * self.running_mean + 0.1 * mean.mean(0).squeeze()
            self.num_batches_tracked += 1
        
        return self.weight * (x - mean) / (std + self.epsilon) + self.bias

# Verification
model = LayerNormCustom(64)
print(list(model.parameters()))        # weight, bias
print(list(model.buffers()))           # running_mean, num_batches_tracked
print(model.state_dict().keys())       # weight, bias, running_mean, num_batches_tracked

# .to() moves both parameters AND buffers
model = model.to('cuda')  # running_mean is now on GPU too
```

---

## Advanced Training Patterns

### Mixed Precision Training (`torch.cuda.amp`)

Uses float16 for most operations (2x memory savings, faster compute on modern GPUs) while keeping critical operations in float32:

```python
import torch
from torch.cuda.amp import autocast, GradScaler

model = MyModel().cuda()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
scaler = GradScaler()  # Handles loss scaling to prevent underflow in fp16

for epoch in range(num_epochs):
    for batch in train_loader:
        inputs, targets = batch[0].cuda(), batch[1].cuda()
        
        optimizer.zero_grad()
        
        # autocast: automatically uses fp16 where safe
        with autocast():
            outputs = model(inputs)
            loss = criterion(outputs, targets)
        
        # Scale loss to prevent gradient underflow, then backward
        scaler.scale(loss).backward()
        
        # Unscale gradients for clipping (optional)
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        # Step with scaler (skips step if gradients contain inf/nan)
        scaler.step(optimizer)
        scaler.update()
```

**What autocast does internally:**
- MatMul, Conv, Linear → fp16 (fast on tensor cores)
- Softmax, LayerNorm, Loss → fp32 (needs precision)
- Reductions (sum, mean) → fp32

### Gradient Clipping Strategies

```python
# Strategy 1: Clip by global norm (most common)
# Scales all gradients so that the total norm <= max_norm
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

# Strategy 2: Clip by value
# Clips each gradient element independently
torch.nn.utils.clip_grad_value_(model.parameters(), clip_value=0.5)

# Strategy 3: Adaptive clipping (used in some papers)
def adaptive_clip_grad(parameters, clip_factor=0.01, eps=1e-3):
    """Clip gradient based on parameter-to-gradient ratio (AGC from NFNets)."""
    for p in parameters:
        if p.grad is None:
            continue
        p_norm = p.data.norm(2)
        g_norm = p.grad.data.norm(2)
        max_norm = p_norm * clip_factor
        if g_norm > max_norm:
            p.grad.data.mul_(max_norm / (g_norm + eps))
```

### Learning Rate Warmup Implementation

```python
import torch.optim as optim
from torch.optim.lr_scheduler import LambdaLR, CosineAnnealingLR, SequentialLR

# Warmup + Cosine Annealing (very common in transformers)
def get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps):
    def lr_lambda(current_step):
        if current_step < warmup_steps:
            # Linear warmup
            return float(current_step) / float(max(1, warmup_steps))
        # Cosine decay
        progress = float(current_step - warmup_steps) / float(max(1, total_steps - warmup_steps))
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))
    
    return LambdaLR(optimizer, lr_lambda)

# Using PyTorch's built-in SequentialLR (cleaner)
optimizer = optim.AdamW(model.parameters(), lr=1e-3)
warmup = torch.optim.lr_scheduler.LinearLR(optimizer, start_factor=0.01, total_iters=1000)
cosine = CosineAnnealingLR(optimizer, T_max=50000)
scheduler = SequentialLR(optimizer, schedulers=[warmup, cosine], milestones=[1000])

# In training loop:
for step, batch in enumerate(train_loader):
    # ... train ...
    scheduler.step()
```

### Gradient Accumulation for Effective Large Batch

```python
accumulation_steps = 4  # Effective batch = batch_size * accumulation_steps

optimizer.zero_grad()
for i, (inputs, targets) in enumerate(train_loader):
    inputs, targets = inputs.cuda(), targets.cuda()
    
    with autocast():
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        loss = loss / accumulation_steps  # Normalize loss
    
    scaler.scale(loss).backward()  # Accumulate gradients
    
    if (i + 1) % accumulation_steps == 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()
        scheduler.step()
```

### Multi-Task Learning with Shared Backbone

```python
class MultiTaskModel(nn.Module):
    """
    Shared backbone with task-specific heads.
    Common in autonomous driving (detection + segmentation + depth).
    """
    
    def __init__(self, backbone, num_classes_task1, num_classes_task2):
        super().__init__()
        self.backbone = backbone  # Shared feature extractor
        self.head1 = nn.Linear(backbone.output_dim, num_classes_task1)
        self.head2 = nn.Linear(backbone.output_dim, num_classes_task2)
    
    def forward(self, x):
        features = self.backbone(x)
        return self.head1(features), self.head2(features)

# Training with uncertainty-based loss weighting (Kendall et al.)
class MultiTaskLoss(nn.Module):
    def __init__(self, num_tasks):
        super().__init__()
        # Learnable log-variance for each task (uncertainty weighting)
        self.log_vars = nn.Parameter(torch.zeros(num_tasks))
    
    def forward(self, losses):
        total = 0
        for i, loss in enumerate(losses):
            precision = torch.exp(-self.log_vars[i])
            total += precision * loss + self.log_vars[i]
        return total

# Usage
model = MultiTaskModel(backbone, 10, 5)
mt_loss = MultiTaskLoss(2)
optimizer = optim.Adam(list(model.parameters()) + list(mt_loss.parameters()), lr=1e-3)

output1, output2 = model(input)
loss1 = F.cross_entropy(output1, target1)
loss2 = F.cross_entropy(output2, target2)
loss = mt_loss([loss1, loss2])
loss.backward()
```

### Curriculum Learning Implementation

```python
class CurriculumSampler:
    """
    Start training with easy samples, gradually introduce harder ones.
    Difficulty can be based on loss, data complexity, or predefined scores.
    """
    
    def __init__(self, dataset, difficulty_scores, initial_fraction=0.3):
        self.dataset = dataset
        # Sort indices by difficulty (easiest first)
        self.sorted_indices = torch.argsort(torch.tensor(difficulty_scores)).tolist()
        self.current_fraction = initial_fraction
    
    def get_subset(self):
        """Get current curriculum subset."""
        n = int(len(self.sorted_indices) * self.current_fraction)
        indices = self.sorted_indices[:n]
        return torch.utils.data.Subset(self.dataset, indices)
    
    def step(self, increase=0.1):
        """Expand curriculum."""
        self.current_fraction = min(1.0, self.current_fraction + increase)

# Usage
curriculum = CurriculumSampler(dataset, difficulty_scores)
for epoch in range(num_epochs):
    subset = curriculum.get_subset()
    loader = DataLoader(subset, batch_size=32, shuffle=True)
    train_one_epoch(model, loader)
    curriculum.step(increase=0.1)  # Gradually include harder samples
```

---

## Distributed Training Deep Dive

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                    Distributed Training                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Node 0 (Machine 1)          Node 1 (Machine 2)              │
│  ┌──────┐  ┌──────┐         ┌──────┐  ┌──────┐             │
│  │GPU 0 │  │GPU 1 │         │GPU 2 │  │GPU 3 │             │
│  │Rank 0│  │Rank 1│         │Rank 2│  │Rank 3│             │
│  │      │  │      │         │      │  │      │             │
│  │Model │  │Model │         │Model │  │Model │             │
│  │Copy  │  │Copy  │         │Copy  │  │Copy  │             │
│  └──┬───┘  └──┬───┘         └──┬───┘  └──┬───┘             │
│     │         │                 │         │                   │
│     └────┬────┘                 └────┬────┘                   │
│          │                           │                        │
│          └───────── AllReduce ────────┘                        │
│           (NCCL: average gradients across all ranks)           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### `DistributedDataParallel` (DDP) Step by Step

```python
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler

def setup(rank, world_size):
    """Initialize process group."""
    os.environ['MASTER_ADDR'] = 'localhost'
    os.environ['MASTER_PORT'] = '12355'
    dist.init_process_group("nccl", rank=rank, world_size=world_size)
    torch.cuda.set_device(rank)

def cleanup():
    dist.destroy_process_group()

def train(rank, world_size):
    setup(rank, world_size)
    
    # Each process gets its own model copy on its GPU
    model = MyModel().to(rank)
    model = DDP(model, device_ids=[rank])
    
    # DistributedSampler ensures each process gets different data
    sampler = DistributedSampler(dataset, num_replicas=world_size, rank=rank)
    loader = DataLoader(dataset, batch_size=32, sampler=sampler)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    for epoch in range(num_epochs):
        sampler.set_epoch(epoch)  # CRITICAL for proper shuffling
        
        for batch in loader:
            inputs = batch[0].to(rank)
            targets = batch[1].to(rank)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = F.cross_entropy(outputs, targets)
            loss.backward()  # DDP automatically syncs gradients via AllReduce
            optimizer.step()
    
    cleanup()

# Launch
if __name__ == "__main__":
    world_size = torch.cuda.device_count()
    mp.spawn(train, args=(world_size,), nprocs=world_size, join=True)
```

### Launch with `torchrun` (preferred over mp.spawn)

```bash
# Single node, 4 GPUs
torchrun --nproc_per_node=4 train.py

# Multi-node (run on each node)
torchrun --nproc_per_node=4 --nnodes=2 --node_rank=0 \
    --master_addr=192.168.1.1 --master_port=12355 train.py
```

```python
# train.py with torchrun
import os
import torch.distributed as dist

def main():
    # torchrun sets these environment variables automatically
    dist.init_process_group("nccl")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    local_rank = int(os.environ["LOCAL_RANK"])
    
    torch.cuda.set_device(local_rank)
    
    model = MyModel().to(local_rank)
    model = DDP(model, device_ids=[local_rank])
    
    # ... training loop ...
    
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

### FSDP (Fully Sharded Data Parallel)

DDP replicates the full model on each GPU. FSDP **shards** parameters across GPUs — each GPU holds only a fraction:

```
DDP: Each GPU holds full model + full gradients + full optimizer state
     Memory per GPU: Model + Gradients + Optimizer ≈ 16x model params (fp32)

FSDP: Parameters sharded across GPUs, gathered only when needed
      Memory per GPU: (Model + Gradients + Optimizer) / N
```

```python
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
from torch.distributed.fsdp import MixedPrecision, ShardingStrategy

# Mixed precision policy for FSDP
mp_policy = MixedPrecision(
    param_dtype=torch.float16,
    reduce_dtype=torch.float16,
    buffer_dtype=torch.float32,
)

model = MyLargeModel().to(local_rank)
model = FSDP(
    model,
    sharding_strategy=ShardingStrategy.FULL_SHARD,  # Maximum memory savings
    mixed_precision=mp_policy,
    device_id=local_rank,
    # Wrap individual layers for better memory/compute trade-off
    auto_wrap_policy=size_based_auto_wrap_policy,
)

# Training loop is identical to DDP
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
for batch in loader:
    optimizer.zero_grad()
    loss = model(batch).loss
    loss.backward()
    optimizer.step()
```

**Sharding strategies:**
- `FULL_SHARD`: Shard parameters, gradients, optimizer state (most memory efficient)
- `SHARD_GRAD_OP`: Shard gradients and optimizer only (faster, more memory)
- `NO_SHARD`: Equivalent to DDP (baseline)

### Pipeline Parallelism

Split model layers across GPUs for models too large for single GPU:

```python
from torch.distributed.pipelining import SplitPoint, pipeline, ScheduleGPipe

# Define split points
class LargeModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.layers_0_11 = nn.TransformerEncoder(...)   # GPU 0
        self.layers_12_23 = nn.TransformerEncoder(...)  # GPU 1
        self.head = nn.Linear(d_model, vocab_size)      # GPU 1

# Manual pipeline (simplified concept)
# GPU 0 processes micro-batch 1, then passes to GPU 1
# While GPU 1 processes micro-batch 1, GPU 0 starts micro-batch 2
# This overlaps computation across GPUs
```

---

## Model Export and Deployment

### TorchScript Export

```python
# For deployment to C++, mobile, or environments without Python
model.eval()

# Method 1: Tracing (simpler, no control flow)
example = torch.randn(1, 3, 224, 224)
traced = torch.jit.trace(model, example)
traced.save("model_traced.pt")

# Method 2: Scripting (supports control flow)
scripted = torch.jit.script(model)
scripted.save("model_scripted.pt")

# Loading in C++ (libtorch):
# torch::jit::Module model = torch::jit::load("model_traced.pt");
```

### ONNX Export

```python
import torch.onnx

model.eval()
dummy_input = torch.randn(1, 3, 224, 224).cuda()

torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    export_params=True,
    opset_version=17,
    do_constant_folding=True,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={
        'input': {0: 'batch_size'},   # Variable batch size
        'output': {0: 'batch_size'}
    }
)

# Verify
import onnx
model_onnx = onnx.load("model.onnx")
onnx.checker.check_model(model_onnx)

# Run with ONNX Runtime
import onnxruntime as ort
session = ort.InferenceSession("model.onnx")
result = session.run(None, {"input": input_numpy})
```

### Quantization

```python
import torch.quantization as quant

# Dynamic Quantization (easiest, good for LSTMs/Transformers)
# Weights quantized statically, activations quantized dynamically per-batch
quantized_model = torch.quantization.quantize_dynamic(
    model,
    {nn.Linear, nn.LSTM},  # Layers to quantize
    dtype=torch.qint8
)

# Static Quantization (better performance, requires calibration)
model.eval()
model.qconfig = quant.get_default_qconfig('x86')  # or 'qnnpack' for ARM
quant.prepare(model, inplace=True)

# Calibration: run representative data through the model
with torch.no_grad():
    for batch in calibration_loader:
        model(batch)

quant.convert(model, inplace=True)

# Quantization-Aware Training (QAT) — best accuracy
model.train()
model.qconfig = quant.get_default_qat_qconfig('x86')
quant.prepare_qat(model, inplace=True)

# Fine-tune with fake quantization
for epoch in range(num_finetune_epochs):
    train_one_epoch(model, train_loader)

model.eval()
quantized = quant.convert(model)
```

### Pruning

```python
import torch.nn.utils.prune as prune

model = MyModel()

# Unstructured pruning (individual weights)
prune.l1_unstructured(model.linear1, name='weight', amount=0.3)  # Remove 30% smallest

# Structured pruning (entire channels/filters)
prune.ln_structured(model.conv1, name='weight', amount=0.2, n=2, dim=0)

# Global pruning (prune across all layers by importance)
parameters_to_prune = [
    (model.conv1, 'weight'),
    (model.conv2, 'weight'),
    (model.linear1, 'weight'),
]
prune.global_unstructured(
    parameters_to_prune,
    pruning_method=prune.L1Unstructured,
    amount=0.4,  # Remove 40% globally
)

# Check sparsity
total = 0
zero = 0
for module, name in parameters_to_prune:
    total += getattr(module, name).nelement()
    zero += (getattr(module, name) == 0).sum().item()
print(f"Global sparsity: {100 * zero / total:.1f}%")

# Make pruning permanent (remove the mask)
for module, name in parameters_to_prune:
    prune.remove(module, name)
```

### TorchServe Setup

```bash
# Package model
torch-model-archiver --model-name resnet \
    --version 1.0 \
    --serialized-file model.pt \
    --handler image_classifier \
    --export-path model_store

# Start server
torchserve --start --model-store model_store --models resnet=resnet.mar

# Inference
curl http://localhost:8080/predictions/resnet -T image.jpg
```

Custom handler:
```python
from ts.torch_handler.base_handler import BaseHandler

class CustomHandler(BaseHandler):
    def preprocess(self, data):
        # Transform raw input to tensor
        images = [self.transform(Image.open(io.BytesIO(d['body']))) for d in data]
        return torch.stack(images)
    
    def inference(self, data):
        with torch.no_grad():
            return self.model(data)
    
    def postprocess(self, inference_output):
        probs = torch.softmax(inference_output, dim=1)
        return probs.tolist()
```
