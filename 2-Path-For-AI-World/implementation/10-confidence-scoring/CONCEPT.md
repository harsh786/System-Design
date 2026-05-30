# Confidence Scoring for AI Systems

## Why You Should NOT Trust Model Self-Reported Confidence

LLMs produce token-level log-probabilities that are often mistaken for calibrated confidence scores. This is fundamentally flawed for several reasons:

### The Core Problem

1. **Training objective mismatch**: Models are trained to maximize next-token likelihood, not to produce calibrated uncertainty estimates. A model saying "I'm 90% confident" has no grounding in actual outcome frequencies.

2. **Verbalized confidence is performative**: When you ask a model "how confident are you?", the response is generated the same way as any other text — by predicting the most likely next token given training data. It's pattern-matching on how humans express confidence, not introspection.

3. **Log-probabilities ≠ answer correctness**: High token probability means the token is linguistically likely given context. A model can fluently and confidently produce completely fabricated information (hallucination). The probability of the token "Paris" being generated tells you nothing about whether Paris is the correct answer.

4. **Calibration degrades with RLHF**: Reinforcement Learning from Human Feedback pushes models toward confident-sounding responses because humans prefer them. This systematically destroys whatever calibration existed in the base model.

5. **Distribution shift blindness**: Models cannot reliably detect when a query is outside their training distribution. They will confidently answer questions about events after their training cutoff with fabricated information.

6. **Inconsistency under rephrasing**: The same question asked differently can produce wildly different self-reported confidence levels, proving these are surface-level linguistic patterns, not genuine uncertainty estimates.

### What Works Instead: Composite Confidence Scores

Rather than asking the model how confident it is, we **measure confidence externally** using multiple independent signals that correlate with answer correctness.

---

## Composite Confidence Score Design

### Philosophy

A composite confidence score aggregates multiple **independently measurable signals** into a single score that is then **calibrated against ground truth outcomes**. The key insight is:

> No single signal is reliable alone, but the combination of many weak signals produces a strong predictor of answer quality.

### Architecture

```
Query → [Signal Extractors] → [Normalization] → [Weighted Aggregation] → [Calibration] → Final Score
                                                                                              ↓
                                                                              [Action Decision Matrix]
```

### Design Principles

1. **Independence**: Signals should measure different aspects of confidence. Correlated signals add less information.
2. **Measurability**: Every signal must be computable without human judgment at inference time.
3. **Calibratability**: The composite score must be calibratable against binary outcomes (correct/incorrect).
4. **Decomposability**: When confidence is low, you should be able to identify WHICH signals are driving it down.
5. **Domain adaptability**: Weights and thresholds should be tunable per domain/use-case.

---

## Individual Signals

### 1. Retrieval Score

**What it measures**: How well the retrieved documents match the query.

**How to compute**:
- Cosine similarity between query embedding and top-k document embeddings
- Average, max, or weighted combination of top-k scores
- Score distribution statistics (mean, variance, gap between top-1 and top-2)

**Why it matters**: If the retrieval system couldn't find relevant documents, the answer is likely unsupported or hallucinated.

**Signal characteristics**:
- Range: [0, 1] (cosine similarity)
- High signal: Top documents are highly relevant (>0.85 cosine)
- Low signal: No documents above 0.5 similarity → likely out-of-domain query
- Key metric: Gap between top-1 and average — large gap means one clear match; small gap means ambiguous retrieval

**Failure modes**:
- Embedding space collapse (everything looks similar)
- Adversarial queries that are semantically close but factually different
- Stale embeddings that don't reflect document updates

### 2. Reranker Score

**What it measures**: Cross-encoder relevance judgment between query and retrieved passages.

**How to compute**:
- Pass (query, passage) pairs through a cross-encoder model (e.g., ms-marco-MiniLM)
- Score is typically logit output, sigmoid-transformed to [0,1]
- Take max or top-k average of reranker scores

**Why it matters**: Cross-encoders are more accurate than bi-encoders for relevance judgment. A high reranker score means the retrieved context is genuinely relevant to the query.

**Signal characteristics**:
- Range: [0, 1] (after sigmoid)
- More discriminative than retrieval score alone
- Computationally expensive but highly informative
- Can detect semantic mismatches that embedding similarity misses

### 3. Source Freshness

**What it measures**: How recent the source documents are relative to the query's temporal requirements.

**How to compute**:
- Extract document timestamps (publication date, last modified, crawl date)
- Determine if the query is time-sensitive (e.g., "current", "latest", "2024")
- Compute freshness decay: `freshness = exp(-λ * days_since_update)`
- For non-time-sensitive queries, freshness weight is reduced

**Why it matters**: Answering "What is the current interest rate?" from a 2-year-old document is dangerous. Freshness directly correlates with answer correctness for temporal queries.

**Signal characteristics**:
- Range: [0, 1] (exponential decay)
- λ is domain-specific (news: high decay, scientific papers: low decay)
- Binary boost for queries explicitly requesting recent information
- Should be combined with a temporal query classifier

### 4. Source Authority

**What it measures**: Trustworthiness and credibility of the source documents.

**How to compute**:
- Domain authority score (pre-computed per source)
- Source type hierarchy: official docs > peer-reviewed > blogs > forums > unknown
- Author credentials (when available)
- Citation count / PageRank-style authority
- Known misinformation source blacklist

**Why it matters**: An answer sourced from official documentation is more likely correct than one from a random blog post.

**Signal characteristics**:
- Range: [0, 1] (normalized authority tier)
- Requires a maintained source registry
- Domain-specific: medical queries should weight peer-reviewed journals higher
- Can be pre-computed and cached per source

### 5. Context Coverage

**What it measures**: What fraction of the query's information needs are addressed by the retrieved context.

**How to compute**:
- Decompose query into sub-questions or information needs
- Check which sub-questions are answerable from the retrieved context
- Coverage = answered_needs / total_needs
- Can use NLI (Natural Language Inference) to check entailment

**Why it matters**: If a query asks about A, B, and C, but the context only covers A, the model will likely hallucinate answers for B and C.

**Signal characteristics**:
- Range: [0, 1] (fraction of needs covered)
- Requires query decomposition (can be LLM-assisted)
- Partial coverage should reduce confidence proportionally
- Key signal for complex, multi-part queries

### 6. Groundedness Score

**What it measures**: Whether the generated answer is actually supported by the provided context (not hallucinated).

**How to compute**:
- NLI-based: Run (context, answer_claim) through an NLI model; score = P(entailment)
- Decompose answer into atomic claims, check each against context
- Aggregate: min, mean, or weighted average of claim-level scores
- Can use specialized models (e.g., TRUE, AlignScore, MiniCheck)

**Why it matters**: This is the most direct signal for hallucination detection. Even with good retrieval, the model may generate information not present in the context.

**Signal characteristics**:
- Range: [0, 1] (entailment probability)
- Most critical signal for factual accuracy
- Computationally expensive (requires NLI inference per claim)
- Can be approximated with lighter models for real-time use
- Should decompose answer into claims for fine-grained scoring

### 7. Citation Support

**What it measures**: Whether specific claims in the answer can be traced back to specific source passages.

**How to compute**:
- If answer contains inline citations: verify each citation supports its claim
- If no citations: attempt to attribute each sentence to a source passage
- Citation precision: fraction of citations that are valid
- Citation recall: fraction of claims that have valid citations

**Why it matters**: Verifiable claims are more trustworthy. If the system can point to exactly where information came from, it's less likely to be hallucinated.

**Signal characteristics**:
- Range: [0, 1] (F1 of citation precision and recall)
- Requires citation extraction and verification
- Strongly correlated with groundedness but not identical
- Provides explainability in addition to confidence

### 8. Answer Consistency

**What it measures**: Whether the model produces the same answer when asked the same question multiple times or in different ways.

**How to compute**:
- Generate N answers with temperature > 0
- Measure semantic similarity between answers (embedding cosine or NLI)
- Consistency = average pairwise similarity
- Alternative: measure entropy of sampled answers

**Why it matters**: If the model gives different answers each time, it's uncertain. Consistent answers (even with stochastic sampling) suggest the model has strong evidence for that answer.

**Signal characteristics**:
- Range: [0, 1] (average pairwise agreement)
- Requires multiple inference passes (expensive)
- Can be approximated with 3-5 samples
- High consistency ≠ correctness (model can be consistently wrong)
- Most useful when combined with other signals

### 9. Tool Success Signal

**What it measures**: Whether tool/API calls executed successfully and returned valid results.

**How to compute**:
- Binary: did the tool call succeed? (HTTP 200, valid response schema)
- Quality: is the tool response non-empty, well-formed, and relevant?
- Chain: in multi-tool workflows, what fraction of steps succeeded?
- Timeout/retry count as negative signal

**Why it matters**: If the model tried to call an API and it failed, the answer based on that failed call is unreliable.

**Signal characteristics**:
- Range: [0, 1] (success fraction for multi-tool; binary for single tool)
- Easy to compute (just check tool execution status)
- Critical for agentic workflows
- Should distinguish between tool failure (network error) and tool returning "no results"

### 10. Risk Classifier Signal

**What it measures**: Whether the query/answer falls into a high-risk category requiring elevated confidence.

**How to compute**:
- Classify query into risk categories (medical, financial, legal, safety)
- Risk level determination: critical, high, medium, low
- This doesn't increase confidence — it raises the threshold required
- Acts as a multiplier on the required confidence for action

**Why it matters**: "Take 500mg of ibuprofen" requires much higher confidence than "The Eiffel Tower is in Paris." Risk classification determines how confident we need to be before acting.

**Signal characteristics**:
- Range: categorical (risk levels mapped to threshold multipliers)
- Pre-computed classifier on query text
- Domain-specific risk taxonomies
- Affects the ACTION taken at a given confidence level, not the score itself

### 11. Historical Performance

**What it measures**: How well the system has performed on similar queries in the past.

**How to compute**:
- Cluster queries by type/topic/complexity
- Track accuracy per cluster over time
- For new query: find nearest cluster, use historical accuracy as prior
- Bayesian update: combine current signals with historical prior

**Why it matters**: If the system historically struggles with a particular type of question, current confidence should be discounted even if individual signals look good.

**Signal characteristics**:
- Range: [0, 1] (historical accuracy for similar queries)
- Requires production feedback loop (user ratings, corrections)
- Cold start problem for new query types
- Smoothed over time window to handle distribution shift

---

## Confidence-Driven Behavior Matrix

The final calibrated confidence score maps to system behavior:

| Confidence Level | Score Range | System Behavior |
|---|---|---|
| **High** | ≥ 0.85 | Answer directly with full confidence |
| **Medium** | 0.60 - 0.85 | Answer with caveats ("Based on available information...", "Note that...") |
| **Low** | 0.35 - 0.60 | Ask for clarification, present multiple options, indicate uncertainty |
| **Very Low** | < 0.35 | Abstain from answering, redirect to human, state inability |
| **High Risk + Not High Confidence** | Risk=high, Score<0.85 | Route to human review before responding |

### Behavior Details

**High Confidence (≥ 0.85)**:
- Direct answer without hedging
- Include citations for verifiability
- Log for calibration monitoring

**Medium Confidence (0.60 - 0.85)**:
- Answer with epistemic markers: "Based on the available documents...", "It appears that..."
- Highlight which parts are well-supported vs. inferred
- Offer to search for more information
- Present confidence-driving factors to user

**Low Confidence (0.35 - 0.60)**:
- Ask clarifying questions to narrow the query
- Present top-2/3 possible answers with reasoning
- Explicitly state: "I'm not confident in this answer"
- Suggest alternative information sources

**Very Low Confidence (< 0.35)**:
- Do NOT attempt to answer
- State clearly: "I don't have enough information to answer this reliably"
- Suggest what information would be needed
- Route to human expert if available

**High Risk + Insufficient Confidence**:
- Never auto-respond for medical/financial/legal/safety queries below threshold
- Queue for human expert review
- Provide the system's best guess as a DRAFT for the human reviewer
- Log as a safety event

### Threshold Customization by Domain

```
Medical:     high=0.95, medium=0.80, low=0.60, abstain=0.40
Financial:   high=0.90, medium=0.75, low=0.50, abstain=0.30
Legal:       high=0.92, medium=0.78, low=0.55, abstain=0.35
General:     high=0.85, medium=0.60, low=0.35, abstain=0.20
Creative:    high=0.70, medium=0.50, low=0.30, abstain=0.15
```

---

## Calibration Techniques

### Why Calibration Matters

A confidence score of 0.8 should mean "80% of the time I say 0.8, I'm correct." Without calibration, raw composite scores have no probabilistic interpretation.

### Platt Scaling

**What**: Fit a logistic regression on the raw scores to produce calibrated probabilities.

**How**:
```
P(correct | score) = 1 / (1 + exp(-(a * score + b)))
```

- Collect labeled data: (raw_score, was_correct) pairs
- Fit parameters a, b via maximum likelihood
- Apply sigmoid transformation at inference time

**Pros**: Simple, fast, well-understood, works well when score distribution is approximately Gaussian
**Cons**: Assumes monotonic sigmoid relationship, may underfit complex distributions

### Isotonic Regression

**What**: Non-parametric calibration that fits a monotonically increasing step function.

**How**:
- Sort predictions by raw score
- Fit a piecewise-constant monotone function that minimizes squared error
- Uses Pool Adjacent Violators (PAV) algorithm

**Pros**: No distributional assumptions, can capture any monotone relationship
**Cons**: Requires more data (prone to overfitting with < 1000 samples), step-function output

### Temperature Scaling

**What**: For LLM logits specifically — divide logits by a learned temperature T before softmax.

**How**:
```
calibrated_prob = softmax(logits / T)
```

- T > 1: softens probabilities (reduces overconfidence)
- T < 1: sharpens probabilities (reduces underconfidence)
- Fit T on validation set to minimize negative log-likelihood

**Pros**: Single parameter, preserves ranking, fast to compute
**Cons**: Only applicable to raw model logits, global correction (same T for all inputs)

### Ensemble Calibration

Combine multiple calibration methods:
1. Apply temperature scaling to LLM logits
2. Compute composite score from all signals
3. Apply isotonic regression to composite score
4. Final calibrated probability

---

## Calibration Metrics

### Brier Score

```
BS = (1/N) * Σ(predicted_probability - actual_outcome)²
```

- Range: [0, 1], lower is better
- Decomposes into: calibration + resolution + uncertainty
- Proper scoring rule (incentivizes honest probability reporting)

### Expected Calibration Error (ECE)

```
ECE = Σ (|B_m| / N) * |accuracy(B_m) - confidence(B_m)|
```

- Bin predictions by confidence level
- For each bin: measure gap between average confidence and actual accuracy
- Weighted average of gaps

### Maximum Calibration Error (MCE)

```
MCE = max_m |accuracy(B_m) - confidence(B_m)|
```

- Worst-case calibration error across all bins
- Important for safety-critical applications

### Reliability Diagrams

- X-axis: predicted probability (binned)
- Y-axis: observed frequency of positive outcomes
- Perfect calibration = diagonal line
- Above diagonal = underconfident, below = overconfident
- Include histogram of prediction counts per bin

---

## Threshold Tuning

### Precision-Recall Tradeoff

- **Precision**: Of all queries we answered, what fraction were correct?
- **Recall**: Of all answerable queries, what fraction did we answer?
- Raising the confidence threshold increases precision but decreases recall (more abstentions)

### ROC-AUC

- Plot True Positive Rate vs False Positive Rate at varying thresholds
- AUC measures ranking quality independent of threshold choice
- Useful for comparing confidence scoring systems

### Cost-Sensitive Optimization

Different errors have different costs:
```
Cost = C_FP * FalsePositives + C_FN * FalseNegatives + C_abstain * Abstentions
```

Optimize threshold to minimize total cost:
- Medical: C_FP >> C_FN (wrong answer is very expensive)
- Customer service: C_FN > C_FP (not answering is costly)

### F-beta Score

```
F_β = (1 + β²) * (precision * recall) / (β² * precision + recall)
```

- β > 1: weight recall higher (prefer answering)
- β < 1: weight precision higher (prefer accuracy)
- Choose β based on domain requirements

---

## Domain-Specific Confidence

### Medical Domain
- Require multi-source corroboration for drug interactions
- Weight peer-reviewed sources 3x over general web
- Temporal freshness critical for treatment guidelines
- Mandatory human review for dosage recommendations
- Never auto-respond to emergency symptoms

### Financial Domain
- Real-time data freshness is critical (minutes, not days)
- Regulatory compliance requires audit trail of confidence decisions
- Different thresholds for informational vs. transactional advice
- Market condition volatility affects confidence decay rate

### Legal Domain
- Jurisdiction-specific confidence (law varies by location)
- Case law recency matters (overturned decisions)
- Statutory interpretation requires high authority sources
- Disclaimer requirements regardless of confidence level

---

## Confidence Aggregation for Multi-Step Agents

When an agent executes multiple steps, confidence propagates:

### Serial Steps
```
confidence_chain = Π(confidence_step_i)  # multiplicative (conservative)
# or
confidence_chain = min(confidence_step_i)  # bottleneck (most conservative)
# or
confidence_chain = weighted_mean(confidence_step_i)  # balanced
```

### Parallel Steps (independent)
```
confidence_parallel = mean(confidence_step_i)  # if independent
```

### Recommended: Bottleneck with Decay
```
confidence_final = min(confidence_steps) * decay_factor^(num_steps - 1)
```

The more steps in a chain, the more opportunities for error accumulation. Each additional step should slightly decrease overall confidence.

---

## Confidence Decay Over Time

Cached answers lose confidence over time:

```
confidence_t = confidence_0 * exp(-λ * (t - t_0))
```

Where:
- λ depends on domain volatility (news: high λ, math: λ≈0)
- t_0 is when the answer was generated
- Trigger re-computation when confidence drops below threshold

### Domain Decay Rates
- Breaking news: half-life = 1 hour
- Stock prices: half-life = 5 minutes
- Scientific facts: half-life = 6 months
- Mathematical truths: half-life = ∞ (no decay)
- Software documentation: half-life = 3 months

---

## Production Monitoring of Confidence Distribution

### Key Metrics to Track

1. **Confidence distribution histogram**: Should be bimodal (mostly high or low, not clustered at medium)
2. **Abstention rate**: Fraction of queries where system refuses to answer
3. **Calibration drift**: ECE computed on rolling windows
4. **Confidence-accuracy correlation**: Should remain high over time
5. **Signal contribution analysis**: Which signals are most predictive over time

### Alerts

- Calibration drift > 0.05 ECE: trigger recalibration
- Abstention rate spike > 2σ: potential distribution shift
- Confidence distribution collapse (all scores in narrow band): scoring system failure
- Accuracy drop at previously-reliable confidence levels: model degradation

### Dashboard Requirements

- Real-time confidence distribution (histogram, updated every 5 min)
- Rolling calibration curve (reliability diagram, 24h window)
- Per-signal health (are individual signals still discriminative?)
- Threshold performance (precision/recall at current thresholds)
- Comparison across model versions / A/B test variants
