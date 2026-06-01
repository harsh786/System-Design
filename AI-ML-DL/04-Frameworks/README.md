# AI/ML/DL Frameworks - Comprehensive Overview

## Framework Ecosystem Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI/ML/DL Framework Ecosystem                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─── Classical ML ───┐  ┌──── Deep Learning ────┐  ┌── Ecosystem ──┐     │
│  │                     │  │                        │  │               │     │
│  │  ┌───────────────┐  │  │  ┌────────────────┐   │  │  Jupyter      │     │
│  │  │  Scikit-Learn  │  │  │  │   PyTorch      │   │  │  Notebooks    │     │
│  │  │  - Classification│ │  │  │  - Research    │   │  │               │     │
│  │  │  - Regression   │  │  │  │  - Dynamic    │   │  │  MLflow       │     │
│  │  │  - Clustering   │  │  │  │  - Pythonic   │   │  │  W&B          │     │
│  │  │  - Pipelines    │  │  │  └────────────────┘   │  │  DVC          │     │
│  │  └───────────────┘  │  │                        │  │               │     │
│  │                     │  │  ┌────────────────┐   │  │  Hugging Face │     │
│  │  ┌───────────────┐  │  │  │  TensorFlow    │   │  │  ONNX Runtime │     │
│  │  │  XGBoost      │  │  │  │  - Production  │   │  │               │     │
│  │  │  LightGBM     │  │  │  │  - TF Serving  │   │  └───────────────┘     │
│  │  │  CatBoost     │  │  │  │  - TFLite      │   │                        │
│  │  └───────────────┘  │  │  └────────────────┘   │                        │
│  └─────────────────────┘  └────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Framework Comparison Matrix

| Feature | Scikit-Learn | PyTorch | TensorFlow |
|---------|-------------|---------|------------|
| **Primary Use** | Classical ML | DL Research + Production | DL Production |
| **Learning Curve** | Low | Medium | Medium-High |
| **API Style** | Consistent OOP | Pythonic/Imperative | Declarative + Imperative |
| **GPU Support** | No (mostly) | Native CUDA | Native CUDA/TPU |
| **Deployment** | joblib/pickle | TorchServe/ONNX | TF Serving/TFLite |
| **Debugging** | Easy (Python) | Easy (eager mode) | Medium (eager/graph) |
| **Community** | Mature/Stable | Fast-growing | Large/Enterprise |
| **Best For** | Tabular data, prototyping | Research, NLP, CV | Production pipelines, mobile |
| **Auto-diff** | No | Yes (autograd) | Yes (GradientTape) |
| **Distributed** | Limited (joblib) | DDP, FSDP | MirroredStrategy, TPU |
| **Mobile/Edge** | No | PyTorch Mobile | TFLite |
| **Model Zoo** | No | TorchVision/Hub | TF Hub/Model Garden |

## Decision Flowchart

```
Start: What problem are you solving?
│
├── Tabular data / Classical ML?
│   ├── YES → Scikit-Learn
│   │         (+ XGBoost/LightGBM for boosting)
│   └── NO ↓
│
├── Deep Learning needed?
│   ├── Research / Rapid prototyping?
│   │   └── PyTorch (dynamic graphs, easy debugging)
│   │
│   ├── Production deployment at scale?
│   │   ├── Mobile/Edge? → TensorFlow (TFLite)
│   │   ├── TPU training? → TensorFlow
│   │   └── Server inference? → Either (TorchServe or TF Serving)
│   │
│   ├── NLP / Transformers?
│   │   └── Hugging Face (supports both PyTorch & TF)
│   │
│   └── Computer Vision?
│       └── PyTorch (torchvision) or TF (tf.keras.applications)
│
└── Experimentation / Exploration?
    └── Jupyter Ecosystem
```

## Framework Synergy Patterns

### Pattern 1: Prototype → Production Pipeline
```
Jupyter (EDA) → Scikit-Learn (baseline) → PyTorch (DL model) → ONNX → Production
```

### Pattern 2: Full TensorFlow Stack
```
Jupyter (EDA) → tf.data → Keras model → SavedModel → TF Serving → TFLite (mobile)
```

### Pattern 3: Research to Deployment
```
Jupyter (experiments) → PyTorch (research) → PyTorch Lightning → TorchServe
                                           → ONNX → ONNX Runtime
```

### Pattern 4: ML Engineering Pipeline
```
Scikit-Learn (preprocessing) → Feature Store → Model Training → MLflow → Deploy
```

## When to Use Each Framework

### Scikit-Learn
- Tabular/structured data problems
- Need fast prototyping and baselines
- Classical algorithms (SVM, Random Forest, KNN)
- Feature engineering pipelines
- When interpretability matters
- Small-to-medium datasets that fit in memory

### PyTorch
- Deep learning research
- Custom architectures and loss functions
- Dynamic computation graphs needed
- NLP tasks (Hugging Face ecosystem)
- GANs, reinforcement learning
- When debugging ease is priority

### TensorFlow
- Production ML systems at scale
- Mobile/edge deployment (TFLite)
- End-to-end ML pipelines (TFX)
- TPU training
- Enterprise environments
- When you need TensorBoard integration

### Jupyter Ecosystem
- Exploratory data analysis
- Prototyping and experimentation
- Documentation and presentation
- Teaching and learning
- Collaborative data science
- Reproducible research

## Performance Benchmarks (Approximate)

```
Task: Image Classification (ResNet-50, ImageNet)
┌─────────────────┬──────────────┬──────────────┐
│ Framework       │ Training     │ Inference    │
├─────────────────┼──────────────┼──────────────┤
│ PyTorch         │ ~1.0x (base) │ ~1.0x (base) │
│ TensorFlow      │ ~1.05x       │ ~0.95x       │
│ ONNX Runtime    │ N/A          │ ~0.85x       │
│ TensorRT        │ N/A          │ ~0.5x        │
└─────────────────┴──────────────┴──────────────┘
(Lower is better, relative to PyTorch baseline)

Task: Tabular Classification (10K samples, 50 features)
┌─────────────────┬──────────────┐
│ Framework       │ Train Time   │
├─────────────────┼──────────────┤
│ Scikit-Learn RF │ ~1.0x (base) │
│ XGBoost         │ ~0.7x        │
│ LightGBM        │ ~0.4x        │
│ CatBoost        │ ~0.8x        │
└─────────────────┴──────────────┘
```

## Installation Quick Reference

```bash
# Scikit-Learn
pip install scikit-learn pandas numpy

# PyTorch (CPU)
pip install torch torchvision torchaudio

# PyTorch (CUDA 11.8)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# TensorFlow
pip install tensorflow

# Jupyter
pip install jupyterlab notebook ipywidgets

# Full ML Stack
pip install scikit-learn torch tensorflow jupyterlab pandas numpy matplotlib seaborn
```

## Learning Path Recommendation

```
Week 1-2: Scikit-Learn (foundations, pipelines, classical ML)
Week 3-4: PyTorch (tensors, autograd, nn.Module, training loops)
Week 5-6: TensorFlow/Keras (models, tf.data, deployment)
Week 7-8: Integration (Jupyter workflows, MLflow, production patterns)
```

## File Structure

```
04-Frameworks/
├── README.md                    ← You are here
├── 01-Scikit-Learn/
│   └── README.md               ← Classical ML mastery
├── 02-PyTorch/
│   └── README.md               ← Deep learning research & production
├── 03-TensorFlow/
│   └── README.md               ← Production ML systems
└── 04-Jupyter-Ecosystem/
    └── README.md               ← Development environment mastery
```
