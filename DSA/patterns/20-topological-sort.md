# Pattern 20: Topological Sort

## When Topological Sort Applies — Detection Signals

```
Ask yourself:
  1. Is there a "prerequisite" / "dependency" / "ordering" relationship?
  2. Are we dealing with directed edges (A must come before B)?
  3. Do we need to detect if a valid ordering EXISTS (cycle detection)?
  4. Do we need to FIND an ordering or the SHORTEST/LONGEST path in a DAG?

If YES to any → Topological Sort family.
```

**Keyword triggers:** prerequisites, dependencies, build order, course schedule,
alien dictionary, task scheduling, compilation order, "before/after" constraints.

---

## Decision Flowchart

```
                    ┌─────────────────────────┐
                    │ Directed dependency graph│
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  Need just yes/no DAG?   │
                    └───┬───────────────┬──────┘
                      YES               NO
                        │                │
              ┌─────────▼──────┐  ┌─────▼──────────────────┐
              │ Cycle Detection│  │ Need one valid order?   │
              │ (Kahn's: check │  └───┬────────────────┬───┘
              │  |order|< n)   │    YES                NO
              └────────────────┘      │                │
                              ┌───────▼──────┐  ┌─────▼─────────────────┐
                              │ Kahn's / DFS │  │ Need ALL orderings?   │
                              │ Topo Sort    │  └───┬───────────────┬───┘
                              └──────────────┘    YES               NO
                                                    │                │
                                          ┌─────────▼────┐  ┌───────▼──────────┐
                                          │ Backtracking │  │ Min steps/longest│
                                          │ all topo     │  │ path? → BFS      │
                                          │ orderings    │  │ levels or DP     │
                                          └──────────────┘  └──────────────────┘
```

---

## Visual Example of Topological Ordering

```
Graph:
    5 → 0 ← 4
    │         │
    ▼         ▼
    2 → 3 → 1

Adjacency: 5→[0,2], 4→[0,1], 2→[3], 3→[1]

In-degrees: 0:2, 1:2, 2:1, 3:1, 4:0, 5:0

Kahn's BFS:
  Queue init: [4, 5]  (in-degree 0)
  Process 4 → decrement 0(→1), 1(→1)  → queue: [5]
  Process 5 → decrement 0(→0), 2(→0)  → queue: [0, 2]
  Process 0 → (no outgoing)            → queue: [2]
  Process 2 → decrement 3(→0)          → queue: [3]
  Process 3 → decrement 1(→0)          → queue: [1]
  Process 1 → done

  Order: [4, 5, 0, 2, 3, 1] ✓

DFS post-order (reversed):
  Visit 5 → 0(done), 2 → 3 → 1(done) → post: 1,3,2,0  then post: 5
  Visit 4 → 0(visited), 1(visited)    → post: 4
  Full post-order: [1, 3, 2, 0, 5, 4]
  Reversed: [4, 5, 0, 2, 3, 1] ✓
```

---

## Kahn's vs DFS Comparison

| Aspect | Kahn's (BFS) | DFS-based |
|--------|-------------|-----------|
| Core idea | Remove zero in-degree nodes layer by layer | Post-order traversal, reverse at end |
| Data structure | Queue + in-degree array | Recursion stack + visited states |
| Cycle detection | `order.size() < n` | Detect back-edge (node in current path) |
| Level/layer info | Natural (process level by level) | Not naturally available |
| Parallelism | Yes — nodes in same level are independent | No |
| Use when | Need levels/min-steps, or iterative preferred | Simple recursive, or need cycle via coloring |
| Space | O(V + E) | O(V + E) + recursion stack |

---

## 1. Kahn's Algorithm (BFS-based)

### Signal
- Need a valid ordering of tasks with dependencies
- Need to detect cycles in a directed graph
- Need level-by-level processing (parallel scheduling)

### Template (Java)

```java
List<Integer> kahnsTopoSort(int n, List<List<Integer>> adj) {
    int[] inDegree = new int[n];
    for (int u = 0; u < n; u++)
        for (int v : adj.get(u))
            inDegree[v]++;

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < n; i++)
        if (inDegree[i] == 0)
            queue.offer(i);

    List<Integer> order = new ArrayList<>();
    while (!queue.isEmpty()) {
        int u = queue.poll();
        order.add(u);
        for (int v : adj.get(u)) {
            if (--inDegree[v] == 0)
                queue.offer(v);
        }
    }

    // If order.size() < n → cycle exists
    return order.size() == n ? order : Collections.emptyList();
}
```

### Complexity
- Time: O(V + E)
- Space: O(V + E)

---

## 2. DFS-based Topological Sort

### Signal
- Same as Kahn's but prefer recursive approach
- Need cycle detection via 3-color (white/gray/black) scheme

### Template (Java)

```java
List<Integer> dfsTopoSort(int n, List<List<Integer>> adj) {
    int[] color = new int[n]; // 0=white, 1=gray, 2=black
    Deque<Integer> stack = new ArrayDeque<>();
    boolean hasCycle = false;

    for (int i = 0; i < n && !hasCycle; i++)
        if (color[i] == 0)
            hasCycle = dfs(i, adj, color, stack);

    if (hasCycle) return Collections.emptyList();

    List<Integer> order = new ArrayList<>();
    while (!stack.isEmpty()) order.add(stack.pop());
    return order;
}

boolean dfs(int u, List<List<Integer>> adj, int[] color, Deque<Integer> stack) {
    color[u] = 1; // visiting (gray)
    for (int v : adj.get(u)) {
        if (color[v] == 1) return true;  // back edge → cycle
        if (color[v] == 0 && dfs(v, adj, color, stack)) return true;
    }
    color[u] = 2; // done (black)
    stack.push(u); // post-order
    return false;
}
```

### Complexity
- Time: O(V + E)
- Space: O(V + E) + O(V) recursion stack

---

## 3. Course Schedule I (Can Finish?)

> LeetCode 207. Can you finish all courses given prerequisites?

### Signal
- "Can all tasks be completed?" = "Is the graph a DAG?"

### Template (Java)

```java
boolean canFinish(int numCourses, int[][] prerequisites) {
    List<List<Integer>> adj = new ArrayList<>();
    int[] inDegree = new int[numCourses];
    for (int i = 0; i < numCourses; i++) adj.add(new ArrayList<>());

    for (int[] pre : prerequisites) {
        adj.get(pre[1]).add(pre[0]); // pre[1] → pre[0]
        inDegree[pre[0]]++;
    }

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < numCourses; i++)
        if (inDegree[i] == 0) queue.offer(i);

    int count = 0;
    while (!queue.isEmpty()) {
        int u = queue.poll();
        count++;
        for (int v : adj.get(u))
            if (--inDegree[v] == 0) queue.offer(v);
    }
    return count == numCourses;
}
```

### Key Insight
- If Kahn's processes all nodes → DAG → can finish
- If some nodes remain (in-degree never reaches 0) → cycle → cannot finish

---

## 4. Course Schedule II (Find Valid Ordering)

> LeetCode 210. Return one valid course ordering.

### Signal
- "Return the order" — identical to Kahn's but return the result

### Template (Java)

```java
int[] findOrder(int numCourses, int[][] prerequisites) {
    List<List<Integer>> adj = new ArrayList<>();
    int[] inDegree = new int[numCourses];
    for (int i = 0; i < numCourses; i++) adj.add(new ArrayList<>());

    for (int[] pre : prerequisites) {
        adj.get(pre[1]).add(pre[0]);
        inDegree[pre[0]]++;
    }

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < numCourses; i++)
        if (inDegree[i] == 0) queue.offer(i);

    int[] order = new int[numCourses];
    int idx = 0;
    while (!queue.isEmpty()) {
        int u = queue.poll();
        order[idx++] = u;
        for (int v : adj.get(u))
            if (--inDegree[v] == 0) queue.offer(v);
    }
    return idx == numCourses ? order : new int[0];
}
```

---

## 5. Alien Dictionary

> LeetCode 269. Given sorted alien words, derive character ordering.

### Signal
- "Derive ordering from comparisons" — build graph from adjacent word pairs, then topo sort

### Template (Java)

```java
String alienOrder(String[] words) {
    // Step 1: Initialize graph for all characters
    Map<Character, Set<Character>> adj = new HashMap<>();
    Map<Character, Integer> inDegree = new HashMap<>();
    for (String w : words)
        for (char c : w.toCharArray()) {
            adj.putIfAbsent(c, new HashSet<>());
            inDegree.putIfAbsent(c, 0);
        }

    // Step 2: Build edges from adjacent word pairs
    for (int i = 0; i < words.length - 1; i++) {
        String w1 = words[i], w2 = words[i + 1];
        // Edge case: "abc" before "ab" → invalid
        if (w1.length() > w2.length() && w1.startsWith(w2))
            return "";
        for (int j = 0; j < Math.min(w1.length(), w2.length()); j++) {
            char c1 = w1.charAt(j), c2 = w2.charAt(j);
            if (c1 != c2) {
                if (!adj.get(c1).contains(c2)) {
                    adj.get(c1).add(c2);
                    inDegree.merge(c2, 1, Integer::sum);
                }
                break; // only first difference matters
            }
        }
    }

    // Step 3: Kahn's
    Queue<Character> queue = new LinkedList<>();
    for (char c : inDegree.keySet())
        if (inDegree.get(c) == 0) queue.offer(c);

    StringBuilder sb = new StringBuilder();
    while (!queue.isEmpty()) {
        char c = queue.poll();
        sb.append(c);
        for (char next : adj.get(c))
            if (inDegree.merge(next, -1, Integer::sum) == 0)
                queue.offer(next);
    }

    return sb.length() == inDegree.size() ? sb.toString() : "";
}
```

### Visualization

```
Words: ["wrt", "wrf", "er", "ett", "rftt"]

Compare adjacent pairs:
  "wrt" vs "wrf" → t ≠ f  → t → f
  "wrf" vs "er"  → w ≠ e  → w → e
  "er"  vs "ett" → r ≠ t  → r → t
  "ett" vs "rftt"→ e ≠ r  → e → r

Graph: w → e → r → t → f
Order: "wertf"
```

---

## 6. Parallel Courses / Minimum Semesters

> LeetCode 1136. Minimum number of semesters to finish all courses.

### Signal
- "Minimum time with parallelism" = longest path in DAG = number of BFS levels

### Template (Java)

```java
int minimumSemesters(int n, int[][] relations) {
    List<List<Integer>> adj = new ArrayList<>();
    int[] inDegree = new int[n + 1];
    for (int i = 0; i <= n; i++) adj.add(new ArrayList<>());

    for (int[] rel : relations) {
        adj.get(rel[0]).add(rel[1]);
        inDegree[rel[1]]++;
    }

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 1; i <= n; i++)
        if (inDegree[i] == 0) queue.offer(i);

    int semesters = 0, processed = 0;
    while (!queue.isEmpty()) {
        semesters++;
        int size = queue.size(); // all nodes at this level → one semester
        for (int i = 0; i < size; i++) {
            int u = queue.poll();
            processed++;
            for (int v : adj.get(u))
                if (--inDegree[v] == 0) queue.offer(v);
        }
    }
    return processed == n ? semesters : -1; // -1 if cycle
}
```

### Key Insight
- BFS levels in Kahn's = critical path length
- All nodes in the same BFS level can be processed in parallel
- Answer = number of BFS levels = longest dependency chain

---

## 7. Build Matrix with Row/Column Conditions

> LeetCode 2392. Build a k x k matrix with row and column ordering constraints.

### Signal
- Two independent topological orderings applied to 2D placement

### Template (Java)

```java
int[][] buildMatrix(int k, int[][] rowConditions, int[][] colConditions) {
    List<Integer> rowOrder = topoSort(k, rowConditions);
    List<Integer> colOrder = topoSort(k, colConditions);

    if (rowOrder.isEmpty() || colOrder.isEmpty()) return new int[0][0];

    // Map value → position
    int[] rowPos = new int[k + 1], colPos = new int[k + 1];
    for (int i = 0; i < k; i++) {
        rowPos[rowOrder.get(i)] = i;
        colPos[colOrder.get(i)] = i;
    }

    int[][] matrix = new int[k][k];
    for (int val = 1; val <= k; val++)
        matrix[rowPos[val]][colPos[val]] = val;

    return matrix;
}

List<Integer> topoSort(int k, int[][] conditions) {
    List<List<Integer>> adj = new ArrayList<>();
    int[] inDegree = new int[k + 1];
    for (int i = 0; i <= k; i++) adj.add(new ArrayList<>());

    for (int[] c : conditions) {
        adj.get(c[0]).add(c[1]);
        inDegree[c[1]]++;
    }

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 1; i <= k; i++)
        if (inDegree[i] == 0) queue.offer(i);

    List<Integer> order = new ArrayList<>();
    while (!queue.isEmpty()) {
        int u = queue.poll();
        order.add(u);
        for (int v : adj.get(u))
            if (--inDegree[v] == 0) queue.offer(v);
    }
    return order.size() == k ? order : Collections.emptyList();
}
```

### Key Insight
- Row conditions and column conditions are INDEPENDENT graphs
- Topo sort each independently, then combine positions into a matrix
- If either has a cycle → impossible

---

## 8. Cycle Detection via Topological Sort

### Signal
- "Is it a DAG?" / "Does a cycle exist in directed graph?"

### Template (Java) — Kahn's Approach

```java
boolean hasCycle(int n, List<List<Integer>> adj) {
    int[] inDegree = new int[n];
    for (int u = 0; u < n; u++)
        for (int v : adj.get(u))
            inDegree[v]++;

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < n; i++)
        if (inDegree[i] == 0) queue.offer(i);

    int count = 0;
    while (!queue.isEmpty()) {
        int u = queue.poll();
        count++;
        for (int v : adj.get(u))
            if (--inDegree[v] == 0) queue.offer(v);
    }
    return count < n; // true = cycle exists
}
```

### Why It Works
```
In a cycle: A → B → C → A
  - In-degree of A, B, C never reaches 0
  - They are never enqueued
  - count < n at the end

No cycle (DAG):
  - At least one node always has in-degree 0
  - Eventually all nodes processed
  - count == n
```

---

## 9. All Topological Orderings (Backtracking)

### Signal
- "Find ALL valid orderings" — rare in interviews, appears in combinatorics

### Template (Java)

```java
List<List<Integer>> allTopoOrders(int n, List<List<Integer>> adj) {
    int[] inDegree = new int[n];
    for (int u = 0; u < n; u++)
        for (int v : adj.get(u))
            inDegree[v]++;

    List<List<Integer>> result = new ArrayList<>();
    boolean[] visited = new boolean[n];
    List<Integer> path = new ArrayList<>();
    backtrack(n, adj, inDegree, visited, path, result);
    return result;
}

void backtrack(int n, List<List<Integer>> adj, int[] inDegree,
               boolean[] visited, List<Integer> path, List<List<Integer>> result) {
    if (path.size() == n) {
        result.add(new ArrayList<>(path));
        return;
    }

    for (int u = 0; u < n; u++) {
        if (!visited[u] && inDegree[u] == 0) {
            // Choose
            visited[u] = true;
            path.add(u);
            for (int v : adj.get(u)) inDegree[v]--;

            // Explore
            backtrack(n, adj, inDegree, visited, path, result);

            // Un-choose
            visited[u] = false;
            path.remove(path.size() - 1);
            for (int v : adj.get(u)) inDegree[v]++;
        }
    }
}
```

### Complexity
- Time: O(V! ) worst case (no edges → all permutations)
- Space: O(V)

---

## 10. Longest Path in DAG (Topological Order + DP)

### Signal
- "Longest path" / "critical path" / "maximum chain length" in a DAG
- NOTE: Longest path in general graph is NP-hard, but in DAG it's O(V+E)

### Template (Java)

```java
int longestPathInDAG(int n, List<List<int[]>> adj) {
    // adj.get(u) = list of [v, weight]
    // Step 1: Topo sort (Kahn's)
    int[] inDegree = new int[n];
    for (int u = 0; u < n; u++)
        for (int[] edge : adj.get(u))
            inDegree[edge[0]]++;

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < n; i++)
        if (inDegree[i] == 0) queue.offer(i);

    List<Integer> topoOrder = new ArrayList<>();
    while (!queue.isEmpty()) {
        int u = queue.poll();
        topoOrder.add(u);
        for (int[] edge : adj.get(u))
            if (--inDegree[edge[0]] == 0) queue.offer(edge[0]);
    }

    // Step 2: DP relaxation in topological order
    int[] dist = new int[n];
    Arrays.fill(dist, 0); // longest distance from any source

    for (int u : topoOrder) {
        for (int[] edge : adj.get(u)) {
            int v = edge[0], w = edge[1];
            dist[v] = Math.max(dist[v], dist[u] + w);
        }
    }

    int longest = 0;
    for (int d : dist) longest = Math.max(longest, d);
    return longest;
}
```

### Unweighted Variant (Longest Chain)

```java
// For unweighted: dist[v] = max(dist[v], dist[u] + 1)
int longestChain(int n, List<List<Integer>> adj) {
    List<Integer> order = kahnsTopoSort(n, adj);
    int[] dist = new int[n];
    for (int u : order)
        for (int v : adj.get(u))
            dist[v] = Math.max(dist[v], dist[u] + 1);
    return Arrays.stream(dist).max().orElse(0);
}
```

### Complexity
- Time: O(V + E)
- Space: O(V + E)

---

## Summary — Pattern Selection Guide

| Problem Type | Approach | Key Difference |
|---|---|---|
| Is it a DAG? | Kahn's, check count | count < n → cycle |
| Find one ordering | Kahn's or DFS | Either works |
| Min parallel steps | Kahn's BFS levels | Level count = answer |
| Longest path | Topo + DP | Relax edges in topo order |
| Derive ordering from comparisons | Build graph + topo sort | Graph construction is the hard part |
| 2D placement constraints | Two independent topo sorts | Combine row/col positions |
| All orderings | Backtracking | Exponential, rarely asked |

---

## Common Pitfalls

1. **Self-loops**: A node depending on itself → always a cycle
2. **Duplicate edges**: Use Set or check before adding to avoid inflated in-degrees
3. **Disconnected components**: Kahn's handles naturally (all zero-degree nodes start)
4. **1-indexed vs 0-indexed**: Off-by-one in in-degree arrays
5. **Alien Dictionary edge case**: Longer word before shorter prefix → invalid input
6. **Empty graph**: 0 edges → any permutation is valid topo order
