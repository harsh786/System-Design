# The Real Path to Senior AI/ML Architect

> This is not a list of topics. This is how you actually get there.

---

## My Philosophy (Read This First)

Most roadmaps are shopping lists. They tell you "learn X, then Y, then Z" and leave you
with 400 open browser tabs and zero real competence. Here's what actually works:

**1. Build things every single week.** Not toy examples. Real, ugly, broken things that
you fix until they work. A model you can't deploy is a model that doesn't exist.

**2. Depth beats breadth until it doesn't.** You don't need to know 15 frameworks.
You need to know ONE deeply (PyTorch) and understand the rest conceptually. The architect
who knows one tool inside-out designs better systems than the one who knows 10 tools
at surface level.

**3. The gap between "knows ML" and "Senior Architect" is 80% engineering and 20% ML.**
Most people over-invest in algorithms and under-invest in systems thinking, production
engineering, and the ability to make tradeoff decisions under uncertainty.

**4. Papers > courses after the basics.** Once you've done the foundational courses,
switch to reading papers. Courses teach you what was cutting-edge 2 years ago. Papers
teach you what's cutting-edge now.

**5. Your GitHub IS your resume.** Every phase below produces a real project that goes
on your GitHub. No project = phase not complete.

---

## The Actual Timeline (Honest Assessment)

```
If you're starting from near-zero:           24-36 months full-time
If you have a CS degree + some Python:        18-24 months full-time  
If you're already an ML engineer:             12-18 months focused work
Part-time alongside a job:                    Add 50-80% more time
```

This is not a sprint. It's closer to getting a second degree while building a portfolio
that proves you didn't just watch videos.

---

## THE MAP

```
                        ┌─────────────────────────────────┐
                        │                                 │
                        │   YOU ARE HERE                  │
                        │                                 │
                        └───────────────┬─────────────────┘
                                        │
                                        ▼
            ╔═══════════════════════════════════════════════════╗
            ║           STAGE 1: FOUNDATIONS                    ║
            ║                                                   ║
            ║   Math is learned BY coding, not before coding.  ║
            ║   Python is learned BY solving, not by syntax.   ║
            ║                                                   ║
            ║   Duration: 3-4 months                           ║
            ║   Output: NumPy-only neural net + math library   ║
            ╚═══════════════════════════╤═══════════════════════╝
                                        │
                                        ▼
            ╔═══════════════════════════════════════════════════╗
            ║           STAGE 2: CORE ML                        ║
            ║                                                   ║
            ║   You don't understand ML until you've shipped   ║
            ║   a model that a business depends on.            ║
            ║                                                   ║
            ║   Duration: 3-4 months                           ║
            ║   Output: Kaggle medals + deployed ML service    ║
            ╚═══════════════════════════╤═══════════════════════╝
                                        │
                                        ▼
            ╔═══════════════════════════════════════════════════╗
            ║           STAGE 3: DEEP LEARNING                 ║
            ║                                                   ║
            ║   From perceptrons to transformers. Build each   ║
            ║   one from scratch ONCE, then use frameworks.    ║
            ║                                                   ║
            ║   Duration: 4-5 months                           ║
            ║   Output: Paper reimplementation portfolio       ║
            ╚═══════════════════════════╤═══════════════════════╝
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
     ╔══════════════════════════════╗  ╔══════════════════════════════╗
     ║    STAGE 4A: NLP + GenAI    ║  ║    STAGE 4B: Computer Vision ║
     ║                              ║  ║                              ║
     ║  LLMs, RAG, Agents,         ║  ║  Detection, Segmentation,   ║
     ║  Fine-tuning, Prompt Eng.   ║  ║  Video, 3D, Multimodal      ║
     ║                              ║  ║                              ║
     ║  Duration: 3-4 months       ║  ║  Duration: 3-4 months       ║
     ╚══════════════╤═══════════════╝  ╚══════════════╤═══════════════╝
                    │                                  │
                    └──────────────┬───────────────────┘
                                   ▼
            ╔═══════════════════════════════════════════════════╗
            ║        STAGE 5: PRODUCTION ENGINEERING            ║
            ║                                                   ║
            ║   This is where "ML person" becomes "ML          ║
            ║   Engineer." Docker, K8s, CI/CD, monitoring,     ║
            ║   cost optimization, distributed training.       ║
            ║                                                   ║
            ║   Duration: 3-4 months                           ║
            ║   Output: Full prod system handling 10K+ RPS     ║
            ╚═══════════════════════════╤═══════════════════════╝
                                        │
                                        ▼
            ╔═══════════════════════════════════════════════════╗
            ║        STAGE 6: SENIOR ARCHITECT                 ║
            ║                                                   ║
            ║   System design. Cost-performance tradeoffs.     ║
            ║   Multi-team coordination. Technology strategy.  ║
            ║   This is about JUDGMENT, not just knowledge.    ║
            ║                                                   ║
            ║   Duration: 6-12 months (ongoing forever)        ║
            ║   Output: Architecture docs + team leadership    ║
            ╚═══════════════════════════════════════════════════╝
```

---

## What Makes an Architect Different from a Senior Engineer

```
Senior ML Engineer:                    Senior ML Architect:
─────────────────────                  ──────────────────────
Builds what's designed                 Decides WHAT to build
Optimizes one model                    Designs the whole system
Picks the best tool                    Defines the tool strategy
Writes great code                      Ensures teams write great code
Solves the problem given               Reframes the problem correctly
Knows "how"                            Knows "why" and "when NOT to"
Deploys one service                    Designs for 50 services to coexist
Reads papers                           Decides which papers matter for the org
```

The gap is not "more knowledge." It's judgment, systems thinking, and communication.

---

## How to Use These Files

| File | What It Covers | When to Read |
|------|---------------|--------------|
| `01-FOUNDATIONS.md` | Math + Python learned together through projects | Day 1 |
| `02-CORE-ML.md` | Classical ML, feature engineering, real deployment | After foundations |
| `03-DEEP-LEARNING.md` | Neural nets through transformers, PyTorch mastery | After core ML |
| `04-SPECIALIZATIONS.md` | NLP, CV, GenAI/LLMs - pick your path | After deep learning |
| `05-ENGINEERING.md` | Production systems, MLOps, scaling | Overlaps with Stage 4 |
| `06-ARCHITECT.md` | System design, leadership, the final transformation | After engineering |

---

## Non-Negotiable Habits (Start Day 1, Never Stop)

1. **Write code every day.** Even 30 minutes. Streaks matter.
2. **Read 2 papers per week** (from Stage 2 onwards). Use https://arxiv.org and https://paperswithcode.com
3. **Write about what you learn.** Blog, notes, whatever. Teaching = understanding.
4. **Contribute to open source** (from Stage 3 onwards). Even docs/tests count at first.
5. **Build in public.** Push messy work. Perfect is the enemy of done.

---

## The One Uncomfortable Truth

You will feel lost and behind for the entire journey. That feeling never fully goes away.
The difference between people who make it and people who don't isn't talent -- it's the
ability to keep building while feeling incompetent. The imposter syndrome is the signal
that you're growing, not that you're failing.

Now go read `01-FOUNDATIONS.md` and start building.
