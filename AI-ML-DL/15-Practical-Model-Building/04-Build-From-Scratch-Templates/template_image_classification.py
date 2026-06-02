"""
=============================================================================
TEMPLATE: Image Classification with PyTorch
=============================================================================
A complete, runnable template for image classification.
Uses Fashion-MNIST by default (downloads automatically).

USAGE:
    python template_image_classification.py

MODIFY:
    Search for "MODIFY THIS" to find all customization points.

REQUIREMENTS:
    pip install torch torchvision
=============================================================================
"""

import sys
import os
import time
from pathlib import Path

# ============================================================
# Graceful handling if torch is not installed
# ============================================================
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader
    import torchvision
    import torchvision.transforms as transforms
except ImportError:
    print("ERROR: PyTorch is not installed.")
    print("Install with: pip install torch torchvision")
    print("See: https://pytorch.org/get-started/locally/")
    sys.exit(1)


# ============================================================
# MODIFY THIS: Configuration
# ============================================================
CONFIG = {
    # Model
    "num_classes": 10,          # MODIFY THIS: number of output classes
    "input_channels": 1,        # MODIFY THIS: 1 for grayscale, 3 for RGB
    "image_size": 28,           # MODIFY THIS: input image dimensions

    # Training
    "batch_size": 64,           # MODIFY THIS: reduce if GPU OOM
    "num_epochs": 15,           # MODIFY THIS: more epochs if underfitting
    "learning_rate": 1e-3,      # MODIFY THIS: try 1e-4 if unstable
    "weight_decay": 1e-4,       # L2 regularization

    # Infrastructure
    "num_workers": 2,           # DataLoader workers
    "save_path": "best_model.pth",
    "device": "cuda" if torch.cuda.is_available() else "cpu",
}

print(f"Using device: {CONFIG['device']}")


# ============================================================
# MODIFY THIS: Data Loading and Preprocessing
# ============================================================
def get_data_loaders():
    """
    Load and preprocess data.

    MODIFY THIS FUNCTION to load your own dataset.
    Options:
      - torchvision.datasets.ImageFolder("path/to/data") for directory structure
      - Custom Dataset class for complex loading
      - Replace transforms for your image size/type
    """

    # Transforms for training (with augmentation)
    train_transform = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        # MODIFY THIS: adjust normalization for your data
        # For ImageNet pretrained: mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        transforms.Normalize((0.5,), (0.5,)),  # Fashion-MNIST: single channel
    ])

    # Transforms for validation (NO augmentation)
    val_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,)),
    ])

    # MODIFY THIS: Replace with your dataset
    # For custom images in folders: datasets.ImageFolder("data/train", transform=...)
    train_dataset = torchvision.datasets.FashionMNIST(
        root="./data", train=True, download=True, transform=train_transform
    )
    val_dataset = torchvision.datasets.FashionMNIST(
        root="./data", train=False, download=True, transform=val_transform
    )

    train_loader = DataLoader(
        train_dataset, batch_size=CONFIG["batch_size"],
        shuffle=True, num_workers=CONFIG["num_workers"], pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=CONFIG["batch_size"] * 2,
        shuffle=False, num_workers=CONFIG["num_workers"], pin_memory=True
    )

    # MODIFY THIS: class names for your dataset
    class_names = [
        "T-shirt/top", "Trouser", "Pullover", "Dress", "Coat",
        "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"
    ]

    return train_loader, val_loader, class_names


# ============================================================
# MODIFY THIS: Model Architecture
# ============================================================
class ImageClassifier(nn.Module):
    """
    Simple CNN for image classification.

    MODIFY THIS CLASS for your architecture needs:
    - Add more conv layers for complex images
    - Increase channels for higher resolution
    - Add batch norm, residual connections, etc.
    - Or replace entirely with a pretrained model (see transfer learning cookbook)
    """

    def __init__(self, num_classes, input_channels=1):
        super().__init__()

        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(input_channels, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),

            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),

            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),
        )

        # Calculate flatten size (depends on input image size)
        self._flatten_size = self._get_flatten_size(input_channels)

        self.classifier = nn.Sequential(
            nn.Linear(self._flatten_size, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes),
        )

    def _get_flatten_size(self, input_channels):
        """Calculate the size after conv layers."""
        dummy = torch.zeros(1, input_channels, CONFIG["image_size"], CONFIG["image_size"])
        out = self.features(dummy)
        return out.view(1, -1).size(1)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


# ============================================================
# Training Loop
# ============================================================
def train_one_epoch(model, loader, criterion, optimizer, device):
    """Train for one epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (images, labels) in enumerate(loader):
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    avg_loss = running_loss / len(loader)
    accuracy = 100.0 * correct / total
    return avg_loss, accuracy


def evaluate(model, loader, criterion, device):
    """Evaluate on validation set."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

    avg_loss = running_loss / len(loader)
    accuracy = 100.0 * correct / total
    return avg_loss, accuracy


# ============================================================
# Main Training Script
# ============================================================
def main():
    print("=" * 60)
    print("IMAGE CLASSIFICATION TEMPLATE")
    print("=" * 60)

    # Load data
    print("\n[1/4] Loading data...")
    train_loader, val_loader, class_names = get_data_loaders()
    print(f"  Train batches: {len(train_loader)}")
    print(f"  Val batches:   {len(val_loader)}")
    print(f"  Classes:       {len(class_names)}")

    # Create model
    print("\n[2/4] Creating model...")
    model = ImageClassifier(
        num_classes=CONFIG["num_classes"],
        input_channels=CONFIG["input_channels"],
    ).to(CONFIG["device"])

    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {total_params:,}")

    # Setup training
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(
        model.parameters(),
        lr=CONFIG["learning_rate"],
        weight_decay=CONFIG["weight_decay"],
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=3, verbose=True
    )

    # Train
    print("\n[3/4] Training...")
    print(f"  {'Epoch':<8}{'Train Loss':<12}{'Train Acc':<12}{'Val Loss':<12}{'Val Acc':<12}")
    print("  " + "-" * 54)

    best_val_acc = 0.0
    start_time = time.time()

    for epoch in range(CONFIG["num_epochs"]):
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, CONFIG["device"]
        )
        val_loss, val_acc = evaluate(
            model, val_loader, criterion, CONFIG["device"]
        )
        scheduler.step(val_loss)

        print(f"  {epoch+1:<8}{train_loss:<12.4f}{train_acc:<12.2f}{val_loss:<12.4f}{val_acc:<12.2f}")

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": val_acc,
                "class_names": class_names,
                "config": CONFIG,
            }, CONFIG["save_path"])

    elapsed = time.time() - start_time
    print(f"\n  Training complete in {elapsed:.1f}s")
    print(f"  Best validation accuracy: {best_val_acc:.2f}%")

    # Final evaluation
    print("\n[4/4] Final evaluation...")
    checkpoint = torch.load(CONFIG["save_path"], weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    val_loss, val_acc = evaluate(model, val_loader, criterion, CONFIG["device"])
    print(f"  Best model val accuracy: {val_acc:.2f}%")
    print(f"  Model saved to: {CONFIG['save_path']}")


if __name__ == "__main__":
    main()
