# Deep Learning

## Overview

Deep Learning is a subset of Machine Learning that uses neural networks with multiple layers (deep architectures) to learn hierarchical representations of data. It has revolutionized AI since 2012, achieving superhuman performance in vision, language, and game-playing tasks.

## Evolution Timeline

```
1958  Perceptron (Rosenblatt)
1986  Backpropagation (Rumelhart, Hinton, Williams)
1989  CNN for digit recognition (LeCun)
1997  LSTM (Hochreiter & Schmidhuber)
2006  Deep Belief Networks / "Deep Learning" renaissance (Hinton)
2012  AlexNet wins ImageNet (Krizhevsky) ← modern DL era begins
2014  GANs (Goodfellow), VGG, GoogLeNet
2015  ResNet (He), Batch Normalization
2017  Transformer / "Attention Is All You Need" (Vaswani)
2018  BERT (Devlin), GPT (Radford)
2020  GPT-3 (175B params), Vision Transformer (ViT)
2021  DALL-E, Codex
2022  ChatGPT, Stable Diffusion, Whisper
2023  GPT-4, LLaMA, Segment Anything
2024  Mixture of Experts at scale, Sora, Claude 3
2025  Reasoning models, multi-modal agents
```

## Key Architecture Families

| Family | Key Idea | Best For |
|--------|----------|----------|
| MLP | Fully connected layers | Tabular data, simple mappings |
| CNN | Local receptive fields, weight sharing | Images, spatial data |
| RNN/LSTM | Sequential memory | Time series, sequences |
| Transformer | Self-attention | NLP, vision, multimodal |
| GAN | Adversarial training | Generation |
| Diffusion | Iterative denoising | High-quality generation |
| GNN | Message passing on graphs | Social networks, molecules |

## When to Use Deep Learning vs Traditional ML

### Use Deep Learning When:
- **Large dataset** (>10K-100K samples depending on task)
- **Unstructured data** (images, text, audio, video)
- **Complex patterns** that can't be hand-engineered
- **Compute budget** is available (GPUs/TPUs)
- **State-of-the-art** performance is required
- **End-to-end learning** is preferred over feature engineering

### Use Traditional ML When:
- **Small dataset** (<10K samples)
- **Structured/tabular data** (XGBoost often wins)
- **Interpretability** is critical (healthcare, finance regulations)
- **Low latency** inference on CPU is required
- **Limited compute** budget
- **Feature engineering** knowledge is available

### Decision Framework

```
                    ┌─────────────────┐
                    │  Data > 100K?   │
                    └────────┬────────┘
                        Yes/ \No
                          /   \
              ┌──────────┐   ┌──────────────┐
              │Unstructured│   │ Traditional  │
              │  data?     │   │ ML (XGBoost, │
              └─────┬──────┘   │ Random Forest│
                Yes/ \No       └──────────────┘
                  /   \
     ┌───────────┐   ┌────────────────┐
     │Deep Learning│   │ Try both DL &  │
     │ (CNN/Trans-│   │ Traditional ML │
     │  former)   │   │ Compare        │
     └───────────┘   └────────────────┘
```

## Hardware Landscape

| Hardware | Use Case | Memory | Cost |
|----------|----------|--------|------|
| NVIDIA A100 | Training large models | 40/80GB HBM | $$$$ |
| NVIDIA H100 | LLM training | 80GB HBM3 | $$$$$ |
| NVIDIA RTX 4090 | Research/small training | 24GB GDDR6X | $$ |
| Google TPU v4 | Large-scale training | 32GB HBM | Cloud |
| Apple M-series | Local inference | Unified memory | $ |
| CPU | Small inference | System RAM | $ |

## Frameworks

| Framework | Strengths | Used By |
|-----------|-----------|---------|
| PyTorch | Research flexibility, dynamic graphs | Meta, academia |
| TensorFlow | Production deployment, TFLite | Google |
| JAX | Functional, composable transforms | DeepMind |
| MLX | Apple Silicon native | Apple ecosystem |

## Directory Structure

```
03-Deep-Learning/
├── README.md (this file)
├── 01-Neural-Network-Fundamentals/
├── 02-Convolutional-Neural-Networks/
├── 03-Recurrent-Neural-Networks/
├── 04-Transformers-and-Attention/
├── 05-Generative-Models/
└── 06-Reinforcement-Learning/
```

## Production Considerations

1. **Model Serving**: TorchServe, TF Serving, Triton Inference Server, vLLM
2. **Optimization**: Quantization (INT8/INT4), pruning, distillation, ONNX
3. **Monitoring**: Data drift detection, performance degradation alerts
4. **Cost**: GPU hours, batch vs real-time inference tradeoffs
5. **MLOps**: Experiment tracking (W&B, MLflow), model registry, CI/CD for ML

## Learning Path

1. Start with Neural Network Fundamentals (backprop, activations)
2. Learn CNNs for computer vision tasks
3. Understand RNNs/LSTMs for sequence modeling
4. Master Transformers (the dominant architecture today)
5. Explore Generative Models (GANs, Diffusion)
6. Study Reinforcement Learning for decision-making


---

## Recommended Resources

For curated video courses, books, blogs, and practice platforms related to this section, see the comprehensive resources guide:

> **[RESOURCES.md](../RESOURCES.md)** — Organized by learning phase with free and paid options.
