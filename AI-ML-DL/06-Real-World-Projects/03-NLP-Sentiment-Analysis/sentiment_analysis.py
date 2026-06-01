"""
NLP Sentiment Analysis Pipeline
================================
Approach 1: TF-IDF + Classical ML (Logistic Regression, SVM, Naive Bayes)
Approach 2: LSTM with PyTorch
Uses sklearn's 20newsgroups as a proxy text classification dataset.
"""

import logging
import re
import time
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.datasets import fetch_20newsgroups
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from torch.utils.data import DataLoader, Dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# =============================================================================
# Data Loading & Preprocessing
# =============================================================================

def load_binary_sentiment_data() -> Tuple[List[str], np.ndarray]:
    """
    Load a binary classification dataset from 20newsgroups.
    We pick 2 categories to simulate positive/negative sentiment.
    """
    categories = ["rec.sport.baseball", "sci.space"]  # 2 distinct topics
    data = fetch_20newsgroups(subset="all", categories=categories, remove=("headers", "footers", "quotes"))
    logger.info(f"Loaded {len(data.data)} documents, {len(categories)} classes")
    return data.data, np.array(data.target)


def clean_text(text: str) -> str:
    """Basic text cleaning."""
    text = text.lower()
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =============================================================================
# Approach 1: TF-IDF + Classical ML
# =============================================================================

def classical_ml_pipeline(texts: List[str], labels: np.ndarray) -> Dict[str, float]:
    """TF-IDF + multiple classifiers."""
    print("\n" + "=" * 60)
    print("APPROACH 1: TF-IDF + Classical ML")
    print("=" * 60)

    cleaned = [clean_text(t) for t in texts]
    X_train, X_test, y_train, y_test = train_test_split(cleaned, labels, test_size=0.2, random_state=42)

    # Vectorize
    vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), min_df=2)
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)
    logger.info(f"TF-IDF matrix: {X_train_tfidf.shape}")

    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, C=1.0),
        "Linear SVM": LinearSVC(max_iter=2000),
        "Naive Bayes": MultinomialNB(alpha=0.1),
    }

    results = {}
    print(f"\n{'Model':<22} {'Accuracy':>10} {'F1':>10} {'Time':>8}")
    print("-" * 52)

    for name, model in models.items():
        start = time.time()
        model.fit(X_train_tfidf, y_train)
        preds = model.predict(X_test_tfidf)
        elapsed = time.time() - start

        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds, average="weighted")
        results[name] = acc
        print(f"{name:<22} {acc:>10.4f} {f1:>10.4f} {elapsed:>7.2f}s")

    # Best model detailed report
    best_name = max(results, key=results.get)
    print(f"\nBest: {best_name} ({results[best_name]:.4f})")
    return results


# =============================================================================
# Approach 2: LSTM with PyTorch
# =============================================================================

class TextDataset(Dataset):
    """Simple text dataset with integer encoding."""

    def __init__(self, texts: List[str], labels: np.ndarray, vocab: Dict[str, int], max_len: int = 200):
        self.labels = labels
        self.max_len = max_len
        self.encoded = []
        for text in texts:
            tokens = clean_text(text).split()[:max_len]
            ids = [vocab.get(t, 1) for t in tokens]  # 1 = UNK
            # Pad
            ids = ids + [0] * (max_len - len(ids))
            self.encoded.append(ids)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return torch.tensor(self.encoded[idx], dtype=torch.long), torch.tensor(self.labels[idx], dtype=torch.long)


class LSTMClassifier(nn.Module):
    """Bidirectional LSTM for text classification."""

    def __init__(self, vocab_size: int, embed_dim: int = 128, hidden_dim: int = 128, num_classes: int = 2):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, num_layers=2, batch_first=True, bidirectional=True, dropout=0.3)
        self.fc = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        emb = self.embedding(x)
        _, (hidden, _) = self.lstm(emb)
        # Concatenate last hidden states from both directions
        hidden = torch.cat((hidden[-2], hidden[-1]), dim=1)
        return self.fc(hidden)


def build_vocab(texts: List[str], max_vocab: int = 15000) -> Dict[str, int]:
    """Build vocabulary from texts."""
    word_counts: Dict[str, int] = {}
    for text in texts:
        for word in clean_text(text).split():
            word_counts[word] = word_counts.get(word, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:max_vocab - 2]
    vocab = {"<PAD>": 0, "<UNK>": 1}
    for word, _ in sorted_words:
        vocab[word] = len(vocab)
    return vocab


def lstm_pipeline(texts: List[str], labels: np.ndarray) -> float:
    """Train LSTM classifier."""
    print("\n" + "=" * 60)
    print("APPROACH 2: LSTM (PyTorch)")
    print("=" * 60)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(texts, labels, test_size=0.2, random_state=42)

    # Build vocab
    vocab = build_vocab(X_train)
    logger.info(f"Vocabulary size: {len(vocab)}")

    # Datasets
    train_ds = TextDataset(X_train, y_train, vocab, max_len=150)
    test_ds = TextDataset(X_test, y_test, vocab, max_len=150)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=64)

    # Model
    model = LSTMClassifier(vocab_size=len(vocab), num_classes=2).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {params:,}")
    print(f"Device: {DEVICE}")

    # Train
    epochs = 5
    print(f"\n{'Epoch':>5} {'Train Loss':>11} {'Train Acc':>10} {'Test Acc':>9}")
    print("-" * 40)

    best_acc = 0.0
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for inputs, targets in train_loader:
            inputs, targets = inputs.to(DEVICE), targets.to(DEVICE)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item() * inputs.size(0)
            _, preds = outputs.max(1)
            correct += preds.eq(targets).sum().item()
            total += targets.size(0)

        train_acc = 100.0 * correct / total

        # Evaluate
        model.eval()
        test_correct = 0
        test_total = 0
        with torch.no_grad():
            for inputs, targets in test_loader:
                inputs, targets = inputs.to(DEVICE), targets.to(DEVICE)
                outputs = model(inputs)
                _, preds = outputs.max(1)
                test_correct += preds.eq(targets).sum().item()
                test_total += targets.size(0)

        test_acc = 100.0 * test_correct / test_total
        best_acc = max(best_acc, test_acc)
        print(f"{epoch:>5d} {total_loss/total:>11.4f} {train_acc:>9.2f}% {test_acc:>8.2f}%")

    print(f"\nBest LSTM Test Accuracy: {best_acc:.2f}%")
    return best_acc


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """Run complete sentiment analysis pipeline."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        NLP SENTIMENT ANALYSIS PIPELINE                  ║")
    print("╚══════════════════════════════════════════════════════════╝")

    texts, labels = load_binary_sentiment_data()

    # Approach 1: Classical ML
    classical_results = classical_ml_pipeline(texts, labels)

    # Approach 2: LSTM
    lstm_acc = lstm_pipeline(texts, labels)

    # Comparison
    print("\n" + "=" * 60)
    print("FINAL COMPARISON")
    print("=" * 60)
    print(f"\n{'Method':<25} {'Accuracy':>10}")
    print("-" * 37)
    for name, acc in classical_results.items():
        print(f"{name:<25} {acc:>10.4f}")
    print(f"{'LSTM (PyTorch)':<25} {lstm_acc/100:>10.4f}")

    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
