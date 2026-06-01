# Project 3: NLP Sentiment Analysis

## What You'll Learn
- Text preprocessing and tokenization
- TF-IDF vectorization with classical ML
- LSTM-based deep learning approach
- Comparing traditional vs deep learning for NLP

## Architecture

```
┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│ Raw Text │───►│ Preprocessing│───►│ Approach 1: TF-IDF + ML        │
│ (Reviews)│    │ (clean,      │    │   LogReg, SVM, NaiveBayes      │
└──────────┘    │  tokenize)   │    ├─────────────────────────────────┤
                └──────────────┘    │ Approach 2: LSTM (PyTorch)      │
                                    │   Embedding → LSTM → FC         │
                                    └─────────────────────────────────┘
                                                    │
                                              ┌─────▼─────┐
                                              │ Compare   │
                                              │ Results   │
                                              └───────────┘
```

## Prerequisites

```bash
pip install numpy pandas scikit-learn torch
```

## How to Run

```bash
python sentiment_analysis.py
```

## Expected Output
- Classical ML model comparison (accuracy, F1)
- LSTM training progress
- Side-by-side comparison of approaches

## Extension Ideas
- Use HuggingFace transformers (BERT fine-tuning)
- Add attention mechanism visualization
- Deploy as a sentiment API
