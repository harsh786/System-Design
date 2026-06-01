# PyTorch Mastery

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       PyTorch Architecture                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ Tensors  │───▶│ Autograd │───▶│nn.Module │───▶│Optimizer │    │
│  │ (Data)   │    │(Gradient)│    │ (Model)  │    │ (Update) │    │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
│       │                                                │           │
│       ▼                                                ▼           │
│  ┌──────────┐                                    ┌──────────┐    │
│  │DataLoader│                                    │Scheduler │    │
│  │(Batching)│                                    │(LR decay)│    │
│  └──────────┘                                    └──────────┘    │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    Training Loop                            │   │
│  │  for epoch:                                                 │   │
│  │    for batch in dataloader:                                 │   │
│  │      output = model(batch)        # Forward pass            │   │
│  │      loss = criterion(output, target)                       │   │
│  │      loss.backward()              # Backward pass           │   │
│  │      optimizer.step()             # Update weights          │   │
│  │      optimizer.zero_grad()        # Clear gradients         │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Tensors

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# ============================================================
# TENSOR CREATION
# ============================================================

# From data
x = torch.tensor([1, 2, 3], dtype=torch.float32)
x = torch.from_numpy(numpy_array)  # Shares memory!

# Common constructors
zeros = torch.zeros(3, 4)
ones = torch.ones(3, 4)
rand = torch.rand(3, 4)        # Uniform [0, 1)
randn = torch.randn(3, 4)     # Normal(0, 1)
arange = torch.arange(0, 10, 2)
linspace = torch.linspace(0, 1, 100)
eye = torch.eye(3)             # Identity matrix
empty = torch.empty(3, 4)     # Uninitialized

# Like existing tensor
x_like = torch.zeros_like(x)
x_new = x.new_ones(5, 3)

# ============================================================
# TENSOR OPERATIONS
# ============================================================

# Shape operations
x = torch.randn(2, 3, 4)
x.shape                    # torch.Size([2, 3, 4])
x.view(6, 4)             # Reshape (contiguous memory required)
x.reshape(6, 4)          # Reshape (always works)
x.permute(2, 0, 1)       # Transpose dimensions
x.unsqueeze(0)           # Add dimension: [1, 2, 3, 4]
x.squeeze()              # Remove size-1 dimensions
x.flatten()              # Flatten to 1D
x.expand(5, 3, 4)       # Expand (no memory copy)

# Math operations
a = torch.randn(3, 4)
b = torch.randn(3, 4)
c = a + b                 # Element-wise add
c = a @ b.T               # Matrix multiplication
c = torch.matmul(a, b.T)  # Same as above
c = torch.bmm(batch_a, batch_b)  # Batch matrix multiply

# Reduction
x.sum(), x.mean(), x.std()
x.sum(dim=1)             # Sum along dimension 1
x.max(dim=1)             # Returns (values, indices)
x.argmax(dim=1)          # Indices of max values

# Indexing
x[0, :, :]               # First element
x[:, 1:3, :]             # Slice
x[x > 0]                 # Boolean indexing
x.masked_fill_(mask, 0)  # Fill where mask is True

# ============================================================
# GPU OPERATIONS
# ============================================================

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Move to GPU
x = x.to(device)
x = x.cuda()              # Shorthand
x = x.cpu()               # Back to CPU

# Create directly on GPU
x = torch.randn(3, 4, device=device)

# Check GPU memory
print(torch.cuda.memory_allocated())
print(torch.cuda.memory_reserved())
torch.cuda.empty_cache()
```

## Autograd (Automatic Differentiation)

```python
# ============================================================
# AUTOGRAD BASICS
# ============================================================

# Enable gradient tracking
x = torch.randn(3, requires_grad=True)
y = x ** 2 + 2 * x + 1
z = y.sum()

# Compute gradients
z.backward()
print(x.grad)  # dz/dx = 2x + 2

# Gradient accumulation (default behavior!)
x.grad.zero_()  # Must manually zero gradients

# Disable gradient tracking
with torch.no_grad():
    # Inference, evaluation
    output = model(x)

# Detach from computation graph
x_detached = x.detach()  # New tensor, no gradient

# Gradient clipping (prevent exploding gradients)
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
torch.nn.utils.clip_grad_value_(model.parameters(), clip_value=0.5)

# Custom autograd function
class CustomReLU(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input):
        ctx.save_for_backward(input)
        return input.clamp(min=0)
    
    @staticmethod
    def backward(ctx, grad_output):
        input, = ctx.saved_tensors
        grad_input = grad_output.clone()
        grad_input[input < 0] = 0
        return grad_input
```

## nn.Module (Building Blocks)

```python
# ============================================================
# BUILDING NEURAL NETWORKS
# ============================================================

class ConvNet(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        
        # Feature extractor
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )
    
    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)  # Flatten
        x = self.classifier(x)
        return x

# Common layers
nn.Linear(in_features, out_features)
nn.Conv2d(in_channels, out_channels, kernel_size)
nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
nn.Transformer(d_model, nhead, num_encoder_layers)
nn.Embedding(num_embeddings, embedding_dim)
nn.BatchNorm2d(num_features)
nn.LayerNorm(normalized_shape)
nn.Dropout(p=0.5)

# Inspect model
model = ConvNet()
print(model)
print(sum(p.numel() for p in model.parameters()))  # Total parameters
print(sum(p.numel() for p in model.parameters() if p.requires_grad))  # Trainable

# Parameter groups
for name, param in model.named_parameters():
    print(f"{name}: {param.shape}")
```

## Custom Datasets and DataLoaders

```python
# ============================================================
# CUSTOM DATASET
# ============================================================

class ImageDataset(Dataset):
    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        image = Image.open(self.image_paths[idx]).convert('RGB')
        label = self.labels[idx]
        
        if self.transform:
            image = self.transform(image)
        
        return image, label

# Transforms
from torchvision import transforms

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])

# DataLoader
train_loader = DataLoader(
    train_dataset,
    batch_size=32,
    shuffle=True,
    num_workers=4,
    pin_memory=True,       # Faster GPU transfer
    drop_last=True,        # Drop incomplete last batch
    prefetch_factor=2,
)

# Tabular Dataset
class TabularDataset(Dataset):
    def __init__(self, df, target_col):
        self.features = torch.tensor(
            df.drop(columns=[target_col]).values, dtype=torch.float32
        )
        self.targets = torch.tensor(df[target_col].values, dtype=torch.long)
    
    def __len__(self):
        return len(self.targets)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]
```

## Complete Training Loop

```python
# ============================================================
# PRODUCTION-READY TRAINING LOOP
# ============================================================

def train_model(model, train_loader, val_loader, config):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config['lr'], weight_decay=config['weight_decay']
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config['epochs']
    )
    
    # Mixed precision
    scaler = torch.amp.GradScaler('cuda')
    
    best_val_loss = float('inf')
    patience_counter = 0
    
    for epoch in range(config['epochs']):
        # ─── Training ───
        model.train()
        train_loss = 0
        correct = 0
        total = 0
        
        for batch_idx, (inputs, targets) in enumerate(train_loader):
            inputs, targets = inputs.to(device), targets.to(device)
            
            # Mixed precision forward pass
            with torch.amp.autocast('cuda'):
                outputs = model(inputs)
                loss = criterion(outputs, targets)
            
            # Backward pass with gradient scaling
            scaler.scale(loss).backward()
            
            # Gradient clipping
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)  # More efficient than zero_grad()
            
            train_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
        
        train_acc = 100. * correct / total
        avg_train_loss = train_loss / len(train_loader)
        
        # ─── Validation ───
        model.eval()
        val_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                with torch.amp.autocast('cuda'):
                    outputs = model(inputs)
                    loss = criterion(outputs, targets)
                
                val_loss += loss.item()
                _, predicted = outputs.max(1)
                total += targets.size(0)
                correct += predicted.eq(targets).sum().item()
        
        val_acc = 100. * correct / total
        avg_val_loss = val_loss / len(val_loader)
        
        scheduler.step()
        
        print(f"Epoch {epoch+1}/{config['epochs']} | "
              f"Train Loss: {avg_train_loss:.4f} Acc: {train_acc:.2f}% | "
              f"Val Loss: {avg_val_loss:.4f} Acc: {val_acc:.2f}%")
        
        # ─── Early Stopping & Checkpointing ───
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': best_val_loss,
                'val_acc': val_acc,
            }, 'best_model.pth')
        else:
            patience_counter += 1
            if patience_counter >= config['patience']:
                print(f"Early stopping at epoch {epoch+1}")
                break
    
    return model

# Usage
config = {
    'lr': 3e-4,
    'weight_decay': 0.01,
    'epochs': 100,
    'patience': 10,
}
trained_model = train_model(model, train_loader, val_loader, config)
```

## Loss Functions and Optimizers

```python
# ============================================================
# LOSS FUNCTIONS
# ============================================================

# Classification
nn.CrossEntropyLoss()           # Multi-class (includes softmax)
nn.BCEWithLogitsLoss()          # Binary (includes sigmoid)
nn.NLLLoss()                    # Use with log_softmax output

# Regression
nn.MSELoss()                    # Mean Squared Error
nn.L1Loss()                     # Mean Absolute Error
nn.SmoothL1Loss()               # Huber loss
nn.HuberLoss(delta=1.0)

# Other
nn.TripletMarginLoss()          # Metric learning
nn.CosineEmbeddingLoss()        # Similarity learning
nn.CTCLoss()                    # Sequence-to-sequence (OCR, ASR)

# Custom loss
class FocalLoss(nn.Module):
    """Handles class imbalance by down-weighting easy examples."""
    def __init__(self, alpha=1, gamma=2):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, inputs, targets):
        BCE_loss = F.cross_entropy(inputs, targets, reduction='none')
        pt = torch.exp(-BCE_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * BCE_loss
        return focal_loss.mean()

# ============================================================
# OPTIMIZERS
# ============================================================

# Common optimizers
torch.optim.SGD(params, lr=0.01, momentum=0.9, weight_decay=1e-4)
torch.optim.Adam(params, lr=1e-3, betas=(0.9, 0.999), weight_decay=0)
torch.optim.AdamW(params, lr=1e-3, weight_decay=0.01)  # Decoupled weight decay
torch.optim.RMSprop(params, lr=0.01)

# Learning rate schedulers
torch.optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)
torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=0.01, total_steps=1000)
torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)

# Differential learning rates (fine-tuning)
optimizer = torch.optim.AdamW([
    {'params': model.features.parameters(), 'lr': 1e-5},   # Pretrained: low LR
    {'params': model.classifier.parameters(), 'lr': 1e-3}, # New layers: high LR
])
```

## Transfer Learning

```python
import torchvision.models as models

# ============================================================
# TRANSFER LEARNING PATTERNS
# ============================================================

# Pattern 1: Feature extraction (freeze backbone)
model = models.resnet50(weights='IMAGENET1K_V2')
for param in model.parameters():
    param.requires_grad = False

# Replace classifier head
model.fc = nn.Sequential(
    nn.Linear(2048, 512),
    nn.ReLU(),
    nn.Dropout(0.3),
    nn.Linear(512, num_classes)
)

# Pattern 2: Fine-tuning (unfreeze gradually)
model = models.resnet50(weights='IMAGENET1K_V2')
model.fc = nn.Linear(2048, num_classes)

# Freeze all except last few layers
for name, param in model.named_parameters():
    if 'layer4' not in name and 'fc' not in name:
        param.requires_grad = False

# Pattern 3: Gradual unfreezing
def unfreeze_layer(model, layer_name):
    for name, param in model.named_parameters():
        if layer_name in name:
            param.requires_grad = True
```

## Model Saving and Loading

```python
# ============================================================
# SAVING / LOADING
# ============================================================

# Save state dict (RECOMMENDED)
torch.save(model.state_dict(), 'model_weights.pth')

# Load state dict
model = ConvNet(num_classes=10)
model.load_state_dict(torch.load('model_weights.pth', map_location=device))
model.eval()

# Save full checkpoint (for resuming training)
checkpoint = {
    'epoch': epoch,
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'scheduler_state_dict': scheduler.state_dict(),
    'best_val_loss': best_val_loss,
    'config': config,
}
torch.save(checkpoint, 'checkpoint.pth')

# Resume training
checkpoint = torch.load('checkpoint.pth')
model.load_state_dict(checkpoint['model_state_dict'])
optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
start_epoch = checkpoint['epoch'] + 1
```

## Distributed Training

```python
# ============================================================
# DataParallel (Simple, single machine multi-GPU)
# ============================================================
model = nn.DataParallel(model)  # Wraps model
# Access original model: model.module

# ============================================================
# DistributedDataParallel (RECOMMENDED for multi-GPU)
# ============================================================
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler

def setup(rank, world_size):
    dist.init_process_group("nccl", rank=rank, world_size=world_size)
    torch.cuda.set_device(rank)

def cleanup():
    dist.destroy_process_group()

def train_ddp(rank, world_size):
    setup(rank, world_size)
    
    model = ConvNet().to(rank)
    model = DDP(model, device_ids=[rank])
    
    sampler = DistributedSampler(dataset, num_replicas=world_size, rank=rank)
    loader = DataLoader(dataset, batch_size=32, sampler=sampler)
    
    for epoch in range(epochs):
        sampler.set_epoch(epoch)  # Important for shuffling
        for data, target in loader:
            # Normal training loop
            pass
    
    cleanup()

# Launch
import torch.multiprocessing as mp
mp.spawn(train_ddp, args=(world_size,), nprocs=world_size)

# Or with torchrun:
# torchrun --nproc_per_node=4 train.py
```

## TorchScript and ONNX Export

```python
# ============================================================
# TORCHSCRIPT (Production inference)
# ============================================================

# Method 1: Tracing (works for models without control flow)
model.eval()
example_input = torch.randn(1, 3, 224, 224)
traced_model = torch.jit.trace(model, example_input)
traced_model.save('model_traced.pt')

# Method 2: Scripting (handles control flow)
scripted_model = torch.jit.script(model)
scripted_model.save('model_scripted.pt')

# Load and use
loaded = torch.jit.load('model_traced.pt')
output = loaded(input_tensor)

# ============================================================
# ONNX EXPORT
# ============================================================
torch.onnx.export(
    model,
    example_input,
    'model.onnx',
    export_params=True,
    opset_version=17,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={
        'input': {0: 'batch_size'},
        'output': {0: 'batch_size'}
    }
)

# Inference with ONNX Runtime
import onnxruntime as ort
session = ort.InferenceSession('model.onnx')
result = session.run(None, {'input': input_numpy})
```

## Mixed Precision Training

```python
# Automatic Mixed Precision (AMP)
# Uses float16 for forward pass (faster), float32 for gradients (stable)

scaler = torch.amp.GradScaler('cuda')

for inputs, targets in train_loader:
    inputs, targets = inputs.to(device), targets.to(device)
    
    with torch.amp.autocast('cuda'):  # float16 forward pass
        outputs = model(inputs)
        loss = criterion(outputs, targets)
    
    scaler.scale(loss).backward()     # Scale loss to prevent underflow
    scaler.step(optimizer)            # Unscale and step
    scaler.update()                   # Update scale factor
    optimizer.zero_grad()

# Benefits: ~2x speedup, ~50% memory reduction on modern GPUs
```

## PyTorch Lightning Overview

```python
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping

class LitModel(pl.LightningModule):
    def __init__(self, num_classes, lr=1e-3):
        super().__init__()
        self.save_hyperparameters()
        self.model = ConvNet(num_classes)
        self.criterion = nn.CrossEntropyLoss()
    
    def forward(self, x):
        return self.model(x)
    
    def training_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = self.criterion(logits, y)
        acc = (logits.argmax(1) == y).float().mean()
        self.log_dict({'train_loss': loss, 'train_acc': acc}, prog_bar=True)
        return loss
    
    def validation_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = self.criterion(logits, y)
        acc = (logits.argmax(1) == y).float().mean()
        self.log_dict({'val_loss': loss, 'val_acc': acc}, prog_bar=True)
    
    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(self.parameters(), lr=self.hparams.lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=50)
        return [optimizer], [scheduler]

# Train
trainer = pl.Trainer(
    max_epochs=50,
    accelerator='gpu',
    devices=1,
    precision='16-mixed',
    callbacks=[
        ModelCheckpoint(monitor='val_loss', mode='min'),
        EarlyStopping(monitor='val_loss', patience=10),
    ],
)
trainer.fit(model, train_loader, val_loader)
```

## Debugging Tips

```python
# 1. Check tensor shapes at each step
def debug_forward(self, x):
    print(f"Input: {x.shape}")
    x = self.conv1(x)
    print(f"After conv1: {x.shape}")
    return x

# 2. Detect anomalies (NaN, Inf)
torch.autograd.set_detect_anomaly(True)

# 3. Check gradients
for name, param in model.named_parameters():
    if param.grad is not None:
        print(f"{name}: grad mean={param.grad.mean():.6f}, max={param.grad.max():.6f}")

# 4. Memory debugging
print(torch.cuda.memory_summary())

# 5. Profile performance
with torch.profiler.profile(
    activities=[torch.profiler.ProfilerActivity.CPU,
                torch.profiler.ProfilerActivity.CUDA],
    with_stack=True
) as prof:
    model(input)
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=10))

# 6. Reproducibility
torch.manual_seed(42)
torch.cuda.manual_seed_all(42)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
```

## Common Anti-Patterns

```python
# BAD: Forgetting model.eval() during inference
output = model(x)  # BatchNorm and Dropout still active!

# GOOD:
model.eval()
with torch.no_grad():
    output = model(x)

# BAD: Not zeroing gradients
loss.backward()
optimizer.step()  # Gradients accumulate across batches!

# GOOD:
optimizer.zero_grad()
loss.backward()
optimizer.step()

# BAD: Moving data to GPU in the loop body
for x, y in loader:
    x = x.to(device)  # Synchronous transfer, slow

# GOOD: Use pin_memory=True in DataLoader + non_blocking
loader = DataLoader(..., pin_memory=True)
for x, y in loader:
    x = x.to(device, non_blocking=True)

# BAD: Keeping computation graph in memory during validation
for x, y in val_loader:
    output = model(x)
    val_loss += loss.item()
    all_outputs.append(output)  # Keeps entire graph in memory!

# GOOD:
with torch.no_grad():
    all_outputs.append(output.detach().cpu())
```

## Performance Optimization Summary

```
1. Use pin_memory=True + non_blocking transfers
2. Use num_workers > 0 in DataLoader (typically 4-8)
3. Use mixed precision (AMP) for ~2x speedup
4. Use torch.compile() (PyTorch 2.0+) for graph optimization
5. Use gradient accumulation for effective larger batch sizes
6. Profile before optimizing (torch.profiler)
7. Use channels_last memory format for CNNs
8. Set torch.backends.cudnn.benchmark = True (if input size is fixed)
```
