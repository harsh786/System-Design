# Advanced Theory for ML/AI

## Why Theory Matters for Staff+ Engineers

Theory is not academic luxury — it is the difference between an engineer who tunes hyperparameters
and an architect who knows *why* certain approaches work, *when* they will fail, and *what* the
fundamental limits are.

## What This Section Covers

| Module | Core Question |
|--------|--------------|
| 01 - Bayesian ML | How do we reason under uncertainty? |
| 02 - Causal Inference | How do we move from correlation to causation? |
| 03 - Graph Neural Networks | How do we learn on relational/structured data? |
| 04 - Learning Theory (PAC/VC) | What are the fundamental limits of learning? |
| 05 - Meta-Learning | How do we learn to learn efficiently? |
| 06 - Federated Learning | How do we learn without centralizing data? |

## How Theory Guides Intuition

```
Theory Knowledge → Architectural Intuition → Better System Design
     ↓                      ↓                        ↓
 VC Dimension      "This model is too complex"   Regularization choices
 Bayes' Rule       "We need uncertainty"         Probabilistic outputs
 Causal DAGs       "Correlation ≠ causation"     Debiased recommendations
 PAC bounds        "More data needed"            Data collection strategy
```

## Reading Order

1. Start with **Learning Theory** (04) for foundations
2. Then **Bayesian ML** (01) for probabilistic reasoning
3. Then **Causal Inference** (02) for moving beyond prediction
4. **GNNs** (03), **Meta-Learning** (05), **Federated** (06) in any order

## Staff Architect Perspective

At L6+/Staff level, you are expected to:
- Know when a problem is fundamentally unsolvable (No Free Lunch)
- Quantify uncertainty in model predictions
- Reason about causality in A/B tests and recommendation systems
- Choose architectures based on data structure (graphs, sequences, etc.)
- Design privacy-preserving ML systems
- Understand scaling laws to plan compute budgets
