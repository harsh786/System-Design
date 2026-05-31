# DSA Patterns - Master Index

> **Navigation Guide:** Each file covers one category with complete pattern templates, visualizations, and decision flowcharts.

---

## Quick Start: "Which Pattern Do I Use?"

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PATTERN SELECTION DECISION TREE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  "Find pair/triplet with property"                                       │
│     → Sorted? TWO POINTERS. Unsorted? HASHMAP.                          │
│                                                                          │
│  "Contiguous subarray/substring with constraint"                         │
│     → Fixed size? FIXED SLIDING WINDOW                                   │
│     → Longest valid? VARIABLE WINDOW (shrink when invalid)               │
│     → Shortest valid? VARIABLE WINDOW (shrink while valid)               │
│     → Exact sum K? PREFIX SUM + HASHMAP                                  │
│                                                                          │
│  "Find position / boundary / min satisfying condition"                   │
│     → Monotonic? BINARY SEARCH                                           │
│     → "Minimize the maximum"? BINARY SEARCH ON ANSWER                    │
│                                                                          │
│  "Count ways / min cost / optimal with overlapping subproblems"          │
│     → DYNAMIC PROGRAMMING (see DP taxonomy below)                        │
│                                                                          │
│  "Local choice = global optimal"                                         │
│     → GREEDY (intervals, scheduling, reachability)                       │
│                                                                          │
│  "Generate all valid combinations/permutations"                          │
│     → BACKTRACKING (choose-explore-unchoose)                             │
│                                                                          │
│  "Shortest path / connected / reachable"                                 │
│     → Unweighted: BFS                                                    │
│     → Weighted (no neg): DIJKSTRA                                        │
│     → Negative weights: BELLMAN-FORD                                     │
│     → Dependencies/order: TOPOLOGICAL SORT                               │
│                                                                          │
│  "Next greater/smaller element"                                          │
│     → MONOTONIC STACK                                                    │
│                                                                          │
│  "Max/min in sliding window"                                             │
│     → MONOTONIC DEQUE                                                    │
│                                                                          │
│  "Top K / Kth element / streaming"                                       │
│     → HEAP (min-heap size K) or QUICKSELECT                              │
│                                                                          │
│  "Prefix-based lookup / autocomplete / multi-pattern"                    │
│     → TRIE                                                               │
│                                                                          │
│  "Range query with point/range updates"                                  │
│     → SEGMENT TREE or BIT (Fenwick Tree)                                 │
│                                                                          │
│  "Dynamic connectivity / merge groups"                                   │
│     → UNION-FIND                                                         │
│                                                                          │
│  "Design data structure with O(1) operations"                            │
│     → COMPOSITE: HashMap + LinkedList, HashMap + Array, etc.             │
│                                                                          │
│  "Two-player game, optimal play"                                         │
│     → MINIMAX / GAME THEORY DP                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Index

### Part A: Core Data Structures

| # | File | Categories Covered | Key Patterns |
|---|------|-------------------|--------------|
| 01 | [arrays.md](./01-arrays.md) | Arrays, Prefix Sum | Kadane, Prefix Sum+Map, Dutch Flag, Boyer-Moore, Cyclic Sort, Intervals, Two-Pass |
| 02 | [strings.md](./02-strings.md) | Strings | Frequency Array, Expand Center, KMP, Stack Decode, Parsing |
| 03 | [hashtable.md](./03-hashtable.md) | Hash Table | Complement Lookup, Frequency+Bucket, Group by Key, Cycle Detection |
| 04 | [linkedlist.md](./04-linkedlist.md) | Linked List | Floyd's, Reverse, Merge, Dummy Head, Nth from End, Reorder |
| 05 | [stack.md](./05-stack.md) | Stack, Monotonic Stack | Brackets, Next Greater/Smaller, Largest Rectangle, Calculator, Min Stack |
| 06 | [queue-monotonic-queue.md](./06-queue-monotonic-queue.md) | Queue, Monotonic Queue, BFS | Level-order, Multi-source BFS, Sliding Window Max, Circular Queue |
| 07 | [matrix.md](./07-matrix.md) | Matrix, Grid | Spiral, Rotate, Sorted Search, Islands, Grid DP, Game of Life |

### Part B: Algorithmic Patterns

| # | File | Categories Covered | Key Patterns |
|---|------|-------------------|--------------|
| 08 | [dynamic-programming.md](./08-dynamic-programming.md) | DP (all types) | Linear, Knapsack 0/1 & Unbounded, LIS, Two-String, Interval, State Machine, Tree DP, Bitmask |
| 09 | [graphs.md](./09-graphs.md) | Graphs, Shortest Path, MST, Topo Sort | BFS, DFS, Dijkstra, Bellman-Ford, Union-Find, Bipartite, Tarjan's SCC |
| 10 | [binary-search-sliding-window-two-pointers-greedy-backtracking.md](./10-binary-search-sliding-window-two-pointers-greedy-backtracking.md) | Binary Search, Sliding Window, Two Pointers, Greedy, Backtracking | Search on Answer, Variable/Fixed Window, Converge/Diverge, Intervals, Subsets/Permutations/N-Queens |
| 11 | [advanced-patterns.md](./11-advanced-patterns.md) | Segment Tree, BIT, Bit Manipulation, Design, Concurrency, Prefix Sum, Sweep Line, D&C, Game Theory, String Matching | All advanced algorithmic patterns |
| 12 | [heap-trie.md](./12-heap-trie.md) | Heap/Priority Queue, Trie | Top-K, Two Heaps, K-Way Merge, Scheduling, XOR Trie, Autocomplete |

---

## DP Pattern Taxonomy (Quick Reference)

| Problem Type | Pattern | State Definition |
|---|---|---|
| f(n) from f(n-1), f(n-2) | Linear/Fibonacci | dp[i] |
| Take or skip adjacent | House Robber | dp[i] = max(skip, take) |
| Longest ordered subsequence | LIS | dp[i] or patience sort |
| Items + capacity, once each | 0/1 Knapsack | dp[w] backwards |
| Items + capacity, unlimited | Unbounded Knapsack | dp[w] forwards |
| Transform string A → B | Two-String DP | dp[i][j] on prefixes |
| Grid paths / min cost | Grid DP | dp[i][j] |
| Optimal split of range | Interval DP | dp[i][j] with split k |
| Multi-phase transitions | State Machine | dp per state |
| Optimize on tree | Tree DP | dfs returns to parent |
| Track used set (n≤20) | Bitmask DP | dp[mask] |
| Count numbers with property | Digit DP | dp(pos, tight, state) |

---

## Complexity Cheat Sheet

| Algorithm | Time | Space |
|-----------|------|-------|
| Binary Search | O(log n) | O(1) |
| Two Pointers | O(n) | O(1) |
| Sliding Window | O(n) | O(k) or O(1) |
| Kadane's | O(n) | O(1) |
| DFS / BFS | O(V + E) | O(V) |
| Dijkstra | O((V+E) log V) | O(V) |
| Bellman-Ford | O(V * E) | O(V) |
| Floyd-Warshall | O(V³) | O(V²) |
| Topological Sort | O(V + E) | O(V) |
| Union-Find | O(α(n)) ≈ O(1) | O(n) |
| Segment Tree | O(log n) query/update | O(n) |
| BIT (Fenwick) | O(log n) query/update | O(n) |
| Trie | O(m) per op | O(Σ * total_chars) |
| KMP | O(n + m) | O(m) |
| Kruskal MST | O(E log E) | O(V) |
| Prim MST | O((V+E) log V) | O(V) |
| QuickSelect | O(n) average | O(1) |
| Merge Sort | O(n log n) | O(n) |
| Heap (push/pop) | O(log n) | O(n) |

---

## Interview Execution Framework

### Step 1: Clarify (2 min)
- Input size and constraints (this determines complexity!)
- Edge cases: empty, single element, all same, negative numbers
- Return type: count, boolean, actual elements, indices?

### Step 2: Identify Pattern (1 min)
- Use the decision tree above
- State explicitly: "This is a [pattern] problem because [signal]..."

### Step 3: Approach (3 min)
- High-level algorithm
- State time/space complexity BEFORE coding
- Mention trade-offs if multiple approaches exist

### Step 4: Code (15 min)
- Write clean, template-based code
- Handle edge cases inline (not as separate blocks)
- Use meaningful variable names

### Step 5: Verify (3 min)
- Dry run with given example
- Check edge cases: empty, n=1, duplicates, overflow
- Confirm complexity matches stated
