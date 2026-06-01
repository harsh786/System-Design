# Meta-Learning: Learning to Learn

## Core Concept

```
Traditional ML:  Learn a TASK from DATA
Meta-Learning:   Learn to LEARN from a DISTRIBUTION OF TASKS

                ┌──────────────────────────────────────────┐
                │ Meta-training: many tasks (episodes)      │
                │   Task 1: {support set, query set}        │
                │   Task 2: {support set, query set}        │
                │   ...                                     │
                │   Task N: {support set, query set}        │
                │                                          │
                │ Meta-testing: new unseen task             │
                │   Given: K examples (support)             │
                │   Goal:  Classify new examples (query)    │
                └──────────────────────────────────────────┘
```

## Few-Shot Learning Formulation

```
N-way K-shot classification:
  - N classes per episode
  - K labeled examples per class (support set)
  - Evaluate on query set (unlabeled examples from same N classes)

Example: 5-way 1-shot
  Support: 1 image each of {dog, cat, car, plane, boat}
  Query:   "Which of these 5 classes does this new image belong to?"

Episode construction (during meta-training):
  1. Sample N classes from training classes
  2. Sample K examples per class → support set
  3. Sample Q examples per class → query set
  4. Train on support, evaluate on query, backprop meta-loss
```

## Metric-Based Methods

Learn an embedding space where similar items are close.

### Siamese Networks (Koch et al., 2015)

```
Input: pair (x₁, x₂)
Output: P(same class)

  x₁ → [Encoder] → z₁ ─┐
                          ├→ |z₁ - z₂| → σ(W|z₁-z₂|) → P(same)
  x₂ → [Encoder] → z₂ ─┘

Loss: Binary cross-entropy on pair similarity
```

### Matching Networks (Vinyals et al., 2016)

```
Classify query x by attention over support set:

  P(y=k|x, S) = Σᵢ a(x, xᵢ) · 1[yᵢ=k]
  
  a(x, xᵢ) = softmax(cosine(f(x), g(xᵢ)))

f = query encoder (with full context attention over S)
g = support encoder
```

### Prototypical Networks (Snell et al., 2017)

```
Key idea: Each class represented by PROTOTYPE (mean embedding)

  cₖ = (1/|Sₖ|) Σ_{(xᵢ,yᵢ)∈Sₖ} f_φ(xᵢ)    (class prototype)

  P(y=k|x) = softmax(-d(f_φ(x), cₖ))          (distance to prototype)

┌───────────────────────────────────────┐
│  Embedding Space:                      │
│                                        │
│    ★ c₁     (class 1 prototype)       │
│   ● ●       (class 1 support)         │
│        ◆    (query → closest to c₁)   │
│                                        │
│         ★ c₂  (class 2 prototype)     │
│        ▲ ▲    (class 2 support)       │
└───────────────────────────────────────┘

Simple, effective, and has nice theoretical properties
(equivalent to linear classifier in embedding space)
```

```python
import torch
import torch.nn.functional as F

class PrototypicalNetwork(torch.nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder  # e.g., Conv4, ResNet12
    
    def forward(self, support, query, n_way, k_shot):
        # support: [n_way * k_shot, C, H, W]
        # query:   [n_way * q_query, C, H, W]
        
        z_support = self.encoder(support)  # [n_way*k_shot, d]
        z_query = self.encoder(query)      # [n_way*q, d]
        
        # Compute prototypes
        z_support = z_support.view(n_way, k_shot, -1)
        prototypes = z_support.mean(dim=1)  # [n_way, d]
        
        # Euclidean distance query → prototypes
        dists = torch.cdist(z_query, prototypes)  # [n_q, n_way]
        log_probs = F.log_softmax(-dists, dim=1)
        return log_probs
```

## Model-Based Methods

### MANN (Memory-Augmented Neural Networks)

```
Use external memory to store and retrieve task information:
  - Write support examples to memory
  - Read from memory to classify queries
  - Memory acts as a differentiable lookup table

Architecture: Controller + External Memory (like NTM)
```

### SNAIL (Simple Neural AttentIve Learner)

```
Interleave temporal convolutions + attention:
  - Temporal conv: aggregate info from recent inputs
  - Attention: pinpoint specific relevant past inputs
  
Process support set sequentially, then classify query
using all accumulated context.
```

## Optimization-Based Methods

### MAML (Model-Agnostic Meta-Learning, Finn et al., 2017)

```
Key idea: Find initialization θ that can be quickly adapted to any task.

┌──────────────────────────────────────────────────────────────┐
│ Algorithm: MAML                                               │
│                                                              │
│ Require: Task distribution p(T), step sizes α, β            │
│ Initialize θ randomly                                        │
│                                                              │
│ while not converged:                                         │
│   Sample batch of tasks {Tᵢ} ~ p(T)                         │
│   for each task Tᵢ:                                         │
│     Sample support set Sᵢ and query set Qᵢ                  │
│     // Inner loop: task-specific adaptation                  │
│     θᵢ' = θ - α ∇_θ L(θ, Sᵢ)                              │
│                                                              │
│   // Outer loop: meta-update                                 │
│   θ ← θ - β ∇_θ Σᵢ L(θᵢ', Qᵢ)                            │
│                     ↑                                        │
│         Evaluate adapted params on QUERY set                 │
│         Backprop THROUGH the inner gradient step             │
└──────────────────────────────────────────────────────────────┘

At test time:
  θ_new = θ - α ∇_θ L(θ, S_new)  (1-5 gradient steps)
  Predict on query using θ_new
```

```python
import torch
import torch.nn.functional as F
from copy import deepcopy

class MAML:
    def __init__(self, model, inner_lr=0.01, outer_lr=0.001, inner_steps=5):
        self.model = model
        self.inner_lr = inner_lr
        self.outer_lr = outer_lr
        self.inner_steps = inner_steps
        self.meta_optim = torch.optim.Adam(model.parameters(), lr=outer_lr)
    
    def inner_loop(self, support_x, support_y):
        """Adapt model to a single task"""
        fast_weights = {name: p.clone() for name, p in self.model.named_parameters()}
        
        for _ in range(self.inner_steps):
            logits = self.model.functional_forward(support_x, fast_weights)
            loss = F.cross_entropy(logits, support_y)
            grads = torch.autograd.grad(loss, fast_weights.values(), create_graph=True)
            fast_weights = {
                name: w - self.inner_lr * g 
                for (name, w), g in zip(fast_weights.items(), grads)
            }
        return fast_weights
    
    def meta_step(self, tasks):
        """One meta-training step over a batch of tasks"""
        meta_loss = 0
        for support_x, support_y, query_x, query_y in tasks:
            fast_weights = self.inner_loop(support_x, support_y)
            query_logits = self.model.functional_forward(query_x, fast_weights)
            meta_loss += F.cross_entropy(query_logits, query_y)
        
        self.meta_optim.zero_grad()
        meta_loss.backward()
        self.meta_optim.step()
        return meta_loss.item() / len(tasks)
```

### Reptile (Nichol et al., 2018)

```
Simpler first-order approximation of MAML:

  for each iteration:
    Sample task T
    θ̃ = θ
    for k steps:
      θ̃ = θ̃ - α ∇L_T(θ̃)    (standard SGD on task)
    θ = θ + β(θ̃ - θ)          (move toward adapted params)

No second-order gradients needed!
Surprisingly competitive with MAML.
```

## In-Context Learning as Meta-Learning

```
GPT-style models perform meta-learning implicitly:

Prompt: "cat → gato, dog → perro, house → "
Output: "casa"

The model learned to learn translation from context!

Connection to MAML:
  - Pre-training ≈ outer loop (learn good initialization)
  - In-context examples ≈ inner loop (task adaptation via attention)
  - No explicit gradient steps, but attention implements soft adaptation

Key insight: Transformer attention can simulate gradient descent
(von Oswald et al., 2023; Akyürek et al., 2023)
```

## Comparison Table

| Method | Type | Pros | Cons |
|--------|------|------|------|
| Prototypical Nets | Metric | Simple, fast inference | Fixed distance metric |
| Matching Nets | Metric | Attention-based | Expensive at test time |
| MAML | Optimization | Model-agnostic, expressive | Second-order gradients, slow |
| Reptile | Optimization | Simple, first-order | Less principled than MAML |
| SNAIL | Model-based | Flexible, powerful | Complex architecture |

## Applications

### Personalization
- Few interactions → personalized model
- Example: Keyboard prediction adapting to new user with 10 sentences

### Cold-Start Problem
- New user/item in recommendation system
- Meta-learn from similar users, adapt with few interactions

### Low-Resource Languages
- Meta-train on high-resource languages
- Adapt to new language with limited parallel text

### Drug Discovery
- Few molecules tested for a new protein target
- Meta-learn molecular property predictor across many targets

### Robotics
- Learn a manipulation skill from 5 demonstrations
- Meta-train across many different objects/tasks

## Interview Questions

1. Explain the difference between metric-based and optimization-based meta-learning.
2. Why does MAML require second-order gradients? How does Reptile avoid this?
3. How is in-context learning related to meta-learning?
4. When would you use Prototypical Networks vs MAML?
5. How would you apply meta-learning to a cold-start recommendation problem?
6. What is the episode-based training paradigm and why is it important?

## Key Papers

- Vinyals et al., "Matching Networks for One Shot Learning" (2016)
- Snell et al., "Prototypical Networks for Few-shot Learning" (2017)
- Finn et al., "Model-Agnostic Meta-Learning (MAML)" (2017)
- Nichol et al., "On First-Order Meta-Learning Algorithms (Reptile)" (2018)
- Hospedales et al., "Meta-Learning in Neural Networks: A Survey" (2021)
- von Oswald et al., "Transformers Learn In-Context by Gradient Descent" (2023)
