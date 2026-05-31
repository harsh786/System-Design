# LLM-as-Judge

## The Core Idea

**Analogy**: Imagine you're a teacher with 10,000 essays to grade. You can't read them all yourself, but you have a highly capable teaching assistant (TA). You give the TA a detailed rubric and spot-check their grading. That TA is your LLM judge.

LLM-as-judge uses one LLM to evaluate the outputs of another LLM (or the same LLM). It's the most scalable approach to AI evaluation when:
- Human evaluation is too expensive or slow
- You need to evaluate thousands of outputs
- You need consistent scoring criteria

## Why LLM-as-Judge Works

Research shows strong LLMs (GPT-4, Claude) agree with human evaluators ~80-85% of the time — comparable to inter-annotator agreement between humans themselves.

| Evaluation Method | Cost per Item | Speed | Scalability | Quality |
|---|---|---|---|---|
| Expert human | $2-10 | Minutes | Low | Gold standard |
| Crowdsource | $0.50-2 | Hours | Medium | Variable |
| LLM-as-judge | $0.01-0.05 | Seconds | High | Good (80-85% human agreement) |
| Heuristic | $0 | Instant | Infinite | Low (surface only) |

## LLM-as-Judge Patterns

### Pattern 1: Single Evaluator (Point-wise)

The simplest: give the judge a response and ask it to score.

```
You are an expert evaluator. Score the following answer on a scale of 1-5.

Question: {question}
Context: {context}
Answer: {answer}

Criteria:
- Faithfulness: Is every claim supported by the context?
- Completeness: Does it address all parts of the question?
- Clarity: Is it well-written and easy to understand?

Score each criterion 1-5 and explain your reasoning.
```

**Best for**: Quick evaluation, single-dimension scoring.

### Pattern 2: Pairwise Comparison

Show the judge two responses and ask which is better:

```
Which response better answers the question? Explain why.

Question: {question}
Response A: {response_a}
Response B: {response_b}

Output: "A is better", "B is better", or "Tie"
With explanation.
```

**Best for**: A/B testing, model comparison, ranking outputs.

### Pattern 3: Reference-Based Grading

Compare against a known-good answer:

```
Compare the candidate answer to the reference answer.

Question: {question}
Reference (correct) answer: {reference}
Candidate answer: {candidate}

Score the candidate 1-5 based on how well it captures
the key information from the reference.
```

**Best for**: When you have ground truth answers (golden datasets).

### Pattern 4: Rubric-Based Evaluation

Provide a detailed rubric with specific criteria:

```
Evaluate using this rubric:

5 - Excellent: All claims supported, complete, clear, properly caveated
4 - Good: Minor omissions, all claims supported, clear
3 - Acceptable: Mostly supported, some gaps, understandable
2 - Poor: Some unsupported claims, significant gaps
1 - Unacceptable: Hallucinations, wrong information, or off-topic

Question: {question}
Context: {context}
Answer: {answer}

Provide: score, evidence for the score, specific issues found.
```

**Best for**: Consistent, reproducible evaluation with clear standards.

## Designing Judge Prompts

### Key Principles

1. **Be specific** — "Is this good?" → "Is every factual claim supported by the provided context?"
2. **Provide rubrics** — Define what each score level means
3. **Ask for reasoning first** — "Explain your analysis, then give a score" (reduces bias)
4. **Include examples** — Show what a 1, 3, and 5 look like
5. **Decompose** — Evaluate one dimension at a time, not everything at once

### Example: Faithfulness Judge

```
You are evaluating whether an AI answer is faithful to the provided context.

TASK: Identify each factual claim in the answer. For each claim, determine
if it is SUPPORTED, PARTIALLY SUPPORTED, or NOT SUPPORTED by the context.

Context:
{context}

Answer to evaluate:
{answer}

Steps:
1. List each factual claim in the answer
2. For each claim, quote the supporting evidence from context (or state "no support")
3. Calculate: faithfulness = supported_claims / total_claims
4. Output the score as a decimal between 0 and 1

Output format:
Claims: [list]
Faithfulness Score: X.XX
```

## Judge Calibration

Your judge is only useful if it's accurate. Calibrate it:

1. **Create a calibration set** — 50-100 examples with human scores
2. **Run your judge** — Get LLM scores for the same examples
3. **Measure agreement** — Cohen's Kappa, Spearman correlation
4. **Identify failure modes** — Where does the judge disagree with humans?
5. **Iterate on prompts** — Improve the judge prompt based on failures

Target: Cohen's Kappa > 0.7 (substantial agreement).

## Biases in LLM Judges

LLM judges have systematic biases you must account for:

### Position Bias
In pairwise comparison, judges prefer the response shown FIRST (or sometimes LAST). **Mitigation**: Run both orderings, average results.

### Verbosity Bias
Judges prefer longer, more detailed responses even when shorter is better. **Mitigation**: Explicitly state "conciseness is valued" in rubric.

### Self-Preference Bias
GPT-4 rates GPT-4 outputs higher than equally good Claude outputs (and vice versa). **Mitigation**: Use a different model family as judge than the one being evaluated.

### Authority Bias
Judges are swayed by confident, authoritative tone even when content is wrong. **Mitigation**: Focus rubric on factual accuracy, not style.

### Format Bias
Well-formatted responses (bullet points, headers) score higher regardless of content. **Mitigation**: Evaluate content separately from presentation.

## When NOT to Use LLM-as-Judge

| Scenario | Why Not | Alternative |
|---|---|---|
| Safety-critical decisions | Liability requires human judgment | Human expert review |
| Legal compliance | Courts require human accountability | Legal team review |
| Highly subjective tasks | LLMs lack cultural/personal context | User ratings |
| Novel domains | Judge may not understand the domain | Domain expert |
| When judge accuracy < 70% | Unreliable evaluations | Human annotation |

## Cost Analysis

Evaluating 1,000 responses:

| Method | Cost | Time | Notes |
|---|---|---|---|
| GPT-4 judge | ~$15-50 | 30 min | Automated, consistent |
| Claude judge | ~$15-40 | 30 min | Automated, consistent |
| GPT-4-mini judge | ~$2-5 | 15 min | Cheaper, slightly less accurate |
| Human annotators | ~$2,000-5,000 | 1-2 weeks | Gold standard but slow |
| Crowdsource | ~$500-1,000 | 2-3 days | Variable quality |

For most teams: use LLM-as-judge for daily evaluation, human review for periodic calibration.

## LLM-as-Judge Pipeline

```mermaid
graph TD
    Input[Eval Dataset<br>Questions + Answers + Context] --> Split[Split by Dimension]

    Split --> F[Faithfulness Judge]
    Split --> R[Relevance Judge]
    Split --> C[Completeness Judge]

    F --> FS[Faithfulness Scores]
    R --> RS[Relevance Scores]
    C --> CS[Completeness Scores]

    FS --> Agg[Aggregate Scores]
    RS --> Agg
    CS --> Agg

    Agg --> Report[Evaluation Report]

    Report --> Cal{Calibrated?}
    Cal -->|Check| Human[Human Spot-Check<br>10% sample]
    Human --> Agreement{Agreement > 80%?}
    Agreement -->|Yes| Trust[Trust Results]
    Agreement -->|No| Fix[Fix Judge Prompts]
    Fix --> F

    style Input fill:#e1f5fe
    style Report fill:#e8f5e9
    style Human fill:#fff3e0
```

## Best Practices Summary

1. **Decompose evaluation** — One judge per dimension, not one judge for everything
2. **Always calibrate** — Verify against human judgments periodically
3. **Mitigate biases** — Randomize order, control for length, use cross-model judges
4. **Ask for reasoning before scores** — Reduces snap judgments
5. **Use rubrics** — Specific criteria produce consistent results
6. **Spot-check regularly** — 10% human review maintains quality
7. **Version your judge prompts** — They're as important as your system prompts

---

*Next: [06-observability-for-ai.md](./06-observability-for-ai.md) — Monitoring AI systems in production*
