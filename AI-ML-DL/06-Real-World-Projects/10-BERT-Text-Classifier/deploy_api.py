"""
DEPLOY MODEL AS REST API
=========================
Simple API endpoint for predictions.
Requires: pip install fastapi uvicorn

Run:
    uvicorn deploy_api:app --host 0.0.0.0 --port 8000

Test:
    curl -X POST http://localhost:8000/predict \
         -H "Content-Type: application/json" \
         -d '{"text": "The new iPhone has amazing battery life"}'
"""

import os
import sys
import json

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import List, Dict
except ImportError:
    print("=" * 60)
    print("  FastAPI not installed.")
    print("  Install with: pip install fastapi uvicorn")
    print("  Then run: uvicorn deploy_api:app --host 0.0.0.0 --port 8000")
    print("=" * 60)
    sys.exit(1)

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
except ImportError:
    print("[ERROR] Install: pip install -r requirements.txt")
    sys.exit(1)


# ============ CONFIG ============
MODEL_DIR = "saved_model"
MAX_LENGTH = 256

# ============ LOAD MODEL ON STARTUP ============
if not os.path.exists(MODEL_DIR):
    print(f"[ERROR] Model not found at {MODEL_DIR}. Run train.py first!")
    sys.exit(1)

print(f"Loading model from {MODEL_DIR}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()

with open(os.path.join(MODEL_DIR, "label_mapping.json"), "r") as f:
    mapping = json.load(f)
id2label = {int(k): v for k, v in mapping["id2label"].items()}

print(f"[OK] Model loaded. Classes: {list(id2label.values())}")


# ============ API SETUP ============
app = FastAPI(
    title="BERT Text Classifier API",
    description="Multi-class text classification using fine-tuned transformer",
    version="1.0.0",
)


# ============ REQUEST/RESPONSE MODELS ============
class PredictRequest(BaseModel):
    text: str

class BatchPredictRequest(BaseModel):
    texts: List[str]

class PredictionResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: Dict[str, float]

class HealthResponse(BaseModel):
    status: str
    model_dir: str
    num_classes: int
    classes: List[str]


# ============ PREDICTION LOGIC ============
def predict_text(text: str) -> PredictionResponse:
    inputs = tokenizer(text, padding=True, truncation=True,
                       max_length=MAX_LENGTH, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]

    pred_id = probs.argmax().item()
    return PredictionResponse(
        prediction=id2label[pred_id],
        confidence=round(probs[pred_id].item(), 4),
        probabilities={id2label[i]: round(probs[i].item(), 4) for i in range(len(id2label))},
    )


# ============ ENDPOINTS ============
@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy",
        model_dir=MODEL_DIR,
        num_classes=len(id2label),
        classes=list(id2label.values()),
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    return predict_text(request.text)


@app.post("/predict/batch", response_model=List[PredictionResponse])
def predict_batch(request: BatchPredictRequest):
    if not request.texts:
        raise HTTPException(status_code=400, detail="Texts list cannot be empty")
    if len(request.texts) > 100:
        raise HTTPException(status_code=400, detail="Max 100 texts per batch")
    return [predict_text(text) for text in request.texts]
