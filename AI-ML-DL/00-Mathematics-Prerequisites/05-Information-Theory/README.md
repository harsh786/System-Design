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

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** Compute the information content (surprise) of: (a) rolling a 6 on a fair die, (b) flipping heads on a fair coin, (c) an event with P=0.01.

**Hint:** I(x) = -log₂P(x)

<details><summary>Solution</summary>

```
(a) P(6) = 1/6 → I = -log₂(1/6) = log₂(6) ≈ 2.585 bits
(b) P(H) = 1/2 → I = -log₂(1/2) = 1 bit
(c) P = 0.01 → I = -log₂(0.01) = log₂(100) ≈ 6.644 bits
```
</details>

### Exercise 2 (Beginner)
**Problem:** Compute the entropy of: (a) a fair coin, (b) a biased coin with P(H)=0.9, (c) a fair 8-sided die.

**Hint:** H(X) = -Σ P(xᵢ)log₂P(xᵢ)

<details><summary>Solution</summary>

```
(a) H = -[0.5log₂(0.5) + 0.5log₂(0.5)] = -[-0.5-0.5] = 1 bit
(b) H = -[0.9log₂(0.9) + 0.1log₂(0.1)] = -[-0.137-0.332] = 0.469 bits
(c) H = -8×(1/8)log₂(1/8) = -8×(1/8)×(-3) = 3 bits

Note: Fair coin = 1 bit (one yes/no question), biased coin < 1 bit (less uncertain)
```
</details>

### Exercise 3 (Beginner)
**Problem:** Compute the cross-entropy H(P,Q) where P=[0.7, 0.2, 0.1] (true) and Q=[0.5, 0.3, 0.2] (predicted). Also compute KL divergence D_KL(P||Q).

**Hint:** H(P,Q) = -Σ P(x)log₂Q(x). D_KL = H(P,Q) - H(P).

<details><summary>Solution</summary>

```
H(P,Q) = -[0.7log₂(0.5) + 0.2log₂(0.3) + 0.1log₂(0.2)]
       = -[0.7(-1) + 0.2(-1.737) + 0.1(-2.322)]
       = -[-0.7 - 0.347 - 0.232] = 1.280 bits

H(P) = -[0.7log₂(0.7) + 0.2log₂(0.2) + 0.1log₂(0.1)]
     = -[0.7(-0.515) + 0.2(-2.322) + 0.1(-3.322)]
     = -[-0.360 - 0.464 - 0.332] = 1.157 bits

D_KL(P||Q) = H(P,Q) - H(P) = 1.280 - 1.157 = 0.123 bits
```
</details>

### Exercise 4 (Beginner)
**Problem:** A decision tree splits on feature A, producing: left child (30 class-0, 10 class-1) and right child (5 class-0, 25 class-1). Compute the information gain.

**Hint:** IG = H(parent) - weighted average H(children).

<details><summary>Solution</summary>

```
Parent: 35 class-0, 35 class-1 → P=[0.5, 0.5] → H(parent) = 1 bit

Left (40 samples): P=[30/40, 10/40]=[0.75, 0.25]
H(left) = -[0.75log₂(0.75)+0.25log₂(0.25)] = 0.811 bits

Right (30 samples): P=[5/30, 25/30]=[0.167, 0.833]
H(right) = -[0.167log₂(0.167)+0.833log₂(0.833)] = 0.650 bits

Weighted: (40/70)×0.811 + (30/70)×0.650 = 0.463 + 0.279 = 0.742

Information Gain = 1.0 - 0.742 = 0.258 bits
```
</details>

### Exercise 5 (Intermediate)
**Problem:** Show that H(X) ≤ log₂(n) where n is the number of possible outcomes, with equality iff X is uniform.

**Hint:** Use Jensen's inequality or Lagrange multipliers.

<details><summary>Solution</summary>

```
Want to maximize H(X) = -Σ pᵢlog₂pᵢ subject to Σpᵢ = 1.

Using Lagrange multipliers:
L = -Σ pᵢlog₂pᵢ - λ(Σpᵢ - 1)
∂L/∂pᵢ = -log₂pᵢ - 1/ln2 - λ = 0
→ log₂pᵢ = -(1/ln2 + λ) = constant for all i
→ pᵢ = 1/n for all i (uniform!)

H(uniform) = -n×(1/n)log₂(1/n) = log₂(n)

Alternative: D_KL(P||U) ≥ 0 where U is uniform
D_KL(P||U) = Σ pᵢ log(pᵢ/(1/n)) = log(n) - H(P) ≥ 0
→ H(P) ≤ log(n) ✓
```
</details>

### Exercise 6 (Intermediate)
**Problem:** Compute the mutual information I(X;Y) between two binary variables where:
P(X=0,Y=0)=0.4, P(X=0,Y=1)=0.1, P(X=1,Y=0)=0.1, P(X=1,Y=1)=0.4.

**Hint:** I(X;Y) = H(X) + H(Y) - H(X,Y) or I(X;Y) = Σ P(x,y)log[P(x,y)/(P(x)P(y))].

<details><summary>Solution</summary>

```
Marginals: P(X=0)=0.5, P(X=1)=0.5, P(Y=0)=0.5, P(Y=1)=0.5

H(X) = H(Y) = 1 bit
H(X,Y) = -[0.4log₂(0.4)+0.1log₂(0.1)+0.1log₂(0.1)+0.4log₂(0.4)]
       = -[2×0.4×(-1.322) + 2×0.1×(-3.322)]
       = -[-1.058 - 0.664] = 1.722 bits

I(X;Y) = H(X) + H(Y) - H(X,Y) = 1 + 1 - 1.722 = 0.278 bits

X and Y share 0.278 bits of information (they're correlated: tend to be equal).
```
</details>

### Exercise 7 (Intermediate)
**Problem:** In a VAE, the loss is: L = E_q[log p(x|z)] - D_KL(q(z|x) || p(z)). Explain what each term means and why minimizing this maximizes a lower bound on log p(x).

**Hint:** This is the Evidence Lower Bound (ELBO). Derive from log p(x) using Jensen's inequality.

<details><summary>Solution</summary>

```
Start: log p(x) = log ∫ p(x|z)p(z)dz

Introduce q(z|x):
log p(x) = log ∫ p(x|z)p(z)/q(z|x) × q(z|x) dz
          ≥ ∫ q(z|x) log[p(x|z)p(z)/q(z|x)] dz  (Jensen's inequality)
          = E_q[log p(x|z)] + E_q[log p(z)/q(z|x)]
          = E_q[log p(x|z)] - D_KL(q(z|x)||p(z))
          = ELBO

Terms:
- E_q[log p(x|z)]: Reconstruction quality (decoder likelihood)
- D_KL(q(z|x)||p(z)): Regularization (push encoder toward prior N(0,I))

Gap: log p(x) - ELBO = D_KL(q(z|x)||p(z|x)) ≥ 0
Maximizing ELBO = maximizing log p(x) + making q approximate true posterior.
```
</details>

### Exercise 8 (Intermediate)
**Problem:** Explain why cross-entropy is preferred over MSE for classification tasks. What happens to gradients of MSE with sigmoid outputs near 0 or 1?

**Hint:** Compute ∂MSE/∂z vs ∂CE/∂z where output = σ(z).

<details><summary>Solution</summary>

```
Let a = σ(z) (sigmoid output), y ∈ {0,1}

MSE loss: L = (a-y)²
∂L/∂z = 2(a-y)·σ'(z) = 2(a-y)·a(1-a)

Cross-entropy: L = -[y·log(a)+(1-y)·log(1-a)]
∂L/∂z = a - y

Problem with MSE:
When a≈0 or a≈1: σ'(z)=a(1-a)≈0
→ MSE gradient ≈ 0 even when prediction is WRONG!
→ Learning stalls (sigmoid saturation)

Cross-entropy gradient = (a-y):
- Proportional to error
- No σ'(z) factor → no saturation problem
- Larger error → larger gradient → faster learning

This is why cross-entropy is the natural loss for classification.
```
</details>

### Exercise 9 (Advanced)
**Problem:** Derive the optimal discriminator in a GAN and show that the generator loss is related to the Jensen-Shannon divergence.

**Hint:** GAN objective: min_G max_D E_x[log D(x)] + E_z[log(1-D(G(z)))].

<details><summary>Solution</summary>

```
For fixed G, optimize D:
V(D) = ∫ [p_data(x)log D(x) + p_g(x)log(1-D(x))] dx

For each x, maximize: p_data log(D) + p_g log(1-D)
∂/∂D = p_data/D - p_g/(1-D) = 0
→ D*(x) = p_data(x) / (p_data(x) + p_g(x))

Substituting D* back:
V(G,D*) = E_data[log(p_data/(p_data+p_g))] + E_g[log(p_g/(p_data+p_g))]
= E_data[log(p_data) - log((p_data+p_g)/2) - log2]
  + E_g[log(p_g) - log((p_data+p_g)/2) - log2]
= -log4 + D_KL(p_data || (p_data+p_g)/2) + D_KL(p_g || (p_data+p_g)/2)
= -log4 + 2·JSD(p_data || p_g)

Minimum when p_data = p_g → JSD = 0 → V = -log4.
Generator minimizes Jensen-Shannon divergence between real and generated distributions!
```
</details>

### Exercise 10 (Advanced)
**Problem:** Explain the Information Bottleneck method. How does it formalize the tradeoff between compression and prediction in deep learning?

**Hint:** Minimize I(X;T) - β·I(T;Y) where T is the representation.

<details><summary>Solution</summary>

```
Information Bottleneck:
Given: input X, target Y, representation T (hidden layer)
Optimize: min I(X;T) - β·I(T;Y)

Terms:
- I(X;T): how much T remembers about input (minimize → compress)
- I(T;Y): how much T retains about target (maximize → predict)
- β: trade-off parameter

Deep Learning interpretation:
- Each layer compresses: I(X;T_l) decreases deeper in network
- Each layer preserves: I(T_l;Y) remains high
- Training has two phases:
  1. Fitting: I(T;Y) increases rapidly (learning signal)
  2. Compression: I(X;T) decreases slowly (forgetting noise)

Connection to generalization:
- Good representations compress out irrelevant input details
- Retain only information needed for prediction
- PAC-Bayes bound: generalization ∝ I(X;T) → less memorization = better
```
</details>

### Exercise 11 (Advanced)
**Problem:** Prove the data processing inequality: if X → Y → Z forms a Markov chain, then I(X;Z) ≤ I(X;Y).

**Hint:** Use the chain rule for mutual information and the Markov property.

<details><summary>Solution</summary>

```
Chain rule: I(X; Y,Z) = I(X;Z) + I(X;Y|Z) = I(X;Y) + I(X;Z|Y)

Markov chain X→Y→Z means: X ⊥ Z | Y
Therefore: I(X;Z|Y) = 0

So: I(X;Y) + 0 = I(X;Z) + I(X;Y|Z)
    I(X;Y) = I(X;Z) + I(X;Y|Z)

Since I(X;Y|Z) ≥ 0:
    I(X;Y) ≥ I(X;Z) ✓

Intuition: Processing data can only lose information, never gain it.
Each layer in a neural network can only lose information about the input.
The task of learning is to lose the RIGHT information (noise, not signal).
```
</details>

### Exercise 12 (Advanced)
**Problem:** Derive the connection between softmax temperature and entropy. What happens to the output distribution as T→0 and T→∞?

**Hint:** Softmax with temperature: p_i = exp(z_i/T) / Σ exp(z_j/T).

<details><summary>Solution</summary>

```
Standard softmax: p_i = exp(z_i) / Σ exp(z_j)
Temperature-scaled: p_i = exp(z_i/T) / Σ exp(z_j/T)

As T → 0 (low temperature):
- exp(z_max/T) dominates → p_max → 1, others → 0
- Entropy H → 0
- Distribution becomes one-hot (argmax)
- "Confident" predictions

As T → ∞ (high temperature):
- All exp(z_i/T) → 1 → p_i → 1/n (uniform)
- Entropy H → log(n) (maximum)
- All classes equally likely
- "Uncertain" / maximum entropy

As T = 1: Standard softmax

Applications:
- Knowledge distillation: T=2-20 (softer targets reveal class relationships)
- Exploration in RL: high T for exploration, anneal toward T=1
- Sampling from LLMs: T<1 for focused, T>1 for creative
```
</details>

---

## Self-Assessment Quiz

**1. Entropy H(X) is maximized when:**
- (a) X is deterministic
- (b) X has uniform distribution
- (c) X is binary
- (d) X has high variance

<details><summary>Answer</summary>(b) Uniform distribution. H is maximized when all outcomes are equally likely (maximum uncertainty).</details>

**2. Cross-entropy H(P,Q) equals entropy H(P) when:**
- (a) P and Q are different
- (b) P = Q
- (c) Q is uniform
- (d) P is uniform

<details><summary>Answer</summary>(b) P = Q. Cross-entropy H(P,Q) = H(P) + D_KL(P||Q). When P=Q, KL divergence is 0.</details>

**3. KL divergence D_KL(P||Q) is:**
- (a) Symmetric: D_KL(P||Q) = D_KL(Q||P)
- (b) Always non-negative
- (c) A true metric (satisfies triangle inequality)
- (d) Sometimes negative

<details><summary>Answer</summary>(b) Always non-negative (≥0), with equality iff P=Q. It's NOT symmetric and NOT a metric.</details>

**4. In a decision tree, information gain measures:**
- (a) The accuracy improvement
- (b) The reduction in entropy after splitting
- (c) The number of features
- (d) The depth of the tree

<details><summary>Answer</summary>(b) IG = H(parent) - weighted_average(H(children)). It's the entropy reduction from the split.</details>

**5. The cross-entropy loss for classification -Σ yᵢ log(pᵢ) is equivalent to:**
- (a) Mean squared error
- (b) Negative log-likelihood of a categorical distribution
- (c) KL divergence
- (d) Mutual information

<details><summary>Answer</summary>(b) Minimizing cross-entropy = maximizing log-likelihood of the predicted categorical distribution for the true labels.</details>

**6. Mutual information I(X;Y) = 0 implies:**
- (a) X and Y are correlated
- (b) X and Y are independent
- (c) X = Y
- (d) X and Y have the same distribution

<details><summary>Answer</summary>(b) Zero mutual information means X and Y share no information — they are independent. (Note: zero correlation doesn't imply independence, but zero MI does.)</details>

**7. The entropy of a Bernoulli variable with p=0.5 vs p=0.99:**
- (a) Both have H=1
- (b) p=0.5 has higher entropy
- (c) p=0.99 has higher entropy
- (d) Cannot compare

<details><summary>Answer</summary>(b) H(0.5) = 1 bit (maximum for binary). H(0.99) ≈ 0.08 bits (almost certain → low entropy).</details>

**8. In knowledge distillation, high temperature softmax helps because:**
- (a) It makes training faster
- (b) It reveals dark knowledge (relationships between non-target classes)
- (c) It reduces model size
- (d) It increases accuracy directly

<details><summary>Answer</summary>(b) High temperature produces softer distributions that expose inter-class similarities ("cat is more like dog than car"), transferring richer information to the student model.</details>

**9. The data processing inequality states:**
- (a) More data always helps
- (b) Processing cannot create new information about the source
- (c) Deeper networks are always better
- (d) Compression is always lossy

<details><summary>Answer</summary>(b) If X→Y→Z, then I(X;Z) ≤ I(X;Y). Each processing step can only lose information, never gain it.</details>

**10. Binary cross-entropy for y=1, p=0.01 gives loss:**
- (a) ≈0
- (b) ≈2
- (c) ≈4.6
- (d) ≈6.6

<details><summary>Answer</summary>(c) L = -log(0.01) = -ln(0.01) ≈ 4.6 (using natural log as typical in implementations). High loss because prediction is very wrong.</details>

---

## Coding Challenges

### Challenge 1: Compute Information-Theoretic Quantities
```python
"""
Implement from scratch:
1. Entropy H(X)
2. Joint entropy H(X,Y)
3. Conditional entropy H(X|Y)
4. Mutual information I(X;Y)
5. KL divergence D_KL(P||Q)
Verify: I(X;Y) = H(X) - H(X|Y) = H(X) + H(Y) - H(X,Y)
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

def entropy(p):
    """H(X) = -Σ p(x) log2 p(x)"""
    p = np.array(p, dtype=float)
    p = p[p > 0]  # avoid log(0)
    return -np.sum(p * np.log2(p))

def joint_entropy(p_xy):
    """H(X,Y) from joint probability table"""
    return entropy(p_xy.flatten())

def conditional_entropy(p_xy):
    """H(X|Y) = H(X,Y) - H(Y)"""
    p_y = p_xy.sum(axis=0)
    return joint_entropy(p_xy) - entropy(p_y)

def mutual_information(p_xy):
    """I(X;Y) = H(X) + H(Y) - H(X,Y)"""
    p_x = p_xy.sum(axis=1)
    p_y = p_xy.sum(axis=0)
    return entropy(p_x) + entropy(p_y) - joint_entropy(p_xy)

def kl_divergence(p, q):
    """D_KL(P||Q) = Σ p(x) log2(p(x)/q(x))"""
    p, q = np.array(p, dtype=float), np.array(q, dtype=float)
    mask = p > 0
    return np.sum(p[mask] * np.log2(p[mask] / q[mask]))

# Test
p_xy = np.array([[0.4, 0.1],
                  [0.1, 0.4]])

print(f"H(X) = {entropy(p_xy.sum(axis=1)):.4f} bits")
print(f"H(Y) = {entropy(p_xy.sum(axis=0)):.4f} bits")
print(f"H(X,Y) = {joint_entropy(p_xy):.4f} bits")
print(f"H(X|Y) = {conditional_entropy(p_xy):.4f} bits")
print(f"I(X;Y) = {mutual_information(p_xy):.4f} bits")

# Verify identity
p_x = p_xy.sum(axis=1)
print(f"\nVerification: H(X) - H(X|Y) = {entropy(p_x) - conditional_entropy(p_xy):.4f}")
print(f"Should equal I(X;Y) = {mutual_information(p_xy):.4f} ✓")

# KL divergence
p = [0.7, 0.2, 0.1]
q = [0.5, 0.3, 0.2]
print(f"\nD_KL(P||Q) = {kl_divergence(p, q):.4f} bits")
print(f"D_KL(Q||P) = {kl_divergence(q, p):.4f} bits (asymmetric!)")
```
</details>

### Challenge 2: Build a Decision Tree using Information Gain
```python
"""
Implement a simple decision tree (ID3 algorithm):
1. Compute entropy of target
2. For each feature, compute information gain
3. Split on best feature
4. Recurse
Test on a small dataset (play tennis, mushroom, etc.)
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
from collections import Counter

def entropy(labels):
    counts = Counter(labels)
    total = len(labels)
    return -sum((c/total) * np.log2(c/total) for c in counts.values() if c > 0)

def information_gain(data, labels, feature_idx):
    parent_entropy = entropy(labels)
    values = set(data[:, feature_idx])
    child_entropy = 0
    for v in values:
        mask = data[:, feature_idx] == v
        weight = mask.sum() / len(labels)
        child_entropy += weight * entropy(labels[mask])
    return parent_entropy - child_entropy

class DecisionTree:
    def __init__(self, max_depth=5):
        self.max_depth = max_depth
        self.tree = None
    
    def fit(self, data, labels, depth=0, feature_names=None):
        if len(set(labels)) == 1:
            return {'leaf': labels[0]}
        if depth >= self.max_depth or data.shape[1] == 0:
            return {'leaf': Counter(labels).most_common(1)[0][0]}
        
        gains = [information_gain(data, labels, i) for i in range(data.shape[1])]
        best = np.argmax(gains)
        
        if gains[best] == 0:
            return {'leaf': Counter(labels).most_common(1)[0][0]}
        
        tree = {'feature': best, 'gain': gains[best], 'children': {}}
        for value in set(data[:, best]):
            mask = data[:, best] == value
            subtree = self.fit(data[mask], labels[mask], depth+1)
            tree['children'][value] = subtree
        
        self.tree = tree
        return tree
    
    def predict_one(self, x, tree=None):
        if tree is None: tree = self.tree
        if 'leaf' in tree: return tree['leaf']
        value = x[tree['feature']]
        if value in tree['children']:
            return self.predict_one(x, tree['children'][value])
        return 'unknown'

# Test: Play Tennis dataset
data = np.array([
    ['Sunny','Hot','High','Weak'],['Sunny','Hot','High','Strong'],
    ['Overcast','Hot','High','Weak'],['Rain','Mild','High','Weak'],
    ['Rain','Cool','Normal','Weak'],['Rain','Cool','Normal','Strong'],
    ['Overcast','Cool','Normal','Strong'],['Sunny','Mild','High','Weak'],
    ['Sunny','Cool','Normal','Weak'],['Rain','Mild','Normal','Weak'],
    ['Sunny','Mild','Normal','Strong'],['Overcast','Mild','High','Strong'],
    ['Overcast','Hot','Normal','Weak'],['Rain','Mild','High','Strong']
])
labels = np.array(['No','No','Yes','Yes','Yes','No','Yes','No','Yes','Yes','Yes','Yes','Yes','No'])

dt = DecisionTree(max_depth=3)
tree = dt.fit(data, labels)
print("Tree:", tree)
print("Predictions:", [dt.predict_one(x) for x in data[:5]])
```
</details>

### Challenge 3: Visualize Cross-Entropy Loss Landscape
```python
"""
For binary classification:
1. Plot cross-entropy loss as a function of predicted probability p for y=1 and y=0
2. Compare with MSE loss
3. Show why cross-entropy provides better gradients near 0 and 1
4. Plot the gradient magnitude comparison
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

p = np.linspace(0.001, 0.999, 1000)

# Losses for y=1
ce_loss_y1 = -np.log(p)
mse_loss_y1 = (1-p)**2

# Losses for y=0
ce_loss_y0 = -np.log(1-p)
mse_loss_y0 = p**2

# Gradients (w.r.t. pre-sigmoid logit z, where p=sigmoid(z))
# CE: dL/dz = p - y
ce_grad_y1 = p - 1  # when y=1
# MSE: dL/dz = 2(p-y)*p*(1-p)
mse_grad_y1 = 2*(p-1)*p*(1-p)  # when y=1

fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# Loss comparison (y=1)
axes[0,0].plot(p, ce_loss_y1, 'b-', label='Cross-Entropy')
axes[0,0].plot(p, mse_loss_y1, 'r-', label='MSE')
axes[0,0].set_xlabel('Predicted P(y=1)'); axes[0,0].set_ylabel('Loss')
axes[0,0].set_title('Loss when y=1'); axes[0,0].legend()

# Loss comparison (y=0)
axes[0,1].plot(p, ce_loss_y0, 'b-', label='Cross-Entropy')
axes[0,1].plot(p, mse_loss_y0, 'r-', label='MSE')
axes[0,1].set_xlabel('Predicted P(y=1)'); axes[0,1].set_ylabel('Loss')
axes[0,1].set_title('Loss when y=0'); axes[0,1].legend()

# Gradient magnitudes
axes[1,0].plot(p, np.abs(ce_grad_y1), 'b-', label='CE |gradient|')
axes[1,0].plot(p, np.abs(mse_grad_y1), 'r-', label='MSE |gradient|')
axes[1,0].set_xlabel('Predicted P(y=1)'); axes[1,0].set_ylabel('|Gradient|')
axes[1,0].set_title('Gradient Magnitude (y=1)')
axes[1,0].legend()
axes[1,0].annotate('MSE gradient vanishes\nwhen p≈0 (wrong!)', xy=(0.05, 0.02), fontsize=9)

# Key insight
axes[1,1].text(0.1, 0.5, 
    'KEY INSIGHT:\n\n'
    'When prediction is WRONG (p≈0, y=1):\n'
    '• CE gradient ≈ 1 (strong signal)\n'
    '• MSE gradient ≈ 0 (vanishes!)\n\n'
    'CE provides consistent learning signal\n'
    'regardless of how wrong the prediction is.\n\n'
    'This is why CE is standard for classification.',
    transform=axes[1,1].transAxes, fontsize=11, verticalalignment='center')
axes[1,1].axis('off')

plt.tight_layout(); plt.show()
```
</details>

### Challenge 4: Implement Knowledge Distillation
```python
"""
Demonstrate knowledge distillation using temperature scaling:
1. Train a "teacher" model (large) on MNIST-like data
2. Generate soft targets using high temperature
3. Train a "student" model (small) using soft targets
4. Compare: student trained on hard labels vs soft labels
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

def softmax(z, T=1.0):
    z = z / T
    exp_z = np.exp(z - z.max(axis=-1, keepdims=True))
    return exp_z / exp_z.sum(axis=-1, keepdims=True)

def cross_entropy(pred, target):
    return -np.sum(target * np.log(pred + 1e-10), axis=-1).mean()

# Simulate: 3-class problem
np.random.seed(42)
n_samples = 500
X = np.random.randn(n_samples, 10)
true_W = np.random.randn(10, 3)
logits_true = X @ true_W
y_hard = np.eye(3)[logits_true.argmax(axis=1)]  # one-hot

# "Teacher" (has access to true logits)
teacher_logits = logits_true + 0.5*np.random.randn(n_samples, 3)

# Generate soft targets at different temperatures
temperatures = [1, 2, 5, 10, 20]
print("Effect of temperature on soft targets (sample 0):")
print(f"Hard label: {y_hard[0]}")
for T in temperatures:
    soft = softmax(teacher_logits[0:1], T=T)
    print(f"T={T:2d}: {soft[0].round(3)}, H={-np.sum(soft*np.log2(soft+1e-10)):.3f} bits")

# Train student models
def train_linear(X, targets, lr=0.01, epochs=100):
    W = np.random.randn(X.shape[1], targets.shape[1]) * 0.01
    for _ in range(epochs):
        pred = softmax(X @ W)
        grad = X.T @ (pred - targets) / len(X)
        W -= lr * grad
    return W

# Student with hard labels
W_hard = train_linear(X[:400], y_hard[:400])
pred_hard = softmax(X[400:] @ W_hard)
acc_hard = (pred_hard.argmax(1) == y_hard[400:].argmax(1)).mean()

# Student with soft labels (T=5)
soft_targets = softmax(teacher_logits[:400], T=5)
W_soft = train_linear(X[:400], soft_targets)
pred_soft = softmax(X[400:] @ W_soft)
acc_soft = (pred_soft.argmax(1) == y_hard[400:].argmax(1)).mean()

print(f"\nStudent accuracy (hard labels): {acc_hard:.1%}")
print(f"Student accuracy (soft labels, T=5): {acc_soft:.1%}")
print("Soft labels transfer inter-class relationships from teacher!")
```
</details>

### Challenge 5: Mutual Information Feature Selection
```python
"""
Implement feature selection using mutual information:
1. Discretize continuous features into bins
2. Compute MI between each feature and target
3. Rank features by MI
4. Compare with correlation-based ranking
5. Show MI captures non-linear relationships that correlation misses
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
from collections import Counter

def discretize(x, n_bins=10):
    bins = np.linspace(x.min(), x.max(), n_bins+1)
    return np.digitize(x, bins[1:-1])

def mutual_information(x, y, n_bins=10):
    x_d = discretize(x, n_bins) if x.dtype != int else x
    y_d = discretize(y, n_bins) if y.dtype != int else y
    
    n = len(x)
    mi = 0
    for xi in set(x_d):
        for yi in set(y_d):
            p_xy = np.sum((x_d==xi) & (y_d==yi)) / n
            p_x = np.sum(x_d==xi) / n
            p_y = np.sum(y_d==yi) / n
            if p_xy > 0:
                mi += p_xy * np.log2(p_xy / (p_x * p_y))
    return mi

# Generate features with different relationships to target
np.random.seed(42)
n = 1000
target = np.random.randn(n)

features = {
    'linear': target + 0.5*np.random.randn(n),
    'quadratic': target**2 + 0.5*np.random.randn(n),
    'sin': np.sin(3*target) + 0.3*np.random.randn(n),
    'noise': np.random.randn(n),
    'weak_linear': 0.3*target + np.random.randn(n),
}

print(f"{'Feature':<15} {'Correlation':>12} {'MI (bits)':>10} {'MI Rank':>8} {'Corr Rank':>10}")
print("-"*60)

mi_scores = {}
corr_scores = {}
for name, feat in features.items():
    corr = np.abs(np.corrcoef(feat, target)[0,1])
    mi = mutual_information(feat, target)
    mi_scores[name] = mi
    corr_scores[name] = corr
    print(f"{name:<15} {corr:>12.4f} {mi:>10.4f}")

print("\nKey insight: 'quadratic' and 'sin' have LOW correlation but HIGH MI!")
print("MI captures non-linear dependencies that correlation completely misses.")
print("This is why MI-based feature selection is superior for non-linear models.")
```
</details>

---

## Interview Questions

### 1. Why is cross-entropy used as the loss function for classification?
<details><summary>Answer</summary>

Cross-entropy is the natural loss for classification because:
1. **MLE connection**: Minimizing CE = maximizing likelihood of a categorical distribution
2. **Gradient properties**: CE gradient = (predicted - target), no vanishing gradient problem
3. **Information-theoretic meaning**: Measures the extra bits needed to encode data from P using model Q
4. **Proper scoring rule**: Minimized only when predicted probabilities equal true probabilities
5. **KL divergence**: CE = H(P) + D_KL(P||Q); since H(P) is constant, minimizing CE = minimizing KL divergence between true and predicted distributions
</details>

### 2. Explain KL divergence and why it's asymmetric. When does this matter?
<details><summary>Answer</summary>

D_KL(P||Q) = E_P[log(P/Q)] measures information lost when Q approximates P.

Asymmetry:
- D_KL(P||Q): "forward KL" — penalizes Q=0 where P>0 (Q must cover P's support)
  → mode-covering: Q spreads out to cover all of P
- D_KL(Q||P): "reverse KL" — penalizes Q>0 where P=0 (Q avoids P's zeros)  
  → mode-seeking: Q collapses to one mode of P

When it matters:
- VAE training: minimizes D_KL(q||p) → q seeks modes of posterior → potential mode collapse
- GAN training: generator minimizes reverse KL → mode collapse risk
- Variational inference: forward KL gives mean-field, reverse KL gives MAP-like
</details>

### 3. What is mutual information and how is it used for feature selection?
<details><summary>Answer</summary>

I(X;Y) = H(X) + H(Y) - H(X,Y) = H(X) - H(X|Y)

It measures how much knowing X reduces uncertainty about Y (and vice versa).

Advantages over correlation for feature selection:
- Captures ANY dependency (linear, nonlinear, periodic)
- Zero iff truly independent (vs correlation only detects linear)
- Scale-invariant

Applications:
- Feature ranking: select features with highest I(feature; target)
- MIFS/mRMR: max relevance, min redundancy among selected features
- InfoGAN: maximize MI between latent codes and generated outputs
- Contrastive learning (InfoNCE loss): maximize MI between views
</details>

### 4. Explain the ELBO in variational autoencoders.
<details><summary>Answer</summary>

ELBO = Evidence Lower BOund on log p(x):

log p(x) ≥ ELBO = E_q(z|x)[log p(x|z)] - D_KL(q(z|x) || p(z))

Components:
- **Reconstruction term** E_q[log p(x|z)]: encoder samples z, decoder reconstructs x. Encourages good reconstructions.
- **KL term** D_KL(q(z|x)||p(z)): penalizes encoder q for deviating from prior p(z)=N(0,I). Regularizes latent space.

Trade-off: reconstruction quality vs latent space regularity.
- β-VAE: ELBO with β>1 on KL term → more disentangled but blurrier
- Gap: log p(x) - ELBO = D_KL(q(z|x) || p(z|x)) → tighter ELBO = better approximate posterior
</details>

### 5. How does temperature scaling affect model calibration?
<details><summary>Answer</summary>

Temperature scaling: p = softmax(z/T) where T is learned post-training.

Calibration: predicted probabilities should match true frequencies.
- Overconfident model: predicted P(correct)=0.99 but actual accuracy=0.85 → T>1 softens
- Underconfident model: T<1 sharpens

Why it works:
- Doesn't change rankings (argmax preserved) → accuracy unchanged
- Only adjusts confidence levels
- Single parameter → no overfitting risk
- Minimizes NLL (= cross-entropy) on validation set to find optimal T

This is the simplest post-hoc calibration method. More complex: Platt scaling, isotonic regression.
</details>

### 6. What is the connection between information theory and compression in neural networks?
<details><summary>Answer</summary>

Connections:
1. **Minimum Description Length**: best model = shortest description of data + model
2. **Information Bottleneck**: layers compress I(X;T) while preserving I(T;Y)
3. **Weight pruning**: removing weights with little "information" about the task
4. **Quantization**: reducing bits per weight (32→8→4→2 bit) loses information but preserves most accuracy
5. **Knowledge distillation**: teacher's soft labels contain more information than hard labels (higher entropy)
6. **Dropout**: during training, forces network to compress information into redundant paths

The lottery ticket hypothesis connects: sparse subnetworks contain all necessary information.
</details>

### 7. Explain the InfoNCE loss used in contrastive learning (SimCLR, CLIP).
<details><summary>Answer</summary>

InfoNCE maximizes a lower bound on mutual information between positive pairs:

L = -log[exp(sim(z_i, z_j)/τ) / Σ_k exp(sim(z_i, z_k)/τ)]

Where (i,j) is a positive pair and k iterates over all negatives.

Information-theoretic interpretation:
- Maximizes MI between representations of positive pairs
- Equivalent to (N-1)-way classification: identify the positive among N-1 negatives
- Lower bound: I(X;Y) ≥ log(N) - L_NCE
- More negatives → tighter bound → better representation

Temperature τ controls:
- Low τ: focuses on hardest negatives (sharpens distribution)
- High τ: treats all negatives more equally

Used in: SimCLR (image), CLIP (image-text), sentence-BERT (text).
</details>

### 8. Why does label smoothing help training, from an information theory perspective?
<details><summary>Answer</summary>

Standard one-hot: y = [0, 0, 1, 0] (H=0 bits, zero entropy)
Smoothed: y = [0.033, 0.033, 0.9, 0.033] (H>0 bits, positive entropy)

Information-theoretic benefits:
1. **Prevents overconfidence**: model can't achieve 0 loss (CE with smoothed targets > 0)
2. **Regularizes logits**: prevents them from growing unboundedly (which would be needed for H→0)
3. **Implicit KL regularization**: equivalent to adding D_KL(uniform||p) to the loss
4. **Calibration**: model's output entropy better matches smoothed target entropy
5. **Dark knowledge**: non-zero probabilities on wrong classes encode that "cat" is more like "dog" than "car"

Practice: smoothing factor ε=0.1 is standard. Label smoothing improves both accuracy and calibration.
</details>
