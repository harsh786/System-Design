# Probability and Statistics for AI/ML/Deep Learning

## Why Probability & Statistics Matter for ML

Machine learning IS applied statistics. Every prediction has uncertainty. Every model makes probabilistic assumptions. Understanding probability lets you:
- Design better models (Bayesian methods, generative models)
- Evaluate models properly (hypothesis testing, confidence intervals)
- Handle uncertainty (prediction intervals, calibration)

```
"All models are wrong, but some are useful." — George Box
```

---

## 1. Basic Probability

### Sample Space and Events

```
Experiment: Rolling a die
Sample space: Ω = {1, 2, 3, 4, 5, 6}
Event A (even): {2, 4, 6}
P(A) = |A|/|Ω| = 3/6 = 0.5
```

### Axioms of Probability

```
1. P(A) ≥ 0                    (non-negative)
2. P(Ω) = 1                   (total probability = 1)
3. P(A∪B) = P(A) + P(B)       (for mutually exclusive events)
```

### Key Rules

```
Addition:       P(A∪B) = P(A) + P(B) - P(A∩B)
Complement:     P(A') = 1 - P(A)
Independence:   P(A∩B) = P(A)·P(B)  iff A,B independent
```

---

## 2. Conditional Probability and Bayes' Theorem

### Conditional Probability

```
P(A|B) = P(A∩B) / P(B)

"Probability of A given that B has occurred"
```

**Analogy:** If it's cloudy (B), what's the probability of rain (A)? The "given cloudy" restricts our sample space.

### Bayes' Theorem

```
P(hypothesis | data) = P(data | hypothesis) × P(hypothesis) / P(data)

        posterior    =    likelihood      ×     prior        / evidence
```

```
┌─────────────────────────────────────────────────────────┐
│                    BAYES' THEOREM                         │
│                                                          │
│              P(B|A) · P(A)                               │
│  P(A|B) = ─────────────────                             │
│                 P(B)                                     │
│                                                          │
│  posterior ∝ likelihood × prior                          │
│                                                          │
│  What we         What we      What we believed           │
│  now believe     observed     before seeing data         │
└─────────────────────────────────────────────────────────┘
```

**ML Example: Spam Filter**
```
P(spam | "free money") = P("free money" | spam) × P(spam) / P("free money")

If: P("free money"|spam) = 0.8, P(spam) = 0.3, P("free money") = 0.25
Then: P(spam|"free money") = 0.8 × 0.3 / 0.25 = 0.96
```

```python
# Naive Bayes classifier (simplified)
def naive_bayes_predict(features, class_priors, likelihoods):
    """
    P(class|features) ∝ P(class) × ∏ P(feature_i|class)
    """
    scores = {}
    for cls in class_priors:
        log_prob = np.log(class_priors[cls])
        for i, feat in enumerate(features):
            log_prob += np.log(likelihoods[cls][i][feat])
        scores[cls] = log_prob
    return max(scores, key=scores.get)
```

---

## 3. Random Variables

### Discrete Random Variables

Take on countable values. Defined by a Probability Mass Function (PMF).

```python
# PMF: P(X = x) for each possible x
# Example: fair die
pmf = {1: 1/6, 2: 1/6, 3: 1/6, 4: 1/6, 5: 1/6, 6: 1/6}
```

### Continuous Random Variables

Take on uncountable values. Defined by a Probability Density Function (PDF).

```
Note: For continuous RVs, P(X = exact value) = 0
      Instead: P(a ≤ X ≤ b) = ∫[a,b] f(x) dx
```

---

## 4. Common Distributions

### Bernoulli Distribution
Single binary trial. X ∈ {0, 1}.

```
P(X=1) = p,  P(X=0) = 1-p
E[X] = p,    Var(X) = p(1-p)
```
**ML Use:** Binary classification output, coin flip.

### Binomial Distribution
Number of successes in n independent Bernoulli trials.

```
P(X=k) = C(n,k) · pᵏ · (1-p)ⁿ⁻ᵏ
```

### Normal (Gaussian) Distribution

The most important distribution in ML.

```
f(x) = (1/√(2πσ²)) · exp(-(x-μ)²/(2σ²))

Parameters: μ (mean), σ² (variance)
```

```
Standard Normal (μ=0, σ=1):

         ┌──╮
        ╱│   ╲
       ╱ │    ╲
      ╱  │     ╲        68% within 1σ
     ╱   │      ╲       95% within 2σ
    ╱    │       ╲      99.7% within 3σ
───╱─────┼────────╲───
  -3σ  -σ  μ   σ   3σ
```

**ML Use:** Weight initialization, noise modeling, Gaussian processes, VAE latent space.

```python
# Gaussian/Normal distribution
mu, sigma = 0, 1
samples = np.random.normal(mu, sigma, 10000)

# Multivariate Gaussian (for multiple features)
mean = np.array([0, 0])
cov = np.array([[1, 0.5], [0.5, 1]])
samples_2d = np.random.multivariate_normal(mean, cov, 1000)
```

### Poisson Distribution
Counts of events in fixed intervals.

```
P(X=k) = (λᵏ · e⁻λ) / k!
E[X] = Var(X) = λ
```
**ML Use:** Modeling count data (clicks, arrivals, events).

### Exponential Distribution
Time between events. Memoryless property.

```
f(x) = λe⁻λˣ for x ≥ 0
E[X] = 1/λ
```

### Uniform Distribution
Equal probability over an interval.

```
f(x) = 1/(b-a) for a ≤ x ≤ b
```
**ML Use:** Random initialization, random sampling.

---

## 5. Expected Value, Variance, Covariance

### Expected Value (Mean)

```
E[X] = Σ xᵢ · P(X=xᵢ)           (discrete)
E[X] = ∫ x · f(x) dx             (continuous)
```

**Analogy:** The "center of mass" of the distribution.

### Variance

```
Var(X) = E[(X - E[X])²] = E[X²] - (E[X])²
```

Measures spread. Standard deviation σ = √Var(X).

### Covariance

```
Cov(X,Y) = E[(X-μₓ)(Y-μᵧ)]

Cov > 0: X and Y tend to increase together
Cov < 0: One increases as other decreases  
Cov = 0: No linear relationship
```

**ML Application:** The covariance matrix is central to PCA, Gaussian distributions, and understanding feature relationships.

```python
# Covariance matrix of features
X = np.random.randn(1000, 5)  # 1000 samples, 5 features
cov_matrix = np.cov(X.T)      # 5×5 covariance matrix

# Correlation (normalized covariance)
corr_matrix = np.corrcoef(X.T)  # Values between -1 and 1
```

---

## 6. Maximum Likelihood Estimation (MLE)

### The Idea

Find parameters θ that maximize the probability of observing the data we actually saw.

```
θ_MLE = argmax_θ P(data | θ) = argmax_θ ∏ P(xᵢ | θ)

In practice, maximize log-likelihood (easier):
θ_MLE = argmax_θ Σ log P(xᵢ | θ)
```

**Analogy:** You found 7 heads in 10 coin flips. What's the most likely bias of the coin? MLE says p=0.7.

```python
# MLE for Gaussian: find μ and σ that best explain data
data = np.array([2.1, 1.9, 2.3, 2.0, 1.8, 2.2])

# MLE estimates (closed-form for Gaussian):
mu_mle = np.mean(data)       # 2.05
sigma_mle = np.std(data)     # biased MLE estimate

# MLE for logistic regression = minimizing cross-entropy loss!
# The negative log-likelihood of a Bernoulli IS cross-entropy.
```

### Connection to ML Loss Functions

```
Minimizing cross-entropy loss = Maximizing likelihood of correct labels
Minimizing MSE loss = Maximizing likelihood under Gaussian noise assumption
```

---

## 7. Maximum A Posteriori (MAP)

### MLE + Prior = MAP

```
θ_MAP = argmax_θ P(θ | data) = argmax_θ P(data | θ) · P(θ)
                                         ↑              ↑
                                     likelihood       prior
```

**ML Connection:**
- MLE + L2 regularization = MAP with Gaussian prior on weights
- MLE + L1 regularization = MAP with Laplacian prior on weights

```python
# MAP = MLE + regularization
# Loss = -log_likelihood + λ||θ||²
#       = cross_entropy   + weight_decay
#         ↑ MLE part        ↑ Gaussian prior part
```

---

## 8. Hypothesis Testing

### Framework

```
1. Null hypothesis H₀: "no effect" (e.g., new model = old model)
2. Alternative hypothesis H₁: "there IS an effect"
3. Compute p-value: P(data this extreme | H₀ is true)
4. If p-value < α (typically 0.05): reject H₀
```

### p-value

```
p-value = probability of seeing results at least as extreme as observed,
          assuming the null hypothesis is true.

Small p-value → evidence against H₀
Large p-value → insufficient evidence to reject H₀

WARNING: p-value ≠ P(H₀ is true)!
```

### Confidence Intervals

```
95% CI for mean: x̄ ± 1.96 · (s/√n)

Interpretation: If we repeated this experiment many times,
95% of the intervals would contain the true parameter.
```

```python
from scipy import stats

# Two-sample t-test: Is model A better than model B?
scores_A = np.array([0.85, 0.87, 0.84, 0.86, 0.88])
scores_B = np.array([0.82, 0.83, 0.81, 0.84, 0.83])

t_stat, p_value = stats.ttest_ind(scores_A, scores_B)
print(f"p-value: {p_value:.4f}")
if p_value < 0.05:
    print("Statistically significant difference!")
```

---

## 9. Central Limit Theorem (CLT)

### Statement

The mean of many independent random variables is approximately normally distributed, regardless of the original distribution.

```
X̄ = (X₁ + X₂ + ... + Xₙ) / n

As n → ∞:  X̄ ~ N(μ, σ²/n)
```

```
Original distribution      Sample means (n=30)
(can be anything):         (always approximately Normal):

  ┌──┐                           ╭──╮
  │  │                          ╱    ╲
  │  │  ┌──┐                  ╱      ╲
──┴──┴──┴──┴──    ───→    ───╱────────╲───
  (uniform)                (Gaussian!)
```

**ML Relevance:**
- Justifies using Gaussian assumptions for averaged quantities
- Mini-batch gradients are approximately normal (CLT on gradient samples)
- Confidence intervals rely on CLT

---

## 10. A/B Testing in Production

### Framework for ML Model Comparison

```
┌─────────────────────────────────────────────┐
│              A/B TEST PIPELINE               │
├─────────────────────────────────────────────┤
│                                             │
│  Traffic ──┬──▶ Model A (control): 50%     │
│            │                                │
│            └──▶ Model B (variant): 50%     │
│                                             │
│  Metrics: CTR, conversion, revenue, etc.   │
│                                             │
│  Statistical test after sufficient samples  │
│  → Decide: ship B, keep A, or inconclusive │
└─────────────────────────────────────────────┘
```

```python
# A/B test for click-through rate
def ab_test(conversions_a, total_a, conversions_b, total_b):
    p_a = conversions_a / total_a
    p_b = conversions_b / total_b
    
    # Pooled proportion
    p_pool = (conversions_a + conversions_b) / (total_a + total_b)
    
    # Standard error
    se = np.sqrt(p_pool * (1-p_pool) * (1/total_a + 1/total_b))
    
    # Z-statistic
    z = (p_b - p_a) / se
    
    # Two-tailed p-value
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    
    return z, p_value

# Example: Model B has 520 conversions out of 5000, A has 480/5000
z, p = ab_test(480, 5000, 520, 5000)
print(f"Z={z:.2f}, p={p:.4f}")
```

### Key Considerations
- **Sample size:** Calculate required n BEFORE the test
- **Multiple testing:** Correct for testing many metrics (Bonferroni)
- **Novelty effect:** Users may behave differently initially
- **Simpson's paradox:** Aggregate results can mislead if segments differ

---

## 11. Bayesian vs Frequentist Approaches

```
┌────────────────────────┬─────────────────────────────┐
│      FREQUENTIST       │         BAYESIAN             │
├────────────────────────┼─────────────────────────────┤
│ Parameters are fixed   │ Parameters have distributions│
│ Data is random         │ Data is fixed (observed)     │
│ P(data|θ)             │ P(θ|data)                    │
│ Point estimates (MLE)  │ Full posterior distribution  │
│ Confidence intervals   │ Credible intervals           │
│ p-values              │ Posterior probability         │
│ No prior needed       │ Requires prior specification │
│ Simpler computation   │ Can be computationally heavy │
└────────────────────────┴─────────────────────────────┘
```

**When to use Bayesian:**
- Small data (prior helps regularize)
- Need uncertainty quantification
- Sequential updating (online learning)
- Domain knowledge to incorporate

**When to use Frequentist:**
- Large data (prior becomes irrelevant)
- Need simple, fast methods
- Regulatory requirements (clinical trials)

---

## 12. Applications in ML

### Naive Bayes Classifier

Assumes features are independent given the class (naive assumption):

```
P(class|features) ∝ P(class) × ∏ P(feature_i|class)
```

### Gaussian Mixture Models (GMM)

Model data as a mixture of K Gaussian distributions:

```
p(x) = Σₖ πₖ · N(x|μₖ, Σₖ)

where πₖ = mixing weight for cluster k
```

```python
from sklearn.mixture import GaussianMixture

gmm = GaussianMixture(n_components=3)
gmm.fit(X)
labels = gmm.predict(X)
probabilities = gmm.predict_proba(X)  # Soft assignments!
```

### Bayesian Neural Networks

Instead of point estimates for weights, maintain distributions:

```
Standard NN:  w = 2.5  (single value)
Bayesian NN:  w ~ N(2.5, 0.3)  (distribution → uncertainty!)

Prediction uncertainty comes for free:
- Run forward pass multiple times with sampled weights
- Variance of outputs = model uncertainty
```

### Variational Autoencoders (VAE)

Use probability to generate new data:

```
Encoder: x → q(z|x) ≈ N(μ, σ²)    (approximate posterior)
Decoder: z → p(x|z)                 (likelihood)
Loss = Reconstruction + KL(q(z|x) || p(z))
```

---

## Summary

| Concept | ML Application |
|---------|---------------|
| Bayes' theorem | Naive Bayes, Bayesian inference |
| Normal distribution | Weight init, noise, latent spaces |
| MLE | Training = maximizing likelihood |
| MAP | Training with regularization |
| Hypothesis testing | A/B tests, model comparison |
| Covariance | PCA, feature relationships |
| CLT | Justifies Gaussian assumptions |
| Posterior | Bayesian NNs, uncertainty |

---

## Key Takeaways

1. **ML training = MLE** (or MAP with regularization)
2. **Bayes' theorem** enables updating beliefs with data — the foundation of learning
3. **Distributions model uncertainty** — the real world is noisy
4. **Statistical testing** prevents shipping models that only appear better
5. **Bayesian methods** give you uncertainty for free — critical for high-stakes decisions
