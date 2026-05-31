# Graphs - Complete Pattern Guide

---

## Algorithm Selection Decision Tree

```
Graph Problem?
│
├─ Shortest path?
│   ├─ Unweighted? ────────────────→ BFS
│   ├─ Non-negative weights? ──────→ Dijkstra
│   ├─ Negative weights? ──────────→ Bellman-Ford
│   ├─ All pairs? ─────────────────→ Floyd-Warshall
│   └─ Weights 0/1 only? ─────────→ 0-1 BFS (deque)
│
├─ Connectivity?
│   ├─ Static components? ─────────→ DFS/BFS or Union-Find
│   ├─ Dynamic (online additions)? → Union-Find
│   └─ Bridges/articulation? ──────→ Tarjan's DFS
│
├─ Ordering / Dependencies?
│   └─ DAG ordering? ─────────────→ Topological Sort (Kahn's or DFS)
│
├─ Cycle detection?
│   ├─ Directed graph? ────────────→ DFS 3-coloring
│   └─ Undirected graph? ──────────→ Union-Find or DFS with parent
│
├─ Minimum Spanning Tree?
│   ├─ Sparse graph? ─────────────→ Kruskal's (sort edges + UF)
│   └─ Dense graph? ──────────────→ Prim's (grow with heap)
│
├─ Strongly connected components?
│   └─ ────────────────────────────→ Tarjan's or Kosaraju's
│
└─ Bipartite / Coloring?
    └─ ────────────────────────────→ BFS 2-coloring
```

---

## Pattern 1: BFS (Shortest Path in Unweighted Graph)

### Template
```java
int bfs(int start, int target, Map<Integer, List<Integer>> graph) {
    Queue<Integer> queue = new LinkedList<>();
    Set<Integer> visited = new HashSet<>();
    queue.offer(start);
    visited.add(start);
    int level = 0;
    
    while (!queue.isEmpty()) {
        int size = queue.size();
        for (int i = 0; i < size; i++) {
            int node = queue.poll();
            if (node == target) return level;
            for (int neighbor : graph.get(node)) {
                if (!visited.contains(neighbor)) {
                    visited.add(neighbor);
                    queue.offer(neighbor);
                }
            }
        }
        level++;
    }
    return -1;  // unreachable
}
```

### Grid BFS (Shortest Path in Binary Matrix)
```java
int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0},{1,1},{1,-1},{-1,1},{-1,-1}};
Queue<int[]> queue = new LinkedList<>();
queue.offer(new int[]{0, 0});
grid[0][0] = 1;  // mark visited
int dist = 1;

while (!queue.isEmpty()) {
    int size = queue.size();
    for (int i = 0; i < size; i++) {
        int[] cell = queue.poll();
        if (cell[0] == m-1 && cell[1] == n-1) return dist;
        for (int[] d : dirs) {
            int r = cell[0]+d[0], c = cell[1]+d[1];
            if (r >= 0 && r < m && c >= 0 && c < n && grid[r][c] == 0) {
                grid[r][c] = 1;
                queue.offer(new int[]{r, c});
            }
        }
    }
    dist++;
}
```

---

## Pattern 2: DFS (Explore All / Cycle Detection)

### Template: Connected Components
```java
int components = 0;
boolean[] visited = new boolean[n];
for (int i = 0; i < n; i++) {
    if (!visited[i]) {
        components++;
        dfs(graph, i, visited);
    }
}

void dfs(Map<Integer, List<Integer>> graph, int node, boolean[] visited) {
    visited[node] = true;
    for (int neighbor : graph.getOrDefault(node, List.of())) {
        if (!visited[neighbor]) dfs(graph, neighbor, visited);
    }
}
```

### Cycle Detection in Directed Graph (3-Color)
```java
// WHITE=0 (unvisited), GRAY=1 (in current DFS path), BLACK=2 (fully processed)
int[] color = new int[n];

boolean hasCycle(int node, List<List<Integer>> graph) {
    color[node] = 1;  // GRAY: processing
    for (int neighbor : graph.get(node)) {
        if (color[neighbor] == 1) return true;   // back edge → CYCLE!
        if (color[neighbor] == 0 && hasCycle(neighbor, graph)) return true;
    }
    color[node] = 2;  // BLACK: done
    return false;
}
```

### Cycle Detection in Undirected Graph
```java
boolean dfs(int node, int parent, List<List<Integer>> graph, boolean[] visited) {
    visited[node] = true;
    for (int neighbor : graph.get(node)) {
        if (neighbor == parent) continue;          // skip edge we came from
        if (visited[neighbor]) return true;        // cycle!
        if (dfs(neighbor, node, graph, visited)) return true;
    }
    return false;
}
```

---

## Pattern 3: Topological Sort

### Kahn's Algorithm (BFS-based)
```java
int[] inDegree = new int[n];
for (int[] edge : edges) inDegree[edge[1]]++;

Queue<Integer> queue = new LinkedList<>();
for (int i = 0; i < n; i++)
    if (inDegree[i] == 0) queue.offer(i);

List<Integer> order = new ArrayList<>();
while (!queue.isEmpty()) {
    int node = queue.poll();
    order.add(node);
    for (int neighbor : graph.get(node)) {
        if (--inDegree[neighbor] == 0)
            queue.offer(neighbor);
    }
}
if (order.size() != n) // CYCLE EXISTS
```

### DFS-based Topological Sort
```java
boolean[] visited = new boolean[n];
Deque<Integer> stack = new ArrayDeque<>();

for (int i = 0; i < n; i++)
    if (!visited[i]) topoSort(i, graph, visited, stack);

void topoSort(int node, ...) {
    visited[node] = true;
    for (int neighbor : graph.get(node))
        if (!visited[neighbor]) topoSort(neighbor, ...);
    stack.push(node);  // add AFTER all descendants processed
}
// Result: pop from stack
```

### Problems
- Course Schedule I (can finish? = is DAG?)
- Course Schedule II (find valid order)
- Alien Dictionary (derive letter ordering from sorted words)
- Parallel Courses (min semesters = longest path in DAG)

---

## Pattern 4: Dijkstra's Algorithm

### Template
```java
int[] dist = new int[n];
Arrays.fill(dist, Integer.MAX_VALUE);
dist[source] = 0;
PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[1] - b[1]);
pq.offer(new int[]{source, 0});

while (!pq.isEmpty()) {
    int[] curr = pq.poll();
    int u = curr[0], d = curr[1];
    if (d > dist[u]) continue;  // stale entry (already found shorter)
    
    for (int[] edge : graph.get(u)) {
        int v = edge[0], w = edge[1];
        if (dist[u] + w < dist[v]) {
            dist[v] = dist[u] + w;
            pq.offer(new int[]{v, dist[v]});
        }
    }
}
```

### Visualization
```
      A ──2──→ B ──1──→ D
      |        ↑        ↑
      4        3        2
      ↓        |        |
      C ───────┘──5────→┘

Process order: A(0) → B(2) → C(4) → D(3)
Final: dist[A]=0, dist[B]=2, dist[C]=4, dist[D]=3
Path to D: A→B→D (cost 3)
```

### Variants
| Variant | Modification |
|---------|-------------|
| K stops max (Cheapest Flights) | BFS with level limit (no PQ needed) or modified Dijkstra |
| Max probability path | Negate log(prob), or use max-heap with multiplication |
| Swim in Rising Water | Dijkstra where edge weight = max(elevation) |

---

## Pattern 5: Bellman-Ford

### Template
```java
int[] dist = new int[n];
Arrays.fill(dist, Integer.MAX_VALUE);
dist[source] = 0;

for (int i = 0; i < n - 1; i++) {          // relax n-1 times
    for (int[] edge : edges) {              // all edges
        int u = edge[0], v = edge[1], w = edge[2];
        if (dist[u] != Integer.MAX_VALUE && dist[u] + w < dist[v])
            dist[v] = dist[u] + w;
    }
}

// Negative cycle detection: one more pass
for (int[] edge : edges)
    if (dist[edge[0]] != Integer.MAX_VALUE && dist[edge[0]] + edge[2] < dist[edge[1]])
        return "NEGATIVE CYCLE";
```

**When to use over Dijkstra:** negative edge weights, at most K edges constraint

---

## Pattern 6: Union-Find (Disjoint Set Union)

### Template
```java
class UnionFind {
    int[] parent, rank;
    int components;
    
    UnionFind(int n) {
        parent = new int[n]; rank = new int[n];
        components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }
    
    int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);  // path compression
        return parent[x];
    }
    
    boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return false;  // already connected
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
        components--;
        return true;
    }
    
    boolean connected(int x, int y) { return find(x) == find(y); }
}
```

### When to Use Union-Find vs DFS/BFS

| Scenario | Use |
|----------|-----|
| Static connectivity query | Either (DFS once, or UF) |
| Dynamic edges added | Union-Find (DFS would need redo) |
| Detect cycle in undirected | Union-Find |
| Kruskal's MST | Union-Find |
| Accounts merge / equivalence | Union-Find |
| Islands with online additions | Union-Find |

---

## Pattern 7: Bipartite Check (2-Coloring)

### Template
```java
int[] color = new int[n];
Arrays.fill(color, -1);

for (int i = 0; i < n; i++) {
    if (color[i] != -1) continue;
    Queue<Integer> queue = new LinkedList<>();
    queue.offer(i);
    color[i] = 0;
    while (!queue.isEmpty()) {
        int node = queue.poll();
        for (int neighbor : graph.get(node)) {
            if (color[neighbor] == -1) {
                color[neighbor] = 1 - color[node];  // opposite color
                queue.offer(neighbor);
            } else if (color[neighbor] == color[node]) {
                return false;  // NOT bipartite
            }
        }
    }
}
return true;
```

---

## Pattern 8: Minimum Spanning Tree

### Kruskal's (Sort Edges + Union-Find)
```java
Arrays.sort(edges, (a,b) -> a[2] - b[2]);  // sort by weight
UnionFind uf = new UnionFind(n);
int mstCost = 0, edgesUsed = 0;

for (int[] edge : edges) {
    if (uf.union(edge[0], edge[1])) {
        mstCost += edge[2];
        if (++edgesUsed == n - 1) break;
    }
}
```

### Prim's (Grow from Vertex with Heap)
```java
boolean[] visited = new boolean[n];
PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[1] - b[1]);
pq.offer(new int[]{0, 0});  // (node, weight)
int mstCost = 0;

while (!pq.isEmpty()) {
    int[] curr = pq.poll();
    if (visited[curr[0]]) continue;
    visited[curr[0]] = true;
    mstCost += curr[1];
    for (int[] edge : graph.get(curr[0]))
        if (!visited[edge[0]])
            pq.offer(new int[]{edge[0], edge[1]});
}
```

---

## Pattern 9: Clone Graph (DFS/BFS with Map)

```java
Map<Node, Node> visited = new HashMap<>();

Node cloneGraph(Node node) {
    if (node == null) return null;
    if (visited.containsKey(node)) return visited.get(node);
    
    Node clone = new Node(node.val);
    visited.put(node, clone);
    for (Node neighbor : node.neighbors)
        clone.neighbors.add(cloneGraph(neighbor));
    return clone;
}
```

---

## Pattern 10: Strongly Connected Components (Tarjan's)

```java
int index = 0;
int[] disc = new int[n], low = new int[n];
boolean[] onStack = new boolean[n];
Deque<Integer> stack = new ArrayDeque<>();
Arrays.fill(disc, -1);

void tarjan(int u) {
    disc[u] = low[u] = index++;
    stack.push(u);
    onStack[u] = true;
    
    for (int v : graph.get(u)) {
        if (disc[v] == -1) {
            tarjan(v);
            low[u] = Math.min(low[u], low[v]);
        } else if (onStack[v]) {
            low[u] = Math.min(low[u], disc[v]);
        }
    }
    
    if (low[u] == disc[u]) {  // u is root of SCC
        List<Integer> scc = new ArrayList<>();
        int w;
        do {
            w = stack.pop();
            onStack[w] = false;
            scc.add(w);
        } while (w != u);
        components.add(scc);
    }
}
```

---

## Pattern 11: Bridges and Articulation Points

```java
// Bridge: edge (u,v) where low[v] > disc[u]
// Articulation Point: low[v] >= disc[u] (for non-root), or root with 2+ DFS children

void dfs(int u, int parent) {
    disc[u] = low[u] = timer++;
    int children = 0;
    
    for (int v : graph.get(u)) {
        if (disc[v] == -1) {
            children++;
            dfs(v, u);
            low[u] = Math.min(low[u], low[v]);
            
            if (low[v] > disc[u]) bridges.add(new int[]{u, v});  // bridge
            if (parent != -1 && low[v] >= disc[u]) articulationPoints.add(u);
        } else if (v != parent) {
            low[u] = Math.min(low[u], disc[v]);
        }
    }
    if (parent == -1 && children > 1) articulationPoints.add(u);  // root case
}
```

---

## Pattern 12: Multi-Source BFS / 0-1 BFS

### Multi-Source BFS
```java
// All sources in queue at start → expand simultaneously
Queue<int[]> queue = new LinkedList<>();
for (each source) queue.offer(source);
// Standard BFS from here
```

### 0-1 BFS (edge weights 0 or 1)
```java
Deque<int[]> deque = new ArrayDeque<>();
deque.offerFirst(new int[]{source, 0});
int[] dist = new int[n]; Arrays.fill(dist, Integer.MAX_VALUE);
dist[source] = 0;

while (!deque.isEmpty()) {
    int[] curr = deque.pollFirst();
    int u = curr[0], d = curr[1];
    if (d > dist[u]) continue;
    for (int[] edge : graph.get(u)) {
        int v = edge[0], w = edge[1];
        if (dist[u] + w < dist[v]) {
            dist[v] = dist[u] + w;
            if (w == 0) deque.offerFirst(new int[]{v, dist[v]});   // front
            else deque.offerLast(new int[]{v, dist[v]});           // back
        }
    }
}
```

---

## Complexity Reference

| Algorithm | Time | Space | Use Case |
|-----------|------|-------|----------|
| BFS | O(V+E) | O(V) | Shortest unweighted |
| DFS | O(V+E) | O(V) | Explore all, cycles |
| Dijkstra | O((V+E)logV) | O(V) | Shortest, non-negative |
| Bellman-Ford | O(VE) | O(V) | Shortest, negative ok |
| Floyd-Warshall | O(V³) | O(V²) | All pairs |
| Kahn's Topo | O(V+E) | O(V) | DAG ordering |
| Union-Find | O(α(n))≈O(1) | O(V) | Dynamic connectivity |
| Kruskal MST | O(E logE) | O(V) | Sparse MST |
| Prim MST | O((V+E)logV) | O(V) | Dense MST |
| Tarjan SCC | O(V+E) | O(V) | Strongly connected |
