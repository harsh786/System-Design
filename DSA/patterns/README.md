# DSA Patterns Guide - Staff Architect Interview Prep

> 45 comprehensive pattern guides covering every DSA category.  
> Each file: **Signal** (when to use) | **Template** (Java) | **Visualization** | **Variants** | **Complexity** | **Decision Flowchart**

---

## Quick Navigation

### Fundamental Data Structures
| # | Pattern | Key Problems |
|---|---------|-------------|
| [01](01-arrays.md) | **Arrays** | Kadane's, Dutch National Flag, Rotate, Next Permutation |
| [02](02-strings.md) | **Strings** | Palindromes, Anagrams, Encoding, Parsing |
| [03](03-hashtable.md) | **Hash Table** | Two Sum, Group Anagrams, LRU, Frequency Maps |
| [04](04-linkedlist.md) | **Linked List** | Reverse, Cycle Detection, Merge, LRU |
| [05](05-stack.md) | **Stack** | Valid Parentheses, Calculator, Decode String |
| [06](06-queue.md) | **Queue** | BFS, Sliding Window Max, Task Scheduler |
| [37](37-doubly-linked-list.md) | **Doubly Linked List** | LRU/LFU Cache, Flatten Multilevel, Browser History |

### Tree Structures
| # | Pattern | Key Problems |
|---|---------|-------------|
| [34](34-binary-tree.md) | **Binary Tree** | Traversals, LCA, Path Sum, Serialize, Morris |
| [35](35-binary-search-tree.md) | **Binary Search Tree** | Validate, Kth Smallest, Iterator, Recover BST |
| [09](09-trie.md) | **Trie** | Prefix Search, Word Search II, Autocomplete |

### Specialized Data Structures
| # | Pattern | Key Problems |
|---|---------|-------------|
| [07](07-matrix.md) | **Matrix** | Spiral, Rotate, Search, Island problems |
| [08](08-heap-priority-queue.md) | **Heap / Priority Queue** | Top-K, Merge K Lists, Median Stream |
| [10](10-monotonic-stack.md) | **Monotonic Stack** | Next Greater, Largest Rectangle, Trapping Rain |
| [11](11-monotonic-queue.md) | **Monotonic Queue** | Sliding Window Max, Jump Game VI |
| [41](41-ordered-set.md) | **Ordered Set (TreeMap)** | My Calendar, Sliding Window Median, Intervals |

### Search & Pointer Techniques
| # | Pattern | Key Problems |
|---|---------|-------------|
| [12](12-binary-search.md) | **Binary Search** | Search on Answer, Rotated Array, Median of Two |
| [13](13-sliding-window.md) | **Sliding Window** | Min Window Substring, Longest Without Repeating |
| [14](14-two-pointers.md) | **Two Pointers** | 3Sum, Container Water, Trapping Rain Water |

### Algorithmic Paradigms
| # | Pattern | Key Problems |
|---|---------|-------------|
| [15](15-dynamic-programming.md) | **Dynamic Programming** | All 12 sub-patterns: LIS, Knapsack, Interval, Bitmask, Digit DP |
| [16](16-greedy.md) | **Greedy** | Intervals, Jump Game, Task Scheduler, Gas Station |
| [17](17-backtracking.md) | **Backtracking** | Subsets, Permutations, N-Queens, Sudoku |
| [28](28-divide-and-conquer.md) | **Divide & Conquer** | Merge Sort, Quick Select, Closest Pair |
| [36](36-sorting.md) | **Sorting** | Merge, Quick, Counting, Bucket, Radix, Custom Comparators |

### Graph Algorithms
| # | Pattern | Key Problems |
|---|---------|-------------|
| [18](18-graphs.md) | **Graphs (BFS/DFS)** | Islands, Components, Cycle Detection, Clone |
| [19](19-union-find.md) | **Union-Find** | Components, Redundant Connection, Accounts Merge |
| [20](20-topological-sort.md) | **Topological Sort** | Course Schedule, Alien Dictionary, Parallel Courses |
| [21](21-shortest-path.md) | **Shortest Path** | Dijkstra, Bellman-Ford, Floyd-Warshall, 0-1 BFS |
| [22](22-minimum-spanning-tree.md) | **Minimum Spanning Tree** | Kruskal's, Prim's, Critical Edges |
| [44](44-advanced-graph.md) | **Advanced Graph** | SCC, Bridges, Eulerian, Network Flow, 2-SAT |

### Range Query & Prefix Structures
| # | Pattern | Key Problems |
|---|---------|-------------|
| [23](23-segment-tree.md) | **Segment Tree** | Range Query, Lazy Propagation, Persistent |
| [24](24-binary-indexed-tree.md) | **Binary Indexed Tree** | Prefix Sums, Inversions, Order Statistics |
| [26](26-prefix-sum.md) | **Prefix Sum** | Subarray Sum K, 2D Prefix, Difference Array |

### Bit & Number Operations
| # | Pattern | Key Problems |
|---|---------|-------------|
| [25](25-bit-manipulation.md) | **Bit Manipulation** | Single Number, Subset Enum, XOR tricks |
| [38](38-math-and-number-theory.md) | **Math & Number Theory** | GCD, Sieve, Modular Pow, Catalan, Combinatorics |

### Technique-Specific
| # | Pattern | Key Problems |
|---|---------|-------------|
| [27](27-sweep-line.md) | **Sweep Line** | Meeting Rooms, Skyline, Merge Intervals |
| [29](29-game-theory.md) | **Game Theory** | Minimax, Stone Game, Nim, Sprague-Grundy |
| [30](30-recursion.md) | **Recursion & Trees** | Tree DP, LCA, Serialize, Morris Traversal |
| [33](33-string-matching.md) | **String Matching** | KMP, Rabin-Karp, Z-Algorithm, Manacher's |
| [39](39-simulation-and-enumeration.md) | **Simulation & Enumeration** | Spiral, Game of Life, Contribution Technique |
| [40](40-data-stream.md) | **Data Stream** | Median Stream, Moving Average, Top-K Stream |
| [42](42-randomized-algorithms.md) | **Randomized Algorithms** | Shuffle, Reservoir Sampling, Skip List |
| [43](43-geometry.md) | **Geometry** | Convex Hull, Cross Product, Closest Pair |
| [45](45-interactive.md) | **Interactive Problems** | Guess Number, Find Celebrity, Master Mind |

### System & OOP Design
| # | Pattern | Key Problems |
|---|---------|-------------|
| [31](31-design-patterns.md) | **Design Patterns** | LRU/LFU Cache, RandomizedSet, Iterator |
| [32](32-concurrency.md) | **Concurrency** | Print in Order, Dining Philosophers, Producer-Consumer |

---

## How to Use This Guide

```
1. Read the problem statement
2. Identify SIGNALS (constraints, keywords, data characteristics)
3. Navigate to the matching pattern file
4. Apply the TEMPLATE, adjusting for the specific variant
5. Verify with the COMPLEXITY section
```

## Pattern Selection Mega-Flowchart

```
Problem arrives
    |
    v
Is it asking to DESIGN a data structure?  ──────────────>  [31-design-patterns.md]
    |
    No
    v
Is it about CONCURRENCY / thread safety?  ──────────────>  [32-concurrency.md]
    |
    No
    v
Is it INTERACTIVE (query an API)?  ─────────────────────>  [45-interactive.md]
    |
    No
    v
Is it a GAME / two-player optimal play?  ───────────────>  [29-game-theory.md]
    |
    No
    v
Is it about PROBABILITY / random sampling?  ────────────>  [42-randomized-algorithms.md]
    |
    No
    v
Is the input a TREE?
    |       |
    Yes     No
    |       |
    v       v
BST property needed?     Is input a GRAPH or can be modeled as one?
  Yes → [35]               |           |
  No  → [34]               Yes         No
                            |           |
                            v           v
                    What operation?     Is input SORTED or can we sort?
                        |                   |           |
                        |                   Yes         No
                        |                   |           |
                        v                   v           v
                    Shortest path? → [21]   Binary Search → [12]
                    Ordering/deps? → [20]   Two Pointers → [14]
                    Components?    → [19]   Sliding Window → [13]
                    MST?           → [22]       |
                    SCC/Bridges?   → [44]       v
                    Traversal?     → [18]   Array/String → [01]/[02]
                                            Hash Table → [03]
                                            Stack → [05]
                                            Monotonic → [10]/[11]
                                            Prefix Sum → [26]
                                            DP → [15]
                                            Greedy → [16]
                                            Backtracking → [17]
                                            Math → [38]
                                            Geometry → [43]
                                            Simulation → [39]
                                            Stream → [40]
```

## Complexity Quick Reference

| Pattern | Time | Space |
|---------|------|-------|
| Binary Search | O(log n) | O(1) |
| Two Pointers | O(n) | O(1) |
| Sliding Window | O(n) | O(k) |
| Sorting | O(n log n) | O(n) |
| BFS/DFS | O(V+E) | O(V) |
| Dijkstra | O((V+E) log V) | O(V) |
| Union-Find | O(α(n)) amortized | O(n) |
| Topo Sort | O(V+E) | O(V) |
| DP | O(states × transitions) | O(states) |
| Backtracking | O(k^n) or O(n!) | O(n) |
| Segment Tree | O(log n) query/update | O(n) |
| BIT | O(log n) query/update | O(n) |
| Trie | O(L) per operation | O(Σ × L × n) |
| KMP | O(n + m) | O(m) |
| TreeMap ops | O(log n) | O(n) |
| Convex Hull | O(n log n) | O(n) |
| SCC (Tarjan) | O(V+E) | O(V) |
| Network Flow | O(V²E) Edmonds-Karp | O(V+E) |

---

## Category Coverage Map

Maps repo directories to pattern files:

| Repo Folder | Pattern File(s) |
|-------------|----------------|
| 01-arrays | [01](01-arrays.md) |
| 02-strings | [02](02-strings.md) |
| 03-hashtable | [03](03-hashtable.md) |
| 04-dynamic-programming | [15](15-dynamic-programming.md) |
| 05-binary-search | [12](12-binary-search.md) |
| 06-sorting | [36](36-sorting.md) |
| 07-greedy | [16](16-greedy.md) |
| 08-trees | [34](34-binary-tree.md) |
| 09-graphs | [18](18-graphs.md) |
| 10-linked-list | [04](04-linkedlist.md) |
| 11-stack | [05](05-stack.md) |
| 12-sliding-window | [13](13-sliding-window.md) |
| 13-two-pointers | [14](14-two-pointers.md) |
| 14-heap-priority-queue | [08](08-heap-priority-queue.md) |
| 15-backtracking | [17](17-backtracking.md) |
| 16-design | [31](31-design-patterns.md) |
| 17-dfs | [18](18-graphs.md), [34](34-binary-tree.md) |
| 18-bfs | [18](18-graphs.md), [34](34-binary-tree.md) |
| 19-bit-manipulation | [25](25-bit-manipulation.md) |
| 20-matrix | [07](07-matrix.md) |
| 21-prefix-sum | [26](26-prefix-sum.md) |
| 22-union-find | [19](19-union-find.md) |
| 23-trie | [09](09-trie.md) |
| 24-monotonic-stack | [10](10-monotonic-stack.md) |
| 25-divide-and-conquer | [28](28-divide-and-conquer.md) |
| 26-math | [38](38-math-and-number-theory.md) |
| 27-simulation | [39](39-simulation-and-enumeration.md) |
| 28-counting | [39](39-simulation-and-enumeration.md) |
| 29-enumeration | [39](39-simulation-and-enumeration.md) |
| 30-queue | [06](06-queue.md) |
| 31-recursion | [30](30-recursion.md) |
| 32-geometry | [43](43-geometry.md) |
| 33-binary-indexed-tree | [24](24-binary-indexed-tree.md) |
| 34-segment-tree | [23](23-segment-tree.md) |
| 36-bitmask | [15](15-dynamic-programming.md) (Bitmask DP), [25](25-bit-manipulation.md) |
| 37-combinatorics | [38](38-math-and-number-theory.md) |
| 38-number-theory | [38](38-math-and-number-theory.md) |
| 39-topological-sort | [20](20-topological-sort.md) |
| 40-shortest-path | [21](21-shortest-path.md) |
| 41-string-matching | [33](33-string-matching.md) |
| 42-rolling-hash | [33](33-string-matching.md) (Rabin-Karp) |
| 43-game-theory | [29](29-game-theory.md) |
| 44-data-stream | [40](40-data-stream.md) |
| 45-monotonic-queue | [11](11-monotonic-queue.md) |
| 46-concurrency | [32](32-concurrency.md) |
| 48-ordered-set | [41](41-ordered-set.md) |
| 49-binary-search-tree | [35](35-binary-search-tree.md) |
| 50-memoization | [15](15-dynamic-programming.md) |
| 51-hash-function | [03](03-hashtable.md), [33](33-string-matching.md) |
| 52-interactive | [45](45-interactive.md) |
| 53-brainteaser | [39](39-simulation-and-enumeration.md), [38](38-math-and-number-theory.md) |
| 54-doubly-linked-list | [37](37-doubly-linked-list.md) |
| 55-merge-sort | [36](36-sorting.md), [28](28-divide-and-conquer.md) |
| 56-randomized | [42](42-randomized-algorithms.md) |
| 57-counting-sort | [36](36-sorting.md) |
| 58-iterator | [31](31-design-patterns.md) |
| 59-suffix-array | [33](33-string-matching.md) |
| 60-quickselect | [36](36-sorting.md), [28](28-divide-and-conquer.md) |
| 61-sweep-line | [27](27-sweep-line.md) |
| 62-probability-statistics | [42](42-randomized-algorithms.md) |
| 63-minimum-spanning-tree | [22](22-minimum-spanning-tree.md) |
| 64-bucket-sort | [36](36-sorting.md) |
| 65-shell-sort | [36](36-sorting.md) |
| 66-reservoir-sampling | [42](42-randomized-algorithms.md) |
| 67-eulerian-circuit | [44](44-advanced-graph.md) |
| 68-radix-sort | [36](36-sorting.md) |
| 69-strongly-connected-component | [44](44-advanced-graph.md) |
| 70-rejection-sampling | [42](42-randomized-algorithms.md) |
| 71-biconnected-component | [44](44-advanced-graph.md) |

---

*45 files, ~300+ patterns, all 69 repo categories covered. Staff Architect ready.*
