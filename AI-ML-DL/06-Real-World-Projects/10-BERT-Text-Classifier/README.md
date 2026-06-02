# BERT/RoBERTa Text Classification - Complete Project

## What This Builds

A **multi-class text classifier** using transformer models (DistilBERT, BERT, RoBERTa).
Takes you from messy CSV data to a deployed REST API.

## Architecture

```
Raw CSV Data
    │
    ▼
┌─────────────────────┐
│  data_preparation.py │  ← Clean, encode labels, stratified split
└─────────┬───────────┘
          │ train.csv, val.csv, test.csv, label_mapping.json
          ▼
┌─────────────────────┐
│      train.py        │  ← Fine-tune pretrained transformer
└─────────┬───────────┘
          │ saved_model/
          ▼
┌─────────────────────┐
│     evaluate.py      │  ← Per-class metrics, confusion matrix, error analysis
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│     predict.py       │  ← Single text, batch, or interactive predictions
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    deploy_api.py     │  ← FastAPI REST endpoint
└─────────────────────┘
```

## Prerequisites

**Knowledge:**
- Python basics (functions, classes, file I/O)
- What BERT/transformers are conceptually (attention, tokenization, fine-tuning)
- Basic ML concepts (train/val/test split, overfitting, metrics)

**System:**
- Python 3.9+
- 8GB+ RAM (16GB recommended)
- GPU optional but recommended (CPU works, just slower)

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Prepare data (creates synthetic demo data if you have no CSV)
python data_preparation.py

# 3. Train the model (~5 min on GPU, ~30 min on CPU with DistilBERT)
python train.py --model distilbert-base-uncased --epochs 3

# 4. Evaluate
python evaluate.py

# 5. Make predictions
python predict.py "The new iPhone has incredible battery life"
python predict.py --interactive

# 6. Deploy (optional)
pip install fastapi uvicorn
uvicorn deploy_api:app --host 0.0.0.0 --port 8000
```

## Expected Output

After training (~3 epochs on demo data):
```
Accuracy:  ~0.85-0.92
Macro F1:  ~0.84-0.91
Per-class: technology (0.90), sports (0.88), politics (0.85), entertainment (0.87)
```

## Modifications

| What to Change | Where | How |
|---|---|---|
| Your own dataset | `data_preparation.py` | Set `DATA_PATH`, `TEXT_COLUMN`, `LABEL_COLUMN` |
| Different model | `train.py` | `--model roberta-base` or `bert-base-uncased` |
| Number of classes | Automatic | Just have different labels in your CSV |
| Longer texts | `data_preparation.py` | Increase `MAX_LENGTH` (up to 512) |
| More epochs | `train.py` | `--epochs 5` (watch for overfitting) |
| Learning rate | `train.py` | `--lr 3e-5` (range: 1e-5 to 5e-5) |

## Model Selection Guide

| Model | Params | Speed | Accuracy | Use When |
|---|---|---|---|---|
| `distilbert-base-uncased` | 66M | Fast | Good | Prototyping, limited compute |
| `bert-base-uncased` | 110M | Medium | Better | Standard baseline |
| `roberta-base` | 125M | Medium | Best | Production, need best accuracy |
| `microsoft/deberta-v3-base` | 183M | Slow | State-of-art | Competitions, max performance |

## Troubleshooting

- **CUDA out of memory**: Reduce `--batch-size` to 8 or 4
- **Training too slow**: Use `distilbert-base-uncased` or add `--fp16`
- **Low accuracy**: Check class balance, increase epochs, try `roberta-base`
- **Import errors**: Run `pip install -r requirements.txt`

## Project Structure

```
10-BERT-Text-Classifier/
├── README.md
├── requirements.txt
├── data_preparation.py    # Step 1: Clean and split data
├── train.py               # Step 2: Fine-tune model
├── evaluate.py            # Step 3: Detailed evaluation
├── predict.py             # Step 4: Run inference
├── deploy_api.py          # Step 5: REST API
└── data/                  # Created by data_preparation.py
    ├── train.csv
    ├── val.csv
    ├── test.csv
    └── label_mapping.json
```
