# Information Theory for AI/ML/Deep Learning

## Why Information Theory Matters for ML

Information theory, created by Claude Shannon in 1948, quantifies information, uncertainty, and surprise. In ML, it provides:
- The theoretical foundation for **loss functions** (cross-entropy)
- The splitting criterion for **decision trees** (information gain)
- The training objective for **GANs** and **VAEs** (KL divergence)
- Measures of **feature relevance** (mutual information)

---

## 1. Information Content and Entropy

### Information Content (Surprise)

The information content of an event measures how "surprising" it is:

```
I(x) = -log₂ P(x)

Rare event (P small)   → high information (very surprising)
Common event (P large) → low information (not surprising)
```

**Analogy:** "The sun rose today" → low information (expected). "It snowed in July" → high information (unexpected).

```
P(x)    I(x) = -log₂P(x)
─────   ──────────────────
1.0     0 bits      (certain → no surprise)
0.5     1 bit       (coin flip)
0.25    2 bits
0.125   3 bits
0.01    6.64 bits   (rare → very surprising!)
```

### Entropy (H)

The **expected information content** — average surprise across all events.

```
H(X) = -Σ P(xᵢ) · log₂ P(xᵢ)
```

```
Entropy measures uncertainty/disorder:

Low entropy (certain):     High entropy (uncertain):
P = [0.99, 0.01]          P = [0.25, 0.25, 0.25, 0.25]
H ≈ 0.08 bits             H = 2 bits

Almost certain of          Maximum uncertainty
one outcome                (uniform = max entropy)
```

**Analogy:** Entropy = how many yes/no questions you need (on average) to identify the outcome.

```python
import numpy as np

def entropy(probs):
    """Shannon entropy in bits."""
    probs = np.array(probs)
    probs = probs[probs > 0]  # Avoid log(0)
    return -np.sum(probs * np.log2(probs))

# Fair coin: maximum entropy for 2 outcomes
print(entropy([0.5, 0.5]))      # 1.0 bit

# Biased coin: lower entropy
print(entropy([0.9, 0.1]))      # 0.469 bits

# Fair die: maximum entropy for 6 outcomes
print(entropy([1/6]*6))          # 2.585 bits

# Uniform over n outcomes gives H = log₂(n)
```

### Properties of Entropy

```
1. H(X) ≥ 0                           (always non-negative)
2. H(X) = 0 iff X is deterministic    (no uncertainty)
3. H(X) ≤ log₂(n)                     (maximum when uniform)
4. H(X,Y) ≤ H(X) + H(Y)              (joint ≤ sum, equal if independent)
```

---

## 2. Cross-Entropy

### Definition

Cross-entropy measures the average number of bits needed to encode events from distribution P using a code optimized for distribution Q.

```
H(P, Q) = -Σ P(xᵢ) · log Q(xᵢ)
```

```
If P = true distribution, Q = model's predicted distribution:
H(P, Q) = how well Q approximates P

H(P, Q) ≥ H(P)  (always worse or equal to optimal)
H(P, Q) = H(P)  only when Q = P (perfect model)
```

### Cross-Entropy as a Loss Function

This is THE standard loss function for classification:

```python
def cross_entropy_loss(y_true, y_pred):
    """
    y_true: one-hot encoded labels [0, 0, 1, 0, ...]
    y_pred: model's predicted probabilities (after softmax)
    """
    # Clip to avoid log(0)
    y_pred = np.clip(y_pred, 1e-15, 1 - 1e-15)
    return -np.sum(y_true * np.log(y_pred))

# Binary cross-entropy
def binary_cross_entropy(y_true, y_pred):
    """For binary classification."""
    return -np.mean(
        y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred)
    )
```

**Why cross-entropy and not MSE for classification?**
- Cross-entropy has stronger gradients when predictions are wrong
- MSE gradients vanish near 0 and 1 (sigmoid saturation)
- Cross-entropy is the theoretically correct loss (MLE for categorical distribution)

```
Gradient comparison (binary classification):

Cross-entropy gradient:     MSE gradient:
│ ████                      │ ██
│ ████                      │ ███
│ ████                      │ ████
│ ████                      │ ███
│ ████                      │ ██
└─────── predicted prob     └─────── predicted prob
Strong signal everywhere    Vanishes at extremes!
```

---

## 3. KL Divergence (Kullback-Leibler Divergence)

### Definition

Measures how much one distribution diverges from another. The "extra bits" needed.

```
KL(P || Q) = Σ P(xᵢ) · log(P(xᵢ) / Q(xᵢ))
           = H(P, Q) - H(P)
           = Cross-entropy - Entropy
```

### Key Properties

```
1. KL(P||Q) ≥ 0              (Gibbs' inequality)
2. KL(P||Q) = 0  iff P = Q   (zero only when distributions are identical)
3. KL(P||Q) ≠ KL(Q||P)       (NOT symmetric! Not a true distance)
```

### Asymmetry and Its Implications

```
KL(P||Q): "Forward KL" — Q must cover all of P's mass
           → Mode-covering (Q spreads out)
           → Used in variational inference (ELBO)

KL(Q||P): "Reverse KL" — Q can ignore parts of P
           → Mode-seeking (Q concentrates)
           → Used in policy optimization

P:  ___╱╲___╱╲___     (bimodal)

Forward KL(P||Q):    Reverse KL(Q||P):
Q:  ___╱────────╲__   Q:  _____╱╲________
    (covers both)          (picks one mode)
```

```python
def kl_divergence(p, q):
    """KL(P || Q)"""
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)
    # Only where p > 0
    mask = p > 0
    return np.sum(p[mask] * np.log(p[mask] / q[mask]))

# Example
p = [0.4, 0.6]
q = [0.5, 0.5]
print(f"KL(P||Q) = {kl_divergence(p, q):.4f}")  # 0.0204
print(f"KL(Q||P) = {kl_divergence(q, p):.4f}")  # 0.0206 (different!)
```

### ML Applications of KL Divergence

1. **VAE Loss:** ELBO = Reconstruction - KL(q(z|x) || p(z))
2. **Knowledge Distillation:** Match student to teacher distribution
3. **Regularization:** Penalize deviation from prior
4. **Policy gradient (RL):** Trust region (limit KL between old/new policy)

```python
# VAE loss
def vae_loss(x_reconstructed, x_original, mu, log_var):
    # Reconstruction loss (cross-entropy or MSE)
    recon_loss = binary_cross_entropy(x_original, x_reconstructed)
    
    # KL divergence: KL(N(mu, sigma) || N(0, 1))
    # Closed form for two Gaussians:
    kl_loss = -0.5 * np.sum(1 + log_var - mu**2 - np.exp(log_var))
    
    return recon_loss + kl_loss
```

---

## 4. Mutual Information

### Definition

How much knowing X tells you about Y (and vice versa).

```
I(X; Y) = H(X) + H(Y) - H(X, Y)
         = H(X) - H(X|Y)
         = KL(P(X,Y) || P(X)P(Y))
```

```
Venn diagram of information:

    ┌──────────┬──────────┐
    │          │          │
    │  H(X|Y) │  I(X;Y)  │  H(Y|X)  │
    │          │          │
    └──────────┴──────────┘
    
    ├── H(X) ──┤          ├── H(Y) ──┤
    
    I(X;Y) = shared information between X and Y
    H(X|Y) = uncertainty about X that Y doesn't resolve
```

### Properties

```
I(X;Y) ≥ 0
I(X;Y) = 0  iff X and Y are independent
I(X;Y) = I(Y;X)  (symmetric!)
I(X;X) = H(X)    (variable has maximum info about itself)
```

### ML Applications

```python
from sklearn.feature_selection import mutual_info_classif

# Feature selection: which features are most informative about the label?
X = np.random.randn(1000, 10)
y = (X[:, 0] + X[:, 1] > 0).astype(int)  # Label depends on features 0,1

mi_scores = mutual_info_classif(X, y)
# Features 0 and 1 will have high MI, others near zero
print("MI scores:", mi_scores.round(3))
```

**Applications:**
- **Feature selection:** Pick features with high MI with target
- **InfoGAN:** Maximize MI between latent codes and generated outputs
- **Representation learning:** Learn representations that maximize MI with inputs (contrastive learning)
- **Decision trees:** Information gain = MI between feature and label

---

## 5. Information Gain (Decision Trees)

```
Information Gain = H(parent) - Σ (|child|/|parent|) · H(child)
                = Reduction in entropy after splitting

Higher IG → Better split → More informative feature
```

```
Before split:          After split on feature "Age > 30":
H = 1.0 bit           
                       Age ≤ 30:  H = 0.5 bits (more certain)
[50% yes, 50% no]     Age > 30:  H = 0.2 bits (very certain)

IG = 1.0 - (0.5 × 0.5 + 0.5 × 0.2) = 0.65 bits gained!
```

```python
def information_gain(parent_labels, left_labels, right_labels):
    H_parent = entropy_from_labels(parent_labels)
    n = len(parent_labels)
    n_left, n_right = len(left_labels), len(right_labels)
    
    H_children = (n_left/n) * entropy_from_labels(left_labels) + \
                 (n_right/n) * entropy_from_labels(right_labels)
    
    return H_parent - H_children

def entropy_from_labels(labels):
    _, counts = np.unique(labels, return_counts=True)
    probs = counts / len(labels)
    return -np.sum(probs * np.log2(probs))
```

---

## 6. Applications Summary

### Loss Functions

```
┌─────────────────────────────────────────────────────────┐
│ Task              │ Loss Function    │ Info Theory Basis │
├───────────────────┼──────────────────┼───────────────────┤
│ Classification    │ Cross-entropy    │ H(P, Q)          │
│ Binary classif.   │ Binary CE        │ H(P, Q) for 2    │
│ VAE training      │ ELBO             │ KL divergence    │
│ GAN training      │ JS divergence    │ Symmetric KL     │
│ Knowledge distill │ KL(teacher||stud)│ KL divergence    │
│ Decision trees    │ Information gain │ Entropy reduction│
│ Contrastive learn │ InfoNCE          │ Mutual info bound│
└───────────────────┴──────────────────┴───────────────────┘
```

### GANs and Divergences

```
Original GAN objective ≈ minimizing Jensen-Shannon divergence:
JS(P||Q) = ½ KL(P||M) + ½ KL(Q||M),  where M = ½(P+Q)

WGAN uses Wasserstein distance instead (more stable training)
```

---

## Key Takeaways

1. **Entropy** = uncertainty. Model training reduces entropy of predictions.
2. **Cross-entropy loss** = the standard classification loss, grounded in information theory.
3. **KL divergence** = how different two distributions are. Appears in VAEs, distillation, RL.
4. **Mutual information** = shared information. Used for feature selection and contrastive learning.
5. **Information gain** = entropy reduction. The splitting criterion for decision trees.
6. **Minimizing cross-entropy = maximizing likelihood.** Same thing, different perspective.
