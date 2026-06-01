# How to Read ML Papers

## Why This Skill Matters

The ML field produces thousands of papers annually. Reading every paper cover-to-cover is impossible.
You need a systematic approach to efficiently extract value, identify what's genuinely novel, and
determine what's applicable to your work.

---

## The 3-Pass Method

### Pass 1: Survey (5-10 minutes)

**Goal**: Decide if the paper deserves more time.

1. Read the **title**, **abstract**, and **keywords**
2. Read **section headings** only
3. Read the **conclusion**
4. Glance at **figures and tables** (especially results tables)
5. Check the **references** - do you recognize key related work?

**After Pass 1, you should know**:
- Category (new method, empirical study, survey, theoretical)
- Context (what problem, what field)
- Claimed contributions
- Whether it's relevant to you

**Decision**: Stop here (80% of papers), or continue to Pass 2.

### Pass 2: Comprehension (30-60 minutes)

**Goal**: Understand the paper's claims and evidence without diving into proofs.

1. Read the **introduction** carefully - understand the problem framing
2. Read **related work** - understand positioning
3. Read the **method section** - understand the approach at a high level
4. Study **figures and tables** in detail
5. Read **experiments** - understand evaluation setup and results
6. Note things you don't understand (but don't get stuck)

**After Pass 2, you should be able to**:
- Summarize the paper to someone in 2-3 sentences
- Identify the key novelty
- Understand the experimental setup
- Know the main results and whether they're convincing

**Decision**: Stop here (sufficient for most purposes), or continue to Pass 3.

### Pass 3: Mastery (4-8 hours)

**Goal**: Deeply understand the paper, potentially reproduce it.

1. Re-read **every section** in detail
2. Work through **mathematical derivations**
3. Understand every **design choice** and why alternatives weren't used
4. Identify **implicit assumptions**
5. Think about how you would **implement** this
6. Consider what **experiments are missing**

**After Pass 3, you should be able to**:
- Reproduce the work from scratch
- Identify strengths and weaknesses
- Propose extensions or improvements
- Explain it to a colleague in detail

---

## Understanding Paper Structure

### Abstract (~150-300 words)
- Problem statement
- Proposed approach (1-2 sentences)
- Key results (numbers!)
- Impact/significance claim

### Introduction (1-2 pages)
- Problem motivation (why should we care?)
- Limitations of existing approaches
- Key insight of this work
- Summary of contributions (usually a bulleted list)
- Paper outline

### Related Work (1-2 pages)
- How does this fit into the broader literature?
- What's different from prior approaches?
- Watch for: selective citation, unfair characterization of competitors

### Method / Approach (2-5 pages)
- Problem formulation (mathematical notation)
- Proposed solution
- Architecture details
- Training procedure
- Theoretical analysis (if any)

### Experiments (2-4 pages)
- Datasets used
- Baselines compared against
- Evaluation metrics
- Main results (tables)
- Ablation studies
- Analysis/visualization

### Conclusion (0.5-1 page)
- Summary of contributions
- Limitations (if honest)
- Future work

### Appendix
- Implementation details crucial for reproduction
- Additional results
- Proofs

---

## Critical Reading: Identifying Problems

### Red Flags in Claims

| Red Flag | What It Might Mean |
|----------|-------------------|
| "SOTA on all benchmarks" | Cherry-picked benchmarks or unfair baselines |
| No error bars / single run | Results may not be reproducible |
| Comparison against weak baselines | Missing obvious strong baselines |
| Hyperparameter tuning on test set | Overly optimistic results |
| "Our method is simple yet effective" | May be underspecifying complexity |
| Vague dataset description | Hard to reproduce, possible data leakage |

### Questions to Ask

1. **Assumptions**: What assumptions does the method make? Are they realistic?
2. **Baselines**: Are comparisons fair? Same compute budget? Same tuning effort?
3. **Metrics**: Are the metrics appropriate for the task? Is anything missing?
4. **Scale**: Will this work at 10x or 100x the scale tested?
5. **Generalization**: How narrow is the evaluation? Would this work on other domains?
6. **Compute**: What's the actual compute cost? Is this practical?
7. **Ablations**: Does each component actually contribute?

### Common Unfair Comparisons

```
Problem: "We compare our 2024 model against XYZ (2019)"
Issue:   - XYZ may have been improved since original paper
         - XYZ may have used less compute/data
         - Hyperparameters may not be tuned fairly for XYZ

Problem: "We achieve 85.2% vs their reported 84.1%"  
Issue:   - Is the difference within statistical noise?
         - Were the same splits used?
         - Was there hyperparameter search on the test set?
```

---

## Reproducing Results

### Why Reproduce?

- Deepens understanding far beyond reading
- Reveals details the paper omits
- Builds implementation skills
- Helps evaluate if the approach works for your use case

### Reproduction Checklist

```markdown
□ Find official code (check paper, GitHub links, author pages)
□ Check if community reimplementations exist
□ Identify exact dataset versions used
□ Note all hyperparameters (check appendix!)
□ Verify hardware requirements
□ Set random seeds
□ Compare against reported numbers (±2% is typically acceptable)
□ If numbers don't match, check errata or contact authors
```

### Levels of Reproduction

1. **Run official code** - Verify claims with their code
2. **Reimplement key parts** - Understand the method deeply
3. **Full reimplementation** - Maximum understanding
4. **Extend** - Apply to new data/tasks

---

## Keeping Up with Literature

### Sources

| Source | Frequency | Best For |
|--------|-----------|----------|
| arXiv (arxiv.org) | Daily | Latest preprints |
| Papers With Code | Weekly | SOTA tracking, code availability |
| Semantic Scholar | On-demand | Citation graphs, related papers |
| Conference proceedings | Annual | Peer-reviewed, high quality |
| Twitter/X ML community | Daily | Discussion, hot takes |
| ML newsletters (TLDR, Import AI) | Weekly | Curated summaries |
| Podcast (Gradient Dissent, TWIML) | Weekly | Author interviews |

### Recommended Workflow

```
Monday:    Check arXiv cs.LG, cs.CL, cs.CV "new" listings
           Read 5-10 abstracts, save 2-3 for Pass 1
Tuesday:   Pass 1 on saved papers (5 min each)
Wednesday: Pass 2 on 1 paper that passed Pass 1
Thursday:  Reading group discussion
Friday:    Write up notes, update reading log
```

---

## Key Conferences

### Tier 1 (Must-follow for ML practitioners)

| Conference | Focus | When | Acceptance Rate |
|-----------|-------|------|-----------------|
| **NeurIPS** | General ML | December | ~25% |
| **ICML** | General ML | July | ~25% |
| **ICLR** | Representation Learning | May | ~30% |

### Tier 1 (Domain-specific)

| Conference | Focus | When | Acceptance Rate |
|-----------|-------|------|-----------------|
| **CVPR** | Computer Vision | June | ~25% |
| **ACL** | NLP | July | ~25% |
| **EMNLP** | NLP (Empirical) | November | ~25% |
| **KDD** | Data Mining/Applied ML | August | ~20% |
| **AAAI** | General AI | February | ~20% |

### Industry Conferences

- **MLSys** - ML systems and infrastructure
- **RecSys** - Recommendation systems
- **SIGIR** - Information retrieval
- **WWW** - Web applications

### Workshop Papers

- Lower acceptance bar but often more novel/speculative
- Good for early-stage ideas
- Shorter (4 pages vs 8-10 for main conference)

---

## Paper Annotation Workflow

### Tools

1. **Zotero** - Free, open-source reference manager
2. **Paperpile** - Google Docs integration
3. **Mendeley** - Elsevier's tool (good PDF annotation)
4. **Notion/Obsidian** - For structured notes
5. **Connected Papers** - Visual exploration of related work

### Annotation System

Use consistent highlighting colors:

| Color | Meaning |
|-------|---------|
| Yellow | Key contribution/insight |
| Green | Method details I need to remember |
| Red | Claim I'm skeptical about |
| Blue | Experimental detail for reproduction |
| Purple | Connection to my work |

### Digital Note Structure

```markdown
## Paper: [Title]
**Authors**: ...
**Venue**: ... (Year)
**Link**: ...

### One-sentence summary
...

### Problem
What problem does this solve? Why does it matter?

### Method
How do they solve it? (diagram if helpful)

### Key Results
- Metric 1: XX.X% (vs baseline YY.Y%)
- ...

### Strengths
- ...

### Weaknesses
- ...

### Questions/Concerns
- ...

### Relevance to My Work
- ...

### Follow-up Papers
- ...
```

---

## Building a Reading Group

### Format Options

1. **Presenter model**: One person presents, others discuss
2. **Everyone reads**: All read the paper, structured discussion
3. **Lightning rounds**: 5-minute summaries of many papers
4. **Reproduction club**: Group implements papers together

### Running an Effective Reading Group

```
Frequency:     Weekly or biweekly
Duration:      45-60 minutes
Size:          4-8 people (sweet spot)
Paper selection: Rotating responsibility
Preparation:   Everyone does at least Pass 1

Agenda:
- 5 min: Paper context and why we picked it
- 15 min: Presenter walks through method
- 10 min: Key results and ablations
- 15 min: Discussion (strengths, weaknesses, applications)
- 5 min: Action items (implement? cite? extend?)
```

### Discussion Questions Template

1. What is the key insight that makes this work?
2. What are the strongest and weakest experiments?
3. How would we apply this to our systems?
4. What would break if we tried this at our scale?
5. What's the simplest baseline that might achieve 80% of these results?

---

## Worked Example: Reading "Attention Is All You Need"

### Pass 1 (5 minutes)

**Title**: "Attention Is All You Need" - bold claim, suggests removing something (RNNs/CNNs)

**Abstract**: Proposes Transformer - new architecture using only attention mechanisms.
Achieves 28.4 BLEU on English-to-German translation. Trains faster than prior work.

**Headings**: Introduction, Background, Model Architecture, Why Self-Attention,
Training, Results, Conclusion

**Conclusion**: Transformer is first sequence model based entirely on attention.
Faster to train than recurrent/convolutional models.

**Figures**: Architecture diagram (Fig 1) - encoder-decoder with multi-head attention.

**Decision**: Extremely relevant. Proceed to Pass 2.

### Pass 2 (45 minutes)

**Problem**: Sequential computation in RNNs prevents parallelization. Attention was
used as supplement to RNNs but not as standalone mechanism.

**Method**:
- Encoder-decoder architecture
- Multi-head self-attention (allows attending to different positions)
- Positional encoding (sinusoidal) since no recurrence
- Key innovation: Q, K, V projections with scaled dot-product attention

**Results**:
- WMT 2014 En-De: 28.4 BLEU (new SOTA, +2 BLEU over best ensemble)
- WMT 2014 En-Fr: 41.0 BLEU (new SOTA)
- Training cost: significantly less than competing models
- English constituency parsing: generalizes to other tasks

**Key Insight**: Self-attention can replace recurrence entirely, enabling
massive parallelization while capturing long-range dependencies better.

### Pass 3 Questions

- Why scaled dot-product (divide by √d_k)? Prevents softmax saturation.
- Why multi-head? Different heads learn different relationship types.
- How does positional encoding preserve order? Sinusoidal allows extrapolation.
- What are the limitations? O(n²) attention for sequence length n.

---

## Templates

### Quick Paper Assessment (Pass 1)

```markdown
# Quick Assessment: [Paper Title]

**Date read**: YYYY-MM-DD
**Time spent**: 5 min
**Source**: [Conference/arXiv]

## Category
[ ] New method  [ ] Empirical study  [ ] Survey  [ ] Theory  [ ] System

## Claimed Contribution (from abstract)
1. ...
2. ...

## Relevance to My Work: [High/Medium/Low/None]

## Decision: [ ] Deep read  [ ] Skim later  [ ] Skip

## Why:
...
```

### Deep Paper Notes (Pass 2-3)

```markdown
# Deep Notes: [Paper Title]

**Authors**: ...
**Venue/Year**: ...
**arXiv**: ...
**Code**: ...
**Date read**: YYYY-MM-DD

## TL;DR (1 sentence)
...

## Problem Statement
- What gap does this fill?
- Why now?

## Method Summary
- Key idea in plain English:
- Architecture/Algorithm (diagram):
- Mathematical formulation:
- Training details:

## Experiments
| Dataset | Their Result | Previous SOTA | Improvement |
|---------|-------------|---------------|-------------|
| ... | ... | ... | ... |

## Ablation Study Summary
| Component Removed | Effect |
|-------------------|--------|
| ... | ... |

## Critical Assessment

### Strengths
1. ...

### Weaknesses  
1. ...

### Missing Experiments
1. ...

### Assumptions That May Not Hold
1. ...

## Implementation Notes
- Estimated effort to reproduce: [hours/days/weeks]
- Key hyperparameters: ...
- Compute requirements: ...
- Dataset availability: ...

## Connections
- Builds on: [papers]
- Extended by: [papers]
- Related to my work because: ...

## Action Items
- [ ] ...
```

### Weekly Reading Log

```markdown
# Week of YYYY-MM-DD

## Papers Surveyed (Pass 1)
1. [Title] - [1 sentence] - Decision: [read/skip]
2. ...

## Papers Read (Pass 2)
1. [Title] - [2-3 sentence summary + assessment]

## Papers Studied (Pass 3)
1. [Title] - [Key learnings, implementation notes]

## Key Takeaways This Week
- ...

## To Read Next Week
- ...
```

---

## Summary

Reading ML papers is a skill that improves with practice. The 3-pass method lets you
efficiently triage hundreds of papers while deeply understanding the few that matter.
Combine this with a consistent annotation system and a reading group to maximize
learning and retention.

**Key habits**:
1. Read daily (even just abstracts)
2. Take structured notes
3. Be skeptical of claims without strong evidence
4. Attempt reproduction of important papers
5. Connect papers to each other and to your work
