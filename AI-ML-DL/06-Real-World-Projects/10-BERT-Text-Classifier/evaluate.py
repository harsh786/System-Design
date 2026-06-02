"""
EVALUATE TRAINED MODEL
======================
Generates detailed evaluation report:
- Per-class precision/recall/F1
- Confusion matrix (ASCII)
- Error analysis (worst predictions)
- Confidence distribution

Usage:
    python evaluate.py                          # Evaluate with defaults
    python evaluate.py --model-dir saved_model  # Custom model path
"""

import os
import sys
import json
import argparse

import pandas as pd
import numpy as np

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from sklearn.metrics import classification_report, confusion_matrix
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Install with: pip install -r requirements.txt")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate trained model")
    parser.add_argument("--model-dir", type=str, default="saved_model")
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--output", type=str, default="evaluation_report.txt")
    return parser.parse_args()


def load_model_and_data(args):
    """Load saved model, tokenizer, test data."""
    # Load label mapping
    mapping_path = os.path.join(args.model_dir, "label_mapping.json")
    with open(mapping_path, "r") as f:
        mapping = json.load(f)
    id2label = {int(k): v for k, v in mapping["id2label"].items()}

    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir)
    model.eval()

    # Load test data
    test_df = pd.read_csv(os.path.join(args.data_dir, "test.csv"))
    print(f"[OK] Loaded model from {args.model_dir}")
    print(f"[OK] Test set: {len(test_df)} samples, {len(id2label)} classes")

    return model, tokenizer, test_df, id2label


def get_predictions(model, tokenizer, texts, max_length, batch_size):
    """Get predictions with probabilities for all texts."""
    all_probs = []
    device = next(model.parameters()).device

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        inputs = tokenizer(
            batch_texts, padding=True, truncation=True,
            max_length=max_length, return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            all_probs.append(probs.cpu().numpy())

    return np.concatenate(all_probs, axis=0)


def print_confusion_matrix(y_true, y_pred, labels):
    """Print ASCII confusion matrix."""
    cm = confusion_matrix(y_true, y_pred)
    n = len(labels)

    # Header
    max_label_len = max(len(l) for l in labels)
    header = " " * (max_label_len + 2) + "  ".join(f"{l[:6]:>6}" for l in labels)
    print(f"\n  Confusion Matrix (rows=true, cols=predicted):")
    print(f"  {header}")

    for i in range(n):
        row = f"  {labels[i]:<{max_label_len}}  "
        for j in range(n):
            val = cm[i][j]
            if i == j:
                row += f"{val:>6}  "  # Diagonal (correct)
            elif val > 0:
                row += f"*{val:>5}  "  # Errors marked with *
            else:
                row += f"{'·':>6}  "
        print(row)

    return cm


def error_analysis(test_df, probs, y_pred, id2label, top_n=10):
    """Show most confident wrong predictions."""
    texts = test_df["text"].tolist()
    y_true = test_df["label_id"].tolist()

    errors = []
    for i in range(len(texts)):
        if y_pred[i] != y_true[i]:
            confidence = probs[i][y_pred[i]]
            errors.append({
                "text": texts[i][:80],
                "true": id2label[y_true[i]],
                "predicted": id2label[y_pred[i]],
                "confidence": confidence,
            })

    # Sort by confidence (most confident errors first - these are worst)
    errors.sort(key=lambda x: x["confidence"], reverse=True)

    print(f"\n  Top {top_n} Most Confident WRONG Predictions:")
    print(f"  {'─'*80}")
    for err in errors[:top_n]:
        print(f"  [{err['confidence']:.2f}] True: {err['true']:<15} Pred: {err['predicted']:<15}")
        print(f"         \"{err['text']}...\"")

    return errors


def confidence_analysis(probs, y_true, y_pred):
    """Analyze prediction confidence distribution."""
    max_probs = np.max(probs, axis=1)
    correct = np.array(y_pred) == np.array(y_true)

    print(f"\n  Confidence Distribution:")
    brackets = [(0.9, 1.0), (0.7, 0.9), (0.5, 0.7), (0.0, 0.5)]
    for low, high in brackets:
        mask = (max_probs >= low) & (max_probs < high)
        count = mask.sum()
        if count > 0:
            acc = correct[mask].mean()
            print(f"    Confidence {low:.1f}-{high:.1f}: {count:4d} samples, accuracy: {acc:.2%}")


def main():
    args = parse_args()
    print("BERT Text Classifier Evaluation")
    print("=" * 60)

    model, tokenizer, test_df, id2label = load_model_and_data(args)

    # Get predictions
    texts = test_df["text"].tolist()
    y_true = test_df["label_id"].tolist()
    labels = [id2label[i] for i in range(len(id2label))]

    print("\n[STEP] Running predictions...")
    probs = get_predictions(model, tokenizer, texts, args.max_length, args.batch_size)
    y_pred = np.argmax(probs, axis=1).tolist()

    # Classification report
    print("\n" + "=" * 60)
    print("  CLASSIFICATION REPORT")
    print("=" * 60)
    report = classification_report(y_true, y_pred, target_names=labels, digits=4)
    print(report)

    # Confusion matrix
    print_confusion_matrix(y_true, y_pred, labels)

    # Error analysis
    error_analysis(test_df, probs, y_pred, id2label)

    # Confidence analysis
    confidence_analysis(probs, y_true, y_pred)

    # Save report
    report_text = classification_report(y_true, y_pred, target_names=labels, digits=4)
    with open(args.output, "w") as f:
        f.write("EVALUATION REPORT\n")
        f.write("=" * 60 + "\n")
        f.write(report_text)
    print(f"\n[DONE] Report saved to {args.output}")
    print(f"[NEXT] Run: python predict.py \"Your text here\"")


if __name__ == "__main__":
    main()
