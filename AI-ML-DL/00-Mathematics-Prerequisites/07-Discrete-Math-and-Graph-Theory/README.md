# Discrete Mathematics and Graph Theory for ML

## 1. Set Theory Essentials

### Basic Definitions

A **set** is an unordered collection of distinct elements.

```
A = {1, 2, 3, 4, 5}
B = {3, 4, 5, 6, 7}
∅ = {} (empty set)
```

**Subset**: A ⊆ B means every element of A is in B.

### Set Operations

```
Union:        A ∪ B = {1, 2, 3, 4, 5, 6, 7}
Intersection: A ∩ B = {3, 4, 5}
Complement:   A^c = U \ A (everything in universe not in A)
Difference:   A \ B = {1, 2}
Sym. Diff:    A △ B = {1, 2, 6, 7}
```

### Cartesian Product

A × B = {(a, b) | a ∈ A, b ∈ B}

If |A| = m, |B| = n → |A × B| = m × n

### Why It Matters for ML

| Concept | ML Application |
|---------|---------------|
| Feature space | X = ℝ^d (Cartesian product of ℝ with itself d times) |
| Hypothesis class | H = {h: X → Y} is a set of functions |
| Sample space | S = {(x₁,y₁),...,(xₙ,yₙ)} ⊆ X × Y |
| Power set | P(features) = all possible feature subsets (2^d options) |
| Partition | Clustering divides data into disjoint subsets |

```python
# Feature selection: iterating over subsets
from itertools import combinations

features = ['age', 'income', 'education', 'location']
# All possible feature subsets of size 2
for subset in combinations(features, 2):
    print(subset)
# ('age', 'income'), ('age', 'education'), ... → C(4,2) = 6 subsets
```

---

## 2. Combinatorics

### Permutations and Combinations

**Permutation** (order matters): P(n, k) = n! / (n-k)!
**Combination** (order doesn't matter): C(n, k) = n! / (k!(n-k)!)

### Binomial Coefficients

C(n, k) = (n choose k) = coefficient of x^k in (1+x)^n

Properties:
- C(n, k) = C(n, n-k)  (symmetry)
- C(n, 0) + C(n, 1) + ... + C(n, n) = 2^n  (sum of all subsets)
- C(n, k) = C(n-1, k-1) + C(n-1, k)  (Pascal's rule)

### Counting Arguments in ML

**Number of possible decision trees:**
- Binary features: d features, depth h
- Number of internal nodes: 2^h - 1
- Each node picks 1 of d features → d^(2^h - 1) possible trees
- Exponential explosion → need pruning/regularization!

**VC Dimension calculations:**
- A set of n points can be labeled in 2^n ways
- VC dim = largest n such that hypothesis class can shatter n points
- Linear classifiers in ℝ^d: VC dim = d + 1

**Feature selection:**
- d features → 2^d possible subsets
- d = 20 → 1,048,576 subsets (brute force feasible)
- d = 100 → 2^100 ≈ 10^30 subsets (need heuristics!)

### Pigeonhole Principle

If n items go into m boxes and n > m, at least one box has ≥2 items.

**ML application**: Hash collisions in locality-sensitive hashing (LSH).
If you map n points to m buckets where n > m, collisions are guaranteed.

```python
import math

def count_combinations(n, k):
    """Number of ways to choose k items from n"""
    return math.comb(n, k)

# Feature selection search space
d = 50  # features
for k in range(1, 6):
    print(f"Subsets of size {k}: {count_combinations(d, k):,}")
# size 1: 50 | size 2: 1,225 | size 3: 19,600 | size 4: 230,300 | size 5: 2,118,760
```

---

## 3. Graph Fundamentals

### Basic Definitions

```
Undirected Graph:          Directed Graph (Digraph):

    A --- B                    A --> B
    |   / |                    |   ↗ |
    |  /  |                    |  /  |
    | /   |                    ↓ /   ↓
    C --- D                    C --> D
```

- **Vertex (node)**: Entity in the graph
- **Edge (link)**: Connection between two vertices
- **Degree**: Number of edges incident to a vertex
- **In-degree/Out-degree**: For directed graphs, incoming/outgoing edges

### Representations

**Adjacency Matrix** (good for dense graphs, matrix operations):
```
     A  B  C  D
A [  0  1  1  0 ]
B [  1  0  1  1 ]
C [  1  1  0  1 ]
D [  0  1  1  0 ]
```
Space: O(V²) | Edge lookup: O(1) | Great for spectral methods

**Adjacency List** (good for sparse graphs):
```
A: [B, C]
B: [A, C, D]
C: [A, B, D]
D: [B, C]
```
Space: O(V + E) | Iteration over neighbors: O(degree)

### Weighted Graphs

```
    A --5-- B
    |      /|
    3    2  4
    |  /    |
    C --1-- D

Adjacency matrix (weighted):
     A    B    C    D
A [  0    5    3    ∞ ]
B [  5    0    2    4 ]
C [  3    2    0    1 ]
D [  ∞    4    1    0 ]
```

### Paths, Cycles, Connectivity

- **Path**: Sequence of vertices connected by edges
- **Cycle**: Path that starts and ends at same vertex
- **Connected**: Path exists between every pair of vertices
- **DAG**: Directed Acyclic Graph (no cycles) → computation graphs!

### Bipartite Graphs

```
Users          Items
  U1 ----+---- I1
  U2 --+ +---- I2
  U3 --+-+---- I3
        +------ I4

No edges within the same partition!
Used in: Recommendation systems, matching problems
```

```python
import numpy as np

class Graph:
    """Simple graph with adjacency matrix and list representations"""
    def __init__(self, n_vertices, directed=False):
        self.n = n_vertices
        self.directed = directed
        self.adj_matrix = np.zeros((n, n))
        self.adj_list = {i: [] for i in range(n)}

    def add_edge(self, u, v, weight=1):
        self.adj_matrix[u][v] = weight
        self.adj_list[u].append((v, weight))
        if not self.directed:
            self.adj_matrix[v][u] = weight
            self.adj_list[v].append((u, weight))

    def degree(self, v):
        return len(self.adj_list[v])
```

---

## 4. Graph Algorithms

### BFS (Breadth-First Search)

Explores level by level. Finds shortest path in unweighted graphs.

```
Pseudocode:
  BFS(graph, start):
    queue = [start]
    visited = {start}
    while queue not empty:
      node = queue.pop_front()
      for neighbor in graph[node]:
        if neighbor not in visited:
          visited.add(neighbor)
          queue.append(neighbor)
```

```python
from collections import deque

def bfs(adj_list, start):
    """BFS returning distances from start node"""
    visited = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor, _ in adj_list[node]:
            if neighbor not in visited:
                visited[neighbor] = visited[node] + 1
                queue.append(neighbor)
    return visited
```

### DFS (Depth-First Search)

Explores as deep as possible before backtracking. Used for topological sort, cycle detection.

```python
def dfs(adj_list, start):
    """DFS with discovery and finish times (useful for topological sort)"""
    visited = set()
    order = []

    def _dfs(node):
        visited.add(node)
        for neighbor, _ in adj_list[node]:
            if neighbor not in visited:
                _dfs(neighbor)
        order.append(node)  # post-order

    _dfs(start)
    return order
```

### Dijkstra's Shortest Path

```
Pseudocode:
  Dijkstra(graph, source):
    dist[source] = 0, dist[all others] = ∞
    priority_queue = [(0, source)]
    while pq not empty:
      d, u = pq.pop_min()
      for each neighbor v of u:
        if dist[u] + weight(u,v) < dist[v]:
          dist[v] = dist[u] + weight(u,v)
          pq.push((dist[v], v))
    return dist
```

Time: O((V + E) log V) with binary heap

### Topological Sort (Critical for ML!)

Only works on DAGs. Orders vertices so all edges go "forward."

**ML connection**: Neural network computation graphs are DAGs!
- Forward pass: topological order
- Backward pass: reverse topological order

```python
def topological_sort(adj_list, n_vertices):
    """Kahn's algorithm: BFS-based topological sort"""
    in_degree = [0] * n_vertices
    for u in adj_list:
        for v, _ in adj_list[u]:
            in_degree[v] += 1

    queue = deque([v for v in range(n_vertices) if in_degree[v] == 0])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor, _ in adj_list[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order if len(order) == n_vertices else None  # None = cycle exists
```

### PageRank Algorithm

The eigenvalue connection! PageRank finds the dominant eigenvector of the transition matrix.

```
PR(page) = (1-d)/N + d * Σ PR(linking_page) / out_degree(linking_page)

Where d ≈ 0.85 (damping factor), N = total pages
```

```python
import numpy as np

def pagerank(adj_matrix, damping=0.85, max_iter=100, tol=1e-6):
    """PageRank via power iteration (finding dominant eigenvector)"""
    n = adj_matrix.shape[0]
    # Build transition matrix
    out_degree = adj_matrix.sum(axis=1)
    out_degree[out_degree == 0] = 1  # handle dangling nodes
    M = adj_matrix / out_degree[:, np.newaxis]

    # Power iteration
    rank = np.ones(n) / n
    for _ in range(max_iter):
        new_rank = (1 - damping) / n + damping * M.T @ rank
        if np.abs(new_rank - rank).sum() < tol:
            break
        rank = new_rank
    return rank / rank.sum()
```

---

## 5. Graphs in Machine Learning

### Computation Graphs

```
Forward Pass (topological order):

  x ──→ [Linear: W₁x+b₁] ──→ h ──→ [ReLU] ──→ a ──→ [Linear: W₂a+b₂] ──→ ŷ ──→ [Loss] ──→ L

Backward Pass (reverse topological order):

  ∂L/∂ŷ ←── ∂L/∂a ←── ∂L/∂h ←── ∂L/∂x
     ↓          ↓          ↓
  ∂L/∂W₂    ∂L/∂W₁    (input, no grad needed)
  ∂L/∂b₂    ∂L/∂b₁
```

### Bayesian Networks (Directed Graphical Models)

```
  Rain ──→ Sprinkler
    |            |
    ↓            ↓
  Wet Grass ←───┘

DAG encodes conditional independence:
P(R, S, W) = P(R) · P(S|R) · P(W|R,S)
```

### Markov Random Fields (Undirected Graphical Models)

```
  X₁ ─── X₂ ─── X₃
  |       |       |
  X₄ ─── X₅ ─── X₆

Used in: Image segmentation (pixels as nodes, edges to neighbors)
Each node conditioned only on its neighbors (Markov blanket)
```

### Attention as Graph Operation

```
Transformer Self-Attention = GNN on Fully Connected Graph:

  Token₁ ←──→ Token₂ ←──→ Token₃ ←──→ Token₄
    ↕      ╲   ↕    ╱  ╲   ↕    ╱      ↕
    └────────╲──┼───╱────╲──┼───╱────────┘
              ╲ ↕  ╱      ╲ ↕  ╱
               every token attends to every other token

  Attention(Q, K, V) = softmax(QK^T / √d_k) V
                      = weighted message passing on complete graph
  Edge weight from i→j = softmax(q_i · k_j / √d_k)
  Message from j to i  = weight_ij * v_j
```

### Graph Neural Networks (Message Passing)

```python
def gnn_layer(node_features, adj_matrix, W_msg, W_update):
    """One layer of message-passing GNN"""
    # Aggregate messages from neighbors
    messages = adj_matrix @ node_features @ W_msg  # sum of neighbor features
    # Update node representations
    updated = np.tanh(node_features @ W_update + messages)
    return updated
```

### Knowledge Graphs

```
(Einstein) ──born_in──→ (Germany)
(Einstein) ──field──→ (Physics)
(Einstein) ──won──→ (Nobel Prize)

Triple: (subject, relation, object)
Embedding methods: TransE, RotatE, ComplEx
```

---

## 6. Spectral Graph Theory

### Graph Laplacian

```
Adjacency Matrix A:        Degree Matrix D:        Laplacian L = D - A:
[0 1 1 0]                  [2 0 0 0]              [ 2 -1 -1  0]
[1 0 1 1]                  [0 3 0 0]              [-1  3 -1 -1]
[1 1 0 1]                  [0 0 3 0]              [-1 -1  3 -1]
[0 1 1 0]                  [0 0 0 2]              [ 0 -1 -1  2]
```

**Properties of L:**
- Symmetric, positive semi-definite
- Smallest eigenvalue = 0 (eigenvector = all-ones)
- Number of zero eigenvalues = number of connected components
- Second smallest eigenvalue (Fiedler value) = algebraic connectivity

### Spectral Clustering

```python
import numpy as np
from scipy.linalg import eigh

def spectral_clustering(adj_matrix, k):
    """Spectral clustering using normalized Laplacian"""
    n = adj_matrix.shape[0]
    # Compute degree matrix
    D = np.diag(adj_matrix.sum(axis=1))
    # Normalized Laplacian: L_norm = I - D^{-1/2} A D^{-1/2}
    D_inv_sqrt = np.diag(1.0 / np.sqrt(np.diag(D) + 1e-10))
    L_norm = np.eye(n) - D_inv_sqrt @ adj_matrix @ D_inv_sqrt

    # Get k smallest eigenvectors
    eigenvalues, eigenvectors = eigh(L_norm)
    features = eigenvectors[:, :k]  # first k eigenvectors

    # Normalize rows
    norms = np.linalg.norm(features, axis=1, keepdims=True) + 1e-10
    features = features / norms

    # K-means on spectral embedding (simplified: just return features)
    return features  # Apply k-means on these features
```

### Connection to GCN

Graph Convolutional Network layer:
```
H^(l+1) = σ(D̃^{-1/2} Ã D̃^{-1/2} H^(l) W^(l))

Where Ã = A + I (add self-loops), D̃ = degree matrix of Ã
This is a first-order approximation of spectral graph convolution!
```

---

## 7. Trees and Their Role in ML

### Decision Trees

```
             [Age > 30?]
            /            \
       Yes /              \ No
          /                \
   [Income > 50k?]      [Student?]
    /          \          /       \
  Yes          No       Yes       No
   ↓            ↓        ↓         ↓
 Buy         Don't    Buy       Don't
```

### KD-Trees (for Nearest Neighbor)

```
Split alternating dimensions:

         (7,2)          ← split on x
        /     \
    (5,4)     (9,6)     ← split on y
    /   \       \
 (2,3) (4,7)  (8,1)    ← split on x

Query: find nearest neighbor to (6,5)
- Prune entire subtrees that can't contain closer points
- O(log n) average case vs O(n) brute force
```

### Huffman Coding (Connection to BPE Tokenization)

```
Characters: A(45%) B(13%) C(12%) D(16%) E(9%) F(5%)

Huffman Tree:
            (100)
           /     \
        (55)    A(45)
        /   \
     (25)  (30)
     / \   / \
   C  B  D (14)
            / \
           F   E

Codes: A=0, C=100, B=101, D=110, F=1110, E=1111
BPE similarly builds a tree of token merges!
```

### Random Forests

```
    Tree₁          Tree₂          Tree₃
     /\             /\             /\
    /  \           /  \           /  \
   /\   L         L   /\        /\   /\
  L  L               L  L      L  L L  L

Final prediction = majority vote (classification) or average (regression)
Each tree trained on bootstrap sample + random feature subset
```

---

## 8. Exercises

### Exercise 1: Set Operations
Given A = {1,2,3,4,5}, B = {3,4,5,6,7}, C = {5,6,7,8,9}.
Find: (A ∪ B) ∩ C, A \ (B ∩ C), |P(A ∩ B)|

**Solution**: A ∪ B = {1..7}, (A ∪ B) ∩ C = {5,6,7}. B ∩ C = {5,6,7}, A \ {5,6,7} = {1,2,3,4}. A ∩ B = {3,4,5}, |P(A ∩ B)| = 2³ = 8.

### Exercise 2: Counting Decision Trees
With 4 binary features, how many distinct depth-2 decision trees exist (considering feature choice at each node)?

**Solution**: Root: 4 choices. Each of 2 children: 3 remaining choices. Each of 4 leaves: 2 label choices. Total = 4 × 3 × 3 × 2⁴ = 576. (Simplified; exact count depends on constraints.)

### Exercise 3: Implement BFS
Write BFS to find connected components of an undirected graph.

**Solution**:
```python
def connected_components(adj_list, n):
    visited = set()
    components = []
    for start in range(n):
        if start not in visited:
            component = []
            queue = deque([start])
            visited.add(start)
            while queue:
                node = queue.popleft()
                component.append(node)
                for neighbor, _ in adj_list[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    return components
```

### Exercise 4: Topological Sort
Given computation graph: Input→Linear₁→ReLU→Linear₂→Loss. Add a skip connection from Input→Linear₂. Give a valid topological ordering.

**Solution**: Input, Linear₁, ReLU, Linear₂, Loss. (Skip connection doesn't change valid orderings since Input already comes first.)

### Exercise 5: PageRank
For graph A→B, B→C, C→A, B→A with damping=0.85, compute one iteration of PageRank starting from uniform [1/3, 1/3, 1/3].

**Solution**: Out-degrees: A=1, B=2, C=1. PR(A) = 0.15/3 + 0.85*(PR(B)/2 + PR(C)/1) = 0.05 + 0.85*(1/6 + 1/3) = 0.05 + 0.425 = 0.475. Similarly for B and C.

### Exercise 6: Graph Laplacian
Compute the Laplacian for a triangle graph (3 nodes, all connected). Find its eigenvalues.

**Solution**: A = [[0,1,1],[1,0,1],[1,1,0]], D = diag(2,2,2), L = [[2,-1,-1],[-1,2,-1],[-1,-1,2]]. Eigenvalues: 0, 3, 3.

### Exercise 7: Spectral Clustering
Why does the second eigenvector of the Laplacian give a good 2-way partition?

**Solution**: The Fiedler vector (2nd eigenvector) minimizes the ratio cut objective. Nodes with same sign tend to be densely connected. The eigenvector solves a relaxed version of the NP-hard min-cut problem.

### Exercise 8: VC Dimension
What is the VC dimension of the set of all circles in 2D?

**Solution**: VC dim = 3. Can shatter 3 non-collinear points (draw circle to include/exclude any subset). Cannot shatter 4 points (if 3 form a triangle with 4th inside, cannot label inside point + and all others -).

### Exercise 9: KD-Tree Query
Build a KD-tree from points (2,3), (5,4), (9,6), (4,7), (8,1), (7,2). Find the nearest neighbor to (6,5).

**Solution**: Build tree splitting alternately on x/y. Root=(7,2) splits on x. Query (6,5): go left (x<7). Check (5,4), distance=√2. Backtrack and check right subtree. (9,6) distance=√10 > √2. Answer: (5,4).

### Exercise 10: Message Passing
Given a 3-node graph (triangle) with features [1,0], [0,1], [1,1]. Perform one round of sum-aggregation message passing (no learned weights, just sum neighbors).

**Solution**: Node 0 gets messages from 1,2: [0,1]+[1,1]=[1,2]. New feature: [1,0]+[1,2]=[2,2]. Node 1: [1,0]+[1,1]+[0,1]=[2,2]. Node 2: [1,0]+[0,1]+[1,1]=[2,2]. All nodes get [2,2] (symmetric graph + features sum to same thing).

---

## 9. Interview Questions

**Q1**: How would you detect cycles in a directed graph? Why does this matter for neural network architectures?

**A**: Use DFS with 3 states (white/gray/black). A back edge (to gray node) indicates a cycle. Matters because computation graphs must be DAGs for standard backprop. RNNs "unroll" to avoid actual cycles.

**Q2**: Explain the connection between PageRank and eigenvalues.

**A**: PageRank computes the stationary distribution of a random walk, which is the dominant eigenvector of the transition matrix. Power iteration converges to this eigenvector. Convergence rate depends on the spectral gap (ratio of 1st to 2nd eigenvalue).

**Q3**: Why is the adjacency matrix representation preferred for GNNs over adjacency lists?

**A**: GNN operations (message passing) are matrix multiplications: H' = AHW. Sparse matrix multiplication is well-optimized on GPUs. Adjacency lists don't vectorize well for batch processing.

**Q4**: How does the attention mechanism relate to graphs?

**A**: Self-attention computes a weighted fully-connected graph where edge weights are attention scores. Each token aggregates information from all others weighted by compatibility (dot product of Q and K). This is exactly message passing on a complete graph with learned edge weights.

**Q5**: What's the time complexity of training a GNN with L layers on a graph with V nodes and E edges?

**A**: O(L × (E × d + V × d²)) where d = hidden dimension. E×d for message aggregation (sparse matmul), V×d² for feature transformation. With adjacency matrix: O(L × V² × d) which is expensive for large graphs → need sampling (GraphSAGE) or subgraph methods.

**Q6**: How would you represent a transformer's computation as a graph?

**A**: The full transformer is a DAG (computation graph). Within self-attention, it's a complete bipartite-like graph between queries and keys. Multi-head = multiple parallel complete graphs. Cross-attention = bipartite graph between encoder and decoder tokens.

**Q7**: Explain how decision trees relate to axis-aligned hyperplane partitions.

**A**: Each internal node splits the feature space with an axis-aligned hyperplane (threshold on one feature). The tree partitions ℝ^d into axis-aligned rectangles (leaf regions). This limits expressiveness compared to oblique splits but enables fast inference O(depth).

**Q8**: Why is spectral clustering sometimes preferred over k-means?

**A**: K-means assumes convex, spherical clusters. Spectral clustering can find non-convex clusters by operating in the eigenvector space of the Laplacian. It effectively performs dimensionality reduction that respects graph structure before clustering. Works well for community detection in networks.
