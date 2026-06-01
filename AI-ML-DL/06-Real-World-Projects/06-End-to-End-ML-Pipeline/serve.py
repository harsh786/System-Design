"""
Model Serving with FastAPI
===========================
REST API for the trained house price model.
Run: python serve.py
Test: curl http://localhost:8000/predict -X POST -H "Content-Type: application/json" \
      -d '{"features": [8.3, 41, 6.9, 1.02, 322, 2.5, 37.88, -122.23]}'
"""

import logging
import pickle
import time
from pathlib import Path
from typing import List

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not installed. Run: pip install fastapi uvicorn")


# Feature names for California Housing
FEATURE_NAMES = ["MedInc", "HouseAge", "AveRooms", "AveBedrms", "Population", "AveOccup", "Latitude", "Longitude"]
MODEL_PATH = Path("./model_registry/house_price_model/model_v1.0.pkl")


def load_model():
    """Load model artifacts."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run pipeline.py first.")
    with open(MODEL_PATH, "rb") as f:
        artifacts = pickle.load(f)
    logger.info("Model loaded successfully")
    return artifacts["model"], artifacts["scaler"]


if FASTAPI_AVAILABLE:
    app = FastAPI(title="House Price Prediction API", version="1.0")

    class PredictRequest(BaseModel):
        """Input features for prediction."""
        features: List[float] = Field(..., min_length=8, max_length=8, description="8 housing features")

    class PredictResponse(BaseModel):
        """Prediction response."""
        prediction: float
        confidence_interval: List[float]
        latency_ms: float
        model_version: str = "1.0"

    class HealthResponse(BaseModel):
        status: str
        model_loaded: bool

    # Load model at startup
    try:
        model, scaler = load_model()
        model_loaded = True
    except FileNotFoundError as e:
        logger.error(str(e))
        model, scaler = None, None
        model_loaded = False

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(status="ok", model_loaded=model_loaded)

    @app.post("/predict", response_model=PredictResponse)
    def predict(request: PredictRequest):
        if not model_loaded:
            raise HTTPException(status_code=503, detail="Model not loaded. Run pipeline.py first.")

        start = time.time()
        features = np.array(request.features).reshape(1, -1)
        features_scaled = scaler.transform(features)
        prediction = float(model.predict(features_scaled)[0])
        latency = (time.time() - start) * 1000

        # Simple confidence interval (±10% for demo)
        ci = [prediction * 0.9, prediction * 1.1]

        return PredictResponse(
            prediction=round(prediction, 4),
            confidence_interval=[round(ci[0], 4), round(ci[1], 4)],
            latency_ms=round(latency, 2),
        )

    @app.get("/features")
    def get_features():
        return {"features": FEATURE_NAMES, "count": len(FEATURE_NAMES)}


def main():
    """Run the API server."""
    if not FASTAPI_AVAILABLE:
        print("FastAPI not installed. Install with: pip install fastapi uvicorn")
        print("\nDemo mode - simulating prediction:")
        try:
            model, scaler = load_model()
            sample = np.array([[8.3, 41, 6.9, 1.02, 322, 2.5, 37.88, -122.23]])
            pred = model.predict(scaler.transform(sample))[0]
            print(f"  Input: {dict(zip(FEATURE_NAMES, sample[0]))}")
            print(f"  Prediction: ${pred * 100000:.0f}")
        except FileNotFoundError as e:
            print(f"  Error: {e}")
        return

    print("Starting API server at http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
