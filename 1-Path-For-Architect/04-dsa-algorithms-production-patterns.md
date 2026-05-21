# DSA and Algorithms for Architect Interviews

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 5. DSA Roadmap for Architect Interviews

## Why DSA Matters for Architects

DSA is not only for coding rounds. It helps you reason about scalability, memory, streaming, scheduling, routing, caching, partitioning, query planning, and distributed systems.

## Must-Master Patterns

- Arrays and prefix sums.
- Hash maps and sets.
- Two pointers.
- Sliding window.
- Stack and monotonic stack.
- Queue and deque.
- Heap and priority queue.
- Binary search.
- Intervals.
- Linked lists.
- Trees.
- Tries.
- Graph BFS/DFS.
- Topological sort.
- Union-find.
- Shortest paths.
- Backtracking.
- Dynamic programming.
- Greedy algorithms.
- Bit manipulation.
- Streaming top-K.
- Bloom filters.
- Consistent hashing.
- LRU/LFU caches.
- Concurrent queues.

## Production Connections

| DSA Topic | Production Usage |
| --- | --- |
| Heap | Schedulers, top-K analytics, priority queues. |
| Trie | Autocomplete, prefix search, routing tables. |
| Graph traversal | Dependency resolution, workflow engines, social graphs. |
| Union-find | Clustering, connectivity, account merge. |
| Consistent hashing | Distributed cache, sharded storage, load distribution. |
| Bloom filter | Avoiding unnecessary database or disk reads. |
| Sliding window | Rate limiting, stream analytics, fraud detection. |
| LRU/LFU | Cache eviction. |
| Dynamic programming | Optimization, pricing, scheduling. |

---


## Top 20 LeetCode Problems Per DSA Category

### 1. Arrays
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Two Sum | 1 | Easy |
| 2 | Best Time to Buy and Sell Stock | 121 | Easy |
| 3 | Contains Duplicate | 217 | Easy |
| 4 | Product of Array Except Self | 238 | Medium |
| 5 | Maximum Subarray | 53 | Medium |
| 6 | Maximum Product Subarray | 152 | Medium |
| 7 | Find Minimum in Rotated Sorted Array | 153 | Medium |
| 8 | Search in Rotated Sorted Array | 33 | Medium |
| 9 | 3Sum | 15 | Medium |
| 10 | Container With Most Water | 11 | Medium |
| 11 | Next Permutation | 31 | Medium |
| 12 | Merge Intervals | 56 | Medium |
| 13 | Sort Colors | 75 | Medium |
| 14 | Subarray Sum Equals K | 560 | Medium |
| 15 | Rotate Array | 189 | Medium |
| 16 | Trapping Rain Water | 42 | Hard |
| 17 | First Missing Positive | 41 | Hard |
| 18 | Longest Consecutive Sequence | 128 | Medium |
| 19 | 4Sum | 18 | Medium |
| 20 | Median of Two Sorted Arrays | 4 | Hard |

### 2. Hash Maps
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Two Sum | 1 | Easy |
| 2 | Group Anagrams | 49 | Medium |
| 3 | Valid Anagram | 242 | Easy |
| 4 | Longest Substring Without Repeating Characters | 3 | Medium |
| 5 | Top K Frequent Elements | 347 | Medium |
| 6 | Contains Duplicate II | 219 | Easy |
| 7 | Subarray Sum Equals K | 560 | Medium |
| 8 | Isomorphic Strings | 205 | Easy |
| 9 | Word Pattern | 290 | Easy |
| 10 | Longest Consecutive Sequence | 128 | Medium |
| 11 | 4Sum II | 454 | Medium |
| 12 | Minimum Window Substring | 76 | Hard |
| 13 | Copy List with Random Pointer | 138 | Medium |
| 14 | Happy Number | 202 | Easy |
| 15 | Insert Delete GetRandom O(1) | 380 | Medium |
| 16 | First Unique Character in a String | 387 | Easy |
| 17 | Design HashMap | 706 | Easy |
| 18 | LRU Cache | 146 | Medium |
| 19 | Brick Wall | 554 | Medium |
| 20 | Encode and Decode TinyURL | 535 | Medium |

### 3. Two Pointers
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Valid Palindrome | 125 | Easy |
| 2 | Two Sum II - Input Array Is Sorted | 167 | Medium |
| 3 | 3Sum | 15 | Medium |
| 4 | Container With Most Water | 11 | Medium |
| 5 | Trapping Rain Water | 42 | Hard |
| 6 | Remove Duplicates from Sorted Array | 26 | Easy |
| 7 | Move Zeroes | 283 | Easy |
| 8 | Sort Colors | 75 | Medium |
| 9 | Boats to Save People | 881 | Medium |
| 10 | 3Sum Closest | 16 | Medium |
| 11 | Backspace String Compare | 844 | Easy |
| 12 | Squares of a Sorted Array | 977 | Easy |
| 13 | 4Sum | 18 | Medium |
| 14 | Remove Nth Node From End of List | 19 | Medium |
| 15 | Linked List Cycle | 141 | Easy |
| 16 | Palindrome Linked List | 234 | Easy |
| 17 | Merge Sorted Array | 88 | Easy |
| 18 | Intersection of Two Arrays II | 350 | Easy |
| 19 | Longest Mountain in Array | 845 | Medium |
| 20 | Partition Labels | 763 | Medium |

### 4. Sliding Window
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Best Time to Buy and Sell Stock | 121 | Easy |
| 2 | Longest Substring Without Repeating Characters | 3 | Medium |
| 3 | Longest Repeating Character Replacement | 424 | Medium |
| 4 | Permutation in String | 567 | Medium |
| 5 | Minimum Window Substring | 76 | Hard |
| 6 | Sliding Window Maximum | 239 | Hard |
| 7 | Minimum Size Subarray Sum | 209 | Medium |
| 8 | Fruit Into Baskets | 904 | Medium |
| 9 | Subarrays with K Different Integers | 992 | Hard |
| 10 | Maximum Number of Vowels in a Substring | 1456 | Medium |
| 11 | Get Equal Substrings Within Budget | 1208 | Medium |
| 12 | Max Consecutive Ones III | 1004 | Medium |
| 13 | Grumpy Bookstore Owner | 1052 | Medium |
| 14 | Find All Anagrams in a String | 438 | Medium |
| 15 | Substring with Concatenation of All Words | 30 | Hard |
| 16 | Minimum Operations to Reduce X to Zero | 1658 | Medium |
| 17 | Count Number of Nice Subarrays | 1248 | Medium |
| 18 | Longest Subarray of 1s After Deleting One Element | 1493 | Medium |
| 19 | Maximum Points You Can Obtain from Cards | 1423 | Medium |
| 20 | Frequency of the Most Frequent Element | 1838 | Medium |

### 5. Stacks
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Valid Parentheses | 20 | Easy |
| 2 | Min Stack | 155 | Medium |
| 3 | Evaluate Reverse Polish Notation | 150 | Medium |
| 4 | Daily Temperatures | 739 | Medium |
| 5 | Car Fleet | 853 | Medium |
| 6 | Largest Rectangle in Histogram | 84 | Hard |
| 7 | Generate Parentheses | 22 | Medium |
| 8 | Asteroid Collision | 735 | Medium |
| 9 | Basic Calculator | 224 | Hard |
| 10 | Basic Calculator II | 227 | Medium |
| 11 | Decode String | 394 | Medium |
| 12 | Remove All Adjacent Duplicates in String II | 1209 | Medium |
| 13 | Trapping Rain Water | 42 | Hard |
| 14 | Next Greater Element I | 496 | Easy |
| 15 | Next Greater Element II | 503 | Medium |
| 16 | Online Stock Span | 901 | Medium |
| 17 | Simplify Path | 71 | Medium |
| 18 | Remove K Digits | 402 | Medium |
| 19 | Maximal Rectangle | 85 | Hard |
| 20 | Longest Valid Parentheses | 32 | Hard |

### 6. Queues
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Implement Queue using Stacks | 232 | Easy |
| 2 | Implement Stack using Queues | 225 | Easy |
| 3 | Number of Recent Calls | 933 | Easy |
| 4 | Design Circular Queue | 622 | Medium |
| 5 | Sliding Window Maximum | 239 | Hard |
| 6 | Rotting Oranges | 994 | Medium |
| 7 | Walls and Gates | 286 | Medium |
| 8 | Number of Islands | 200 | Medium |
| 9 | Open the Lock | 752 | Medium |
| 10 | Shortest Path in Binary Matrix | 1091 | Medium |
| 11 | Jump Game III | 1306 | Medium |
| 12 | Design Hit Counter | 362 | Medium |
| 13 | Moving Average from Data Stream | 346 | Easy |
| 14 | Snakes and Ladders | 909 | Medium |
| 15 | Perfect Squares | 279 | Medium |
| 16 | Word Ladder | 127 | Hard |
| 17 | Minimum Knight Moves | 1197 | Medium |
| 18 | Shortest Bridge | 934 | Medium |
| 19 | Bus Routes | 815 | Hard |
| 20 | Design Circular Deque | 641 | Medium |

### 7. Heaps / Priority Queues
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Kth Largest Element in an Array | 215 | Medium |
| 2 | Top K Frequent Elements | 347 | Medium |
| 3 | Find Median from Data Stream | 295 | Hard |
| 4 | Merge k Sorted Lists | 23 | Hard |
| 5 | Task Scheduler | 621 | Medium |
| 6 | K Closest Points to Origin | 973 | Medium |
| 7 | Reorganize String | 767 | Medium |
| 8 | Sort Characters By Frequency | 451 | Medium |
| 9 | Kth Smallest Element in a Sorted Matrix | 378 | Medium |
| 10 | Last Stone Weight | 1046 | Easy |
| 11 | Ugly Number II | 264 | Medium |
| 12 | Meeting Rooms II | 253 | Medium |
| 13 | Smallest Range Covering Elements from K Lists | 632 | Hard |
| 14 | IPO | 502 | Hard |
| 15 | Find K Pairs with Smallest Sums | 373 | Medium |
| 16 | Furthest Building You Can Reach | 1642 | Medium |
| 17 | Sliding Window Median | 480 | Hard |
| 18 | Maximum Performance of a Team | 1383 | Hard |
| 19 | Minimum Cost to Hire K Workers | 857 | Hard |
| 20 | Design Twitter | 355 | Medium |

### 8. Binary Search
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Binary Search | 704 | Easy |
| 2 | Search in Rotated Sorted Array | 33 | Medium |
| 3 | Find Minimum in Rotated Sorted Array | 153 | Medium |
| 4 | Search a 2D Matrix | 74 | Medium |
| 5 | Koko Eating Bananas | 875 | Medium |
| 6 | Find Peak Element | 162 | Medium |
| 7 | Median of Two Sorted Arrays | 4 | Hard |
| 8 | Time Based Key-Value Store | 981 | Medium |
| 9 | Search in Rotated Sorted Array II | 81 | Medium |
| 10 | Find First and Last Position of Element in Sorted Array | 34 | Medium |
| 11 | Capacity To Ship Packages Within D Days | 1011 | Medium |
| 12 | Split Array Largest Sum | 410 | Hard |
| 13 | Minimum Number of Days to Make m Bouquets | 1482 | Medium |
| 14 | Aggressive Cows (Binary Search on Answer) | — | Medium |
| 15 | Sqrt(x) | 69 | Easy |
| 16 | Single Element in a Sorted Array | 540 | Medium |
| 17 | Search Insert Position | 35 | Easy |
| 18 | Magnetic Force Between Two Balls | 1552 | Medium |
| 19 | Longest Increasing Subsequence (Binary Search) | 300 | Medium |
| 20 | Russian Doll Envelopes | 354 | Hard |

### 9. Intervals
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Merge Intervals | 56 | Medium |
| 2 | Insert Interval | 57 | Medium |
| 3 | Non-overlapping Intervals | 435 | Medium |
| 4 | Meeting Rooms | 252 | Easy |
| 5 | Meeting Rooms II | 253 | Medium |
| 6 | Minimum Number of Arrows to Burst Balloons | 452 | Medium |
| 7 | Interval List Intersections | 986 | Medium |
| 8 | Employee Free Time | 759 | Hard |
| 9 | Remove Covered Intervals | 1288 | Medium |
| 10 | My Calendar I | 729 | Medium |
| 11 | My Calendar II | 731 | Medium |
| 12 | Car Pooling | 1094 | Medium |
| 13 | Minimum Interval to Include Each Query | 1851 | Hard |
| 14 | Data Stream as Disjoint Intervals | 352 | Hard |
| 15 | Summary Ranges | 228 | Easy |
| 16 | Teemo Attacking | 495 | Easy |
| 17 | Video Stitching | 1024 | Medium |
| 18 | Maximum Length of Pair Chain | 646 | Medium |
| 19 | Add Bold Tag in String | 616 | Medium |
| 20 | Range Module | 715 | Hard |

### 10. Linked Lists
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Reverse Linked List | 206 | Easy |
| 2 | Merge Two Sorted Lists | 21 | Easy |
| 3 | Linked List Cycle | 141 | Easy |
| 4 | Linked List Cycle II | 142 | Medium |
| 5 | Remove Nth Node From End of List | 19 | Medium |
| 6 | Reorder List | 143 | Medium |
| 7 | Add Two Numbers | 2 | Medium |
| 8 | Copy List with Random Pointer | 138 | Medium |
| 9 | LRU Cache | 146 | Medium |
| 10 | Merge k Sorted Lists | 23 | Hard |
| 11 | Reverse Nodes in k-Group | 25 | Hard |
| 12 | Palindrome Linked List | 234 | Easy |
| 13 | Flatten a Multilevel Doubly Linked List | 430 | Medium |
| 14 | Sort List | 148 | Medium |
| 15 | Intersection of Two Linked Lists | 160 | Easy |
| 16 | Odd Even Linked List | 328 | Medium |
| 17 | Swap Nodes in Pairs | 24 | Medium |
| 18 | Rotate List | 61 | Medium |
| 19 | Remove Duplicates from Sorted List II | 82 | Medium |
| 20 | Design Linked List | 707 | Medium |

### 11. Trees (Binary Trees)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Maximum Depth of Binary Tree | 104 | Easy |
| 2 | Invert Binary Tree | 226 | Easy |
| 3 | Same Tree | 100 | Easy |
| 4 | Binary Tree Level Order Traversal | 102 | Medium |
| 5 | Subtree of Another Tree | 572 | Easy |
| 6 | Construct Binary Tree from Preorder and Inorder | 105 | Medium |
| 7 | Binary Tree Right Side View | 199 | Medium |
| 8 | Lowest Common Ancestor of a Binary Tree | 236 | Medium |
| 9 | Binary Tree Zigzag Level Order Traversal | 103 | Medium |
| 10 | Diameter of Binary Tree | 543 | Easy |
| 11 | Balanced Binary Tree | 110 | Easy |
| 12 | Path Sum III | 437 | Medium |
| 13 | Binary Tree Maximum Path Sum | 124 | Hard |
| 14 | Serialize and Deserialize Binary Tree | 297 | Hard |
| 15 | Count Good Nodes in Binary Tree | 1448 | Medium |
| 16 | Flatten Binary Tree to Linked List | 114 | Medium |
| 17 | Populating Next Right Pointers in Each Node | 116 | Medium |
| 18 | Vertical Order Traversal of a Binary Tree | 987 | Hard |
| 19 | Sum Root to Leaf Numbers | 129 | Medium |
| 20 | All Nodes Distance K in Binary Tree | 863 | Medium |

### 12. Binary Search Trees (BST)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Validate Binary Search Tree | 98 | Medium |
| 2 | Kth Smallest Element in a BST | 230 | Medium |
| 3 | Lowest Common Ancestor of a BST | 235 | Medium |
| 4 | Convert Sorted Array to BST | 108 | Easy |
| 5 | Delete Node in a BST | 450 | Medium |
| 6 | Insert into a Binary Search Tree | 701 | Medium |
| 7 | Inorder Successor in BST | 285 | Medium |
| 8 | Binary Search Tree Iterator | 173 | Medium |
| 9 | Recover Binary Search Tree | 99 | Medium |
| 10 | Trim a Binary Search Tree | 669 | Medium |
| 11 | Range Sum of BST | 938 | Easy |
| 12 | Two Sum IV - Input is a BST | 653 | Easy |
| 13 | Closest Binary Search Tree Value | 270 | Easy |
| 14 | Serialize and Deserialize BST | 449 | Medium |
| 15 | Balance a Binary Search Tree | 1382 | Medium |
| 16 | Convert BST to Greater Tree | 538 | Medium |
| 17 | Unique Binary Search Trees | 96 | Medium |
| 18 | Unique Binary Search Trees II | 95 | Medium |
| 19 | Minimum Absolute Difference in BST | 530 | Easy |
| 20 | Contains Duplicate III | 220 | Hard |

### 13. Tries
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Implement Trie (Prefix Tree) | 208 | Medium |
| 2 | Design Add and Search Words Data Structure | 211 | Medium |
| 3 | Word Search II | 212 | Hard |
| 4 | Replace Words | 648 | Medium |
| 5 | Longest Word in Dictionary | 720 | Medium |
| 6 | Map Sum Pairs | 677 | Medium |
| 7 | Search Suggestions System | 1268 | Medium |
| 8 | Maximum XOR of Two Numbers in an Array | 421 | Medium |
| 9 | Palindrome Pairs | 336 | Hard |
| 10 | Stream of Characters | 1032 | Hard |
| 11 | Word Search | 79 | Medium |
| 12 | Longest Common Prefix | 14 | Easy |
| 13 | Extra Characters in a String | 2707 | Medium |
| 14 | Count Prefixes of a Given String | 2255 | Easy |
| 15 | Implement Magic Dictionary | 676 | Medium |
| 16 | Concatenated Words | 472 | Hard |
| 17 | Short Encoding of Words | 820 | Medium |
| 18 | Prefix and Suffix Search | 745 | Hard |
| 19 | Design File System | 1166 | Medium |
| 20 | Camelcase Matching | 1023 | Medium |

### 14. Graphs (BFS/DFS)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Number of Islands | 200 | Medium |
| 2 | Clone Graph | 133 | Medium |
| 3 | Pacific Atlantic Water Flow | 417 | Medium |
| 4 | Course Schedule | 207 | Medium |
| 5 | Course Schedule II | 210 | Medium |
| 6 | Number of Connected Components in an Undirected Graph | 323 | Medium |
| 7 | Graph Valid Tree | 261 | Medium |
| 8 | Word Ladder | 127 | Hard |
| 9 | Surrounded Regions | 130 | Medium |
| 10 | Accounts Merge | 721 | Medium |
| 11 | Evaluate Division | 399 | Medium |
| 12 | Shortest Path in Binary Matrix | 1091 | Medium |
| 13 | All Paths From Source to Target | 797 | Medium |
| 14 | Redundant Connection | 684 | Medium |
| 15 | Is Graph Bipartite? | 785 | Medium |
| 16 | Minimum Height Trees | 310 | Medium |
| 17 | Reconstruct Itinerary | 332 | Hard |
| 18 | Alien Dictionary | 269 | Hard |
| 19 | Cheapest Flights Within K Stops | 787 | Medium |
| 20 | Making A Large Island | 827 | Hard |

### 15. Topological Sort
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Course Schedule | 207 | Medium |
| 2 | Course Schedule II | 210 | Medium |
| 3 | Alien Dictionary | 269 | Hard |
| 4 | Sequence Reconstruction | 444 | Medium |
| 5 | Minimum Height Trees | 310 | Medium |
| 6 | Parallel Courses | 1136 | Medium |
| 7 | Parallel Courses III | 2050 | Hard |
| 8 | Longest Increasing Path in a Matrix | 329 | Hard |
| 9 | Sort Items by Groups Respecting Dependencies | 1203 | Hard |
| 10 | Find All Possible Recipes from Supplies | 2115 | Medium |
| 11 | Build a Matrix With Conditions | 2392 | Hard |
| 12 | Course Schedule IV | 1462 | Medium |
| 13 | Loud and Rich | 851 | Medium |
| 14 | All Ancestors of a Node in a DAG | 2192 | Medium |
| 15 | Largest Color Value in a Directed Graph | 1857 | Hard |
| 16 | Detect Cycles in 2D Grid | 1559 | Medium |
| 17 | Find Eventual Safe States | 802 | Medium |
| 18 | Longest Path With Different Adjacent Characters | 2246 | Hard |
| 19 | Minimum Number of Semesters to Graduate | 1494 | Hard |
| 20 | Restricted Paths From First to Last Node | 1786 | Medium |

### 16. Shortest Path
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Network Delay Time (Dijkstra) | 743 | Medium |
| 2 | Cheapest Flights Within K Stops (Bellman-Ford) | 787 | Medium |
| 3 | Path With Minimum Effort | 1631 | Medium |
| 4 | Swim in Rising Water | 778 | Hard |
| 5 | Shortest Path in Binary Matrix | 1091 | Medium |
| 6 | Path with Maximum Probability | 1514 | Medium |
| 7 | Find the City With the Smallest Number of Neighbors (Floyd-Warshall) | 1334 | Medium |
| 8 | Shortest Path to Get All Keys | 864 | Hard |
| 9 | Minimum Cost to Make at Least One Valid Path | 1368 | Hard |
| 10 | Shortest Path Visiting All Nodes | 847 | Hard |
| 11 | Word Ladder | 127 | Hard |
| 12 | Sliding Puzzle | 773 | Hard |
| 13 | Minimum Obstacle Removal to Reach Corner | 2290 | Hard |
| 14 | Shortest Path in a Grid with Obstacles Elimination | 1293 | Hard |
| 15 | Design Graph With Shortest Path Calculator | 2642 | Hard |
| 16 | Number of Ways to Arrive at Destination | 1976 | Medium |
| 17 | Reachable Nodes In Subdivided Graph | 882 | Hard |
| 18 | Minimum Weighted Subgraph With Required Paths | 2203 | Hard |
| 19 | Second Minimum Time to Reach Destination | 2045 | Hard |
| 20 | The Maze II | 505 | Medium |

### 17. Union Find (Disjoint Set)
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Number of Connected Components in an Undirected Graph | 323 | Medium |
| 2 | Redundant Connection | 684 | Medium |
| 3 | Graph Valid Tree | 261 | Medium |
| 4 | Accounts Merge | 721 | Medium |
| 5 | Longest Consecutive Sequence | 128 | Medium |
| 6 | Number of Islands II | 305 | Hard |
| 7 | Surrounded Regions | 130 | Medium |
| 8 | Most Stones Removed with Same Row or Column | 947 | Medium |
| 9 | Satisfiability of Equality Equations | 990 | Medium |
| 10 | Connecting Cities With Minimum Cost (Kruskal) | 1135 | Medium |
| 11 | Number of Operations to Make Network Connected | 1319 | Medium |
| 12 | Smallest String With Swaps | 1202 | Medium |
| 13 | Swim in Rising Water | 778 | Hard |
| 14 | Regions Cut By Slashes | 959 | Medium |
| 15 | Remove Max Number of Edges to Keep Graph Fully Traversable | 1579 | Hard |
| 16 | Optimize Water Distribution in a Village | 1168 | Hard |
| 17 | Checking Existence of Edge Length Limited Paths | 1697 | Hard |
| 18 | Min Cost to Connect All Points | 1584 | Medium |
| 19 | Lexicographically Smallest Equivalent String | 1061 | Medium |
| 20 | Making A Large Island | 827 | Hard |

### 18. Backtracking
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Subsets | 78 | Medium |
| 2 | Subsets II | 90 | Medium |
| 3 | Permutations | 46 | Medium |
| 4 | Permutations II | 47 | Medium |
| 5 | Combination Sum | 39 | Medium |
| 6 | Combination Sum II | 40 | Medium |
| 7 | Palindrome Partitioning | 131 | Medium |
| 8 | Letter Combinations of a Phone Number | 17 | Medium |
| 9 | Word Search | 79 | Medium |
| 10 | N-Queens | 51 | Hard |
| 11 | N-Queens II | 52 | Hard |
| 12 | Sudoku Solver | 37 | Hard |
| 13 | Generate Parentheses | 22 | Medium |
| 14 | Combinations | 77 | Medium |
| 15 | Restore IP Addresses | 93 | Medium |
| 16 | Partition to K Equal Sum Subsets | 698 | Medium |
| 17 | Splitting a String Into Descending Consecutive Values | 1849 | Medium |
| 18 | Maximum Length of a Concatenated String with Unique Characters | 1239 | Medium |
| 19 | Word Break II | 140 | Hard |
| 20 | Expression Add Operators | 282 | Hard |

### 19. Dynamic Programming
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Climbing Stairs | 70 | Easy |
| 2 | House Robber | 198 | Medium |
| 3 | House Robber II | 213 | Medium |
| 4 | Longest Increasing Subsequence | 300 | Medium |
| 5 | Coin Change | 322 | Medium |
| 6 | Word Break | 139 | Medium |
| 7 | Longest Common Subsequence | 1143 | Medium |
| 8 | Unique Paths | 62 | Medium |
| 9 | Jump Game | 55 | Medium |
| 10 | Decode Ways | 91 | Medium |
| 11 | Partition Equal Subset Sum | 416 | Medium |
| 12 | Target Sum | 494 | Medium |
| 13 | Edit Distance | 72 | Medium |
| 14 | 0/1 Knapsack (classic) | — | Medium |
| 15 | Longest Palindromic Substring | 5 | Medium |
| 16 | Palindromic Substrings | 647 | Medium |
| 17 | Minimum Path Sum | 64 | Medium |
| 18 | Maximal Square | 221 | Medium |
| 19 | Best Time to Buy and Sell Stock with Cooldown | 309 | Medium |
| 20 | Burst Balloons | 312 | Hard |

### 20. Greedy
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Jump Game | 55 | Medium |
| 2 | Jump Game II | 45 | Medium |
| 3 | Gas Station | 134 | Medium |
| 4 | Hand of Straights | 846 | Medium |
| 5 | Merge Triplets to Form Target Triplet | 1899 | Medium |
| 6 | Partition Labels | 763 | Medium |
| 7 | Valid Parenthesis String | 678 | Medium |
| 8 | Task Scheduler | 621 | Medium |
| 9 | Minimum Number of Arrows to Burst Balloons | 452 | Medium |
| 10 | Non-overlapping Intervals | 435 | Medium |
| 11 | Maximum Subarray | 53 | Medium |
| 12 | Best Time to Buy and Sell Stock II | 122 | Medium |
| 13 | Candy | 135 | Hard |
| 14 | Lemonade Change | 860 | Easy |
| 15 | Queue Reconstruction by Height | 406 | Medium |
| 16 | Boats to Save People | 881 | Medium |
| 17 | Minimum Platforms (Train Station) | — | Medium |
| 18 | Assign Cookies | 455 | Easy |
| 19 | Reorganize String | 767 | Medium |
| 20 | Wiggle Subsequence | 376 | Medium |

### 21. Bit Manipulation
| # | Problem | LC# | Difficulty |
|---|---------|-----|------------|
| 1 | Single Number | 136 | Easy |
| 2 | Number of 1 Bits | 191 | Easy |
| 3 | Counting Bits | 338 | Easy |
| 4 | Reverse Bits | 190 | Easy |
| 5 | Missing Number | 268 | Easy |
| 6 | Sum of Two Integers | 371 | Medium |
| 7 | Single Number II | 137 | Medium |
| 8 | Single Number III | 260 | Medium |
| 9 | Bitwise AND of Numbers Range | 201 | Medium |
| 10 | Power of Two | 231 | Easy |
| 11 | Subsets (bit masking) | 78 | Medium |
| 12 | Hamming Distance | 461 | Easy |
| 13 | Total Hamming Distance | 477 | Medium |
| 14 | Maximum XOR of Two Numbers in an Array | 421 | Medium |
| 15 | Complement of Base 10 Integer | 1009 | Easy |
| 16 | UTF-8 Validation | 393 | Medium |
| 17 | Minimum Flips to Make a OR b Equal to c | 1318 | Medium |
| 18 | Decode XORed Permutation | 1734 | Medium |
| 19 | Find the Duplicate Number (bit approach) | 287 | Medium |
| 20 | Maximum Product of Word Lengths | 318 | Medium |

---


# 23. DSA and Algorithms Interview Bank by Category

This section follows the LeetCode-style category map from the attached image. Treat each category as a 20-question sprint. For architect roles, solve the problem and also explain the production connection.

## 23.1 Array - Top 20

1. Two Sum
2. Best Time to Buy and Sell Stock
3. Product of Array Except Self
4. Maximum Subarray
5. Maximum Product Subarray
6. Contains Duplicate
7. Rotate Array
8. Move Zeroes
9. Merge Sorted Array
10. Majority Element
11. Missing Number
12. Find All Numbers Disappeared in an Array
13. First Missing Positive
14. Subarray Sum Equals K
15. 3Sum
16. Container With Most Water
17. Trapping Rain Water
18. Insert Interval
19. Merge Intervals
20. Minimum Size Subarray Sum

## 23.2 String - Top 20

1. Valid Anagram
2. Valid Palindrome
3. Longest Substring Without Repeating Characters
4. Longest Palindromic Substring
5. Palindromic Substrings
6. Group Anagrams
7. Encode and Decode Strings
8. String to Integer
9. Implement strStr
10. Reverse Words in a String
11. Minimum Window Substring
12. Longest Repeating Character Replacement
13. Valid Parentheses
14. Generate Parentheses
15. Decode String
16. Multiply Strings
17. Add Binary
18. Roman to Integer
19. Integer to Roman
20. Find All Anagrams in a String

## 23.3 Hash Table - Top 20

1. Two Sum
2. Group Anagrams
3. Top K Frequent Elements
4. Longest Consecutive Sequence
5. Subarray Sum Equals K
6. Valid Sudoku
7. Copy List with Random Pointer
8. LRU Cache
9. LFU Cache
10. Design HashMap
11. Design HashSet
12. Randomized Set
13. First Unique Character in a String
14. Isomorphic Strings
15. Word Pattern
16. Intersection of Two Arrays
17. Four Sum II
18. Find Duplicate File in System
19. Time Based Key-Value Store
20. Logger Rate Limiter

## 23.4 Math - Top 20

1. Reverse Integer
2. Palindrome Number
3. Pow(x, n)
4. Sqrt(x)
5. Plus One
6. Add Binary
7. Multiply Strings
8. Factorial Trailing Zeroes
9. Happy Number
10. Excel Sheet Column Number
11. Integer to Roman
12. Roman to Integer
13. Count Primes
14. Product of Array Except Self
15. Divide Two Integers
16. Fraction to Recurring Decimal
17. Random Pick with Weight
18. Rectangle Area
19. Max Points on a Line
20. Basic Calculator

## 23.5 Dynamic Programming - Top 20

1. Climbing Stairs
2. House Robber
3. House Robber II
4. Coin Change
5. Coin Change II
6. Longest Increasing Subsequence
7. Longest Common Subsequence
8. Edit Distance
9. Word Break
10. Decode Ways
11. Unique Paths
12. Minimum Path Sum
13. Maximum Product Subarray
14. Partition Equal Subset Sum
15. Target Sum
16. Palindromic Substrings
17. Longest Palindromic Substring
18. Best Time to Buy and Sell Stock with Cooldown
19. Burst Balloons
20. Regular Expression Matching

## 23.6 Sorting and Intervals - Top 20

1. Merge Intervals
2. Insert Interval
3. Non-overlapping Intervals
4. Meeting Rooms
5. Meeting Rooms II
6. Sort Colors
7. Kth Largest Element in an Array
8. Top K Frequent Elements
9. Largest Number
10. Merge Sorted Array
11. Merge k Sorted Lists
12. Queue Reconstruction by Height
13. Car Fleet
14. Minimum Number of Arrows to Burst Balloons
15. Employee Free Time
16. Accounts Merge
17. H-Index
18. Sort List
19. Relative Sort Array
20. Maximum Gap

## 23.7 Greedy - Top 20

1. Jump Game
2. Jump Game II
3. Gas Station
4. Candy
5. Best Time to Buy and Sell Stock II
6. Partition Labels
7. Task Scheduler
8. Non-overlapping Intervals
9. Minimum Number of Arrows to Burst Balloons
10. Queue Reconstruction by Height
11. Hand of Straights
12. Merge Triplets to Form Target Triplet
13. Valid Parenthesis String
14. Remove K Digits
15. Reorganize String
16. Meeting Rooms II
17. Minimum Cost to Hire K Workers
18. Boats to Save People
19. Car Pooling
20. Maximum Units on a Truck

## 23.8 Binary Search - Top 20

1. Binary Search
2. Search Insert Position
3. Search in Rotated Sorted Array
4. Find Minimum in Rotated Sorted Array
5. Find Peak Element
6. First Bad Version
7. Search a 2D Matrix
8. Median of Two Sorted Arrays
9. Koko Eating Bananas
10. Capacity To Ship Packages Within D Days
11. Split Array Largest Sum
12. Find K Closest Elements
13. Time Based Key-Value Store
14. Search in Rotated Sorted Array II
15. Find First and Last Position of Element in Sorted Array
16. Single Element in a Sorted Array
17. Successful Pairs of Spells and Potions
18. Minimized Maximum of Products Distributed to Any Store
19. Magnetic Force Between Two Balls
20. Minimize Max Distance to Gas Station

## 23.9 Depth-First Search - Top 20

1. Number of Islands
2. Max Area of Island
3. Clone Graph
4. Pacific Atlantic Water Flow
5. Surrounded Regions
6. Course Schedule
7. Course Schedule II
8. Word Search
9. Path Sum
10. Path Sum II
11. Binary Tree Maximum Path Sum
12. Diameter of Binary Tree
13. Same Tree
14. Subtree of Another Tree
15. Serialize and Deserialize Binary Tree
16. Decode String
17. Accounts Merge
18. Reconstruct Itinerary
19. Critical Connections in a Network
20. All Paths From Source to Target

## 23.10 Breadth-First Search - Top 20

1. Binary Tree Level Order Traversal
2. Rotting Oranges
3. Word Ladder
4. Minimum Genetic Mutation
5. Open the Lock
6. Shortest Path in Binary Matrix
7. Walls and Gates
8. Perfect Squares
9. 01 Matrix
10. Number of Islands
11. Clone Graph
12. Course Schedule
13. Bus Routes
14. Snakes and Ladders
15. Minimum Knight Moves
16. As Far from Land as Possible
17. Nearest Exit from Entrance in Maze
18. Shortest Bridge
19. Jump Game III
20. Race Car

## 23.11 Matrix - Top 20

1. Set Matrix Zeroes
2. Spiral Matrix
3. Rotate Image
4. Search a 2D Matrix
5. Search a 2D Matrix II
6. Word Search
7. Number of Islands
8. Max Area of Island
9. Surrounded Regions
10. Pacific Atlantic Water Flow
11. Rotting Oranges
12. 01 Matrix
13. Game of Life
14. Toeplitz Matrix
15. Valid Sudoku
16. Shortest Path in Binary Matrix
17. Minimum Path Sum
18. Unique Paths
19. Longest Increasing Path in a Matrix
20. Number of Enclaves

## 23.12 Tree and Binary Tree - Top 20

1. Maximum Depth of Binary Tree
2. Invert Binary Tree
3. Same Tree
4. Symmetric Tree
5. Diameter of Binary Tree
6. Balanced Binary Tree
7. Subtree of Another Tree
8. Binary Tree Level Order Traversal
9. Binary Tree Right Side View
10. Lowest Common Ancestor of a Binary Tree
11. Validate Binary Search Tree
12. Kth Smallest Element in a BST
13. Construct Binary Tree from Preorder and Inorder Traversal
14. Binary Tree Maximum Path Sum
15. Serialize and Deserialize Binary Tree
16. Flatten Binary Tree to Linked List
17. Path Sum
18. Path Sum II
19. Count Complete Tree Nodes
20. Recover Binary Search Tree

## 23.13 Graph Theory - Top 20

1. Clone Graph
2. Course Schedule
3. Course Schedule II
4. Number of Connected Components in an Undirected Graph
5. Graph Valid Tree
6. Redundant Connection
7. Accounts Merge
8. Network Delay Time
9. Cheapest Flights Within K Stops
10. Reconstruct Itinerary
11. Alien Dictionary
12. Minimum Height Trees
13. Critical Connections in a Network
14. Evaluate Division
15. Pacific Atlantic Water Flow
16. Word Ladder
17. Shortest Path in Binary Matrix
18. Min Cost to Connect All Points
19. Find if Path Exists in Graph
20. Detonate the Maximum Bombs

## 23.14 Two Pointers - Top 20

1. Valid Palindrome
2. Two Sum II - Input Array Is Sorted
3. 3Sum
4. 4Sum
5. Container With Most Water
6. Trapping Rain Water
7. Remove Duplicates from Sorted Array
8. Remove Element
9. Move Zeroes
10. Sort Colors
11. Merge Sorted Array
12. Linked List Cycle
13. Palindrome Linked List
14. Reverse String
15. Squares of a Sorted Array
16. Backspace String Compare
17. Partition Labels
18. Minimum Size Subarray Sum
19. Boats to Save People
20. Valid Palindrome II

## 23.15 Sliding Window - Top 20

1. Longest Substring Without Repeating Characters
2. Minimum Window Substring
3. Longest Repeating Character Replacement
4. Permutation in String
5. Find All Anagrams in a String
6. Sliding Window Maximum
7. Minimum Size Subarray Sum
8. Max Consecutive Ones III
9. Fruit Into Baskets
10. Subarrays with K Different Integers
11. Binary Subarrays With Sum
12. Count Number of Nice Subarrays
13. Frequency of the Most Frequent Element
14. Get Equal Substrings Within Budget
15. Grumpy Bookstore Owner
16. Longest Ones After Replacement
17. Maximum Average Subarray I
18. Minimum Operations to Reduce X to Zero
19. Maximize the Confusion of an Exam
20. Longest Subarray of 1s After Deleting One Element

## 23.16 Prefix Sum - Top 20

1. Range Sum Query - Immutable
2. Range Sum Query 2D - Immutable
3. Subarray Sum Equals K
4. Continuous Subarray Sum
5. Contiguous Array
6. Product of Array Except Self
7. Find Pivot Index
8. Maximum Size Subarray Sum Equals K
9. Minimum Operations to Reduce X to Zero
10. Car Pooling
11. Corporate Flight Bookings
12. Plates Between Candles
13. Path Sum III
14. Subarrays Divisible by K
15. Binary Subarrays With Sum
16. Count Number of Nice Subarrays
17. Maximum Sum of Two Non-Overlapping Subarrays
18. Minimum Value to Get Positive Step by Step Sum
19. Sum of Absolute Differences in a Sorted Array
20. Number of Ways to Split Array

## 23.17 Heap and Priority Queue - Top 20

1. Kth Largest Element in an Array
2. Top K Frequent Elements
3. Merge k Sorted Lists
4. Find Median from Data Stream
5. Task Scheduler
6. Meeting Rooms II
7. K Closest Points to Origin
8. Last Stone Weight
9. Reorganize String
10. Smallest Range Covering Elements from K Lists
11. Sliding Window Maximum
12. Trapping Rain Water II
13. IPO
14. The Skyline Problem
15. Minimum Cost to Connect Sticks
16. Single-Threaded CPU
17. Process Tasks Using Servers
18. Kth Smallest Element in a Sorted Matrix
19. Find K Pairs with Smallest Sums
20. Design Twitter

## 23.18 Stack and Monotonic Stack - Top 20

1. Valid Parentheses
2. Min Stack
3. Evaluate Reverse Polish Notation
4. Daily Temperatures
5. Next Greater Element I
6. Next Greater Element II
7. Largest Rectangle in Histogram
8. Trapping Rain Water
9. Basic Calculator
10. Basic Calculator II
11. Decode String
12. Remove K Digits
13. Asteroid Collision
14. Simplify Path
15. Online Stock Span
16. Car Fleet
17. Sum of Subarray Minimums
18. Maximal Rectangle
19. Remove Duplicate Letters
20. Design Browser History

## 23.19 Linked List - Top 20

1. Reverse Linked List
2. Merge Two Sorted Lists
3. Linked List Cycle
4. Linked List Cycle II
5. Remove Nth Node From End of List
6. Reorder List
7. Add Two Numbers
8. Copy List with Random Pointer
9. Merge k Sorted Lists
10. Sort List
11. Palindrome Linked List
12. Intersection of Two Linked Lists
13. Reverse Nodes in k-Group
14. Swap Nodes in Pairs
15. Rotate List
16. Partition List
17. Flatten a Multilevel Doubly Linked List
18. LRU Cache
19. Design Linked List
20. Delete Node in a Linked List

## 23.20 Backtracking - Top 20

1. Subsets
2. Subsets II
3. Permutations
4. Permutations II
5. Combination Sum
6. Combination Sum II
7. Combinations
8. Letter Combinations of a Phone Number
9. Generate Parentheses
10. Word Search
11. N-Queens
12. Sudoku Solver
13. Palindrome Partitioning
14. Restore IP Addresses
15. Word Break II
16. Matchsticks to Square
17. Partition to K Equal Sum Subsets
18. Expression Add Operators
19. Beautiful Arrangement
20. Unique Paths III

## 23.21 Trie - Top 20

1. Implement Trie
2. Design Add and Search Words Data Structure
3. Word Search II
4. Replace Words
5. Map Sum Pairs
6. Search Suggestions System
7. Maximum XOR of Two Numbers in an Array
8. Concatenated Words
9. Word Squares
10. Stream of Characters
11. Prefix and Suffix Search
12. Design Search Autocomplete System
13. Longest Word in Dictionary
14. Longest Word in Dictionary Through Deleting
15. Short Encoding of Words
16. Camelcase Matching
17. Count Pairs With XOR in a Range
18. Sum of Prefix Scores of Strings
19. Implement Magic Dictionary
20. Word Break

## 23.22 Union-Find - Top 20

1. Number of Islands
2. Number of Connected Components in an Undirected Graph
3. Graph Valid Tree
4. Redundant Connection
5. Accounts Merge
6. Sentence Similarity II
7. Satisfiability of Equality Equations
8. Most Stones Removed with Same Row or Column
9. Regions Cut By Slashes
10. Connecting Cities With Minimum Cost
11. Min Cost to Connect All Points
12. The Earliest Moment When Everyone Become Friends
13. Number of Provinces
14. Path With Minimum Effort
15. Swim in Rising Water
16. Similar String Groups
17. Number of Operations to Make Network Connected
18. Checking Existence of Edge Length Limited Paths
19. Bricks Falling When Hit
20. Remove Max Number of Edges to Keep Graph Fully Traversable

## 23.23 Bit Manipulation - Top 20

1. Single Number
2. Single Number II
3. Single Number III
4. Number of 1 Bits
5. Counting Bits
6. Reverse Bits
7. Missing Number
8. Sum of Two Integers
9. Bitwise AND of Numbers Range
10. Maximum XOR of Two Numbers in an Array
11. Subsets
12. Power of Two
13. Power of Four
14. Hamming Distance
15. Total Hamming Distance
16. Find the Difference
17. UTF-8 Validation
18. Integer Replacement
19. Minimum Flips to Make a OR b Equal to c
20. Minimum XOR Sum of Two Arrays

## 23.24 Database and SQL - Top 20

1. Combine Two Tables
2. Second Highest Salary
3. Nth Highest Salary
4. Rank Scores
5. Consecutive Numbers
6. Employees Earning More Than Their Managers
7. Duplicate Emails
8. Customers Who Never Order
9. Department Highest Salary
10. Department Top Three Salaries
11. Trips and Users
12. Game Play Analysis I
13. Game Play Analysis II
14. Game Play Analysis III
15. Game Play Analysis IV
16. Managers with at Least 5 Direct Reports
17. Rising Temperature
18. Delete Duplicate Emails
19. Exchange Seats
20. Human Traffic of Stadium

## 23.25 Design, Data Stream, and Concurrency - Top 20

1. LRU Cache
2. LFU Cache
3. Min Stack
4. Implement Trie
5. Design HashMap
6. Design HashSet
7. Design Add and Search Words Data Structure
8. Find Median from Data Stream
9. Moving Average from Data Stream
10. Time Based Key-Value Store
11. Design Twitter
12. Design Hit Counter
13. Logger Rate Limiter
14. Design Circular Queue
15. Design Browser History
16. Insert Delete GetRandom O(1)
17. Serialize and Deserialize Binary Tree
18. Print in Order
19. Building H2O
20. Design Bounded Blocking Queue

---


