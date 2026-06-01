# Modern AI Tools - Ecosystem Overview

## The Modern AI/ML Toolchain

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI/ML Development Lifecycle                    │
├─────────────┬──────────────┬──────────────┬─────────────────────────┤
│   Data      │   Training   │  Evaluation  │   Deployment            │
├─────────────┼──────────────┼──────────────┼─────────────────────────┤
│ DVC         │ HuggingFace  │ W&B          │ ONNX Runtime            │
│ LakeFS      │ PyTorch      │ MLflow       │ TensorRT                │
│ Delta Lake  │ Accelerate   │ Evaluate     │ vLLM / TGI              │
│ Datasets    │ PEFT/LoRA    │ LangSmith    │ Triton                  │
├─────────────┼──────────────┼──────────────┼─────────────────────────┤
│             │              │              │                         │
│  Orchestration & Applications                                       │
│  ├── LangChain / LangGraph (LLM orchestration)                      │
│  ├── LlamaIndex (data-augmented generation)                         │
│  ├── Semantic Kernel / DSPy (alternatives)                          │
│  └── Gradio / Streamlit (demos & UIs)                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Tool Categories

| Category | Tools | Purpose |
|----------|-------|---------|
| Model Hub | HuggingFace Hub, Model Zoo | Pre-trained model access |
| Training | Transformers, Accelerate, PEFT | Model training & fine-tuning |
| Data | DVC, Datasets, LakeFS | Data versioning & loading |
| Experiment Tracking | W&B, MLflow, Neptune | Logging metrics & artifacts |
| Optimization | ONNX, TensorRT, vLLM | Inference speed & efficiency |
| Orchestration | LangChain, LlamaIndex | LLM application building |
| Serving | TGI, Triton, BentoML | Production model serving |
| Monitoring | LangSmith, W&B, Arize | Production observability |

## How Tools Fit Together

```
Data Pipeline:       DVC → Datasets → Tokenizers → DataLoader
Training Pipeline:   Transformers + Accelerate + PEFT → Trainer → W&B logging
Optimization:        Trained Model → ONNX Export → Quantization → TensorRT
Serving:             Optimized Model → TGI/vLLM → API Gateway
Application:         LangChain/LlamaIndex → Vector DB → User Interface
```

## Learning Path

1. **[HuggingFace Ecosystem](./01-HuggingFace-Ecosystem/)** - The foundation for modern NLP/ML
2. **[LangChain & Orchestration](./02-LangChain-and-Orchestration/)** - Building LLM applications
3. **[Weights & Biases](./03-Weights-and-Biases/)** - Experiment tracking & collaboration
4. **[DVC - Data Version Control](./04-DVC-Data-Version-Control/)** - Reproducible ML pipelines
5. **[ONNX & Model Optimization](./05-ONNX-and-Model-Optimization/)** - Production-ready inference

## Selection Guide

**Building an LLM app?** → LangChain/LlamaIndex + Vector DB
**Fine-tuning a model?** → HuggingFace Transformers + PEFT + W&B
**Need reproducibility?** → DVC + W&B + Docker
**Deploying to production?** → ONNX/TensorRT + TGI/vLLM + Triton
**Quick prototype?** → HuggingFace Pipeline + Gradio
