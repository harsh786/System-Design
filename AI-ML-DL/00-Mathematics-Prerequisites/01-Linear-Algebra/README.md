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
