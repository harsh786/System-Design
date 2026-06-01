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

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** A bag contains 5 red, 3 blue, and 2 green balls. What is the probability of drawing (a) a red ball, (b) not a green ball, (c) a red or blue ball?

**Hint:** P(A) = favorable outcomes / total outcomes.

<details><summary>Solution</summary>

```
Total balls = 10
(a) P(red) = 5/10 = 0.5
(b) P(not green) = 1 - P(green) = 1 - 2/10 = 0.8
(c) P(red or blue) = P(red) + P(blue) = 5/10 + 3/10 = 0.8
    (mutually exclusive, so no overlap to subtract)
```
</details>

### Exercise 2 (Beginner)
**Problem:** Two fair dice are rolled. What is P(sum = 7)? What is P(sum = 7 | first die = 3)?

**Hint:** List favorable outcomes. For conditional, restrict sample space.

<details><summary>Solution</summary>

```
P(sum=7): favorable = {(1,6),(2,5),(3,4),(4,3),(5,2),(6,1)} = 6 outcomes
Total outcomes = 36
P(sum=7) = 6/36 = 1/6

P(sum=7|first=3): given first=3, need second=4
Only 1 outcome out of 6 possible for second die
P(sum=7|first=3) = 1/6
```
</details>

### Exercise 3 (Beginner)
**Problem:** A medical test has 95% sensitivity (true positive rate) and 90% specificity (true negative rate). If 1% of the population has the disease, what is P(disease | positive test)?

**Hint:** Use Bayes' theorem: P(D|+) = P(+|D)P(D) / P(+).

<details><summary>Solution</summary>

```
P(D) = 0.01, P(+|D) = 0.95, P(+|¬D) = 0.10
P(+) = P(+|D)P(D) + P(+|¬D)P(¬D)
     = 0.95×0.01 + 0.10×0.99 = 0.0095 + 0.099 = 0.1085

P(D|+) = 0.0095/0.1085 ≈ 0.0876 ≈ 8.8%

Despite 95% sensitivity, only ~9% of positive tests are true positives!
(Base rate fallacy — the low prevalence dominates)
```
</details>

### Exercise 4 (Beginner)
**Problem:** Compute the mean, variance, and standard deviation of X = {2, 4, 6, 8, 10}.

**Hint:** μ = Σxᵢ/n, σ² = Σ(xᵢ-μ)²/n.

<details><summary>Solution</summary>

```
μ = (2+4+6+8+10)/5 = 30/5 = 6
σ² = [(2-6)²+(4-6)²+(6-6)²+(8-6)²+(10-6)²]/5
   = [16+4+0+4+16]/5 = 40/5 = 8
σ = √8 ≈ 2.83
```
</details>

### Exercise 5 (Intermediate)
**Problem:** X ~ N(μ=100, σ=15). Find P(X > 130), P(85 < X < 115), and the value x such that P(X < x) = 0.95.

**Hint:** Standardize: Z = (X-μ)/σ. Use Z-table or scipy.

<details><summary>Solution</summary>

```
P(X > 130) = P(Z > (130-100)/15) = P(Z > 2) ≈ 0.0228 (2.28%)
P(85 < X < 115) = P(-1 < Z < 1) ≈ 0.6827 (68.27%)
P(X < x) = 0.95 → Z = 1.645 → x = 100 + 1.645×15 = 124.67
```
</details>

### Exercise 6 (Intermediate)
**Problem:** You flip a biased coin (P(H)=0.7) 10 times. (a) What's the expected number of heads? (b) P(exactly 7 heads)? (c) P(at least 8 heads)?

**Hint:** Binomial distribution: P(X=k) = C(n,k) × p^k × (1-p)^(n-k).

<details><summary>Solution</summary>

```
n=10, p=0.7
(a) E[X] = np = 10×0.7 = 7

(b) P(X=7) = C(10,7)×0.7⁷×0.3³ = 120×0.0824×0.027 = 0.2668

(c) P(X≥8) = P(X=8) + P(X=9) + P(X=10)
    P(X=8) = C(10,8)×0.7⁸×0.3² = 45×0.0576×0.09 = 0.2335
    P(X=9) = C(10,9)×0.7⁹×0.3¹ = 10×0.0404×0.3 = 0.1211
    P(X=10) = 0.7¹⁰ = 0.0282
    P(X≥8) ≈ 0.3828
```
</details>

### Exercise 7 (Intermediate)
**Problem:** Prove that for independent random variables X and Y: Var(X+Y) = Var(X) + Var(Y).

**Hint:** Expand Var(X+Y) = E[(X+Y-E[X+Y])²] and use E[XY] = E[X]E[Y] for independent variables.

<details><summary>Solution</summary>

```
Var(X+Y) = E[(X+Y)²] - (E[X+Y])²
= E[X²+2XY+Y²] - (E[X]+E[Y])²
= E[X²]+2E[XY]+E[Y²] - E[X]²-2E[X]E[Y]-E[Y]²

Since X,Y independent: E[XY] = E[X]E[Y]

= E[X²]+2E[X]E[Y]+E[Y²] - E[X]²-2E[X]E[Y]-E[Y]²
= (E[X²]-E[X]²) + (E[Y²]-E[Y]²)
= Var(X) + Var(Y) ✓
```
</details>

### Exercise 8 (Intermediate)
**Problem:** You're A/B testing a new recommendation model. Control: 1000 users, 50 conversions. Treatment: 1000 users, 65 conversions. Is the difference statistically significant (α=0.05)?

**Hint:** Two-proportion Z-test: Z = (p₁-p₂)/√(p̂(1-p̂)(1/n₁+1/n₂)) where p̂ is pooled proportion.

<details><summary>Solution</summary>

```
p₁ = 50/1000 = 0.05, p₂ = 65/1000 = 0.065
p̂ = (50+65)/(1000+1000) = 115/2000 = 0.0575

SE = √(0.0575×0.9425×(1/1000+1/1000)) = √(0.0575×0.9425×0.002)
   = √(0.0001084) = 0.01041

Z = (0.065-0.05)/0.01041 = 0.015/0.01041 = 1.44

Critical value for α=0.05 (two-tailed): Z=1.96
1.44 < 1.96 → NOT statistically significant (p≈0.15)
Need more data or larger effect size.
```
</details>

### Exercise 9 (Advanced)
**Problem:** Derive the maximum likelihood estimate for the parameters (μ, σ²) of a Gaussian distribution given n i.i.d. samples x₁,...,xₙ.

**Hint:** Write the log-likelihood, take derivatives, set to zero.

<details><summary>Solution</summary>

```
Likelihood: L(μ,σ²) = Πᵢ (1/√(2πσ²)) exp(-(xᵢ-μ)²/(2σ²))

Log-likelihood: ℓ = -n/2 log(2π) - n/2 log(σ²) - (1/2σ²)Σ(xᵢ-μ)²

∂ℓ/∂μ = (1/σ²)Σ(xᵢ-μ) = 0
→ μ_MLE = (1/n)Σxᵢ = x̄ (sample mean)

∂ℓ/∂σ² = -n/(2σ²) + (1/2σ⁴)Σ(xᵢ-μ)² = 0
→ σ²_MLE = (1/n)Σ(xᵢ-x̄)² (sample variance, biased)

Note: Unbiased estimate uses 1/(n-1) instead of 1/n.
```
</details>

### Exercise 10 (Advanced)
**Problem:** Explain the bias-variance tradeoff mathematically. Decompose E[(y-f̂(x))²] into bias², variance, and irreducible noise.

**Hint:** Add and subtract E[f̂(x)] inside the squared term.

<details><summary>Solution</summary>

```
Let y = f(x) + ε where E[ε]=0, Var(ε)=σ²

E[(y-f̂)²] = E[(f+ε-f̂)²]
= E[(f-E[f̂]+E[f̂]-f̂+ε)²]
= E[(f-E[f̂])² + (E[f̂]-f̂)² + ε² + cross terms]

Cross terms vanish (independence of ε and f̂, and E[f̂-E[f̂]]=0):

= (f-E[f̂])² + E[(f̂-E[f̂])²] + σ²
= Bias²      + Variance        + Irreducible noise

- High bias: model too simple (underfitting)
- High variance: model too complex (overfitting)
- σ²: noise in data, can't reduce
```
</details>

### Exercise 11 (Advanced)
**Problem:** Derive the posterior distribution for Bayesian linear regression with a Gaussian prior on weights: p(w|X,y) ∝ p(y|X,w)p(w).

**Hint:** Prior: w ~ N(0, τ²I). Likelihood: y|X,w ~ N(Xw, σ²I). Product of Gaussians is Gaussian.

<details><summary>Solution</summary>

```
Prior: p(w) = N(0, τ²I) → log p(w) ∝ -w^Tw/(2τ²)
Likelihood: p(y|X,w) = N(Xw, σ²I) → log p(y|X,w) ∝ -(y-Xw)^T(y-Xw)/(2σ²)

Log posterior ∝ -(y-Xw)^T(y-Xw)/(2σ²) - w^Tw/(2τ²)
= -(1/2)[w^T(X^TX/σ² + I/τ²)w - 2w^TX^Ty/σ²] + const

This is quadratic in w → posterior is Gaussian!

p(w|X,y) = N(μ_post, Σ_post) where:
Σ_post = (X^TX/σ² + I/τ²)⁻¹
μ_post = Σ_post × X^Ty/σ²

Note: μ_post = (X^TX + (σ²/τ²)I)⁻¹X^Ty = Ridge regression solution!
MAP estimate of Bayesian LR = Ridge regression.
```
</details>

### Exercise 12 (Advanced)
**Problem:** Prove that the KL divergence D_KL(P||Q) ≥ 0 with equality iff P = Q (Gibbs' inequality).

**Hint:** Use Jensen's inequality with the concave function log.

<details><summary>Solution</summary>

```
D_KL(P||Q) = Σ p(x) log(p(x)/q(x)) = -Σ p(x) log(q(x)/p(x))

By Jensen's inequality (log is concave):
-Σ p(x) log(q(x)/p(x)) ≥ -log(Σ p(x)×q(x)/p(x))
                        = -log(Σ q(x))
                        = -log(1) = 0

Equality holds iff q(x)/p(x) is constant → q(x) = p(x) for all x.

Therefore D_KL(P||Q) ≥ 0 with equality iff P = Q. ∎
```
</details>

---

## Self-Assessment Quiz

**1. If P(A) = 0.3 and P(B) = 0.4 and A,B are independent, then P(A∩B) =?**
- (a) 0.7
- (b) 0.12
- (c) 0.1
- (d) 0.58

<details><summary>Answer</summary>(b) 0.12. For independent events: P(A∩B) = P(A)×P(B) = 0.3×0.4 = 0.12.</details>

**2. The Central Limit Theorem states that:**
- (a) All data is normally distributed
- (b) Sample means converge to a normal distribution as n→∞
- (c) Variance decreases with more data
- (d) Outliers disappear with large samples

<details><summary>Answer</summary>(b) Regardless of the underlying distribution, the distribution of sample means approaches normal with mean μ and variance σ²/n as sample size increases.</details>

**3. Maximum Likelihood Estimation finds parameters that:**
- (a) Minimize the prior probability
- (b) Maximize the probability of observed data given the parameters
- (c) Minimize variance
- (d) Maximize the posterior

<details><summary>Answer</summary>(b) MLE finds θ that maximizes P(data|θ), the likelihood function.</details>

**4. A p-value of 0.03 means:**
- (a) There's a 3% chance the null hypothesis is true
- (b) The probability of seeing data this extreme (or more) if H₀ is true is 3%
- (c) The effect size is 3%
- (d) 97% of the data supports the alternative

<details><summary>Answer</summary>(b) p-value = P(data this extreme or more | H₀ true). It's NOT the probability that H₀ is true.</details>

**5. The expected value of a discrete random variable is:**
- (a) The most common value
- (b) The median
- (c) Σ xᵢ × P(xᵢ)
- (d) The maximum value

<details><summary>Answer</summary>(c) E[X] = Σ xᵢ × P(xᵢ), the probability-weighted average of all possible values.</details>

**6. Bayes' theorem relates:**
- (a) Prior, likelihood, and posterior
- (b) Mean and variance
- (c) Bias and variance
- (d) Precision and recall

<details><summary>Answer</summary>(a) P(θ|data) ∝ P(data|θ) × P(θ). Posterior ∝ Likelihood × Prior.</details>

**7. Two variables with correlation = 0 are:**
- (a) Always independent
- (b) Linearly uncorrelated (but may have nonlinear dependence)
- (c) Identically distributed
- (d) Mutually exclusive

<details><summary>Answer</summary>(b) Zero correlation means no LINEAR relationship. Variables can still be dependent (e.g., Y=X² has correlation 0 with X if X is symmetric around 0).</details>

**8. The law of large numbers guarantees that:**
- (a) You'll eventually win in gambling
- (b) Sample mean converges to population mean as n→∞
- (c) Variance goes to zero
- (d) All distributions become normal

<details><summary>Answer</summary>(b) As sample size increases, x̄ → μ (with probability 1 in the strong law).</details>

**9. In a Gaussian Mixture Model, the number of parameters for K components in d dimensions is:**
- (a) K×d
- (b) K×(d + d(d+1)/2 + 1) - 1
- (c) K×d²
- (d) K+d

<details><summary>Answer</summary>(b) Each component needs: d means + d(d+1)/2 covariance entries + 1 mixing weight. Subtract 1 because weights sum to 1. Total ≈ K(d + d²/2 + 1) - 1.</details>

**10. The difference between MAP and MLE estimation is:**
- (a) MAP includes a prior distribution on parameters
- (b) MAP always gives better results
- (c) MLE is Bayesian
- (d) There is no difference

<details><summary>Answer</summary>(a) MAP = argmax P(θ|data) ∝ P(data|θ)P(θ). MLE = argmax P(data|θ). MAP adds a prior which acts as regularization (e.g., Gaussian prior → L2 regularization).</details>

---

## Coding Challenges

### Challenge 1: Implement Naive Bayes Classifier from Scratch
```python
"""
Build a Gaussian Naive Bayes classifier:
1. Fit: compute mean and variance per feature per class
2. Predict: apply Bayes' theorem assuming feature independence
3. Test on a simple 2D dataset
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
from sklearn.datasets import make_classification

class NaiveBayes:
    def fit(self, X, y):
        self.classes = np.unique(y)
        self.params = {}
        for c in self.classes:
            X_c = X[y == c]
            self.params[c] = {
                'mean': X_c.mean(axis=0),
                'var': X_c.var(axis=0) + 1e-9,
                'prior': len(X_c) / len(X)
            }
    
    def _gaussian_pdf(self, x, mean, var):
        return np.exp(-0.5*(x-mean)**2/var) / np.sqrt(2*np.pi*var)
    
    def predict(self, X):
        predictions = []
        for x in X:
            posteriors = []
            for c in self.classes:
                p = self.params[c]
                likelihood = np.prod(self._gaussian_pdf(x, p['mean'], p['var']))
                posterior = likelihood * p['prior']
                posteriors.append(posterior)
            predictions.append(self.classes[np.argmax(posteriors)])
        return np.array(predictions)

# Test
X, y = make_classification(n_samples=200, n_features=2, n_redundant=0, random_state=42)
nb = NaiveBayes()
nb.fit(X[:150], y[:150])
preds = nb.predict(X[150:])
accuracy = np.mean(preds == y[150:])
print(f"Accuracy: {accuracy:.2%}")
```
</details>

### Challenge 2: Monte Carlo Estimation of Pi
```python
"""
Estimate π using Monte Carlo simulation:
1. Generate random points in a unit square
2. Count points falling inside the unit circle
3. π ≈ 4 × (points inside) / (total points)
4. Plot convergence as sample size increases
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

def estimate_pi(n_samples):
    x = np.random.uniform(-1, 1, n_samples)
    y = np.random.uniform(-1, 1, n_samples)
    inside = (x**2 + y**2) <= 1
    return 4 * np.sum(inside) / n_samples

# Convergence plot
np.random.seed(42)
sample_sizes = np.logspace(1, 6, 50).astype(int)
estimates = [estimate_pi(n) for n in sample_sizes]

plt.figure(figsize=(10, 5))
plt.semilogx(sample_sizes, estimates, 'b-')
plt.axhline(y=np.pi, color='r', linestyle='--', label=f'π = {np.pi:.6f}')
plt.xlabel('Number of samples')
plt.ylabel('Estimate of π')
plt.title('Monte Carlo Estimation of π')
plt.legend()
plt.grid(True)
plt.show()
print(f"Final estimate with 1M samples: {estimate_pi(1000000):.6f}")
```
</details>

### Challenge 3: Bootstrap Confidence Intervals
```python
"""
Implement bootstrap to estimate confidence intervals:
1. Given a sample, resample with replacement B=10000 times
2. Compute statistic (mean, median) for each resample
3. Report 95% confidence interval using percentile method
4. Compare with analytical CI for the mean
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

def bootstrap_ci(data, statistic_fn, n_bootstrap=10000, ci=0.95):
    n = len(data)
    bootstrap_stats = []
    for _ in range(n_bootstrap):
        resample = data[np.random.randint(0, n, size=n)]
        bootstrap_stats.append(statistic_fn(resample))
    
    alpha = (1 - ci) / 2
    lower = np.percentile(bootstrap_stats, 100*alpha)
    upper = np.percentile(bootstrap_stats, 100*(1-alpha))
    return lower, upper, np.array(bootstrap_stats)

# Test with skewed data
np.random.seed(42)
data = np.random.exponential(scale=2.0, size=50)

# Bootstrap CI for mean
lower, upper, boot_means = bootstrap_ci(data, np.mean)
print(f"Bootstrap 95% CI for mean: [{lower:.3f}, {upper:.3f}]")

# Analytical CI for mean (t-distribution)
from scipy import stats
se = stats.sem(data)
analytical_ci = stats.t.interval(0.95, df=len(data)-1, loc=np.mean(data), scale=se)
print(f"Analytical 95% CI for mean: [{analytical_ci[0]:.3f}, {analytical_ci[1]:.3f}]")

# Bootstrap CI for median (no simple analytical formula!)
lower_med, upper_med, _ = bootstrap_ci(data, np.median)
print(f"Bootstrap 95% CI for median: [{lower_med:.3f}, {upper_med:.3f}]")
```
</details>

### Challenge 4: Implement A/B Test Analysis
```python
"""
Build a complete A/B test analysis pipeline:
1. Simulate experiment data (conversions for control vs treatment)
2. Compute Z-test for proportions
3. Calculate p-value and confidence interval for the difference
4. Determine required sample size for 80% power to detect 2% lift
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
from scipy import stats

def ab_test(control_conversions, control_total, treatment_conversions, treatment_total, alpha=0.05):
    p1 = control_conversions / control_total
    p2 = treatment_conversions / treatment_total
    p_pool = (control_conversions + treatment_conversions) / (control_total + treatment_total)
    
    se = np.sqrt(p_pool*(1-p_pool)*(1/control_total + 1/treatment_total))
    z = (p2 - p1) / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    
    # CI for difference
    se_diff = np.sqrt(p1*(1-p1)/control_total + p2*(1-p2)/treatment_total)
    ci_lower = (p2-p1) - 1.96*se_diff
    ci_upper = (p2-p1) + 1.96*se_diff
    
    return {
        'control_rate': p1, 'treatment_rate': p2,
        'lift': (p2-p1)/p1*100,
        'z_statistic': z, 'p_value': p_value,
        'ci_95': (ci_lower, ci_upper),
        'significant': p_value < alpha
    }

def required_sample_size(baseline_rate, min_detectable_effect, alpha=0.05, power=0.80):
    z_alpha = stats.norm.ppf(1 - alpha/2)
    z_beta = stats.norm.ppf(power)
    p1, p2 = baseline_rate, baseline_rate + min_detectable_effect
    n = (z_alpha*np.sqrt(2*p1*(1-p1)) + z_beta*np.sqrt(p1*(1-p1)+p2*(1-p2)))**2 / (p2-p1)**2
    return int(np.ceil(n))

# Simulate
np.random.seed(42)
result = ab_test(control_conversions=500, control_total=10000,
                 treatment_conversions=550, treatment_total=10000)
print(f"Control: {result['control_rate']:.1%}, Treatment: {result['treatment_rate']:.1%}")
print(f"Lift: {result['lift']:.1f}%, p-value: {result['p_value']:.4f}")
print(f"95% CI: [{result['ci_95'][0]:.4f}, {result['ci_95'][1]:.4f}]")
print(f"Significant: {result['significant']}")

n = required_sample_size(0.05, 0.02)
print(f"\nRequired sample size per group for 2% lift detection: {n:,}")
```
</details>

### Challenge 5: Gaussian Mixture Model with EM Algorithm
```python
"""
Implement the Expectation-Maximization algorithm for GMM:
1. Initialize K cluster means, variances, and mixing coefficients
2. E-step: compute responsibilities (soft assignments)
3. M-step: update parameters using responsibilities
4. Iterate until convergence
5. Visualize clusters on 2D data
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

class GMM:
    def __init__(self, k=3, max_iters=100, tol=1e-6):
        self.k = k
        self.max_iters = max_iters
        self.tol = tol
    
    def fit(self, X):
        n, d = X.shape
        # Initialize
        idx = np.random.choice(n, self.k, replace=False)
        self.means = X[idx].copy()
        self.covs = [np.eye(d) for _ in range(self.k)]
        self.weights = np.ones(self.k) / self.k
        
        for iteration in range(self.max_iters):
            # E-step
            resp = self._e_step(X)
            # M-step
            old_means = self.means.copy()
            self._m_step(X, resp)
            # Check convergence
            if np.linalg.norm(self.means - old_means) < self.tol:
                break
        self.responsibilities = resp
        return self
    
    def _gaussian(self, X, mean, cov):
        d = X.shape[1]
        diff = X - mean
        inv_cov = np.linalg.inv(cov + 1e-6*np.eye(d))
        exponent = -0.5 * np.sum(diff @ inv_cov * diff, axis=1)
        norm = np.sqrt((2*np.pi)**d * np.linalg.det(cov + 1e-6*np.eye(d)))
        return np.exp(exponent) / norm
    
    def _e_step(self, X):
        resp = np.zeros((X.shape[0], self.k))
        for j in range(self.k):
            resp[:, j] = self.weights[j] * self._gaussian(X, self.means[j], self.covs[j])
        resp /= resp.sum(axis=1, keepdims=True) + 1e-10
        return resp
    
    def _m_step(self, X, resp):
        n = X.shape[0]
        for j in range(self.k):
            r_j = resp[:, j]
            N_j = r_j.sum()
            self.means[j] = (r_j[:, None] * X).sum(axis=0) / N_j
            diff = X - self.means[j]
            self.covs[j] = (r_j[:, None] * diff).T @ diff / N_j
            self.weights[j] = N_j / n

# Generate test data
np.random.seed(42)
X = np.vstack([
    np.random.randn(100, 2) + [2, 2],
    np.random.randn(100, 2) + [-2, -2],
    np.random.randn(100, 2) + [2, -2]
])

gmm = GMM(k=3).fit(X)
labels = gmm.responsibilities.argmax(axis=1)

plt.scatter(X[:, 0], X[:, 1], c=labels, cmap='viridis', alpha=0.6)
plt.scatter(gmm.means[:, 0], gmm.means[:, 1], c='red', marker='x', s=200)
plt.title('GMM Clustering with EM')
plt.show()
```
</details>

---

## Interview Questions

### 1. Explain the difference between generative and discriminative models.
<details><summary>Answer</summary>

- **Generative models** learn the joint distribution P(X,Y) or P(X). Can generate new samples and compute P(Y|X) via Bayes' theorem. Examples: Naive Bayes, GMMs, VAEs, GANs, GPT.
- **Discriminative models** learn P(Y|X) directly (the decision boundary). Can't generate data but often more accurate for classification. Examples: logistic regression, SVMs, neural network classifiers.

Key tradeoff: Generative models need more data to estimate P(X,Y) accurately but are more flexible. Discriminative models focus on what matters for prediction.
</details>

### 2. What is the curse of dimensionality and how does it relate to probability?
<details><summary>Answer</summary>

In high dimensions:
- Data becomes sparse: volume of a d-dimensional unit cube = 1ᵈ = 1, but most volume is near the surface
- Distance metrics become meaningless: all points are roughly equidistant
- You need exponentially more data to maintain density
- Gaussian distributions concentrate in a thin shell (not at the mean!)

ML implications: KNN fails, density estimation requires too many samples, feature selection becomes critical. Solutions: dimensionality reduction (PCA), regularization, manifold learning.
</details>

### 3. Explain cross-validation and why it gives better estimates than a single train/test split.
<details><summary>Answer</summary>

K-fold CV:
1. Split data into K folds
2. Train on K-1 folds, evaluate on the held-out fold
3. Repeat K times, average the scores

Benefits over single split:
- Uses ALL data for both training and evaluation
- Reduces variance of the performance estimate
- Detects overfitting more reliably
- Provides confidence intervals on performance

Standard: K=5 or K=10. Leave-one-out (K=n) has high variance despite low bias.
</details>

### 4. What is the difference between Type I and Type II errors? How do they relate to precision/recall?
<details><summary>Answer</summary>

- **Type I (False Positive)**: Rejecting H₀ when it's true (false alarm). Rate = α (significance level).
- **Type II (False Negative)**: Failing to reject H₀ when it's false (missed detection). Rate = β. Power = 1-β.

In classification:
- Precision = 1 - FP rate among positives = TP/(TP+FP) ← relates to Type I
- Recall = 1 - FN rate among actual positives = TP/(TP+FN) ← relates to Type II

Trade-off: lowering threshold increases recall (fewer Type II) but decreases precision (more Type I).
</details>

### 5. When would you use Bayesian methods over frequentist methods?
<details><summary>Answer</summary>

Use Bayesian when:
- You have strong prior knowledge (domain expertise)
- Small sample size (prior regularizes)
- You need uncertainty estimates on predictions (posterior predictive distribution)
- You want to update beliefs incrementally (online learning)
- Model comparison is needed (Bayes factors)

Use frequentist when:
- Large data (prior becomes irrelevant)
- Computational efficiency matters (posteriors can be expensive)
- Regulatory requirements demand p-values
- Simple interpretability needed
</details>

### 6. Explain the relationship between cross-entropy loss and MLE.
<details><summary>Answer</summary>

Minimizing cross-entropy loss IS maximum likelihood estimation for classification:

For binary classification with Bernoulli likelihood:
- P(y|x,θ) = p^y × (1-p)^(1-y) where p = σ(θᵀx)
- Log-likelihood: y·log(p) + (1-y)·log(1-p)
- Negative log-likelihood = binary cross-entropy loss

For multi-class with categorical distribution:
- NLL = -Σ yₖ log(pₖ) = categorical cross-entropy

So when you minimize cross-entropy, you're finding the MLE of the model parameters. This is why cross-entropy is the "natural" loss for classification.
</details>

### 7. What assumptions does linear regression make and what happens when they're violated?
<details><summary>Answer</summary>

Assumptions (LINE):
1. **Linearity**: y = Xβ + ε → violation: biased estimates, use polynomial/nonlinear models
2. **Independence**: errors are independent → violation (autocorrelation): underestimated SEs, use time-series models
3. **Normality**: ε ~ N(0, σ²) → violation: CIs/p-values unreliable (but estimates still unbiased by CLT for large n)
4. **Equal variance** (homoscedasticity): Var(ε) = σ² constant → violation: inefficient estimates, use weighted LS or robust SEs
5. **No multicollinearity**: features not perfectly correlated → violation: unstable estimates, use regularization/VIF

</details>

### 8. Explain the reparameterization trick in VAEs.
<details><summary>Answer</summary>

In VAEs, we need to backpropagate through z ~ N(μ, σ²), but sampling is not differentiable.

Reparameterization trick: Instead of z ~ N(μ, σ²), write z = μ + σ × ε where ε ~ N(0,1).

Now μ and σ are deterministic functions of input (computed by encoder), ε is external randomness. Gradients flow through μ and σ:
- ∂z/∂μ = 1
- ∂z/∂σ = ε

This enables training the encoder end-to-end with gradient descent while maintaining stochasticity.
</details>
