"""
TensorFlow Complete Project: Fashion-MNIST Classification
=========================================================

A production-ready TensorFlow/Keras project demonstrating:
- tf.data pipeline with performance optimization
- Custom Keras model using Functional API
- Custom callbacks for logging and scheduling
- Mixed precision training
- Learning rate scheduling with warmup
- Model evaluation with detailed metrics
- SavedModel export
- Inference function

Dataset: Fashion-MNIST (built into keras.datasets)
- 60,000 training images, 10,000 test images
- 28x28 grayscale images, 10 classes

Requirements: tensorflow >= 2.10
"""

from __future__ import annotations

import os
import time
import math
from typing import Optional, Tuple

# Handle missing tensorflow gracefully
try:
    import tensorflow as tf
    import numpy as np
    TF_AVAILABLE = True
except ImportError:
    print("ERROR: TensorFlow is not installed.")
    print("Install with: pip install tensorflow>=2.10")
    print("For GPU support: pip install tensorflow[and-cuda]")
    TF_AVAILABLE = False

# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Centralized configuration for the project."""
    # Data
    BATCH_SIZE = 128
    BUFFER_SIZE = 60000  # Shuffle buffer
    VALIDATION_SPLIT = 0.1
    
    # Model
    NUM_CLASSES = 10
    INPUT_SHAPE = (28, 28, 1)
    DROPOUT_RATE = 0.3
    
    # Training
    EPOCHS = 20
    INITIAL_LR = 1e-3
    WARMUP_EPOCHS = 3
    MIN_LR = 1e-6
    WEIGHT_DECAY = 1e-4
    
    # Mixed precision
    USE_MIXED_PRECISION = True
    
    # Paths
    MODEL_DIR = "saved_model/fashion_mnist"
    LOG_DIR = "logs/fashion_mnist"
    
    # Class names for Fashion-MNIST
    CLASS_NAMES = [
        'T-shirt/top', 'Trouser', 'Pullover', 'Dress', 'Coat',
        'Sandal', 'Shirt', 'Sneaker', 'Bag', 'Ankle boot'
    ]


# ============================================================================
# Data Pipeline
# ============================================================================

def create_data_pipeline(
    images: np.ndarray,
    labels: np.ndarray,
    batch_size: int,
    is_training: bool = True,
    cache: bool = True
) -> tf.data.Dataset:
    """
    Create an optimized tf.data pipeline.
    
    Optimizations applied:
    1. Cache: Store preprocessed data in memory after first epoch
    2. Shuffle: Randomize order for training
    3. Batch: Group samples for parallel processing
    4. Prefetch: Overlap data preparation with model execution
    5. Map with parallel calls: Parallelize augmentation
    """
    # Normalize images to [0, 1] and add channel dimension
    images = images.astype(np.float32) / 255.0
    images = np.expand_dims(images, axis=-1)  # (N, 28, 28) → (N, 28, 28, 1)
    
    dataset = tf.data.Dataset.from_tensor_slices((images, labels))
    
    # Cache before augmentation (raw normalized data)
    if cache:
        dataset = dataset.cache()
    
    if is_training:
        dataset = dataset.shuffle(buffer_size=Config.BUFFER_SIZE)
        # Apply augmentation only during training
        dataset = dataset.map(
            augment_image,
            num_parallel_calls=tf.data.AUTOTUNE
        )
    
    dataset = dataset.batch(batch_size, drop_remainder=is_training)
    dataset = dataset.prefetch(tf.data.AUTOTUNE)
    
    return dataset


def augment_image(image: tf.Tensor, label: tf.Tensor) -> Tuple[tf.Tensor, tf.Tensor]:
    """Apply data augmentation to a single image."""
    # Random horizontal flip
    image = tf.image.random_flip_left_right(image)
    # Random brightness adjustment
    image = tf.image.random_brightness(image, max_delta=0.1)
    # Random contrast
    image = tf.image.random_contrast(image, lower=0.9, upper=1.1)
    # Clip to valid range
    image = tf.clip_by_value(image, 0.0, 1.0)
    return image, label


def load_and_prepare_data() -> Tuple[tf.data.Dataset, tf.data.Dataset, tf.data.Dataset]:
    """Load Fashion-MNIST and create train/val/test datasets."""
    (x_train_full, y_train_full), (x_test, y_test) = tf.keras.datasets.fashion_mnist.load_data()
    
    # Split training into train + validation
    val_size = int(len(x_train_full) * Config.VALIDATION_SPLIT)
    x_val, y_val = x_train_full[:val_size], y_train_full[:val_size]
    x_train, y_train = x_train_full[val_size:], y_train_full[val_size:]
    
    print(f"Training samples:   {len(x_train)}")
    print(f"Validation samples: {len(x_val)}")
    print(f"Test samples:       {len(x_test)}")
    
    train_ds = create_data_pipeline(x_train, y_train, Config.BATCH_SIZE, is_training=True)
    val_ds = create_data_pipeline(x_val, y_val, Config.BATCH_SIZE, is_training=False)
    test_ds = create_data_pipeline(x_test, y_test, Config.BATCH_SIZE, is_training=False)
    
    return train_ds, val_ds, test_ds


# ============================================================================
# Model Definition (Functional API)
# ============================================================================

def residual_block(x: tf.Tensor, filters: int, name: str) -> tf.Tensor:
    """A residual block with two convolutions and a skip connection."""
    shortcut = x
    
    # If dimensions don't match, project shortcut
    if x.shape[-1] != filters:
        shortcut = tf.keras.layers.Conv2D(
            filters, 1, padding='same', name=f'{name}_proj'
        )(shortcut)
        shortcut = tf.keras.layers.BatchNormalization(name=f'{name}_proj_bn')(shortcut)
    
    # First convolution
    x = tf.keras.layers.Conv2D(filters, 3, padding='same', name=f'{name}_conv1')(x)
    x = tf.keras.layers.BatchNormalization(name=f'{name}_bn1')(x)
    x = tf.keras.layers.ReLU(name=f'{name}_relu1')(x)
    
    # Second convolution
    x = tf.keras.layers.Conv2D(filters, 3, padding='same', name=f'{name}_conv2')(x)
    x = tf.keras.layers.BatchNormalization(name=f'{name}_bn2')(x)
    
    # Add skip connection
    x = tf.keras.layers.Add(name=f'{name}_add')([x, shortcut])
    x = tf.keras.layers.ReLU(name=f'{name}_relu2')(x)
    return x


def create_model() -> tf.keras.Model:
    """
    Create a custom CNN with residual connections using the Functional API.
    
    Architecture:
    - Input → Conv → ResBlock(32) → Pool → ResBlock(64) → Pool 
      → ResBlock(128) → GlobalAvgPool → Dense → Output
    """
    inputs = tf.keras.Input(shape=Config.INPUT_SHAPE, name='image_input')
    
    # Initial convolution
    x = tf.keras.layers.Conv2D(32, 3, padding='same', name='initial_conv')(inputs)
    x = tf.keras.layers.BatchNormalization(name='initial_bn')(x)
    x = tf.keras.layers.ReLU(name='initial_relu')(x)
    
    # Residual blocks with progressive downsampling
    x = residual_block(x, 32, name='res_block_1')
    x = tf.keras.layers.MaxPooling2D(2, name='pool_1')(x)  # 28→14
    
    x = residual_block(x, 64, name='res_block_2')
    x = tf.keras.layers.MaxPooling2D(2, name='pool_2')(x)  # 14→7
    
    x = residual_block(x, 128, name='res_block_3')
    
    # Global average pooling (more parameter-efficient than Flatten)
    x = tf.keras.layers.GlobalAveragePooling2D(name='global_avg_pool')(x)
    
    # Classification head
    x = tf.keras.layers.Dense(256, name='fc1')(x)
    x = tf.keras.layers.BatchNormalization(name='fc_bn')(x)
    x = tf.keras.layers.ReLU(name='fc_relu')(x)
    x = tf.keras.layers.Dropout(Config.DROPOUT_RATE, name='dropout')(x)
    
    # Output layer (no softmax - using from_logits=True in loss)
    outputs = tf.keras.layers.Dense(Config.NUM_CLASSES, name='predictions')(x)
    
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name='fashion_mnist_resnet')
    return model


# ============================================================================
# Custom Callbacks
# ============================================================================

class WarmupCosineSchedule(tf.keras.callbacks.Callback):
    """
    Learning rate schedule with linear warmup followed by cosine decay.
    
    - Warmup: LR increases linearly from 0 to initial_lr
    - Cosine: LR decreases following cosine curve to min_lr
    """
    
    def __init__(self, initial_lr: float, warmup_epochs: int,
                 total_epochs: int, min_lr: float = 1e-6):
        super().__init__()
        self.initial_lr = initial_lr
        self.warmup_epochs = warmup_epochs
        self.total_epochs = total_epochs
        self.min_lr = min_lr
        self.history = []
    
    def on_epoch_begin(self, epoch: int, logs=None):
        if epoch < self.warmup_epochs:
            # Linear warmup
            lr = self.initial_lr * (epoch + 1) / self.warmup_epochs
        else:
            # Cosine decay
            progress = (epoch - self.warmup_epochs) / (self.total_epochs - self.warmup_epochs)
            lr = self.min_lr + (self.initial_lr - self.min_lr) * \
                 0.5 * (1.0 + math.cos(math.pi * progress))
        
        self.model.optimizer.learning_rate.assign(lr)
        self.history.append(lr)


class TrainingMonitor(tf.keras.callbacks.Callback):
    """Custom callback that logs detailed training metrics."""
    
    def __init__(self):
        super().__init__()
        self.epoch_start_time = None
    
    def on_epoch_begin(self, epoch: int, logs=None):
        self.epoch_start_time = time.perf_counter()
    
    def on_epoch_end(self, epoch: int, logs=None):
        duration = time.perf_counter() - self.epoch_start_time
        lr = float(self.model.optimizer.learning_rate)
        
        print(f"\n{'─'*60}")
        print(f"  Epoch {epoch+1}/{Config.EPOCHS} | Time: {duration:.1f}s | LR: {lr:.2e}")
        print(f"  Train Loss: {logs['loss']:.4f} | Train Acc: {logs['accuracy']:.4f}")
        if 'val_loss' in logs:
            print(f"  Val Loss:   {logs['val_loss']:.4f} | Val Acc:   {logs['val_accuracy']:.4f}")
        print(f"{'─'*60}")


# ============================================================================
# Training
# ============================================================================

def train_model(
    model: tf.keras.Model,
    train_ds: tf.data.Dataset,
    val_ds: tf.data.Dataset
) -> tf.keras.callbacks.History:
    """Train the model with all optimizations."""
    
    # Compile model
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(
            learning_rate=Config.INITIAL_LR,
            weight_decay=Config.WEIGHT_DECAY
        ),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy']
    )
    
    # Print model summary
    model.summary()
    
    # Setup callbacks
    callbacks = [
        WarmupCosineSchedule(
            initial_lr=Config.INITIAL_LR,
            warmup_epochs=Config.WARMUP_EPOCHS,
            total_epochs=Config.EPOCHS,
            min_lr=Config.MIN_LR
        ),
        TrainingMonitor(),
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True,
            verbose=1
        ),
        tf.keras.callbacks.TensorBoard(
            log_dir=Config.LOG_DIR,
            histogram_freq=1,
            profile_batch='5,10'  # Profile batches 5-10
        ),
    ]
    
    # Train
    print("\n" + "="*60)
    print("  Starting Training")
    print("="*60)
    
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=Config.EPOCHS,
        callbacks=callbacks,
        verbose=0  # We use our custom callback for output
    )
    
    return history


# ============================================================================
# Evaluation
# ============================================================================

def evaluate_model(model: tf.keras.Model, test_ds: tf.data.Dataset) -> None:
    """Evaluate model with detailed per-class metrics."""
    print("\n" + "="*60)
    print("  Model Evaluation")
    print("="*60)
    
    # Overall metrics
    results = model.evaluate(test_ds, verbose=0)
    print(f"\n  Test Loss:     {results[0]:.4f}")
    print(f"  Test Accuracy: {results[1]:.4f}")
    
    # Per-class predictions
    all_predictions = []
    all_labels = []
    
    for images, labels in test_ds:
        logits = model(images, training=False)
        predictions = tf.argmax(logits, axis=-1)
        all_predictions.extend(predictions.numpy())
        all_labels.extend(labels.numpy())
    
    all_predictions = np.array(all_predictions)
    all_labels = np.array(all_labels)
    
    # Per-class accuracy
    print(f"\n  {'Class':<15} {'Accuracy':>10} {'Count':>8}")
    print(f"  {'─'*35}")
    for i, name in enumerate(Config.CLASS_NAMES):
        mask = all_labels == i
        class_acc = np.mean(all_predictions[mask] == i)
        count = np.sum(mask)
        print(f"  {name:<15} {class_acc:>9.1%} {count:>8}")
    
    # Confusion matrix summary (most confused pairs)
    print(f"\n  Most Confused Pairs:")
    confusion = np.zeros((Config.NUM_CLASSES, Config.NUM_CLASSES), dtype=np.int32)
    for true, pred in zip(all_labels, all_predictions):
        confusion[true][pred] += 1
    
    # Find off-diagonal maximums
    np.fill_diagonal(confusion, 0)
    for _ in range(5):
        idx = np.unravel_index(np.argmax(confusion), confusion.shape)
        true_name = Config.CLASS_NAMES[idx[0]]
        pred_name = Config.CLASS_NAMES[idx[1]]
        count = confusion[idx]
        if count > 0:
            print(f"    {true_name} → {pred_name}: {count} misclassifications")
        confusion[idx] = 0


# ============================================================================
# Export and Inference
# ============================================================================

def export_model(model: tf.keras.Model, export_dir: str) -> None:
    """Export model as SavedModel for TF Serving."""
    print(f"\n  Exporting model to: {export_dir}")
    
    # Define serving signature with explicit input spec
    @tf.function(input_signature=[
        tf.TensorSpec(shape=[None, 28, 28, 1], dtype=tf.float32, name='image')
    ])
    def serving_fn(image):
        logits = model(image, training=False)
        probabilities = tf.nn.softmax(logits, axis=-1)
        predicted_class = tf.argmax(probabilities, axis=-1)
        return {
            'probabilities': probabilities,
            'predicted_class': predicted_class,
            'logits': logits
        }
    
    # Save with serving signature
    tf.saved_model.save(
        model,
        export_dir,
        signatures={'serving_default': serving_fn}
    )
    
    # Verify saved model
    loaded = tf.saved_model.load(export_dir)
    print(f"  Model saved successfully.")
    print(f"  Signatures: {list(loaded.signatures.keys())}")
    
    # Print model size
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(export_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    print(f"  Model size: {total_size / 1024 / 1024:.2f} MB")


def run_inference(model_dir: str, images: np.ndarray) -> dict:
    """
    Run inference using a saved model.
    
    Args:
        model_dir: Path to SavedModel directory
        images: Numpy array of shape (N, 28, 28, 1), float32, range [0, 1]
    
    Returns:
        Dictionary with 'probabilities', 'predicted_class', 'logits'
    """
    loaded_model = tf.saved_model.load(model_dir)
    infer = loaded_model.signatures['serving_default']
    
    # Run inference
    input_tensor = tf.constant(images, dtype=tf.float32)
    results = infer(image=input_tensor)
    
    return {
        'probabilities': results['probabilities'].numpy(),
        'predicted_class': results['predicted_class'].numpy(),
        'logits': results['logits'].numpy()
    }


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the complete training pipeline."""
    if not TF_AVAILABLE:
        return
    
    print(f"TensorFlow version: {tf.__version__}")
    print(f"GPU available: {len(tf.config.list_physical_devices('GPU')) > 0}")
    
    # Configure GPU memory growth
    gpus = tf.config.list_physical_devices('GPU')
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)
        print(f"  GPU: {gpu.name}")
    
    # Enable mixed precision if configured and GPU available
    if Config.USE_MIXED_PRECISION and gpus:
        tf.keras.mixed_precision.set_global_policy('mixed_float16')
        print("  Mixed precision: enabled (float16 compute, float32 variables)")
    
    # Step 1: Load data
    print("\n[1/5] Loading and preparing data...")
    train_ds, val_ds, test_ds = load_and_prepare_data()
    
    # Step 2: Create model
    print("\n[2/5] Creating model...")
    model = create_model()
    
    # Step 3: Train
    print("\n[3/5] Training model...")
    history = train_model(model, train_ds, val_ds)
    
    # Step 4: Evaluate
    print("\n[4/5] Evaluating model...")
    evaluate_model(model, test_ds)
    
    # Step 5: Export
    print("\n[5/5] Exporting model...")
    export_model(model, Config.MODEL_DIR)
    
    # Demo inference
    print("\n" + "="*60)
    print("  Inference Demo")
    print("="*60)
    
    # Load a few test images
    (_, _), (x_test, y_test) = tf.keras.datasets.fashion_mnist.load_data()
    sample_images = x_test[:5].astype(np.float32) / 255.0
    sample_images = np.expand_dims(sample_images, axis=-1)
    
    results = run_inference(Config.MODEL_DIR, sample_images)
    
    for i in range(5):
        pred_class = results['predicted_class'][i]
        confidence = results['probabilities'][i][pred_class]
        true_class = y_test[i]
        correct = "✓" if pred_class == true_class else "✗"
        print(f"  {correct} True: {Config.CLASS_NAMES[true_class]:<15} "
              f"Pred: {Config.CLASS_NAMES[pred_class]:<15} "
              f"Conf: {confidence:.1%}")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
