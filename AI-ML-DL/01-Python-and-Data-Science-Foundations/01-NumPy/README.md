# NumPy Mastery

## 1. ndarray Fundamentals

NumPy's core is the `ndarray` - a fixed-size, homogeneous, n-dimensional array stored in contiguous memory.

```python
import numpy as np

# === Creation ===
# From Python lists
a = np.array([1, 2, 3])                    # 1D
b = np.array([[1, 2, 3], [4, 5, 6]])       # 2D (shape: 2x3)

# Factory functions
zeros = np.zeros((3, 4))                    # 3x4 of zeros
ones = np.ones((2, 3), dtype=np.float32)    # specify dtype
empty = np.empty((2, 2))                    # uninitialized (fast)
full = np.full((3, 3), fill_value=7)        # all 7s

# Ranges
r1 = np.arange(0, 10, 2)                   # [0, 2, 4, 6, 8]
r2 = np.linspace(0, 1, 5)                  # [0, 0.25, 0.5, 0.75, 1.0]
r3 = np.logspace(0, 3, 4)                  # [1, 10, 100, 1000]

# Identity and diagonal
eye = np.eye(3)                             # 3x3 identity
diag = np.diag([1, 2, 3])                  # diagonal matrix

# === Key Attributes ===
arr = np.random.randn(3, 4, 5)
print(arr.shape)      # (3, 4, 5)
print(arr.ndim)       # 3
print(arr.size)       # 60
print(arr.dtype)      # float64
print(arr.itemsize)   # 8 bytes per element
print(arr.nbytes)     # 480 total bytes
```

### Indexing and Slicing

```python
arr = np.arange(20).reshape(4, 5)
# array([[ 0,  1,  2,  3,  4],
#        [ 5,  6,  7,  8,  9],
#        [10, 11, 12, 13, 14],
#        [15, 16, 17, 18, 19]])

# Basic indexing (returns VIEWS - no copy!)
arr[0]          # first row: [0, 1, 2, 3, 4]
arr[1, 3]       # element at row 1, col 3: 8
arr[:2, 1:4]    # rows 0-1, cols 1-3

# IMPORTANT: Slices are views, not copies!
view = arr[0:2]
view[0, 0] = 999   # This modifies arr too!
copy = arr[0:2].copy()  # Use .copy() for independent data
```

## 2. Broadcasting Rules

Broadcasting allows NumPy to operate on arrays of different shapes without copying data.

```
Rules (applied right-to-left on dimensions):
1. If arrays differ in ndim, prepend 1s to the smaller shape
2. Dimensions of size 1 are stretched to match the other
3. If dimensions differ and neither is 1 → ERROR

Examples:
  (3, 4) + (4,)     → (3, 4) + (1, 4) → (3, 4)  ✓
  (3, 4) + (3, 1)   → (3, 4)                      ✓
  (3, 4) + (3,)     → (3, 4) + (1, 3) → ERROR     ✗ (4≠3)
  (2, 1, 3) + (4, 3) → (2, 1, 3) + (1, 4, 3) → (2, 4, 3) ✓
```

```
Visual: Adding (3,4) array + (4,) array

    Array A (3,4)          Array B (4,)         Result (3,4)
  ┌─────────────┐        ┌─────────┐         ┌─────────────┐
  │ a b c d     │   +    │ w x y z │    =    │a+w b+x c+y d+z│
  │ e f g h     │        │(broadcast│         │e+w f+x g+y h+z│
  │ i j k l     │        │ to 3 rows)│        │i+w j+x k+y l+z│
  └─────────────┘        └─────────┘         └─────────────┘
```

```python
# Practical broadcasting examples
A = np.array([[1, 2, 3],
              [4, 5, 6]])           # shape (2, 3)

# Subtract column means (center each column)
col_means = A.mean(axis=0)          # shape (3,)
centered = A - col_means            # broadcasts (3,) across rows

# Subtract row means (center each row)
row_means = A.mean(axis=1, keepdims=True)  # shape (2, 1) - keepdims!
centered_rows = A - row_means              # broadcasts (2,1) across cols

# Outer product via broadcasting
x = np.array([1, 2, 3])[:, np.newaxis]  # (3, 1)
y = np.array([4, 5, 6])[np.newaxis, :]  # (1, 3)
outer = x * y                            # (3, 3)
```

## 3. Vectorized Operations vs Loops

```python
import time

n = 1_000_000
a = np.random.randn(n)
b = np.random.randn(n)

# BAD: Python loop
start = time.time()
result_loop = np.empty(n)
for i in range(n):
    result_loop[i] = a[i] + b[i]
print(f"Loop: {time.time() - start:.4f}s")  # ~0.3-0.5s

# GOOD: Vectorized
start = time.time()
result_vec = a + b
print(f"Vectorized: {time.time() - start:.4f}s")  # ~0.001s

# Speedup: 100-500x!
```

```python
# Common vectorized operations
arr = np.random.randn(1000, 1000)

# Element-wise math
np.exp(arr)
np.log(np.abs(arr))
np.sqrt(np.abs(arr))
np.clip(arr, -1, 1)

# Aggregations
arr.sum(axis=0)       # column sums
arr.mean(axis=1)      # row means
arr.std()             # global std
arr.min(), arr.max()
np.percentile(arr, [25, 50, 75])

# Conditional (replaces if/else loops)
np.where(arr > 0, arr, 0)           # ReLU!
np.where(arr > 0, 'positive', 'negative')
```

## 4. Linear Algebra with NumPy

```python
from numpy import linalg as LA

A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])

# Matrix multiplication
C = A @ B                    # preferred syntax (Python 3.5+)
C = np.dot(A, B)            # equivalent
C = np.matmul(A, B)         # equivalent

# Key operations
det = LA.det(A)              # determinant
inv = LA.inv(A)              # inverse
rank = LA.matrix_rank(A)     # rank

# Eigenvalues and eigenvectors
eigenvalues, eigenvectors = LA.eig(A)

# Singular Value Decomposition (crucial for ML!)
U, S, Vt = LA.svd(A)
# A = U @ np.diag(S) @ Vt

# Solving linear systems: Ax = b
b = np.array([1, 2])
x = LA.solve(A, b)          # faster than inv(A) @ b

# Norms
LA.norm(A)            # Frobenius norm (default)
LA.norm(A, ord=1)     # L1 norm
LA.norm(A, ord=np.inf)  # infinity norm
LA.norm(b, ord=2)     # L2 vector norm (Euclidean distance)

# Practical: Cosine similarity
def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (LA.norm(v1) * LA.norm(v2))
```

## 5. Random Number Generation

```python
# Modern API (NumPy >= 1.17) - preferred
rng = np.random.default_rng(seed=42)  # reproducible

# Distributions
uniform = rng.uniform(0, 1, size=(3, 4))       # Uniform [0, 1)
normal = rng.normal(loc=0, scale=1, size=1000)  # Gaussian
integers = rng.integers(0, 10, size=20)         # discrete
choice = rng.choice(['a', 'b', 'c'], size=5, replace=True)

# ML-relevant distributions
binomial = rng.binomial(n=10, p=0.5, size=1000)   # coin flips
poisson = rng.poisson(lam=5, size=1000)            # event counts
exponential = rng.exponential(scale=1.0, size=1000) # waiting times

# Shuffling and sampling
arr = np.arange(100)
rng.shuffle(arr)                                    # in-place
sample = rng.choice(arr, size=10, replace=False)    # without replacement

# PITFALL: Legacy API (still common in tutorials)
# np.random.seed(42)     ← global state, not thread-safe
# np.random.randn(3, 4)  ← use rng.standard_normal((3,4)) instead
```

## 6. Memory Layout

```
C-order (row-major, default):         F-order (column-major):
Memory: [a00, a01, a02, a10, a11...]  Memory: [a00, a10, a20, a01, a11...]

┌───┬───┬───┐                         ┌───┬───┬───┐
│ 1 → 2 → 3 │ (contiguous in memory)  │ 1 │ 4 │ 7 │
├───┼───┼───┤                         │ ↓ │ ↓ │ ↓ │
│ 4 → 5 → 6 │                         │ 2 │ 5 │ 8 │
└───┴───┴───┘                         │ ↓ │ ↓ │ ↓ │
                                       │ 3 │ 6 │ 9 │
                                       └───┴───┴───┘
```

```python
# C-order (default) - row operations are fast
c_arr = np.array([[1, 2, 3], [4, 5, 6]], order='C')
print(c_arr.flags['C_CONTIGUOUS'])  # True

# F-order - column operations are fast (Fortran, MATLAB style)
f_arr = np.array([[1, 2, 3], [4, 5, 6]], order='F')
print(f_arr.flags['F_CONTIGUOUS'])  # True

# Performance implication: iterate over contiguous dimension
big = np.random.randn(10000, 10000)
%timeit big.sum(axis=1)  # Fast (summing along rows, C-contiguous)
%timeit big.sum(axis=0)  # Slower (summing along cols, not contiguous)

# Reshaping and contiguity
a = np.arange(12).reshape(3, 4)       # view, still C-contiguous
b = a.T                                 # transpose is a VIEW, not contiguous
c = np.ascontiguousarray(b)            # force contiguous copy
```

## 7. Advanced Indexing

```python
arr = np.arange(20).reshape(4, 5)

# Fancy indexing (integer array indexing) - returns COPY
rows = np.array([0, 2, 3])
cols = np.array([1, 3, 4])
arr[rows, cols]          # elements at (0,1), (2,3), (3,4) → [1, 13, 19]
arr[rows]                # rows 0, 2, 3 (full rows)
arr[:, cols]             # columns 1, 3, 4

# Boolean masking - the bread and butter of data filtering
data = np.random.randn(1000)
positives = data[data > 0]              # all positive values
outliers = data[np.abs(data) > 2]       # values beyond 2 std

# Combining conditions (use & | ~, NOT and/or/not)
mask = (data > -1) & (data < 1)         # within 1 std
filtered = data[mask]

# np.where for conditional selection
labels = np.where(data > 0, 1, 0)       # binary classification labels

# Advanced: np.ix_ for cross-indexing
rows_ix = np.array([0, 2])
cols_ix = np.array([1, 3, 4])
submatrix = arr[np.ix_(rows_ix, cols_ix)]  # 2x3 submatrix

# Practical: Top-k indices
scores = np.random.randn(100)
top_5_idx = np.argsort(scores)[-5:][::-1]  # indices of 5 largest
top_5_values = scores[top_5_idx]
```

## 8. Structured Arrays

```python
# Structured arrays - heterogeneous data in NumPy (like a mini-DataFrame)
dt = np.dtype([
    ('name', 'U20'),
    ('age', 'i4'),
    ('salary', 'f8')
])

employees = np.array([
    ('Alice', 30, 75000.0),
    ('Bob', 25, 65000.0),
    ('Charlie', 35, 85000.0)
], dtype=dt)

# Access by field name
print(employees['name'])     # ['Alice', 'Bob', 'Charlie']
print(employees['salary'].mean())  # 75000.0

# Filter
senior = employees[employees['age'] > 28]

# Record arrays (attribute access)
rec = employees.view(np.recarray)
print(rec.name)   # attribute-style access
```

## 9. Performance Tips and Common Pitfalls

```python
# TIP 1: Pre-allocate arrays instead of growing them
# BAD
result = []
for i in range(10000):
    result.append(i ** 2)
result = np.array(result)

# GOOD
result = np.empty(10000)
for i in range(10000):  # still bad, but better than append
    result[i] = i ** 2

# BEST
result = np.arange(10000) ** 2

# TIP 2: Use appropriate dtypes
big_arr = np.zeros(1_000_000, dtype=np.float64)  # 8MB
small_arr = np.zeros(1_000_000, dtype=np.float32)  # 4MB  (often sufficient for ML)

# TIP 3: Avoid unnecessary copies
a = np.arange(1000000)
b = a[::2]          # view - no memory cost
c = a[::2].copy()   # copy - allocates new memory

# TIP 4: Use einsum for complex tensor operations
# Matrix multiply: C_ij = sum_k A_ik * B_kj
A = np.random.randn(100, 200)
B = np.random.randn(200, 300)
C = np.einsum('ik,kj->ij', A, B)  # equivalent to A @ B but more flexible

# Batch matrix multiply
batch_A = np.random.randn(32, 4, 4)  # 32 matrices of 4x4
batch_B = np.random.randn(32, 4, 4)
batch_C = np.einsum('bij,bjk->bik', batch_A, batch_B)

# TIP 5: Use np.add, np.multiply with `out` parameter to avoid temporaries
a = np.random.randn(10_000_000)
b = np.random.randn(10_000_000)
out = np.empty_like(a)
np.add(a, b, out=out)  # no temporary allocation
```

### Common Pitfalls

```python
# PITFALL 1: Integer overflow
a = np.array([200, 200], dtype=np.int8)  # max 127!
print(a + a)  # [-112, -112]  ← overflow! Use int32/int64

# PITFALL 2: View vs Copy confusion
original = np.array([1, 2, 3, 4, 5])
sliced = original[1:4]   # VIEW
sliced[0] = 99           # modifies original!

# PITFALL 3: Floating point comparison
a = 0.1 + 0.2
print(a == 0.3)                    # False!
print(np.isclose(a, 0.3))         # True
print(np.allclose([a], [0.3]))    # True

# PITFALL 4: Chained indexing in assignment (doesn't work reliably)
arr = np.zeros((3, 3))
# arr[arr > 0][0] = 1   # May not modify arr!
mask = arr > 0
arr[mask] = 1            # This works

# PITFALL 5: axis confusion
data = np.random.randn(100, 5)  # 100 samples, 5 features
col_means = data.mean(axis=0)   # shape (5,) - mean of each COLUMN
row_means = data.mean(axis=1)   # shape (100,) - mean of each ROW
# axis=0 collapses rows, axis=1 collapses columns
```

## 10. Production Considerations

```python
# Saving/Loading arrays efficiently
np.save('array.npy', arr)              # single array (binary)
np.savez('arrays.npz', a=a, b=b)      # multiple arrays
np.savez_compressed('compressed.npz', a=a)  # compressed

loaded = np.load('array.npy')
data = np.load('arrays.npz')
a_loaded = data['a']

# Memory-mapped files for arrays larger than RAM
mmap = np.memmap('large_data.dat', dtype='float32', mode='r', shape=(1000000, 100))
# Access like normal array but only loads needed pages from disk

# Thread safety: NumPy releases the GIL for many operations
# This means NumPy + threading can give real parallelism
from concurrent.futures import ThreadPoolExecutor
chunks = np.array_split(big_array, 4)
with ThreadPoolExecutor(4) as ex:
    results = list(ex.map(np.sort, chunks))
```
