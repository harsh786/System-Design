# 28 — AI vs ML vs DL vs NLP vs Computer Vision

## The Complete Comparison, Decision Guide & Use Case Reference

> "A Staff Architect knows not just WHAT each domain does, but WHEN to use it,
> WHY it works there, and WHERE domains overlap in production systems."

---

## What This Section Covers

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                      │
│  "I have a problem. Which AI domain do I need? Why? How do they relate?"            │
│                                                                                      │
│  This section answers:                                                               │
│  • What is AI vs ML vs DL vs NLP vs CV?                                             │
│  • How do they relate (hierarchy + overlap)?                                        │
│  • What problem does each domain solve?                                              │
│  • When should I use which approach?                                                 │
│  • What are the real-world production use cases?                                    │
│  • How do I choose the right approach for my problem?                               │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## File Index

### Part 1: Domain Overview & When-To-Use (Files 00-07)

| # | File | Content | Key Question Answered |
|---|------|---------|----------------------|
| 00 | [Overview & Comparison](./00-Overview-and-Comparison.md) | Master hierarchy, relationship diagrams, comparison tables | "How do all 5 domains relate?" |
| 01 | [Artificial Intelligence](./01-Artificial-Intelligence.md) | AI types (ANI/AGI/ASI), branches, approaches, rule-based systems | "What is AI beyond just ML?" |
| 02 | [Machine Learning](./02-Machine-Learning.md) | Supervised/Unsupervised/RL, algorithms, pipeline, evaluation | "When do I use classical ML?" |
| 03 | [Deep Learning](./03-Deep-Learning.md) | Neural networks, CNNs, Transformers, generative models, transfer learning | "When do I need deep learning?" |
| 04 | [Natural Language Processing](./04-Natural-Language-Processing.md) | NLP pipeline, tasks, BERT/GPT evolution, modern approaches | "How do I work with text data?" |
| 05 | [Computer Vision](./05-Computer-Vision.md) | Detection, segmentation, classical vs DL, model selection | "How do I work with image data?" |
| 06 | [Decision Workflow](./06-Decision-Workflow-When-To-Use-What.md) | Complete decision trees, cost/accuracy tradeoffs, iteration strategy | "Given my problem, what should I use?" |
| 07 | [Real-World Use Cases](./07-Real-World-Use-Cases.md) | Industry cases mapped to domains with rationale | "How are companies using this?" |

### Part 2: Algorithm & Architecture Deep Dives (Files 08-11)

| # | File | Content | Key Question Answered |
|---|------|---------|----------------------|
| 08 | [ML Algorithms Deep Dive](./08-ML-Algorithms-Deep-Dive.md) | Every ML algo with math, internals, hyperparams: LinReg, LogReg, Trees, RF, XGBoost, SVM, KNN, NaiveBayes, KMeans, DBSCAN, PCA, Isolation Forest, Ensembles, GMM | "How does each ML algorithm actually work?" |
| 09 | [DL Architectures Deep Dive](./09-DL-Architectures-Deep-Dive.md) | Backprop math, all optimizers (SGD→AdamW→LAMB), loss functions, LR schedules, CNN internals, Transformer internals (Q/K/V, MHA, RoPE, Flash Attention), MoE, Mamba/SSM, Diffusion, GAN, GNN, RLHF/DPO, PEFT/LoRA, Quantization | "How does each DL architecture work under the hood?" |
| 10 | [Frameworks & Tools Ecosystem](./10-Frameworks-and-Tools-Ecosystem.md) | Every framework: scikit-learn, XGBoost, PyTorch, TensorFlow, JAX, HuggingFace, spaCy, LangChain, vLLM, OpenCV, YOLOv8, MLflow, W&B, vector DBs, cloud platforms | "Which tool do I use for what?" |
| 11 | [Advanced Concepts](./11-Advanced-Concepts-and-Techniques.md) | Semi-supervised, active learning, few-shot, federated learning, edge AI, drift detection, fairness/bias, online learning, RAG architecture, prompt engineering, decoding strategies | "What advanced techniques am I missing?" |

### Part 3: Runnable Code (File 12)

| # | File | Content | Key Question Answered |
|---|------|---------|----------------------|
| 12 | [Code Examples](./12-Code-Examples-and-Implementations.md) | Production Python snippets: sklearn pipelines, XGBoost/LightGBM/CatBoost, PyTorch CNN/training loops, Transformer from scratch, BERT fine-tuning, HuggingFace NLP, YOLOv8, SAM, RAG (LangChain + from scratch), MLflow, FastAPI serving, drift detection, full end-to-end pipelines | "Show me the code!" |

---

## Quick Reference

```
TEXT data?                → NLP (04)
IMAGE data?              → Computer Vision (05)
TABULAR data?            → Machine Learning (02)
NEED GENERATION?         → Deep Learning (03)
NEED PLANNING?           → AI (01)
DON'T KNOW?              → Decision Workflow (06)
WANT EXAMPLES?           → Use Cases (07)
HOW does algo X work?    → ML Algorithms (08)
HOW does architecture work? → DL Architectures (09)
WHICH tool to use?       → Frameworks (10)
ADVANCED techniques?     → Advanced Concepts (11)
SHOW ME THE CODE?        → Code Examples (12)
```

---

## The One Diagram That Explains Everything

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARTIFICIAL INTELLIGENCE                                    │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────┐         │
│   │              MACHINE LEARNING                                  │         │
│   │                                                                │         │
│   │   ┌───────────────────────────────────────────────────┐       │         │
│   │   │           DEEP LEARNING                            │       │         │
│   │   │                                                    │       │         │
│   │   │   ┌──────────────┐    ┌──────────────────┐       │       │         │
│   │   │   │     NLP      │    │ Computer Vision  │       │       │         │
│   │   │   └──────────────┘    └──────────────────┘       │       │         │
│   │   │                                                    │       │         │
│   │   └───────────────────────────────────────────────────┘       │         │
│   │                                                                │         │
│   └───────────────────────────────────────────────────────────────┘         │
│                                                                              │
│   + Expert Systems + Search + Planning + Knowledge Graphs                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Total Content: ~8,000+ lines across 13 files with 30+ Mermaid diagrams, 50+ ASCII workflow diagrams, and 30+ runnable Python examples
