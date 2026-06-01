"""
Image Classification with CNN - PyTorch on CIFAR-10
====================================================
Demonstrates: CNN architecture, data augmentation, training loop, evaluation.
"""

import logging
import time
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 128
EPOCHS = 10
LEARNING_RATE = 0.001
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
CLASSES = ("plane", "car", "bird", "cat", "deer", "dog", "frog", "horse", "ship", "truck")


def get_data_loaders() -> Tuple[DataLoader, DataLoader]:
    """Create train and test data loaders with augmentation."""
    logger.info("Loading CIFAR-10 dataset...")

    train_transform = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.RandomCrop(32, padding=4),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])

    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])

    train_set = datasets.CIFAR10(root="./data", train=True, download=True, transform=train_transform)
    test_set = datasets.CIFAR10(root="./data", train=False, download=True, transform=test_transform)

    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    test_loader = DataLoader(test_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    logger.info(f"Train: {len(train_set)}, Test: {len(test_set)}")
    return train_loader, test_loader


class CIFAR10CNN(nn.Module):
    """CNN for CIFAR-10 classification."""

    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            # Block 1: 3 -> 32 channels
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),

            # Block 2: 32 -> 64 channels
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),

            # Block 3: 64 -> 128 channels
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(0.25),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, 10),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.classifier(x)
        return x


def train_one_epoch(
    model: nn.Module, loader: DataLoader, criterion: nn.Module,
    optimizer: optim.Optimizer, epoch: int
) -> Tuple[float, float]:
    """Train for one epoch, return (loss, accuracy)."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for inputs, labels in loader:
        inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * inputs.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    return running_loss / total, 100.0 * correct / total


def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module) -> Tuple[float, float]:
    """Evaluate model, return (loss, accuracy)."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for inputs, labels in loader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * inputs.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

    return running_loss / total, 100.0 * correct / total


def per_class_accuracy(model: nn.Module, loader: DataLoader) -> Dict[str, float]:
    """Compute per-class accuracy."""
    class_correct = [0.0] * 10
    class_total = [0.0] * 10

    model.eval()
    with torch.no_grad():
        for inputs, labels in loader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            outputs = model(inputs)
            _, predicted = outputs.max(1)
            for i in range(labels.size(0)):
                label = labels[i].item()
                class_total[label] += 1
                if predicted[i] == label:
                    class_correct[label] += 1

    return {CLASSES[i]: 100.0 * class_correct[i] / max(class_total[i], 1) for i in range(10)}


def main() -> None:
    """Run the complete image classification pipeline."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      IMAGE CLASSIFICATION - CNN on CIFAR-10             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\nDevice: {DEVICE}")

    # Data
    train_loader, test_loader = get_data_loaders()

    # Model
    model = CIFAR10CNN().to(DEVICE)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,}")

    # Training setup
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    # Training loop
    print(f"\n{'Epoch':>5} {'Train Loss':>11} {'Train Acc':>10} {'Test Loss':>10} {'Test Acc':>9} {'Time':>6}")
    print("-" * 55)

    best_acc = 0.0
    for epoch in range(1, EPOCHS + 1):
        start = time.time()
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, epoch)
        test_loss, test_acc = evaluate(model, test_loader, criterion)
        scheduler.step()
        elapsed = time.time() - start

        marker = " *" if test_acc > best_acc else ""
        best_acc = max(best_acc, test_acc)
        print(f"{epoch:>5d} {train_loss:>11.4f} {train_acc:>9.2f}% {test_loss:>10.4f} {test_acc:>8.2f}%{marker} {elapsed:>5.1f}s")

    # Per-class results
    print(f"\n{'=' * 40}")
    print(f"Best Test Accuracy: {best_acc:.2f}%")
    print(f"{'=' * 40}")
    print("\nPer-class Accuracy:")
    class_acc = per_class_accuracy(model, test_loader)
    for cls, acc in sorted(class_acc.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(acc / 5)
        print(f"  {cls:>8s}: {acc:5.1f}% {bar}")

    print("\n✅ Training complete!")


if __name__ == "__main__":
    main()
