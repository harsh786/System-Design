# Bias and Fairness

## Overview

ML systems can perpetuate and amplify societal biases present in training data.
Understanding types of bias, definitions of fairness, and mitigation strategies
is essential for any ML practitioner building systems that affect people.

---

## Types of Bias

### Historical Bias

Bias that exists in the world and is reflected in data, even when data is perfectly collected.

```
Example: If historical hiring data shows men were hired more for engineering roles,
a model trained on this data will learn to prefer male candidates - not because of
any data collection error, but because the world was (is) biased.
```

### Representation Bias

Training data doesn't represent the population the model will serve.

```
Example: Facial recognition trained primarily on lighter-skinned faces
performs poorly on darker-skinned faces (Gender Shades study).

Example: Medical AI trained on data from one hospital doesn't generalize
to patient populations at other hospitals.
```

### Measurement Bias

The features or labels used are imperfect proxies for what we actually care about.

```
Example: Using "arrest rate" as a proxy for "crime rate" introduces bias
because arrest rates reflect policing patterns, not actual crime distribution.

Example: Using "GPA" as a proxy for "student ability" - GPA reflects
school resources, grading standards, and socioeconomic factors.
```

### Aggregation Bias

One model is used for all groups when different groups have different patterns.

```
Example: A single diabetes risk model for all ethnicities, when risk factors
and progression differ significantly across groups.
```

### Evaluation Bias

Benchmarks don't represent the deployment population, or metrics hide disparities.

```
Example: Reporting overall 95% accuracy while one demographic group
experiences 85% accuracy (masked by the majority group's high performance).
```

### Deployment Bias

The model is used in a context different from what it was designed for.

```
Example: A model designed as a "decision support tool" being used
as an automated decision-maker without human oversight.
```

---

## Fairness Definitions

### Key Definitions

There are many mathematical definitions of fairness. No single one is universally correct.

#### Demographic Parity (Statistical Parity)

```
P(Ŷ = 1 | A = 0) = P(Ŷ = 1 | A = 1)

The probability of positive prediction is the same across groups.

Example: Equal acceptance rates for loan applications across racial groups.

Limitation: Ignores whether there are actual differences in qualification rates.
May force equal outcomes regardless of base rates.
```

#### Equalized Odds

```
P(Ŷ = 1 | Y = 1, A = 0) = P(Ŷ = 1 | Y = 1, A = 1)  (Equal TPR)
P(Ŷ = 1 | Y = 0, A = 0) = P(Ŷ = 1 | Y = 0, A = 1)  (Equal FPR)

Same true positive rate AND same false positive rate across groups.

Example: A hiring model that is equally likely to correctly identify
qualified candidates and equally likely to incorrectly flag unqualified
candidates, regardless of demographic group.
```

#### Equal Opportunity

```
P(Ŷ = 1 | Y = 1, A = 0) = P(Ŷ = 1 | Y = 1, A = 1)  (Equal TPR only)

Among actually positive cases, equal prediction rates across groups.

Example: Among actually creditworthy people, approval rates are
the same regardless of race.
```

#### Calibration (Predictive Parity)

```
P(Y = 1 | Ŷ = p, A = 0) = P(Y = 1 | Ŷ = p, A = 1) = p

When the model says "70% probability," it's correct 70% of the time
for ALL groups.
```

### The Impossibility Theorem

**You cannot satisfy all fairness criteria simultaneously** (except in trivial cases).

Specifically: demographic parity, equalized odds, and calibration cannot all hold
simultaneously when base rates differ between groups (Chouldechova, 2017; Kleinberg et al., 2016).

```
If Group A has 30% base rate and Group B has 50% base rate:
- Calibration: P(Y=1|score=0.7, A) = 0.7 for both groups ✓
- Demographic Parity: Equal positive prediction rates → VIOLATES calibration
- You must CHOOSE which fairness criterion matters most for your context
```

### Choosing a Fairness Metric

| Context | Recommended Metric | Rationale |
|---------|-------------------|-----------|
| Lending/hiring (legal) | Demographic parity | Disparate impact law |
| Criminal justice | Calibration | Scores should mean the same thing |
| Medical diagnosis | Equal opportunity | Don't miss sick patients from any group |
| Content moderation | Equalized odds | Equal error rates across groups |

---

## Bias in the ML Pipeline

### Data Collection

```python
# Common data collection biases
collection_biases = {
    "sampling_bias": "Not all populations equally represented in data sources",
    "survivorship_bias": "Only seeing data from people who stayed/succeeded",
    "selection_bias": "Data reflects who uses the system, not target population",
    "temporal_bias": "Training data from one time period, deployment in another",
    "label_bias": "Annotators bring their own biases to labeling",
}
```

### Data Labeling

- Annotator demographics influence labels (especially for subjective tasks)
- Inter-annotator disagreement may be higher for marginalized groups
- Label definitions may encode cultural assumptions

### Model Training

- Models can amplify biases present in data
- Feature selection can introduce or remove bias
- Loss functions may not penalize fairness violations
- Class imbalance disproportionately affects minority groups

### Deployment

- Feedback loops: biased predictions → biased user behavior → more biased data
- Context shift: model used in scenarios it wasn't designed for
- Automation bias: humans over-trust model predictions

---

## Mitigation Strategies

### Pre-processing (Fix the Data)

#### Re-sampling

```python
from sklearn.utils import resample

def balanced_resample(X, y, sensitive_attr):
    """Resample to equalize representation across groups."""
    groups = {}
    for val in sensitive_attr.unique():
        mask = sensitive_attr == val
        groups[val] = (X[mask], y[mask])
    
    # Upsample minority groups to match majority
    max_size = max(len(g[0]) for g in groups.values())
    
    X_balanced, y_balanced = [], []
    for val, (X_g, y_g) in groups.items():
        X_up, y_up = resample(X_g, y_g, n_samples=max_size, random_state=42)
        X_balanced.append(X_up)
        y_balanced.append(y_up)
    
    return pd.concat(X_balanced), pd.concat(y_balanced)
```

#### Re-weighting

```python
def compute_sample_weights(y, sensitive_attr):
    """Assign higher weights to underrepresented group-label combinations."""
    import numpy as np
    
    weights = np.ones(len(y))
    for group in sensitive_attr.unique():
        for label in y.unique():
            mask = (sensitive_attr == group) & (y == label)
            count = mask.sum()
            if count > 0:
                weights[mask] = len(y) / (len(sensitive_attr.unique()) * len(y.unique()) * count)
    
    return weights
```

### In-processing (Fix the Model)

#### Adversarial Debiasing

```python
import torch
import torch.nn as nn

class AdversarialDebiasing(nn.Module):
    """
    Main task head + adversarial head that tries to predict sensitive attribute.
    The main model is trained to MAXIMIZE adversary loss (fool the adversary).
    """
    def __init__(self, input_dim, hidden_dim, num_classes, num_sensitive):
        super().__init__()
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        # Main task head
        self.classifier = nn.Linear(hidden_dim, num_classes)
        # Adversary (tries to predict sensitive attribute from features)
        self.adversary = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, num_sensitive),
        )
    
    def forward(self, x):
        features = self.feature_extractor(x)
        task_output = self.classifier(features)
        adv_output = self.adversary(features)
        return task_output, adv_output

# Training loop
def train_adversarial(model, data_loader, lambda_adv=1.0):
    task_criterion = nn.CrossEntropyLoss()
    adv_criterion = nn.CrossEntropyLoss()
    
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    for x, y, sensitive in data_loader:
        task_pred, adv_pred = model(x)
        
        task_loss = task_criterion(task_pred, y)
        adv_loss = adv_criterion(adv_pred, sensitive)
        
        # SUBTRACT adversary loss: we want features that DON'T predict sensitive attr
        total_loss = task_loss - lambda_adv * adv_loss
        
        optimizer.zero_grad()
        total_loss.backward()
        optimizer.step()
```

#### Fairness Constraints

```python
# Using Fairlearn's constrained optimization
from fairlearn.reductions import ExponentiatedGradient, DemographicParity
from sklearn.linear_model import LogisticRegression

# Define constraint
constraint = DemographicParity()

# Wrap base estimator with fairness constraint
mitigator = ExponentiatedGradient(
    estimator=LogisticRegression(),
    constraints=constraint,
)

# Train with fairness constraint
mitigator.fit(X_train, y_train, sensitive_features=A_train)

# Predict
y_pred = mitigator.predict(X_test)
```

### Post-processing (Fix the Output)

#### Threshold Adjustment

```python
from fairlearn.postprocessing import ThresholdOptimizer

# Find group-specific thresholds that satisfy fairness constraints
postprocessor = ThresholdOptimizer(
    estimator=trained_model,
    constraints="equalized_odds",
    objective="accuracy_score",
)

postprocessor.fit(X_val, y_val, sensitive_features=A_val)
y_pred_fair = postprocessor.predict(X_test, sensitive_features=A_test)
```

---

## Fairness Tools

### Fairlearn (Microsoft)

```python
from fairlearn.metrics import MetricFrame, selection_rate, false_positive_rate
from sklearn.metrics import accuracy_score

# Compute metrics disaggregated by group
metric_frame = MetricFrame(
    metrics={
        "accuracy": accuracy_score,
        "selection_rate": selection_rate,
        "fpr": false_positive_rate,
    },
    y_true=y_test,
    y_pred=y_pred,
    sensitive_features=A_test,
)

print(metric_frame.by_group)
print(f"Accuracy difference: {metric_frame.difference()['accuracy']:.3f}")
print(f"Selection rate ratio: {metric_frame.ratio()['selection_rate']:.3f}")
```

### AIF360 (IBM)

```python
from aif360.datasets import BinaryLabelDataset
from aif360.metrics import BinaryLabelDatasetMetric, ClassificationMetric
from aif360.algorithms.preprocessing import Reweighing

# Compute disparate impact
metric = BinaryLabelDatasetMetric(
    dataset,
    unprivileged_groups=[{"race": 0}],
    privileged_groups=[{"race": 1}],
)
print(f"Disparate Impact: {metric.disparate_impact():.3f}")
print(f"Statistical Parity Difference: {metric.statistical_parity_difference():.3f}")
```

### What-If Tool (Google)

- Interactive visualization of model fairness
- No code required (works with TensorBoard)
- Explore counterfactuals and threshold effects
- Compare multiple models side by side

---

## Case Studies

### COMPAS (Criminal Recidivism)

**System**: Correctional Offender Management Profiling for Alternative Sanctions
**Problem**: ProPublica (2016) showed Black defendants were 2x as likely to be falsely
flagged as high-risk compared to white defendants.
**Debate**: Northpointe (maker) argued the tool was calibrated (scores mean the same thing
across races). ProPublica argued error rates differed. Both were right - illustrating
the impossibility theorem.
**Lesson**: Fairness metric choice has real consequences for real people.

### Amazon Hiring Tool

**System**: Resume screening model trained on historical hiring data
**Problem**: Model learned to penalize resumes containing "women's" (e.g., "women's chess club")
because historical data reflected male-dominated hiring.
**Outcome**: Project was scrapped entirely.
**Lesson**: Historical bias in labels directly transfers to model predictions.

### Facial Recognition

**System**: Commercial face recognition APIs (Microsoft, IBM, Amazon)
**Problem**: Gender Shades study (Buolamwini & Gebru, 2018) showed error rates of 0.8%
for lighter-skinned males vs 34.7% for darker-skinned females.
**Outcome**: Companies improved models; some cities banned facial recognition.
**Lesson**: Representation bias in training data → disparate performance.

---

## Fairness Auditing Process

### Pre-deployment Audit

```markdown
1. DEFINE protected attributes and relevant fairness criteria
2. MEASURE baseline metrics disaggregated by group
3. IDENTIFY disparities exceeding acceptable thresholds
4. MITIGATE using appropriate technique (pre/in/post-processing)
5. RE-MEASURE to verify mitigation worked without degrading overall performance
6. DOCUMENT findings in model card
7. ESTABLISH monitoring for production drift
```

### Ongoing Monitoring

```python
def fairness_monitor(predictions, labels, sensitive_features, thresholds):
    """Monitor fairness metrics and alert on violations."""
    from fairlearn.metrics import MetricFrame, selection_rate
    
    mf = MetricFrame(
        metrics={"selection_rate": selection_rate},
        y_true=labels,
        y_pred=predictions,
        sensitive_features=sensitive_features,
    )
    
    ratio = mf.ratio()["selection_rate"]
    
    if ratio < thresholds["disparate_impact"]:  # e.g., 0.8 (4/5 rule)
        alert(f"Disparate impact violation: ratio = {ratio:.3f}")
        return False
    return True
```

---

## Decision Framework

### When You Discover Bias

```
1. Is the bias causing harm NOW?
   YES → Immediate mitigation (threshold adjustment, human review)
   NO  → Proceed with systematic fix

2. Can we remove the bias without significant accuracy loss?
   YES → Apply mitigation, validate, deploy
   NO  → Determine acceptable accuracy-fairness tradeoff with stakeholders

3. Is the tradeoff acceptable to affected communities?
   YES → Deploy with monitoring
   NO  → Consider whether the system should exist at all

4. Can we achieve the business goal with a less biased approach?
   YES → Redesign the system
   NO  → Add human oversight, constrain use cases, or don't build it
```

### The 4/5 Rule (Disparate Impact)

From US employment law: selection rate of any group should be at least 80% (4/5)
of the group with the highest selection rate.

```python
def four_fifths_rule(y_pred, sensitive_attr):
    """Check if predictions satisfy the 4/5 rule."""
    rates = {}
    for group in sensitive_attr.unique():
        mask = sensitive_attr == group
        rates[group] = y_pred[mask].mean()
    
    max_rate = max(rates.values())
    
    violations = {}
    for group, rate in rates.items():
        ratio = rate / max_rate
        if ratio < 0.8:
            violations[group] = ratio
    
    return violations  # Empty dict = no violations
```

---

## Summary

Bias and fairness in ML is not a solved problem - it requires ongoing vigilance,
clear thinking about values and tradeoffs, and systematic processes.

**Key takeaways**:
1. Bias enters at every stage of the pipeline
2. There's no single "correct" fairness definition - context matters
3. Fairness and accuracy often (but not always) trade off
4. Mitigation techniques exist at pre-processing, in-processing, and post-processing stages
5. Audit before deployment, monitor after deployment
6. Include affected communities in the conversation
