# Naive Bayes

## Intuition

Apply Bayes' theorem to classification, assuming all features are independent given the class. Despite this "naive" assumption being almost always wrong, it works remarkably well in practice.

```
P(spam | "buy cheap now") ∝ P("buy"|spam) · P("cheap"|spam) · P("now"|spam) · P(spam)
                                    ↑ assumes word probabilities are independent
```

## Bayes' Theorem for Classification

```
P(Y=c | X) = P(X | Y=c) · P(Y=c) / P(X)

Prediction: ŷ = argmax_c  P(Y=c) · P(X | Y=c)
                           ↑prior    ↑likelihood
```

Since P(X) is the same for all classes, we only need the numerator for comparison.

## The Naive Independence Assumption

```
P(x₁, x₂, ..., xₙ | Y=c) = Π P(xᵢ | Y=c)

Without this: need to estimate joint distribution (exponential parameters)
With this: estimate each P(xᵢ|Y) independently (linear parameters)
```

## Variants

### Gaussian Naive Bayes (continuous features)
```
P(xᵢ | Y=c) = (1/√(2πσ²_ic)) · exp(-(xᵢ - μ_ic)² / (2σ²_ic))

Estimate μ_ic and σ²_ic from training data for each feature-class pair.
Use for: general continuous data (iris, sensor readings)
```

### Multinomial Naive Bayes (count features)
```
P(xᵢ | Y=c) ∝ θ_ic^xᵢ    where θ_ic = count of feature i in class c / total

Use for: text classification with word counts or TF-IDF
```

### Bernoulli Naive Bayes (binary features)
```
P(x | Y=c) = Π θ_ic^xᵢ · (1-θ_ic)^(1-xᵢ)

Explicitly models absence of features (unlike Multinomial).
Use for: text with binary word presence/absence, binary feature data
```

## Laplace Smoothing

Problem: if a word never appears in class c, P(word|c) = 0, zeroing out the entire product.

```
θ_ic = (count(feature i in class c) + α) / (total count in class c + α·|V|)

α = 1: Laplace smoothing (add-one)
α < 1: Lidstone smoothing
|V| = vocabulary size (number of distinct features)
```

## Why It Works Despite Wrong Assumption

1. Classification needs correct **ranking** of P(Y|X), not exact probabilities
2. Errors in individual P(xᵢ|Y) estimates may cancel out
3. The decision boundary may still be correct even if probabilities are wrong
4. With limited data, the low-variance estimate outperforms high-variance correct models

## From-Scratch Implementation

```python
import numpy as np

class MultinomialNaiveBayes:
    def __init__(self, alpha=1.0):
        self.alpha = alpha  # Laplace smoothing
    
    def fit(self, X, y):
        self.classes = np.unique(y)
        self.class_log_prior = {}
        self.feature_log_prob = {}
        
        for c in self.classes:
            X_c = X[y == c]
            self.class_log_prior[c] = np.log(len(X_c) / len(y))
            # Word counts per class + smoothing
            word_counts = X_c.sum(axis=0) + self.alpha
            total = word_counts.sum()
            self.feature_log_prob[c] = np.log(word_counts / total)
    
    def predict(self, X):
        predictions = []
        for x in X:
            scores = {}
            for c in self.classes:
                # Log-space to prevent underflow
                scores[c] = self.class_log_prior[c] + np.sum(x * self.feature_log_prob[c])
            predictions.append(max(scores, key=scores.get))
        return np.array(predictions)

class GaussianNaiveBayes:
    def fit(self, X, y):
        self.classes = np.unique(y)
        self.params = {}  # {class: (means, variances)}
        self.priors = {}
        
        for c in self.classes:
            X_c = X[y == c]
            self.params[c] = (X_c.mean(axis=0), X_c.var(axis=0) + 1e-9)
            self.priors[c] = len(X_c) / len(y)
    
    def predict(self, X):
        predictions = []
        for x in X:
            scores = {}
            for c in self.classes:
                mean, var = self.params[c]
                log_likelihood = -0.5 * np.sum(np.log(2*np.pi*var) + (x-mean)**2/var)
                scores[c] = np.log(self.priors[c]) + log_likelihood
            predictions.append(max(scores, key=scores.get))
        return np.array(predictions)
```

## Sklearn Usage

```python
from sklearn.naive_bayes import GaussianNB, MultinomialNB, BernoulliNB
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.pipeline import Pipeline

# Text classification (the killer app for NB)
text_pipe = Pipeline([
    ('vectorizer', TfidfVectorizer(max_features=10000, stop_words='english')),
    ('clf', MultinomialNB(alpha=1.0))
])
text_pipe.fit(train_texts, train_labels)

# Gaussian NB for continuous features
gnb = GaussianNB()
gnb.fit(X_train, y_train)

# Complement NB (better for imbalanced text)
from sklearn.naive_bayes import ComplementNB
cnb = ComplementNB(alpha=0.5)
```

## Hyperparameter Guide

| Parameter | Variant | Values to Try | Effect |
|-----------|---------|---------------|--------|
| alpha | All | [0.01, 0.1, 0.5, 1.0, 2.0] | Smoothing strength |
| var_smoothing | Gaussian | [1e-9, 1e-7, 1e-5] | Variance floor |
| fit_prior | All | True, False | Use class priors or uniform |

Minimal tuning needed — one of NB's advantages.

## When to Use / When NOT to Use

**Use when:**
- Text classification (spam, sentiment, topic) — NB's sweet spot
- Very high-dimensional sparse data
- Small training sets (low variance estimator)
- Real-time prediction needed (extremely fast)
- Multi-class problems
- Baseline model

**Don't use when:**
- Features are heavily correlated (violates independence badly)
- Need accurate probability estimates (NB probabilities are poorly calibrated)
- Complex non-linear relationships between features
- Numerical features with non-Gaussian distributions (for GaussianNB)

## Common Mistakes

1. **Forgetting Laplace smoothing** → zero probabilities kill predictions
2. **Using MultinomialNB with negative values** → needs non-negative inputs (counts or TF-IDF)
3. **Trusting NB probability outputs** → they're often extreme (near 0 or 1), use calibration
4. **Not working in log-space** → product of many small probabilities = underflow

## Interview Questions

**Q1: Why does Naive Bayes work well despite the wrong independence assumption?**
For classification, we only need the correct argmax, not exact probabilities. The independence assumption reduces variance significantly (fewer parameters to estimate), which often outweighs the bias it introduces, especially with limited data.

**Q2: Naive Bayes vs Logistic Regression?**
NB is generative (models P(X|Y)), LR is discriminative (models P(Y|X) directly). NB converges faster with less data but to a worse asymptotic error. NB assumes independence; LR doesn't. Both produce linear decision boundaries under certain conditions.

**Q3: How does Naive Bayes handle missing features?**
Simply omit the missing feature from the product — P(X|Y) = Π over observed features only. This is a natural advantage of the independence assumption.

**Q4: What's the difference between Multinomial and Bernoulli NB for text?**
Multinomial uses word counts (how many times each word appears). Bernoulli uses binary presence/absence and explicitly penalizes absence of expected words. Bernoulli works better for short texts; Multinomial for longer documents.

**Q5: When would Naive Bayes outperform deep learning?**
Very small datasets (< 1000 samples), extremely high-dimensional sparse data, need for real-time training/updating, or when interpretability of feature contributions is required.
