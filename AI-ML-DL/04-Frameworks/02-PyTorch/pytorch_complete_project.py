"""
PyTorch Complete Project: Image Classification on Fashion-MNIST
==============================================================

A production-ready training pipeline demonstrating best practices:
- Custom Dataset with augmentation
- ResNet-like model built from scratch
- Mixed precision training
- Cosine annealing LR schedule
- Gradient clipping
- Model checkpointing
- Evaluation with confusion matrix
- Model export and inference

Requirements: torch, torchvision
Run: python pytorch_complete_project.py

Author: Learning Reference
"""

import os
import sys
import time
import math
from pathlib import Path

# Graceful handling if PyTorch is not installed
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.utils.data import DataLoader, Dataset, random_split
    from torch.cuda.amp import autocast, GradScaler
    import torchvision
    import torchvision.transforms as transforms
except ImportError:
    print("=" * 60)
    print("PyTorch and/or torchvision not installed.")
    print("Install with: pip install torch torchvision")
    print("=" * 60)
    sys.exit(0)


# ==============================================================================
# Configuration
# ==============================================================================

class Config:
    """
    Centralized configuration. Using a class instead of scattered constants
    makes it easy to modify, serialize, and pass around.
    """
    # Data
    data_dir = "./data"
    num_classes = 10
    image_size = 32  # We'll resize Fashion-MNIST from 28x28 to 32x32 for ResNet compatibility
    
    # Training
    batch_size = 128
    num_epochs = 15
    learning_rate = 1e-3
    weight_decay = 1e-4
    gradient_clip_max_norm = 1.0
    
    # Architecture
    num_residual_blocks = [2, 2, 2]  # Blocks per stage (like ResNet-14)
    channels = [64, 128, 256]
    
    # System
    device = "cuda" if torch.cuda.is_available() else "cpu"
    num_workers = 2 if sys.platform != "win32" else 0  # Windows multiprocessing issues
    use_amp = torch.cuda.is_available()  # Mixed precision only on GPU
    
    # Checkpointing
    checkpoint_dir = "./checkpoints"
    
    # Class names for Fashion-MNIST
    class_names = [
        "T-shirt/top", "Trouser", "Pullover", "Dress", "Coat",
        "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"
    ]


# ==============================================================================
# Data Pipeline
# ==============================================================================

def get_transforms(train=True):
    """
    Data augmentation strategy:
    - Training: Random crops, horizontal flips, slight rotation, normalization
    - Validation: Only resize and normalize
    
    WHY these augmentations:
    - RandomCrop with padding: simulates translation invariance
    - HorizontalFlip: clothing looks same when mirrored
    - RandomRotation: slight rotation invariance
    - Normalization: centers data, helps optimization converge
    """
    if train:
        return transforms.Compose([
            transforms.Resize(Config.image_size),
            transforms.RandomCrop(Config.image_size, padding=4),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=10),
            transforms.ToTensor(),
            # Fashion-MNIST is grayscale; these are approximate mean/std
            transforms.Normalize(mean=[0.2860], std=[0.3530]),
        ])
    else:
        return transforms.Compose([
            transforms.Resize(Config.image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.2860], std=[0.3530]),
        ])


def get_dataloaders():
    """
    Load Fashion-MNIST and create train/val/test splits.
    
    WHY Fashion-MNIST over MNIST:
    - More challenging (clothing vs digits)
    - Same format, drop-in replacement
    - Better benchmark for architecture comparisons
    """
    train_dataset = torchvision.datasets.FashionMNIST(
        root=Config.data_dir,
        train=True,
        download=True,
        transform=get_transforms(train=True),
    )
    
    test_dataset = torchvision.datasets.FashionMNIST(
        root=Config.data_dir,
        train=False,
        download=True,
        transform=get_transforms(train=False),
    )
    
    # Split training into train (90%) and validation (10%)
    # WHY: We need val set to monitor overfitting without touching test set
    train_size = int(0.9 * len(train_dataset))
    val_size = len(train_dataset) - train_size
    train_subset, val_subset = random_split(
        train_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42)  # Reproducible split
    )
    
    train_loader = DataLoader(
        train_subset,
        batch_size=Config.batch_size,
        shuffle=True,
        num_workers=Config.num_workers,
        pin_memory=True,  # Faster CPU->GPU transfer
        drop_last=True,   # Avoid small last batch (helps BatchNorm stability)
    )
    
    val_loader = DataLoader(
        val_subset,
        batch_size=Config.batch_size * 2,  # Can use larger batch for eval (no gradients stored)
        shuffle=False,
        num_workers=Config.num_workers,
        pin_memory=True,
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=Config.batch_size * 2,
        shuffle=False,
        num_workers=Config.num_workers,
        pin_memory=True,
    )
    
    print(f"Train: {len(train_subset)}, Val: {len(val_subset)}, Test: {len(test_dataset)}")
    return train_loader, val_loader, test_loader


# ==============================================================================
# Model Architecture
# ==============================================================================

class ResidualBlock(nn.Module):
    """
    Basic residual block with skip connection.
    
    WHY residual connections:
    - Solves vanishing gradient problem in deep networks
    - Enables training of much deeper models
    - Identity shortcut means the block only needs to learn the RESIDUAL
    
    Architecture: Conv -> BN -> ReLU -> Conv -> BN -> (+skip) -> ReLU
    """
    
    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        
        self.conv1 = nn.Conv2d(
            in_channels, out_channels, kernel_size=3,
            stride=stride, padding=1, bias=False  # bias=False because BN has its own bias
        )
        self.bn1 = nn.BatchNorm2d(out_channels)
        
        self.conv2 = nn.Conv2d(
            out_channels, out_channels, kernel_size=3,
            stride=1, padding=1, bias=False
        )
        self.bn2 = nn.BatchNorm2d(out_channels)
        
        # Skip connection: if dimensions change, use 1x1 conv to match
        self.skip = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.skip = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )
    
    def forward(self, x):
        identity = self.skip(x)
        
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += identity  # Residual addition
        out = F.relu(out)
        
        return out


class ResNetSmall(nn.Module):
    """
    Small ResNet-like model for 32x32 grayscale images.
    
    Architecture:
        Input (1x32x32)
        -> Conv 3x3 (64 channels)
        -> Stage 1: 2 ResBlocks (64 channels, 32x32)
        -> Stage 2: 2 ResBlocks (128 channels, 16x16)  [stride=2 downsamples]
        -> Stage 3: 2 ResBlocks (256 channels, 8x8)    [stride=2 downsamples]
        -> Global Average Pooling (256x1x1)
        -> FC (256 -> 10)
    
    WHY this architecture:
    - Small enough to train quickly on CPU/single GPU
    - Deep enough to benefit from residual connections
    - Global avg pool instead of FC: reduces parameters, less overfitting
    """
    
    def __init__(self, num_classes=10):
        super().__init__()
        
        # Initial convolution
        # WHY kernel=3 instead of 7: input is only 32x32, large kernel would lose too much info
        self.conv1 = nn.Conv2d(1, 64, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        
        # Residual stages
        self.stage1 = self._make_stage(64, Config.channels[0], Config.num_residual_blocks[0], stride=1)
        self.stage2 = self._make_stage(Config.channels[0], Config.channels[1], Config.num_residual_blocks[1], stride=2)
        self.stage3 = self._make_stage(Config.channels[1], Config.channels[2], Config.num_residual_blocks[2], stride=2)
        
        # Classification head
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(0.2)  # WHY: regularization to prevent overfitting
        self.fc = nn.Linear(Config.channels[2], num_classes)
        
        # Weight initialization
        # WHY Kaiming: designed for ReLU networks, maintains variance through layers
        self._initialize_weights()
    
    def _make_stage(self, in_channels, out_channels, num_blocks, stride):
        """Create a stage of residual blocks. First block may downsample."""
        layers = [ResidualBlock(in_channels, out_channels, stride)]
        for _ in range(1, num_blocks):
            layers.append(ResidualBlock(out_channels, out_channels, stride=1))
        return nn.Sequential(*layers)
    
    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight)
                nn.init.constant_(m.bias, 0)
    
    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.stage1(x)
        x = self.stage2(x)
        x = self.stage3(x)
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)  # Flatten
        x = self.dropout(x)
        x = self.fc(x)
        return x


# ==============================================================================
# Training Engine
# ==============================================================================

class Trainer:
    """
    Encapsulates the training loop with all best practices.
    
    WHY a class:
    - Groups related state (model, optimizer, scaler, best_acc)
    - Easy to save/restore training state
    - Clean interface for train/eval/export
    """
    
    def __init__(self, model, train_loader, val_loader, config=Config):
        self.model = model.to(config.device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = config
        self.device = config.device
        
        # Optimizer: AdamW (Adam with decoupled weight decay)
        # WHY AdamW over Adam: proper L2 regularization, better generalization
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
        
        # LR Scheduler: Cosine Annealing
        # WHY cosine: smooth decay, no need to tune step milestones, proven effective
        self.scheduler = optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=config.num_epochs,
            eta_min=1e-6,  # Don't let LR go to exactly 0
        )
        
        # Loss function
        self.criterion = nn.CrossEntropyLoss()
        
        # Mixed precision scaler
        # WHY: ~2x speedup on modern GPUs (Volta+), half memory for activations
        self.scaler = GradScaler(enabled=config.use_amp)
        
        # Tracking
        self.best_val_acc = 0.0
        self.train_losses = []
        self.val_accuracies = []
        
        # Create checkpoint directory
        Path(config.checkpoint_dir).mkdir(parents=True, exist_ok=True)
    
    def train_one_epoch(self, epoch):
        """Train for one epoch, return average loss."""
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        for batch_idx, (inputs, targets) in enumerate(self.train_loader):
            inputs = inputs.to(self.device, non_blocking=True)
            targets = targets.to(self.device, non_blocking=True)
            
            # Zero gradients
            # WHY set_to_none=True: slightly faster than zero_grad(), sets .grad to None instead of zero tensor
            self.optimizer.zero_grad(set_to_none=True)
            
            # Forward pass with mixed precision
            with autocast(enabled=self.config.use_amp):
                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)
            
            # Backward pass
            self.scaler.scale(loss).backward()
            
            # Gradient clipping (unscale first for correct norm computation)
            # WHY clip: prevents exploding gradients, stabilizes training
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                max_norm=self.config.gradient_clip_max_norm
            )
            
            # Optimizer step
            self.scaler.step(self.optimizer)
            self.scaler.update()
            
            total_loss += loss.item()
            num_batches += 1
        
        avg_loss = total_loss / num_batches
        self.train_losses.append(avg_loss)
        return avg_loss
    
    @torch.no_grad()
    def evaluate(self, loader):
        """Evaluate model, return accuracy and per-class accuracy."""
        self.model.eval()
        correct = 0
        total = 0
        class_correct = [0] * self.config.num_classes
        class_total = [0] * self.config.num_classes
        
        for inputs, targets in loader:
            inputs = inputs.to(self.device, non_blocking=True)
            targets = targets.to(self.device, non_blocking=True)
            
            with autocast(enabled=self.config.use_amp):
                outputs = self.model(inputs)
            
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
            
            # Per-class accuracy
            for i in range(targets.size(0)):
                label = targets[i].item()
                class_total[label] += 1
                if predicted[i] == label:
                    class_correct[label] += 1
        
        accuracy = 100.0 * correct / total
        per_class_acc = {
            Config.class_names[i]: 100.0 * class_correct[i] / max(class_total[i], 1)
            for i in range(self.config.num_classes)
        }
        
        return accuracy, per_class_acc
    
    def save_checkpoint(self, epoch, accuracy, is_best=False):
        """
        Save training state for resumption.
        
        WHY save optimizer and scheduler state:
        - Allows resuming training exactly where we left off
        - Optimizer has momentum buffers; scheduler has step count
        """
        state = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'scaler_state_dict': self.scaler.state_dict(),
            'best_val_acc': self.best_val_acc,
            'accuracy': accuracy,
        }
        
        path = os.path.join(self.config.checkpoint_dir, 'last.pt')
        torch.save(state, path)
        
        if is_best:
            best_path = os.path.join(self.config.checkpoint_dir, 'best.pt')
            torch.save(state, best_path)
            print(f"  ★ New best model saved! Accuracy: {accuracy:.2f}%")
    
    def train(self):
        """Full training loop."""
        print(f"\nTraining on {self.device}")
        print(f"Mixed precision: {self.config.use_amp}")
        print(f"Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")
        print("-" * 60)
        
        for epoch in range(self.config.num_epochs):
            start_time = time.time()
            
            # Train
            train_loss = self.train_one_epoch(epoch)
            
            # Evaluate
            val_acc, per_class_acc = self.evaluate(self.val_loader)
            self.val_accuracies.append(val_acc)
            
            # Step scheduler (after epoch, not after each batch for CosineAnnealing)
            self.scheduler.step()
            
            # Checkpoint
            is_best = val_acc > self.best_val_acc
            if is_best:
                self.best_val_acc = val_acc
            self.save_checkpoint(epoch, val_acc, is_best=is_best)
            
            # Logging
            elapsed = time.time() - start_time
            lr = self.optimizer.param_groups[0]['lr']
            print(
                f"Epoch {epoch+1:3d}/{self.config.num_epochs} | "
                f"Loss: {train_loss:.4f} | "
                f"Val Acc: {val_acc:.2f}% | "
                f"LR: {lr:.6f} | "
                f"Time: {elapsed:.1f}s"
            )
        
        print("-" * 60)
        print(f"Best validation accuracy: {self.best_val_acc:.2f}%")
        return self.best_val_acc


# ==============================================================================
# Evaluation and Confusion Matrix
# ==============================================================================

@torch.no_grad()
def compute_confusion_matrix(model, loader, device, num_classes=10):
    """
    Compute confusion matrix.
    
    WHY confusion matrix:
    - Shows WHICH classes are confused with each other
    - Reveals if model has systematic biases
    - More informative than single accuracy number
    """
    model.eval()
    matrix = torch.zeros(num_classes, num_classes, dtype=torch.int64)
    
    for inputs, targets in loader:
        inputs = inputs.to(device)
        outputs = model(inputs)
        _, predicted = outputs.max(1)
        
        for t, p in zip(targets, predicted.cpu()):
            matrix[t.long(), p.long()] += 1
    
    return matrix


def print_confusion_matrix(matrix, class_names):
    """Pretty-print confusion matrix."""
    print("\nConfusion Matrix:")
    print("-" * 80)
    
    # Header
    header = f"{'True\\Pred':<12}"
    for name in class_names:
        header += f"{name[:6]:>7}"
    print(header)
    print("-" * 80)
    
    # Rows
    for i, name in enumerate(class_names):
        row = f"{name:<12}"
        for j in range(len(class_names)):
            val = matrix[i, j].item()
            row += f"{val:>7}"
        # Add row accuracy
        row_total = matrix[i].sum().item()
        row_acc = 100.0 * matrix[i, i].item() / max(row_total, 1)
        row += f"  | {row_acc:.1f}%"
        print(row)
    
    print("-" * 80)
    total_correct = matrix.diag().sum().item()
    total = matrix.sum().item()
    print(f"Overall Accuracy: {100.0 * total_correct / total:.2f}%")


# ==============================================================================
# Model Export
# ==============================================================================

def export_model(model, device, export_dir="./exported_models"):
    """
    Export model in multiple formats for deployment.
    
    WHY multiple formats:
    - TorchScript: deploy to C++/mobile without Python
    - ONNX: framework-agnostic, use with TensorRT/ONNX Runtime
    """
    Path(export_dir).mkdir(parents=True, exist_ok=True)
    model.eval()
    
    dummy_input = torch.randn(1, 1, Config.image_size, Config.image_size).to(device)
    
    # TorchScript export via tracing
    try:
        traced = torch.jit.trace(model, dummy_input)
        trace_path = os.path.join(export_dir, "model_traced.pt")
        traced.save(trace_path)
        print(f"TorchScript model saved to: {trace_path}")
    except Exception as e:
        print(f"TorchScript export failed: {e}")
    
    # ONNX export
    try:
        onnx_path = os.path.join(export_dir, "model.onnx")
        torch.onnx.export(
            model,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=11,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}},
        )
        print(f"ONNX model saved to: {onnx_path}")
    except Exception as e:
        print(f"ONNX export failed: {e}")


# ==============================================================================
# Inference
# ==============================================================================

def predict(model, image_tensor, device):
    """
    Run inference on a single image.
    
    Args:
        model: trained model
        image_tensor: preprocessed image tensor (1, 1, 32, 32)
        device: torch device
    
    Returns:
        predicted class name, confidence score, all probabilities
    """
    model.eval()
    with torch.inference_mode():  # Fastest inference mode
        image_tensor = image_tensor.to(device)
        if image_tensor.dim() == 3:
            image_tensor = image_tensor.unsqueeze(0)  # Add batch dim
        
        output = model(image_tensor)
        probabilities = F.softmax(output, dim=1)
        confidence, predicted_idx = probabilities.max(1)
        
        predicted_class = Config.class_names[predicted_idx.item()]
        return predicted_class, confidence.item(), probabilities[0].cpu()


# ==============================================================================
# Main
# ==============================================================================

def main():
    """Main entry point — orchestrates the full pipeline."""
    
    # Reproducibility
    # WHY: Ensures results are reproducible across runs
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
        # WHY False: deterministic algorithms are slower, only for debugging
        torch.backends.cudnn.deterministic = False
        # WHY True: allows cuDNN to find optimal algorithm for fixed input sizes
        torch.backends.cudnn.benchmark = True
    
    print("=" * 60)
    print("PyTorch Complete Project: Fashion-MNIST Classification")
    print(f"PyTorch version: {torch.__version__}")
    print(f"Device: {Config.device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print("=" * 60)
    
    # Data
    print("\n[1/5] Loading data...")
    train_loader, val_loader, test_loader = get_dataloaders()
    
    # Model
    print("\n[2/5] Building model...")
    model = ResNetSmall(num_classes=Config.num_classes)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    # Train
    print("\n[3/5] Training...")
    trainer = Trainer(model, train_loader, val_loader)
    trainer.train()
    
    # Load best model for evaluation
    best_ckpt = torch.load(
        os.path.join(Config.checkpoint_dir, 'best.pt'),
        map_location=Config.device,
        weights_only=False,
    )
    model.load_state_dict(best_ckpt['model_state_dict'])
    model = model.to(Config.device)
    
    # Test evaluation
    print("\n[4/5] Evaluating on test set...")
    test_acc, per_class_acc = trainer.evaluate(test_loader)
    print(f"Test Accuracy: {test_acc:.2f}%")
    print("\nPer-class accuracy:")
    for cls_name, acc in per_class_acc.items():
        print(f"  {cls_name:<12}: {acc:.1f}%")
    
    # Confusion matrix
    conf_matrix = compute_confusion_matrix(model, test_loader, Config.device)
    print_confusion_matrix(conf_matrix, Config.class_names)
    
    # Export
    print("\n[5/5] Exporting model...")
    export_model(model, Config.device)
    
    # Demo inference
    print("\n" + "=" * 60)
    print("Demo Inference:")
    sample_input, sample_target = next(iter(test_loader))
    pred_class, confidence, probs = predict(model, sample_input[0], Config.device)
    true_class = Config.class_names[sample_target[0].item()]
    print(f"  True: {true_class}")
    print(f"  Predicted: {pred_class} (confidence: {confidence:.4f})")
    print("=" * 60)
    print("\nDone!")


if __name__ == "__main__":
    main()
