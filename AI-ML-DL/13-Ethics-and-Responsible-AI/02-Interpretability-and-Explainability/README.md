# Interpretability and Explainability

## Why Interpretability Matters

### Three Core Reasons

1. **Trust**: Users and stakeholders need to understand why a model made a decision
2. **Debugging**: Understanding model behavior helps identify and fix errors
3. **Compliance**: Regulations increasingly require explanations for automated decisions

### The Interpretability-Accuracy Tradeoff

```
High Interpretability ←──────────────────────→ High Accuracy (historically)
Linear Regression    Decision Trees    Random Forests    Deep Neural Networks

Note: This tradeoff is less clear-cut with modern explainability tools.
Post-hoc explanations allow using complex models + providing explanations.
```

---

## Intrinsically Interpretable Models

### Linear Models

```python
from sklearn.linear_model import LogisticRegression
import numpy as np

model = LogisticRegression()
model.fit(X_train, y_train)

# Interpretation: each coefficient = effect of 1-unit change in feature
for feature, coef in zip(feature_names, model.coef_[0]):
    print(f"{feature}: {coef:+.3f}")
    # Positive = increases probability of class 1
    # Magnitude = strength of effect

# Example output:
# income: +0.45      (higher income → more likely approved)
# debt_ratio: -0.89  (higher debt → less likely approved)
# age: +0.12         (slightly favors older applicants)
```

### Decision Trees

```python
from sklearn.tree import DecisionTreeClassifier, export_text

tree = DecisionTreeClassifier(max_depth=4)
tree.fit(X_train, y_train)

# Full explanation is the path from root to leaf
print(export_text(tree, feature_names=feature_names))

# Example:
# |--- income <= 50000
# |   |--- debt_ratio <= 0.4
# |   |   |--- class: approved
# |   |--- debt_ratio > 0.4
# |   |   |--- class: denied
# |--- income > 50000
# |   |--- class: approved
```

### Generalized Additive Models (GAMs)

```python
from interpret.glassbox import ExplainableBoostingClassifier

# EBM: state-of-the-art interpretable model
ebm = ExplainableBoostingClassifier()
ebm.fit(X_train, y_train)

# Each feature has a learned shape function
# f(x) = f1(x1) + f2(x2) + ... + f_ij(xi, xj) + intercept
from interpret import show
ebm_global = ebm.explain_global()
show(ebm_global)  # Interactive plots of each shape function
```

---

## Post-Hoc Explanations

### SHAP (SHapley Additive exPlanations) ⭐

**Theory**: Based on Shapley values from cooperative game theory. Each feature's contribution
is computed as its marginal contribution averaged over all possible feature orderings.

```
φᵢ = Σ [|S|!(|N|-|S|-1)! / |N|!] × [f(S ∪ {i}) - f(S)]
     S⊆N\{i}

Where:
- φᵢ = Shapley value for feature i
- S = subset of features
- N = all features
- f(S) = model prediction using features in S
```

**Properties** (uniquely satisfying):
- **Efficiency**: Shapley values sum to f(x) - E[f(x)]
- **Symmetry**: Equal features get equal attribution
- **Dummy**: Unused features get zero attribution
- **Additivity**: Values are additive across features

```python
import shap

# For tree-based models (fast, exact)
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# For any model (slower, approximate)
explainer = shap.KernelExplainer(model.predict, X_train[:100])
shap_values = explainer.shap_values(X_test[:10])

# For deep learning models
explainer = shap.DeepExplainer(model, X_train[:100])
shap_values = explainer.shap_values(X_test[:10])

# Visualizations
# Single prediction explanation
shap.force_plot(explainer.expected_value, shap_values[0], X_test.iloc[0])

# Global feature importance
shap.summary_plot(shap_values, X_test)

# Feature dependence
shap.dependence_plot("income", shap_values, X_test)
```

#### SHAP for a Loan Decision

```python
import shap
import xgboost as xgb

# Train model
model = xgb.XGBClassifier()
model.fit(X_train, y_train)

# Explain a single prediction
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# For applicant #42:
idx = 42
print(f"Prediction: {'Approved' if model.predict(X_test[idx:idx+1])[0] else 'Denied'}")
print(f"\nBase value (average): {explainer.expected_value:.3f}")
print(f"Output value: {shap_values[idx].sum() + explainer.expected_value:.3f}")
print(f"\nTop contributing features:")
feature_contributions = list(zip(feature_names, shap_values[idx]))
feature_contributions.sort(key=lambda x: abs(x[1]), reverse=True)
for feat, val in feature_contributions[:5]:
    direction = "↑ toward approval" if val > 0 else "↓ toward denial"
    print(f"  {feat}: {val:+.3f} ({direction})")

# Output:
# Prediction: Denied
# Base value (average): 0.620
# Output value: 0.234
#
# Top contributing features:
#   debt_to_income: -0.234 (↓ toward denial)
#   credit_score: -0.098 (↓ toward denial)
#   income: +0.045 (↑ toward approval)
#   employment_years: -0.067 (↓ toward denial)
#   loan_amount: -0.032 (↓ toward denial)
```

### LIME (Local Interpretable Model-agnostic Explanations)

**Theory**: Approximate the complex model locally with an interpretable model (usually linear)
by perturbing the input and observing how predictions change.

```python
import lime
import lime.lime_tabular

explainer = lime.lime_tabular.LimeTabularExplainer(
    X_train.values,
    feature_names=feature_names,
    class_names=['denied', 'approved'],
    mode='classification'
)

# Explain single prediction
exp = explainer.explain_instance(
    X_test.iloc[42].values,
    model.predict_proba,
    num_features=10,
)

# Show explanation
exp.show_in_notebook()  # or
print(exp.as_list())
# [('debt_to_income > 0.45', -0.32),
#  ('credit_score <= 620', -0.18),
#  ('income <= 45000', -0.08), ...]
```

**LIME vs SHAP**:

| Aspect | LIME | SHAP |
|--------|------|------|
| Theory | Local linear approximation | Game theory (Shapley values) |
| Consistency | Can be unstable | Consistent, unique solution |
| Speed | Fast (samples locally) | Varies (exact for trees, slow for kernel) |
| Global view | Not directly | Yes (aggregate local explanations) |
| Guarantees | None | Satisfies fairness axioms |

### Feature Importance Methods

#### Permutation Importance

```python
from sklearn.inspection import permutation_importance

# Shuffle each feature and measure performance drop
result = permutation_importance(
    model, X_test, y_test,
    n_repeats=30,
    random_state=42,
    scoring='accuracy'
)

# Plot
for i in result.importances_mean.argsort()[::-1][:10]:
    print(f"{feature_names[i]}: {result.importances_mean[i]:.3f} ± {result.importances_std[i]:.3f}")
```

#### Built-in Importance (Tree-based)

```python
# Gini importance (biased toward high-cardinality features)
importances = model.feature_importances_

# CAUTION: Built-in importance can be misleading!
# - Biased toward features with more unique values
# - Doesn't account for feature correlation
# - Use permutation importance instead for reliable results
```

### Partial Dependence Plots (PDP)

Shows marginal effect of a feature on predictions, averaged over all other features.

```python
from sklearn.inspection import PartialDependenceDisplay

# How does income affect loan approval probability?
PartialDependenceDisplay.from_estimator(
    model, X_test,
    features=['income', 'credit_score', ('income', 'credit_score')],
    kind='average',  # or 'individual' for ICE plots
)
```

### ICE Plots (Individual Conditional Expectation)

Like PDP but shows individual lines instead of average - reveals heterogeneous effects.

```python
PartialDependenceDisplay.from_estimator(
    model, X_test,
    features=['income'],
    kind='individual',  # Each line = one data point
    subsample=50,       # Show 50 random individuals
)
# If lines are parallel → feature has uniform effect
# If lines cross → feature effect depends on other features (interaction)
```

### Counterfactual Explanations

"What's the smallest change that would flip the decision?"

```python
# Using DiCE (Diverse Counterfactual Explanations)
import dice_ml

# Setup
data = dice_ml.Data(dataframe=df, continuous_features=cont_features,
                    outcome_name='approved')
model_dice = dice_ml.Model(model=model, backend='sklearn')
exp = dice_ml.Dice(data, model_dice)

# Generate counterfactuals for a denied applicant
counterfactuals = exp.generate_counterfactuals(
    query_instance=denied_applicant,
    total_CFs=3,
    desired_class="approved"
)
counterfactuals.visualize_as_dataframe()

# Output: "If your income increased from $40K to $52K and your 
#          debt ratio decreased from 0.5 to 0.38, you would be approved"
```

---

## Attention Visualization (Limitations)

### The Appeal

```python
# Extract attention weights from a transformer
outputs = model(input_ids, attention_mask=attention_mask, output_attentions=True)
attention = outputs.attentions  # List of [batch, heads, seq_len, seq_len]

# Visualize
import seaborn as sns
sns.heatmap(attention[0][0][0].detach().numpy(), 
            xticklabels=tokens, yticklabels=tokens)
```

### The Problem

**Attention is NOT explanation** (Jain & Wallace, 2019; Wiegreffe & Pinter, 2019):

1. Attention weights don't necessarily correlate with feature importance
2. Different attention patterns can produce identical outputs
3. Attention shows where the model LOOKS, not what it USES
4. Gradient-based attribution is more reliable for transformers

### Better Alternatives for Transformers

- **Integrated Gradients**: Attributes along a path from baseline to input
- **Attention Rollout**: Accounts for residual connections
- **Layer-wise Relevance Propagation (LRP)**
- **Input × Gradient**: Simple but often effective

---

## Concept-Based Explanations (TCAV)

Testing with Concept Activation Vectors: Explains in terms of human concepts rather than features.

```
Instead of: "pixel (23, 45) contributed +0.03 to 'cat' prediction"
TCAV says:  "The concept 'stripes' is important for predicting 'zebra'"
```

---

## Model Cards and Datasheets

### Model Card Template

```markdown
# Model Card: [Model Name]

## Model Details
- Developed by: [Team]
- Model type: [Architecture]
- Training data: [Dataset, version, size]
- Intended use: [Specific use cases]
- Out-of-scope use: [What NOT to use it for]

## Performance
- Overall accuracy: XX%
- Performance by demographic group:
  | Group | Accuracy | FPR | FNR |
  |-------|----------|-----|-----|
  | ... | ... | ... | ... |

## Limitations
- Known failure modes: ...
- Known biases: ...
- Not suitable for: ...

## Ethical Considerations
- Potential harms: ...
- Mitigation measures: ...

## Evaluation Data
- Datasets used: ...
- Motivation for choice: ...
- Preprocessing: ...
```

---

## Explainability for LLMs

### Chain-of-Thought as Explanation

```python
prompt = """Explain your reasoning step by step before giving the final answer.

Question: Should this loan application be approved?
Applicant: Income $75K, Debt-to-income 0.35, Credit score 720, 5 years employed

Step-by-step reasoning:
1. Income of $75K is above the median threshold
2. Debt-to-income ratio of 0.35 is within acceptable range (<0.43)
3. Credit score of 720 is "good" (above 670 threshold)
4. 5 years of employment shows stability

Decision: Approve
"""
# Caveat: CoT may be a post-hoc rationalization, not the actual computation
```

### Attribution for RAG Systems

```python
# When using RAG, cite which retrieved documents influenced the answer
response = {
    "answer": "The policy covers water damage from burst pipes.",
    "sources": [
        {"doc": "policy_v3.pdf", "page": 12, "relevance": 0.94},
        {"doc": "claims_guide.pdf", "page": 7, "relevance": 0.87},
    ],
    "confidence": 0.91,
}
```

---

## Regulations Requiring Explainability

### EU AI Act (2024)

- **High-risk AI systems** must be "sufficiently transparent to enable users to interpret the system's output and use it appropriately"
- Requires documentation of system logic, capabilities, and limitations

### GDPR Article 22

- Right to "meaningful information about the logic involved" in automated decisions
- Right to human review of automated decisions with legal effects

### US Context

- No federal AI explainability law (as of 2024)
- Sector-specific: ECOA (lending), Fair Housing Act, EEOC guidelines
- State laws emerging (Colorado AI Act, NYC Local Law 144)

### Practical Implications

```
Risk Level → Explanation Requirement

Low (content recommendations):
  - Minimal: "Recommended because you watched X"

Medium (insurance pricing):  
  - Moderate: Top factors, direction of influence

High (loan denial, hiring):
  - Full: Specific reasons, actionable recourse
  - "Your application was denied primarily because:
     1. Debt-to-income ratio (0.55) exceeds our threshold (0.43)
     2. Credit history length (2 years) is below minimum (3 years)
     To improve: reduce outstanding debt or wait for longer credit history"

Critical (criminal justice, medical):
  - Maximum + human oversight mandatory
```

---

## Summary

Interpretability is not a single technique but a toolbox. Choose based on:

1. **Who needs the explanation?** (data scientist debugging vs. customer vs. regulator)
2. **What model type?** (intrinsic for simple models, post-hoc for complex)
3. **Local or global?** (explain one prediction vs. overall model behavior)
4. **What fidelity?** (approximate explanation vs. exact attribution)

**Key tools**: SHAP for rigorous feature attribution, LIME for quick local explanations,
PDPs for global feature effects, counterfactuals for actionable recourse.
