"""
=============================================================================
TEMPLATE: Text Classification
=============================================================================
A complete, runnable template for text classification.
Uses TF-IDF + Logistic Regression (works without deep learning libraries).
Optional: BERT fine-tuning section (requires transformers + torch).

USAGE:
    python template_text_classification.py

MODIFY:
    Search for "MODIFY THIS" to find all customization points.

REQUIREMENTS (minimal):
    pip install numpy pandas scikit-learn

OPTIONAL (for BERT):
    pip install transformers torch datasets
=============================================================================
"""

import numpy as np
import pandas as pd
import warnings
import joblib
from pathlib import Path

warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix


# ============================================================
# MODIFY THIS: Configuration
# ============================================================
CONFIG = {
    # Data
    "test_size": 0.2,
    "random_state": 42,

    # TF-IDF
    "max_features": 10000,      # Vocabulary size
    "ngram_range": (1, 2),      # Unigrams + bigrams
    "min_df": 2,                # Minimum document frequency
    "max_df": 0.95,             # Maximum document frequency

    # Model
    "cv_folds": 5,

    # Output
    "save_path": "text_classifier.joblib",
}


# ============================================================
# MODIFY THIS: Data Loading
# ============================================================
def load_data():
    """
    Load your text dataset.

    MODIFY THIS FUNCTION to load your own data.
    Must return:
      - texts: list of strings
      - labels: list/array of labels
      - label_names: list of class names (optional)

    Options:
      - pd.read_csv("data.csv") then extract text and label columns
      - Load from database, API, etc.
    """

    # Default: Built-in 20 newsgroups subset (no download needed)
    from sklearn.datasets import fetch_20newsgroups

    # MODIFY THIS: Choose your categories or use all
    categories = [
        "comp.graphics",
        "rec.sport.baseball",
        "sci.medicine",
        "talk.politics.guns",
    ]

    data = fetch_20newsgroups(
        subset="all",
        categories=categories,
        remove=("headers", "footers", "quotes"),  # Remove metadata for fair eval
        random_state=CONFIG["random_state"],
    )

    texts = data.data
    labels = data.target
    label_names = data.target_names

    print(f"  Total documents: {len(texts)}")
    print(f"  Classes ({len(label_names)}): {label_names}")
    print(f"  Class distribution:")
    for i, name in enumerate(label_names):
        count = sum(1 for l in labels if l == i)
        print(f"    {name}: {count}")
    print(f"  Sample text (first 100 chars): '{texts[0][:100]}...'")

    return texts, labels, label_names


# ============================================================
# Text Preprocessing
# ============================================================
def preprocess_text(text):
    """
    Basic text preprocessing.

    MODIFY THIS for your domain:
    - Add/remove steps as needed
    - Domain-specific cleaning (HTML, URLs, etc.)
    """
    import re

    # Lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r"http\S+|www\.\S+", "", text)

    # Remove email addresses
    text = re.sub(r"\S+@\S+", "", text)

    # Remove special characters (keep letters, numbers, spaces)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# Model Building
# ============================================================
def build_models():
    """
    Build candidate pipelines (TF-IDF + classifier).

    Each pipeline handles text vectorization AND classification.
    """

    models = {
        "LogisticRegression": Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=CONFIG["max_features"],
                ngram_range=CONFIG["ngram_range"],
                min_df=CONFIG["min_df"],
                max_df=CONFIG["max_df"],
                sublinear_tf=True,      # Apply log normalization
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=1.0,
                random_state=CONFIG["random_state"],
            )),
        ]),

        "MultinomialNB": Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=CONFIG["max_features"],
                ngram_range=CONFIG["ngram_range"],
                min_df=CONFIG["min_df"],
                max_df=CONFIG["max_df"],
            )),
            ("clf", MultinomialNB(alpha=0.1)),
        ]),

        "LinearSVC": Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=CONFIG["max_features"],
                ngram_range=CONFIG["ngram_range"],
                min_df=CONFIG["min_df"],
                max_df=CONFIG["max_df"],
                sublinear_tf=True,
            )),
            ("clf", LinearSVC(
                max_iter=2000,
                C=1.0,
                random_state=CONFIG["random_state"],
            )),
        ]),
    }

    return models


# ============================================================
# Main Pipeline
# ============================================================
def main():
    print("=" * 60)
    print("TEXT CLASSIFICATION TEMPLATE")
    print("=" * 60)

    # Step 1: Load data
    print("\n[1/5] Loading data...")
    texts, labels, label_names = load_data()

    # Step 2: Preprocess
    print("\n[2/5] Preprocessing text...")
    texts_clean = [preprocess_text(t) for t in texts]
    # Remove empty documents
    valid_idx = [i for i, t in enumerate(texts_clean) if len(t.strip()) > 0]
    texts_clean = [texts_clean[i] for i in valid_idx]
    labels = np.array(labels)[valid_idx]
    print(f"  Documents after cleaning: {len(texts_clean)}")

    # Step 3: Split
    print("\n[3/5] Splitting data...")
    X_train, X_test, y_train, y_test = train_test_split(
        texts_clean, labels,
        test_size=CONFIG["test_size"],
        random_state=CONFIG["random_state"],
        stratify=labels,
    )
    print(f"  Train: {len(X_train)} documents")
    print(f"  Test:  {len(X_test)} documents")

    # Step 4: Model selection
    print("\n[4/5] Model selection with cross-validation...")
    models = build_models()

    best_score = 0
    best_name = None
    best_model = None
    results = {}

    for name, pipeline in models.items():
        scores = cross_val_score(
            pipeline, X_train, y_train,
            cv=CONFIG["cv_folds"], scoring="accuracy", n_jobs=-1
        )
        mean_score = scores.mean()
        std_score = scores.std()
        results[name] = {"mean": mean_score, "std": std_score}
        print(f"  {name:<25} Accuracy: {mean_score:.4f} (+/- {std_score:.4f})")

        if mean_score > best_score:
            best_score = mean_score
            best_name = name
            best_model = pipeline

    # Step 5: Train best model and evaluate
    print(f"\n[5/5] Training best model ({best_name})...")
    best_model.fit(X_train, y_train)
    y_pred = best_model.predict(X_test)

    print(f"\n  Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=label_names))

    # Save
    joblib.dump(best_model, CONFIG["save_path"])
    print(f"  Model saved to: {CONFIG['save_path']}")

    # Demo prediction
    print("\n" + "=" * 60)
    print("DEMO PREDICTIONS:")
    print("=" * 60)
    demo_texts = [
        "The patient was diagnosed with pneumonia and prescribed antibiotics.",
        "The pitcher threw a fastball for strike three to end the inning.",
        "The new GPU renders 3D graphics at 120 frames per second.",
    ]
    for text in demo_texts:
        pred = best_model.predict([preprocess_text(text)])[0]
        print(f"  Text: '{text[:60]}...'")
        print(f"  Predicted: {label_names[pred]}\n")

    # Usage instructions
    print("=" * 60)
    print("TO USE THIS MODEL:")
    print("=" * 60)
    print(f"""
    import joblib

    model = joblib.load("{CONFIG['save_path']}")
    predictions = model.predict(["Your text here", "Another text"])
    """)

    # ============================================================
    # OPTIONAL: BERT Fine-tuning (requires transformers + torch)
    # ============================================================
    print("\n" + "=" * 60)
    print("OPTIONAL: BERT Fine-tuning")
    print("=" * 60)

    try:
        from transformers import (
            AutoTokenizer, AutoModelForSequenceClassification,
            TrainingArguments, Trainer
        )
        from datasets import Dataset
        import torch

        print("  transformers and torch available! BERT fine-tuning is possible.")
        print("  To enable, set RUN_BERT=True below.\n")

        RUN_BERT = False  # MODIFY THIS: Set True to run BERT fine-tuning

        if RUN_BERT:
            print("  Running BERT fine-tuning...")
            model_name = "distilbert-base-uncased"
            tokenizer = AutoTokenizer.from_pretrained(model_name)

            # Prepare datasets
            train_dataset = Dataset.from_dict({
                "text": X_train, "label": y_train.tolist()
            })
            test_dataset = Dataset.from_dict({
                "text": X_test, "label": y_test.tolist()
            })

            def tokenize(examples):
                return tokenizer(examples["text"], padding="max_length",
                                truncation=True, max_length=256)

            train_dataset = train_dataset.map(tokenize, batched=True)
            test_dataset = test_dataset.map(tokenize, batched=True)

            model = AutoModelForSequenceClassification.from_pretrained(
                model_name, num_labels=len(label_names)
            )

            training_args = TrainingArguments(
                output_dir="./bert_results",
                num_train_epochs=3,
                per_device_train_batch_size=16,
                per_device_eval_batch_size=32,
                learning_rate=2e-5,
                warmup_ratio=0.1,
                eval_strategy="epoch",
                save_strategy="epoch",
                load_best_model_at_end=True,
                report_to="none",
            )

            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=test_dataset,
            )
            trainer.train()
            print("  BERT fine-tuning complete!")
        else:
            print("  Skipping BERT (set RUN_BERT=True to enable)")

    except ImportError:
        print("  transformers/torch not installed. Skipping BERT section.")
        print("  Install with: pip install transformers torch datasets")
        print("  The TF-IDF model above is already very good for most tasks!")


if __name__ == "__main__":
    main()
