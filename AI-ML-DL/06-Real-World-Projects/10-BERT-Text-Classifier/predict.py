"""
PREDICT WITH TRAINED MODEL
===========================
Usage:
    python predict.py "This movie was amazing!"
    python predict.py --file new_texts.csv
    python predict.py --interactive
"""

import os
import sys
import json
import argparse

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Install with: pip install -r requirements.txt")
    sys.exit(1)


MODEL_DIR = "saved_model"


def parse_args():
    parser = argparse.ArgumentParser(description="Predict with trained BERT model")
    parser.add_argument("text", nargs="?", default=None, help="Text to classify")
    parser.add_argument("--file", type=str, help="CSV file with texts to classify")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--model-dir", type=str, default=MODEL_DIR)
    parser.add_argument("--max-length", type=int, default=256)
    return parser.parse_args()


def load_model(model_dir):
    """Load model, tokenizer, and label mapping."""
    if not os.path.exists(model_dir):
        print(f"[ERROR] Model not found at {model_dir}. Run train.py first!")
        sys.exit(1)

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()

    with open(os.path.join(model_dir, "label_mapping.json"), "r") as f:
        mapping = json.load(f)
    id2label = {int(k): v for k, v in mapping["id2label"].items()}

    return model, tokenizer, id2label


def predict_single(text, model, tokenizer, id2label, max_length=256):
    """Predict a single text. Returns label, confidence, all probabilities."""
    inputs = tokenizer(text, padding=True, truncation=True,
                       max_length=max_length, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]

    pred_id = probs.argmax().item()
    pred_label = id2label[pred_id]
    confidence = probs[pred_id].item()

    all_probs = {id2label[i]: probs[i].item() for i in range(len(id2label))}
    return pred_label, confidence, all_probs


def print_prediction(text, label, confidence, all_probs):
    """Pretty print a prediction."""
    print(f"\n  Text: \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
    print(f"  Prediction: {label} (confidence: {confidence:.2%})")
    print(f"  All classes:")
    for cls, prob in sorted(all_probs.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(prob * 30)
        marker = " ◀" if cls == label else ""
        print(f"    {cls:20s}: {prob:.4f} {bar}{marker}")


def interactive_mode(model, tokenizer, id2label, max_length):
    """Interactive prediction loop."""
    print("\n  Interactive Mode (type 'quit' to exit)")
    print("  " + "─" * 40)
    while True:
        try:
            text = input("\n  Enter text: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("quit", "exit", "q"):
            break
        if not text:
            continue
        label, confidence, all_probs = predict_single(text, model, tokenizer, id2label, max_length)
        print_prediction(text, label, confidence, all_probs)


def batch_predict(file_path, model, tokenizer, id2label, max_length):
    """Predict from CSV file."""
    import pandas as pd
    df = pd.read_csv(file_path)
    text_col = "text" if "text" in df.columns else df.columns[0]
    texts = df[text_col].tolist()

    print(f"\n  Predicting {len(texts)} texts from {file_path}...")
    results = []
    for text in texts:
        label, confidence, _ = predict_single(str(text), model, tokenizer, id2label, max_length)
        results.append({"text": text, "prediction": label, "confidence": confidence})

    results_df = pd.DataFrame(results)
    output_path = file_path.replace(".csv", "_predictions.csv")
    results_df.to_csv(output_path, index=False)
    print(f"  Saved predictions to: {output_path}")
    print(results_df.head(10).to_string(index=False))


def main():
    args = parse_args()
    model, tokenizer, id2label = load_model(args.model_dir)
    print(f"[OK] Model loaded ({len(id2label)} classes: {list(id2label.values())})")

    if args.interactive:
        interactive_mode(model, tokenizer, id2label, args.max_length)
    elif args.file:
        batch_predict(args.file, model, tokenizer, id2label, args.max_length)
    elif args.text:
        label, confidence, all_probs = predict_single(args.text, model, tokenizer, id2label, args.max_length)
        print_prediction(args.text, label, confidence, all_probs)
    else:
        print("[ERROR] Provide text, --file, or --interactive")
        print("  python predict.py \"Your text here\"")
        print("  python predict.py --interactive")


if __name__ == "__main__":
    main()
