# Stage 1: Foundations (Math + Python, Together)

> Duration: 3-4 months | Output: A working neural network built from raw NumPy

---

## Why I Combine Math and Python

The traditional approach -- "learn all the math first, then code" -- fails because:
- You forget the math by the time you code it
- You never build intuition for WHY the math matters
- It's boring and most people quit

Instead: **Learn each math concept, then immediately implement it in Python.**
The code IS the understanding.

---

## The Structure

```
Month 1                    Month 2                    Month 3-4
───────                    ───────                    ─────────
                                                     
Linear Algebra             Probability &              Optimization &
+ NumPy                    Statistics +               Autograd +
+ Matplotlib               Pandas + EDA               Neural Net from Scratch
                                                     
┌─────────────┐            ┌─────────────┐           ┌──────────────────┐
│ Vectors     │            │ Distributions│           │ Gradient Descent │
│ Matrices    │            │ Bayes' Rule  │           │ Backpropagation  │
│ Transforms  │            │ MLE/MAP      │           │ Autograd engine  │
│ Eigenvalues │            │ Hypothesis   │           │ Optimizers       │
│ SVD/PCA     │            │ A/B Testing  │           │ Full neural net  │
│ Broadcasting│            │ Correlation  │           │ Training loop    │
└─────────────┘            └─────────────┘           └──────────────────┘
      │                          │                          │
      ▼                          ▼                          ▼
 Project:                   Project:                   Project:
 Image compression          Statistical analysis       micrograd + 
 with SVD                   tool (like a mini-R)       mini-torch
```

---

## Month 1: Linear Algebra + NumPy

### Week 1-2: Vectors, Matrices, and NumPy Fluency

**What to learn (in this order):**

1. Vectors: what they are geometrically, dot product, cross product
2. Matrices: multiplication (WHY it works that way), transpose, inverse
3. NumPy: arrays, shapes, dtypes, reshaping, broadcasting
4. Systems of linear equations (Ax = b)
5. Matrix decompositions: LU, QR

**How to learn it:**

| Resource | Why This One | Link |
|----------|-------------|------|
| 3Blue1Brown: Essence of Linear Algebra | Best geometric intuition ever made. Watch ALL of it. | https://youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab |
| NumPy official "NumPy for absolute beginners" | Learn NumPy as you learn the math | https://numpy.org/doc/stable/user/absolute_beginners.html |
| MIT 18.06 (Gilbert Strang) - first 10 lectures | The OG linear algebra course | https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/video_galleries/video-lectures/ |
| "From Python to NumPy" - Rougier | How to THINK in NumPy (vectorization) | https://www.labri.fr/perso/nrougier/from-python-to-numpy/ |

**What to build (Week 2):**
- Implement matrix multiplication without using `@` or `np.matmul`
- Build a simple image transformation tool (rotate, scale, shear using matrices)
- Solve a system of 5 equations using your own Gaussian elimination

### Week 3-4: Eigenvalues, SVD, PCA

**What to learn:**

1. Eigenvalues/eigenvectors: what they mean geometrically (stretching directions)
2. Diagonalization and why it matters
3. SVD: the single most important decomposition in all of ML
4. PCA: SVD applied to find important directions in data
5. Matrix norms and condition numbers

**How to learn it:**

| Resource | Why | Link |
|----------|-----|------|
| 3Blue1Brown: Change of basis + Eigenvalues | Geometry of eigen-decomposition | Same playlist above, videos 13-14 |
| Steve Brunton: SVD series | Best SVD explanation on YouTube | https://youtube.com/playlist?list=PLMrJAkhIeNNSVjnsviglFoY2nXildDCcv |
| Mathematics for Machine Learning (Ch 2-4) | Connects math to ML directly | https://mml-book.github.io/ |

**What to build (Week 4) -- FIRST REAL PROJECT:**

```
PROJECT: Image Compression with SVD
─────────────────────────────────────
1. Load a color image as a 3D NumPy array
2. Split into R, G, B channels
3. Perform SVD on each channel
4. Reconstruct using top-k singular values (k = 5, 10, 20, 50, 100, 200)
5. Plot: original vs reconstructed at each k, with compression ratio
6. Calculate PSNR and SSIM at each level
7. Build an interactive slider (matplotlib widgets or Gradio)

Bonus: Compare SVD compression vs JPEG at similar file sizes
```

---

## Month 2: Probability, Statistics, and Data Analysis

### Week 5-6: Probability and Distributions

**What to learn:**

1. Probability axioms, conditional probability, Bayes' theorem
2. Random variables, expectation, variance
3. Key distributions: Normal, Bernoulli, Binomial, Poisson, Uniform, Exponential
4. Multivariate Gaussian (crucial for basically everything)
5. Central Limit Theorem (why everything looks Gaussian)
6. Maximum Likelihood Estimation (MLE) -- this is how models learn
7. Maximum A Posteriori (MAP) -- this is regularization in disguise

**How to learn it:**

| Resource | Why | Link |
|----------|-----|------|
| StatQuest (Josh Starmer) | Makes stats click in 10-15 min videos | https://youtube.com/c/joshstarmer |
| Harvard Stat 110 (first 15 lectures) | Rigorous but clear | https://projects.iq.harvard.edu/stat110/youtube |
| Think Stats + Think Bayes (Allen Downey) | Programming-first stats books, free | https://greenteapress.com/wp/think-stats-2e/ |
| Seeing Theory | Beautiful interactive probability visualizations | https://seeing-theory.brown.edu/ |

**What to build:**
- Monte Carlo simulation: estimate Pi, birthday paradox, Monty Hall
- Distribution visualizer: tool that plots any distribution with interactive params
- Implement MLE for Gaussian parameters from scratch (derive, then code)

### Week 7-8: Statistics for Real Data + Pandas

**What to learn:**

1. Pandas: DataFrames, groupby, merge, pivot, window functions
2. Hypothesis testing: t-test, chi-squared, Mann-Whitney (know WHEN to use each)
3. Confidence intervals and what they actually mean
4. Correlation vs causation (Simpson's paradox, confounders)
5. A/B testing: sample size calculation, early stopping, multiple comparisons
6. EDA: how to look at a dataset systematically

**How to learn it:**

| Resource | Why | Link |
|----------|-----|------|
| "Python for Data Analysis" - Wes McKinney | Written by Pandas creator | Book (3rd ed) |
| Kaggle Learn: Pandas + Data Viz | Quick interactive exercises | https://www.kaggle.com/learn |
| Calling Bullshit (UW course) | How to not fool yourself with stats | https://www.callingbullshit.org/ |

**What to build -- SECOND PROJECT:**

```
PROJECT: Statistical Analysis Toolkit
──────────────────────────────────────
Build a CLI tool (or Streamlit app) that:

1. Takes any CSV dataset
2. Auto-generates EDA report:
   - Missing data heatmap
   - Distribution of every column
   - Correlation matrix with significance
   - Outlier detection (IQR + Z-score)
3. Runs appropriate statistical tests:
   - Normality tests (Shapiro-Wilk)
   - Comparison tests (auto-picks t-test vs Mann-Whitney based on normality)
   - Chi-squared for categorical associations
4. Generates a PDF/HTML report

Think of it as building a mini version of pandas-profiling from scratch.
You learn more building the tool than using someone else's.
```

---

## Month 3-4: Optimization + Building a Neural Network from Nothing

### Week 9-10: Calculus You Actually Need + Optimization

**What to learn:**

1. Chain rule (this IS backpropagation)
2. Partial derivatives and gradients
3. Gradient descent (vanilla, with momentum, Adam)
4. Learning rate: why it matters, schedules, warm-up
5. Convexity: when gradient descent guarantees finding the answer
6. Computational graphs: how autograd systems work

**Key insight:** You don't need to be a calculus expert. You need to understand
the chain rule deeply, know what a gradient is, and understand why optimization
is hard in high dimensions.

**How to learn it:**

| Resource | Why | Link |
|----------|-----|------|
| 3Blue1Brown: Deep Learning series (Ch 1-4) | Backprop explained visually | https://youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi |
| Andrej Karpathy: "micrograd" | Build autograd in 100 lines. This is THE exercise. | https://youtube.com/watch?v=VMj-3S1tku0 |
| Convex Optimization (Boyd), Ch 1-3 only | When/why optimization works | https://web.stanford.edu/~boyd/cvxbook/ |
| "Mathematics for Machine Learning" Ch 5,7 | Optimization for ML specifically | https://mml-book.github.io/ |

**What to build:**
- Implement gradient descent, SGD, Momentum, Adam from scratch
- Build visualizations showing optimization trajectories on 2D loss surfaces
- Benchmark your optimizers on Rosenbrock and Rastrigin functions

### Week 11-14: Build a Neural Network Framework from Scratch

**This is the single most important exercise in the entire roadmap.**

If you complete nothing else from this document, complete this.

**What to build -- CAPSTONE PROJECT FOR STAGE 1:**

```
PROJECT: "minigrad" - Your Own Deep Learning Framework
──────────────────────────────────────────────────────

Phase A (Week 11): Autograd Engine
├── Value class with operator overloading (+, *, -, /, **)
├── Computational graph construction (DAG of operations)
├── Backward pass (topological sort + chain rule)
├── Support: add, mul, pow, relu, exp, log, tanh
└── Test: gradients match PyTorch autograd exactly

Phase B (Week 12): Tensor Support
├── Extend from scalars to N-dimensional tensors
├── Broadcasting (follow NumPy rules)
├── Matmul with autograd
├── Reshaping operations with proper grad
└── Test: matrix operations match PyTorch

Phase C (Week 13): Neural Network API
├── Module base class (parameters, zero_grad)
├── Linear layer
├── Activation functions (ReLU, Sigmoid, Tanh, Softmax)
├── Loss functions (MSE, CrossEntropy)
├── Optimizers (SGD, Adam)
├── Sequential container
└── Test: train on XOR problem

Phase D (Week 14): Train Something Real
├── DataLoader (batching, shuffling)
├── Train a 3-layer net on MNIST
├── Achieve >95% accuracy
├── Compare training curves with PyTorch
├── Profile and optimize bottlenecks
└── Write documentation explaining the math behind each component

Reference implementations to study (AFTER attempting yourself):
- Karpathy's micrograd: https://github.com/karpathy/micrograd
- Tinygrad: https://github.com/tinygrad/tinygrad
- Joel Grus's "livecoding an autograd": YouTube
```

---

## Python Proficiency Requirements

By the end of Stage 1, you must be comfortable with:

```
Non-negotiable Python skills:
├── OOP: classes, inheritance, dunder methods, ABC
├── Functional: map/filter/reduce, closures, decorators
├── Data structures: know when to use dict vs set vs list vs deque
├── Generators and iterators (lazy evaluation)
├── Context managers (with statements)
├── Type hints (you'll need them for large projects)
├── Virtual environments (venv or conda)
├── Git basics (commit, branch, merge, rebase)
└── pytest (write tests for your projects)
```

**How to get here if you're weak in Python:**

| Resource | Time Needed | Link |
|----------|-------------|------|
| "Fluent Python" Ch 1-9 | 2-3 weeks alongside the math | Book (2nd ed) |
| Python official tutorial | 1 week if you already program | https://docs.python.org/3/tutorial/ |
| Exercism Python track | Daily practice problems | https://exercism.org/tracks/python |
| LeetCode Easy (50 problems) | 2-3 weeks of daily practice | https://leetcode.com |

---

## Stage 1 Completion Criteria

You're done with Stage 1 when you can honestly answer YES to all of these:

- [ ] I built a neural network from scratch that trains on MNIST using only NumPy
- [ ] I can explain backpropagation by drawing the computational graph and applying chain rule
- [ ] I can implement PCA without sklearn and explain why it works (eigendecomposition of covariance)
- [ ] I can look at a dataset and perform meaningful EDA without following a tutorial
- [ ] I can derive the gradient of cross-entropy loss with respect to logits
- [ ] I understand what happens numerically when learning rate is too high or too low
- [ ] My GitHub has at least 3 projects from this phase with READMEs
- [ ] I can explain MLE, MAP, and how regularization connects to Bayesian priors

If you can't check all of these, you're not ready for Stage 2. Go back and build more.
Speed comes from depth, not from rushing.

---

## Common Mistakes at This Stage

1. **Watching 3Blue1Brown without coding along.** Those videos are beautiful but
   ephemeral unless you implement what you see.

2. **Spending 3 months on pure math before touching code.** Interleave. Always.

3. **Using sklearn/PyTorch too early.** You should feel the PAIN of implementing
   things manually. That pain becomes deep understanding.

4. **Skipping probability.** "I'll learn it when I need it." You need it in
   Stage 2, and it's too late to cram then.

5. **Not writing tests.** Your minigrad MUST have tests. How else do you know
   your gradients are correct?
