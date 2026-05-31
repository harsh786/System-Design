# 44 - Advanced Graph Algorithms

> Beyond BFS/DFS/Shortest Path: connectivity decomposition, flow networks, and NP-hard reductions.

---

## Decision Flowchart

```
Graph Problem Identified
│
├─ "Find all groups that are mutually reachable" → SCC (Tarjan/Kosaraju)
├─ "Remove ONE edge/node to disconnect" → Bridges / Articulation Points
├─ "Decompose into 2-connected pieces" → Biconnected Components
├─ "Visit every EDGE exactly once" → Eulerian Path (Hierholzer)
├─ "Visit every NODE exactly once" → Hamiltonian (bitmask DP)
├─ "Maximum throughput / matching" → Network Flow
├─ "Assign pairs optimally" → Bipartite Matching
├─ "Boolean satisfiability with 2 vars/clause" → 2-SAT via SCC
└─ "Critical links whose removal disconnects" → Bridges (LC 1192)
```

---

## When These Appear in Interviews

| Algorithm | Level | Companies | Frequency |
|-----------|-------|-----------|-----------|
| Bridges / Articulation Points | L5+ | Google, Meta, Amazon | Medium |
| SCC (Tarjan/Kosaraju) | Staff+ | Google, Bloomberg | Low-Medium |
| Network Flow | Staff+ | Google, Jane Street, quant | Low |
| Bipartite Matching | L5+ | Google, Uber | Low-Medium |
| 2-SAT | Staff+ | Google, competitive | Rare |
| Eulerian Path | L5+ | Google, Uber (route planning) | Low |
| Hamiltonian Path | L4+ (bitmask DP) | Google, Meta | Medium (as DP) |

---

## SCC vs Bridges vs Articulation Points Comparison

| Property | SCC | Bridge | Articulation Point |
|----------|-----|--------|--------------------|
| Applies to | Directed graphs | Undirected graphs | Undirected graphs |
| Finds | Maximal sets of mutually reachable nodes | Edges whose removal disconnects | Nodes whose removal disconnects |
| Core idea | low-link collapse on stack | disc[u] < low[v] | disc[u] <= low[v] (with root special case) |
| Result | Partition of all vertices | Set of critical edges | Set of critical vertices |
| Use case | 2-SAT, condensation DAG | Network reliability | Network reliability |

---

## Flow Problems Recognition Signals

- "Maximum number of X that can simultaneously Y" → Max Flow
- "Minimum edges/nodes to remove to disconnect s from t" → Min Cut (= Max Flow)
- "Assign workers to jobs optimally" → Bipartite Matching (special flow)
- "Route maximum cargo through network" → Max Flow
- "Cheapest way to send K units" → Min Cost Flow
- "Maximum number of edge-disjoint paths" → Max Flow with unit capacities

---

## 1. Strongly Connected Components - Tarjan's Algorithm

### Signal
- Directed graph: find all maximal groups where every node can reach every other
- Condensation into DAG needed
- 2-SAT prerequisite

### Template (Java)

```java
class TarjanSCC {
    int n, timer = 0, sccCount = 0;
    List<List<Integer>> adj;
    int[] disc, low, comp;
    boolean[] onStack;
    Deque<Integer> stack = new ArrayDeque<>();

    // Returns number of SCCs; comp[v] = SCC id of vertex v
    int findSCCs() {
        disc = new int[n]; low = new int[n]; comp = new int[n];
        onStack = new boolean[n];
        Arrays.fill(disc, -1);

        for (int i = 0; i < n; i++)
            if (disc[i] == -1) dfs(i);
        return sccCount;
    }

    void dfs(int u) {
        disc[u] = low[u] = timer++;
        stack.push(u);
        onStack[u] = true;

        for (int v : adj.get(u)) {
            if (disc[v] == -1) {
                dfs(v);
                low[u] = Math.min(low[u], low[v]);
            } else if (onStack[v]) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }

        // u is root of an SCC
        if (low[u] == disc[u]) {
            while (true) {
                int v = stack.pop();
                onStack[v] = false;
                comp[v] = sccCount;
                if (v == u) break;
            }
            sccCount++;
        }
    }
}
```

### Visualization

```
Graph:  1 → 2 → 3 → 1,  3 → 4 → 5 → 6 → 4

DFS from 1:
  disc: 1=0, 2=1, 3=2, 4=3, 5=4, 6=5
  
  Backtrack from 6: low[6]=3 (back edge to 4)
  Backtrack from 5: low[5]=3
  Backtrack from 4: low[4]=3 = disc[4] → POP SCC: {4,5,6}
  Backtrack from 3: low[3]=0 (back edge to 1)
  Backtrack from 2: low[2]=0
  Backtrack from 1: low[1]=0 = disc[1] → POP SCC: {1,2,3}

Condensation DAG: SCC{1,2,3} → SCC{4,5,6}
```

### Complexity
- **Time:** O(V + E)
- **Space:** O(V)

---

## 2. Strongly Connected Components - Kosaraju's Algorithm

### Signal
Same as Tarjan's. Kosaraju is conceptually simpler (two-pass DFS) but uses more space (transpose graph).

### Template (Java)

```java
class KosarajuSCC {
    int n;
    List<List<Integer>> adj, radj; // original and transposed
    boolean[] visited;
    List<Integer> order = new ArrayList<>();
    int[] comp;

    int findSCCs() {
        visited = new boolean[n];
        comp = new int[n];

        // Pass 1: DFS on original, record finish order
        for (int i = 0; i < n; i++)
            if (!visited[i]) dfs1(i);

        // Pass 2: DFS on transposed in reverse finish order
        Arrays.fill(visited, false);
        int sccCount = 0;
        for (int i = n - 1; i >= 0; i--) {
            int v = order.get(i);
            if (!visited[v]) {
                dfs2(v, sccCount);
                sccCount++;
            }
        }
        return sccCount;
    }

    void dfs1(int u) {
        visited[u] = true;
        for (int v : adj.get(u))
            if (!visited[v]) dfs1(v);
        order.add(u);
    }

    void dfs2(int u, int id) {
        visited[u] = true;
        comp[u] = id;
        for (int v : radj.get(u))
            if (!visited[v]) dfs2(v, id);
    }
}
```

### Tarjan vs Kosaraju

| | Tarjan | Kosaraju |
|---|--------|----------|
| Passes | 1 DFS | 2 DFS |
| Extra graph | No | Yes (transpose) |
| Conceptual | Harder (low-link) | Easier |
| Practical | Faster (single pass) | Simpler to code |

### Complexity
- **Time:** O(V + E)
- **Space:** O(V + E) (transpose graph)

---

## 3. Bridges and Articulation Points

### Signal
- "Critical connection" / "critical link" whose removal disconnects the graph
- "Single point of failure" in a network
- LC 1192: Critical Connections in a Network

### Template (Java) - Bridges

```java
class BridgeFinder {
    int n, timer = 0;
    List<List<Integer>> adj;
    int[] disc, low;
    List<int[]> bridges = new ArrayList<>();

    void findBridges() {
        disc = new int[n]; low = new int[n];
        Arrays.fill(disc, -1);
        for (int i = 0; i < n; i++)
            if (disc[i] == -1) dfs(i, -1);
    }

    void dfs(int u, int parent) {
        disc[u] = low[u] = timer++;

        for (int v : adj.get(u)) {
            if (v == parent) continue;  // skip parent edge
            if (disc[v] == -1) {
                dfs(v, u);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) {         // BRIDGE condition
                    bridges.add(new int[]{u, v});
                }
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }
}
```

### Template (Java) - Articulation Points

```java
class ArticulationPointFinder {
    int n, timer = 0;
    List<List<Integer>> adj;
    int[] disc, low;
    boolean[] isAP;

    void findAPs() {
        disc = new int[n]; low = new int[n];
        isAP = new boolean[n];
        Arrays.fill(disc, -1);
        for (int i = 0; i < n; i++)
            if (disc[i] == -1) dfs(i, -1);
    }

    void dfs(int u, int parent) {
        disc[u] = low[u] = timer++;
        int children = 0;

        for (int v : adj.get(u)) {
            if (v == parent) continue;
            if (disc[v] == -1) {
                children++;
                dfs(v, u);
                low[u] = Math.min(low[u], low[v]);
                // Non-root: AP if no back edge from subtree bypasses u
                if (parent != -1 && low[v] >= disc[u])
                    isAP[u] = true;
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
        // Root: AP if it has 2+ DFS children
        if (parent == -1 && children > 1)
            isAP[u] = true;
    }
}
```

### Visualization

```
    1 --- 2 --- 3
    |         / |
    4       5 - 6
    
Bridges: (2,3) if no alternate path exists
         (1,4) — removing disconnects 4

Articulation Points: node 2 (separates {1,4} from {3,5,6})

Key insight:
  Bridge:            low[v] > disc[u]   (strictly greater)
  Articulation Pt:   low[v] >= disc[u]  (greater or equal, non-root)
```

### Complexity
- **Time:** O(V + E)
- **Space:** O(V)

---

## 4. Biconnected Components (Block-Cut Tree)

### Signal
- Partition edges into maximal 2-connected subgraphs
- "If any single node fails, which parts remain connected?"
- Building block-cut tree for structural decomposition

### Template (Java)

```java
class BiconnectedComponents {
    int n, timer = 0;
    List<List<Integer>> adj;
    int[] disc, low;
    Deque<int[]> edgeStack = new ArrayDeque<>();
    List<List<int[]>> components = new ArrayList<>(); // each BCC as edge list

    void findBCCs() {
        disc = new int[n]; low = new int[n];
        Arrays.fill(disc, -1);
        for (int i = 0; i < n; i++)
            if (disc[i] == -1) dfs(i, -1);
    }

    void dfs(int u, int parent) {
        disc[u] = low[u] = timer++;
        int children = 0;

        for (int v : adj.get(u)) {
            if (disc[v] == -1) {
                children++;
                edgeStack.push(new int[]{u, v});
                dfs(v, u);
                low[u] = Math.min(low[u], low[v]);

                // u is an articulation point or root with 2+ children
                if ((parent == -1 && children > 1) || 
                    (parent != -1 && low[v] >= disc[u])) {
                    List<int[]> bcc = new ArrayList<>();
                    while (true) {
                        int[] e = edgeStack.pop();
                        bcc.add(e);
                        if (e[0] == u && e[1] == v) break;
                    }
                    components.add(bcc);
                }
            } else if (v != parent && disc[v] < disc[u]) {
                edgeStack.push(new int[]{u, v});
                low[u] = Math.min(low[u], disc[v]);
            }
        }
        // Handle remaining edges for root
        if (parent == -1 && !edgeStack.isEmpty()) {
            List<int[]> bcc = new ArrayList<>();
            while (!edgeStack.isEmpty()) bcc.add(edgeStack.pop());
            components.add(bcc);
        }
    }
}
```

### Block-Cut Tree Concept

```
Original graph with APs {A, C}:

  [BCC1: {A,B,C}] --- A --- [BCC2: {A,D}]
                       |
                       C --- [BCC3: {C,E,F}]

Block-Cut Tree:
  - Blocks (BCCs) and cut vertices alternate
  - Tree structure reveals 2-connected decomposition
  - Useful for: queries about connectivity after removing a node
```

### Complexity
- **Time:** O(V + E)
- **Space:** O(V + E)

---

## 5. Eulerian Path / Circuit (Hierholzer's Algorithm)

### Signal
- "Visit every EDGE exactly once" (not every node)
- "Reconstruct itinerary" (LC 332)
- "Draw figure without lifting pen"
- Existence: all vertices even degree (circuit) or exactly 2 odd degree (path)

### Template (Java)

```java
class EulerianPath {
    // For directed graph: Hierholzer's algorithm
    Map<String, PriorityQueue<String>> graph = new HashMap<>();
    List<String> result = new LinkedList<>();

    // LC 332: Reconstruct Itinerary
    List<String> findItinerary(List<List<String>> tickets) {
        for (var t : tickets)
            graph.computeIfAbsent(t.get(0), k -> new PriorityQueue<>()).add(t.get(1));
        
        dfs("JFK");
        return result;
    }

    void dfs(String node) {
        PriorityQueue<String> nexts = graph.get(node);
        while (nexts != null && !nexts.isEmpty()) {
            dfs(nexts.poll());  // remove edge as we traverse
        }
        result.add(0, node);   // add to front (post-order)
    }

    // Generic undirected Eulerian circuit (adjacency list with edge removal)
    List<Integer> eulerCircuit(int n, List<List<int[]>> adj) {
        // adj[u] contains {v, edgeIndex} pairs
        boolean[] usedEdge = new boolean[/* num edges */];
        List<Integer> circuit = new ArrayList<>();
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(0);

        while (!stack.isEmpty()) {
            int u = stack.peek();
            boolean found = false;
            while (!adj.get(u).isEmpty()) {
                int[] edge = adj.get(u).remove(adj.get(u).size() - 1);
                if (!usedEdge[edge[1]]) {
                    usedEdge[edge[1]] = true;
                    stack.push(edge[0]);
                    found = true;
                    break;
                }
            }
            if (!found) {
                circuit.add(stack.pop());
            }
        }
        return circuit;
    }
}
```

### Existence Conditions

| | Undirected | Directed |
|---|-----------|----------|
| Circuit | All vertices even degree | in-degree = out-degree for all |
| Path | Exactly 2 vertices odd degree | Exactly 1 vertex with out-in=1 (start), 1 with in-out=1 (end) |

### Visualization

```
Hierholzer's on:  A → B → C → A → D → C

Step 1: Start at A, greedily follow edges removing them:
        A → B → C → A (stuck, have circuit)
Step 2: C still has unused edge. Expand from C:
        C → D → ... (but wait, let's re-trace)

Actually with stack approach:
  Push A, go to B, push B, go to C, push C, go to A (all A's edges used)
  Pop A → result. Peek C, go to D, push D, go to C (all C-D used)
  Pop C → result. Pop D → result. Pop C → result. Pop B → result. Pop A → result.
  
  Reverse: A → B → C → D → C → A  ✓ (visits all edges once)
```

### Complexity
- **Time:** O(E)
- **Space:** O(E)

---

## 6. Hamiltonian Path (Bitmask DP)

### Signal
- "Visit every NODE exactly once"
- Small n (n ≤ 20)
- Traveling Salesman Problem (TSP)
- "Shortest path visiting all nodes" (LC 847)

### Template (Java)

```java
class HamiltonianDP {
    // LC 847: Shortest Path Visiting All Nodes
    // BFS + bitmask approach
    int shortestPathLength(int[][] graph) {
        int n = graph.length;
        int fullMask = (1 << n) - 1;
        
        // dp[mask][i] = visited? (BFS explores shortest first)
        boolean[][] visited = new boolean[1 << n][n];
        Queue<int[]> queue = new LinkedList<>();

        // Start BFS from every node
        for (int i = 0; i < n; i++) {
            queue.offer(new int[]{1 << i, i, 0}); // mask, node, dist
            visited[1 << i][i] = true;
        }

        while (!queue.isEmpty()) {
            int[] curr = queue.poll();
            int mask = curr[0], node = curr[1], dist = curr[2];

            if (mask == fullMask) return dist;

            for (int next : graph[node]) {
                int nextMask = mask | (1 << next);
                if (!visited[nextMask][next]) {
                    visited[nextMask][next] = true;
                    queue.offer(new int[]{nextMask, next, dist + 1});
                }
            }
        }
        return -1;
    }

    // Classic TSP DP: minimum cost Hamiltonian cycle
    int tsp(int[][] dist) {
        int n = dist.length;
        int[][] dp = new int[1 << n][n];
        for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
        dp[1][0] = 0; // start at node 0

        for (int mask = 1; mask < (1 << n); mask++) {
            for (int u = 0; u < n; u++) {
                if ((mask & (1 << u)) == 0) continue;
                if (dp[mask][u] == Integer.MAX_VALUE / 2) continue;
                for (int v = 0; v < n; v++) {
                    if ((mask & (1 << v)) != 0) continue;
                    int newMask = mask | (1 << v);
                    dp[newMask][v] = Math.min(dp[newMask][v], dp[mask][u] + dist[u][v]);
                }
            }
        }
        // Return to start
        int ans = Integer.MAX_VALUE;
        int full = (1 << n) - 1;
        for (int u = 1; u < n; u++)
            ans = Math.min(ans, dp[full][u] + dist[u][0]);
        return ans;
    }
}
```

### Complexity
- **Time:** O(2^n * n^2)
- **Space:** O(2^n * n)
- Feasible for n ≤ 20

---

## 7. Network Flow - Ford-Fulkerson / Edmonds-Karp

### Signal
- "Maximum flow from source to sink"
- "Minimum cut to disconnect"
- "Maximum number of edge-disjoint paths"
- "Maximum bipartite matching" (reducible to flow)

### Template (Java) - Edmonds-Karp (BFS-based Ford-Fulkerson)

```java
class MaxFlow {
    int[][] capacity; // capacity[u][v]
    int[] parent;
    int n;

    int edmondsKarp(int source, int sink) {
        int maxFlow = 0;

        while (true) {
            // BFS to find augmenting path
            parent = new int[n];
            Arrays.fill(parent, -1);
            parent[source] = source;
            Queue<Integer> queue = new LinkedList<>();
            queue.offer(source);

            while (!queue.isEmpty() && parent[sink] == -1) {
                int u = queue.poll();
                for (int v = 0; v < n; v++) {
                    if (parent[v] == -1 && capacity[u][v] > 0) {
                        parent[v] = u;
                        queue.offer(v);
                    }
                }
            }

            if (parent[sink] == -1) break; // no augmenting path

            // Find bottleneck
            int pathFlow = Integer.MAX_VALUE;
            for (int v = sink; v != source; v = parent[v])
                pathFlow = Math.min(pathFlow, capacity[parent[v]][v]);

            // Update residual capacities
            for (int v = sink; v != source; v = parent[v]) {
                capacity[parent[v]][v] -= pathFlow;
                capacity[v][parent[v]] += pathFlow; // reverse edge
            }

            maxFlow += pathFlow;
        }
        return maxFlow;
    }
}
```

### Template (Java) - Dinic's Algorithm (faster for dense graphs)

```java
class Dinic {
    static final int INF = Integer.MAX_VALUE;
    int n;
    int[] level, iter;
    List<List<int[]>> graph; // {to, capacity, rev_index}

    void addEdge(int from, int to, int cap) {
        graph.get(from).add(new int[]{to, cap, graph.get(to).size()});
        graph.get(to).add(new int[]{from, 0, graph.get(from).size() - 1});
    }

    boolean bfs(int s, int t) {
        level = new int[n];
        Arrays.fill(level, -1);
        Queue<Integer> queue = new LinkedList<>();
        level[s] = 0;
        queue.offer(s);
        while (!queue.isEmpty()) {
            int v = queue.poll();
            for (int[] e : graph.get(v)) {
                if (e[1] > 0 && level[e[0]] < 0) {
                    level[e[0]] = level[v] + 1;
                    queue.offer(e[0]);
                }
            }
        }
        return level[t] >= 0;
    }

    int dfs(int v, int t, int f) {
        if (v == t) return f;
        for (; iter[v] < graph.get(v).size(); iter[v]++) {
            int[] e = graph.get(v).get(iter[v]);
            if (e[1] > 0 && level[v] < level[e[0]]) {
                int d = dfs(e[0], t, Math.min(f, e[1]));
                if (d > 0) {
                    e[1] -= d;
                    graph.get(e[0]).get(e[2])[1] += d;
                    return d;
                }
            }
        }
        return 0;
    }

    int maxflow(int s, int t) {
        int flow = 0;
        while (bfs(s, t)) {
            iter = new int[n];
            int d;
            while ((d = dfs(s, t, INF)) > 0)
                flow += d;
        }
        return flow;
    }
}
```

### Max-Flow Min-Cut Theorem

```
Max Flow = Min Cut

To find min cut after running max flow:
1. Run BFS/DFS from source on residual graph (edges with remaining capacity)
2. Reachable vertices = S, unreachable = T
3. Cut edges: all original edges from S to T with full capacity used

Application: minimum number of edges to remove to disconnect s from t
```

### Complexity
- **Edmonds-Karp:** O(V * E^2)
- **Dinic's:** O(V^2 * E) — O(E√V) for unit capacity graphs

---

## 8. Bipartite Matching

### Signal
- "Maximum matching in bipartite graph"
- "Assign workers to jobs" (each worker does one job, each job by one worker)
- "Maximum number of pairs"
- König's theorem: in bipartite graph, max matching = min vertex cover

### Template (Java) - Hungarian / Kuhn's Algorithm

```java
class BipartiteMatching {
    int n, m; // left side n, right side m
    List<List<Integer>> adj; // adj[left_node] = list of right_nodes
    int[] matchL, matchR;   // matchL[i] = right node matched to left i
    boolean[] visited;

    int maxMatching() {
        matchL = new int[n]; matchR = new int[m];
        Arrays.fill(matchL, -1); Arrays.fill(matchR, -1);

        int result = 0;
        for (int u = 0; u < n; u++) {
            visited = new boolean[m];
            if (dfs(u)) result++;
        }
        return result;
    }

    boolean dfs(int u) {
        for (int v : adj.get(u)) {
            if (!visited[v]) {
                visited[v] = true;
                // If v is free or we can re-match v's current partner
                if (matchR[v] == -1 || dfs(matchR[v])) {
                    matchL[u] = v;
                    matchR[v] = u;
                    return true;
                }
            }
        }
        return false;
    }
}
```

### Template (Java) - Hopcroft-Karp (faster)

```java
class HopcroftKarp {
    int n, m;
    List<List<Integer>> adj;
    int[] matchL, matchR, dist;
    static final int INF = Integer.MAX_VALUE;

    int maxMatching() {
        matchL = new int[n]; matchR = new int[m];
        Arrays.fill(matchL, -1); Arrays.fill(matchR, -1);
        int matching = 0;

        while (bfs()) {
            for (int u = 0; u < n; u++)
                if (matchL[u] == -1 && dfs(u))
                    matching++;
        }
        return matching;
    }

    boolean bfs() {
        dist = new int[n];
        Queue<Integer> queue = new LinkedList<>();
        for (int u = 0; u < n; u++) {
            if (matchL[u] == -1) {
                dist[u] = 0;
                queue.offer(u);
            } else {
                dist[u] = INF;
            }
        }
        boolean found = false;
        while (!queue.isEmpty()) {
            int u = queue.poll();
            for (int v : adj.get(u)) {
                int w = matchR[v]; // partner of v on right side
                if (w == -1) {
                    found = true;
                } else if (dist[w] == INF) {
                    dist[w] = dist[u] + 1;
                    queue.offer(w);
                }
            }
        }
        return found;
    }

    boolean dfs(int u) {
        for (int v : adj.get(u)) {
            int w = matchR[v];
            if (w == -1 || (dist[w] == dist[u] + 1 && dfs(w))) {
                matchL[u] = v;
                matchR[v] = u;
                return true;
            }
        }
        dist[u] = INF;
        return false;
    }
}
```

### Complexity
- **Kuhn's:** O(V * E)
- **Hopcroft-Karp:** O(E * √V)

---

## 9. 2-SAT (Implication Graph + SCC)

### Signal
- Boolean formula with clauses of exactly 2 literals
- "Is there an assignment satisfying all constraints?"
- "Exactly one of X or Y must be true" type constraints
- Scheduling with mutual exclusions

### Template (Java)

```java
class TwoSAT {
    // Variables: 0..n-1. Literal x = 2*x, literal ¬x = 2*x+1
    int n;
    List<List<Integer>> adj, radj;
    int[] comp;
    boolean[] assignment;

    TwoSAT(int n) {
        this.n = n;
        adj = new ArrayList<>(); radj = new ArrayList<>();
        for (int i = 0; i < 2 * n; i++) {
            adj.add(new ArrayList<>()); radj.add(new ArrayList<>());
        }
    }

    int neg(int lit) { return lit ^ 1; }

    // Add clause (a OR b): means ¬a → b AND ¬b → a
    void addClause(int a, int b) {
        adj.get(neg(a)).add(b);
        adj.get(neg(b)).add(a);
        radj.get(b).add(neg(a));
        radj.get(a).add(neg(b));
    }

    // "At least one of a, b": addClause(a, b)
    // "Exactly one of a, b": addClause(a, b) + addClause(neg(a), neg(b))
    // "a must be true": addClause(a, a)

    boolean solve() {
        // Run Kosaraju's SCC on implication graph
        // ... (use Kosaraju from pattern #2)
        
        // Check satisfiability
        for (int i = 0; i < n; i++) {
            if (comp[2 * i] == comp[2 * i + 1])
                return false; // x and ¬x in same SCC = contradiction
        }

        // Extract assignment: x is true if comp[x] > comp[¬x]
        // (in topological order of condensation)
        assignment = new boolean[n];
        for (int i = 0; i < n; i++)
            assignment[i] = comp[2 * i] > comp[2 * i + 1];
        return true;
    }
}
```

### Visualization

```
Problem: (x₁ ∨ x₂) ∧ (¬x₁ ∨ x₃) ∧ (¬x₂ ∨ ¬x₃)

Implication graph:
  ¬x₁ → x₂,  ¬x₂ → x₁    (from clause 1)
  x₁ → x₃,   ¬x₃ → ¬x₁   (from clause 2)  
  x₂ → ¬x₃,  x₃ → ¬x₂    (from clause 3)

Find SCCs. If xᵢ and ¬xᵢ are in different SCCs → satisfiable.
Assignment: x₁=T, x₂=T, x₃=F  ✓
```

### Complexity
- **Time:** O(V + E) where V = 2n literals, E = 2 * (number of clauses)
- **Space:** O(V + E)

---

## 10. Critical Connections (LC 1192)

### Signal
- Direct application of bridge-finding (Pattern #3)
- "Find all edges whose removal increases the number of connected components"

### Template (Java)

```java
class CriticalConnections {
    int timer = 0;
    List<List<Integer>> graph;
    int[] disc, low;
    List<List<Integer>> result = new ArrayList<>();

    public List<List<Integer>> criticalConnections(int n, List<List<Integer>> connections) {
        graph = new ArrayList<>();
        disc = new int[n]; low = new int[n];
        Arrays.fill(disc, -1);

        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (var c : connections) {
            graph.get(c.get(0)).add(c.get(1));
            graph.get(c.get(1)).add(c.get(0));
        }

        dfs(0, -1);
        return result;
    }

    void dfs(int u, int parent) {
        disc[u] = low[u] = timer++;
        for (int v : graph.get(u)) {
            if (v == parent) continue;
            if (disc[v] == -1) {
                dfs(v, u);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u])
                    result.add(Arrays.asList(u, v));
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }
}
```

### Edge Case: Parallel Edges
When the graph has multiple edges between same pair of nodes, track edge index instead of parent node to avoid skipping valid back edges.

### Complexity
- **Time:** O(V + E)
- **Space:** O(V + E)

---

## 11. Minimum Cost Flow

### Signal (System Design Context)
- "Route K units from source to sink at minimum total cost"
- "Cheapest assignment where each resource has a cost"
- Supply chain optimization, transportation problems
- Weighted bipartite matching (assignment problem)

### Concept

```
Each edge has: (capacity, cost_per_unit)

Goal: Send exactly F units from s to t minimizing total cost.

Algorithm (Successive Shortest Paths):
1. While flow < F:
   a. Find shortest path (by cost) from s to t in residual graph
      (use Bellman-Ford or SPFA due to negative edges from reverse arcs)
   b. Augment along this path
   c. Update residual graph

Alternative: Cycle-canceling (find negative cost cycles and push flow around them)
```

### Template (Java) - SPFA-based Min Cost Flow

```java
class MinCostFlow {
    static final int INF = Integer.MAX_VALUE / 2;
    int n;
    List<List<int[]>> graph; // {to, cap, cost, rev_idx}

    void addEdge(int from, int to, int cap, int cost) {
        graph.get(from).add(new int[]{to, cap, cost, graph.get(to).size()});
        graph.get(to).add(new int[]{from, 0, -cost, graph.get(from).size() - 1});
    }

    int[] minCostFlow(int s, int t, int maxFlow) {
        int totalFlow = 0, totalCost = 0;

        while (totalFlow < maxFlow) {
            // SPFA (Bellman-Ford with queue) to find min cost path
            int[] dist = new int[n], prevv = new int[n], preve = new int[n];
            boolean[] inQueue = new boolean[n];
            Arrays.fill(dist, INF);
            dist[s] = 0;
            Queue<Integer> queue = new LinkedList<>();
            queue.offer(s); inQueue[s] = true;

            while (!queue.isEmpty()) {
                int v = queue.poll(); inQueue[v] = false;
                for (int i = 0; i < graph.get(v).size(); i++) {
                    int[] e = graph.get(v).get(i);
                    if (e[1] > 0 && dist[v] + e[2] < dist[e[0]]) {
                        dist[e[0]] = dist[v] + e[2];
                        prevv[e[0]] = v; preve[e[0]] = i;
                        if (!inQueue[e[0]]) { queue.offer(e[0]); inQueue[e[0]] = true; }
                    }
                }
            }

            if (dist[t] == INF) break;

            // Find bottleneck
            int d = maxFlow - totalFlow;
            for (int v = t; v != s; v = prevv[v])
                d = Math.min(d, graph.get(prevv[v]).get(preve[v])[1]);

            // Augment
            totalFlow += d;
            totalCost += d * dist[t];
            for (int v = t; v != s; v = prevv[v]) {
                int[] e = graph.get(prevv[v]).get(preve[v]);
                e[1] -= d;
                graph.get(v).get(e[3])[1] += d;
            }
        }
        return new int[]{totalFlow, totalCost};
    }
}
```

### System Design Applications
- **Load balancing:** Route requests to servers minimizing latency (cost) respecting capacity
- **Task scheduling:** Assign tasks to machines with time/cost constraints
- **Network routing:** Route data packets minimizing cost while respecting bandwidth

### Complexity
- **Time:** O(V * E * F) with SPFA, O(F * E * log V) with Dijkstra + potentials
- **Space:** O(V + E)

---

## 12. Interactive Problems with Graphs

### Signal
- "Determine graph structure using queries"
- "Find the hidden edge/path with minimum queries"
- Adaptive algorithms, information-theoretic lower bounds

### Approach Template

```java
class InteractiveGraphProblem {
    // Example: Find a hidden edge in complete graph using "is there an edge 
    // between sets S and T?" queries
    
    // Strategy: Binary search on vertex sets
    int[] findEdge(int n, QueryOracle oracle) {
        List<Integer> candidates = new ArrayList<>();
        for (int i = 0; i < n; i++) candidates.add(i);

        // Find one endpoint via binary search
        int u = findEndpoint(candidates, oracle);
        
        // Find the other endpoint
        List<Integer> others = new ArrayList<>();
        for (int i = 0; i < n; i++) if (i != u) others.add(i);
        int v = findNeighbor(u, others, oracle);
        
        return new int[]{u, v};
    }

    int findEndpoint(List<Integer> nodes, QueryOracle oracle) {
        if (nodes.size() == 1) return nodes.get(0);
        int mid = nodes.size() / 2;
        List<Integer> left = nodes.subList(0, mid);
        List<Integer> right = nodes.subList(mid, nodes.size());
        // Query: does the hidden structure involve the left half?
        if (oracle.query(left)) return findEndpoint(left, oracle);
        return findEndpoint(right, oracle);
    }
    
    int findNeighbor(int u, List<Integer> candidates, QueryOracle oracle) {
        if (candidates.size() == 1) return candidates.get(0);
        int mid = candidates.size() / 2;
        List<Integer> left = candidates.subList(0, mid);
        // Query: is u connected to any node in left half?
        if (oracle.queryEdge(u, left)) return findNeighbor(u, left, oracle);
        return findNeighbor(u, candidates.subList(mid, candidates.size()), oracle);
    }
}
```

### Common Interactive Graph Patterns

| Problem | Strategy | Query Complexity |
|---------|----------|-----------------|
| Find hidden edge | Binary search on sets | O(log n) |
| Find hidden path | BFS-like expansion with queries | O(n log n) |
| Determine bipartiteness | Query edges adaptively | O(n log n) |
| Find shortest path interactively | Layered exploration | Varies |

### Key Principles
1. **Information theory:** Each query gives 1 bit → need at least log₂(answer space) queries
2. **Binary search on sets:** Divide candidate set in half each query
3. **Adaptive vs non-adaptive:** Adaptive (queries depend on answers) usually needs fewer queries

---

## Summary Table

| # | Algorithm | Time | Space | Key Condition |
|---|-----------|------|-------|---------------|
| 1 | Tarjan SCC | O(V+E) | O(V) | Directed graph |
| 2 | Kosaraju SCC | O(V+E) | O(V+E) | Directed graph |
| 3 | Bridges/APs | O(V+E) | O(V) | Undirected graph |
| 4 | Biconnected Comp | O(V+E) | O(V+E) | Undirected graph |
| 5 | Eulerian (Hierholzer) | O(E) | O(E) | Degree conditions met |
| 6 | Hamiltonian (bitmask) | O(2ⁿ·n²) | O(2ⁿ·n) | n ≤ 20 |
| 7 | Max Flow (Dinic) | O(V²E) | O(V+E) | Capacity graph |
| 8 | Bipartite Match (HK) | O(E√V) | O(V+E) | Bipartite graph |
| 9 | 2-SAT | O(V+E) | O(V+E) | 2 literals/clause |
| 10 | Critical Connections | O(V+E) | O(V+E) | Undirected graph |
| 11 | Min Cost Flow | O(VEF) | O(V+E) | Capacity + cost |
| 12 | Interactive | O(log n) per query | O(n) | Query access only |

---

## Variants and Extensions

### SCC Applications
- **Condensation DAG:** Collapse each SCC to a single node → DAG for DP
- **Reachability:** After condensation, topological sort answers reachability
- **Minimum edges to make strongly connected:** max(sources, sinks) in condensation

### Flow Extensions
- **Vertex capacity:** Split node v into v_in → v_out with edge capacity
- **Multiple sources/sinks:** Add super-source/super-sink
- **Lower bounds on flow:** Transform to regular max-flow with adjusted capacities
- **Maximum weight closure:** Reduction to min-cut (project selection problem)

### Bridge/AP Extensions
- **Bridge tree:** Contract each 2-edge-connected component → tree of bridges
- **Online bridge finding:** Maintain bridges as edges are added
- **Edge connectivity:** Minimum number of edges to disconnect = min cut over all pairs
