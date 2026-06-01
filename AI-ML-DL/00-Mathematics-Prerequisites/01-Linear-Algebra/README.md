# Linear Algebra for AI/ML/Deep Learning

## Why Linear Algebra Matters for ML

Every piece of data in ML is represented as vectors and matrices. Images are matrices of pixels, text is embedded as vectors, and neural networks are chains of matrix multiplications. Linear algebra IS the computational backbone of modern AI.

```
Input Image (28x28)  →  Flatten to Vector (784,)  →  Matrix Multiply W(784x128)  →  Output (128,)
     [Matrix]              [Vector]                    [Linear Transform]            [Vector]
```

---

## 1. Scalars, Vectors, Matrices, and Tensors

### Scalars
A single number. Examples: learning rate (α = 0.01), loss value (L = 2.34)

```python
alpha = 0.01  # scalar - learning rate
loss = 2.34   # scalar - loss value
```

### Vectors
An ordered array of numbers. Represents a point or direction in space.

```
Real-world examples:
• A word embedding: word "king" → [0.2, -0.5, 0.8, ..., 0.1] (300 dimensions)
• A data point: house → [sqft=1500, bedrooms=3, price=300000]
• RGB pixel: [255, 128, 0]
```

```python
import numpy as np

# Word embedding vector (simplified)
king = np.array([0.2, -0.5, 0.8, 0.1])

# Feature vector for a house
house = np.array([1500, 3, 2, 300000])  # sqft, beds, baths, price
```

**Geometric Intuition:**
```
        y
        ▲
        │      • v = [3, 2]
        │     /
    2   │    /
        │   /
    1   │  /
        │ /
        │/────────────▶ x
        0    1    2    3
```

### Matrices
A 2D array of numbers. Represents transformations, datasets, or images.

```
Real-world examples:
• Dataset: rows = samples, columns = features
• Image: 28x28 matrix of pixel intensities
• Weight matrix in a neural network layer
```

```python
# Dataset matrix: 3 houses, 4 features each
X = np.array([
    [1500, 3, 2, 300000],
    [2000, 4, 3, 450000],
    [1200, 2, 1, 200000]
])  # Shape: (3, 4)

# Neural network weight matrix
W = np.random.randn(784, 128)  # Maps 784 inputs to 128 neurons
```

### Tensors
Generalization to N dimensions. A 3D tensor could be a batch of images or a color image.

```
Scalar:  0D tensor     → single number
Vector:  1D tensor     → array
Matrix:  2D tensor     → 2D array
3D Tensor:             → batch of matrices (e.g., batch of images)
4D Tensor:             → batch of color images [batch, channels, height, width]
```

```python
# 3D Tensor: batch of 32 grayscale images, each 28x28
batch = np.random.randn(32, 28, 28)

# 4D Tensor: batch of 32 RGB images, each 224x224
images = np.random.randn(32, 3, 224, 224)  # [batch, channels, H, W]
```

---

## 2. Vector Operations

### Dot Product (Inner Product)

The dot product measures similarity between vectors. Fundamental to attention mechanisms, cosine similarity, and neural network computations.

```
a · b = Σ(aᵢ × bᵢ) = |a| × |b| × cos(θ)
```

```
Geometric interpretation:
         b
        /
       / θ
      /___________  a
     
     a · b > 0  → vectors point in similar direction (θ < 90°)
     a · b = 0  → vectors are perpendicular (θ = 90°)
     a · b < 0  → vectors point in opposite directions (θ > 90°)
```

```python
a = np.array([1, 2, 3])
b = np.array([4, 5, 6])

# Dot product
dot = np.dot(a, b)  # 1*4 + 2*5 + 3*6 = 32

# Cosine similarity (used in NLP for word similarity)
cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

**ML Application:** In attention mechanisms, dot product computes how much "attention" one token pays to another:
```
Attention(Q, K, V) = softmax(Q × Kᵀ / √d) × V
                          ↑ dot products between queries and keys
```

### Vector Norms

Norms measure the "size" or "length" of a vector.

```
L1 norm (Manhattan):  ||x||₁ = Σ|xᵢ|         → Lasso regularization
L2 norm (Euclidean):  ||x||₂ = √(Σxᵢ²)       → Ridge regularization, distance
L∞ norm (Max):        ||x||∞ = max(|xᵢ|)      → Adversarial robustness
```

```python
x = np.array([3, -4, 5])

l1 = np.linalg.norm(x, ord=1)    # |3|+|-4|+|5| = 12
l2 = np.linalg.norm(x, ord=2)    # √(9+16+25) = √50 ≈ 7.07
linf = np.linalg.norm(x, ord=np.inf)  # max(3,4,5) = 5
```

**ML Application:** Regularization in neural networks:
- L1 → Sparse weights (feature selection)
- L2 → Small weights (prevents overfitting)

### Cross Product (3D only)

Produces a vector perpendicular to both inputs. Less common in ML but used in 3D vision and robotics.

```python
a = np.array([1, 0, 0])
b = np.array([0, 1, 0])
cross = np.cross(a, b)  # [0, 0, 1] - perpendicular to both
```

---

## 3. Matrix Operations

### Matrix Multiplication

The workhorse of deep learning. Every neural network layer is a matrix multiplication followed by a nonlinearity.

```
C = A × B
where A is (m×n) and B is (n×p), result C is (m×p)

Rule: Inner dimensions must match!
(m×n) × (n×p) = (m×p)
```

```
Geometric view: Matrix multiplication = Linear transformation

   Original          After transformation
   ┌─────┐          ┌─────────┐
   │     │    A×    │         │
   │  □  │   ───▶   │   ◇     │  (rotated, scaled, skewed)
   │     │          │         │
   └─────┘          └─────────┘
```

```python
# Neural network forward pass
X = np.random.randn(32, 784)    # 32 images, 784 pixels each
W = np.random.randn(784, 256)   # Weight matrix
b = np.random.randn(256)        # Bias vector

# Linear layer: y = Xw + b
output = X @ W + b  # Shape: (32, 256)
```

### Transpose

Flips rows and columns. (A^T)ᵢⱼ = Aⱼᵢ

```python
A = np.array([[1, 2, 3],
              [4, 5, 6]])  # Shape: (2, 3)
              
A_T = A.T  # Shape: (3, 2)
# [[1, 4],
#  [2, 5],
#  [3, 6]]
```

**ML Application:** Computing Gram matrices (AᵀA) for style transfer, computing covariance matrices.

### Matrix Inverse

A⁻¹ such that A × A⁻¹ = I (identity matrix). Only exists for square, non-singular matrices.

```python
A = np.array([[2, 1],
              [5, 3]])
              
A_inv = np.linalg.inv(A)
# Verify: A @ A_inv ≈ Identity
print(A @ A_inv)  # [[1, 0], [0, 1]]
```

**ML Application:** Solving linear systems (normal equation for linear regression):
```
θ = (XᵀX)⁻¹ Xᵀy    ← closed-form solution for linear regression
```

### Determinant

Measures how a matrix scales volume. det(A) = 0 means the matrix is singular (not invertible).

```python
A = np.array([[3, 1], [2, 4]])
det = np.linalg.det(A)  # 3*4 - 1*2 = 10
```

---

## 4. Eigenvalues and Eigenvectors

### The Core Idea

An eigenvector of matrix A is a vector that, when transformed by A, only gets scaled (not rotated):

```
A × v = λ × v

where:
  v = eigenvector (direction that doesn't change)
  λ = eigenvalue (how much it scales)
```

### Geometric Intuition

```
    Before (v)              After (A×v)
        ▲                      ▲
        │                      │
        │ v                    │ λv  (same direction, different magnitude)
        │                      │
────────┼────────      ────────┼────────
        │                      │

    Most vectors change direction when transformed by A.
    Eigenvectors ONLY change magnitude.
```

**Real-World Analogy:** Imagine stretching a rubber sheet. Most points move in complex ways, but some points only move straight outward or inward along fixed axes - those are the eigenvectors.

```python
A = np.array([[4, 2],
              [1, 3]])

eigenvalues, eigenvectors = np.linalg.eig(A)
# eigenvalues: [5, 2]
# eigenvectors: columns of the matrix

# Verify: A @ v = λ * v
v = eigenvectors[:, 0]
lam = eigenvalues[0]
print(np.allclose(A @ v, lam * v))  # True
```

### ML Applications of Eigendecomposition

1. **PCA (Principal Component Analysis):** Eigenvectors of the covariance matrix give the principal components
2. **Google's PageRank:** Dominant eigenvector of the link matrix
3. **Spectral Clustering:** Uses eigenvectors of the graph Laplacian
4. **Stability Analysis:** Eigenvalues determine if a system diverges or converges

---

## 5. Singular Value Decomposition (SVD)

### The Most Important Matrix Decomposition in ML

Every matrix A (m×n) can be decomposed as:

```
A = U × Σ × Vᵀ

where:
  U  (m×m) = left singular vectors (orthogonal)
  Σ  (m×n) = diagonal matrix of singular values (σ₁ ≥ σ₂ ≥ ... ≥ 0)
  Vᵀ (n×n) = right singular vectors (orthogonal)
```

```
┌─────┐     ┌─────┐   ┌─────┐   ┌─────┐
│     │     │     │   │σ₁   │   │     │
│  A  │  =  │  U  │ × │ σ₂  │ × │ Vᵀ  │
│     │     │     │   │  σ₃ │   │     │
│(m×n)│     │(m×m)│   │(m×n)│   │(n×n)│
└─────┘     └─────┘   └─────┘   └─────┘
             rotate     scale     rotate
```

### Low-Rank Approximation (Image Compression)

Keep only the top-k singular values to approximate the matrix:

```python
from PIL import Image

# Load grayscale image as matrix
img = np.random.randn(512, 512)  # Simulating an image

U, S, Vt = np.linalg.svd(img, full_matrices=False)

# Reconstruct with only top-k components
k = 50  # Keep only 50 singular values (out of 512)
img_compressed = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]

# Compression ratio: original=512*512=262144, compressed=512*50+50+50*512=51250
# ~5x compression!
```

### ML Applications of SVD

1. **PCA:** SVD of centered data matrix gives principal components
2. **Recommendation Systems:** Matrix factorization (Netflix Prize)
3. **NLP:** Latent Semantic Analysis (LSA)
4. **Image Compression:** Keep top singular values
5. **Pseudoinverse:** A⁺ = V Σ⁺ Uᵀ (for least squares)

---

## 6. Other Matrix Decompositions

### LU Decomposition
Factors A = L × U (Lower × Upper triangular). Used for solving linear systems efficiently.

### QR Decomposition
Factors A = Q × R (Orthogonal × Upper triangular). Used in numerical linear algebra, least squares.

### Cholesky Decomposition
For symmetric positive-definite matrices: A = LLᵀ. Used in Gaussian processes, sampling from multivariate normals.

```python
# Cholesky: used to sample from multivariate Gaussian
cov = np.array([[1.0, 0.5], [0.5, 2.0]])  # Covariance matrix
L = np.linalg.cholesky(cov)

# Sample: x = μ + L @ z, where z ~ N(0, I)
z = np.random.randn(2, 1000)
samples = L @ z  # Samples from N(0, cov)
```

---

## 7. Vector Spaces, Span, Basis, and Rank

### Vector Space
A set of vectors closed under addition and scalar multiplication. Rⁿ is the most common.

### Span
The span of a set of vectors is all possible linear combinations of those vectors.

```
span({v₁, v₂}) = {a₁v₁ + a₂v₂ | a₁, a₂ ∈ ℝ}
```

### Basis
A minimal set of vectors that spans the entire space. In Rⁿ, you need exactly n linearly independent vectors.

```
Standard basis for R³:
e₁ = [1, 0, 0]
e₂ = [0, 1, 0]
e₃ = [0, 0, 1]
```

### Rank
The number of linearly independent rows (or columns). Tells you the "true" dimensionality of the data.

```python
A = np.array([[1, 2, 3],
              [2, 4, 6],   # This row is 2× the first (linearly dependent)
              [1, 0, 1]])

rank = np.linalg.matrix_rank(A)  # 2 (not 3, because row 2 is dependent)
```

**ML Application:** If your feature matrix has rank < number of features, you have redundant features (multicollinearity). PCA finds the true rank.

---

## 8. Applications in ML

### PCA (Principal Component Analysis)

Reduce dimensionality by projecting onto eigenvectors of the covariance matrix.

```python
from sklearn.decomposition import PCA

# High-dimensional data
X = np.random.randn(1000, 50)  # 1000 samples, 50 features

# Reduce to 2 dimensions
pca = PCA(n_components=2)
X_reduced = pca.fit_transform(X)

# Manual PCA with SVD:
X_centered = X - X.mean(axis=0)
U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
X_pca = X_centered @ Vt[:2].T  # Project onto top 2 components
```

### Word Embeddings

Words as vectors allows algebraic reasoning:
```
king - man + woman ≈ queen

    king [0.5, 0.8, -0.2, ...]
  - man  [0.4, 0.7, -0.3, ...]
  + woman[0.3, 0.6, -0.4, ...]
  ≈ queen[0.4, 0.7, -0.3, ...]
```

### Neural Network Forward Pass

```python
def forward(x, weights, biases):
    """Every layer is: output = activation(W @ x + b)"""
    for W, b in zip(weights, biases):
        x = np.maximum(0, W @ x + b)  # ReLU activation
    return x
```

---

## Summary Table

| Concept | Symbol | ML Use Case |
|---------|--------|-------------|
| Dot product | a·b | Attention, similarity |
| Matrix multiply | AB | Neural network layers |
| Transpose | Aᵀ | Covariance, Gram matrices |
| Inverse | A⁻¹ | Normal equation |
| Eigenvalues | λ | PCA, stability |
| SVD | UΣVᵀ | Compression, recommendations |
| Norm | \|\|x\|\| | Regularization |
| Rank | rank(A) | Dimensionality, redundancy |

---

## Key Takeaways

1. **Data = Matrices/Tensors.** Think of everything as linear algebra objects.
2. **Neural networks = chains of matrix multiplications** + nonlinearities.
3. **SVD and eigendecomposition** unlock dimensionality reduction and compression.
4. **Dot products** measure similarity — the basis of attention mechanisms.
5. **Norms** are used everywhere for regularization and distance.

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** Given vectors a = [1, 2, 3] and b = [4, 5, 6], compute: (a) a + b, (b) 3a, (c) dot product a·b, (d) ||a|| (Euclidean norm).

**Hint:** Dot product = sum of element-wise products. Norm = sqrt(sum of squares).

<details><summary>Solution</summary>

```
(a) a + b = [5, 7, 9]
(b) 3a = [3, 6, 9]
(c) a·b = 1×4 + 2×5 + 3×6 = 4 + 10 + 18 = 32
(d) ||a|| = sqrt(1² + 2² + 3²) = sqrt(14) ≈ 3.742
```
</details>

### Exercise 2 (Beginner)
**Problem:** Multiply matrices A = [[1,2],[3,4]] and B = [[5,6],[7,8]]. What is AB? Is AB = BA?

**Hint:** (AB)ᵢⱼ = sum over k of Aᵢₖ × Bₖⱼ

<details><summary>Solution</summary>

```
AB = [[1×5+2×7, 1×6+2×8], [3×5+4×7, 3×6+4×8]]
   = [[19, 22], [43, 50]]

BA = [[5×1+6×3, 5×2+6×4], [7×1+8×3, 7×2+8×4]]
   = [[23, 34], [31, 46]]

AB ≠ BA → Matrix multiplication is NOT commutative.
```
</details>

### Exercise 3 (Beginner)
**Problem:** Find the transpose of A = [[1,2,3],[4,5,6]]. What are the dimensions of A and Aᵀ?

**Hint:** Transpose swaps rows and columns.

<details><summary>Solution</summary>

```
A is 2×3
Aᵀ = [[1,4],[2,5],[3,6]] which is 3×2
```
</details>

### Exercise 4 (Beginner)
**Problem:** Compute the cosine similarity between u = [1, 0, 1] and v = [0, 1, 1]. What does this tell you about their relationship?

**Hint:** cos(θ) = (u·v) / (||u|| × ||v||)

<details><summary>Solution</summary>

```
u·v = 0 + 0 + 1 = 1
||u|| = sqrt(2), ||v|| = sqrt(2)
cos(θ) = 1 / (sqrt(2)×sqrt(2)) = 1/2 = 0.5
θ = 60° → vectors are somewhat similar but not identical
```
</details>

### Exercise 5 (Intermediate)
**Problem:** Find the eigenvalues and eigenvectors of A = [[4, 1],[2, 3]].

**Hint:** Solve det(A - λI) = 0 for eigenvalues, then (A - λI)v = 0 for eigenvectors.

<details><summary>Solution</summary>

```
det(A - λI) = (4-λ)(3-λ) - 2 = λ² - 7λ + 10 = (λ-5)(λ-2) = 0
λ₁ = 5, λ₂ = 2

For λ₁ = 5: (A-5I)v = 0 → [[-1,1],[2,-2]]v = 0 → v₁ = [1, 1]
For λ₂ = 2: (A-2I)v = 0 → [[2,1],[2,1]]v = 0 → v₂ = [1, -2]
```
</details>

### Exercise 6 (Intermediate)
**Problem:** Given a matrix A = [[3, 1],[1, 3]], compute AᵀA and show it's symmetric positive semi-definite.

**Hint:** A matrix M is PSD if xᵀMx ≥ 0 for all x, or equivalently all eigenvalues ≥ 0.

<details><summary>Solution</summary>

```
AᵀA = [[3,1],[1,3]]×[[3,1],[1,3]] = [[10, 6],[6, 10]]
Eigenvalues: det(AᵀA - λI) = (10-λ)² - 36 = 0 → λ = 16, 4
Both eigenvalues > 0, so AᵀA is symmetric positive definite (hence also PSD).
Also (AᵀA)ᵀ = Aᵀ(Aᵀ)ᵀ = AᵀA → symmetric ✓
```
</details>

### Exercise 7 (Intermediate)
**Problem:** Perform SVD conceptually: If A is a 5×3 matrix of rank 2, what are the dimensions of U, Σ, and Vᵀ in the full SVD? How many non-zero singular values exist?

**Hint:** Full SVD: A = UΣVᵀ where U is m×m, Σ is m×n, Vᵀ is n×n.

<details><summary>Solution</summary>

```
A is 5×3, rank 2
U: 5×5 (orthogonal)
Σ: 5×3 (diagonal with singular values)
Vᵀ: 3×3 (orthogonal)
Non-zero singular values: 2 (equals the rank)
```
</details>

### Exercise 8 (Intermediate)
**Problem:** You have 1000 data points in 50 dimensions. After PCA, you want to retain 95% of variance. The eigenvalues (sorted descending) sum to 100, and the first 5 eigenvalues sum to 96. How many components do you keep? What's the compression ratio?

**Hint:** Keep components until cumulative variance ≥ 95%.

<details><summary>Solution</summary>

```
First 5 eigenvalues sum = 96, total = 100 → 96% variance retained
Keep 5 components (96% > 95% threshold)
Compression ratio: 50/5 = 10x dimensionality reduction
Data goes from 1000×50 to 1000×5
```
</details>

### Exercise 9 (Advanced)
**Problem:** Prove that for any matrix A, the matrices AᵀA and AAᵀ have the same non-zero eigenvalues.

**Hint:** If Av = σu and Aᵀu = σv (from SVD), relate eigenvalues of AᵀA and AAᵀ.

<details><summary>Solution</summary>

```
If λ is a non-zero eigenvalue of AᵀA with eigenvector v:
  AᵀA v = λv
Multiply both sides by A:
  A(AᵀA)v = λ(Av)
  (AAᵀ)(Av) = λ(Av)

So Av is an eigenvector of AAᵀ with the same eigenvalue λ.
Since λ ≠ 0, Av ≠ 0 (otherwise AᵀAv = 0, contradiction).
Therefore all non-zero eigenvalues of AᵀA are also eigenvalues of AAᵀ.
By symmetry (swap A and Aᵀ), the reverse holds too.
```
</details>

### Exercise 10 (Advanced)
**Problem:** In a neural network layer y = Wx + b, W is 128×784. (a) What's the input dimension? (b) Output dimension? (c) How many parameters? (d) If we apply rank-10 approximation W ≈ UV where U is 128×10 and V is 10×784, how many parameters now? What's the compression?

**Hint:** Count total elements in each matrix.

<details><summary>Solution</summary>

```
(a) Input dimension: 784
(b) Output dimension: 128
(c) Parameters in W: 128×784 = 100,352 (+ 128 bias = 100,480)
(d) Low-rank: U(128×10) + V(10×784) = 1,280 + 7,840 = 9,120
    Compression: 100,352 / 9,120 ≈ 11x fewer parameters
```
</details>

### Exercise 11 (Advanced)
**Problem:** Show that the projection of vector b onto the column space of A is given by p = A(AᵀA)⁻¹Aᵀb. What are the dimensions of the projection matrix if A is m×n with m > n?

**Hint:** The projection minimizes ||b - Ax||². Set derivative to zero.

<details><summary>Solution</summary>

```
Minimize ||b - Ax||² = (b-Ax)ᵀ(b-Ax)
Derivative w.r.t. x: -2Aᵀ(b-Ax) = 0
→ AᵀAx = Aᵀb
→ x = (AᵀA)⁻¹Aᵀb  (normal equations!)
→ p = Ax = A(AᵀA)⁻¹Aᵀb

Projection matrix P = A(AᵀA)⁻¹Aᵀ has dimensions m×m
Properties: P² = P (idempotent), Pᵀ = P (symmetric)
```
</details>

### Exercise 12 (Advanced)
**Problem:** Explain why the determinant of a matrix equals the product of its eigenvalues, and why the trace equals the sum of eigenvalues. What does det(A) = 0 mean geometrically?

**Hint:** Consider the characteristic polynomial and its relationship to eigenvalues.

<details><summary>Solution</summary>

```
Characteristic polynomial: det(A - λI) = (λ₁-λ)(λ₂-λ)...(λₙ-λ)

Setting λ=0: det(A) = λ₁×λ₂×...×λₙ (product of eigenvalues)
Comparing coefficients of λⁿ⁻¹: trace(A) = λ₁+λ₂+...+λₙ

det(A) = 0 means:
- At least one eigenvalue is 0
- The matrix is singular (not invertible)
- Geometrically: the transformation collapses space by at least one dimension
- The column vectors are linearly dependent
```
</details>

---

## Self-Assessment Quiz

**1. What is the result of multiplying a 3×4 matrix by a 4×2 matrix?**
- (a) 3×2 matrix
- (b) 4×4 matrix
- (c) 3×4 matrix
- (d) Cannot be multiplied

<details><summary>Answer</summary>(a) 3×2 matrix. Inner dimensions (4) must match; result has outer dimensions.</details>

**2. The eigenvalues of a symmetric matrix are always:**
- (a) Complex
- (b) Real
- (c) Positive
- (d) Zero

<details><summary>Answer</summary>(b) Real. Symmetric matrices always have real eigenvalues (Spectral Theorem).</details>

**3. What does PCA use to find principal components?**
- (a) Eigendecomposition of the covariance matrix
- (b) Inverse of the data matrix
- (c) Determinant of the feature matrix
- (d) Cross product of vectors

<details><summary>Answer</summary>(a) Eigendecomposition of the covariance matrix (or equivalently, SVD of the centered data matrix).</details>

**4. If a matrix has rank r < min(m,n), it means:**
- (a) All columns are independent
- (b) The matrix is invertible
- (c) Some columns are linear combinations of others
- (d) All eigenvalues are non-zero

<details><summary>Answer</summary>(c) Some columns are linear combinations of others (rank-deficient).</details>

**5. The dot product of two orthogonal vectors is:**
- (a) 1
- (b) -1
- (c) 0
- (d) Undefined

<details><summary>Answer</summary>(c) 0. Orthogonal means perpendicular, so their dot product is zero.</details>

**6. In SVD (A = UΣVᵀ), the diagonal values of Σ represent:**
- (a) Eigenvalues of A
- (b) Singular values (square roots of eigenvalues of AᵀA)
- (c) The rank of A
- (d) The determinant of A

<details><summary>Answer</summary>(b) Singular values, which are the square roots of eigenvalues of AᵀA.</details>

**7. What's the computational complexity of multiplying two n×n matrices naively?**
- (a) O(n)
- (b) O(n²)
- (c) O(n³)
- (d) O(2ⁿ)

<details><summary>Answer</summary>(c) O(n³). Each of n² entries requires a dot product of length n.</details>

**8. The column space of a matrix A (m×n) is:**
- (a) A subspace of Rⁿ
- (b) A subspace of Rᵐ
- (c) Always equal to Rᵐ
- (d) The set of all possible inputs

<details><summary>Answer</summary>(b) A subspace of Rᵐ. It's the set of all possible outputs Ax.</details>

**9. A positive definite matrix has:**
- (a) All eigenvalues > 0
- (b) All eigenvalues < 0
- (c) Determinant = 0
- (d) At least one zero eigenvalue

<details><summary>Answer</summary>(a) All eigenvalues > 0. Equivalently, xᵀAx > 0 for all non-zero x.</details>

**10. Why is the identity matrix used in regularization (A + λI)?**
- (a) To make the matrix bigger
- (b) To ensure invertibility by shifting eigenvalues away from zero
- (c) To reduce the rank
- (d) To make computations faster

<details><summary>Answer</summary>(b) Adding λI shifts all eigenvalues by λ, ensuring they're all > 0 (for λ > 0), making the matrix invertible.</details>

---

## Coding Challenges

### Challenge 1: Implement Matrix Operations from Scratch
```python
"""
Implement WITHOUT numpy:
1. Matrix multiplication
2. Matrix transpose
3. Dot product of vectors
Test with: A = [[1,2],[3,4]], B = [[5,6],[7,8]]
"""
```

<details><summary>Solution</summary>

```python
def mat_mul(A, B):
    rows_A, cols_A = len(A), len(A[0])
    rows_B, cols_B = len(B), len(B[0])
    assert cols_A == rows_B
    result = [[0]*cols_B for _ in range(rows_A)]
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                result[i][j] += A[i][k] * B[k][j]
    return result

def transpose(A):
    return [[A[j][i] for j in range(len(A))] for i in range(len(A[0]))]

def dot_product(u, v):
    return sum(a*b for a, b in zip(u, v))

# Test
A = [[1,2],[3,4]]
B = [[5,6],[7,8]]
print(mat_mul(A, B))  # [[19,22],[43,50]]
print(transpose(A))    # [[1,3],[2,4]]
print(dot_product([1,2,3], [4,5,6]))  # 32
```
</details>

### Challenge 2: PCA from Scratch
```python
"""
Implement PCA on a 2D dataset:
1. Center the data (subtract mean)
2. Compute covariance matrix
3. Find eigenvalues/eigenvectors (use numpy.linalg.eig)
4. Project data onto top-k components
5. Visualize original vs projected data

Use: X = np.random.randn(100, 2) @ [[2, 1],[1, 3]] (correlated data)
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

# Generate correlated 2D data
np.random.seed(42)
X = np.random.randn(100, 2) @ np.array([[2, 1],[1, 3]])

# Step 1: Center
X_centered = X - X.mean(axis=0)

# Step 2: Covariance matrix
cov = (X_centered.T @ X_centered) / (len(X) - 1)

# Step 3: Eigendecomposition
eigenvalues, eigenvectors = np.linalg.eig(cov)
idx = np.argsort(eigenvalues)[::-1]
eigenvalues = eigenvalues[idx]
eigenvectors = eigenvectors[:, idx]

# Step 4: Project onto first component
X_projected = X_centered @ eigenvectors[:, :1]

# Step 5: Reconstruct and visualize
X_reconstructed = X_projected @ eigenvectors[:, :1].T + X.mean(axis=0)

plt.scatter(X[:, 0], X[:, 1], alpha=0.5, label='Original')
plt.scatter(X_reconstructed[:, 0], X_reconstructed[:, 1], alpha=0.5, label='1-PC')
plt.legend()
plt.title(f'PCA: {eigenvalues[0]/sum(eigenvalues)*100:.1f}% variance in PC1')
plt.show()
```
</details>

### Challenge 3: Image Compression with SVD
```python
"""
1. Load a grayscale image (or create a 100x100 random one)
2. Perform SVD: U, S, Vt = np.linalg.svd(image)
3. Reconstruct using only top-k singular values (k=5, 10, 20, 50)
4. Plot the reconstructions and compute compression ratios
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

# Create a test image (gradient + noise)
image = np.outer(np.linspace(0,1,100), np.linspace(0,1,100)) + 0.1*np.random.randn(100,100)

U, S, Vt = np.linalg.svd(image, full_matrices=False)

fig, axes = plt.subplots(1, 5, figsize=(15, 3))
for idx, k in enumerate([5, 10, 20, 50, 100]):
    reconstructed = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
    compression = (100*100) / (100*k + k + k*100)
    axes[idx].imshow(reconstructed, cmap='gray')
    axes[idx].set_title(f'k={k}\n{compression:.1f}x compression')
    axes[idx].axis('off')
plt.tight_layout()
plt.show()
```
</details>

### Challenge 4: Cosine Similarity Search
```python
"""
Implement a simple word embedding similarity search:
1. Create 10 random "word embeddings" (vectors of dim 50)
2. Given a query vector, find the top-3 most similar words using cosine similarity
3. Compare with Euclidean distance ranking — do they agree?
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

np.random.seed(42)
words = ['king', 'queen', 'man', 'woman', 'child', 'royal', 'throne', 'cat', 'dog', 'fish']
embeddings = np.random.randn(10, 50)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def euclidean_distance(a, b):
    return np.linalg.norm(a - b)

query = embeddings[0]  # "king"

# Cosine similarity ranking
cos_scores = [(words[i], cosine_similarity(query, embeddings[i])) for i in range(1, 10)]
cos_ranked = sorted(cos_scores, key=lambda x: -x[1])

# Euclidean distance ranking
euc_scores = [(words[i], euclidean_distance(query, embeddings[i])) for i in range(1, 10)]
euc_ranked = sorted(euc_scores, key=lambda x: x[1])

print("Top-3 by cosine similarity:", [(w, f"{s:.3f}") for w, s in cos_ranked[:3]])
print("Top-3 by Euclidean distance:", [(w, f"{s:.3f}") for w, s in euc_ranked[:3]])
print("Rankings agree?", [x[0] for x in cos_ranked[:3]] == [x[0] for x in euc_ranked[:3]])
```
</details>

### Challenge 5: Power Iteration for Dominant Eigenvalue
```python
"""
Implement the power iteration algorithm:
1. Start with a random vector
2. Repeatedly multiply by matrix A and normalize
3. Converge to the dominant eigenvector
4. Verify against numpy.linalg.eig

Test with A = [[2, 1],[1, 3]]
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

def power_iteration(A, num_iters=100, tol=1e-10):
    n = A.shape[0]
    v = np.random.randn(n)
    v = v / np.linalg.norm(v)
    
    for i in range(num_iters):
        Av = A @ v
        v_new = Av / np.linalg.norm(Av)
        if np.abs(np.abs(np.dot(v_new, v)) - 1.0) < tol:
            break
        v = v_new
    
    eigenvalue = v @ A @ v  # Rayleigh quotient
    return eigenvalue, v

A = np.array([[2., 1.],[1., 3.]])
eigval, eigvec = power_iteration(A)
print(f"Power iteration: λ = {eigval:.6f}, v = {eigvec}")

# Verify
vals, vecs = np.linalg.eig(A)
idx = np.argmax(vals)
print(f"Numpy:           λ = {vals[idx]:.6f}, v = {vecs[:, idx]}")
```
</details>

---

## Interview Questions

### 1. What is the intuition behind eigenvalues and eigenvectors? How are they used in ML?
<details><summary>Answer</summary>

Eigenvectors are directions that remain unchanged (only scaled) under a linear transformation. Eigenvalues are the scaling factors. In ML:
- **PCA**: Eigenvectors of covariance matrix = principal components; eigenvalues = variance explained
- **PageRank**: Dominant eigenvector of web link matrix
- **Spectral clustering**: Eigenvectors of graph Laplacian
- **Stability analysis**: Eigenvalues determine convergence of iterative algorithms
</details>

### 2. Explain SVD and its applications in ML.
<details><summary>Answer</summary>

SVD decomposes any matrix A (m×n) into A = UΣVᵀ where U (m×m orthogonal), Σ (m×n diagonal with singular values), Vᵀ (n×n orthogonal). Applications:
- **Dimensionality reduction**: Keep top-k singular values (truncated SVD)
- **Recommender systems**: Matrix factorization for collaborative filtering
- **NLP**: Latent Semantic Analysis (LSA)
- **Image compression**: Low-rank approximation
- **Pseudoinverse**: A⁺ = VΣ⁺Uᵀ for least-squares solutions
</details>

### 3. Why do we need to normalize/standardize features before applying PCA?
<details><summary>Answer</summary>

PCA finds directions of maximum variance. If features have different scales (e.g., age 0-100 vs salary 0-1M), PCA will be dominated by the high-variance feature regardless of actual importance. Standardization (zero mean, unit variance) ensures all features contribute equally. Without it, PCA results are meaningless.
</details>

### 4. What's the difference between the rank of a matrix and its dimensions?
<details><summary>Answer</summary>

Dimensions (m×n) describe size; rank describes the number of linearly independent rows/columns. Rank ≤ min(m,n). A rank-deficient matrix means some rows/columns are redundant. In ML:
- Low-rank data suggests redundancy (can compress with PCA)
- Low-rank weight matrices enable model compression
- Rank of the design matrix affects whether linear regression has a unique solution
</details>

### 5. How does the condition number of a matrix affect numerical stability in ML?
<details><summary>Answer</summary>

Condition number κ(A) = σ_max/σ_min (ratio of largest to smallest singular value). High condition number means:
- Small input perturbations cause large output changes
- Gradient descent converges slowly (elongated loss landscape)
- Numerical errors are amplified
Solutions: regularization (Ridge/L2 adds λI, improving condition number), feature scaling, using SVD-based solvers instead of direct inverse.
</details>

### 6. Explain the relationship between matrix inversion and solving linear systems. Why don't we invert matrices in practice?
<details><summary>Answer</summary>

Solving Ax = b theoretically gives x = A⁻¹b, but computing A⁻¹ is:
- O(n³) and numerically unstable
- Unnecessary — we only need x, not A⁻¹
Instead, use LU decomposition, QR decomposition, or iterative methods (conjugate gradient). In ML, we rarely need exact solutions anyway — gradient descent approximates iteratively.
</details>

### 7. What is the kernel trick and how does it relate to linear algebra?
<details><summary>Answer</summary>

The kernel trick maps data to a higher-dimensional space where it becomes linearly separable, without explicitly computing the transformation. It works because many algorithms (SVM, PCA) only need dot products between data points. If K(x,y) = φ(x)·φ(y) computes the dot product in the high-dimensional space, we never need to compute φ explicitly. This is a linear algebra insight: the algorithm depends only on the Gram matrix (matrix of all pairwise dot products).
</details>

### 8. How are matrices used in graph neural networks?
<details><summary>Answer</summary>

Graphs are represented as adjacency matrices A. Key operations:
- **Message passing**: H' = σ(D⁻¹AHW) — normalized adjacency × features × weights
- **Graph Laplacian**: L = D - A (used in spectral GNNs)
- **Eigendecomposition of L** gives graph Fourier basis
- Sparse matrix operations are critical for efficiency with large graphs
</details>
