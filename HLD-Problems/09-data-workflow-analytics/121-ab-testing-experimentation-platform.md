# Problem 121: Design an A/B Testing & Experimentation Platform

## Problem Statement

Design a scalable A/B Testing and Experimentation Platform similar to Optimizely, GrowthBook, or internal platforms at Netflix/LinkedIn/Microsoft. The platform should enable product teams to run controlled experiments, measure impact with statistical rigor, and make data-driven decisions at scale.

## Key Challenges

### 1. Experiment Assignment
- Deterministic hashing for consistent user-to-variant mapping
- Avoiding selection bias and ensuring randomization quality
- Supporting multiple assignment strategies (user-level, session-level, page-level)
- Ramp-up and ramp-down of traffic allocation without reassignment

### 2. Statistical Significance Calculation
- Proper hypothesis testing (frequentist vs Bayesian approaches)
- Multiple comparison correction (Bonferroni, FDR)
- Sample size estimation and power analysis
- Confidence interval computation at scale

### 3. Metric Pipeline
- Guardrail metrics (must not degrade: latency, error rate, revenue)
- Primary metrics (what we're trying to move)
- Secondary metrics (exploratory, informational)
- Real-time metric computation vs batch analysis trade-offs

### 4. Experiment Interference
- Multi-layer experiment design for orthogonal experiments
- Detecting and preventing metric pollution between experiments
- Holdout groups for measuring cumulative impact
- Mutual exclusion groups for conflicting experiments

### 5. Feature Interaction Detection
- Identifying when experiments interact statistically
- Heterogeneous treatment effect analysis
- Segment-level analysis (did variant help/hurt specific user segments?)

### 6. Sequential Testing & Early Stopping
- Continuous monitoring without inflating false positive rates
- Always-valid confidence intervals
- Automated decision rules for stopping experiments

## Scale Requirements
- 1B+ users across experiments
- 1000+ concurrent experiments running simultaneously
- Real-time metric computation (minutes, not hours)
- Sub-millisecond assignment latency (on the hot path)
- Petabytes of event data for metric computation

## Expected Design Areas
- Assignment service architecture
- Metric computation pipeline
- Statistical engine
- Experiment management UI/API
- Data storage and query layer
- Caching and performance optimization
