# 19. Union-Find (Disjoint Set Union) Patterns

## Decision Flowchart

```
Need to group/connect elements dynamically?
│
├─ Are queries about connectivity between pairs? ─── YES ──→ Union-Find
│
├─ Need to detect cycles in undirected graph? ─── YES ──→ Union-Find
│
├─ Need to count/track connected components? 
│   ├─ Static graph (built once) ──→ DFS/BFS simpler
│   └─ Dynamic (edges added online) ──→ Union-Find
│
├─ Need shortest path / distances? ──→ BFS/Dijkstra (NOT UF)
│
├─ Need to traverse/enumerate all nodes in component? ──→ DFS/BFS
│
└─ Need to merge equivalence classes? ──→ Union-Find
```

## When to Use Union-Find vs DFS/BFS

| Criteria | Union-Find | DFS/BFS |
|----------|-----------|---------|
| Dynamic edge additions | Optimal | Rebuild each time |
| Cycle detection (undirected) | O(α(n)) per edge | O(V+E) full traversal |
| Connected component count | Maintained incrementally | O(V+E) each query |
| Path/distance queries | Cannot do | Natural fit |
| Enumerate component members | Needs extra structure | Natural fit |
| Weighted relationships (a/b=k) | Weighted UF | DFS on graph |
| Space complexity | O(n) | O(V+E) adjacency list |
| Implementation complexity | Simple class | Recursion/queue |

---

## Pattern 1: Basic Union-Find Template

### Signal
- "Are X and Y connected?"
- "Group elements together"
- Dynamic equivalence relations

### Template (Java)

```java
class UnionFind {
    private int[] parent;
    private int[] rank;
    private int components;

    public UnionFind(int n) {
        parent = new int[n];
        rank = new int[n];
        components = n;
        for (int i = 0; i < n; i++) {
            parent[i] = i;  // each element is its own root
            rank[i] = 0;
        }
    }

    // Path compression: point every node on path directly to root
    public int find(int x) {
        if (parent[x] != x) {
            parent[x] = find(parent[x]);  // recursive path compression
        }
        return parent[x];
    }

    // Union by rank: attach shorter tree under taller tree
    public boolean union(int x, int y) {
        int rootX = find(x);
        int rootY = find(y);
        if (rootX == rootY) return false;  // already connected

        if (rank[rootX] < rank[rootY]) {
            parent[rootX] = rootY;
        } else if (rank[rootX] > rank[rootY]) {
            parent[rootY] = rootX;
        } else {
            parent[rootY] = rootX;
            rank[rootX]++;
        }
        components--;
        return true;
    }

    public boolean connected(int x, int y) {
        return find(x) == find(y);
    }

    public int getComponents() {
        return components;
    }
}
```

### Visualization: Union + Path Compression

```
Initial: each node is its own parent
parent: [0, 1, 2, 3, 4, 5, 6]

Step 1: union(1, 2)
    0  1  3  4  5  6       parent: [0, 1, 2, 3, 4, 5, 6]
       |                            [0, 1, 1, 3, 4, 5, 6]
       2                   rank:   [0, 1, 0, 0, 0, 0, 0]

Step 2: union(3, 4)
    0  1  3  5  6          parent: [0, 1, 1, 3, 4, 5, 6]
       |  |                         [0, 1, 1, 3, 3, 5, 6]
       2  4

Step 3: union(2, 4) → find(2)=1, find(4)=3 → union roots 1,3
    0    1    5  6          parent: [0, 1, 1, 1, 3, 5, 6]
        /|                  rank:   [0, 2, 0, 1, 0, 0, 0]
       3  2                 (rank[1]=2 > rank[3]=1, so 3→1)
       |
       4

Step 4: find(4) with path compression
    Before: 4→3→1 (two hops)
    After:  4→1   (one hop, parent[4] = 1)

    0    1     5  6         parent: [0, 1, 1, 1, 1, 5, 6]
       / | \
      3  2  4              All children point directly to root!
```

### Complexity

| Operation | Without optimization | Path compression only | Union by rank only | Both |
|-----------|---------------------|----------------------|-------------------|------|
| find | O(n) | O(log n) amortized | O(log n) | O(α(n)) |
| union | O(n) | O(log n) amortized | O(log n) | O(α(n)) |
| Space | O(n) | O(n) | O(n) | O(n) |

**α(n) = inverse Ackermann function ≈ constant (≤ 4 for all practical n < 10^80)**

---

## Pattern 2: Connected Components Counting

### Signal
- "Number of connected components"
- "Is the graph a valid tree?" (connected + no cycle → n nodes, n-1 edges, 1 component)

### Template

```java
// LC 323: Number of Connected Components in Undirected Graph
public int countComponents(int n, int[][] edges) {
    UnionFind uf = new UnionFind(n);
    for (int[] edge : edges) {
        uf.union(edge[0], edge[1]);
    }
    return uf.getComponents();
}

// LC 261: Graph Valid Tree
// A valid tree: n nodes, n-1 edges, fully connected (1 component), no cycles
public boolean validTree(int n, int[][] edges) {
    if (edges.length != n - 1) return false;  // quick check
    UnionFind uf = new UnionFind(n);
    for (int[] edge : edges) {
        if (!uf.union(edge[0], edge[1])) return false;  // cycle detected
    }
    return uf.getComponents() == 1;
}
```

---

## Pattern 3: Cycle Detection in Undirected Graph

### Signal
- "Find the redundant edge" / "Remove one edge to make a tree"
- "Does adding this edge create a cycle?"

### Template

```java
// LC 684: Redundant Connection
// Find the edge that, if removed, makes the graph a tree
public int[] findRedundantConnection(int[][] edges) {
    int n = edges.length;
    UnionFind uf = new UnionFind(n + 1);  // 1-indexed nodes

    for (int[] edge : edges) {
        // If two nodes already connected, this edge creates a cycle
        if (!uf.union(edge[0], edge[1])) {
            return edge;
        }
    }
    return new int[0];
}
```

### Visualization

```
Edges: [1,2], [1,3], [2,3]

Process [1,2]: union(1,2) → success. Components: {1,2}, {3}
Process [1,3]: union(1,3) → success. Components: {1,2,3}
Process [2,3]: find(2)=1, find(3)=1 → SAME ROOT → CYCLE!
Return [2,3]
```

---

## Pattern 4: Dynamic Connectivity (Online Additions)

### Signal
- Elements/nodes added incrementally
- "After each addition, how many components?"
- Grid-based with cells turning ON over time

### Template

```java
// LC 305: Number of Islands II
// Grid positions turn into land one at a time, return component count after each
public List<Integer> numIslands2(int m, int n, int[][] positions) {
    List<Integer> result = new ArrayList<>();
    UnionFind uf = new UnionFind(m * n);
    boolean[][] grid = new boolean[m][n];
    int count = 0;
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    for (int[] pos : positions) {
        int r = pos[0], c = pos[1];
        if (grid[r][c]) {  // duplicate position
            result.add(count);
            continue;
        }
        grid[r][c] = true;
        count++;  // new island

        int idx = r * n + c;
        for (int[] d : dirs) {
            int nr = r + d[0], nc = c + d[1];
            if (nr >= 0 && nr < m && nc >= 0 && nc < n && grid[nr][nc]) {
                int nIdx = nr * n + nc;
                if (uf.union(idx, nIdx)) {
                    count--;  // merged two components
                }
            }
        }
        result.add(count);
    }
    return result;
}
```

### Visualization

```
Grid 3x3, positions: [0,0], [0,1], [1,2], [0,2]

After [0,0]:  1■ . .    count=1
              .  . .
              .  . .

After [0,1]:  1■ 1■ .   count=1 (merged with [0,0])
              .  .  .

After [1,2]:  1■ 1■ .   count=2 (new island)
              .  .  2■

After [0,2]:  1■ 1■ 1■  count=1 (merged [0,2] connects group1 and group2)
              .  .  1■
```

---

## Pattern 5: Accounts Merge / Equivalence Grouping

### Signal
- "Merge groups that share a common element"
- "Find all equivalent items across multiple sets"
- Transitive relationships: if a~b and b~c then a~c

### Template

```java
// LC 721: Accounts Merge
public List<List<String>> accountsMerge(List<List<String>> accounts) {
    int n = accounts.size();
    UnionFind uf = new UnionFind(n);

    // Map each email to the account index that owns it
    Map<String, Integer> emailToId = new HashMap<>();

    for (int i = 0; i < n; i++) {
        for (int j = 1; j < accounts.get(i).size(); j++) {
            String email = accounts.get(i).get(j);
            if (emailToId.containsKey(email)) {
                // This email seen before → merge accounts
                uf.union(i, emailToId.get(email));
            } else {
                emailToId.put(email, i);
            }
        }
    }

    // Group emails by root account
    Map<Integer, TreeSet<String>> rootToEmails = new HashMap<>();
    for (Map.Entry<String, Integer> entry : emailToId.entrySet()) {
        int root = uf.find(entry.getValue());
        rootToEmails.computeIfAbsent(root, k -> new TreeSet<>())
                    .add(entry.getKey());
    }

    // Build result
    List<List<String>> result = new ArrayList<>();
    for (Map.Entry<Integer, TreeSet<String>> entry : rootToEmails.entrySet()) {
        List<String> merged = new ArrayList<>();
        merged.add(accounts.get(entry.getKey()).get(0));  // name
        merged.addAll(entry.getValue());  // sorted emails
        result.add(merged);
    }
    return result;
}
```

---

## Pattern 6: Kruskal's MST

### Signal
- "Minimum spanning tree"
- "Minimum cost to connect all nodes"
- "Min cost edges such that all nodes reachable"

### Template

```java
// LC 1135: Connecting Cities With Minimum Cost
// LC 1584: Min Cost to Connect All Points
public int minCostConnectPoints(int[][] points) {
    int n = points.length;
    // Generate all edges with Manhattan distance
    List<int[]> edges = new ArrayList<>();  // [cost, i, j]
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            int cost = Math.abs(points[i][0] - points[j][0])
                     + Math.abs(points[i][1] - points[j][1]);
            edges.add(new int[]{cost, i, j});
        }
    }

    // Sort edges by cost (Kruskal's)
    edges.sort((a, b) -> a[0] - b[0]);

    UnionFind uf = new UnionFind(n);
    int totalCost = 0;
    int edgesUsed = 0;

    for (int[] edge : edges) {
        if (uf.union(edge[1], edge[2])) {
            totalCost += edge[0];
            edgesUsed++;
            if (edgesUsed == n - 1) break;  // MST complete
        }
    }
    return totalCost;
}
```

### Visualization

```
Kruskal's Algorithm:
1. Sort all edges by weight
2. For each edge (u,v,w) in sorted order:
   - If find(u) != find(v): add edge to MST, union(u,v)
   - Else: skip (would create cycle)
3. Stop when n-1 edges added

Edges sorted: (A-B,1) (B-C,2) (A-C,3) (C-D,4) (B-D,5)

Process (A-B,1): union(A,B) ✓  MST cost=1
Process (B-C,2): union(B,C) ✓  MST cost=3
Process (A-C,3): find(A)=find(C) ✗ SKIP (cycle)
Process (C-D,4): union(C,D) ✓  MST cost=7  → DONE (3 edges for 4 nodes)
```

---

## Pattern 7: Longest Consecutive Sequence

### Signal
- "Longest consecutive sequence" in unsorted array
- Union adjacent values (val and val+1)

### Template

```java
// LC 128: Longest Consecutive Sequence (O(n) with UF)
public int longestConsecutive(int[] nums) {
    if (nums.length == 0) return 0;

    Map<Integer, Integer> valToIdx = new HashMap<>();
    UnionFindWithSize uf = new UnionFindWithSize(nums.length);

    for (int i = 0; i < nums.length; i++) {
        if (valToIdx.containsKey(nums[i])) continue;  // skip duplicates
        valToIdx.put(nums[i], i);

        // Union with adjacent values if they exist
        if (valToIdx.containsKey(nums[i] - 1)) {
            uf.union(i, valToIdx.get(nums[i] - 1));
        }
        if (valToIdx.containsKey(nums[i] + 1)) {
            uf.union(i, valToIdx.get(nums[i] + 1));
        }
    }
    return uf.getMaxSize();
}
```

---

## Pattern 8: Weighted Union-Find

### Signal
- Equations like `a/b = 2.0`, query `a/c = ?`
- Relationships with numeric weights between nodes
- Transitive ratio/difference computations

### Template

```java
// LC 399: Evaluate Division
// If a/b=2 and b/c=3, then a/c=6
// Weight[x] = value of (x / root(x))
class WeightedUnionFind {
    private int[] parent;
    private double[] weight;  // weight[x] = x / parent[x]

    public WeightedUnionFind(int n) {
        parent = new int[n];
        weight = new double[n];
        for (int i = 0; i < n; i++) {
            parent[i] = i;
            weight[i] = 1.0;  // x / x = 1
        }
    }

    // Returns root, and after call weight[x] = x / root
    public int find(int x) {
        if (parent[x] != x) {
            int root = find(parent[x]);
            weight[x] *= weight[parent[x]];  // x/root = (x/parent) * (parent/root)
            parent[x] = root;
        }
        return parent[x];
    }

    // Record that x / y = value
    public void union(int x, int y, double value) {
        int rootX = find(x);
        int rootY = find(y);
        if (rootX == rootY) return;

        parent[rootX] = rootY;
        // rootX / rootY = (x/rootX is weight[x]) ... solve:
        // x / y = value
        // x / rootX = weight[x], y / rootY = weight[y]
        // rootX / rootY = (x / rootX)^-1 * (x / y) * (y / rootY)
        //               = value * weight[y] / weight[x]
        weight[rootX] = value * weight[y] / weight[x];
    }

    // Query x / y, returns -1.0 if not connected
    public double query(int x, int y) {
        int rootX = find(x);
        int rootY = find(y);
        if (rootX != rootY) return -1.0;
        return weight[x] / weight[y];  // (x/root) / (y/root) = x/y
    }
}

// Full solution for LC 399
public double[] calcEquation(List<List<String>> equations, double[] values,
                             List<List<String>> queries) {
    Map<String, Integer> varToId = new HashMap<>();
    int id = 0;

    for (List<String> eq : equations) {
        if (!varToId.containsKey(eq.get(0))) varToId.put(eq.get(0), id++);
        if (!varToId.containsKey(eq.get(1))) varToId.put(eq.get(1), id++);
    }

    WeightedUnionFind uf = new WeightedUnionFind(id);
    for (int i = 0; i < equations.size(); i++) {
        int x = varToId.get(equations.get(i).get(0));
        int y = varToId.get(equations.get(i).get(1));
        uf.union(x, y, values[i]);
    }

    double[] result = new double[queries.size()];
    for (int i = 0; i < queries.size(); i++) {
        String a = queries.get(i).get(0), b = queries.get(i).get(1);
        if (!varToId.containsKey(a) || !varToId.containsKey(b)) {
            result[i] = -1.0;
        } else {
            result[i] = uf.query(varToId.get(a), varToId.get(b));
        }
    }
    return result;
}
```

### Visualization

```
Equations: a/b=2.0, b/c=3.0
Query: a/c=?

After union(a, b, 2.0):
  a ──2.0──→ b (root)
  weight[a]=2.0 means a/b=2.0

After union(b, c, 3.0):
  a ──2.0──→ b ──3.0──→ c (root)

find(a): path compress
  weight[a] = 2.0 * 3.0 = 6.0, parent[a] = c
  Now: a ──6.0──→ c

Query a/c: weight[a] / weight[c] = 6.0 / 1.0 = 6.0 ✓
```

---

## Pattern 9: Union-Find with Size

### Signal
- "Largest component size"
- "Size of component containing X"
- Need to track how many elements in each group

### Template

```java
class UnionFindWithSize {
    private int[] parent;
    private int[] size;
    private int maxSize;

    public UnionFindWithSize(int n) {
        parent = new int[n];
        size = new int[n];
        maxSize = 1;
        for (int i = 0; i < n; i++) {
            parent[i] = i;
            size[i] = 1;
        }
    }

    public int find(int x) {
        if (parent[x] != x) {
            parent[x] = find(parent[x]);
        }
        return parent[x];
    }

    // Union by size: attach smaller tree to larger tree's root
    public boolean union(int x, int y) {
        int rootX = find(x), rootY = find(y);
        if (rootX == rootY) return false;

        // Merge smaller into larger
        if (size[rootX] < size[rootY]) {
            parent[rootX] = rootY;
            size[rootY] += size[rootX];
            maxSize = Math.max(maxSize, size[rootY]);
        } else {
            parent[rootY] = rootX;
            size[rootX] += size[rootY];
            maxSize = Math.max(maxSize, size[rootX]);
        }
        return true;
    }

    public int getSize(int x) {
        return size[find(x)];
    }

    public int getMaxSize() {
        return maxSize;
    }
}

// LC 827: Making A Large Island (flip one 0 to 1, maximize island)
public int largestIsland(int[][] grid) {
    int n = grid.length;
    UnionFindWithSize uf = new UnionFindWithSize(n * n);
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    // Build UF for existing islands
    for (int r = 0; r < n; r++) {
        for (int c = 0; c < n; c++) {
            if (grid[r][c] == 1) {
                for (int[] d : dirs) {
                    int nr = r + d[0], nc = c + d[1];
                    if (nr >= 0 && nr < n && nc >= 0 && nc < n && grid[nr][nc] == 1) {
                        uf.union(r * n + c, nr * n + nc);
                    }
                }
            }
        }
    }

    // Try flipping each 0
    int result = uf.getMaxSize();
    for (int r = 0; r < n; r++) {
        for (int c = 0; c < n; c++) {
            if (grid[r][c] == 0) {
                Set<Integer> neighborRoots = new HashSet<>();
                int total = 1;  // the flipped cell itself
                for (int[] d : dirs) {
                    int nr = r + d[0], nc = c + d[1];
                    if (nr >= 0 && nr < n && nc >= 0 && nc < n && grid[nr][nc] == 1) {
                        int root = uf.find(nr * n + nc);
                        if (neighborRoots.add(root)) {
                            total += uf.getSize(nr * n + nc);
                        }
                    }
                }
                result = Math.max(result, total);
            }
        }
    }
    return result == 0 ? 1 : result;  // handle all-zeros grid
}
```

---

## Amortized Complexity: Inverse Ackermann Proof Sketch

```
Why O(α(n)) per operation with path compression + union by rank?

1. Union by rank alone guarantees tree height ≤ log(n)
   - Proof: A tree of rank r has ≥ 2^r nodes (by induction)
   - So height ≤ log(n)

2. Path compression flattens trees further
   - After find(x), every node on the path points directly to root
   - Future finds on these nodes are O(1)

3. Combined analysis (Tarjan 1975):
   - Define iterated-log function: log*(n) = min{k : log^(k)(n) ≤ 1}
   - log*(2^65536) = 5  →  practically constant
   
   - Tighter bound uses inverse Ackermann α(n):
     A(0,j) = j+1
     A(i,0) = A(i-1, 1)
     A(i,j) = A(i-1, A(i,j-1))
     
     α(n) = min{k : A(k,k) ≥ n}
     
   - A(4,4) > 10^80 (more than atoms in universe)
   - So α(n) ≤ 4 for ALL practical inputs
   
   - m operations on n elements: O(m · α(n)) total
   - Each operation: O(α(n)) amortized ≈ O(1)

Key insight: Path compression makes repeated operations nearly free,
while union by rank prevents pathological tree shapes.
```

---

## Common Pitfalls & Tips

| Pitfall | Fix |
|---------|-----|
| Forgetting 1-indexed nodes | Initialize UF with `n+1` size |
| Not handling duplicates | Check before adding to map |
| Grid problems: wrong index mapping | Use `row * cols + col` consistently |
| Checking `parent[x] == parent[y]` instead of `find(x) == find(y)` | Always use `find()` |
| Union returns void (can't detect cycles) | Return boolean from `union` |
| Weighted UF: forgetting to update weight during path compression | Must multiply weights along path |

---

## LeetCode Problem Map

| Problem | Pattern | Key Insight |
|---------|---------|-------------|
| 200. Number of Islands | Components (static) | DFS simpler; UF works too |
| 305. Number of Islands II | Dynamic Connectivity | Online additions → UF optimal |
| 323. Number of Connected Components | Components | Direct UF application |
| 261. Graph Valid Tree | Components + Cycle | n-1 edges + 1 component |
| 684. Redundant Connection | Cycle Detection | First edge creating cycle |
| 721. Accounts Merge | Equivalence Grouping | Shared email → union accounts |
| 128. Longest Consecutive Sequence | Union adjacent | HashSet approach often simpler |
| 399. Evaluate Division | Weighted UF | Track ratios on edges |
| 1135. Connecting Cities Min Cost | Kruskal's MST | Sort + UF |
| 1584. Min Cost Connect All Points | Kruskal's MST | Generate all edges first |
| 827. Making A Large Island | UF with Size | Flip 0, sum neighbor components |
| 547. Number of Provinces | Components | Adjacency matrix input |
| 990. Satisfiability of Equality | UF + validation | Union equals, check not-equals |
| 1319. Number of Operations to Connect Network | Components | Answer = components - 1 (if enough edges) |
