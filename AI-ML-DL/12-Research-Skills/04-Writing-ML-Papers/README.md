# Writing ML Papers

## Overview

Whether you're publishing externally or writing internal technical reports, the ability to
communicate ML research clearly is a critical skill. This guide covers structure, writing
style, figures, experiments, and the review process.

---

## Structure of a Good ML Paper

### Standard Structure (8-10 pages for conferences)

```
1. Title                          - Clear, specific, memorable
2. Abstract          (~150 words) - Self-contained summary
3. Introduction      (1-1.5 pages) - Problem, motivation, contribution
4. Related Work      (1-1.5 pages) - Context and differentiation
5. Method            (2-3 pages)  - Your approach in detail
6. Experiments       (2-3 pages)  - Evaluation and analysis
7. Conclusion        (0.5 pages)  - Summary and future work
8. References        (1 page)     - Comprehensive citations
   Appendix          (unlimited)  - Implementation details, proofs, extra results
```

### Title

```
GOOD: "Attention Is All You Need"          - Memorable, makes a clear claim
GOOD: "BERT: Pre-Training of Deep Bidirectional Transformers"  - Acronym + description
BAD:  "A Novel Deep Learning Approach for..."  - Vague, could be anything
BAD:  "On the Effectiveness of..."             - Boring, no information
```

### Abstract Formula

1. **Problem** (1-2 sentences): What problem exists?
2. **Gap** (1 sentence): Why don't current approaches work?
3. **Approach** (1-2 sentences): What do you propose?
4. **Results** (1-2 sentences): Key numbers proving it works.
5. **Impact** (1 sentence): Why does this matter?

### Introduction Formula

1. **Hook**: Why is this problem important? (1 paragraph)
2. **Background**: Minimal context needed (1 paragraph)
3. **Problem**: What specific challenge remains? (1 paragraph)
4. **Insight**: Your key idea, in plain English (1 paragraph)
5. **Contributions**: Bulleted list of what this paper provides
6. **Outline**: "The rest of this paper is organized as..." (optional)

---

## Writing Clear Mathematical Notation

### Conventions

```
Scalars:        lowercase italic          x, y, α, λ
Vectors:        lowercase bold            x, w, θ
Matrices:       uppercase bold            W, X, A
Sets:           calligraphic              𝒟, 𝒳, 𝒴
Functions:      named                     f(x), L(θ), σ(z)
Distributions:  calligraphic or named     p(x), 𝒩(μ, σ²)
Expectations:   𝔼                         𝔼[f(x)]
Loss:           ℒ or L                    ℒ(θ; x, y)
```

### Best Practices

1. **Define before use**: Every symbol should be introduced before it appears in equations
2. **Consistent notation**: Don't use `x` for input in one section and `z` in another
3. **Minimize notation**: Fewer symbols = easier to read
4. **Use standard conventions**: Don't redefine well-known symbols
5. **Number important equations**: Reference them in text

### Example of Good vs Bad

```
BAD:
"We compute f(x) = σ(Wx + b) where σ is the activation"

GOOD:
"Given input x ∈ ℝᵈ, we compute the hidden representation 
h = σ(Wx + b), where W ∈ ℝʰˣᵈ is the weight matrix, 
b ∈ ℝʰ is the bias vector, and σ(·) denotes the ReLU activation."
```

---

## Creating Effective Figures and Tables

### Figures

**Architecture diagrams**:
- Use consistent shapes (rectangles for layers, arrows for data flow)
- Label dimensions
- Use color sparingly and meaningfully
- Include a legend

**Results plots**:
- Always include axis labels with units
- Use error bars/shading for confidence intervals
- Make sure it's readable in black and white
- Use distinct line styles, not just colors
- Font size should be readable when printed

**Comparison figures**:
- Show qualitative examples (good AND failure cases)
- Use the same examples across methods for fair comparison

### Tables

```
GOOD table practices:
- Bold the best result in each column
- Include ± standard deviation
- Separate your method visually (horizontal line or shading)
- Include the metric in the column header with direction (↑ or ↓)
- Cite baselines properly
```

Example:

| Method | Accuracy (↑) | F1 (↑) | Latency (↓) |
|--------|:---:|:---:|:---:|
| Baseline A [1] | 84.2 ± 0.3 | 81.1 ± 0.4 | 12ms |
| Baseline B [2] | 86.1 ± 0.2 | 83.4 ± 0.3 | 45ms |
| **Ours** | **88.3 ± 0.2** | **85.7 ± 0.3** | **15ms** |

---

## Experimental Methodology

### Designing Fair Experiments

1. **Same compute budget**: Don't compare a model trained for 100 epochs against one trained for 10
2. **Same hyperparameter tuning effort**: Tune baselines too
3. **Same data**: Exact same splits, preprocessing
4. **Strong baselines**: Include the best known methods
5. **Standard benchmarks**: Use established datasets
6. **Multiple runs**: Report mean ± std

### What Experiments to Include

1. **Main results table**: Your method vs baselines on standard benchmarks
2. **Ablation study**: Contribution of each component
3. **Analysis**: Why does it work? Attention visualization, error analysis
4. **Efficiency**: Training cost, inference speed, memory
5. **Sensitivity**: How sensitive to hyperparameters?
6. **Failure cases**: When does it NOT work?

### Ablation Study Design

```
Full model:                    92.3% ± 0.2
 - component A:               91.1% ± 0.3  → A contributes +1.2%
 - component B:               89.5% ± 0.2  → B contributes +2.8%
 - component C:               91.9% ± 0.3  → C contributes +0.4%
 - all (baseline):            85.2% ± 0.4
```

---

## Common Reviewer Complaints (and How to Avoid Them)

| Complaint | Prevention |
|-----------|-----------|
| "Missing baselines" | Include ALL recent strong methods, even if not directly comparable |
| "No error bars" | Always report std over multiple seeds |
| "Unfair comparison" | Same tuning budget, same data, same compute |
| "Incremental contribution" | Clearly articulate what's novel and why it matters |
| "Limited evaluation" | Multiple datasets, multiple metrics |
| "No ablation" | Include one. Always. |
| "Unclear writing" | Get feedback before submission. Read it fresh after a break. |
| "Missing related work" | Thorough literature search. Cite relevant concurrent work. |
| "Overclaimed results" | Be precise. "Improves by 2.1% on X" not "significantly better" |
| "No code/reproducibility" | Promise code release. Include implementation details in appendix. |

### Writing for Reviewers

Remember:
- Reviewers have 10-30 papers to review
- They may spend 30-60 minutes on your paper
- Make their job easy: clear structure, clear contributions, clear evidence
- Front-load the important stuff (assume they read intro + experiments first)

---

## LaTeX Tips for ML Papers

### Essential Packages

```latex
\usepackage{amsmath,amssymb}    % Math
\usepackage{booktabs}           % Professional tables
\usepackage{hyperref}           % Clickable references
\usepackage{algorithm2e}        % Pseudocode
\usepackage{graphicx}           % Figures
\usepackage{subcaption}         % Sub-figures
\usepackage{xcolor}             % Colors (for highlights)
\usepackage{microtype}          % Better typography
```

### Table with Booktabs

```latex
\begin{table}[t]
\centering
\caption{Comparison on benchmark X. Best results in \textbf{bold}.}
\label{tab:main_results}
\begin{tabular}{lcc}
\toprule
Method & Accuracy (\%) & F1 (\%) \\
\midrule
Baseline A & 84.2 $\pm$ 0.3 & 81.1 $\pm$ 0.4 \\
Baseline B & 86.1 $\pm$ 0.2 & 83.4 $\pm$ 0.3 \\
\midrule
\textbf{Ours} & \textbf{88.3 $\pm$ 0.2} & \textbf{85.7 $\pm$ 0.3} \\
\bottomrule
\end{tabular}
\end{table}
```

### Algorithm Pseudocode

```latex
\begin{algorithm}[t]
\caption{Our Training Procedure}
\label{alg:training}
\KwIn{Dataset $\mathcal{D}$, learning rate $\eta$}
\KwOut{Trained parameters $\theta^*$}
Initialize $\theta$ randomly\;
\For{epoch $= 1$ \KwTo $T$}{
    \For{mini-batch $(x, y) \sim \mathcal{D}$}{
        $\hat{y} \leftarrow f_\theta(x)$\;
        $\mathcal{L} \leftarrow \text{loss}(\hat{y}, y)$\;
        $\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}$\;
    }
}
\Return $\theta$
\end{algorithm}
```

### Useful Macros

```latex
\newcommand{\R}{\mathbb{R}}
\newcommand{\E}{\mathbb{E}}
\newcommand{\bx}{\mathbf{x}}
\newcommand{\bw}{\mathbf{w}}
\DeclareMathOperator*{\argmin}{arg\,min}
\DeclareMathOperator*{\argmax}{arg\,max}
```

---

## Rebuttal Writing Strategies

### Structure

1. **Thank reviewers** (brief, professional)
2. **Address each concern** point by point
3. **Provide evidence** (new experiments if needed)
4. **Acknowledge limitations** honestly
5. **Highlight misunderstandings** politely

### Tone

```
BAD:  "The reviewer is incorrect because..."
GOOD: "We appreciate this concern. To clarify, our method handles this case 
       because... We have added additional experiments to demonstrate this 
       (see Table R1 below)."

BAD:  "This is already in the paper."
GOOD: "Thank you for raising this point. We discuss this in Section 3.2, 
       paragraph 2. We will make this more prominent in the revision."
```

### Tips

- Rebuttals that include new experimental results are significantly more successful
- Be concise - reviewers have limited time for rebuttals too
- Prioritize major concerns over minor ones
- If a reviewer misunderstood something, it's YOUR writing that needs fixing
- Promise specific revisions (and follow through)

---

## Internal Technical Reports

Not publishing externally? The same principles apply to internal docs:

1. **Clear problem statement**: Why are we doing this?
2. **Method description**: What did we build?
3. **Results**: Does it work? How well?
4. **Ablations**: What matters?
5. **Recommendations**: What should we do next?
6. **Reproducibility**: Can someone else run this?

The main difference: you can be more direct, skip some formality, and focus
on business impact alongside technical merit.

---

## Summary

Good ML writing is:
- **Clear**: A busy reader gets the key points quickly
- **Honest**: Reports limitations and failure cases
- **Complete**: Enough detail to reproduce
- **Rigorous**: Statistical evidence, not anecdotes
- **Structured**: Follows conventions readers expect
