# Project 6: End-to-End ML Pipeline

## What You'll Learn
- Production ML pipeline design
- Data validation and schema enforcement
- Model training with experiment tracking
- FastAPI model serving
- Model monitoring and drift detection
- Containerization with Docker

## Production Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ Data Source │───►│ Validation   │───►│ Training    │───►│ Model        │
│             │    │ (schema,     │    │ Pipeline    │    │ Registry     │
│             │    │  quality)    │    │             │    │ (versioned)  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                                                                 │
                   ┌──────────────┐    ┌─────────────┐          │
                   │ Monitoring   │◄───│ API Serving │◄─────────┘
                   │ (drift,      │    │ (FastAPI)   │
                   │  performance)│    └─────────────┘
                   └──────────────┘
```

## Files
- `pipeline.py` - Training pipeline with validation and model registry
- `serve.py` - FastAPI serving endpoint
- `monitor.py` - Drift detection and monitoring
- `Dockerfile` - Container for deployment

## Prerequisites

```bash
pip install numpy pandas scikit-learn fastapi uvicorn pydantic
```

## How to Run

```bash
# 1. Train the model
python pipeline.py

# 2. Start the API server
python serve.py
# Then: curl http://localhost:8000/predict -X POST -H "Content-Type: application/json" -d '{"features": [8.3, 41, 6.9, 1.02, 322, 2.5, 37.88, -122.23]}'

# 3. Run monitoring
python monitor.py
```

## Extension Ideas
- Add MLflow for experiment tracking
- Kubernetes deployment with Helm
- CI/CD pipeline with GitHub Actions
- A/B testing between model versions
- Feature store integration
