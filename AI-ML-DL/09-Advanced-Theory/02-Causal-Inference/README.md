# Causal Inference

## Correlation vs Causation

```
Ice cream sales ↑  ←→  Drowning deaths ↑
Correlation: 0.95
Causation: NONE (confounded by temperature/summer)

            Temperature
           /           \
          ↓             ↓
   Ice Cream Sales    Drowning
```

**The fundamental problem**: We can never observe both Y(treatment=1) AND Y(treatment=0)
for the same individual at the same time.

## Structural Causal Models (SCMs)

An SCM consists of:
1. **Endogenous variables** V (observed)
2. **Exogenous variables** U (noise/unobserved)
3. **Structural equations** V_i = f_i(pa_i, U_i)

```
Example: Drug → Recovery
  U_age ~ Uniform(20, 80)
  U_drug ~ Bernoulli(0.5)
  U_noise ~ Normal(0, 1)
  
  Age = U_age
  Drug = g(Age, U_drug)           # older people more likely prescribed
  Recovery = h(Drug, Age, U_noise) # both drug and age affect recovery
```

## Directed Acyclic Graphs (DAGs)

```
Confounder (common cause):        Collider (common effect):
      Z                                 X    Y
     / \                                 \  /
    ↓   ↓                                 ↓
    X   Y                                 Z
  
  Condition on Z: removes            Condition on Z: CREATES
  spurious X-Y association           spurious X-Y association!

Mediator (causal chain):           Fork (confounder):
    X → M → Y                          Z → X
                                        Z → Y
  Condition on M: blocks               Must condition on Z
  causal effect through M              to get X→Y effect
```

### d-Separation Rules

A path is blocked if:
1. It contains a chain A → B → C or fork A ← B → C, and B is conditioned on
2. It contains a collider A → B ← C, and B (nor its descendants) is NOT conditioned on

## do-Calculus (Pearl's Intervention)

```
Observational:  P(Y | X=x)     "What is Y among those who happen to have X=x?"
Interventional: P(Y | do(X=x)) "What would Y be if we FORCED X=x?"

Key difference:
  P(Y | X=x) includes confounding (people who choose X may differ)
  P(Y | do(X=x)) removes confounding (we set X regardless of other factors)
```

### Adjustment Formula (Back-door criterion)

If Z satisfies the back-door criterion (blocks all back-door paths from X to Y):

```
P(Y | do(X=x)) = Σ_z P(Y | X=x, Z=z) P(Z=z)
```

### Front-door Criterion

When no valid back-door adjustment exists but a mediator M is available:

```
P(Y | do(X)) = Σ_m P(M=m|X) Σ_x' P(Y|M=m, X=x') P(X=x')
```

## do-Calculus Rules

Pearl's three rules for manipulating interventional distributions:

```
Rule 1 (Insertion/deletion of observations):
  P(Y|do(X),Z,W) = P(Y|do(X),W)  if (Y ⊥ Z | X,W) in G_X̄

Rule 2 (Action/observation exchange):
  P(Y|do(X),do(Z),W) = P(Y|do(X),Z,W)  if (Y ⊥ Z | X,W) in G_X̄Z̲

Rule 3 (Insertion/deletion of actions):
  P(Y|do(X),do(Z),W) = P(Y|do(X),W)  if (Y ⊥ Z | X,W) in G_X̄Z̄(W)
```

## Observational Causal Inference Methods

### Propensity Score Matching

```
Propensity score: e(x) = P(Treatment=1 | Covariates=x)

Steps:
1. Estimate e(x) (e.g., logistic regression)
2. Match treated units with control units having similar e(x)
3. Estimate ATE from matched pairs

Assumption: No unmeasured confounders (strong ignorability)
```

### Instrumental Variables (IV)

```
When there IS unmeasured confounding:

  Instrument Z → Treatment X → Outcome Y
                      ↑               ↑
                      └─── U ─────────┘  (unmeasured confounder)

Requirements for valid instrument Z:
  1. Relevance: Z affects X (strong first stage)
  2. Exclusion: Z affects Y ONLY through X
  3. Independence: Z is independent of U

IV estimate (Wald): β_IV = Cov(Y,Z) / Cov(X,Z)
Example: Distance to college (Z) → Education (X) → Earnings (Y)
```

### Regression Discontinuity (RD)

```
Idea: At a sharp threshold, treatment is "as good as random"

Example: Scholarship if GPA > 3.5
  - Students at 3.49 vs 3.51 are nearly identical
  - Difference in outcomes ≈ causal effect of scholarship

   Y │         ●●●
     │       ●●   ←── Treatment effect (jump)
     │     ●●
     │   ●●
     │ ●●●●●●
     └──────────── X
          cutoff
```

### Difference-in-Differences (DiD)

```
                    Before    After
Treatment group:    Y_T0      Y_T1
Control group:      Y_C0      Y_C1

DiD estimate = (Y_T1 - Y_T0) - (Y_C1 - Y_C0)

Assumption: Parallel trends (absent treatment, both groups would
have changed by the same amount)

   Y │        ●── Treatment (actual)
     │       /
     │      / ·── Treatment (counterfactual, parallel trend)
     │     / /
     │    ○─────── Control
     └──────────── Time
         intervention
```

## Counterfactual Reasoning

Three levels of causal hierarchy (Pearl's Ladder):

```
Level 3: Counterfactuals  "What if I had done X differently?"
Level 2: Interventions    "What if I do X?"
Level 1: Associations     "What is P(Y|X)?"

Counterfactual query: "Would patient have survived (Y) had they 
received treatment (X=1), given that they did NOT receive it (X=0) 
and died (Y=0)?"

P(Y_x=1 = 1 | X=0, Y=0) — cannot be answered from data alone!
Requires structural model + assumptions.
```

## Treatment Effects

```
Individual Treatment Effect (ITE):
  τᵢ = Yᵢ(1) - Yᵢ(0)   ← fundamental problem: only one is observed

Average Treatment Effect (ATE):
  τ = E[Y(1) - Y(0)]

Average Treatment Effect on the Treated (ATT):
  τ_ATT = E[Y(1) - Y(0) | T=1]

Conditional ATE (CATE):
  τ(x) = E[Y(1) - Y(0) | X=x]   ← heterogeneous treatment effects
```

## Uplift Modeling

Estimate **individual** treatment effects for targeting:

```
┌─────────────────────────────────────────────────────┐
│ Customer Segments by Treatment Response:            │
│                                                     │
│  "Sure Things"  - buy regardless    → don't target  │
│  "Persuadables" - buy IF targeted   → TARGET THESE  │
│  "Lost Causes"  - won't buy either  → don't target  │
│  "Sleeping Dogs" - buy unless targeted → avoid!     │
└─────────────────────────────────────────────────────┘

Methods:
  - Two-model approach: τ̂(x) = M₁(x) - M₀(x)
  - Causal forests (Athey & Imbens)
  - Meta-learners (S-learner, T-learner, X-learner)
```

## Causal Discovery Algorithms

Learn the DAG structure from data:

```
PC Algorithm:
  1. Start with complete undirected graph
  2. Remove edges using conditional independence tests
  3. Orient edges using v-structures and rules

FCI (Fast Causal Inference):
  - Handles latent confounders
  - Outputs PAG (partial ancestral graph)

GES (Greedy Equivalence Search):
  - Score-based (BIC)
  - Forward phase: add edges
  - Backward phase: remove edges
```

## Python Example with DoWhy

```python
import dowhy
from dowhy import CausalModel
import pandas as pd
import numpy as np

# Generate data with confounding
np.random.seed(42)
n = 1000
age = np.random.normal(50, 10, n)
treatment = (age > 50).astype(int) + np.random.binomial(1, 0.3, n)
treatment = np.clip(treatment, 0, 1)
outcome = 2 * treatment - 0.05 * age + np.random.normal(0, 1, n)

data = pd.DataFrame({'age': age, 'treatment': treatment, 'outcome': outcome})

# Define causal model
model = CausalModel(
    data=data,
    treatment='treatment',
    outcome='outcome',
    common_causes=['age'],  # Known confounder
    graph="digraph { age -> treatment; age -> outcome; treatment -> outcome; }"
)

# Identify causal effect
identified = model.identify_effect(proceed_when_unidentifiable=True)
print(identified.estimand)

# Estimate using different methods
estimate_psm = model.estimate_effect(
    identified,
    method_name="backdoor.propensity_score_matching"
)
print(f"PSM estimate: {estimate_psm.value:.3f}")  # Should be ~2.0

estimate_iv = model.estimate_effect(
    identified,
    method_name="backdoor.linear_regression"
)
print(f"Linear regression estimate: {estimate_iv.value:.3f}")

# Refutation: Add random common cause
refutation = model.refute_estimate(
    identified, estimate_psm,
    method_name="random_common_cause"
)
print(refutation)
```

## EconML for Heterogeneous Treatment Effects

```python
from econml.dml import CausalForestDML
from sklearn.ensemble import GradientBoostingRegressor

# Estimate CATE (heterogeneous effects)
est = CausalForestDML(
    model_y=GradientBoostingRegressor(),
    model_t=GradientBoostingRegressor(),
    n_estimators=1000
)
est.fit(Y=outcome, T=treatment, X=features, W=confounders)

# Individual treatment effects
cate = est.effect(X_test)
# Confidence intervals
lb, ub = est.effect_interval(X_test, alpha=0.05)
```

## Applications

### A/B Testing Limitations
- Network effects (SUTVA violation)
- Long-term effects vs short-term metrics
- Ethical constraints on randomization
- Solution: quasi-experimental methods above

### Recommendation Debiasing
- Users only see recommended items → feedback loop
- Causal approach: model what user would have done without recommendation
- Inverse propensity weighting for unbiased evaluation

### Policy Evaluation
- Off-policy evaluation: estimate effect of new policy from old policy's data
- Importance sampling: reweight by P(new)/P(old)
- Doubly robust estimators

## Interview Questions

1. Explain the difference between P(Y|X) and P(Y|do(X)) with an example.
2. When would you use instrumental variables vs propensity score matching?
3. What is the fundamental problem of causal inference?
4. How would you detect if a confounder is missing from your causal graph?
5. Explain the parallel trends assumption in DiD.
6. How can causal inference improve a recommendation system?
7. What is a collider and why is conditioning on it problematic?

## Key Papers

- Pearl, "Causality" (2009) — foundational textbook
- Rubin, "Causal Inference Using Potential Outcomes" (2005)
- Athey & Imbens, "Recursive Partitioning for Heterogeneous Causal Effects" (2016)
- Sharma & Kiciman, "DoWhy: An End-to-End Library for Causal Inference" (2020)
- Peters, Janzing, Schölkopf, "Elements of Causal Inference" (2017)
- Hernán & Robins, "Causal Inference: What If" (2020, free online)
