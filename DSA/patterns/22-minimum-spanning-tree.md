# 22 - Minimum Spanning Tree (MST) Patterns

## Core Concept

A **Minimum Spanning Tree** of a weighted, connected, undirected graph is a subset of edges that:
- Connects all vertices (spanning)
- Forms a tree (no cycles, exactly V-1 edges)
- Has minimum total edge weight

---

## Why Greedy Works: The Cut Property

```
The Cut Property:
For any cut (partition of vertices into two sets S and V-S),
the minimum weight edge crossing the cut MUST be in some MST.

Proof intuition:
- Assume min-weight crossing edge e is NOT in MST T
- Adding e to T creates a cycle
- That cycle must cross the cut again via some other edge e'
- weight(e) <= weight(e'), so swapping e for e' gives weight <= T
- Therefore e belongs to some MST

This is WHY both Kruskal's and Prim's produce optimal results:
- Kruskal's: each edge added is the min crossing the cut between two components
- Prim's: each edge added is the min crossing the cut between tree and non-tree vertices
```

---

## Signal (When to Recognize MST)

| Signal | Example |
|--------|---------|
| "Connect all nodes with minimum cost" | Network wiring |
| "Minimum cost to make graph connected" | Connecting cities |
| "Spanning tree" mentioned directly | Find MST weight |
| Undirected weighted graph + connect everything | Infrastructure planning |
| "Remove maximum weight while keeping connected" | Equivalent to MST |

---

## Decision Flowchart

```
Is the graph sparse (E ~ V)?
├── YES → Kruskal's (O(E log E)) - sorting dominates
│         Also prefer when edges given as list
└── NO (dense, E ~ V^2)?
    ├── YES → Prim's with adjacency matrix O(V^2)
    │         or Prim's with heap O(E log V)
    └── Need to detect critical edges?
        ├── YES → Kruskal's + Union-Find (easier to exclude/force edges)
        └── Need to grow from specific vertex?
            └── YES → Prim's
```

---

## Pattern 1: Kruskal's Algorithm

### Signal
- Edges given as a list (or easy to enumerate)
- Need Union-Find anyway (component tracking)
- Sparse graph

### Template (Java)

```java
class UnionFind {
    int[] parent, rank;
    int components;

    UnionFind(int n) {
        parent = new int[n];
        rank = new int[n];
        components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }

    int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]); // path compression
        return parent[x];
    }

    boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return false; // already connected
        // union by rank
        if (rank[px] < rank[py]) { int tmp = px; px = py; py = tmp; }
        parent[py] = px;
        if (rank[px] == rank[py]) rank[px]++;
        components--;
        return true;
    }

    boolean isConnected() { return components == 1; }
}

public int kruskalMST(int n, int[][] edges) {
    // edges[i] = [u, v, weight]
    Arrays.sort(edges, (a, b) -> a[2] - b[2]); // sort by weight

    UnionFind uf = new UnionFind(n);
    int mstWeight = 0;
    int edgesUsed = 0;

    for (int[] edge : edges) {
        if (edgesUsed == n - 1) break; // MST complete
        int u = edge[0], v = edge[1], w = edge[2];
        if (uf.union(u, v)) { // no cycle formed
            mstWeight += w;
            edgesUsed++;
        }
    }

    return edgesUsed == n - 1 ? mstWeight : -1; // -1 if not connected
}
```

### Step-by-Step Visualization

```
Graph:
    0 ---4--- 1
    |       / |
    2     3   5
    |   /     |
    3 ---1--- 2

Edges sorted by weight: (1,2,1), (0,3,2), (1,3,3), (0,1,4), (1,2,5)

Step 1: Process edge (1,2, w=1)
  Components: {0} {1,2} {3}
  MST edges: [(1,2)]  Weight: 1
  
  0         1
            |  (w=1)
  3         2

Step 2: Process edge (0,3, w=2)
  Components: {0,3} {1,2}
  MST edges: [(1,2),(0,3)]  Weight: 3

  0         1
  |  (w=2)  |  (w=1)
  3         2

Step 3: Process edge (1,3, w=3)
  Connects component {0,3} with {1,2} → ACCEPT
  Components: {0,1,2,3}
  MST edges: [(1,2),(0,3),(1,3)]  Weight: 6

  0         1
  |  (w=2)/ |  (w=1)
  3 (w=3)   2

Step 4: Process edge (0,1, w=4)
  find(0) == find(1) → same component → REJECT (would form cycle)

Step 5: Process edge (1,2, w=5)
  find(1) == find(2) → same component → REJECT

DONE: 3 edges used = V-1 = 4-1 ✓
MST Weight = 6
```

### Complexity
- **Time:** O(E log E) for sorting + O(E * α(V)) for union-find ≈ O(E log E)
- **Space:** O(V) for Union-Find

---

## Pattern 2: Prim's Algorithm

### Signal
- Dense graph (adjacency matrix)
- Growing from a specific starting vertex
- Graph given as adjacency list

### Template (Java)

```java
public int primMST(int n, List<int[]>[] graph) {
    // graph[u] contains [v, weight] pairs
    boolean[] inMST = new boolean[n];
    // PQ stores [weight, vertex]
    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);

    int mstWeight = 0;
    int edgesUsed = 0;

    // Start from vertex 0
    pq.offer(new int[]{0, 0}); // [weight=0, vertex=0]

    while (!pq.isEmpty() && edgesUsed < n) {
        int[] curr = pq.poll();
        int w = curr[0], u = curr[1];

        if (inMST[u]) continue; // already in MST
        inMST[u] = true;
        mstWeight += w;
        edgesUsed++;

        for (int[] neighbor : graph[u]) {
            int v = neighbor[0], weight = neighbor[1];
            if (!inMST[v]) {
                pq.offer(new int[]{weight, v});
            }
        }
    }

    return edgesUsed == n ? mstWeight : -1;
}
```

### Visualization

```
Prim's grows a single tree outward:

Start: vertex 0
MST = {0}, Frontier edges from 0: (0→1, w=4), (0→3, w=2)

Pick min frontier: (0→3, w=2)
MST = {0,3}, Frontier: (0→1, w=4), (3→1, w=3), (3→2, w=?)

Pick min frontier: (3→1, w=3)
MST = {0,3,1}, Frontier: (1→2, w=1), ...

Pick min frontier: (1→2, w=1)
MST = {0,3,1,2} → DONE

Contrast with Kruskal's: Prim's always maintains ONE connected component
that grows. Kruskal's merges multiple components.
```

### Complexity
- **Time:** O(E log V) with binary heap, O(V^2) with adjacency matrix (no heap)
- **Space:** O(V + E)

---

## Pattern 3: Min Cost to Connect All Points (LeetCode 1584)

### Problem
Given `points[i] = [xi, yi]`, connect all points with minimum total Manhattan distance. Cost between two points = |xi - xj| + |yi - yj|.

### Template (Java) - Kruskal's Approach

```java
public int minCostConnectPoints(int[][] points) {
    int n = points.length;
    // Generate all edges (complete graph)
    List<int[]> edges = new ArrayList<>();
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            int dist = Math.abs(points[i][0] - points[j][0])
                     + Math.abs(points[i][1] - points[j][1]);
            edges.add(new int[]{dist, i, j});
        }
    }

    edges.sort((a, b) -> a[0] - b[0]);

    UnionFind uf = new UnionFind(n);
    int cost = 0, edgesUsed = 0;

    for (int[] edge : edges) {
        if (edgesUsed == n - 1) break;
        if (uf.union(edge[1], edge[2])) {
            cost += edge[0];
            edgesUsed++;
        }
    }
    return cost;
}
```

### Template (Java) - Prim's Approach (More Efficient for Dense)

```java
public int minCostConnectPoints(int[][] points) {
    int n = points.length;
    boolean[] inMST = new boolean[n];
    // minDist[i] = minimum distance from i to any vertex in MST
    int[] minDist = new int[n];
    Arrays.fill(minDist, Integer.MAX_VALUE);
    minDist[0] = 0;

    int totalCost = 0;

    for (int count = 0; count < n; count++) {
        // Find vertex with min distance not yet in MST
        int u = -1;
        for (int i = 0; i < n; i++) {
            if (!inMST[i] && (u == -1 || minDist[i] < minDist[u])) {
                u = i;
            }
        }

        inMST[u] = true;
        totalCost += minDist[u];

        // Update distances for neighbors
        for (int v = 0; v < n; v++) {
            if (!inMST[v]) {
                int dist = Math.abs(points[u][0] - points[v][0])
                         + Math.abs(points[u][1] - points[v][1]);
                minDist[v] = Math.min(minDist[v], dist);
            }
        }
    }

    return totalCost;
}
```

### Why Prim's O(V^2) Wins Here
- Complete graph → E = V*(V-1)/2 ≈ V^2
- Kruskal's: O(V^2 log V) for sorting all edges
- Prim's (no heap, matrix): O(V^2) — just scan for min each time
- For dense/complete graphs, avoid the heap overhead

### Complexity
- **Kruskal's:** Time O(V^2 log V), Space O(V^2)
- **Prim's (matrix):** Time O(V^2), Space O(V)

---

## Pattern 4: Connecting Cities with Minimum Cost (LeetCode 1135)

### Problem
N cities, given connections `[city1, city2, cost]`. Find minimum cost to connect all cities. Return -1 if impossible.

### Template (Java)

```java
public int minimumCost(int n, int[][] connections) {
    Arrays.sort(connections, (a, b) -> a[2] - b[2]);

    UnionFind uf = new UnionFind(n);
    int totalCost = 0;
    int edgesUsed = 0;

    for (int[] conn : connections) {
        int u = conn[0] - 1, v = conn[1] - 1, cost = conn[2]; // 1-indexed cities
        if (uf.union(u, v)) {
            totalCost += cost;
            edgesUsed++;
            if (edgesUsed == n - 1) return totalCost;
        }
    }

    return -1; // not all cities connected
}
```

### Key Insight
This is pure Kruskal's. The only addition is checking if the graph is connected (edgesUsed == n-1). If we exhaust all edges without connecting everything, return -1.

---

## Pattern 5: Critical and Pseudo-Critical Edges in MST (LeetCode 1489)

### Problem
Find edges that:
- **Critical:** appear in ALL MSTs (removing them increases MST weight)
- **Pseudo-Critical:** appear in SOME but not all MSTs (can be swapped)

### Template (Java)

```java
public List<List<Integer>> findCriticalAndPseudoCriticalEdges(int n, int[][] edges) {
    // Add original index to edges before sorting
    int m = edges.length;
    int[][] indexed = new int[m][4];
    for (int i = 0; i < m; i++) {
        indexed[i] = new int[]{edges[i][0], edges[i][1], edges[i][2], i};
    }
    Arrays.sort(indexed, (a, b) -> a[2] - b[2]);

    // Find standard MST weight
    int mstWeight = buildMST(n, indexed, -1, -1);

    List<Integer> critical = new ArrayList<>();
    List<Integer> pseudoCritical = new ArrayList<>();

    for (int i = 0; i < m; i++) {
        // Test if critical: exclude this edge, does MST weight increase?
        int weightWithout = buildMST(n, indexed, i, -1);
        if (weightWithout > mstWeight) {
            critical.add(indexed[i][3]);
        } else {
            // Test if pseudo-critical: force-include this edge, same MST weight?
            int weightWith = buildMST(n, indexed, -1, i);
            if (weightWith == mstWeight) {
                pseudoCritical.add(indexed[i][3]);
            }
        }
    }

    return List.of(critical, pseudoCritical);
}

// Build MST, optionally excluding one edge and/or force-including one edge
private int buildMST(int n, int[][] edges, int excludeIdx, int forceIdx) {
    UnionFind uf = new UnionFind(n);
    int weight = 0;

    // Force-include edge first
    if (forceIdx != -1) {
        uf.union(edges[forceIdx][0], edges[forceIdx][1]);
        weight += edges[forceIdx][2];
    }

    for (int i = 0; i < edges.length; i++) {
        if (i == excludeIdx) continue;
        if (uf.union(edges[i][0], edges[i][1])) {
            weight += edges[i][2];
        }
    }

    return uf.isConnected() ? weight : Integer.MAX_VALUE;
}
```

### Visualization

```
Example:
Edges: (0,1,1) (1,2,1) (0,2,1) (2,3,2) (1,3,3)
MST weight = 4

Test edge (2,3, w=2):
  Exclude it → can't connect 3 cheaply → weight increases → CRITICAL

Test edge (0,1, w=1):
  Exclude it → use (0,2,1) instead → same weight → NOT critical
  Force it → MST weight still 4 → PSEUDO-CRITICAL

Test edge (1,3, w=3):
  Exclude it → weight unchanged (wasn't needed)
  Force it → weight = 1+1+3 = 5 > 4 → NEITHER
```

### Complexity
- **Time:** O(E^2 * α(V)) — build MST once per edge
- **Space:** O(V + E)

---

## Pattern 6: Second Minimum Spanning Tree

### Problem
Find the spanning tree with the second smallest total weight.

### Approach
1. Find MST using Kruskal's
2. For each non-MST edge (u,v,w): adding it creates a cycle. The second MST = MST - max_edge_on_path(u,v) + (u,v,w)
3. Take the minimum over all such swaps

### Template (Java)

```java
public int secondMinimumSpanningTree(int n, int[][] edges) {
    Arrays.sort(edges, (a, b) -> a[2] - b[2]);

    UnionFind uf = new UnionFind(n);
    List<int[]>[] mstAdj = new ArrayList[n];
    for (int i = 0; i < n; i++) mstAdj[i] = new ArrayList<>();

    Set<Integer> mstEdgeIndices = new HashSet<>();
    int mstWeight = 0;

    // Build MST
    for (int i = 0; i < edges.length; i++) {
        int u = edges[i][0], v = edges[i][1], w = edges[i][2];
        if (uf.union(u, v)) {
            mstWeight += w;
            mstEdgeIndices.add(i);
            mstAdj[u].add(new int[]{v, w});
            mstAdj[v].add(new int[]{u, w});
        }
    }

    // For each non-MST edge, find max edge on path in MST between its endpoints
    int secondMin = Integer.MAX_VALUE;

    for (int i = 0; i < edges.length; i++) {
        if (mstEdgeIndices.contains(i)) continue;
        int u = edges[i][0], v = edges[i][1], w = edges[i][2];

        // BFS/DFS to find max edge weight on path from u to v in MST
        int maxOnPath = findMaxOnPath(mstAdj, n, u, v);

        // Swap: remove max edge on path, add this edge
        int candidate = mstWeight - maxOnPath + w;
        if (candidate > mstWeight) { // must be strictly greater
            secondMin = Math.min(secondMin, candidate);
        }
    }

    return secondMin;
}

private int findMaxOnPath(List<int[]>[] adj, int n, int src, int dst) {
    // BFS tracking max edge weight
    int[] maxWeight = new int[n];
    Arrays.fill(maxWeight, -1);
    maxWeight[src] = 0;
    Queue<Integer> queue = new LinkedList<>();
    queue.offer(src);

    while (!queue.isEmpty()) {
        int u = queue.poll();
        if (u == dst) return maxWeight[dst];
        for (int[] next : adj[u]) {
            int v = next[0], w = next[1];
            if (maxWeight[v] == -1) {
                maxWeight[v] = Math.max(maxWeight[u], w);
                queue.offer(v);
            }
        }
    }
    return maxWeight[dst];
}
```

### Key Insight
The second MST differs from the first MST by exactly one edge swap. We try all possible swaps: add a non-MST edge (creates cycle), remove the heaviest edge in that cycle (which is the max edge on the MST path between the edge's endpoints).

### Complexity
- **Time:** O(E log E + E*V) — MST build + path queries for each non-MST edge
- **Space:** O(V + E)
- Can be optimized to O(E log E + V^2) with LCA + sparse table for max-on-path queries

---

## Pattern 7: Kruskal's vs Prim's Comparison

| Aspect | Kruskal's | Prim's |
|--------|-----------|--------|
| **Strategy** | Sort all edges globally, pick smallest that doesn't form cycle | Grow tree from one vertex, always pick cheapest frontier edge |
| **Data Structure** | Union-Find | Priority Queue (or array scan) |
| **Best for sparse** | Yes — O(E log E) | O(E log V) with heap |
| **Best for dense** | No — O(V^2 log V) | Yes — O(V^2) without heap |
| **Edge list input** | Natural fit | Need to build adjacency first |
| **Adjacency matrix** | Must enumerate edges | Natural fit |
| **Disconnected graph** | Detects naturally (edgesUsed < V-1) | Only spans one component |
| **Force/exclude edges** | Easy (skip or pre-union) | Harder |
| **Critical edge detection** | Easy | Hard |
| **Parallelizable** | Boruvka's variant is | Not easily |

### When to Use Which

```
Kruskal's:
  ✓ Edges given as a list
  ✓ Need to detect/force/exclude specific edges
  ✓ Sparse graphs
  ✓ Need component tracking (Union-Find useful elsewhere)
  ✓ Problems about critical/pseudo-critical edges

Prim's:
  ✓ Dense or complete graphs (V^2 edges)
  ✓ Adjacency matrix representation
  ✓ Need to grow from a specific start vertex
  ✓ Min Cost to Connect All Points (complete graph)
  ✓ Already have adjacency list
```

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Forgetting MST needs exactly V-1 edges | Check `edgesUsed == n-1` |
| 1-indexed vertices | Convert to 0-indexed or size UF accordingly |
| Disconnected graph → no MST exists | Return -1 if components > 1 |
| Integer overflow on edge weights | Use `long` for total weight |
| Comparing `a[2] - b[2]` in sort (overflow) | Use `Integer.compare(a[2], b[2])` for safety |
| Prim's: not checking `inMST` after poll | Stale entries in PQ, must skip |

---

## Summary Table

| Problem | Algorithm | Key Trick |
|---------|-----------|-----------|
| Basic MST (sparse) | Kruskal's | Sort + Union-Find |
| Basic MST (dense) | Prim's | O(V^2) matrix scan |
| Connect All Points | Prim's O(V^2) | Complete graph, skip PQ |
| Connecting Cities | Kruskal's | Edge list natural |
| Critical Edges | Kruskal's x E | Exclude/force each edge |
| Second MST | Kruskal's + BFS | Swap non-MST edge with max-on-path |
| MST with constraints | Kruskal's | Pre-union forced edges |

---

## Complexity Reference

| Algorithm | Time | Space |
|-----------|------|-------|
| Kruskal's | O(E log E) | O(V) |
| Prim's (heap) | O(E log V) | O(V + E) |
| Prim's (matrix) | O(V^2) | O(V) |
| Critical Edges | O(E^2 * α(V)) | O(V + E) |
| Second MST | O(EV) naive, O(E log V + V^2) optimized | O(V + E) |
