# 18. Graph Traversal & General Graph Patterns

## Algorithm Selection Decision Tree

```
Graph Problem?
├── Shortest path needed?
│   ├── Unweighted → BFS (Pattern 1)
│   ├── Multiple sources → Multi-Source BFS (Pattern 2)
│   └── Weighted → Dijkstra / Bellman-Ford (separate doc)
├── Connectivity / Reachability?
│   ├── Count components → DFS/BFS + visited (Pattern 3)
│   ├── Flood fill / region → DFS (Pattern 3)
│   └── Clone structure → HashMap DFS (Pattern 8)
├── Cycle detection?
│   ├── Directed graph → 3-color DFS (Pattern 4)
│   └── Undirected graph → Parent-tracking DFS (Pattern 5)
├── Enumerate all paths?
│   └── DFS + Backtracking (Pattern 6)
├── Graph coloring / partitioning?
│   └── Bipartite check (Pattern 7)
└── No explicit graph given?
    └── Implicit Graph modeling (Pattern 10)
```

---

## Complexity Reference Table

| Pattern | Time | Space | Notes |
|---------|------|-------|-------|
| BFS Shortest Path | O(V + E) | O(V) | Queue + visited |
| Multi-Source BFS | O(V + E) | O(V) | All sources enqueued initially |
| DFS Connected Components | O(V + E) | O(V) | Recursion stack / visited |
| Cycle Detection (Directed) | O(V + E) | O(V) | 3-color states |
| Cycle Detection (Undirected) | O(V + E) | O(V) | Parent tracking |
| DFS All Paths | O(V! or 2^V) | O(V·paths) | Exponential in worst case |
| Bipartite Check | O(V + E) | O(V) | 2-color BFS/DFS |
| Clone Graph | O(V + E) | O(V) | HashMap for mapping |
| Word Ladder (Implicit) | O(M²·N) | O(M²·N) | M=word len, N=word count |

Where V = vertices, E = edges unless noted otherwise.

---

## Pattern 1: BFS Shortest Path (Unweighted)

### Signal
- Find **shortest path / minimum steps** in unweighted graph or grid
- "Minimum number of moves/operations to reach target"
- Level-by-level exploration needed

### Template (Java)

```java
// Generic BFS on adjacency list
public int bfsShortestPath(Map<Integer, List<Integer>> graph, int src, int dest) {
    Queue<Integer> queue = new LinkedList<>();
    Set<Integer> visited = new HashSet<>();
    queue.offer(src);
    visited.add(src);
    int distance = 0;

    while (!queue.isEmpty()) {
        int size = queue.size(); // level boundary
        for (int i = 0; i < size; i++) {
            int node = queue.poll();
            if (node == dest) return distance;
            for (int neighbor : graph.getOrDefault(node, List.of())) {
                if (!visited.contains(neighbor)) {
                    visited.add(neighbor);
                    queue.offer(neighbor);
                }
            }
        }
        distance++;
    }
    return -1; // unreachable
}

// BFS on grid (4-directional)
public int bfsGrid(int[][] grid, int[] start, int[] end) {
    int rows = grid.length, cols = grid[0].length;
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
    boolean[][] visited = new boolean[rows][cols];
    Queue<int[]> queue = new LinkedList<>();
    queue.offer(start);
    visited[start[0]][start[1]] = true;
    int steps = 0;

    while (!queue.isEmpty()) {
        int size = queue.size();
        for (int i = 0; i < size; i++) {
            int[] cell = queue.poll();
            if (cell[0] == end[0] && cell[1] == end[1]) return steps;
            for (int[] d : dirs) {
                int nr = cell[0] + d[0], nc = cell[1] + d[1];
                if (nr >= 0 && nr < rows && nc >= 0 && nc < cols
                    && !visited[nr][nc] && grid[nr][nc] != 1) { // 1 = wall
                    visited[nr][nc] = true;
                    queue.offer(new int[]{nr, nc});
                }
            }
        }
        steps++;
    }
    return -1;
}
```

### Visualization

```
Graph: 0 -- 1 -- 3 -- 5 (target)
       |         |
       2 ------- 4

BFS from 0 to 5:
Level 0: [0]           visited: {0}
Level 1: [1, 2]       visited: {0,1,2}
Level 2: [3, 4]       visited: {0,1,2,3,4}
Level 3: [5]          → found! distance = 3

Grid BFS:
S . . .        0 1 2 3
. # # .   →   1 . . 4
. . . E        2 3 4 5 ← shortest = 5 steps
```

### Variants
- **Shortest Path with obstacles** (LC 1293): BFS with state = (row, col, obstacles_remaining)
- **Knight on chessboard** (LC 1197): 8-directional BFS
- **Minimum Knight Moves** (LC 1197): BFS with pruning or bidirectional BFS

### Complexity
- **Time:** O(V + E) — each node/edge visited once
- **Space:** O(V) — queue + visited set

---

## Pattern 2: Multi-Source BFS

### Signal
- "Distance from **any** source" (multiple starting points)
- Propagation from multiple origins simultaneously
- "Rotting oranges", "Walls and Gates", "01 Matrix"

### Template (Java)

```java
// Multi-source BFS: distance from nearest source
public int[][] multiSourceBFS(int[][] grid, int sourceValue) {
    int rows = grid.length, cols = grid[0].length;
    int[][] dist = new int[rows][cols];
    Queue<int[]> queue = new LinkedList<>();
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    // Initialize: enqueue ALL sources at once
    for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
    for (int r = 0; r < rows; r++) {
        for (int c = 0; c < cols; c++) {
            if (grid[r][c] == sourceValue) {
                dist[r][c] = 0;
                queue.offer(new int[]{r, c});
            }
        }
    }

    // BFS expands all sources in parallel
    while (!queue.isEmpty()) {
        int[] cell = queue.poll();
        for (int[] d : dirs) {
            int nr = cell[0] + d[0], nc = cell[1] + d[1];
            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols
                && dist[nr][nc] == Integer.MAX_VALUE) {
                dist[nr][nc] = dist[cell[0]][cell[1]] + 1;
                queue.offer(new int[]{nr, nc});
            }
        }
    }
    return dist;
}

// Rotting Oranges (LC 994)
public int orangesRotting(int[][] grid) {
    int rows = grid.length, cols = grid[0].length;
    Queue<int[]> queue = new LinkedList<>();
    int fresh = 0;
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++) {
            if (grid[r][c] == 2) queue.offer(new int[]{r, c}); // rotten = source
            else if (grid[r][c] == 1) fresh++;
        }

    int minutes = 0;
    while (!queue.isEmpty() && fresh > 0) {
        int size = queue.size();
        for (int i = 0; i < size; i++) {
            int[] cell = queue.poll();
            for (int[] d : dirs) {
                int nr = cell[0] + d[0], nc = cell[1] + d[1];
                if (nr >= 0 && nr < rows && nc >= 0 && nc < cols && grid[nr][nc] == 1) {
                    grid[nr][nc] = 2;
                    fresh--;
                    queue.offer(new int[]{nr, nc});
                }
            }
        }
        minutes++;
    }
    return fresh == 0 ? minutes : -1;
}
```

### Visualization

```
Rotting Oranges:
Initial:        t=1:            t=2:            t=3:
2 1 1           2 2 1           2 2 2           2 2 2
1 1 0           2 1 0           2 2 0           2 2 0
0 1 1           0 1 1           0 2 1           0 2 2
                                                → answer: 3 (if no fresh left)

Key insight: ALL rotten oranges start in queue simultaneously
             → BFS wavefront expands from all sources in parallel
```

### Variants
- **01 Matrix** (LC 542): sources = all 0-cells, find distance to nearest 0
- **Walls and Gates** (LC 286): sources = gates, fill rooms with distances
- **Shortest Bridge** (LC 934): find one island with DFS, multi-source BFS to other

### Complexity
- **Time:** O(V + E) = O(rows × cols) for grids
- **Space:** O(V) — all sources may be in queue initially

---

## Pattern 3: DFS — Connected Components / Flood Fill

### Signal
- "Number of islands / connected components"
- "Fill a region" / flood fill
- "Are two nodes connected?"
- Group related nodes together

### Template (Java)

```java
// Number of Islands (LC 200)
public int numIslands(char[][] grid) {
    int count = 0;
    for (int r = 0; r < grid.length; r++) {
        for (int c = 0; c < grid[0].length; c++) {
            if (grid[r][c] == '1') {
                dfsFlood(grid, r, c);
                count++;
            }
        }
    }
    return count;
}

private void dfsFlood(char[][] grid, int r, int c) {
    if (r < 0 || r >= grid.length || c < 0 || c >= grid[0].length
        || grid[r][c] != '1') return;
    grid[r][c] = '0'; // mark visited (in-place)
    dfsFlood(grid, r + 1, c);
    dfsFlood(grid, r - 1, c);
    dfsFlood(grid, r, c + 1);
    dfsFlood(grid, r, c - 1);
}

// Connected Components on adjacency list
public int countComponents(int n, int[][] edges) {
    List<List<Integer>> graph = new ArrayList<>();
    for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
    for (int[] e : edges) {
        graph.get(e[0]).add(e[1]);
        graph.get(e[1]).add(e[0]);
    }

    boolean[] visited = new boolean[n];
    int components = 0;
    for (int i = 0; i < n; i++) {
        if (!visited[i]) {
            dfs(graph, i, visited);
            components++;
        }
    }
    return components;
}

private void dfs(List<List<Integer>> graph, int node, boolean[] visited) {
    visited[node] = true;
    for (int neighbor : graph.get(node)) {
        if (!visited[neighbor]) {
            dfs(graph, neighbor, visited);
        }
    }
}
```

### Visualization

```
Grid:              Components:
1 1 0 0 0          A A . . .
1 1 0 0 0          A A . . .
0 0 1 0 0    →     . . B . .     → 3 islands
0 0 0 1 1          . . . C C
0 0 0 1 1          . . . C C

DFS from (0,0): visits all 'A' cells, marks them visited
DFS from (2,2): visits 'B'
DFS from (3,3): visits all 'C' cells
```

### Variants
- **Number of Provinces** (LC 547): adjacency matrix, nodes = cities
- **Surrounded Regions** (LC 130): DFS from border 'O's, flip remaining
- **Max Area of Island** (LC 695): DFS returns size of component
- **Pacific Atlantic Water Flow** (LC 417): DFS from both oceans inward

### Complexity
- **Time:** O(V + E) — each node visited once
- **Space:** O(V) — recursion stack (worst case: linear chain)

---

## Pattern 4: DFS — Cycle Detection in Directed Graph (3-Color)

### Signal
- "Can we finish all courses?" (topological ordering possible?)
- Detect back edge in directed graph
- Deadlock detection

### Template (Java)

```java
// States: 0=WHITE (unvisited), 1=GRAY (in current path), 2=BLACK (fully processed)
public boolean hasCycleDirected(int numNodes, List<List<Integer>> graph) {
    int[] color = new int[numNodes]; // all WHITE initially

    for (int i = 0; i < numNodes; i++) {
        if (color[i] == 0) { // WHITE
            if (dfsDetectCycle(graph, i, color)) return true;
        }
    }
    return false;
}

private boolean dfsDetectCycle(List<List<Integer>> graph, int node, int[] color) {
    color[node] = 1; // GRAY — entering current DFS path

    for (int neighbor : graph.get(node)) {
        if (color[neighbor] == 1) return true;  // back edge → cycle!
        if (color[neighbor] == 0) {             // WHITE → explore
            if (dfsDetectCycle(graph, neighbor, color)) return true;
        }
        // BLACK → already fully processed, skip (cross/forward edge)
    }

    color[node] = 2; // BLACK — fully processed
    return false;
}

// Course Schedule (LC 207)
public boolean canFinish(int numCourses, int[][] prerequisites) {
    List<List<Integer>> graph = new ArrayList<>();
    for (int i = 0; i < numCourses; i++) graph.add(new ArrayList<>());
    for (int[] p : prerequisites) graph.get(p[1]).add(p[0]); // prereq → course

    return !hasCycleDirected(numCourses, graph);
}
```

### Visualization

```
3-Color DFS on directed graph:

0 → 1 → 2 → 3
         ↑   ↓
         └───┘  ← back edge (cycle: 2→3→2)

DFS from 0:
  Visit 0 [GRAY]
    Visit 1 [GRAY]
      Visit 2 [GRAY]
        Visit 3 [GRAY]
          Neighbor 2 is GRAY → CYCLE DETECTED!

Without cycle (DAG):
0 → 1 → 2
    ↓
    3 → 2  (2 is BLACK when reached from 3, not GRAY → no cycle)

Color meaning:
  WHITE: not yet visited in any DFS
  GRAY:  on the current recursion stack (ancestor)
  BLACK: fully explored, no cycle through this node
```

### Variants
- **Course Schedule II** (LC 210): topological sort (reverse post-order)
- **Detect cycle + return the cycle nodes**
- **Kahn's algorithm** (BFS-based topo sort): if processed < numNodes → cycle

### Complexity
- **Time:** O(V + E)
- **Space:** O(V) — color array + recursion stack

---

## Pattern 5: DFS — Cycle Detection in Undirected Graph (Parent Tracking)

### Signal
- Cycle detection in **undirected** graph
- "Is this graph a tree?" (tree = connected + no cycles)
- Redundant connection detection

### Template (Java)

```java
public boolean hasCycleUndirected(int n, List<List<Integer>> graph) {
    boolean[] visited = new boolean[n];

    for (int i = 0; i < n; i++) {
        if (!visited[i]) {
            if (dfsCycle(graph, i, -1, visited)) return true;
        }
    }
    return false;
}

private boolean dfsCycle(List<List<Integer>> graph, int node, int parent, boolean[] visited) {
    visited[node] = true;

    for (int neighbor : graph.get(node)) {
        if (!visited[neighbor]) {
            if (dfsCycle(graph, neighbor, node, visited)) return true;
        } else if (neighbor != parent) {
            // visited neighbor that isn't our parent → cycle!
            return true;
        }
    }
    return false;
}

// Graph Valid Tree (LC 261): connected + no cycle
public boolean validTree(int n, int[][] edges) {
    if (edges.length != n - 1) return false; // quick check: tree has exactly n-1 edges

    List<List<Integer>> graph = new ArrayList<>();
    for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
    for (int[] e : edges) {
        graph.get(e[0]).add(e[1]);
        graph.get(e[1]).add(e[0]);
    }

    boolean[] visited = new boolean[n];
    if (dfsCycle(graph, 0, -1, visited)) return false; // has cycle

    for (boolean v : visited) if (!v) return false; // not connected
    return true;
}
```

### Visualization

```
Undirected graph:
0 — 1 — 2
    |   /
    3 — ←  (edge 2-3 creates cycle)

DFS from 0 (parent=-1):
  Visit 0, parent=-1
    Visit 1, parent=0
      Visit 2, parent=1
        Neighbor 3: unvisited → recurse
          Visit 3, parent=2
            Neighbor 1: visited AND ≠ parent(2) → CYCLE!

Why parent check matters:
  0 — 1   DFS at 1 (parent=0): neighbor 0 is visited
           but 0 IS the parent → not a cycle, just the edge we came from
```

### Variants
- **Redundant Connection** (LC 684): find the edge that creates cycle (Union-Find preferred)
- **Is Graph a Tree**: V-1 edges + connected + no cycle

### Complexity
- **Time:** O(V + E)
- **Space:** O(V) — visited + recursion stack

---

## Pattern 6: DFS — All Paths / Backtracking on Graph

### Signal
- "Find **all** paths from source to target"
- Enumerate possibilities on a graph structure
- Path constraints (visit at most once, specific length)

### Template (Java)

```java
// All Paths From Source to Target (LC 797) — DAG, no visited needed
public List<List<Integer>> allPathsSourceTarget(int[][] graph) {
    List<List<Integer>> result = new ArrayList<>();
    List<Integer> path = new ArrayList<>();
    path.add(0);
    dfsAllPaths(graph, 0, graph.length - 1, path, result);
    return result;
}

private void dfsAllPaths(int[][] graph, int node, int target,
                         List<Integer> path, List<List<Integer>> result) {
    if (node == target) {
        result.add(new ArrayList<>(path)); // snapshot
        return;
    }
    for (int neighbor : graph[node]) {
        path.add(neighbor);
        dfsAllPaths(graph, neighbor, target, path, result);
        path.remove(path.size() - 1); // backtrack
    }
}

// General graph (with cycles): must track visited
public void dfsAllPathsGeneral(List<List<Integer>> graph, int node, int target,
                                boolean[] visited, List<Integer> path,
                                List<List<Integer>> result) {
    if (node == target) {
        result.add(new ArrayList<>(path));
        return;
    }
    visited[node] = true;
    for (int neighbor : graph.get(node)) {
        if (!visited[neighbor]) {
            path.add(neighbor);
            dfsAllPathsGeneral(graph, neighbor, target, visited, path, result);
            path.remove(path.size() - 1);
        }
    }
    visited[node] = false; // BACKTRACK: unmark so other paths can use this node
}
```

### Visualization

```
DAG:  0 → 1 → 3
      |       ↑
      └→ 2 ──┘

All paths 0→3:
  Path: [0] → try 1
    Path: [0,1] → try 3
      Path: [0,1,3] → TARGET ✓ → record
    Backtrack: [0,1]
  Backtrack: [0]
  Path: [0] → try 2
    Path: [0,2] → try 3
      Path: [0,2,3] → TARGET ✓ → record
    Backtrack: [0,2]
  Backtrack: [0]

Result: [[0,1,3], [0,2,3]]

Key: backtrack visited[] when graph has cycles to allow node reuse across paths
```

### Variants
- **Hamiltonian Path**: visit every node exactly once (NP-complete)
- **Path with constraints**: max weight, required nodes, etc.
- **Count paths** (use DP/memoization on DAGs instead)

### Complexity
- **Time:** O(2^V · V) worst case — exponential number of paths
- **Space:** O(V) recursion depth + O(paths · V) for storing results

---

## Pattern 7: Bipartite Check / 2-Coloring

### Signal
- "Can we divide nodes into two groups with no intra-group edges?"
- "Is the graph 2-colorable?"
- Odd-cycle detection (graph is bipartite iff no odd-length cycles)

### Template (Java)

```java
// BFS-based bipartite check
public boolean isBipartite(int[][] graph) {
    int n = graph.length;
    int[] color = new int[n]; // 0=uncolored, 1=color_A, -1=color_B

    for (int i = 0; i < n; i++) {
        if (color[i] != 0) continue; // already colored
        // BFS from uncolored node
        Queue<Integer> queue = new LinkedList<>();
        queue.offer(i);
        color[i] = 1;

        while (!queue.isEmpty()) {
            int node = queue.poll();
            for (int neighbor : graph[node]) {
                if (color[neighbor] == 0) {
                    color[neighbor] = -color[node]; // opposite color
                    queue.offer(neighbor);
                } else if (color[neighbor] == color[node]) {
                    return false; // same color on both sides of edge → not bipartite
                }
            }
        }
    }
    return true;
}

// DFS-based (alternative)
public boolean isBipartiteDFS(int[][] graph) {
    int n = graph.length;
    int[] color = new int[n];

    for (int i = 0; i < n; i++) {
        if (color[i] == 0 && !dfsColor(graph, i, 1, color)) return false;
    }
    return true;
}

private boolean dfsColor(int[][] graph, int node, int c, int[] color) {
    color[node] = c;
    for (int neighbor : graph[node]) {
        if (color[neighbor] == 0) {
            if (!dfsColor(graph, neighbor, -c, color)) return false;
        } else if (color[neighbor] == c) return false;
    }
    return true;
}
```

### Visualization

```
Bipartite (2-colorable):         NOT bipartite:
  1 — 2                           1 — 2
  |   |     → color 1=A,2=B       |   |
  4 — 3       color 4=B,3=A       3 — 4 — 5
                                       |   /
Group A: {1,3}                         └──┘  ← odd cycle (4-5-? forms triangle)
Group B: {2,4}

BFS coloring:
  Start node 1 → color A
  Neighbors {2,4} → color B
  From 2: neighbor 3 → color A
  From 4: neighbor 3 already A ✓ (opposite of B)
  → BIPARTITE

Failed case:
  Nodes in triangle: 1-A, 2-B, 3-? 
  3 is neighbor of 1(A) → must be B
  3 is neighbor of 2(B) → must be A  → CONFLICT!
```

### Variants
- **Possible Bipartition** (LC 886): group dislikes
- **Is Graph Bipartite** (LC 785)
- **m-Coloring** (general graph coloring — NP-complete for m>2)

### Complexity
- **Time:** O(V + E)
- **Space:** O(V) — color array + queue/stack

---

## Pattern 8: Clone Graph

### Signal
- "Deep copy a graph" / "Clone a linked structure with random pointers"
- Need to map original nodes to new copies
- Avoid duplicating already-cloned nodes

### Template (Java)

```java
// Clone Graph (LC 133)
public Node cloneGraph(Node node) {
    if (node == null) return null;
    Map<Node, Node> cloned = new HashMap<>(); // original → clone
    return dfsClone(node, cloned);
}

private Node dfsClone(Node node, Map<Node, Node> cloned) {
    if (cloned.containsKey(node)) return cloned.get(node); // already cloned

    Node copy = new Node(node.val);
    cloned.put(node, copy); // register BEFORE recursing (handles cycles)

    for (Node neighbor : node.neighbors) {
        copy.neighbors.add(dfsClone(neighbor, cloned));
    }
    return copy;
}

// BFS alternative
public Node cloneGraphBFS(Node node) {
    if (node == null) return null;
    Map<Node, Node> cloned = new HashMap<>();
    Queue<Node> queue = new LinkedList<>();

    cloned.put(node, new Node(node.val));
    queue.offer(node);

    while (!queue.isEmpty()) {
        Node curr = queue.poll();
        for (Node neighbor : curr.neighbors) {
            if (!cloned.containsKey(neighbor)) {
                cloned.put(neighbor, new Node(neighbor.val));
                queue.offer(neighbor);
            }
            cloned.get(curr).neighbors.add(cloned.get(neighbor));
        }
    }
    return cloned.get(node);
}
```

### Visualization

```
Original:           Clone:
  1 — 2               1'— 2'
  |   |      →        |   |
  4 — 3               4'— 3'

HashMap state during DFS from node 1:
  clone(1): create 1', map{1→1'}, recurse neighbors
    clone(2): create 2', map{1→1',2→2'}, recurse neighbors
      clone(3): create 3', map{...,3→3'}, recurse neighbors
        clone(4): create 4', map{...,4→4'}, recurse neighbors
          clone(1): found in map → return 1' (no infinite loop!)
          clone(3): found in map → return 3'
        return 4'
      return 3'
    return 2'
  return 1'

Critical: put in map BEFORE recursing to handle cycles
```

### Variants
- **Copy List with Random Pointer** (LC 138): same HashMap approach
- **Clone Binary Tree with Random Pointer** (LC 1485)
- **Deep clone any object graph** (serialization alternative)

### Complexity
- **Time:** O(V + E) — visit each node and edge once
- **Space:** O(V) — HashMap storing all clones

---

## Pattern 9: Graph Representation

### Signal
- Choosing the right data structure before solving any graph problem

### Representations (Java)

```java
// 1. ADJACENCY LIST — most common, best for sparse graphs
// Space: O(V + E)
List<List<Integer>> adjList = new ArrayList<>();
for (int i = 0; i < n; i++) adjList.add(new ArrayList<>());
// Add edge u→v (directed)
adjList.get(u).add(v);
// Undirected: add both directions
adjList.get(u).add(v);
adjList.get(v).add(u);

// With weights:
List<List<int[]>> weightedAdj = new ArrayList<>();
weightedAdj.get(u).add(new int[]{v, weight});

// 2. ADJACENCY MATRIX — good for dense graphs, O(1) edge lookup
// Space: O(V²)
boolean[][] adjMatrix = new boolean[n][n];
adjMatrix[u][v] = true; // edge u→v

// With weights:
int[][] weightMatrix = new int[n][n];
Arrays.fill(weightMatrix, Integer.MAX_VALUE); // init as no edge

// 3. EDGE LIST — good for Kruskal's, simple input parsing
// Space: O(E)
int[][] edges = new int[m][3]; // [from, to, weight]
// or
List<int[]> edgeList = new ArrayList<>();
edgeList.add(new int[]{u, v, weight});

// 4. HASHMAP-BASED (for non-integer node labels)
Map<String, List<String>> graph = new HashMap<>();
graph.computeIfAbsent(src, k -> new ArrayList<>()).add(dst);
```

### Comparison

```
                    Adj List    Adj Matrix    Edge List
Space               O(V + E)   O(V²)         O(E)
Add edge            O(1)       O(1)           O(1)
Check edge (u,v)    O(deg(u))  O(1)           O(E)
Iterate neighbors   O(deg(u))  O(V)           O(E)
Best for            Sparse     Dense/small    Kruskal's

Decision:
  E ≪ V² (sparse) → Adjacency List ✓
  E ≈ V² (dense)  → Adjacency Matrix ✓
  Need sorted edges → Edge List ✓
  Node labels are strings → HashMap<String, List<String>> ✓
```

### Building from Common Inputs

```java
// From edge list input: int[][] edges = {{0,1},{1,2},{2,0}}
// Build undirected adjacency list:
List<List<Integer>> graph = new ArrayList<>();
for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
for (int[] e : edges) {
    graph.get(e[0]).add(e[1]);
    graph.get(e[1]).add(e[0]);
}

// From adjacency matrix input: int[][] isConnected (LC 547)
// Just use matrix[i][j] == 1 to check edge directly
```

---

## Pattern 10: Implicit Graphs (Word Ladder)

### Signal
- No explicit graph given — you must **model** the graph
- States as nodes, valid transitions as edges
- "Minimum transformations", "minimum operations to reach target"
- Word Ladder, Open the Lock, Sliding Puzzle

### Template (Java)

```java
// Word Ladder (LC 127): shortest transformation sequence
public int ladderLength(String beginWord, String endWord, List<String> wordList) {
    Set<String> wordSet = new HashSet<>(wordList);
    if (!wordSet.contains(endWord)) return 0;

    Queue<String> queue = new LinkedList<>();
    Set<String> visited = new HashSet<>();
    queue.offer(beginWord);
    visited.add(beginWord);
    int steps = 1;

    while (!queue.isEmpty()) {
        int size = queue.size();
        for (int i = 0; i < size; i++) {
            String word = queue.poll();
            if (word.equals(endWord)) return steps;

            // Generate all neighbors (words differing by 1 char)
            char[] chars = word.toCharArray();
            for (int j = 0; j < chars.length; j++) {
                char original = chars[j];
                for (char c = 'a'; c <= 'z'; c++) {
                    if (c == original) continue;
                    chars[j] = c;
                    String next = new String(chars);
                    if (wordSet.contains(next) && !visited.contains(next)) {
                        visited.add(next);
                        queue.offer(next);
                    }
                }
                chars[j] = original; // restore
            }
        }
        steps++;
    }
    return 0; // unreachable
}

// Open the Lock (LC 752)
public int openLock(String[] deadends, String target) {
    Set<String> dead = new HashSet<>(Arrays.asList(deadends));
    if (dead.contains("0000")) return -1;

    Queue<String> queue = new LinkedList<>();
    Set<String> visited = new HashSet<>();
    queue.offer("0000");
    visited.add("0000");
    int turns = 0;

    while (!queue.isEmpty()) {
        int size = queue.size();
        for (int i = 0; i < size; i++) {
            String state = queue.poll();
            if (state.equals(target)) return turns;

            // 8 neighbors: each of 4 wheels can go +1 or -1
            for (int j = 0; j < 4; j++) {
                for (int d : new int[]{1, -1}) {
                    char[] arr = state.toCharArray();
                    arr[j] = (char) (((arr[j] - '0' + d + 10) % 10) + '0');
                    String next = new String(arr);
                    if (!dead.contains(next) && !visited.contains(next)) {
                        visited.add(next);
                        queue.offer(next);
                    }
                }
            }
        }
        turns++;
    }
    return -1;
}
```

### Visualization

```
Word Ladder: "hit" → "cog", wordList = [hot, dot, dog, lot, log, cog]

Implicit graph (edges = 1-char difference):
  hit → hot → dot → dog → cog
              ↓         ↗
              lot → log

BFS levels:
  Level 1: [hit]
  Level 2: [hot]
  Level 3: [dot, lot]
  Level 4: [dog, log]
  Level 5: [cog] ← FOUND! answer = 5

Modeling pattern:
  Node = state (word, lock position, board config)
  Edge = valid single transition
  Goal = BFS shortest path on this implicit graph

Optimization (wildcard pattern):
  Build adjacency: h*t → [hit, hot, hat, ...]
  Avoids O(26·L) per word, useful for large dictionaries
```

### Variants
- **Word Ladder II** (LC 126): find ALL shortest paths (BFS + DFS backtrack)
- **Open the Lock** (LC 752): 4-digit lock, deadends as blocked nodes
- **Sliding Puzzle** (LC 773): board state as node, swaps as edges
- **Minimum Genetic Mutation** (LC 433): same as word ladder with genes
- **Bidirectional BFS**: search from both ends, meet in middle (halves depth)

### Complexity (Word Ladder)
- **Time:** O(M² · N) where M = word length, N = wordList size
  - Each word has M positions × 26 chars to try, string creation is O(M)
- **Space:** O(M² · N) — visited set stores up to N words of length M

---

## Common Pitfalls & Best Practices

| Pitfall | Fix |
|---------|-----|
| BFS without level tracking | Use `size = queue.size()` loop for distance |
| DFS on large grid → stack overflow | Use iterative DFS or BFS instead |
| Forgetting to mark visited BEFORE enqueue | Causes duplicate processing, TLE |
| Using DFS for shortest path | DFS does NOT guarantee shortest in unweighted graph |
| Undirected cycle: counting parent as cycle | Pass parent parameter, skip parent in check |
| Directed cycle: using simple visited | Need 3 colors; visited alone can't distinguish back edge from cross edge |
| Clone graph: infinite loop on cycles | Put node in map BEFORE recursing into neighbors |
| Implicit graph: generating invalid states | Validate state before enqueueing |

---

## Pattern Composition Examples

| Problem | Patterns Combined |
|---------|-------------------|
| Shortest Bridge (LC 934) | DFS (find island) + Multi-Source BFS (expand to other) |
| Word Ladder II (LC 126) | BFS (shortest distance) + DFS (reconstruct all paths) |
| Alien Dictionary (LC 269) | Build graph + Cycle detection + Topological sort |
| Accounts Merge (LC 721) | Build graph + DFS connected components |
| Evaluate Division (LC 399) | Build weighted graph + BFS/DFS path search |
