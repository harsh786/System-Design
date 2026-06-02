"""
TRAIN BERT/RoBERTa TEXT CLASSIFIER
===================================
Complete training pipeline from prepared data to saved model.

Usage:
    python train.py                          # Train with defaults (DistilBERT)
    python train.py --model roberta-base     # Use RoBERTa
    python train.py --epochs 5 --lr 2e-5     # Custom hyperparams
    python train.py --batch-size 8           # Smaller batch for less memory
    python train.py --no-gpu                 # Force CPU training
"""

import os
import sys
import json
import time
import argparse

import pandas as pd
import numpy as np

# ============ CHECK DEPENDENCIES ============
try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
    )
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("\nInstall with: pip install -r requirements.txt")
    print("  Required: torch, transformers, datasets, scikit-learn, accelerate")
    sys.exit(1)


# ============ MODEL SELECTION GUIDE ============
MODEL_OPTIONS = {
    "distilbert-base-uncased": "Fastest, good for prototyping (66M params)",
    "bert-base-uncased": "Standard baseline, well-documented (110M params)",
    "roberta-base": "Best accuracy for most tasks (125M params)",
    "microsoft/deberta-v3-base": "State-of-art but slower (183M params)",
}

DATA_DIR = "data"
OUTPUT_DIR = "saved_model"


def parse_args():
    parser = argparse.ArgumentParser(description="Train BERT text classifier")
    parser.add_argument("--model", type=str, default="distilbert-base-uncased",
                        help=f"Model name. Options: {list(MODEL_OPTIONS.keys())}")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs (default: 3, transformers overfit quickly)")
    parser.add_argument("--lr", type=float, default=2e-5,
                        help="Learning rate (default: 2e-5, standard for BERT fine-tuning)")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="Batch size per device (reduce if OOM)")
    parser.add_argument("--max-length", type=int, default=256,
                        help="Max token length (default: 256)")
    parser.add_argument("--warmup-ratio", type=float, default=0.1,
                        help="Warmup ratio (stabilizes early training)")
    parser.add_argument("--weight-decay", type=float, default=0.01,
                        help="Weight decay for regularization")
    parser.add_argument("--grad-accum", type=int, default=2,
                        help="Gradient accumulation steps (effective batch = batch_size * grad_accum)")
    parser.add_argument("--no-gpu", action="store_true", help="Force CPU training")
    parser.add_argument("--fp16", action="store_true", default=True,
                        help="Use mixed precision (2x faster on supported GPUs)")
    parser.add_argument("--data-dir", type=str, default=DATA_DIR)
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR)
    return parser.parse_args()


# ============ LOAD PREPARED DATA ============

def load_prepared_data(data_dir):
    """Load train/val CSVs and label mapping from data_preparation.py output."""
    train_path = os.path.join(data_dir, "train.csv")
    val_path = os.path.join(data_dir, "val.csv")
    mapping_path = os.path.join(data_dir, "label_mapping.json")

    if not os.path.exists(train_path):
        print(f"[ERROR] {train_path} not found. Run data_preparation.py first!")
        sys.exit(1)

    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)

    with open(mapping_path, "r") as f:
        mapping = json.load(f)

    label2id = mapping["label2id"]
    id2label = {int(k): v for k, v in mapping["id2label"].items()}
    num_labels = len(label2id)

    print(f"[OK] Loaded data: {len(train_df)} train, {len(val_df)} val, {num_labels} classes")
    return train_df, val_df, label2id, id2label, num_labels


# ============ TOKENIZATION ============

def tokenize_data(train_df, val_df, model_name, max_length):
    """Tokenize text data into BERT input format."""
    print(f"\n[STEP] Tokenizing with {model_name} tokenizer (max_length={max_length})...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=max_length,
        )

    # Convert pandas to HuggingFace Dataset
    train_dataset = Dataset.from_pandas(train_df[["text", "label_id"]].rename(columns={"label_id": "labels"}))
    val_dataset = Dataset.from_pandas(val_df[["text", "label_id"]].rename(columns={"label_id": "labels"}))

    # Tokenize
    train_dataset = train_dataset.map(tokenize_function, batched=True, desc="Tokenizing train")
    val_dataset = val_dataset.map(tokenize_function, batched=True, desc="Tokenizing val")

    # Set format for PyTorch
    train_dataset.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
    val_dataset.set_format("torch", columns=["input_ids", "attention_mask", "labels"])

    print(f"  Train tokens shape: {len(train_dataset)} samples x {max_length} tokens")
    return tokenizer, train_dataset, val_dataset


# ============ METRICS ============

def compute_metrics(eval_pred):
    """Compute accuracy, F1, precision, recall."""
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1_macro": f1_score(labels, predictions, average="macro"),
        "precision_macro": precision_score(labels, predictions, average="macro"),
        "recall_macro": recall_score(labels, predictions, average="macro"),
    }


# ============ TRAINING ============

def train_model(args):
    """Full training pipeline."""
    start_time = time.time()

    # Load data
    train_df, val_df, label2id, id2label, num_labels = load_prepared_data(args.data_dir)

    # Tokenize
    tokenizer, train_dataset, val_dataset = tokenize_data(
        train_df, val_df, args.model, args.max_length
    )

    # Load pretrained model
    print(f"\n[STEP] Loading model: {args.model} ({MODEL_OPTIONS.get(args.model, 'custom')})")
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
    )

    # Device info
    if args.no_gpu:
        device = "cpu"
    else:
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"  Device: {device}")
    if device == "cpu":
        print("  [NOTE] Training on CPU will be slow. Consider using --model distilbert-base-uncased")

    # Determine fp16 availability
    use_fp16 = args.fp16 and device == "cuda"

    # Training arguments
    training_args = TrainingArguments(
        output_dir=os.path.join(args.output_dir, "checkpoints"),
        # --- Core hyperparameters ---
        num_train_epochs=args.epochs,              # 3 is standard; transformers overfit quickly
        learning_rate=args.lr,                     # 2e-5 is the "magic number" for BERT fine-tuning
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,  # Can use larger batch for eval
        gradient_accumulation_steps=args.grad_accum,     # Effective batch = batch_size * this
        # --- Regularization ---
        warmup_ratio=args.warmup_ratio,            # Warm up LR for first 10% of steps
        weight_decay=args.weight_decay,            # L2 regularization (0.01 is standard)
        # --- Evaluation & Saving ---
        eval_strategy="epoch",                     # Evaluate every epoch
        save_strategy="epoch",                     # Save checkpoint every epoch
        load_best_model_at_end=True,               # Keep best model (by eval_loss)
        metric_for_best_model="f1_macro",          # Use F1 to pick best model
        greater_is_better=True,
        # --- Performance ---
        fp16=use_fp16,                             # Mixed precision (2x faster on GPU)
        dataloader_num_workers=2,
        # --- Logging ---
        logging_steps=50,
        logging_first_step=True,
        report_to="none",                          # Disable wandb/tensorboard
        # --- Device ---
        no_cuda=args.no_gpu,
        use_mps_device=(device == "mps"),
    )

    # Create Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    # Train!
    print(f"\n{'='*60}")
    print(f"  TRAINING START")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}, LR: {args.lr}, Batch: {args.batch_size}")
    print(f"  Effective batch size: {args.batch_size * args.grad_accum}")
    print(f"{'='*60}\n")

    trainer.train()

    # ============ POST-TRAINING ============
    elapsed = time.time() - start_time

    # Evaluate on validation set
    print(f"\n{'='*60}")
    print("  TRAINING COMPLETE")
    print(f"{'='*60}")
    eval_results = trainer.evaluate()
    print(f"\n  Final Validation Metrics:")
    for key, value in eval_results.items():
        if key.startswith("eval_"):
            name = key.replace("eval_", "")
            print(f"    {name:20s}: {value:.4f}")
    print(f"\n  Training time: {elapsed/60:.1f} minutes")

    # Save final model + tokenizer + label mapping
    final_path = args.output_dir
    trainer.save_model(final_path)
    tokenizer.save_pretrained(final_path)

    # Also save label mapping in model directory
    mapping = {"label2id": label2id, "id2label": id2label}
    with open(os.path.join(final_path, "label_mapping.json"), "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"\n[DONE] Model saved to: {final_path}/")
    print(f"[NEXT] Run: python evaluate.py")


# ============ MAIN ============

if __name__ == "__main__":
    args = parse_args()
    print(f"BERT Text Classifier Training")
    print(f"{'='*60}")
    train_model(args)
