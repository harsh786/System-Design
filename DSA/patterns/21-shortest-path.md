# 21 - Shortest Path Algorithms

## Algorithm Selection Decision Matrix

```
Question                          → Algorithm
─────────────────────────────────────────────────────────────────
Unweighted graph?                 → BFS                    O(V+E)
Non-negative weights?             → Dijkstra               O((V+E) log V)
Negative weights allowed?         → Bellman-Ford            O(VE)
All-pairs needed?                 → Floyd-Warshall          O(V³)
Edge weights only 0 or 1?        → 0-1 BFS (Deque)        O(V+E)
DAG (no cycles)?                  → Topo Sort + Relax      O(V+E)
K stops constraint?               → Modified BFS/BF        O(K·E)
Max edge on path (minimax)?       → Modified Dijkstra      O((V+E) log V)
Max product path?                 → Modified Dijkstra      O((V+E) log V)
Dense graph, all-pairs?           → Floyd-Warshall         O(V³)
Sparse graph, single source?      → Dijkstra               O((V+E) log V)
Need negative cycle detection?    → Bellman-Ford            O(VE)
```

## Complexity Comparison Table

| Algorithm | Time | Space | Negative Wt | Neg Cycle Detect | Notes |
|-----------|------|-------|-------------|-----------------|-------|
| BFS | O(V+E) | O(V) | N/A | N/A | Unweighted only |
| Dijkstra | O((V+E)logV) | O(V+E) | No | No | Greedy, PQ-based |
| Bellman-Ford | O(VE) | O(V) | Yes | Yes | Relax V-1 times |
| Floyd-Warshall | O(V³) | O(V²) | Yes | Yes | All-pairs, DP |
| 0-1 BFS | O(V+E) | O(V) | No | No | Deque trick |
| DAG SP | O(V+E) | O(V) | Yes | N/A (no cycles) | Topo sort first |

---

## Pattern 1: BFS for Unweighted Graphs

### Signal
- Graph with uniform edge weights (or unweighted)
- Find minimum number of edges/steps from source to target

### Template (Java)

```java
public int[] bfsShortestPath(List<List<Integer>> graph, int src) {
    int n = graph.size();
    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    Queue<Integer> queue = new LinkedList<>();
    queue.offer(src);

    while (!queue.isEmpty()) {
        int u = queue.poll();
        for (int v : graph.get(u)) {
            if (dist[u] + 1 < dist[v]) {
                dist[v] = dist[u] + 1;
                queue.offer(v);
            }
        }
    }
    return dist;
}
```

### Visualization

```
Graph: 0 -- 1 -- 3 -- 5
       |         |
       2 ------- 4

BFS from 0:
Queue: [0]        dist: [0, ∞, ∞, ∞, ∞, ∞]
Queue: [1,2]      dist: [0, 1, 1, ∞, ∞, ∞]
Queue: [2,3]      dist: [0, 1, 1, 2, ∞, ∞]
Queue: [3,4]      dist: [0, 1, 1, 2, 2, ∞]
Queue: [4,5]      dist: [0, 1, 1, 2, 2, 3]
Queue: [5]        dist: [0, 1, 1, 2, 2, 3]  (4 already visited)
Queue: []         dist: [0, 1, 1, 2, 2, 3]
```

### Variants
- **Multi-source BFS**: Add all sources to queue initially (dist=0 for each)
- **Bidirectional BFS**: Search from both ends, meet in middle (halves search space)
- **Grid BFS**: 4/8-directional movement on 2D grid

### Complexity
- Time: O(V + E)
- Space: O(V)

---

## Pattern 2: Dijkstra's Algorithm

### Signal
- Weighted graph with **non-negative** weights
- Single-source shortest path
- Priority queue / greedy approach

### Template (Java) — with Stale Entry Handling

```java
public int[] dijkstra(List<List<int[]>> graph, int src) {
    // graph.get(u) = list of {neighbor, weight}
    int n = graph.size();
    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    // {distance, node}
    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
    pq.offer(new int[]{0, src});

    while (!pq.isEmpty()) {
        int[] curr = pq.poll();
        int d = curr[0], u = curr[1];

        // STALE ENTRY HANDLING: skip if we already found a better path
        if (d > dist[u]) continue;

        for (int[] edge : graph.get(u)) {
            int v = edge[0], w = edge[1];
            if (dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
                pq.offer(new int[]{dist[v], v});
            }
        }
    }
    return dist;
}
```

### Why Stale Entry Handling?

```
Without decrease-key, the PQ may contain multiple entries for the same node.
When we pop {d, u}, if d > dist[u], a shorter path was already processed.
This entry is "stale" — skip it.

PQ state example:
  Insert {10, B}, then later {7, B}
  Pop {7, B} → process, dist[B] = 7
  Pop {10, B} → 10 > dist[B]=7 → SKIP (stale)
```

### Visualization: Dijkstra's Relaxation Process

```
Graph:
    A --4-- B --1-- D
    |       |       |
    2       3       5
    |       |       |
    C --7-- E --2-- F

Source: A

Step 1: Process A (dist=0)
  Relax A→B: dist[B] = min(∞, 0+4) = 4  ✓
  Relax A→C: dist[C] = min(∞, 0+2) = 2  ✓
  PQ: [{2,C}, {4,B}]
  dist: [A=0, B=4, C=2, D=∞, E=∞, F=∞]

Step 2: Process C (dist=2)
  Relax C→E: dist[E] = min(∞, 2+7) = 9  ✓
  PQ: [{4,B}, {9,E}]
  dist: [A=0, B=4, C=2, D=∞, E=9, F=∞]

Step 3: Process B (dist=4)
  Relax B→D: dist[D] = min(∞, 4+1) = 5  ✓
  Relax B→E: dist[E] = min(9, 4+3) = 7   ✓ (RELAXED!)
  PQ: [{5,D}, {7,E}, {9,E}]  ← stale {9,E} remains
  dist: [A=0, B=4, C=2, D=5, E=7, F=∞]

Step 4: Process D (dist=5)
  Relax D→F: dist[F] = min(∞, 5+5) = 10 ✓
  PQ: [{7,E}, {9,E}, {10,F}]
  dist: [A=0, B=4, C=2, D=5, E=7, F=10]

Step 5: Process E (dist=7)
  Relax E→F: dist[F] = min(10, 7+2) = 9  ✓ (RELAXED!)
  PQ: [{9,E}, {9,F}, {10,F}]
  dist: [A=0, B=4, C=2, D=5, E=7, F=9]

Step 6: Pop {9,E} → 9 > dist[E]=7 → STALE, skip

Step 7: Process F (dist=9) — no outgoing relaxation

Step 8: Pop {10,F} → 10 > dist[F]=9 → STALE, skip

FINAL: [A=0, B=4, C=2, D=5, E=7, F=9]
```

### Variants
- **Lazy Dijkstra** (above): allows stale entries, simpler code
- **Indexed PQ Dijkstra**: true decrease-key, no stale entries, O((V+E)logV)
- **Dijkstra on grid**: nodes are cells, weight = cell value
- **Stop early**: return when target is popped from PQ

### Complexity
- Time: O((V + E) log V) with binary heap
- Space: O(V + E)

---

## Pattern 3: Bellman-Ford Algorithm

### Signal
- Graph may have **negative weight** edges
- Need to detect **negative cycles**
- Single-source shortest path

### Template (Java)

```java
public int[] bellmanFord(int n, int[][] edges, int src) {
    // edges[i] = {u, v, weight}
    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    // Relax all edges V-1 times
    for (int i = 0; i < n - 1; i++) {
        boolean updated = false;
        for (int[] edge : edges) {
            int u = edge[0], v = edge[1], w = edge[2];
            if (dist[u] != Integer.MAX_VALUE && dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
                updated = true;
            }
        }
        if (!updated) break; // Early termination
    }

    // V-th iteration: detect negative cycle
    for (int[] edge : edges) {
        int u = edge[0], v = edge[1], w = edge[2];
        if (dist[u] != Integer.MAX_VALUE && dist[u] + w < dist[v]) {
            return null; // Negative cycle exists
        }
    }
    return dist;
}
```

### Negative Cycle Explanation

```
A negative cycle is a cycle whose total edge weight is negative.
Any path passing through it can be made infinitely short by looping.

Example:
    A --1-→ B --(-3)-→ C --1-→ A
    Cycle weight: 1 + (-3) + 1 = -1

    Each loop around the cycle reduces total distance by 1.
    After V-1 relaxations, all shortest paths (without cycles) are found.
    If a V-th relaxation STILL reduces a distance → negative cycle reachable.

Why V-1 iterations suffice (without negative cycles):
    Shortest path has at most V-1 edges.
    Each iteration guarantees at least one more edge of the shortest path is finalized.
    Iteration 1: paths with 1 edge correct
    Iteration 2: paths with ≤2 edges correct
    ...
    Iteration V-1: paths with ≤V-1 edges correct
```

### Visualization

```
Graph: edges = [(A,B,4), (A,C,2), (B,C,-3), (C,D,1)]
Source: A,  Nodes: A=0, B=1, C=2, D=3

Initial:  dist = [0, ∞, ∞, ∞]

Iteration 1:
  (A→B,4):  dist[B] = min(∞, 0+4) = 4
  (A→C,2):  dist[C] = min(∞, 0+2) = 2
  (B→C,-3): dist[C] = min(2, 4+(-3)) = 1  ✓
  (C→D,1):  dist[D] = min(∞, 1+1) = 2
  dist = [0, 4, 1, 2]

Iteration 2:
  (B→C,-3): dist[C] = min(1, 4+(-3)) = 1 (no change)
  No updates → early termination

FINAL: [0, 4, 1, 2]
```

### Variants
- **SPFA** (Shortest Path Faster Algorithm): queue-based Bellman-Ford, avg O(E) but worst O(VE)
- **Detect which nodes are in negative cycle**: run BFS/DFS from nodes that relax on V-th iteration

### Complexity
- Time: O(V * E)
- Space: O(V)

---

## Pattern 4: Floyd-Warshall (All-Pairs Shortest Path)

### Signal
- Need shortest path between **every pair** of nodes
- Small graph (V ≤ 400-500 due to O(V³))
- May have negative edges (detects negative cycles via diagonal)

### Template (Java)

```java
public int[][] floydWarshall(int n, int[][] edges) {
    int INF = (int) 1e9;
    int[][] dist = new int[n][n];

    // Initialize
    for (int[] row : dist) Arrays.fill(row, INF);
    for (int i = 0; i < n; i++) dist[i][i] = 0;
    for (int[] e : edges) dist[e[0]][e[1]] = e[2]; // directed

    // DP: try each node k as intermediate
    for (int k = 0; k < n; k++) {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (dist[i][k] != INF && dist[k][j] != INF) {
                    dist[i][j] = Math.min(dist[i][j], dist[i][k] + dist[k][j]);
                }
            }
        }
    }

    // Negative cycle: dist[i][i] < 0 for some i
    for (int i = 0; i < n; i++) {
        if (dist[i][i] < 0) return null; // negative cycle
    }
    return dist;
}
```

### Visualization

```
DP Intuition:
  dist[i][j] via k = "shortest path from i to j using only nodes {0..k} as intermediates"

  k=0: Can we improve i→j by going through node 0?
  k=1: Can we improve i→j by going through nodes {0,1}?
  ...
  k=V-1: All intermediates considered → final answer

Example (3 nodes):
  Initial:        After k=0:       After k=1:       After k=2:
    0  3  ∞         0  3  ∞         0  3  5          0  3  5
    ∞  0  2         ∞  0  2         ∞  0  2          ∞  0  2
    7  ∞  0         7  10 0         7  10 0          7  10 0
                    (2→1 via 0)    (0→2 via 1)
```

### Variants
- **Path reconstruction**: maintain `next[i][j]` matrix
- **Transitive closure**: use boolean OR instead of min/add
- **Minimax paths**: `dist[i][j] = min(max(dist[i][k], dist[k][j]))`

### Complexity
- Time: O(V³)
- Space: O(V²)

---

## Pattern 5: 0-1 BFS (Deque-Based)

### Signal
- Edge weights are **only 0 or 1**
- Need shortest path (BFS-like but respects weights)
- More efficient than Dijkstra for this special case

### Template (Java)

```java
public int[] zeroOneBFS(List<List<int[]>> graph, int src) {
    int n = graph.size();
    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    Deque<Integer> deque = new ArrayDeque<>();
    deque.offerFirst(src);

    while (!deque.isEmpty()) {
        int u = deque.pollFirst();

        for (int[] edge : graph.get(u)) {
            int v = edge[0], w = edge[1]; // w is 0 or 1
            if (dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
                if (w == 0) {
                    deque.offerFirst(v); // 0-weight: front (same level)
                } else {
                    deque.offerLast(v);  // 1-weight: back (next level)
                }
            }
        }
    }
    return dist;
}
```

### Visualization

```
Intuition: Generalization of BFS where 0-weight edges don't "cost" a level.

Graph: A -0→ B -1→ C -0→ D -1→ E

Deque processing (front | back):
  [A]           dist: A=0
  [B]           dist: A=0, B=0  (0-edge → push front)
  [C]           dist: A=0, B=0, C=1  (1-edge → push back... but deque was empty)
  Wait — let's redo with a real example:

  A -1→ B -0→ C -1→ D
  A -0→ C

  [A]           dist=[0,∞,∞,∞]
  Process A:
    A→B (w=1): dist[B]=1, push back   deque: [C | B]  wait...
    A→C (w=0): dist[C]=0, push front  deque: [C, B]
  Process C (front):
    C→D (w=1): dist[D]=1, push back   deque: [B, D]
  Process B:
    B→C (w=0): dist[C]=min(0,1+0)=0, no update
  Process D: done

  Final: [A=0, B=1, C=0, D=1]

  Key insight: 0-weight edges keep node at same "distance level" (push front).
```

### Variants
- **Grid problems**: walls cost 1, open cells cost 0 (LC 2290)
- **Minimum flips**: flip = cost 1, follow = cost 0

### Complexity
- Time: O(V + E)
- Space: O(V)

---

## Pattern 6: Shortest Path in DAG

### Signal
- Graph is a **Directed Acyclic Graph**
- Can have negative weights (no cycles means no negative cycles)
- Process in topological order

### Template (Java)

```java
public int[] shortestPathDAG(List<List<int[]>> graph, int src) {
    int n = graph.size();
    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    // Step 1: Topological sort (Kahn's or DFS-based)
    int[] inDegree = new int[n];
    for (int u = 0; u < n; u++)
        for (int[] e : graph.get(u))
            inDegree[e[0]]++;

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < n; i++)
        if (inDegree[i] == 0) queue.offer(i);

    List<Integer> topoOrder = new ArrayList<>();
    while (!queue.isEmpty()) {
        int u = queue.poll();
        topoOrder.add(u);
        for (int[] e : graph.get(u))
            if (--inDegree[e[0]] == 0) queue.offer(e[0]);
    }

    // Step 2: Relax edges in topological order
    for (int u : topoOrder) {
        if (dist[u] == Integer.MAX_VALUE) continue;
        for (int[] edge : graph.get(u)) {
            int v = edge[0], w = edge[1];
            if (dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
            }
        }
    }
    return dist;
}
```

### Visualization

```
DAG:  A →(2) B →(3) D →(1) F
      A →(6) C →(1) D
      B →(7) E →(2) F

Topo order: A, B, C, E, D, F  (one valid ordering)

Process A (dist=0): relax A→B(2), A→C(6)  → dist=[0,2,6,∞,∞,∞]
Process B (dist=2): relax B→D(3), B→E(7)  → dist=[0,2,6,5,9,∞]
Process C (dist=6): relax C→D(1)           → dist=[0,2,6,5,9,∞] (6+1=7 > 5, no update)
Process E (dist=9): relax E→F(2)           → dist=[0,2,6,5,9,11]
Process D (dist=5): relax D→F(1)           → dist=[0,2,6,5,9,6]  (5+1=6 < 11 ✓)
Process F: no outgoing edges

FINAL: [A=0, B=2, C=6, D=5, E=9, F=6]
```

### Variants
- **Longest path in DAG**: negate weights or use `max` instead of `min`
- **Critical path** (project scheduling): longest path in DAG
- **Number of shortest paths**: track count alongside distance

### Complexity
- Time: O(V + E)
- Space: O(V)

---

## Pattern 7: Cheapest Flights Within K Stops

### Signal
- Shortest path with a **hop/stop limit**
- Cannot use standard Dijkstra (greedy doesn't respect hop constraint)
- LC 787: Cheapest Flights Within K Stops

### Template (Java) — Modified Bellman-Ford

```java
public int findCheapestPrice(int n, int[][] flights, int src, int dst, int k) {
    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    // K stops = K+1 edges, so iterate K+1 times
    for (int i = 0; i <= k; i++) {
        int[] temp = dist.clone(); // Use previous iteration's values
        for (int[] f : flights) {
            int u = f[0], v = f[1], w = f[2];
            if (dist[u] != Integer.MAX_VALUE && dist[u] + w < temp[v]) {
                temp[v] = dist[u] + w;
            }
        }
        dist = temp;
    }
    return dist[dst] == Integer.MAX_VALUE ? -1 : dist[dst];
}
```

### Template (Java) — BFS with Level Limit

```java
public int findCheapestPriceBFS(int n, int[][] flights, int src, int dst, int k) {
    List<List<int[]>> graph = new ArrayList<>();
    for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
    for (int[] f : flights) graph.get(f[0]).add(new int[]{f[1], f[2]});

    int[] dist = new int[n];
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[src] = 0;

    Queue<int[]> queue = new LinkedList<>(); // {node, cost}
    queue.offer(new int[]{src, 0});
    int stops = 0;

    while (!queue.isEmpty() && stops <= k) {
        int size = queue.size();
        while (size-- > 0) {
            int[] curr = queue.poll();
            int u = curr[0], cost = curr[1];
            for (int[] edge : graph.get(u)) {
                int v = edge[0], w = edge[1];
                if (cost + w < dist[v]) {
                    dist[v] = cost + w;
                    queue.offer(new int[]{v, dist[v]});
                }
            }
        }
        stops++;
    }
    return dist[dst] == Integer.MAX_VALUE ? -1 : dist[dst];
}
```

### Key Insight

```
Why clone dist[] in Bellman-Ford variant?
  Without clone, within one iteration we might use a freshly-updated dist[u]
  which represents a path with MORE edges than allowed.
  The clone ensures we only use distances from the PREVIOUS iteration.

  Iteration i finds shortest paths using at most i+1 edges.
  So K+1 iterations = at most K+1 edges = at most K stops.
```

### Complexity
- Bellman-Ford variant: Time O((K+1) * E), Space O(V)
- BFS variant: Time O(K * E), Space O(V)

---

## Pattern 8: Swim in Rising Water (Minimax Path)

### Signal
- Find path minimizing the **maximum edge/node weight** along the path
- Binary search + BFS/DFS or modified Dijkstra
- LC 778: Swim in Rising Water

### Template (Java) — Dijkstra Variant

```java
public int swimInWater(int[][] grid) {
    int n = grid.length;
    int[][] dist = new int[n][n];
    for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
    dist[0][0] = grid[0][0];

    // {max_weight_on_path, row, col}
    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
    pq.offer(new int[]{grid[0][0], 0, 0});

    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    while (!pq.isEmpty()) {
        int[] curr = pq.poll();
        int maxW = curr[0], r = curr[1], c = curr[2];

        if (r == n - 1 && c == n - 1) return maxW;
        if (maxW > dist[r][c]) continue; // stale

        for (int[] d : dirs) {
            int nr = r + d[0], nc = c + d[1];
            if (nr < 0 || nr >= n || nc < 0 || nc >= n) continue;
            // Key: cost = max of path so far and next cell
            int newDist = Math.max(maxW, grid[nr][nc]);
            if (newDist < dist[nr][nc]) {
                dist[nr][nc] = newDist;
                pq.offer(new int[]{newDist, nr, nc});
            }
        }
    }
    return -1;
}
```

### Key Insight

```
Standard Dijkstra: dist[v] = min(dist[v], dist[u] + w)    (sum)
Minimax Dijkstra:  dist[v] = min(dist[v], max(dist[u], w)) (bottleneck)

The PQ still works because:
  - We process minimum-cost paths first
  - Once a node is finalized, no better path exists (same greedy argument)
```

### Variants
- **Path with Minimum Effort** (LC 1631): max absolute difference between adjacent cells
- **Path with Maximum Minimum** (widest path): max(min(...)) — reverse the logic

### Complexity
- Time: O(N² log N) for N×N grid
- Space: O(N²)

---

## Pattern 9: Path with Maximum Probability

### Signal
- Maximize **product** of edge weights (probabilities ≤ 1)
- Convert to shortest path by negating log or use max-heap
- LC 1514: Path with Maximum Probability

### Template (Java) — Max-Heap Dijkstra

```java
public double maxProbability(int n, int[][] edges, double[] succProb, int src, int dst) {
    List<List<double[]>> graph = new ArrayList<>();
    for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
    for (int i = 0; i < edges.length; i++) {
        graph.get(edges[i][0]).add(new double[]{edges[i][1], succProb[i]});
        graph.get(edges[i][1]).add(new double[]{edges[i][0], succProb[i]});
    }

    double[] maxProb = new double[n];
    maxProb[src] = 1.0;

    // Max-heap by probability
    PriorityQueue<double[]> pq = new PriorityQueue<>((a, b) -> Double.compare(b[1], a[1]));
    pq.offer(new double[]{src, 1.0});

    while (!pq.isEmpty()) {
        double[] curr = pq.poll();
        int u = (int) curr[0];
        double prob = curr[1];

        if (u == dst) return prob;
        if (prob < maxProb[u]) continue; // stale

        for (double[] edge : graph.get(u)) {
            int v = (int) edge[0];
            double newProb = prob * edge[1];
            if (newProb > maxProb[v]) {
                maxProb[v] = newProb;
                pq.offer(new double[]{v, newProb});
            }
        }
    }
    return 0.0;
}
```

### Key Insight

```
Standard Dijkstra: minimize sum     → min-heap, dist[v] = dist[u] + w
Max Probability:   maximize product → max-heap, prob[v] = prob[u] * w

Why Dijkstra still works:
  - Probabilities ∈ (0, 1], so products only decrease
  - Max-heap ensures we process highest probability first
  - Once popped, no better path can reach that node
  
Alternative: minimize -log(prob), since -log(a*b) = -log(a) + -log(b)
  converts product maximization to sum minimization (standard Dijkstra)
```

### Complexity
- Time: O((V + E) log V)
- Space: O(V + E)

---

## Pattern 10: Network Delay Time

### Signal
- Standard single-source shortest path application
- Find time for signal to reach ALL nodes (max of all shortest paths)
- LC 743: Network Delay Time

### Template (Java)

```java
public int networkDelayTime(int[][] times, int n, int k) {
    List<List<int[]>> graph = new ArrayList<>();
    for (int i = 0; i <= n; i++) graph.add(new ArrayList<>());
    for (int[] t : times) graph.get(t[0]).add(new int[]{t[1], t[2]});

    int[] dist = new int[n + 1]; // 1-indexed
    Arrays.fill(dist, Integer.MAX_VALUE);
    dist[k] = 0;

    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
    pq.offer(new int[]{0, k});

    while (!pq.isEmpty()) {
        int[] curr = pq.poll();
        int d = curr[0], u = curr[1];
        if (d > dist[u]) continue;

        for (int[] edge : graph.get(u)) {
            int v = edge[0], w = edge[1];
            if (dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
                pq.offer(new int[]{dist[v], v});
            }
        }
    }

    int ans = 0;
    for (int i = 1; i <= n; i++) {
        if (dist[i] == Integer.MAX_VALUE) return -1; // unreachable node
        ans = Math.max(ans, dist[i]);
    }
    return ans;
}
```

### Key Insight

```
"Network delay" = time for ALL nodes to receive the signal
                = max(shortest path from source to each node)

If any node is unreachable → return -1.
Otherwise → answer is max(dist[1..n]).
```

### Variants
- **Minimum time to inform all employees** (tree structure)
- **Minimum cost to reach destination** (basic Dijkstra)
- **Reachability within time T**: count nodes with dist[v] ≤ T

### Complexity
- Time: O((V + E) log V)
- Space: O(V + E)

---

## Common Pitfalls

1. **Using Dijkstra with negative weights** — breaks greedy property, produces wrong answers
2. **Integer overflow in Bellman-Ford** — check `dist[u] != MAX_VALUE` before adding
3. **Forgetting stale entry check in Dijkstra** — causes TLE on dense graphs
4. **Floyd-Warshall loop order** — `k` MUST be the outermost loop
5. **Bellman-Ford with K stops** — must clone array to prevent using current iteration's updates
6. **0-1 BFS pushing to wrong end** — 0-weight → front, 1-weight → back

---

## LeetCode Problem Mapping

| Problem | Pattern |
|---------|---------|
| 743 Network Delay Time | Dijkstra |
| 787 Cheapest Flights Within K Stops | Modified BF / BFS |
| 778 Swim in Rising Water | Minimax Dijkstra |
| 1514 Path with Maximum Probability | Max-product Dijkstra |
| 1631 Path With Minimum Effort | Minimax Dijkstra |
| 1091 Shortest Path in Binary Matrix | BFS |
| 127 Word Ladder | BFS |
| 1334 Find the City With Smallest Number of Neighbors | Floyd-Warshall |
| 2290 Minimum Obstacle Removal | 0-1 BFS |
| 1368 Min Cost to Make Valid Path in Grid | 0-1 BFS |
| 882 Reachable Nodes in Subdivided Graph | Dijkstra |
| 1976 Number of Ways to Arrive at Destination | Dijkstra + count |
| 2045 Second Minimum Time to Reach Destination | Modified BFS |
